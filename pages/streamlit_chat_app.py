import streamlit as st
import os
from dotenv import load_dotenv
import time
import os.path
from agents.debugger_agent import DebuggerAgent, DEFAULT_SYSTEM_PROMPT as DEBUGGER_DEFAULT_PROMPT
from agents.evaluator_agent import evaluate_response, DEFAULT_SYSTEM_PROMPT as EVALUATOR_DEFAULT_PROMPT
from agents.concise_agent import ConciseAgent, DEFAULT_SYSTEM_PROMPT as CONCISE_DEFAULT_PROMPT
from agents.intent_agent import IntentAgent, DEFAULT_SYSTEM_PROMPT as INTENT_DEFAULT_PROMPT
from clustering import init_clusters, query_clusters
import hashlib
from query_images import ImageSearchEngine
from utils.rrr import get_similar_queries
from utils.hayd import hyde

# Load environment variables
load_dotenv()

# Authentication check - redirect to login if not authenticated
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    st.info("Redirecting to login page...")
    time.sleep(1)
    st.switch_page("../Landing.py")
    st.stop()

# Set page configuration
st.set_page_config(
    page_title="MATBot - MATLAB AI Assistant",
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

# File path for self memory storage
SELF_MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "self_memory.json")

# print('Debugging: self_memory_file:', SELF_MEMORY_FILE)

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
    st.session_state.rag_params = {
        "n_clusters": 30,
        "num_closest_clusters": 5,
        "top_y": 5,
        "top_k_self": 3,
        "use_self_memory": True,
        "memory_threshold": 0.85  # Threshold for adding to self memory
    }
    st.session_state.image_search_params = {
        "top_k": 3,
        "embeddings_file": "images_log.json"
    }
    st.session_state.hyde_params = {
        "use_hyde": True  # Default to use HyDE
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
    st.session_state.retrieved_context = None
    st.session_state.last_evaluation = None
    st.session_state.show_images = {}  # Track which messages have images displayed
    st.session_state.image_search_engine = None  # Will initialize when needed
    st.session_state.query_alternatives = {}  # Store query alternatives
    st.session_state.query_selection = None   # Store selected query
    st.session_state.query_improvement = None  # Store improved query
    st.session_state.at_query_selection = False  # Flag to show alternatives
    st.session_state.at_query_improvement = False  # Flag to show improved query
    st.session_state.source_memory = {}  # Track which responses came from self-memory
    st.session_state.memory_added = {}  # Track which responses were added to self-memory

# Custom CSS - adding styles for self-memory indicators
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
    
    /* Style for image gallery */
    .image-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px;
        margin-top: 10px;
    }
    
    .image-card {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 5px;
        background-color: white;
    }
    
    .image-card img {
        width: 100%;
        border-radius: 3px;
    }
    
    .image-heading {
        font-size: 0.8rem;
        color: #555;
        margin-top: 5px;
        font-style: italic;
    }
    
    .image-score {
        font-size: 0.8rem;
        color: #0066cc;
        font-weight: bold;
    }
    
    /* Self-memory source indicator */
    .self-memory-indicator {
        background-color: #e6f7ff;
        color: #0066cc;
        padding: 0.3rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        border: 1px solid #99ccff;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    /* Memory added indicator */
    .memory-added-indicator {
        background-color: #f0fff0;
        color: #008800;
        padding: 0.3rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        border: 1px solid #ccffcc;
        display: inline-block;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Cache cluster initialization to avoid re-processing on every rerun
@st.cache_resource
def get_clusterer(n_clusters=30, num_closest_clusters=5, memory_file=None):
    """Initialize and cache the RAGClusterer with optional self-memory loading"""
    print(f"Initializing clusterer with memory_file={memory_file}")
    clusterer = init_clusters(
        n_clusters=n_clusters, 
        num_closest_clusters=num_closest_clusters,
        memory_file=memory_file
    )
    return clusterer

# Cache context fetching for queries
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_query_clusters(_clusterer, query, top_y=5, top_k_self=3, use_self_memory=True):
    """Get query results from clusterer with self-memory support"""
    return query_clusters(
        _clusterer, 
        query, 
        top_y=top_y, 
        top_k_self=top_k_self, 
        use_self_memory=use_self_memory
    )

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

# Initialize image search engine
@st.cache_resource
def get_image_search_engine(embeddings_file="images_log.json"):
    """Initialize and cache the image search engine"""
    try:
        search_engine = ImageSearchEngine(embeddings_file)
        return search_engine
    except Exception as e:
        st.error(f"Error initializing image search engine: {e}")
        return None

# Function to search for images related to a query
def search_related_images(query, top_k=3):
    """Search for images related to the given query"""
    if st.session_state.image_search_engine is None:
        embeddings_file = st.session_state.image_search_params["embeddings_file"]
        st.session_state.image_search_engine = get_image_search_engine(embeddings_file)
    
    if st.session_state.image_search_engine:
        return st.session_state.image_search_engine.search(query, top_k)
    return []

# Define UI sections
def render_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='main-header'><h1>🐞 MATBot - MATLAB AI Assistant</h1></div>", unsafe_allow_html=True)

def render_chat_container():
    st.markdown("<div class='chat-container'></div>", unsafe_allow_html=True)

def render_chat_message(message, is_user=False, message_idx=None, intent_type=None):
    if is_user:
        role = "user"
        header = "👤 You"
    else:
        role = "assistant"
        header = "🤖 MATBot"
    
    # Add an intent badge for assistant messages if intent_type is provided
    intent_badge = f"<div></div>"
    if not is_user and intent_type is not None:
        badge_class = intent_type.lower()
        badge_text = intent_type.capitalize()
        intent_badge = f"<div class='intent-badge {badge_class}'>Intent: {badge_text}</div>"
    
    # Add self-memory indicator if applicable
    memory_badge = "<div></div>"
    if not is_user and message_idx in st.session_state.source_memory:
        memory_source = st.session_state.source_memory[message_idx]
        if memory_source == "self_memory":
            memory_badge = "<div class='self-memory-indicator'>🧠 From Self Memory</div>"
    
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
        {memory_badge}
        <div class="message-content">{message}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show memory added indicator if applicable
    if not is_user and message_idx in st.session_state.memory_added and st.session_state.memory_added[message_idx]:
        st.markdown("<div class='memory-added-indicator'>✅ Added to Self Memory</div>", unsafe_allow_html=True)
    
    # Show sources for assistant messages
    if not is_user and message_idx is not None and message_idx in st.session_state.source_clusters:
        sources = st.session_state.source_clusters[message_idx]
        if sources:
            # Check if this is a self-memory source
            if len(sources) == 1 and sources[0].get('source') == 'self_memory':
                with st.expander("Show original query from memory"):
                    st.markdown(f"**Original Query:** {sources[0].get('original_query', 'Unknown')}")
            else:
                with st.expander("Show sources used for this response"):
                    for i, source in enumerate(sources):
                        if source.get('source') != 'self_memory':
                            st.markdown(f"**Source {i+1}: {source['title'].strip()}**")
                            st.markdown(f"*{source['heading']}*")
                            st.markdown(source['content'])
                            if 'link' in source:
                                st.markdown(f"[View original document]({source['link']})")
                            st.divider()

def display_image_results(query, message_idx):
    """Display images related to the user query"""
    # Get the top_k from session state
    top_k = st.session_state.image_search_params["top_k"]
    
    # Search for related images
    with st.spinner("Finding related images..."):
        images = search_related_images(query, top_k)
    
    if not images:
        st.info("No relevant images found for this query.")
        return
    
    st.subheader("Related Images")
    
    # Display images in a grid
    cols = st.columns(min(3, len(images)))
    for i, image in enumerate(images):
        with cols[i % len(cols)]:
            st.image(image["url"], caption=f"Score: {image['score']:.3f}", use_container_width=True)
            if image["heading"]:
                st.caption(f"Context: {image['heading']}")
            
            # Add a link to the image
            st.markdown(f"[Open Image]({image['url']})")

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
        
        # Add "View related images" button for assistant messages
        if message["role"] == "assistant" and i > 0:  # Make sure there's a user message before this
            user_query = st.session_state.chat_history[i-1]["content"]
            
            # Show the button if images aren't already displayed
            if i not in st.session_state.show_images:
                # Wrap the button in a container div for centering
                st.markdown('<div class="centered-button" style="display: flex; justify-content: center; width: 100%;">', unsafe_allow_html=True)
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🖼️ View related images", key=f"images_{i}", use_container_width=True):
                        st.session_state.show_images[i] = True
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                # Display images related to the user query
                display_image_results(user_query, i)
        
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

# Function to get color based on score value
def get_score_color(score):
    """Return a color based on the score value"""
    if score >= 0.8:
        return "#00CC66"  # Green for high scores
    elif score >= 0.6:
        return "#CCCC00"  # Yellow for medium scores
    else:
        return "#FF6666"  # Red for low scores

def render_evaluation_sidebar():
    """Display all evaluation results in the sidebar with Ragas metrics"""
    st.sidebar.markdown("<h3 class='sidebar-header'>Response Evaluations</h3>", unsafe_allow_html=True)
    
    if not st.session_state.evaluation_history:
        st.sidebar.info("No evaluations yet. Send a message to get started.")
        return
    
    for i, eval_data in enumerate(st.session_state.evaluation_history):
        with st.sidebar.expander(f"Evaluation #{i+1} (Score: {eval_data.get('score', 0.5):.2f})", expanded=(i == len(st.session_state.evaluation_history) - 1)):
            # Quality score with color
            score = eval_data.get("score", 0.5)
            score_color = get_score_color(score)
            st.markdown(f"<h3 style='color: {score_color}'>Quality Score: {score:.2f}</h3>", unsafe_allow_html=True)
            
            # Ragas metrics if available
            if "ragas_metrics" in eval_data:
                st.markdown("### Ragas Metrics")
                ragas = eval_data["ragas_metrics"]
                
                # Faithfulness (accuracy)
                faith_color = get_score_color(ragas["faithfulness"])
                st.markdown(f"<p>Faithfulness: <span style='color: {faith_color}'>{ragas['faithfulness']:.3f}</span></p>", 
                            unsafe_allow_html=True)
                
                # Answer relevance
                ans_color = get_score_color(ragas["answer_relevance"])
                st.markdown(f"<p>Answer Relevance: <span style='color: {ans_color}'>{ragas['answer_relevance']:.3f}</span></p>", 
                            unsafe_allow_html=True)
                
                # Context relevance
                ctx_color = get_score_color(ragas["context_relevance"])
                st.markdown(f"<p>Context Relevance: <span style='color: {ctx_color}'>{ragas['context_relevance']:.3f}</span></p>", 
                            unsafe_allow_html=True)
            
            # Strengths
            if "strengths" in eval_data and eval_data["strengths"]:
                st.markdown("### Strengths")
                for strength in eval_data["strengths"]:
                    st.markdown(f"- {strength}")
            
            # Weaknesses
            if "weaknesses" in eval_data and eval_data["weaknesses"]:
                st.markdown("### Weaknesses")
                for weakness in eval_data["weaknesses"]:
                    st.markdown(f"- {weakness}")
            
            # Improvement suggestions
            if "improvement_suggestions" in eval_data:
                st.markdown("### Improvement Suggestions")
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
            
            # Add HyDE toggle
            use_hyde = st.checkbox(
                "Use HyDE Query Expansion", 
                value=st.session_state.hyde_params.get("use_hyde", True),
                help="Enable Hypothetical Document Embeddings to expand and improve queries"
            )
            # Update HyDE parameter in session state
            st.session_state.hyde_params["use_hyde"] = use_hyde
            
            # Add self-memory parameters
            st.sidebar.markdown("<h4 class='sidebar-header'>Self Memory Parameters</h4>", unsafe_allow_html=True)
            
            use_self_memory = st.checkbox(
                "Use Self Memory", 
                value=st.session_state.rag_params.get("use_self_memory", True),
                help="Enable self-memory to remember and use previous interactions"
            )
            
            memory_threshold = st.slider(
                "Memory Quality Threshold", 
                min_value=0.5, 
                max_value=1.0, 
                value=st.session_state.rag_params.get("memory_threshold", 0.85),
                step=0.05,
                help="Minimum quality score required to add responses to self-memory",
                disabled=not use_self_memory
            )
            
            top_k_self = st.slider(
                "Self Memory Results", 
                min_value=1, 
                max_value=10, 
                value=st.session_state.rag_params.get("top_k_self", 3),
                step=1,
                help="Number of self-memory entries to check during retrieval",
                disabled=not use_self_memory
            )
            
            # Update self-memory parameters in session state
            st.session_state.rag_params["use_self_memory"] = use_self_memory
            st.session_state.rag_params["memory_threshold"] = memory_threshold
            st.session_state.rag_params["top_k_self"] = top_k_self
            
            # Add image search parameters
            st.sidebar.markdown("<h4 class='sidebar-header'>Image Search Parameters</h4>", unsafe_allow_html=True)
            
            top_k = st.slider(
                "Number of Images to Display", 
                min_value=1, 
                max_value=10, 
                value=st.session_state.image_search_params["top_k"],
                step=1,
                help="Number of related images to display for each query."
            )
            
            # Update image search parameters in session state
            st.session_state.image_search_params["top_k"] = top_k
            
            # Add RAG Parameters section in advanced mode
            st.sidebar.markdown("<h4 class='sidebar-header'>RAG Parameters</h4>", unsafe_allow_html=True)
            
            n_clusters = st.slider(
                "Number of Clusters", 
                min_value=10, 
                max_value=50, 
                value=st.session_state.rag_params["n_clusters"],
                step=5,
                help="Number of clusters for document organization. Higher values create more specific clusters.",
                disabled=disabled
            )
            
            num_closest_clusters = st.slider(
                "Closest Clusters to Retrieve", 
                min_value=1, 
                max_value=10, 
                value=st.session_state.rag_params["num_closest_clusters"],
                step=1,
                help="Number of closest topic clusters to search for context. Higher values retrieve more diverse information.",
                disabled=disabled
            )
            
            top_y = st.slider(
                "Top Documents per Cluster", 
                min_value=1, 
                max_value=10, 
                value=st.session_state.rag_params["top_y"],
                step=1,
                help="Number of most relevant documents to retrieve from each cluster. Higher values provide more context.",
                disabled=disabled
            )
            
            # Update RAG parameters in session state
            st.session_state.rag_params["n_clusters"] = n_clusters
            st.session_state.rag_params["num_closest_clusters"] = num_closest_clusters
            st.session_state.rag_params["top_y"] = top_y
            
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
            
            # Clear the cache for the clusterer to apply new RAG parameters
            if st.session_state.show_advanced:
                st.cache_resource.clear()
            
            st.success("Parameters set successfully!")
            st.rerun()
        
        if st.button("Reset to Default", disabled=disabled):
            st.session_state.model_params["model"] = AVAILABLE_MODELS[0]
            st.session_state.model_params["system_prompt"] = DEBUGGER_DEFAULT_PROMPT
            st.session_state.response_mode = "auto"
            st.session_state.rag_params = {
                "n_clusters": 30,
                "num_closest_clusters": 5,
                "top_y": 5,
                "top_k_self": 3,
                "use_self_memory": True,
                "memory_threshold": 0.85
            }
            st.session_state.image_search_params = {
                "top_k": 3
            }
            st.session_state.hyde_params = {
                "use_hyde": True
            }
            
            # Create a new debugger agent with default parameters
            st.session_state.debugger_agent = DebuggerAgent()
            
            # Clear the cache for the clusterer
            st.cache_resource.clear()
            
            st.success("Parameters reset to default!")
            st.rerun()

def handle_user_input(clusterer):
    user_message = st.chat_input("Ask your code question here...")
    
    if user_message and not st.session_state.at_query_selection and not st.session_state.at_query_improvement:
        # Step 1: Generate query alternatives using RRR
        with st.spinner("Generating query alternatives..."):
            alternatives = get_similar_queries(user_message)
            # Store the original and alternative queries
            st.session_state.query_alternatives = {
                "original": user_message,
                "alternatives": alternatives
            }
            # Set flag to show alternatives
            st.session_state.at_query_selection = True
            st.rerun()
            
    # Step 2: Show query alternatives and let the user select one
    if st.session_state.at_query_selection:
        st.subheader("Did you mean...?")
        st.info("Please select the query that best matches your intention:")
        
        # Display the original query as an option
        col_orig = st.columns(1)[0]
        with col_orig:
            st.markdown("**Original Query:**")
            if st.button(f"🔵 {st.session_state.query_alternatives['original']}", key="orig_query", use_container_width=True):
                st.session_state.query_selection = st.session_state.query_alternatives['original']
                st.session_state.at_query_selection = False
                
                # Only go to query improvement if HyDE is enabled
                if st.session_state.hyde_params.get("use_hyde", True):
                    st.session_state.at_query_improvement = True
                else:
                    # Skip HyDE and process the query directly
                    selected_query = st.session_state.query_alternatives['original']
                    # Add the original query to chat history
                    st.session_state.chat_history.append({
                        "role": "user", 
                        "content": selected_query
                    })
                    # Process with the original query
                    process_query(clusterer, selected_query, selected_query)
                st.rerun()
        
        # Display alternatives in columns
        st.markdown("**Alternative Queries:**")
        # Create columns for alternatives
        cols = st.columns(len(st.session_state.query_alternatives['alternatives']))
        
        # Display each alternative in its own column
        for i, (col, alt) in enumerate(zip(cols, st.session_state.query_alternatives['alternatives'])):
            with col:
                if st.button(f"🟢 {alt}", key=f"alt_{i}", use_container_width=True):
                    st.session_state.query_selection = alt
                    st.session_state.at_query_selection = False
                    
                    # Only go to query improvement if HyDE is enabled
                    if st.session_state.hyde_params.get("use_hyde", True):
                        st.session_state.at_query_improvement = True
                    else:
                        # Skip HyDE and process the query directly
                        selected_query = alt
                        # Add the selected query to chat history
                        st.session_state.chat_history.append({
                            "role": "user", 
                            "content": selected_query
                        })
                        # Process with the selected query
                        process_query(clusterer, selected_query, selected_query)
                    st.rerun()
    
    # Step 3: Improve the selected query with HAYD and process
    if st.session_state.at_query_improvement:
        # Use the selected query 
        selected_query = st.session_state.query_selection
        
        with st.spinner("Improving query..."):
            # Use HAYD to improve the query
            hyde_result = hyde(selected_query)
            improved_query = hyde_result['expanded_query']
            
            # Store the original and improved queries to display
            st.session_state.query_improvement = {
                "original": selected_query,
                "improved": improved_query
            }
            
            # Display the improvement
            st.info(f"""
            **Original Query:** {selected_query}
            
            **Improved Query:** {improved_query}
            """)
            
            # Add the original query to chat history (what the user actually asked)
            st.session_state.chat_history.append({
                "role": "user", 
                "content": selected_query
            })
            
            # Process the improved query
            process_query(clusterer, selected_query, improved_query)
            
            # Reset the query selection flags
            st.session_state.at_query_selection = False  
            st.session_state.at_query_improvement = False
            
            st.rerun()

# Extract the query processing code into a separate function
def process_query(clusterer, original_query, processed_query):
    """Process a query with the RAG system and generate a response"""
    # Mark chat as started
    st.session_state.chat_started = True
    
    # Create a progress bar for better UX during processing
    progress_bar = st.progress(0)

    # Get clusters for the user message using parameters from session state
    with st.spinner("Fetching relevant documentation..."):
        # Show "Fetching docs" message for a short time
        time.sleep(1)
        
        # Use cached clustering function with parameters from session state including self-memory
        clusters = get_query_clusters(
            clusterer, 
            processed_query, 
            top_y=st.session_state.rag_params["top_y"],
            top_k_self=st.session_state.rag_params["top_k_self"],
            use_self_memory=st.session_state.rag_params["use_self_memory"]
        )
        progress_bar.progress(20)
        
        # Store the clusters for displaying as sources
        user_message_idx = len(st.session_state.chat_history) - 1
        assistant_message_idx = user_message_idx + 1
        st.session_state.source_clusters[assistant_message_idx] = clusters
        
        # Check if any of the clusters is from self-memory
        if any(cluster.get('source') == 'self_memory' for cluster in clusters):
            # Mark this message as coming from self-memory
            st.session_state.source_memory[assistant_message_idx] = "self_memory"
        
        # Format clusters for context
        context_text = ""
        for i, cluster in enumerate(clusters):
            source_type = cluster.get('source', 'clustered_db')
            if source_type == 'self_memory':
                context_text += f"Source {i+1} (Self Memory):\nPrevious Query: {cluster.get('original_query', 'Unknown')}\nContent: {cluster['content']}\n\n"
            else:
                context_text += f"Source {i+1}:\nTitle: {cluster['title']}\nLink: {cluster.get('link', 'N/A')}\nHeading: {cluster['heading']}\nContent: {cluster['content']}\n\n"
            
        # Add context to user message
        user_message_with_context = f"USER: {processed_query}\n\nCONTEXT: {context_text}"
        st.session_state.retrieved_context = context_text
        
        progress_bar.progress(30)
        
        # Create a cache key for this message
        cache_key = hash_message(user_message_with_context)
        
        # Determine if we should analyze intent
        should_analyze_intent = st.session_state.response_mode == "auto"
        
        # Rest of the existing processing code remains the same
        if should_analyze_intent:
            with st.spinner("Analyzing query intent..."):
                intent_result = st.session_state.intent_agent.determine_response_type(processed_query)
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
                    processed_query, 
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
            
            # Add response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": final_response})
            
            # Evaluate the response
            eval_data = evaluate_response(
                user_message_with_context, 
                final_response,
                system_prompt=EVALUATOR_DEFAULT_PROMPT,
                model=st.session_state.model_params["model"],
                context=st.session_state.retrieved_context
            )
            
            st.session_state.last_evaluation = eval_data
            st.session_state.evaluation_history.append(eval_data)
            
            # Add to self-memory if quality is above threshold
            if st.session_state.rag_params["use_self_memory"]:
                quality_score = eval_data.get('score', 0)
                memory_threshold = st.session_state.rag_params["memory_threshold"]
                
                # Debug statement for self-memory
                print(f"Quality score: {quality_score}, Memory threshold: {memory_threshold}")
                
                # Check if response quality is high enough for self-memory
                if quality_score >= memory_threshold:
                    print(f"Adding to self-memory: {original_query}")
                    memory_added = clusterer.add_to_self_memory(
                        query=original_query,  # Use the original query, not the processed one
                        context=context_text,
                        output=final_response,
                        score=quality_score
                    )
                    
                    # Mark this message as added to self-memory
                    st.session_state.memory_added[assistant_message_idx] = memory_added
                    
                    # Save updated self-memory to file
                    if memory_added:
                        try:
                            # Create parent directory if it doesn't exist
                            os.makedirs(os.path.dirname(SELF_MEMORY_FILE), exist_ok=True)
                            
                            # Debug statement for saving self-memory
                            print(f"Saving self-memory to: {SELF_MEMORY_FILE}")
                            success = clusterer.save_self_memory(SELF_MEMORY_FILE)
                            print(f"Save result: {success}")
                        except Exception as e:
                            print(f"Error saving self-memory: {e}")
                            st.error(f"Error saving self-memory: {e}")
            
            progress_bar.progress(100)
            
            # Use container update with properly formatted success message
            placeholder = st.empty()
            with placeholder.container():
                st.success("Response generated successfully!")
                time.sleep(0.5)

def main():
    render_header()
    
    # Get cached clusterer with RAG parameters from session state and self-memory file
    clusterer = get_clusterer(
        n_clusters=st.session_state.rag_params["n_clusters"],
        num_closest_clusters=st.session_state.rag_params["num_closest_clusters"],
        memory_file=SELF_MEMORY_FILE  # Add self-memory file path
    )
    
    # Initialize image search engine if needed
    if st.session_state.image_search_engine is None:
        embeddings_file = st.session_state.image_search_params["embeddings_file"]
        st.session_state.image_search_engine = get_image_search_engine(embeddings_file)
    
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