#!/usr/bin/env python
"""
Time Capsule Server

This script starts the Time Capsule server with Sanic framework.
"""

import logging
import os
import uuid
import json
import datetime
from sanic import Sanic
from sanic.response import html, json as json_response, file, redirect, text
from sanic.log import logger
import aiofiles
from functools import wraps

# Import database module
from db import init_db, get_session, DiaryDB, UserDB, ChatDB, async_session

# Import profile questions
from data.user_profile_questions import USER_PROFILE_QUESTIONS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce noise from specific loggers
logging.getLogger('sanic.access').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Initialize Sanic app
app = Sanic("TimeCapsule")

# Configure static file serving - use absolute path to avoid issues
app_dir = os.path.dirname(os.path.abspath(__file__))
static_folder = os.path.join(app_dir, 'static')
templates_folder = os.path.join(app_dir, 'templates')
data_folder = os.path.join(app_dir, 'data')

# Create data directory if it doesn't exist
os.makedirs(data_folder, exist_ok=True)
users_file = os.path.join(data_folder, 'users.json')

# Initialize users file if it doesn't exist
if not os.path.exists(users_file):
    with open(users_file, 'w') as f:
        json.dump({}, f)

# Configure session middleware
@app.middleware('request')
async def inject_session(request):
    request.ctx.session = async_session()

@app.middleware('response')
async def close_session(request, response):
    if hasattr(request.ctx, 'session'):
        await request.ctx.session.close()
    return response

