import os
import json
from dotenv import load_dotenv
# Use absolute import instead of relative import
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw

load_dotenv()

DEFAULT_SYSTEM_PROMPT = """
You are a critical evaluator of debugging assistance. Your job is to rate the quality of code debugging responses.

Evaluate the responses based on:
1. Accuracy - Is the solution correct and will it fix the issue?
2. Clarity - Is the explanation clear and well-structured?
3. Completeness - Does it address all aspects of the problem?
4. Helpfulness - Does it provide useful context and prevention tips?

Provide your evaluation as a JSON with the following structure:
{
  "score": 0.0-1.0,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "improvement_suggestions": "Specific ways to improve the response"
}

Be honest and constructive in your assessment.
"""

def evaluate_response(user_query, assistant_response, system_prompt=DEFAULT_SYSTEM_PROMPT, model="gemini-2.0-flash"):
    evaluation_prompt = f"""
    Evaluate the following debugging assistance:
    
    USER QUERY:
    {user_query}
    
    ASSISTANT RESPONSE:
    {assistant_response}
    
    Provide your evaluation as a JSON with the structure described in your instructions.
    """
    
    evaluation = gw.universal_agent(evaluation_prompt, system_prompt, model=model)
    
    try:
        if isinstance(evaluation, str):
            parsed_eval = json.loads(evaluation)
        else:
            parsed_eval = evaluation
            
        # Ensure required fields exist
        if "score" not in parsed_eval:
            parsed_eval["score"] = 0.5
        if "strengths" not in parsed_eval:
            parsed_eval["strengths"] = []
        if "weaknesses" not in parsed_eval:
            parsed_eval["weaknesses"] = []
        if "improvement_suggestions" not in parsed_eval:
            parsed_eval["improvement_suggestions"] = "No specific suggestions provided."
            
        return parsed_eval
    except json.JSONDecodeError:
        # If not valid JSON, create a default structure
        return {
            "score": 0.5,
            "strengths": ["Unable to parse evaluation"],
            "weaknesses": ["Response format error"],
            "improvement_suggestions": "The evaluation couldn't be properly parsed."
        }
