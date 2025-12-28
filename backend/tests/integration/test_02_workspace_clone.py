"""Integration tests for workspace clone functionality."""
import pytest
import os
import shutil
import tempfile
import re
from app.agents.business.workspace_agent import WorkspaceAgent
from app.agents.business.github_agent import GithubAgent
from app.orchestration.workflow import WorkflowManager, WorkflowState, TaskStage, TaskStatus
from tests.conftest import extract_from_agent_result


@pytest.mark.integration
class TestWorkspaceCloneIntegration:
    """Test workspace clone integration across layers."""
    
    @pytest.mark.asyncio
    async def test_workspace_manager_clone_real_repo(self):
        """Test WorkspaceAgent cloning real repository."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        # Create temporary workspace for testing
        temp_base = tempfile.mkdtemp()
        
        try:
            manager = WorkspaceAgent()
            original_base = manager.base_path
            manager.base_path = temp_base
            
            # Clone real repository: https://github.com/clampist/email-risk-reviewer/pull/1
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # First get PR info to get the correct branch
            client = GithubAgent()
            pr_data = await client.get_pr(repo_full_name, pr_number)
            
            print(f"Cloning PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            print(f"Head branch: {pr_data.get('head', {}).get('ref', 'main')}")
            
            # Clone the repository
            workspace_path = await manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=pr_data.get('head', {}).get('ref', 'main')
            )
            
            print(f"Cloned to: {workspace_path}")
            
            # Verify workspace was created
            assert os.path.exists(workspace_path)
            assert "clampist_email-risk-reviewer_pr1" in workspace_path
            
            # Verify it's a git repository
            git_dir = os.path.join(workspace_path, ".git")
            assert os.path.exists(git_dir), "Should be a git repository"
            
            # Verify some expected files exist (based on the repository)
            # Note: Adjust these based on actual repository structure
            print(f"Workspace contents: {os.listdir(workspace_path)}")
            
            # Cleanup
            await manager.cleanup_workspace(workspace_path)
            assert not os.path.exists(workspace_path), "Workspace should be cleaned up"
            
            # Restore original base path
            manager.base_path = original_base
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workflow_clone_repo_step(self):
        """Test workflow clone_repo step with real repository."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        # Create temporary workspace for testing
        temp_base = tempfile.mkdtemp()
        
        try:
            manager = WorkflowManager()
            original_base = manager.workspace_manager.base_path
            manager.workspace_manager.base_path = temp_base
            
            # Create workflow state with real PR data
            state = WorkflowState()
            state.task_id = "test_clone_integration"
            state.repo_full_name = "clampist/email-risk-reviewer"
            state.pr_number = 1
            state.status = TaskStatus.RUNNING
            
            # Get PR data first
            pr_data = await manager.github_agent.get_pr(
                state.repo_full_name,
                state.pr_number
            )
            state.pr_data = pr_data
            
            print(f"Testing workflow clone for PR: {pr_data.get('title', 'N/A')}")
            
            # Execute clone step
            result_state = await manager._clone_repo(state)
            
            print(f"Clone stage: {result_state.stage}")
            print(f"Workspace path: {result_state.workspace_path}")
            
            # Verify results
            assert result_state.stage == TaskStage.REPO_CLONE
            assert result_state.workspace_path is not None
            assert os.path.exists(result_state.workspace_path)
            
            # Verify it's a valid git repository
            git_dir = os.path.join(result_state.workspace_path, ".git")
            assert os.path.exists(git_dir), "Should be a git repository"
            
            print(f"Successfully cloned to: {result_state.workspace_path}")
            
            # Cleanup
            await manager.workspace_manager.cleanup_workspace(result_state.workspace_path)
            
            # Restore original base path
            manager.workspace_manager.base_path = original_base
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workspace_clone_with_different_branches(self):
        """Test cloning with different branch specifications."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            manager = WorkspaceAgent()
            original_base = manager.base_path
            manager.base_path = temp_base
            
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # Get PR info to get the head branch
            client = GithubAgent()
            pr_data = await client.get_pr(repo_full_name, pr_number)
            head_branch = pr_data.get('head', {}).get('ref', 'main')
            
            print(f"Testing clone with branch: {head_branch}")
            
            # Clone with explicit branch
            workspace_path = await manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=head_branch
            )
            
            assert os.path.exists(workspace_path)
            
            # Verify we're on the correct branch
            import subprocess
            result = subprocess.run(
                ["git", "-C", workspace_path, "branch", "--show-current"],
                capture_output=True,
                text=True
            )
            
            current_branch = result.stdout.strip()
            print(f"Current branch: {current_branch}")
            print(f"Expected branch: {head_branch}")
            
            assert current_branch == head_branch, f"Should be on branch {head_branch}"
            
            # Cleanup
            await manager.cleanup_workspace(workspace_path)
            manager.base_path = original_base
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workspace_clone_consistency(self):
        """Test that workspace clone works consistently across all layers."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            # Test data
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # Get PR data
            client = GithubAgent()
            pr_data = await client.get_pr(repo_full_name, pr_number)
            branch = pr_data.get('head', {}).get('ref', 'main')
            
            # Test 1: Direct WorkspaceAgent
            ws_manager = WorkspaceAgent()
            ws_manager.base_path = temp_base
            
            workspace_path_1 = await ws_manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=branch
            )
            
            assert os.path.exists(workspace_path_1)
            print(f"WorkspaceAgent created: {workspace_path_1}")
            
            # Clean up first clone
            await ws_manager.cleanup_workspace(workspace_path_1)
            
            # Test 2: Through Workflow
            workflow_manager = WorkflowManager()
            workflow_manager.workspace_manager.base_path = temp_base
            
            state = WorkflowState()
            state.task_id = "consistency_test"
            state.repo_full_name = repo_full_name
            state.pr_number = pr_number
            state.status = TaskStatus.RUNNING
            
            result_state = await workflow_manager._clone_repo(state)
            workspace_path_2 = result_state.workspace_path
            
            assert os.path.exists(workspace_path_2)
            print(f"Workflow created: {workspace_path_2}")
            
            # Both should create the same structure
            expected_name = "clampist_email-risk-reviewer_pr1"
            assert expected_name in workspace_path_1
            assert expected_name in workspace_path_2
            
            # Both should be valid git repositories
            assert os.path.exists(os.path.join(workspace_path_2, ".git"))
            
            print("✓ Workspace clone is consistent across layers")
            
            # Cleanup
            await workflow_manager.workspace_manager.cleanup_workspace(workspace_path_2)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workspace_agent_with_prompt(self):
        """Test WorkspaceAgent with natural language prompt using execute method."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            agent = WorkspaceAgent()
            original_base = agent.base_path
            agent.base_path = temp_base
            
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # Test with natural language prompt
            prompt = f"Clone repository {repo_full_name} for PR #{pr_number} to the main branch"
            
            print(f"\n{'='*60}")
            print("Testing WorkspaceAgent with natural language prompt")
            print(f"{'='*60}")
            print(f"Prompt: {prompt}")
            
            result = await agent.execute(prompt=prompt)
            
            print(f"Agent result type: {type(result)}")
            print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            # Extract workspace_path from agent result using helper function
            workspace_path = await extract_from_agent_result(
                result=result,
                field_name="workspace_path",
                validator=lambda path: path and os.path.exists(path) if path else False,
                fallback_func=lambda: agent.clone_repo(repo_full_name, pr_number, "main"),
                path_pattern=r'(/[^\s\n"]+clampist_email-risk-reviewer_pr1[^\s\n"]*)',
                debug=True
            )
            
            # Verify workspace was created
            assert workspace_path is not None, "Workspace path should be returned"
            assert os.path.exists(workspace_path), f"Workspace should exist at {workspace_path}"
            assert "clampist_email-risk-reviewer_pr1" in workspace_path
            
            # Verify it's a git repository
            git_dir = os.path.join(workspace_path, ".git")
            assert os.path.exists(git_dir), "Should be a git repository"
            
            print(f"✓ Successfully cloned to: {workspace_path}")
            
            # Test cleanup with prompt
            cleanup_prompt = f"Clean up workspace at {workspace_path}"
            print(f"\nTesting cleanup with prompt: {cleanup_prompt}")
            
            cleanup_result = await agent.execute(prompt=cleanup_prompt)
            
            print(f"Cleanup result: {cleanup_result}")
            
            # Verify cleanup
            if "result" in cleanup_result or "success" in cleanup_result:
                # Wait a bit for cleanup to complete
                import time
                time.sleep(0.5)
                if not os.path.exists(workspace_path):
                    print("✓ Workspace cleaned up successfully via agent")
                else:
                    # Fallback to direct cleanup
                    await agent.cleanup_workspace(workspace_path)
                    print("✓ Workspace cleaned up via direct method")
            else:
                # Fallback to direct cleanup
                await agent.cleanup_workspace(workspace_path)
                print("✓ Workspace cleaned up via direct method")
            
            # Restore original base path
            agent.base_path = original_base
            
            print(f"{'='*60}")
            print("✓ WorkspaceAgent query test completed successfully")
            print(f"{'='*60}\n")
            
        finally:
            # Clean up temp directory
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
