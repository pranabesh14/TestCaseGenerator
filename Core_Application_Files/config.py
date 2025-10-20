"""
Configuration settings for the Test Case Generator
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Main configuration class"""
    
    # Application settings
    APP_NAME = "AI Test Case Generator"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # LLM Configuration
    LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT", "http://localhost:11434/api/generate")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
    
    # File handling
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "1000000"))  # 1MB
    MAX_FILES_PER_REQUEST = int(os.getenv("MAX_FILES_PER_REQUEST", "50"))
    SUPPORTED_EXTENSIONS = [
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
        '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala'
    ]
    
    # Git configuration
    GIT_CLONE_DEPTH = int(os.getenv("GIT_CLONE_DEPTH", "1"))
    GIT_TIMEOUT = int(os.getenv("GIT_TIMEOUT", "300"))  # 5 minutes
    MAX_REPO_FILES = int(os.getenv("MAX_REPO_FILES", "100"))
    
    # RAG configuration
    RAG_MAX_RESULTS = int(os.getenv("RAG_MAX_RESULTS", "3"))
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.1"))
    
    # Test generation settings
    DEFAULT_TEST_TYPES = ["Unit Test", "Regression Test", "Functional Test"]
    UNIT_TESTS_PER_FILE = int(os.getenv("UNIT_TESTS_PER_FILE", "5"))
    REGRESSION_TESTS_PER_CHANGE = int(os.getenv("REGRESSION_TESTS_PER_CHANGE", "3"))
    FUNCTIONAL_TESTS_PER_MODULE = int(os.getenv("FUNCTIONAL_TESTS_PER_MODULE", "5"))
    
    # Security settings
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour
    ENABLE_SECURITY_LOGGING = os.getenv("ENABLE_SECURITY_LOGGING", "True").lower() == "true"
    
    # Storage paths
    BASE_DIR = Path(__file__).parent
    STORAGE_DIR = BASE_DIR / "storage"
    CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
    RAG_STORAGE_DIR = BASE_DIR / "rag_storage"
    TEST_OUTPUT_DIR = BASE_DIR / "test_outputs"
    TEMP_REPOS_DIR = BASE_DIR / "temp_repos"
    LOGS_DIR = BASE_DIR / "logs"
    
    # Create directories
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        for dir_path in [
            cls.STORAGE_DIR,
            cls.CHAT_HISTORY_DIR,
            cls.RAG_STORAGE_DIR,
            cls.TEST_OUTPUT_DIR,
            cls.TEMP_REPOS_DIR,
            cls.LOGS_DIR
        ]:
            dir_path.mkdir(exist_ok=True, parents=True)
    
    # Streamlit configuration
    STREAMLIT_PORT = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    STREAMLIT_THEME = {
        "primaryColor": "#4CAF50",
        "backgroundColor": "#FFFFFF",
        "secondaryBackgroundColor": "#F0F2F6",
        "textColor": "#262730",
        "font": "sans serif"
    }
    
    # CSV Export settings
    CSV_ENCODING = "utf-8"
    CSV_DELIMITER = ","
    CSV_MAX_CODE_LENGTH = int(os.getenv("CSV_MAX_CODE_LENGTH", "5000"))
    
    # Test priorities
    TEST_PRIORITIES = {
        "Unit Test": "High",
        "Regression Test": "Critical",
        "Functional Test": "Medium"
    }
    
    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = LOGS_DIR / "app.log"
    
    # Feature flags
    ENABLE_GIT_INTEGRATION = os.getenv("ENABLE_GIT_INTEGRATION", "True").lower() == "true"
    ENABLE_CHAT_HISTORY = os.getenv("ENABLE_CHAT_HISTORY", "True").lower() == "true"
    ENABLE_RAG_SYSTEM = os.getenv("ENABLE_RAG_SYSTEM", "True").lower() == "true"
    ENABLE_CHANGE_DETECTION = os.getenv("ENABLE_CHANGE_DETECTION", "True").lower() == "true"
    
    @classmethod
    def get_llm_config(cls) -> dict:
        """Get LLM configuration as dictionary"""
        return {
            "api_endpoint": cls.LLM_API_ENDPOINT,
            "model_name": cls.LLM_MODEL_NAME,
            "temperature": cls.LLM_TEMPERATURE,
            "max_tokens": cls.LLM_MAX_TOKENS,
            "timeout": cls.LLM_TIMEOUT
        }
    
    @classmethod
    def get_security_config(cls) -> dict:
        """Get security configuration as dictionary"""
        return {
            "max_input_length": cls.MAX_INPUT_LENGTH,
            "rate_limit_requests": cls.RATE_LIMIT_REQUESTS,
            "rate_limit_window": cls.RATE_LIMIT_WINDOW,
            "enable_logging": cls.ENABLE_SECURITY_LOGGING
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Check if LLM endpoint is accessible
        try:
            import requests
            response = requests.get(cls.LLM_API_ENDPOINT.replace('/api/generate', ''), timeout=5)
        except Exception as e:
            errors.append(f"Cannot connect to LLM endpoint: {e}")
        
        # Check if required directories can be created
        try:
            cls.create_directories()
        except Exception as e:
            errors.append(f"Cannot create directories: {e}")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = "WARNING"
    LLM_TIMEOUT = 120
    MAX_FILES_PER_REQUEST = 100


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    LLM_API_ENDPOINT = "http://localhost:11434/api/generate"
    MAX_FILE_SIZE = 100000  # 100KB for testing


# Select configuration based on environment
ENV = os.getenv("ENVIRONMENT", "development").lower()

if ENV == "production":
    config = ProductionConfig()
elif ENV == "testing":
    config = TestingConfig()
else:
    config = DevelopmentConfig()

# Create directories on import
config.create_directories()