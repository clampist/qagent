"""E2E test environment setup tool (MCP)."""
from typing import Dict, Any
import subprocess
import os
from app.mcp.base import MCPTool


class E2EEnvironmentSetupTool(MCPTool):
    """Setup E2E test environment (install dependencies, browsers, etc)."""
    
    def __init__(self):
        super().__init__(
            name="e2e_environment_setup",
            description="Setup E2E test environment by installing dependencies and browsers",
            tool_type="high"
        )
    
    async def execute(
        self,
        workspace_path: str,
        frontend_path: str = None,
        force_reinstall: bool = False,
        timeout: int = 600
    ) -> Dict[str, Any]:
        """Setup E2E test environment.
        
        Args:
            workspace_path: Root workspace path
            frontend_path: Frontend project path (if different from workspace)
            force_reinstall: Force reinstall even if node_modules exists
            timeout: Timeout in seconds for each command
        
        Returns:
            Dict with setup results
        """
        # Use frontend path if provided, otherwise use workspace path
        exec_path = frontend_path if frontend_path else workspace_path
        
        # Check if package.json exists
        package_json_path = os.path.join(exec_path, "package.json")
        if not os.path.exists(package_json_path):
            return {
                "success": False,
                "error": f"No package.json found in {exec_path}",
                "steps": []
            }
        
        steps = []
        
        # Check if node_modules exists
        node_modules_path = os.path.join(exec_path, "node_modules")
        needs_install = force_reinstall or not os.path.exists(node_modules_path)
        
        if not needs_install:
            steps.append({
                "name": "check_dependencies",
                "status": "skipped",
                "message": "Dependencies already installed (node_modules exists)"
            })
        else:
            # Step 1: Install dependencies
            install_result = await self._install_dependencies(exec_path, timeout)
            steps.append(install_result)
            
            if not install_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to install dependencies",
                    "steps": steps
                }
        
        # Step 2: Install Playwright browsers (if Playwright is used)
        playwright_result = await self._install_playwright_browsers(exec_path, timeout)
        steps.append(playwright_result)
        
        # Step 3: Check if test command is available
        test_check_result = await self._check_test_command(exec_path)
        steps.append(test_check_result)
        
        # Determine overall success
        all_success = all(
            step.get("success") or step.get("status") == "skipped" 
            for step in steps
        )
        
        return {
            "success": all_success,
            "steps": steps,
            "environment_ready": all_success
        }
    
    async def _install_dependencies(self, exec_path: str, timeout: int) -> Dict[str, Any]:
        """Install npm/yarn dependencies."""
        try:
            # Try npm install first
            result = subprocess.run(
                ["npm", "install", "--legacy-peer-deps"],
                cwd=exec_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return {
                    "name": "install_dependencies",
                    "success": True,
                    "command": "npm install --legacy-peer-deps",
                    "message": "Dependencies installed successfully"
                }
            else:
                return {
                    "name": "install_dependencies",
                    "success": False,
                    "command": "npm install --legacy-peer-deps",
                    "error": result.stderr[:500],
                    "exit_code": result.returncode
                }
        except subprocess.TimeoutExpired:
            return {
                "name": "install_dependencies",
                "success": False,
                "error": f"Installation timed out after {timeout} seconds"
            }
        except FileNotFoundError:
            return {
                "name": "install_dependencies",
                "success": False,
                "error": "npm command not found. Please ensure Node.js is installed."
            }
        except Exception as e:
            return {
                "name": "install_dependencies",
                "success": False,
                "error": str(e)
            }
    
    async def _install_playwright_browsers(self, exec_path: str, timeout: int) -> Dict[str, Any]:
        """Install Playwright browsers if needed."""
        # Check if @playwright/test is in package.json
        package_json_path = os.path.join(exec_path, "package.json")
        try:
            import json
            with open(package_json_path, "r") as f:
                package_data = json.load(f)
            
            dependencies = {
                **package_data.get("dependencies", {}),
                **package_data.get("devDependencies", {})
            }
            
            has_playwright = "@playwright/test" in dependencies or "playwright" in dependencies
            
            if not has_playwright:
                return {
                    "name": "install_playwright_browsers",
                    "status": "skipped",
                    "message": "Playwright not found in dependencies"
                }
            
            # Install Playwright browsers
            result = subprocess.run(
                ["npx", "playwright", "install", "--with-deps"],
                cwd=exec_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return {
                    "name": "install_playwright_browsers",
                    "success": True,
                    "command": "npx playwright install --with-deps",
                    "message": "Playwright browsers installed successfully"
                }
            else:
                # Try without --with-deps (in case of permission issues)
                result2 = subprocess.run(
                    ["npx", "playwright", "install"],
                    cwd=exec_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result2.returncode == 0:
                    return {
                        "name": "install_playwright_browsers",
                        "success": True,
                        "command": "npx playwright install",
                        "message": "Playwright browsers installed (without system deps)",
                        "warning": "System dependencies not installed, tests may fail"
                    }
                else:
                    return {
                        "name": "install_playwright_browsers",
                        "success": False,
                        "command": "npx playwright install",
                        "error": result2.stderr[:500],
                        "exit_code": result2.returncode
                    }
        except Exception as e:
            return {
                "name": "install_playwright_browsers",
                "success": False,
                "error": str(e)
            }
    
    async def _check_test_command(self, exec_path: str) -> Dict[str, Any]:
        """Check if test command is available."""
        package_json_path = os.path.join(exec_path, "package.json")
        try:
            import json
            with open(package_json_path, "r") as f:
                package_data = json.load(f)
            
            scripts = package_data.get("scripts", {})
            test_scripts = [key for key in scripts.keys() if "test" in key or "e2e" in key]
            
            if test_scripts:
                return {
                    "name": "check_test_command",
                    "success": True,
                    "message": f"Test scripts found: {', '.join(test_scripts)}",
                    "available_scripts": test_scripts
                }
            else:
                return {
                    "name": "check_test_command",
                    "success": False,
                    "warning": "No test scripts found in package.json"
                }
        except Exception as e:
            return {
                "name": "check_test_command",
                "success": False,
                "error": str(e)
            }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Workspace path"
                },
                "frontend_path": {
                    "type": "string",
                    "description": "Frontend project path (optional)"
                },
                "force_reinstall": {
                    "type": "boolean",
                    "description": "Force reinstall dependencies",
                    "default": False
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for each command",
                    "default": 600
                }
            },
            "required": ["workspace_path"]
        }
