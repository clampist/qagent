"""Low-level formatting tools (MCP)."""
from typing import Dict, Any
from app.mcp.base import MCPTool


class TestFileFormatterTool(MCPTool):
    """Format test file contents for prompts."""
    
    def __init__(self):
        super().__init__(
            name="test_file_formatter",
            description="Format test file contents for prompts",
            tool_type="low"
        )
    
    async def execute(self, test_file_contents: Dict[str, str], max_files: int = 10) -> Dict[str, Any]:
        """Format test file contents for prompt.
        
        Args:
            test_file_contents: Dict of {file_path: content}
            max_files: Maximum number of files to include
            
        Returns:
            Dictionary with formatted string
        """
        if not test_file_contents:
            formatted = "## Existing Test Files\nNo existing test files found for reference.\n"
        else:
            formatted = "## Existing Test Files (for style and pattern reference)\n\n"
            formatted += "Study these files carefully to match the project's testing style (showing first ~100 lines):\n\n"
            
            for file_path, content in list(test_file_contents.items())[:max_files]:
                formatted += f"### File: {file_path}\n"
                formatted += f"```typescript\n{content}\n```\n\n"
            
            if len(test_file_contents) > max_files:
                formatted += f"... and {len(test_file_contents) - max_files} more test files available\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "file_count": len(test_file_contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_file_contents": {
                    "type": "object",
                    "description": "Dictionary of file paths to contents",
                    "additionalProperties": {"type": "string"}
                },
                "max_files": {"type": "integer", "description": "Maximum files to include", "default": 10}
            },
            "required": ["test_file_contents"]
        }


class FrontendFileFormatterTool(MCPTool):
    """Format frontend changed files for prompts."""
    
    def __init__(self):
        super().__init__(
            name="frontend_file_formatter",
            description="Format frontend changed files for prompts",
            tool_type="low"
        )
    
    async def execute(self, frontend_changed_contents: Dict[str, str]) -> Dict[str, Any]:
        """Format frontend changed files for prompt.
        
        Args:
            frontend_changed_contents: Dict of {file_path: content}
            
        Returns:
            Dictionary with formatted string
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not frontend_changed_contents:
            formatted = "## Frontend Changed Files\nNo frontend source files were changed in this PR.\n"
        else:
            formatted = "## Frontend Changed Files (from PR changes)\n\n"
            formatted += "These are the frontend source files modified in this PR (understand what changed):\n\n"
            
            # Log file list before processing
            file_list = list(frontend_changed_contents.keys())
            logger.info(f"Frontend changed files to format ({len(file_list)} files):")
            for idx, file_path in enumerate(file_list, 1):
                logger.info(f"  {idx}. {file_path}")
            
            for file_path, content in frontend_changed_contents.items():
                formatted += f"### File: {file_path}\n"
                formatted += f"```typescript\n{content}\n```\n\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "file_count": len(frontend_changed_contents)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "frontend_changed_contents": {
                    "type": "object",
                    "description": "Dictionary of file paths to contents",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["frontend_changed_contents"]
        }


class PageObjectFormatterTool(MCPTool):
    """Format page-objects and helpers for prompts."""
    
    def __init__(self):
        super().__init__(
            name="page_object_formatter",
            description="Format page-objects and helpers for prompts",
            tool_type="low"
        )
    
    async def execute(self, po_helper_contents: Dict[str, str]) -> Dict[str, Any]:
        """Format page-objects and helpers for prompt.
        
        Args:
            po_helper_contents: Dict of {file_path: content}
            
        Returns:
            Dictionary with formatted string
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Initialize variables to avoid UnboundLocalError
        page_objects = {}
        helpers = {}
        fixtures = {}
        
        if not po_helper_contents:
            formatted = "## Page Objects and Helpers\nNo page-objects or helpers found for reference.\n"
        else:
            formatted = "## Page Objects and Helpers (COMPLETE content - use these APIs!)\n\n"
            formatted += "🚨 CRITICAL: Study these files to understand AVAILABLE methods and properties.\n"
            formatted += "ONLY use methods that exist in these files. DO NOT invent new methods!\n\n"
            
            # Log file list before processing
            file_list = list(po_helper_contents.keys())
            logger.info(f"Page objects and helpers files to format ({len(file_list)} files):")
            for idx, file_path in enumerate(file_list, 1):
                logger.info(f"  {idx}. {file_path}")
            
            # Group by type
            for file_path, content in po_helper_contents.items():
                if 'page-objects/' in file_path or 'page_objects/' in file_path:
                    page_objects[file_path] = content
                elif 'helpers/' in file_path:
                    helpers[file_path] = content
                elif 'fixtures/' in file_path:
                    fixtures[file_path] = content
            
            # Output page objects
            if page_objects:
                formatted += "### Page Objects\n\n"
                for file_path, content in page_objects.items():
                    formatted += f"#### File: {file_path}\n"
                    formatted += f"```typescript\n{content}\n```\n\n"
            
            # Output helpers
            if helpers:
                formatted += "### Helpers\n\n"
                for file_path, content in helpers.items():
                    formatted += f"#### File: {file_path}\n"
                    formatted += f"```typescript\n{content}\n```\n\n"
            
            # Output fixtures
            if fixtures:
                formatted += "### Fixtures\n\n"
                for file_path, content in fixtures.items():
                    formatted += f"#### File: {file_path}\n"
                    formatted += f"```typescript\n{content}\n```\n\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "file_count": len(po_helper_contents) if po_helper_contents else 0,
            "page_objects_count": len(page_objects),
            "helpers_count": len(helpers),
            "fixtures_count": len(fixtures)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "po_helper_contents": {
                    "type": "object",
                    "description": "Dictionary of file paths to contents",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["po_helper_contents"]
        }


