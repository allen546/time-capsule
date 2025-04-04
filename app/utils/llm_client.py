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
import sys
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# For fallback to mock response if API key is not set
USE_MOCK_RESPONSE = not DEEPSEEK_API_KEY

# Import the Chinese prompt template
from utils.zh_prompt_template import ZH_PROMPT_TEMPLATE, ZH_DEFAULT_PROMPT

# Import app configuration if this module is imported on its own
try:
    from config import CONFIG, get_secret
except ImportError:
    import os
    import sys
    # Add the parent directory to the path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import CONFIG, get_secret

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
            try:
                self.provider = LLMProvider(provider.lower())
            except ValueError:
                logger.warning(f"Unknown provider: {provider}, defaulting to OpenAI")
                self.provider = LLMProvider.OPENAI
        else:
            self.provider = provider
        
        logger.info(f"Using LLM provider: {self.provider.value}")
        
        # Set base URL based on provider
        self.base_url = base_url or self._get_default_base_url()
        
        # Set API key based on provider
        self.api_key = api_key or os.environ.get(self._get_api_key_env_var()) or get_secret(self._get_api_key_env_var())
        if not self.api_key:
            logger.warning(f"No API key provided for {self.provider.value}. API calls will fail!")
        
        # Client settings
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Create session
        self._session = None
        
        # Configure SSL verification based on environment settings
        self.verify_ssl = CONFIG.get("verify_ssl", True)
        if not self.verify_ssl:
            logger.warning("SSL verification is disabled! This is insecure and should only be used in development.")
    
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
        """Get or create the aiohttp session with proper SSL configuration."""
        if self._session is None or self._session.closed:
            ssl_context = ssl.create_default_context()
            
            # Only disable SSL verification if explicitly configured
            if not self.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create session with configured SSL context
            self._session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=aiohttp.TCPConnector(ssl=ssl_context)
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
    """
    Generate a mock LLM response for testing purposes.
    This is used when the LLM API is not configured or unavailable.
    
    Args:
        user_message: The user's message to respond to
        user_data: Optional user profile data
        session_id: Optional chat session ID
        db_session: Optional database session
        
    Returns:
        A simple mock response
    """
    try:
        logger.info("Generating mock LLM response")
        from db import ChatDB
        
        # Get user name if available
        name = user_data.get('name', '用户') if user_data else '用户'
        
        # Basic response components
        response_parts = []
        
        # Start with a greeting that includes the user's name if available
        response_parts.append(f"你好，{name}！")
        response_parts.append("这只是一个模拟回复，因为LLM API暂时不可用。")
        
        # Add a reference to the user's message
        if user_message:
            # Shorten very long messages for the response
            short_message = user_message[:50] + "..." if len(user_message) > 50 else user_message
            response_parts.append(f"\n\n你说：\"{short_message}\"")
        
        # Add chat history if session_id and db_session are provided
        if session_id and db_session:
            try:
                messages = await ChatDB.get_messages_by_session(db_session, session_id, limit=10)
                
                # Only add history reference if we have messages
                if messages and len(messages) > 1:  # More than just the current message
                    response_parts.append("\n\n聊天历史：")
                    
                    # Format the chat history with proper indentation and formatting
                    for i, msg in enumerate(messages[:5]):  # Limit to 5 messages
                        # Skip the current message to avoid duplication
                        if msg.is_user and msg.content.strip() == user_message.strip():
                            continue
                            
                        # Add a formatted history entry
                        sender = "你" if msg.is_user else "我"
                        content = msg.content[:30] + "..." if len(msg.content) > 30 else msg.content
                        response_parts.append(f"- {sender}: {content}")
            except Exception as e:
                logger.error(f"Error fetching chat history for mock response: {str(e)}")
        
        # Join all parts
        response = "\n".join(response_parts)
        return response
    except Exception as e:
        logger.error(f"Error in mock LLM response: {str(e)}")
        return f"回声: {user_message} (获取聊天历史时出错)"

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
        # Use the imported prompt template
        prompt = ZH_PROMPT_TEMPLATE.format(
            name=name or "用户",
            age=age or "未知",
            birth_year=birth_year or "未知",
            year_at_20=year_at_20 or "20岁时",
            location=location or "你生活的地方",
            occupation=occupation or "",
            education=education or "",
            major=major or "",
            hobbies=hobbies or "",
            important_people=important_people or "朋友、家人和其他重要的人",
            family_relations=family_relations or "",
            health=health or "",
            habits=habits or "",
            personality=personality or "",
            concerns=concerns or "典型20岁年轻人的烦恼",
            dreams=dreams or "对未来的希望和梦想",
            regrets=regrets or "",
            significant_events=significant_events or "",
            background=background or ""
        )
        
        # Remove commented lines from the template (lines starting with #)
        prompt_lines = [
            line for line in prompt.split('\n') 
            if not line.strip().startswith('//') and line.strip()
        ]
        prompt = '\n'.join(prompt_lines)
            
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
    # Only support Chinese language now
    if language != "zh":
        return "You are simulating a conversation with a 20-year-old version of the user."
    
    # Use the enhanced prompt generator if user data is available
    if user_data:
        return generate_prompt_from_user_model(user_data, language="zh")
    
    # Default basic prompt for Chinese if no user data is available
    return ZH_DEFAULT_PROMPT

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
        # Always use Chinese language for prompts
        language = "zh"
        
        # Format system prompt based on user data
        logger.info(f"[API:{request_id}] Generating system prompt in Chinese")
        system_prompt = create_system_prompt(user_data, language="zh")
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
        
        # Create SSL context based on environment configuration
        ssl_context = ssl.create_default_context()
        
        # Only disable verification in development when explicitly configured
        if not CONFIG.get("verify_ssl", True):
            logger.warning(f"[API:{request_id}] SSL verification is disabled! This is insecure and should only be used in development.")
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
                        return f"API账户余额不足，无法生成回复。"
                    
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

