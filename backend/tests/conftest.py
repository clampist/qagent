"""Shared pytest fixtures and test utilities."""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, Callable, Awaitable
import os
import tempfile
import shutil
import json
import re
from app.config import Settings
from app.models.task import Task, TaskStatus, TaskStage
from datetime import datetime


@pytest.fixture
def test_settings():
    """Test configuration settings."""
    return Settings(
        llm_provider="openai",
        openai_api_key="test_key",
        openai_model="gpt-4",
        anthropic_api_key="test_anthropic_key",
        anthropic_model="claude-3-5-sonnet-20241022",
        github_token="test_github_token",
        redis_url="redis://localhost:6379/1",
        database_url="sqlite:///:memory:",
        workspace_base_path=tempfile.mkdtemp(),
        debug=True
    )


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    def _create_response(content: str):
        mock_response = Mock()
        mock_response.content = content
        return mock_response
    return _create_response


@pytest.fixture
def mock_llm(mock_openai_response):
    """Mock LangChain LLM (supports both OpenAI and Anthropic)."""
    with patch("app.agents.base.ChatOpenAI") as mock_openai_class, \
         patch("app.agents.base.ChatAnthropic") as mock_anthropic_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_openai_response("test response"))
        mock_openai_class.return_value = mock_llm
        mock_anthropic_class.return_value = mock_llm
        yield mock_llm


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    mock_client = Mock()
    mock_client.get_repo = Mock()
    mock_client.get_user = Mock()
    
    mock_repo = Mock()
    mock_pr = Mock()
    mock_pr.number = 123
    mock_pr.title = "Test PR"
    mock_pr.body = "Test PR description"
    mock_pr.state = "open"
    mock_pr.head.ref = "feature-branch"
    mock_pr.head.sha = "abc123"
    mock_pr.base.ref = "main"
    mock_pr.base.sha = "def456"
    mock_pr.user.login = "testuser"
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.create_pull.return_value = mock_pr
    mock_repo.permissions = Mock(admin=True, push=True, pull=True)
    mock_client.get_repo.return_value = mock_repo
    
    return mock_client


@pytest.fixture
def mock_docker_client():
    """Mock Docker client."""
    mock_client = Mock()
    mock_container = Mock()
    mock_container.id = "container_123"
    mock_container.exec_run = Mock(return_value=Mock(exit_code=0, output=b"success"))
    mock_client.containers.create.return_value = mock_container
    mock_client.containers.get.return_value = mock_container
    return mock_client


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def sample_pr_data():
    """Sample PR data for testing."""
    return {
        "number": 123,
        "title": "Add new feature",
        "body": "This PR adds a new feature to the application.",
        "state": "open",
        "head": {
            "ref": "feature-branch",
            "sha": "abc123"
        },
        "base": {
            "ref": "main",
            "sha": "def456"
        },
        "user": "testuser"
    }


@pytest.fixture
def sample_task():
    """Sample task for testing."""
    return Task(
        task_id="test_task_123",
        status=TaskStatus.PENDING,
        stage=TaskStage.INITIALIZING,
        pr_number=123,
        repo_full_name="test/repo",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={}
    )


@pytest.fixture
def mock_mcp_tool():
    """Mock MCP tool."""
    tool = Mock()
    tool.name = "test_tool"
    tool.description = "Test tool"
    tool.tool_type = "high"
    tool.execute = AsyncMock(return_value={"success": True, "result": "test"})
    tool.get_schema = Mock(return_value={
        "name": "test_tool",
        "description": "Test tool",
        "inputSchema": {}
    })
    return tool


