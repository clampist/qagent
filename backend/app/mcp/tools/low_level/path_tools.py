"""Low-level path utility tools (MCP)."""
from typing import Dict, Any
from app.mcp.base import MCPTool


class PathTypeCheckerTool(MCPTool):
    """Check if file path is frontend-related."""
    
    def __init__(self):
        super().__init__(
            name="path_type_checker",
            description="Check if file path is frontend-related",
            tool_type="low"
        )
    
    async def execute(self, file_path: str) -> Dict[str, Any]:
        """Check if file path is frontend-related.
        
        Args:
            file_path: File path to check
            
        Returns:
            Dictionary with is_frontend flag
        """
        frontend_indicators = [
            'frontend/',
            'client/',
            'web/',
            'ui/',
            'app/',
            'src/components/',
            'src/pages/',
            '.tsx',
            '.jsx',
            '.vue',
            '/tests/e2e/',
            '/tests/integration/',
            '.spec.ts',
            '.spec.js'
        ]
        
        file_path_lower = file_path.lower()
        is_frontend = any(indicator in file_path_lower for indicator in frontend_indicators)
        
        return {
            "success": True,
            "is_frontend": is_frontend,
            "file_path": file_path
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to check"}
            },
            "required": ["file_path"]
        }


class TestFileExtractorTool(MCPTool):
    """Extract test files from file list."""
    
    def __init__(self):
        super().__init__(
            name="test_file_extractor",
            description="Extract test files from file list",
            tool_type="low"
        )
    
    async def execute(self, files: list) -> Dict[str, Any]:
        """Extract test files from file list.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary with test files list
        """
        test_patterns = ['.spec.ts', '.spec.js', '.test.ts', '.test.js', '.spec.tsx', '.spec.jsx']
        test_files = [f for f in files if any(pattern in f.lower() for pattern in test_patterns)]
        
        return {
            "success": True,
            "test_files": test_files,
            "count": len(test_files)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths"
                }
            },
            "required": ["files"]
        }


class FileContentFormatterTool(MCPTool):
    """Format file contents for prompts."""
    
    def __init__(self):
        super().__init__(
            name="file_content_formatter",
            description="Format file contents for prompts",
            tool_type="low"
        )
    
    async def execute(self, file_contents: Dict[str, str], title: str, max_files: int = 15) -> Dict[str, Any]:
        """Format file contents for prompt.
        
        Args:
            file_contents: Dict of {file_path: content}
            title: Section title
            max_files: Maximum number of files to include
            
        Returns:
            Dictionary with formatted string
        """
        if not file_contents:
            formatted = f"## {title}\nNo files to display.\n"
        else:
            formatted = f"## {title}\n\n"
            
            for file_path, content in list(file_contents.items())[:max_files]:
                formatted += f"### File: {file_path}\n```\n{content}\n```\n\n"
            
            if len(file_contents) > max_files:
                formatted += f"... and {len(file_contents) - max_files} more files\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "file_count": len(file_contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_contents": {
                    "type": "object",
                    "description": "Dictionary of file paths to contents",
                    "additionalProperties": {"type": "string"}
                },
                "title": {"type": "string", "description": "Section title"},
                "max_files": {"type": "integer", "description": "Maximum files to include", "default": 15}
            },
            "required": ["file_contents", "title"]
        }

