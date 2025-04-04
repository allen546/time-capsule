#!/usr/bin/env python
"""
Command Line Interface for Time Capsule

This script provides a simple CLI for interacting with the Time Capsule application,
allowing users to test functionality without a web browser.
"""

import os
import sys
import json
import getpass
from pathlib import Path
import warnings

# Suppress SSL verification warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Add the project root to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

# Base URL for the API
BASE_URL = "http://localhost:8080"
if BASE_URL.startswith("https://"):
    BASE_URL = BASE_URL.replace("https://", "http://", 1)
    print(f"Switched to HTTP protocol: {BASE_URL}")


class TimeCapsuleCLI:
    """Command line interface for the Time Capsule application."""
    
    def __init__(self):
        self.token = None
        self.user_data = None
        self.language = "zh"  # Default language
    
    def start(self):
        """Main menu loop."""
        print("\n===== 时光胶囊 (Time Capsule) CLI =====\n")
        
        while True:
            if not self.token:
                self.show_auth_menu()
            else:
                self.show_main_menu()
    
    def show_auth_menu(self):
        """Show authentication menu options."""
        print("\n=== Authentication ===")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            self.login()
        elif choice == "2":
            self.register()
        elif choice == "3":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")
    
    def show_main_menu(self):
        """Show main menu options for authenticated users."""
        print(f"\n=== Main Menu (Logged in as: {self.user_data['username']}) ===")
        print("1. View conversation")
        print("2. Chat with younger self")
        print("3. Switch language (current: " + ("Chinese" if self.language == "zh" else "English") + ")")
        print("4. Logout")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            self.view_conversation()
        elif choice == "2":
            self.chat()
        elif choice == "3":
            self.switch_language()
        elif choice == "4":
            self.logout()
        elif choice == "5":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")
    
    def api_request(self, method, endpoint, data=None, headers=None):
        """Make an API request to the Time Capsule server."""
        if headers is None:
            headers = {}
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        headers["Content-Type"] = "application/json"
        url = f"{BASE_URL}{endpoint}"
        
        try:
            print(f"Sending {method} request to {url}")
            print(f"Headers: {headers}")
            if data:
                print(f"Data: {json.dumps(data, ensure_ascii=False)}")
            
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=15,  # 15 seconds timeout
                verify=False  # Disable SSL verification
            )
            status = response.status_code
            print(f"Received response with status {status}")
            print(f"Response headers: {response.headers}")
            
            try:
                result = response.json()
                return status, result
            except json.JSONDecodeError as e:
                # If response is not JSON
                text = response.text
                print(f"Error parsing response as JSON: {str(e)}")
                print(f"Response text: {text[:200]}...")  # Print first 200 chars
                return status, {"error": "Invalid JSON response"}
                
        except requests.ConnectionError as e:
            print(f"Error connecting to server: {str(e)}")
            return 500, {"error": str(e)}
        except requests.Timeout as e:
            print(f"Request timed out: {str(e)}")
            return 500, {"error": f"Request timeout: {str(e)}"}
        except Exception as e:
            print(f"Unexpected error during request: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            return 500, {"error": str(e)}
    
    def login(self):
        """Login to the Time Capsule application."""
        print("\n=== Login ===")
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        
        status, result = self.api_request(
            "POST",
            "/api/users/login",
            {"username": username, "password": password}
        )
        
        if status == 200:
            self.token = result["access_token"]
            self.get_user_profile()
            print("Login successful!")
        else:
            print(f"Login failed: {result.get('error', 'Unknown error')}")
    
    def register(self):
        """Register a new user account."""
        print("\n=== Register ===")
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        real_name = input("Real name: ")
        
        while True:
            try:
                age = int(input("Age: "))
                break
            except ValueError:
                print("Please enter a valid number for age.")
        
        basic_data = input("Basic data (optional): ")
        
        status, result = self.api_request(
            "POST",
            "/api/users/register",
            {
                "username": username,
                "password_hash": password,
                "real_name": real_name,
                "age": age,
                "basic_data": basic_data
            }
        )
        
        if status == 200:
            self.token = result["access_token"]
            self.user_data = result
            print("Registration successful!")
        else:
            print(f"Registration failed: {result.get('error', 'Unknown error')}")
    
    def get_user_profile(self):
        """Get the user profile information."""
        status, result = self.api_request("GET", "/api/users/me")
        
        if status == 200:
            self.user_data = result
            return True
        else:
            print(f"Failed to get user profile: {result.get('error', 'Unknown error')}")
            return False
    
    def view_conversation(self):
        """View the user's conversation with messages."""
        print("\n=== Your Conversation ===")
        
        status, result = self.api_request("GET", "/api/conversation")
        
        if status == 200:
            print(f"Created: {result.get('created_at', 'Unknown')}")
            print(f"Updated: {result.get('updated_at', 'Unknown')}")
            print("\n=== Messages ===")
            
            messages = result.get("messages", [])
            
            if not messages:
                print("No messages yet.")
            else:
                for msg in messages:
                    sender = "You" if msg["sender"] == "USER" else "Young Self"
                    print(f"[{msg['timestamp']}] {sender}: {msg['content']}")
            
            # Show message options
            print("\n1. Send a new message")
            print("2. Chat with young self")
            print("3. Return to main menu")
            
            choice = input("\nEnter your choice (1-3): ")
            
            if choice == "1":
                self.send_message()
            elif choice == "2":
                self.chat()
        else:
            print(f"Failed to retrieve conversation: {result.get('error', 'Unknown error')}")
    
    def send_message(self):
        """Send a message to the conversation."""
        print("\n=== Send Message ===")
        content = input("Message: ")
        
        status, result = self.api_request(
            "POST",
            "/api/conversation/messages",
            {"sender": "USER", "content": content}
        )
        
        if status == 200:
            print("Message sent!")
        else:
            print(f"Failed to send message: {result.get('error', 'Unknown error')}")
        
        self.view_conversation()
    
    def chat(self):
        """Chat with younger self."""
        print("\n=== Chat with Your Younger Self ===")
        print("Type 'exit' to end the chat.")
        
        while True:
            message = input("\nYou: ")
            
            if message.lower() == 'exit':
                break
            
            status, result = self.api_request(
                "POST",
                "/api/conversation/chat",
                {"message": message, "language": self.language}
            )
            
            if status == 200:
                bot_message = result.get("message", {}).get("content", "")
                print(f"\nYoung Self: {bot_message}")
            else:
                print(f"\nError: {result.get('error', 'Failed to get response')}")
                break
    
    def switch_language(self):
        """Switch between Chinese and English."""
        if self.language == "zh":
            self.language = "en"
            print("Language switched to English.")
        else:
            self.language = "zh"
            print("Language switched to Chinese.")
    
    def logout(self):
        """Log out the current user."""
        self.token = None
        self.user_data = None
        print("Logged out successfully.")


def check_server():
    """Check if the server is running."""
    try:
        print(f"Attempting to connect to server at {BASE_URL}...")
        response = requests.get(f"{BASE_URL}", timeout=10, verify=False)  # Disable SSL verification
        print(f"Connected to server. Status: {response.status_code}")
        if response.status_code == 200:
            return True
        else:
            print(f"Server error: HTTP {response.status_code}")
            return False
    except requests.ConnectionError as e:
        print(f"Cannot connect to server at {BASE_URL}: {str(e)}")
        print("Make sure the server is running with 'python run.py'")
        return False
    except requests.Timeout as e:
        print(f"Connection to server timed out: {str(e)}")
        print("Server might be slow to respond. Check server logs.")
        return False
    except Exception as e:
        print(f"Unexpected error when connecting to server: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return False


def main():
    """Main entry point for the CLI application."""
    # Check if server is running
    if not check_server():
        return
    
    # Start the CLI
    cli = TimeCapsuleCLI()
    cli.start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        sys.exit(0) 