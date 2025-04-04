"""
Extended User Model Definitions

This module defines the structure and schema for the extended user model
that includes questionnaire data for the Time Capsule application.
"""

from typing import Dict, Any, Optional, TypedDict


class UserProfileFields(TypedDict, total=False):
    """TypedDict defining all possible fields in a user profile."""
    # Basic user information
    real_name: str  # User's real name
    age: int  # User's current age
    basic_data: str  # General background information

    # 20-year-old self questionnaire data
    location_at_20: str  # Where the user lived at age 20
    occupation_at_20: str  # Whether the user was a student, working, etc.
    education: str  # Educational background
    major_at_20: str  # What subject the user studied
    hobbies_at_20: str  # What the user enjoyed doing
    important_people_at_20: str  # Significant relationships
    significant_events_at_20: str  # Major life events around age 20
    concerns_at_20: str  # What worried or motivated the user
    dreams_at_20: str  # Hopes and aspirations for the future
    family_relations_at_20: str  # Relationships with family members
    health_at_20: str  # Physical health condition
    habits_at_20: str  # Lifestyle habits
    regrets_at_20: str  # Regrets or advice to younger self
    personality: str  # Personality traits and characteristics


def create_empty_user_profile() -> Dict[str, Any]:
    """
    Create an empty user profile with all fields initialized to None.
    
    Returns:
        A dictionary with all user profile fields set to None
    """
    return {
        # Basic user information
        "real_name": None,
        "age": None,
        "basic_data": None,
        
        # 20-year-old self questionnaire data
        "location_at_20": None,
        "occupation_at_20": None,
        "education": None,
        "major_at_20": None,
        "hobbies_at_20": None,
        "important_people_at_20": None,
        "significant_events_at_20": None,
        "concerns_at_20": None,
        "dreams_at_20": None,
        "family_relations_at_20": None,
        "health_at_20": None,
        "habits_at_20": None,
        "regrets_at_20": None,
        "personality": None
    }


def process_questionnaire_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Process raw questionnaire answers into a structured user profile.
    
    Args:
        answers: Dictionary of answers to questionnaire questions
        
    Returns:
        A structured user profile with questionnaire data
    """
    profile = create_empty_user_profile()
    
    # Map answers to corresponding profile fields
    if "name" in answers:
        profile["real_name"] = answers["name"]
        
    if "location" in answers:
        profile["location_at_20"] = answers["location"]
    
    if "occupation" in answers:
        occupation = answers["occupation"]
        if "学生" in occupation or "student" in occupation.lower():
            profile["occupation_at_20"] = "学生"
            if "专业" in answers:
                profile["major_at_20"] = answers["专业"]
        else:
            profile["occupation_at_20"] = occupation
    
    if "hobbies" in answers:
        profile["hobbies_at_20"] = answers["hobbies"]
    
    if "important_people" in answers:
        profile["important_people_at_20"] = answers["important_people"]
    
    if "significant_events" in answers:
        profile["significant_events_at_20"] = answers["significant_events"]
    
    if "concerns" in answers:
        profile["concerns_at_20"] = answers["concerns"]
    
    if "dreams" in answers:
        profile["dreams_at_20"] = answers["dreams"]
    
    if "family_relations" in answers:
        profile["family_relations_at_20"] = answers["family_relations"]
    
    if "health" in answers:
        profile["health_at_20"] = answers["health"]
        
    if "habits" in answers:
        profile["habits_at_20"] = answers["habits"]
    
    if "regrets" in answers:
        profile["regrets_at_20"] = answers["regrets"]
    
    return profile


def update_user_profile(existing_profile: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing user profile with new data.
    
    Args:
        existing_profile: The current user profile
        updates: New data to update the profile with
        
    Returns:
        The updated profile
    """
    # Start with a copy of the existing profile
    updated_profile = dict(existing_profile)
    
    # Update with new values, skipping None values
    for key, value in updates.items():
        if value is not None:
            updated_profile[key] = value
            
    return updated_profile 