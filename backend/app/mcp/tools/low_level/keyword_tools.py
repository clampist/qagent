"""Low-level keyword extraction and search tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool
import re


class KeywordExtractionTool(MCPTool):
    """Extract keywords from text using regex fallback method."""
    
    def __init__(self):
        super().__init__(
            name="keyword_extraction",
            description="Extract keywords from text using regex patterns (fallback method)",
            tool_type="low"
        )
    
    async def execute(self, title: str, body: str = "") -> Dict[str, Any]:
        """Extract keywords using simple regex.
        
        Args:
            title: Title text
            body: Body text (optional)
            
        Returns:
            Dictionary with extracted keywords (max 3)
        """
        # Extract words with underscores/hyphens (likely feature names)
        text = f"{title} {body or ''}"
        # Find words with underscores or hyphens (e.g., user_login, email-verification)
        pattern = r'\b[a-zA-Z]+[_-][a-zA-Z0-9_-]+\b'
        matches = re.findall(pattern, text)
        
        if matches:
            # Return first 3 unique matches
            seen = set()
            keywords = []
            for match in matches:
                if match.lower() not in seen:
                    keywords.append(match.lower())
                    seen.add(match.lower())
                if len(keywords) >= 3:
                    break
            return {
                "success": True,
                "keywords": keywords,
                "count": len(keywords)
            }
        
        # If no underscored/hyphenated words, extract from title
        words = re.findall(r'\b[a-zA-Z]{4,}\b', title)
        stop_words = {'add', 'update', 'fix', 'remove', 'delete', 'implement', 'feature'}
        keywords = [w.lower() for w in words if w.lower() not in stop_words][:3]
        
        return {
            "success": True,
            "keywords": keywords if keywords else ["unknown"],
            "count": len(keywords) if keywords else 1
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title text"},
                "body": {"type": "string", "description": "Body text (optional)", "default": ""}
            },
            "required": ["title"]
        }


class KeywordVariantsTool(MCPTool):
    """Generate keyword variants using StringVariantsTool."""
    
    def __init__(self):
        super().__init__(
            name="keyword_variants",
            description="Generate variants for keywords using string transformation",
            tool_type="low"
        )
    
    async def execute(self, keywords: List[str]) -> Dict[str, Any]:
        """Generate variants for each keyword.
        
        Args:
            keywords: List of keywords
            
        Returns:
            Dictionary mapping keyword to its variants
        """
        from app.mcp.tools.low_level.string_tools import StringVariantsTool
        
        variants_dict = {}
        tool = StringVariantsTool()
        
        for keyword in keywords:
            # Skip if keyword doesn't contain separators
            if '_' not in keyword and '-' not in keyword and ' ' not in keyword:
                variants_dict[keyword] = [keyword]
                continue
            
            result = await tool.execute(keyword)
            if result.get("success"):
                all_forms = result.get("all_forms", {})
                # Collect all unique variants
                variants = set([keyword])
                variants.update(all_forms.values())
                variants_dict[keyword] = list(variants)
            else:
                variants_dict[keyword] = [keyword]
        
        return {
            "success": True,
            "variants": variants_dict,
            "count": len(variants_dict)
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords"
                }
            },
            "required": ["keywords"]
        }

