"""
Time Capsule Configuration Module

This module provides configuration settings for different environments (development, production, testing).
Configuration is selected based on the TIME_CAPSULE_ENV environment variable.
"""

import os
import logging
from typing import Dict, Any
import pathlib
import json
from dotenv import load_dotenv
import base64

# Load environment variables from .env file if present
load_dotenv()

# Get the base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Environment variable to determine the current environment
ENV = os.environ.get("TIME_CAPSULE_ENV", "dev").lower()

# Data directory
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Secrets directory - consider using a proper secret manager for production
SECRETS_DIR = os.path.join(BASE_DIR, "secrets")
os.makedirs(SECRETS_DIR, exist_ok=True)

# Set up secrets manager
class SecretsManager:
    """Manages application secrets."""
    
    def __init__(self, secrets_dir: str, env: str):
        self.secrets_dir = secrets_dir
        self.env = env
        self.secrets_cache = {}
        self._ensure_secrets_file()
    
    def _ensure_secrets_file(self):
        """Ensure the secrets file exists."""
        env_secrets_file = os.path.join(self.secrets_dir, f"{self.env}.secrets.json")
        if not os.path.exists(env_secrets_file):
            with open(env_secrets_file, 'w') as f:
                json.dump({}, f)
            # Set proper permissions
            os.chmod(env_secrets_file, 0o600)  # Read/write only for owner
    
    def get_secret(self, key: str, default: str = None) -> str:
        """
        Get a secret from environment variables, then secrets file.
        Always prefer environment variables over secrets file.
        
        Args:
            key: The secret key
            default: Default value if secret is not found
            
        Returns:
            The secret value or default
        """
        # First try environment variable (highest priority)
        env_value = os.environ.get(key)
        if env_value is not None:
            return env_value
        
        # Then try secrets file
        if not self.secrets_cache:
            self._load_secrets()
        
        return self.secrets_cache.get(key, default)
    
    def _load_secrets(self):
        """Load secrets from the environment-specific secrets file."""
        env_secrets_file = os.path.join(self.secrets_dir, f"{self.env}.secrets.json")
        try:
            if os.path.exists(env_secrets_file):
                with open(env_secrets_file, 'r') as f:
                    self.secrets_cache = json.load(f)
        except Exception as e:
            print(f"Error loading secrets: {str(e)}")
            self.secrets_cache = {}
    
    def set_secret(self, key: str, value: str) -> bool:
        """
        Set a secret in the secrets file.
        
        Args:
            key: The secret key
            value: The secret value
            
        Returns:
            True if successful, False otherwise
        """
        # Load current secrets
        if not self.secrets_cache:
            self._load_secrets()
        
        try:
            # Update the secret
            self.secrets_cache[key] = value
            
            # Write back to file
            env_secrets_file = os.path.join(self.secrets_dir, f"{self.env}.secrets.json")
            with open(env_secrets_file, 'w') as f:
                json.dump(self.secrets_cache, f)
            
            return True
        except Exception as e:
            print(f"Error setting secret: {str(e)}")
            return False
    
    def get_dict(self) -> Dict[str, str]:
        """Get all secrets as a dictionary."""
        if not self.secrets_cache:
            self._load_secrets()
        return self.secrets_cache

# Initialize secrets manager
secrets = SecretsManager(SECRETS_DIR, ENV)

# Common configuration shared across all environments
COMMON_CONFIG = {
    "app_name": "TimeCapsule",
    "display_name": "Time Capsule",
    "data_folder": DATA_DIR,
    "static_folder": os.path.join(BASE_DIR, "static"),
    "templates_folder": os.path.join(BASE_DIR, "templates"),
    "session_timeout": 86400,  # 24 hours in seconds
    "api_timeout": 30,  # API request timeout in seconds
}

# Development environment configuration
DEV_CONFIG = {
    "log_level": "WARNING",
    "db": {
        "driver": "sqlite+aiosqlite",
        "path": DATA_DIR,
        "name": "timecapsule.db",
        "echo": False,
    },
    "use_https": False,
    "verify_ssl": False,
}

# Production environment configuration
PROD_CONFIG = {
    "log_level": "INFO",
    "db": {
        "driver": secrets.get_secret("DB_DRIVER", "sqlite+aiosqlite"),
        "host": secrets.get_secret("DB_HOST", "localhost"),
        "port": secrets.get_secret("DB_PORT", "5432"),
        "user": secrets.get_secret("DB_USER", "postgres"),
        "password": secrets.get_secret("DB_PASSWORD", ""),
        "name": secrets.get_secret("DB_NAME", "timecapsule"),
        "path": DATA_DIR,  # Only used for SQLite
        "pool_size": 5,
        "max_overflow": 10,
        "echo": False,
    },
    "use_https": True,
    "verify_ssl": True,
}

# Testing environment configuration
TEST_CONFIG = {
    "log_level": "DEBUG",
    "db": {
        "driver": "sqlite+aiosqlite",
        "path": DATA_DIR,
        "name": "test_timecapsule.db",
        "echo": False,
    },
    "use_https": False,
    "verify_ssl": False,
}

# Select the appropriate configuration based on the environment
ENV_CONFIGS = {
    "dev": DEV_CONFIG,
    "development": DEV_CONFIG,
    "prod": PROD_CONFIG,
    "production": PROD_CONFIG,
    "test": TEST_CONFIG,
    "testing": TEST_CONFIG
}

# Merge the environment-specific configuration with the common configuration
CONFIG = {**COMMON_CONFIG, **ENV_CONFIGS.get(ENV, DEV_CONFIG)}

def get_db_url() -> str:
    """
    Construct the database URL based on the current configuration.
    
    Returns:
        str: The database URL for SQLAlchemy
    """
    db = CONFIG["db"]
    
    if db["driver"].startswith("sqlite"):
        db_path = os.path.join(db["path"], db["name"])
        return f"{db['driver']}:///{db_path}"
    
    # For PostgreSQL or other databases
    password = db['password']
    # URL encode the password for special characters
    if password:
        password = f":{password}@"
    else:
        password = "@" if db['user'] else ""
        
    return f"{db['driver']}://{db['user']}{password}{db['host']}:{db['port']}/{db['name']}"

def get_db_config() -> Dict[str, Any]:
    """
    Get the database configuration.
    
    Returns:
        Dict[str, Any]: The database configuration dictionary
    """
    return CONFIG["db"]

def get_secret(key: str, default: str = None) -> str:
    """
    Get a secret value.
    
    Args:
        key: The secret key
        default: Default value if secret is not found
        
    Returns:
        The secret value or default
    """
    return secrets.get_secret(key, default)

# Log the selected environment and configuration with sensitive data masked
cleaned_config = dict(CONFIG)
if "db" in cleaned_config and cleaned_config["db"].get("password"):
    cleaned_config["db"] = dict(cleaned_config["db"])
    cleaned_config["db"]["password"] = "********" if cleaned_config["db"]["password"] else ""

print(f"Environment: {ENV}")
print(f"Database: {get_db_url().replace(CONFIG['db'].get('password', ''), '********' if CONFIG['db'].get('password') else '')}") 