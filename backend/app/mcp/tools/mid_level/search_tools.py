"""Mid-level search tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool


class CodeSearchTool(MCPTool):
    """Search code in repository."""
    
    def __init__(self):
        super().__init__(
            name="code_search",
            description="Search for code patterns in repository",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        query: str,
        file_pattern: str = "*.{js,ts,jsx,tsx,py}",
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Search code."""
        import subprocess
        try:
            # Use ripgrep (rg) or grep for searching
            # TODO add ripgrep to env
            result = subprocess.run(
                ["rg", "-l", "-i", query, workspace_path, "-g", file_pattern],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            files = result.stdout.strip().split("\n") if result.stdout else []
            files = [f for f in files if f][:max_results]
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except FileNotFoundError:
            # Fallback to grep
            try:
                result = subprocess.run(
                    ["grep", "-r", "-l", query, workspace_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                files = result.stdout.strip().split("\n") if result.stdout else []
                files = [f for f in files if f][:max_results]
                return {"success": True, "files": files, "count": len(files)}
            except Exception as e:
                return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "query": {"type": "string", "description": "Search query"},
                "file_pattern": {"type": "string", "description": "File pattern", "default": "*.{js,ts,jsx,tsx,py}"},
                "max_results": {"type": "integer", "description": "Max results", "default": 10}
            },
            "required": ["workspace_path", "query"]
        }


class FileSearchTool(MCPTool):
    """Search for files by name."""
    
    def __init__(self):
        super().__init__(
            name="file_search",
            description="Search for files by name pattern",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        pattern: str,
        max_results: int = 20
    ) -> Dict[str, Any]:
        """Search files."""
        import os
        import fnmatch
        from pathlib import Path
        
        try:
            matches = []
            for root, dirs, files in os.walk(workspace_path):
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        matches.append(os.path.join(root, file))
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break
            
            return {
                "success": True,
                "files": matches,
                "count": len(matches)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "pattern": {"type": "string", "description": "File name pattern (e.g., *.test.js)"},
                "max_results": {"type": "integer", "description": "Max results", "default": 20}
            },
            "required": ["workspace_path", "pattern"]
        }


class KeywordSearchTool(MCPTool):
    """Search for files using keywords and their variants."""
    
    def __init__(self):
        super().__init__(
            name="keyword_search",
            description="Search for files using keywords and their variants",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        keywords: List[str],
        variants: Dict[str, List[str]] = None,
        file_pattern: str = "*.{js,ts,jsx,tsx,py,java,go}",
        max_results_per_query: int = 50
    ) -> Dict[str, Any]:
        """Search for files using keywords and variants.
        
        Args:
            workspace_path: Workspace path
            keywords: Original keywords
            variants: Keyword variants dictionary (optional)
            file_pattern: File pattern to search
            max_results_per_query: Max results per search query
            
        Returns:
            Search result with found files (as relative paths)
        """
        import os
        
        search_tool = CodeSearchTool()
        all_files = set()
        
        # Search with original keywords
        for keyword in keywords[:10]:  # Limit to top 10
            result = await search_tool.execute(
                workspace_path=workspace_path,
                query=keyword,
                file_pattern=file_pattern,
                max_results=max_results_per_query
            )
            if result.get("success"):
                all_files.update(result.get("files", []))
        
        # Search with variants if provided
        if variants:
            for keyword, variant_list in list(variants.items())[:10]:
                for variant in variant_list[:3]:  # Max 3 variants per keyword
                    if variant != keyword:  # Skip if same as original
                        result = await search_tool.execute(
                            workspace_path=workspace_path,
                            query=variant,
                            file_pattern=file_pattern,
                            max_results=max_results_per_query
                        )
                        if result.get("success"):
                            all_files.update(result.get("files", []))
        
        # Convert absolute paths to relative paths
        relative_files = []
        for file_path in all_files:
            try:
                # Get relative path from workspace
                rel_path = os.path.relpath(file_path, workspace_path)
                # Only include if it's actually within workspace (not ../)
                if not rel_path.startswith('..'):
                    relative_files.append(rel_path)
            except (ValueError, TypeError):
                # If conversion fails, skip this file
                continue
        
        return {
            "success": True,
            "files": relative_files,
            "count": len(relative_files)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords to search"
                },
                "variants": {
                    "type": "object",
                    "description": "Dictionary mapping keywords to their variants",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to search",
                    "default": "*.{js,ts,jsx,tsx,py,java,go}"
                },
                "max_results_per_query": {
                    "type": "integer",
                    "description": "Max results per search query",
                    "default": 50
                }
            },
            "required": ["workspace_path", "keywords"]
        }

