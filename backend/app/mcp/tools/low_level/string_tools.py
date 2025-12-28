"""Low-level string transformation tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool
import re


class StringVariantsTool(MCPTool):
    """Generate string variants with different separators (snake_case, kebab-case, space separated)."""
    
    def __init__(self):
        super().__init__(
            name="string_variants",
            description="Generate string variants with different separators (underscore, hyphen, space)",
            tool_type="low"
        )
    
    async def execute(self, input_string: str) -> Dict[str, Any]:
        """Generate string variants.
        
        Args:
            input_string: Input string (e.g., "medium_risk", "medium-risk", "medium risk")
            
        Returns:
            Dictionary with variants and metadata
            
        Examples:
            Input: "medium_risk"
            Output: {
                "success": True,
                "input": "medium_risk",
                "variants": ["medium risk", "medium-risk"],
                "all_forms": {
                    "snake_case": "medium_risk",
                    "kebab_case": "medium-risk",
                    "space_separated": "medium risk"
                }
            }
        """
        if not input_string or not input_string.strip():
            return {
                "success": False,
                "error": "Input string cannot be empty",
                "input": input_string,
                "variants": []
            }
        
        input_string = input_string.strip()
        
        # Detect input format and extract words
        words = self._extract_words(input_string)
        
        if not words:
            return {
                "success": False,
                "error": "Could not extract words from input",
                "input": input_string,
                "variants": []
            }
        
        # Generate all three forms
        snake_case = "_".join(words)
        kebab_case = "-".join(words)
        space_separated = " ".join(words)
        
        # Determine input format
        input_format = self._detect_format(input_string)
        
        # Generate variants (exclude input format)
        variants = []
        if input_format != "snake_case":
            variants.append(snake_case)
        if input_format != "kebab_case":
            variants.append(kebab_case)
        if input_format != "space_separated":
            variants.append(space_separated)
        
        return {
            "success": True,
            "input": input_string,
            "input_format": input_format,
            "variants": variants,
            "all_forms": {
                "snake_case": snake_case,
                "kebab_case": kebab_case,
                "space_separated": space_separated
            },
            "words": words
        }
    
    def _extract_words(self, s: str) -> List[str]:
        """Extract words from string regardless of separator.
        
        Args:
            s: Input string
            
        Returns:
            List of words (lowercased)
        """
        # Replace common separators with space
        s = s.replace("_", " ").replace("-", " ")
        
        # Split by space and filter empty strings
        words = [word.strip().lower() for word in s.split() if word.strip()]
        
        return words
    
    def _detect_format(self, s: str) -> str:
        """Detect the format of input string.
        
        Args:
            s: Input string
            
        Returns:
            Format name: "snake_case", "kebab_case", "space_separated", or "unknown"
        """
        if "_" in s and "-" not in s and " " not in s:
            return "snake_case"
        elif "-" in s and "_" not in s and " " not in s:
            return "kebab_case"
        elif " " in s and "_" not in s and "-" not in s:
            return "space_separated"
        else:
            return "unknown"
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "input_string": {
                    "type": "string",
                    "description": "Input string with any separator (underscore, hyphen, or space)",
                    "minLength": 1
                }
            },
            "required": ["input_string"]
        }


class StringCaseConverterTool(MCPTool):
    """Convert string between different case formats (camelCase, PascalCase, etc.)."""
    
    def __init__(self):
        super().__init__(
            name="string_case_converter",
            description="Convert string to different case formats (camelCase, PascalCase, snake_case, etc.)",
            tool_type="low"
        )
    
    async def execute(
        self,
        input_string: str,
        target_format: str = "all"
    ) -> Dict[str, Any]:
        """Convert string to different case formats.
        
        Args:
            input_string: Input string
            target_format: Target format (camelCase, PascalCase, snake_case, kebab_case, all)
            
        Returns:
            Dictionary with converted formats
        """
        if not input_string or not input_string.strip():
            return {
                "success": False,
                "error": "Input string cannot be empty"
            }
        
        input_string = input_string.strip()
        
        # Extract words
        words = self._extract_words_advanced(input_string)
        
        if not words:
            return {
                "success": False,
                "error": "Could not extract words from input"
            }
        
        # Generate all formats
        formats = {
            "snake_case": "_".join(w.lower() for w in words),
            "kebab_case": "-".join(w.lower() for w in words),
            "camelCase": words[0].lower() + "".join(w.capitalize() for w in words[1:]) if words else "",
            "PascalCase": "".join(w.capitalize() for w in words),
            "space_separated": " ".join(w.lower() for w in words),
            "SCREAMING_SNAKE_CASE": "_".join(w.upper() for w in words),
            "Train-Case": "-".join(w.capitalize() for w in words)
        }
        
        if target_format == "all":
            return {
                "success": True,
                "input": input_string,
                "formats": formats,
                "words": words
            }
        elif target_format in formats:
            return {
                "success": True,
                "input": input_string,
                "output": formats[target_format],
                "format": target_format
            }
        else:
            return {
                "success": False,
                "error": f"Unknown target format: {target_format}",
                "available_formats": list(formats.keys())
            }
    
    def _extract_words_advanced(self, s: str) -> List[str]:
        """Extract words from string with advanced parsing (handles camelCase, PascalCase, etc.).
        
        Args:
            s: Input string
            
        Returns:
            List of words
        """
        # First, handle separators
        s = s.replace("_", " ").replace("-", " ")
        
        # Split camelCase and PascalCase using regex
        # Insert space before uppercase letters
        s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
        s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
        
        # Split by space and filter
        words = [word.strip() for word in s.split() if word.strip()]
        
        return words
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "input_string": {
                    "type": "string",
                    "description": "Input string in any format",
                    "minLength": 1
                },
                "target_format": {
                    "type": "string",
                    "enum": [
                        "all",
                        "snake_case",
                        "kebab_case",
                        "camelCase",
                        "PascalCase",
                        "space_separated",
                        "SCREAMING_SNAKE_CASE",
                        "Train-Case"
                    ],
                    "description": "Target format to convert to",
                    "default": "all"
                }
            },
            "required": ["input_string"]
        }
