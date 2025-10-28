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
logger.info("Test Case Generator - Application Starting")
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
if 'current_repo_path' not in st.session_state:
    st.session_state.current_repo_path = None

def generate_chat_name(message: str) -> str:
    """Generate a chat name from first few words of message"""
    # Clean the message
    words = message.strip().split()
    # Take first 5 words, max 50 chars
    name_words = words[:5]
    name = '_'.join(name_words)
    # Remove special characters
    name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
    # Limit length
    name = name[:50]
    return name if name else "chat"

def has_context() -> bool:
    """Check if there's any context available (files, repo, or test results)"""
    # Check for uploaded files
    if st.session_state.uploaded_files:
        return True
    
    # Check for repository
    if st.session_state.current_repo_path:
        return True
    
    # Check for test results in chat history
    for message in st.session_state.chat_history:
        if message.get("role") == "assistant" and "test_results" in message:
            return True
    
    # Check if RAG system has documents
    if st.session_state.rag_system.code_documents:
        return True
    
    return False

def auto_save_chat():
    """Auto-save chat after significant interactions"""
    if st.session_state.chat_history and len(st.session_state.chat_history) >= 2:
        # Only auto-save if there's meaningful content
        save_chat_history()

def save_chat_history():
    """Save chat history to file with meaningful name"""
    if not st.session_state.chat_history:
        return None
    
    history_dir = Path("chat_history")
    history_dir.mkdir(exist_ok=True)
    
    # Get first user message for naming
    first_message = None
    for msg in st.session_state.chat_history:
        if msg['role'] == 'user':
            first_message = msg['content']
            break
    
    if first_message:
        chat_name = generate_chat_name(first_message)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = history_dir / f"{chat_name}_{timestamp}.json"
    else:
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
    """Display sidebar with options and chat history"""
    with st.sidebar:
        st.title("🧪 Test Generator")
        
        # Test case type selection
        st.subheader("Test Case Types")
        test_types = st.multiselect(
            "Select test types:",
            ["Unit Test", "Functional Test"],
            default=["Unit Test", "Functional Test"],
            help="Regression tests have been removed for simplicity"
        )
        
        st.divider()
        
        # Format selection
        st.subheader("⚙️ Output Format")
        functional_format = st.radio(
            "Functional Test Format:",
            ["Professional (Test Case ID, Steps, Expected Result)", "Code-based (Test Functions)"],
            help="Professional format matches industry standards"
        )
        
        st.session_state.functional_format = "professional" if "Professional" in functional_format else "code"
        
        st.divider()
        
        # Chat history management
        st.subheader("📜 Chat History")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🆕 New", use_container_width=True, help="Start a new chat"):
                # Auto-save current chat before clearing
                if st.session_state.chat_history:
                    save_chat_history()
                st.session_state.chat_history = []
                st.session_state.uploaded_files = {}
                st.session_state.current_repo_path = None
                st.success("New chat started!")
                st.rerun()
        
        with col2:
            if st.button("💾 Save", use_container_width=True, help="Save current chat"):
                if st.session_state.chat_history:
                    filename = save_chat_history()
                    if filename:
                        st.success(f"Saved!")
                else:
                    st.warning("No chat to save")
        
        with col3:
            if st.button("🗑️ Clear", use_container_width=True, help="Clear without saving"):
                st.session_state.chat_history = []
                st.session_state.uploaded_files = {}
                st.session_state.current_repo_path = None
                st.rerun()
        
        st.divider()
        
        # Display saved chats
        history_dir = Path("chat_history")
        if history_dir.exists():
            chat_files = sorted(history_dir.glob("*.json"), reverse=True)
            if chat_files:
                st.write("**Recent Chats:**")
                for chat_file in chat_files[:10]:
                    # Extract readable name from filename
                    name = chat_file.stem
                    # Remove timestamp if present
                    parts = name.split('_')
                    if len(parts) > 1 and parts[-1].isdigit():
                        display_name = '_'.join(parts[:-2])  # Remove date and time
                    else:
                        display_name = name
                    
                    # Limit display name length
                    if len(display_name) > 30:
                        display_name = display_name[:30] + "..."
                    
                    if st.button(f"📄 {display_name}", key=chat_file.name, use_container_width=True):
                        st.session_state.chat_history = load_chat_history(chat_file)
                        st.rerun()
        
        return test_types

