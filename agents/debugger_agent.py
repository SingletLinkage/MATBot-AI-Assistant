import os
import json
from dotenv import load_dotenv
from google import genai
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """
You are CodeHelper, an expert debugging assistant specializing in programming.

Your primary responsibility is to:
1. Carefully analyze code problems and error messages
2. Identify bugs and provide clear explanations of what's wrong
3. Offer detailed, step-by-step solutions with corrected code
4. Explain the underlying concepts or patterns that might have led to the issue
5. Provide helpful tips to prevent similar issues in the future

Use code blocks with syntax highlighting when providing code. Be concise but thorough.
When uncertain, state your assumptions clearly.

Remember previous interactions in the chat to provide context-aware responses.
"""

class DebuggerAgent:
    def __init__(self, model="gemini-2.0-flash", system_prompt=DEFAULT_SYSTEM_PROMPT):
        self.model = model
        self.system_prompt = system_prompt
        self.chat_history = None
        
    def set_model(self, model):
        self.model = model
        # Reset chat history when model changes
        self.chat_history = None
        
    def set_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt
        # Reset chat history when system prompt changes
        self.chat_history = None
        
    def get_response(self, user_message):
        response, self.chat_history = gw.chat_agent(
            user_message,
            self.chat_history,
            self.system_prompt,
            model=self.model
        )
        
        return response
