#!/usr/bin/env python
"""
Test script for the AI module

This script tests the AI integration functions in app/ai.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ai import generate_young_self_response, do_api_request


async def test_young_self_response():
    """Test the young self response generation function"""
    print("Testing young self response generation...")

    # Example user profile
    user_profile = {
        "real_name": "张伟",
        "age": 35,
        "basic_data": "大学毕业于2009年，主修计算机科学。喜欢篮球和音乐，擅长编程。"
    }

    # Example conversation history
    conversation_history = [
        {"sender": "USER", "content": "你好，年轻的我。你现在在做什么？"},
        {"sender": "BOT", "content": "嘿！我正在准备下周的考试，压力有点大，但还好。你呢？"},
        {"sender": "USER", "content": "我想知道你对未来有什么计划？"}
    ]

    # Test Chinese response
    print("\nTesting Chinese response:")
    response_zh = await generate_young_self_response(
        conversation_history=conversation_history,
        user_profile=user_profile,
        language="zh",
        verify_ssl=False  # Disable SSL verification for testing
    )
    print(f"Response (Chinese): {response_zh}")

    # Test English response
    print("\nTesting English response:")
    response_en = await generate_young_self_response(
        conversation_history=conversation_history,
        user_profile=user_profile,
        language="en",
        verify_ssl=False  # Disable SSL verification for testing
    )
    print(f"Response (English): {response_en}")


async def test_direct_api_request():
    """Test direct API request to DeepSeek"""
    print("\nTesting direct API request...")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a short joke about programming."}
    ]
    
    response = await do_api_request(
        messages=messages,
        verify_ssl=False  # Disable SSL verification for testing
    )
    
    if "error" in response and response["error"]:
        print(f"Error: {response['message']}")
    else:
        try:
            content = response["choices"][0]["message"]["content"]
            print(f"API Response: {content}")
        except (KeyError, IndexError) as e:
            print(f"Error extracting content: {e}")
            print(f"Raw response: {response}")


async def main():
    """Run all tests"""
    # Check if API key is set
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("Warning: DEEPSEEK_API_KEY environment variable is not set.")
        print("Make sure a valid API key is configured in the app/ai.py file.")
        print("For production use, set the DEEPSEEK_API_KEY environment variable.")

    # Create prompts directory and templates if needed
    print("Checking prompt templates...")
    from app.ai import ensure_prompt_directory, load_prompt_template
    
    ensure_prompt_directory()
    en_template = load_prompt_template("en")
    zh_template = load_prompt_template("zh")
    
    print(f"English template loaded: {len(en_template)} characters")
    print(f"Chinese template loaded: {len(zh_template)} characters")

    # Run the tests using real API connection with SSL verification disabled
    print("\nIMPORTANT: Using real API connection with SSL verification disabled.")
    print("This is for testing only. In production, enable SSL verification.")
    print("If you encounter 'Insufficient Balance' errors, you can run with:")
    print("    export AI_MOCK_MODE=true && python test_ai.py")
    
    await test_young_self_response()
    await test_direct_api_request()


if __name__ == "__main__":
    asyncio.run(main()) 