def process_files(uploaded_files, test_types):
    """Process uploaded files and generate tests"""
    import time
    start_time = time.time()
    
    logger.info(f"Processing {len(uploaded_files)} files")
    test_logger.log_generation_start(', '.join(test_types), len(uploaded_files))
    
    # Create progress indicators
    with st.status("🔄 Processing files...", expanded=True) as status:
        st.write("📝 Parsing code files...")
        
        # Parse code
        parser = CodeParser()
        parsed_data = {}
        
        for filename, content in uploaded_files.items():
            parsed_data[filename] = parser.parse_code(content, filename)
        
        st.write("🧠 Building code context...")
        st.session_state.rag_system.add_code_documents(parsed_data)
        
        st.write("🔬 Generating tests...")
        generator = TestGenerator(
            st.session_state.llm_handler,
            st.session_state.rag_system
        )
        
        test_cases = generator.generate_tests(
            parsed_data,
            test_types,
            module_level=True
        )
        
        total_tests = sum(len(tests) for tests in test_cases.values())
        elapsed_time = time.time() - start_time
        
        status.update(label=f"✅ Complete! Generated {total_tests} tests in {elapsed_time:.1f}s", state="complete")
    
    logger.info(f"Generated {total_tests} test cases in {elapsed_time:.2f}s")
    test_logger.log_generation_complete(', '.join(test_types), total_tests, elapsed_time)
    
    return test_cases, elapsed_time

def process_git_repo(repo_url, branch, test_types):
    """Process Git repository and generate tests"""
    import time
    start_time = time.time()
    
    logger.info(f"Processing Git repository: {repo_url}")
    
    with st.status("🔄 Processing repository...", expanded=True) as status:
        # Clone/update repository
        st.write("📥 Cloning/updating repository...")
        git_handler = GitHandler()
        repo_path = git_handler.clone_repository(repo_url, branch, depth=1)
        st.session_state.current_repo_path = repo_path
        
        # Get code files
        st.write("📂 Scanning for code files...")
        code_files = git_handler.get_code_files(repo_path)
        st.write(f"Found {len(code_files)} code files")
        
        # Parse code files
        st.write("📝 Parsing code files...")
        parser = CodeParser()
        parsed_data = {}
        
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    parsed_data[file_path.name] = parser.parse_code(content, file_path.name)
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")
                continue
        
        if not parsed_data:
            st.error("❌ No code files could be parsed")
            return None, 0
        
        # Build RAG context
        st.write("🧠 Building code context...")
        st.session_state.rag_system.add_code_documents(parsed_data)
        
        # Generate tests
        st.write("🔬 Generating tests...")
        generator = TestGenerator(
            st.session_state.llm_handler,
            st.session_state.rag_system
        )
        
        test_cases = generator.generate_tests(
            parsed_data,
            test_types,
            module_level=True
        )
        
        total_tests = sum(len(tests) for tests in test_cases.values())
        elapsed_time = time.time() - start_time
        
        # Show repo info
        repo_structure = git_handler.get_repo_structure(repo_path)
        commit_info = git_handler.get_commit_info(repo_path)
        
        st.write(f"📊 Repo: {repo_structure['code_files']} code files, {len(repo_structure['languages'])} languages")
        st.write(f"📌 Commit: {commit_info['hash']} by {commit_info['author']}")
        
        status.update(label=f"✅ Complete! Generated {total_tests} tests in {elapsed_time:.1f}s", state="complete")
    
    logger.info(f"Generated {total_tests} test cases in {elapsed_time:.2f}s")
    
    return test_cases, elapsed_time

