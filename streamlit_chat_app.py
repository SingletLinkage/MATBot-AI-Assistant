import streamlit as st
import os
from dotenv import load_dotenv
import json
import time
from agents.debugger_agent import DebuggerAgent, DEFAULT_SYSTEM_PROMPT as DEBUGGER_DEFAULT_PROMPT
from agents.evaluator_agent import evaluate_response, DEFAULT_SYSTEM_PROMPT as EVALUATOR_DEFAULT_PROMPT
from agents.concise_agent import ConciseAgent, DEFAULT_SYSTEM_PROMPT as CONCISE_DEFAULT_PROMPT
from agents.intent_agent import IntentAgent, DEFAULT_SYSTEM_PROMPT as INTENT_DEFAULT_PROMPT
from clustering import init_clusters, query_clusters
from functools import lru_cache
import hashlib

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

# Response modes
RESPONSE_MODES = ["auto", "detailed", "concise"]

# Initialize session state and use get() pattern to avoid re-initialization on rerun
if "session_initialized" not in st.session_state:
    st.session_state.chat_history = []
    st.session_state.debugger_agent = DebuggerAgent()
    st.session_state.concise_agent = ConciseAgent()
    st.session_state.intent_agent = IntentAgent()
    st.session_state.evaluation_history = []
    st.session_state.feedback_given = {}
    st.session_state.chat_started = False
    st.session_state.model_params = {
        "model": AVAILABLE_MODELS[0],
        "system_prompt": DEBUGGER_DEFAULT_PROMPT
    }
    st.session_state.source_clusters = {}
    st.session_state.feedback_messages = {}
    st.session_state.improved_responses = {}
    st.session_state.response_mode = "auto"  # Default to auto for smart detection
    st.session_state.expanded_details = {}
    st.session_state.expanded_summary = {}
    st.session_state.cached_responses = {}
    st.session_state.alternative_versions = {}  # Store both versions of responses
    st.session_state.intent_analysis = {}  # Store intent analysis results
    st.session_state.show_advanced = False  # Advanced mode toggle
    st.session_state.session_initialized = True

# Custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        position: relative;
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
        display: flex;
        align-items: center;
    }
    .message-header-icon {
        margin-right: 0.3rem;
    }
    .intent-badge {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.7rem;
        font-weight: bold;
    }
    .intent-badge.user-badge {
        background-color: #e6f7ff;
        color: #0056b3;
        border: 1px solid #b3d7ff;
    }
    .intent-badge.concise {
        background-color: #e6f4ff;
        color: #0066cc;
        border: 1px solid #99ccff;
    }
    .intent-badge.detailed {
        background-color: #fff0e6;
        color: #cc6600;
        border: 1px solid #ffcc99;
    }
    /* Fix for code blocks not rendering properly */
    pre {
        margin-top: 1em;
        margin-bottom: 1em;
        background-color: #f6f8fa;
        border-radius: 0.3rem;
        padding: 16px;
        overflow: auto;
    }
    code {
        font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;
        font-size: 85%;
        padding: 0.2em 0.4em;
        margin: 0;
        background-color: rgba(27,31,35,0.05);
        border-radius: 3px;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        margin: 0;
        overflow: visible;
        font-size: 100%;
        word-break: normal;
        white-space: pre;
        border: 0;
    }
    
    /* Reduce corner rounding for chat input */
    .stChatInput {
        border-radius: 0.3rem !important;
    }
    .stChatInput > div {
        border-radius: 0.3rem !important;
    }
    .stChatInput input {
        border-radius: 0.3rem !important;
    }
    /* Adjust the send button styling as well */
    .stChatInput button {
        border-radius: 0.3rem !important;
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
    .chat-container {
        padding: 1rem 0;
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
    
    /* Style for buttons */
    .stButton>button {
        border-radius: 20px;
        padding: 0.3rem 1rem;
        font-size: 0.9rem;
    }

</style>
""", unsafe_allow_html=True)

# Cache cluster initialization to avoid re-processing on every rerun
@st.cache_resource
def get_clusterer():
    return init_clusters()

# Cache context fetching for queries
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_query_clusters(_clusterer, query):  # Added underscore to prevent hashing
    return query_clusters(_clusterer, query)

# Hash a message to create a cache key
def hash_message(message):
    return hashlib.md5(message.encode()).hexdigest()

# Cache response generation
@st.cache_data(ttl=3600)
def generate_agent_response(agent_type, message, model=None):
    if agent_type == "debugger":
        if model:
            st.session_state.debugger_agent.set_model(model)
        response = st.session_state.debugger_agent.get_response(message)
    elif agent_type == "concise":
        if model:
            st.session_state.concise_agent.set_model(model)
        # This will need special handling since it needs two inputs
        user_query, detailed_response = message.split("::SPLIT::")
        response = st.session_state.concise_agent.get_concise_response(
            user_query, detailed_response
        )
    return response

# Define UI sections
def render_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='main-header'><h1>🐞 CodeHelper - AI Assistant</h1></div>", unsafe_allow_html=True)

def render_chat_container():
    st.markdown("<div class='chat-container'></div>", unsafe_allow_html=True)

def render_chat_message(message, is_user=False, message_idx=None, intent_type=None):
    if is_user:
        role = "user"
        header = "👤 You"
    else:
        role = "assistant"
        header = "🤖 CodeHelper"
    
    # Add an intent badge for assistant messages if intent_type is provided
    intent_badge = f"<div></div>"
    if not is_user and intent_type is not None:
        badge_class = intent_type.lower()
        badge_text = intent_type.capitalize()
        intent_badge = f"<div class='intent-badge {badge_class}'>Intent: {badge_text}</div>"
    
    # Process message to ensure code blocks render correctly
    if not is_user:
        # Ensure proper rendering of code blocks by replacing markdown with HTML
        if message.startswith('```'):
            message = message.replace('```', '<pre><code>', 1)
            message = message.replace('```', '</code></pre>', 1)
    
    st.markdown(f"""
    <div class="chat-message {role}">
        {intent_badge}
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
    """Generate an improved response based on evaluation feedback with caching"""
    # Get the original message and its evaluation
    original_message = st.session_state.chat_history[message_idx]["content"]
    user_query = st.session_state.chat_history[message_idx-1]["content"]
    
    # Create a cache key based on the original message and user query
    cache_key = hash_message(f"{user_query}::{original_message}")
    if cache_key in st.session_state.cached_responses:
        improved_response = st.session_state.cached_responses[cache_key]
    else:
        # Get the evaluation data
        eval_idx = (message_idx - 1) // 2
        if eval_idx < len(st.session_state.evaluation_history):
            strengths = "\n".join([f"- {s}" for s in st.session_state.evaluation_history[eval_idx]["strengths"]])
            weaknesses = "\n".join([f"- {w}" for w in st.session_state.evaluation_history[eval_idx]["weaknesses"]])
            
            # Fixed formatting for improvement prompt - proper indentation and no extra whitespace
            improvement_prompt = (
                f"Please improve your previous response based on the following feedback:\n\n"
                f"USER QUERY:\n{user_query}\n\n"
                f"YOUR PREVIOUS RESPONSE:\n{original_message}\n\n"
                f"EVALUATION:\n"
                f"Strengths:\n{strengths}\n\n"
                f"Weaknesses:\n{weaknesses}\n\n"
                f"Suggestions for improvement:\n"
                f"{st.session_state.evaluation_history[eval_idx]['improvement_suggestions']}\n\n"
                f"Please provide a completely revised response that addresses the weaknesses "
                f"while maintaining the strengths."
            )
            
            with st.spinner("Generating improved response..."):
                # Get the context clusters if available
                if message_idx in st.session_state.source_clusters:
                    context_text = ""
                    for i, cluster in enumerate(st.session_state.source_clusters[message_idx]):
                        context_text += (
                            f"Source {i+1}:\n"
                            f"Title: {cluster['title']}\n"
                            f"Link: {cluster.get('link', 'N/A')}\n"
                            f"Heading: {cluster['heading']}\n"
                            f"Content: {cluster['content']}\n\n"
                        )
                    
                    improvement_prompt += f"\nCONTEXT:\n{context_text}"
                
                # Generate improved response
                improved_response = st.session_state.debugger_agent.get_response(improvement_prompt)
                
                # Cache the response
                st.session_state.cached_responses[cache_key] = improved_response
        else:
            improved_response = "Sorry, I couldn't generate an improved response. Please try asking your question again."
    
    # Store the improved response
    st.session_state.improved_responses[message_idx] = improved_response
    
    # Add the improved response to chat history as a new assistant message
    st.session_state.chat_history.append({"role": "assistant", "content": improved_response})
    
    # Clone the source clusters from the original message to the new one
    new_message_idx = len(st.session_state.chat_history) - 1
    if message_idx in st.session_state.source_clusters:
        st.session_state.source_clusters[new_message_idx] = st.session_state.source_clusters[message_idx]
    
    # Evaluate the improved response with properly formatted spinner text
    with st.spinner("Evaluating improved response..."):
        eval_data = evaluate_response(
            user_query, 
            improved_response,
            system_prompt=EVALUATOR_DEFAULT_PROMPT,
            model=st.session_state.model_params["model"]
        )
        st.session_state.evaluation_history.append(eval_data)
    
    return improved_response

def display_chat_history():
    for i, message in enumerate(st.session_state.chat_history):
        # Get the intent type for this message (if available and it's an assistant message)
        intent_type = None
        if message["role"] == "assistant":
            # Calculate the corresponding message index for intent analysis
            # Check both the current message index and the assistant message index
            if i in st.session_state.intent_analysis:
                intent_type = st.session_state.intent_analysis[i]["response_type"].lower()
        
        # Display message with intent badge if available
        render_chat_message(message["content"], message["role"] == "user", i, intent_type)
        
        # Display alternate version buttons for assistant messages
        if message["role"] == "assistant" and i in st.session_state.alternative_versions:
            # Check intent type to determine which alternative version to show
            if intent_type == "concise" and "detailed" in st.session_state.alternative_versions[i]:
                # Show "Explain in Detail" button for concise responses
                if i not in st.session_state.expanded_details:
                    # Wrap the button in a container div for centering
                    st.markdown('<div class="centered-button" style="display: flex; justify-content: center; width: 100%;">', unsafe_allow_html=True)
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        if st.button("🔍 Explain in Detail", key=f"expand_{i}", use_container_width=True):
                            st.session_state.expanded_details[i] = True
                            # Simulate processing time
                            placeholder = st.empty()
                            with placeholder.container():
                                with st.spinner("Generating detailed explanation..."):
                                    time.sleep(3.5)
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    # Show detailed version in an expander
                    with st.expander("Detailed Explanation"):
                        st.markdown(st.session_state.alternative_versions[i]["detailed"])
            
            elif intent_type == "detailed" and "concise" in st.session_state.alternative_versions[i]:
                # Show "View concise summary" button for detailed responses
                if i not in st.session_state.expanded_summary:
                    # Wrap the button in a container div for centering
                    st.markdown('<div class="centered-button" style="display: flex; justify-content: center; width: 100%;">', unsafe_allow_html=True)
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        if st.button("📝 View concise summary", key=f"concise_{i}", use_container_width=True):
                            st.session_state.expanded_summary[i] = True
                            # Simulate processing time
                            placeholder = st.empty()
                            with placeholder.container():
                                with st.spinner("Generating concise summary..."):
                                    time.sleep(2)
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    # Show concise version in an expander
                    with st.expander("Concise Summary"):
                        st.markdown(st.session_state.alternative_versions[i]["concise"])
        
        # Display feedback thank you message if present
        if i in st.session_state.feedback_messages:
            st.info(st.session_state.feedback_messages[i])
        
        # Add feedback buttons after assistant's messages
        if message["role"] == "assistant" and i not in st.session_state.feedback_given:
            # Use custom centered buttons container instead of columns
            st.markdown('<div class="centered-buttons">', unsafe_allow_html=True)
            
            _, col1, _, col2, _ = st.columns(5)
            with col1:
                if st.button("👍 Helpful", key=f"helpful_{i}"):
                    st.session_state.feedback_given[i] = "helpful"
                    st.session_state.feedback_messages[i] = "Thank you for your positive feedback! I'm glad the response was helpful."
                    st.rerun()
            with col2:
                if st.button("👎 Not Helpful", key=f"not_helpful_{i}"):
                    st.session_state.feedback_given[i] = "not_helpful"
                    st.session_state.feedback_messages[i] = "I'm sorry the response wasn't helpful. Generating an improved response..."
                    
                    # Process negative feedback to generate improved response
                    process_negative_feedback(i)
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

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
        
        # Add advanced mode toggle
        if st.checkbox("Show Advanced Options", value=st.session_state.show_advanced):
            st.session_state.show_advanced = True
            
            # Add response mode toggle (only shown in advanced mode)
            response_mode = st.radio(
                "Response Style",
                RESPONSE_MODES,
                index=RESPONSE_MODES.index(st.session_state.response_mode),
                format_func=lambda x: x.capitalize(),
                help="Auto: Smart detection based on query. Detailed: Comprehensive answers. Concise: Shorter responses."
            )
            st.session_state.response_mode = response_mode
        else:
            st.session_state.show_advanced = False
        
        # Select model
        selected_model = st.selectbox(
            "Select Model", 
            options=AVAILABLE_MODELS,
            index=AVAILABLE_MODELS.index(st.session_state.model_params["model"]) if st.session_state.model_params["model"] in AVAILABLE_MODELS else 0,
            disabled=disabled
        )
        
        # Show system prompt in advanced mode only
        if st.session_state.show_advanced:
            system_prompt = st.text_area(
                "System Prompt", 
                value=st.session_state.model_params["system_prompt"],
                height=300,
                disabled=disabled
            )
        else:
            system_prompt = st.session_state.model_params["system_prompt"]
        
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
            st.session_state.response_mode = "auto"
            
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
        
        # Create a progress bar for better UX during processing
        progress_bar = st.progress(0)

        # Get clusters for the user message
        with st.spinner("Finding relevant clusters..."):
            # Use cached clustering function with underscore parameter
            clusters = get_query_clusters(clusterer, user_message)
            progress_bar.progress(20)
            
            # Store the clusters for displaying as sources
            assistant_message_idx = user_message_idx + 1
            st.session_state.source_clusters[assistant_message_idx] = clusters
            
            # Format clusters for context
            context_text = ""
            for i, cluster in enumerate(clusters):
                context_text += f"Source {i+1}:\nTitle: {cluster['title']}\nLink: {cluster.get('link', 'N/A')}\nHeading: {cluster['heading']}\nContent: {cluster['content']}\n\n"
            
            # Add context to user message
            user_message_with_context = f"USER: {user_message}\n\nCONTEXT: {context_text}"
        
        progress_bar.progress(30)
        
        # Create a cache key for this message
        cache_key = hash_message(user_message_with_context)
        
        # Determine if we should analyze intent
        should_analyze_intent = st.session_state.response_mode == "auto"
        
        if should_analyze_intent:
            with st.spinner("Analyzing query intent..."):
                intent_result = st.session_state.intent_agent.determine_response_type(user_message)
                st.session_state.intent_analysis[assistant_message_idx] = intent_result
                # Determine which response type to show based on intent analysis
                response_type = intent_result["response_type"].lower()
                progress_bar.progress(40)
        else:
            response_type = st.session_state.response_mode
        
        # Generate both concise and detailed responses for caching and display
        with st.spinner("Generating responses..."):
            # Generate detailed response
            detailed_cache_key = hash_message(f"{user_message_with_context}::DETAILED")
            if detailed_cache_key in st.session_state.cached_responses:
                detailed_response = st.session_state.cached_responses[detailed_cache_key]
            else:
                # Generate detailed response
                detailed_response = st.session_state.debugger_agent.get_response(user_message_with_context)
                st.session_state.cached_responses[detailed_cache_key] = detailed_response
            
            progress_bar.progress(60)
            
            # Generate concise response
            concise_cache_key = hash_message(f"{user_message_with_context}::CONCISE")
            if concise_cache_key in st.session_state.cached_responses:
                concise_response = st.session_state.cached_responses[concise_cache_key]
            else:
                # Process through concise agent
                concise_response = st.session_state.concise_agent.get_concise_response(
                    user_message, 
                    detailed_response
                )
                st.session_state.cached_responses[concise_cache_key] = concise_response
                
            progress_bar.progress(80)
            
            # Store both versions
            st.session_state.alternative_versions[assistant_message_idx] = {
                "detailed": detailed_response,
                "concise": concise_response
            }
            
            # Choose which one to display based on response_type
            if response_type == "concise":
                final_response = concise_response
            else:  # detailed or any other value
                final_response = detailed_response
            
            # Store the intent analysis for this assistant message using the assistant_message_idx
            if should_analyze_intent:
                st.session_state.intent_analysis[assistant_message_idx] = intent_result
            elif st.session_state.response_mode == "concise":
                # If manually set to concise, create a dummy intent result
                st.session_state.intent_analysis[assistant_message_idx] = {
                    "response_type": "CONCISE",
                    "confidence": 1.0,
                    "reasoning": "User manually selected concise mode"
                }
            else:
                # If manually set to detailed, create a dummy intent result
                st.session_state.intent_analysis[assistant_message_idx] = {
                    "response_type": "DETAILED",
                    "confidence": 1.0,
                    "reasoning": "User manually selected detailed mode"
                }
            
            # Add final response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": final_response})
            
            # Evaluate the response
            eval_data = evaluate_response(
                user_message_with_context, 
                final_response,
                system_prompt=EVALUATOR_DEFAULT_PROMPT,
                model=st.session_state.model_params["model"]
            )
            
            st.session_state.evaluation_history.append(eval_data)
            
        progress_bar.progress(100)
        
        # Use container update with properly formatted success message
        placeholder = st.empty()
        with placeholder.container():
            st.success("Response generated successfully!")
            time.sleep(0.5)
        
        # Still need rerun to update the chat history display
        st.rerun()

def main():
    render_header()
    
    # Get cached clusterer
    clusterer = get_clusterer()
    
    # Create three columns - main chat and two sidebars
    left_sidebar, main_col, right_sidebar = st.columns([1, 3, 1])
    
    with main_col:
        render_chat_container()  # Replace the debug session header with a simple container
        display_chat_history()
        handle_user_input(clusterer)
    
    # Left sidebar for evaluations
    with left_sidebar:
        render_evaluation_sidebar()
        
        # Show intent analysis results always, not just in advanced mode
        if st.session_state.intent_analysis:
            st.sidebar.markdown("<h3 class='sidebar-header'>Intent Analysis</h3>", unsafe_allow_html=True)
            for idx, intent in st.session_state.intent_analysis.items():
                with st.sidebar.expander(f"Message #{idx//2 + 1} Intent"):
                    st.write(f"**Response Type:** {intent['response_type']}")
                    st.write(f"**Confidence:** {intent['confidence']:.2f}")
                    st.write(f"**Reasoning:** {intent['reasoning']}")
    
    # Right sidebar for model parameters
    with right_sidebar:
        render_model_params_sidebar()

if __name__ == "__main__":
    main()