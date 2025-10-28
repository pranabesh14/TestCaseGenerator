import os
import shutil
import stat
from pathlib import Path
from typing import List, Optional
import subprocess
import tempfile

class GitHandler:
    """Handle Git repository operations with smart update/pull functionality"""
    
    def __init__(self):
        self.repos_dir = Path("temp_repos")
        self.repos_dir.mkdir(exist_ok=True)
        
        # Supported code file extensions
        self.code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
            '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala',
            '.r', '.m', '.h', '.hpp'
        }
    
    def _handle_remove_readonly(self, func, path, exc):
        """
        Error handler for Windows readonly files
        Used with shutil.rmtree to handle permission errors
        """
        if func in (os.unlink, os.rmdir):
            # Clear the readonly bit and retry
            os.chmod(path, stat.S_IWRITE)
            func(path)
        else:
            raise
    
    def _safe_rmtree(self, path: Path) -> bool:
        """
        Safely remove directory tree, handling Windows file locks
        
        Args:
            path: Path to remove
            
        Returns:
            True if successful, False otherwise
        """
        if not path.exists():
            return True
        
        try:
            # On Windows, use onerror handler for readonly files
            shutil.rmtree(path, onerror=self._handle_remove_readonly)
            return True
        except Exception as e:
            print(f"⚠️  Warning: Could not remove {path}: {e}")
            
            # Try alternative approach: rename then delete
            try:
                import uuid
                temp_name = path.parent / f"_delete_{uuid.uuid4().hex[:8]}"
                path.rename(temp_name)
                shutil.rmtree(temp_name, onerror=self._handle_remove_readonly)
                return True
            except:
                pass
            
            return False
    
    def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        depth: int = 1,
        force_fresh: bool = False
    ) -> Path:
        """
        Clone a Git repository or update if it already exists
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone/pull
            depth: Clone depth (1 for shallow clone)
            force_fresh: If True, remove existing repo and clone fresh
            
        Returns:
            Path to cloned repository
        """
        # Sanitize repo name
        repo_name = self._sanitize_repo_name(repo_url)
        repo_path = self.repos_dir / repo_name
        
        # If force_fresh is True, remove existing repo
        if force_fresh and repo_path.exists():
            print(f"🗑️  Removing existing repository for fresh clone...")
            if not self._safe_rmtree(repo_path):
                raise Exception(f"Failed to remove existing repository. Please manually delete '{repo_path}' and try again.")
        
        # Check if repository already exists locally
        if repo_path.exists() and (repo_path / '.git').exists():
            # Repository exists - try to update it
            print(f"📦 Repository already exists at {repo_path}")
            
            try:
                return self._update_repository(repo_path, branch)
            except Exception as e:
                print(f"⚠️  Update failed: {str(e)}")
                print(f"💡 Tip: You can continue using the existing code, or manually delete '{repo_path}' to clone fresh.")
                
                # Don't try to remove - just return existing path
                # User can still work with existing code
                print(f"✅ Using existing repository (may not be latest version)")
                return repo_path
        
        # Clone repository fresh
        try:
            print(f"📥 Cloning repository from {repo_url}...")
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
            
            print(f"✅ Successfully cloned repository")
            return repo_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Git clone operation timed out")
        except Exception as e:
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def _update_repository(self, repo_path: Path, branch: str) -> Path:
        """
        Update an existing repository with latest changes
        
        Args:
            repo_path: Path to existing repository
            branch: Branch to update
            
        Returns:
            Path to updated repository
        """
        try:
            # First, check if we're in a valid git repo
            check_result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if check_result.returncode != 0:
                raise Exception("Not a valid git repository")
            
            print(f"🔄 Fetching latest changes from origin/{branch}...")
            
            # Fetch latest changes
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin', branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if fetch_result.returncode != 0:
                raise Exception(f"Git fetch failed: {fetch_result.stderr}")
            
            # Get current and remote commit hashes to check for changes
            current_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if current_result.returncode != 0:
                raise Exception("Could not get current commit hash")
            
            current_hash = current_result.stdout.strip()
            
            remote_result = subprocess.run(
                ['git', 'rev-parse', f'origin/{branch}'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if remote_result.returncode != 0:
                raise Exception(f"Could not get remote commit hash for branch {branch}")
            
            remote_hash = remote_result.stdout.strip()
            
            if current_hash == remote_hash:
                print(f"✅ Repository is already up to date (commit: {current_hash[:7]})")
                return repo_path
            
            # There are changes - update
            print(f"📥 Updating from {current_hash[:7]} to {remote_hash[:7]}...")
            
            # Stash any local changes first (just in case)
            subprocess.run(
                ['git', 'stash'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Reset to latest origin/branch
            reset_result = subprocess.run(
                ['git', 'reset', '--hard', f'origin/{branch}'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if reset_result.returncode != 0:
                raise Exception(f"Git reset failed: {reset_result.stderr}")
            
            # Clean any untracked files
            clean_result = subprocess.run(
                ['git', 'clean', '-fd'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if clean_result.returncode != 0:
                print(f"⚠️  Warning: Git clean had issues: {clean_result.stderr}")
            
            print(f"✅ Successfully updated repository to latest {branch}")
            return repo_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Git update operation timed out")
        except Exception as e:
            raise Exception(f"Update failed: {str(e)}")
    
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
        """
        Clean up cloned repositories
        
        Args:
            repo_path: Specific repo to clean, or None to keep all repos
        """
        if repo_path and repo_path.exists():
            if self._safe_rmtree(repo_path):
                print(f"✅ Cleaned up repository: {repo_path}")
            else:
                print(f"⚠️  Could not clean up {repo_path} - you may need to delete it manually")
    
    def get_commit_info(self, repo_path: Path) -> dict:
        """Get latest commit information"""
        try:
            # Get latest commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%B'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_message = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%an'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            author = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%ai'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            date = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            return {
                'hash': commit_hash[:7],
                'full_hash': commit_hash,
                'message': commit_message,
                'author': author,
                'date': date
            }
        except Exception:
            return {
                'hash': 'unknown',
                'full_hash': 'unknown',
                'message': 'unknown',
                'author': 'unknown',
                'date': 'unknown'
            }
    
    def check_for_changes(self, repo_path: Path, old_hash: str) -> dict:
        """
        Check what changed between old commit and current
        
        Args:
            repo_path: Path to repository
            old_hash: Previous commit hash
            
        Returns:
            Dictionary with change information
        """
        try:
            current_info = self.get_commit_info(repo_path)
            
            if current_info['full_hash'] == old_hash:
                return {
                    'has_changes': False,
                    'files_changed': 0,
                    'changed_files': []
                }
            
            # Get list of changed files
            result = subprocess.run(
                ['git', 'diff', '--name-only', old_hash, 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                changed_files = [f for f in result.stdout.split('\n') if f.strip()]
                return {
                    'has_changes': True,
                    'files_changed': len(changed_files),
                    'changed_files': changed_files,
                    'old_commit': old_hash[:7],
                    'new_commit': current_info['hash']
                }
            
            return {
                'has_changes': True,
                'files_changed': 0,
                'changed_files': []
            }
            
        except Exception as e:
            return {
                'has_changes': False,
                'error': str(e)
            }
    
    def force_clean_repo(self, repo_name: str) -> bool:
        """
        Force clean a specific repository (for manual cleanup)
        
        Args:
            repo_name: Name of the repository folder
            
        Returns:
            True if successful
        """
        repo_path = self.repos_dir / repo_name
        
        if not repo_path.exists():
            print(f"Repository '{repo_name}' does not exist")
            return True
        
        print(f"🗑️  Force cleaning repository: {repo_name}")
        
        if self._safe_rmtree(repo_path):
            print(f"✅ Successfully removed {repo_name}")
            return True
        else:
            print(f"❌ Failed to remove {repo_name}")
            print(f"💡 Try closing any programs that might be using files in: {repo_path}")
            print(f"   Then manually delete the folder or restart your computer")
            return False