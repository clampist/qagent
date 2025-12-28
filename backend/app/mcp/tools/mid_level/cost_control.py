"""Mid-level cost control tools (MCP)."""
from typing import Dict, Any
from pydantic import Field
from app.mcp.base import MCPTool
from app.config import settings


class CostControlTool(MCPTool):
    """Control iteration and token costs."""
    iteration_count: int = Field(default=0)
    token_count: int = Field(default=0)
    
    def __init__(self):
        super().__init__(
            name="cost_control",
            description="Control loop iterations and token usage",
            tool_type="mid",
            iteration_count=0,
            token_count=0
        )
    
    async def execute(
        self,
        action: str,
        increment: int = 1
    ) -> Dict[str, Any]:
        """Execute cost control action."""
        if action == "check_iteration":
            can_continue = self.iteration_count < settings.max_iterations
            return {
                "success": True,
                "can_continue": can_continue,
                "current_iterations": self.iteration_count,
                "max_iterations": settings.max_iterations
            }
        
        elif action == "increment_iteration":
            self.iteration_count += increment
            can_continue = self.iteration_count < settings.max_iterations
            return {
                "success": True,
                "current_iterations": self.iteration_count,
                "can_continue": can_continue
            }
        
        elif action == "check_tokens":
            can_continue = self.token_count < settings.max_tokens_per_request
            return {
                "success": True,
                "can_continue": can_continue,
                "current_tokens": self.token_count,
                "max_tokens": settings.max_tokens_per_request
            }
        
        elif action == "add_tokens":
            self.token_count += increment
            can_continue = self.token_count < settings.max_tokens_per_request
            return {
                "success": True,
                "current_tokens": self.token_count,
                "can_continue": can_continue
            }
        
        elif action == "reset":
            self.iteration_count = 0
            self.token_count = 0
            return {"success": True, "message": "Counters reset"}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check_iteration", "increment_iteration", "check_tokens", "add_tokens", "reset"],
                    "description": "Cost control action"
                },
                "increment": {
                    "type": "integer",
                    "description": "Increment value",
                    "default": 1
                }
            },
            "required": ["action"]
        }

