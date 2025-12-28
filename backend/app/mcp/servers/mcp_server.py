"""MCP server implementation."""
from typing import List, Dict, Any
from app.mcp.base import MCPToolRegistry
from app.mcp.tools.mid_level.git_tools import GitCloneTool, GitCommitTool, GitPushTool
from app.mcp.tools.mid_level.search_tools import CodeSearchTool, FileSearchTool
from app.mcp.tools.high_level.case_runner import CaseRunnerTool, E2ECaseRunnerTool
# Framework detector is now an agent, not an MCP tool
# from app.mcp.tools.high_level.framework_detector import E2ETestFrameworkDetector
from app.mcp.tools.mid_level.cost_control import CostControlTool
from app.mcp.tools.mid_level.environment import EnvironmentCreateTool, PermissionCheckTool
from app.mcp.tools.low_level.time_tools import GetTimeTool, SleepTool


class MCPServer:
    """MCP server for tool management."""
    
    def __init__(self):
        self.registry = MCPToolRegistry()
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default MCP tools."""
        # High-level tools
        self.registry.register(GitCloneTool())
        self.registry.register(GitCommitTool())
        self.registry.register(GitPushTool())
        self.registry.register(CodeSearchTool())
        self.registry.register(FileSearchTool())
        self.registry.register(CaseRunnerTool())
        self.registry.register(E2ECaseRunnerTool())
        # Framework detector is now an agent, not registered as MCP tool
        # self.registry.register(E2ETestFrameworkDetector())
        
        # Mid-level tools
        self.registry.register(CostControlTool())
        self.registry.register(EnvironmentCreateTool())
        self.registry.register(PermissionCheckTool())
        
        # Low-level tools
        self.registry.register(GetTimeTool())
        self.registry.register(SleepTool())
    
    async def list_tools(self, tool_type: str = None) -> List[Dict[str, Any]]:
        """List available tools."""
        tools = self.registry.list_tools(tool_type)
        return [tool.get_schema() for tool in tools]
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool by name."""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas."""
        return self.registry.get_tool_schemas()


# Global MCP server instance
mcp_server = MCPServer()