class GitDiffFormatterTool(MCPTool):
    """Format git diff for prompts."""
    
    def __init__(self):
        super().__init__(
            name="git_diff_formatter",
            description="Format git diff for prompts",
            tool_type="low"
        )
    
    async def execute(self, git_diff: str, max_length: int = 5000) -> Dict[str, Any]:
        """Format git diff for prompt.
        
        Args:
            git_diff: Git diff output
            max_length: Maximum length to truncate to
            
        Returns:
            Dictionary with formatted string
        """
        if not git_diff or git_diff == "Git diff unavailable" or git_diff == "No code changes detected in frontend files":
            formatted = "## Git Diff (Frontend Code Changes)\nNo git diff available or no frontend code changes detected.\n"
        else:
            # Truncate if too long
            original_length = len(git_diff)
            if len(git_diff) > max_length:
                git_diff = git_diff[:max_length] + "\n\n... (diff truncated at {} characters)".format(max_length)
            
            formatted = "## Git Diff (Frontend Code Changes)\n\n"
            formatted += "```diff\n"
            formatted += git_diff
            formatted += "\n```\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "original_length": len(git_diff) if git_diff else 0,
            "truncated": len(git_diff) > max_length if git_diff else False
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "git_diff": {"type": "string", "description": "Git diff output"},
                "max_length": {"type": "integer", "description": "Maximum length to truncate", "default": 5000}
            },
            "required": ["git_diff"]
        }


class FailedTestFormatterTool(MCPTool):
    """Format failed test details for prompts."""
    
    def __init__(self):
        super().__init__(
            name="failed_test_formatter",
            description="Format failed test details for prompts",
            tool_type="low"
        )
    
    async def execute(self, failed_tests: list) -> Dict[str, Any]:
        """Format failed test details for prompt.
        
        Args:
            failed_tests: List of failed test objects with file, exit_code, stderr, stdout
            
        Returns:
            Dictionary with formatted string
        """
        if not failed_tests:
            formatted = "No failed tests found."
        else:
            formatted = ""
            for i, test in enumerate(failed_tests, 1):
                formatted += f"\n### Failed Test {i}: {test.get('file', 'unknown')}\n"
                formatted += f"Exit Code: {test.get('exit_code')}\n"
                if test.get('stderr'):
                    formatted += f"Error Output:\n```\n{test.get('stderr')}\n```\n"
                if test.get('stdout'):
                    formatted += f"Standard Output (first 500 chars):\n```\n{test.get('stdout')[:500]}\n```\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "failed_count": len(failed_tests)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "failed_tests": {
                    "type": "array",
                    "description": "List of failed test objects",
                    "items": {"type": "object"}
                }
            },
            "required": ["failed_tests"]
        }


class TestCaseFormatterTool(MCPTool):
    """Format test cases for prompts."""
    
    def __init__(self):
        super().__init__(
            name="test_case_formatter",
            description="Format test cases for prompts",
            tool_type="low"
        )
    
    async def execute(self, test_cases: list, max_cases: int = 5) -> Dict[str, Any]:
        """Format test cases for prompt.
        
        Args:
            test_cases: List of test case objects
            max_cases: Maximum number of test cases to show
            
        Returns:
            Dictionary with formatted string
        """
        if not test_cases:
            formatted = "No test cases provided."
        else:
            formatted = f"Total test cases: {len(test_cases)}\n\n"
            for i, case in enumerate(test_cases[:max_cases], 1):
                formatted += f"### Test Case {i}\n"
                formatted += f"File: {case.get('file_path', 'N/A')}\n"
                formatted += f"Type: {case.get('type', 'N/A')}\n"
                if case.get('syntax_errors'):
                    formatted += f"Syntax Errors: {len(case.get('syntax_errors', []))}\n"
                formatted += "\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "total_count": len(test_cases) if test_cases else 0
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_cases": {
                    "type": "array",
                    "description": "List of test case objects",
                    "items": {"type": "object"}
                },
                "max_cases": {
                    "type": "integer",
                    "description": "Maximum number of test cases to show",
                    "default": 5
                }
            },
            "required": ["test_cases"]
        }


