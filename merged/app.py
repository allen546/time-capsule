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
import aiohttp
import asyncio
import ssl
from sanic import Sanic
from sanic.response import html, json as json_response, file, redirect, text
from sanic.log import logger
import aiofiles
from functools import wraps
from websockets.exceptions import WebSocketProtocolError
from sqlalchemy.exc import DBAPIError
from typing import Dict, List, Optional, Union, Any, Tuple

# Import database module
from db import init_db, get_session, DiaryDB, UserDB, ChatDB, async_session

# Import profile questions
from data.user_profile_questions import USER_PROFILE_QUESTIONS

# Import route blueprints
from routes.chat import chat_bp
from routes.contacts import bp as contacts_bp

# Import LLM utils instead of defining functions here
from utils.llm_client import llm_response

def configure_logging():
    """Configure application logging."""
    # Basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )

    # Reduce noise from Sanic loggers
    logging.getLogger('sanic.access').setLevel(logging.ERROR)
    logging.getLogger('sanic.server').setLevel(logging.ERROR)
    logging.getLogger('sanic.root').setLevel(logging.ERROR)
    logging.getLogger('sanic.error').setLevel(logging.WARNING)
    
    # Set up chat-related loggers with detailed logging - Debug level to catch everything
    websocket_logger = logging.getLogger('websocket')
    websocket_logger.setLevel(logging.INFO)
    
    # Create a detailed formatter for chat logs
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure chat logger to show DEBUG level (maximum detail)
    chat_logger = logging.getLogger('chat')
    chat_logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all detail
    
    # Add a StreamHandler for console output with the detailed formatter
    chat_handler = logging.StreamHandler()
    chat_handler.setFormatter(detailed_formatter)
    chat_handler.setLevel(logging.DEBUG)
    chat_logger.addHandler(chat_handler)
    
    # Set up non-chat API loggers with minimal logging
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.INFO)
    
    # Set up specific loggers for non-chat components
    diary_logger = logging.getLogger('diary')
    diary_logger.setLevel(logging.WARNING)  # Only log warnings and errors
    
    profile_logger = logging.getLogger('profile')
    profile_logger.setLevel(logging.WARNING)  # Only log warnings and errors
    
    contacts_logger = logging.getLogger('contacts')
    contacts_logger.setLevel(logging.WARNING)  # Only log warnings and errors
    
    # Get the application logger
    app_logger = logging.getLogger(__name__)
    
    # Log configuration completed
    app_logger.info("Logging configured")
    return app_logger

# Configure logging
logger = configure_logging()

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

# Get DeepSeek API key from environment variable
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# For fallback to mock response if API key is not set
USE_MOCK_RESPONSE = not DEEPSEEK_API_KEY

# Print debug information about API configuration
print(f"DEEPSEEK_API_KEY: {'[SET]' if DEEPSEEK_API_KEY else '[NOT SET]'}")
print(f"USE_MOCK_RESPONSE: {USE_MOCK_RESPONSE}")
print(f"API MODEL: {DEEPSEEK_MODEL}")

# Initialize users file if it doesn't exist
if not os.path.exists(users_file):
    with open(users_file, 'w') as f:
        json.dump({}, f)

# Configure session middleware
@app.middleware('request')
async def inject_session(request):
    request.ctx.session = async_session()

@app.middleware('request')
async def log_request_details(request):
    """Log detailed information about incoming requests."""
    # Create a request ID for tracking
    request_id = str(uuid.uuid4())[:8]
    request.ctx.request_id = request_id
    
    # Store start time for performance monitoring
    request.ctx.request_start_time = datetime.datetime.now()
    
    # Get path and method
    path = request.path
    method = request.method
    
    # Log basic request info for all requests
    logger.info(f"[REQ:{request_id}] {method} {path}")
    
    # Only log detailed debug information for chat-related paths
    if '/chat' in path or path.startswith('/api/chat'):
        # Log headers (especially authentication headers)
        headers = dict(request.headers)
        sanitized_headers = headers.copy()
        
        # Remove sensitive information from logs
        for key in headers:
            if 'auth' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                sanitized_headers[key] = "[REDACTED]"
        
        # Log important headers for debugging
        important_headers = ['x-user-uuid', 'x-client-id', 'content-type', 'user-agent']
        header_info = {k: headers.get(k, 'N/A') for k in important_headers}
        logger.info(f"[REQ:{request_id}] Headers: {header_info}")
        
        # For API chat routes, log more details
        if path.startswith('/api/chat'):
            # Log query parameters
            if request.args:
                logger.info(f"[REQ:{request_id}] Query params: {dict(request.args)}")
            
            # For chat message endpoints, log additional details
            if 'chat/sessions' in path and '/messages' in path:
                user_uuid = headers.get('x-user-uuid', 'MISSING')
                user_uuid_display = user_uuid[:8] if user_uuid and user_uuid != 'MISSING' else 'MISSING'
                session_id = path.split('/')[-2] if '/sessions/' in path else 'unknown'
                logger.info(f"[REQ:{request_id}] Chat request for session {session_id} from user {user_uuid_display}")
    
    return None

