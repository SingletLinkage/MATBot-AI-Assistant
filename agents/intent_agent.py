import os
import json
from dotenv import load_dotenv
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """
You are an intent analysis agent that helps determine the most appropriate response style for technical questions.

Your task is to analyze a user query about code, debugging, or technical topics and determine whether the user would 
benefit more from:

1. CONCISE response: Short, to-the-point answers that focus on direct solutions and key information
   * Best for: Simple questions, quick fixes, experienced users who just need specific commands or solutions

2. DETAILED response: Comprehensive explanations with context, background information, and thorough explanations
   * Best for: Complex problems, conceptual questions, beginners who need more explanation

Your output should ONLY be a JSON object with this format:
{
  "response_type": "CONCISE" or "DETAILED",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your decision"
}

If you're uncertain, default to "DETAILED" as it's better to provide too much information than too little.
"""

class IntentAgent:
    def __init__(self, model="gemini-2.0-flash", system_prompt=DEFAULT_SYSTEM_PROMPT):
        """
        Initialize the IntentAgent for determining appropriate response type.
        
        Args:
            model (str): The Gemini model to use
            system_prompt (str): System prompt that guides the agent's behavior
        """
        self.model = model
        self.system_prompt = system_prompt
        self.response_cache = {}  # Cache for responses
    
    def set_model(self, model):
        """Set a new model and reset cache."""
        self.model = model
        self.response_cache = {}  # Reset cache when model changes
    
    def set_system_prompt(self, system_prompt):
        """Set a new system prompt and reset cache."""
        self.system_prompt = system_prompt
        self.response_cache = {}  # Reset cache when prompt changes
    
    def determine_response_type(self, query):
        """
        Analyze the user query and determine whether it needs a concise or detailed response.
        
        Args:
            query (str): The user's question or request
            
        Returns:
            dict: Contains response_type ("CONCISE" or "DETAILED"), confidence score, and reasoning
        """
        # Generate a cache key based on the query
        cache_key = query[:100]  # Use first 100 chars as cache key
        
        # Check if we already have this response cached
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
        
        # Create the prompt for intent analysis
        prompt = f"""
        Please analyze this user query and determine the most appropriate response style:
        
        USER QUERY:
        {query}
        
        Determine if this query would be better answered with a CONCISE or DETAILED response.
        Provide your answer as a JSON object with response_type, confidence, and reasoning.
        """
        
        # Get response from LLM
        response = gw.universal_agent(
            prompt,
            self.system_prompt,
            model=self.model
        )
        
        # Handle different response types
        if isinstance(response, str):
            try:
                parsed_response = json.loads(response)
            except json.JSONDecodeError:
                # If we can't parse the response, default to detailed
                parsed_response = {
                    "response_type": "DETAILED",
                    "confidence": 0.5,
                    "reasoning": "Failed to parse LLM response, defaulting to detailed."
                }
        else:
            parsed_response = response
        
        # Ensure we have all required fields
        if "response_type" not in parsed_response:
            parsed_response["response_type"] = "DETAILED"
        if "confidence" not in parsed_response:
            parsed_response["confidence"] = 0.5
        if "reasoning" not in parsed_response:
            parsed_response["reasoning"] = "No reasoning provided."
            
        # Normalize response_type to uppercase
        parsed_response["response_type"] = parsed_response["response_type"].upper()
        
        # If response type is not recognized, default to detailed
        if parsed_response["response_type"] not in ["CONCISE", "DETAILED"]:
            parsed_response["response_type"] = "DETAILED"
        
        # Cache the response
        self.response_cache[cache_key] = parsed_response
        
        return parsed_response