def display_test_results(test_cases, test_types):
    """Display test results with download buttons"""
    if not test_cases:
        return
    
    total_tests = sum(len(tests) for tests in test_cases.values())
    
    if total_tests == 0:
        st.warning("⚠️ No test cases were generated")
        return
    
    # Show metrics
    cols = st.columns(3)
    with cols[0]:
        st.metric("Total Tests", total_tests)
    with cols[1]:
        st.metric("Unit Tests", len(test_cases.get('Unit Test', [])))
    with cols[2]:
        st.metric("Functional Tests", len(test_cases.get('Functional Test', [])))
    
    # Generate output files
    csv_handler = CSVHandler()
    csv_file = csv_handler.generate_csv(test_cases)
    report_file = csv_handler.generate_professional_test_report(test_cases)
    
    # Download buttons
    col1, col2 = st.columns(2)
    
    # Generate unique key using timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with col1:
        with open(csv_file, 'rb') as f:
            st.download_button(
                label="📥 Download CSV",
                data=f,
                file_name=f"test_cases_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"download_csv_{timestamp}"  # Unique key
            )
    
    with col2:
        with open(report_file, 'rb') as f:
            st.download_button(
                label="📄 Download Report",
                data=f,
                file_name=f"test_report_{timestamp}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"download_report_{timestamp}"  # Unique key
            )
    
    # Display test cases in expandable sections
    st.divider()
    
    for test_type in test_types:
        if test_type in test_cases and len(test_cases[test_type]) > 0:
            with st.expander(f"{test_type}s ({len(test_cases[test_type])} cases)", expanded=False):
                for i, test in enumerate(test_cases[test_type][:10], 1):
                    if test.get('format') == 'professional':
                        # Professional format
                        st.markdown(f"### {test.get('test_case_id', f'TC-{i:03d}')}")
                        st.markdown(f"**Description:** {test.get('description', 'N/A')}")
                        st.markdown(f"**Target:** {test.get('target', 'N/A')}")
                        
                        st.markdown("**Steps:**")
                        steps = test.get('steps', 'N/A')
                        if steps != 'N/A':
                            for step in steps.split('\n'):
                                if step.strip():
                                    st.markdown(f"- {step.strip()}")
                        
                        st.markdown("**Expected Result:**")
                        st.info(test.get('expected_result', 'N/A'))
                    else:
                        # Code format
                        st.markdown(f"**Test {i}:** {test.get('name', 'Unnamed')}")
                        st.caption(test.get('description', ''))
                        st.code(test.get('code', 'No code'), language='python')
                    
                    st.divider()
                
                if len(test_cases[test_type]) > 10:
                    st.info(f"... and {len(test_cases[test_type]) - 10} more tests (download files for full list)")

