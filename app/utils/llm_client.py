#!/usr/bin/env python
"""
LLM API Client Utility

A low-level utility for making API requests to various LLM providers.
This module handles the basic HTTP requests, authentication, and error handling.
"""

import os
import json
import logging
import asyncio
import time
import ssl
import datetime
import aiohttp
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
import uuid

# Configure logging
logger = logging.getLogger(__name__)

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# For fallback to mock response if API key is not set
USE_MOCK_RESPONSE = not DEEPSEEK_API_KEY


class LLMProvider(Enum):
    """Supported LLM API providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    CUSTOM = "custom"


class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, status_code: int, message: str, details: Optional[Dict] = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"API Error ({status_code}): {message}")


class RateLimitError(APIError):
    """Exception for rate limit errors."""
    def __init__(self, status_code: int, message: str, retry_after: Optional[int] = None):
        super().__init__(status_code, message)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Exception for authentication errors."""
    pass


class LLMClient:
    """
    Low-level client for interacting with LLM APIs.
    
    This client handles:
    - Authentication
    - Request construction
    - Rate limiting with backoff
    - Response parsing
    - Error handling
    
    It provides a unified interface to multiple LLM providers.
    """
    
    def __init__(
        self,
        provider: Union[LLMProvider, str] = LLMProvider.OPENAI,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the LLM API client.
        
        Args:
            provider: The LLM provider to use
            api_key: API key for authentication (defaults to env var based on provider)
            base_url: Override the default API URL for the provider
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Initial delay between retries (increases exponentially)
        """
        if isinstance(provider, str):
            provider = LLMProvider(provider.lower())
        
        self.provider = provider
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = None
        
        # Set base URL based on provider
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = self._get_default_base_url()
        
        # Set API key based on provider
        if api_key:
            self.api_key = api_key
        else:
            env_var = self._get_api_key_env_var()
            self.api_key = os.environ.get(env_var)
            if not self.api_key:
                logger.warning(f"No API key provided and environment variable {env_var} not found")
    
    def _get_default_base_url(self) -> str:
        """Get the default base URL for the selected provider."""
        if self.provider == LLMProvider.OPENAI:
            return "https://api.openai.com/v1"
        elif self.provider == LLMProvider.ANTHROPIC:
            return "https://api.anthropic.com/v1"
        elif self.provider == LLMProvider.COHERE:
            return "https://api.cohere.ai/v1"
        elif self.provider == LLMProvider.CUSTOM:
            return ""  # Custom provider requires explicit base_url
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        if self.provider == LLMProvider.OPENAI:
            return "OPENAI_API_KEY"
        elif self.provider == LLMProvider.ANTHROPIC:
            return "ANTHROPIC_API_KEY"
        elif self.provider == LLMProvider.COHERE:
            return "COHERE_API_KEY"
        elif self.provider == LLMProvider.CUSTOM:
            return "CUSTOM_API_KEY"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get the headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.provider == LLMProvider.OPENAI:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.provider == LLMProvider.ANTHROPIC:
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.provider == LLMProvider.COHERE:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.provider == LLMProvider.CUSTOM:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle API response and errors."""
        if response.status >= 200 and response.status < 300:
            return await response.json()
        
        error_data = await response.text()
        try:
            error_json = json.loads(error_data)
        except json.JSONDecodeError:
            error_json = {"error": error_data}
        
        error_message = error_json.get("error", {}).get("message", error_data)
        
        if response.status == 401:
            raise AuthenticationError(401, "Authentication failed. Check your API key.")
        elif response.status == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    retry_after = int(retry_after)
                except ValueError:
                    retry_after = None
            raise RateLimitError(429, "Rate limit exceeded", retry_after)
        else:
            raise APIError(response.status, error_message, error_json)
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request with retries and backoff."""
        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        
        retries = 0
        while retries <= self.max_retries:
            try:
                if method.upper() == "GET":
                    response = await session.get(url, params=params)
                elif method.upper() == "POST":
                    response = await session.post(url, json=data, params=params)
                elif method.upper() == "DELETE":
                    response = await session.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                return await self._handle_response(response)
            
            except RateLimitError as e:
                retries += 1
                if retries > self.max_retries:
                    raise
                
                # Use retry-after header if available, otherwise use exponential backoff
                delay = e.retry_after if e.retry_after else self.retry_delay * (2 ** (retries - 1))
                logger.warning(f"Rate limit hit. Retrying in {delay} seconds. Attempt {retries}/{self.max_retries}")
                await asyncio.sleep(delay)
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                retries += 1
                if retries > self.max_retries:
                    raise APIError(0, f"Request failed after {self.max_retries} retries: {str(e)}")
                
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.warning(f"Request error: {str(e)}. Retrying in {delay} seconds. Attempt {retries}/{self.max_retries}")
                await asyncio.sleep(delay)
    
    async def _generate_openai(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using OpenAI API."""
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        for key, value in kwargs.items():
            data[key] = value
        
        return await self._make_request("POST", "/chat/completions", data=data)
    
    async def _generate_anthropic(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-opus-20240229",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using Anthropic API."""
        # Convert to Anthropic message format if needed
        if isinstance(messages[0], dict) and "role" in messages[0]:
            anthropic_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    # Note: In newest Claude API, system is at top level
                    kwargs["system"] = msg["content"]
                else:
                    anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
            messages = anthropic_messages
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        for key, value in kwargs.items():
            data[key] = value
        
        return await self._make_request("POST", "/messages", data=data)
    
    async def _generate_cohere(
        self,
        messages: List[Dict[str, str]],
        model: str = "command",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using Cohere API."""
        # Convert to Cohere message format
        chat_history = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                chat_history.append({"role": "USER", "message": msg["content"]})
            elif msg["role"] == "assistant":
                chat_history.append({"role": "CHATBOT", "message": msg["content"]})
        
        data = {
            "model": model,
            "chat_history": chat_history,
            "message": chat_history[-1]["message"] if chat_history and chat_history[-1]["role"] == "USER" else "",
            "temperature": temperature,
        }
        
        if system_message:
            data["preamble"] = system_message
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        for key, value in kwargs.items():
            data[key] = value
        
        return await self._make_request("POST", "/chat", data=data)
    
    async def _generate_custom(
        self,
        messages: List[Dict[str, str]],
        endpoint: str = "/completions",
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using a custom API."""
        # Pass through the data directly
        data = {"messages": messages, **kwargs}
        return await self._make_request("POST", endpoint, data=data)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text from the LLM based on the provided messages.
        
        Args:
            messages: List of message objects with "role" and "content" keys
            model: The model to use (provider-specific)
            temperature: Randomness parameter between 0.0 and 2.0
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        
        Returns:
            The full API response as a dictionary
        """
        if self.provider == LLMProvider.OPENAI:
            model = model or "gpt-4"
            return await self._generate_openai(messages, model, temperature, max_tokens, **kwargs)
        elif self.provider == LLMProvider.ANTHROPIC:
            model = model or "claude-3-opus-20240229"
            return await self._generate_anthropic(messages, model, temperature, max_tokens, **kwargs)
        elif self.provider == LLMProvider.COHERE:
            model = model or "command"
            return await self._generate_cohere(messages, model, temperature, max_tokens, **kwargs)
        elif self.provider == LLMProvider.CUSTOM:
            return await self._generate_custom(messages, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def generate_text(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Helper function to generate text with a simple prompt.
        
        Args:
            prompt: The text prompt
            system_message: Optional system message to control behavior
            model: The model to use (provider-specific)
            temperature: Randomness parameter between 0.0 and 2.0
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        
        Returns:
            The generated text as a string
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.generate(messages, model, temperature, max_tokens, **kwargs)
        
        # Extract the text based on the provider
        if self.provider == LLMProvider.OPENAI:
            return response["choices"][0]["message"]["content"]
        elif self.provider == LLMProvider.ANTHROPIC:
            return response["content"][0]["text"]
        elif self.provider == LLMProvider.COHERE:
            return response["text"]
        elif self.provider == LLMProvider.CUSTOM:
            # This will need to be customized based on the API response structure
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0].get("text", "")
            return response.get("text", "")


async def generate_async(
    prompt: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    Convenience function for generating text asynchronously.
    
    Args:
        prompt: The text prompt
        provider: Provider name (openai, anthropic, cohere, custom)
        api_key: API key (defaults to env var)
        model: Model name (provider-specific)
        system_message: Optional system message
        temperature: Randomness parameter
        max_tokens: Maximum tokens to generate
        **kwargs: Additional provider-specific parameters
    
    Returns:
        The generated text as a string
    """
    client = LLMClient(provider=provider, api_key=api_key)
    try:
        return await client.generate_text(
            prompt=prompt,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    finally:
        await client.close()


def generate(
    prompt: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    Synchronous wrapper for generate_async.
    
    Args:
        prompt: The text prompt
        provider: Provider name (openai, anthropic, cohere, custom)
        api_key: API key (defaults to env var)
        model: Model name (provider-specific)
        system_message: Optional system message
        temperature: Randomness parameter
        max_tokens: Maximum tokens to generate
        **kwargs: Additional provider-specific parameters
    
    Returns:
        The generated text as a string
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If we're in an async context, create a new loop in a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                generate_async(
                    prompt=prompt,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    system_message=system_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            )
            return future.result()
    else:
        # If we're not in an async context, we can just use the current loop
        return asyncio.run(
            generate_async(
                prompt=prompt,
                provider=provider,
                api_key=api_key,
                model=model,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        )


# Mock function for LLM API call
async def mock_llm_response(user_message, user_data=None, session_id=None, db_session=None):
    """Mock function to simulate LLM API call with history."""
    try:
        # Initialize response
        response_parts = [f"Echo: {user_message}"]
        
        # Add chat history if session_id and db_session are provided
        if session_id and db_session:
            # Import ChatDB locally to avoid circular imports
            from db import ChatDB
            
            # Get previous messages (limited to last 10 for better context)
            messages = await ChatDB.get_messages_by_session(db_session, session_id, limit=10)
            
            # If there are previous messages, include them in the response
            if messages and len(messages) > 1:  # Only show history if there's more than just the current message
                # Skip the most recent user message (it's the one we're responding to)
                previous_messages = [msg for msg in messages if msg.content.strip() != user_message.strip()]
                
                if previous_messages:
                    response_parts.append("\n\nChat History:")
                    
                    # Create a seen set to track unique message content
                    seen_contents = set()
                    
                    # Format the chat history with proper indentation and formatting
                    for msg in previous_messages:
                        # Skip duplicate content
                        content_key = msg.content.strip()[:50]  # Use first 50 chars as key
                        if content_key in seen_contents:
                            continue
                        
                        seen_contents.add(content_key)
                        speaker = "You" if msg.is_user else "AI"
                        response_parts.append(f"\n{speaker}: {msg.content}")
        
        # If user data is available, personalize the response
        if user_data and user_data.get('name'):
            response_parts.append(f"\n\nBy the way, {user_data.get('name')}, this is just a mock response. In the future, we'll connect to a real LLM API.")
        
        # Join all parts
        response = "".join(response_parts)
        return response
    except Exception as e:
        logger.error(f"Error in mock LLM response: {str(e)}")
        return f"Echo: {user_message} (Error fetching chat history)"

def generate_prompt_from_user_model(user_data, language="zh"):
    """
    Generate a customized prompt text based on the user model.
    
    Args:
        user_data: User profile data containing personal information
        language: Language code ('en' for English, 'zh' for Chinese)
        
    Returns:
        A customized prompt text incorporating user data
    """
    # Extract basic user information
    name = user_data.get("name", "")
    age = user_data.get("age", "")
    current_year = datetime.datetime.now().year
    birth_year = current_year - int(age) if age and str(age).isdigit() else None
    year_at_20 = birth_year + 20 if birth_year else None
    
    # Extract profile data
    profile_data = user_data.get("profile_data", {})
    if isinstance(profile_data, str):
        try:
            profile_data = json.loads(profile_data)
        except json.JSONDecodeError:
            profile_data = {}
            
    # Extract questionnaire data
    location = profile_data.get("location_at_20", "")
    occupation = profile_data.get("occupation_at_20", "")
    education = profile_data.get("education", "")
    major = profile_data.get("major_at_20", "")
    hobbies = profile_data.get("hobbies_at_20", "")
    important_people = profile_data.get("important_people_at_20", "")
    significant_events = profile_data.get("significant_events_at_20", "")
    concerns = profile_data.get("concerns_at_20", "")
    dreams = profile_data.get("dreams_at_20", "")
    family_relations = profile_data.get("family_relations_at_20", "")
    health = profile_data.get("health_at_20", "")
    habits = profile_data.get("habits_at_20", "")
    regrets = profile_data.get("regrets_at_20", "")
    background = profile_data.get("basic_data", "")
    personality = profile_data.get("personality", "")
    
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

def create_system_prompt(user_data, language="zh"):
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

async def deepseek_chat_completion(user_message, user_data=None, session_id=None, db_session=None):
    """
    Get a chat completion from DeepSeek API with conversation history.
    
    Args:
        user_message: The current user message
        user_data: User profile data for personalization
        session_id: The current chat session ID
        db_session: Database session for retrieving message history
        
    Returns:
        The AI response from DeepSeek API or a fallback response
    """
    # Import needed modules locally to avoid circular imports
    from db import ChatDB
    
    request_id = str(uuid.uuid4())[:8]  # Generate a short ID for this request
    logger.info(f"[API:{request_id}] Starting DeepSeek API request for session {session_id}")
    logger.info(f"[API:{request_id}] API Key: {'[SET]' if DEEPSEEK_API_KEY else '[NOT SET]'}, USE_MOCK_RESPONSE: {USE_MOCK_RESPONSE}")
    logger.info(f"[API:{request_id}] Using model: {DEEPSEEK_MODEL}")
    
    try:
        # Set preferred language (default to Chinese)
        language = "zh"
        
        # Format system prompt based on user data
        logger.info(f"[API:{request_id}] Generating system prompt")
        system_prompt = create_system_prompt(user_data, language)
        logger.debug(f"[API:{request_id}] System prompt length: {len(system_prompt)} chars")
        
        # Prepare messages list with system prompt
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available - limited to 10 messages
        if session_id and db_session:
            logger.info(f"[API:{request_id}] Retrieving message history (limited to last 10 messages)")
            
            # Get the last 10 messages for context
            history_messages = await ChatDB.get_messages_by_session(db_session, session_id, limit=10)
            history_messages = history_messages[::-1]  # Reverse to get newest first
            
            # Skip error messages and mock messages
            filtered_history = []
            for msg in history_messages:
                # Skip messages that are errors or mock responses
                if (not msg.is_user and 
                   (msg.content.startswith("Error:") or 
                    msg.content.startswith("Echo:") or
                    "this is just a mock response" in msg.content)):
                    logger.debug(f"[API:{request_id}] Skipping error/mock message from history")
                    continue
                filtered_history.append(msg)
            
            # Limit to last 10 messages after filtering
            filtered_history = filtered_history[:10]
            filtered_history.reverse()  # Put back in chronological order
            
            logger.info(f"[API:{request_id}] Using {len(filtered_history)} messages from history after filtering")
            
            # Add messages to the context (oldest first)
            for msg in filtered_history:
                role = "assistant" if not msg.is_user else "user"
                content = msg.content
                
                # Skip the current message if it's in history already
                if msg.is_user and content.strip() == user_message.strip():
                    logger.debug(f"[API:{request_id}] Skipping duplicate of current message in history")
                    continue
                    
                messages.append({"role": role, "content": content})
        
        # Add the current user message if not already in history
        messages.append({"role": "user", "content": user_message})
        logger.info(f"[API:{request_id}] Final message count for context: {len(messages)}")
        
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 1024
        }
        
        # Log the API request details
        logger.info(f"[API:{request_id}] Request URL: {DEEPSEEK_API_URL}")
        logger.info(f"[API:{request_id}] Request headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer [REDACTED]'}}")
        logger.info(f"[API:{request_id}] Request payload model: {payload['model']}")
        logger.info(f"[API:{request_id}] Request payload message count: {len(payload['messages'])}")
        
        # Create SSL context to handle certificate verification issues
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Make API request
        logger.info(f"[API:{request_id}] Sending request to DeepSeek API with {len(messages)} messages")
        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
                ssl=ssl_context
            ) as response:
                response_time = (datetime.datetime.now() - start_time).total_seconds()
                logger.info(f"[API:{request_id}] Received response from DeepSeek API in {response_time:.2f} seconds")
                logger.info(f"[API:{request_id}] Response status code: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[API:{request_id}] DeepSeek API request failed with status {response.status}: {error_text}")
                    
                    # Check for insufficient balance or other API errors
                    if "Insufficient Balance" in error_text:
                        logger.error(f"[API:{request_id}] API account has insufficient balance")
                        return f"API账户余额不足，无法生成回复。" if language == "zh" else "The API account has insufficient balance."
                    
                    # Default to mock response as fallback
                    logger.warning(f"[API:{request_id}] Using mock response as fallback due to API error")
                    return await mock_llm_response(user_message, user_data, session_id, db_session)
                
                # Process successful response
                result = await response.json()
                logger.info(f"[API:{request_id}] Successfully received valid JSON response from DeepSeek API")
                
                try:
                    content = result["choices"][0]["message"]["content"]
                    content_preview = content[:50] + ('...' if len(content) > 50 else '')
                    logger.info(f"[API:{request_id}] Response content: '{content_preview}'")
                    return content
                except (KeyError, IndexError) as e:
                    logger.error(f"[API:{request_id}] Error extracting content from DeepSeek API response: {e}")
                    logger.error(f"[API:{request_id}] Response structure: {json.dumps(result)[:200]}...")
                    # Fall back to mock response
                    logger.warning(f"[API:{request_id}] Using mock response as fallback")
                    return await mock_llm_response(user_message, user_data, session_id, db_session)
    
    except Exception as e:
        logger.error(f"[API:{request_id}] Error in DeepSeek API request: {str(e)}", exc_info=True)
        # Fall back to mock response
        logger.warning(f"[API:{request_id}] Using mock response as fallback due to exception")
        return await mock_llm_response(user_message, user_data, session_id, db_session)

async def llm_response(user_message, user_data=None, session_id=None, db_session=None):
    """
    Unified function for getting LLM responses - uses DeepSeek API or mock depending on configuration.
    
    Args:
        user_message: The current user message
        user_data: User profile data for personalization
        session_id: The current chat session ID
        db_session: Database session for retrieving message history
        
    Returns:
        The AI response from the chosen method
    """
    # Use mock response if API key is not set or if explicitly configured to use mock
    if USE_MOCK_RESPONSE:
        logger.info("Using mock LLM response")
        return await mock_llm_response(user_message, user_data, session_id, db_session)
    
    # Otherwise use DeepSeek API
    logger.info("Using DeepSeek API for response")
    return await deepseek_chat_completion(user_message, user_data, session_id, db_session) 