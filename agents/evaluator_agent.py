import os
import json
from dotenv import load_dotenv
import sys
sys.path.append('/home/arka/Desktop/Hackathons/HCLTech_CS671')
from utils import gemini_wrapper as gw
from utils.ragas import evaluate_ragas

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
All the agrents have memory so they can remember previous interactions.
"""

def evaluate_response(user_query, assistant_response, system_prompt=DEFAULT_SYSTEM_PROMPT, model="gemini-2.0-flash", context=None):
    """
    Evaluate the assistant response with both traditional metrics and Ragas metrics if context is provided.
    
    Args:
        user_query: The user's original question
        assistant_response: The response from the assistant
        system_prompt: System prompt for the evaluator
        model: The model to use for evaluation
        context: The context used in RAG, if any
    
    Returns:
        Dictionary with evaluation metrics including Ragas metrics if context is provided
    """
    # Get Ragas metrics if context is provided
    ragas_metrics = None
    if context:
        ragas_metrics = evaluate_ragas(assistant_response, context, user_query)
    
    evaluation_prompt = f"""
    Evaluate the following debugging assistance:
    
    USER QUERY:
    {user_query}
    
    ASSISTANT RESPONSE:
    {assistant_response}
    """
    
    if ragas_metrics:
        evaluation_prompt += f"""
    
    RAGAS METRICS:
    - Faithfulness (accuracy of response facts): {ragas_metrics['faithfulness']}
    - Answer Relevance (relevance to query): {ragas_metrics['answer_relevance']}
    - Context Relevance (relevance of retrieved context): {ragas_metrics['context_relevance']}
    """
    
    evaluation_prompt += """
    
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
        
        # Add Ragas metrics if available
        if ragas_metrics:
            parsed_eval["ragas_metrics"] = ragas_metrics
            
        return parsed_eval
    except json.JSONDecodeError:
        # If not valid JSON, create a default structure
        default_eval = {
            "score": 0.5,
            "strengths": ["Unable to parse evaluation"],
            "weaknesses": ["Response format error"],
            "improvement_suggestions": "The evaluation couldn't be properly parsed."
        }
        
        # Add Ragas metrics if available
        if ragas_metrics:
            default_eval["ragas_metrics"] = ragas_metrics
            
        return default_eval
