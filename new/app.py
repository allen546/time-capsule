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

@app.route('/diary')
async def diary(request):
    """Serve the diary page."""
    async with aiofiles.open(os.path.join(templates_folder, 'diary.html'), mode='r') as f:
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

# Diary API endpoints
@app.route('/api/diary/entries', methods=['GET'])
async def get_diary_entries(request):
    """Get all diary entries for a user."""
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get diary file path
        diary_file = os.path.join(data_folder, f'diary_{user_uuid}.json')
        
        # If file doesn't exist, return empty array
        if not os.path.exists(diary_file):
            return json_response({"status": "success", "data": []})
        
        # Read diary entries
        async with aiofiles.open(diary_file, mode='r') as f:
            content = await f.read()
            entries = json.loads(content) if content else []
        
        # Sort by pinned status and then by date (newest first)
        sorted_entries = sorted(entries, key=lambda x: (not x.get('pinned', False), x.get('date', ''), x.get('created_at', '')), reverse=True)
        
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
    try:
        # Get user UUID from header
        user_uuid = request.headers.get('X-User-UUID')
        if not user_uuid:
            return json_response({"status": "error", "message": "Missing user UUID"}, status=400)
        
        # Get diary entry data
        data = request.json
        if not data:
            return json_response({"status": "error", "message": "Missing diary entry data"}, status=400)
        
        # Validate required fields
        title = data.get('title')
        content = data.get('content')
        date = data.get('date')
        
        if not title or not isinstance(title, str):
            return json_response({"status": "error", "message": "Invalid title"}, status=400)
        
        if not content or not isinstance(content, str):
            return json_response({"status": "error", "message": "Invalid content"}, status=400)
        
        if not date or not isinstance(date, str):
            return json_response({"status": "error", "message": "Invalid date"}, status=400)
        
        # Get diary file path
        diary_file = os.path.join(data_folder, f'diary_{user_uuid}.json')
        
        # Read existing entries or create empty array
        entries = []
        if os.path.exists(diary_file):
            async with aiofiles.open(diary_file, mode='r') as f:
                content = await f.read()
                entries = json.loads(content) if content else []
        
        # Create new entry with ID
        entry_id = str(uuid.uuid4())
        new_entry = {
            "id": entry_id,
            "title": title,
            "content": content,
            "date": date,
            "mood": data.get('mood', 'calm'),
            "pinned": data.get('pinned', False),
            "created_at": str(datetime.datetime.now()),
            "updated_at": str(datetime.datetime.now())
        }
        
        # Add new entry
        entries.append(new_entry)
        
        # Save updated entries
        async with aiofiles.open(diary_file, mode='w') as f:
            await f.write(json.dumps(entries, indent=2))
        
        # Return the new entry
        return json_response({
            "status": "success",
            "message": "Diary entry created successfully",
            "data": new_entry
        })
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
        
        # Get diary file path
        diary_file = os.path.join(data_folder, f'diary_{user_uuid}.json')
        
        # Check if diary file exists
        if not os.path.exists(diary_file):
            return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
        
        # Read existing entries
        async with aiofiles.open(diary_file, mode='r') as f:
            content = await f.read()
            entries = json.loads(content) if content else []
        
        # Find entry by ID
        entry_index = None
        for i, entry in enumerate(entries):
            if entry.get('id') == entry_id:
                entry_index = i
                break
        
        # Return error if entry not found
        if entry_index is None:
            return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
        
        # Update entry fields
        entries[entry_index]['title'] = data.get('title', entries[entry_index]['title'])
        entries[entry_index]['content'] = data.get('content', entries[entry_index]['content'])
        entries[entry_index]['date'] = data.get('date', entries[entry_index]['date'])
        entries[entry_index]['mood'] = data.get('mood', entries[entry_index]['mood'])
        entries[entry_index]['pinned'] = data.get('pinned', entries[entry_index]['pinned'])
        entries[entry_index]['updated_at'] = str(datetime.datetime.now())
        
        # Save updated entries
        async with aiofiles.open(diary_file, mode='w') as f:
            await f.write(json.dumps(entries, indent=2))
        
        # Return the updated entry
        return json_response({
            "status": "success",
            "message": "Diary entry updated successfully",
            "data": entries[entry_index]
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
        
        # Get diary file path
        diary_file = os.path.join(data_folder, f'diary_{user_uuid}.json')
        
        # Check if diary file exists
        if not os.path.exists(diary_file):
            return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
        
        # Read existing entries
        async with aiofiles.open(diary_file, mode='r') as f:
            content = await f.read()
            entries = json.loads(content) if content else []
        
        # Find and remove entry by ID
        new_entries = [entry for entry in entries if entry.get('id') != entry_id]
        
        # Return error if entry not found (length didn't change)
        if len(new_entries) == len(entries):
            return json_response({"status": "error", "message": "Diary entry not found"}, status=404)
        
        # Save updated entries
        async with aiofiles.open(diary_file, mode='w') as f:
            await f.write(json.dumps(new_entries, indent=2))
        
        return json_response({
            "status": "success",
            "message": "Diary entry deleted successfully"
        })
    except Exception as e:
        logger.error(f"Error deleting diary entry: {str(e)}", exc_info=True)
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