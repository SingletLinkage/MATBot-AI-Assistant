from utils.gemini_wrapper import universal_agent
import os

def get_similar_queries(user_query, num_alternatives=3, model="gemini-2.0-flash"):
    """
    Generate similar queries based on the input query using the Gemini model.
    
    Args:
        user_query (str): The original user query
        num_alternatives (int): Number of alternative queries to generate
        model (str): The model name to use for generation
        
    Returns:
        list: List of similar queries
    """
    # Define the prompt for Gemini
    prompt = f"""
    Based on the following user query, generate {num_alternatives} alternative versions by rephrasing,
    restructuring, or improving grammar without changing the core meaning.

    Original query: "{user_query}"

    Return exactly {num_alternatives} alternatives in a JSON array with the field name "alternatives".
    
    For example:
    {{
        "alternatives": [
            "First alternative query",
            "Second alternative query",
            "Third alternative query"
        ]
    }}
    """

    # Set system prompt to guide the model
    system_prompt = "You are a query rephrasing specialist for technical documentation search systems."
    
    # Generate response using universal_agent
    response = universal_agent(prompt, system_prompt, model)
    
    # Process the response to extract the alternatives
    alternatives = []
    
    # Handle response based on its type
    if isinstance(response, dict) and "alternatives" in response:
        alternatives = response["alternatives"]
    elif isinstance(response, str):
        # Try to extract numbered list from text if returned as string
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            for i in range(1, num_alternatives + 1):
                if line.startswith(f"{i}."):
                    query = line[2:].strip()
                    alternatives.append(query)
                    break
    
    # Ensure we have the requested number of alternatives
    if len(alternatives) != num_alternatives:
        print(f"Warning: Expected {num_alternatives} alternatives, but got {len(alternatives)}.")
        # Fill with placeholders if we don't have enough
        while len(alternatives) < num_alternatives:
            alternatives.append(f"Alternative version of: {user_query}")
    
    return alternatives

# Example usage
if __name__ == "__main__":
    user_query = "In the SimpleMessagesModel, after changing the Receive block's Sample time to 0.5, the Scope output no longer matches the original sine wave pattern. What could be causing this discrepancy?"
    similar_queries = get_similar_queries(user_query)
    for i, query in enumerate(similar_queries, 1):
        print(f"{i}. {query}")
