"""Test helper utilities."""
import os
import tempfile
import shutil
from typing import Dict, Any
from pathlib import Path


def create_test_repo_structure(base_path: str) -> Dict[str, str]:
    """Create a test repository structure."""
    files = {
        "package.json": '{"name": "test-app", "version": "1.0.0"}',
        "src/index.js": "console.log('Hello World');",
        "tests/e2e/example.spec.js": "test('example', () => {});"
    }
    
    created_files = {}
    for file_path, content in files.items():
        full_path = os.path.join(base_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        created_files[file_path] = full_path
    
    return created_files


def create_mock_pr_files(base_path: str, pr_number: int) -> Dict[str, str]:
    """Create mock PR files for testing."""
    pr_dir = os.path.join(base_path, f"pr_{pr_number}")
    os.makedirs(pr_dir, exist_ok=True)
    
    files = {
        "changed_file1.js": "export function newFeature() { return true; }",
        "changed_file2.ts": "export const newConstant = 'value';"
    }
    
    created_files = {}
    for filename, content in files.items():
        file_path = os.path.join(pr_dir, filename)
        with open(file_path, "w") as f:
            f.write(content)
        created_files[filename] = file_path
    
    return created_files


def assert_task_status(task: Any, expected_status: str, expected_stage: str = None):
    """Assert task status and stage."""
    assert task.status == expected_status
    if expected_stage:
        assert task.stage == expected_stage


def assert_workflow_state(state: Any, **expected_values):
    """Assert workflow state values."""
    for key, value in expected_values.items():
        assert hasattr(state, key), f"State missing attribute: {key}"
        assert getattr(state, key) == value, f"State.{key} = {getattr(state, key)}, expected {value}"

