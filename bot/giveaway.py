import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.database import (
    async_session, get_active_giveaways, get_giveaway_by_id,
    enter_giveaway, get_or_create_user, get_giveaway_entries
)

logger = logging.getLogger(__name__)

async def show_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active giveaways to users"""
    async with async_session() as session:
        giveaways = await get_active_giveaways(session)
        
        if not giveaways:
            await update.message.reply_text(
                "🎁 **No Active Giveaways**\n\n"
                "Check back later for new giveaways!",
                parse_mode='Markdown'
            )
            return
        
        for giveaway in giveaways:
            # Check if giveaway has started
            now = datetime.utcnow()
            if now < giveaway.start_time:
                status = "⏳ Starting Soon"
            else:
                status = "🟢 Active"
            
            time_left = giveaway.end_time - now
            days = time_left.days
            hours = time_left.seconds // 3600
            
            text = (
                f"🎁 **{giveaway.title}**\n\n"
                f"📝 {giveaway.description}\n\n"
                f"🏆 **Prize:** {giveaway.prize_description}\n"
                f"👥 **Winners:** {giveaway.number_of_winners}\n"
                f"🎟️ **Entries:** {len(giveaway.entries)}\n"
                f"⏰ **Ends in:** {days}d {hours}h\n"
                f"📊 **Status:** {status}\n\n"
                f"Click below to participate!"
            )
            
            keyboard = [[InlineKeyboardButton(
                "🎉 Participate", 
                callback_data=f"join_{giveaway.id}"
            )]]
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

async def join_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user joining giveaway"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    # Get or create user in database
    async with async_session() as session:
        db_user = await get_or_create_user(session, user)
        
        giveaway_id = int(query.data.split("_")[1])
        giveaway = await get_giveaway_by_id(session, giveaway_id)
        
        if not giveaway:
            await query.edit_message_text("❌ Giveaway not found.")
            return
        
        # Check if giveaway is active and started
        now = datetime.utcnow()
        if now < giveaway.start_time:
            await query.answer("⏳ This giveaway hasn't started yet!", show_alert=True)
            return
        
        if now > giveaway.end_time:
            await query.answer("❌ This giveaway has ended!", show_alert=True)
            return
        
        # Enter user
        entry, status = await enter_giveaway(session, giveaway_id, db_user.id)
        
        if status == "already_entered":
            await query.answer("✅ You're already participating!", show_alert=True)
        elif status == "success":
            await query.answer("🎉 Successfully entered!", show_alert=True)
            await query.edit_message_text(
                f"✅ **You're in!**\n\n"
                f"Giveaway: {giveaway.title}\n"
                f"Your Entry Number: #{entry.entry_number}\n\n"
                f"Good luck! 🍀",
                parse_mode='Markdown'
            )

async def check_giveaway_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check status of a specific giveaway"""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/status <giveaway_id>`\n"
            "Example: `/status 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        giveaway_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid giveaway ID (number).")
        return
    
    async with async_session() as session:
        giveaway = await get_giveaway_by_id(session, giveaway_id)
        
        if not giveaway:
            await update.message.reply_text("❌ Giveaway not found.")
            return
        
        entries = await get_giveaway_entries(session, giveaway_id)
        
        now = datetime.utcnow()
        if now > giveaway.end_time:
            status = "🔴 Ended"
        elif now >= giveaway.start_time:
            status = "🟢 Active"
        else:
            status = "⏳ Not Started"
        
        time_left = giveaway.end_time - now
        if time_left.total_seconds() > 0:
            days = time_left.days
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            time_str = f"{days}d {hours}h {minutes}m"
        else:
            time_str = "Ended"
        
        text = (
            f"🎁 **{giveaway.title}**\n\n"
            f"🆔 ID: `{giveaway.id}`\n"
            f"📊 Status: {status}\n"
            f"🎟️ Total Entries: {len(entries)}\n"
            f"👥 Winners: {giveaway.number_of_winners}\n"
            f"⏰ Time Left: {time_str}\n\n"
            f"🏆 Prize: {giveaway.prize_description}"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

async def my_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's entries"""
    user = update.effective_user
    
    async with async_session() as session:
        db_user = await get_or_create_user(session, user)
        
        from sqlalchemy import select
        from bot.database import GiveawayEntry, Giveaway
        
        result = await session.execute(
            select(GiveawayEntry, Giveaway).join(Giveaway).where(
                GiveawayEntry.user_id == db_user.id
            )
        )
        entries = result.all()
        
        if not entries:
            await update.message.reply_text(
                "🎟️ **Your Entries**\n\n"
                "You haven't joined any giveaways yet.\n"
                "Use /giveaways to see active ones!"
            )
            return
        
        text = "🎟️ **Your Giveaway Entries:**\n\n"
        
        for entry, giveaway in entries:
            status = "🟢 Active" if giveaway.is_active and not giveaway.is_completed else "🔴 Ended"
            text += (
                f"🎁 {giveaway.title}\n"
                f"   Entry #{entry.entry_number} | {status}\n\n"
            )
        
        await update.message.reply_text(text, parse_mode='Markdown')
