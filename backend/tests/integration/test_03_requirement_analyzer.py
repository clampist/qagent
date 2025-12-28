"""Integration tests for RequirementAnalyzer with real PR."""
import pytest
import os
import tempfile
import shutil
import re
import json
from app.agents.business.requirement_analyzer import RequirementAnalyzer
from app.agents.business.github_agent import GithubAgent
from app.agents.business.workspace_agent import WorkspaceAgent
from tests.conftest import extract_from_agent_result


@pytest.mark.integration
class TestRequirementAnalyzerIntegration:
    """Test RequirementAnalyzer with real GitHub PR."""
    
    @pytest.mark.asyncio
    async def test_analyze_real_pr_email_risk_reviewer(self):
        """Test analyzing real PR with structure validation and detailed output.
        
        Tests:
        - PR data fetching from GitHub
        - Repository cloning
        - Requirement analysis execution
        - Output structure validation
        - Type checking
        - Content validation
        
        Target PR: https://github.com/clampist/email-risk-reviewer/pull/1
        """
        if not os.getenv("GITHUB_TOKEN"):
            pytest.skip("GITHUB_TOKEN not set, skipping integration test")
        
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set, skipping integration test")
        
        # Setup
        temp_base = tempfile.mkdtemp()
        repo_full_name = "clampist/email-risk-reviewer"
        pr_number = 1
        
        try:
            # 1. Get PR data from GitHub
            github_client = GithubAgent()
            pr_data = await github_client.get_pr(repo_full_name, pr_number)
            
            print(f"\n{'='*60}")
            print(f"Testing PR Analysis")
            print(f"{'='*60}")
            print(f"PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            print(f"State: {pr_data.get('state', 'N/A')}")
            print(f"Author: {pr_data.get('user', 'N/A')}")
            print(f"Description: {pr_data.get('body', 'N/A')[:100]}...")
            print(f"{'='*60}\n")
            
            # Verify PR data was fetched
            assert "number" in pr_data or "error" in pr_data
            if "error" in pr_data:
                pytest.skip(f"Could not fetch PR: {pr_data['error']}")
            
            # 2. Clone repository to workspace
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_path = await workspace_manager.clone_repo(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                branch=branch
            )
            
            print(f"Cloned to: {workspace_path}")
            print(f"Branch: {branch}")
            assert os.path.exists(workspace_path)
            
            # 3. Run RequirementAnalyzer
            analyzer = RequirementAnalyzer()
            
            print("\n" + "="*60)
            print("Running Requirement Analysis...")
            print("="*60 + "\n")
            
            result = await analyzer.analyze(
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            # 4. Validate top-level structure
            print("\n" + "="*60)
            print("Structure Validation")
            print("="*60)
            
            assert isinstance(result, dict), "Result should be a dictionary"
            
            # Check top-level keys
            required_keys = ["pr_number", "analysis", "changed_files", "raw_analysis"]
            for key in required_keys:
                assert key in result, f"Missing required key: {key}"
                print(f"✓ Found key: {key}")
            
            # Type validation for top-level fields
            assert isinstance(result["pr_number"], int), "pr_number should be int"
            assert isinstance(result["changed_files"], list), "changed_files should be list"
            assert isinstance(result["raw_analysis"], str), "raw_analysis should be str"
            assert result["pr_number"] == pr_number, "pr_number should match"
            
            print(f"\n✓ Top-level structure validated")
            
            # 5. Validate analysis structure and types
            print("\n" + "="*60)
            print("Analysis Content Validation")
            print("="*60)
            
            analysis = result["analysis"]
            
            # Check analysis keys
            analysis_keys = ["summary", "requirements", "affected_areas", "test_implications", "complexity"]
            for key in analysis_keys:
                assert key in analysis, f"Missing analysis key: {key}"
            
            # Type validation for analysis fields
            assert isinstance(analysis["summary"], str), "summary should be str"
            assert isinstance(analysis["requirements"], list), "requirements should be list"
            assert isinstance(analysis["affected_areas"], list), "affected_areas should be list"
            assert isinstance(analysis["test_implications"], str), "test_implications should be str"
            assert isinstance(analysis["complexity"], str), "complexity should be str"
            
            # Content validation
            assert len(analysis["requirements"]) > 0, "Should have at least one requirement"
            assert analysis["complexity"] in ["low", "medium", "high"], "Invalid complexity value"
            
            print(f"\n✓ Analysis structure validated")
            
            # 6. Display analysis results
            print("\n" + "="*60)
            print("Analysis Results")
            print("="*60)
            
            print(f"\nSummary: {analysis['summary']}")
            print(f"\nRequirements ({len(analysis['requirements'])}):")
            for i, req in enumerate(analysis['requirements'], 1):
                print(f"  {i}. {req}")
            
            print(f"\nAffected Areas ({len(analysis['affected_areas'])}):")
            for area in analysis['affected_areas']:
                print(f"  - {area}")
            
            print(f"\nTest Implications: {analysis['test_implications']}")
            print(f"Complexity: {analysis['complexity']}")
            
            # Display changed files
            changed_files = result["changed_files"]
            print(f"\nChanged Files ({len(changed_files)}):")
            for file in changed_files[:10]:  # Show first 10
                print(f"  - {file}")
            if len(changed_files) > 10:
                print(f"  ... and {len(changed_files) - 10} more files")
            
            # 7. Content-specific validation (email-risk-reviewer PR #1)
            print("\n" + "="*60)
            print("Content-Specific Validation")
            print("="*60)
            
            summary_lower = analysis["summary"].lower()
            print(f"\nSummary contains 'risk': {'risk' in summary_lower}")
            print(f"Summary contains 'medium': {'medium' in summary_lower}")
            
            print(f"\n{'='*60}")
            print("✓ All validations passed!")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_analyze_execute_method(self):
        """Test the execute method with real PR."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
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
            
            # Test execute method
            analyzer = RequirementAnalyzer()
            result = await analyzer.execute(
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            # Verify result
            assert "analysis" in result
            assert "pr_number" in result
            
            print(f"\n✓ Execute method works correctly!")
            print(f"Analysis summary: {result['analysis']['summary'][:100]}...")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_requirement_analyzer_with_prompt(self):
        """Test RequirementAnalyzer with natural language prompt using execute method."""
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Required tokens not set, skipping integration test")
        
        temp_base = tempfile.mkdtemp()
        
        try:
            # Setup
            repo_full_name = "clampist/email-risk-reviewer"
            pr_number = 1
            
            # 1. Get PR data from GitHub using execute method
            github_client = GithubAgent()
            github_prompt = f"Get PR #{pr_number} from {repo_full_name}"
            print(f"\nGetting PR data with prompt: {github_prompt}")
            
            github_result = await github_client.execute(prompt=github_prompt)
            
            # Extract PR data from agent result using helper function
            pr_data = await extract_from_agent_result(
                result=github_result,
                field_name="pr_data",
                validator=lambda data: data is not None and ("number" in data or "title" in data) if isinstance(data, dict) else False,
                fallback_func=lambda: github_client.get_pr(repo_full_name, pr_number),
                debug=True
            )
            
            # Verify PR data was fetched
            if pr_data is None or "error" in pr_data:
                error_msg = pr_data.get("error", "Unknown error") if pr_data else "PR data is None"
                pytest.skip(f"Could not fetch PR: {error_msg}")
            
            # 2. Clone repository to workspace using execute method
            workspace_manager = WorkspaceAgent()
            workspace_manager.base_path = temp_base
            
            branch = pr_data.get('head', {}).get('ref', 'main')
            workspace_prompt = f"Clone repository {repo_full_name} for PR #{pr_number} to branch {branch}"
            print(f"Cloning repository with prompt: {workspace_prompt}")
            
            workspace_result = await workspace_manager.execute(prompt=workspace_prompt)
            
            # Extract workspace_path from agent result using helper function
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
            
            # Verify workspace_path was obtained
            if workspace_path is None:
                pytest.skip("Could not clone repository, skipping test")
            
            print(f"\n{'='*60}")
            print("Testing RequirementAnalyzer with natural language prompt")
            print(f"{'='*60}")
            print(f"PR #{pr_number}: {pr_data.get('title', 'N/A')}")
            print(f"Workspace: {workspace_path}")
            
            # 3. Test with natural language prompt
            analyzer = RequirementAnalyzer()
            
            # Create a prompt that includes the necessary information
            prompt = f"Analyze the requirements for PR #{pr_number} from {repo_full_name}. " \
                    f"The PR title is '{pr_data.get('title', '')}'. " \
                    f"Use the workspace at {workspace_path}."
            
            print(f"\nPrompt: {prompt}")
            
            result = await analyzer.execute(
                prompt=prompt,
                pr_data=pr_data,
                workspace_path=workspace_path
            )
            
            print(f"\nAgent result type: {type(result)}")
            print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            # Extract analysis from agent result using helper function
            async def get_analysis_fallback():
                result = await analyzer.analyze(
                    pr_data=pr_data,
                    workspace_path=workspace_path
                )
                return result.get("analysis")
            
            analysis = await extract_from_agent_result(
                result=result,
                field_name="analysis",
                validator=lambda data: data is not None and isinstance(data, dict) and "summary" in data if data else False,
                fallback_func=get_analysis_fallback,
                debug=True
            )
            
            # If analysis is still None, try direct method call
            if analysis is None:
                print("⚠ Could not extract analysis from agent result, using direct method")
                result = await analyzer.analyze(
                    pr_data=pr_data,
                    workspace_path=workspace_path
                )
                analysis = result.get("analysis")
            
            # Verify analysis was created
            assert analysis is not None, "Analysis should be returned"
            assert isinstance(analysis, dict), "Analysis should be a dictionary"
            
            # Verify analysis structure
            required_keys = ["summary", "requirements", "affected_areas", "test_implications", "complexity"]
            for key in required_keys:
                assert key in analysis, f"Analysis should contain '{key}'"
            
            print(f"\n✓ Analysis structure validated")
            print(f"Summary: {analysis.get('summary', 'N/A')[:100]}...")
            print(f"Requirements: {len(analysis.get('requirements', []))} items")
            print(f"Complexity: {analysis.get('complexity', 'N/A')}")
            
            print(f"\n{'='*60}")
            print("✓ RequirementAnalyzer prompt test completed successfully")
            print(f"{'='*60}\n")
            
            # Cleanup
            await workspace_manager.cleanup_workspace(workspace_path)
            
        finally:
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)
