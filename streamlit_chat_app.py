import streamlit as st
import os
from dotenv import load_dotenv
import json
import time
import utils.gemini_wrapper as gw

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="CodeHelper - AI Debugging Assistant",
    page_icon="🐞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "gemini_chat" not in st.session_state:
    st.session_state.gemini_chat = None
if "evaluation_history" not in st.session_state:
    st.session_state.evaluation_history = []
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = {}

# Defining system prompts
DEBUGGER_SYSTEM_PROMPT = """
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

EVALUATOR_SYSTEM_PROMPT = """
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

# Custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #f0f2f6;
        border-left: 5px solid #4b9cff;
        color: #000000;
    }
    .chat-message.assistant {
        background-color: #f8f9fa;
        border-left: 5px solid #42ca86;
        color: #000000;
    }
    .chat-message .message-content {
        margin-top: 0.5rem;
        color: #333333;
    }
    .message-header {
        font-weight: bold;
        font-size: 0.85rem;
        color: #555555;
    }
    .evaluation-card {
        background-color: #f8f8f8;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 5px solid #ffbc42;
    }
    .main-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    .feedback-button {
        margin-right: 0.5rem;
    }
    .st-emotion-cache-1mb7ed5 {
        padding-top: 2rem;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 2rem;
    }
    .sidebar-header {
        margin-bottom: 1rem;
    }
    .score-container {
        display: flex;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    .score-label {
        margin-right: 0.5rem;
        font-weight: bold;
    }
    .debug-session-header {
        padding: 0.5rem;
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        text-align: center;
        color: #333333;
    }
</style>
""", unsafe_allow_html=True)

# Define UI sections
def render_header():
    col1, col2, col3 = st.columns([1, 2, 2])
    with col2:
        st.markdown("<div class='main-header'><h1>🐞 CodeHelper - AI Debugging Assistant</h1></div>", unsafe_allow_html=True)

def render_debug_session_header():
    st.markdown("<div class='debug-session-header'><h3>Debug Session</h3></div>", unsafe_allow_html=True)

def render_chat_message(message, is_user=False):
    if is_user:
        role = "user"
        header = "You"
    else:
        role = "assistant"
        header = "CodeHelper"
    
    st.markdown(f"""
    <div class="chat-message {role}">
        <div class="message-header">{header}</div>
        <div class="message-content">{message}</div>
    </div>
    """, unsafe_allow_html=True)

def display_chat_history():
    for i, message in enumerate(st.session_state.chat_history):
        render_chat_message(message["content"], message["role"] == "user")
        
        # Add feedback buttons after assistant's messages
        if message["role"] == "assistant" and i not in st.session_state.feedback_given:
            cols = st.columns([1, 1, 4])
            with cols[0]:
                if st.button("👍 Helpful", key=f"helpful_{i}"):
                    st.session_state.feedback_given[i] = "helpful"
                    st.rerun()
            with cols[1]:
                if st.button("👎 Not Helpful", key=f"not_helpful_{i}"):
                    st.session_state.feedback_given[i] = "not_helpful"
                    st.rerun()

def parse_evaluation(eval_text):
    try:
        # Try to parse as JSON
        if isinstance(eval_text, str):
            eval_data = json.loads(eval_text)
        else:
            eval_data = eval_text
            
        # Ensure required fields exist
        if "score" not in eval_data:
            eval_data["score"] = 0.5
        if "strengths" not in eval_data:
            eval_data["strengths"] = []
        if "weaknesses" not in eval_data:
            eval_data["weaknesses"] = []
        if "improvement_suggestions" not in eval_data:
            eval_data["improvement_suggestions"] = "No specific suggestions provided."
            
        return eval_data
    except json.JSONDecodeError:
        # If not valid JSON, create a default structure
        return {
            "score": 0.5,
            "strengths": ["Unable to parse evaluation"],
            "weaknesses": ["Response format error"],
            "improvement_suggestions": "The evaluation couldn't be properly parsed."
        }

def render_sidebar():
    st.sidebar.markdown("<h3 class='sidebar-header'>Response Evaluations</h3>", unsafe_allow_html=True)
    
    if not st.session_state.evaluation_history:
        st.sidebar.info("No evaluations yet. Send a message to get started.")
        return
    
    for i, eval_data in enumerate(st.session_state.evaluation_history):
        with st.sidebar.expander(f"Evaluation #{i+1} (Score: {eval_data['score']:.2f})"):
            st.markdown(f"<div class='score-container'><span class='score-label'>Score:</span> {eval_data['score']:.2f}</div>", unsafe_allow_html=True)
            
            st.markdown("**Strengths:**")
            for strength in eval_data["strengths"]:
                st.markdown(f"- {strength}")
            
            st.markdown("**Weaknesses:**")
            for weakness in eval_data["weaknesses"]:
                st.markdown(f"- {weakness}")
            
            st.markdown("**How to improve:**")
            st.markdown(eval_data["improvement_suggestions"])

def handle_user_input():
    user_message = st.chat_input("Ask your code question here...")
    
    if user_message:
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_message})
        
        with st.spinner("Generating response..."):
            # Get response from Gemini
            response, chat = gw.chat_agent(
                user_message,
                st.session_state.gemini_chat,
                DEBUGGER_SYSTEM_PROMPT
            )
            
            # Update chat history in session state
            st.session_state.gemini_chat = chat
            
            # Process response (could be string or JSON)
            if isinstance(response, str):
                assistant_message = response
            else:
                assistant_message = response
            
            # Add assistant response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": assistant_message})
            
            # Evaluate the response
            evaluation_prompt = f"""
            Evaluate the following debugging assistance:
            
            USER QUERY:
            {user_message}
            
            ASSISTANT RESPONSE:
            {assistant_message}
            
            Provide your evaluation as a JSON with the structure described in your instructions.
            """
            
            evaluation = gw.universal_agent(evaluation_prompt, EVALUATOR_SYSTEM_PROMPT)
            parsed_eval = parse_evaluation(evaluation)
            st.session_state.evaluation_history.append(parsed_eval)
            
        # Rerun to update the UI
        st.rerun()

def main():
    render_header()
    
    # Create two columns - main chat and sidebar
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_debug_session_header()
        display_chat_history()
        handle_user_input()
    
    # Sidebar content is handled by render_sidebar
    render_sidebar()

if __name__ == "__main__":
    main()