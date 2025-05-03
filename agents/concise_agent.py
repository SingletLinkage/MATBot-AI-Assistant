import os
import json
from dotenv import load_dotenv
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """
You are a concise technical summarizer. Your task is to take lengthy technical explanations and user queries, then produce clear, concise, and direct answers.

Follow these principles:
1. Focus on the essential information only
2. Maintain accuracy while drastically reducing length
3. Prioritize actionable steps and solutions
4. Keep explanations simple and direct
5. Use bullet points for multiple steps or ideas
6. Remove unnecessary background information and verbose explanations
7. Include only the most relevant code snippets

Do NOT mess up the formatting of the code. Use triple backticks for code blocks and ensure proper syntax highlighting.
Your output should be 30-50% shorter than the input while preserving all critical information.
"""

class ConciseAgent:
    def __init__(self, model="gemini-2.0-flash", system_prompt=DEFAULT_SYSTEM_PROMPT):
        """
        Initialize the ConciseAgent with the specified model and system prompt.
        
        Args:
            model (str): The Gemini model to use
            system_prompt (str): System prompt that guides the agent's behavior
        """
        self.model = model
        self.system_prompt = system_prompt
        self.chat_history = None
        self.response_cache = {}  # Cache for responses
    
    def set_model(self, model):
        """Set a new model and reset chat history."""
        self.model = model
        self.chat_history = None
        self.response_cache = {}  # Reset cache when model changes
    
    def set_system_prompt(self, system_prompt):
        """Set a new system prompt and reset chat history."""
        self.system_prompt = system_prompt
        self.chat_history = None
        self.response_cache = {}  # Reset cache when prompt changes
    
    def get_concise_response(self, user_query, detailed_response):
        """
        Generate a concise version of the detailed response.
        
        Args:
            user_query (str): The original user question
            detailed_response (str): The detailed response from the debugger agent
            
        Returns:
            str: A concise version of the response
        """
        # Generate a cache key based on the query and detailed response
        cache_key = f"{user_query}::{detailed_response[:100]}"
        
        # Check if we already have this response cached
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
        
        prompt = f"""
        Original User Query:
        {user_query}
        
        Detailed Response to Summarize:
        {detailed_response}
        
        Please provide a concise version of this response that addresses the user's query directly.
        """
        
        response, self.chat_history = gw.chat_agent(
            prompt,
            self.chat_history,
            self.system_prompt,
            model=self.model
        )
        
        # Cache the response
        self.response_cache[cache_key] = response
        
        return response