# Disable caching for static files in development
@app.middleware('response')
async def add_no_cache_headers(request, response):
    """Add no-cache headers to all responses in development."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Configure static serving
app.static('/static', static_folder)

# Event listeners for database initialization
@app.listener('before_server_start')
async def setup_db(app, loop):
    """Initialize database before server starts."""
    logger.info("Starting database initialization...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
        
        # Log database location to help with debugging
        db_path = os.path.join(data_folder, 'timecapsule.db')
        logger.info(f"Database location: {db_path}")
        logger.info(f"Database exists: {os.path.exists(db_path)}")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        raise

# Routes
@app.route('/')
async def index(request):
    """Serve the index page."""
    try:
        async with aiofiles.open(os.path.join(templates_folder, 'index.html'), mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        logger.error(f"Error serving index page: {str(e)}")
        return html("<h1>Error loading page</h1><p>Please try again later.</p>")

@app.route('/profile')
async def profile(request):
    async with aiofiles.open(os.path.join(templates_folder, 'profile.html'), mode='r') as f:
        content = await f.read()
    return html(content)

@app.route('/diary')
async def diary(request):
    """Serve the diary page."""
    async with aiofiles.open(os.path.join(templates_folder, 'diary.html'), mode='r') as f:
        content = await f.read()
    return html(content)

@app.route('/chat')
async def chat(request):
    """Serve the chat page."""
    try:
        logger.info("Serving chat page")
        async with aiofiles.open(os.path.join(templates_folder, 'chat.html'), mode='r') as f:
            content = await f.read()
        return html(content)
    except Exception as e:
        logger.error(f"Error serving chat page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the chat page. Please try again later.</p>", status=500)

@app.route('/create-entry', methods=['GET'])
async def create_entry(request):
    """Serve the create entry page."""
    try:
        logger.info("Serving create entry page")
        template_path = os.path.join(templates_folder, 'create_entry.html')
        if not os.path.exists(template_path):
            logger.error(f"Template file not found: {template_path}")
            return html("<h1>Error 404</h1><p>The create entry page template was not found.</p>", status=404)
            
        async with aiofiles.open(template_path, mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        logger.error(f"Error serving create entry page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the create entry page. Please try again later.</p>", status=500)

@app.route('/health')
async def health_check(request):
    return text("OK")

@app.route('/api/info')
async def api_info(request):
    return json_response({
        "name": "Time Capsule API",
        "version": "1.0.0",
        "status": "active"
    })

# User management API
@app.route('/api/users/generate-uuid', methods=['POST'])
async def generate_uuid(request):
    """Generate a new UUID for anonymous users."""
    try:
        # Generate a new UUID
        user_uuid = str(uuid.uuid4())
        
        # Create user in database
        async with request.ctx.session as session:
            await UserDB.create_user(session, user_uuid)
        
        return json_response({"uuid": user_uuid, "status": "success"})
    except Exception as e:
        logger.error(f"Error generating UUID: {str(e)}")
        return json_response({"error": "Could not generate UUID"}, status=500)

@app.route('/api/users/profile', methods=['POST'])
async def update_profile(request):
    """Update user profile information."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get profile data from request
        data = request.json
        if not data:
            return json_response({"status": "error", "message": "Missing profile data"}, status=400)
            
        name = data.get('name')
        age = data.get('age')
        profile_data = data.get('profile_data', {})
        
        # Validate required data
        if not name or not isinstance(name, str):
            return json_response({"status": "error", "message": "Invalid name"}, status=400)
        
        # Update user in database
        async with request.ctx.session as session:
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                # Create user if not exists
                user = await UserDB.create_user(session, user_uuid, name, age, profile_data)
            else:
                # Update existing user
                user = await UserDB.update_user(session, user_uuid, name, age, profile_data)
        
        logger.info(f"User profile updated: {user_uuid}")
        return json_response({"status": "success", "message": "Profile updated successfully"})
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return json_response({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/users/profile', methods=['GET'])
async def get_profile(request):
    """Get user profile information."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get user from database
        async with request.ctx.session as session:
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            
            if not user:
                return json_response({"status": "error", "message": "User not found"}, status=404)
            
            # Get user data as dictionary (includes profile_data)
            user_data = user.to_dict()
            
            # Return user profile
            return json_response({
                "status": "success",
                "data": user_data
            })
    except Exception as e:
        logger.error(f"Error retrieving profile: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/users/reset', methods=['POST'])
async def reset_device(request):
    """Handle device reset request."""
    try:
        # Get old UUID from request body
        data = request.json
        if not data:
            return json_response({"status": "error", "message": "Missing request data"}, status=400)
        
        old_uuid = data.get('old_uuid')
        
        # Log the reset event
        logger.info(f"Device reset request for UUID: {old_uuid}")
        
        # Mark user as reset in database
        async with request.ctx.session as session:
            await UserDB.reset_user(session, old_uuid)
        
        return json_response({"status": "success", "message": "Device reset completed"})
    except Exception as e:
        logger.error(f"Error handling device reset: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

# Diary API endpoints
@app.route('/api/diary/entries', methods=['GET'])
async def get_diary_entries(request):
    """Get all diary entries for a user."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get entries from database
        async with request.ctx.session as session:
            entries = await DiaryDB.get_entries_by_user(session, user_uuid)
            
            # Convert entries to dictionaries
            entries_data = [entry.to_dict() for entry in entries]
            
            # Sort by pinned status and then by date (newest first)
            sorted_entries = sorted(
                entries_data, 
                key=lambda x: (not x.get('pinned', False), x.get('date', ''), x.get('created_at', '')), 
                reverse=True
            )
            
            return json_response({
                "status": "success",
                "data": sorted_entries
            })
    except Exception as e:
        logger.error(f"Error retrieving diary entries: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries', methods=['POST'])
async def create_diary_entry(request):
    """Create a new diary entry."""
    # Add request logging
    logger.info(f"Received diary entry creation request")
    
    try:
        # Log headers for debugging
        headers = dict(request.headers)
        logger.info(f"Request headers: {headers}")
        
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            logger.error("Missing user UUID in request headers")
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        logger.info(f"Creating diary entry for user: {user_uuid}")
        
        # Get diary entry data
        try:
            data = request.json
        except Exception as json_error:
            logger.error(f"Error parsing JSON: {str(json_error)}")
            return json_response({"status": "error", "message": f"Invalid JSON: {str(json_error)}"}, status=400)
            
        if not data:
            logger.error("Missing diary entry data")
            return json_response({"status": "error", "message": "Missing diary entry data"}, status=400)
        
        # Log request data for debugging
        logger.info(f"Diary entry data: {data}")
        
        # Validate required fields
        title = data.get('title')
        content = data.get('content')
        date = data.get('date')
        
        if not title or not isinstance(title, str):
            logger.error(f"Invalid title: {title}")
            return json_response({"status": "error", "message": "Invalid title"}, status=400)
        
        if not content or not isinstance(content, str):
            logger.error(f"Invalid content type or empty content")
            return json_response({"status": "error", "message": "Invalid content"}, status=400)
        
        if not date or not isinstance(date, str):
            logger.error(f"Invalid date: {date}")
            return json_response({"status": "error", "message": "Invalid date"}, status=400)
        
        # Generate UUID for the entry
        entry_uuid = str(uuid.uuid4())
        logger.info(f"Generated entry UUID: {entry_uuid}")
        
        # Create entry in database
        try:
            async with request.ctx.session as session:
                # Check if user exists
                user = await UserDB.get_user_by_uuid(session, user_uuid)
                if not user:
                    # Create user if not exists
                    logger.info(f"User {user_uuid} not found, creating new user")
                    user = await UserDB.create_user(session, user_uuid)
                
                # Create entry
                entry = await DiaryDB.create_entry(
                    session,
                    user_uuid,
                    entry_uuid,
                    title,
                    content,
                    date,
                    data.get('mood', 'calm'),
                    data.get('pinned', False)
                )
                
                # Log success
                logger.info(f"Diary entry created successfully: {entry_uuid}")
                
                # Return the new entry
                entry_dict = entry.to_dict()
                
                return json_response({
                    "status": "success",
                    "message": "Diary entry created successfully",
                    "data": entry_dict
                })
        except Exception as db_error:
            logger.error(f"Database error creating entry: {str(db_error)}", exc_info=True)
            return json_response({"status": "error", "message": f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        logger.error(f"Error creating diary entry: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries/<entry_id>', methods=['PUT'])
async def update_diary_entry(request, entry_id):
    """Update an existing diary entry."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get diary entry data
        data = request.json
        if not data:
            return json_response({"status": "error", "message": "Missing diary entry data"}, status=400)
        
        # Update entry in database
        async with request.ctx.session as session:
            # Get the entry
            entry = await DiaryDB.get_entry_by_uuid(session, entry_id)
            
            # Check if entry exists and belongs to user
            if not entry:
                return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
            
            if entry.user_uuid != user_uuid:
                return json_response({"status": "error", "message": "Access denied"}, status=403)
            
            # Update entry
            entry = await DiaryDB.update_entry(
                session,
                entry_id,
                title=data.get('title'),
                content=data.get('content'),
                date=data.get('date'),
                mood=data.get('mood'),
                pinned=data.get('pinned')
            )
            
            # Return the updated entry
            return json_response({
                "status": "success",
                "message": "Diary entry updated successfully",
                "data": entry.to_dict()
            })
    except Exception as e:
        logger.error(f"Error updating diary entry: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries/<entry_id>', methods=['DELETE'])
async def delete_diary_entry(request, entry_id):
    """Delete a diary entry."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Delete entry from database
        async with request.ctx.session as session:
            # Get the entry
            entry = await DiaryDB.get_entry_by_uuid(session, entry_id)
            
            # Check if entry exists and belongs to user
            if not entry:
                return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
            
            if entry.user_uuid != user_uuid:
                return json_response({"status": "error", "message": "Access denied"}, status=403)
            
            # Delete entry
            success = await DiaryDB.delete_entry(session, entry_id)
            
            if success:
                return json_response({
                    "status": "success",
                    "message": "Diary entry deleted successfully"
                })
            else:
                return json_response({"status": "error", "message": "Failed to delete entry"}, status=500)
    except Exception as e:
        logger.error(f"Error deleting diary entry: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/profile-questions', methods=['GET'])
async def get_profile_questions(request):
    """Get the profile questions."""
    try:
        return json_response({
            "status": "success",
            "data": USER_PROFILE_QUESTIONS
        })
    except Exception as e:
        logger.error(f"Error getting profile questions: {str(e)}")
        return json_response({"status": "error", "message": "Could not retrieve profile questions"}, status=500)

# Chat API Routes
@app.route('/api/chat/sessions', methods=['GET'])
async def get_chat_sessions(request):
    """Get all chat sessions for the user."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get chat sessions from database
        async with request.ctx.session as session:
            # Verify user exists
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                return json_response({"status": "error", "message": "User not found"}, status=404)
                
            chat_sessions = await ChatDB.get_sessions_by_user(session, user_uuid)
            
        # Convert to dict
        sessions_data = [session.to_dict() for session in chat_sessions]
        
        return json_response({
            "status": "success",
            "data": sessions_data
        })
    except Exception as e:
        logger.error(f"Error getting chat sessions: {str(e)}")
        return json_response({"status": "error", "message": "Could not retrieve chat sessions"}, status=500)

@app.route('/api/chat/sessions', methods=['POST'])
async def create_chat_session(request):
    """Create a new chat session."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
            
        # Get data from request
        data = request.json
        if not data:
            return json_response({"status": "error", "message": "Missing request data"}, status=400)
            
        title = data.get('title', 'New Chat')
        
        # Generate a new session UUID
        session_uuid = str(uuid.uuid4())
        
        # Create chat session in database
        async with request.ctx.session as session:
            # Verify user exists
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                return json_response({"status": "error", "message": "User not found"}, status=404)
                
            chat_session = await ChatDB.create_session(session, user_uuid, session_uuid, title)
            
        # Return the created chat session
        return json_response({
            "status": "success",
            "data": chat_session.to_dict()
        })
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        return json_response({"status": "error", "message": "Could not create chat session"}, status=500)

@app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
async def delete_chat_session(request, session_id):
    """Delete a chat session."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
            
        # Delete chat session from database
        async with request.ctx.session as session:
            # Verify user exists
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                return json_response({"status": "error", "message": "User not found"}, status=404)
                
            # Verify session exists and belongs to user
            chat_session = await ChatDB.get_session_by_uuid(session, session_id)
            if not chat_session:
                return json_response({"status": "error", "message": "Chat session not found"}, status=404)
                
            if chat_session.user_uuid != user_uuid:
                return json_response({"status": "error", "message": "Unauthorized access to chat session"}, status=403)
                
            # Delete the session
            success = await ChatDB.delete_session(session, session_id)
            
        if success:
            return json_response({"status": "success", "message": "Chat session deleted successfully"})
        else:
            return json_response({"status": "error", "message": "Failed to delete chat session"}, status=500)
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        return json_response({"status": "error", "message": "Could not delete chat session"}, status=500)

@app.route('/api/chat/sessions/<session_id>/messages', methods=['GET'])
async def get_chat_messages(request, session_id):
    """Get messages for a chat session."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
            
        # Get pagination parameters
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Get messages from database
        async with request.ctx.session as session:
            # Verify user exists
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                return json_response({"status": "error", "message": "User not found"}, status=404)
                
            # Verify session exists and belongs to user
            chat_session = await ChatDB.get_session_by_uuid(session, session_id)
            if not chat_session:
                return json_response({"status": "error", "message": "Chat session not found"}, status=404)
                
            if chat_session.user_uuid != user_uuid:
                return json_response({"status": "error", "message": "Unauthorized access to chat session"}, status=403)
                
            # Get the messages
            messages = await ChatDB.get_messages_by_session(session, session_id, limit, offset)
            
        # Convert to dict
        messages_data = [message.to_dict() for message in messages]
        
        return json_response({
            "status": "success",
            "data": messages_data
        })
    except Exception as e:
        logger.error(f"Error getting chat messages: {str(e)}")
        return json_response({"status": "error", "message": "Could not retrieve chat messages"}, status=500)

# Mock function for LLM API call
async def mock_llm_response(user_message, user_data=None, session_id=None, db_session=None):
    """Mock function to simulate LLM API call with history."""
    try:
        # Initialize response
        response_parts = [f"Echo: {user_message}"]
        
        # Add chat history if session_id and db_session are provided
        if session_id and db_session:
            # Get previous messages (limited to last 10 for better context)
            messages = await ChatDB.get_messages_by_session(db_session, session_id, limit=10)
            
            # If there are previous messages, include them in the response
            if messages and len(messages) > 1:  # Only show history if there's more than just the current message
                # Skip the most recent user message (it's the one we're responding to)
                previous_messages = [msg for msg in messages if msg.content.strip() != user_message.strip()]
                
                if previous_messages:
                    response_parts.append("\n\nChat History:")
                    
                    # Create a seen set to track unique message content
                    seen_contents = set()
                    
                    # Format the chat history with proper indentation and formatting
                    for msg in previous_messages:
                        # Skip duplicate content
                        content_key = msg.content.strip()[:50]  # Use first 50 chars as key
                        if content_key in seen_contents:
                            continue
                        
                        seen_contents.add(content_key)
                        speaker = "You" if msg.is_user else "AI"
                        response_parts.append(f"\n{speaker}: {msg.content}")
        
        # If user data is available, personalize the response
        if user_data and user_data.get('name'):
            response_parts.append(f"\n\nBy the way, {user_data.get('name')}, this is just a mock response. In the future, we'll connect to a real LLM API.")
        
        # Join all parts
        response = "".join(response_parts)
        return response
    except Exception as e:
        logger.error(f"Error in mock LLM response: {str(e)}")
        return f"Echo: {user_message} (Error fetching chat history)"

# WebSocket route for chat
@app.websocket('/ws/chat/<session_id>')
async def chat_socket(request, ws, session_id):
    """WebSocket handler for real-time chat."""
    logger.info(f"WebSocket connection established for chat session {session_id}")
    
    try:
        # Get user UUID from query parameters
        user_uuid = request.args.get('user_uuid')
        if not user_uuid:
            await ws.send(json.dumps({"status": "error", "message": "Missing user UUID"}))
            await ws.close()
            return
            
        # Verify session exists and belongs to user
        async with async_session() as session:
            # Get user data
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            if not user:
                await ws.send(json.dumps({"status": "error", "message": "User not found"}))
                await ws.close()
                return
                
            # For fixed single conversation with ID "single-chat-session"
            chat_session = await ChatDB.get_session_by_uuid(session, session_id)
            if not chat_session:
                # Create a new session with the fixed ID if it doesn't exist
                chat_session = await ChatDB.create_session(session, user_uuid, session_id, "与20岁的自己对话")
            elif chat_session.user_uuid != user_uuid:
                # If session exists but belongs to another user, create a new one for this user
                # This shouldn't normally happen with client-generated UUIDs, but handle it anyway
                await ChatDB.delete_session(session, session_id)
                chat_session = await ChatDB.create_session(session, user_uuid, session_id, "与20岁的自己对话")
        
        # Send initial connection confirmation
        await ws.send(json.dumps({
            "status": "connected",
            "message": "WebSocket connection established",
            "session_id": session_id
        }))
        
        # Main WebSocket loop
        while True:
            # Wait for message from client
            data = await ws.recv()
            try:
                message_data = json.loads(data)
                user_message = message_data.get('message', '')
                
                if not user_message:
                    await ws.send(json.dumps({"status": "error", "message": "Empty message"}))
                    continue
                
                # Generate a UUID for the user message
                message_uuid = str(uuid.uuid4())
                
                # Get user data for personalization
                async with async_session() as db_session:
                    # Get user data
                    user = await UserDB.get_user_by_uuid(db_session, user_uuid)
                    user_data = user.to_dict() if user else {}
                    
                    # Store the user message
                    await ChatDB.add_message(
                        db_session, 
                        session_id, 
                        message_uuid, 
                        user_message,
                        is_user=True
                    )
                    
                    # Process the message and get AI response with the current session
                    ai_response = await mock_llm_response(user_message, user_data, session_id, db_session)
                    
                    # Generate a UUID for the AI response
                    ai_message_uuid = str(uuid.uuid4())
                    
                    # Save AI response to database - IMPORTANT: use the same session to preserve correct order
                    await ChatDB.add_message(
                        db_session, 
                        session_id, 
                        ai_message_uuid, 
                        ai_response,
                        is_user=False
                    )
                
                # Acknowledge receipt of message to client
                await ws.send(json.dumps({
                    "status": "message_received",
                    "message_id": message_uuid
                }))
                
                # Send AI response to client
                await ws.send(json.dumps({
                    "status": "ai_response",
                    "message_id": ai_message_uuid,
                    "message": ai_response
                }))
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in WebSocket message")
                await ws.send(json.dumps({"status": "error", "message": "Invalid JSON message"}))
            except Exception as e:
                logger.error(f"Error in WebSocket message handling: {str(e)}")
                await ws.send(json.dumps({"status": "error", "message": "Server error processing message"}))
                
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        logger.info(f"WebSocket connection closed for chat session {session_id}")

# Start the server if this file is run directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, auto_reload=True) 