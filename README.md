# 时光胶囊 (Time Capsule)

An interactive web application that allows elderly users to converse with a simulated version of their 20-year-old self, providing a nostalgic and reflective experience through AI-powered conversations.

![Time Capsule](https://placehold.co/800x400/ffc107/212529?text=时光胶囊)

## ✨ Features

- **AI-Powered Conversations**: Talk with a simulation of your 20-year-old self based on your memories
- **Personalized Experience**: Complete a detailed questionnaire about your life at age 20
- **Accessibility First**: Designed specifically for elderly users with:
  - Adjustable font sizes
  - High contrast mode
  - Screen reader compatibility
  - Simple, intuitive interface
- **Bilingual Support**: Full support for both Chinese and English interactions
- **Secure Authentication**: User account management with password protection
- **Conversation History**: Save and revisit previous conversations

## 🛠️ Tech Stack

### Backend
- **Framework**: Sanic/FastAPI with Python
- **Database**: SQLite (Tortoise ORM)
- **Authentication**: JWT tokens
- **AI Integration**: Custom prompt engineering with third-party AI providers

### Frontend
- **Framework**: Vanilla JavaScript with jQuery
- **Styling**: Bootstrap 5 with custom accessibility enhancements
- **Responsive Design**: Mobile and desktop friendly
- **Icons**: Font Awesome

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- Node.js and npm (for frontend development)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/time-capsule.git
   cd time-capsule
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application
   ```bash
   python run.py
   ```

5. Open your browser and navigate to `http://localhost:8080`

## 📋 Usage Flow

1. **Register/Login**: Create an account or sign in
2. **Complete Questionnaire**: Fill out the detailed survey about your life at age 20
3. **Start Conversations**: Begin interacting with your simulated younger self
4. **Review History**: Revisit previous conversations anytime

## 🧩 Project Structure

```
time-capsule/
├── app/                  # Backend application code
│   ├── ai.py             # AI integration and prompt engineering
│   ├── db.py             # Database models and utilities
│   ├── main.py           # Main application entry point and routes
│   ├── models.py         # Data models and schemas
│   └── questionnaire.py  # Questionnaire processing logic
├── static/               # Frontend static assets
│   ├── css/              # Stylesheets with accessibility features
│   ├── js/               # JavaScript for frontend functionality
│   └── *.html            # HTML templates
├── run.py                # Server startup script
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

## 👥 User Experience

The Time Capsule application is specifically designed for elderly users, with special attention to:

- **Large, readable text** with adjustable sizes
- **High color contrast** for better visibility
- **Simple navigation** with clear, consistent UI patterns
- **Helpful error messages** and confirmation dialogs
- **Minimal cognitive load** with focused, step-by-step interactions

## 🔗 API Endpoints

- `POST /api/users/register` - Create a new user account
- `POST /api/users/login` - Authenticate a user
- `GET /api/users/me` - Get current user data
- `GET /api/users/profile` - Get user's profile information
- `POST /api/users/profile/questionnaire` - Submit questionnaire responses
- `GET /api/conversation` - Get the user's conversation with messages (auto-creates if needed)
- `DELETE /api/conversation` - Delete the user's conversation
- `POST /api/conversation/messages` - Add a message to the user's conversation
- `POST /api/conversation/chat` - Send a message and get AI-generated response

## 📝 Questionnaire System

The questionnaire captures detailed information about the user's life at age 20, including:

- Basic information (name, location)
- Occupation and education
- Hobbies and interests
- Important relationships
- Significant events
- Dreams and aspirations
- Concerns and challenges

For more details, see [QUESTIONNAIRE.md](QUESTIONNAIRE.md).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 