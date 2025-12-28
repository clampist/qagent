"""Mid-level Git tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool


class GitCloneTool(MCPTool):
    """Clone a git repository."""
    
    def __init__(self):
        super().__init__(
            name="git_clone",
            description="Clone a git repository to a local path",
            tool_type="mid"
        )
    
    async def execute(self, repo_url: str, target_path: str, branch: str = "main") -> Dict[str, Any]:
        """Clone repository."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "clone", "-b", branch, repo_url, target_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_url": {"type": "string", "description": "Repository URL"},
                "target_path": {"type": "string", "description": "Target directory path"},
                "branch": {"type": "string", "description": "Branch name", "default": "main"}
            },
            "required": ["repo_url", "target_path"]
        }


class GitCommitTool(MCPTool):
    """Commit changes to git."""
    
    def __init__(self):
        super().__init__(
            name="git_commit",
            description="Commit changes to git repository",
            tool_type="mid"
        )
    
    async def execute(self, repo_path: str, message: str, files: list = None) -> Dict[str, Any]:
        """Commit changes."""
        import subprocess
        try:
            # Add files
            if files:
                subprocess.run(
                    ["git", "-C", repo_path, "add"] + files,
                    check=True,
                    timeout=60
                )
            else:
                subprocess.run(
                    ["git", "-C", repo_path, "add", "."],
                    check=True,
                    timeout=60
                )
            
            # Commit
            result = subprocess.run(
                ["git", "-C", repo_path, "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Repository path"},
                "message": {"type": "string", "description": "Commit message"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to commit (empty for all)"
                }
            },
            "required": ["repo_path", "message"]
        }


