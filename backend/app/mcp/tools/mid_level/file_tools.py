"""Mid-level file operation tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool
import os


class FileReaderTool(MCPTool):
    """Read file contents with line limit."""
    
    def __init__(self):
        super().__init__(
            name="file_reader",
            description="Read file contents with line limit",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        files: List[str],
        max_lines_per_file: int = 200,
        max_files: int = 20
    ) -> Dict[str, Any]:
        """Read file contents with line limit.
        
        Args:
            workspace_path: Workspace path
            files: List of file paths (relative)
            max_lines_per_file: Max lines to read per file
            max_files: Maximum number of files to read
            
        Returns:
            Dict of {file_path: content}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        contents = {}
        
        for file_path in files[:max_files]:
            try:
                full_path = os.path.join(workspace_path, file_path)
                if not os.path.exists(full_path):
                    continue
                
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:max_lines_per_file]
                    content = ''.join(lines)
                    
                    if len(lines) == max_lines_per_file:
                        content += f"\n... (truncated, total lines may exceed {max_lines_per_file})"
                    
                    contents[file_path] = content
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                continue
        
        return {
            "success": True,
            "contents": contents,
            "count": len(contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths (relative)"
                },
                "max_lines_per_file": {"type": "integer", "description": "Max lines per file", "default": 200},
                "max_files": {"type": "integer", "description": "Maximum files to read", "default": 20}
            },
            "required": ["workspace_path", "files"]
        }


class TestFileSearchTool(MCPTool):
    """Search for related test files using keywords."""
    
    def __init__(self):
        super().__init__(
            name="test_file_search",
            description="Search for related test files using keywords",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        keywords: List[str],
        test_dir: str = None,
        max_keywords: int = 3,
        max_results_per_keyword: int = 20
    ) -> Dict[str, Any]:
        """Search for related test files using keywords.
        
        Args:
            workspace_path: Workspace path
            keywords: Keywords to search
            test_dir: Test directory path (optional)
            max_keywords: Maximum keywords to use
            max_results_per_keyword: Maximum results per keyword
            
        Returns:
            List of related test file paths (relative to workspace)
        """
        from app.mcp.tools.mid_level.search_tools import CodeSearchTool
        
        search_tool = CodeSearchTool()
        test_files = set()
        
        # Determine search path
        if test_dir:
            search_path = test_dir if os.path.isabs(test_dir) else os.path.join(workspace_path, test_dir)
        else:
            # Search in common test directories
            search_path = workspace_path
        
        # Search with each keyword
        for keyword in keywords[:max_keywords]:
            try:
                result = await search_tool.execute(
                    workspace_path=search_path,
                    query=keyword,
                    file_pattern="*.spec.{ts,js,tsx,jsx}",
                    max_results=max_results_per_keyword
                )
                
                if result.get("success"):
                    files = result.get("files", [])
                    # Convert to relative paths
                    for f in files:
                        try:
                            rel_path = os.path.relpath(f, workspace_path)
                            if not rel_path.startswith('..'):
                                test_files.add(rel_path)
                        except ValueError:
                            continue
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to search with keyword '{keyword}': {e}")
                continue
        
        return {
            "success": True,
            "files": list(test_files),
            "count": len(test_files)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to search"
                },
                "test_dir": {"type": "string", "description": "Test directory path (optional)"},
                "max_keywords": {"type": "integer", "description": "Maximum keywords to use", "default": 3},
                "max_results_per_keyword": {"type": "integer", "description": "Max results per keyword", "default": 20}
            },
            "required": ["workspace_path", "keywords"]
        }


