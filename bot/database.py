import asyncio
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from bot.config import Config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    language_code = Column(String(10))
    is_bot = Column(Boolean, default=False)
    phone_number = Column(String(20))
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    entries = relationship("GiveawayEntry", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "language_code": self.language_code,
            "is_bot": self.is_bot,
            "phone_number": self.phone_number,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }

class Giveaway(Base):
    __tablename__ = 'giveaways'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    prize_description = Column(Text)
    number_of_winners = Column(Integer, default=1)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    message_id = Column(Integer)
    chat_id = Column(Integer)
    
    entries = relationship("GiveawayEntry", back_populates="giveaway", cascade="all, delete-orphan")
    winners = relationship("Winner", back_populates="giveaway", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "prize_description": self.prize_description,
            "number_of_winners": self.number_of_winners,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
            "is_completed": self.is_completed,
            "total_entries": len(self.entries),
        }

class GiveawayEntry(Base):
    __tablename__ = 'giveaway_entries'
    
    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey('giveaways.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    entered_at = Column(DateTime, default=datetime.utcnow)
    entry_number = Column(Integer)
    
    giveaway = relationship("Giveaway", back_populates="entries")
    user = relationship("User", back_populates="entries")

class Winner(Base):
    __tablename__ = 'winners'
    
    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey('giveaways.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    position = Column(Integer)
    selected_at = Column(DateTime, default=datetime.utcnow)
    
    giveaway = relationship("Giveaway", back_populates="winners")

# Database engine setup - FIXED
if Config.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(Config.DATABASE_URL, echo=False)
else:
    # PostgreSQL with asyncpg
    engine = create_async_engine(Config.DATABASE_URL, echo=False, pool_pre_ping=True)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with async_session() as session:
        yield session

async def get_or_create_user(session: AsyncSession, telegram_user):
    from sqlalchemy import select
    
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            is_bot=telegram_user.is_bot,
        )
        session.add(user)
        await session.commit()
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name
        user.last_activity = datetime.utcnow()
        await session.commit()
    
    return user

async def get_all_users(session: AsyncSession):
    from sqlalchemy import select
    result = await session.execute(select(User))
    return result.scalars().all()

async def get_user_count(session: AsyncSession):
    from sqlalchemy import func
    result = await session.execute(func.count(User.id))
    return result.scalar()

async def create_giveaway(session: AsyncSession, title, description, prize_description, 
                         number_of_winners, start_time, end_time, created_by):
    giveaway = Giveaway(
        title=title,
        description=description,
        prize_description=prize_description,
        number_of_winners=number_of_winners,
        start_time=start_time,
        end_time=end_time,
        created_by=created_by,
        is_active=True,
        is_completed=False
    )
    session.add(giveaway)
    await session.commit()
    await session.refresh(giveaway)
    return giveaway

async def get_active_giveaways(session: AsyncSession):
    from sqlalchemy import select
    result = await session.execute(
        select(Giveaway).where(Giveaway.is_active == True, Giveaway.is_completed == False)
    )
    return result.scalars().all()

async def get_giveaway_by_id(session: AsyncSession, giveaway_id: int):
    from sqlalchemy import select
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    return result.scalar_one_or_none()

async def delete_giveaway(session: AsyncSession, giveaway_id: int):
    giveaway = await get_giveaway_by_id(session, giveaway_id)
    if giveaway:
        await session.delete(giveaway)
        await session.commit()
        return True
    return False

async def enter_giveaway(session: AsyncSession, giveaway_id: int, user_id: int):
    from sqlalchemy import select, func
    
    result = await session.execute(
        select(GiveawayEntry).where(
            GiveawayEntry.giveaway_id == giveaway_id,
            GiveawayEntry.user_id == user_id
        )
    )
    if result.scalar_one_or_none():
        return None, "already_entered"
    
    result = await session.execute(
        select(func.count(GiveawayEntry.id)).where(GiveawayEntry.giveaway_id == giveaway_id)
    )
    entry_number = result.scalar() + 1
    
    entry = GiveawayEntry(
        giveaway_id=giveaway_id,
        user_id=user_id,
        entry_number=entry_number
    )
    session.add(entry)
    await session.commit()
    return entry, "success"

async def get_giveaway_entries(session: AsyncSession, giveaway_id: int):
    from sqlalchemy import select
    result = await session.execute(
        select(GiveawayEntry).where(GiveawayEntry.giveaway_id == giveaway_id)
    )
    return result.scalars().all()

async def get_user_giveaways(session: AsyncSession, user_id: int):
    from sqlalchemy import select
    result = await session.execute(
        select(GiveawayEntry).where(GiveawayEntry.user_id == user_id)
    )
    return result.scalars().all()
