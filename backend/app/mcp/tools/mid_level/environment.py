"""Mid-level environment management tools (MCP)."""
from typing import Dict, Any, Optional
from app.mcp.base import MCPTool


class EnvironmentCreateTool(MCPTool):
    """Create isolated environment."""
    
    def __init__(self):
        super().__init__(
            name="environment_create",
            description="Create isolated environment for testing",
            tool_type="mid"
        )
    
    async def execute(
        self,
        environment_type: str = "docker",
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create environment."""
        # This would integrate with sandbox manager
        # For now, return placeholder
        return {
            "success": True,
            "environment_id": "env_placeholder",
            "type": environment_type,
            "message": "Environment creation delegated to sandbox manager"
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "environment_type": {
                    "type": "string",
                    "enum": ["docker", "vm", "container"],
                    "description": "Environment type",
                    "default": "docker"
                },
                "config": {
                    "type": "object",
                    "description": "Environment configuration"
                }
            }
        }


class PermissionCheckTool(MCPTool):
    """Check GitHub permissions."""
    _github_client: Optional[Any] = None  # Private field, lazy initialized
    
    def __init__(self):
        super().__init__(
            name="permission_check",
            description="Check GitHub repository permissions",
            tool_type="mid"
        )
    
    def _get_github_client(self):
        """Lazy initialization of GithubAgent to avoid circular import."""
        if self._github_client is None:
            # Lazy import to avoid circular dependency
            from app.agents.business.github_agent import GithubAgent
            self._github_client = GithubAgent()
        return self._github_client
    
    async def execute(
        self,
        repo_full_name: str,
        required_permissions: list = None
    ) -> Dict[str, Any]:
        """Check permissions."""
        if required_permissions is None:
            required_permissions = ["pull", "push"]
        
        # Lazy initialize and use GitHub client to check actual permissions
        github_client = self._get_github_client()
        result = await github_client.check_permissions(
            repo_full_name=repo_full_name,
            required_permissions=required_permissions
        )
        
        return {
            "success": True,
            "has_permission": result.get("has_permission", False),
            "permissions": result.get("permissions", {}),
            "error": result.get("error") if "error" in result else None
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo_full_name": {"type": "string", "description": "Repository full name (owner/repo)"},
                "required_permissions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required permissions list"
                }
            },
            "required": ["repo_full_name"]
        }

