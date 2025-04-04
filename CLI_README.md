# Time Capsule CLI

A simple command-line interface for testing the Time Capsule application.

## Prerequisites

Before using the CLI, make sure you have:

1. The Time Capsule server running (`python run.py`)
2. Python 3.8 or higher
3. Required packages: `aiohttp`

## Usage

Run the CLI by executing:

```bash
./cli_test.py
```

or

```bash
python cli_test.py
```

## Features

The CLI provides the following functionality:

### Authentication
- Login with existing user credentials
- Register a new user account

### Conversation Management
- List all conversations
- View conversation details and messages
- Create new conversations

### Chat
- Send manual messages to a conversation
- Chat with the AI-powered younger self
- Switch between Chinese and English language

## Examples

Here's a typical usage flow:

1. Register a new account or login
2. Create a new conversation
3. Start chatting with your younger self
4. View conversation history

## Troubleshooting

- If you see a connection error, make sure the Time Capsule server is running on localhost:8080
- Authentication errors typically mean invalid credentials
- If the API returns errors, check the server logs for more detailed information

## Notes

This is a testing tool and is not intended for production use. The real-time chat experience 
is designed to be used with the DeepSeek API which requires a valid API key configured in the 
server settings. 