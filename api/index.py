import os
import logging
import asyncio
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application

from bot.config import Config
from bot.database import init_db
from bot.handlers import setup_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    
    # Validate token
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        raise ValueError("BOT_TOKEN environment variable is required")
    
    # Initialize bot
    bot_app = Application.builder().token(Config.BOT_TOKEN).build()
    setup_handlers(bot_app)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    await bot_app.initialize()
    await bot_app.start()
    logger.info("Bot started successfully!")
    
    # Set webhook if URL provided
    if Config.WEBHOOK_URL:
        webhook_url = Config.WEBHOOK_URL.rstrip('/') + '/'
        await bot_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    
    yield
    
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {
        "status": "Premium Giveaway Bot Running",
        "version": "2.0",
        "database": "PostgreSQL" if "postgresql" in Config.DATABASE_URL else "SQLite",
        "powered_by": "Venice AI"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "bot": "running"}
