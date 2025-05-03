import streamlit as st
import os
from dotenv import load_dotenv
import json
import time
from agents.debugger_agent import DebuggerAgent, DEFAULT_SYSTEM_PROMPT as DEBUGGER_DEFAULT_PROMPT
from agents.evaluator_agent import evaluate_response, DEFAULT_SYSTEM_PROMPT as EVALUATOR_DEFAULT_PROMPT
from clustering import init_clusters, query_clusters

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
if "source_clusters" not in st.session_state:
    st.session_state.source_clusters = {}
if "feedback_messages" not in st.session_state:
    st.session_state.feedback_messages = {}
if "improved_responses" not in st.session_state:
    st.session_state.improved_responses = {}

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
    .source-button {
        margin-top: 0.5rem;
        color: #4b9cff;
        background: none;
        border: none;
        padding: 0;
        text-decoration: underline;
        cursor: pointer;
    }
    .source-container {
        margin-top: 0.5rem;
        padding: 0.5rem;
        background-color: #f9f9f9;
        border-left: 3px solid #ffbc42;
        font-size: 0.9rem;
    }
    .source-title {
        font-weight: bold;
        margin-bottom: 0.3rem;
    }
    .source-heading {
        font-style: italic;
        color: #555555;
    }
    .source-link {
        color: #0366d6;
        text-decoration: none;
        display: inline-block;
        padding: 0.3rem 0.7rem;
        margin-top: 0.5rem;
        border-radius: 0.3rem;
        background-color: #e6f1ff;
        font-size: 0.85rem;
        transition: background-color 0.2s;
        border: 1px solid #c8e1ff;
    }
    .source-link:hover {
        background-color: #c8e1ff;
        text-decoration: none;
    }
    .source-link i {
        margin-right: 0.3rem;
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

def render_chat_message(message, is_user=False, message_idx=None):
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
    
    # Show sources for assistant messages
    if not is_user and message_idx is not None and message_idx in st.session_state.source_clusters:
        sources = st.session_state.source_clusters[message_idx]
        if sources:
            with st.expander("Show sources used for this response"):
                for i, source in enumerate(sources):
                    st.markdown(f"**Source {i+1}: {source['title']}**")
                    st.markdown(f"*{source['heading']}*")
                    st.markdown(source['content'])
                    if 'link' in source:
                        st.markdown(f"[View original document]({source['link']})")
                    st.divider()

def process_negative_feedback(message_idx):
    """Generate an improved response based on evaluation feedback"""
    # Get the original message and its evaluation
    original_message = st.session_state.chat_history[message_idx]["content"]
    user_query = st.session_state.chat_history[message_idx-1]["content"]
    
    # Get the evaluation data
    eval_idx = (message_idx - 1) // 2
    if eval_idx < len(st.session_state.evaluation_history):
        eval_data = st.session_state.evaluation_history[eval_idx]
        
        # Format the strengths and weaknesses
        strengths = "\n".join([f"- {s}" for s in eval_data["strengths"]])
        weaknesses = "\n".join([f"- {w}" for w in eval_data["weaknesses"]])
        
        # Create the improvement prompt
        improvement_prompt = f"""
        Please improve your previous response based on the following feedback:
        
        USER QUERY:
        {user_query}
        
        YOUR PREVIOUS RESPONSE:
        {original_message}
        
        EVALUATION:
        Strengths:
        {strengths}
        
        Weaknesses:
        {weaknesses}
        
        Suggestions for improvement:
        {eval_data["improvement_suggestions"]}
        
        Please provide a completely revised response that addresses the weaknesses
        while maintaining the strengths.
        """
        
        with st.spinner("Generating improved response..."):
            # Get the context clusters if available
            if message_idx in st.session_state.source_clusters:
                context_text = ""
                for i, cluster in enumerate(st.session_state.source_clusters[message_idx]):
                    context_text += f"Source {i+1}:\nTitle: {cluster['title']}\nLink: {cluster.get('link', 'N/A')}\nHeading: {cluster['heading']}\nContent: {cluster['content']}\n\n"
                
                improvement_prompt += f"\n\nCONTEXT: {context_text}"
            
            # Generate improved response
            improved_response = st.session_state.debugger_agent.get_response(improvement_prompt)
            
            # Store the improved response
            st.session_state.improved_responses[message_idx] = improved_response
            
            # Add the improved response to chat history as a new assistant message
            st.session_state.chat_history.append({"role": "assistant", "content": improved_response})
            
            # Clone the source clusters from the original message to the new one
            new_message_idx = len(st.session_state.chat_history) - 1
            if message_idx in st.session_state.source_clusters:
                st.session_state.source_clusters[new_message_idx] = st.session_state.source_clusters[message_idx]
            
            # Evaluate the improved response
            with st.spinner("Evaluating improved response..."):
                eval_data = evaluate_response(
                    user_query, 
                    improved_response,
                    system_prompt=EVALUATOR_DEFAULT_PROMPT,
                    model=st.session_state.model_params["model"]
                )
                st.session_state.evaluation_history.append(eval_data)
            
            return improved_response
    
    return "Sorry, I couldn't generate an improved response. Please try asking your question again."

def display_chat_history():
    for i, message in enumerate(st.session_state.chat_history):
        # Display message
        render_chat_message(message["content"], message["role"] == "user", i)
        
        # Display feedback thank you message if present
        if i in st.session_state.feedback_messages:
            st.info(st.session_state.feedback_messages[i])
        
        # Add feedback buttons after assistant's messages
        if message["role"] == "assistant" and i not in st.session_state.feedback_given:
            cols = st.columns([1, 1, 4])
            with cols[0]:
                if st.button("👍 Helpful", key=f"helpful_{i}"):
                    st.session_state.feedback_given[i] = "helpful"
                    st.session_state.feedback_messages[i] = "Thank you for your positive feedback! I'm glad the response was helpful."
                    # st.toast("Thank you for your positive feedback! I'm glad the response was helpful.", icon="😊")
                    st.rerun()

            with cols[1]:
                if st.button("👎 Not Helpful", key=f"not_helpful_{i}"):
                    st.session_state.feedback_given[i] = "not_helpful"
                    st.session_state.feedback_messages[i] = "I'm sorry the response wasn't helpful. Generating an improved response..."
                    # st.toast("I'm sorry the response wasn't helpful.", icon="😞")

                    # Process negative feedback to generate improved response
                    process_negative_feedback(i)
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

def handle_user_input(clusterer):
    user_message = st.chat_input("Ask your code question here...")
    
    if user_message:
        # Mark chat as started
        st.session_state.chat_started = True
        
        # Add user message to chat history
        user_message_idx = len(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "user", "content": user_message})

        # Get clusters for the user message
        with st.spinner("Finding relevant clusters..."):
            clusters = query_clusters(clusterer, user_message)
            
            # Store the clusters for displaying as sources
            assistant_message_idx = user_message_idx + 1
            st.session_state.source_clusters[assistant_message_idx] = clusters
            
            # Format clusters for context
            context_text = ""
            for i, cluster in enumerate(clusters):
                context_text += f"Source {i+1}:\nTitle: {cluster['title']}\n Link: {cluster['link']}\nHeading: {cluster['heading']}\nContent: {cluster['content']}\n\n"
            
            # Add context to user message
            user_message_with_context = f"USER: {user_message}\n\nCONTEXT: {context_text}"
        
        with st.spinner("Generating response..."):
            # Get response from Debugger Agent
            assistant_message = st.session_state.debugger_agent.get_response(user_message_with_context)
            
            # Add assistant response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": assistant_message})
            
            # Evaluate the response
            eval_data = evaluate_response(
                user_message_with_context, 
                assistant_message,
                system_prompt=EVALUATOR_DEFAULT_PROMPT,
                model=st.session_state.model_params["model"]
            )
            
            st.session_state.evaluation_history.append(eval_data)
            
        # Rerun to update the UI
        st.rerun()

def main(clusterer):
    render_header()
    
    # Create three columns - main chat and two sidebars
    left_sidebar, main_col, right_sidebar = st.columns([1, 3, 1])
    
    with main_col:
        render_debug_session_header()
        display_chat_history()
        handle_user_input(clusterer)
    
    # Left sidebar for evaluations
    with left_sidebar:
        render_evaluation_sidebar()
    
    # Right sidebar for model parameters
    with right_sidebar:
        render_model_params_sidebar()

if __name__ == "__main__":
    clusterer = init_clusters()
    main(clusterer)