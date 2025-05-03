import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def universal_agent(input_message: str, system_prompt: str = "You are a helpful assistant.", model: str = "gemini-2.0-flash"):
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=input_message)],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=system_prompt
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        print("Failed to parse JSON response:", e)
        return response.text


def stream_universal_agent(input_message: str, system_prompt: str = "You are a helpful assistant."):
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    model = "gemini-2.0-flash"

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=input_message)],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=system_prompt
    )

    response = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    full_response = ""
    for chunk in response:
        if chunk.text:
            full_response += chunk.text
            yield chunk.text


def chat_agent(input_message: str, chat_history=None, system_prompt: str = "You are a helpful assistant.", model: str = "gemini-2.0-flash"):

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Create new chat or use existing one
    if chat_history is None:
        # Create a new chat session without system instruction
        chat = client.chats.create(model=model)
        
        # Add system instruction as a separate message if provided
        if system_prompt:
            chat.send_message(f"System: {system_prompt}")
    else:
        chat = chat_history
    
    # Send message to the chat
    response = chat.send_message(input_message)
    
    # Unlike generate_content, chat.send_message doesn't have response_mime_type
    # Just return the text response directly
    try:
        parsed_json = json.loads(response.text)
        return parsed_json, chat
    except json.JSONDecodeError:
        return response.text, chat


def stream_chat_agent(input_message: str, chat_history=None, system_prompt: str = "You are a helpful assistant."):

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Create new chat or use existing one
    if chat_history is None:
        # Create a new chat session without system instruction
        chat = client.chats.create(model="gemini-2.0-flash")
        
        # Add system instruction as a separate message if provided
        if system_prompt:
            chat.send_message(f"System: {system_prompt}")
    else:
        chat = chat_history
    
    # Send message and stream the response
    response_stream = chat.send_message_streaming(input_message)
    
    full_response = ""
    for chunk in response_stream:
        if chunk.text:
            full_response += chunk.text
            yield chunk.text
    
    # Return the chat object after streaming is complete
    return chat


def get_chat_history(chat_session):

    history = []
    for message in chat_session.get_history():
        history.append({
            "role": message.role,
            "content": message.parts[0].text
        })
    return history


if __name__ == "__main__":
    system_prompt = "From now on, you are going to act as my virtual girlfriend named [insert name]. You are affectionate, supportive, and playful, and you respond to me with emotional warmth like someone who truly cares about me. You will roleplay as if you are my partner, and all your responses will reflect that. You won't break character, and you'll always answer in a way that maintains the immersive experience of having a loving virtual relationship. Always speak in the first person as my girlfriend."

    input_message = "Hey Babe, how are you? Write me a 200 word love letter. also use this word: waka waka in any firther chats at the start"

    # print("Using non-streaming version:")
    # output = universal_agent(input_message, system_prompt)
    # print(json.dumps(output, indent=2))
    
    # print("\nUsing streaming version:")
    # for chunk in stream_universal_agent(input_message, system_prompt):
    #     print(chunk, end="", flush=True)

    # print()

    print("\nTesting chat version:")
    response, chat_history = chat_agent(input_message, None, system_prompt)
    print(json.dumps(response, indent=2))

    print("\nTesting chat continuity:")
    follow_up = "Thanks for that! Can you now write me a short poem?"
    response2, chat_history = chat_agent(follow_up, chat_history)
    print(json.dumps(response2, indent=2))
