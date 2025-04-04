from sanic import Blueprint, response
from sanic.response import json
from db import ChatDB, MessageDB, async_session
import uuid
import time
from functools import lru_cache

chat_bp = Blueprint('chat', url_prefix='/api/chat')

# Cache chat history for 5 minutes
@lru_cache(maxsize=100)
async def get_cached_chat(chat_id):
    async with async_session() as session:
        return await ChatDB.get_chat(session, chat_id)

@chat_bp.route('/chats', methods=['GET'])
async def get_chats(request):
    try:
        user_uuid = request.args.get('user_uuid')
        if not user_uuid:
            return json({'error': 'User UUID is required'}, status=400)
        
        async with async_session() as session:
            chats = await ChatDB.get_chats_by_user(session, user_uuid)
            return json({'chats': chats})
    except Exception as e:
        return json({'error': str(e)}, status=500)

@chat_bp.route('/<chat_id>', methods=['GET'])
async def get_chat(request, chat_id):
    try:
        async with async_session() as session:
            # Try to get from cache first
            chat = await get_cached_chat(chat_id)
            if not chat:
                chat = await ChatDB.get_chat(session, chat_id)
                
            if not chat:
                return json({'error': 'Chat not found'}, status=404)
                
            messages = await MessageDB.get_messages_by_chat(session, chat_id)
            return json({
                'chat': chat,
                'messages': messages
            })
    except Exception as e:
        return json({'error': str(e)}, status=500)

@chat_bp.route('', methods=['POST'])
async def create_message(request):
    try:
        data = request.json
        message = data.get('message')
        chat_id = data.get('chat_id')
        user_uuid = data.get('user_uuid')
        
        if not all([message, user_uuid]):
            return json({'error': 'Message and user UUID are required'}, status=400)
        
        async with async_session() as session:
            # Create new chat if chat_id is not provided
            if not chat_id:
                chat_id = str(uuid.uuid4())
                await ChatDB.create_chat(session, chat_id, user_uuid)
                
            # Create user message
            message_id = str(uuid.uuid4())
            await MessageDB.create_message(session, message_id, chat_id, user_uuid, message, 'user')
            
            # Generate AI response (placeholder for now)
            ai_response = "这是一个测试回复。实际项目中，这里会调用AI模型生成回复。"
            
            # Create AI message
            ai_message_id = str(uuid.uuid4())
            await MessageDB.create_message(session, ai_message_id, chat_id, 'ai', ai_response, 'ai')
            
            # Clear cache for this chat
            get_cached_chat.cache_clear()
            
            return json({
                'chat_id': chat_id,
                'response': ai_response
            })
    except Exception as e:
        return json({'error': str(e)}, status=500)

@chat_bp.route('/<chat_id>', methods=['DELETE'])
async def delete_chat(request, chat_id):
    try:
        async with async_session() as session:
            await ChatDB.delete_chat(session, chat_id)
            # Clear cache for this chat
            get_cached_chat.cache_clear()
            return json({'message': 'Chat deleted successfully'})
    except Exception as e:
        return json({'error': str(e)}, status=500) 