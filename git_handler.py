"""
Git Handler with enhanced error handling, logging, and auto-branch detection
"""
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict
import subprocess
import tempfile
from logger import get_app_logger

logger = get_app_logger("git_handler")

class GitHandler:
    """Handle Git repository operations with comprehensive logging"""
    
    def __init__(self):
        self.repos_dir = Path("temp_repos")
        self.repos_dir.mkdir(exist_ok=True)
        
        # Supported code file extensions
        self.code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
            '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala',
            '.r', '.m', '.h', '.hpp', '.cc', '.cxx'
        }
        
        logger.info(" GitHandler initialized")
        logger.info(f"📁 Repository directory: {self.repos_dir.absolute()}")
        
        # Check if git is available
        self._check_git_availability()
    
    def _check_git_availability(self) -> bool:
        """Check if git is installed and available"""
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f" Git is available: {version}")
                return True
            else:
                logger.error(" Git is not available")
                return False
                
        except FileNotFoundError:
            logger.error(" Git is not installed on this system")
            return False
        except Exception as e:
            logger.error(f" Error checking git availability: {e}")
            return False
    
    def get_default_branch(self, repo_url: str) -> str:
        """
        Detect the default branch of a remote repository
        
        Args:
            repo_url: URL of the Git repository
            
        Returns:
            Default branch name (e.g., 'main', 'master')
        """
        logger.info(f" Detecting default branch for {repo_url}")
        
        try:
            # Use git ls-remote to find the default branch
            cmd = ['git', 'ls-remote', '--symref', repo_url, 'HEAD']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse output: "ref: refs/heads/main	HEAD"
                output = result.stdout.strip()
                if output:
                    # Extract branch name from first line
                    first_line = output.split('\n')[0]
                    if 'refs/heads/' in first_line:
                        branch = first_line.split('refs/heads/')[1].split('\t')[0]
                        logger.info(f" Default branch detected: {branch}")
                        return branch
            
            # If detection failed, try common branch names
            logger.warning("⚠️ Could not detect default branch, trying common names...")
            
            # Try to list all branches
            cmd = ['git', 'ls-remote', '--heads', repo_url]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                branches = []
                for line in result.stdout.strip().split('\n'):
                    if 'refs/heads/' in line:
                        branch_name = line.split('refs/heads/')[1]
                        branches.append(branch_name)
                
                logger.info(f" Available branches: {', '.join(branches)}")
                
                # Prioritize common default branch names
                for preferred in ['main', 'master', 'develop', 'dev']:
                    if preferred in branches:
                        logger.info(f" Using branch: {preferred}")
                        return preferred
                
                # If no common names found, use the first branch
                if branches:
                    logger.info(f" Using first available branch: {branches[0]}")
                    return branches[0]
            
            # Final fallback
            logger.warning("⚠️ Using fallback branch: main")
            return 'main'
            
        except subprocess.TimeoutExpired:
            logger.error(" Timeout while detecting branch")
            return 'main'
        except Exception as e:
            logger.error(f" Error detecting branch: {e}")
            return 'main'
    
    def clone_repository(
        self,
        repo_url: str,
        branch: str = None,
        depth: int = 1
    ) -> Path:
        """
        Clone a Git repository with auto-detection of default branch
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone (None = auto-detect)
            depth: Clone depth (1 for shallow clone)
            
        Returns:
            Path to cloned repository
        """
        logger.info("="*60)
        logger.info(f"🔗 Cloning Git repository")
        logger.info(f"   URL: {repo_url}")
        logger.info(f"   Branch: {branch if branch else 'auto-detect'}")
        logger.info(f"   Depth: {depth}")
        logger.info("="*60)
        
        # Auto-detect branch if not specified or if 'main' is specified
        if not branch or branch == 'main':
            detected_branch = self.get_default_branch(repo_url)
            if detected_branch:
                branch = detected_branch
                logger.info(f" Using detected branch: {branch}")
        
        # Sanitize repo name
        repo_name = self._sanitize_repo_name(repo_url)
        repo_path = self.repos_dir / repo_name
        
        # Remove if exists
        if repo_path.exists():
            logger.info(f"🗑️ Removing existing repository at {repo_path}")
            shutil.rmtree(repo_path)
        
        # Try to clone with the detected/specified branch
        try:
            cmd = [
                'git', 'clone',
                '--branch', branch,
                '--depth', str(depth),
                '--single-branch',
                repo_url,
                str(repo_path)
            ]
            
            logger.info(f"⚙️ Running command: git clone --branch {branch} ...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                
                # If branch not found, try without branch specification
                if 'not found' in error_msg.lower() or 'does not exist' in error_msg.lower():
                    logger.warning(f"⚠️ Branch '{branch}' not found, trying without branch specification...")
                    
                    # Clone without branch specification (gets default)
                    cmd = [
                        'git', 'clone',
                        '--depth', str(depth),
                        repo_url,
                        str(repo_path)
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if result.returncode != 0:
                        error_msg = result.stderr or result.stdout
                        logger.error(f" Git clone failed with code {result.returncode}")
                        logger.error(f"   Error: {error_msg}")
                        raise Exception(f"Git clone failed: {error_msg}")
                else:
                    logger.error(f" Git clone failed with code {result.returncode}")
                    logger.error(f"   Error: {error_msg}")
                    raise Exception(f"Git clone failed: {error_msg}")
            
            logger.info(f" Repository cloned successfully to {repo_path}")
            
            # Get commit info
            commit_info = self.get_commit_info(repo_path)
            logger.info(f"  Latest commit: {commit_info['hash']} by {commit_info['author']}")
            
            # Get actual branch name
            actual_branch = self.get_current_branch(repo_path)
            logger.info(f"🌿 Current branch: {actual_branch}")
            
            return repo_path
            
        except subprocess.TimeoutExpired:
            logger.error(" Git clone operation timed out (5 minutes)")
            raise Exception("Git clone operation timed out")
        except FileNotFoundError:
            logger.error(" Git command not found - is Git installed?")
            raise Exception("Git is not installed on this system")
        except Exception as e:
            logger.error(f" Failed to clone repository: {str(e)}", exc_info=True)
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def get_current_branch(self, repo_path: Path) -> str:
        """Get the current branch name of a cloned repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Error getting current branch: {e}")
            return 'unknown'
    
    def get_code_files(self, repo_path: Path, max_files: int = 100) -> List[Path]:
        """
        Get all code files from repository
        
        Args:
            repo_path: Path to repository
            max_files: Maximum number of files to return
            
        Returns:
            List of code file paths
        """
        logger.info(f" Scanning for code files in {repo_path.name}")
        
        code_files = []
        
        # Exclude common directories
        exclude_dirs = {
            '.git', 'node_modules', 'venv', '.venv', 'env', '__pycache__',
            'dist', 'build', 'target', '.idea', 'vendor', 'deps', '.next',
            'coverage', '.pytest_cache', '.mypy_cache', 'bin', 'obj',
            'packages', '.gradle', '.vs', 'Debug', 'Release'
        }
        
        file_count_by_ext = {}
        
        try:
            for root, dirs, files in os.walk(repo_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                for file in files:
                    file_path = Path(root) / file
                    ext = file_path.suffix.lower()
                    
                    # Check if it's a code file
                    if ext in self.code_extensions:
                        # Skip very large files (> 1MB)
                        try:
                            file_size = file_path.stat().st_size
                            if file_size < 1_000_000:
                                code_files.append(file_path)
                                file_count_by_ext[ext] = file_count_by_ext.get(ext, 0) + 1
                                
                                if len(code_files) >= max_files:
                                    logger.warning(f"⚠️ Reached maximum file limit ({max_files})")
                                    break
                            else:
                                logger.debug(f"⏭️ Skipping large file: {file_path.name} ({file_size/1024:.1f} KB)")
                        except Exception as e:
                            logger.warning(f"⚠️ Error checking file {file_path}: {e}")
                            continue
                
                if len(code_files) >= max_files:
                    break
        
        except Exception as e:
            logger.error(f" Error scanning repository: {e}", exc_info=True)
        
        # Log summary
        logger.info(f" Found {len(code_files)} code files:")
        for ext, count in sorted(file_count_by_ext.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   • {ext}: {count} files")
        
        return code_files
    
    def get_repo_structure(self, repo_path: Path) -> Dict:
        """Get repository structure information"""
        logger.info(f"  Analyzing repository structure: {repo_path.name}")
        
        structure = {
            'total_files': 0,
            'code_files': 0,
            'directories': 0,
            'file_types': {},
            'languages': set(),
            'total_size': 0
        }
        
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.cc': 'C++',
            '.cxx': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.cs': 'C#',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.rs': 'Rust',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
        }
        
        try:
            for root, dirs, files in os.walk(repo_path):
                if '.git' not in root:
                    structure['directories'] += len(dirs)
                    structure['total_files'] += len(files)
                    
                    for file in files:
                        file_path = Path(root) / file
                        ext = file_path.suffix.lower()
                        
                        try:
                            file_size = file_path.stat().st_size
                            structure['total_size'] += file_size
                            
                            if ext in self.code_extensions:
                                structure['code_files'] += 1
                                structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                                
                                if ext in language_map:
                                    structure['languages'].add(language_map[ext])
                        except:
                            continue
        
        except Exception as e:
            logger.error(f" Error analyzing structure: {e}")
        
        structure['languages'] = sorted(list(structure['languages']))
        
        logger.info(f"  Repository Statistics:")
        logger.info(f"   • Total files: {structure['total_files']}")
        logger.info(f"   • Code files: {structure['code_files']}")
        logger.info(f"   • Directories: {structure['directories']}")
        logger.info(f"   • Total size: {structure['total_size']/1024/1024:.2f} MB")
        logger.info(f"   • Languages: {', '.join(structure['languages'])}")
        
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
        
        result = name or 'repo'
        logger.debug(f" Sanitized repo name: {result}")
        
        return result
    
    def get_file_content(self, file_path: Path) -> Optional[str]:
        """
        Read file content safely
        
        Args:
            file_path: Path to file
            
        Returns:
            File content or None if error
        """
        try:
            logger.debug(f"📖 Reading file: {file_path.name}")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                logger.debug(f" Read {len(content)} characters from {file_path.name}")
                return content
        except Exception as e:
            logger.error(f" Error reading file {file_path}: {e}")
            return None
    
    def cleanup(self, repo_path: Path = None):
        """Clean up cloned repositories"""
        try:
            if repo_path and repo_path.exists():
                logger.info(f" Cleaning up repository: {repo_path}")
                shutil.rmtree(repo_path)
                logger.info(" Cleanup completed")
            elif self.repos_dir.exists():
                logger.info(f" Cleaning up all repositories in {self.repos_dir}")
                shutil.rmtree(self.repos_dir)
                self.repos_dir.mkdir(exist_ok=True)
                logger.info(" All repositories cleaned up")
        except Exception as e:
            logger.error(f" Error during cleanup: {e}")
    
    def get_commit_info(self, repo_path: Path) -> Dict:
        """Get latest commit information"""
        logger.debug(f" Retrieving commit info from {repo_path.name}")
        
        try:
            # Get latest commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%B'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commit_message = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%an'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            author = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%ai'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            date = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            info = {
                'hash': commit_hash[:7],
                'full_hash': commit_hash,
                'message': commit_message[:100] + '...' if len(commit_message) > 100 else commit_message,
                'author': author,
                'date': date
            }
            
            logger.debug(f" Commit info retrieved: {info['hash']}")
            
            return info
            
        except Exception as e:
            logger.error(f" Error getting commit info: {e}")
            return {
                'hash': 'unknown',
                'full_hash': 'unknown',
                'message': 'unknown',
                'author': 'unknown',
                'date': 'unknown'
            }
    
    def get_branch_list(self, repo_path: Path) -> List[str]:
        """Get list of branches in repository"""
        try:
            result = subprocess.run(
                ['git', 'branch', '-r'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                branches = [
                    line.strip().replace('origin/', '') 
                    for line in result.stdout.split('\n') 
                    if line.strip() and 'HEAD' not in line
                ]
                logger.info(f" Found {len(branches)} branches")
                return branches
            
        except Exception as e:
            logger.error(f" Error getting branch list: {e}")
        
        return []
    
    def list_available_branches(self, repo_url: str) -> List[str]:
        """
        List all available branches in a remote repository
        
        Args:
            repo_url: URL of the Git repository
            
        Returns:
            List of branch names
        """
        logger.info(f" Listing branches for {repo_url}")
        
        try:
            cmd = ['git', 'ls-remote', '--heads', repo_url]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                branches = []
                for line in result.stdout.strip().split('\n'):
                    if 'refs/heads/' in line:
                        branch_name = line.split('refs/heads/')[1]
                        branches.append(branch_name)
                
                logger.info(f" Found {len(branches)} branches: {', '.join(branches[:5])}")
                return branches
            
            return []
            
        except Exception as e:
            logger.error(f" Error listing branches: {e}")
            return []