"""LangGraph workflow orchestration."""
from typing import Dict, Any, Optional, List, TypedDict
from datetime import datetime
import uuid
from langgraph.graph import StateGraph, END
from app.models.task import Task, TaskStatus, TaskStage
from app.agents.business.requirement_analyzer import RequirementAnalyzer
from app.agents.business.case_designer import CaseDesigner
from app.agents.business.case_developer import CaseDeveloper
from app.agents.business.case_checker import CaseCheckerAgent
from app.infrastructure.sandbox import SandboxManager
from app.agents.business.workspace_agent import WorkspaceAgent
from app.agents.business.github_agent import GithubAgent


class WorkflowStateDict(TypedDict, total=False):
    """TypedDict for LangGraph state schema (prevents default value initialization)."""
    task_id: str
    status: TaskStatus
    stage: TaskStage
    pr_number: Optional[int]
    repo_full_name: Optional[str]
    pr_data: Dict[str, Any]
    workspace_path: Optional[str]
    sandbox_id: Optional[str]
    requirement_analysis: Dict[str, Any]
    test_framework: Optional[Dict[str, Any]]
    test_design: Dict[str, Any]
    test_cases: List[Dict[str, Any]]
    test_results: Dict[str, Any]
    test_review: Dict[str, Any]
    feedback: Optional[str]
    retry_count: int
    error_message: Optional[str]
    metadata: Dict[str, Any]
    config: Dict[str, Any]


