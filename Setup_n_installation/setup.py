#!/usr/bin/env python3
"""
Cross-platform setup script for Test Case Generator
Supports: Windows, macOS, Linux
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
import urllib.request
import json

class Colors:
    """ANSI color codes (work on most terminals)"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color
    
    @staticmethod
    def disable():
        """Disable colors (for Windows without ANSI support)"""
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.BLUE = ''
        Colors.MAGENTA = ''
        Colors.CYAN = ''
        Colors.WHITE = ''
        Colors.NC = ''


class SetupManager:
    """Manage cross-platform setup"""
    
    def __init__(self):
        self.platform = platform.system()
        self.is_windows = self.platform == "Windows"
        self.is_macos = self.platform == "Darwin"
        self.is_linux = self.platform == "Linux"
        
        # Enable ANSI colors on Windows 10+
        if self.is_windows:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except:
                Colors.disable()
        
        self.python_cmd = self._get_python_command()
        self.pip_cmd = self._get_pip_command()
        self.venv_activate = self._get_venv_activate()
        
    def _get_python_command(self):
        """Get the correct Python command for the platform"""
        commands = ['python3', 'python', 'py']
        for cmd in commands:
            try:
                result = subprocess.run(
                    [cmd, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return cmd
            except:
                continue
        return 'python3'
    
    def _get_pip_command(self):
        """Get the correct pip command"""
        if self.is_windows:
            return 'pip'
        return 'pip3'
    
    def _get_venv_activate(self):
        """Get the virtual environment activation command"""
        if self.is_windows:
            return 'venv\\Scripts\\activate'
        return 'source venv/bin/activate'
    
    def print_header(self):
        """Print setup header"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.WHITE}Test Case Generator - Setup Script{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")
        print(f"Platform: {Colors.YELLOW}{self.platform}{Colors.NC}")
        print(f"Python: {Colors.YELLOW}{self.python_cmd}{Colors.NC}\n")
    
    def check_python_version(self):
        """Check if Python version is adequate"""
        print(f"{Colors.BLUE}Checking Python version...{Colors.NC}")
        
        try:
            result = subprocess.run(
                [self.python_cmd, '--version'],
                capture_output=True,
                text=True
            )
            
            version_str = result.stdout.strip() or result.stderr.strip()
            print(f"Found: {version_str}")
            
            # Extract version number
            version = version_str.split()[1]
            major, minor = map(int, version.split('.')[:2])
            
            if major < 3 or (major == 3 and minor < 8):
                print(f"{Colors.RED}✗ Python 3.8+ is required{Colors.NC}")
                print(f"{Colors.YELLOW}Please install Python 3.8 or higher{Colors.NC}")
                return False
            
            print(f"{Colors.GREEN}✓ Python version is adequate{Colors.NC}")
            return True
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error checking Python: {e}{Colors.NC}")
            return False
    
    def create_virtual_environment(self):
        """Create Python virtual environment"""
        print(f"\n{Colors.BLUE}Creating virtual environment...{Colors.NC}")
        
        venv_path = Path('venv')
        
        if venv_path.exists():
            print(f"{Colors.YELLOW}! Virtual environment already exists{Colors.NC}")
            response = input("Do you want to recreate it? (y/N): ").lower()
            
            if response == 'y':
                print("Removing existing virtual environment...")
                shutil.rmtree(venv_path)
            else:
                print("Keeping existing virtual environment")
                return True
        
        try:
            subprocess.run(
                [self.python_cmd, '-m', 'venv', 'venv'],
                check=True
            )
            print(f"{Colors.GREEN}✓ Virtual environment created{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}✗ Failed to create virtual environment: {e}{Colors.NC}")
            return False
    
    def install_dependencies(self):
        """Install Python dependencies"""
        print(f"\n{Colors.BLUE}Installing dependencies...{Colors.NC}")
        
        # Get pip path in venv
        if self.is_windows:
            pip_path = Path('venv/Scripts/pip.exe')
        else:
            pip_path = Path('venv/bin/pip')
        
        if not pip_path.exists():
            print(f"{Colors.RED}✗ pip not found in virtual environment{Colors.NC}")
            return False
        
        try:
            # Upgrade pip
            print("Upgrading pip...")
            subprocess.run(
                [str(pip_path), 'install', '--upgrade', 'pip'],
                check=True,
                capture_output=True
            )
            
            # Check which requirements file to use
            if not Path('requirements.txt').exists():
                print(f"{Colors.RED}✗ requirements.txt not found{Colors.NC}")
                return False
            
            # Try installing with requirements.txt
            print("Installing packages...")
            result = subprocess.run(
                [str(pip_path), 'install', '-r', 'requirements.txt'],
                capture_output=True,
                text=True
            )
            
            # Check for dependency conflicts
            if 'conflict' in result.stderr.lower() or result.returncode != 0:
                print(f"{Colors.YELLOW}! Dependency conflicts detected{Colors.NC}")
                
                # Check if minimal requirements exists
                if Path('requirements-minimal.txt').exists():
                    print(f"{Colors.BLUE}Trying minimal requirements...{Colors.NC}")
                    result = subprocess.run(
                        [str(pip_path), 'install', '-r', 'requirements-minimal.txt'],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        print(f"{Colors.GREEN}✓ Minimal dependencies installed{Colors.NC}")
                        print(f"{Colors.YELLOW}! Some optional features may be limited{Colors.NC}")
                        print(f"{Colors.CYAN}See TROUBLESHOOTING.md for full installation{Colors.NC}")
                        return True
                
                # If still failing, try upgrading key packages first
                print(f"{Colors.BLUE}Upgrading key packages...{Colors.NC}")
                key_packages = ['requests>=2.32.5', 'protobuf>=5.0', 'pytest>=8.2.0']
                for package in key_packages:
                    subprocess.run(
                        [str(pip_path), 'install', '--upgrade', package],
                        capture_output=True
                    )
                
                # Try again
                result = subprocess.run(
                    [str(pip_path), 'install', '-r', 'requirements.txt'],
                    capture_output=True,
                    text=True
                )
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ Dependencies installed{Colors.NC}")
                
                # Check for any remaining conflicts
                check_result = subprocess.run(
                    [str(pip_path), 'check'],
                    capture_output=True,
                    text=True
                )
                
                if check_result.returncode != 0 and check_result.stdout:
                    print(f"{Colors.YELLOW}! Warning: Some dependency conflicts remain{Colors.NC}")
                    print(f"{Colors.CYAN}Run 'pip check' to see details{Colors.NC}")
                    print(f"{Colors.CYAN}See TROUBLESHOOTING.md for solutions{Colors.NC}")
                
                return True
            else:
                print(f"{Colors.RED}✗ Failed to install dependencies{Colors.NC}")
                print(f"{Colors.YELLOW}Error details:{Colors.NC}")
                print(result.stderr[:500])  # Show first 500 chars
                print(f"\n{Colors.CYAN}See TROUBLESHOOTING.md for solutions{Colors.NC}")
                return False
            
        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}✗ Failed to install dependencies: {e}{Colors.NC}")
            print(f"{Colors.CYAN}See TROUBLESHOOTING.md for solutions{Colors.NC}")
            return False
    
    def create_env_file(self):
        """Create .env file from template"""
        print(f"\n{Colors.BLUE}Creating .env file...{Colors.NC}")
        
        if Path('.env').exists():
            print(f"{Colors.YELLOW}! .env file already exists{Colors.NC}")
            return True
        
        if not Path('.env.example').exists():
            print(f"{Colors.YELLOW}! .env.example not found, creating basic .env{Colors.NC}")
            
            basic_env = """# Environment Configuration
ENVIRONMENT=development
DEBUG=True

# LLM Configuration
LLM_API_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL_NAME=llama3
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_TIMEOUT=60

# File Upload Limits
MAX_FILE_SIZE=1000000
MAX_FILES_PER_REQUEST=50

# Streamlit Server
STREAMLIT_SERVER_PORT=8501
"""
            
            with open('.env', 'w') as f:
                f.write(basic_env)
        else:
            shutil.copy('.env.example', '.env')
        
        print(f"{Colors.GREEN}✓ .env file created{Colors.NC}")
        print(f"{Colors.YELLOW}! Please review and edit .env with your settings{Colors.NC}")
        return True
    
    def create_directories(self):
        """Create necessary directories"""
        print(f"\n{Colors.BLUE}Creating directories...{Colors.NC}")
        
        directories = [
            'chat_history',
            'rag_storage',
            'test_outputs',
            'logs',
            'temp_repos',
            'storage'
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
        
        print(f"{Colors.GREEN}✓ Directories created{Colors.NC}")
        return True
    
    def check_git(self):
        """Check if Git is installed"""
        print(f"\n{Colors.BLUE}Checking for Git...{Colors.NC}")
        
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"{Colors.GREEN}✓ {version}{Colors.NC}")
                return True
            
        except FileNotFoundError:
            print(f"{Colors.YELLOW}! Git is not installed{Colors.NC}")
            print(f"{Colors.YELLOW}Git is optional but recommended for repository integration{Colors.NC}")
            
            if self.is_windows:
                print(f"\nDownload Git for Windows: {Colors.CYAN}https://git-scm.com/download/win{Colors.NC}")
            elif self.is_macos:
                print(f"\nInstall Git via Homebrew: {Colors.CYAN}brew install git{Colors.NC}")
            else:
                print(f"\nInstall Git: {Colors.CYAN}sudo apt install git{Colors.NC} or {Colors.CYAN}sudo yum install git{Colors.NC}")
            
            return False
    
    def check_ollama(self):
        """Check if Ollama is installed"""
        print(f"\n{Colors.BLUE}Checking for Ollama...{Colors.NC}")
        
        # Check if ollama command exists
        ollama_cmd = 'ollama.exe' if self.is_windows else 'ollama'
        
        try:
            result = subprocess.run(
                [ollama_cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ Ollama is installed{Colors.NC}")
                return self.check_ollama_service()
            
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        print(f"{Colors.RED}✗ Ollama is not installed{Colors.NC}")
        self.print_ollama_instructions()
        return False
    
    def check_ollama_service(self):
        """Check if Ollama service is running"""
        print(f"{Colors.BLUE}Checking Ollama service...{Colors.NC}")
        
        try:
            # Try to connect to Ollama API
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 11434))
            sock.close()
            
            if result == 0:
                print(f"{Colors.GREEN}✓ Ollama service is running{Colors.NC}")
                return self.check_llama3_model()
            else:
                print(f"{Colors.YELLOW}! Ollama service is not running{Colors.NC}")
                print(f"\n{Colors.CYAN}Start Ollama with:{Colors.NC}")
                if self.is_windows:
                    print(f"  {Colors.WHITE}Just start the Ollama app from Start menu{Colors.NC}")
                else:
                    print(f"  {Colors.WHITE}ollama serve{Colors.NC}")
                return False
                
        except Exception as e:
            print(f"{Colors.YELLOW}! Could not check Ollama service: {e}{Colors.NC}")
            return False
    
    def check_llama3_model(self):
        """Check if Llama3 model is available"""
        print(f"{Colors.BLUE}Checking for Llama3 model...{Colors.NC}")
        
        ollama_cmd = 'ollama.exe' if self.is_windows else 'ollama'
        
        try:
            result = subprocess.run(
                [ollama_cmd, 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if 'llama3' in result.stdout.lower():
                print(f"{Colors.GREEN}✓ Llama3 model is available{Colors.NC}")
                return True
            else:
                print(f"{Colors.YELLOW}! Llama3 model not found{Colors.NC}")
                print(f"\n{Colors.CYAN}Pull Llama3 model with:{Colors.NC}")
                print(f"  {Colors.WHITE}{ollama_cmd} pull llama3{Colors.NC}")
                
                response = input(f"\nPull Llama3 model now? (y/N): ").lower()
                if response == 'y':
                    return self.pull_llama3()
                return False
                
        except Exception as e:
            print(f"{Colors.YELLOW}! Could not check for Llama3: {e}{Colors.NC}")
            return False
    
    def pull_llama3(self):
        """Pull Llama3 model"""
        print(f"\n{Colors.BLUE}Pulling Llama3 model (this may take several minutes)...{Colors.NC}")
        
        ollama_cmd = 'ollama.exe' if self.is_windows else 'ollama'
        
        try:
            process = subprocess.Popen(
                [ollama_cmd, 'pull', 'llama3'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Stream output
            for line in process.stdout:
                print(line, end='')
            
            process.wait()
            
            if process.returncode == 0:
                print(f"{Colors.GREEN}✓ Llama3 model downloaded{Colors.NC}")
                return True
            else:
                print(f"{Colors.RED}✗ Failed to download Llama3{Colors.NC}")
                return False
                
        except Exception as e:
            print(f"{Colors.RED}✗ Error downloading Llama3: {e}{Colors.NC}")
            return False
    
    def print_ollama_instructions(self):
        """Print Ollama installation instructions"""
        print(f"\n{Colors.CYAN}Install Ollama:{Colors.NC}")
        
        if self.is_windows:
            print(f"""
{Colors.WHITE}Windows:{Colors.NC}
1. Download from: {Colors.CYAN}https://ollama.com/download/windows{Colors.NC}
2. Run the installer
3. Ollama will start automatically
4. Then run: {Colors.WHITE}ollama pull llama3{Colors.NC}
""")
        elif self.is_macos:
            print(f"""
{Colors.WHITE}macOS:{Colors.NC}
1. Download from: {Colors.CYAN}https://ollama.com/download/mac{Colors.NC}
   Or via Homebrew: {Colors.WHITE}brew install ollama{Colors.NC}
2. Start Ollama: {Colors.WHITE}ollama serve{Colors.NC}
3. Pull model: {Colors.WHITE}ollama pull llama3{Colors.NC}
""")
        else:
            print(f"""
{Colors.WHITE}Linux:{Colors.NC}
1. Install: {Colors.WHITE}curl -fsSL https://ollama.com/install.sh | sh{Colors.NC}
2. Start service: {Colors.WHITE}ollama serve{Colors.NC}
3. Pull model: {Colors.WHITE}ollama pull llama3{Colors.NC}
""")
    
    def run_tests(self):
        """Run setup tests"""
        print(f"\n{Colors.BLUE}Running tests...{Colors.NC}")
        
        if not Path('test_setup.py').exists():
            print(f"{Colors.YELLOW}! test_setup.py not found, skipping tests{Colors.NC}")
            return True
        
        # Get pytest path in venv
        if self.is_windows:
            pytest_path = Path('venv/Scripts/pytest.exe')
        else:
            pytest_path = Path('venv/bin/pytest')
        
        if not pytest_path.exists():
            print(f"{Colors.YELLOW}! pytest not found, skipping tests{Colors.NC}")
            return True
        
        try:
            result = subprocess.run(
                [str(pytest_path), 'test_setup.py', '-v', '--tb=short'],
                timeout=60
            )
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ All tests passed{Colors.NC}")
                return True
            else:
                print(f"{Colors.YELLOW}! Some tests failed (this is okay for first setup){Colors.NC}")
                return True
                
        except subprocess.TimeoutExpired:
            print(f"{Colors.YELLOW}! Tests timed out{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.YELLOW}! Could not run tests: {e}{Colors.NC}")
            return True
    
    def print_summary(self):
        """Print setup summary and next steps"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.GREEN}Setup Complete!{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")
        
        print(f"{Colors.WHITE}Next Steps:{Colors.NC}\n")
        
        # Step 1: Activate virtual environment
        print(f"{Colors.YELLOW}1. Activate virtual environment:{Colors.NC}")
        if self.is_windows:
            print(f"   {Colors.WHITE}venv\\Scripts\\activate{Colors.NC}")
        else:
            print(f"   {Colors.WHITE}source venv/bin/activate{Colors.NC}")
        
        # Step 2: Start Ollama
        print(f"\n{Colors.YELLOW}2. Make sure Ollama is running:{Colors.NC}")
        if self.is_windows:
            print(f"   {Colors.WHITE}Start Ollama from Start menu{Colors.NC}")
        else:
            print(f"   {Colors.WHITE}ollama serve{Colors.NC}")
        
        # Step 3: Start application
        print(f"\n{Colors.YELLOW}3. Start the application:{Colors.NC}")
        print(f"   {Colors.WHITE}streamlit run app.py{Colors.NC}")
        print(f"   {Colors.CYAN}Or use CLI: {Colors.WHITE}python cli.py --help{Colors.NC}")
        
        # Docker alternative
        print(f"\n{Colors.YELLOW}Alternative with Docker:{Colors.NC}")
        print(f"   {Colors.WHITE}docker-compose up{Colors.NC}")
        
        # Documentation
        print(f"\n{Colors.YELLOW}Documentation:{Colors.NC}")
        print(f"   - Full guide: {Colors.CYAN}README.md{Colors.NC}")
        print(f"   - Quick start: {Colors.CYAN}QUICKSTART.md{Colors.NC}")
        
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}\n")
    
    def run(self):
        """Run the complete setup process"""
        self.print_header()
        
        steps = [
            ("Python Version", self.check_python_version),
            ("Virtual Environment", self.create_virtual_environment),
            ("Dependencies", self.install_dependencies),
            ("Environment File", self.create_env_file),
            ("Directories", self.create_directories),
            ("Git", self.check_git),
            ("Ollama", self.check_ollama),
            ("Tests", self.run_tests),
        ]
        
        failed_steps = []
        
        for step_name, step_func in steps:
            try:
                if not step_func():
                    failed_steps.append(step_name)
            except Exception as e:
                print(f"{Colors.RED}✗ Error in {step_name}: {e}{Colors.NC}")
                failed_steps.append(step_name)
        
        # Print summary
        self.print_summary()
        
        # Report any failed steps
        if failed_steps:
            print(f"{Colors.YELLOW}Note: The following steps need attention:{Colors.NC}")
            for step in failed_steps:
                print(f"  - {step}")
            print()


def main():
    """Main entry point"""
    try:
        setup = SetupManager()
        setup.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup interrupted by user{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Setup failed with error: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()