class TestDesignFormatterTool(MCPTool):
    """Format test design for prompts."""
    
    def __init__(self):
        super().__init__(
            name="test_design_formatter",
            description="Format test design for prompts",
            tool_type="low"
        )
    
    async def execute(self, test_design: Dict[str, Any]) -> Dict[str, Any]:
        """Format test design for prompt.
        
        Args:
            test_design: Test design dictionary with 'design' key
            
        Returns:
            Dictionary with formatted string
        """
        design = test_design.get("design", {})
        test_cases = design.get("test_cases", [])
        
        formatted = f"Test Framework: {design.get('test_framework', 'N/A')}\n"
        formatted += f"Test Cases in Design: {len(test_cases)}\n"
        if test_cases:
            formatted += "\nFirst test case:\n"
            formatted += f"- Title: {test_cases[0].get('title', 'N/A')}\n"
            formatted += f"- Steps: {len(test_cases[0].get('steps', []))}\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "test_cases_count": len(test_cases)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_design": {
                    "type": "object",
                    "description": "Test design dictionary"
                }
            },
            "required": ["test_design"]
        }


class RequirementAnalysisFormatterTool(MCPTool):
    """Format requirement analysis for prompts."""
    
    def __init__(self):
        super().__init__(
            name="requirement_analysis_formatter",
            description="Format requirement analysis for prompts",
            tool_type="low"
        )
    
    async def execute(self, requirement_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format requirement analysis for prompt.
        
        Args:
            requirement_analysis: Requirement analysis dictionary
            
        Returns:
            Dictionary with formatted string
        """
        if not requirement_analysis:
            formatted = "N/A"
        else:
            formatted = f"Summary: {requirement_analysis.get('summary', 'N/A')}\n"
            formatted += f"Requirements: {len(requirement_analysis.get('requirements', []))}\n"
            formatted += f"Affected Areas: {len(requirement_analysis.get('affected_areas', []))}\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "has_data": bool(requirement_analysis)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirement_analysis": {
                    "type": "object",
                    "description": "Requirement analysis dictionary"
                }
            },
            "required": ["requirement_analysis"]
        }


class SyntaxCheckResultFormatterTool(MCPTool):
    """Format syntax check results for prompts."""
    
    def __init__(self):
        super().__init__(
            name="syntax_check_result_formatter",
            description="Format syntax check results for prompts",
            tool_type="low"
        )
    
    async def execute(self, syntax_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Format syntax check results for prompt.
        
        Args:
            syntax_results: Dict of {file_path: {valid: bool, errors: list}}
            
        Returns:
            Dictionary with formatted string
        """
        if not syntax_results:
            formatted = "No syntax check results available."
        else:
            formatted = ""
            for file_path, result in syntax_results.items():
                status = "✓ PASSED" if result.get("valid", False) else "✗ FAILED"
                formatted += f"\n### {file_path}: {status}\n"
                
                if not result.get("valid", False):
                    errors = result.get("errors", [])
                    if errors:
                        formatted += f"Errors ({len(errors)}):\n"
                        for error in errors[:5]:  # Show first 5 errors
                            if error.strip():
                                formatted += f"  - {error[:200]}\n"
                        if len(errors) > 5:
                            formatted += f"  ... and {len(errors) - 5} more errors\n"
        
        return {
            "success": True,
            "formatted": formatted,
            "files_checked": len(syntax_results),
            "passed_count": sum(1 for r in syntax_results.values() if r.get("valid", False)),
            "failed_count": sum(1 for r in syntax_results.values() if not r.get("valid", False))
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "syntax_results": {
                    "type": "object",
                    "description": "Dict of {file_path: {valid: bool, errors: list}}",
                    "additionalProperties": {"type": "object"}
                }
            },
            "required": ["syntax_results"]
        }


class ResponseParserTool(MCPTool):
    """Parse LLM review response (JSON or text)."""
    
    def __init__(self):
        super().__init__(
            name="response_parser",
            description="Parse LLM review response (JSON or text)",
            tool_type="low"
        )
    
    async def execute(self, response: str) -> Dict[str, Any]:
        """Parse LLM review response (JSON or text).
        
        Args:
            response: LLM response string (may contain JSON or plain text)
            
        Returns:
            Dictionary with parsed fields: root_causes, specific_issues, feedback, recommendations
        """
        import json
        import re
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return {
                    "success": True,
                    "root_causes": parsed.get("root_causes", []),
                    "specific_issues": parsed.get("specific_issues", []),
                    "feedback": parsed.get("feedback", response),
                    "recommendations": parsed.get("recommendations", [])
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback: treat entire response as feedback
        return {
            "success": True,
            "root_causes": [],
            "specific_issues": [],
            "feedback": response,
            "recommendations": []
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "LLM response string (may contain JSON or plain text)"
                }
            },
            "required": ["response"]
        }

