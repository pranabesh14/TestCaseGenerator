An AI-assisted test case generator. Generated cases are drafts and need review.

## Source-grounded functional generation

Functional generation indexes definitions and static call relationships for
**C, C++, Python, JavaScript/JSX, TypeScript/TSX, Java, C#, Go, Rust, Ruby,
PHP, Swift, Kotlin/Kotlin scripts, Scala, R, and MATLAB**. Each language uses
its syntax adapter; generation, source evidence checks and CSV export are shared.
Upload validation and repository discovery include all their supported extensions.

- Repository paths are preserved (for example `src/bcd.cpp`), including duplicate basenames.
- C++ declarations in `abc.h` do not become implementation targets. Definitions
  in `bcd.cpp` produce CSV rows pointing to `bcd.cpp`. Inline header definitions
  correctly keep the header as their source.
- Each functional request includes the whole entry definition and its resolved
  transitive callees. Source is never silently cut at 1,500 characters.
- CSV rows include `Direct Calls`, `Tiered Functions`, `Call Graph`,
  `Related Source Files`, `Context Complete`, `Context Warnings`, and `Source Evidence`.
  Tiers use minimum static call distance from the entry; the graph preserves
  branching and cycles. Unresolved/dynamic call names remain in the tiers with
  explicit labels; candidate definition locations are retained where available.
  These are possible static calls, not execution traces.
- Unknown/dynamic receivers, virtual dispatch, and ambiguous overloads remain
  unresolved. This syntax index does not replace compiler type analysis or
  `compile_commands.json`; macros, templates and build variants can require
  compiler-backed indexing. Malformed C/C++ files are skipped. Other adapters
  can retain intact definitions from partially parsed files, with warnings;
  erroneous definitions are skipped and context is marked incomplete.
- The generator validates target identity and citation locations, requires
  evidence from the entry function, and labels accepted cases `Needs Review`.
  It cannot prove that an expected result follows from a citation. API errors
  and invalid JSON produce no dummy functional cases.
- Repositories are no longer silently limited to 100 files. Each explicit
  repository-generation request rebuilds the whole suite, including on unchanged
  commits, so old cases or stale callers are not reused. This increases API work
  and latency for large repositories; there is currently one request per definition.

Configuration (character limits, not token counts):

```env
FUNCTIONAL_CONTEXT_MAX_CHARS=60000
FUNCTIONAL_CALL_MAX_DEPTH=8
LLM_TEMPERATURE=0.1
```

Oversized entry definitions are skipped with diagnostics. Dependency/file context
that exceeds the budget or depth limit is reported as incomplete. Scenarios that
depend on missing source must be omitted; review remains necessary.

Install/update with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q
streamlit run app.py
```

The regression checks use controlled LLM responses and source fixtures. They
test parsing, graph resolution, validation, budgets and CSV provenance; they do
not measure live-model accuracy. Actual functional requirements still need a
specification or a human review; code describes implemented behavior.

The multilingual adapters use the pinned `tree-sitter-language-pack==0.9.0`,
which bundles grammar binaries. Supported syntax includes named methods/functions,
JavaScript arrows, expression bodies and R function assignments. The graph
handles lexical scopes, self/this calls, package/namespace references, explicit
JS/TS imports and exports (including basic CommonJS), Go import aliases,
simple Rust `use` paths, and simple Java/Kotlin/Scala/PHP/C# import directives.
These are syntax adapters, not complete compiler or runtime analyzers. Complex
re-exports, dynamic rebinding, reflection, dependency-injection targets, wildcard
or build-specific import resolution, Swift modules, Rust macro expansion,
Ruby/R runtime loading and MATLAB search-path rules can need more information.
Unknown targets are recorded rather than guessed. Script/data-only files and
callable forms that yield no named definitions receive a diagnostic.

Features
🎯 Core Capabilities

Multi-Language Support: Python, JavaScript, TypeScript, Java, C++, Go, Ruby, PHP, and more
Multiple Test Types:

Unit Tests (function-level testing)
Regression Tests (change detection and backward compatibility)
Functional Tests (end-to-end behavior validation)


Professional Test Formats: Industry-standard test case documentation with Test IDs, Steps, and Expected Results
Code-Based Tests: Ready-to-run test functions with assertions

🚀 Input Methods

File Upload: Upload individual code files through web interface
Git Repository: Clone and analyze entire repositories
Interactive Chat: Ask questions and get guidance on test generation

🧠 Intelligent Features

RAG System: Context-aware test generation using Retrieval Augmented Generation
Code Chunking: Intelligent code splitting for optimal LLM processing
Change Detection: Identifies code modifications for targeted regression testing
Security Validation: Input sanitization and malicious pattern detection

📊 Export Options

CSV format for spreadsheet integration
Professional test reports (TXT format)
JSON format for programmatic access
Multiple format export in one go

Installation
Prerequisites

Python 3.8 or higher
Git (for repository cloning features)
LLM API endpoint (local or remote)

Setup

Clone the repository

bashgit clone <repository-url>
cd test-case-generator

Install dependencies

bashpip install -r requirements.txt

Configure environment variables
Create a .env file in the root directory:

env# LLM Configuration
LLM_API_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL_NAME=your-model-name
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# Application Settings
DEBUG=False
LOG_LEVEL=INFO
MAX_FILE_SIZE=1000000

# Feature Flags
ENABLE_GIT_INTEGRATION=True
ENABLE_RAG_SYSTEM=True

Create necessary directories

bashpython -c "from config import config; config.create_directories()"
Usage
Web Interface (Streamlit)
Start the web application:
bashstreamlit run app.py
The application will be available at http://localhost:8501
Features:

Upload code files via drag-and-drop
Clone Git repositories by URL
Interactive chat for test generation guidance
Real-time test generation with progress tracking
Download generated tests in multiple formats

Command Line Interface
Generate tests from local files
bashpython cli.py generate file1.py file2.py --types unit regression functional --output csv
Generate tests from Git repository
bashpython cli.py generate-repo https://github.com/username/repo.git --branch main --types unit functional
Analyze code structure
bashpython cli.py analyze mycode.py
Export in multiple formats
bashpython cli.py generate file.py --output all
```

