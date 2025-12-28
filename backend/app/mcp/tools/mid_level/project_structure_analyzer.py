"""Mid-level project structure analysis tools (MCP)."""
from typing import Dict, Any, List, Set
from app.mcp.base import MCPTool
import os
from pathlib import Path


class ProjectStructureAnalyzerTool(MCPTool):
    """Analyze project structure and identify E2E test framework directories and files."""
    
    def __init__(self):
        super().__init__(
            name="project_structure_analyzer",
            description="Analyze project directory structure and identify E2E test framework patterns",
            tool_type="mid"
        )
    
    async def execute(
        self,
        workspace_path: str,
        changed_files: List[str] = None,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """Analyze project structure and identify E2E test framework files.
        
        Args:
            workspace_path: Path to the project workspace
            changed_files: List of changed files to exclude from reference files
            max_depth: Maximum directory depth to scan
            
        Returns:
            Dictionary with project structure analysis and reference files
        """
        import logging
        logger = logging.getLogger(__name__)
        
        changed_files = changed_files or []
        changed_files_set = set(changed_files)
        
        # E2E test framework directory patterns (exact match)
        e2e_directory_names = {
            "fixtures": "fixtures",
            "helpers": "helpers",
            "page_objects": "page-objects",  # Note: use hyphen as primary
            "seeds": "seeds",
            "setup": "setup"
        }
        
        # File extensions to exclude (globally)
        excluded_extensions = {'.md', '.sh', '.csv'}
        
        # File names to exclude (globally)
        excluded_filenames = {'__init__.py'}
        
        # Scan project structure
        reference_files = []
        directory_tree = {}
        e2e_directories = []
        
        try:
            # Walk through directory
            for root, dirs, files in os.walk(workspace_path):
                # Calculate depth
                depth = root[len(workspace_path):].count(os.sep)
                if depth > max_depth:
                    continue
                
                # Skip common ignore directories
                dirs[:] = [d for d in dirs if d not in {
                    'node_modules', '.git', 'dist', 'build', '.next', 
                    '__pycache__', '.pytest_cache', 'coverage', 'htmlcov'
                }]
                
                rel_path = os.path.relpath(root, workspace_path)
                
                # Check if current directory or any parent directory is an E2E directory
                # This handles nested structures like fixtures/csv/
                current_path_parts = rel_path.split(os.sep)
                matched_type = None
                
                for pattern_type, dir_name in e2e_directory_names.items():
                    # Check if any part of the path matches the E2E directory name
                    if dir_name in current_path_parts:
                        matched_type = pattern_type
                        # Only add the top-level E2E directory to e2e_directories
                        idx = current_path_parts.index(dir_name)
                        e2e_dir_path = os.sep.join(current_path_parts[:idx+1])
                        if e2e_dir_path not in e2e_directories:
                            e2e_directories.append(e2e_dir_path)
                        break
                
                # If this directory (or parent) is an E2E directory, add its files
                if matched_type:
                    for file in files:
                        # Skip files with excluded extensions
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in excluded_extensions:
                            continue
                        
                        # Skip files with excluded names
                        if file in excluded_filenames:
                            continue
                        
                        file_path = os.path.join(root, file)
                        rel_file_path = os.path.relpath(file_path, workspace_path)
                        
                        # Skip if it's a changed file
                        if rel_file_path in changed_files_set or file_path in changed_files_set:
                            continue
                        
                        reference_files.append({
                            "path": rel_file_path,
                            "type": matched_type,
                            "reason": f"Located in {matched_type} directory"
                        })
            
            # Deduplicate reference files
            unique_refs = []
            seen_paths = set()
            for ref in reference_files:
                if ref["path"] not in seen_paths:
                    unique_refs.append(ref)
                    seen_paths.add(ref["path"])
            
            logger.info(f"Found {len(unique_refs)} reference files (E2E framework patterns)")
            logger.info(f"Found {len(e2e_directories)} E2E-related directories")
            
            return {
                "success": True,
                "reference_files": unique_refs,
                "e2e_directories": list(set(e2e_directories)),
                "summary": {
                    "total_reference_files": len(unique_refs),
                    "total_e2e_directories": len(set(e2e_directories)),
                    "by_type": self._count_by_type(unique_refs)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze project structure: {e}")
            return {
                "success": False,
                "error": str(e),
                "reference_files": [],
                "e2e_directories": []
            }
    
    def _count_by_type(self, reference_files: List[Dict]) -> Dict[str, int]:
        """Count reference files by type."""
        counts = {}
        for ref in reference_files:
            ref_type = ref.get("type", "unknown")
            counts[ref_type] = counts.get(ref_type, 0) + 1
        return counts
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Path to the project workspace"
                },
                "changed_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of changed files to exclude from reference files"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth to scan",
                    "default": 10
                }
            },
            "required": ["workspace_path"]
        }