class WorkflowState:
    """Workflow state definition."""
    def __init__(self):
        self.task_id: str = ""
        self.status: TaskStatus = TaskStatus.PENDING
        self.stage: TaskStage = TaskStage.INITIALIZING
        self.pr_number: Optional[int] = None
        self.repo_full_name: Optional[str] = None
        self.pr_data: Dict[str, Any] = {}
        self.workspace_path: Optional[str] = None
        self.sandbox_id: Optional[str] = None
        self.requirement_analysis: Dict[str, Any] = {}
        self.test_framework: Optional[Dict[str, Any]] = None  # Detected test framework info
        self.test_design: Dict[str, Any] = {}
        self.test_cases: List[Dict[str, Any]] = []
        self.test_results: Dict[str, Any] = {}
        self.test_review: Dict[str, Any] = {}  # Review feedback from CaseCheckerAgent
        self.feedback: Optional[str] = None  # Feedback for regenerating test cases
        self.retry_count: int = 0  # Number of retry attempts
        self.error_message: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        # Configuration
        self.config: Dict[str, Any] = {
            "max_test_cases": 3,  # Default: generate maximum 3 test cases
            "max_retries": 3  # Maximum retry attempts for test generation
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert WorkflowState to dictionary for LangGraph."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "stage": self.stage,
            "pr_number": self.pr_number,
            "repo_full_name": self.repo_full_name,
            "pr_data": self.pr_data,
            "workspace_path": self.workspace_path,
            "sandbox_id": self.sandbox_id,
            "requirement_analysis": self.requirement_analysis,
            "test_framework": self.test_framework,
            "test_design": self.test_design,
            "test_cases": self.test_cases,
            "test_results": self.test_results,
            "test_review": self.test_review,
            "feedback": self.feedback,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """Create WorkflowState from dictionary."""
        state = cls()
        state.task_id = data.get("task_id", "")
        state.status = data.get("status", TaskStatus.PENDING)
        state.stage = data.get("stage", TaskStage.INITIALIZING)
        state.pr_number = data.get("pr_number")
        state.repo_full_name = data.get("repo_full_name")
        state.pr_data = data.get("pr_data", {})
        state.workspace_path = data.get("workspace_path")
        state.sandbox_id = data.get("sandbox_id")
        state.requirement_analysis = data.get("requirement_analysis", {})
        state.test_framework = data.get("test_framework")
        state.test_design = data.get("test_design", {})
        state.test_cases = data.get("test_cases", [])
        state.test_results = data.get("test_results", {})
        state.test_review = data.get("test_review", {})
        state.feedback = data.get("feedback")
        state.retry_count = data.get("retry_count", 0)
        state.error_message = data.get("error_message")
        state.metadata = data.get("metadata", {})
        state.config = data.get("config", {"max_test_cases": 3, "max_retries": 3})
        return state


class WorkflowManager:
    """Manages workflow execution using LangGraph."""
    
    def __init__(self):
        self.graph = self._build_graph()
        self.tasks: Dict[str, Task] = {}
        self.sandbox_manager = SandboxManager()
        self.workspace_agent = WorkspaceAgent()
        self.github_agent = GithubAgent()
        # Store initial state values to preserve them across node calls
        self._initial_state_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_langsmith_trace_url(self, task_id: str, wait_for_completion: bool = False) -> Optional[str]:
        """Get LangSmith trace URL for the workflow execution.
        
        Args:
            task_id: Task ID to search for in LangSmith
            wait_for_completion: If True, wait for all tracers to finish before getting URL.
                               If False, get URL immediately (may be less accurate).
            
        Returns:
            LangSmith trace URL if found, None otherwise
        """
        from app.config import settings
        import logging
        logger = logging.getLogger(__name__)
        
        # Check if LangSmith tracing is enabled
        if not settings.langsmith_tracing or settings.langsmith_tracing.lower() != "true":
            return None
        
        if not settings.langsmith_api_key:
            return None
        
        try:
            from langsmith import Client
            
            # Wait for tracers if requested
            if wait_for_completion:
                from langchain_core.tracers.langchain import wait_for_all_tracers
                import time
                wait_for_all_tracers()
                time.sleep(1)  # Give a small delay to ensure traces are indexed
            
            # Initialize LangSmith client
            client = Client(
                api_key=settings.langsmith_api_key,
                api_url=settings.langsmith_endpoint
            )
            
            # Search for runs related to this task
            project_name = settings.langsmith_project or "default"
            
            # Use different limits based on whether we're waiting
            limit = 5 if wait_for_completion else 1
            
            # Get the most recent run (should be our workflow execution)
            runs = list(client.list_runs(
                project_name=project_name,
                limit=limit,
                execution_order=1  # Get root runs only
            ))
            
            if not runs:
                # Try without project filter
                runs = list(client.list_runs(
                    limit=limit,
                    execution_order=1
                ))
            
            if runs:
                # Get the most recent run (first in the list)
                latest_run = runs[0]
                run_id = latest_run.id
                
                # Build LangSmith URL
                endpoint = settings.langsmith_endpoint or "https://api.smith.langchain.com"
                
                # Parse endpoint to get base URL
                if "eu.smith.langchain.com" in endpoint or (hasattr(latest_run, 'url') and latest_run.url and "eu.smith.langchain.com" in latest_run.url):
                    base_url = "https://eu.smith.langchain.com"
                else:
                    base_url = "https://smith.langchain.com"
                
                # Try to get organization and project from the run
                # If run has URL, use it directly
                if hasattr(latest_run, 'url') and latest_run.url:
                    return latest_run.url
                
                # Otherwise, construct URL manually
                if project_name and project_name != "default":
                    url = f"{base_url}/o/default/projects/p/{project_name}?peek={run_id}"
                    return url
                else:
                    url = f"{base_url}/traces/{run_id}"
                    return url
            
            return None
            
        except ImportError:
            if wait_for_completion:
                logger.warning("langsmith package not installed, cannot get trace URL")
            else:
                logger.debug("langsmith package not installed, cannot get trace URL")
            return None
        except Exception as e:
            if wait_for_completion:
                logger.warning(f"Error getting LangSmith trace URL: {e}")
            else:
                logger.debug(f"Error getting LangSmith trace URL: {e}")
            return None
        
    def _normalize_state(self, state) -> Dict[str, Any]:
        """Normalize state to dict (handle both WorkflowState object and dict)."""
        import logging
        logger = logging.getLogger(__name__)
        
        
        if isinstance(state, WorkflowState):
            result = state.to_dict()
            logger.debug(f"_normalize_state: Converted WorkflowState to dict, keys: {list(result.keys())}")
            logger.debug(f"_normalize_state: repo_full_name={result.get('repo_full_name')}, pr_number={result.get('pr_number')}, workspace_path={result.get('workspace_path')}")
            
            
            return result
        
        logger.debug(f"_normalize_state: State is already dict, keys: {list(state.keys()) if isinstance(state, dict) else 'not a dict'}")
        logger.debug(f"_normalize_state: repo_full_name={state.get('repo_full_name') if isinstance(state, dict) else 'N/A'}, pr_number={state.get('pr_number') if isinstance(state, dict) else 'N/A'}, workspace_path={state.get('workspace_path') if isinstance(state, dict) else 'N/A'}")
        return state
    
    def _preserve_essential_fields(self, state: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Preserve essential fields from state in node return dictionary.
        
        IMPORTANT: Check cached initial state values to avoid overwriting with None.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Get task_id to look up initial state cache
        task_id = updates.get("task_id") or state.get("task_id", "")
        initial_values = self._initial_state_cache.get(task_id, {})
        
        essential_fields = ["task_id", "pr_number", "repo_full_name", "workspace_path", "pr_data"]
        for field in essential_fields:
            if field not in updates:
                # First, try to get from current state (if not None)
                if field in state and state[field] is not None:
                    updates[field] = state[field]
                    logger.debug(f"_preserve_essential_fields: Preserved {field}={state[field]} from state")
                # If state has None but initial cache has a value, use initial value
                elif field in initial_values and initial_values[field] is not None:
                    updates[field] = initial_values[field]
                    logger.debug(f"_preserve_essential_fields: Restored {field}={initial_values[field]} from initial cache")
                elif field in state and state[field] is None:
                    logger.debug(f"_preserve_essential_fields: Skipping {field}=None (no initial value in cache)")
                else:
                    logger.debug(f"_preserve_essential_fields: Field {field} not in state or cache")
            else:
                logger.debug(f"_preserve_essential_fields: Field {field} already in updates: {updates[field]}")
        
        logger.debug(f"_preserve_essential_fields: Final updates keys: {list(updates.keys())}")
        logger.debug(f"_preserve_essential_fields: workspace_path={updates.get('workspace_path')}, pr_number={updates.get('pr_number')}")
        return updates
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow graph."""
        # Use TypedDict instead of class to prevent LangGraph from creating default instances
        # that overwrite initial state values
        workflow = StateGraph(WorkflowStateDict)
        
        # Add nodes
        workflow.add_node("initialize", self._initialize)
        workflow.add_node("create_sandbox", self._create_sandbox)
        workflow.add_node("check_permissions", self._check_permissions)
        workflow.add_node("clone_repo", self._clone_repo)
        workflow.add_node("analyze_requirements", self._analyze_requirements)
        workflow.add_node("startup_service", self._startup_service)  # New node
        workflow.add_node("detect_framework", self._detect_framework)  # New node
        workflow.add_node("design_tests", self._design_tests)
        workflow.add_node("develop_cases", self._develop_cases)
        workflow.add_node("setup_e2e_environment", self._setup_e2e_environment)  # New node
        workflow.add_node("run_tests", self._run_tests)
        workflow.add_node("check_results", self._check_results)
        workflow.add_node("agent_chain_review", self._agent_chain_review)  # New review node
        workflow.add_node("create_pr", self._create_pr)
        workflow.add_node("handle_error", self._handle_error)
        
        # Define edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "create_sandbox")
        workflow.add_edge("create_sandbox", "check_permissions")
        workflow.add_edge("check_permissions", "clone_repo")
        workflow.add_edge("clone_repo", "analyze_requirements")
        workflow.add_edge("analyze_requirements", "startup_service")  # Added
        workflow.add_edge("startup_service", "detect_framework")  # Added
        workflow.add_edge("detect_framework", "design_tests")  # Added
        workflow.add_edge("design_tests", "develop_cases")
        workflow.add_edge("develop_cases", "setup_e2e_environment")  # Added
        workflow.add_edge("setup_e2e_environment", "run_tests")  # Added
        workflow.add_edge("run_tests", "check_results")
        workflow.add_edge("check_results", "agent_chain_review")  # Always review after check
        workflow.add_conditional_edges(
            "agent_chain_review",
            self._should_retry_or_proceed,
            {
                "create_pr": "create_pr",
                "retry": "develop_cases",  # Retry with feedback
                "error": "handle_error"
            }
        )
        workflow.add_edge("create_pr", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def start_pr_workflow(
        self,
        pr_number: int,
        repo_full_name: str,
        pr_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start a new PR workflow.
        
        Returns:
            Dict containing:
            - task_id: Task identifier
            - langsmith_trace_url: LangSmith trace URL (if available)
        """
        task_id = str(uuid.uuid4())
        
        state = WorkflowState()
        state.task_id = task_id
        state.pr_number = pr_number
        state.repo_full_name = repo_full_name
        state.pr_data = pr_data
        state.status = TaskStatus.RUNNING
        state.stage = TaskStage.INITIALIZING
        
        # Create task record
        task = Task(
            task_id=task_id,
            status=TaskStatus.RUNNING,
            stage=TaskStage.INITIALIZING,
            pr_number=pr_number,
            repo_full_name=repo_full_name,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={"pr_data": pr_data}
        )
        self.tasks[task_id] = task
        
        # Run workflow asynchronously (in production, use Celery)
        # For now, we'll run it in background
        import asyncio
        asyncio.create_task(self._run_workflow(state))
        
        # Try to get LangSmith trace URL immediately after starting workflow
        # Wait a short time for LangGraph to create the trace
        langsmith_trace_url = None
        try:
            import time
            await asyncio.sleep(0.5)  # Wait 500ms for trace to be created
            langsmith_trace_url = self._get_langsmith_trace_url(task_id, wait_for_completion=False)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not get LangSmith trace URL immediately: {e}")
        
        return {
            "task_id": task_id,
            "langsmith_trace_url": langsmith_trace_url
        }
    
    async def _run_workflow(self, initial_state: WorkflowState):
        """Execute workflow with given initial state."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Convert WorkflowState to dict for LangGraph
            initial_dict = initial_state.to_dict()
            logger.debug(f"_run_workflow: Initial state keys: {list(initial_dict.keys())}")
            logger.debug(f"_run_workflow: Initial state - repo_full_name={initial_dict.get('repo_full_name')}, pr_number={initial_dict.get('pr_number')}, workspace_path={initial_dict.get('workspace_path')}")
            
            # Cache initial state values to preserve them across node calls
            # This is necessary because LangGraph may convert dict to WorkflowState with default values
            task_id = initial_dict.get("task_id", "")
            self._initial_state_cache[task_id] = {
                "pr_number": initial_dict.get("pr_number"),
                "repo_full_name": initial_dict.get("repo_full_name"),
                "workspace_path": initial_dict.get("workspace_path"),
                "pr_data": initial_dict.get("pr_data", {}),
                "task_id": task_id
            }
            logger.debug(f"_run_workflow: Cached initial state values for task_id={task_id}: {self._initial_state_cache[task_id]}")
            
            
            final_dict = await self.graph.ainvoke(initial_dict)
            
            # Clean up cache after workflow completes
            if task_id in self._initial_state_cache:
                del self._initial_state_cache[task_id]
            
            logger.debug(f"_run_workflow: Final state keys: {list(final_dict.keys())}")
            logger.debug(f"_run_workflow: Final state - repo_full_name={final_dict.get('repo_full_name')}, pr_number={final_dict.get('pr_number')}, workspace_path={final_dict.get('workspace_path')}")
            
            # Convert back to WorkflowState
            final_state = WorkflowState.from_dict(final_dict)
            # Update task status
            if final_state.error_message:
                self.tasks[final_state.task_id].status = TaskStatus.FAILED
            else:
                self.tasks[final_state.task_id].status = TaskStatus.COMPLETED
            self.tasks[final_state.task_id].stage = final_state.stage
            self.tasks[final_state.task_id].completed_at = datetime.now()
            
            # Get and print LangSmith trace URL if tracing is enabled
            try:
                langsmith_url = self._get_langsmith_trace_url(task_id)
                if langsmith_url:
                    logger.info(f"\n{'='*70}")
                    logger.info(f"LangSmith Trace URL for task {task_id}:")
                    logger.info(f"{langsmith_url}")
                    logger.info(f"{'='*70}\n")
                    print(f"\n{'='*70}")
                    print(f"LangSmith Trace URL for task {task_id}:")
                    print(f"{langsmith_url}")
                    print(f"{'='*70}\n")
            except Exception as e:
                logger.warning(f"Failed to get LangSmith trace URL: {e}")
        except Exception as e:
            if initial_state.task_id in self.tasks:
                self.tasks[initial_state.task_id].status = TaskStatus.FAILED
                self.tasks[initial_state.task_id].error_message = str(e)
    
    # Workflow node implementations
    async def _initialize(self, state) -> Dict[str, Any]:
        """Initialize workflow state."""
        import logging
        logger = logging.getLogger(__name__)
        
        
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        logger.debug(f"_initialize: Received state keys: {list(state.keys())}")
        logger.debug(f"_initialize: repo_full_name={state.get('repo_full_name')}, pr_number={state.get('pr_number')}, workspace_path={state.get('workspace_path')}")
        
        result = self._preserve_essential_fields(state, {
            "stage": TaskStage.INITIALIZING,
            "status": TaskStatus.RUNNING
        })
        logger.debug(f"_initialize: Returning workspace_path={result.get('workspace_path')}, pr_number={result.get('pr_number')}")
        return result
    
    async def _create_sandbox(self, state) -> Dict[str, Any]:
        """Create sandbox environment."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        sandbox_id = await self.sandbox_manager.create_sandbox()
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.SANDBOX_CREATION,
            "sandbox_id": sandbox_id
        })
    
    async def _check_permissions(self, state) -> Dict[str, Any]:
        """Check repository permissions."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        # Check if we have required permissions to clone and create PR
        perm_result = await self.github_agent.check_permissions(
            state["repo_full_name"],
            required_permissions=["pull", "push"]
        )
        
        result = {
            "stage": TaskStage.PERMISSION_CHECK,
            "metadata": {**state.get("metadata", {}), "permissions": perm_result.get("permissions", {})}
        }
        
        if not perm_result.get("has_permission", False):
            result["error_message"] = f"Insufficient permissions: {perm_result.get('error', 'Unknown error')}"
            result["status"] = TaskStatus.FAILED
        
        return self._preserve_essential_fields(state, result)
    
    async def _clone_repo(self, state) -> Dict[str, Any]:
        """Clone repository and fetch PR data."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        
        logger.debug(f"_clone_repo: Received state keys: {list(state.keys())}")
        logger.debug(f"_clone_repo: repo_full_name={state.get('repo_full_name')}, pr_number={state.get('pr_number')}, workspace_path={state.get('workspace_path')}")
        
        # Validate required fields
        repo_full_name = state.get("repo_full_name")
        pr_number = state.get("pr_number")
        
        if not repo_full_name:
            return self._preserve_essential_fields(state, {
                "error_message": "repo_full_name is required but was not provided",
                "status": TaskStatus.FAILED
            })
        if pr_number is None:
            return self._preserve_essential_fields(state, {
                "error_message": "pr_number is required but was not provided",
                "status": TaskStatus.FAILED
            })
        
        # Clone repository
        logger.debug(f"_clone_repo: Cloning repo {repo_full_name}, PR {pr_number}")
        workspace_path = await self.workspace_agent.clone_repo(
            repo_full_name,
            pr_number
        )
        
        logger.debug(f"_clone_repo: Clone result - workspace_path={workspace_path}")
        
        # Validate workspace_path was created successfully
        if not workspace_path:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to clone repository: {repo_full_name}")
            return self._preserve_essential_fields(state, {
                "error_message": f"Failed to clone repository: {repo_full_name}",
                "status": TaskStatus.FAILED,
                "stage": TaskStage.REPO_CLONE
            })
        
        pr_data = state.get("pr_data", {})
        # Fetch PR data if not already provided (e.g., from manual trigger)
        if not pr_data or not pr_data.get("title"):
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Fetching PR data for {state['repo_full_name']}#{state['pr_number']}")
            
            pr_data = await self.github_agent.get_pr(
                state["repo_full_name"],
                state["pr_number"]
            )
            
            # Update task metadata
            if state["task_id"] in self.tasks:
                self.tasks[state["task_id"]].metadata["pr_data"] = pr_data
            
            logger.info(f"PR data fetched: title='{pr_data.get('title', 'N/A')}'")
        
        # Save PR data to markdown for reference
        metadata = state.get("metadata", {}).copy()
        try:
            from app.mcp.tools.mid_level.markdown_export import MarkdownExportTool
            import logging
            logger = logging.getLogger(__name__)
            
            export_tool = MarkdownExportTool()
            export_result = await export_tool.execute(
                output_data=pr_data,
                stage_name="pr_information",
                task_id=state["task_id"],
                workspace_path=workspace_path
            )
            
            if export_result.get("success"):
                metadata["pr_info_file"] = export_result["filepath"]
                logger.info(f"PR information saved to: {export_result['filepath']}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to save PR information to markdown: {e}")
        
        result = self._preserve_essential_fields(state, {
            "stage": TaskStage.REPO_CLONE,
            "workspace_path": workspace_path,
            "pr_data": pr_data,
            "metadata": metadata
        })
        logger.debug(f"_clone_repo: Returning result keys: {list(result.keys())}")
        logger.debug(f"_clone_repo: Returning workspace_path={result.get('workspace_path')}, pr_number={result.get('pr_number')}")
        return result
    
    async def _analyze_requirements(self, state) -> Dict[str, Any]:
        """Analyze PR requirements."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        
        logger.debug(f"_analyze_requirements: Received state keys: {list(state.keys())}")
        logger.debug(f"_analyze_requirements: repo_full_name={state.get('repo_full_name')}, pr_number={state.get('pr_number')}, workspace_path={state.get('workspace_path')}")
        
        if not state.get("workspace_path"):
            logger.error(f"_analyze_requirements: workspace_path is None! State: {state}")
        
        # Use global default (settings.llm_provider), or pass llm_provider="anthropic" to override
        analyzer = RequirementAnalyzer()
        analysis = await analyzer.analyze(
            pr_data=state["pr_data"],
            workspace_path=state["workspace_path"],
            save_to_markdown=True,
            task_id=state["task_id"]
        )
        
        metadata = state.get("metadata", {}).copy()
        # Store markdown file path if generated
        if "markdown_file" in analysis:
            metadata["requirement_analysis_review_file"] = analysis["markdown_file"]
        
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.REQUIREMENT_ANALYSIS,
            "requirement_analysis": analysis,
            "metadata": metadata
        })
    
    async def _startup_service(self, state) -> Dict[str, Any]:
        """Start service and run smoke test before E2E testing."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.mcp.tools.high_level.service_startup import ServiceStartupTool
        
        startup_tool = ServiceStartupTool()
        
        # Note: We don't have frontend_path yet (it's detected in next step)
        # But startup script should be in frontend directory
        startup_result = await startup_tool.execute(
            workspace_path=state["workspace_path"],
            startup_script="start_e2e_smoke.sh"
        )
        
        # Store startup results in metadata
        metadata = state.get("metadata", {}).copy()
        metadata["service_startup"] = startup_result
        
        result = {
            "stage": TaskStage.SERVICE_STARTUP,
            "metadata": metadata
        }
        
        # If startup failed, mark workflow as failed and stop
        if not startup_result.get("service_ready", False):
            result["error_message"] = f"Service startup failed: {startup_result.get('error', 'Unknown error')}"
            result["status"] = TaskStatus.FAILED
        
        return self._preserve_essential_fields(state, result)
    
    async def _detect_framework(self, state) -> Dict[str, Any]:
        """Detect existing test framework in the project."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.agents.business.framework_detector import FrameworkDetectorAgent
        
        detector = FrameworkDetectorAgent()
        framework_info = await detector.detect(workspace_path=state["workspace_path"])
        
        metadata = state.get("metadata", {}).copy()
        metadata["test_framework"] = framework_info
        
        # Log framework detection output
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: FRAMEWORK_DETECTION (Task: {state['task_id']})")
        logger.info(f"{'='*70}")
        logger.info(f"Framework: {framework_info.get('framework', 'unknown')}")
        logger.info(f"Version: {framework_info.get('version', 'N/A')}")
        logger.info(f"Confidence: {framework_info.get('confidence', 'unknown')}")
        logger.info(f"Config File: {framework_info.get('config_file', 'N/A')}")
        logger.info(f"Test Dir: {framework_info.get('test_dir', 'N/A')}")
        logger.info(f"Frontend Path: {framework_info.get('frontend_path', 'N/A')}")
        logger.info(f"Evidence:")
        for evidence in framework_info.get('evidence', []):
            logger.info(f"  - {evidence}")
        logger.info(f"{'='*70}\n")
        
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.FRAMEWORK_DETECTION,
            "test_framework": framework_info,
            "metadata": metadata
        })
    
    async def _design_tests(self, state) -> Dict[str, Any]:
        """Design test cases."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        # Use global default (settings.llm_provider), or pass llm_provider="anthropic" to override
        # Example: designer = CaseDesigner(llm_provider="anthropic")
        designer = CaseDesigner()
        # Pass detected framework to designer
        design = await designer.design(
            requirement_analysis=state["requirement_analysis"],
            workspace_path=state["workspace_path"],
            test_framework=state.get("test_framework"),
            save_to_markdown=True,
            task_id=state["task_id"],
            max_test_cases=state.get("config", {}).get("max_test_cases", 3)
        )
        
        metadata = state.get("metadata", {}).copy()
        # Store markdown file path if generated
        if "markdown_file" in design:
            metadata["test_design_review_file"] = design["markdown_file"]
        
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.TEST_DESIGN,
            "test_design": design,
            "metadata": metadata
        })
    
    async def _develop_cases(self, state) -> Dict[str, Any]:
        """Develop test cases."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        import logging
        logger = logging.getLogger(__name__)
        
        retry_count = state.get("retry_count", 0)
        # Log retry information if this is a retry
        if retry_count > 0:
            logger.info(f"\n{'='*70}")
            logger.info(f"RETRY ATTEMPT {retry_count} - Regenerating test cases with feedback")
            logger.info(f"{'='*70}")
            if state.get("feedback"):
                logger.info(f"Feedback from reviewer: {state['feedback'][:500]}...")
            logger.info(f"{'='*70}\n")
        
        # Use global default (settings.llm_provider), or pass llm_provider="anthropic" to override
        # Example: developer = CaseDeveloper(llm_provider="anthropic")
        developer = CaseDeveloper(llm_provider="openai")
        
        # Log data passed to developer for debugging
        ref_files_count = len(state.get("requirement_analysis", {}).get("reference_files", []))
        logger.info(f"[DEBUG] Passing to CaseDeveloper: requirement_analysis with {ref_files_count} reference_files")
        
        cases = await developer.develop(
            state["test_design"],
            state["workspace_path"],
            requirement_analysis=state.get("requirement_analysis"),  # Pass requirement_analysis to get reference_files
            previous_feedback=state.get("feedback") if retry_count > 0 else None  # Pass feedback for retry
        )
        
        # Log case development output
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: CASE_DEVELOPMENT (Task: {state['task_id']})")
        logger.info(f"{'='*70}")
        logger.info(f"Test Files Generated: {len(cases)} files")
        
        for idx, case in enumerate(cases, 1):
            logger.info(f"  {idx}. File: {case.get('file_path', 'N/A')}")
            logger.info(f"     Syntax Valid: {case.get('syntax_valid', False)}")
            
            if case.get('syntax_errors'):
                logger.warning(f"     Syntax Errors: {len(case.get('syntax_errors', []))} errors")
                for error in case.get('syntax_errors', [])[:3]:
                    logger.warning(f"       - {error[:100]}")
            
            code_lines = case.get('code', '').count('\\n') if case.get('code') else 0
            logger.info(f"     Code Lines: ~{code_lines}")
            
            test_cases_count = len(case.get('test_cases', []))
            logger.info(f"     Test Cases Covered: {test_cases_count}")
        
        logger.info(f"{'='*70}\n")
        
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.CASE_DEVELOPMENT,
            "test_cases": cases
        })
    
    async def _setup_e2e_environment(self, state) -> Dict[str, Any]:
        """Setup E2E test environment (install dependencies, browsers, etc)."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.mcp.tools.high_level.e2e_env_setup import E2EEnvironmentSetupTool
        
        setup_tool = E2EEnvironmentSetupTool()
        # Get frontend path from test_framework if available
        test_framework = state.get("test_framework")
        frontend_path = test_framework.get("frontend_path") if test_framework else None
        
        setup_result = await setup_tool.execute(
            workspace_path=state["workspace_path"],
            frontend_path=frontend_path,
            force_reinstall=False  # Only install if node_modules doesn't exist
        )
        
        # Store setup results in metadata
        metadata = state.get("metadata", {}).copy()
        metadata["e2e_setup"] = setup_result
        
        result = {
            "stage": TaskStage.ENV_SETUP,
            "metadata": metadata
        }
        
        if not setup_result.get("success"):
            result["error_message"] = f"E2E environment setup failed: {setup_result.get('error', 'Unknown error')}"
            result["status"] = TaskStatus.FAILED
        
        return self._preserve_essential_fields(state, result)
    
    async def _run_tests(self, state) -> Dict[str, Any]:
        """Execute generated test cases."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.mcp.tools.high_level.case_runner import CaseExecutionTool
        
        executor = CaseExecutionTool()
        # Get frontend path from test_framework if available
        test_framework = state.get("test_framework")
        frontend_path = test_framework.get("frontend_path") if test_framework else None
        
        test_results = await executor.execute(
            workspace_path=state["workspace_path"],
            test_cases=state["test_cases"],
            frontend_path=frontend_path,  # Pass frontend path
            run_full_suite=True  # Run both new tests and full suite
        )
        
        result = {
            "stage": TaskStage.TEST_EXECUTION,
            "test_results": test_results
        }
        
        if not test_results.get("success"):
            result["error_message"] = test_results.get("error", "Test execution failed")
            result["status"] = TaskStatus.FAILED
        
        # Log test execution output
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: TEST_EXECUTION (Task: {state['task_id']})")
        logger.info(f"{'='*70}")
        logger.info(f"Execution Success: {test_results.get('success', False)}")
        logger.info(f"All Tests Passed: {test_results.get('passed', False)}")
        logger.info(f"Total Test Files: {test_results.get('total_tests', 0)}")
        logger.info(f"New Tests Passed: {test_results.get('new_tests_passed', 'N/A')}")
        logger.info(f"Full Suite Passed: {test_results.get('full_suite_passed', 'N/A')}")
        logger.info(f"Stage Completed: {test_results.get('stage_completed', 'unknown')}")
        
        logger.info(f"\nTest Results Detail:")
        for idx, result_item in enumerate(test_results.get('results', []), 1):
            result_type = result_item.get('type', 'individual')
            logger.info(f"  {idx}. {result_type.upper()}")
            
            if result_type == 'full_suite':
                logger.info(f"     Success: {result_item.get('success', False)}")
                logger.info(f"     Exit Code: {result_item.get('exit_code', 'N/A')}")
                logger.info(f"     Command: {result_item.get('command', 'N/A')}")
            else:
                logger.info(f"     File: {result_item.get('file', 'N/A')}")
                logger.info(f"     Success: {result_item.get('success', False)}")
                logger.info(f"     Exit Code: {result_item.get('exit_code', 'N/A')}")
            
            if not result_item.get('success'):
                stderr = result_item.get('stderr', '')
                if stderr:
                    logger.error(f"     Error: {stderr[:200]}...")
        
        if test_results.get('error'):
            logger.error(f"\nExecution Error: {test_results.get('error')}")
        
        logger.info(f"{'='*70}\n")
        
        return self._preserve_essential_fields(state, result)
    
    async def _check_results(self, state) -> Dict[str, Any]:
        """Check test execution results (basic pass/fail check)."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.mcp.tools.high_level.case_result_checker import CaseResultCheckerTool
        
        checker = CaseResultCheckerTool()
        check_result = await checker.execute(
            test_results=state["test_results"],
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("config", {}).get("max_retries", 3)
        )
        
        # Store summary in metadata
        metadata = state.get("metadata", {}).copy()
        metadata["test_execution_summary"] = check_result.get("summary", {})
        metadata["basic_check_result"] = check_result
        
        # TODO 检查结果没问题后 stop service
        return self._preserve_essential_fields(state, {
            "stage": TaskStage.RESULT_CHECK,
            "metadata": metadata
        })
    
    async def _agent_chain_review(self, state) -> Dict[str, Any]:
        """Review test results using CaseCheckerAgent (LLM-based review with feedback)."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        import logging
        logger = logging.getLogger(__name__)
        
        # Use CaseCheckerAgent for detailed review
        # Use global default provider (can be overridden by passing llm_provider parameter)
        # For dedicated review model, configure in .env: OPENAI_MODEL_FOR_CHECK or ANTHROPIC_MODEL_FOR_CHECK
        checker = CaseCheckerAgent(llm_provider=None)  # Use global default from settings
        
        review_result = await checker.review(
            test_results=state["test_results"],
            test_cases=state["test_cases"],
            test_design=state["test_design"],
            requirement_analysis=state.get("requirement_analysis", {}),
            retry_count=state.get("retry_count", 0),
            max_retries=state.get("config", {}).get("max_retries", 3),
            workspace_path=state["workspace_path"]  # Pass workspace_path for syntax checking
        )
        
        result = {
            "stage": TaskStage.RESULT_CHECK,
            "test_review": review_result
        }
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: TEST_REVIEW (Task: {state['task_id']})")
        logger.info(f"{'='*70}")
        logger.info(f"Review Approved: {review_result.get('approved', False)}")
        logger.info(f"Action: {review_result.get('action', 'unknown')}")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("config", {}).get("max_retries", 3)
        logger.info(f"Retry Count: {retry_count} / {max_retries}")
        
        if review_result.get("approved", False):
            logger.info("✅ Tests approved - ready to create PR")
        else:
            feedback_data = review_result.get("feedback", {})
            if isinstance(feedback_data, dict):
                feedback_text = feedback_data.get("feedback", "")
                logger.info(f"Feedback provided: {feedback_text}...")
                # Store feedback for next retry
                result["feedback"] = feedback_text
            else:
                result["feedback"] = str(feedback_data)
            
            result["retry_count"] = review_result.get("retry_count", retry_count + 1)
            logger.info(f"Will retry with feedback (attempt {result['retry_count']})")
        
        logger.info(f"{'='*70}\n")
        
        return self._preserve_essential_fields(state, result)
    
    async def _create_pr(self, state) -> Dict[str, Any]:
        """Create a pull request with generated test cases."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        from app.mcp.tools.high_level.pr_creator import PRCreatorTool
        
        creator = PRCreatorTool()
        pr_result = await creator.execute(
            workspace_path=state["workspace_path"],
            repo_full_name=state["repo_full_name"],
            pr_number=state["pr_number"],
            test_cases=state["test_cases"],
            test_summary=state.get("metadata", {}).get("test_execution_summary", {}),
            test_framework=state.get("test_framework") or {},
            base_branch=state.get("pr_data", {}).get("base", {}).get("ref", "main")
        )
        
        metadata = state.get("metadata", {}).copy()
        result = {
            "stage": TaskStage.PR_CREATION,
            "metadata": metadata
        }
        
        if pr_result.get("success"):
            metadata["created_pr"] = {
                "number": pr_result.get("pr_number"),
                "url": pr_result.get("pr_url"),
                "branch": pr_result.get("branch")
            }
            result["status"] = TaskStatus.COMPLETED
            result["stage"] = TaskStage.COMPLETED
        else:
            result["error_message"] = pr_result.get("error", "Failed to create PR")
            result["status"] = TaskStatus.FAILED
        
        return self._preserve_essential_fields(state, result)
    
    async def _handle_error(self, state) -> Dict[str, Any]:
        """Handle workflow errors."""
        # Handle both dict and WorkflowState object (not used in this function, but for consistency)
        state = self._normalize_state(state)
        return self._preserve_essential_fields(state, {
            "status": TaskStatus.FAILED
        })
    
    def _should_retry_or_proceed(self, state) -> str:
        """Conditional edge function for review results."""
        # Handle both dict and WorkflowState object
        state = self._normalize_state(state)
        if state.get("error_message"):
            return "error"
        
        # Check if review approved
        review_result = state.get("test_review", {})
        if review_result.get("approved", False):
            return "create_pr"
        
        # Check if max retries reached
        max_retries = state.get("config", {}).get("max_retries", 3)
        retry_count = state.get("retry_count", 0)
        if retry_count >= max_retries:
            return "error"
        
        # Retry with feedback
        return "retry"
    
    async def get_task_status(self, task_id: str) -> Optional[Task]:
        """Get task status."""
        return self.tasks.get(task_id)
    
    async def list_tasks(self, limit: int = 10, offset: int = 0) -> List[Task]:
        """List tasks."""
        tasks = list(self.tasks.values())
        return tasks[offset:offset + limit]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED
            return True
        return False

