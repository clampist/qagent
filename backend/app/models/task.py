"""Task data models."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStage(str, Enum):
    """Workflow stage enumeration."""
    INITIALIZING = "initializing"
    SANDBOX_CREATION = "sandbox_creation"
    PERMISSION_CHECK = "permission_check"
    REPO_CLONE = "repo_clone"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    SERVICE_STARTUP = "service_startup"  # New stage for service startup and smoke test
    FRAMEWORK_DETECTION = "framework_detection"
    TEST_DESIGN = "test_design"
    CASE_DEVELOPMENT = "case_development"
    ENV_SETUP = "env_setup"  # New stage for environment setup
    TEST_EXECUTION = "test_execution"
    RESULT_CHECK = "result_check"
    PR_CREATION = "pr_creation"
    COMPLETED = "completed"


class Task(BaseModel):
    """Task model."""
    model_config = ConfigDict(use_enum_values=True)
    
    task_id: str
    status: TaskStatus
    stage: TaskStage
    pr_number: Optional[int] = None
    repo_full_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}

