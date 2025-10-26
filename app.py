"""
Enhanced Streamlit UI for Test Case Generator with Gemini API
Fixed version - NO nested expanders anywhere
"""
import streamlit as st
import os
from pathlib import Path
import time
from datetime import datetime
from llm_handler import LLMHandler
from code_parser import CodeParser
from test_generator import TestGenerator
from git_handler import GitHandler
from csv_handler import CSVHandler
from rag_system import RAGSystem
from security import SecurityManager
from chat_manager import ChatManager
from logger import get_app_logger
from config import config

# Initialize logger
logger = get_app_logger("streamlit_app")

# Log application startup
logger.info("="*60)
logger.info(f"🚀 Test Case Generator v{config.APP_VERSION} - Starting")
logger.info(f"🔧 Using Gemini Model: {config.GEMINI_MODEL}")
logger.info("="*60)

# Page configuration
st.set_page_config(
    page_title="AI Test Case Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize all session state variables"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.uploaded_files = {}
        st.session_state.previous_code = {}
        st.session_state.test_results = None
        st.session_state.current_input_type = None
        
        # Initialize components
        try:
            st.session_state.rag_system = RAGSystem()
            st.session_state.llm_handler = LLMHandler()
            st.session_state.security_manager = SecurityManager()
            st.session_state.chat_manager = ChatManager()
            
            # Start new chat session
            st.session_state.chat_manager.start_new_session("New Conversation")
            
            logger.info("✅ All components initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing components: {e}", exc_info=True)
            st.error(f"Failed to initialize: {e}")
            st.stop()

init_session_state()

def display_sidebar():
    """Display enhanced sidebar"""
    with st.sidebar:
        st.markdown("<h1 style='text-align: center;'>🧪 Test Generator</h1>", unsafe_allow_html=True)
        
        st.divider()
        
        # Test configuration
        st.subheader("⚙️ Configuration")
        
        test_types = st.multiselect(
            "Test Types:",
            ["Unit Test", "Regression Test", "Functional Test"],
            default=["Unit Test", "Regression Test", "Functional Test"],
            help="Select which types of tests to generate"
        )
        
        functional_format = st.radio(
            "Functional Format:",
            ["Professional", "Code-based"],
            help="Professional format for documentation, Code-based for automation"
        )
        
        st.session_state.functional_format = "professional" if functional_format == "Professional" else "code"
        
        st.divider()
        
        # Chat history management
        st.subheader("💬 Chat History")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("➕ New Chat", use_container_width=True):
                st.session_state.chat_manager.start_new_session("New Conversation")
                st.rerun()
        
        with col2:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.chat_manager.clear_current_session()
                st.session_state.chat_manager.start_new_session("New Conversation")
                st.rerun()
        
        # List previous sessions
        sessions = st.session_state.chat_manager.list_sessions(limit=10)
        
        if sessions:
            st.caption("📚 Recent Sessions:")
            for session in sessions[:5]:
                session_title = session['title'][:30] + "..." if len(session['title']) > 30 else session['title']
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        f"📄 {session_title}",
                        key=f"load_{session['session_id']}",
                        use_container_width=True
                    ):
                        st.session_state.chat_manager.load_session(session['session_id'])
                        st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"del_{session['session_id']}"):
                        st.session_state.chat_manager.delete_session(session['session_id'])
                        st.rerun()
        
        st.divider()
        
        # Statistics
        st.subheader("📊 Statistics")
        stats = st.session_state.chat_manager.get_statistics()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Sessions", stats['total_sessions'])
        with col2:
            st.metric("Messages", stats['total_messages'])
        
        st.divider()
        
        # System info
        st.caption("ℹ️ System Information")
        st.caption(f"🤖 Model: {config.GEMINI_MODEL}")
        st.caption(f"📦 Version: {config.APP_VERSION}")
        
        return test_types