@app.middleware('response')
async def close_session(request, response):
    if hasattr(request.ctx, 'session'):
        await request.ctx.session.close()
    return response

@app.middleware('response')
async def log_response_details(request, response):
    """Log details about the response."""
    # Get request ID from context
    request_id = getattr(request.ctx, 'request_id', 'unknown')
    
    # Get path, method and status
    status = response.status
    path = request.path
    method = request.method
    
    # Calculate response time if we have request_start_time
    timing_info = ""
    if hasattr(request.ctx, 'request_start_time'):
        elapsed = (datetime.datetime.now() - request.ctx.request_start_time).total_seconds()
        timing_info = f" in {elapsed:.2f}s"
    
    # Log basic response info for all requests
    logger.info(f"[RES:{request_id}] {method} {path} → {status}{timing_info}")
    
    # For error responses, always log details
    if status >= 400:
        # For chat-related paths, log more detailed error information
        if '/chat' in path or path.startswith('/api/chat'):
            # For specific paths with permissions issues, log more details
            if status == 403 and path.startswith('/api/chat/sessions/'):
                headers = dict(request.headers)
                user_uuid = headers.get('x-user-uuid', 'MISSING')
                logger.warning(f"[ERROR:{request_id}] Permission denied for {user_uuid}")
                
                # Log session details for debugging
                session_id = path.split('/')[4] if len(path.split('/')) > 4 else 'unknown'
                logger.warning(f"[ERROR:{request_id}] Session access denied: {session_id}")
                
                # Store this event for analysis
                try:
                    asyncio.create_task(
                        store_error_event(
                            error_type="permission_denied", 
                            user_uuid=user_uuid,
                            session_id=session_id,
                            path=path,
                            headers=headers
                        )
                    )
                except Exception as e:
                    logger.error(f"[ERROR:{request_id}] Failed to store error event: {str(e)}")
        
        # Always log error response bodies regardless of path
        try:
            if hasattr(response, 'body'):
                body = response.body.decode('utf-8')
                logger.warning(f"[RES:{request_id}] Error response: {body[:200]}")
        except Exception as e:
            logger.debug(f"[RES:{request_id}] Could not decode response body: {str(e)}")
    
    return response

# Helper function to store error events
async def store_error_event(error_type, user_uuid, session_id, path, headers):
    """Store error events for later analysis."""
    try:
        # Create a timestamp
        timestamp = datetime.datetime.now().isoformat()
        
        # Create the error record
        error_record = {
            "timestamp": timestamp,
            "error_type": error_type,
            "user_uuid": user_uuid,
            "session_id": session_id,
            "path": path,
            "headers": {k: v for k, v in headers.items() if not any(s in k.lower() for s in ['auth', 'key', 'token', 'secret'])}
        }
        
        # Get the error log directory
        error_log_dir = os.path.join(data_folder, 'error_logs')
        os.makedirs(error_log_dir, exist_ok=True)
        
        # Create a filename with date prefix
        date_prefix = datetime.datetime.now().strftime('%Y%m%d')
        filename = f"{date_prefix}_{error_type}.jsonl"
        filepath = os.path.join(error_log_dir, filename)
        
        # Append the error record to the file
        async with aiofiles.open(filepath, mode='a') as f:
            await f.write(json.dumps(error_record) + '\n')
            
        logger.info(f"Error event stored: {error_type} for user {user_uuid[:8] if user_uuid else 'unknown'}")
    except Exception as e:
        logger.error(f"Failed to store error event: {str(e)}")

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

