import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.config import Config
from bot.database import init_db, get_or_create_user
from bot.admin import (
    admin_panel, admin_callback_handler, get_admin_conversation_handler,
    CREATE_TITLE, CREATE_DESCRIPTION, CREATE_PRIZE, CREATE_WINNERS,
    CREATE_START_TIME, CREATE_END_TIME, CREATE_CONFIRM, confirm_create_callback
)
from bot.giveaway import show_giveaways, join_giveaway, check_giveaway_status, my_entries

logger = logging.getLogger(__name__)

async def start(update: Update, context):
    """Handle /start command"""
    user = update.effective_user
    
    from bot.database import async_session
    async with async_session() as session:
        await get_or_create_user(session, user)
    
    welcome_text = (
        f"👋 **Welcome to {Config.BOT_NAME}!**\n\n"
        f"Hello {user.first_name}! 🎉\n\n"
        f"🎁 Participate in exciting giveaways\n"
        f"🏆 Win amazing prizes\n"
        f"📱 Get notified when you win\n\n"
        f"**Available Commands:**\n"
        f"/giveaways - View active giveaways\n"
        f"/myentries - Check your entries\n"
        f"/status <id> - Check giveaway status\n"
        f"/help - Show help\n\n"
    )
    
    if Config.is_admin(user.id):
        welcome_text += f"🔐 **Admin Commands:**\n/admin - Open admin panel\n\n"
    
    welcome_text += "🎉 Good luck!"
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context):
    """Handle /help command"""
    help_text = (
        f"📖 **{Config.BOT_NAME} Help**\n\n"
        f"**User Commands:**\n"
        f"/start - Start the bot\n"
        f"/giveaways - View active giveaways\n"
        f"/myentries - Check your entries\n"
        f"/status <id> - Check giveaway status\n"
        f"/help - Show this help\n\n"
    )
    
    if Config.is_admin(update.effective_user.id):
        help_text += (
            f"🔐 **Admin Commands:**\n"
            f"/admin - Open admin panel\n\n"
            f"**Admin Panel Features:**\n"
            f"• Create giveaways with full details\n"
            f"• View all users with complete info\n"
            f"• Delete giveaways\n"
            f"• View statistics\n"
        )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel_conversation(update: Update, context):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled.")
    return -1

def setup_handlers(application: Application):
    """Setup all handlers"""
    import asyncio
    asyncio.create_task(init_db())
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("giveaways", show_giveaways))
    application.add_handler(CommandHandler("myentries", my_entries))
    application.add_handler(CommandHandler("status", check_giveaway_status))
    
    admin_conv_handler = get_admin_conversation_handler()
    application.add_handler(admin_conv_handler)
    
    application.add_handler(CallbackQueryHandler(join_giveaway, pattern="^join_"))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_|delete_|confirm_|cancel_)"))
    
    application.add_error_handler(error_handler)

async def error_handler(update: Update, context):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ An error occurred. Please try again later.")
