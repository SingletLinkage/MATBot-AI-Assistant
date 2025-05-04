import streamlit as st
import sqlalchemy
import time

# ——— CONFIG ——————————————
st.set_page_config(
    page_title="MATBot Login", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling - Dark Mode Theme
st.markdown("""
<style>
    /* Main theme colors and styling - Dark Mode */
    :root {
        --primary-color: #3A7CA5;
        --secondary-color: #2C3E50;
        --accent-color: #F39C12;
        --text-color: #E0E0E0;
        --bg-color: #1A1A2E;
        --card-bg: #16213E;
    }
    
    /* Background and base styling */
    .stApp {
        background-color: var(--bg-color);
        color: var(--text-color);
    }
    
    /* Card styling for forms */
    .card {
        background-color: var(--card-bg);
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        margin-bottom: 1rem;
        transition: transform 0.3s, box-shadow 0.3s;
        color: var(--text-color);
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.25);
    }
    
    /* Buttons styling */
    .stButton > button {
        border-radius: 10px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s;
        border: none;
        background-color: #f39c12; /* Bronze/gold button */
        color: #000000; /* Black text for contrast */
    }
    .stButton > button:hover {
        background-color: #e67e22;
        transform: scale(1.05);
        color: #ffffff; /* White text on hover */
    }
    
    /* Form inputs styling */
    input[type="text"], input[type="password"] {
        border-radius: 5px;
        border: 1px solid #444;
        padding: 10px;
        transition: all 0.3s;
        background-color: #121212;
        color: var(--text-color);
    }
    input[type="text"]:focus, input[type="password"]:focus {
        border-color: var(--accent-color);
        box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2);
    }
    
    /* Headers and text */
    h1, h2, h3 {
        color: #D4AF37; /* Bronze/gold headers */
        font-weight: 700;
    }
    
    /* Logo and branding */
    .logo-text {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #000000, #D4AF37, #000000);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0;
    }
    
    .logo-subtitle {
        font-size: 1.2rem;
        color: var(--text-color);
        text-align: center;
        margin-top: 0;
        opacity: 0.8;
    }
    
    /* Center image container */
    .center-image {
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 1rem 0;
    }
    
    /* Animation for success message */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    .success-msg {
        animation: fadeInUp 0.5s ease-out;
    }
    
    /* Form labels */
    label {
        font-weight: 500;
        color: var(--text-color);
    }
    
    /* Back button styling */
    .back-btn {
        color: var(--text-color);
        font-size: 0.9rem;
        text-align: center;
        opacity: 0.7;
        margin-top: 1rem;
    }
    .back-btn:hover {
        opacity: 1;
    }
    
    /* Expander customization */
    .streamlit-expanderHeader {
        color: var(--accent-color);
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: var(--accent-color);
    }
    
    /* Badge styling for admin */
    .admin-badge {
        background-color: #F39C12;
        color: #000;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-left: 8px;
    }
            
</style>
""", unsafe_allow_html=True)

# Lazy‐init session state for page routing and authentication
if "page" not in st.session_state:
    st.session_state.page = "home"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_info = None
    st.session_state.user_role = None

def go(page):
    st.session_state.page = page

# Initialize DB engine once
@st.cache_resource
def get_engine():
    # hard-coded NeonDB URL
    url = "postgresql://test_owner:Vdk6Z9MXuqTO@ep-little-bird-a1iyap0y-pooler.ap-southeast-1.aws.neon.tech/test?sslmode=require"
    return sqlalchemy.create_engine(url)

engine = get_engine()

# Ensure users table exists with role column
with engine.begin() as conn:
    conn.execute(
        sqlalchemy.text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
        """)
    )

# If user is already authenticated, redirect to the appropriate page
if st.session_state.authenticated:
    try:
        # Redirect based on user role
        if st.session_state.user_role == "admin":
            st.switch_page("./pages/AdminPage.py")
        else:
            # Regular users go to chat app
            st.switch_page("./pages/streamlit_chat_app.py")
    except Exception as e:
        st.error(f"Error redirecting to application: {str(e)}")
        # Reset auth state on error
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.session_state.user_role = None

# Page layout with columns for centering content
_, center_col, _ = st.columns([1, 2, 1])

with center_col:
    # ——— COMMON HEADER ——————————————
    # Enhanced application header
    st.markdown('''
        <div style="text-align: center; padding: 20px 0;">
            <h1 class="logo-text" style="font-size: 4.5rem; margin-bottom: 5px; 
                background: linear-gradient(90deg, #4E9FDE 0%, #FF8C00 50%, #4E9FDE 100%); 
                background-size: 200% auto; animation: gradient 3s ease infinite; 
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;">MATBot</h1>
            <p class="logo-subtitle" style="font-size: 1.5rem; letter-spacing: 1px; 
                margin-top: 0; text-transform: uppercase; font-weight: 300; 
                text-shadow: 0px 2px 4px rgba(0,0,0,0.5);">
                Your MATLAB Intelligent AI Assistant
            </p>
        </div>
        <style>
            @keyframes gradient {
                0% {background-position: 0% 50%;}
                50% {background-position: 100% 50%;}
                100% {background-position: 0% 50%;}
            }
        </style>
    ''', unsafe_allow_html=True)
    
    # Logo/illustration - centered with a properly themed image for MATLAB assistant
    # Create 4 columns and use the middle 2 for the image
    img_col1, img_col2, img_col3 = st.columns(3)
    
    # Use the middle two columns for the image
    with img_col2:
        st.image("https://img.freepik.com/free-vector/chat-bot-concept-illustration_114360-5412.jpg", width=500)

    # ——— HOME SCREEN ——————————————
    if st.session_state.page == "home":
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Welcome</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Your MATLAB AI troubleshooting Assistant is ready to help</p>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.button("✨ Create Account", on_click=lambda: go("signup"), use_container_width=True)
        with col2:
            st.button("🔑 Login", on_click=lambda: go("login"), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Additional information
        with st.expander("About MATBot"):
            st.write("""
            MATBot is an intelligent AI assistant designed to help with MATLAB programming, 
            data analysis, and scientific computing. Create an account to get personalized 
            assistance with coding, debugging, and algorithm development.
            """)
    
    # ——— SIGN UP ——————————————————
    elif st.session_state.page == "signup":
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Create Your Account</h2>", unsafe_allow_html=True)
        
        with st.form("signup_form", clear_on_submit=True):
            st.markdown("<label>Username</label>", unsafe_allow_html=True)
            usr = st.text_input("", placeholder="Choose a username", label_visibility="collapsed")
            
            st.markdown("<label>Password</label>", unsafe_allow_html=True)
            pwd = st.text_input("", type="password", placeholder="Create a secure password", label_visibility="collapsed")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submitted = st.form_submit_button("Sign Up", use_container_width=True)
        
        if submitted:
            if not usr or not pwd:
                st.error("👆 Both username and password are required.")
            else:
                try:
                    with st.spinner("Creating your account..."):
                        time.sleep(0.5)  # Small delay for better UX
                        with engine.begin() as conn:
                            conn.execute(
                                sqlalchemy.text(
                                    "INSERT INTO users (username, password, role) VALUES (:u, :p, 'user')"
                                ),
                                {"u": usr, "p": pwd},
                            )
                    st.markdown('<div class="success-msg">', unsafe_allow_html=True)
                    st.success("✅ Account created successfully!")
                    st.markdown('</div>', unsafe_allow_html=True)
                    time.sleep(1)
                    go("login")
                except sqlalchemy.exc.IntegrityError:
                    st.error("🔄 That username is already taken. Please try another.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="back-btn">', unsafe_allow_html=True)
        st.button("← Back to Home", on_click=lambda: go("home"))
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ——— LOGIN ——————————————————
    elif st.session_state.page == "login":
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Welcome Back</h2>", unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=True):
            st.markdown("<label>Username</label>", unsafe_allow_html=True)
            usr = st.text_input("", placeholder="Enter your username", label_visibility="collapsed")
            
            st.markdown("<label>Password</label>", unsafe_allow_html=True)
            pwd = st.text_input("", type="password", placeholder="Enter your password", label_visibility="collapsed")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submitted = st.form_submit_button("Login", use_container_width=True)
        
        if submitted:
            if not usr or not pwd:
                st.error("👆 Both username and password are required.")
            else:
                with st.spinner("Verifying your credentials..."):
                    time.sleep(0.8)  # Small delay for better UX
                    with engine.connect() as conn:
                        result = conn.execute(
                            sqlalchemy.text(
                                "SELECT id, password, role FROM users WHERE username = :u"
                            ),
                            {"u": usr},
                        ).fetchone()
                    
                    if result and result[1] == pwd:
                        # Get role from database (default to 'user' if None)
                        user_role = result[2] if result[2] else 'user'
                        
                        # Display appropriate welcome message with role badge for admins
                        if user_role == 'admin':
                            st.markdown('<div class="success-msg">', unsafe_allow_html=True)
                            # Fix: Use st.markdown for HTML content instead of st.success
                            st.markdown(f'<div style="padding: 1rem; border-radius: 0.5rem; background-color: #d4edda; border-color: #c3e6cb; color: #155724;"><span>Welcome back, <strong>{usr}</strong>! <span class="admin-badge">Admin</span></span></div>', unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="success-msg">', unsafe_allow_html=True)
                            st.success(f"Welcome back, **{usr}**!")
                            st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Set authentication state with role
                        st.session_state.authenticated = True
                        st.session_state.user_role = user_role
                        st.session_state.user_info = {
                            "id": result[0],
                            "username": usr,
                            "email": f"{usr}@example.com"  # Placeholder
                        }
                        
                        # Add a loading message with progress
                        with st.spinner(f"Loading {'Admin Dashboard' if user_role == 'admin' else 'MATBot'}..."):
                            progress = st.progress(0)
                            for i in range(101):
                                progress.progress(i)
                                time.sleep(0.01)
                        
                        # Redirect based on role
                        if user_role == 'admin':
                            st.switch_page("./pages/AdminPage.py")
                        else:
                            # Regular users go to chat app
                            st.switch_page("./pages/streamlit_chat_app.py")
                    else:
                        st.error("❌ Invalid username or password. Please try again.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="back-btn">', unsafe_allow_html=True)
        st.button("← Back to Home", on_click=lambda: go("home"))
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Footer
    st.markdown("<div style='text-align: center; margin-top: 40px; opacity: 0.7;'><p>© 2025 MATBot - Your MATLAB Intelligent AI Assistant</p></div>", unsafe_allow_html=True)