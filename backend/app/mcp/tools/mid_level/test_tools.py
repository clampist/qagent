"""Mid-level test-related tools (MCP)."""
from typing import Dict, Any, List, Optional
from app.mcp.base import MCPTool
import os


class SyntaxCheckerTool(MCPTool):
    """Check test file syntax."""
    
    def __init__(self):
        super().__init__(
            name="syntax_checker",
            description="Check test file syntax using TypeScript/JavaScript compiler",
            tool_type="mid"
        )
    
    async def execute(self, test_file: str, workspace_path: str) -> Dict[str, Any]:
        """Check test file syntax.
        
        Args:
            test_file: Path to test file (relative to workspace_path)
            workspace_path: Workspace path
            
        Returns:
            Dictionary with validation result
        """
        import subprocess
        import logging
        logger = logging.getLogger(__name__)
        
        full_path = os.path.join(workspace_path, test_file)
        
        try:
            # Try TypeScript/JavaScript syntax check
            if test_file.endswith(".ts") or test_file.endswith(".tsx"):
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit", test_file],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                result = subprocess.run(
                    ["node", "--check", test_file],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            return {
                "success": True,
                "valid": result.returncode == 0,
                "errors": result.stderr.split("\n") if result.stderr else []
            }
        except Exception as e:
            logger.error(f"Syntax check failed: {e}")
            return {
                "success": False,
                "valid": False,
                "errors": [str(e)]
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_file": {"type": "string", "description": "Path to test file (relative to workspace_path)"},
                "workspace_path": {"type": "string", "description": "Workspace path"}
            },
            "required": ["test_file", "workspace_path"]
        }


