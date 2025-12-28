"""Workspace management agent using LangChain agent framework."""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.infrastructure.workspace import WorkspaceManager
import logging

logger = logging.getLogger(__name__)


class WorkspaceAgent(BaseAgent):
    """Agent for workspace management operations using LangChain agent framework.
    
    This agent wraps WorkspaceManager methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language queries)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="workspace_agent",
            description="Agent for workspace management (repository cloning, cleanup, path management)",
            llm_provider=llm_provider
        )
        
        # Initialize WorkspaceManager
        self.workspace_manager = WorkspaceManager()
        
        # Create tools from WorkspaceManager methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        # Note: create_agent may not be available in all LangChain versions
        # The agent framework is optional - direct method calls will work regardless
        system_prompt = "You are a helpful assistant for workspace management. " \
                       "You can clone repositories, clean up workspaces, and get workspace paths. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from WorkspaceManager methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to workspace_manager for closure
        workspace_manager = self.workspace_manager
        
        @tool
        def clone_repo_tool(
            repo_full_name: str,
            pr_number: int,
            branch: Optional[str] = None
        ) -> str:
            """Clone a repository to workspace.
            
            Args:
                repo_full_name: Repository full name (e.g., "owner/repo")
                pr_number: Pull request number
                branch: Branch name to clone (optional, defaults to "main")
            
            Returns:
                Workspace path where repository was cloned
            """
            import asyncio
            try:
                return asyncio.run(
                    workspace_manager.clone_repo(repo_full_name, pr_number, branch)
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    workspace_manager.clone_repo(repo_full_name, pr_number, branch)
                )
            except Exception as e:
                logger.error(f"Error cloning repo: {e}")
                raise
        
        @tool
        def cleanup_workspace_tool(workspace_path: str) -> bool:
            """Clean up a workspace directory.
            
            Args:
                workspace_path: Path to the workspace directory to clean up
            
            Returns:
                True if cleanup was successful, False otherwise
            """
            import asyncio
            try:
                return asyncio.run(
                    workspace_manager.cleanup_workspace(workspace_path)
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    workspace_manager.cleanup_workspace(workspace_path)
                )
            except Exception as e:
                logger.error(f"Error cleaning up workspace: {e}")
                return False
        
        @tool
        def get_workspace_path_tool(repo_full_name: str, pr_number: int) -> str:
            """Get workspace path for a repository without cloning.
            
            Args:
                repo_full_name: Repository full name (e.g., "owner/repo")
                pr_number: Pull request number
            
            Returns:
                Workspace path string (directory may not exist yet)
            """
            return workspace_manager.get_workspace_path(repo_full_name, pr_number)
        
        return [clone_repo_tool, cleanup_workspace_tool, get_workspace_path_tool]
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Clone repository owner/repo PR #1")
            action: Direct action name ("clone_repo", "cleanup_workspace", "get_workspace_path")
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "clone_repo":
            repo_full_name = kwargs.get("repo_full_name")
            pr_number = kwargs.get("pr_number")
            branch = kwargs.get("branch")
            if repo_full_name and pr_number is not None:
                return {"workspace_path": await self.workspace_manager.clone_repo(repo_full_name, pr_number, branch)}
        
        elif action == "cleanup_workspace":
            workspace_path = kwargs.get("workspace_path")
            if workspace_path:
                return {"success": await self.workspace_manager.cleanup_workspace(workspace_path)}
        
        elif action == "get_workspace_path":
            repo_full_name = kwargs.get("repo_full_name")
            pr_number = kwargs.get("pr_number")
            if repo_full_name and pr_number is not None:
                return {"workspace_path": self.workspace_manager.get_workspace_path(repo_full_name, pr_number)}
        
        # If prompt is provided and agent is available, use agent
        if prompt:
            if self.agent:
                try:
                    result = self.agent.invoke({
                        "messages": [{"role": "user", "content": prompt}]
                    })
                    return {"result": result}
                except Exception as e:
                    logger.error(f"Error executing agent prompt: {e}")
                    return {"error": str(e)}
            else:
                logger.warning("Agent framework not available, but prompt was provided. Use direct method calls instead.")
                return {"error": "Agent framework not available. Use direct method calls (clone_repo, cleanup_workspace, get_workspace_path) instead."}
        
        return {"error": "No valid action or prompt provided"}
    
    # Direct methods for backward compatibility (same interface as WorkspaceManager)
    async def clone_repo(
        self,
        repo_full_name: str,
        pr_number: int,
        branch: Optional[str] = None
    ) -> str:
        """Clone repository to workspace (direct method, same as WorkspaceManager.clone_repo)."""
        return await self.workspace_manager.clone_repo(repo_full_name, pr_number, branch)
    
    async def cleanup_workspace(self, workspace_path: str) -> bool:
        """Clean up workspace directory (direct method, same as WorkspaceManager.cleanup_workspace)."""
        return await self.workspace_manager.cleanup_workspace(workspace_path)
    
    def get_workspace_path(self, repo_full_name: str, pr_number: int) -> str:
        """Get workspace path without cloning (direct method, same as WorkspaceManager.get_workspace_path)."""
        return self.workspace_manager.get_workspace_path(repo_full_name, pr_number)
    
    @property
    def base_path(self) -> str:
        """Get base path (for backward compatibility)."""
        return self.workspace_manager.base_path
    
    @base_path.setter
    def base_path(self, value: str):
        """Set base path (for backward compatibility)."""
        self.workspace_manager.base_path = value

