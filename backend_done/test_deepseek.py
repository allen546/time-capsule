#!/usr/bin/env python3
"""
Test script for DeepSeek API integration
"""

import asyncio
import os
import logging
import json
import aiohttp
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# API configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat-v3"

async def test_deepseek_api():
    """Test the DeepSeek API with a simple message."""
    logger.info(f"Testing DeepSeek API with model: {DEEPSEEK_MODEL}")
    
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set. Please set it before running this test.")
        logger.info("Mock response: Echo: Hello, this is a test")
        return
    
    # Prepare test message
    system_prompt = "You are a helpful assistant."
    user_message = "Hello, this is a test message. Please respond with a short greeting."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Prepare API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    # Create SSL context to handle certificate verification issues
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Make API request
        logger.info(f"Sending request to DeepSeek API")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
                ssl=ssl_context
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"DeepSeek API request failed with status {response.status}: {error_text}")
                    return
                
                # Process successful response
                result = await response.json()
                logger.info("Successfully received response from DeepSeek API")
                
                response_text = result["choices"][0]["message"]["content"]
                logger.info(f"API Response: {response_text}")
    
    except Exception as e:
        logger.error(f"Error in DeepSeek API request: {str(e)}", exc_info=True)
        logger.warning("If you're seeing API errors, make sure your API key is valid and has sufficient balance.")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_deepseek_api()) 