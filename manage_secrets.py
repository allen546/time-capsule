#!/usr/bin/env python
"""
Time Capsule Secrets Management Utility

This script helps manage secrets for the Time Capsule application.
It can set, get, and list secrets for different environments.
"""

import os
import sys
import json
import getpass
import argparse
import secrets
import string
from pathlib import Path

# Get application directory
APP_DIR = Path(__file__).resolve().parent / "app"
SECRETS_DIR = APP_DIR / "secrets"
ENV_FILE = Path(".env")

# Ensure secrets directory exists
SECRETS_DIR.mkdir(exist_ok=True, parents=True)

def load_secrets(env):
    """Load secrets for the specified environment."""
    secrets_file = SECRETS_DIR / f"{env}.secrets.json"
    
    if not secrets_file.exists():
        return {}
        
    try:
        with open(secrets_file, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Secrets file for {env} environment is corrupted.")
        return {}
    except Exception as e:
        print(f"Error loading secrets: {str(e)}")
        return {}

def save_secrets(env, secrets_data):
    """Save secrets for the specified environment."""
    secrets_file = SECRETS_DIR / f"{env}.secrets.json"
    
    try:
        with open(secrets_file, "w") as f:
            json.dump(secrets_data, f, indent=2)
        
        # Set secure permissions
        os.chmod(secrets_file, 0o600)  # Read/write only for owner
        return True
    except Exception as e:
        print(f"Error saving secrets: {str(e)}")
        return False

def set_secret(env, key, value=None, prompt=True):
    """Set a secret value for the specified environment."""
    secrets_data = load_secrets(env)
    
    if value is None and prompt:
        # Prompt for secret value with hidden input
        value = getpass.getpass(f"Enter value for '{key}' in {env} environment: ")
    
    if value:
        secrets_data[key] = value
        if save_secrets(env, secrets_data):
            print(f"Secret '{key}' set successfully for {env} environment.")
            return True
    else:
        print("No value provided, secret not set.")
    
    return False

def get_secret(env, key):
    """Get a secret value for the specified environment."""
    secrets_data = load_secrets(env)
    value = secrets_data.get(key)
    
    if value:
        return value
    else:
        print(f"Secret '{key}' not found in {env} environment.")
        return None

def delete_secret(env, key):
    """Delete a secret for the specified environment."""
    secrets_data = load_secrets(env)
    
    if key in secrets_data:
        del secrets_data[key]
        if save_secrets(env, secrets_data):
            print(f"Secret '{key}' deleted successfully from {env} environment.")
            return True
    else:
        print(f"Secret '{key}' not found in {env} environment.")
    
    return False

def list_secrets(env):
    """List all secrets for the specified environment."""
    secrets_data = load_secrets(env)
    
    if not secrets_data:
        print(f"No secrets found for {env} environment.")
        return
    
    print(f"\nSecrets for {env} environment:")
    print("-" * 40)
    for key, value in secrets_data.items():
        # Mask secret values for display
        masked_value = value[:3] + "*" * (len(value) - 3) if len(value) > 3 else "****"
        print(f"{key}: {masked_value}")
    print("-" * 40)

def generate_random_password(length=16):
    """Generate a strong random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def init_env_file():
    """Create a .env file from the example if it doesn't exist."""
    if not ENV_FILE.exists():
        example_env = Path(".env.example")
        if example_env.exists():
            with open(example_env, "r") as src, open(ENV_FILE, "w") as dest:
                dest.write(src.read())
            print(".env file created from example.")
            return True
        else:
            print("Error: .env.example file not found.")
            return False
    else:
        print(".env file already exists.")
        return True

def setup_production():
    """Set up production secrets with secure defaults."""
    env = "prod"
    print(f"\nSetting up {env} environment secrets...")
    
    # Generate a strong JWT secret
    jwt_secret = generate_random_password(32)
    set_secret(env, "JWT_SECRET", jwt_secret, prompt=False)
    
    # Set admin password
    admin_password = generate_random_password(16)
    set_secret(env, "ADMIN_PASSWORD", admin_password, prompt=False)
    
    # Prompt for database credentials
    print("\nDatabase Configuration:")
    db_driver = input("Database driver (default: sqlite+aiosqlite): ") or "sqlite+aiosqlite"
    
    if "sqlite" not in db_driver:
        # For non-SQLite databases, prompt for connection details
        db_host = input("Database host (default: localhost): ") or "localhost"
        db_port = input("Database port (default: 5432): ") or "5432"
        db_name = input("Database name (default: timecapsule): ") or "timecapsule"
        db_user = input("Database user: ")
        db_password = getpass.getpass("Database password: ")
        
        set_secret(env, "DB_DRIVER", db_driver, prompt=False)
        set_secret(env, "DB_HOST", db_host, prompt=False)
        set_secret(env, "DB_PORT", db_port, prompt=False)
        set_secret(env, "DB_NAME", db_name, prompt=False)
        set_secret(env, "DB_USER", db_user, prompt=False)
        set_secret(env, "DB_PASSWORD", db_password, prompt=False)
    
    # Prompt for API keys
    print("\nAPI Configuration:")
    api_key = getpass.getpass("DeepSeek API Key (leave empty to skip): ")
    if api_key:
        set_secret(env, "DEEPSEEK_API_KEY", api_key, prompt=False)
    
    # Generate encryption key
    encryption_key = generate_random_password(32)
    set_secret(env, "ENCRYPTION_KEY", encryption_key, prompt=False)
    
    print("\nProduction setup complete!")
    print(f"Admin password: {admin_password} (please save this!)")
    return True

def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description="Time Capsule Secrets Management")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Set command
    set_parser = subparsers.add_parser("set", help="Set a secret value")
    set_parser.add_argument("--env", "-e", default="dev", help="Environment (dev, prod, test)")
    set_parser.add_argument("key", help="Secret key")
    set_parser.add_argument("value", nargs="?", help="Secret value (will prompt if not provided)")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Get a secret value")
    get_parser.add_argument("--env", "-e", default="dev", help="Environment (dev, prod, test)")
    get_parser.add_argument("key", help="Secret key")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a secret")
    delete_parser.add_argument("--env", "-e", default="dev", help="Environment (dev, prod, test)")
    delete_parser.add_argument("key", help="Secret key")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all secrets for an environment")
    list_parser.add_argument("--env", "-e", default="dev", help="Environment (dev, prod, test)")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize .env file")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up production environment")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute the appropriate command
    if args.command == "set":
        set_secret(args.env, args.key, args.value)
    elif args.command == "get":
        value = get_secret(args.env, args.key)
        if value:
            print(f"{args.key}: {value}")
    elif args.command == "delete":
        delete_secret(args.env, args.key)
    elif args.command == "list":
        list_secrets(args.env)
    elif args.command == "init":
        init_env_file()
    elif args.command == "setup":
        setup_production()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 