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

def clear_chat_cache(chat_id=None):
    """Clear the chat cache for a specific chat or all chats"""
    if chat_id:
        if chat_id in _chat_cache:
            del _chat_cache[chat_id]
        if chat_id in _cache_expiry:
            del _cache_expiry[chat_id]
        chat_logger.debug(f"Cache cleared for chat {chat_id}")
    else:
        _chat_cache.clear()
        _cache_expiry.clear()
        chat_logger.debug("All chat cache cleared")

@chat_bp.route('/chats', methods=['GET'])
async def get_chats(request):
    request_id = getattr(request.ctx, 'request_id', str(uuid.uuid4())[:8])
    chat_logger.info(f"[API:{request_id}] GET /api/chat/chats request received")
    
    try:
        user_uuid = request.args.get('user_uuid')
        chat_logger.debug(f"[API:{request_id}] User UUID from args: {user_uuid}")
        
        if not user_uuid:
            chat_logger.warning(f"[API:{request_id}] Missing user_uuid parameter in GET /api/chat/chats request")
            return json({'error': 'User UUID is required'}, status=400)
        
        async with async_session() as session:
            chats = await ChatDB.get_sessions_by_user(session, user_uuid)
            chat_logger.info(f"[API:{request_id}] Found {len(chats)} chats for user {user_uuid[:8] if user_uuid else 'unknown'}")
            return json({'chats': [chat.to_dict() for chat in chats]})
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in GET /api/chat/chats: {str(e)}", exc_info=True)
        return json({'error': str(e)}, status=500)

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

