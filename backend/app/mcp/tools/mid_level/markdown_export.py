"""Markdown export tool for workflow stage outputs."""
import json
import os
from datetime import datetime
from typing import Dict, Any
from app.mcp.base import MCPTool


class MarkdownExportTool(MCPTool):
    """Export workflow stage output to markdown file for human review."""
    
    def __init__(self):
        super().__init__(
            name="markdown_export",
            description="Export workflow stage output to markdown file",
            tool_type="mid"
        )
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """Get input schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "output_data": {
                    "type": "object",
                    "description": "The data to export"
                },
                "stage_name": {
                    "type": "string",
                    "description": "Name of the stage (e.g., 'requirement_analysis', 'test_design')"
                },
                "task_id": {
                    "type": "string",
                    "description": "Task identifier"
                },
                "workspace_path": {
                    "type": "string",
                    "description": "Workspace path to save the file"
                }
            },
            "required": ["output_data", "stage_name", "task_id", "workspace_path"]
        }
    
    async def execute(
        self,
        output_data: dict,
        stage_name: str,
        task_id: str,
        workspace_path: str
    ) -> Dict[str, Any]:
        """Execute markdown export.
        
        Args:
            output_data: The data to save
            stage_name: Name of the stage
            task_id: Task identifier
            workspace_path: Workspace path to save the file
            
        Returns:
            Dict with success status and file path
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: Log input parameters
        logger.info(f"\n{'*'*70}")
        logger.info(f"[DEBUG] MarkdownExportTool.execute called")
        logger.info(f"  stage_name: {stage_name}")
        logger.info(f"  task_id: {task_id}")
        logger.info(f"  workspace_path: {workspace_path}")
        logger.info(f"  workspace_path exists: {os.path.exists(workspace_path) if workspace_path else False}")
        logger.info(f"  workspace_path is_dir: {os.path.isdir(workspace_path) if workspace_path else False}")
        
        # Create review directory in workspace
        review_dir = os.path.join(workspace_path, ".qagent", "review")
        logger.info(f"  review_dir to create: {review_dir}")
        
        try:
            os.makedirs(review_dir, exist_ok=True)
            logger.info(f"  review_dir created/exists: {os.path.exists(review_dir)}")
            logger.info(f"  review_dir is_dir: {os.path.isdir(review_dir)}")
        except Exception as e:
            logger.error(f"  Failed to create review_dir: {e}")
            return {
                "success": False,
                "error": str(e),
                "filepath": None
            }
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{stage_name}_{timestamp}.md"
        filepath = os.path.join(review_dir, filename)
        logger.info(f"  output filepath: {filepath}")
        logger.info(f"{'*'*70}\n")
        
        # Format data as markdown
        md_content = self._format_markdown(output_data, stage_name, task_id)
        
        # Write to file
        logger.info(f"[DEBUG] Writing markdown file: {filepath}")
        logger.info(f"[DEBUG] Content length: {len(md_content)} characters")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"[DEBUG] File written successfully")
            logger.info(f"[DEBUG] File size: {os.path.getsize(filepath)} bytes")
            
            return {
                "success": True,
                "filepath": filepath,
                "file_size": os.path.getsize(filepath)
            }
        except Exception as e:
            logger.error(f"[DEBUG] Failed to write file: {e}")
            return {
                "success": False,
                "error": str(e),
                "filepath": None
            }
    
    def _format_markdown(self, output_data: dict, stage_name: str, task_id: str) -> str:
        """Format data as markdown content."""
        md_content = f"""# {stage_name.replace('_', ' ').title()}

**Task ID**: {task_id}  
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Stage**: {stage_name}

---

## Summary

"""
        
        # Add stage-specific content
        if stage_name == "requirement_analysis":
            md_content += self._format_requirement_analysis(output_data)
        elif stage_name == "test_design":
            md_content += self._format_test_design(output_data)
        
        # Add raw JSON data at the end
        md_content += f"""\n## Raw Data (JSON)

```json
{json.dumps(output_data, indent=2, ensure_ascii=False)}
```
"""
        
        return md_content
    
    def _format_requirement_analysis(self, output_data: dict) -> str:
        """Format requirement analysis data."""
        analysis_data = output_data.get('analysis', {})
        content = f"""### PR Information
- **PR Number**: {output_data.get('pr_number', 'N/A')}
- **Complexity**: {analysis_data.get('complexity', 'unknown')}
- **Changed Files**: {len(output_data.get('changed_files', []))} files

### Summary
{analysis_data.get('summary', 'N/A')}

### Requirements
"""
        for idx, req in enumerate(analysis_data.get('requirements', []), 1):
            content += f"{idx}. {req}\n"
        
        content += f"""\n### Affected Areas
"""
        for area in analysis_data.get('affected_areas', []):
            content += f"- {area}\n"
        
        content += f"""\n### Changed Files
"""
        for file in output_data.get('changed_files', []):
            content += f"- `{file}`\n"
        
        return content
    
    def _format_test_design(self, output_data: dict) -> str:
        """Format test design data."""
        design_data = output_data.get('design', {})
        content = f"""### Test Suite
- **Name**: {design_data.get('test_suite_name', 'N/A')}
- **Framework**: {design_data.get('test_framework', 'N/A')}
- **Frontend Path**: {design_data.get('frontend_path', 'N/A')}

### Coverage Areas
"""
        for area in design_data.get('coverage_areas', []):
            content += f"- {area}\n"
        
        test_cases = design_data.get('test_cases', [])
        content += f"""\n### Test Cases ({len(test_cases)} total)

"""
        for idx, case in enumerate(test_cases, 1):
            content += f"""#### {idx}. {case.get('name', 'Unnamed Test')}

**Description**: {case.get('description', 'N/A')}

**Priority**: {case.get('priority', 'medium')}

**Steps**:
"""
            for step_idx, step in enumerate(case.get('steps', []), 1):
                content += f"{step_idx}. {step}\n"
            
            if case.get('expected_results'):
                content += f"\n**Expected Results**:\n"
                for result in case.get('expected_results', []):
                    content += f"- {result}\n"
            
            content += "\n---\n\n"
        
        return content
