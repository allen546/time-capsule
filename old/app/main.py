"""
Time Capsule API Documentation
==============================

This API provides endpoints for managing user accounts, conversations, and messages
in the Time Capsule application - a platform for simulating conversations with your past self.

Authentication
-------------
All API endpoints (except registration and login) require authentication using a Bearer token.
Include the token in the Authorization header as: `Authorization: Bearer <token>`.

API Endpoints
------------

Authentication:
- POST /api/users/login
  - Login and get access token
  - Request: {"username": "string", "password": "string"}
  - Response: {"access_token": "string", "token_type": "bearer"}

User Management:
- POST /api/users/register
  - Register a new user
  - Request: {"username": "string", "password_hash": "string", "real_name": "string", "age": int, "basic_data": "string"}
  - Response: User data with access token

- GET /api/users/me
  - Get current user profile
  - Response: User data (excluding password)

Conversation Management:
- GET /api/conversation
  - Get the user's conversation with all messages
  - Response: Conversation data with messages array
  - Note: A conversation is automatically created if one doesn't exist

- DELETE /api/conversation
  - Delete the user's conversation and all its messages
  - Response: {"message": "Conversation deleted successfully"}

Message Management:
- POST /api/conversation/messages
  - Add a message to the user's conversation
  - Request: {"sender": "USER|BOT", "content": "string"}
  - Response: Created message data
  - Note: A conversation is automatically created if one doesn't exist

- POST /api/conversation/chat
  - Send a message to the conversation and get an AI response
  - Request: {"message": "string", "language": "zh|en"}
  - Response: {"success": true, "message": {message_object}}
  - Note: A conversation is automatically created if one doesn't exist
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import json
import functools
import uuid
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Fix for bcrypt version error
import bcrypt
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="passlib.handlers.bcrypt")
# Monkey patch __about__ if it doesn't exist
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type('obj', (object,), {"__version__": bcrypt.__version__})

from sanic import Sanic, response
from sanic.request import Request
from sanic.response import HTTPResponse, json as json_response, empty
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.db import User, Conversation, Message, MessageSender, init_db, close_db
from app.models import process_questionnaire_answers, update_user_profile
from app.questionnaire import process_questionnaire_text, get_questionnaire_as_json
from tortoise.exceptions import ValidationError

# Security configurations
SECRET_KEY = os.getenv("JWT_SECRET", "YOUR_SECRET_KEY_FOR_TESTING")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
# Set DEV_MODE from environment (defaults to True for development)
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

# Initialize Sanic app
app = Sanic("TimeCapsuleAPI")

# Configure CORS
@app.middleware("response")
async def add_cors_headers(request, response):
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "3600"
    })

# Configure static file serving
app.static("/static", "./static", name="static_files")
app.static("/", "./static/index.html", name="index")

# Security utilities
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helper functions for authentication
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(username: str, password: str):
    user = await User.get_or_none(username=username)
    if not user or not verify_password(password, user.password_hash):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.replace('Bearer ', '')
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    user = await User.get_or_none(username=username)
    return user


def login_required(f):
    @functools.wraps(f)
    async def decorated_function(request, *args, **kwargs):
        user = await get_current_user(request)
        if user is None:
            return json_response({"error": "Not authorized"}, status=401)
        
        # Add user to request context
        request.ctx.user = user
        return await f(request, *args, **kwargs)
    return decorated_function


def dev_only(f):
    """Decorator to restrict access to development mode only."""
    @functools.wraps(f)
    async def decorated_function(request, *args, **kwargs):
        if not DEV_MODE:
            return json_response({"error": "This endpoint is only available in development mode"}, status=403)
        return await f(request, *args, **kwargs)
    return decorated_function


# Helper functions for conversation management
async def format_conversation(conversation, include_messages=False):
    """Format a conversation for API response."""
    result = {
        "id": str(conversation.id),
        "user_id": conversation.user_id,
        "created_at": str(conversation.created_at),
        "updated_at": str(conversation.updated_at)
    }
    
    if include_messages:
        messages = await Message.filter(conversation_id=conversation.id).order_by("timestamp")
        result["messages"] = [await format_message(msg) for msg in messages]
    
    return result


async def format_message(message):
    """Format a message for API response."""
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender": message.sender,  # This will be the string value of the enum
        "content": message.content,
        "timestamp": str(message.timestamp)
    }


async def get_authorized_conversation(user_id):
    """Get a conversation for the specified user."""
    try:
        user = await User.get(id=user_id)
        conversation = await Conversation.get(user=user)
        return conversation
    except (Conversation.DoesNotExist, ValidationError):
        return None


async def create_conversation(user_id):
    """Create a new conversation for a user if one doesn't exist."""
    user = await User.get_or_none(id=user_id)
    if not user:
        return None
    
    # Check if user already has a conversation
    existing_conversation = await Conversation.filter(user_id=user_id).first()
    
    if existing_conversation:
        # Return existing conversation
        return existing_conversation
    
    # Create new conversation
    conversation = await Conversation.create(
        user=user
    )
    return conversation


