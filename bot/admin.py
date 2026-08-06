import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, 
    MessageHandler, CallbackQueryHandler, filters
)

from bot.config import Config
from bot.database import (
    async_session, create_giveaway, get_active_giveaways, 
    delete_giveaway, get_giveaway_by_id, get_all_users, get_user_count
)

logger = logging.getLogger(__name__)

# Conversation states (using integers, not ConversationTypes)
ADMIN_MENU = 0
CREATE_TITLE = 1
CREATE_DESCRIPTION = 2
CREATE_PRIZE = 3
CREATE_WINNERS = 4
CREATE_START_TIME = 5
CREATE_END_TIME = 6
CREATE_CONFIRM = 7

def admin_only(func):
    """Decorator to restrict access to admins only"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not Config.is_admin(user_id):
            if update.message:
                await update.message.reply_text("⛔ Access Denied. Admin only.")
            elif update.callback_query:
                await update.callback_query.answer("⛔ Access Denied!")
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
        await update.message.reply_text(text, reply_markup=reply_markup,