def main():
    # Display sidebar and get test types
    test_types = display_sidebar()
    
    # Main content - Single unified interface
    st.title("🧪 AI Test Case Generator")
    st.caption("Upload code files or provide a Git repository URL in the chat")
    
    # File uploader in main area (compact)
    with st.container():
        uploaded_files = st.file_uploader(
            "📎 Or upload files here",
            accept_multiple_files=True,
            type=['py', 'js', 'java', 'cpp', 'c', 'cs', 'go', 'rb', 'php', 'swift', 'kt', 'ts', 'rs'],
            label_visibility="collapsed"
        )
        
        if uploaded_files:
            st.caption(f"📁 {len(uploaded_files)} file(s) uploaded")
            
            # Process uploaded files
            for uploaded_file in uploaded_files:
                try:
                    file_content = uploaded_file.read().decode('utf-8')
                    st.session_state.uploaded_files[uploaded_file.name] = file_content
                except Exception as e:
                    logger.error(f"Error processing file {uploaded_file.name}: {str(e)}")
                    st.error(f"Error: {uploaded_file.name}")
    
    st.divider()
    
    # Chat interface
    st.subheader("💬 Chat")
    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Display test results if available
            if message["role"] == "assistant" and "test_results" in message:
                display_test_results(message["test_results"], test_types)
    
    # Chat input
    if prompt := st.chat_input("Ask me to generate tests, or paste a Git repository URL..."):
        logger.info(f"User input: {prompt[:100]}...")
        
        # Sanitize input
        sanitized_prompt = st.session_state.security_manager.sanitize_input(prompt)
        
        # Add user message to chat
        st.session_state.chat_history.append({
            "role": "user",
            "content": sanitized_prompt,
            "timestamp": datetime.now().isoformat()
        })
        
        with st.chat_message("user"):
            st.markdown(sanitized_prompt)
        
        # Process the input
        with st.chat_message("assistant"):
            # Check if it's a Git URL
            if sanitized_prompt.startswith(('http://', 'https://')) and ('github.com' in sanitized_prompt or 'gitlab.com' in sanitized_prompt or '.git' in sanitized_prompt):
                # Extract URL and branch
                parts = sanitized_prompt.split()
                git_url = parts[0]
                branch = parts[1] if len(parts) > 1 else "main"
                
                # Validate Git URL
                is_valid, error_msg = st.session_state.security_manager.validate_git_url(git_url)
                
                if not is_valid:
                    response = f"❌ Invalid Git URL: {error_msg}"
                    st.markdown(response)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    try:
                        test_cases, elapsed_time = process_git_repo(git_url, branch, test_types)
                        
                        if test_cases:
                            total_tests = sum(len(tests) for tests in test_cases.values())
                            response = f"✅ Successfully generated **{total_tests}** test cases from repository in {elapsed_time:.1f}s"
                            st.markdown(response)
                            
                            # Display results
                            display_test_results(test_cases, test_types)
                            
                            # Save to chat history with results
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "test_results": test_cases,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # Auto-save after test generation
                            auto_save_chat()
                        else:
                            response = "❌ Failed to generate tests from repository"
                            st.markdown(response)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    except Exception as e:
                        logger.error(f"Git processing error: {str(e)}", exc_info=True)
                        response = f"❌ Error: {str(e)}"
                        st.markdown(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
            
            # Check if asking to generate tests from uploaded files
            elif any(keyword in sanitized_prompt.lower() for keyword in ['generate', 'create', 'analyze']):
                if st.session_state.uploaded_files or has_context():
                    try:
                        # If files uploaded, process them
                        if st.session_state.uploaded_files:
                            test_cases, elapsed_time = process_files(st.session_state.uploaded_files, test_types)
                            
                            total_tests = sum(len(tests) for tests in test_cases.values())
                            response = f"✅ Successfully generated **{total_tests}** test cases in {elapsed_time:.1f}s"
                            st.markdown(response)
                            
                            # Display results
                            display_test_results(test_cases, test_types)
                            
                            # Save to chat history with results
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "test_results": test_cases,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # Auto-save after test generation
                            auto_save_chat()
                        else:
                            # Has context but no new files - answer based on existing context
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
                        logger.error(f"Test generation error: {str(e)}", exc_info=True)
                        response = f"❌ Error generating tests: {str(e)}"
                        st.markdown(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    response = "📎 Please upload code files first, or provide a Git repository URL."
                    st.markdown(response)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })
            
            # General chat
            else:
                # If we have context, allow broader questions
                if has_context():
                    try:
                        context = st.session_state.rag_system.get_relevant_context(sanitized_prompt)
                        
                        # Include test results from chat history in context if available
                        # Find the latest test results
                        test_results = None
                        for message in reversed(st.session_state.chat_history):
                            if message.get("role") == "assistant" and "test_results" in message:
                                test_results = message["test_results"]
                                break
                        
                        test_context = ""
                        if test_results:
                            test_context += "\n\nPreviously generated tests:\n"
                            for test_type, tests in test_results.items():
                                test_context += f"{test_type}s ({len(tests)} tests):\n"
                                # Limit to first 10 tests to avoid token overflow
                                for i, test in enumerate(tests[:10], 1):
                                    if test.get('format') == 'professional':
                                        test_context += f"Test {i}: ID: {test.get('test_case_id', '')}, Description: {test.get('description', 'N/A')}, Steps: {test.get('steps', 'N/A')}, Expected: {test.get('expected_result', 'N/A')}\n"
                                    else:
                                        test_context += f"Test {i}: Name: {test.get('name', 'Unnamed')}, Description: {test.get('description', 'N/A')}, Code snippet: {test.get('code', 'No code')[:200]}...\n"
                                if len(tests) > 10:
                                    test_context += f"... and {len(tests) - 10} more tests\n"
                            test_context += "\n"
                        
                        full_context = context + test_context
                        
                        response = st.session_state.llm_handler.generate_chat_response(
                            sanitized_prompt,
                            full_context,
                            st.session_state.chat_history
                        )
                        
                        st.markdown(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Chat error: {str(e)}", exc_info=True)
                        response = "Sorry, I encountered an error. Please try again."
                        st.markdown(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    # No context - check if it's a valid test query
                    if not st.session_state.security_manager.is_valid_test_query(sanitized_prompt):
                        response = "I can only assist with generating test cases. Please ask questions related to test case generation, code analysis, or provide a Git repository URL."
                        st.markdown(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
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
                            logger.error(f"Chat error: {str(e)}", exc_info=True)
                            response = "Sorry, I encountered an error. Please try again."
                            st.markdown(response)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": datetime.now().isoformat()
                            })
        
        st.rerun()

if __name__ == "__main__":
    main()