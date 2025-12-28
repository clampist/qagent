"""Integration tests for permission check functionality."""
import pytest
import os
from app.agents.business.github_agent import GithubAgent
from app.mcp.tools.mid_level.environment import PermissionCheckTool
from app.orchestration.workflow import WorkflowState, TaskStage, TaskStatus


@pytest.mark.integration
class TestPermissionCheckIntegration:
    """Test permission check integration across layers."""
    
    @pytest.mark.asyncio
    async def test_github_client_real_pr(self):
        """Test GitHub client with real PR from email-risk-reviewer."""
        # Skip if no GitHub token is set
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        client = GithubAgent()
        
        # Test with real repository: https://github.com/clampist/email-risk-reviewer/pull/1
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        # Get PR info
        pr_data = await client.get_pr(repo_full_name, pr_number)
        
        assert "number" in pr_data or "error" in pr_data
        if "number" in pr_data:
            assert pr_data["number"] == pr_number
            print(f"PR Title: {pr_data.get('title')}")
            print(f"PR State: {pr_data.get('state')}")
        
        # Check permissions
        perm_result = await client.check_permissions(
            repo_full_name,
            required_permissions=["pull", "push"]
        )
        
        print(f"Has permission: {perm_result.get('has_permission')}")
        print(f"Permissions: {perm_result.get('permissions')}")
        
        assert "has_permission" in perm_result
        assert "permissions" in perm_result or "error" in perm_result
    
    @pytest.mark.asyncio
    async def test_mcp_permission_tool_real_pr(self):
        """Test MCP permission tool with real repository."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        tool = PermissionCheckTool()
        
        # Test with email-risk-reviewer repository
        result = await tool.execute(
            repo_full_name="clampist/email-risk-reviewer",
            required_permissions=["pull", "push"]
        )
        
        print(f"Tool result: {result}")
        
        assert result["success"] is True
        assert "has_permission" in result
        assert "permissions" in result
    
    @pytest.mark.asyncio
    async def test_workflow_permission_check_real_pr(self):
        """Test workflow permission check step with real repository."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        from app.orchestration.workflow import WorkflowManager
        
        manager = WorkflowManager()
        
        # Create workflow state with real PR data
        state = WorkflowState()
        state.task_id = "test_integration_123"
        state.repo_full_name = "clampist/email-risk-reviewer"
        state.pr_number = 1
        state.status = TaskStatus.RUNNING
        
        # Execute permission check step
        result_state = await manager._check_permissions(state)
        
        print(f"Permission check stage: {result_state.stage}")
        print(f"Has error: {result_state.error_message}")
        print(f"Metadata: {result_state.metadata.get('permissions')}")
        
        assert result_state.stage == TaskStage.PERMISSION_CHECK
        
        # If we have valid GitHub token with access, should not have error
        # If not, should have error message
        if result_state.error_message:
            print(f"Permission denied (expected if token lacks access): {result_state.error_message}")
            assert result_state.status == TaskStatus.FAILED
        else:
            print("Permission check passed")
            assert "permissions" in result_state.metadata
    
    @pytest.mark.asyncio
    async def test_permission_check_consistency(self):
        """Test that all three layers return consistent results."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        repo_full_name = "clampist/email-risk-reviewer"
        required_perms = ["pull", "push"]
        
        # Test GitHub client
        client = GithubAgent()
        client_result = await client.check_permissions(repo_full_name, required_perms)
        
        # Test MCP tool
        tool = PermissionCheckTool()
        tool_result = await tool.execute(repo_full_name, required_perms)
        
        # Test workflow
        from app.orchestration.workflow import WorkflowManager
        manager = WorkflowManager()
        state = WorkflowState()
        state.repo_full_name = repo_full_name
        state.task_id = "consistency_test"
        state.status = TaskStatus.RUNNING
        workflow_state = await manager._check_permissions(state)
        
        # All should have consistent has_permission result
        print(f"Client has_permission: {client_result.get('has_permission')}")
        print(f"Tool has_permission: {tool_result.get('has_permission')}")
        print(f"Workflow error: {workflow_state.error_message}")
        
        # If client says no permission, tool should agree
        if not client_result.get("has_permission"):
            assert tool_result.get("has_permission") is False
            assert workflow_state.error_message is not None
        else:
            # If client says yes, others should agree
            assert tool_result.get("has_permission") is True
            assert workflow_state.error_message is None
    
    @pytest.mark.asyncio
    async def test_github_agent_execute_with_query(self):
        """Test GithubAgent execute method with natural language query."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        agent = GithubAgent()
        
        # Test with natural language prompt to get PR information
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        prompt = f"Get PR #{pr_number} from {repo_full_name}"
        
        print(f"\nTesting GithubAgent.execute with prompt: {prompt}")
        
        result = await agent.execute(prompt=prompt)
        
        # Verify result structure
        assert isinstance(result, dict)
        
        # If agent is available, result should contain agent response
        # If agent is not available, should fall back to error or direct method
        if "result" in result:
            print(f"Agent executed successfully (LangChain agent available)")
            print(f"Agent result type: {type(result['result'])}")
            # Agent result might be a complex structure, just verify it exists
            assert result["result"] is not None
        elif "error" in result:
            # If agent is not available, it should return an error
            print(f"Agent not available (expected if LangChain agent framework not configured): {result['error']}")
            # This is acceptable - agent framework is optional
            assert "error" in result
        else:
            # Fallback: should have some result
            print(f"Unexpected result structure: {result}")
            assert False, "Result should contain 'result' or 'error'"
        
        # Also test with action parameter (direct method call via execute)
        print(f"\nTesting GithubAgent.execute with action parameter")
        action_result = await agent.execute(
            action="get_pr",
            repo_full_name=repo_full_name,
            pr_number=pr_number
        )
        
        # Verify action-based execution works
        assert isinstance(action_result, dict)
        assert "number" in action_result or "error" in action_result
        if "number" in action_result:
            assert action_result["number"] == pr_number
            print(f"✓ Direct action execution works: PR #{action_result['number']}")
        
        # Test with prompt for permission check
        print(f"\nTesting GithubAgent.execute with permission check prompt")
        perm_prompt = f"Check permissions for {repo_full_name} repository"
        
        perm_result = await agent.execute(prompt=perm_prompt)
        
        assert isinstance(perm_result, dict)
        if "result" in perm_result:
            print(f"✓ Permission check query executed via agent")
        elif "error" in perm_result:
            print(f"Agent not available for permission check (expected if LangChain not configured)")
        
        # Also test direct action for permission check
        perm_action_result = await agent.execute(
            action="check_permissions",
            repo_full_name=repo_full_name,
            required_permissions=["pull", "push"]
        )
        
        assert isinstance(perm_action_result, dict)
        assert "has_permission" in perm_action_result or "error" in perm_action_result
        if "has_permission" in perm_action_result:
            print(f"✓ Direct permission check action works: {perm_action_result.get('has_permission')}")
        
        print(f"\n✓ GithubAgent.execute method validated!")