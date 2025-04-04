"""
Test script for the Time Capsule questionnaire processing.

This script demonstrates how to use the questionnaire processing functionality
by providing a sample questionnaire response and processing it into structured data.
"""

import asyncio
import json
import sys
import aiohttp
from app.questionnaire import (
    parse_free_text_answers,
    extract_structured_data,
    process_questionnaire_text,
    get_questionnaire_as_json
)


# Sample questionnaire response
SAMPLE_QUESTIONNAIRE = """
你20岁时的名字是？张伟
你20岁时生活在哪个城市或地区？北京
你当时是学生还是已经工作了？如果是学生，读什么专业？如果工作了，职业是什么？大学生，计算机科学专业
你20岁时最大的兴趣爱好是什么？打篮球，编程，看科幻小说
那时有没有特别重要的人在你身边？我的大学室友李明，我们一起学习编程
20岁那一年，你经历过什么重大的事件或转折点吗？获得了第一次编程比赛的奖项，让我确定了未来要走的方向
那时的你正在为什么事情烦恼或努力？担心毕业后找不到好工作，努力学习专业知识
你对未来的自己有过哪些期待或梦想？希望能在大型科技公司工作，开发有影响力的软件
你和家人的关系如何？和父母关系不错，但由于在外地上学，联系不是很频繁
20岁时，你的身体健康状况如何？健康状况良好，经常运动
你有没有特别的生活习惯？喜欢熬夜编程，经常忘记吃饭
如果现在能对20岁的自己说一句话，你最想提的"遗憾"或"建议"是什么？建议多尝试不同领域的项目，不要局限在学校学到的知识上
"""


def display_structured_data(data):
    """Pretty print structured data"""
    print("\n=== Structured Data ===")
    for key, value in data.items():
        print(f"{key}: {value}")


async def submit_to_api(data, is_free_text=True):
    """Submit data to the API"""
    API_URL = "http://localhost:8000/api/users/profile/questionnaire"
    
    # Sample user credentials
    LOGIN_URL = "http://localhost:8000/api/users/login"
    credentials = {
        "username": "testuser",
        "password": "password123"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Login to get token
            async with session.post(LOGIN_URL, json=credentials) as response:
                if response.status != 200:
                    print(f"Failed to login: {response.status}")
                    return
                
                login_data = await response.json()
                token = login_data.get("access_token")
                
                if not token:
                    print("No token received")
                    return
                
                # Prepare headers with token
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                # Prepare payload
                if is_free_text:
                    payload = {"free_text": data}
                else:
                    payload = {"answers": data}
                
                # Submit questionnaire data
                async with session.post(API_URL, json=payload, headers=headers) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print("\n=== API Response ===")
                        print(f"Status: {response.status}")
                        print(f"Message: {result.get('message')}")
                    else:
                        print(f"API Error: {response.status}")
                        print(result)
    except Exception as e:
        print(f"Error communicating with API: {str(e)}")


def display_questionnaire():
    """Display the questionnaire questions"""
    questions = get_questionnaire_as_json()
    
    print("\n=== Questionnaire ===")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q['question']}")
        print(f"   ({q['description']})")
        print()


def main():
    """Main function to demonstrate questionnaire processing"""
    print("Time Capsule Questionnaire Processor")
    print("====================================")
    
    # Display all questions
    display_questionnaire()
    
    # Process the sample questionnaire
    print("\n=== Processing Sample Data ===")
    
    # Parse free text answers
    answers = parse_free_text_answers(SAMPLE_QUESTIONNAIRE)
    print("\n=== Parsed Answers ===")
    for q_id, answer in answers.items():
        print(f"{q_id}: {answer}")
    
    # Extract structured data
    structured_data = extract_structured_data(answers)
    display_structured_data(structured_data)
    
    # Or use the combined process_questionnaire_text function
    combined_result = process_questionnaire_text(SAMPLE_QUESTIONNAIRE)
    print("\n=== Combined Processing Result ===")
    display_structured_data(combined_result)
    
    # Ask if user wants to submit to API
    if input("\nSubmit to API? (y/n): ").lower() == 'y':
        asyncio.run(submit_to_api(SAMPLE_QUESTIONNAIRE))


if __name__ == "__main__":
    main() 