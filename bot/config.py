import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Admin Configuration - REPLACE WITH YOUR TWO ADMIN TELEGRAM IDs
    ADMIN_IDS = [
        int(os.getenv("ADMIN_ID_1", "123456789")),  # Replace with first admin TG ID
        int(os.getenv("ADMIN_ID_2", "987654321")),  # Replace with second admin TG ID
    ]
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///giveaway_bot.db")
    
    # Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    # Bot Settings
    BOT_NAME = "Premium Giveaway Bot"
    MAX_GIVEAWAYS = 50  # Max active giveaways
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is an admin"""
        return user_id in cls.ADMIN_IDS
