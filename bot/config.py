import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Admin Configuration - REPLACE WITH YOUR TWO ADMIN TELEGRAM IDs
    ADMIN_IDS = [
        int(os.getenv("ADMIN_ID_1", "123456789")),
        int(os.getenv("ADMIN_ID_2", "987654321")),
    ]
    
    # Database - Auto-detect and fix URL format
    raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///tmp/giveaway_bot.db")
    
    # Fix PostgreSQL URL for async
    if raw_db_url.startswith("postgres://"):
        DATABASE_URL = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
        DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DATABASE_URL = raw_db_url
    
    # Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    # Bot Settings
    BOT_NAME = "Premium Giveaway Bot"
    MAX_GIVEAWAYS = 50
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS
