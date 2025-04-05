from sanic import Blueprint, response
from sanic.response import json
from db import ChatDB, async_session, UserDB
import uuid
import time
import logging
import json as json_module
from functools import lru_cache
import sys
import os
import importlib
import datetime

# Import LLM response function from utils instead of app
from utils.llm_client import llm_response

# Get chat-specific logger
chat_logger = logging.getLogger('chat')

chat_bp = Blueprint('chat', url_prefix='/api/chat')

# Cache chat history for 5 minutes
_chat_cache = {}
_cache_expiry = {}

async def get_cached_chat(chat_id):
    """Get a chat session from cache or database with proper async caching"""
    now = time.time()
    
    # Check cache first
    if chat_id in _chat_cache and now < _cache_expiry.get(chat_id, 0):
        chat_logger.debug(f"Chat {chat_id} found in cache")
        return _chat_cache[chat_id]
    
    # Not in cache or expired, fetch from database
    chat_logger.debug(f"Chat {chat_id} not in cache, fetching from database")
    return None  # Return None and let the caller fetch from the database

def clear_chat_cache(chat_id):
    """Clear the cache for a specific chat"""
    if chat_id in _chat_cache:
        del _chat_cache[chat_id]
    if chat_id in _cache_expiry:
        del _cache_expiry[chat_id]

@chat_bp.route('/<chat_id>', methods=['GET'])
async def get_chat(request, chat_id):
    request_id = getattr(request.ctx, 'request_id', str(uuid.uuid4())[:8])
    chat_logger.info(f"[API:{request_id}] GET /api/chat/{chat_id} request received")
    
    try:
        # Try to get from cache first
        chat = await get_cached_chat(chat_id)
        
        async with async_session() as session:
            # If not in cache, fetch from database
            if not chat:
                chat_logger.debug(f"[API:{request_id}] Chat {chat_id} not in cache, fetching from database")
                chat = await ChatDB.get_session_by_uuid(session, chat_id)
                
                # Cache the result if found
                if chat:
                    chat_dict = chat.to_dict()
                    _chat_cache[chat_id] = chat_dict
                    _cache_expiry[chat_id] = time.time() + 300  # 5 minutes
                
            if not chat:
                chat_logger.warning(f"[API:{request_id}] Chat {chat_id} not found in database")
                return json({'error': 'Chat not found'}, status=404)
            
            chat_logger.debug(f"[API:{request_id}] Retrieved chat {chat_id}")    
            messages = await ChatDB.get_messages_by_session(session, chat_id)
            chat_logger.info(f"[API:{request_id}] Retrieved {len(messages)} messages for chat {chat_id}")
            
            # Convert objects to dictionaries while the session is still active
            message_dicts = [msg.to_dict() for msg in messages]
            
            # If chat is from cache, it's already a dict, otherwise convert it
            if isinstance(chat, dict):
                chat_dict = chat
            else:
                chat_dict = chat.to_dict()
            
            # Update message count
            chat_dict["message_count"] = len(messages)
            
            return json({
                'chat': chat_dict,
                'messages': message_dicts
            })
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in GET /api/chat/{chat_id}: {str(e)}", exc_info=True)
        return json({'error': str(e)}, status=500)

@chat_bp.route('/<chat_id>', methods=['DELETE'])
async def delete_chat(request, chat_id):
    request_id = getattr(request.ctx, 'request_id', str(uuid.uuid4())[:8])
    chat_logger.info(f"[API:{request_id}] DELETE /api/chat/{chat_id} request received")
    
    try:
        async with async_session() as session:
            chat_logger.debug(f"[API:{request_id}] Deleting chat session {chat_id}")
            await ChatDB.delete_session(session, chat_id)
            
            # Clear cache for this chat
            clear_chat_cache(chat_id)
            chat_logger.debug(f"[API:{request_id}] Cleared cache for chat {chat_id}")
            
            chat_logger.info(f"[API:{request_id}] Successfully deleted chat session {chat_id}")
            return json({'message': 'Chat deleted successfully'})
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in DELETE /api/chat/{chat_id}: {str(e)}", exc_info=True)
        return json({'error': str(e)}, status=500)

# Add routes for sessions
@chat_bp.route('/sessions/<session_id>', methods=['GET', 'DELETE'])
async def session_handler(request, session_id):
    """Handle get or delete operations for a chat session."""
    if request.method == 'GET':
        return await get_chat(request, session_id)
    elif request.method == 'DELETE':
        return await delete_chat(request, session_id)

