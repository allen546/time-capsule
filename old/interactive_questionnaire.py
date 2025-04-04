"""
Interactive Questionnaire for Time Capsule

This script provides a command-line interface to interactively fill out
the Time Capsule questionnaire, save responses, and submit them to the API.
"""

import asyncio
import json
import sys
import os
import argparse
import aiohttp
from datetime import datetime
from app.questionnaire import get_questionnaire_as_json, process_questionnaire_text


class InteractiveQuestionnaire:
    def __init__(self):
        self.questions = get_questionnaire_as_json()
        self.answers = {}
        self.api_url = "http://localhost:8000/api/users/profile/questionnaire"
        self.auth_url = "http://localhost:8000/api/users/login"
        self.output_dir = "questionnaire_responses"
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def display_welcome(self):
        """Display welcome message"""
        print("\n" + "=" * 50)
        print("Time Capsule Interactive Questionnaire".center(50))
        print("=" * 50)
        print("\nThis questionnaire will gather information about your life at age 20.")
        print("Your answers will be used to create a personalized AI interaction.")
        print("\nInstructions:")
        print("- For each question, type your answer and press Enter")
        print("- You can skip optional questions by pressing Enter without typing anything")
        print("- Your answers will be saved automatically")
        print("- At the end, you can review and edit your answers before submitting")
        print("\nLet's begin!\n")
    
    async def run(self, username=None, password=None):
        """Run the interactive questionnaire"""
        self.display_welcome()
        
        # Ask each question
        for i, question in enumerate(self.questions, 1):
            q_id = question["id"]
            q_text = question["question"]
            q_desc = question["description"]
            is_required = question["required"]
            
            # Display question
            print(f"\nQuestion {i} of {len(self.questions)}")
            print(f"{q_text}")
            print(f"({q_desc})")
            
            if is_required:
                print("* Required")
            
            # Get answer
            while True:
                answer = input("> ").strip()
                
                if not answer and is_required:
                    print("This question is required. Please provide an answer.")
                else:
                    break
            
            if answer:
                self.answers[q_id] = answer
        
        # Review answers
        self.review_answers()
        
        # Save answers
        self.save_responses()
        
        # Submit to API
        if self.ask_yes_no("Would you like to submit your answers to the server?"):
            if not username:
                username = input("Username: ")
            if not password:
                password = input("Password: ")
            
            await self.submit_to_api(username, password)
    
    def review_answers(self):
        """Review and potentially edit answers"""
        while True:
            print("\n=== Your Answers ===")
            for i, question in enumerate(self.questions, 1):
                q_id = question["id"]
                q_text = question["question"]
                answer = self.answers.get(q_id, "(not answered)")
                print(f"{i}. {q_text}")
                print(f"   Answer: {answer}")
                print()
            
            if not self.ask_yes_no("Would you like to edit any of your answers?"):
                break
            
            try:
                q_num = int(input("Which question would you like to edit? (enter number): "))
                if 1 <= q_num <= len(self.questions):
                    question = self.questions[q_num - 1]
                    q_id = question["id"]
                    q_text = question["question"]
                    
                    print(f"\nEditing: {q_text}")
                    print(f"Current answer: {self.answers.get(q_id, '(not answered)')}")
                    
                    new_answer = input("New answer: ").strip()
                    if new_answer:
                        self.answers[q_id] = new_answer
                    elif q_id in self.answers:
                        del self.answers[q_id]
                else:
                    print("Invalid question number.")
            except ValueError:
                print("Please enter a valid number.")
    
    def save_responses(self):
        """Save responses to a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_dir}/questionnaire_{timestamp}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            for question in self.questions:
                q_id = question["id"]
                q_text = question["question"]
                answer = self.answers.get(q_id, "")
                
                if answer:
                    f.write(f"{q_text}{answer}\n\n")
        
        print(f"\nYour responses have been saved to {filename}")
        
        # Also save as structured JSON
        structured_text = self.format_as_text()
        structured_data = process_questionnaire_text(structured_text)
        
        json_filename = f"{self.output_dir}/questionnaire_{timestamp}.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        print(f"Structured data has been saved to {json_filename}")
    
    def format_as_text(self):
        """Format answers as text for processing"""
        text = ""
        for question in self.questions:
            q_id = question["id"]
            q_text = question["question"]
            answer = self.answers.get(q_id, "")
            
            if answer:
                text += f"{q_text}{answer}\n\n"
        
        return text
    
    def ask_yes_no(self, question):
        """Ask a yes/no question"""
        while True:
            response = input(f"{question} (y/n): ").lower()
            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            print("Please answer 'y' or 'n'.")
    
    async def submit_to_api(self, username, password):
        """Submit answers to the API"""
        try:
            async with aiohttp.ClientSession() as session:
                # Login
                credentials = {
                    "username": username,
                    "password": password
                }
                
                print("\nLogging in...")
                async with session.post(self.auth_url, json=credentials) as response:
                    if response.status != 200:
                        print(f"Login failed: {response.status}")
                        return
                    
                    login_data = await response.json()
                    token = login_data.get("access_token")
                    
                    if not token:
                        print("No token received")
                        return
                
                # Submit questionnaire
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                text_data = self.format_as_text()
                payload = {"free_text": text_data}
                
                print("Submitting answers...")
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        print("\n✓ Answers submitted successfully!")
                        print(f"Response: {result.get('message')}")
                    else:
                        print(f"\n✗ Submission failed: {response.status}")
                        print(result)
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Interactive Time Capsule Questionnaire")
    parser.add_argument("--username", help="Username for API submission")
    parser.add_argument("--password", help="Password for API submission")
    
    args = parser.parse_args()
    
    questionnaire = InteractiveQuestionnaire()
    asyncio.run(questionnaire.run(args.username, args.password))


if __name__ == "__main__":
    main() 