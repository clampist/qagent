"""Case result checker tool (MCP)."""
from typing import Dict, Any
from app.mcp.base import MCPTool


class CaseResultCheckerTool(MCPTool):
    """Check test execution results and determine next action."""
    
    def __init__(self):
        super().__init__(
            name="case_result_checker",
            description="Check test results and decide whether to proceed or retry",
            tool_type="high"
        )
    
    async def execute(
        self,
        test_results: Dict[str, Any],
        retry_count: int = 0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Check test results and return action decision."""
        # Check if tests passed
        passed = test_results.get("passed", False)
        results = test_results.get("results", [])
        
        # Calculate summary
        summary = {
            "passed": passed,
            "total_tests": len(results),
            "passed_count": sum(1 for r in results if r.get("success")),
            "failed_count": sum(1 for r in results if not r.get("success"))
        }
        
        # Determine next action
        if passed:
            return {
                "success": True,
                "action": "create_pr",
                "summary": summary,
                "ready_for_pr": True
            }
        else:
            # Check if we should retry
            if retry_count < max_retries:
                return {
                    "success": True,
                    "action": "retry",
                    "summary": summary,
                    "retry_count": retry_count + 1,
                    "retry_reason": "Test execution failed"
                }
            else:
                # Max retries reached
                return {
                    "success": False,
                    "action": "error",
                    "summary": summary,
                    "error": f"Test execution failed after {max_retries} retries"
                }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_results": {
                    "type": "object",
                    "description": "Test execution results from CaseExecutionTool"
                },
                "retry_count": {
                    "type": "integer",
                    "description": "Current retry count",
                    "default": 0
                },
                "max_retries": {
                    "type": "integer",
                    "description": "Maximum number of retries allowed",
                    "default": 2
                }
            },
            "required": ["test_results"]
        }