class FileModifierTool(MCPTool):
    """Apply modifications to an existing file."""
    
    def __init__(self):
        super().__init__(
            name="file_modifier",
            description="Apply modifications to an existing file",
            tool_type="mid"
        )
    
    async def execute(
        self,
        file_path: str,
        changes: List[Dict[str, Any]],
        workspace_path: str
    ) -> Dict[str, Any]:
        """Apply modifications to an existing file.
        
        Args:
            file_path: File path (relative to workspace_path)
            changes: List of change objects
            workspace_path: Workspace root path
            
        Returns:
            Dictionary with success status and message
        """
        import logging
        logger = logging.getLogger(__name__)
        
        full_path = os.path.join(workspace_path, file_path) if not os.path.isabs(file_path) else file_path
        
        if not os.path.exists(full_path):
            return {
                "success": False,
                "message": f"File does not exist: {full_path}"
            }
        
        try:
            # Read current file content
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            original_content = content
            modifications_applied = []
            
            for change in changes:
                change_type = change.get("type")
                code = change.get("code", "")
                location = change.get("location", "")
                reason = change.get("reason", "No reason provided")
                
                logger.info(f"Applying change: type={change_type}, location={location}, reason={reason}")
                
                if change_type == "add_method":
                    # Add method after specified location
                    if location.startswith("after_method:"):
                        method_name = location.split(":", 1)[1]
                        # For now, append to end of class (before last closing brace)
                        last_brace = content.rfind("}")
                        if last_brace != -1:
                            content = content[:last_brace] + "\n" + code + "\n" + content[last_brace:]
                            modifications_applied.append(f"Added method (reason: {reason})")
                        else:
                            logger.warning(f"Could not find insertion point for method")
                    elif location == "end_of_class":
                        # Append before last closing brace
                        last_brace = content.rfind("}")
                        if last_brace != -1:
                            content = content[:last_brace] + "\n" + code + "\n" + content[last_brace:]
                            modifications_applied.append(f"Added method at end of class (reason: {reason})")
                
                elif change_type == "add_import":
                    # Add import at top of file
                    lines = content.split("\n")
                    # Find last import line
                    last_import_idx = -1
                    for i, line in enumerate(lines):
                        if line.strip().startswith("import "):
                            last_import_idx = i
                    
                    if last_import_idx != -1:
                        lines.insert(last_import_idx + 1, code)
                        content = "\n".join(lines)
                        modifications_applied.append(f"Added import (reason: {reason})")
                    else:
                        # No imports found, add at top
                        content = code + "\n" + content
                        modifications_applied.append(f"Added import at top (reason: {reason})")
                
                elif change_type == "add_helper":
                    # Add helper function at end of file
                    content = content + "\n\n" + code
                    modifications_applied.append(f"Added helper function (reason: {reason})")
                
                elif change_type == "add_property":
                    # Add property to class
                    if location.startswith("after_property:"):
                        property_name = location.split(":", 1)[1]
                        property_pattern = f"{property_name}:"
                        property_pos = content.find(property_pattern)
                        
                        if property_pos != -1:
                            line_end = content.find("\n", property_pos)
                            if line_end != -1:
                                content = content[:line_end + 1] + code.strip() + "\n" + content[line_end + 1:]
                                modifications_applied.append(f"Added property after {property_name} (reason: {reason})")
                    elif location == "start_of_class":
                        class_pos = content.find("class ")
                        if class_pos != -1:
                            brace_pos = content.find("{", class_pos)
                            if brace_pos != -1:
                                content = content[:brace_pos + 1] + "\n  " + code.strip() + "\n" + content[brace_pos + 1:]
                                modifications_applied.append(f"Added property at start of class (reason: {reason})")
                
                elif change_type == "add_code":
                    # Add code at specific location
                    if location.startswith("after_line:"):
                        target_line = location.split(":", 1)[1]
                        target_pos = content.find(target_line)
                        
                        if target_pos != -1:
                            line_end = content.find("\n", target_pos)
                            if line_end != -1:
                                content = content[:line_end + 1] + code.strip() + "\n" + content[line_end + 1:]
                                modifications_applied.append(f"Added code after target line (reason: {reason})")
                
                elif change_type == "add_constant":
                    # Add constant property or new constant
                    if location.startswith("inside:"):
                        constant_name = location.split(":", 1)[1]
                        constant_pattern = f"export const {constant_name}"
                        constant_pos = content.find(constant_pattern)
                        
                        if constant_pos != -1:
                            open_brace = content.find("{", constant_pos)
                            if open_brace != -1:
                                # Find matching closing brace
                                brace_count = 1
                                pos = open_brace + 1
                                while pos < len(content) and brace_count > 0:
                                    if content[pos] == "{":
                                        brace_count += 1
                                    elif content[pos] == "}":
                                        brace_count -= 1
                                    pos += 1
                                
                                if brace_count == 0:
                                    close_brace = pos - 1
                                    content = content[:close_brace] + "\n  " + code.strip() + "\n" + content[close_brace:]
                                    modifications_applied.append(f"Added property to {constant_name} (reason: {reason})")
                    elif location.startswith("after_constant:"):
                        constant_name = location.split(":", 1)[1]
                        constant_pattern = f"export const {constant_name}"
                        constant_pos = content.find(constant_pattern)
                        
                        if constant_pos != -1:
                            brace_pos = content.find("}", constant_pos)
                            semicolon_pos = content.find(";", constant_pos)
                            
                            if brace_pos != -1 and (semicolon_pos == -1 or brace_pos < semicolon_pos):
                                insert_pos = brace_pos + 1
                            elif semicolon_pos != -1:
                                insert_pos = semicolon_pos + 1
                            else:
                                insert_pos = content.find("\n", constant_pos) + 1
                            
                            content = content[:insert_pos] + "\n\n" + code + content[insert_pos:]
                            modifications_applied.append(f"Added constant after {constant_name} (reason: {reason})")
                    else:
                        content = content + "\n\n" + code
                        modifications_applied.append(f"Added constant (reason: {reason})")
                
                else:
                    logger.warning(f"Unknown change type: {change_type}")
            
            # Write modified content
            if content != original_content:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                logger.info(f"Applied {len(modifications_applied)} modifications to {file_path}")
                return {
                    "success": True,
                    "message": f"Applied {len(modifications_applied)} changes: {', '.join(modifications_applied)}",
                    "modifications_applied": modifications_applied
                }
            else:
                return {
                    "success": False,
                    "message": "No changes were applied"
                }
                
        except Exception as e:
            logger.error(f"Error applying modifications to {file_path}: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path (relative to workspace_path)"},
                "changes": {
                    "type": "array",
                    "description": "List of change objects",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "code": {"type": "string"},
                            "location": {"type": "string"},
                            "reason": {"type": "string"}
                        }
                    }
                },
                "workspace_path": {"type": "string", "description": "Workspace root path"}
            },
            "required": ["file_path", "changes", "workspace_path"]
        }


