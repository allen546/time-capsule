"""
Chat API Module

This module provides API endpoint for DeepSeek chat integration with the Time Capsule application.
"""

import logging
from typing import Dict, List, Any, Optional

from sanic import response
from sanic.request import Request
from sanic.response import json as json_response

from app.db import Message, MessageSender, User
from app.ai import chat_completion
from app.main import login_required, get_authorized_conversation, add_message_to_conversation, format_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_routes(app):
    """
    Register chat API routes with the Sanic app.
    
    Args:
        app: The Sanic application instance
    """
    app.add_route(
        chat_with_young_self,
        "/api/conversation/chat",
        methods=["POST"]
    )


@login_required
async def chat_with_young_self(request: Request):
    """
    Chat with the AI version of the user's younger self.
    
    Args:
        request: The Sanic request object
        
    Returns:
        JSON response with the AI response
    """
    user = request.ctx.user
    data = request.json
    
    # Validate request data
    if not data or "message" not in data:
        return json_response({"error": "Message field is required"}, status=400)
    
    user_message = data["message"]
    if not user_message or not isinstance(user_message, str):
        return json_response({"error": "Message must be a non-empty string"}, status=400)
    
    # Get language preference (default to Chinese)
    language = data.get("language", "zh")
    
    # Get conversation if it exists
    conversation = await get_authorized_conversation(user.id)
    if not conversation:
        return json_response({"error": "No conversation found"}, status=404)
    
    try:
        # Add user message to conversation
        user_message_obj = await add_message_to_conversation(
            user_id=user.id,
            sender=MessageSender.USER,
            content=user_message
        )
        
        if not user_message_obj:
            return json_response({"error": "Failed to add user message"}, status=500)
        
        # Get conversation history
        messages = await Message.filter(conversation_id=conversation.id).order_by("timestamp")
        message_list = [{"sender": msg.sender, "content": msg.content} for msg in messages]
        
        # Get user profile data
        user_data = {}
        user_obj = await User.get(id=user.id)
        if user_obj:
            user_data = {
                "real_name": user_obj.real_name,
                "age": user_obj.age,
                "basic_data": user_obj.basic_data
            }
            
            # Get additional profile data if available
            if hasattr(user_obj, "profiles") and user_obj.profiles:
                profile = await user_obj.profiles.first()
                if profile:
                    user_data.update(profile.data)
        
        # Generate AI response using DeepSeek API
        ai_response = await chat_completion(
            messages=message_list,
            user_data=user_data,
            language=language
        )
        
        # Add AI response to conversation
        ai_message_obj = await add_message_to_conversation(
            user_id=user.id,
            sender=MessageSender.BOT,
            content=ai_response
        )
        
        if not ai_message_obj:
            return json_response({"error": "Failed to add AI response"}, status=500)
        
        # Format the response message
        formatted_message = await format_message(ai_message_obj)
        
        return json_response({
            "success": True,
            "message": formatted_message
        })
        
    except Exception as e:
        logger.error(f"Error in chat processing: {str(e)}", exc_info=True)
        return json_response({"error": f"Failed to process chat: {str(e)}"}, status=500) 