# Register blueprints
app.blueprint(chat_bp)
app.blueprint(contacts_bp)

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
        
        # Log API configuration
        if USE_MOCK_RESPONSE:
            logger.warning("DEEPSEEK_API_KEY not set. Using mock LLM responses.")
        else:
            logger.info(f"Using DeepSeek API with model: {DEEPSEEK_MODEL}")
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
    diary_logger = logging.getLogger('diary')
    try:
        async with aiofiles.open(os.path.join(templates_folder, 'diary.html'), mode='r') as f:
            content = await f.read()
            diary_logger.debug("Diary page served successfully")
            return html(content)
    except Exception as e:
        diary_logger.error(f"Error serving diary page: {str(e)}")
        return html("<h1>Error loading page</h1><p>Unable to load the diary page. Please try again later.</p>", status=500)

@app.route('/chat')
async def chat(request):
    """Serve the chat page."""
    chat_logger = logging.getLogger('chat')
    try:
        chat_logger.info("Serving chat page")
        chat_logger.debug("Loading chat.html template")
        async with aiofiles.open(os.path.join(templates_folder, 'chat.html'), mode='r') as f:
            content = await f.read()
        chat_logger.debug("Chat page template loaded successfully")
        return html(content)
    except Exception as e:
        chat_logger.error(f"Error serving chat page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the chat page. Please try again later.</p>", status=500)

@app.route('/my-chats')
async def my_chats(request):
    """Serve the my chats page."""
    chat_logger = logging.getLogger('chat')
    try:
        chat_logger.info("Serving my chats page")
        chat_logger.debug("Loading my_chats.html template")
        async with aiofiles.open(os.path.join(templates_folder, 'my_chats.html'), mode='r') as f:
            content = await f.read()
        chat_logger.debug("My chats page template loaded successfully")
        return html(content)
    except Exception as e:
        chat_logger.error(f"Error serving my chats page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the my chats page. Please try again later.</p>", status=500)

