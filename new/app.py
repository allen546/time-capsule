#!/usr/bin/env python
"""
Time Capsule Server

This script starts the Time Capsule server with Sanic framework.
"""

import logging
import os
from sanic import Sanic
from sanic.response import html, json, file, redirect
import aiofiles

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

@app.route('/api/health')
async def health_check(request):
    """API health check endpoint."""
    return json({"status": "healthy"})

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