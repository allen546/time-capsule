# Time Capsule Questionnaire System

This document explains how to use the Time Capsule questionnaire system to collect and process user information for the young self simulation feature.

## Overview

The questionnaire system collects detailed information about a user's life at age 20. This information is used to generate a personalized AI model that can simulate conversations with the user's younger self.

## Questionnaire Content

The questionnaire covers the following areas:
- Basic information (name, location)
- Occupation/education
- Hobbies and interests
- Important relationships
- Significant life events
- Concerns and challenges
- Dreams and aspirations
- Family relationships
- Health and habits
- Regrets or advice

## Using the System

### Command-Line Tools

Two command-line tools are provided for testing and using the questionnaire system:

1. **Test Script** (`test_questionnaire.py`):
   - Demonstrates the questionnaire processing functionality
   - Contains a sample questionnaire response
   - Shows how answers are processed into structured data
   - Allows testing API submission

   ```bash
   python test_questionnaire.py
   ```

2. **Interactive Questionnaire** (`interactive_questionnaire.py`):
   - Provides an interactive command-line interface
   - Guides users through each question
   - Allows review and editing of answers
   - Saves responses to files
   - Submits data to the API

   ```bash
   python interactive_questionnaire.py [--username USERNAME] [--password PASSWORD]
   ```

### API Endpoints

The system provides the following API endpoints:

1. **Get Questionnaire Questions**:
   ```
   GET /api/questionnaire
   ```
   Returns the list of questions in the questionnaire.

2. **Submit Questionnaire Answers**:
   ```
   POST /api/users/profile/questionnaire
   Authorization: Bearer <token>
   Content-Type: application/json

   {
     "free_text": "你20岁时的名字是？张伟\n你20岁时生活在哪个城市或地区？北京\n..."
   }
   ```
   Or:
   ```
   POST /api/users/profile/questionnaire
   Authorization: Bearer <token>
   Content-Type: application/json

   {
     "answers": {
       "name": "张伟",
       "location": "北京",
       ...
     }
   }
   ```

3. **Get User Profile**:
   ```
   GET /api/users/profile
   Authorization: Bearer <token>
   ```
   Returns the user's profile data.

4. **Update Specific Profile Fields**:
   ```
   PATCH /api/users/profile
   Authorization: Bearer <token>
   Content-Type: application/json

   {
     "occupation_at_20": "新的职业信息",
     "hobbies_at_20": "新的爱好信息"
   }
   ```
   Updates only the specified fields in the user profile.

## Data Format

The questionnaire processes answers into a structured format with the following fields:

- `real_name`: User's name at age 20
- `location_at_20`: Where the user lived at age 20
- `occupation_at_20`: User's occupation or student status
- `major_at_20`: User's college major (if applicable)
- `hobbies_at_20`: User's interests and hobbies
- `important_people_at_20`: Significant relationships
- `significant_events_at_20`: Important life events
- `concerns_at_20`: Worries or challenges
- `dreams_at_20`: Aspirations and goals
- `family_relations_at_20`: Family relationships
- `health_at_20`: Health status
- `habits_at_20`: Personal habits
- `regrets_at_20`: Regrets or advice to younger self

## Processing Workflow

1. Users provide answers either through:
   - The interactive questionnaire tool
   - Direct API submission
   - A web interface (to be implemented)

2. The system processes the answers:
   - Parses free-text responses or structured answers
   - Extracts relevant information
   - Generates structured user profile data

3. The data is stored in the user's profile and used to:
   - Generate personalized AI prompts
   - Create the young self simulation
   - Enable realistic conversations

## Implementation Details

The questionnaire system is implemented with the following components:

- `app/questionnaire.py`: Core processing module
- `app/models.py`: User profile data models
- `app/main.py`: API endpoints
- `app/db.py`: Database interactions

## Example Usage

### Sample API Requests

```python
import requests
import json

# Login to get token
login_response = requests.post(
    "http://localhost:8000/api/users/login",
    json={"username": "user123", "password": "password123"}
)
token = login_response.json()["access_token"]

# Get questionnaire questions
questions_response = requests.get(
    "http://localhost:8000/api/questionnaire"
)
questions = questions_response.json()["questions"]

# Submit questionnaire answers
answers_response = requests.post(
    "http://localhost:8000/api/users/profile/questionnaire",
    headers={"Authorization": f"Bearer {token}"},
    json={"free_text": "你20岁时的名字是？张伟\n你20岁时生活在哪个城市或地区？北京\n..."}
)

# Get profile data
profile_response = requests.get(
    "http://localhost:8000/api/users/profile",
    headers={"Authorization": f"Bearer {token}"}
)
profile_data = profile_response.json()["profile"]

# Update specific fields
update_response = requests.patch(
    "http://localhost:8000/api/users/profile",
    headers={"Authorization": f"Bearer {token}"},
    json={"hobbies_at_20": "Updated hobbies information"}
) 