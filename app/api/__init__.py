"""
API Package for Time Capsule

This package contains API endpoints for the Time Capsule application.
"""

from app.api.chat import register_routes as register_chat_routes

def register_all_routes(app):
    """
    Register all API routes with the Sanic app.
    
    Args:
        app: The Sanic application instance
    """
    register_chat_routes(app) 