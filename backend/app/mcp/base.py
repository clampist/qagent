"""Base MCP tool interface."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict


class MCPTool(BaseModel, ABC):
    """Base class for MCP tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    description: str
    tool_type: str  # "high", "mid", "low"
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool."""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for MCP protocol."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self._get_input_schema()
        }
    
    @abstractmethod
    def _get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        pass


class MCPToolRegistry:
    """Registry for MCP tools."""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
    
    def register(self, tool: MCPTool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self, tool_type: Optional[str] = None) -> List[MCPTool]:
        """List all tools, optionally filtered by type."""
        if tool_type:
            return [t for t in self.tools.values() if t.tool_type == tool_type]
        return list(self.tools.values())
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas."""
        return [tool.get_schema() for tool in self.tools.values()]

