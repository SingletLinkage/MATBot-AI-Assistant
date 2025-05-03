import streamlit as st
import os
from dotenv import load_dotenv
import json
import time
from agents.debugger_agent import DebuggerAgent, DEFAULT_SYSTEM_PROMPT as DEBUGGER_DEFAULT_PROMPT
from agents.evaluator_agent import evaluate_response, DEFAULT_SYSTEM_PROMPT as EVALUATOR_DEFAULT_PROMPT

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="CodeHelper - AI Debugging Assistant",
    page_icon="🐞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Available models
AVAILABLE_MODELS = [
    "gemini-2.0-flash",
    "gemini-pro", 
    "gemini-1.5-flash"
]

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "debugger_agent" not in st.session_state:
    st.session_state.debugger_agent = DebuggerAgent()
if "evaluation_history" not in st.session_state:
    st.session_state.evaluation_history = []
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = {}
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
if "model_params" not in st.session_state:
    st.session_state.model_params = {
        "model": AVAILABLE_MODELS[0],
        "system_prompt": DEBUGGER_DEFAULT_PROMPT
    }

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
    col1, col2, col3 = st.columns([1, 2, 1])
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

def render_evaluation_sidebar():
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

def render_model_params_sidebar():
    with st.sidebar:
        st.sidebar.markdown("<h3 class='sidebar-header'>Model Parameters</h3>", unsafe_allow_html=True)
        
        # Only allow changes if chat hasn't started
        disabled = st.session_state.chat_started
        
        if disabled:
            st.info("Chat already started. Parameters are locked.")
        
        selected_model = st.selectbox(
            "Select Model", 
            options=AVAILABLE_MODELS,
            index=AVAILABLE_MODELS.index(st.session_state.model_params["model"]) if st.session_state.model_params["model"] in AVAILABLE_MODELS else 0,
            disabled=disabled
        )
        
        system_prompt = st.text_area(
            "System Prompt", 
            value=st.session_state.model_params["system_prompt"],
            height=300,
            disabled=disabled
        )
        
        if st.button("Set Parameters", disabled=disabled):
            st.session_state.model_params["model"] = selected_model
            st.session_state.model_params["system_prompt"] = system_prompt
            
            # Create a new debugger agent with these parameters
            st.session_state.debugger_agent = DebuggerAgent(
                model=selected_model,
                system_prompt=system_prompt
            )
            
            st.success("Parameters set successfully!")
            st.rerun()
        
        if st.button("Reset to Default", disabled=disabled):
            st.session_state.model_params["model"] = AVAILABLE_MODELS[0]
            st.session_state.model_params["system_prompt"] = DEBUGGER_DEFAULT_PROMPT
            
            # Create a new debugger agent with default parameters
            st.session_state.debugger_agent = DebuggerAgent()
            
            st.success("Parameters reset to default!")
            st.rerun()

def handle_user_input():
    user_message = st.chat_input("Ask your code question here...")
    
    if user_message:
        # Mark chat as started
        st.session_state.chat_started = True
        
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_message})
        
        with st.spinner("Generating response..."):
            # Get response from Debugger Agent
            assistant_message = st.session_state.debugger_agent.get_response(user_message)
            
            # Add assistant response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": assistant_message})
            
            # Evaluate the response
            eval_data = evaluate_response(
                user_message, 
                assistant_message,
                system_prompt=EVALUATOR_DEFAULT_PROMPT,
                model=st.session_state.model_params["model"]
            )
            
            st.session_state.evaluation_history.append(eval_data)
            
        # Rerun to update the UI
        st.rerun()

def main():
    render_header()
    
    # Create three columns - main chat and two sidebars
    left_sidebar, main_col, right_sidebar = st.columns([1, 3, 1])
    
    with main_col:
        render_debug_session_header()
        display_chat_history()
        handle_user_input()
    
    # Left sidebar for evaluations
    with left_sidebar:
        render_evaluation_sidebar()
    
    # Right sidebar for model parameters
    with right_sidebar:
        render_model_params_sidebar()

if __name__ == "__main__":
    main()