@chat_bp.route('', methods=['POST', 'GET', 'HEAD'])
async def create_message(request):
    """
    API endpoint to create a new message.
    
    For GET: Returns user chat sessions (backward compatibility)
    For POST: Creates a new message and returns the AI response
    """
    request_id = str(uuid.uuid4())[:8]
    
    # Handle GET requests (backward compatibility)
    if request.method == 'GET' or request.method == 'HEAD':
        chat_logger.info(f"[API:{request_id}] GET /api/chat request received (backward compatibility)")
        
        # Extract user_uuid from query parameters or header
        user_uuid = request.args.get('user_uuid') or request.headers.get('X-User-UUID')
        
        # If no user_uuid is provided, return a temporary UUID and empty list
        # instead of returning a 400 error for better compatibility
        if not user_uuid:
            chat_logger.warning(f"[API:{request_id}] No user_uuid provided in GET request, returning empty response with temporary UUID")
            user_uuid = f"temp-{str(uuid.uuid4())}"
            return json({"sessions": [], "user_uuid": user_uuid})
        
        # Get chat sessions for this user
        try:
            async with async_session() as session:
                sessions = await ChatDB.get_sessions_by_user(session, user_uuid)
                return json([session.to_dict() for session in sessions])
        except Exception as e:
            chat_logger.error(f"[API:{request_id}] Error fetching chat sessions: {str(e)}")
            return json({"error": str(e)}, status=500)
    
    # Handle POST requests (creating a new message)
    chat_logger.info(f"[API:{request_id}] POST /api/chat request received")
    
    # Log headers for debugging
    headers = dict(request.headers)
    sanitized_headers = {k: v for k, v in headers.items() 
                      if not any(s in k.lower() for s in ['auth', 'key', 'token', 'secret'])}
    chat_logger.debug(f"[API:{request_id}] Request headers: {sanitized_headers}")
    
    try:
        # Parse the request data
        data = request.json
        chat_logger.debug(f"[API:{request_id}] Request body: {data}")
        
        # Extract message and user data
        message = data.get('message')
        chat_id = data.get('chat_id')
        user_uuid = data.get('user_uuid')
        
        # Log validation of required fields
        chat_logger.debug(f"[API:{request_id}] Validating request parameters - message: {bool(message)}, user_uuid: {bool(user_uuid)}")
        
        if not all([message, user_uuid]):
            missing_fields = []
            if not message:
                missing_fields.append('message')
            if not user_uuid:
                missing_fields.append('user_uuid')
                
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            chat_logger.warning(f"[API:{request_id}] {error_msg}. Request data: {data}")
            return json({'error': error_msg}, status=400)
        
        # Log message details
        chat_logger.info(f"[API:{request_id}] Processing message from user {user_uuid[:8] if user_uuid else 'unknown'} for chat {chat_id or 'new chat'}")
        chat_logger.debug(f"[API:{request_id}] Message content: '{message[:50]}...' ({len(message)} chars)")
        
        async with async_session() as session:
            # Create new chat if chat_id is not provided
            if not chat_id:
                chat_id = str(uuid.uuid4())
                chat_logger.info(f"[API:{request_id}] Creating new chat session with ID {chat_id}")
                await ChatDB.create_session(session, user_uuid, chat_id)
            else:
                chat_logger.info(f"[API:{request_id}] Using existing chat session {chat_id}")
                
            # Create user message
            message_id = str(uuid.uuid4())
            chat_logger.debug(f"[API:{request_id}] Adding user message {message_id}")
            await ChatDB.add_message(session, chat_id, message_id, message, is_user=True)
        
            # Get user data for personalization
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            user_data = user.to_dict() if user else None
            
            # Generate AI response using the LLM integration
            chat_logger.info(f"[API:{request_id}] Generating AI response with LLM integration")
            ai_response = await llm_response(message, user_data, chat_id, session)
            
            # Create AI message
            ai_message_id = str(uuid.uuid4())
            chat_logger.debug(f"[API:{request_id}] Adding AI message {ai_message_id}")
            await ChatDB.add_message(session, chat_id, ai_message_id, ai_response, is_user=False)
            
            # Clear cache for this chat
            clear_chat_cache(chat_id)
            chat_logger.debug(f"[API:{request_id}] Cleared cache for chat {chat_id}")
            
            chat_logger.info(f"[API:{request_id}] Successfully processed message and generated response")
            return json({
                'chat_id': chat_id,
                'response': ai_response
            })
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in POST /api/chat: {str(e)}", exc_info=True)
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
    """Handle chat messages within a session."""
    request_id = getattr(request.ctx, 'request_id', str(uuid.uuid4())[:8])
    
    try:
        if request.method == 'GET':
            chat_logger.info(f"[API:{request_id}] GET /api/chat/sessions/{session_id}/messages request received")
            
            # Check if user has access to this chat
            user_uuid = request.headers.get('x-user-uuid')
            if not user_uuid:
                return json({'error': 'User UUID is required'}, status=400)
            
            async with async_session() as session:
                chat = await ChatDB.get_session_by_uuid(session, session_id)
                
                if not chat:
                    return json({'error': 'Chat session not found'}, status=404)
                
                # Verify ownership (optional, based on your security model)
                if chat.user_uuid != user_uuid:
                    new_session_id = str(uuid.uuid4())
                    return json({
                        'error': 'Session belongs to another user',
                        'new_session_id': new_session_id
                    }, status=403)
                
                messages = await ChatDB.get_messages_by_session(session, session_id)
                
                # Convert to client-friendly format
                message_dicts = []
                for msg in messages:
                    msg_dict = msg.to_dict()
                    # Adapt to expected frontend format
                    msg_dict['sender'] = 'user' if msg.is_user else 'ai'
                    message_dicts.append(msg_dict)
                
                return json({
                    'status': 'success',
                    'data': message_dicts
                })
                
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
                session_id=session_id,
                message_uuid=user_msg_id,
                content=user_message,
                is_user=True
            )
            
            # Get user data for personalization
            user = await UserDB.get_user_by_uuid(session, user_uuid)
            user_data = user.to_dict() if user else None
            
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
                        session_id=session_id,
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
            
            # Format response
            response_data = {
                "message": ai_response,
                "session_id": session_id,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            
            chat_logger.info(f"[API:{request_id}] Response generated successfully")
            return json({"status": "success", "data": {"ai_response": response_data}})
    except Exception as e:
        chat_logger.error(f"[API:{request_id}] Error in add_chat_message: {str(e)}", exc_info=True)
        return json({"error": str(e)}, status=500) 