class TestStructureAnalyzerTool(MCPTool):
    """Analyze existing test structure for naming patterns."""
    
    def __init__(self):
        super().__init__(
            name="test_structure_analyzer",
            description="Analyze existing test structure for naming patterns",
            tool_type="mid"
        )
    
    async def execute(self, base_path: str) -> Dict[str, Any]:
        """Analyze existing test structure.
        
        Args:
            base_path: Base path to analyze
            
        Returns:
            Dictionary with test structure information
        """
        test_dir = os.path.join(base_path, "tests", "e2e")
        
        if not os.path.exists(test_dir):
            return {
                "success": True,
                "exists": False,
                "examples": []
            }
        
        # Find existing test files
        test_files = []
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                if file.endswith((".spec.ts", ".spec.js", ".test.ts", ".test.js")):
                    rel_path = os.path.relpath(os.path.join(root, file), test_dir)
                    test_files.append(rel_path)
        
        return {
            "success": True,
            "exists": True,
            "test_dir": test_dir,
            "examples": test_files[:5],  # Return up to 5 examples
            "count": len(test_files)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_path": {"type": "string", "description": "Base path to analyze"}
            },
            "required": ["base_path"]
        }


class TestFilePathDeterminerTool(MCPTool):
    """Determine appropriate test file path."""
    
    def __init__(self):
        super().__init__(
            name="test_file_path_determiner",
            description="Determine appropriate test file path based on reference test file",
            tool_type="mid"
        )
    
    async def execute(
        self,
        base_path: str,
        suite_name: str,
        coverage_areas: List[str],
        existing_structure: Dict[str, Any],
        test_framework: str,
        reference_test_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Determine appropriate test file path.
        
        Args:
            base_path: Base path
            suite_name: Test suite name
            coverage_areas: Coverage areas
            existing_structure: Existing test structure
            test_framework: Test framework
            reference_test_file: Reference test file path (optional)
            
        Returns:
            Dictionary with suggested test file path
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # If we have a reference test file, use its directory
        if reference_test_file:
            ref_dir = os.path.dirname(reference_test_file)
            logger.info(f"Using directory from reference test file: {ref_dir}")
            
            # Generate filename based on coverage areas or suite name
            if coverage_areas and len(coverage_areas) > 0:
                filename_hint = coverage_areas[0].lower().replace(" ", "-").replace("/", "-")
                # Remove common prefixes
                for prefix in ["src-", "app-", "components-", "pages-"]:
                    if filename_hint.startswith(prefix):
                        filename_hint = filename_hint[len(prefix):]
                        break
            else:
                filename_hint = suite_name.lower().replace(" ", "-").replace("_", "-")
            
            # Add file extension
            ext = "ts" if test_framework == "playwright" else "js"
            test_file = os.path.join(ref_dir, f"{filename_hint}.spec.{ext}")
            
            logger.info(f"Suggested test file path: {test_file}")
            return {
                "success": True,
                "test_file_path": test_file
            }
        
        # Fallback: original logic
        test_dir = os.path.join(base_path, "tests", "e2e")
        
        # If coverage areas are specific, create subdirectories
        if coverage_areas and len(coverage_areas) > 0:
            main_area = coverage_areas[0].lower().replace(" ", "-")
            if "/" in main_area:
                path_parts = main_area.split("/")
                meaningful_parts = [p for p in path_parts if p not in ["src", "app", "components", "pages"]]
                if meaningful_parts:
                    test_dir = os.path.join(test_dir, *meaningful_parts[:-1])
                    filename_hint = meaningful_parts[-1]
                else:
                    filename_hint = "test"
            else:
                filename_hint = main_area
        else:
            filename_hint = suite_name
        
        # Convert to kebab-case if needed
        filename = filename_hint.lower().replace(" ", "-").replace("_", "-")
        
        # Add file extension
        ext = "ts" if test_framework == "playwright" else "js"
        test_file = os.path.join(test_dir, f"{filename}.spec.{ext}")
        
        return {
            "success": True,
            "test_file_path": test_file
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_path": {"type": "string", "description": "Base path"},
                "suite_name": {"type": "string", "description": "Test suite name"},
                "coverage_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Coverage areas"
                },
                "existing_structure": {
                    "type": "object",
                    "description": "Existing test structure"
                },
                "test_framework": {"type": "string", "description": "Test framework"},
                "reference_test_file": {"type": "string", "description": "Reference test file path (optional)"}
            },
            "required": ["base_path", "suite_name", "coverage_areas", "existing_structure", "test_framework"]
        }


