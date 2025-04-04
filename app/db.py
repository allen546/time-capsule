from tortoise import fields, models, Tortoise
from typing import List, Optional, Literal, Dict, Any
import datetime
import uuid
import json
from enum import Enum


class MessageSender(str, Enum):
    """Enum for message sender types."""
    USER = "USER"
    BOT = "BOT"


class User(models.Model):
    """User model for authentication and profile information."""
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=128)
    real_name = fields.CharField(max_length=50, description="User's real name (Chinese)")
    age = fields.IntField()
    basic_data = fields.TextField(null=True, description="Optional basic data about the user")
    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)
    
    # Relationships
    conversation: fields.ReverseRelation["Conversation"]
    profiles: fields.ReverseRelation["UserProfile"]
    
    class Meta:
        table = "users"
    
    def __str__(self):
        return f"{self.username} ({self.real_name})"


class UserProfile(models.Model):
    """Model to store extended user profile data for the Time Capsule application."""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.ForeignKeyField("models.User", related_name="profiles")
    # Store profile data as JSON
    data_json = fields.TextField(description="JSON-encoded profile data")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    class Meta:
        table = "user_profiles"
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get profile data as a dictionary."""
        if not self.data_json:
            return {}
        try:
            return json.loads(self.data_json)
        except json.JSONDecodeError:
            return {}
    
    @data.setter
    def data(self, value: Dict[str, Any]):
        """Set profile data from a dictionary."""
        self.data_json = json.dumps(value)


class Conversation(models.Model):
    """Model to represent a conversation thread between a user and the chatbot."""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user = fields.OneToOneField("models.User", related_name="conversation")
    title = fields.CharField(max_length=255, description="Title of the conversation")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    # Relationships
    messages: fields.ReverseRelation["Message"]
    
    class Meta:
        table = "conversations"
    
    def __str__(self):
        return f"Conversation {self.id} - {self.title} ({self.user.username})"


class Message(models.Model):
    """Model to store individual messages within a conversation."""
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    conversation = fields.ForeignKeyField("models.Conversation", related_name="messages")
    # Using a string field with choices to represent the sender (user or bot)
    sender = fields.CharEnumField(MessageSender, default=MessageSender.USER)
    content = fields.TextField(description="Content of the message")
    timestamp = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "messages"
        ordering = ["timestamp"]  # Messages ordered by time
    
    def __str__(self):
        return f"Message {self.id} - From {self.sender} at {self.timestamp}"


async def init_db():
    """Initialize the database connection."""
    await Tortoise.init(
        db_url="sqlite://db.sqlite3",
        modules={"models": ["app.db"]}
    )
    # Generate the schema
    await Tortoise.generate_schemas()


async def close_db():
    """Close the database connection."""
    await Tortoise.close_connections()


# Helper functions for user profiles
async def get_user_profile(user_id: int) -> Optional[UserProfile]:
    """
    Get a user's profile.
    
    Args:
        user_id: The user's ID
        
    Returns:
        The UserProfile object or None if not found
    """
    return await UserProfile.filter(user_id=user_id).first()


async def create_user_profile(user_id: int, profile_data: Dict[str, Any]) -> UserProfile:
    """
    Create a new user profile.
    
    Args:
        user_id: The user's ID
        profile_data: Dictionary of profile data
        
    Returns:
        The newly created UserProfile object
    """
    user = await User.get(id=user_id)
    profile = await UserProfile.create(user=user)
    profile.data = profile_data
    await profile.save()
    return profile 