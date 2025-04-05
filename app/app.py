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
import argparse
from sqlalchemy import select
import traceback
from sanic.handlers import ErrorHandler
from sanic.exceptions import SanicException, NotFound, Unauthorized, InvalidUsage

# Import configuration
from config import CONFIG, get_db_url, DATA_DIR, get_secret, ENV

# Import database module
from db import init_db, get_session, DiaryDB, UserDB, ChatDB, async_session

# Import profile questions
from data.user_profile_questions import USER_PROFILE_QUESTIONS

# Import route blueprints
from routes.chat import chat_bp
from routes.contacts import bp as contacts_bp

# Import LLM utils instead of defining functions here
from utils.llm_client import llm_response

# Rate limiting configuration
RATE_LIMIT = {
    "enabled": True,
    "default_rate": 30,  # requests per minute
    "admin_rate": 60,    # requests per minute
    "login_rate": 5,     # requests per minute
    "whitelist": ["127.0.0.1", "::1"]  # localhost
}

# Rate limiting storage (in-memory for simplicity, use Redis in production)
rate_limit_storage = {}

def configure_logging():
    """Configure application logging."""
    # Basic logging configuration
    logging.basicConfig(
        level=getattr(logging, CONFIG["log_level"]),
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
    
    # Set up chat-related loggers with detailed logging - WARN level to catch profile checks
    websocket_logger = logging.getLogger('websocket')
    websocket_logger.setLevel(logging.INFO)
    
    # Create a detailed formatter for chat logs
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure chat logger to show WARNING level (to make profile checks more visible)
    chat_logger = logging.getLogger('chat')
    chat_logger.setLevel(logging.WARNING)  # Set to WARNING to focus on profile checks
    
    # Create a file specifically for profile checks
    profile_file_handler = logging.FileHandler('profile_checks.log')
    profile_file_handler.setFormatter(detailed_formatter)
    profile_file_handler.setLevel(logging.WARNING)
    chat_logger.addHandler(profile_file_handler)
    
    # Add a StreamHandler with distinctive formatting for console output
    chat_handler = logging.StreamHandler()
    chat_handler.setFormatter(logging.Formatter(
        '\033[1;33m%(asctime)s - CHAT - %(levelname)s - %(message)s\033[0m'  # Yellow bold text
    ))
    chat_handler.setLevel(logging.WARNING)
    chat_logger.addHandler(chat_handler)
    
    # Set up non-chat API loggers with minimal logging
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.INFO)
    
    # Set up specific loggers for non-chat components
    diary_logger = logging.getLogger('diary')
    diary_logger.setLevel(logging.INFO)  # Changed from WARNING to INFO
    
    profile_logger = logging.getLogger('profile')
    profile_logger.setLevel(logging.WARNING)  # Only log warnings and errors
    
    contacts_logger = logging.getLogger('contacts')
    contacts_logger.setLevel(logging.WARNING)  # Only log warnings and errors
    
    # Get the application logger，，
    app_logger = logging.getLogger(__name__)
    
    # Log configuration completed
    app_logger.info("Logging configured")
    return app_logger

# Configure logging
logger = configure_logging()

# Custom error handler
class CustomErrorHandler(ErrorHandler):
    def default(self, request, exception):
        """Handle uncaught exceptions."""
        error_uuid = str(uuid.uuid4())[:8]
        error_type = type(exception).__name__
        
        # Get error details but limit traceback for security
        error_msg = str(exception)
        error_traceback = traceback.format_exc()
        
        # Log the complete error for debugging
        logger.error(f"[ERROR:{error_uuid}] Uncaught {error_type}: {error_msg}")
        logger.debug(f"[ERROR:{error_uuid}] Traceback: {error_traceback}")
        
        # Prepare safe response - don't expose implementation details to client
        if isinstance(exception, SanicException):
            # Known Sanic exceptions
            status_code = exception.status_code
            error_message = str(exception)
        elif isinstance(exception, DBAPIError):
            # Database errors
            status_code = 500
            error_message = "A database error occurred."
        else:
            # Any other exception
            status_code = 500
            error_message = "An unexpected error occurred."
        
        # In development mode, include more details for debugging
        if ENV != "prod":
            error_details = {
                "error_type": error_type,
                "error_message": error_msg,
                "error_id": error_uuid
            }
        else:
            error_details = {
                "error_id": error_uuid
            }
        
        # Return JSON response with error details
        return json_response({
            "status": "error",
            "message": error_message,
            "details": error_details
        }, status=status_code)