@chat_bp.route('/sessions/<session_id>/messages', methods=['GET', 'POST'])
async def session_messages_handler(request, session_id):
    """Handle chat messages for a specific session."""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        # Get method will return all messages for the session
        if request.method == 'GET':
            chat_logger.info(f"[API:{request_id}] GET /api/chat/sessions/{session_id}/messages request received")
            
            # Get user_uuid from headers
            user_uuid = request.headers.get('x-user-uuid')
            
            if not user_uuid:
                chat_logger.error(f"[API:{request_id}] No user_uuid provided in GET request")
                return json({'error': 'User UUID is required'}, status=400)
            
            async with async_session() as session:
                # Get chat session info
                chat = await ChatDB.get_session_by_uuid(session, session_id)
                
                if not chat:
                    chat_logger.warning(f"[API:{request_id}] Chat session {session_id} not found")
                    return json({'error': 'Chat session not found'}, status=404)
                
                # Check if user has permission to access this chat
                if chat.user_uuid != user_uuid:
                    chat_logger.warning(f"[API:{request_id}] Unauthorized access attempt to session {session_id}")
                    return json({
                        'error': 'Session belongs to another user',
                        'new_session_id': str(uuid.uuid4())
                    }, status=403)
                
                # Get all messages for this session
                messages = await ChatDB.get_messages_by_session(session, session_id)
                
                # Format messages for response - ensure they match client-side expectations
                formatted_messages = []
                for msg in messages:
                    formatted_messages.append({
                        'id': msg.message_uuid,
                        'session_id': msg.session_uuid,
                        'is_user': msg.is_user,
                        'content': msg.content,  # use 'content' not 'message'
                        'created_at': msg.created_at.isoformat()
                    })
                
                # Return messages
                return json({
                    'status': 'success',
                    'data': formatted_messages
                })
        # POST method will add a new message to the session
        elif request.method == 'POST':
            return await add_chat_message(request, session_id)
                
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in session_messages_handler: {str(e)}", exc_info=True)
        return json({'error': str(e)}, status=500)

@chat_bp.route('/sessions', methods=['GET'])
async def get_chat_sessions(request):
    """Get all chat sessions for a user."""
    chat_logger.info("GET request to /api/chat/sessions")
    user_uuid = request.args.get('user_uuid') or request.headers.get('X-User-UUID')
    
    if not user_uuid:
        chat_logger.error("No user_uuid provided in GET request")
        return json({"error": "No user_uuid provided"}, status=400)
    
    try:
        async with async_session() as db_session:
            sessions = await ChatDB.get_sessions_by_user(db_session, user_uuid)
            return json([session.to_dict() for session in sessions])
    except Exception as e:
        chat_logger.error(f"Error fetching chat sessions: {str(e)}")
        return json({"error": str(e)}, status=500)

@chat_bp.route('/sessions', methods=['POST'])
async def create_chat_session(request):
    """Create a new chat session."""
    chat_logger.info("POST request to /api/chat/sessions")
    request_data = request.json
    user_uuid = request_data.get('user_uuid')
    
    if not user_uuid:
        chat_logger.error("No user_uuid provided in POST request")
        return json({"error": "No user_uuid provided"}, status=400)
    
    try:
        session_id = str(uuid.uuid4())
        async with async_session() as db_session:
            session = await ChatDB.create_session(db_session, user_uuid, session_id)
            return json(session.to_dict())
    except Exception as e:
        chat_logger.error(f"Error creating chat session: {str(e)}")
        return json({"error": str(e)}, status=500)

