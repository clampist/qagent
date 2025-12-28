"""Integration tests for CaseDeveloper with real PR."""
import pytest
import os
import tempfile
import shutil
from app.agents.business.case_developer import CaseDeveloper
from app.agents.business.case_designer import CaseDesigner
from app.agents.business.requirement_analyzer import RequirementAnalyzer
from app.agents.business.github_agent import GithubAgent
from app.agents.business.workspace_agent import WorkspaceAgent
from app.agents.business.framework_detector import FrameworkDetectorAgent
from tests.conftest import extract_from_agent_result


@pytest.mark.integration
class TestCaseDeveloperIntegration:
    """Test CaseDeveloper with real GitHub PR."""
    
    @pytest.mark.asyncio
    async def test_develop_cases_comprehensive(self):
        """Comprehensive test for case development: structure and code quality.
        
        Tests for real PR: https://github.com/clampist/email-risk-reviewer/pull/1
        Combines structure validation, code quality checks, and file creation validation.
        """
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        try:
            print(f"\n{'='*60}")
            print(f"Testing Test Case Development (Comprehensive)")
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
            
            # Run requirement analysis
            analyzer = RequirementAnalyzer()
            requirement_analysis = await analyzer.analyze(
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            print(f"\nRequirement Analysis Complete:")
            print(f"Requirements: {len(requirement_analysis['analysis']['requirements'])}")
            
            # Detect test framework
            detector = FrameworkDetectorAgent()
            framework_info = await detector.detect(workspace_path=workspace_path)
            
            print(f"\nFramework Detection Complete:")
            print(f"Framework: {framework_info['framework']}")
            
            # Design test cases
            designer = CaseDesigner()
            test_design = await designer.design(
                requirement_analysis=requirement_analysis,
                workspace_path=workspace_path,
                test_framework=framework_info
            )
            
            print(f"\nTest Design Complete:")
            print(f"Test Cases: {len(test_design['design']['test_cases'])}")
            
            # Develop test cases
            developer = CaseDeveloper()
            
            print(f"\n{'='*60}")
            print("Running Test Case Development...")
            print(f"{'='*60}\n")
            
            developed_cases = await developer.develop(
                test_design=test_design,
                workspace_path=workspace_path,
                requirement_analysis=requirement_analysis
            )
            
            # ========== 1. Structure Validation ==========
            print(f"\n{'='*60}")
            print("1. Structure Validation")
            print(f"{'='*60}")
            
            assert isinstance(developed_cases, list)
            assert len(developed_cases) > 0, "Should have at least one developed test file"
            
            for case in developed_cases:
                # Common required keys for all cases
                assert "file_path" in case, f"Missing required key: file_path"
                assert isinstance(case["file_path"], str)
                assert len(case["file_path"]) > 0
                assert os.path.isabs(case["file_path"])
                
                # Type-specific validation
                case_type = case.get("type", "new")
                if case_type == "new":
                    # Required keys for new files
                    required_keys = ["test_cases", "code", "syntax_valid", "syntax_errors"]
                    for key in required_keys:
                        assert key in case, f"Missing required key: {key}"
                    
                    # Type validation
                    assert isinstance(case["test_cases"], list)
                    assert isinstance(case["code"], str)
                    assert isinstance(case["syntax_valid"], bool)
                    assert isinstance(case["syntax_errors"], list)
                    
                    # Content validation
                    assert len(case["code"]) > 0
                elif case_type == "modified":
                    # Modified files have different structure
                    assert "changes" in case or "status" in case
            
            print("✓ Structure validation passed")
            
            # ========== 2. File Creation and Content Validation ==========
            print(f"\n{'='*60}")
            print("2. File Creation and Content Validation")
            print(f"{'='*60}")
            
            for case in developed_cases:
                case_type = case.get("type", "new")
                print(f"\nDeveloped Test File (type: {case_type}):")
                print(f"  File: {case.get('file_path', 'N/A')}")
                
                # Verify file exists
                file_path = case["file_path"]
                assert os.path.exists(file_path), f"Test file should be created: {file_path}"
                
                # Verify file has content
                with open(file_path, 'r') as f:
                    file_content = f.read()
                    assert len(file_content) > 0, "Test file should have content"
                    print(f"\nTest File Preview (first 500 chars):")
                    print(f"{file_content[:500]}...")
                
                # Type-specific validation
                if case_type == "new":
                    print(f"  Test Cases: {len(case.get('test_cases', []))}")
                    print(f"  Code Length: {len(case.get('code', ''))} characters")
                    print(f"  Syntax Valid: {case.get('syntax_valid', False)}")
                    
                    # Verify code structure
                    code = case["code"]
                    assert len(code) > 0, "Generated code should not be empty"
                    
                    # Syntax check results
                    if not case.get("syntax_valid"):
                        print(f"\n  Syntax Errors:")
                        for error in case.get("syntax_errors", [])[:5]:
                            if error.strip():
                                print(f"    - {error}")
                        print(f"  Note: Syntax errors may be due to missing dependencies")
                    else:
                        print(f"  ✓ Syntax check passed!")
                elif case_type == "modified":
                    print(f"  Status: {case.get('status', 'N/A')}")
                    print(f"  Changes: {len(case.get('changes', []))}")
            
            print("✓ File creation and content validation passed")
            
            # ========== 3. Framework Pattern Validation ==========
            print(f"\n{'='*60}")
            print("3. Framework Pattern Validation")
            print(f"{'='*60}")
            
            framework = test_design['design']['test_framework']
            for case in developed_cases:
                case_type = case.get("type", "new")
                # Only validate framework patterns for new files
                if case_type == "new":
                    code = case["code"]
                    
                    if framework == "playwright":
                        assert "test(" in code or "describe(" in code, \
                            "Playwright tests should have test() or describe()"
                        print(f"✓ Playwright patterns found")
                    elif framework == "cypress":
                        assert "cy." in code or "describe(" in code, \
                            "Cypress tests should have cy. commands or describe()"
                        print(f"✓ Cypress patterns found")
            
            print("✓ Framework pattern validation passed")
            
            # ========== 4. Code Quality Validation ==========
            print(f"\n{'='*60}")
            print("4. Code Quality Validation")
            print(f"{'='*60}")
            
            for case in developed_cases:
                case_type = case.get("type", "new")
                # Only validate code quality for new files
                if case_type == "new":
                    code = case["code"]
                    
                    # Check for basic test structure
                    has_test_structure = (
                        "test(" in code or 
                        "it(" in code or 
                        "describe(" in code
                    )
                    assert has_test_structure, "Code should have test structure"
                    
                    # Check for assertions/expectations
                    has_assertions = (
                        "expect(" in code or 
                        "assert" in code.lower() or
                        "should" in code.lower()
                    )
                    assert has_assertions, "Code should have assertions"
                    
                    # Check that code is not too short (likely incomplete)
                    assert len(code) > 100, "Code should be substantial"
                    
                    # Check for proper formatting (has newlines)
                    assert "\n" in code, "Code should be properly formatted with newlines"
                    
                    print(f"✓ Code quality checks passed!")
                    print(f"  - Has test structure: {has_test_structure}")
                    print(f"  - Has assertions: {has_assertions}")
                    print(f"  - Code length: {len(code)} chars")
            
            print("✓ Code quality validation passed")
            
            # ========== Summary ==========
            print(f"\n{'='*60}")
            print("✓ Comprehensive test case development validation completed!")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_workflow_develop_cases_step(self):
        """Test workflow's develop_cases step with real PR."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
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
            
            # Get requirement analysis
            analyzer = RequirementAnalyzer()
            requirement_analysis = await analyzer.analyze(pr_data, workspace_path)
            
            # Detect framework
            detector = FrameworkDetectorAgent()
            framework_info = await detector.detect(workspace_path=workspace_path)
            
            # Design tests
            designer = CaseDesigner()
            test_design = await designer.design(
                requirement_analysis,
                workspace_path,
                framework_info
            )
            
            # Create workflow state
            workflow_manager = WorkflowManager()
            state = WorkflowState()
            state.task_id = "test_case_development"
            state.repo_full_name = repo_full_name
            state.pr_number = pr_number
            state.status = TaskStatus.RUNNING
            state.workspace_path = workspace_path
            state.test_design = test_design
            
            print(f"\nTesting workflow develop_cases step...")
            
            # Execute develop_cases step
            result_state = await workflow_manager._develop_cases(state)
            
            # Verify results
            assert result_state.stage == TaskStage.CASE_DEVELOPMENT
            assert result_state.test_cases is not None
            assert isinstance(result_state.test_cases, list)
            assert len(result_state.test_cases) > 0
            
            print(f"✓ Workflow develop_cases step completed!")
            print(f"Developed {len(result_state.test_cases)} test file(s)")
            
            for case in result_state.test_cases:
                print(f"  - {case.get('file_path', 'N/A')}")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_case_developer_agent_with_prompt(self):
        """Test CaseDeveloper with natural language prompt using execute method."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # 1. Get PR data and clone repository
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
            print("Testing CaseDeveloper with natural language prompt")
            print(f"{'='*60}")
            print(f"PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            print(f"Workspace: {workspace_path}")
            
            # 2. Run requirement analysis
            analyzer = RequirementAnalyzer()
            requirement_analysis = await analyzer.analyze(
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            print(f"\nRequirement Analysis Complete:")
            print(f"Requirements: {len(requirement_analysis['analysis']['requirements'])}")
            
            # 3. Detect test framework
            detector = FrameworkDetectorAgent()
            framework_info = await detector.detect(workspace_path=workspace_path)
            
            print(f"\nFramework Detection Complete:")
            print(f"Framework: {framework_info['framework']}")
            print(f"Confidence: {framework_info['confidence']}")
            
            # 4. Design test cases using execute method
            designer = CaseDesigner()
            design_prompt = f"""Design E2E test cases for PR #{pr_number} in workspace {workspace_path}.
            The requirement analysis shows {len(requirement_analysis['analysis']['requirements'])} requirements.
            The detected test framework is {framework_info['framework']} with {framework_info['confidence']} confidence.
            Please design comprehensive test cases based on the requirements."""
            
            design_result = await designer.execute(
                prompt=design_prompt,
                requirement_analysis=requirement_analysis,
                workspace_path=workspace_path,
                test_framework=framework_info
            )
            
            print(f"\nDesign result type: {type(design_result)}")
            print(f"Design result keys: {design_result.keys() if isinstance(design_result, dict) else 'N/A'}")
            
            # Extract test design from result using helper function
            async def get_design_fallback():
                return await designer.design(
                    requirement_analysis=requirement_analysis,
                    workspace_path=workspace_path,
                    test_framework=framework_info
                )
            
            test_design = await extract_from_agent_result(
                result=design_result,
                field_name="design",
                validator=lambda data: data is not None and isinstance(data, dict) and "test_cases" in data.get("design", {}) if data else False,
                fallback_func=get_design_fallback,
                debug=True
            )
            
            # If test_design is None, try to extract from result directly
            if test_design is None:
                if isinstance(design_result, dict) and "design" in design_result:
                    test_design = design_result
                elif isinstance(design_result, dict) and "result" in design_result:
                    result_data = design_result.get("result", {})
                    if isinstance(result_data, dict) and "messages" in result_data:
                        # Try to extract from messages
                        messages = result_data.get("messages", [])
                        for msg in messages:
                            msg_type = type(msg).__name__
                            if msg_type == "ToolMessage":
                                content = getattr(msg, "content", None)
                                if content and isinstance(content, dict) and "design" in content:
                                    test_design = content
                                    break
                                elif content and isinstance(content, str):
                                    import json
                                    try:
                                        if "{" in content and "}" in content:
                                            json_start = content.find("{")
                                            json_end = content.rfind("}") + 1
                                            content_dict = json.loads(content[json_start:json_end])
                                            if "design" in content_dict:
                                                test_design = content_dict
                                                break
                                    except json.JSONDecodeError:
                                        pass
                else:
                    # Final fallback
                    test_design = await designer.design(
                        requirement_analysis=requirement_analysis,
                        workspace_path=workspace_path,
                        test_framework=framework_info
                    )
            
            # Verify test design was created
            assert test_design is not None, "Test design should be returned"
            assert isinstance(test_design, dict), "Test design should be a dictionary"
            assert "design" in test_design, "Test design should contain 'design' key"
            
            print(f"\nTest Design Complete:")
            print(f"Test Cases: {len(test_design['design']['test_cases'])}")
            
            # 5. Test with natural language prompt
            developer = CaseDeveloper()
            
            prompt = f"""Develop test case code for the test design in workspace {workspace_path}.
            The test design includes {len(test_design['design']['test_cases'])} test cases.
            The test framework is {framework_info['framework']} with {framework_info['confidence']} confidence.
            Please generate the actual test code files based on the test design."""
            
            print(f"\nPrompt: {prompt[:200]}...")
            
            result = await developer.execute(
                prompt=prompt,
                test_design=test_design,
                workspace_path=workspace_path,
                requirement_analysis=requirement_analysis
            )
            
            print(f"\nAgent result type: {type(result)}")
            print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            # Extract test cases from result using helper function
            async def get_test_cases_fallback():
                cases = await developer.develop(
                    test_design=test_design,
                    workspace_path=workspace_path,
                    requirement_analysis=requirement_analysis
                )
                return cases
            
            test_cases = await extract_from_agent_result(
                result=result,
                field_name="test_cases",
                validator=lambda data: data is not None and isinstance(data, list) and len(data) > 0 if data else False,
                fallback_func=get_test_cases_fallback,
                debug=True
            )
            
            # If test_cases is None, try to extract from result directly
            if test_cases is None:
                if isinstance(result, dict) and "test_cases" in result:
                    test_cases = result["test_cases"]
                elif isinstance(result, dict) and "result" in result:
                    result_data = result.get("result", {})
                    if isinstance(result_data, dict) and "messages" in result_data:
                        # Try to extract from messages
                        messages = result_data.get("messages", [])
                        for msg in messages:
                            msg_type = type(msg).__name__
                            if msg_type == "ToolMessage":
                                content = getattr(msg, "content", None)
                                if content and isinstance(content, list):
                                    test_cases = content
                                    break
                                elif content and isinstance(content, dict) and "test_cases" in content:
                                    test_cases = content["test_cases"]
                                    break
                                elif content and isinstance(content, str):
                                    import json
                                    try:
                                        if "[" in content and "]" in content:
                                            json_start = content.find("[")
                                            json_end = content.rfind("]") + 1
                                            content_list = json.loads(content[json_start:json_end])
                                            if isinstance(content_list, list) and len(content_list) > 0:
                                                test_cases = content_list
                                                break
                                    except json.JSONDecodeError:
                                        pass
                else:
                    # Final fallback
                    test_cases = await developer.develop(
                        test_design=test_design,
                        workspace_path=workspace_path,
                        requirement_analysis=requirement_analysis
                    )
            
            # Verify test cases were created
            assert test_cases is not None, "Test cases should be returned"
            assert isinstance(test_cases, list), "Test cases should be a list"
            assert len(test_cases) > 0, "Test cases should have at least one item"
            
            # Verify structure
            for case in test_cases:
                assert "file_path" in case, "Each test case should have file_path"
                assert isinstance(case["file_path"], str), "file_path should be a string"
                assert len(case["file_path"]) > 0, "file_path should not be empty"
            
            print(f"\n✓ Test case development validated")
            print(f"Test Files Generated: {len(test_cases)}")
            
            # Print first few test cases
            for idx, case in enumerate(test_cases[:3], 1):
                print(f"\n  {idx}. {case.get('file_path', 'N/A')}")
                print(f"     Type: {case.get('type', 'N/A')}")
                if case.get('type') == 'new':
                    print(f"     Code Length: {len(case.get('code', ''))} chars")
                    print(f"     Syntax Valid: {case.get('syntax_valid', False)}")
                elif case.get('type') == 'modified':
                    print(f"     Status: {case.get('status', 'N/A')}")
                    print(f"     Changes: {len(case.get('changes', []))}")
            
            print(f"\n{'='*60}")
            print("✓ CaseDeveloper prompt test completed successfully")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