async def llm_response(user_message=None, user_data=None, session_id=None, db_session=None, messages=None, model="deepseek-chat", temperature=0.7, max_tokens=4096):
    """
    Unified function for getting LLM responses - uses DeepSeek API or mock depending on configuration.
    
    Args:
        user_message: The current user message (legacy parameter)
        user_data: User profile data for personalization
        session_id: The current chat session ID
        db_session: Database session for retrieving message history
        messages: List of message dictionaries with 'role' and 'content' (preferred)
        model: Model name to use
        temperature: Temperature parameter for generation
        max_tokens: Maximum tokens to generate
        
    Returns:
        The AI response from the chosen method
    """
    # Check if mock response is configured
    USE_MOCK_RESPONSE = not get_secret("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
    
    # If messages are provided directly, use them
    if messages and isinstance(messages, list):
        try:
            # Use DeepSeek API or mock
            if USE_MOCK_RESPONSE:
                logger.info("Using mock LLM response for direct messages")
                return "This is a mock response for the provided messages. In production, this would be a proper LLM-generated response."
            else:
                # Create SSL context based on environment configuration
                ssl_context = ssl.create_default_context()
                
                # Only disable verification in development when explicitly configured
                if not CONFIG.get("verify_ssl", True):
                    logger.warning("SSL verification is disabled! This is insecure and should only be used in development.")
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                
                # Get API key
                api_key = get_secret("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
                
                if not api_key:
                    logger.error("No DeepSeek API key provided, using mock response")
                    return "This is a mock response. No API key was provided."
                
                # Prepare API request
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                
                # Make API request
                logger.info(f"Sending request to DeepSeek API with {len(messages)} messages")
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60,
                        ssl=ssl_context
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"DeepSeek API request failed with status {response.status}: {error_text}")
                            return "Sorry, I'm having trouble responding right now. Please try again later."
                        
                        # Process successful response
                        result = await response.json()
                        try:
                            content = result["choices"][0]["message"]["content"]
                            return content
                        except (KeyError, IndexError) as e:
                            logger.error(f"Error extracting content from DeepSeek API response: {e}")
                            return "Sorry, there was an error processing the response."
                            
        except Exception as e:
            logger.error(f"Error in LLM request with direct messages: {str(e)}")
            return "Sorry, an error occurred while processing your request."
    
    # Otherwise, use legacy method with user_message
    if user_message:
        # Use mock response if API key is not set or if explicitly configured to use mock
        if USE_MOCK_RESPONSE:
            logger.info("Using mock LLM response")
            return await mock_llm_response(user_message, user_data, session_id, db_session)
        
        # Otherwise use DeepSeek API
        logger.info("Using DeepSeek API for response")
        return await deepseek_chat_completion(user_message, user_data, session_id, db_session)
    
    # If no message content, return error
    return "No message content provided." 