class TestFileFinderTool(MCPTool):
    """Find test files in directory."""
    
    def __init__(self):
        super().__init__(
            name="test_file_finder",
            description="Find test files in directory (first or longest)",
            tool_type="mid"
        )
    
    async def execute(self, base_path: str, find_longest: bool = False) -> Dict[str, Any]:
        """Find test file in directory.
        
        Args:
            base_path: Base path to search from
            find_longest: If True, find longest file; if False, find first file
            
        Returns:
            Dictionary with test file path
        """
        import logging
        logger = logging.getLogger(__name__)
        
        test_dir = os.path.join(base_path, "tests", "e2e")
        if not os.path.exists(test_dir):
            # Try alternative paths
            for alt_dir in ["tests", "test", "e2e", "__tests__"]:
                alt_path = os.path.join(base_path, alt_dir)
                if os.path.exists(alt_path):
                    test_dir = alt_path
                    break
            else:
                logger.warning(f"No test directory found in {base_path}")
                return {
                    "success": False,
                    "test_file": None
                }
        
        # Find test files
        test_files = []
        for root, dirs, files in os.walk(test_dir):
            for file in files:
                if file.endswith(('.spec.ts', '.spec.js', '.test.ts', '.test.js')):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_path)
                    test_files.append((rel_path, full_path))
        
        if not test_files:
            logger.warning(f"No test files found in {test_dir}")
            return {
                "success": False,
                "test_file": None
            }
        
        if find_longest:
            # Find longest file
            longest_file = max(test_files, key=lambda x: os.path.getsize(x[1]))
            test_file = longest_file[0]
            logger.info(f"Found longest test file: {test_file}")
        else:
            # Find first file
            test_file = test_files[0][0]
            logger.info(f"Found first test file: {test_file}")
        
        return {
            "success": True,
            "test_file": test_file
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_path": {"type": "string", "description": "Base path to search from"},
                "find_longest": {"type": "boolean", "description": "Find longest file instead of first", "default": False}
            },
            "required": ["base_path"]
        }


class TestDirectoryTreeGeneratorTool(MCPTool):
    """Generate test directory tree structure."""
    
    def __init__(self):
        super().__init__(
            name="test_directory_tree_generator",
            description="Generate test directory tree structure",
            tool_type="mid"
        )
    
    async def execute(self, base_path: str, max_depth: int = 5) -> Dict[str, Any]:
        """Generate test directory tree structure.
        
        Args:
            base_path: Base path to generate tree from
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary with formatted directory tree string
        """
        import logging
        logger = logging.getLogger(__name__)
        
        test_dir = os.path.join(base_path, "tests")
        if not os.path.exists(test_dir):
            # Try alternative paths
            for alt_dir in ["test", "e2e", "__tests__"]:
                alt_path = os.path.join(base_path, alt_dir)
                if os.path.exists(alt_path):
                    test_dir = alt_path
                    break
            else:
                return {
                    "success": True,
                    "tree": "Test directory not found"
                }
        
        tree_lines = []
        tree_lines.append("```")
        tree_lines.append(os.path.basename(test_dir) + "/")
        
        def build_tree(directory: str, prefix: str = "", current_depth: int = 0):
            """Recursively build directory tree."""
            if current_depth >= max_depth:
                return
            
            try:
                items = sorted(os.listdir(directory))
                # Filter out common ignore patterns
                items = [item for item in items if not item.startswith('.') and item not in ['node_modules', '__pycache__', 'coverage']]
                
                # Separate directories and files
                dirs = [item for item in items if os.path.isdir(os.path.join(directory, item))]
                files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
                
                # Process directories first
                for i, dir_name in enumerate(dirs):
                    is_last_dir = (i == len(dirs) - 1) and len(files) == 0
                    connector = "└── " if is_last_dir else "├── "
                    tree_lines.append(f"{prefix}{connector}{dir_name}/")
                    
                    # Recursively process subdirectory
                    extension = "    " if is_last_dir else "│   "
                    build_tree(
                        os.path.join(directory, dir_name),
                        prefix + extension,
                        current_depth + 1
                    )
                
                # Process files
                for i, file_name in enumerate(files):
                    is_last = i == len(files) - 1
                    connector = "└── " if is_last else "├── "
                    tree_lines.append(f"{prefix}{connector}{file_name}")
                    
            except PermissionError:
                tree_lines.append(f"{prefix}[Permission Denied]")
        
        build_tree(test_dir, "")
        tree_lines.append("```")
        
        tree_str = "\n".join(tree_lines)
        logger.info(f"Generated directory tree with {len(tree_lines)} lines")
        
        return {
            "success": True,
            "tree": tree_str
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_path": {"type": "string", "description": "Base path to generate tree from"},
                "max_depth": {"type": "integer", "description": "Maximum depth to traverse", "default": 5}
            },
            "required": ["base_path"]
        }


