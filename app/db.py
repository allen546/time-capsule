"""
Time Capsule Database Module

This module provides the SQLAlchemy models and database connection for the application.
"""

import os
import logging
import datetime
import json
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, create_engine, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.future import select
from sqlalchemy.sql import func
import uuid

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
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
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


class ChatSession(Base):
    """Chat session model for storing chat conversations."""
    
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True)
    session_uuid = Column(String(36), unique=True, nullable=False, index=True)
    user_uuid = Column(String(36), ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False, default="New Chat")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, title='{self.title}')>"
    
    def to_dict(self):
        """Convert ChatSession object to dictionary."""
        return {
            "id": self.session_uuid,
            "user_uuid": self.user_uuid,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": 0  # Don't try to access self.messages, will be set separately if needed
        }


class ChatMessage(Base):
    """Chat message model for storing individual messages in a chat session."""
    
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True)
    message_uuid = Column(String(36), unique=True, nullable=False, index=True)
    session_uuid = Column(String(36), ForeignKey("chat_sessions.session_uuid", ondelete="CASCADE"), nullable=False)
    is_user = Column(Boolean, default=True)  # True if message is from user, False if from AI
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, is_user={self.is_user})>"
    
    def to_dict(self):
        """Convert ChatMessage object to dictionary."""
        return {
            "id": self.message_uuid,
            "session_id": self.session_uuid,
            "is_user": self.is_user,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Contact(Base):
    """Contact model for storing user's contacts."""
    
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    user_uuid = Column(String(36), ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    relation = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="contacts")
    
    def __repr__(self):
        return f"<Contact(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        """Convert Contact object to dictionary."""
        return {
            "id": self.uuid,
            "name": self.name,
            "relation": self.relation,
            "phone": self.phone,
            "address": self.address,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
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
        user = User(
            uuid=uuid,
            name=name,
            age=age,
            profile_data=json.dumps(profile_data) if profile_data else None,
            created_at=datetime.datetime.utcnow()
        )
        session.add(user)
        await session.commit()
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
    
    @staticmethod
    async def get_all_users(session):
        """Get all users (admin only)."""
        query = select(User).order_by(User.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def delete_user(session, uuid):
        """Delete a user (admin only)."""
        user = await UserDB.get_user_by_uuid(session, uuid)
        if user:
            await session.delete(user)
            await session.commit()
            return True
        return False


class DiaryDB:
    """Diary database operations."""
    
    @staticmethod
    async def get_entries_by_user(session, user_uuid):
        """Get all diary entries for a user."""
        stmt = select(DiaryEntry).where(DiaryEntry.user_uuid == user_uuid).order_by(DiaryEntry.created_at.desc())
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
    
    @staticmethod
    async def delete_entries_by_user(session, user_uuid):
        """Delete all diary entries for a specific user (admin only)."""
        query = delete(DiaryEntry).where(DiaryEntry.user_uuid == user_uuid)
        await session.execute(query)
        await session.commit()
        return True


class ChatDB:
    """Chat database operations."""
    
    @staticmethod
    async def get_sessions_by_user(session, user_uuid):
        """Get all chat sessions for a user."""
        stmt = select(ChatSession).where(ChatSession.user_uuid == user_uuid).order_by(ChatSession.updated_at.desc())
        result = await session.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_session_by_uuid(session, session_uuid):
        """Get a chat session by UUID."""
        stmt = select(ChatSession).where(ChatSession.session_uuid == session_uuid)
        result = await session.execute(stmt)
        return result.scalars().first()
    
    @staticmethod
    async def create_session(session, user_uuid, session_uuid=None):
        """Create a new chat session."""
        if not session_uuid:
            session_uuid = str(uuid.uuid4())
        
        chat_session = ChatSession(
            session_uuid=session_uuid,
            user_uuid=user_uuid,
            created_at=datetime.datetime.utcnow()
        )
        session.add(chat_session)
        await session.commit()
        return chat_session
    
    @staticmethod
    async def get_messages_by_session(session, session_uuid, limit=None):
        """Get messages for a chat session."""
        query = select(ChatMessage).where(ChatMessage.session_uuid == session_uuid).order_by(ChatMessage.created_at)
        
        if limit:
            query = query.limit(limit)
            
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def add_message(session, session_uuid, message_uuid, content, is_user=True):
        """Add a new message to a chat session."""
        message = ChatMessage(
            message_uuid=message_uuid,
            session_uuid=session_uuid,
            is_user=is_user,
            content=content,
            created_at=datetime.datetime.utcnow()
        )
        session.add(message)
        
        # Update session's updated_at timestamp
        chat_session = await ChatDB.get_session_by_uuid(session, session_uuid)
        if chat_session:
            chat_session.updated_at = datetime.datetime.utcnow()
        
        await session.commit()
        return message
    
    @staticmethod
    async def delete_session(session, session_uuid):
        """Delete a chat session and its messages."""
        # First delete all messages for this session
        delete_messages_query = delete(ChatMessage).where(ChatMessage.session_uuid == session_uuid)
        await session.execute(delete_messages_query)
        
        # Then delete the session itself
        delete_session_query = delete(ChatSession).where(ChatSession.session_uuid == session_uuid)
        await session.execute(delete_session_query)
        
        await session.commit()
        return True
    
    @staticmethod
    async def get_all_sessions(session):
        """Get all chat sessions (admin only)."""
        query = select(ChatSession).order_by(ChatSession.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def count_messages_by_session(session, session_uuid):
        """Count the number of messages in a chat session."""
        query = select(func.count()).select_from(ChatMessage).where(ChatMessage.session_uuid == session_uuid)
        result = await session.execute(query)
        return result.scalar()

    @staticmethod
    async def delete_all_sessions_by_user(session, user_uuid):
        """Delete all chat sessions and messages for a specific user (admin only)."""
        # Get all sessions for the user
        sessions = await ChatDB.get_sessions_by_user(session, user_uuid)
        
        # Delete each session and its associated messages
        for chat_session in sessions:
            await ChatDB.delete_session(session, chat_session.session_uuid)
            
        return True


class ContactDB:
    """Contact database operations."""
    
    @staticmethod
    async def get_contacts_by_user(session, user_uuid):
        """Get all contacts for a user."""
        stmt = select(Contact).where(Contact.user_uuid == user_uuid)
        result = await session.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_contact_by_uuid(session, uuid):
        """Get a contact by UUID."""
        stmt = select(Contact).where(Contact.uuid == uuid)
        result = await session.execute(stmt)
        return result.scalars().first()
    
    @staticmethod
    async def get_contact(session, contact_uuid):
        """Get a contact by UUID - Alias for get_contact_by_uuid."""
        return await ContactDB.get_contact_by_uuid(session, contact_uuid)
    
    @staticmethod
    async def create_contact(session, uuid, user_uuid, name, relation, phone, address=None, notes=None):
        """Create a new contact."""
        contact = Contact(
            uuid=uuid,
            user_uuid=user_uuid,
            name=name,
            relation=relation,
            phone=phone,
            address=address,
            notes=notes
        )
        session.add(contact)
        await session.commit()
        await session.refresh(contact)
        return contact
    
    @staticmethod
    async def update_contact(session, uuid, name=None, relation=None, phone=None, address=None, notes=None):
        """Update an existing contact."""
        contact = await ContactDB.get_contact_by_uuid(session, uuid)
        if contact:
            if name is not None:
                contact.name = name
            if relation is not None:
                contact.relation = relation
            if phone is not None:
                contact.phone = phone
            if address is not None:
                contact.address = address
            if notes is not None:
                contact.notes = notes
            contact.updated_at = datetime.datetime.utcnow()
            await session.commit()
            await session.refresh(contact)
        return contact
    
    @staticmethod
    async def delete_contact(session, uuid):
        """Delete a contact."""
        contact = await ContactDB.get_contact_by_uuid(session, uuid)
        if contact:
            await session.delete(contact)
            await session.commit()
            return True
        return False 