def handle_file_upload():
    """Handle file upload - NO EXPANDERS"""
    st.markdown("### 📁 Upload Code Files")
    
    uploaded_files = st.file_uploader(
        "Select code files to upload",
        accept_multiple_files=True,
        type=['py', 'js', 'java', 'cpp', 'c', 'cs', 'go', 'rb', 'php', 'swift', 'kt', 'ts', 'rs'],
        help="Upload one or more source code files for test generation"
    )
    
    if uploaded_files:
        logger.info(f"📂 User uploaded {len(uploaded_files)} files")
        
        st.success(f"✅ Uploaded {len(uploaded_files)} file(s)")
        
        # Show file list
        st.markdown("**Uploaded Files:**")
        
        for uploaded_file in uploaded_files:
            try:
                file_content = uploaded_file.read().decode('utf-8')
                st.session_state.uploaded_files[uploaded_file.name] = file_content
                
                # Show file info
                lines = len(file_content.split('\n'))
                size_kb = len(file_content) / 1024
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.markdown(f"- 📄 **{uploaded_file.name}**: {lines} lines, {size_kb:.1f} KB")
                
                with col2:
                    # Checkbox to show/hide code preview
                    show_code = st.checkbox("Preview", key=f"show_{uploaded_file.name}")
                
                # If checkbox is checked, show code preview
                if show_code:
                    st.code(file_content[:500], language='python')
                    if len(file_content) > 500:
                        st.caption(f"... showing first 500 of {len(file_content)} chars")
                
            except Exception as e:
                logger.error(f"❌ Error processing file {uploaded_file.name}: {e}")
                st.error(f"Error processing {uploaded_file.name}: {e}")
        
        return True
    
    return False

def handle_git_repo():
    """Handle Git repository - NO EXPANDERS"""
    st.markdown("### 🔗 Clone Git Repository")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        git_url = st.text_input(
            "Repository URL:",
            placeholder="https://github.com/username/repo.git",
            help="Enter the Git repository URL"
        )
    
    with col2:
        branch = st.text_input("Branch:", value="main")
    
    if git_url:
        return git_url, branch
    
    return None, None

def generate_tests(test_types):
    """Generate tests from uploaded files or git repo"""
    
    if not st.session_state.uploaded_files:
        st.warning("⚠️ No files to process. Please upload files or clone a repository.")
        return
    
    start_time = time.time()
    
    logger.info(f"🚀 Starting test generation for {len(st.session_state.uploaded_files)} files")
    logger.info(f"📋 Test types: {', '.join(test_types)}")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Parse code
        status_text.text("📝 Parsing code files...")
        parser = CodeParser()
        parsed_data = {}
        
        for i, (filename, content) in enumerate(st.session_state.uploaded_files.items()):
            parsed_data[filename] = parser.parse_code(content, filename)
            progress_bar.progress((i + 1) / (len(st.session_state.uploaded_files) * 4))
        
        # Add to RAG
        status_text.text("🧠 Building code context...")
        st.session_state.rag_system.add_code_documents(parsed_data)
        progress_bar.progress(0.3)
        
        # Generate tests
        status_text.text("⚡ Generating tests with AI...")
        generator = TestGenerator(
            st.session_state.llm_handler,
            st.session_state.rag_system
        )
        
        progress_bar.progress(0.4)
        
        test_cases = generator.generate_tests(
            parsed_data,
            test_types,
            module_level=True
        )
        
        progress_bar.progress(0.9)
        
        elapsed_time = time.time() - start_time
        total_tests = sum(len(tests) for tests in test_cases.values())
        
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        
        logger.info(f"✅ Generated {total_tests} tests in {elapsed_time:.2f}s")
        
        # Store results
        st.session_state.test_results = test_cases
        
        # Display results
        display_test_results(test_cases, elapsed_time)
        
        # Add to chat history
        st.session_state.chat_manager.add_message(
            "assistant",
            f"✅ Generated {total_tests} test cases in {elapsed_time:.2f}s",
            metadata={'test_count': total_tests, 'duration': elapsed_time}
        )
        
    except Exception as e:
        logger.error(f"❌ Test generation failed: {e}", exc_info=True)
        st.error(f"❌ Error generating tests: {e}")
        st.info("💡 Check the logs for more details: logs/app.log")
        status_text.empty()
        progress_bar.empty()

