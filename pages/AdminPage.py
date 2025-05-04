import streamlit as st
import sqlalchemy
import pandas as pd
import os
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# Initialize DB engine once
@st.cache_resource
def get_engine():
    url = "postgresql://test_owner:Vdk6Z9MXuqTO@ep-little-bird-a1iyap0y-pooler.ap-southeast-1.aws.neon.tech/test?sslmode=require"
    return sqlalchemy.create_engine(url)

# Authentication check
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    # st.info("Redirecting to login page...")
    # time.sleep(1)
    # st.switch_page("../Landing.py")
    st.stop()

# Check if user is admin
if "user_role" not in st.session_state or st.session_state.user_role != "admin":
    st.error("You don't have permission to access this page")
    st.info("Redirecting to user dashboard...")
    time.sleep(1.5)
    st.switch_page("./streamlit_chat_app.py")
    st.stop()

# File size utility function
@st.cache_data(ttl=3600)
def get_file_stats():
    stats = {}
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    
    # Track important files
    files_to_check = {
        "corpus.json": os.path.join(base_dir, "corpus.json"),
        "images_log.json": os.path.join(base_dir, "images_log.json"),
        "self_memory.json": os.path.join(base_dir, "self_memory.json"),
    }
    
    for name, filepath in files_to_check.items():
        if os.path.exists(filepath):
            size_bytes = os.path.getsize(filepath)
            modified_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            # Read first few entries to get counts
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    item_count = len(data)
                    
                    # Get additional data based on file type
                    if name == "corpus.json":
                        chunk_count = sum(len(item.get('chunks', [])) for item in data)
                    else:
                        chunk_count = None
            except Exception as e:
                item_count = "Error reading file"
                chunk_count = None
                
            stats[name] = {
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "modified": modified_time,
                "item_count": item_count,
                "chunk_count": chunk_count
            }
        else:
            stats[name] = {"exists": False}
    
    return stats

# Get corpus statistics
@st.cache_data(ttl=3600)
def get_corpus_stats():
    try:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        corpus_path = os.path.join(base_dir, "corpus.json")
        
        with open(corpus_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Count document types
        doc_types = {}
        for item in data:
            title = item.get('title', 'Unknown')
            if '/' in title:
                doc_type = title.split('/')[0]
            else:
                doc_type = 'General'
                
            if doc_type not in doc_types:
                doc_types[doc_type] = 0
            doc_types[doc_type] += 1
            
        # Count chunks per document
        chunks_per_doc = [len(item.get('chunks', [])) for item in data]
        
        return {
            "count": len(data),
            "doc_types": doc_types,
            "chunks_per_doc": chunks_per_doc,
            "avg_chunks": sum(chunks_per_doc) / len(chunks_per_doc) if chunks_per_doc else 0
        }
    except Exception as e:
        return {"error": str(e)}

# Get image statistics
@st.cache_data(ttl=3600)
def get_image_stats():
    try:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        image_path = os.path.join(base_dir, "images_log.json")
        
        with open(image_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get image sources
        image_sources = {}
        for item in data:
            url = item.get('url', '')
            domain = url.split('/')[2] if '//' in url and len(url.split('/')) > 2 else 'Unknown'
            
            if domain not in image_sources:
                image_sources[domain] = 0
            image_sources[domain] += 1
        
        return {
            "count": len(data),
            "sources": image_sources
        }
    except Exception as e:
        return {"error": str(e)}

# Get user activity data
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_user_activity(_engine):
    """
    Get user activity data - uses leading underscore in parameter name to avoid hashing the engine
    
    Args:
        _engine: SQLAlchemy engine (with leading underscore to prevent hashing)
    """
    try:
        # This is a placeholder - in a real app, you'd have a proper user_activity table
        # For now, we'll just get basic user counts
        query = "SELECT role, COUNT(*) as count FROM users GROUP BY role"
        return pd.read_sql(query, _engine)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})

