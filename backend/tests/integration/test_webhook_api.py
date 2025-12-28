"""Integration tests for API endpoints."""
import pytest
import os
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.models.task import TaskStatus, TaskStage
from app.agents.business.github_agent import GithubAgent


@pytest.mark.integration
class TestWebhookAPI:
    """Test webhook API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_github_webhook_pr_opened(self, client, sample_pr_data):
        """Test GitHub webhook for PR opened event."""
        with patch("app.api.webhooks.workflow_manager") as mock_manager:
            mock_manager.start_pr_workflow = AsyncMock(return_value={"task_id": "task_123", "langsmith_trace_url": None})
            
            payload = {
                "action": "opened",
                "pull_request": sample_pr_data,
                "repository": {"full_name": "test/repo"}
            }
            
            response = client.post(
                "/api/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "pull_request"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "accepted"
            assert "task_id" in response.json()
    
    def test_github_webhook_invalid_signature(self, client):
        """Test webhook with invalid signature."""
        with patch("app.config.settings.github_webhook_secret", "secret"):
            payload = {"action": "opened"}
            
            response = client.post(
                "/api/webhooks/github",
                json=payload,
                headers={
                    "X-GitHub-Event": "pull_request",
                    "X-Hub-Signature-256": "invalid_signature"
                }
            )
            
            assert response.status_code == 401
    
    def test_github_webhook_test_endpoint(self, client):
        """Test webhook test endpoint."""
        response = client.get("/api/webhooks/github/test")
        
        assert response.status_code == 200
        assert "message" in response.json()
    
    @pytest.mark.asyncio
    async def test_github_webhook_with_real_pr(self, client):
        """Test GitHub webhook with real PR data from clampist/email-risk-reviewer PR #1.
        
        This test uses the actual PR data from GitHub to verify the webhook handler
        works correctly with real-world data.
        """
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test with real PR")
        
        # Fetch real PR data from GitHub
        github_client = GithubAgent()
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        try:
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
        except Exception as e:
            pytest.skip(f"Could not fetch PR from GitHub: {e}")
        
        # Construct webhook payload matching GitHub's format
        webhook_payload = {
            "action": "opened",
            "pull_request": pr_data,
            "repository": {
                "full_name": repo_full_name,
                "name": "email-risk-reviewer",
                "owner": {
                    "login": "clampist"
                }
            }
        }
        
        # Mock workflow_manager to avoid actually running the workflow
        # Also mock webhook_secret to None to skip signature verification in tests
        with patch("app.api.webhooks.workflow_manager") as mock_manager, \
             patch("app.api.webhooks.settings.github_webhook_secret", None):
            mock_manager.start_pr_workflow = AsyncMock(return_value={"task_id": "test_task_real_pr_1", "langsmith_trace_url": None})
            
            # Send webhook request
            response = client.post(
                "/api/webhooks/github",
                json=webhook_payload,
                headers={"X-GitHub-Event": "pull_request"}
            )
            
            # Verify response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"] == "accepted"
            assert response_data["task_id"] == "test_task_real_pr_1"
            assert f"PR #{pr_number}" in response_data["message"]
            
            # Verify workflow_manager was called with correct parameters
            mock_manager.start_pr_workflow.assert_called_once()
            call_args = mock_manager.start_pr_workflow.call_args
            assert call_args.kwargs["pr_number"] == pr_number
            assert call_args.kwargs["repo_full_name"] == repo_full_name
            assert call_args.kwargs["pr_data"]["number"] == pr_number
            assert call_args.kwargs["pr_data"]["title"] == pr_data["title"]
    
    @pytest.mark.asyncio
    async def test_github_webhook_pr_synchronize_event(self, client):
        """Test GitHub webhook for PR synchronize event (update) with real PR."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        # Fetch real PR data
        github_client = GithubAgent()
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        try:
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
        except Exception as e:
            pytest.skip(f"Could not fetch PR from GitHub: {e}")
        
        # Construct webhook payload for synchronize event
        webhook_payload = {
            "action": "synchronize",
            "pull_request": pr_data,
            "repository": {
                "full_name": repo_full_name
            }
        }
        
        with patch("app.api.webhooks.workflow_manager") as mock_manager, \
             patch("app.api.webhooks.settings.github_webhook_secret", None):
            mock_manager.start_pr_workflow = AsyncMock(return_value={"task_id": "test_task_sync", "langsmith_trace_url": None})
            
            response = client.post(
                "/api/webhooks/github",
                json=webhook_payload,
                headers={"X-GitHub-Event": "pull_request"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "accepted"
            mock_manager.start_pr_workflow.assert_called_once()
    
    def test_github_webhook_ignored_event(self, client):
        """Test that non-PR events are ignored."""
        payload = {
            "action": "created",
            "issue": {"number": 123}
        }
        
        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert response.json()["event"] == "issues"
    
    def test_github_webhook_pr_closed_event(self, client):
        """Test that closed PR events are ignored."""
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 1,
                "state": "closed"
            },
            "repository": {"full_name": "test/repo"}
        }
        
        response = client.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"


@pytest.mark.integration
class TestTaskAPI:
    """Test task API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_get_task_status(self, client, sample_task):
        """Test getting task status."""
        with patch("app.api.tasks.workflow_manager") as mock_manager:
            mock_manager.get_task_status = AsyncMock(return_value=sample_task)
            
            response = client.get("/api/tasks/test_task_123")
            
            assert response.status_code == 200
            assert response.json()["task_id"] == "test_task_123"
    
    def test_get_task_not_found(self, client):
        """Test getting non-existent task."""
        with patch("app.api.tasks.workflow_manager") as mock_manager:
            mock_manager.get_task_status = AsyncMock(return_value=None)
            
            response = client.get("/api/tasks/nonexistent")
            
            assert response.status_code == 404
    
    def test_list_tasks(self, client, sample_task):
        """Test listing tasks."""
        with patch("app.api.tasks.workflow_manager") as mock_manager:
            mock_manager.list_tasks = AsyncMock(return_value=[sample_task])
            
            response = client.get("/api/tasks/")
            
            assert response.status_code == 200
            assert len(response.json()["tasks"]) == 1
    
    def test_cancel_task(self, client):
        """Test cancelling a task."""
        with patch("app.api.tasks.workflow_manager") as mock_manager:
            mock_manager.cancel_task = AsyncMock(return_value=True)
            
            response = client.post("/api/tasks/test_task_123/cancel")
            
            assert response.status_code == 200
            assert response.json()["status"] == "cancelled"


@pytest.mark.integration
class TestHealthEndpoints:
    """Test health check endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root health check."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_health_endpoint(self, client):
        """Test detailed health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