async def add_chat_message(request, session_id):
    """Add a new message to a chat session and get an AI response."""
    request_id = str(uuid.uuid4())[:8]
    chat_logger.info(f"[API:{request_id}] POST request to /api/chat/sessions/{session_id}/messages")
    
    # Get request data
    data = request.json
    user_message = data.get('message', '')
    user_uuid = data.get('user_uuid')
    
    if not user_message:
        chat_logger.error(f"[API:{request_id}] No message provided")
        return json({"error": "No message provided"}, status=400)
    
    if not user_uuid:
        chat_logger.error(f"[API:{request_id}] No user_uuid provided")
        return json({"error": "No user_uuid provided"}, status=400)
    
    try:
        async with async_session() as session:
            # Verify the session exists and belongs to this user
            chat_session = await ChatDB.get_session_by_uuid(session, session_id)
            if not chat_session:
                chat_logger.warning(f"[API:{request_id}] Chat session not found")
                return json({"error": "Chat session not found"}, status=404)
            
            if chat_session.user_uuid != user_uuid:
                chat_logger.warning(f"[API:{request_id}] Session belongs to another user")
                # Create a new session for this user
                new_session_id = str(uuid.uuid4())
                await ChatDB.create_session(session, user_uuid, new_session_id)
                return json({"error": "Session belongs to another user", 
                            "new_session_id": new_session_id}, status=403)
            
            # Store user message
            user_msg_id = str(uuid.uuid4())
            chat_logger.info(f"[API:{request_id}] Adding user message {user_msg_id[:8]}")
            await ChatDB.add_message(
                session, 
                session_uuid=session_id,
                message_uuid=user_msg_id,
                content=user_message,
                is_user=True
            )
            
            # Get user data for personalization
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            user_data = user.to_dict() if user else None
            
            # Enhanced debugging - full dump of user data to diagnose profile issues
            chat_logger.warning(f"==== USER DATA DUMP ==== [API:{request_id}] User {user_uuid[:8]}")
            chat_logger.warning(f"USER OBJECT: {user}")
            chat_logger.warning(f"USER DATA DICT: {user_data}")
            
            # Check if user profile is complete
            if user_data is None:
                # Log the fact that we're redirecting due to missing user data
                chat_logger.warning(f"!!!! NO USER DATA REDIRECT !!!! [API:{request_id}] User {user_uuid[:8]}")
                
                return json({
                    'status': 'redirect',
                    'message': '请先创建您的个人资料，以便我们能为您提供个性化服务。',
                    'redirect_url': '/profile'
                })
            else:
                # Check if name is missing or if profile_data is empty
                has_name = bool(user_data.get('name'))
                profile_data_is_dict = isinstance(user_data.get('profile_data'), dict)
                profile_data_has_entries = len(user_data.get('profile_data', {})) > 0 if profile_data_is_dict else False
                
                profile_complete = has_name and profile_data_is_dict and profile_data_has_entries
                
                # Add distinctive log message that will be easy to search for
                chat_logger.warning(f"!!!! PROFILE CHECK !!!! [API:{request_id}] User {user_uuid[:8]} - " +
                               f"has_name={has_name}, " +
                               f"profile_data_is_dict={profile_data_is_dict}, " + 
                               f"profile_data_has_entries={profile_data_has_entries}, " +
                               f"profile_complete={profile_complete}")
                
                if not profile_complete:
                    # Log detailed info about the profile
                    chat_logger.warning(f"!!!! PROFILE INCOMPLETE !!!! [API:{request_id}] User {user_uuid[:8]} - " +
                                   f"name='{user_data.get('name')}', " +
                                   f"profile_data_type={type(user_data.get('profile_data')).__name__}, " +
                                   f"profile_data={user_data.get('profile_data')}")
                    
                    # Log the fact that we're redirecting
                    chat_logger.warning(f"!!!! REDIRECTING TO PROFILE !!!! [API:{request_id}] User {user_uuid[:8]}")
                    
                    return json({
                        'status': 'redirect',
                        'message': '请先完善您的个人资料，以便我更好地为您提供服务。',
                        'redirect_url': '/profile'
                    })
                else:
                    chat_logger.warning(f"!!!! PROFILE COMPLETE !!!! [API:{request_id}] User {user_uuid[:8]} - Proceeding with response")
            
            # Generate AI response
            chat_logger.info(f"[API:{request_id}] Generating AI response")
            try:
                ai_response = await llm_response(user_message, user_data, session_id, session)
                
                # Only store AI response if it's not an error or mock message
                if not (ai_response.startswith("Error:") or 
                        ai_response.startswith("Echo:") or
                        "this is just a mock response" in ai_response):
                    # Store AI response in database
                    ai_msg_id = str(uuid.uuid4())
                    chat_logger.info(f"[API:{request_id}] Adding AI message {ai_msg_id[:8]}")
                    await ChatDB.add_message(
                        session, 
                        session_uuid=session_id,
                        message_uuid=ai_msg_id,
                        content=ai_response,
                        is_user=False
                    )
                else:
                    chat_logger.info(f"[API:{request_id}] Not storing error/mock response in history")
            except Exception as e:
                chat_logger.error(f"[API:{request_id}] Error generating AI response: {str(e)}")
                ai_response = f"Error: {str(e)}"
                # We don't store error responses in the database
            
            # Format response to match expected client format
            response_data = {
                "content": ai_response,  # Change 'message' to 'content' to match client expectation
                "session_id": session_id,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "id": ai_msg_id if 'ai_msg_id' in locals() else str(uuid.uuid4()),
                "is_user": False
            }
            
            chat_logger.info(f"[API:{request_id}] Response generated successfully")
            return json({"status": "success", "data": {"ai_response": response_data}})
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in add_chat_message: {str(e)}", exc_info=True)
        return json({"error": str(e)}, status=500) 