@pytest.fixture
def mock_workflow_state():
    """Mock workflow state."""
    from app.orchestration.workflow import WorkflowState
    state = WorkflowState()
    state.task_id = "test_task_123"
    state.pr_number = 123
    state.repo_full_name = "test/repo"
    state.status = TaskStatus.PENDING
    state.stage = TaskStage.INITIALIZING
    return state


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test."""
    yield
    # Cleanup if needed


# ============================================================================
# Agent Result Extraction Utilities
# ============================================================================

async def extract_from_agent_result(
    result: Dict[str, Any],
    field_name: str,
    validator: Optional[Callable[[Any], bool]] = None,
    fallback_func: Optional[Callable[[], Awaitable[Any]]] = None,
    path_pattern: Optional[str] = None,
    debug: bool = False
) -> Any:
    """Extract a field value from agent execute result.
    
    This function handles extraction from different result formats:
    1. Agent framework result (with "result" key containing messages)
    2. Direct action result (with field_name directly in result)
    3. Error result (falls back to fallback_func)
    
    Args:
        result: Agent execute result dictionary
        field_name: Name of the field to extract (e.g., "workspace_path", "analysis", "pr_data")
        validator: Optional function to validate extracted value (returns True if valid)
        fallback_func: Optional async function to call if extraction fails
        path_pattern: Optional regex pattern for path extraction (used for workspace_path)
        debug: Whether to print debug information
    
    Returns:
        Extracted value or None if not found
    """
    extracted_value = None
    
    # Case 1: Agent framework was used (has "result" key)
    if "result" in result:
        if debug:
            print("✓ Agent framework was used")
        result_data = result.get("result", {})
        
        # Try to extract from messages
        if isinstance(result_data, dict) and "messages" in result_data:
            messages = result_data.get("messages", [])
            if debug:
                print(f"Found {len(messages)} messages")
            
            for msg in messages:
                msg_type = type(msg).__name__
                if debug:
                    print(f"  Message type: {msg_type}")
                
                if msg_type == "ToolMessage":
                    content = getattr(msg, "content", None)
                    if content:
                        extracted_value = _extract_from_content(
                            content, field_name, path_pattern, debug
                        )
                        if extracted_value and (validator is None or validator(extracted_value)):
                            if debug:
                                print(f"✓ Found {field_name} in ToolMessage")
                            break
                
                elif msg_type == "AIMessage":
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str):
                        extracted_value = _extract_from_ai_message(
                            content, field_name, path_pattern, debug
                        )
                        if extracted_value and (validator is None or validator(extracted_value)):
                            if debug:
                                print(f"✓ Found {field_name} in AIMessage")
                            break
        
        # Fallback: try direct access in result_data
        if not extracted_value and isinstance(result_data, dict):
            if field_name in result_data:
                extracted_value = result_data[field_name]
            elif field_name == "workspace_path" and "workspace_path" in result_data:
                extracted_value = result_data["workspace_path"]
            elif field_name == "analysis" and "analysis" in result_data:
                extracted_value = result_data["analysis"]
            elif field_name == "pr_data":
                # Check if result_data itself is PR data
                if "number" in result_data or "title" in result_data:
                    extracted_value = result_data
    
    # Case 2: Direct action was used (field_name directly in result)
    elif field_name in result:
        extracted_value = result[field_name]
        if debug:
            print(f"✓ Found {field_name} in direct result")
    
    # Case 3: Error result - use fallback
    elif "error" in result:
        if debug:
            print(f"⚠ Agent framework not available: {result.get('error')}")
            if fallback_func:
                print("   Falling back to direct method call")
        if fallback_func:
            extracted_value = await fallback_func()
    
    # Case 4: Try to extract from JSON string (last resort for paths)
    if not extracted_value and path_pattern:
        result_str = json.dumps(result, default=str)
        path_match = re.search(path_pattern, result_str)
        if path_match:
            potential_path = path_match.group(1)
            if os.path.exists(potential_path):
                extracted_value = potential_path
                if debug:
                    print(f"✓ Extracted {field_name} from result JSON")
    
    # Final fallback
    if not extracted_value and fallback_func:
        if debug:
            print(f"⚠ Could not extract {field_name} from agent result, using fallback")
        extracted_value = await fallback_func()
    
    return extracted_value


def _extract_from_content(
    content: Any,
    field_name: str,
    path_pattern: Optional[str] = None,
    debug: bool = False
) -> Any:
    """Extract value from message content (ToolMessage or AIMessage).
    
    Handles different content formats:
    - dict: Direct access
    - JSON string: Parse and extract
    - String: Extract JSON or path pattern
    """
    # Case 1: Content is already a dict
    if isinstance(content, dict):
        if field_name in content:
            return content[field_name]
        elif field_name == "workspace_path" and "workspace_path" in content:
            return content["workspace_path"]
        elif field_name == "analysis" and "analysis" in content:
            return content["analysis"]
        elif field_name == "pr_data":
            # Check if content itself is PR data
            if "number" in content or "title" in content:
                return content
    
    # Case 2: Content is a string - try to parse as JSON
    content_str = str(content) if not isinstance(content, str) else content
    
    # For workspace_path with pattern
    if field_name == "workspace_path" and path_pattern:
        # Check if content is a valid path
        if content_str.startswith("/"):
            content_str = content_str.strip()
            if os.path.exists(content_str):
                return content_str
            # Try regex extraction
            path_match = re.search(path_pattern, content_str)
            if path_match:
                potential_path = path_match.group(1)
                if os.path.exists(potential_path):
                    return potential_path
    
    # Try to parse as JSON
    try:
        data = json.loads(content_str)
        if isinstance(data, dict):
            if field_name in data:
                return data[field_name]
            elif field_name == "analysis" and "analysis" in data:
                return data["analysis"]
            elif field_name == "pr_data" and ("number" in data or "title" in data):
                return data
    except json.JSONDecodeError:
        # Try to extract JSON from string
        if "{" in content_str and "}" in content_str:
            json_start = content_str.find("{")
            json_end = content_str.rfind("}") + 1
            try:
                data = json.loads(content_str[json_start:json_end])
                if isinstance(data, dict):
                    if field_name in data:
                        return data[field_name]
                    elif field_name == "analysis" and "analysis" in data:
                        return data["analysis"]
                    elif field_name == "pr_data" and ("number" in data or "title" in data):
                        return data
            except json.JSONDecodeError:
                pass
    
    return None


def _extract_from_ai_message(
    content: str,
    field_name: str,
    path_pattern: Optional[str] = None,
    debug: bool = False
) -> Any:
    """Extract value from AIMessage content string."""
    # For workspace_path with pattern
    if field_name == "workspace_path" and path_pattern:
        path_match = re.search(path_pattern, content)
        if path_match:
            potential_path = path_match.group(1)
            if os.path.exists(potential_path):
                return potential_path
    
    # Try to extract JSON from content
    if field_name in content.lower():
        # Look for JSON in the content
        json_match = re.search(r'\{[^{}]*"' + field_name + r'"[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if field_name in data:
                    return data[field_name]
            except json.JSONDecodeError:
                pass
    
    return None