def display_professional_test(test, index):
    """Display professional format test - NO EXPANDERS"""
    with st.container():
        st.markdown(f"### 🧪 {test.get('test_case_id', test.get('name', f'TC-{index:03d}'))}")
        
        # Info row
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"**🎯 Target:** {test.get('target', 'N/A')}")
        
        with col2:
            st.markdown(f"**📄 File:** {test.get('file', 'N/A')}")
        
        with col3:
            priority = test.get('priority', 'Medium')
            color_map = {
                'Critical': ':red',
                'High': ':orange',
                'Medium': ':blue',
                'Low': ':gray'
            }
            color = color_map.get(priority, '')
            st.markdown(f"**Priority:** {color}[{priority}]" if color else f"**Priority:** {priority}")
        
        # Description
        st.markdown(f"**📝 Description:** {test.get('description', 'N/A')}")
        
        # Steps and Expected Result in columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📋 Steps:**")
            steps = test.get('steps', 'N/A')
            if steps != 'N/A':
                for i, step in enumerate(steps.split('\n'), 1):
                    if step.strip():
                        st.markdown(f"{i}. {step.strip()}")
            else:
                st.markdown("_No steps provided_")
        
        with col2:
            st.markdown("**✅ Expected Result:**")
            st.info(test.get('expected_result', 'N/A'))
        
        st.divider()

def display_code_test(test, index):
    """Display code format test - NO EXPANDERS"""
    with st.container():
        st.markdown(f"### 🧪 {test.get('name', f'Test {index}')}")
        
        # Info
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**🎯 Target:** {test.get('target', 'N/A')}")
            st.markdown(f"**📄 File:** {test.get('file', 'N/A')}")
            if test.get('description'):
                st.caption(test['description'])
        
        with col2:
            priority = test.get('priority', 'Medium')
            st.markdown(f"**Priority:** {priority}")
        
        # Code
        st.markdown("**💻 Test Code:**")
        st.code(test.get('code', 'No code'), language='python')
        
        st.divider()

