"""Integration tests for workflow orchestration."""
import pytest
from unittest.mock import patch, AsyncMock, Mock
from app.orchestration.workflow import WorkflowManager, WorkflowState
from app.models.task import TaskStatus, TaskStage


@pytest.mark.integration
class TestWorkflowOrchestration:
    """Test workflow orchestration."""
    
    @pytest.fixture
    def workflow_manager(self):
        """Create workflow manager with mocked dependencies."""
        manager = WorkflowManager()
        
        # Mock dependencies
        manager.sandbox_manager = Mock()
        manager.sandbox_manager.create_sandbox = AsyncMock(return_value="sandbox_123")
        
        manager.workspace_manager = Mock()
        manager.workspace_manager.clone_repo = AsyncMock(return_value="/tmp/workspace")
        
        manager.github_client = Mock()
        manager.github_client.check_permissions = AsyncMock(return_value={"has_permission": True})
        
        return manager
    
    @pytest.mark.asyncio
    async def test_workflow_initialization(self, workflow_manager):
        """Test workflow initialization."""
        state = WorkflowState()
        state.task_id = "test_123"
        state.pr_number = 123
        state.repo_full_name = "test/repo"
        
        result = await workflow_manager._initialize(state)
        
        assert result.stage == TaskStage.INITIALIZING
        assert result.status == TaskStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_create_sandbox_node(self, workflow_manager):
        """Test sandbox creation node."""
        state = WorkflowState()
        state.task_id = "test_123"
        
        result = await workflow_manager._create_sandbox(state)
        
        assert result.stage == TaskStage.SANDBOX_CREATION
        assert result.sandbox_id == "sandbox_123"
    
    @pytest.mark.asyncio
    async def test_clone_repo_node(self, workflow_manager):
        """Test repository cloning node."""
        state = WorkflowState()
        state.repo_full_name = "test/repo"
        state.pr_number = 123
        
        result = await workflow_manager._clone_repo(state)
        
        assert result.stage == TaskStage.REPO_CLONE
        assert result.workspace_path == "/tmp/workspace"
    
    @pytest.mark.asyncio
    async def test_analyze_requirements_node(self, workflow_manager, sample_pr_data):
        """Test requirement analysis node."""
        state = WorkflowState()
        state.pr_data = sample_pr_data
        state.workspace_path = "/tmp/workspace"
        
        with patch("app.orchestration.workflow.RequirementAnalyzer") as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze = AsyncMock(return_value={"analysis": {"summary": "Test"}})
            mock_analyzer_class.return_value = mock_analyzer
            
            result = await workflow_manager._analyze_requirements(state)
            
            assert result.stage == TaskStage.REQUIREMENT_ANALYSIS
            assert "requirement_analysis" in result.__dict__
    
    @pytest.mark.asyncio
    async def test_start_pr_workflow(self, workflow_manager, sample_pr_data):
        """Test starting a PR workflow."""
        result = await workflow_manager.start_pr_workflow(
            pr_number=123,
            repo_full_name="test/repo",
            pr_data=sample_pr_data
        )
        task_id = result["task_id"]
        
        assert task_id is not None
        assert task_id in workflow_manager.tasks
        assert workflow_manager.tasks[task_id].pr_number == 123
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, workflow_manager, sample_task):
        """Test getting task status."""
        workflow_manager.tasks["test_123"] = sample_task
        
        status = await workflow_manager.get_task_status("test_123")
        
        assert status is not None
        assert status.task_id == "test_123"
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, workflow_manager, sample_task):
        """Test listing tasks."""
        workflow_manager.tasks["test_1"] = sample_task
        workflow_manager.tasks["test_2"] = sample_task
        
        tasks = await workflow_manager.list_tasks(limit=10, offset=0)
        
        assert len(tasks) == 2