class FrontendRequirementFilterTool(MCPTool):
    """Filter frontend-only requirements."""
    
    def __init__(self):
        super().__init__(
            name="frontend_requirement_filter",
            description="Filter frontend-only requirements (excluding backend and documentation)",
            tool_type="mid"
        )
    
    async def execute(
        self,
        requirements: List[str],
        changed_files: List[str],
        related_files: List[str] = None
    ) -> Dict[str, Any]:
        """Filter frontend-only requirements.
        
        Args:
            requirements: All requirements
            changed_files: Changed files list
            related_files: Related changed files list (optional)
            
        Returns:
            Frontend-only requirements
        """
        frontend_requirements = []
        all_files = changed_files + (related_files or [])
        
        # Check if any files are frontend-related (using same logic as PathTypeCheckerTool)
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
        
        has_frontend_changes = False
        for f in all_files:
            file_path_lower = f.lower()
            if any(indicator in file_path_lower for indicator in frontend_indicators):
                has_frontend_changes = True
                break
        
        if not has_frontend_changes:
            # No frontend changes, return empty
            return {
                "success": True,
                "frontend_requirements": [],
                "count": 0
            }
        
        # Filter requirements
        for req in requirements:
            req_lower = req.lower()
            
            # Skip documentation-related requirements
            documentation_keywords = [
                'documentation', 'document', 'readme', 'docs', 'doc',
                'comment', 'comments', 'changelog', 'guide',
                'manual', 'specification', 'spec document'
            ]
            if any(keyword in req_lower for keyword in documentation_keywords):
                # Only skip if it's ONLY about documentation
                code_keywords = ['code', 'implementation', 'function', 'component', 'test']
                if not any(keyword in req_lower for keyword in code_keywords):
                    continue
            
            # Skip if contains backend keywords
            backend_keywords = ['backend', 'api', 'database', 'model', 'migration', 'endpoint', 'service']
            if any(keyword in req_lower for keyword in backend_keywords):
                # Check if also mentions frontend
                frontend_keywords = ['frontend', 'ui', 'component', 'page', 'button', 'form', 'display']
                if not any(keyword in req_lower for keyword in frontend_keywords):
                    continue
            
            frontend_requirements.append(req)
        
        return {
            "success": True,
            "frontend_requirements": frontend_requirements,
            "count": len(frontend_requirements)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "All requirements"
                },
                "changed_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Changed files list"
                },
                "related_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related changed files list (optional)"
                }
            },
            "required": ["requirements", "changed_files"]
        }


class TestFileReaderTool(MCPTool):
    """Read test file contents with line limit."""
    
    def __init__(self):
        super().__init__(
            name="test_file_reader",
            description="Read test file contents with line limit",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        test_files: List[str],
        max_lines_per_file: int = 500,
        max_files: int = 20
    ) -> Dict[str, Any]:
        """Read test file contents with line limit.
        
        Args:
            workspace_path: Workspace path
            test_files: List of test file paths (relative)
            max_lines_per_file: Max lines to read per file
            max_files: Maximum number of files to read
            
        Returns:
            Dict of {file_path: content}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        contents = {}
        
        for file_path in test_files[:max_files]:
            try:
                full_path = os.path.join(workspace_path, file_path)
                if not os.path.exists(full_path):
                    continue
                
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:max_lines_per_file]
                    content = ''.join(lines)
                    
                    if len(lines) == max_lines_per_file:
                        content += f"\n... (truncated, file may have more lines)"
                    
                    contents[file_path] = content
            except Exception as e:
                logger.warning(f"Failed to read test file {file_path}: {e}")
                continue
        
        return {
            "success": True,
            "contents": contents,
            "count": len(contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "test_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of test file paths (relative)"
                },
                "max_lines_per_file": {"type": "integer", "description": "Max lines per file", "default": 500},
                "max_files": {"type": "integer", "description": "Maximum files to read", "default": 20}
            },
            "required": ["workspace_path", "test_files"]
        }


class FrontendFileReaderTool(MCPTool):
    """Read frontend changed files content (for context)."""
    
    def __init__(self):
        super().__init__(
            name="frontend_file_reader",
            description="Read frontend changed files content (for context)",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        changed_files: List[str],
        max_lines_per_file: int = 300,
        max_files: int = 15
    ) -> Dict[str, Any]:
        """Read frontend changed files content.
        
        Args:
            workspace_path: Workspace path
            changed_files: List of changed file paths from git diff
            max_lines_per_file: Max lines to read per file
            max_files: Maximum number of files to read
            
        Returns:
            Dict of {file_path: content}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Filter: skip backend/ files, only keep frontend files
        frontend_changed = [f for f in changed_files if not f.startswith('backend/')]
        logger.info(f"[DEBUG] After excluding backend/: {len(frontend_changed)} files")
        
        # Further filter: only frontend source code (not test files, not config files)
        frontend_source = []
        config_file_patterns = [
            '.config.',
            'config.ts',
            'config.js',
            'package.json',
            'package-lock.json',
            'yarn.lock',
            'tsconfig.json',
            'jsconfig.json',
            '.eslintrc',
            '.prettierrc',
            'tailwind.config',
            'next.config',
            'webpack.config',
            'rollup.config',
            '.env',
            '.gitignore',
            'README.md',
            'CHANGELOG.md'
        ]
        
        for file_path in frontend_changed:
            # Exclude test files
            if any(pattern in file_path for pattern in ['.spec.', '.test.', '/tests/', '/__tests__/']):
                continue
            
            # Exclude configuration files
            if any(pattern in file_path for pattern in config_file_patterns):
                logger.debug(f"Excluding config file: {file_path}")
                continue
            
            # Include frontend source code directories
            if any(pattern in file_path for pattern in ['src/', 'components/', 'pages/', 'lib/', 'utils/', 'hooks/', 'types/', 'app/', 'views/']):
                frontend_source.append(file_path)
        
        logger.info(f"Reading {len(frontend_source)} frontend changed files (source code only)")
        
        contents = {}
        for file_path in frontend_source[:max_files]:
            try:
                full_path = os.path.join(workspace_path, file_path)
                if not os.path.exists(full_path):
                    continue
                
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:max_lines_per_file]
                    content = ''.join(lines)
                    
                    if len(lines) == max_lines_per_file:
                        content += f"\n... (truncated at {max_lines_per_file} lines)"
                    
                    contents[file_path] = content
            except Exception as e:
                logger.warning(f"Failed to read changed file {file_path}: {e}")
                continue
        
        logger.info(f"Successfully read {len(contents)} frontend changed files")
        return {
            "success": True,
            "contents": contents,
            "count": len(contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "changed_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of changed file paths from git diff"
                },
                "max_lines_per_file": {"type": "integer", "description": "Max lines per file", "default": 300},
                "max_files": {"type": "integer", "description": "Maximum files to read", "default": 15}
            },
            "required": ["workspace_path", "changed_files"]
        }


