# AI-Powered Test Case Generator

A comprehensive RAG-based chatbot system for automated test case generation using Llama3 and Streamlit.

## Features

✅ **Multi-Language Support**: Parse and analyze code in Python, JavaScript, Java, C++, Go, and more  
✅ **Three Test Types**: Generate Unit Tests, Regression Tests, and Functional Tests  
✅ **Code Change Detection**: Automatically detect changes when files are re-uploaded  
✅ **Git Integration**: Clone and analyze entire repositories  
✅ **RAG System**: Context-aware test generation using Retrieval-Augmented Generation  
✅ **CSV Export**: Export test cases with categorization and priority  
✅ **Chat History**: Persistent chat history saved to sidebar  
✅ **Security Hardened**: Input sanitization and LLM boundaries to prevent misuse  
✅ **Module-Level Testing**: Generate tests for entire modules/projects  

## Architecture

```
├── app.py                 # Main Streamlit application
├── llm_handler.py         # LLM integration with Llama3
├── code_parser.py         # Multi-language code parsing
├── test_generator.py      # Test case generation logic
├── git_handler.py         # Git repository operations
├── csv_handler.py         # CSV export functionality
├── rag_system.py          # RAG implementation
├── security.py            # Security and input sanitization
└── requirements.txt       # Python dependencies
```

## Prerequisites

1. **Python 3.8+**
2. **Ollama** (for running Llama3 locally)
3. **Git** (for repository cloning)

## Installation

### Step 1: Install Ollama and Llama3

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Or for Windows, download from: https://ollama.com/download

# Pull Llama3 model
ollama pull llama3
```

### Step 2: Install Python Dependencies

```bash
# Clone this repository
git clone <your-repo-url>
cd test-case-generator

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment

Create a `.env` file in the root directory:

```env
# LLM Configuration
LLM_API_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL_NAME=llama3

# Optional: Set custom ports
STREAMLIT_SERVER_PORT=8501
```

## Usage

### Start the Application

```bash
# Start Ollama service (if not running)
ollama serve

# In another terminal, start the Streamlit app
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### Using the Application

#### 1. Upload Files Tab

1. Click "Upload Code Files"
2. Select one or more code files
3. Review detected changes (if re-uploading)
4. Click "Generate Test Cases from Files"
5. Download the CSV with all test cases

#### 2. Git Repository Tab

1. Enter Git repository URL (e.g., `https://github.com/user/repo.git`)
2. Specify branch (default: main)
3. Set clone depth
4. Click "Clone and Generate Tests"
5. Wait for analysis and download results

#### 3. Chat Tab

1. Ask questions about test generation
2. Get recommendations for testing strategies
3. Discuss specific test scenarios
4. Chat history is automatically saved

### Test Case Types

**Unit Tests**: Test individual functions and methods
- Focus on single units of code
- Include assertions and edge cases
- High priority

**Regression Tests**: Ensure changes don't break functionality
- Generated when code changes are detected
- Test affected areas
- Critical priority for changed code

**Functional Tests**: End-to-end feature testing
- Test complete workflows
- Integration between components
- Medium-High priority

## Security Features

### Input Sanitization
- Removes malicious patterns (SQL injection, XSS, etc.)
- Validates file sizes and formats
- Sanitizes filenames

### LLM Boundaries
The system enforces strict boundaries on the LLM:
- **Only** generates test-related content
- Refuses non-testing queries
- Cannot be used for general coding tasks
- Blocks malicious requests

### Rate Limiting
- Prevents abuse through rate limiting
- Logs security events
- Validates Git URLs

## Configuration

### Custom LLM Endpoint

If using a different LLM service, modify `llm_handler.py`:

```python
# For OpenAI-compatible APIs
self.api_endpoint = "https://your-api-endpoint.com/v1/chat/completions"

# For Anthropic Claude
self.api_endpoint = "https://api.anthropic.com/v1/messages"
```

### Adjust Test Generation

Modify parameters in `test_generator.py`:

```python
# Change number of tests generated
def _generate_unit_tests(self, parsed_data: Dict) -> List[Dict]:
    # Generate 3-5 tests instead of 5-10
    # Modify prompt in llm_handler.py
```

## Project Structure

```
test-case-generator/
├── app.py                      # Main application
├── llm_handler.py              # LLM integration
├── code_parser.py              # Code analysis
├── test_generator.py           # Test generation
├── git_handler.py              # Git operations
├── csv_handler.py              # Export functionality
├── rag_system.py               # RAG implementation
├── security.py                 # Security layer
├── requirements.txt            # Dependencies
├── README.md                   # This file
├── .env                        # Configuration
├── chat_history/               # Saved chats
├── rag_storage/                # RAG data
├── test_outputs/               # Generated test files
├── temp_repos/                 # Cloned repositories
└── logs/                       # Security logs
```

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Module Import Errors

```bash
# Ensure all dependencies are installed
pip install -r requirements.txt --upgrade
```

### Git Clone Failures

- Check internet connection
- Verify repository URL
- Ensure Git is installed: `git --version`
- Check repository permissions

### Large Files

The system limits:
- Individual files: 1MB
- Total code per request: 5000 characters to LLM
- Repository: 100 files maximum

## Advanced Usage

### Custom Test Templates

Create custom test templates by modifying prompts in `llm_handler.py`:

```python
def generate_unit_tests(self, code: str, file_name: str, context: Dict):
    prompt = f"""Your custom prompt here...
    
    Use framework: pytest/unittest/jest
    Follow pattern: Given-When-Then
    ...
    """
```

### Integration with CI/CD

```yaml
# Example GitHub Actions workflow
name: Generate Tests
on: [push]
jobs:
  generate-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Generate tests
        run: python generate_tests_cli.py  # Create CLI version
```

## API Reference

### LLMHandler

```python
llm = LLMHandler(model_name="llama3")

# Generate unit tests
tests = llm.generate_unit_tests(code, filename, context)

# Generate regression tests
tests = llm.generate_regression_tests(old_code, new_code, changes)

# Generate functional tests
tests = llm.generate_functional_tests(code, module_info)
```

### CodeParser

```python
parser = CodeParser()

# Parse code
parsed = parser.parse_code(code, filename)
# Returns: {functions, classes, imports, complexity, ...}

# Detect language
lang = parser.detect_language("script.py")
```

### RAGSystem

```python
rag = RAGSystem()

# Add documents
rag.add_code_documents(parsed_data)

# Get relevant context
context = rag.get_relevant_context("unit tests for login")

# Search functions
results = rag.search_by_function("authenticate")
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: [your-email@example.com]

## Acknowledgments

- Llama3 by Meta AI
- Streamlit for the amazing UI framework
- Ollama for local LLM hosting