class BatchSyntaxCheckerTool(MCPTool):
    """Check syntax for multiple test case files."""
    
    def __init__(self):
        super().__init__(
            name="batch_syntax_checker",
            description="Check syntax for multiple test case files",
            tool_type="mid"
        )
    
    async def execute(
        self,
        test_cases: List[Dict[str, Any]],
        workspace_path: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Check syntax for all test case files.
        
        Args:
            test_cases: List of test case objects with file_path
            workspace_path: Workspace root path for running tsc
            
        Returns:
            Dict of {file_path: {valid: bool, errors: list, stderr: list}}
        """
        import subprocess
        import logging
        logger = logging.getLogger(__name__)
        
        syntax_results = {}
        
        if not workspace_path:
            # Try to find workspace path from test case file paths
            for case in test_cases:
                file_path = case.get("file_path", "")
                if file_path:
                    # Try to find workspace path from absolute file path
                    if os.path.isabs(file_path):
                        # Find common workspace root (look for package.json, tsconfig.json, etc.)
                        current = os.path.dirname(file_path)
                        for _ in range(10):  # Search up to 10 levels
                            if os.path.exists(os.path.join(current, "package.json")) or \
                               os.path.exists(os.path.join(current, "tsconfig.json")):
                                workspace_path = current
                                break
                            parent = os.path.dirname(current)
                            if parent == current:
                                break
                            current = parent
                        if workspace_path:
                            break
            
            if not workspace_path:
                logger.warning("Could not determine workspace path for syntax check")
                return syntax_results
        
        # Check syntax for each test case file
        for case in test_cases:
            file_path = case.get("file_path", "")
            if not file_path:
                continue
            
            # Convert to relative path if absolute
            if os.path.isabs(file_path):
                try:
                    rel_path = os.path.relpath(file_path, workspace_path)
                except ValueError:
                    rel_path = file_path
            else:
                rel_path = file_path
            
            # Only check TypeScript files
            if not rel_path.endswith((".ts", ".tsx")):
                continue
            
            logger.info(f"Checking syntax for: {rel_path}")
            
            try:
                # Determine working directory for tsc command
                # If file is in frontend/tests, run tsc from frontend directory
                if rel_path.startswith("frontend/tests/") or rel_path.startswith("frontend\\tests\\"):
                    tsc_cwd = os.path.join(workspace_path, "frontend")
                    # Adjust relative path for frontend directory
                    tsc_rel_path = os.path.relpath(file_path, tsc_cwd) if os.path.isabs(file_path) else rel_path.replace("frontend/", "").replace("frontend\\", "")
                else:
                    tsc_cwd = workspace_path
                    tsc_rel_path = rel_path
                
                logger.debug(f"Running tsc in directory: {tsc_cwd}")
                logger.debug(f"Checking file: {tsc_rel_path}")
                
                # Run TypeScript compiler check
                result = subprocess.run(
                    [
                        "npx", "tsc",
                        "--allowSyntheticDefaultImports",
                        "--noEmit",
                        tsc_rel_path
                    ],
                    cwd=tsc_cwd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                syntax_results[rel_path] = {
                    "valid": result.returncode == 0,
                    "errors": result.stdout.split("\n") if result.stdout else [],
                    "stderr": result.stderr.split("\n") if result.stderr else []
                }
                
                if result.returncode != 0:
                    # Count non-empty error lines from stdout
                    error_lines = [line for line in syntax_results[rel_path]['errors'] if line.strip()]
                    logger.warning(f"Syntax errors found in {rel_path}: {len(error_lines)} errors")
                    # Log first few errors for debugging
                    for i, error in enumerate(error_lines[:3], 1):
                        logger.error(f"  Error {i}: {error[:200]}")
                else:
                    logger.info(f"Syntax check passed for {rel_path}")
                    
            except subprocess.TimeoutExpired:
                syntax_results[rel_path] = {
                    "valid": False,
                    "errors": ["Syntax check timed out"],
                    "stderr": []
                }
                logger.error(f"Syntax check timed out for {rel_path}")
            except Exception as e:
                syntax_results[rel_path] = {
                    "valid": False,
                    "errors": [f"Syntax check failed: {str(e)}"],
                    "stderr": []
                }
                logger.error(f"Syntax check error for {rel_path}: {e}")
        
        return syntax_results
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_cases": {
                    "type": "array",
                    "description": "List of test case objects with file_path",
                    "items": {"type": "object"}
                },
                "workspace_path": {
                    "type": "string",
                    "description": "Workspace root path for running tsc",
                    "default": None
                }
            },
            "required": ["test_cases"]
        }

