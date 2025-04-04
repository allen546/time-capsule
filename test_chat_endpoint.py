#!/usr/bin/env python
"""
Test script for the chat endpoint

This script tests the chat endpoint that interacts with the DeepSeek API
"""

import os
import sys
from pathlib import Path
import json

# Add the project root to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

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

def register_user():
    """Register a test user and return the access token"""
    print("Registering test user...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/users/register",
            json=TEST_USER,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Error registering user: {response.text}")
            # Try logging in if registration fails
            return login_user()
    except Exception as e:
        print(f"Error during registration: {str(e)}")
        return None

def login_user():
    """Login the test user and return the access token"""
    print("Logging in test user...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/users/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password_hash"]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Error logging in: {response.text}")
            return None
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return None

def test_chat_endpoint(token):
    """Test the chat endpoint with a simple message"""
    print("Testing chat endpoint...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/conversation/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "message": "你好，年轻的我",
                "language": "zh"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            print("Chat endpoint test successful!")
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"Error testing chat endpoint: {response.text}")
            return False
    except Exception as e:
        print(f"Error during chat test: {str(e)}")
        return False

def main():
    """Run the test"""
    # Check if the server is running
    try:
        response = requests.get(f"{BASE_URL}", timeout=10)
        if response.status_code != 200:
            print(f"Error: Server not running at {BASE_URL}")
            return
    except requests.ConnectionError:
        print(f"Error: Server not running at {BASE_URL}")
        return
    except Exception as e:
        print(f"Error checking server: {str(e)}")
        return
    
    # Get access token
    token = register_user()
    if not token:
        print("Failed to get access token")
        return
    
    # Test chat endpoint
    success = test_chat_endpoint(token)
    
    if success:
        print("\nChat endpoint test completed successfully!")
    else:
        print("\nChat endpoint test failed.")

if __name__ == "__main__":
    main() 