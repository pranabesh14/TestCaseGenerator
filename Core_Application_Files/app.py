import streamlit as st
import os
from pathlib import Path
import json
from datetime import datetime
from llm_handler import LLMHandler
from code_parser import CodeParser
from test_generator import TestGenerator
from git_handler import GitHandler
from csv_handler import CSVHandler
from rag_system import RAGSystem
from security import SecurityManager
from logger import get_app_logger, TestGenerationLogger

# Initialize logger
logger = get_app_logger("streamlit_app")
test_logger = TestGenerationLogger()

# Log application startup
logger.info("="*60)
logger.info("Test Case Generator - Application Starting (Professional Format Support)")
logger.info("="*60)

# Page configuration
st.set_page_config(
    page_title="Test Case Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = {}
if 'previous_code' not in st.session_state:
    st.session_state.previous_code = {}
if 'rag_system' not in st.session_state:
    st.session_state.rag_system = RAGSystem()
if 'llm_handler' not in st.session_state:
    st.session_state.llm_handler = LLMHandler()
if 'security_manager' not in st.session_state:
    st.session_state.security_manager = SecurityManager()

def save_chat_history():
    """Save chat history to file"""
    history_dir = Path("chat_history")
    history_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = history_dir / f"chat_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(st.session_state.chat_history, f, indent=2)
    
    return filename

def load_chat_history(filename):
    """Load chat history from file"""
    with open(filename, 'r') as f:
        return json.load(f)

def display_sidebar():
    """Display sidebar with chat history and options"""
    with st.sidebar:
        st.title("🧪 Test Generator")
        
        st.info("💡 **NEW**: Functional tests in professional format!")
        
        # Test case type selection
        st.subheader("Test Case Types")
        test_types = st.multiselect(
            "Select test case types to generate:",
            ["Unit Test", "Regression Test", "Functional Test"],
            default=["Unit Test", "Regression Test", "Functional Test"]
        )
        
        st.divider()
        
        # Format selection
        st.subheader("⚙️ Output Format")
        functional_format = st.radio(
            "Functional Test Format:",
            ["Professional (Test Case ID, Steps, Expected Result)", "Code-based (Test Functions)"],
            help="Professional format matches industry standards with detailed test case specifications"
        )
        
        st.session_state.functional_format = "professional" if "Professional" in functional_format else "code"
        
        st.divider()
        
        # Chat history
        st.subheader("📜 Chat History")
        
        if st.button("💾 Save Current Chat"):
            if st.session_state.chat_history:
                filename = save_chat_history()
                st.success(f"Chat saved to {filename.name}")
        
        if st.button("🗑️ Clear Current Chat"):
            st.session_state.chat_history = []
            st.rerun()
        
        st.divider()
        
        # Display saved chats
        history_dir = Path("chat_history")
        if history_dir.exists():
            chat_files = sorted(history_dir.glob("chat_*.json"), reverse=True)
            if chat_files:
                st.write("**Saved Chats:**")
                for chat_file in chat_files[:10]:
                    if st.button(f"📄 {chat_file.stem}", key=chat_file.name):
                        st.session_state.chat_history = load_chat_history(chat_file)
                        st.rerun()
        
        return test_types

def detect_code_changes(file_name, current_code):
    """Detect changes in uploaded code"""
    if file_name in st.session_state.previous_code:
        previous = st.session_state.previous_code[file_name]
        if previous != current_code:
            prev_lines = set(previous.split('\n'))
            curr_lines = set(current_code.split('\n'))
            added = curr_lines - prev_lines
            removed = prev_lines - curr_lines
            
            return {
                'changed': True,
                'added_lines': len(added),
                'removed_lines': len(removed),
                'added': list(added)[:5],
                'removed': list(removed)[:5]
            }
    return {'changed': False}

def display_professional_test(test, index):
    """Display a professional format test case"""
    test_id = test.get('test_case_id', test.get('name', f'TC-{index:03d}'))
    
    # Create a nice card-like display
    with st.container():
        st.markdown(f"### {test_id}")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**Description:** {test.get('description', 'N/A')}")
        
        with col2:
            priority = "High" if "Functional" in test.get('type', '') else "Medium"
            st.markdown(f"**Priority:** :red[{priority}]" if priority == "Critical" else f"**Priority:** {priority}")
        
        st.markdown("**Target:** " + test.get('target', 'N/A'))
        if test.get('file'):
            st.markdown("**File:** " + test.get('file', 'N/A'))
        
        # Steps
        st.markdown("#### Steps")
        steps = test.get('steps', 'N/A')
        if steps != 'N/A':
            for step in steps.split('\n'):
                if step.strip():
                    st.markdown(f"- {step.strip()}")
        else:
            st.markdown("_No steps provided_")
        
        # Expected Result
        st.markdown("#### Expected Result")
        st.info(test.get('expected_result', 'N/A'))
        
        st.divider()

def display_code_test(test, index):
    """Display a code-based test case"""
    test_name = test.get('name', f'Test {index}')
    test_code = test.get('code', 'No code generated')
    test_desc = test.get('description', '')
    test_file = test.get('file', 'N/A')
    test_chunk = test.get('chunk_name', 'N/A')
    
    st.markdown(f"**Test {index}:** {test_name}")
    st.caption(f"📄 {test_file} | 🧩 Chunk: {test_chunk}")
    if test_desc:
        st.caption(test_desc)
    st.code(test_code, language='python')

def main():
    # Display sidebar and get test types
    test_types = display_sidebar()
    
    # Main content
    st.title("🧪 AI-Powered Test Case Generator")
    st.markdown("Upload code files or provide a Git repository to generate comprehensive test cases.")
    
    # Show format info
    with st.expander("ℹ️ About Test Formats"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### Professional Format
            **For Functional Tests**
            
            ✅ Industry-standard format
            - Test Case ID
            - Description
            - Steps
            - Expected Result
            
            Perfect for:
            - QA documentation
            - Test planning
            - Manual testing
            - Compliance requirements
            """)
        
        with col2:
            st.markdown("""
            ### Code Format
            **For Unit & Regression Tests**
            
            ✅ Ready-to-run test code
            - Test functions
            - Assertions
            - Setup/teardown
            
            Perfect for:
            - Automated testing
            - CI/CD pipelines
            - Developer testing
            - Test-driven development
            """)
    
    # Tabs for different input methods
    tab1, tab2, tab3 = st.tabs(["📁 Upload Files", "🔗 Git Repository", "💬 Chat"])
    
    # Tab 1: File Upload
    with tab1:
        st.subheader("Upload Code Files")
        uploaded_files = st.file_uploader(
            "Upload code files (any language)",
            accept_multiple_files=True,
            type=['py', 'js', 'java', 'cpp', 'c', 'cs', 'go', 'rb', 'php', 'swift', 'kt', 'ts', 'rs']
        )
        
        if uploaded_files:
            logger.info(f"User uploaded {len(uploaded_files)} files")
            for uploaded_file in uploaded_files:
                try:
                    file_content = uploaded_file.read().decode('utf-8')
                    
                    # Detect changes
                    changes = detect_code_changes(uploaded_file.name, file_content)
                    
                    if changes['changed']:
                        st.warning(f"⚠️ Changes detected in {uploaded_file.name}")
                        with st.expander("View Changes"):
                            st.write(f"**Added lines:** {changes['added_lines']}")
                            st.write(f"**Removed lines:** {changes['removed_lines']}")
                    
                    # Store code
                    st.session_state.previous_code[uploaded_file.name] = file_content
                    st.session_state.uploaded_files[uploaded_file.name] = file_content
                    
                    # Display file info
                    lines = len(file_content.split('\n'))
                    size_kb = len(file_content) / 1024
                    
                    with st.expander(f"📄 {uploaded_file.name} ({lines} lines, {size_kb:.1f} KB)"):
                        st.code(file_content[:1000], language='python')
                        if len(file_content) > 1000:
                            st.caption(f"... (showing first 1000 chars of {len(file_content)} total)")
                        
                except Exception as e:
                    logger.error(f"Error processing file {uploaded_file.name}: {str(e)}", exc_info=True)
                    st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        if st.button("🚀 Generate Test Cases from Files", type="primary"):
            if st.session_state.uploaded_files:
                import time
                start_time = time.time()
                
                logger.info(f"Starting test generation for {len(st.session_state.uploaded_files)} files")
                logger.info(f"Test types selected: {', '.join(test_types)}")
                logger.info(f"Functional format: {st.session_state.functional_format}")
                test_logger.log_generation_start(', '.join(test_types), len(st.session_state.uploaded_files))
                
                # Create progress indicators
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
                    
                    # Add to RAG system
                    status_text.text("🧠 Building code context...")
                    st.session_state.rag_system.add_code_documents(parsed_data)
                    progress_bar.progress(0.3)
                    
                    # Generate tests
                    status_text.text("🔬 Generating tests...")
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
                    
                    total_tests = sum(len(tests) for tests in test_cases.values())
                    elapsed_time = time.time() - start_time
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    
                    logger.info(f"Generated {total_tests} test cases in {elapsed_time:.2f}s")
                    
                    # Display results
                    if total_tests > 0:
                        st.success(f"✅ Generated {total_tests} test cases in {elapsed_time:.2f}s")
                        
                        # Show metrics
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Tests", total_tests)
                        with col2:
                            st.metric("Unit Tests", len(test_cases.get('Unit Test', [])))
                        with col3:
                            st.metric("Regression Tests", len(test_cases.get('Regression Test', [])))
                        with col4:
                            st.metric("Functional Tests", len(test_cases.get('Functional Test', [])))
                        
                        test_logger.log_generation_complete(', '.join(test_types), total_tests, elapsed_time)
                        
                        # Generate CSV
                        csv_handler = CSVHandler()
                        csv_file = csv_handler.generate_csv(test_cases)
                        
                        # Generate professional report
                        report_file = csv_handler.generate_professional_test_report(test_cases)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            with open(csv_file, 'rb') as f:
                                st.download_button(
                                    label="📥 Download Test Cases (CSV)",
                                    data=f,
                                    file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                        
                        with col2:
                            with open(report_file, 'rb') as f:
                                st.download_button(
                                    label="📄 Download Test Report (TXT)",
                                    data=f,
                                    file_name=f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                    mime="text/plain"
                                )
                        
                        # Display test cases
                        for test_type in test_types:
                            if test_type in test_cases and len(test_cases[test_type]) > 0:
                                with st.expander(f"{test_type}s ({len(test_cases[test_type])} cases)", expanded=True):
                                    
                                    # Check if professional format
                                    is_professional = any(
                                        test.get('format') == 'professional' 
                                        for test in test_cases[test_type]
                                    )
                                    
                                    for i, test in enumerate(test_cases[test_type][:10], 1):
                                        if test.get('format') == 'professional':
                                            display_professional_test(test, i)
                                        else:
                                            display_code_test(test, i)
                                    
                                    if len(test_cases[test_type]) > 10:
                                        st.info(f"... and {len(test_cases[test_type]) - 10} more tests (download files for full list)")
                            else:
                                st.info(f"No {test_type}s generated")
                    else:
                        st.warning("⚠️ No test cases were generated")
                            
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    logger.error(f"Test generation failed: {str(e)}", exc_info=True)
                    test_logger.log_error("generation_failed", str(e), {"files": len(st.session_state.uploaded_files)})
                    st.error(f"❌ Error generating tests: {str(e)}")
                    
                finally:
                    progress_bar.empty()
                    status_text.empty()
            else:
                st.error("Please upload at least one file first.")
    
    # Tab 2: Git Repository
    with tab2:
        st.subheader("Clone Git Repository")
        st.info("⚠️ Git integration with professional test format support!")
        
        git_url = st.text_input("Enter Git repository URL:", placeholder="https://github.com/username/repo.git")
        
        col1, col2 = st.columns(2)
        with col1:
            branch = st.text_input("Branch (optional):", value="main")
        with col2:
            depth = st.number_input("Clone depth:", min_value=1, value=1)
        
        if st.button("🔗 Clone and Generate Tests", type="primary"):
            if git_url:
                import time
                start_time = time.time()
                
                logger.info(f"Starting Git repository test generation: {git_url}")
                
                # Create progress indicators
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # Clone repository
                    status_text.text("📥 Cloning repository...")
                    git_handler = GitHandler()
                    repo_path = git_handler.clone_repository(git_url, branch, depth)
                    st.success(f"✅ Repository cloned to {repo_path}")
                    progress_bar.progress(0.2)
                    
                    # Get code files
                    status_text.text("🔍 Scanning for code files...")
                    code_files = git_handler.get_code_files(repo_path)
                    st.info(f"Found {len(code_files)} code files")
                    progress_bar.progress(0.3)
                    
                    # Parse code files
                    status_text.text("📝 Parsing code files...")
                    parser = CodeParser()
                    parsed_data = {}
                    
                    parse_progress = st.progress(0)
                    for i, file_path in enumerate(code_files):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                parsed_data[file_path.name] = parser.parse_code(content, file_path.name)
                                logger.info(f"Parsed {file_path.name}: {len(parsed_data[file_path.name].get('functions', []))} functions")
                        except Exception as e:
                            logger.error(f"Error parsing {file_path}: {e}")
                            continue
                        
                        parse_progress.progress((i + 1) / len(code_files))
                    
                    parse_progress.empty()
                    progress_bar.progress(0.5)
                    
                    if not parsed_data:
                        st.error("No code files could be parsed successfully")
                        return
                    
                    # Add to RAG system
                    status_text.text("🧠 Building code context...")
                    st.session_state.rag_system.add_code_documents(parsed_data)
                    progress_bar.progress(0.6)
                    
                    # Generate tests
                    status_text.text("🔬 Generating tests with professional format...")
                    generator = TestGenerator(
                        st.session_state.llm_handler,
                        st.session_state.rag_system
                    )
                    
                    test_cases = generator.generate_tests(
                        parsed_data,
                        test_types,
                        module_level=True
                    )
                    
                    progress_bar.progress(0.95)
                    
                    total_tests = sum(len(tests) for tests in test_cases.values())
                    elapsed_time = time.time() - start_time
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    
                    logger.info(f"Generated {total_tests} test cases in {elapsed_time:.2f}s")
                    
                    # Display results
                    if total_tests > 0:
                        st.success(f"✅ Generated {total_tests} test cases in {elapsed_time:.2f}s")
                        
                        # Show metrics
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Tests", total_tests)
                        with col2:
                            st.metric("Unit Tests", len(test_cases.get('Unit Test', [])))
                        with col3:
                            st.metric("Regression Tests", len(test_cases.get('Regression Test', [])))
                        with col4:
                            st.metric("Functional Tests", len(test_cases.get('Functional Test', [])))
                        
                        # Show repository info
                        with st.expander("📊 Repository Statistics"):
                            repo_structure = git_handler.get_repo_structure(repo_path)
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Total Files", repo_structure['total_files'])
                            with col2:
                                st.metric("Code Files", repo_structure['code_files'])
                            with col3:
                                st.metric("Languages", len(repo_structure['languages']))
                            
                            if repo_structure['languages']:
                                st.write("**Languages detected:**")
                                st.write(", ".join(repo_structure['languages']))
                        
                        test_logger.log_generation_complete(', '.join(test_types), total_tests, elapsed_time)
                        
                        # Generate CSV and report
                        csv_handler = CSVHandler()
                        csv_file = csv_handler.generate_csv(test_cases)
                        report_file = csv_handler.generate_professional_test_report(test_cases)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            with open(csv_file, 'rb') as f:
                                st.download_button(
                                    label="📥 Download Test Cases (CSV)",
                                    data=f,
                                    file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv",
                                    key="git_csv"
                                )
                        
                        with col2:
                            with open(report_file, 'rb') as f:
                                st.download_button(
                                    label="📄 Download Test Report (TXT)",
                                    data=f,
                                    file_name=f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                    mime="text/plain",
                                    key="git_report"
                                )
                        
                        # Display test cases
                        for test_type in test_types:
                            if test_type in test_cases and len(test_cases[test_type]) > 0:
                                with st.expander(f"{test_type}s ({len(test_cases[test_type])} cases)", expanded=False):
                                    for i, test in enumerate(test_cases[test_type][:10], 1):
                                        if test.get('format') == 'professional':
                                            display_professional_test(test, i)
                                        else:
                                            display_code_test(test, i)
                                    
                                    if len(test_cases[test_type]) > 10:
                                        st.info(f"... and {len(test_cases[test_type]) - 10} more tests (download files for full list)")
                            else:
                                st.info(f"No {test_type}s generated")
                    else:
                        st.warning("⚠️ No test cases were generated")
                        with st.expander("🔍 Troubleshooting"):
                            st.write("**Possible issues:**")
                            st.write("1. LLM connection problem")
                            st.write("2. Code parsing issues")
                            st.write("3. Check logs: `tail -f logs/app.log`")
                    
                    # Cleanup
                    try:
                        git_handler.cleanup(repo_path)
                        logger.info(f"Cleaned up repository: {repo_path}")
                    except Exception as e:
                        logger.warning(f"Could not cleanup repository: {e}")
                        
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    logger.error(f"Git test generation failed: {str(e)}", exc_info=True)
                    test_logger.log_error("git_generation_failed", str(e), {"repo": git_url})
                    st.error(f"❌ Error: {str(e)}")
                    
                    with st.expander("🔍 Error Details"):
                        st.code(str(e))
                        st.write("\n**Common issues:**")
                        st.write("1. Invalid repository URL")
                        st.write("2. Repository is private (requires authentication)")
                        st.write("3. Branch doesn't exist")
                        st.write("4. Git not installed on system")
                        st.write("5. Network connectivity issues")
                    
                finally:
                    progress_bar.empty()
                    status_text.empty()
            else:
                st.error("Please enter a Git repository URL.")
    
    # Tab 3: Chat Interface
    with tab3:
        st.subheader("💬 Chat with Test Generator")
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask about test generation..."):
            logger.info(f"User chat input: {prompt[:100]}...")
            
            # Sanitize input
            sanitized_prompt = st.session_state.security_manager.sanitize_input(prompt)
            
            # Check if prompt is valid
            if not st.session_state.security_manager.is_valid_test_query(sanitized_prompt):
                with st.chat_message("assistant"):
                    response = "I can only assist with generating test cases. Please ask questions related to test case generation, code analysis, or testing strategies."
                    st.markdown(response)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })
                st.rerun()
            
            # Add user message
            st.session_state.chat_history.append({
                "role": "user",
                "content": sanitized_prompt,
                "timestamp": datetime.now().isoformat()
            })
            
            with st.chat_message("user"):
                st.markdown(sanitized_prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        context = st.session_state.rag_system.get_relevant_context(sanitized_prompt)
                        response = st.session_state.llm_handler.generate_chat_response(
                            sanitized_prompt,
                            context,
                            st.session_state.chat_history
                        )
                        
                        st.markdown(response)
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error generating chat response: {str(e)}", exc_info=True)
                        st.error("Sorry, I encountered an error. Please try again.")

if __name__ == "__main__":
    main()