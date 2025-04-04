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
import aiofiles
from functools import wraps

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

@app.route('/health')
async def health_check(request):
    return text("OK")

@app.route('/api/info')
async def api_info(request):
    return json({
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
        
        # Load existing users
        async with aiofiles.open(users_file, mode='r') as f:
            content = await f.read()
            users = json.loads(content) if content else {}
        
        # Add new user with initial empty profile
        users[user_uuid] = {
            "name": None,
            "age": None,
            "created_at": str(datetime.datetime.now())
        }
        
        # Save updated users
        async with aiofiles.open(users_file, mode='w') as f:
            await f.write(json.dumps(users, indent=2))
        
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
        
        # Validate required data
        if not name or not isinstance(name, str):
            return json_response({"status": "error", "message": "Invalid name"}, status=400)
        
        # Load existing users
        async with aiofiles.open(users_file, mode='r') as f:
            content = await f.read()
            users = json.loads(content) if content else {}
        
        # Create or update user profile
        if user_uuid not in users:
            users[user_uuid] = {
                "created_at": str(datetime.datetime.now())
            }
        
        # Update profile fields
        users[user_uuid]["name"] = name
        users[user_uuid]["age"] = age
        users[user_uuid]["updated_at"] = str(datetime.datetime.now())
        
        # Save updated users
        async with aiofiles.open(users_file, mode='w') as f:
            await f.write(json.dumps(users, indent=2))
        
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
        
        # Load existing users
        async with aiofiles.open(users_file, mode='r') as f:
            content = await f.read()
            users = json.loads(content) if content else {}
        
        # Check if user exists
        if user_uuid not in users:
            return json_response({"status": "error", "message": "User not found"}, status=404)
        
        # Return user profile
        profile = users[user_uuid]
        return json_response({
            "status": "success",
            "data": {
                "uuid": user_uuid,
                "name": profile.get("name"),
                "age": profile.get("age")
            }
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
        
        # Log the reset event (optional, for analytics)
        logger.info(f"Device reset request for UUID: {old_uuid}")
        
        # Load existing users
        async with aiofiles.open(users_file, mode='r') as f:
            content = await f.read()
            users = json.loads(content) if content else {}
        
        # Mark old user data as reset (optional, for analytics)
        if old_uuid in users:
            users[old_uuid]["reset_at"] = str(datetime.datetime.now())
            users[old_uuid]["is_reset"] = True
            
            # Save updated users
            async with aiofiles.open(users_file, mode='w') as f:
                await f.write(json.dumps(users, indent=2))
        
        return json_response({"status": "success", "message": "Device reset completed"})
    except Exception as e:
        logger.error(f"Error handling device reset: {str(e)}", exc_info=True)
        return json_response({"status": "error", "message": "Server error"}, status=500)

if __name__ == "__main__":
    try:
        logger.info("Starting Time Capsule server...")
        app.run(
            host="0.0.0.0",  # Allow external connections
            port=8080,
            debug=True,
            access_log=True
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}", exc_info=True) 