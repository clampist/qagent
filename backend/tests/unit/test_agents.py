"""Unit tests for Agents."""
import pytest
from unittest.mock import patch, AsyncMock, Mock
import json
from app.agents.business.requirement_analyzer import RequirementAnalyzer
from app.agents.business.case_designer import CaseDesigner
from app.agents.business.case_developer import CaseDeveloper


@pytest.mark.unit
class TestRequirementAnalyzer:
    """Test requirement analyzer agent."""
    
    @pytest.mark.asyncio
    async def test_analyze_pr(self, mock_llm, sample_pr_data, temp_workspace):
        """Test PR requirement analysis."""
        analyzer = RequirementAnalyzer()
        
        # Mock LLM response
        mock_response = {
            "summary": "Test PR summary",
            "requirements": ["req1", "req2"],
            "affected_areas": ["area1"],
            "test_implications": "Need E2E tests",
            "complexity": "medium"
        }
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content=json.dumps(mock_response)))
        
        # Mock code search
        with patch.object(analyzer, "call_tool") as mock_tool:
            mock_tool.return_value = {"success": True, "files": ["file1.js", "file2.ts"]}
            
            result = await analyzer.analyze(sample_pr_data, temp_workspace)
            
            assert "analysis" in result
            assert result["pr_number"] == 123
            assert "changed_files" in result
    
    @pytest.mark.asyncio
    async def test_analyze_with_markdown_wrapped_json(self, mock_llm, sample_pr_data, temp_workspace):
        """Test analysis with markdown-wrapped JSON response."""
        analyzer = RequirementAnalyzer()
        
        mock_response = {
            "summary": "Test",
            "requirements": ["req1"],
            "affected_areas": [],
            "test_implications": "Test",
            "complexity": "low"
        }
        wrapped_response = f"```json\n{json.dumps(mock_response)}\n```"
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content=wrapped_response))
        
        with patch.object(analyzer, "call_tool") as mock_tool:
            mock_tool.return_value = {"success": True, "files": []}
            
            result = await analyzer.analyze(sample_pr_data, temp_workspace)
            
            assert "analysis" in result


@pytest.mark.unit
class TestTestDesigner:
    """Test test designer agent."""
    
    @pytest.mark.asyncio
    async def test_design_tests(self, mock_llm, temp_workspace):
        """Test test case design."""
        designer = CaseDesigner()
        
        requirement_analysis = {
            "analysis": {
                "requirements": ["req1"],
                "affected_areas": ["area1"]
            }
        }
        
        mock_design = {
            "test_suite_name": "e2e_tests",
            "test_cases": [
                {
                    "name": "test1",
                    "description": "Test description",
                    "steps": ["step1"],
                    "expected_result": "success",
                    "priority": "high"
                }
            ],
            "test_framework": "playwright",
            "coverage_areas": ["area1"]
        }
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content=json.dumps(mock_design)))
        
        with patch.object(designer, "call_tool") as mock_tool:
            mock_tool.return_value = {"success": True, "files": []}
            
            result = await designer.design(requirement_analysis, temp_workspace)
            
            assert "design" in result
            assert result["design"]["test_framework"] == "playwright"


@pytest.mark.unit
class TestCaseDeveloper:
    """Test case developer agent."""
    
    @pytest.mark.asyncio
    async def test_develop_cases(self, mock_llm, temp_workspace):
        """Test test case development."""
        developer = CaseDeveloper()
        
        test_design = {
            "design": {
                "test_suite_name": "e2e_tests",
                "test_cases": [
                    {
                        "name": "test1",
                        "description": "Test",
                        "steps": ["step1"],
                        "expected_result": "success",
                        "priority": "high"
                    }
                ],
                "test_framework": "playwright"
            }
        }
        
        mock_code = "test('test1', async () => { expect(true).toBe(true); });"
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content=mock_code))
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")
            
            result = await developer.develop(test_design, temp_workspace)
            
            assert len(result) > 0
            assert "file_path" in result[0]
            assert "code" in result[0]
    
    @pytest.mark.asyncio
    async def test_syntax_check(self, temp_workspace):
        """Test syntax checking."""
        developer = CaseDeveloper()
        
        test_file = os.path.join(temp_workspace, "test.spec.ts")
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, "w") as f:
            f.write("const x = 1;")
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")
            
            result = await developer._check_syntax(test_file, temp_workspace)
            
            assert result["valid"] is True

