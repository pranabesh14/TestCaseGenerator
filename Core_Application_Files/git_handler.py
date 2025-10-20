import os
import shutil
from pathlib import Path
from typing import List, Optional
import subprocess
import tempfile

class GitHandler:
    """Handle Git repository operations"""
    
    def __init__(self):
        self.repos_dir = Path("temp_repos")
        self.repos_dir.mkdir(exist_ok=True)
        
        # Supported code file extensions
        self.code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
            '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala',
            '.r', '.m', '.h', '.hpp'
        }
    
    def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        depth: int = 1
    ) -> Path:
        """
        Clone a Git repository
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone
            depth: Clone depth (1 for shallow clone)
            
        Returns:
            Path to cloned repository
        """
        # Sanitize repo name
        repo_name = self._sanitize_repo_name(repo_url)
        repo_path = self.repos_dir / repo_name
        
        # Remove if exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        # Clone repository
        try:
            cmd = [
                'git', 'clone',
                '--branch', branch,
                '--depth', str(depth),
                repo_url,
                str(repo_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            return repo_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Git clone operation timed out")
        except Exception as e:
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def get_code_files(self, repo_path: Path, max_files: int = 100) -> List[Path]:
        """
        Get all code files from repository
        
        Args:
            repo_path: Path to repository
            max_files: Maximum number of files to return
            
        Returns:
            List of code file paths
        """
        code_files = []
        
        # Exclude common directories
        exclude_dirs = {
            '.git', 'node_modules', 'venv', '.venv', 'env',
            '__pycache__', 'dist', 'build', 'target', '.idea',
            'vendor', 'deps', '.next'
        }
        
        for root, dirs, files in os.walk(repo_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check if it's a code file
                if file_path.suffix.lower() in self.code_extensions:
                    # Skip very large files (> 1MB)
                    if file_path.stat().st_size < 1_000_000:
                        code_files.append(file_path)
                        
                        if len(code_files) >= max_files:
                            return code_files
        
        return code_files
    
    def get_repo_structure(self, repo_path: Path) -> dict:
        """Get repository structure information"""
        structure = {
            'total_files': 0,
            'code_files': 0,
            'directories': 0,
            'file_types': {},
            'languages': set()
        }
        
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.rs': 'Rust',
        }
        
        for root, dirs, files in os.walk(repo_path):
            if '.git' not in root:
                structure['directories'] += len(dirs)
                structure['total_files'] += len(files)
                
                for file in files:
                    ext = Path(file).suffix.lower()
                    
                    if ext in self.code_extensions:
                        structure['code_files'] += 1
                        structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                        
                        if ext in language_map:
                            structure['languages'].add(language_map[ext])
        
        structure['languages'] = list(structure['languages'])
        return structure
    
    def _sanitize_repo_name(self, repo_url: str) -> str:
        """Extract and sanitize repository name from URL"""
        # Extract repo name from URL
        name = repo_url.rstrip('/').split('/')[-1]
        
        # Remove .git extension
        if name.endswith('.git'):
            name = name[:-4]
        
        # Remove invalid characters
        name = ''.join(c for c in name if c.isalnum() or c in '-_')
        
        return name or 'repo'
    
    def get_file_content(self, file_path: Path) -> Optional[str]:
        """
        Read file content safely
        
        Args:
            file_path: Path to file
            
        Returns:
            File content or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None
    
    def cleanup(self, repo_path: Path = None):
        """Clean up cloned repositories"""
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path)
        elif self.repos_dir.exists():
            shutil.rmtree(self.repos_dir)
            self.repos_dir.mkdir(exist_ok=True)
    
    def get_commit_info(self, repo_path: Path) -> dict:
        """Get latest commit information"""
        try:
            # Get latest commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%B'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            commit_message = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%an'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            author = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            return {
                'hash': commit_hash[:7],
                'message': commit_message,
                'author': author
            }
        except Exception:
            return {
                'hash': 'unknown',
                'message': 'unknown',
                'author': 'unknown'
            }