#!/usr/bin/env python
"""
Time Capsule Server

This script starts the Time Capsule server with appropriate configuration.
"""

import sys
import logging
from app.main import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('server.log')
    ]
)

# Reduce noise from specific loggers
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('tortoise').setLevel(logging.WARNING)
logging.getLogger('sanic.access').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting Time Capsule server...")
        app.run(
            host="0.0.0.0",
            port=8080, 
            debug=True,
            access_log=True
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}", exc_info=True)
        sys.exit(1) 