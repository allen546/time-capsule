"""
Time Capsule Database Module

This module provides the SQLAlchemy models and database connection for the application.
"""

import os
import logging
import datetime
import json
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.future import select

# Configure logging
logger = logging.getLogger(__name__)

# Get application directory
app_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(app_dir, 'data')

# Create data directory if it doesn't exist
os.makedirs(data_folder, exist_ok=True)

# Database URL
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(data_folder, 'timecapsule.db')}"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create base class for declarative models
Base = declarative_base()

# Async session factory
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Define models
class User(Base):
    """User model for authentication and profile information."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    profile_data = Column(Text, nullable=True, default="{}")  # JSON data for profile questions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_reset = Column(Boolean, default=False)
    reset_at = Column(DateTime, nullable=True)
    
    # Relationships
    diary_entries = relationship("DiaryEntry", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(uuid='{self.uuid}', name='{self.name}')>"
    
    def to_dict(self):
        """Convert User object to dictionary."""
        profile_data = {}
        if self.profile_data:
            try:
                profile_data = json.loads(self.profile_data)
            except json.JSONDecodeError:
                profile_data = {}
        
        return {
            "uuid": self.uuid,
            "name": self.name,
            "age": self.age,
            "profile_data": profile_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DiaryEntry(Base):
    """Diary entry model."""
    
    __tablename__ = "diary_entries"
    
    id = Column(Integer, primary_key=True)
    entry_uuid = Column(String(36), unique=True, nullable=False, index=True)
    user_uuid = Column(String(36), ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    mood = Column(String(20), nullable=True)
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="diary_entries")
    
    def __repr__(self):
        return f"<DiaryEntry(id={self.id}, title='{self.title}', date='{self.date}')>"
    
    def to_dict(self):
        """Convert DiaryEntry object to dictionary."""
        return {
            "id": self.entry_uuid,
            "title": self.title,
            "content": self.content,
            "date": self.date,
            "mood": self.mood,
            "pinned": self.pinned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Chat(Base):
    """Chat model to store chat sessions."""
    
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True)
    chat_uuid = Column(String(36), unique=True, nullable=False, index=True)
    user_uuid = Column(String(36), ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Chat(chat_uuid='{self.chat_uuid}', title='{self.title}')>"
    
    def to_dict(self):
        """Convert Chat object to dictionary."""
        return {
            "id": self.chat_uuid,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Message(Base):
    """Message model to store individual messages in a chat."""
    
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    message_uuid = Column(String(36), unique=True, nullable=False, index=True)
    chat_uuid = Column(String(36), ForeignKey("chats.chat_uuid", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    sender = Column(String(10), nullable=False)  # 'user' or 'ai'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    chat = relationship("Chat", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(message_uuid='{self.message_uuid}', sender='{self.sender}')>"
    
    def to_dict(self):
        """Convert Message object to dictionary."""
        return {
            "id": self.message_uuid,
            "content": self.content,
            "sender": self.sender,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


async def init_db():
    """Initialize the database by creating all tables."""
    try:
        logger.info(f"Initializing database at {DATABASE_URL}")
        
        # Check if data directory exists and is writable
        if not os.path.exists(data_folder):
            logger.info(f"Creating data directory: {data_folder}")
            os.makedirs(data_folder, exist_ok=True)
        
        # Check if we have write permissions to the data directory
        test_file = os.path.join(data_folder, "write_test.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("Test")
            os.remove(test_file)
            logger.info(f"Data directory is writable: {data_folder}")
        except Exception as e:
            logger.error(f"Data directory is not writable: {str(e)}")
            raise RuntimeError(f"Cannot write to data directory: {data_folder}")
        
        # Create database tables
        logger.info("Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Verify the database was created
        db_path = os.path.join(data_folder, 'timecapsule.db')
        if os.path.exists(db_path):
            logger.info(f"Database file created successfully: {db_path} (Size: {os.path.getsize(db_path)} bytes)")
        else:
            logger.warning(f"Database file not found after initialization: {db_path}")
        
        # Test database connection with a simple query
        logger.info("Testing database connection...")
        async with async_session() as session:
            # Try to get user count
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()
            logger.info(f"Database connection successful. Found {len(users)} users.")
        
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        raise


async def get_session():
    """Get an async session for database operations."""
    async with async_session() as session:
        yield session


# Database access functions
class UserDB:
    """User database operations."""
    
    @staticmethod
    async def get_user_by_uuid(session, uuid):
        """Get a user by UUID."""
        stmt = select(User).where(User.uuid == uuid)
        result = await session.execute(stmt)
        return result.scalars().first()
    
    @staticmethod
    async def create_user(session, uuid, name=None, age=None, profile_data=None):
        """Create a new user."""
        if profile_data and isinstance(profile_data, dict):
            profile_data_json = json.dumps(profile_data)
        else:
            profile_data_json = "{}"
            
        user = User(uuid=uuid, name=name, age=age, profile_data=profile_data_json)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    
    @staticmethod
    async def update_user(session, uuid, name=None, age=None, profile_data=None):
        """Update an existing user."""
        user = await UserDB.get_user_by_uuid(session, uuid)
        if user:
            if name is not None:
                user.name = name
            if age is not None:
                user.age = age
                
            if profile_data is not None and isinstance(profile_data, dict):
                # If we have existing profile data, merge with new data
                existing_data = {}
                if user.profile_data:
                    try:
                        existing_data = json.loads(user.profile_data)
                    except json.JSONDecodeError:
                        existing_data = {}
                
                # Update with new data
                existing_data.update(profile_data)
                user.profile_data = json.dumps(existing_data)
                
            user.updated_at = datetime.datetime.utcnow()
            await session.commit()
            await session.refresh(user)
        return user
    
    @staticmethod
    async def reset_user(session, uuid):
        """Mark a user as reset."""
        user = await UserDB.get_user_by_uuid(session, uuid)
        if user:
            user.is_reset = True
            user.reset_at = datetime.datetime.utcnow()
            await session.commit()
        return user


class DiaryDB:
    """Diary entry database operations."""
    
    @staticmethod
    async def get_entries_by_user(session, user_uuid):
        """Get all diary entries for a user."""
        stmt = select(DiaryEntry).where(DiaryEntry.user_uuid == user_uuid)
        result = await session.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_entry_by_uuid(session, entry_uuid):
        """Get a diary entry by UUID."""
        stmt = select(DiaryEntry).where(DiaryEntry.entry_uuid == entry_uuid)
        result = await session.execute(stmt)
        return result.scalars().first()
    
    @staticmethod
    async def create_entry(session, user_uuid, entry_uuid, title, content, date, mood="calm", pinned=False):
        """Create a new diary entry."""
        entry = DiaryEntry(
            entry_uuid=entry_uuid,
            user_uuid=user_uuid,
            title=title,
            content=content,
            date=date,
            mood=mood,
            pinned=pinned
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry
    
    @staticmethod
    async def update_entry(session, entry_uuid, title=None, content=None, date=None, mood=None, pinned=None):
        """Update an existing diary entry."""
        entry = await DiaryDB.get_entry_by_uuid(session, entry_uuid)
        if entry:
            if title is not None:
                entry.title = title
            if content is not None:
                entry.content = content
            if date is not None:
                entry.date = date
            if mood is not None:
                entry.mood = mood
            if pinned is not None:
                entry.pinned = pinned
            entry.updated_at = datetime.datetime.utcnow()
            await session.commit()
            await session.refresh(entry)
        return entry
    
    @staticmethod
    async def delete_entry(session, entry_uuid):
        """Delete a diary entry."""
        entry = await DiaryDB.get_entry_by_uuid(session, entry_uuid)
        if entry:
            await session.delete(entry)
            await session.commit()
            return True
        return False


class ChatDB:
    """Database operations for Chat model."""
    
    @staticmethod
    async def get_chats_by_user(session, user_uuid):
        """Get all chats for a user."""
        result = await session.execute(
            select(Chat).filter(Chat.user_uuid == user_uuid).order_by(Chat.updated_at.desc())
        )
        chats = result.scalars().all()
        
        # Get message count for each chat
        chat_list = []
        for chat in chats:
            result = await session.execute(
                select(Message).filter(Message.chat_uuid == chat.chat_uuid)
            )
            messages = result.scalars().all()
            chat_dict = chat.to_dict()
            chat_dict['message_count'] = len(messages)
            chat_list.append(chat_dict)
        
        return chat_list
    
    @staticmethod
    async def get_chat(session, chat_uuid):
        """Get a specific chat."""
        result = await session.execute(
            select(Chat).filter(Chat.chat_uuid == chat_uuid)
        )
        chat = result.scalar_one_or_none()
        if chat:
            return chat.to_dict()
        return None
    
    @staticmethod
    async def create_chat(session, chat_uuid, user_uuid, title=None):
        """Create a new chat."""
        chat = Chat(
            chat_uuid=chat_uuid,
            user_uuid=user_uuid,
            title=title or "新对话"
        )
        session.add(chat)
        await session.commit()
        return chat.to_dict()
    
    @staticmethod
    async def delete_chat(session, chat_uuid):
        """Delete a chat."""
        result = await session.execute(
            select(Chat).filter(Chat.chat_uuid == chat_uuid)
        )
        chat = result.scalar_one_or_none()
        if chat:
            await session.delete(chat)
            await session.commit()
            return True
        return False


class MessageDB:
    """Database operations for Message model."""
    
    @staticmethod
    async def get_messages_by_chat(session, chat_uuid):
        """Get all messages for a chat."""
        result = await session.execute(
            select(Message).filter(Message.chat_uuid == chat_uuid).order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [msg.to_dict() for msg in messages]
    
    @staticmethod
    async def create_message(session, message_uuid, chat_uuid, sender_uuid, content, sender_type):
        """Create a new message."""
        message = Message(
            message_uuid=message_uuid,
            chat_uuid=chat_uuid,
            content=content,
            sender=sender_type
        )
        session.add(message)
        
        # Update chat's updated_at
        result = await session.execute(
            select(Chat).filter(Chat.chat_uuid == chat_uuid)
        )
        chat = result.scalar_one_or_none()
        if chat:
            chat.updated_at = datetime.datetime.utcnow()
        
        await session.commit()
        return message.to_dict() 