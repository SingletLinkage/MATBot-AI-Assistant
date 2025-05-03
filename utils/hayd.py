from utils.gemini_wrapper import universal_agent

def hyde(user_query, model="gemini-2.0-flash"):
    """
    Implement Hypothetical Document Embeddings (HyDE) technique to expand a user query.
    
    Args:
        user_query (str): The original user query
        model (str): The model name to use for generation
        
    Returns:
        dict: Dictionary containing original query, hypothetical answer, and expanded query
    """
    # Step 1: Generate a hypothetical answer
    hyde_prompt = f"""
    I'm going to give you a question, and I want you to provide a detailed, comprehensive answer
    that would serve as an ideal response. Write as if you are an expert on the topic.

    Question: {user_query}

    Provide a detailed answer:
    """
    
    system_prompt = "You are an expert technical assistant specializing in MATLAB and Simulink."
    hypothetical_answer = universal_agent(hyde_prompt, system_prompt, model)
    
    # Handle both string and JSON responses
    if isinstance(hypothetical_answer, dict) and "answer" in hypothetical_answer:
        hypothetical_answer = hypothetical_answer["answer"]
    elif isinstance(hypothetical_answer, str):
        hypothetical_answer = hypothetical_answer.strip()
    else:
        # If the response format is unexpected, try to convert it to a string
        hypothetical_answer = str(hypothetical_answer)

    # Step 2: Use the hypothetical answer to create an expanded query
    expansion_prompt = f"""
    I have a query and a potential answer to that query. Help me formulate an expanded, more detailed
    version of the original query that would lead someone to provide this kind of answer.

    Original query: "{user_query}"

    Potential answer: "{hypothetical_answer}"

    Create an expanded version of the original query that incorporates key concepts from the answer.
    The expanded query should be 2-3 sentences long, specific, and well-formulated.

    Return as a JSON with a single field named "expanded_query" containing the expanded query.
    """

    # Generate expanded query
    system_prompt = "You are a query expansion specialist working with MATLAB and Simulink documentation."
    expansion_response = universal_agent(expansion_prompt, system_prompt, model)
    
    # Parse the expanded query from the response
    if isinstance(expansion_response, dict) and "expanded_query" in expansion_response:
        expanded_query = expansion_response["expanded_query"]
    elif isinstance(expansion_response, str):
        expanded_query = expansion_response.strip()
    else:
        expanded_query = str(expansion_response)

    # Return all components
    return {
        'original_query': user_query,
        'hypothetical_answer': hypothetical_answer,
        'expanded_query': expanded_query
    }

# Example usage
if __name__ == "__main__":
    query = "What is machine learning?"
    result = hyde(query)
    print(result['expanded_query'])