#!/usr/bin/env python
"""
Command Line Interface for Time Capsule

This script provides a simple CLI for interacting with the Time Capsule application,
allowing users to test functionality without a web browser.
"""

import asyncio
import os
import sys
import json
import getpass
from pathlib import Path

# Add the project root to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aiohttp

# Base URL for the API
BASE_URL = "http://localhost:8080"


class TimeCapsuleCLI:
    """Command line interface for the Time Capsule application."""
    
    def __init__(self):
        self.token = None
        self.user_data = None
        self.current_conversation_id = None
        self.language = "zh"  # Default language
    
    async def start(self):
        """Main menu loop."""
        print("\n===== 时光胶囊 (Time Capsule) CLI =====\n")
        
        while True:
            if not self.token:
                await self.show_auth_menu()
            else:
                await self.show_main_menu()
    
    async def show_auth_menu(self):
        """Show authentication menu options."""
        print("\n=== Authentication ===")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            await self.login()
        elif choice == "2":
            await self.register()
        elif choice == "3":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")
    
    async def show_main_menu(self):
        """Show main menu options for authenticated users."""
        print(f"\n=== Main Menu (Logged in as: {self.user_data['username']}) ===")
        print("1. View conversation")
        print("2. Create/Update conversation")
        print("3. Chat with younger self")
        print("4. Switch language (current: " + ("Chinese" if self.language == "zh" else "English") + ")")
        print("5. Logout")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == "1":
            await self.view_conversation()
        elif choice == "2":
            await self.create_conversation()
        elif choice == "3":
            await self.chat()
        elif choice == "4":
            self.switch_language()
        elif choice == "5":
            self.logout()
        elif choice == "6":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")
    
    async def api_request(self, method, endpoint, data=None, headers=None):
        """Make an API request to the Time Capsule server."""
        if headers is None:
            headers = {}
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        headers["Content-Type"] = "application/json"
        
        # Create a timeout for requests
        timeout = aiohttp.ClientTimeout(total=15)  # 15 seconds timeout
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_method = getattr(session, method.lower())
                
                try:
                    print(f"Sending {method} request to {BASE_URL}{endpoint}...")
                    async with request_method(
                        f"{BASE_URL}{endpoint}",
                        json=data,
                        headers=headers
                    ) as response:
                        status = response.status
                        print(f"Received response with status {status}")
                        
                        try:
                            result = await response.json()
                            return status, result
                        except Exception as e:
                            # If response is not JSON
                            text = await response.text()
                            print(f"Error parsing response as JSON: {str(e)}")
                            print(f"Response text: {text[:200]}...")  # Print first 200 chars
                            return status, {"error": "Invalid JSON response"}
                
                except aiohttp.ClientConnectorError as e:
                    print(f"Error connecting to server: {str(e)}")
                    return 500, {"error": str(e)}
                except aiohttp.ClientOSError as e:
                    print(f"OS Error when connecting to server: {str(e)}")
                    print("This may be due to a connection reset. Check server logs for errors.")
                    return 500, {"error": f"Connection error: {str(e)}"}
                except Exception as e:
                    print(f"Unexpected error during request: {str(e)}")
                    print(f"Error type: {type(e).__name__}")
                    return 500, {"error": str(e)}
        
        except Exception as e:
            print(f"Error creating client session: {str(e)}")
            return 500, {"error": f"Session error: {str(e)}"}
    
    async def login(self):
        """Login to the Time Capsule application."""
        print("\n=== Login ===")
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        
        status, result = await self.api_request(
            "POST",
            "/api/users/login",
            {"username": username, "password": password}
        )
        
        if status == 200:
            self.token = result["access_token"]
            await self.get_user_profile()
            print("Login successful!")
        else:
            print(f"Login failed: {result.get('error', 'Unknown error')}")
    
    async def register(self):
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
        
        status, result = await self.api_request(
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
    
    async def get_user_profile(self):
        """Get the user profile information."""
        status, result = await self.api_request("GET", "/api/users/me")
        
        if status == 200:
            self.user_data = result
            return True
        else:
            print(f"Failed to get user profile: {result.get('error', 'Unknown error')}")
            return False
    
    async def view_conversation(self):
        """View the user's conversation with messages."""
        print("\n=== Your Conversation ===")
        
        status, result = await self.api_request("GET", "/api/conversation")
        
        if status == 200:
            print(f"Title: {result.get('title', 'Untitled')}")
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
                await self.send_message()
            elif choice == "2":
                await self.chat()
        else:
            if status == 404:
                print("You don't have a conversation yet. Create one first.")
            else:
                print(f"Failed to retrieve conversation: {result.get('error', 'Unknown error')}")
    
    async def send_message(self):
        """Send a message to the conversation."""
        print("\n=== Send Message ===")
        content = input("Message: ")
        
        status, result = await self.api_request(
            "POST",
            "/api/conversation/messages",
            {"sender": "USER", "content": content}
        )
        
        if status == 200:
            print("Message sent!")
        else:
            print(f"Failed to send message: {result.get('error', 'Unknown error')}")
        
        await self.view_conversation()
    
    async def chat(self):
        """Chat with younger self."""
        print("\n=== Chat with Your Younger Self ===")
        
        # First check if user has a conversation
        status, result = await self.api_request("GET", "/api/conversation")
        
        if status != 200:
            if status == 404:
                print("You don't have a conversation yet. Let's create one first.")
                create_success = await self.create_conversation()
                if not create_success:
                    return
            else:
                print(f"Failed to check conversation: {result.get('error', 'Unknown error')}")
            return
        
        print("Type 'exit' to end the chat.")
        
        while True:
            message = input("\nYou: ")
            
            if message.lower() == 'exit':
                break
            
            status, result = await self.api_request(
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
    
    async def create_conversation(self):
        """Create or update a conversation."""
        print("\n=== Create/Update Conversation ===")
        title = input("Conversation title: ")
        
        status, result = await self.api_request(
            "POST",
            "/api/conversation",
            {"title": title}
        )
        
        if status == 200:
            print("Conversation created/updated successfully!")
            return True
        else:
            print(f"Failed to create/update conversation: {result.get('error', 'Unknown error')}")
            return False
    
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
        self.current_conversation_id = None
        print("Logged out successfully.")


async def check_server():
    """Check if the server is running."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)  # 10 seconds timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                print(f"Attempting to connect to server at {BASE_URL}...")
                async with session.get(f"{BASE_URL}") as response:
                    print(f"Connected to server. Status: {response.status}")
                    if response.status == 200:
                        return True
                    else:
                        print(f"Server error: HTTP {response.status}")
                        return False
            except aiohttp.ClientConnectorError as e:
                print(f"Cannot connect to server at {BASE_URL}: {str(e)}")
                print("Make sure the server is running with 'python run.py'")
                return False
            except aiohttp.ClientOSError as e:
                print(f"OS Error when connecting to server: {str(e)}")
                print("This may be due to a connection reset. Check server logs for errors.")
                return False
            except Exception as e:
                print(f"Unexpected error when connecting to server: {str(e)}")
                print(f"Error type: {type(e).__name__}")
                return False
    except Exception as e:
        print(f"Error creating client session: {str(e)}")
        return False


async def main():
    """Main entry point for the CLI application."""
    # Check if server is running
    if not await check_server():
        return
    
    # Start the CLI
    cli = TimeCapsuleCLI()
    await cli.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        sys.exit(0) 