```

## Configuration

### LLM Settings
Configure your LLM endpoint and model in the `.env` file or through environment variables:
- `LLM_API_ENDPOINT`: API endpoint URL
- `LLM_MODEL_NAME`: Model identifier
- `LLM_TEMPERATURE`: Creativity level (0.0-1.0)
- `LLM_MAX_TOKENS`: Maximum response length

### Test Generation Settings
- `UNIT_TESTS_PER_FILE`: Number of unit tests per file (default: 5)
- `REGRESSION_TESTS_PER_CHANGE`: Tests per code change (default: 3)
- `FUNCTIONAL_TESTS_PER_MODULE`: Module-level tests (default: 5)

### Security Settings
- `MAX_INPUT_LENGTH`: Maximum input string length
- `RATE_LIMIT_REQUESTS`: Request rate limit
- `ENABLE_SECURITY_LOGGING`: Enable security event logging

## Test Format Examples

### Professional Format (Functional Tests)
```
Test Case ID: TC-FN-01
Description: Validate user authentication flow
Steps:
  Step 1: Navigate to login page
  Step 2: Enter valid credentials
  Step 3: Click login button
Expected Result: User successfully authenticated and redirected to dashboard
Code Format (Unit/Regression Tests)
pythondef test_calculate_total_valid_input():
    """Test calculate_total with valid numeric inputs"""
    result = calculate_total(10, 20, 30)
    assert result == 60, "Sum should equal 60"
Architecture
Code Processing Pipeline

Parsing: Extract functions, classes, imports from code
Chunking: Split code into logical, processable chunks
Context Retrieval: Use RAG to find relevant code context
Test Generation: Generate tests using LLM for each chunk
Formatting: Convert to professional or code format
Export: Save to CSV, TXT, or JSON

RAG System
The RAG (Retrieval Augmented Generation) system maintains a knowledge base of:

Code structure and patterns
Function and class definitions
Previous versions for change detection
Cross-file dependencies

Security
The application includes multiple security layers:

Input Sanitization: Removes malicious patterns and control characters
Query Validation: Ensures requests are test-related
Code Validation: Checks for suspicious patterns in uploaded code
Git URL Validation: Prevents access to private/local repositories
Rate Limiting: Prevents abuse (placeholder for production implementation)

Logging
Comprehensive logging system with multiple log files:

logs/app.log: General application events
logs/test_generation.log: Test generation metrics
logs/errors.log: Error tracking
logs/performance.log: Performance metrics
logs/security_events.log: Security-related events

Troubleshooting
LLM Connection Issues

Verify LLM_API_ENDPOINT is correct and accessible
Check if LLM service is running
Review timeout settings in configuration

Git Clone Failures

Ensure Git is installed and in PATH
Check repository URL format
Verify network connectivity
For private repos, authentication is not currently supported

Test Generation Issues

Check logs in logs/app.log for detailed errors
Verify code files are in supported languages
Ensure LLM has sufficient context window for large files

Contributing
Contributions are welcome! Please:

Fork the repository
Create a feature branch
Make your changes with tests
Submit a pull request

License
[MIT]
Support
For issues, questions, or feature requests, please:

Check the logs for detailed error information
Review the troubleshooting section
Open an issue on the repository


Streamlit for the web interface
Python AST for code parsing
Modern LLM technology for intelligent test generation
