"""
Questionnaire Processing Module

This module processes questionnaire responses for the Time Capsule application.
It handles parsing, validating, and formatting questionnaire answers.
"""

from typing import Dict, Any, List, Tuple
import re


# Questionnaire questions in Chinese
QUESTIONS = [
    {
        "id": "name",
        "question": "你20岁时的名字是？",
        "description": "请回答你的名字，以便我在对话中使用。",
        "required": True
    },
    {
        "id": "location",
        "question": "你20岁时生活在哪个城市或地区？",
        "description": "比如北京、上海，或者某个小镇？",
        "required": True
    },
    {
        "id": "occupation",
        "question": "你当时是学生还是已经工作了？如果是学生，读什么专业？如果工作了，职业是什么？",
        "description": "比如大学生、工厂工人、教师学徒等。",
        "required": True
    },
    {
        "id": "hobbies",
        "question": "你20岁时最大的兴趣爱好是什么？",
        "description": "比如运动、音乐、读书、旅行？",
        "required": False
    },
    {
        "id": "important_people",
        "question": "那时有没有特别重要的人在你身边？",
        "description": "比如挚友、恋人，或者对你影响深远的某个人？",
        "required": False
    },
    {
        "id": "significant_events",
        "question": "20岁那一年，你经历过什么重大的事件或转折点吗？",
        "description": "比如升学、搬家、家庭变故，或者某个改变你想法的事？",
        "required": False
    },
    {
        "id": "concerns",
        "question": "那时的你正在为什么事情烦恼或努力？",
        "description": "比如经济压力、感情问题、对未来的迷茫？",
        "required": False
    },
    {
        "id": "dreams",
        "question": "你对未来的自己有过哪些期待或梦想？",
        "description": "比如想成为怎样的人，希望实现什么目标？",
        "required": False
    },
    {
        "id": "family_relations",
        "question": "你和家人的关系如何？",
        "description": "比如和父母是否亲密，有没有兄弟姐妹？",
        "required": False
    },
    {
        "id": "health",
        "question": "20岁时，你的身体健康状况如何？",
        "description": "比如是否健康，有没有特殊健康状况？",
        "required": False
    },
    {
        "id": "habits",
        "question": "你有没有特别的生活习惯？",
        "description": "比如经常运动、熬夜，或者生过病？",
        "required": False
    },
    {
        "id": "regrets",
        "question": "如果现在能对20岁的自己说一句话，你最想提的\"遗憾\"或\"建议\"是什么？",
        "description": "这能帮你还原年轻时的视角。",
        "required": False
    }
]


def parse_free_text_answers(text: str) -> Dict[str, str]:
    """
    Parse answers from free-form text input.
    
    Args:
        text: Free-form text containing question answers
        
    Returns:
        Dictionary of question IDs and answers
    """
    answers = {}
    current_question = None
    current_answer = []
    
    # Split text into lines and process
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line is a question
        for question in QUESTIONS:
            q_text = question["question"].strip()
            if line.startswith(q_text) or re.match(r'^\d+\.\s*' + re.escape(q_text), line):
                # If we were building an answer for a previous question, save it
                if current_question and current_answer:
                    answers[current_question["id"]] = '\n'.join(current_answer).strip()
                    current_answer = []
                
                # Extract answer from this line if it includes an answer
                if "：" in line or ": " in line:
                    parts = re.split(r'[:：]\s*', line, 1)
                    if len(parts) > 1:
                        # Line contains both question and answer
                        current_question = question
                        current_answer.append(parts[1].strip())
                    else:
                        # Line only contains the question
                        current_question = question
                else:
                    # Line only contains the question
                    current_question = question
                
                break
        else:
            # This line is not a question, so it must be an answer or continuation
            if current_question:
                # Remove the description part if present
                if line.startswith("（") and line.endswith("）"):
                    continue
                if line.startswith("(") and line.endswith(")"):
                    continue
                    
                current_answer.append(line)
    
    # Save the last answer if there is one
    if current_question and current_answer:
        answers[current_question["id"]] = '\n'.join(current_answer).strip()
    
    return answers


def extract_structured_data(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract structured data from questionnaire answers.
    
    Args:
        answers: Raw answers to questionnaire questions
        
    Returns:
        Structured data for the user profile
    """
    structured_data = {}
    
    # Process name
    if "name" in answers:
        structured_data["real_name"] = answers["name"]
    
    # Process location
    if "location" in answers:
        structured_data["location_at_20"] = answers["location"]
    
    # Process occupation and extract major if student
    if "occupation" in answers:
        occupation = answers["occupation"]
        structured_data["occupation_at_20"] = occupation
        
        # Try to extract major if the person was a student
        if "学生" in occupation or "大学" in occupation or "student" in occupation.lower():
            major_match = re.search(r'专业[是为：: ]*([\w\s]+)', occupation)
            if major_match:
                structured_data["major_at_20"] = major_match.group(1).strip()
    
    # Copy remaining fields directly
    field_mappings = {
        "hobbies": "hobbies_at_20",
        "important_people": "important_people_at_20",
        "significant_events": "significant_events_at_20",
        "concerns": "concerns_at_20",
        "dreams": "dreams_at_20",
        "family_relations": "family_relations_at_20",
        "health": "health_at_20",
        "habits": "habits_at_20",
        "regrets": "regrets_at_20"
    }
    
    for source, target in field_mappings.items():
        if source in answers:
            structured_data[target] = answers[source]
    
    return structured_data


def process_questionnaire_text(text: str) -> Dict[str, Any]:
    """
    Process free-form questionnaire text into structured user profile data.
    
    Args:
        text: Free-form text containing questionnaire answers
        
    Returns:
        Structured data for the user profile
    """
    # Parse the free text into answers
    answers = parse_free_text_answers(text)
    
    # Extract structured data from answers
    return extract_structured_data(answers)


def get_questionnaire_as_json() -> List[Dict[str, Any]]:
    """
    Get the questionnaire questions as JSON.
    
    Returns:
        List of question objects
    """
    return QUESTIONS 