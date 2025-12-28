"""GitHub operations agent using LangChain agent framework."""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.infrastructure.github import GitHubClient
import logging

logger = logging.getLogger(__name__)


class GithubAgent(BaseAgent):
    """Agent for GitHub operations using LangChain agent framework.
    
    This agent wraps GitHubClient methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language queries)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="github_agent",
            description="Agent for GitHub repository operations (PR management, permissions checking)",
            llm_provider=llm_provider
        )
        
        # Initialize GitHubClient
        self.github_client = GitHubClient()
        
        # Create tools from GitHubClient methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        # Note: create_agent may not be available in all LangChain versions
        # The agent framework is optional - direct method calls will work regardless
        system_prompt = "You are a helpful assistant for GitHub operations. " \
                       "You can get PR information, create PRs, and check repository permissions. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from GitHubClient methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to github_client for closure
        github_client = self.github_client
        
        @tool
        def get_pr_tool(repo_full_name: str, pr_number: int) -> Dict[str, Any]:
            """Get PR information from GitHub.
            
            Args:
                repo_full_name: Repository full name (e.g., "owner/repo")
                pr_number: Pull request number
            
            Returns:
                Dict containing PR information
            """
            import asyncio
            try:
                return asyncio.run(github_client.get_pr(repo_full_name, pr_number))
            except RuntimeError:
                # If event loop is already running, use get_event_loop
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    github_client.get_pr(repo_full_name, pr_number)
                )
            except Exception as e:
                logger.error(f"Error getting PR: {e}")
                return {"error": str(e)}
        
        @tool
        def create_pr_tool(
            repo_full_name: str,
            title: str,
            body: str,
            head: str,
            base: str = "main"
        ) -> Dict[str, Any]:
            """Create a new pull request on GitHub.
            
            Args:
                repo_full_name: Repository full name (e.g., "owner/repo")
                title: PR title
                body: PR body/description
                head: Source branch name
                base: Target branch name (default: "main")
            
            Returns:
                Dict with success status, PR number, URL, and state
            """
            import asyncio
            try:
                return asyncio.run(
                    github_client.create_pr(repo_full_name, title, body, head, base)
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    github_client.create_pr(repo_full_name, title, body, head, base)
                )
            except Exception as e:
                logger.error(f"Error creating PR: {e}")
                return {"success": False, "error": str(e)}
        
        @tool
        def check_permissions_tool(
            repo_full_name: str,
            required_permissions: list = None
        ) -> Dict[str, Any]:
            """Check repository permissions on GitHub.
            
            Args:
                repo_full_name: Repository full name (e.g., "owner/repo")
                required_permissions: List of required permissions (e.g., ["read", "write"])
            
            Returns:
                Dict with has_permission status and detailed permissions
            """
            import asyncio
            try:
                return asyncio.run(
                    github_client.check_permissions(repo_full_name, required_permissions)
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    github_client.check_permissions(repo_full_name, required_permissions)
                )
            except Exception as e:
                logger.error(f"Error checking permissions: {e}")
                return {"has_permission": False, "error": str(e)}
        
        return [get_pr_tool, create_pr_tool, check_permissions_tool]
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Get PR #1 from owner/repo")
            action: Direct action name ("get_pr", "create_pr", "check_permissions")
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "get_pr":
            repo_full_name = kwargs.get("repo_full_name")
            pr_number = kwargs.get("pr_number")
            if repo_full_name and pr_number:
                return await self.github_client.get_pr(repo_full_name, pr_number)
        
        elif action == "create_pr":
            repo_full_name = kwargs.get("repo_full_name")
            title = kwargs.get("title")
            body = kwargs.get("body")
            head = kwargs.get("head")
            base = kwargs.get("base", "main")
            if repo_full_name and title and body and head:
                return await self.github_client.create_pr(repo_full_name, title, body, head, base)
        
        elif action == "check_permissions":
            repo_full_name = kwargs.get("repo_full_name")
            required_permissions = kwargs.get("required_permissions")
            if repo_full_name:
                return await self.github_client.check_permissions(repo_full_name, required_permissions)
        
        # If prompt is provided and agent is available, use agent
        if prompt and self.agent:
            try:
                result = self.agent.invoke({
                    "messages": [{"role": "user", "content": prompt}]
                })
                return {"result": result}
            except Exception as e:
                logger.error(f"Error executing agent prompt: {e}")
                return {"error": str(e)}
        
        return {"error": "No valid action or prompt provided"}
    
    # Direct methods for backward compatibility (same interface as GitHubClient)
    async def get_pr(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """Get PR information (direct method, same as GitHubClient.get_pr)."""
        return await self.github_client.get_pr(repo_full_name, pr_number)
    
    async def create_pr(
        self,
        repo_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main"
    ) -> Dict[str, Any]:
        """Create a new PR (direct method, same as GitHubClient.create_pr)."""
        return await self.github_client.create_pr(repo_full_name, title, body, head, base)
    
    async def check_permissions(
        self,
        repo_full_name: str,
        required_permissions: list = None
    ) -> Dict[str, Any]:
        """Check repository permissions (direct method, same as GitHubClient.check_permissions)."""
        return await self.github_client.check_permissions(repo_full_name, required_permissions)

