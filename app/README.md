# Time Capsule Application

This is a merged version of the Time Capsule application that combines:
- The latest UI from the `new/` directory
- The improved backend functionality from the `backend_done/` directory

## Features

- Modern, responsive UI for better user experience
- Chat with your 20-year-old self using AI (DeepSeek integration)
- Diary entries to record thoughts and memories
- Contacts management system
- User profiles with customizable information
- WebSocket support for real-time chat

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   - `DEEPSEEK_API_KEY` - Your DeepSeek API key (optional - will use mock responses if not provided)

4. Run the application:
   ```
   ./start.sh
   ```
   or
   ```
   python app.py
   ```

## API Documentation

The application provides several API endpoints:

- User management: `/api/users/*`
- Diary entries: `/api/diary/*`
- Chat sessions: `/api/chat/*`
- Contacts: `/api/contacts/*`

See code comments and routes for detailed API usage.

## Technology Stack

- Backend: Python with Sanic framework
- Database: SQLite with SQLAlchemy (async)
- Frontend: HTML, CSS, JavaScript
- Real-time: WebSockets for chat functionality
- AI: DeepSeek API integration for chat responses

## Development

To set up a development environment:

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the server in development mode:
   ```
   python app.py
   ```

The server will be available at http://localhost:8000 