@app.route('/contacts')
async def contacts(request):
    """Serve the contacts page."""
    contacts_logger = logging.getLogger('contacts')
    try:
        contacts_logger.debug("Serving contacts page")
        async with aiofiles.open(os.path.join(templates_folder, 'contacts.html'), mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        contacts_logger.error(f"Error serving contacts page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the contacts page. Please try again later.</p>", status=500)

@app.route('/create-entry', methods=['GET'])
async def create_entry(request):
    """Serve the create entry page."""
    diary_logger = logging.getLogger('diary')
    try:
        diary_logger.debug("Serving create entry page")
        template_path = os.path.join(templates_folder, 'create_entry.html')
        if not os.path.exists(template_path):
            diary_logger.error(f"Template file not found: {template_path}")
            return html("<h1>Error 404</h1><p>The create entry page template was not found.</p>", status=404)
            
        async with aiofiles.open(template_path, mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        diary_logger.error(f"Error serving create entry page: {str(e)}", exc_info=True)
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

# Handler for direct /api/chat requests (which appear to be causing 400 errors)
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

# Start the server if this file is run directly
if __name__ == "__main__":
    import sys
    # Use default values if command line arguments are not provided
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    
    app.run(
        host=host, 
        port=port, 
        debug=True,
        auto_reload=True
    )

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

def generate_prompt_from_user_model(user_data, language="zh"):
    """
    Generate a customized prompt text based on the user model.
    
    Args:
        user_data: User profile data containing personal information
        language: Language code ('en' for English, 'zh' for Chinese)
        
    Returns:
        A customized prompt text incorporating user data
    """
    # Extract basic user information
    name = user_data.get("name", "")
    age = user_data.get("age", "")
    current_year = datetime.datetime.now().year
    birth_year = current_year - int(age) if age and str(age).isdigit() else None
    year_at_20 = birth_year + 20 if birth_year else None
    
    # Extract profile data
    profile_data = user_data.get("profile_data", {})
    if isinstance(profile_data, str):
        try:
            profile_data = json.loads(profile_data)
        except json.JSONDecodeError:
            profile_data = {}
            
    # Extract questionnaire data
    location = profile_data.get("location_at_20", "")
    occupation = profile_data.get("occupation_at_20", "")
    education = profile_data.get("education", "")
    major = profile_data.get("major_at_20", "")
    hobbies = profile_data.get("hobbies_at_20", "")
    important_people = profile_data.get("important_people_at_20", "")
    significant_events = profile_data.get("significant_events_at_20", "")
    concerns = profile_data.get("concerns_at_20", "")
    dreams = profile_data.get("dreams_at_20", "")
    family_relations = profile_data.get("family_relations_at_20", "")
    health = profile_data.get("health_at_20", "")
    habits = profile_data.get("habits_at_20", "")
    regrets = profile_data.get("regrets_at_20", "")
    background = profile_data.get("basic_data", "")
    personality = profile_data.get("personality", "")
    
    # Build the prompt based on language
    if language == "zh":
        prompt = f"# 20岁时的{name}的角色设定\n\n"
        
        # Basic Information Section
        prompt += f"## 基本信息\n"
        if name:
            prompt += f"- 姓名：{name}\n"
        if age and birth_year and year_at_20:
            prompt += f"- 当前年龄：{age}岁（出生于{birth_year}年）\n"
            prompt += f"- 20岁时的年份：{year_at_20}年\n"
        if location:
            prompt += f"- 20岁时居住地：{location}\n"
        
        # Occupation/Education Section
        if occupation or education or major:
            prompt += f"\n## 学习与工作状况\n"
            if occupation:
                prompt += f"- 职业状态：{occupation}\n"
            if education:
                prompt += f"- 教育背景：{education}\n"
            if major:
                prompt += f"- 所学专业：{major}\n"
        
        # Personal Life Section
        prompt += f"\n## 个人生活\n"
        if hobbies:
            prompt += f"- 兴趣爱好：{hobbies}\n"
        if important_people:
            prompt += f"- 重要的人：{important_people}\n"
        if family_relations:
            prompt += f"- 家庭关系：{family_relations}\n"
        if health:
            prompt += f"- 健康状况：{health}\n"
        if habits:
            prompt += f"- 生活习惯：{habits}\n"
            
        # Mental State Section
        if personality or concerns or dreams:
            prompt += f"\n## 心理状态与想法\n"
            if personality:
                prompt += f"- 性格特点：{personality}\n"
            if concerns:
                prompt += f"- 烦恼与努力方向：{concerns}\n"
            if dreams:
                prompt += f"- 对未来的期待和梦想：{dreams}\n"
            if regrets:
                prompt += f"- 可能的遗憾或想对自己说的话：{regrets}\n"
                
        # Significant Events Section
        if significant_events:
            prompt += f"\n## 重大事件\n"
            prompt += f"{significant_events}\n"
            
        # Additional Background
        if background:
            prompt += f"\n## 其他背景信息\n"
            prompt += f"{background}\n"
            
        # Role-Playing Guidelines
        prompt += f"\n## 角色扮演指南\n"
        prompt += f"""作为20岁的{name}，你应该：
1. 以一个20岁年轻人的语气和思维方式来回应
2. 只讨论{year_at_20 if year_at_20 else '你当时'}年及之前的事件和知识
3. 不要提及未来（对你来说尚未发生）的事情
4. 表现出20岁时的价值观和世界观，特别考虑以下因素：
   - 当时的关注点：{concerns if concerns else '典型20岁年轻人的烦恼'}
   - 对未来的期待：{dreams if dreams else '对未来的希望和梦想'}
   - 重要的人际关系：{important_people if important_people else '朋友、家人和其他重要的人'}
5. 如果被问及未来的事情，你可以表达你对未来的期望，但不应该知道实际发生了什么
6. 你的对话应该反映出你在{location if location else '你生活的地方'}的生活经历和背景"""
            
    else:  # English
        prompt = f"# Character Profile for {name} at Age 20\n\n"
        
        # Basic Information Section
        prompt += f"## Basic Information\n"
        if name:
            prompt += f"- Name: {name}\n"
        if age and birth_year and year_at_20:
            prompt += f"- Current Age: {age} (Born in {birth_year})\n"
            prompt += f"- Year when 20 years old: {year_at_20}\n"
        if location:
            prompt += f"- Location at age 20: {location}\n"
            
        # Occupation/Education Section
        if occupation or education or major:
            prompt += f"\n## Education & Occupation\n"
            if occupation:
                prompt += f"- Occupational status: {occupation}\n"
            if education:
                prompt += f"- Educational background: {education}\n"
            if major:
                prompt += f"- Field of study: {major}\n"
                
        # Personal Life Section
        prompt += f"\n## Personal Life\n"
        if hobbies:
            prompt += f"- Hobbies and interests: {hobbies}\n"
        if important_people:
            prompt += f"- Important people: {important_people}\n"
        if family_relations:
            prompt += f"- Family relationships: {family_relations}\n"
        if health:
            prompt += f"- Health status: {health}\n"
        if habits:
            prompt += f"- Lifestyle habits: {habits}\n"
            
        # Mental State Section
        if personality or concerns or dreams:
            prompt += f"\n## Mental State & Thoughts\n"
            if personality:
                prompt += f"- Personality traits: {personality}\n"
            if concerns:
                prompt += f"- Concerns and efforts: {concerns}\n"
            if dreams:
                prompt += f"- Expectations and dreams for the future: {dreams}\n"
            if regrets:
                prompt += f"- Possible regrets or advice to self: {regrets}\n"
                
        # Significant Events Section
        if significant_events:
            prompt += f"\n## Significant Events\n"
            prompt += f"{significant_events}\n"
            
        # Additional Background
        if background:
            prompt += f"\n## Additional Background\n"
            prompt += f"{background}\n"
            
        # Role-Playing Guidelines
        prompt += f"\n## Role-Playing Guidelines\n"
        prompt += f"""As {name} at age 20, you should:
1. Respond with the tone and mindset of a 20-year-old
2. Only discuss events and knowledge up to {year_at_20 if year_at_20 else 'your time'}
3. Don't mention future events (things that haven't happened for you yet)
4. Reflect the values and worldview you had at 20, especially considering:
   - Your concerns at the time: {concerns if concerns else "typical concerns of a 20-year-old"}
   - Your expectations for the future: {dreams if dreams else "hopes and dreams for the future"}
   - Important relationships: {important_people if important_people else "friends, family, and other important people"}
5. If asked about future events, you may express your hopes for the future, but should not know what actually happened
6. Your conversation should reflect your experiences and background in {location if location else "where you lived"}"""
    
    return prompt

def create_system_prompt(user_data, language="zh"):
    """
    Create a system prompt based on user data.
    
    Args:
        user_data: User profile data
        language: Language code
        
    Returns:
        Formatted system prompt
    """
    # Use the enhanced prompt generator if user data is available
    if user_data:
        return generate_prompt_from_user_model(user_data, language)
    
    # Default basic prompt if no user data is available
    if language == "zh":
        return "你正在模拟与用户20岁时的自己进行对话。"
    return "You are simulating a conversation with a 20-year-old version of the user."

async def deepseek_chat_completion(user_message, user_data=None, session_id=None, db_session=None):
    """
    Get a chat completion from DeepSeek API with conversation history.
    
    Args:
        user_message: The current user message
        user_data: User profile data for personalization
        session_id: The current chat session ID
        db_session: Database session for retrieving message history
        
    Returns:
        The AI response from DeepSeek API or a fallback response
    """
    request_id = str(uuid.uuid4())[:8]  # Generate a short ID for this request
    logger.info(f"[API:{request_id}] Starting DeepSeek API request for session {session_id}")
    logger.info(f"[API:{request_id}] API Key: {'[SET]' if DEEPSEEK_API_KEY else '[NOT SET]'}, USE_MOCK_RESPONSE: {USE_MOCK_RESPONSE}")
    logger.info(f"[API:{request_id}] Using model: {DEEPSEEK_MODEL}")
    
    try:
        # Set preferred language (default to Chinese)
        language = "zh"
        
        # Format system prompt based on user data
        logger.info(f"[API:{request_id}] Generating system prompt")
        system_prompt = create_system_prompt(user_data, language)
        logger.debug(f"[API:{request_id}] System prompt length: {len(system_prompt)} chars")
        
        # Prepare messages list with system prompt
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available
        if session_id and db_session:
            # Get the last 10 messages for context (not including the current one)
            logger.info(f"[API:{request_id}] Retrieving message history")
            history_messages = await ChatDB.get_messages_by_session(db_session, session_id, limit=10)
            logger.info(f"[API:{request_id}] Retrieved {len(history_messages)} messages from history")
            
            # Add messages to the context (oldest first)
            for msg in history_messages:
                # Skip duplicates by checking content
                role = "assistant" if not msg.is_user else "user"
                content = msg.content
                
                # Skip the current message if it's in history already
                if msg.is_user and content.strip() == user_message.strip():
                    logger.debug(f"[API:{request_id}] Skipping duplicate of current message in history")
                    continue
                    
                messages.append({"role": role, "content": content})
        
        # Add the current user message if not already in history
        messages.append({"role": "user", "content": user_message})
        logger.info(f"[API:{request_id}] Final message count for context: {len(messages)}")
        
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 1024
        }
        
        # Log the API request details
        logger.info(f"[API:{request_id}] Request URL: {DEEPSEEK_API_URL}")
        logger.info(f"[API:{request_id}] Request headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer [REDACTED]'}}")
        logger.info(f"[API:{request_id}] Request payload model: {payload['model']}")
        logger.info(f"[API:{request_id}] Request payload message count: {len(payload['messages'])}")
        
        # Create SSL context to handle certificate verification issues
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Make API request
        logger.info(f"[API:{request_id}] Sending request to DeepSeek API with {len(messages)} messages")
        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
                ssl=ssl_context
            ) as response:
                response_time = (datetime.datetime.now() - start_time).total_seconds()
                logger.info(f"[API:{request_id}] Received response from DeepSeek API in {response_time:.2f} seconds")
                logger.info(f"[API:{request_id}] Response status code: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[API:{request_id}] DeepSeek API request failed with status {response.status}: {error_text}")
                    
                    # Check for insufficient balance or other API errors
                    if "Insufficient Balance" in error_text:
                        logger.error(f"[API:{request_id}] API account has insufficient balance")
                        return f"API账户余额不足，无法生成回复。" if language == "zh" else "The API account has insufficient balance."
                    
                    # Default to mock response as fallback
                    logger.warning(f"[API:{request_id}] Using mock response as fallback due to API error")
                    return await mock_llm_response(user_message, user_data, session_id, db_session)
                
                # Process successful response
                result = await response.json()
                logger.info(f"[API:{request_id}] Successfully received valid JSON response from DeepSeek API")
                
                try:
                    content = result["choices"][0]["message"]["content"]
                    content_preview = content[:50] + ('...' if len(content) > 50 else '')
                    logger.info(f"[API:{request_id}] Response content: '{content_preview}'")
                    return content
                except (KeyError, IndexError) as e:
                    logger.error(f"[API:{request_id}] Error extracting content from DeepSeek API response: {e}")
                    logger.error(f"[API:{request_id}] Response structure: {json.dumps(result)[:200]}...")
                    # Fall back to mock response
                    logger.warning(f"[API:{request_id}] Using mock response as fallback")
                    return await mock_llm_response(user_message, user_data, session_id, db_session)
    
    except Exception as e:
        logger.error(f"[API:{request_id}] Error in DeepSeek API request: {str(e)}", exc_info=True)
        # Fall back to mock response
        logger.warning(f"[API:{request_id}] Using mock response as fallback due to exception")
        return await mock_llm_response(user_message, user_data, session_id, db_session)

async def llm_response(user_message, user_data=None, session_id=None, db_session=None):
    """
    Unified function for getting LLM responses - uses DeepSeek API or mock depending on configuration.
    
    Args:
        user_message: The current user message
        user_data: User profile data for personalization
        session_id: The current chat session ID
        db_session: Database session for retrieving message history
        
    Returns:
        The AI response from the chosen method
    """
    # Use mock response if API key is not set or if explicitly configured to use mock
    if USE_MOCK_RESPONSE:
        logger.info("Using mock LLM response")
        return await mock_llm_response(user_message, user_data, session_id, db_session)
    
    # Otherwise use DeepSeek API
    logger.info("Using DeepSeek API for response")
    return await deepseek_chat_completion(user_message, user_data, session_id, db_session)