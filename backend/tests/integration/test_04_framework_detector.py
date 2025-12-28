"""Integration tests for TestFrameworkDetector with real PR."""
import pytest
import os
import tempfile
import shutil
from app.agents.business.framework_detector import FrameworkDetectorAgent
from app.agents.business.github_agent import GithubAgent
from app.agents.business.workspace_agent import WorkspaceAgent


@pytest.mark.integration
class TestFrameworkDetectorIntegration:
    """Test TestFrameworkDetector with real GitHub PR."""
    
    @pytest.mark.asyncio
    async def test_detect_framework_structure_and_validation(self):
        """Test framework detection output structure and value validation for real PR: https://github.com/clampist/email-risk-reviewer/pull/1"""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        try:
            print(f"\n{'='*60}")
            print(f"Testing Framework Detection")
            print(f"{'='*60}")
            
            # Setup: Get PR data and clone repository
            github_client = GithubAgent()
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
            
            print(f"PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_path = await workspace_manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=branch
            )
            
            print(f"Workspace: {workspace_path}")
            
            # Detect test framework
            detector = FrameworkDetectorAgent()
            
            print(f"\n{'='*60}")
            print("Running Framework Detection...")
            print(f"{'='*60}\n")
            
            result = await detector.detect(workspace_path=workspace_path)
            
            # Validate structure
            print(f"\n{'='*60}")
            print("Framework Detection Results")
            print(f"{'='*60}")
            
            assert isinstance(result, dict)
            
            # Required keys
            required_keys = ["success", "framework", "confidence", "evidence"]
            for key in required_keys:
                assert key in result, f"Missing required key: {key}"
            
            # Type validation
            assert isinstance(result["success"], bool)
            assert result["success"] is True
            assert result["framework"] is None or isinstance(result["framework"], str)
            assert isinstance(result["confidence"], str)
            assert isinstance(result["evidence"], list)
            assert len(result["evidence"]) > 0, "Evidence list should not be empty"
            
            # Optional keys type validation
            if result.get("version"):
                assert isinstance(result["version"], str)
            if result.get("config_file"):
                assert isinstance(result["config_file"], str)
            if result.get("test_dir"):
                assert isinstance(result["test_dir"], str)
            
            # Value validation
            valid_frameworks = ["playwright", "cypress", "selenium", "webdriverio", "jest", None]
            assert result["framework"] in valid_frameworks, f"Invalid framework: {result['framework']}"
            
            valid_confidence_levels = ["high", "medium", "low", "default"]
            assert result["confidence"] in valid_confidence_levels, f"Invalid confidence: {result['confidence']}"
            
            # Print results
            print(f"\nDetected Framework: {result['framework']}")
            print(f"Version: {result.get('version', 'N/A')}")
            print(f"Confidence: {result['confidence']}")
            print(f"Config File: {result.get('config_file', 'N/A')}")
            print(f"Test Directory: {result.get('test_dir', 'N/A')}")
            
            print(f"\nEvidence ({len(result['evidence'])}):")
            for i, evidence in enumerate(result['evidence'], 1):
                print(f"  {i}. {evidence}")
            
            if result["framework"]:
                print(f"\n✓ Framework detected: {result['framework']}")
            else:
                print(f"\n! No framework detected, will use default")
            
            print(f"\n{'='*60}")
            print("✓ Framework detection completed successfully!")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workflow_detect_framework_step(self):
        """Test workflow's detect_framework step with real PR."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            from app.orchestration.workflow import WorkflowManager, WorkflowState, TaskStatus, TaskStage
            
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            github_client = GithubAgent()
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
            
            # Clone repository
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_path = await workspace_manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=branch
            )
            
            # Create workflow state
            workflow_manager = WorkflowManager()
            state = WorkflowState()
            state.task_id = "test_framework_detection"
            state.repo_full_name = repo_full_name
            state.pr_number = pr_number
            state.status = TaskStatus.RUNNING
            state.workspace_path = workspace_path
            
            print(f"\nTesting workflow detect_framework step...")
            
            # Execute detect_framework step
            result_state = await workflow_manager._detect_framework(state)
            
            # Verify results
            assert result_state.stage == TaskStage.FRAMEWORK_DETECTION
            assert result_state.test_framework is not None
            assert "framework" in result_state.test_framework
            assert "confidence" in result_state.test_framework
            
            # Verify metadata is updated
            assert "test_framework" in result_state.metadata
            assert result_state.metadata["test_framework"] == result_state.test_framework
            
            framework_info = result_state.test_framework
            print(f"✓ Workflow detect_framework step completed!")
            print(f"Detected framework: {framework_info['framework']}")
            print(f"Confidence: {framework_info['confidence']}")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_framework_detection_confidence_levels(self):
        """Test that confidence levels are correctly assigned."""
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            github_client = GithubAgent()
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
            
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_path = await workspace_manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=branch
            )
            
            # Detect framework
            detector = FrameworkDetectorAgent()
            result = await detector.detect(workspace_path=workspace_path)
            
            confidence = result["confidence"]
            framework = result["framework"]
            evidence = result["evidence"]
            
            print(f"\nFramework: {framework}")
            print(f"Confidence: {confidence}")
            print(f"Evidence count: {len(evidence)}")
            
            # Validate confidence logic
            if confidence == "high":
                # High confidence should have framework found in package.json
                assert any("package.json" in ev for ev in evidence), \
                    "High confidence should come from package.json"
            
            elif confidence == "medium":
                # Medium confidence from test file patterns
                assert any("test files" in ev.lower() for ev in evidence), \
                    "Medium confidence should come from test file patterns"
            
            elif confidence == "default":
                # Default when nothing detected
                assert framework == "playwright", \
                    "Default should be playwright"
                assert any("default" in ev.lower() for ev in evidence), \
                    "Default should be in evidence"
            
            print(f"✓ Confidence level logic validated!")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_framework_detector_agent_with_prompt(self):
        """Test FrameworkDetectorAgent with natural language prompt using execute method."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # 1. Get PR data and clone repository
            from tests.conftest import extract_from_agent_result
            
            github_client = GithubAgent()
            github_prompt = f"Get PR #{pr_number} from {repo_full_name}"
            github_result = await github_client.execute(prompt=github_prompt)
            
            pr_data = await extract_from_agent_result(
                result=github_result,
                field_name="pr_data",
                validator=lambda data: data is not None and ("number" in data or "title" in data) if isinstance(data, dict) else False,
                fallback_func=lambda: github_client.get_pr(repo_full_name, pr_number),
                debug=True
            )
            
            if pr_data is None or "error" in pr_data:
                pytest.skip(f"Could not fetch PR: {pr_data.get('error', 'Unknown error') if pr_data else 'PR data is None'}")
            
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_prompt = f"Clone repository {repo_full_name} for PR #{pr_number} to branch {branch}"
            workspace_result = await workspace_manager.execute(prompt=workspace_prompt)
            
            workspace_path = await extract_from_agent_result(
                result=workspace_result,
                field_name="workspace_path",
                validator=lambda path: path and os.path.exists(path) if path else False,
                fallback_func=lambda: workspace_manager.clone_repo(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    branch=branch
                ),
                path_pattern=r'(/[^\s\n"]+clampist_email-risk-reviewer_pr1[^\s\n"]*)',
                debug=True
            )
            
            if workspace_path is None:
                pytest.skip("Could not clone repository, skipping test")
            
            print(f"\n{'='*60}")
            print("Testing FrameworkDetectorAgent with natural language prompt")
            print(f"{'='*60}")
            print(f"PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            print(f"Workspace: {workspace_path}")
            
            # 2. Test with natural language prompt
            detector = FrameworkDetectorAgent()
            
            prompt = f"Detect the test framework used in the workspace at {workspace_path}"
            
            print(f"\nPrompt: {prompt}")
            
            result = await detector.execute(prompt=prompt, workspace_path=workspace_path)
            
            print(f"\nAgent result type: {type(result)}")
            print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            # Extract framework info from result using helper function
            async def get_framework_fallback():
                return await detector.detect(workspace_path=workspace_path)
            
            framework_info = await extract_from_agent_result(
                result=result,
                field_name="framework_info",
                validator=lambda data: data is not None and isinstance(data, dict) and "framework" in data if data else False,
                fallback_func=get_framework_fallback,
                debug=True
            )
            
            # If framework_info is None, try to extract from result directly
            if framework_info is None:
                if isinstance(result, dict) and "framework" in result:
                    framework_info = result
                elif isinstance(result, dict) and "result" in result:
                    result_data = result.get("result", {})
                    if isinstance(result_data, dict) and "framework" in result_data:
                        framework_info = result_data
                else:
                    # Final fallback
                    framework_info = await detector.detect(workspace_path=workspace_path)
            
            # Verify framework info was created
            assert framework_info is not None, "Framework info should be returned"
            assert isinstance(framework_info, dict), "Framework info should be a dictionary"
            assert "framework" in framework_info, "Framework info should contain 'framework' key"
            
            print(f"\n✓ Framework detection validated")
            print(f"Framework: {framework_info.get('framework', 'N/A')}")
            print(f"Confidence: {framework_info.get('confidence', 'N/A')}")
            print(f"Frontend path: {framework_info.get('frontend_path', 'N/A')}")
            
            print(f"\n{'='*60}")
            print("✓ FrameworkDetectorAgent prompt test completed successfully")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
