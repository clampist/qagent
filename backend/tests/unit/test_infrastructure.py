"""Unit tests for infrastructure layer."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.infrastructure.sandbox import SandboxManager
from app.infrastructure.workspace import WorkspaceManager
from app.infrastructure.github import GitHubClient


@pytest.mark.unit
class TestSandboxManager:
    """Test sandbox manager."""
    
    @pytest.mark.asyncio
    async def test_create_sandbox_success(self, mock_docker_client):
        """Test successful sandbox creation."""
        with patch("docker.from_env", return_value=mock_docker_client):
            manager = SandboxManager()
            
            sandbox_id = await manager.create_sandbox()
            
            assert sandbox_id is not None
            assert sandbox_id.startswith("container_") or sandbox_id.startswith("sandbox_")
    
    @pytest.mark.asyncio
    async def test_create_sandbox_fallback(self):
        """Test sandbox creation fallback when Docker unavailable."""
        with patch("docker.from_env", side_effect=Exception("Docker not available")):
            manager = SandboxManager()
            
            sandbox_id = await manager.create_sandbox()
            
            assert sandbox_id.startswith("sandbox_")
    
    @pytest.mark.asyncio
    async def test_execute_in_sandbox(self, mock_docker_client):
        """Test command execution in sandbox."""
        with patch("docker.from_env", return_value=mock_docker_client):
            manager = SandboxManager()
            
            result = await manager.execute_in_sandbox(
                sandbox_id="container_123",
                command="echo test"
            )
            
            assert result["success"] is True
            assert result["exit_code"] == 0


@pytest.mark.unit
class TestWorkspaceManager:
    """Test workspace manager."""
    
    @pytest.mark.asyncio
    async def test_clone_repo(self, temp_workspace):
        """Test repository cloning."""
        manager = WorkspaceManager()
        manager.base_path = temp_workspace
        
        with patch.object(manager.git_tool, "execute") as mock_clone:
            mock_clone.return_value = {"success": True, "output": "Cloned"}
            
            workspace_path = await manager.clone_repo(
                repo_full_name="test/repo",
                pr_number=123
            )
            
            assert workspace_path is not None
            assert "test_repo_pr123" in workspace_path
    
    @pytest.mark.asyncio
    async def test_clone_repo_failure(self, temp_workspace):
        """Test repository cloning failure."""
        manager = WorkspaceManager()
        manager.base_path = temp_workspace
        
        with patch.object(manager.git_tool, "execute") as mock_clone:
            mock_clone.return_value = {"success": False, "error": "Clone failed"}
            
            with pytest.raises(Exception):
                await manager.clone_repo(
                    repo_full_name="test/repo",
                    pr_number=123
                )


@pytest.mark.unit
class TestGitHubClient:
    """Test GitHub client."""
    
    @pytest.mark.asyncio
    async def test_get_pr(self, mock_github_client):
        """Test getting PR information."""
        with patch("app.infrastructure.github.Github", return_value=mock_github_client):
            client = GitHubClient()
            client.client = mock_github_client
            
            result = await client.get_pr("test/repo", 123)
            
            assert result["number"] == 123
            assert result["title"] == "Test PR"
    
    @pytest.mark.asyncio
    async def test_create_pr(self, mock_github_client):
        """Test creating PR."""
        with patch("app.infrastructure.github.Github", return_value=mock_github_client):
            client = GitHubClient()
            client.client = mock_github_client
            
            result = await client.create_pr(
                repo_full_name="test/repo",
                title="Test PR",
                body="Test body",
                head="feature-branch"
            )
            
            assert result["success"] is True
            assert result["number"] == 123
    
    @pytest.mark.asyncio
    async def test_check_permissions(self, mock_github_client):
        """Test permission checking."""
        with patch("app.infrastructure.github.Github", return_value=mock_github_client):
            client = GitHubClient()
            client.client = mock_github_client
            
            result = await client.check_permissions("test/repo")
            
            assert result["has_permission"] is True
            assert result["permissions"]["admin"] is True