# Initialize Sanic app with custom error handler
app = Sanic(CONFIG["app_name"], error_handler=CustomErrorHandler())

# Get paths from configuration
static_folder = CONFIG["static_folder"]
templates_folder = CONFIG["templates_folder"]
data_folder = CONFIG["data_folder"]

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
logger.info(f"Environment: {os.environ.get('TIME_CAPSULE_ENV', 'dev')}")
logger.info(f"Database URL: {get_db_url()}")
logger.info(f"DEEPSEEK_API_KEY: {'[SET]' if DEEPSEEK_API_KEY else '[NOT SET]'}")
logger.info(f"USE_MOCK_RESPONSE: {USE_MOCK_RESPONSE}")
logger.info(f"API MODEL: {DEEPSEEK_MODEL}")

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
    """Redirect to intro page."""
    return redirect('/intro')

@app.route('/home')
async def home(request):
    """Serve the home page (same as index)."""
    try:
        async with aiofiles.open(os.path.join(templates_folder, 'index.html'), mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        logger.error(f"Error serving home page: {str(e)}")
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
    """Health check endpoint for monitoring."""
    try:
        health_status = {
            "status": "ok",
            "version": "1.0.0",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "environment": ENV,
            "checks": {
                "database": "pending",
                "api": "pending"
            }
        }
        
        # Check database connection
        try:
            async with async_session() as session:
                stmt = select(User)
                result = await session.execute(stmt)
                # Just test the connection, don't need the results
                health_status["checks"]["database"] = "ok"
        except Exception as e:
            logger.error(f"Health check - Database connection failed: {str(e)}")
            health_status["checks"]["database"] = "error"
            health_status["status"] = "error"
        
        # Check API configuration if needed
        if get_secret("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
            health_status["checks"]["api"] = "ok"
        else:
            health_status["checks"]["api"] = "warning"
        
        # Return health status with appropriate status code
        status_code = 200 if health_status["status"] == "ok" else 503
        return json_response(health_status, status=status_code)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return json_response({
            "status": "error",
            "message": "Health check failed",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }, status=500)

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
        
        # Mark user as reset in database and delete associated data
        async with request.ctx.session as session:
            await UserDB.reset_user(session, old_uuid)
        
        return json_response({
            "status": "success", 
            "message": "设备已重置，所有日记、聊天记录和联系人数据已清除"
        })
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
            diary_logger = logging.getLogger('diary')
            diary_logger.warning(f"GET /api/diary/entries 400 user: missing_uuid")
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
            
            diary_logger = logging.getLogger('diary')
            diary_logger.info(f"GET /api/diary/entries 200 user: {user_uuid}")
            
            return json_response({
                "status": "success",
                "data": sorted_entries
            })
    except Exception as e:
        logger.error(f"Error retrieving diary entries: {str(e)}", exc_info=True)
        diary_logger = logging.getLogger('diary')
        diary_logger.error(f"GET /api/diary/entries 500 user: {user_uuid if 'user_uuid' in locals() else 'unknown'}")
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries', methods=['POST'])
async def create_diary_entry(request):
    """Create a new diary entry."""
    # Get user UUID from header
    user_uuid = request.headers.get('X-User-UUID')
    diary_logger = logging.getLogger('diary')
    
    if not user_uuid:
        diary_logger.warning(f"POST /api/diary/entries 400 user: missing_uuid")
        return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
    
    try:
        # Get diary entry data
        try:
            data = request.json
        except Exception as json_error:
            diary_logger.error(f"POST /api/diary/entries 400 user: {user_uuid} - Invalid JSON")
            return json_response({"status": "error", "message": f"Invalid JSON: {str(json_error)}"}, status=400)
            
        if not data:
            diary_logger.error(f"POST /api/diary/entries 400 user: {user_uuid} - Missing data")
            return json_response({"status": "error", "message": "Missing diary entry data"}, status=400)
        
        # Validate required fields
        title = data.get('title')
        content = data.get('content')
        date = data.get('date')
        
        if not title or not isinstance(title, str):
            diary_logger.error(f"POST /api/diary/entries 400 user: {user_uuid} - Invalid title")
            return json_response({"status": "error", "message": "Invalid title"}, status=400)
        
        if not content or not isinstance(content, str):
            diary_logger.error(f"POST /api/diary/entries 400 user: {user_uuid} - Invalid content type or empty content")
            return json_response({"status": "error", "message": "Invalid content"}, status=400)
        
        if not date or not isinstance(date, str):
            diary_logger.error(f"POST /api/diary/entries 400 user: {user_uuid} - Invalid date")
            return json_response({"status": "error", "message": "Invalid date"}, status=400)
        
        # Generate UUID for the entry
        entry_uuid = str(uuid.uuid4())
        
        # Create entry in database
        try:
            async with request.ctx.session as session:
                # Check if user exists
                user = await UserDB.get_user_by_uuid(session, user_uuid)
                if not user:
                    # Create user if not exists
                    diary_logger.info(f"POST /api/diary/entries 200 user: {user_uuid} - User not found, creating new user")
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
                diary_logger.info(f"POST /api/diary/entries 200 user: {user_uuid} entry: {entry_uuid}")
                
                # Return the new entry
                entry_dict = entry.to_dict()
                
                return json_response({
                    "status": "success",
                    "message": "Diary entry created successfully",
                    "data": entry_dict
                })
        except Exception as db_error:
            diary_logger.error(f"POST /api/diary/entries 500 user: {user_uuid} - DB Error")
            return json_response({"status": "error", "message": f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        diary_logger.error(f"POST /api/diary/entries 500 user: {user_uuid} - {str(e)}")
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries/<entry_id>', methods=['PUT'])
async def update_diary_entry(request, entry_id):
    """Update an existing diary entry."""
    diary_logger = logging.getLogger('diary')
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            diary_logger.warning(f"PUT /api/diary/entries/{entry_id} 400 user: missing_uuid")
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
            
            # Log success after update
            diary_logger.info(f"PUT /api/diary/entries/{entry_id} 200 user: {user_uuid}")
            
            # Return the updated entry
            return json_response({
                "status": "success",
                "message": "Diary entry updated successfully",
                "data": entry.to_dict()
            })
    except Exception as e:
        diary_logger.error(f"PUT /api/diary/entries/{entry_id} 500 user: {user_uuid if 'user_uuid' in locals() else 'unknown'}")
        return json_response({"status": "error", "message": "Server error"}, status=500)

@app.route('/api/diary/entries/<entry_id>', methods=['DELETE'])
async def delete_diary_entry(request, entry_id):
    """Delete a diary entry."""
    diary_logger = logging.getLogger('diary')
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            diary_logger.warning(f"DELETE /api/diary/entries/{entry_id} 400 user: missing_uuid")
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
            
            # Log success
            diary_logger.info(f"DELETE /api/diary/entries/{entry_id} 200 user: {user_uuid}")
            
            if success:
                return json_response({
                    "status": "success",
                    "message": "Diary entry deleted successfully"
                })
            else:
                return json_response({"status": "error", "message": "Failed to delete entry"}, status=500)
    except Exception as e:
        diary_logger.error(f"DELETE /api/diary/entries/{entry_id} 500 user: {user_uuid if 'user_uuid' in locals() else 'unknown'}")
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

# Add admin route
@app.route('/admin')
async def admin(request):
    """Serve the admin page."""
    try:
        logger.info("Serving admin page")
        async with aiofiles.open(os.path.join(templates_folder, 'admin.html'), mode='r') as f:
            content = await f.read()
        return html(content)
    except Exception as e:
        logger.error(f"Error serving admin page: {str(e)}", exc_info=True)
        return html("<h1>Error loading page</h1><p>Unable to load the admin page. Please try again later.</p>", status=500)

# Admin API for user management
@app.route('/api/admin/users', methods=['GET'])
async def get_users(request):
    """Get all users (admin only)."""
    # Check admin token
    admin_token = request.headers.get('X-Admin-Token')
    admin_pwd = get_secret("ADMIN_PASSWORD", "admin123")  # Fallback for development
    
    if admin_token != admin_pwd:
        logger.warning(f"Unauthorized admin access attempt")
        return json_response({"error": "Unauthorized"}, status=401)
    
    try:
        async with async_session() as session:
            users = await UserDB.get_all_users(session)
            return json_response({
                "status": "success",
                "users": [user.to_dict() for user in users]
            })
    except Exception as e:
        logger.error(f"Error in get_users: {str(e)}", exc_info=True)
        return json_response({"error": str(e)}, status=500)

@app.route('/api/admin/users/<user_uuid>', methods=['DELETE'])
async def delete_user(request, user_uuid):
    """Delete a user and all their associated data (admin only)."""
    # Check admin token
    admin_token = request.headers.get('X-Admin-Token')
    admin_pwd = get_secret("ADMIN_PASSWORD", "admin123")  # Fallback for development
    
    if admin_token != admin_pwd:
        logger.warning(f"Unauthorized admin access attempt")
        return json_response({"error": "Unauthorized"}, status=401)
    
    try:
        async with async_session() as session:
            # Check delete mode from query params (default to delete everything)
            delete_mode = request.args.get('mode', 'all')
            
            if delete_mode == 'all':
                # Delete user and all associated data
                await UserDB.delete_user(session, user_uuid)
                message = f"User {user_uuid} and all associated data deleted successfully"
            elif delete_mode == 'chats':
                # Only delete chat sessions, keep the user
                await ChatDB.delete_all_sessions_by_user(session, user_uuid)
                message = f"All chat sessions for user {user_uuid} deleted successfully"
            elif delete_mode == 'diary':
                # Only delete diary entries, keep the user
                await DiaryDB.delete_entries_by_user(session, user_uuid)
                message = f"All diary entries for user {user_uuid} deleted successfully"
            else:
                return json_response({"error": f"Invalid delete mode: {delete_mode}"}, status=400)
            
            return json_response({
                "status": "success",
                "message": message
            })
    except Exception as e:
        logger.error(f"Error in delete_user: {str(e)}", exc_info=True)
        return json_response({"error": str(e)}, status=500)

@app.route('/api/admin/sessions', methods=['GET'])
async def get_sessions(request):
    """Get all chat sessions (admin only)."""
    # Check admin token
    admin_token = request.headers.get('X-Admin-Token')
    admin_pwd = get_secret("ADMIN_PASSWORD", "admin123")  # Fallback for development
    
    if admin_token != admin_pwd:
        logger.warning(f"Unauthorized admin access attempt")
        return json_response({"error": "Unauthorized"}, status=401)
    
    try:
        async with async_session() as session:
            sessions = await ChatDB.get_all_sessions(session)
            
            # For each session, count the number of messages
            sessions_with_counts = []
            for chat_session in sessions:
                session_dict = chat_session.to_dict()
                message_count = await ChatDB.count_messages_by_session(session, chat_session.session_uuid)
                session_dict['message_count'] = message_count
                sessions_with_counts.append(session_dict)
            
            return json_response({
                "status": "success",
                "sessions": sessions_with_counts
            })
    except Exception as e:
        logger.error(f"Error in get_sessions: {str(e)}", exc_info=True)
        return json_response({"error": str(e)}, status=500)

@app.route('/api/admin/sessions/<session_id>', methods=['DELETE'])
async def delete_session(request, session_id):
    """Delete a chat session and all its messages (admin only)."""
    # Check admin token
    admin_token = request.headers.get('X-Admin-Token')
    admin_pwd = get_secret("ADMIN_PASSWORD", "admin123")  # Fallback for development
    
    if admin_token != admin_pwd:
        logger.warning(f"Unauthorized admin access attempt")
        return json_response({"error": "Unauthorized"}, status=401)
    
    try:
        async with async_session() as session:
            await ChatDB.delete_session(session, session_id)
            
            return json_response({
                "status": "success",
                "message": f"Session {session_id} deleted successfully"
            })
    except Exception as e:
        logger.error(f"Error in delete_session: {str(e)}", exc_info=True)
        return json_response({"error": str(e)}, status=500)

@app.route('/intro')
async def intro(request):
    """Render the intro animation page."""
    try:
        async with aiofiles.open(os.path.join(templates_folder, 'intro.html'), mode='r') as f:
            content = await f.read()
            return html(content)
    except Exception as e:
        logger.error(f"Error serving intro page: {str(e)}")
        return html("<h1>Error loading page</h1><p>Please try again later.</p>")

@app.route('/api/diary/summary/<date>')
async def get_diary_summary(request, date):
    """
    Get the summary of diary entries for a specific date.
    
    Args:
        request: The request object
        date: The date to get the summary for in YYYY-MM-DD format
        
    Returns:
        JSON response with the summary
    """
    # Get logger for diary operations
    diary_logger = logging.getLogger('diary')
    
    # Get user UUID from header
    user_uuid = request.headers.get('X-User-UUID')
    
    # Validate user UUID
    if not user_uuid:
        diary_logger.warning(f"GET /api/diary/summary/{date} 400 user: missing_uuid")
        return json_response({
            "status": "error",
            "message": "Missing user UUID in header",
            "error_code": "MISSING_USER_UUID"
        }, status=400)
    
    # Validate date format
    try:
        # Validate date format (YYYY-MM-DD)
        datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        diary_logger.warning(f"GET /api/diary/summary/{date} 400 user: {user_uuid}")
        return json_response({
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM-DD",
            "error_code": "INVALID_DATE_FORMAT"
        }, status=400)
    
    try:
        diary_logger.info(f"Retrieving summary for user: {user_uuid}, date: {date}")
        async with async_session() as session:
            # Get summary for the date
            summary = await DiaryDB.get_summary_by_date(session, user_uuid, date)
            
            if not summary:
                diary_logger.info(f"GET /api/diary/summary/{date} 404 user: {user_uuid}")
                return json_response({
                    "status": "error",
                    "message": f"No summary found for date {date}",
                    "error_code": "NO_SUMMARY_FOUND"
                }, status=404)
            
            # Log success
            diary_logger.info(f"GET /api/diary/summary/{date} 200 user: {user_uuid}")
            
            # Return summary
            return json_response({
                "status": "success",
                "data": summary.to_dict()
            })
            
    except Exception as e:
        diary_logger.error(f"GET /api/diary/summary/{date} 500 user: {user_uuid} - {str(e)}")
        return json_response({
            "status": "error",
            "message": "An error occurred while retrieving the diary summary",
            "error_code": "RETRIEVAL_ERROR"
        }, status=500)

@app.route('/api/diary/summarize/<date>')
async def summarize_diary_entries(request, date):
    """
    Summarize all diary entries for a specific date.
    
    Args:
        request: The request object
        date: The date to summarize in YYYY-MM-DD format
        
    Returns:
        JSON response with summarization status
    """
    # Get logger for diary operations
    diary_logger = logging.getLogger('diary')
    
    # Get user UUID from header
    user_uuid = request.headers.get('X-User-UUID')
    
    # Validate user UUID
    if not user_uuid:
        diary_logger.warning(f"GET /api/diary/summarize/{date} 400 user: missing_uuid")
        return json_response({
            "status": "error",
            "message": "Missing user UUID in header",
            "error_code": "MISSING_USER_UUID"
        }, status=400)
    
    # Validate date format
    try:
        # Validate date format (YYYY-MM-DD)
        datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        diary_logger.warning(f"GET /api/diary/summarize/{date} 400 user: {user_uuid}")
        return json_response({
            "status": "error",
            "message": "Invalid date format. Use YYYY-MM-DD",
            "error_code": "INVALID_DATE_FORMAT"
        }, status=400)
    
    try:
        diary_logger.info(f"Processing summary request for user: {user_uuid}, date: {date}")
        async with async_session() as session:
            # Get all entries for the user on the specified date
            entries = await DiaryDB.get_entries_by_date(session, user_uuid, date)
            
            if not entries:
                diary_logger.info(f"GET /api/diary/summarize/{date} 404 user: {user_uuid}")
                return json_response({
                    "status": "error",
                    "message": f"No diary entries found for date {date}",
                    "error_code": "NO_ENTRIES_FOUND"
                }, status=404)
            
            diary_logger.info(f"Found {len(entries)} entries for user: {user_uuid}, date: {date}")
            
            # Format entries for the LLM prompt
            entries_text = ""
            for i, entry in enumerate(entries, 1):
                entries_text += f"条目 {i} - {entry.title}:\n{entry.content}\n\n"
            
            # Create prompt for the LLM
            prompt = f"""
            你是一位能够总结日记内容的助手，现在需要总结一个人在特定日期（{date}）的所有日记条目。
            
            以下是这一天的所有日记内容：
            
            {entries_text}
            
            请提供一份全面的总结，突出这一天的主要事件、情感和想法。
            总结应该在200-300字左右，以第一人称撰写，就像日记主人在回顾自己的一天，并保持原始条目的情感基调,请你不要编造任何东西，请你用中文回答
            """
            
            # Get response from LLM
            from utils.llm_client import llm_response
            
            messages = [
                {"role": "system", "content": "你是一位能够总结日记内容的智能助手。"},
                {"role": "user", "content": prompt}
            ]
            
            # Get the user for potential personalization
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            diary_logger.info(f"Sending request to LLM for user: {user_uuid}, date: {date}")
            
            # Generate summary
            summary_response = await llm_response(
                messages=messages,
                model="deepseek-chat",
                temperature=0.7,
                max_tokens=500
            )
            diary_logger.info(f"Received LLM response for user: {user_uuid}, date: {date}")
            
            # Save summary to database
            summary = await DiaryDB.create_or_update_summary(
                session, 
                user_uuid, 
                date, 
                summary_response
            )
            diary_logger.info(f"Summary saved to database for user: {user_uuid}, date: {date}, uuid: {summary.summary_uuid}")
            
            # Log success
            diary_logger.info(f"GET /api/diary/summarize/{date} 200 user: {user_uuid}")
            
            return json_response({
                "status": "success",
                "message": "Diary entries summarized successfully",
                "data": {
                    "date": date,
                    "summary": summary.summary,
                    "summary_id": summary.summary_uuid,
                    "entry_count": len(entries)
                }
            })
            
    except Exception as e:
        diary_logger.error(f"GET /api/diary/summarize/{date} 500 user: {user_uuid} - {str(e)}")
        return json_response({
            "status": "error",
            "message": "An error occurred while summarizing diary entries",
            "error_code": "SUMMARIZATION_ERROR"
        }, status=500)

# Main entry point
if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(description='Time Capsule Application Server')
    parser.add_argument('--env', type=str, choices=['dev', 'prod', 'test'], 
                        default=os.environ.get('TIME_CAPSULE_ENV', 'dev'),
                        help='Application environment (dev, prod, test)')
    parser.add_argument('--host', type=str, default='0.0.0.0', 
                        help='Host to listen on')
    parser.add_argument('--port', type=int, default=8000, 
                        help='Port to listen on')
    parser.add_argument('--debug', action='store_true', 
                        help='Enable debug mode')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set environment variable for configuration
    os.environ['TIME_CAPSULE_ENV'] = args.env
    
    # Log startup information
    logger.info(f"Starting Time Capsule in {args.env.upper()} mode")
    logger.info(f"Server will listen on {args.host}:{args.port}")
    
    # Initialize database before starting the server
    @app.listener('before_server_start')
    async def initialize_db(app, loop):
        logger.info("Initializing database...")
        try:
            await init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            # Consider fatal error handling here
    
    # Register blueprints
    app.blueprint(chat_bp)
    app.blueprint(contacts_bp)
    
    # Start the server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        auto_reload=args.debug
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

@app.middleware('request')
async def rate_limit_middleware(request):
    """Rate limit middleware to prevent abuse."""
    # Skip rate limiting if disabled
    if not RATE_LIMIT["enabled"]:
        return None
    
    # Skip rate limiting for non-API routes
    if not request.path.startswith('/api/'):
        return None
    
    # Get client IP
    client_ip = request.remote_addr or request.ip
    
    # Skip rate limiting for whitelisted IPs
    if client_ip in RATE_LIMIT["whitelist"]:
        return None
    
    # Determine rate limit based on path
    if request.path.startswith('/api/admin'):
        limit = RATE_LIMIT["admin_rate"]
    elif request.path.startswith('/api/login') or request.path.endswith('/login'):
        limit = RATE_LIMIT["login_rate"]
    else:
        limit = RATE_LIMIT["default_rate"]
    
    # Generate key
    key = f"{client_ip}:{request.path.split('/')[2] if len(request.path.split('/')) > 2 else 'root'}"
    
    # Get current time (minute resolution)
    current_time = int(datetime.datetime.now().timestamp() // 60)
    
    # Initialize or cleanup expired entries
    if key not in rate_limit_storage or rate_limit_storage[key]["time"] != current_time:
        rate_limit_storage[key] = {"time": current_time, "count": 0}
    
    # Increment request count
    rate_limit_storage[key]["count"] += 1
    
    # Check if rate limit is exceeded
    if rate_limit_storage[key]["count"] > limit:
        logger.warning(f"Rate limit exceeded for {key}")
        return json_response({
            "status": "error",
            "message": "Rate limit exceeded. Please try again later.",
            "error_code": "RATE_LIMIT_EXCEEDED"
        }, status=429)
    
    return None

# Register error handlers for specific scenarios
@app.exception(NotFound)
async def handle_not_found(request, exception):
    """Handle 404 errors."""
    # Check if this is an API request
    if request.path.startswith('/api/'):
        return json_response({
            "status": "error",
            "message": "The requested resource was not found.",
            "error_code": "NOT_FOUND"
        }, status=404)
    
    # For non-API routes, serve the 404 page
    try:
        async with aiofiles.open(os.path.join(templates_folder, '404.html'), mode='r') as f:
            content = await f.read()
            return html(content, status=404)
    except:
        return html("<h1>404 - Not Found</h1><p>The requested resource could not be found.</p>", status=404)

@app.exception(Unauthorized)
async def handle_unauthorized(request, exception):
    """Handle 401 errors."""
    return json_response({
        "status": "error",
        "message": "Authentication required.",
        "error_code": "UNAUTHORIZED"
    }, status=401)

@app.exception(InvalidUsage)
async def handle_invalid_usage(request, exception):
    """Handle 400 errors."""
    return json_response({
        "status": "error",
        "message": "Invalid request: " + str(exception),
        "error_code": "INVALID_REQUEST"
    }, status=400)