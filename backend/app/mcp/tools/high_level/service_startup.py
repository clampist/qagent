"""Service startup and smoke test tool (MCP)."""
from typing import Dict, Any
import subprocess
import os
import time
from app.mcp.base import MCPTool


class ServiceStartupTool(MCPTool):
    """Start service and run smoke test to verify it's ready."""
    
    def __init__(self):
        super().__init__(
            name="service_startup",
            description="Start service and verify with smoke test before E2E testing",
            tool_type="high"
        )
    
    async def execute(
        self,
        workspace_path: str,
        frontend_path: str = None,
        startup_script: str = "start_e2e_smoke.sh",
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Start service and run smoke test.
        
        Args:
            workspace_path: Root workspace path
            frontend_path: Frontend project path (if different from workspace)
            startup_script: Name of the startup script (default: start_e2e_smoke.sh)
            timeout: Timeout in seconds for startup and smoke test
        
        Returns:
            Dict with startup results
        """
        # Determine where to look for startup script
        search_paths = []
        
        if frontend_path:
            search_paths.append(frontend_path)
        
        # Also check common frontend directories
        frontend_dirs = ["frontend", "client", "web", "app", "ui"]
        for dir_name in frontend_dirs:
            dir_path = os.path.join(workspace_path, dir_name)
            if os.path.isdir(dir_path) and dir_path not in search_paths:
                search_paths.append(dir_path)
        
        # Fallback to workspace root
        if workspace_path not in search_paths:
            search_paths.append(workspace_path)
        
        # Search for startup script
        startup_script_path = None
        for search_path in search_paths:
            script_path = os.path.join(search_path, startup_script)
            if os.path.exists(script_path):
                startup_script_path = script_path
                break
        
        if not startup_script_path:
            return {
                "success": False,
                "error": f"Startup script '{startup_script}' not found in any of: {[os.path.basename(p) for p in search_paths]}",
                "searched_paths": search_paths,
                "service_ready": False
            }
        
        # Check if script is executable
        if not os.access(startup_script_path, os.X_OK):
            # Try to make it executable
            try:
                os.chmod(startup_script_path, 0o755)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Startup script is not executable and cannot be made executable: {str(e)}",
                    "script_path": startup_script_path,
                    "service_ready": False
                }
        
        # Execute startup script
        script_dir = os.path.dirname(startup_script_path)
        script_name = os.path.basename(startup_script_path)
        
        print(f"Executing startup script: {startup_script_path}")
        print(f"Working directory: {script_dir}")
        
        try:
            # Run the startup script
            result = subprocess.run(
                [f"./{script_name}"],
                cwd=script_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            
            # Check if startup was successful (exit code 0)
            if result.returncode == 0:
                return {
                    "success": True,
                    "service_ready": True,
                    "script_path": startup_script_path,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "message": "Service started successfully and smoke test passed"
                }
            else:
                return {
                    "success": False,
                    "service_ready": False,
                    "script_path": startup_script_path,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": f"Startup script failed with exit code {result.returncode}",
                    "smoke_test_passed": False
                }
        
        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "service_ready": False,
                "script_path": startup_script_path,
                "error": f"Startup script timed out after {timeout} seconds",
                "timeout": timeout,
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": e.stderr.decode() if e.stderr else ""
            }
        
        except FileNotFoundError:
            return {
                "success": False,
                "service_ready": False,
                "script_path": startup_script_path,
                "error": f"Script not found or cannot be executed: {startup_script_path}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "service_ready": False,
                "script_path": startup_script_path,
                "error": f"Unexpected error during startup: {str(e)}"
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
                "startup_script": {
                    "type": "string",
                    "description": "Name of the startup script",
                    "default": "start_e2e_smoke.sh"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for startup and smoke test",
                    "default": 300
                }
            },
            "required": ["workspace_path"]
        }
