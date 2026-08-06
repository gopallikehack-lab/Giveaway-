import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationTypes

from bot.config import Config
from bot.database import (
    async_session, create_giveaway, get_active_giveaways, 
    delete_giveaway, get_giveaway_by_id, get_all_users, get_user_count
)

logger = logging.getLogger(__name__)

# Conversation states
(
    ADMIN_MENU,
    CREATE_TITLE,
    CREATE_DESCRIPTION,
    CREATE_PRIZE,
    CREATE_WINNERS,
    CREATE_START_TIME,
    CREATE_END_TIME,
    CREATE_CONFIRM,
    DELETE_CONFIRM,
) = range(9)

def admin_only(func):
    """Decorator to restrict access to admins only"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not Config.is_admin(user_id):
            await update.message.reply_text("⛔ Access Denied. Admin only.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper

# ============== ADMIN PANEL MAIN MENU ==============

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    keyboard = [
        [InlineKeyboardButton("🎁 Create Giveaway", callback_data="admin_create")],
        [InlineKeyboardButton("📋 Active Giveaways", callback_data="admin_list")],
        [InlineKeyboardButton("👥 View All Users", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🗑️ Delete Giveaway", callback_data="admin_delete")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="admin_close")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🔐 **Admin Panel**\n\n"
        f"Welcome, {update.effective_user.first_name}!\n"
        f"Select an option below:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return ADMIN_MENU

# ============== CREATE GIVEAWAY FLOW ==============

@admin_only
async def create_giveaway_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start giveaway creation"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎁 **Create New Giveaway**\n\n"
        "Step 1/6: Enter the **Title** for your giveaway:\n\n"
        "Example: \"iPhone 15 Pro Giveaway!\"",
        parse_mode='Markdown'
    )
    return CREATE_TITLE

@admin_only
async def create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save title and ask for description"""
    context.user_data['giveaway_title'] = update.message.text
    
    await update.message.reply_text(
        "✅ Title saved!\n\n"
        "Step 2/6: Enter the **Description**:\n\n"
        "Explain the rules, requirements, or any important info.",
        parse_mode='Markdown'
    )
    return CREATE_DESCRIPTION

@admin_only
async def create_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save description and ask for prize"""
    context.user_data['giveaway_description'] = update.message.text
    
    await update.message.reply_text(
        "✅ Description saved!\n\n"
        "Step 3/6: Enter the **Prize Description**:\n\n"
        "What will the winner(s) receive?",
        parse_mode='Markdown'
    )
    return CREATE_PRIZE

@admin_only
async def create_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save prize and ask for winners count"""
    context.user_data['giveaway_prize'] = update.message.text
    
    await update.message.reply_text(
        "✅ Prize saved!\n\n"
        "Step 4/6: Enter the **Number of Winners**:\n\n"
        "Example: 1, 2, 5, etc.",
        parse_mode='Markdown'
    )
    return CREATE_WINNERS

@admin_only
async def create_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save winners count and ask for start time"""
    try:
        winners = int(update.message.text)
        if winners < 1:
            raise ValueError("Must be at least 1")
        context.user_data['giveaway_winners'] = winners
        
        await update.message.reply_text(
            "✅ Winners count saved!\n\n"
            "Step 5/6: Enter **Start Time**:\n\n"
            "Format: `YYYY-MM-DD HH:MM`\n"
            "Example: `2024-12-25 10:00`\n\n"
            "Or type 'now' to start immediately.",
            parse_mode='Markdown'
        )
        return CREATE_START_TIME
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number (minimum 1).")
        return CREATE_WINNERS

@admin_only
async def create_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save start time and ask for end time"""
    time_input = update.message.text.lower()
    
    if time_input == 'now':
        start_time = datetime.utcnow()
    else:
        try:
            start_time = datetime.strptime(time_input, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid format. Please use: `YYYY-MM-DD HH:MM`\n"
                "Example: `2024-12-25 10:00`",
                parse_mode='Markdown'
            )
            return CREATE_START_TIME
    
    context.user_data['giveaway_start'] = start_time
    
    await update.message.reply_text(
        "✅ Start time saved!\n\n"
        "Step 6/6: Enter **End Time**:\n\n"
        "Format: `YYYY-MM-DD HH:MM`\n"
        "Example: `2024-12-30 23:59`\n\n"
        "Or type '+7d' for 7 days from start, '+24h' for 24 hours.",
        parse_mode='Markdown'
    )
    return CREATE_END_TIME

