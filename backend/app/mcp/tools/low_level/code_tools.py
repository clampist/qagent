"""Low-level code utility tools (MCP)."""
from typing import Dict, Any
from app.mcp.base import MCPTool
import re


class CodeCleanerTool(MCPTool):
    """Clean code by removing markdown artifacts."""
    
    def __init__(self):
        super().__init__(
            name="code_cleaner",
            description="Clean code by removing markdown artifacts",
            tool_type="low"
        )
    
    async def execute(self, code: str) -> Dict[str, Any]:
        """Clean code by removing markdown artifacts.
        
        Args:
            code: Raw code from LLM (may contain markdown)
            
        Returns:
            Dictionary with cleaned code
        """
        import logging
        logger = logging.getLogger(__name__)
        
        original_length = len(code)
        
        # Step 1: Remove markdown code blocks (```...```)
        if "```" in code:
            logger.info("Detected markdown code blocks, cleaning...")
            
            # Find all code block patterns
            pattern = r"```(?:typescript|javascript|ts|js)?\n?(.*?)```"
            matches = re.findall(pattern, code, re.DOTALL)
            
            if matches:
                # Use the first (or largest) code block
                code = max(matches, key=len)
                logger.info(f"Extracted code from markdown block (length: {len(code)})")
            else:
                # Fallback: manual extraction
                code_start = code.find("```") + 3
                # Skip language identifier line if present
                first_newline = code.find("\n", code_start)
                if first_newline != -1 and first_newline - code_start < 20:
                    # Language identifier found (typescript, javascript, etc.)
                    code_start = first_newline + 1
                
                code_end = code.rfind("```")
                if code_end > code_start:
                    code = code[code_start:code_end]
                    logger.info("Extracted code using fallback method")
        
        # Step 2: Remove leading language identifiers that somehow remained
        # Pattern: starts with "typescript" or "javascript" on first line
        lines = code.split("\n")
        if lines and lines[0].strip().lower() in ["typescript", "javascript", "ts", "js"]:
            logger.warning(f"Found language identifier at start: '{lines[0].strip()}', removing...")
            code = "\n".join(lines[1:])
        
        # Step 3: Strip leading/trailing whitespace
        code = code.strip()
        
        # Step 4: Ensure it starts with valid code (import, const, etc.)
        if code and not code.startswith(("import", "const", "let", "var", "export", "//", "/*", "type", "interface", "class", "function", "async")):
            logger.warning(f"Code starts with unexpected content: '{code[:50]}...'")
            # Try to find the first import statement
            import_pos = code.find("import")
            if import_pos > 0 and import_pos < 100:  # Within first 100 chars
                logger.info(f"Found 'import' at position {import_pos}, truncating...")
                code = code[import_pos:]
        
        cleaned_length = len(code)
        if original_length != cleaned_length:
            logger.info(f"Code cleaning: {original_length} -> {cleaned_length} chars (removed {original_length - cleaned_length} chars)")
        
        return {
            "success": True,
            "cleaned_code": code,
            "original_length": original_length,
            "cleaned_length": cleaned_length
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Raw code from LLM (may contain markdown)"}
            },
            "required": ["code"]
        }


class PathValidatorTool(MCPTool):
    """Validate that file modification is allowed (tests/ directory only)."""
    
    def __init__(self):
        super().__init__(
            name="path_validator",
            description="Validate that file modification is allowed (tests/ directory only)",
            tool_type="low"
        )
    
    async def execute(self, file_path: str) -> Dict[str, Any]:
        """Validate that file modification is allowed.
        
        Args:
            file_path: File path to validate
            
        Returns:
            Dictionary with validation result
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Normalize path
        normalized = file_path.replace("\\", "/")
        
        # Allowed patterns (tests directory only)
        allowed_patterns = [
            "tests/",
            "test/",
            "__tests__/",
        ]
        
        # Forbidden patterns (business source code)
        forbidden_patterns = [
            "src/",
            "components/",
            "pages/",
            "lib/",
            "app/",
            "backend/",
            "server/",
        ]
        
        # Check if in forbidden area
        for pattern in forbidden_patterns:
            if pattern in normalized:
                logger.warning(f"Modification rejected: {file_path} matches forbidden pattern '{pattern}'")
                return {
                    "success": True,
                    "allowed": False,
                    "reason": f"Matches forbidden pattern '{pattern}'",
                    "file_path": file_path
                }
        
        # Check if in allowed area
        for pattern in allowed_patterns:
            if pattern in normalized:
                logger.info(f"Modification allowed: {file_path} matches allowed pattern '{pattern}'")
                return {
                    "success": True,
                    "allowed": True,
                    "reason": f"Matches allowed pattern '{pattern}'",
                    "file_path": file_path
                }
        
        # Default: reject if not explicitly in tests/
        logger.warning(f"Modification rejected: {file_path} not in tests/ directory")
        return {
            "success": True,
            "allowed": False,
            "reason": "Not in tests/ directory",
            "file_path": file_path
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to validate"}
            },
            "required": ["file_path"]
        }

