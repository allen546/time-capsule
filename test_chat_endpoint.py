#!/usr/bin/env python
"""
Test script for the chat endpoint

This script tests the chat endpoint that interacts with the DeepSeek API
"""

import asyncio
import os
import sys
from pathlib import Path
import uuid
import json

# Add the project root to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aiohttp

# Base URL for the API
BASE_URL = "http://localhost:8080"

# Test data
TEST_USER = {
    "username": "test_user",
    "password_hash": "password123",
    "real_name": "Test User",
    "age": 40,
    "basic_data": "This is a test user for the chat endpoint"
}

async def register_user():
    """Register a test user and return the access token"""
    print("Registering test user...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/users/register",
            json=TEST_USER
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("access_token")
            else:
                text = await response.text()
                print(f"Error registering user: {text}")
                # Try logging in if registration fails
                return await login_user()

async def login_user():
    """Login the test user and return the access token"""
    print("Logging in test user...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/users/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password_hash"]
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("access_token")
            else:
                text = await response.text()
                print(f"Error logging in: {text}")
                return None

async def create_conversation(token):
    """Create or update a conversation for the test user"""
    print("Creating/updating test conversation...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/conversation",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Test Chat Conversation"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                print("Conversation created/updated successfully!")
                return True
            else:
                text = await response.text()
                print(f"Error creating/updating conversation: {text}")
                return False

async def test_chat_endpoint(token):
    """Test the chat endpoint with a simple message"""
    print("Testing chat endpoint...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/conversation/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "你好，年轻的我",
                "language": "zh"
            }
        ) as response:
            if response.status == 200:
                data = await response.json()
                print("Chat endpoint test successful!")
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return True
            else:
                text = await response.text()
                print(f"Error testing chat endpoint: {text}")
                return False

async def main():
    """Run the test"""
    # Check if the server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}") as response:
                if response.status != 200:
                    print(f"Error: Server not running at {BASE_URL}")
                    return
    except aiohttp.ClientConnectorError:
        print(f"Error: Server not running at {BASE_URL}")
        return
    
    # Get access token
    token = await register_user()
    if not token:
        print("Failed to get access token")
        return
    
    # Create conversation
    success = await create_conversation(token)
    if not success:
        print("Failed to create/update conversation")
        return
    
    # Test chat endpoint
    success = await test_chat_endpoint(token)
    
    if success:
        print("\nChat endpoint test completed successfully!")
    else:
        print("\nChat endpoint test failed.")

if __name__ == "__main__":
    asyncio.run(main()) 