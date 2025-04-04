"""
AI Integration Module for Time Capsule

This module provides a function to interact with DeepSeek's API
for generating young-self conversation responses.
"""

import os
import json
import aiohttp
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API configuration
API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-851c7c66c0e444b1822c113ff9314ba8")
API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


def generate_prompt_from_user_model(user_data: Dict[str, Any], language: str = "zh") -> str:
    """
    Generate a customized prompt text based on the user model.
    
    Args:
        user_data: User profile data containing personal information
        language: Language code ('en' for English, 'zh' for Chinese)
        
    Returns:
        A customized prompt text incorporating user data
    """
    # Extract basic user information
    name = user_data.get("real_name", "")
    age = user_data.get("age", "")
    current_year = 2024
    birth_year = current_year - int(age) if age and str(age).isdigit() else None
    year_at_20 = birth_year + 20 if birth_year else None
    
    # Extract questionnaire data
    location = user_data.get("location_at_20", "")
    occupation = user_data.get("occupation_at_20", "")
    education = user_data.get("education", "")
    major = user_data.get("major_at_20", "")
    hobbies = user_data.get("hobbies_at_20", "")
    important_people = user_data.get("important_people_at_20", "")
    significant_events = user_data.get("significant_events_at_20", "")
    concerns = user_data.get("concerns_at_20", "")
    dreams = user_data.get("dreams_at_20", "")
    family_relations = user_data.get("family_relations_at_20", "")
    health = user_data.get("health_at_20", "")
    habits = user_data.get("habits_at_20", "")
    regrets = user_data.get("regrets_at_20", "")
    background = user_data.get("basic_data", "")
    personality = user_data.get("personality", "")
    
    # Build the prompt based on language
    if language == "zh":
        prompt = f"# 20岁时的{name}的角色设定\n\n"
        
        # Basic Information Section
        prompt += f"## 基本信息\n"
        if name:
            prompt += f"- 姓名：{name}\n"
        if age and birth_year and year_at_20:
            prompt += f"- 当前年龄：{age}岁（出生于{birth_year}年）\n"
            prompt += f"- 20岁时的年份：{year_at_20}年\n"
        if location:
            prompt += f"- 20岁时居住地：{location}\n"
        
        # Occupation/Education Section
        if occupation or education or major:
            prompt += f"\n## 学习与工作状况\n"
            if occupation:
                prompt += f"- 职业状态：{occupation}\n"
            if education:
                prompt += f"- 教育背景：{education}\n"
            if major:
                prompt += f"- 所学专业：{major}\n"
        
        # Personal Life Section
        prompt += f"\n## 个人生活\n"
        if hobbies:
            prompt += f"- 兴趣爱好：{hobbies}\n"
        if important_people:
            prompt += f"- 重要的人：{important_people}\n"
        if family_relations:
            prompt += f"- 家庭关系：{family_relations}\n"
        if health:
            prompt += f"- 健康状况：{health}\n"
        if habits:
            prompt += f"- 生活习惯：{habits}\n"
            
        # Mental State Section
        if personality or concerns or dreams:
            prompt += f"\n## 心理状态与想法\n"
            if personality:
                prompt += f"- 性格特点：{personality}\n"
            if concerns:
                prompt += f"- 烦恼与努力方向：{concerns}\n"
            if dreams:
                prompt += f"- 对未来的期待和梦想：{dreams}\n"
            if regrets:
                prompt += f"- 可能的遗憾或想对自己说的话：{regrets}\n"
                
        # Significant Events Section
        if significant_events:
            prompt += f"\n## 重大事件\n"
            prompt += f"{significant_events}\n"
            
        # Additional Background
        if background:
            prompt += f"\n## 其他背景信息\n"
            prompt += f"{background}\n"
            
        # Role-Playing Guidelines
        prompt += f"\n## 角色扮演指南\n"
        prompt += f"""作为20岁的{name}，你应该：
1. 以一个20岁年轻人的语气和思维方式来回应
2. 只讨论{year_at_20 if year_at_20 else '你当时'}年及之前的事件和知识
3. 不要提及未来（对你来说尚未发生）的事情
4. 表现出20岁时的价值观和世界观，特别考虑以下因素：
   - 当时的关注点：{concerns if concerns else '典型20岁年轻人的烦恼'}
   - 对未来的期待：{dreams if dreams else '对未来的希望和梦想'}
   - 重要的人际关系：{important_people if important_people else '朋友、家人和其他重要的人'}
5. 如果被问及未来的事情，你可以表达你对未来的期望，但不应该知道实际发生了什么
6. 你的对话应该反映出你在{location if location else '你生活的地方'}的生活经历和背景"""
            
    else:  # English
        prompt = f"# Character Profile for {name} at Age 20\n\n"
        
        # Basic Information Section
        prompt += f"## Basic Information\n"
        if name:
            prompt += f"- Name: {name}\n"
        if age and birth_year and year_at_20:
            prompt += f"- Current Age: {age} (Born in {birth_year})\n"
            prompt += f"- Year when 20 years old: {year_at_20}\n"
        if location:
            prompt += f"- Location at age 20: {location}\n"
            
        # Occupation/Education Section
        if occupation or education or major:
            prompt += f"\n## Education & Occupation\n"
            if occupation:
                prompt += f"- Occupational status: {occupation}\n"
            if education:
                prompt += f"- Educational background: {education}\n"
            if major:
                prompt += f"- Field of study: {major}\n"
                
        # Personal Life Section
        prompt += f"\n## Personal Life\n"
        if hobbies:
            prompt += f"- Hobbies and interests: {hobbies}\n"
        if important_people:
            prompt += f"- Important people: {important_people}\n"
        if family_relations:
            prompt += f"- Family relationships: {family_relations}\n"
        if health:
            prompt += f"- Health status: {health}\n"
        if habits:
            prompt += f"- Lifestyle habits: {habits}\n"
            
        # Mental State Section
        if personality or concerns or dreams:
            prompt += f"\n## Mental State & Thoughts\n"
            if personality:
                prompt += f"- Personality traits: {personality}\n"
            if concerns:
                prompt += f"- Concerns and efforts: {concerns}\n"
            if dreams:
                prompt += f"- Expectations and dreams for the future: {dreams}\n"
            if regrets:
                prompt += f"- Possible regrets or advice to self: {regrets}\n"
                
        # Significant Events Section
        if significant_events:
            prompt += f"\n## Significant Events\n"
            prompt += f"{significant_events}\n"
            
        # Additional Background
        if background:
            prompt += f"\n## Additional Background\n"
            prompt += f"{background}\n"
            
        # Role-Playing Guidelines
        prompt += f"\n## Role-Playing Guidelines\n"
        prompt += f"""As {name} at age 20, you should:
1. Respond with the tone and mindset of a 20-year-old
2. Only discuss events and knowledge up to {year_at_20 if year_at_20 else 'your time'}
3. Don't mention future events (things that haven't happened for you yet)
4. Reflect the values and worldview you had at 20, especially considering:
   - Your concerns at the time: {concerns if concerns else "typical concerns of a 20-year-old"}
   - Your expectations for the future: {dreams if dreams else "hopes and dreams for the future"}
   - Important relationships: {important_people if important_people else "friends, family, and other important people"}
5. If asked about future events, you may express your hopes for the future, but should not know what actually happened
6. Your conversation should reflect your experiences and background in {location if location else "where you lived"}"""
    
    return prompt


