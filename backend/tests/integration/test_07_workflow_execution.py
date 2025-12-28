"""Integration tests for workflow test execution and result checking."""
import pytest
import os
import tempfile
import shutil
from app.orchestration.workflow import WorkflowManager, WorkflowState, TaskStatus, TaskStage
from app.agents.business.github_agent import GithubAgent
from app.agents.business.workspace_agent import WorkspaceAgent
from app.agents.business.requirement_analyzer import RequirementAnalyzer
from app.agents.business.framework_detector import FrameworkDetectorAgent
from app.agents.business.case_designer import CaseDesigner
from app.agents.business.case_developer import CaseDeveloper
from app.agents.business.case_checker import CaseCheckerAgent
from tests.conftest import extract_from_agent_result


def merge_node_result(state: WorkflowState, result) -> WorkflowState:
    """Merge node function result (dict) back into WorkflowState object."""
    if isinstance(result, dict):
        state_dict = state.to_dict()
        state_dict.update(result)
        return WorkflowState.from_dict(state_dict)
    return result


@pytest.mark.integration
class TestWorkflowExecution:
    """Test workflow execution stages: run_tests and check_results."""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_comprehensive(self):
        """Comprehensive workflow execution test with real PR: https://github.com/clampist/email-risk-reviewer/pull/1
        
        Tests the complete workflow execution stages:
        - Service startup (optional)
        - E2E environment setup
        - Test execution
        - Result checking (basic check)
        - Test review (LLM-based review)
        """
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            print(f"\n{'='*60}")
            print("Testing Workflow Execution Stages (Comprehensive)")
            print(f"{'='*60}")
            
            # Setup workflow
            workflow_manager = WorkflowManager()
            state = WorkflowState()
            state.task_id = "test_execution_workflow"
            state.repo_full_name = "clampist/email-risk-reviewer"
            state.pr_number = 1
            state.status = TaskStatus.RUNNING
            state.retry_count = 0
            state.config = {"max_retries": 3}
            
            # 1. Get real PR and setup workspace
            github_client = GithubAgent()
            pr_data = await github_client.get_pr(state.repo_full_name, state.pr_number)
            
            print(f"\n1. PR Information:")
            print(f"   PR #{state.pr_number}: {pr_data.get('title', 'N/A')}")
            
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_path = await workspace_manager.clone_repo(
                repo_full_name=state.repo_full_name,
                pr_number=state.pr_number,
                branch=branch
            )
            
            state.workspace_path = workspace_path
            state.pr_data = pr_data
            
            print(f"   Workspace: {workspace_path}")
            
            # 2. Prepare test cases
            print(f"\n2. Preparing Test Cases:")
            
            analyzer = RequirementAnalyzer()
            requirement_analysis = await analyzer.analyze(pr_data, workspace_path)
            print(f"   ✓ Requirements analyzed: {len(requirement_analysis['analysis']['requirements'])}")
            
            detector = FrameworkDetectorAgent()
            framework_info = await detector.detect(workspace_path=workspace_path)
            state.test_framework = framework_info
            print(f"   ✓ Framework detected: {framework_info['framework']}")
            
            designer = CaseDesigner()
            test_design = await designer.design(
                requirement_analysis,
                workspace_path,
                framework_info
            )
            print(f"   ✓ Tests designed: {len(test_design['design']['test_cases'])} cases")
            
            developer = CaseDeveloper()
            test_cases = await developer.develop(test_design, workspace_path, requirement_analysis)
            state.test_cases = test_cases
            print(f"   ✓ Tests developed: {len(test_cases)} files")
            
            for case in test_cases:
                print(f"     - {case.get('file_path', 'N/A')}")
            
            # 2.5. Service startup (optional step)
            print(f"\n2.5. Service Startup (Optional):")
            try:
                result = await workflow_manager._startup_service(state)
                state = merge_node_result(state, result)
                if state.metadata.get("service_startup", {}).get("service_ready"):
                    print(f"   ✓ Service started successfully")
                else:
                    print(f"   ⚠ Service startup skipped (no startup script found - expected for test repo)")
            except Exception as e:
                print(f"   ⚠ Service startup error (may be expected): {str(e)[:100]}")
            
            # 3. Setup E2E Environment
            print(f"\n{'='*60}")
            print("3. Running _setup_e2e_environment Step")
            print(f"{'='*60}")
            
            result = await workflow_manager._setup_e2e_environment(state)
            state = merge_node_result(state, result)
            
            # Verify setup results
            assert "e2e_setup" in state.metadata
            assert state.stage == TaskStage.ENV_SETUP
            setup_result = state.metadata["e2e_setup"]
            
            print(f"\nE2E Environment Setup Results:")
            print(f"   Success: {setup_result.get('success', False)}")
            print(f"   Environment Ready: {setup_result.get('environment_ready', False)}")
            
            if "steps" in setup_result:
                print(f"\n   Setup Steps:")
                for step in setup_result["steps"]:
                    step_name = step.get("name", "unknown")
                    step_status = "✓" if step.get("success") or step.get("status") == "skipped" else "✗"
                    print(f"     {step_status} {step_name}")
            
            # 4. Execute _run_tests
            print(f"\n{'='*60}")
            print("4. Running _run_tests Step")
            print(f"{'='*60}")
            
            result = await workflow_manager._run_tests(state)
            state = merge_node_result(state, result)
            
            # Verify _run_tests results
            assert state.stage == TaskStage.TEST_EXECUTION
            assert hasattr(state, 'test_results')
            assert isinstance(state.test_results, dict)
            
            test_results = state.test_results
            print(f"\nTest Execution Results:")
            print(f"   Success: {test_results.get('success', False)}")
            print(f"   Passed: {test_results.get('passed', False)}")
            print(f"   Total Tests: {test_results.get('total_tests', 0)}")
            
            # Verify structure
            assert "success" in test_results or "passed" in test_results
            assert "total_tests" in test_results
            assert "results" in test_results
            
            results_list = test_results.get("results", [])
            print(f"   Results Count: {len(results_list)}")
            
            for idx, result in enumerate(results_list, 1):
                print(f"\n   Test {idx}:")
                print(f"     File: {result.get('file', 'N/A')}")
                print(f"     Success: {result.get('success', False)}")
                print(f"     Exit Code: {result.get('exit_code', 'N/A')}")
                
                # Verify result structure
                assert "file" in result
                assert "success" in result
                assert "exit_code" in result
            
            # 5. Execute _check_results (basic check)
            print(f"\n{'='*60}")
            print("5. Running _check_results Step (Basic Check)")
            print(f"{'='*60}")
            
            result = await workflow_manager._check_results(state)
            state = merge_node_result(state, result)
            
            # Verify _check_results results
            assert state.stage == TaskStage.RESULT_CHECK
            assert "test_execution_summary" in state.metadata
            assert "basic_check_result" in state.metadata
            
            summary = state.metadata["test_execution_summary"]
            print(f"\nTest Execution Summary (Basic Check):")
            print(f"   Passed: {summary.get('passed', False)}")
            print(f"   Total Tests: {summary.get('total_tests', 0)}")
            print(f"   Passed Count: {summary.get('passed_count', 0)}")
            print(f"   Failed Count: {summary.get('failed_count', 0)}")
            
            # Verify summary structure
            assert "passed" in summary
            assert "total_tests" in summary
            assert "passed_count" in summary
            assert "failed_count" in summary
            
            # 6. Execute _agent_chain_review (LLM-based review)
            print(f"\n{'='*60}")
            print("6. Running _agent_chain_review Step (LLM Review)")
            print(f"{'='*60}")
            
            result = await workflow_manager._agent_chain_review(state)
            state = merge_node_result(state, result)
            
            # Verify _agent_chain_review results
            assert state.stage == TaskStage.RESULT_CHECK
            assert hasattr(state, 'test_review')
            assert isinstance(state.test_review, dict)
            
            review_result = state.test_review
            print(f"\nTest Review Results:")
            print(f"   Approved: {review_result.get('approved', False)}")
            print(f"   Action: {review_result.get('action', 'unknown')}")
            print(f"   Retry Count: {state.retry_count}")
            
            # Verify review result structure
            assert "approved" in review_result
            assert "action" in review_result
            assert "summary" in review_result
            
            # Check decision logic based on review
            if review_result.get('approved', False):
                print(f"\n   Decision: Tests approved - Ready for PR creation ✓")
                assert review_result.get("action") == "create_pr"
                assert state.status != TaskStatus.FAILED
            else:
                print(f"\n   Decision: Tests need improvement")
                action = review_result.get("action")
                
                if action == "retry":
                    print(f"   Action: Retry with feedback (attempt {state.retry_count}/{state.config.get('max_retries', 3)})")
                    assert state.retry_count > 0
                    assert state.feedback is not None or review_result.get("feedback") is not None
                    assert state.status != TaskStatus.FAILED
                elif action == "error":
                    print(f"   Action: Mark as error (max retries reached)")
                    assert state.error_message is not None or review_result.get("error") is not None
            
            print(f"\n{'='*60}")
            print("✓ Workflow execution stages validated successfully!")
            print(f"{'='*60}\n")
            
            # Cleanup
            # await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            pass
            # if os.path.exists(temp_base):
                # shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_run_tests_tool_integration(self):
        """Test TestExecutionTool integration with real PR."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            from app.mcp.tools.high_level.case_runner import CaseExecutionTool
            
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
            
            # Generate test cases
            analyzer = RequirementAnalyzer()
            requirement_analysis = await analyzer.analyze(pr_data, workspace_path)
            
            detector = FrameworkDetectorAgent()
            framework_info = await detector.detect(workspace_path=workspace_path)
            
            designer = CaseDesigner()
            test_design = await designer.design(
                requirement_analysis,
                workspace_path,
                framework_info
            )
            
            developer = CaseDeveloper()
            test_cases = await developer.develop(test_design, workspace_path, requirement_analysis)
            
            print(f"\n{'='*60}")
            print("Testing CaseExecutionTool")
            print(f"{'='*60}")
            print(f"Test cases: {len(test_cases)}")
            
            # Setup E2E environment first
            from app.mcp.tools.high_level.e2e_env_setup import E2EEnvironmentSetupTool
            
            setup_tool = E2EEnvironmentSetupTool()
            frontend_path = framework_info.get("frontend_path")
            
            print(f"\nSetting up E2E environment...")
            setup_result = await setup_tool.execute(
                workspace_path=workspace_path,
                frontend_path=frontend_path,
                force_reinstall=False
            )
            
            print(f"Setup success: {setup_result.get('success')}")
            if not setup_result.get('success'):
                print(f"Setup error: {setup_result.get('error')}")
            
            # Test CaseExecutionTool
            executor = CaseExecutionTool()
            result = await executor.execute(
                workspace_path=workspace_path,
                test_cases=test_cases,
                frontend_path=frontend_path  # Pass frontend path
            )
            
            # Verify results
            assert isinstance(result, dict)
            assert "success" in result
            assert "passed" in result
            assert "total_tests" in result
            assert "results" in result
            
            print(f"\nCaseExecutionTool Results:")
            print(f"  Success: {result['success']}")
            print(f"  Passed: {result['passed']}")
            print(f"  Total: {result['total_tests']}")
            
            assert result["total_tests"] == len(test_cases)
            
            print(f"\n✓ CaseExecutionTool integration validated!")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_check_results_tool_integration(self):
        """Test CaseResultCheckerTool with different scenarios."""
        from app.mcp.tools.high_level.case_result_checker import CaseResultCheckerTool
        
        print(f"\n{'='*60}")
        print("Testing CaseResultCheckerTool")
        print(f"{'='*60}")
        
        checker = CaseResultCheckerTool()
        
        # Scenario 1: All tests passed
        print(f"\nScenario 1: All tests passed")
        test_results_passed = {
            "success": True,
            "passed": True,
            "total_tests": 5,
            "results": [
                {"file": "test1.spec.ts", "success": True},
                {"file": "test2.spec.ts", "success": True},
                {"file": "test3.spec.ts", "success": True},
                {"file": "test4.spec.ts", "success": True},
                {"file": "test5.spec.ts", "success": True}
            ]
        }
        
        result = await checker.execute(test_results=test_results_passed)
        
        assert result["action"] == "create_pr"
        assert result["ready_for_pr"] is True
        assert result["summary"]["passed"] is True
        assert result["summary"]["passed_count"] == 5
        assert result["summary"]["failed_count"] == 0
        
        print(f"  Action: {result['action']}")
        print(f"  Ready for PR: {result['ready_for_pr']}")
        print(f"  ✓ Passed")
        
        # Scenario 2: Tests failed, first retry
        print(f"\nScenario 2: Tests failed, should retry")
        test_results_failed = {
            "success": True,
            "passed": False,
            "total_tests": 5,
            "results": [
                {"file": "test1.spec.ts", "success": True},
                {"file": "test2.spec.ts", "success": False},
                {"file": "test3.spec.ts", "success": True},
                {"file": "test4.spec.ts", "success": False},
                {"file": "test5.spec.ts", "success": True}
            ]
        }
        
        result = await checker.execute(test_results=test_results_failed, retry_count=0)
        
        assert result["action"] == "retry"
        assert result["retry_count"] == 1
        assert "retry_reason" in result
        assert result["summary"]["passed"] is False
        assert result["summary"]["passed_count"] == 3
        assert result["summary"]["failed_count"] == 2
        
        print(f"  Action: {result['action']}")
        print(f"  Retry count: {result['retry_count']}")
        print(f"  Retry reason: {result['retry_reason']}")
        print(f"  ✓ Passed")
        
        # Scenario 3: Tests failed, max retries reached
        print(f"\nScenario 3: Tests failed, max retries reached")
        
        result = await checker.execute(test_results=test_results_failed, retry_count=2)
        
        assert result["action"] == "error"
        assert result["success"] is False
        assert "error" in result
        assert "2 retries" in result["error"]
        
        print(f"  Action: {result['action']}")
        print(f"  Error: {result['error']}")
        print(f"  ✓ Passed")
        
        print(f"\n✓ CaseResultCheckerTool validated!")
    
    @pytest.mark.asyncio
    async def test_case_checker_agent_with_prompt(self):
        """Test CaseCheckerAgent with natural language prompt using execute method.
        
        Comprehensive workflow execution test with real PR: https://github.com/clampist/email-risk-reviewer/pull/1
        Tests CaseCheckerAgent using execute method with prompt.
        """
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            print(f"\n{'='*60}")
            print("Testing CaseCheckerAgent with Natural Language Prompt")
            print(f"{'='*60}")
            
            # Setup workflow
            workflow_manager = WorkflowManager()
            state = WorkflowState()
            state.task_id = "test_checker_agent_workflow"
            state.repo_full_name = "clampist/email-risk-reviewer"
            state.pr_number = 1
            state.status = TaskStatus.RUNNING
            state.retry_count = 0
            state.config = {"max_retries": 3}
            
            # 1. Get real PR and setup workspace using execute method
            github_client = GithubAgent()
            github_prompt = f"Get PR #{state.pr_number} from {state.repo_full_name}"
            github_result = await github_client.execute(prompt=github_prompt)
            
            pr_data = await extract_from_agent_result(
                result=github_result,
                field_name="pr_data",
                validator=lambda data: data is not None and ("number" in data or "title" in data) if isinstance(data, dict) else False,
                fallback_func=lambda: github_client.get_pr(state.repo_full_name, state.pr_number),
                debug=True
            )
            
            if pr_data is None or "error" in pr_data:
                pytest.skip(f"Could not fetch PR: {pr_data.get('error', 'Unknown error') if pr_data else 'PR data is None'}")
            
            print(f"\n1. PR Information:")
            print(f"   PR #{state.pr_number}: {pr_data.get('title', 'N/A')}")
            
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_prompt = f"Clone repository {state.repo_full_name} for PR #{state.pr_number} to branch {branch}"
            workspace_result = await workspace_manager.execute(prompt=workspace_prompt)
            
            workspace_path = await extract_from_agent_result(
                result=workspace_result,
                field_name="workspace_path",
                validator=lambda path: path and os.path.exists(path) if path else False,
                fallback_func=lambda: workspace_manager.clone_repo(
                    repo_full_name=state.repo_full_name,
                    pr_number=state.pr_number,
                    branch=branch
                ),
                path_pattern=r'(/[^\s\n"]+clampist_email-risk-reviewer_pr1[^\s\n"]*)',
                debug=True
            )
            
            if workspace_path is None:
                pytest.skip("Could not clone repository, skipping test")
            
            state.workspace_path = workspace_path
            state.pr_data = pr_data
            
            print(f"   Workspace: {workspace_path}")
            
            # 2. Prepare test cases using execute method
            print(f"\n2. Preparing Test Cases:")
            
            # 2.1. Requirement analysis using execute
            analyzer = RequirementAnalyzer()
            analysis_prompt = f"Analyze PR requirements for {state.repo_full_name} PR #{state.pr_number} in workspace {workspace_path}"
            analysis_result = await analyzer.execute(
                prompt=analysis_prompt,
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            requirement_analysis = await extract_from_agent_result(
                result=analysis_result,
                field_name="analysis",
                validator=lambda data: data is not None and isinstance(data, dict) and "summary" in data if data else False,
                fallback_func=lambda: analyzer.analyze(pr_data, workspace_path),
                debug=True
            )
            
            if requirement_analysis is None:
                requirement_analysis = await analyzer.analyze(pr_data, workspace_path)
            
            print(f"   ✓ Requirements analyzed: {len(requirement_analysis['analysis']['requirements'])}")
            
            # 2.2. Framework detection using execute
            detector = FrameworkDetectorAgent()
            framework_prompt = f"Detect the test framework used in workspace {workspace_path}"
            framework_result = await detector.execute(prompt=framework_prompt, workspace_path=workspace_path)
            
            framework_info = await extract_from_agent_result(
                result=framework_result,
                field_name="framework_info",
                validator=lambda data: data is not None and isinstance(data, dict) and "framework" in data if data else False,
                fallback_func=lambda: detector.detect(workspace_path=workspace_path),
                debug=True
            )
            
            if framework_info is None:
                framework_info = await detector.detect(workspace_path=workspace_path)
            
            state.test_framework = framework_info
            print(f"   ✓ Framework detected: {framework_info['framework']}")
            
            # 2.3. Test design using execute
            designer = CaseDesigner()
            design_prompt = f"""Design E2E test cases for PR #{state.pr_number} in workspace {workspace_path}.
            The requirement analysis shows {len(requirement_analysis['analysis']['requirements'])} requirements.
            The detected test framework is {framework_info['framework']} with {framework_info['confidence']} confidence.
            Please design comprehensive test cases based on the requirements."""
            
            design_result = await designer.execute(
                prompt=design_prompt,
                requirement_analysis=requirement_analysis,
                workspace_path=workspace_path,
                test_framework=framework_info
            )
            
            test_design = await extract_from_agent_result(
                result=design_result,
                field_name="design",
                validator=lambda data: data is not None and isinstance(data, dict) and "test_cases" in data.get("design", {}) if data else False,
                fallback_func=lambda: designer.design(requirement_analysis, workspace_path, framework_info),
                debug=True
            )
            
            if test_design is None:
                test_design = await designer.design(requirement_analysis, workspace_path, framework_info)
            
            print(f"   ✓ Tests designed: {len(test_design['design']['test_cases'])} cases")
            
            # 2.4. Test development using execute
            developer = CaseDeveloper()
            develop_prompt = f"""Develop test case code for the test design in workspace {workspace_path}.
            The test design includes {len(test_design['design']['test_cases'])} test cases.
            The test framework is {framework_info['framework']} with {framework_info['confidence']} confidence.
            Please generate the actual test code files based on the test design."""
            
            develop_result = await developer.execute(
                prompt=develop_prompt,
                test_design=test_design,
                workspace_path=workspace_path,
                requirement_analysis=requirement_analysis
            )
            
            test_cases = await extract_from_agent_result(
                result=develop_result,
                field_name="test_cases",
                validator=lambda data: data is not None and isinstance(data, list) and len(data) > 0 if data else False,
                fallback_func=lambda: developer.develop(test_design, workspace_path, requirement_analysis),
                debug=True
            )
            
            if test_cases is None:
                test_cases = await developer.develop(test_design, workspace_path, requirement_analysis)
            
            state.test_cases = test_cases
            print(f"   ✓ Tests developed: {len(test_cases)} files")
            
            for case in test_cases:
                print(f"     - {case.get('file_path', 'N/A')}")
            
            # 2.5. Service startup (optional step)
            print(f"\n2.5. Service Startup (Optional):")
            try:
                result = await workflow_manager._startup_service(state)
                state = merge_node_result(state, result)
                if state.metadata.get("service_startup", {}).get("service_ready"):
                    print(f"   ✓ Service started successfully")
                else:
                    print(f"   ⚠ Service startup skipped (no startup script found - expected for test repo)")
            except Exception as e:
                print(f"   ⚠ Service startup error (may be expected): {str(e)[:100]}")
            
            # 3. Setup E2E Environment
            print(f"\n{'='*60}")
            print("3. Running _setup_e2e_environment Step")
            print(f"{'='*60}")
            
            result = await workflow_manager._setup_e2e_environment(state)
            state = merge_node_result(state, result)
            
            # Verify setup results
            assert "e2e_setup" in state.metadata
            assert state.stage == TaskStage.ENV_SETUP
            setup_result = state.metadata["e2e_setup"]
            
            print(f"\nE2E Environment Setup Results:")
            print(f"   Success: {setup_result.get('success', False)}")
            print(f"   Environment Ready: {setup_result.get('environment_ready', False)}")
            
            # 4. Execute _run_tests
            print(f"\n{'='*60}")
            print("4. Running _run_tests Step")
            print(f"{'='*60}")
            
            result = await workflow_manager._run_tests(state)
            state = merge_node_result(state, result)
            
            # Verify _run_tests results
            assert state.stage == TaskStage.TEST_EXECUTION
            assert hasattr(state, 'test_results')
            assert isinstance(state.test_results, dict)
            
            test_results = state.test_results
            print(f"\nTest Execution Results:")
            print(f"   Success: {test_results.get('success', False)}")
            print(f"   Passed: {test_results.get('passed', False)}")
            print(f"   Total Tests: {test_results.get('total_tests', 0)}")
            
            # 5. Execute _check_results (basic check)
            print(f"\n{'='*60}")
            print("5. Running _check_results Step (Basic Check)")
            print(f"{'='*60}")
            
            result = await workflow_manager._check_results(state)
            state = merge_node_result(state, result)
            
            # Verify _check_results results
            assert state.stage == TaskStage.RESULT_CHECK
            assert "test_execution_summary" in state.metadata
            assert "basic_check_result" in state.metadata
            
            summary = state.metadata["test_execution_summary"]
            print(f"\nTest Execution Summary (Basic Check):")
            print(f"   Passed: {summary.get('passed', False)}")
            print(f"   Total Tests: {summary.get('total_tests', 0)}")
            print(f"   Passed Count: {summary.get('passed_count', 0)}")
            print(f"   Failed Count: {summary.get('failed_count', 0)}")
            
            # 6. Test CaseCheckerAgent with natural language prompt
            print(f"\n{'='*60}")
            print("6. Testing CaseCheckerAgent with Natural Language Prompt")
            print(f"{'='*60}")
            
            checker = CaseCheckerAgent()
            
            prompt = f"""Review the test execution results for the test cases in workspace {workspace_path}.
            The test execution shows {test_results.get('total_tests', 0)} total tests.
            {summary.get('passed_count', 0)} tests passed and {summary.get('failed_count', 0)} tests failed.
            This is retry attempt {state.retry_count + 1} out of {state.config.get('max_retries', 3)}.
            Please analyze the failures and provide detailed feedback for improving the test cases."""
            
            print(f"\nPrompt: {prompt[:200]}...")
            
            review_result = await checker.execute(
                prompt=prompt,
                test_results=test_results,
                test_cases=test_cases,
                test_design=test_design,
                requirement_analysis=requirement_analysis,
                retry_count=state.retry_count,
                max_retries=state.config.get('max_retries', 3),
                workspace_path=workspace_path
            )
            
            print(f"\nAgent result type: {type(review_result)}")
            print(f"Agent result keys: {review_result.keys() if isinstance(review_result, dict) else 'N/A'}")
            
            # Extract review result from agent response using helper function
            async def get_review_fallback():
                return await checker.review(
                    test_results=test_results,
                    test_cases=test_cases,
                    test_design=test_design,
                    requirement_analysis=requirement_analysis,
                    retry_count=state.retry_count,
                    max_retries=state.config.get('max_retries', 3),
                    workspace_path=workspace_path
                )
            
            final_review = await extract_from_agent_result(
                result=review_result,
                field_name="review",
                validator=lambda data: data is not None and isinstance(data, dict) and "approved" in data if data else False,
                fallback_func=get_review_fallback,
                debug=True
            )
            
            # If final_review is None, try to extract from result directly
            if final_review is None:
                if isinstance(review_result, dict) and "approved" in review_result:
                    final_review = review_result
                elif isinstance(review_result, dict) and "result" in review_result:
                    result_data = review_result.get("result", {})
                    if isinstance(result_data, dict) and "messages" in result_data:
                        # Try to extract from messages
                        messages = result_data.get("messages", [])
                        for msg in messages:
                            msg_type = type(msg).__name__
                            if msg_type == "ToolMessage":
                                content = getattr(msg, "content", None)
                                if content and isinstance(content, dict) and "approved" in content:
                                    final_review = content
                                    break
                                elif content and isinstance(content, str):
                                    import json
                                    try:
                                        if "{" in content and "}" in content:
                                            json_start = content.find("{")
                                            json_end = content.rfind("}") + 1
                                            content_dict = json.loads(content[json_start:json_end])
                                            if "approved" in content_dict:
                                                final_review = content_dict
                                                break
                                    except json.JSONDecodeError:
                                        pass
                else:
                    # Final fallback
                    final_review = await checker.review(
                        test_results=test_results,
                        test_cases=test_cases,
                        test_design=test_design,
                        requirement_analysis=requirement_analysis,
                        retry_count=state.retry_count,
                        max_retries=state.config.get('max_retries', 3),
                        workspace_path=workspace_path
                    )
            
            # Verify review result was created
            assert final_review is not None, "Review result should be returned"
            assert isinstance(final_review, dict), "Review result should be a dictionary"
            assert "approved" in final_review, "Review result should contain 'approved' key"
            assert "action" in final_review, "Review result should contain 'action' key"
            assert "summary" in final_review, "Review result should contain 'summary' key"
            
            print(f"\nTest Review Results (from Agent):")
            print(f"   Approved: {final_review.get('approved', False)}")
            print(f"   Action: {final_review.get('action', 'unknown')}")
            print(f"   Retry Count: {final_review.get('retry_count', state.retry_count)}")
            
            # Check decision logic based on review
            if final_review.get('approved', False):
                print(f"\n   Decision: Tests approved - Ready for PR creation ✓")
                assert final_review.get("action") == "create_pr"
            else:
                print(f"\n   Decision: Tests need improvement")
                action = final_review.get("action")
                
                if action == "retry":
                    print(f"   Action: Retry with feedback (attempt {final_review.get('retry_count', state.retry_count)}/{state.config.get('max_retries', 3)})")
                    assert final_review.get("feedback") is not None or final_review.get("retry_reason") is not None
                elif action == "error":
                    print(f"   Action: Mark as error (max retries reached)")
                    assert "error" in final_review or final_review.get("error") is not None
            
            # Print feedback if available
            feedback = final_review.get("feedback")
            if feedback:
                if isinstance(feedback, dict):
                    print(f"\n   Feedback Details:")
                    if "root_causes" in feedback:
                        print(f"     Root Causes: {len(feedback.get('root_causes', []))}")
                    if "specific_issues" in feedback:
                        print(f"     Specific Issues: {len(feedback.get('specific_issues', []))}")
                    if "recommendations" in feedback:
                        print(f"     Recommendations: {len(feedback.get('recommendations', []))}")
                    if "feedback" in feedback:
                        feedback_text = feedback.get("feedback", "")
                        print(f"     Feedback Preview: {feedback_text[:200]}...")
                elif isinstance(feedback, str):
                    print(f"\n   Feedback Preview: {feedback[:200]}...")
            
            print(f"\n{'='*60}")
            print("✓ CaseCheckerAgent prompt test completed successfully!")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            pass
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