class GitPushTool(MCPTool):
    """Push changes to remote repository."""
    
    def __init__(self):
        super().__init__(
            name="git_push",
            description="Push commits to remote repository",
            tool_type="mid"
        )
    
    async def execute(self, repo_path: str, remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """Push to remote."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "push", remote, branch],
                capture_output=True,
                text=True,
                timeout=300
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Repository path"},
                "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                "branch": {"type": "string", "description": "Branch name", "default": "main"}
            },
            "required": ["repo_path"]
        }


class GitDiffTool(MCPTool):
    """Get git diff of code changes."""
    
    def __init__(self):
        super().__init__(
            name="git_diff",
            description="Get git diff of code changes between branches",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        base_ref: str = "origin/main",
        head_ref: str = "HEAD",
        file_patterns: List[str] = None
    ) -> Dict[str, Any]:
        """Get git diff.
        
        Args:
            workspace_path: Workspace path
            base_ref: Base reference (default: origin/main)
            head_ref: Head reference (default: HEAD)
            file_patterns: File patterns to include (default: code files)
            
        Returns:
            Dictionary with diff output
        """
        import subprocess
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        if file_patterns is None:
            file_patterns = ["*.py", "*.tsx", "*.ts", "*.jsx", "*.js"]
        
        try:
            # Change to workspace directory
            original_dir = os.getcwd()
            os.chdir(workspace_path)
            
            # Get diff for specified file patterns
            result = subprocess.run(
                [
                    "git", "diff", f"{base_ref}..{head_ref}", "--"
                ] + file_patterns,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            os.chdir(original_dir)
            
            if result.returncode == 0:
                diff_output = result.stdout or "No code changes detected"
                return {
                    "success": True,
                    "diff": diff_output,
                    "length": len(diff_output)
                }
            else:
                # Fallback: try diff without base_ref (use HEAD~1)
                os.chdir(workspace_path)
                result = subprocess.run(
                    ["git", "diff", "HEAD~1", "--"] + file_patterns,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                os.chdir(original_dir)
                
                diff_output = result.stdout or "No code changes detected"
                return {
                    "success": True,
                    "diff": diff_output,
                    "length": len(diff_output),
                    "fallback_used": True
                }
                
        except Exception as e:
            logger.warning(f"Failed to get git diff: {e}")
            return {
                "success": False,
                "error": str(e),
                "diff": "Git diff unavailable"
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "base_ref": {"type": "string", "description": "Base reference", "default": "origin/main"},
                "head_ref": {"type": "string", "description": "Head reference", "default": "HEAD"},
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to include"
                }
            },
            "required": ["workspace_path"]
        }


class GitChangedFilesTool(MCPTool):
    """Get list of changed files from git diff."""
    
    def __init__(self):
        super().__init__(
            name="git_changed_files",
            description="Get list of changed files from git diff",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        base_ref: str = "origin/main",
        head_ref: str = "HEAD",
        file_patterns: List[str] = None
    ) -> Dict[str, Any]:
        """Get changed files.
        
        Args:
            workspace_path: Workspace path
            base_ref: Base reference (default: origin/main)
            head_ref: Head reference (default: HEAD)
            file_patterns: File patterns to include (default: code files)
            
        Returns:
            Dictionary with list of changed files
        """
        import subprocess
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        if file_patterns is None:
            file_patterns = ["*.py", "*.tsx", "*.ts", "*.jsx", "*.js"]
        
        try:
            # Change to workspace directory
            original_dir = os.getcwd()
            os.chdir(workspace_path)
            
            # Get changed files using git diff --stat --name-only
            result = subprocess.run(
                [
                    "git", "diff", "--stat", "--name-only",
                    f"{base_ref}..{head_ref}", "--"
                ] + file_patterns,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            os.chdir(original_dir)
            
            if result.returncode == 0 and result.stdout:
                # Parse file list (one per line)
                files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                logger.info(f"Git diff found {len(files)} changed files")
                return {
                    "success": True,
                    "files": files,
                    "count": len(files)
                }
            else:
                # Fallback: try diff without base_ref (use HEAD~1)
                os.chdir(workspace_path)
                result = subprocess.run(
                    [
                        "git", "diff", "--stat", "--name-only",
                        "HEAD~1", "--"
                    ] + file_patterns,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                os.chdir(original_dir)
                
                if result.returncode == 0 and result.stdout:
                    files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                    logger.info(f"Git diff (fallback) found {len(files)} changed files")
                    return {
                        "success": True,
                        "files": files,
                        "count": len(files),
                        "fallback_used": True
                    }
                else:
                    logger.warning("No changed files detected by git diff")
                    return {
                        "success": True,
                        "files": [],
                        "count": 0
                    }
                    
        except Exception as e:
            logger.warning(f"Failed to get git changed files: {e}")
            return {
                "success": False,
                "error": str(e),
                "files": [],
                "count": 0
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "base_ref": {"type": "string", "description": "Base reference", "default": "origin/main"},
                "head_ref": {"type": "string", "description": "Head reference", "default": "HEAD"},
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to include"
                }
            },
            "required": ["workspace_path"]
        }


class FrontendGitDiffTool(MCPTool):
    """Get git diff for frontend files (TS/TSX/JS/JSX)."""
    
    def __init__(self):
        super().__init__(
            name="frontend_git_diff",
            description="Get git diff for frontend files (TS/TSX/JS/JSX)",
            tool_type="mid"
        )
    
    async def execute(self, workspace_path: str) -> Dict[str, Any]:
        """Get git diff for frontend files.
        
        Args:
            workspace_path: Workspace path
            
        Returns:
            Dictionary with git diff output
        """
        import subprocess
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Change to workspace directory
            original_dir = os.getcwd()
            os.chdir(workspace_path)
            
            # Get diff for frontend files (TS, TSX, JS, JSX)
            result = subprocess.run(
                [
                    "git", "diff", "origin/main..HEAD", "--",
                    "*.ts", "*.tsx", "*.js", "*.jsx"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            os.chdir(original_dir)
            
            if result.returncode == 0:
                diff_output = result.stdout or "No code changes detected in frontend files"
                logger.info(f"Git diff retrieved: {len(diff_output)} characters")
                return {
                    "success": True,
                    "diff": diff_output,
                    "length": len(diff_output)
                }
            else:
                # Fallback: try diff without origin/main
                os.chdir(workspace_path)
                result = subprocess.run(
                    ["git", "diff", "HEAD~1", "--", "*.ts", "*.tsx", "*.js", "*.jsx"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                os.chdir(original_dir)
                diff_output = result.stdout or "No code changes detected in frontend files"
                logger.info(f"Git diff (fallback) retrieved: {len(diff_output)} characters")
                return {
                    "success": True,
                    "diff": diff_output,
                    "length": len(diff_output),
                    "fallback_used": True
                }
                
        except Exception as e:
            logger.warning(f"Failed to get git diff: {e}")
            return {
                "success": False,
                "error": str(e),
                "diff": "Git diff unavailable"
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"}
            },
            "required": ["workspace_path"]
        }