async def add_message_to_conversation(user_id, sender, content):
    """Add a new message to a user's conversation."""
    try:
        user = await User.get(id=user_id)
        conversation = await Conversation.get(user=user)
        
        message = await Message.create(
            conversation=conversation,
            sender=sender,
            content=content
        )
        
        # Update the conversation's updated_at timestamp
        conversation.updated_at = datetime.now()
        await conversation.save()
        
        return message
    except (User.DoesNotExist, Conversation.DoesNotExist, ValidationError):
        return None


# Startup and shutdown events
@app.listener('before_server_start')
async def setup_db(app, loop):
    await init_db()
    
    # Register API routes
    from app.api import register_all_routes
    register_all_routes(app)


@app.listener('after_server_stop')
async def close_connection(app, loop):
    await close_db()


# Authentication routes
@app.post("/api/users/login")
async def login_for_access_token(request):
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return json_response({"error": "Missing username or password"}, status=400)
    
    user = await authenticate_user(username, password)
    if not user:
        return json_response({"error": "Invalid username or password"}, status=401)
    
    token_data = {"sub": user.username}
    access_token = create_access_token(token_data)
    return json_response({"access_token": access_token, "token_type": "bearer"})


# User routes
@app.post("/api/users/register")
async def create_user(request):
    data = request.json
    
    # Validate required fields
    required_fields = ["username", "password_hash", "real_name", "age"]
    for field in required_fields:
        if field not in data:
            return json_response({"error": f"Missing required field: {field}"}, status=400)
    
    # Check if username exists
    if await User.filter(username=data["username"]).exists():
        return json_response({"error": "Username already registered"}, status=400)
    
    # Create user
    user_data = {
        "username": data["username"],
        "password_hash": get_password_hash(data["password_hash"]),
        "real_name": data["real_name"],
        "age": data["age"],
        "basic_data": data.get("basic_data")
    }
    
    user = await User.create(**user_data)
    
    # Generate token
    token_data = {"sub": user.username}
    access_token = create_access_token(token_data)
    
    # Create response without password
    response_data = {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "age": user.age,
        "basic_data": user.basic_data,
        "created_at": str(user.created_at),
        "modified_at": str(user.modified_at),
        "access_token": access_token,
        "token_type": "bearer"
    }
    
    return json_response(response_data)


@app.get("/api/users/me")
@login_required
async def get_user_profile(request):
    user = request.ctx.user
    return json_response({
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "age": user.age,
        "basic_data": user.basic_data,
        "created_at": str(user.created_at),
        "modified_at": str(user.modified_at)
    })


# Conversation routes
@app.get("/api/conversation")
@login_required
async def retrieve_user_conversation(request):
    """Get the user's conversation with messages."""
    user = request.ctx.user
    
    # Get conversation if it exists
    conversation = await get_authorized_conversation(user.id)
    if not conversation:
        # Auto-create a conversation if one doesn't exist
        conversation = await create_conversation(user.id)
        if not conversation:
            return json_response({"error": "Failed to create conversation"}, status=500)
    
    return json_response(await format_conversation(conversation, include_messages=True))


@app.delete("/api/conversation")
@login_required
async def permanently_remove_conversation(request):
    """Delete the user's conversation and all its messages."""
    user = request.ctx.user
    
    # Get conversation if it exists
    conversation = await get_authorized_conversation(user.id)
    if not conversation:
        return json_response({"error": "No conversation found"}, status=404)
    
    # Delete all messages first (need to do this explicitly due to foreign key constraints)
    await Message.filter(conversation_id=conversation.id).delete()
    
    # Then delete the conversation
    await conversation.delete()
    
    return json_response({"message": "Conversation deleted successfully"})


