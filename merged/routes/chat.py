from sanic import Blueprint, response
from sanic.response import json
from db import ChatDB, async_session
import uuid
import time
import logging
import json as json_module
from functools import lru_cache

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

@chat_bp.route('', methods=['POST'])
async def create_message(request):
    request_id = getattr(request.ctx, 'request_id', str(uuid.uuid4())[:8])
    chat_logger.info(f"[API:{request_id}] POST /api/chat request received")
    
    # Log headers for debugging
    headers = dict(request.headers)
    sanitized_headers = {k: v for k, v in headers.items() 
                       if not any(s in k.lower() for s in ['auth', 'key', 'token', 'secret'])}
    chat_logger.debug(f"[API:{request_id}] Request headers: {sanitized_headers}")
    
    try:
        # Log request body
        try:
            data = request.json
            chat_logger.debug(f"[API:{request_id}] Request body: {data}")
        except Exception as json_error:
            chat_logger.error(f"[API:{request_id}] Failed to parse JSON body: {str(json_error)}")
            request_body = request.body.decode('utf-8') if hasattr(request, 'body') else 'No body'
            chat_logger.error(f"[API:{request_id}] Raw request body: {request_body[:200]}")
            return json({'error': f'Invalid JSON in request body: {str(json_error)}'}, status=400)
        
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
            
            # Generate AI response (placeholder for now)
            chat_logger.debug(f"[API:{request_id}] Generating AI response")
            ai_response = "这是一个测试回复。实际项目中，这里会调用AI模型生成回复。"
            
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