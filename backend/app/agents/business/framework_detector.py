"""Framework detection agent."""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
import os
import logging

logger = logging.getLogger(__name__)


class FrameworkDetectorAgent(BaseAgent):
    """Agent for detecting E2E test frameworks in projects.
    
    This agent wraps framework detection methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language prompts)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="framework_detector",
            description="Detect E2E test frameworks in projects",
            llm_provider=llm_provider
        )
        
        # Create tools from framework detection methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        system_prompt = "You are a helpful assistant for detecting test frameworks. " \
                       "You can check package.json files, find test files, and detect which E2E test framework a project uses. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from framework detection methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Import MCP tools
        from app.mcp.tools.mid_level.framework_tools import (
            check_package_json_for_framework,
            find_test_files_by_pattern,
            check_test_files_for_framework
        )
        
        # Store reference to self for closure
        detector = self
        
        @tool
        def detect_test_framework_tool(workspace_path: str) -> Dict[str, Any]:
            """Detect existing E2E test framework in project.
            
            Args:
                workspace_path: Workspace path to detect framework in
            
            Returns:
                Dict containing:
                - success: bool
                - framework: Framework name (playwright, cypress, etc.)
                - version: Framework version (if found)
                - config_file: Config file name (if found)
                - test_dir: Test directory (if found)
                - frontend_path: Frontend project path (if found)
                - confidence: Detection confidence (high, medium, low, default)
                - evidence: List of evidence strings
            """
            import asyncio
            try:
                return asyncio.run(
                    detector.detect(workspace_path=workspace_path)
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    detector.detect(workspace_path=workspace_path)
                )
            except Exception as e:
                logger.error(f"Error detecting framework: {e}")
                return {"success": False, "error": str(e)}
        
        # Return both the custom tool and the MCP tools
        return [
            detect_test_framework_tool,
            check_package_json_for_framework,
            find_test_files_by_pattern,
            check_test_files_for_framework
        ]
    
    async def detect(self, workspace_path: str) -> Dict[str, Any]:
        """Detect test framework by checking package.json and test files.
        
        Args:
            workspace_path: Path to workspace directory
        
        Returns:
            Dict with framework detection results
        """
        framework_info = {
            "framework": None,
            "version": None,
            "config_file": None,
            "test_dir": None,
            "frontend_path": None,
            "confidence": "low",
            "evidence": []
        }
        
        # Import MCP tools
        from app.mcp.tools.mid_level.framework_tools import (
            check_package_json_for_framework,
            check_test_files_for_framework
        )
        
        # Common frontend directory names
        frontend_dirs = ["frontend", "client", "web", "app", "ui"]
        search_paths = [workspace_path]  # Start with root
        
        # Add frontend subdirectories to search paths
        for dir_name in frontend_dirs:
            frontend_path = os.path.join(workspace_path, dir_name)
            if os.path.isdir(frontend_path):
                search_paths.append(frontend_path)
        
        # Search for package.json in all potential paths
        for search_path in search_paths:
            package_json_path = os.path.join(search_path, "package.json")
            if os.path.exists(package_json_path):
                result = check_package_json_for_framework.invoke({
                    "package_json_path": package_json_path,
                    "search_path": search_path
                })
                if result and result.get("framework"):
                    framework_info.update(result)
                    # If found in subdirectory, record it
                    if search_path != workspace_path:
                        framework_info["frontend_path"] = search_path
                        framework_info["evidence"].append(f"Found frontend project in: {os.path.basename(search_path)}/")
                    break
        
        # Check for test files to infer framework if not found
        if not framework_info["framework"] or framework_info["confidence"] == "low":
            for search_path in search_paths:
                result = check_test_files_for_framework.invoke({
                    "search_path": search_path,
                    "workspace_path": workspace_path
                })
                if result and result.get("framework"):
                    framework_info.update(result)
                    if search_path != workspace_path:
                        framework_info["frontend_path"] = search_path
                    break
        
        # Default to Playwright if nothing found
        if not framework_info["framework"]:
            framework_info["framework"] = "playwright"
            framework_info["confidence"] = "default"
            framework_info["evidence"].append("No test framework detected, defaulting to Playwright")
            # Default to frontend directory if it exists
            for dir_name in frontend_dirs:
                frontend_path = os.path.join(workspace_path, dir_name)
                if os.path.isdir(frontend_path):
                    framework_info["frontend_path"] = frontend_path
                    framework_info["evidence"].append(f"Will use frontend directory: {dir_name}/")
                    break
        
        return {
            "success": True,
            "framework": framework_info["framework"],
            "version": framework_info.get("version"),
            "config_file": framework_info.get("config_file"),
            "test_dir": framework_info.get("test_dir"),
            "frontend_path": framework_info.get("frontend_path"),
            "confidence": framework_info["confidence"],
            "evidence": framework_info["evidence"]
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Detect test framework in /path/to/workspace")
            action: Direct action name ("detect")
            workspace_path: Workspace path (required for direct action)
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "detect":
            workspace_path = kwargs.get("workspace_path", "")
            if workspace_path:
                return await self.detect(workspace_path=workspace_path)
        
        # If prompt is provided and agent is available, use agent
        if prompt and self.agent:
            try:
                result = self.agent.invoke({
                    "messages": [{"role": "user", "content": prompt}]
                })
                return {"result": result}
            except Exception as e:
                logger.error(f"Error executing agent prompt: {e}")
                return {"error": str(e)}
        
        # Fallback to direct detect if workspace_path provided
        workspace_path = kwargs.get("workspace_path", "")
        if workspace_path:
            return await self.detect(workspace_path=workspace_path)
        
        return {"error": "No valid action or prompt provided. Provide 'prompt', 'action', or 'workspace_path'."}

