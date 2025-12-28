"""Workspace management for repository cloning."""
from typing import Optional
import os
import shutil
from app.config import settings
from app.mcp.tools.mid_level.git_tools import GitCloneTool


class WorkspaceManager:
    """Manages workspace directories for repositories."""
    
    def __init__(self):
        self.base_path = settings.workspace_base_path
        self.git_tool = GitCloneTool()
        os.makedirs(self.base_path, exist_ok=True)
    
    async def clone_repo(
        self,
        repo_full_name: str,
        pr_number: int,
        branch: str = None
    ) -> str:
        """Clone repository to workspace."""
        # Create workspace directory
        workspace_name = f"{repo_full_name.replace('/', '_')}_pr{pr_number}"
        workspace_path = os.path.join(self.base_path, workspace_name)
        
        # Remove existing workspace if present
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
        
        os.makedirs(workspace_path, exist_ok=True)
        
        # Clone repository
        repo_url = f"https://github.com/{repo_full_name}.git"
        result = await self.git_tool.execute(
            repo_url=repo_url,
            target_path=workspace_path,
            branch=branch or "main"
        )
        
        if not result.get("success"):
            raise Exception(f"Failed to clone repository: {result.get('error')}")
        
        return workspace_path
    
    async def cleanup_workspace(self, workspace_path: str) -> bool:
        """Clean up workspace directory."""
        try:
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path)
            return True
        except Exception:
            return False
    
    def get_workspace_path(self, repo_full_name: str, pr_number: int) -> str:
        """Get workspace path without cloning."""
        workspace_name = f"{repo_full_name.replace('/', '_')}_pr{pr_number}"
        return os.path.join(self.base_path, workspace_name)