@admin_only
async def create_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save end time and show confirmation"""
    time_input = update.message.text.lower()
    start_time = context.user_data['giveaway_start']
    
    if time_input.endswith('d'):
        days = int(time_input[:-1])
        end_time = start_time + timedelta(days=days)
    elif time_input.endswith('h'):
        hours = int(time_input[:-1])
        end_time = start_time + timedelta(hours=hours)
    else:
        try:
            end_time = datetime.strptime(time_input, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid format. Please use: `YYYY-MM-DD HH:MM` or `+7d` or `+24h`",
                parse_mode='Markdown'
            )
            return CREATE_END_TIME
    
    if end_time <= start_time:
        await update.message.reply_text("❌ End time must be after start time!")
        return CREATE_END_TIME
    
    context.user_data['giveaway_end'] = end_time
    
    # Show confirmation
    text = (
        f"🎁 **Confirm Giveaway Creation**\n\n"
        f"**Title:** {context.user_data['giveaway_title']}\n"
        f"**Description:** {context.user_data['giveaway_description'][:100]}...\n"
        f"**Prize:** {context.user_data['giveaway_prize']}\n"
        f"**Winners:** {context.user_data['giveaway_winners']}\n"
        f"**Start:** {start_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"**End:** {end_time.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"Create this giveaway?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Create", callback_data="confirm_create")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_create")],
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CREATE_CONFIRM

@admin_only
async def confirm_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create the giveaway in database"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_create":
        await query.edit_message_text("❌ Giveaway creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END
    
    async with async_session() as session:
        giveaway = await create_giveaway(
            session,
            title=context.user_data['giveaway_title'],
            description=context.user_data['giveaway_description'],
            prize_description=context.user_data['giveaway_prize'],
            number_of_winners=context.user_data['giveaway_winners'],
            start_time=context.user_data['giveaway_start'],
            end_time=context.user_data['giveaway_end'],
            created_by=update.effective_user.id
        )
        
        await query.edit_message_text(
            f"✅ **Giveaway Created Successfully!**\n\n"
            f"ID: `{giveaway.id}`\n"
            f"Use /giveaways to see active giveaways.",
            parse_mode='Markdown'
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# ============== LIST GIVEAWAYS ==============

async def list_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all active giveaways"""
    query = update.callback_query
    if query:
        await query.answer()
    
    async with async_session() as session:
        giveaways = await get_active_giveaways(session)
        
        if not giveaways:
            text = "📋 No active giveaways found."
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        else:
            text = "📋 **Active Giveaways:**\n\n"
            keyboard = []
            
            for gw in giveaways:
                text += f"🎁 **{gw.title}**\n"
                text += f"ID: `{gw.id}` | Entries: {len(gw.entries)}\n"
                text += f"Winners: {gw.number_of_winners}\n"
                text += f"Ends: {gw.end_time.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(f"🗑️ Delete {gw.id}", callback_data=f"del_{gw.id}")
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")])
        
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============== VIEW ALL USERS ==============

