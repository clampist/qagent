"""Low-level time tools (MCP)."""
from typing import Dict, Any
from datetime import datetime
from app.mcp.base import MCPTool


class GetTimeTool(MCPTool):
    """Get current time."""
    
    def __init__(self):
        super().__init__(
            name="get_time",
            description="Get current timestamp",
            tool_type="low"
        )
    
    async def execute(self, format: str = "iso") -> Dict[str, Any]:
        """Get current time."""
        now = datetime.now()
        
        if format == "iso":
            time_str = now.isoformat()
        elif format == "timestamp":
            time_str = str(now.timestamp())
        elif format == "readable":
            time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = now.isoformat()
        
        return {
            "success": True,
            "time": time_str,
            "timestamp": now.timestamp(),
            "datetime": {
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second
            }
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["iso", "timestamp", "readable"],
                    "description": "Time format",
                    "default": "iso"
                }
            }
        }


class SleepTool(MCPTool):
    """Sleep for specified duration."""
    
    def __init__(self):
        super().__init__(
            name="sleep",
            description="Sleep for specified seconds",
            tool_type="low"
        )
    
    async def execute(self, seconds: float) -> Dict[str, Any]:
        """Sleep."""
        import asyncio
        await asyncio.sleep(seconds)
        return {
            "success": True,
            "slept_for": seconds
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Seconds to sleep",
                    "minimum": 0,
                    "maximum": 3600
                }
            },
            "required": ["seconds"]
        }

