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
        
        # Test case type selection
        st.subheader("Test Case Types")
        test_types = st.multiselect(
            "Select test case types to generate:",
            ["Unit Test", "Regression Test", "Functional Test"],
            default=["Unit Test", "Regression Test", "Functional Test"]
        )
        
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
                for chat_file in chat_files[:10]:  # Show last 10
                    if st.button(f"📄 {chat_file.stem}", key=chat_file.name):
                        st.session_state.chat_history = load_chat_history(chat_file)
                        st.rerun()
        
        return test_types

def detect_code_changes(file_name, current_code):
    """Detect changes in uploaded code"""
    if file_name in st.session_state.previous_code:
        previous = st.session_state.previous_code[file_name]
        if previous != current_code:
            # Calculate simple diff
            prev_lines = set(previous.split('\n'))
            curr_lines = set(current_code.split('\n'))
            added = curr_lines - prev_lines
            removed = prev_lines - curr_lines
            
            return {
                'changed': True,
                'added_lines': len(added),
                'removed_lines': len(removed),
                'added': list(added)[:5],  # Show first 5
                'removed': list(removed)[:5]
            }
    return {'changed': False}

def main():
    # Display sidebar and get test types
    test_types = display_sidebar()
    
    # Main content
    st.title("🧪 AI-Powered Test Case Generator")
    st.markdown("Upload code files or provide a Git repository to generate comprehensive test cases.")
    
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
            for uploaded_file in uploaded_files:
                file_content = uploaded_file.read().decode('utf-8')
                
                # Detect changes
                changes = detect_code_changes(uploaded_file.name, file_content)
                
                if changes['changed']:
                    st.warning(f"⚠️ Changes detected in {uploaded_file.name}")
                    with st.expander("View Changes"):
                        st.write(f"**Added lines:** {changes['added_lines']}")
                        st.write(f"**Removed lines:** {changes['removed_lines']}")
                        if changes['added']:
                            st.write("**Sample additions:**")
                            for line in changes['added']:
                                if line.strip():
                                    st.code(line, language='python')
                
                # Store code
                st.session_state.previous_code[uploaded_file.name] = file_content
                st.session_state.uploaded_files[uploaded_file.name] = file_content
                
                # Display file info
                with st.expander(f"📄 {uploaded_file.name}"):
                    st.code(file_content, language='python')
        
        if st.button("🚀 Generate Test Cases from Files", type="primary"):
            if st.session_state.uploaded_files:
                with st.spinner("Analyzing code and generating test cases..."):
                    # Parse code
                    parser = CodeParser()
                    parsed_data = {}
                    
                    for filename, content in st.session_state.uploaded_files.items():
                        parsed_data[filename] = parser.parse_code(content, filename)
                    
                    # Add to RAG system
                    st.session_state.rag_system.add_code_documents(parsed_data)
                    
                    # Generate tests
                    generator = TestGenerator(
                        st.session_state.llm_handler,
                        st.session_state.rag_system
                    )
                    
                    test_cases = generator.generate_tests(
                        parsed_data,
                        test_types,
                        module_level=True
                    )
                    
                    # Display results
                    st.success("✅ Test cases generated successfully!")
                    
                    # Generate CSV
                    csv_handler = CSVHandler()
                    csv_file = csv_handler.generate_csv(test_cases)
                    
                    with open(csv_file, 'rb') as f:
                        st.download_button(
                            label="📥 Download Test Cases (CSV)",
                            data=f,
                            file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    
                    # Display test cases
                    for test_type in test_types:
                        if test_type in test_cases and len(test_cases[test_type]) > 0:
                            with st.expander(f"{test_type}s ({len(test_cases[test_type])} cases)"):
                                for i, test in enumerate(test_cases[test_type][:5], 1):
                                    test_name = test.get('name', f'Test {i}')
                                    test_code = test.get('code', 'No code generated')
                                    test_desc = test.get('description', '')
                                    
                                    st.markdown(f"**Test {i}:** {test_name}")
                                    if test_desc:
                                        st.caption(test_desc)
                                    st.code(test_code, language='python')
                        else:
                            st.info(f"No {test_type}s generated")
            else:
                st.error("Please upload at least one file first.")
    
    # Tab 2: Git Repository
    with tab2:
        st.subheader("Clone Git Repository")
        git_url = st.text_input("Enter Git repository URL:", placeholder="https://github.com/username/repo.git")
        
        col1, col2 = st.columns(2)
        with col1:
            branch = st.text_input("Branch (optional):", value="main")
        with col2:
            depth = st.number_input("Clone depth:", min_value=1, value=1)
        
        if st.button("🔗 Clone and Generate Tests", type="primary"):
            if git_url:
                with st.spinner("Cloning repository..."):
                    git_handler = GitHandler()
                    
                    try:
                        repo_path = git_handler.clone_repository(git_url, branch, depth)
                        st.success(f"✅ Repository cloned to {repo_path}")
                        
                        # Parse all code files
                        code_files = git_handler.get_code_files(repo_path)
                        st.info(f"Found {len(code_files)} code files")
                        
                        parser = CodeParser()
                        parsed_data = {}
                        
                        for file_path in code_files:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                parsed_data[file_path.name] = parser.parse_code(content, file_path.name)
                        
                        # Add to RAG system
                        st.session_state.rag_system.add_code_documents(parsed_data)
                        
                        # Generate tests
                        generator = TestGenerator(
                            st.session_state.llm_handler,
                            st.session_state.rag_system
                        )
                        
                        test_cases = generator.generate_tests(
                            parsed_data,
                            test_types,
                            module_level=True
                        )
                        
                        st.success("✅ Test cases generated successfully!")
                        
                        # Generate CSV
                        csv_handler = CSVHandler()
                        csv_file = csv_handler.generate_csv(test_cases)
                        
                        with open(csv_file, 'rb') as f:
                            st.download_button(
                                label="📥 Download Test Cases (CSV)",
                                data=f,
                                file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        
                        # Display test cases
                        for test_type in test_types:
                            if test_type in test_cases and len(test_cases[test_type]) > 0:
                                with st.expander(f"{test_type}s ({len(test_cases[test_type])} cases)"):
                                    for i, test in enumerate(test_cases[test_type][:5], 1):
                                        test_name = test.get('name', f'Test {i}')
                                        test_code = test.get('code', 'No code generated')
                                        test_desc = test.get('description', '')
                                        
                                        st.markdown(f"**Test {i}:** {test_name}")
                                        if test_desc:
                                            st.caption(test_desc)
                                        st.code(test_code, language='python')
                            else:
                                st.info(f"No {test_type}s generated")
                        
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
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
            # Sanitize input
            sanitized_prompt = st.session_state.security_manager.sanitize_input(prompt)
            
            # Check if prompt is valid for test generation
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
                    # Get relevant context from RAG
                    context = st.session_state.rag_system.get_relevant_context(sanitized_prompt)
                    
                    # Generate response
                    response = st.session_state.llm_handler.generate_chat_response(
                        sanitized_prompt,
                        context,
                        st.session_state.chat_history
                    )
                    
                    st.markdown(response)
                    
                    # Add to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "timestamp": datetime.now().isoformat()
                    })

if __name__ == "__main__":
    main()