def admin_dashboard():
    st.set_page_config(page_title="Admin Dashboard", layout="wide")
    
    # CSS for styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #4B89DC;
        margin-bottom: 20px;
    }
    .section-header {
        font-size: 1.5rem;
        color: #3C579E;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .dashboard-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-container {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.3s;
    }
    .metric-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #3C579E;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 5px;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .status-good {
        background-color: #28a745;
    }
    .status-warning {
        background-color: #ffc107;
    }
    .status-danger {
        background-color: #dc3545;
    }
    .refresh-btn {
        float: right;
        padding: 4px 10px;
        font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header with user info and refresh button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<p class="main-header">Admin Dashboard</p>', unsafe_allow_html=True)
        st.markdown(f"Logged in as: **{st.session_state.user_info['username']}** (Admin)")
    
    with col2:
        if st.button("🔄 Refresh Data", key="refresh_all"):
            st.cache_data.clear()
            st.rerun()

    # Get DB engine
    engine = get_engine()

    # Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["👤 User Management", "📊 Analytics Dashboard", "⚙️ System Status"])

    with tab1:
        # --- Make Admin Section ---
        with st.expander("Make User Admin", expanded=True):
            st.markdown('<p class="section-header">Promote User to Admin</p>', unsafe_allow_html=True)
            try:
                query = "SELECT username FROM users WHERE role != 'admin'"
                users_df = pd.read_sql(query, engine)

                if users_df.empty:
                    st.info("No regular users found to promote to admin.")
                else:
                    selected_user = st.selectbox("Select user to make admin:", users_df['username'].tolist())

                    if st.button("Make Admin", key="make_admin_btn"):
                        try:
                            with engine.connect() as conn:
                                conn.execute(sqlalchemy.text(
                                    "UPDATE users SET role = 'admin' WHERE username = :user"
                                ), {"user": selected_user})
                                conn.commit()
                            st.success(f"User '{selected_user}' has been promoted to admin!")
                            # Clear cache to refresh user lists
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update user role: {str(e)}")
            except Exception as e:
                st.error(f"Failed to fetch users: {str(e)}")

        # --- Remove Admin Section ---
        with st.expander("Remove Admin Rights"):
            st.markdown('<p class="section-header">Demote Admin to Regular User</p>', unsafe_allow_html=True)
            try:
                query = "SELECT username FROM users WHERE role = 'admin'"
                admins_df = pd.read_sql(query, engine)

                if admins_df.empty:
                    st.info("No admin users found.")
                else:
                    selected_admin = st.selectbox("Select admin to demote:", admins_df['username'].tolist())

                    if st.button("Remove Admin", key="remove_admin_btn"):
                        try:
                            with engine.connect() as conn:
                                conn.execute(sqlalchemy.text(
                                    "UPDATE users SET role = 'user' WHERE username = :user"
                                ), {"user": selected_admin})
                                conn.commit()
                            st.success(f"User '{selected_admin}' has been demoted to regular user.")
                            # Clear cache to refresh user lists
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update user role: {str(e)}")
            except Exception as e:
                st.error(f"Failed to fetch admins: {str(e)}")

        # --- View All Users Section ---
        with st.expander("View All Users"):
            st.markdown('<p class="section-header">All Users and Roles</p>', unsafe_allow_html=True)
            try:
                query = "SELECT username, role FROM users ORDER BY role, username"
                all_users_df = pd.read_sql(query, engine)

                if all_users_df.empty:
                    st.info("No users found in the database.")
                else:
                    st.dataframe(all_users_df, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to fetch users: {str(e)}")

    with tab2:
        st.markdown('<p class="section-header">System Analytics</p>', unsafe_allow_html=True)
        
        # Get stats
        file_stats = get_file_stats()
        corpus_stats = get_corpus_stats()
        image_stats = get_image_stats()
        user_activity = get_user_activity(engine)
        
        # Top level metrics
        st.markdown('<div>', unsafe_allow_html=True)
        metric_cols = st.columns(4)
        
        with metric_cols[0]:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            user_count = len(pd.read_sql("SELECT * FROM users", engine))
            st.markdown(f'<div class="metric-value">{user_count}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Registered Users</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with metric_cols[1]:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            if "error" not in corpus_stats:
                st.markdown(f'<div class="metric-value">{corpus_stats["count"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">N/A</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Knowledge Base Documents</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with metric_cols[2]:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            if "error" not in image_stats:
                st.markdown(f'<div class="metric-value">{image_stats["count"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">N/A</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Indexed Images</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with metric_cols[3]:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            memory_count = file_stats.get("self_memory.json", {}).get("item_count", "N/A")
            if memory_count != "N/A" and memory_count != "Error reading file":
                st.markdown(f'<div class="metric-value">{memory_count}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">0</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Self-Memory Entries</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # User Distribution Chart
        st.markdown('<div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("User Role Distribution")
            if not user_activity.empty and "error" not in user_activity.columns:
                fig = px.pie(
                    user_activity, 
                    names='role', 
                    values='count', 
                    color='role',
                    color_discrete_map={'admin': '#4B89DC', 'user': '#5CB85C'}
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No user data available")
        
        with col2:
            st.subheader("Knowledge Base Composition")
            if "error" not in corpus_stats and corpus_stats.get("doc_types"):
                doc_types_df = pd.DataFrame({
                    'category': list(corpus_stats["doc_types"].keys()),
                    'count': list(corpus_stats["doc_types"].values())
                })
                fig = px.bar(
                    doc_types_df, 
                    x='category', 
                    y='count',
                    title="Document Categories",
                    color='category'
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No corpus data available")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # File size chart
        st.markdown('<div>', unsafe_allow_html=True)
        st.subheader("Database Size (MB)")
        
        # Create dataframe for file sizes
        file_size_data = []
        for file_name, stats in file_stats.items():
            if stats.get("size_mb") is not None:
                file_size_data.append({
                    "file": file_name,
                    "size_mb": stats["size_mb"],
                    "modified": stats.get("modified", "Unknown")
                })
        
        if file_size_data:
            file_size_df = pd.DataFrame(file_size_data)
            fig = px.bar(
                file_size_df,
                x='file',
                y='size_mb',
                text_auto='.2f',
                title="Database File Sizes",
                color='file'
            )
            fig.update_traces(texttemplate='%{text} MB', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Display last modified time
            st.markdown("### Last Modified")
            for item in file_size_data:
                st.markdown(f"**{item['file']}**: {item['modified']}")
        else:
            st.info("No file size data available")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Corpus details
        if "error" not in corpus_stats:
            st.markdown('<div>', unsafe_allow_html=True)
            st.subheader("Corpus Detailed Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Distribution of chunks per document
                if corpus_stats.get("chunks_per_doc"):
                    chunks_df = pd.DataFrame({
                        "chunks_per_doc": corpus_stats["chunks_per_doc"]
                    })
                    fig = px.histogram(
                        chunks_df, 
                        x="chunks_per_doc",
                        nbins=20,
                        title="Distribution of Chunks per Document"
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Image sources distribution
                if "error" not in image_stats and image_stats.get("sources"):
                    source_df = pd.DataFrame({
                        'source': list(image_stats["sources"].keys()),
                        'count': list(image_stats["sources"].values())
                    })
                    source_df = source_df.sort_values('count', ascending=False).head(10)
                    fig = px.bar(
                        source_df,
                        x='count',
                        y='source',
                        orientation='h',
                        title="Top Image Sources"
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<p class="section-header">System Status</p>', unsafe_allow_html=True)
        st.markdown('<div>', unsafe_allow_html=True)
        
        # System file status
        st.subheader("System File Status")
        
        status_cols = st.columns(3)
        
        for i, (file_name, stats) in enumerate(file_stats.items()):
            with status_cols[i % 3]:
                if stats.get("exists") is False:
                    status_class = "status-danger"
                    status_text = "Missing"
                elif stats.get("size_mb", 0) < 0.1:
                    status_class = "status-warning"
                    status_text = "Small"
                else:
                    status_class = "status-good"
                    status_text = "OK"
                
                st.markdown(f"""
                <div style="margin-bottom: 15px; border: 1px solid #ddd; padding: 10px; border-radius: 5px;">
                    <h4>
                        <span class="status-indicator {status_class}"></span>
                        {file_name}
                    </h4>
                    <p>Status: <strong>{status_text}</strong></p>
                    <p>Size: {stats.get('size_mb', 'N/A')} MB</p>
                    <p>Items: {stats.get('item_count', 'N/A')}</p>
                    <p>Last modified: {stats.get('modified', 'Unknown')}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # System Actions
        st.subheader("System Actions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Cache", key="clear_cache"):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache cleared successfully!")
                time.sleep(1)
                st.rerun()
        
        with col2:
            if st.button("Test Database Connection", key="test_db"):
                try:
                    with engine.connect() as conn:
                        result = conn.execute(sqlalchemy.text("SELECT 1")).fetchone()
                    if result and result[0] == 1:
                        st.success("Database connection successful!")
                    else:
                        st.error("Database connection failed!")
                except Exception as e:
                    st.error(f"Database connection error: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    admin_dashboard()
