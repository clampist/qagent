"""Sandbox management for isolated environments."""
from typing import Dict, Any, Optional
import docker
from app.config import settings
import uuid


class SandboxManager:
    """Manages Docker sandbox environments."""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None
    
    async def create_sandbox(
        self,
        image: str = "node:18",
        resources: Dict[str, Any] = None
    ) -> str:
        """Create a new sandbox container."""
        if not self.client:
            # Fallback: return placeholder ID
            return f"sandbox_{uuid.uuid4().hex[:8]}"
        
        try:
            container = self.client.containers.create(
                image=image,
                detach=True,
                mem_limit=resources.get("memory", "2g") if resources else "2g",
                cpu_count=resources.get("cpus", 2) if resources else 2,
                network_disabled=False,
                remove=True  # Auto-remove when stopped
            )
            return container.id
        except Exception as e:
            # Fallback on error
            return f"sandbox_{uuid.uuid4().hex[:8]}"
    
    async def execute_in_sandbox(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = None
    ) -> Dict[str, Any]:
        """Execute command in sandbox."""
        if not self.client:
            return {"success": False, "error": "Docker client not available"}
        
        try:
            container = self.client.containers.get(sandbox_id)
            exec_result = container.exec_run(
                command,
                timeout=timeout or settings.sandbox_timeout
            )
            return {
                "success": exec_result.exit_code == 0,
                "exit_code": exec_result.exit_code,
                "output": exec_result.output.decode("utf-8") if exec_result.output else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy sandbox container."""
        if not self.client:
            return True
        
        try:
            container = self.client.containers.get(sandbox_id)
            container.stop()
            container.remove()
            return True
        except Exception:
            return True  # Already removed or doesn't exist