# Message routes
@app.post("/api/conversation/messages")
@login_required
async def create_new_conversation_message(request):
    """Add a new message to the user's conversation."""
    user = request.ctx.user
    data = request.json
    
    # Get conversation if it exists or create one
    conversation = await get_authorized_conversation(user.id)
    if not conversation:
        conversation = await create_conversation(user.id)
        if not conversation:
            return json_response({"error": "Failed to create conversation"}, status=500)
    
    # Validate required fields
    if "sender" not in data or "content" not in data:
        return json_response({"error": "Missing sender or content"}, status=400)
    
    # Inner function to handle message creation
    async def process_message_creation(user_id, sender_value, content_value):
        try:
            # Validate sender
            sender_enum = MessageSender(sender_value)
            
            # Add message using the existing helper function
            new_message = await add_message_to_conversation(
                user_id=user_id,
                sender=sender_enum,
                content=content_value
            )
            
            if not new_message:
                return None, "Failed to add message"
            
            return new_message, None
        except ValueError:
            return None, f"Invalid sender value. Must be one of: {', '.join([s.value for s in MessageSender])}"
    
    # Use the inner function to create the message
    message, error = await process_message_creation(
        user_id=user.id,
        sender_value=data["sender"],
        content_value=data["content"]
    )
    
    if error:
        return json_response({"error": error}, status=400)
    
    return json_response(await format_message(message))


# User profile routes
@app.post("/api/users/profile/questionnaire")
@login_required
async def update_profile_from_questionnaire(request: Request):
    """Update user profile from questionnaire answers"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return json_response(
                {"message": "User not authenticated"},
                status=401
            )
            
        data = await request.json()
        if not data:
            return json_response(
                {"message": "No data provided"},
                status=400
            )
            
        if "free_text" in data:
            # Process free-form text
            structured_data = process_questionnaire_text(data["free_text"])
        elif "answers" in data:
            # Process structured answers
            structured_data = process_questionnaire_answers(data["answers"])
        else:
            return json_response(
                {"message": "Invalid data format"},
                status=400
            )
        
        # Get existing profile
        user_profile = await get_user_profile(user_id)
        
        if not user_profile:
            # Create new profile
            await create_user_profile(user_id, structured_data)
        else:
            # Update existing profile
            profile_data = user_profile.data
            updated_data = update_user_profile(profile_data, structured_data)
            user_profile.data = updated_data
            await user_profile.save()
        
        return json_response(
            {"message": "Profile updated successfully"},
            status=200
        )
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return json_response(
            {"message": f"Error updating profile: {str(e)}"},
            status=500
        )


@app.get("/api/questionnaire")
async def get_questionnaire(request):
    """Get questionnaire questions"""
    return json_response(
        {"questions": get_questionnaire_as_json()},
        status=200
    )


@app.get("/api/users/profile")
@login_required
async def get_user_profile_endpoint(request):
    """Get the user's profile data."""
    user = request.ctx.user
    
    try:
        # Get the current user profile
        user_profile = await get_user_profile(user.id)
        if not user_profile:
            return json_response({"error": "Profile not found"}, status=404)
        
        return json_response({"profile": user_profile.data})
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        return json_response({"error": f"Failed to retrieve profile: {str(e)}"}, status=500)


@app.patch("/api/users/profile")
@login_required
async def update_user_profile_data(request):
    """Update specific fields in the user profile."""
    user = request.ctx.user
    data = request.json
    
    if not data:
        return json_response({"error": "No data provided"}, status=400)
    
    try:
        # Get the current user profile
        user_profile = await get_user_profile(user.id)
        if not user_profile:
            # Create new profile if it doesn't exist
            return json_response({"error": "Profile not found"}, status=404)
        
        # Update profile with the provided fields
        profile_data = user_profile.data
        updated_data = update_user_profile(profile_data, data)
        user_profile.data = updated_data
        await user_profile.save()
        
        return json_response({
            "message": "Profile updated successfully",
            "profile": user_profile.data
        })
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        return json_response({"error": f"Failed to update profile: {str(e)}"}, status=500)


# Handle OPTIONS requests for preflight CORS
@app.route("/<path:path>", methods=["OPTIONS"])
async def handle_options(request, path):
    return empty()

# Handle root OPTIONS request
@app.route("/", methods=["OPTIONS"])
async def handle_root_options(request):
    return empty() 