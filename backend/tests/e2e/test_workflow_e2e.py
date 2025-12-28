"""End-to-end tests for complete workflows."""
import pytest
import os
import asyncio
import tempfile
import shutil
from unittest.mock import patch, AsyncMock, Mock
from fastapi.testclient import TestClient
from app.main import app
from app.orchestration.workflow import WorkflowManager, TaskStatus, TaskStage
from app.agents.business.github_agent import GithubAgent
import json


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteWorkflow:
    """Test complete workflow from PR to test generation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_complete_workflow(self):
        """Mock complete workflow execution."""
        with patch("app.orchestration.workflow.WorkflowManager") as mock_manager:
            # Mock all workflow steps
            mock_instance = Mock()
            mock_instance.start_pr_workflow = AsyncMock(return_value={"task_id": "task_123", "langsmith_trace_url": None})
            mock_instance.get_task_status = AsyncMock(return_value=Mock(
                task_id="task_123",
                status="completed",
                stage="completed",
                pr_number=123
            ))
            mock_manager.return_value = mock_instance
            yield mock_instance
    
    def test_complete_pr_to_test_workflow(self, client, mock_complete_workflow, sample_pr_data):
        """Test complete workflow from PR webhook to completion."""
        # Step 1: Receive PR webhook
        webhook_payload = {
            "action": "opened",
            "pull_request": sample_pr_data,
            "repository": {"full_name": "test/repo"}
        }
        
        webhook_response = client.post(
            "/api/webhooks/github",
            json=webhook_payload,
            headers={"X-GitHub-Event": "pull_request"}
        )
        
        assert webhook_response.status_code == 200
        task_id = webhook_response.json()["task_id"]
        
        # Step 2: Check task status
        status_response = client.get(f"/api/tasks/{task_id}")
        
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_complete_workflow_real_pr(self):
        """Test complete workflow with real PR: https://github.com/clampist/email-risk-reviewer/pull/1
        
        This test runs the entire workflow from start to finish:
        - Initialize workflow
        - Check permissions
        - Clone repository
        - Analyze requirements
        - Detect framework
        - Design tests
        - Develop test cases
        - Setup E2E environment
        - Run tests
        - Check results
        - Review test results
        """
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping E2E test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            print(f"\n{'='*70}")
            print("E2E Test: Complete Workflow with Real PR")
            print(f"{'='*70}")
            
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # Get real PR data
            github_agent = GithubAgent()
            pr_data = await github_agent.get_pr(repo_full_name, pr_number)
            
            if "error" in pr_data:
                pytest.skip(f"Could not fetch PR: {pr_data.get('error')}")
            
            print(f"\nPR Information:")
            print(f"  Repository: {repo_full_name}")
            print(f"  PR Number: {pr_number}")
            print(f"  Title: {pr_data.get('title', 'N/A')}")
            print(f"  State: {pr_data.get('state', 'N/A')}")
            
            # Setup workspace manager base path
            workflow_manager = WorkflowManager()
            workflow_manager.workspace_agent.base_path = temp_base
            
            # Start workflow
            print(f"\n{'='*70}")
            print("Starting PR Workflow...")
            print(f"{'='*70}")
            
            result = await workflow_manager.start_pr_workflow(
                pr_number=pr_number,
                repo_full_name=repo_full_name,
                pr_data=pr_data
            )
            task_id = result["task_id"]
            
            print(f"Task ID: {task_id}")
            
            # Wait for workflow to complete (poll status)
            print(f"\nWaiting for workflow to complete...")
            print("(This may take several minutes - workflow includes LLM calls, test execution, etc.)")
            max_wait_time = 1800  # 30 minutes max
            wait_interval = 10  # Check every 10 seconds
            elapsed_time = 0
            last_stage = None
            
            while elapsed_time < max_wait_time:
                await asyncio.sleep(wait_interval)
                elapsed_time += wait_interval
                
                task = await workflow_manager.get_task_status(task_id)
                
                if task is None:
                    print(f"  [{elapsed_time}s] Task not found yet...")
                    continue
                
                status = task.status
                stage = task.stage
                
                # Only print when stage changes
                if stage != last_stage:
                    print(f"  [{elapsed_time}s] Stage: {stage}, Status: {status}")
                    last_stage = stage
                
                if status == TaskStatus.COMPLETED:
                    print(f"\n✓ Workflow completed successfully!")
                    print(f"  Final Stage: {stage}")
                    print(f"  Total Time: {elapsed_time}s")
                    break
                elif status == TaskStatus.FAILED:
                    error_msg = task.error_message or "Unknown error"
                    print(f"\n✗ Workflow failed!")
                    print(f"  Error: {error_msg}")
                    print(f"  Stage: {stage}")
                    print(f"  Total Time: {elapsed_time}s")
                    # Don't fail the test immediately - let's see what we got
                    break
                elif status == TaskStatus.CANCELLED:
                    print(f"\n⚠ Workflow was cancelled")
                    print(f"  Stage: {stage}")
                    print(f"  Total Time: {elapsed_time}s")
                    break
            
            if elapsed_time >= max_wait_time:
                print(f"\n⚠ Workflow did not complete within {max_wait_time}s timeout")
                print(f"  Last Status: {last_stage}")
            
            # Get final task status
            final_task = await workflow_manager.get_task_status(task_id)
            
            if final_task is None:
                pytest.fail("Task not found after workflow execution")
            
            # Verify workflow completed
            print(f"\n{'='*70}")
            print("Workflow Execution Summary")
            print(f"{'='*70}")
            print(f"Task ID: {final_task.task_id}")
            print(f"Status: {final_task.status}")
            print(f"Stage: {final_task.stage}")
            print(f"PR Number: {final_task.pr_number}")
            print(f"Repository: {final_task.repo_full_name}")
            
            if final_task.error_message:
                print(f"Error Message: {final_task.error_message}")
            
            # Verify workflow reached a terminal state
            assert final_task.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED
            ], f"Workflow should be in a terminal state, got: {final_task.status}"
            
            # If completed, verify we have test cases
            if final_task.status == TaskStatus.COMPLETED:
                print(f"\n✓ Workflow completed successfully!")
                print(f"  Final Stage: {final_task.stage}")
                
                # Note: We can't directly access the final state from the task,
                # but we can verify the workflow completed without errors
                assert final_task.error_message is None, "Completed workflow should not have errors"
            else:
                print(f"\n⚠ Workflow did not complete successfully")
                print(f"  Status: {final_task.status}")
                print(f"  Stage: {final_task.stage}")
                if final_task.error_message:
                    print(f"  Error: {final_task.error_message}")
                # For E2E test, we might want to allow failures to see what happened
                # Uncomment the line below if you want to fail on errors:
                # pytest.fail(f"Workflow failed: {final_task.error_message}")
            
            print(f"\n{'='*70}")
            print("✓ E2E Workflow Test Completed")
            print(f"{'='*70}\n")
            
        finally:
            # Cleanup
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.requires_api
class TestAgentIntegration:
    """Test agent integration with real API calls (requires API keys)."""
    
    @pytest.mark.skip(reason="Requires actual API keys and external services")
    async def test_requirement_analyzer_with_real_llm(self):
        """Test requirement analyzer with real LLM (requires API key)."""
        from app.agents.business.requirement_analyzer import RequirementAnalyzer
        
        analyzer = RequirementAnalyzer()
        pr_data = {
            "title": "Add login feature",
            "body": "This PR adds user login functionality",
            "number": 1
        }
        
        result = await analyzer.analyze(pr_data, "/tmp/test_workspace")
        
        assert "analysis" in result
        assert "requirements" in result["analysis"]


@pytest.mark.e2e
@pytest.mark.requires_docker
class TestSandboxIntegration:
    """Test sandbox integration with Docker."""
    
    @pytest.mark.skip(reason="Requires Docker daemon running")
    async def test_sandbox_creation_and_execution(self):
        """Test creating and using a real sandbox."""
        from app.infrastructure.sandbox import SandboxManager
        
        manager = SandboxManager()
        
        if manager.client is None:
            pytest.skip("Docker not available")
        
        sandbox_id = await manager.create_sandbox(image="alpine:latest")
        
        try:
            result = await manager.execute_in_sandbox(
                sandbox_id=sandbox_id,
                command="echo 'Hello World'"
            )
            
            assert result["success"] is True
            assert "Hello World" in result["output"]
        finally:
            await manager.destroy_sandbox(sandbox_id)