async def chat_completion(
    messages: List[Dict[str, str]],
    user_data: Optional[Dict[str, Any]] = None,
    language: str = "zh"
) -> str:
    """
    Send chat history to the AI API and get a response.
    
    Args:
        messages: List of message objects with 'role' and 'content'
        user_data: User profile data to incorporate in the prompt
        language: Language code ('en' for English, 'zh' for Chinese)
        
    Returns:
        The generated response as a string
    """
    # Format system prompt based on user data
    system_prompt = create_system_prompt(user_data, language)
    
    # Prepare formatted messages for API
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        # Convert between our format and API format
        role = "assistant" if msg.get("sender", "").upper() == "BOT" else "user"
        formatted_messages.append({
            "role": role,
            "content": msg.get("content", "")
        })
    
    # Prepare API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": DEFAULT_MODEL,
        "messages": formatted_messages,
        "temperature": 0.8,
        "max_tokens": 1024
    }
    
    # Create SSL context for API request
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Make API request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=60,
                ssl=ssl_context
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"API request failed with status {response.status}: {error_text}")
                    
                    # Check for insufficient balance
                    if "Insufficient Balance" in error_text:
                        if language == "zh":
                            return "API账户余额不足，无法生成回复。"
                        return "The API account has insufficient balance."
                    
                    # Default error response
                    if language == "zh":
                        return "抱歉，服务暂时无法使用。"
                    return "Sorry, the service is temporarily unavailable."
                
                # Process successful response
                result = await response.json()
                
                try:
                    return result["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    logger.error(f"Error extracting content: {e}")
                    if language == "zh":
                        return "无法从API获取有效回复。"
                    return "Couldn't get a valid response from the API."
    
    except Exception as e:
        logger.error(f"API request error: {str(e)}")
        if language == "zh":
            return "连接AI服务时出错。"
        return "Error connecting to AI service."


def create_system_prompt(user_data: Optional[Dict[str, Any]], language: str) -> str:
    """
    Create a system prompt based on user data.
    
    Args:
        user_data: User profile data
        language: Language code
        
    Returns:
        Formatted system prompt
    """
    # Use the enhanced prompt generator if user data is available
    if user_data:
        return generate_prompt_from_user_model(user_data, language)
    
    # Default basic prompt if no user data is available
    if language == "zh":
        return "你正在模拟与用户20岁时的自己进行对话。"
    return "You are simulating a conversation with a 20-year-old version of the user." 