async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all users with full details"""
    query = update.callback_query
    if query:
        await query.answer()
    
    async with async_session() as session:
        users = await get_all_users(session)
        total_count = await get_user_count(session)
        
        # Create detailed user report
        text = f"👥 **All Users Report**\n"
        text += f"Total Users: `{total_count}`\n\n"
        text += "📊 **User Details:**\n\n"
        
        for idx, user in enumerate(users[:20], 1):  # Show first 20
            text += (
                f"{idx}. **{user.first_name or 'N/A'} {user.last_name or ''}**\n"
                f"   🆔 ID: `{user.telegram_id}`\n"
                f"   👤 Username: @{user.username or 'N/A'}\n"
                f"   🌐 Lang: {user.language_code or 'N/A'}\n"
                f"   📅 Joined: {user.joined_at.strftime('%Y-%m-%d')}\n\n"
            )
        
        if len(users) > 20:
            text += f"_...and {len(users) - 20} more users_\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============== STATISTICS ==============

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        total_users = await get_user_count(session)
        giveaways = await get_active_giveaways(session)
        
        total_entries = sum(len(gw.entries) for gw in giveaways)
        
        text = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: `{total_users}`\n"
            f"🎁 Active Giveaways: `{len(giveaways)}`\n"
            f"🎟️ Total Entries: `{total_entries}`\n\n"
            f"🤖 Bot: @{context.bot.username}\n"
            f"✅ Status: Online"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============== DELETE GIVEAWAY ==============

async def delete_giveaway_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show delete giveaway menu"""
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        giveaways = await get_active_giveaways(session)
        
        if not giveaways:
            await query.edit_message_text(
                "❌ No active giveaways to delete.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
            )
            return
        
        keyboard = []
        for gw in giveaways:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {gw.id}: {gw.title[:30]}...", 
                callback_data=f"delete_{gw.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="admin_back")])
        
        await query.edit_message_text(
            "🗑️ **Delete Giveaway**\n\nSelect a giveaway to delete:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and delete giveaway"""
    query = update.callback_query
    await query.answer()
    
    giveaway_id = int(query.data.split("_")[1])
    context.user_data['delete_giveaway_id'] = giveaway_id
    
    async with async_session() as session:
        giveaway = await get_giveaway_by_id(session, giveaway_id)
        if not giveaway:
            await query.edit_message_text("❌ Giveaway not found.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_del"),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_back")
            ]
        ]
        
        await query.edit_message_text(
            f"⚠️ **Confirm Deletion**\n\n"
            f"Are you sure you want to delete:\n\n"
            f"🎁 **{giveaway.title}**\n"
            f"🆔 ID: `{giveaway.id}`\n"
            f"🎟️ Entries: {len(giveaway.entries)}\n\n"
            f"This action cannot be undone!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def execute_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute giveaway deletion"""
    query = update.callback_query
    await query.answer()
    
    giveaway_id = context.user_data.get('delete_giveaway_id')
    if not giveaway_id:
        await query.edit_message_text("❌ Error: No giveaway selected.")
        return
    
    async with async_session() as session:
        success = await delete_giveaway(session, giveaway_id)
        if success:
            await query.edit_message_text(
                f"✅ Giveaway `{giveaway_id}` has been deleted.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Failed to delete giveaway.")
    
    context.user_data.pop('delete_giveaway_id', None)

# ============== CALLBACK HANDLER ==============

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_create":
        return await create_giveaway_start(update, context)
    elif data == "admin_list":
        await list_giveaways(update, context)
    elif data == "admin_users":
        await view_users(update, context)
    elif data == "admin_stats":
        await show_stats(update, context)
    elif data == "admin_delete":
        await delete_giveaway_menu(update, context)
    elif data == "admin_back":
        return await admin_panel(update, context)
    elif data == "admin_close":
        await query.edit_message_text("🔒 Admin panel closed. Use /admin to reopen.")
    elif data.startswith("delete_"):
        await confirm_delete(update, context)
    elif data == "confirm_del":
        await execute_delete(update, context)
    elif data == "confirm_create":
        return await confirm_create(update, context)
    elif data == "cancel_create":
        return await confirm_create(update, context)

def get_admin_conversation_handler():
    """Return the admin conversation handler"""
    from telegram.ext import ConversationHandler
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('admin', admin_panel),
            CallbackQueryHandler(admin_callback_handler, pattern='^admin_'),
        ],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_callback_handler)],
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_title)],
            CREATE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_description)],
            CREATE_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_prize)],
            CREATE_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_winners)],
            CREATE_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_start_time)],
            CREATE_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_end_time)],
            CREATE_CONFIRM: [CallbackQueryHandler(confirm_create)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled."))],
  )
