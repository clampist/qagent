"""Unit tests for MCP tools."""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from app.mcp.tools.mid_level.git_tools import GitCloneTool, GitCommitTool, GitPushTool
from app.mcp.tools.mid_level.search_tools import CodeSearchTool, FileSearchTool
from app.mcp.tools.mid_level.cost_control import CostControlTool
from app.mcp.tools.low_level.time_tools import GetTimeTool, SleepTool


@pytest.mark.unit
class TestGitTools:
    """Test Git tools."""
    
    @pytest.mark.asyncio
    async def test_git_clone_success(self):
        """Test successful git clone."""
        tool = GitCloneTool()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Cloned", stderr="")
            
            result = await tool.execute(
                repo_url="https://github.com/test/repo.git",
                target_path="/tmp/test"
            )
            
            assert result["success"] is True
            assert "output" in result
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_git_clone_failure(self):
        """Test failed git clone."""
        tool = GitCloneTool()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")
            
            result = await tool.execute(
                repo_url="https://github.com/test/repo.git",
                target_path="/tmp/test"
            )
            
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_git_commit(self):
        """Test git commit."""
        tool = GitCommitTool()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Committed", stderr="")
            
            result = await tool.execute(
                repo_path="/tmp/repo",
                message="Test commit"
            )
            
            assert result["success"] is True
            assert mock_run.call_count == 2  # git add and git commit
    
    @pytest.mark.asyncio
    async def test_git_push(self):
        """Test git push."""
        tool = GitPushTool()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Pushed", stderr="")
            
            result = await tool.execute(
                repo_path="/tmp/repo",
                remote="origin",
                branch="main"
            )
            
            assert result["success"] is True


@pytest.mark.unit
class TestSearchTools:
    """Test search tools."""
    
    @pytest.mark.asyncio
    async def test_code_search_with_ripgrep(self):
        """Test code search using ripgrep."""
        tool = CodeSearchTool()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="/path/to/file1.js\n/path/to/file2.js",
                stderr=""
            )
            
            result = await tool.execute(
                workspace_path="/tmp/workspace",
                query="test"
            )
            
            assert result["success"] is True
            assert len(result["files"]) == 2
    
    @pytest.mark.asyncio
    async def test_file_search(self):
        """Test file search."""
        tool = FileSearchTool()
        
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                ("/tmp/workspace", [], ["test1.js", "test2.ts", "other.txt"])
            ]
            
            result = await tool.execute(
                workspace_path="/tmp/workspace",
                pattern="*.js"
            )
            
            assert result["success"] is True
            assert len(result["files"]) > 0


@pytest.mark.unit
class TestCostControlTool:
    """Test cost control tool."""
    
    @pytest.mark.asyncio
    async def test_check_iteration(self):
        """Test iteration check."""
        tool = CostControlTool()
        
        result = await tool.execute(action="check_iteration")
        
        assert result["success"] is True
        assert "can_continue" in result
        assert result["current_iterations"] == 0
    
    @pytest.mark.asyncio
    async def test_increment_iteration(self):
        """Test iteration increment."""
        tool = CostControlTool()
        
        result1 = await tool.execute(action="increment_iteration")
        result2 = await tool.execute(action="check_iteration")
        
        assert result1["current_iterations"] == 1
        assert result2["current_iterations"] == 1
    
    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset counters."""
        tool = CostControlTool()
        
        await tool.execute(action="increment_iteration")
        await tool.execute(action="reset")
        result = await tool.execute(action="check_iteration")
        
        assert result["current_iterations"] == 0


@pytest.mark.unit
class TestTimeTools:
    """Test time tools."""
    
    @pytest.mark.asyncio
    async def test_get_time(self):
        """Test get time tool."""
        tool = GetTimeTool()
        
        result = await tool.execute()
        
        assert result["success"] is True
        assert "time" in result
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_sleep(self):
        """Test sleep tool."""
        tool = SleepTool()
        
        import time
        start = time.time()
        result = await tool.execute(seconds=0.1)
        end = time.time()
        
        assert result["success"] is True
        assert (end - start) >= 0.1

