# Time Capsule

A voice-based simulation that lets you interact with a 20-year-old version of an elderly person. This project handles user management, authentication, and conversation history.

## Overview

Time Capsule processes user voice input, sends it to an external API for processing, and returns the simulated voice response. The system maintains conversation history and user data.

## Features

- Voice input/output processing
- User authentication and management
- Conversation history storage
- External API integration for voice simulation

## Tech Stack

- Python with FastAPI for the backend server
- MongoDB for data storage
- JWT for authentication
- API integration for voice processing

## Setup

1. Clone this repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Configure environment variables (see `.env.example`)
6. Run the development server: `uvicorn app.main:app --reload`

## API Endpoints

- `POST /api/auth/register` - Create a new user account
- `POST /api/auth/login` - Authenticate a user
- `POST /api/conversations` - Start a new conversation
- `GET /api/conversations` - Get conversation history
- `POST /api/voice` - Submit voice input and get a response
- `GET /api/questionnaire` - Get questionnaire questions
- `POST /api/users/profile/questionnaire` - Submit questionnaire answers
- `GET /api/users/profile` - Get user profile data
- `PATCH /api/users/profile` - Update specific profile fields

## Environment Variables

Create a `.env` file in the root directory with the following:

```
PORT=8000
MONGODB_URI=mongodb://localhost:27017/timecapsule
JWT_SECRET=your_jwt_secret
VOICE_API_KEY=your_voice_api_key
VOICE_API_URL=https://api.example.com/voice
```

## Development

```
uvicorn app.main:app --reload  # Start development server
pytest                         # Run tests
flake8                         # Run linter
black .                        # Format code
```

## License

MIT 

## New Features

### Young Self Questionnaire

The system now includes a comprehensive questionnaire for collecting information about the user's life at age 20. This data is used to create a personalized AI simulation for conversations with the user's younger self.

Key features:
- Structured questionnaire with 12 key areas about the user's life
- Support for both Chinese and English
- Multiple ways to submit data (interactive CLI, API, free-text format)
- Advanced text parsing to extract structured data

For detailed documentation on the questionnaire system, see [QUESTIONNAIRE.md](QUESTIONNAIRE.md). 