def display_test_results(test_cases, elapsed_time):
    """Display generated test results using TABS - NO EXPANDERS"""
    
    total_tests = sum(len(tests) for tests in test_cases.values())
    
    if total_tests == 0:
        st.warning("⚠️ No test cases were generated")
        return
    
    st.success(f"✅ Generated {total_tests} test cases in {elapsed_time:.2f}s")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total Tests", total_tests)
    with col2:
        st.metric("🔬 Unit Tests", len(test_cases.get('Unit Test', [])))
    with col3:
        st.metric("🔄 Regression Tests", len(test_cases.get('Regression Test', [])))
    with col4:
        st.metric("⚙️ Functional Tests", len(test_cases.get('Functional Test', [])))
    
    # Generate downloads
    try:
        csv_handler = CSVHandler()
        csv_file = csv_handler.generate_csv(test_cases)
        report_file = csv_handler.generate_professional_test_report(test_cases)
        
        st.markdown("---")
        st.markdown("### 📥 Download Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with open(csv_file, 'rb') as f:
                st.download_button(
                    label="📥 Download Test Cases (CSV)",
                    data=f,
                    file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with col2:
            with open(report_file, 'rb') as f:
                st.download_button(
                    label="📄 Download Test Report (TXT)",
                    data=f,
                    file_name=f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
    except Exception as e:
        logger.error(f"❌ Error generating download files: {e}", exc_info=True)
        st.warning("⚠️ Could not generate download files. Check logs for details.")
    
    # Display test cases using TABS
    st.markdown("---")
    st.markdown("## 📋 Generated Test Cases")
    
    # Create tabs for each test type
    test_type_tabs = []
    test_type_data = []
    
    for test_type, tests in test_cases.items():
        if tests:
            test_type_tabs.append(f"{test_type}s ({len(tests)})")
            test_type_data.append((test_type, tests))
    
    if test_type_tabs:
        tabs = st.tabs(test_type_tabs)
        
        for tab, (test_type, tests) in zip(tabs, test_type_data):
            with tab:
                # Display first 10 tests
                display_count = min(len(tests), 10)
                
                st.markdown(f"**Showing {display_count} of {len(tests)} test cases**")
                
                if len(tests) > 10:
                    st.info(f"💡 Download the CSV or Report file to see all {len(tests)} test cases.")
                
                st.markdown("---")
                
                for i, test in enumerate(tests[:display_count], 1):
                    if test.get('format') == 'professional':
                        display_professional_test(test, i)
                    else:
                        display_code_test(test, i)

def handle_chat_input(test_types):
    """Handle chat input"""
    
    # Display chat history
    history = st.session_state.chat_manager.get_current_history()
    
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about test generation or paste a Git URL..."):
        logger.info(f"💬 User input: {prompt[:100]}...")
        
        # Sanitize input
        sanitized_prompt = st.session_state.security_manager.sanitize_input(prompt)
        
        # Add user message
        st.session_state.chat_manager.add_message("user", sanitized_prompt)
        
        with st.chat_message("user"):
            st.markdown(sanitized_prompt)
        
        # Detect input type
        input_type = detect_input_type(sanitized_prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                try:
                    if input_type == 'git':
                        # Handle Git URL
                        response = handle_git_from_chat(sanitized_prompt, test_types)
                    elif st.session_state.uploaded_files:
                        # If files are uploaded, generate tests
                        response = "I'll generate tests for the uploaded files now."
                        st.markdown(response)
                        generate_tests(test_types)
                        return
                    else:
                        # Regular chat
                        context = st.session_state.rag_system.get_relevant_context(sanitized_prompt)
                        response = st.session_state.llm_handler.generate_chat_response(
                            sanitized_prompt,
                            context,
                            history
                        )
                    
                    st.markdown(response)
                    st.session_state.chat_manager.add_message("assistant", response)
                    
                except Exception as e:
                    logger.error(f"❌ Error generating response: {e}", exc_info=True)
                    error_msg = "Sorry, I encountered an error. Please try again."
                    st.error(error_msg)
                    st.session_state.chat_manager.add_message("assistant", error_msg)

def detect_input_type(text: str) -> str:
    """Detect type of user input"""
    text_lower = text.lower()
    
    # Check for Git URL
    if 'github.com' in text_lower or 'gitlab.com' in text_lower or '.git' in text_lower:
        return 'git'
    
    # Check for file-related keywords
    if any(word in text_lower for word in ['upload', 'file', 'code file']):
        return 'file'
    
    return 'chat'

def handle_git_from_chat(text: str, test_types):
    """Handle Git repository from chat input"""
    import re
    
    # Extract Git URL
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, text)
    
    if not match:
        return "I couldn't find a valid Git URL. Please provide a URL like: https://github.com/user/repo.git"
    
    git_url = match.group(0)
    
    st.info(f"🔗 Cloning repository: {git_url}")
    
    try:
        git_handler = GitHandler()
        repo_path = git_handler.clone_repository(git_url, "main", 1)
        
        st.success(f"✅ Repository cloned successfully!")
        
        code_files = git_handler.get_code_files(repo_path)
        
        if not code_files:
            return "❌ No code files found in the repository."
        
        st.info(f"📁 Found {len(code_files)} code files. Parsing...")
        
        # Parse files
        parser = CodeParser()
        for file_path in code_files[:20]:  # Limit to 20 files
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    st.session_state.uploaded_files[file_path.name] = content
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
                continue
        
        # Generate tests
        generate_tests(test_types)
        
        # Cleanup
        git_handler.cleanup(repo_path)
        
        return f"✅ Cloned repository and processed {len(code_files)} files."
        
    except Exception as e:
        logger.error(f"❌ Git clone error: {e}", exc_info=True)
        return f"❌ Error cloning repository: {e}"

def main():
    """Main application"""
    
    # Validate configuration
    if not config.validate_config():
        st.error("⚠️ Configuration Error")
        st.error("Please set GEMINI_API_KEY in .env file")
        st.info("1. Copy .env.example to .env\n2. Add your LLM API key\n3. Restart the application")
        st.stop()
    
    # Sidebar
    test_types = display_sidebar()
    
    # Main header
    st.markdown("<h1 class='main-header'>🧪 AI-Powered Test Case Generator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Upload code • Clone repositories • Chat with AI • Generate comprehensive tests</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # Create tabs for different input methods (NO EXPANDERS)
    tab1, tab2, tab3 = st.tabs(["📁 Upload Files", "🔗 Git Repository", "💬 Chat"])
    
    with tab1:
        has_files = handle_file_upload()
        
        if has_files:
            st.markdown("---")
            if st.button("🚀 Generate Tests from Files", type="primary", use_container_width=True):
                generate_tests(test_types)
    
    with tab2:
        git_url, branch = handle_git_repo()
        
        if git_url:
            st.markdown("---")
            if st.button("🚀 Clone & Generate Tests", type="primary", use_container_width=True):
                st.session_state.chat_manager.add_message("user", f"Clone and analyze: {git_url}")
                handle_git_from_chat(git_url, test_types)
    
    with tab3:
        st.markdown("### 💬 Chat with AI Assistant")
        st.caption("Ask questions, upload files, or paste Git URLs")
        
        handle_chat_input(test_types)
    
    # Footer
    st.divider()
    st.caption("🤖 Powered by AI | 📝 Made with Streamlit")

if __name__ == "__main__":
    main()