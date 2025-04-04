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
from typing import Dict, List, Optional, Union, Any, Tuple
import aiohttp
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


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