class PageObjectReaderTool(MCPTool):
    """Read page-objects and helpers files completely."""
    
    def __init__(self):
        super().__init__(
            name="page_object_reader",
            description="Read page-objects and helpers files completely",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        reference_files: List[Any],
        max_files: int = 30
    ) -> Dict[str, Any]:
        """Read page-objects and helpers files completely.
        
        Args:
            workspace_path: Workspace path
            reference_files: List of reference file objects from requirement_analyzer
            max_files: Maximum number of files to read
            
        Returns:
            Dict of {file_path: content}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract paths from reference_files
        reference_paths = [
            ref.get("path") if isinstance(ref, dict) else ref 
            for ref in reference_files
        ]
        
        logger.info(f"[DEBUG] Extracted reference_paths: {len(reference_paths)} paths")
        
        # Filter to page-objects and helpers (exclude backend files)
        po_helper_files = []
        for file_path in reference_paths:
            # Skip backend files
            if file_path.startswith('backend/'):
                continue
            # Include page-objects, helpers, and fixtures
            if any(pattern in file_path for pattern in ['page-objects/', 'page_objects/', 'helpers/', 'fixtures/']):
                po_helper_files.append(file_path)
        
        logger.info(f"Reading {len(po_helper_files)} page-objects and helpers files (complete content)")
        
        contents = {}
        for file_path in po_helper_files[:max_files]:
            try:
                full_path = os.path.join(workspace_path, file_path)
                if not os.path.exists(full_path):
                    continue
                
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()  # Read complete file (no line limit for helpers)
                    contents[file_path] = content
            except Exception as e:
                logger.warning(f"Failed to read page-object/helper file {file_path}: {e}")
                continue
        
        logger.info(f"Successfully read {len(contents)} page-objects and helpers files")
        return {
            "success": True,
            "contents": contents,
            "count": len(contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "reference_files": {
                    "type": "array",
                    "description": "List of reference file objects from requirement_analyzer"
                },
                "max_files": {"type": "integer", "description": "Maximum files to read", "default": 30}
            },
            "required": ["workspace_path", "reference_files"]
        }

