"""Case design agent."""
from typing import Dict, Any, List, Optional
from app.agents.base import BaseAgent
import json
import logging

logger = logging.getLogger(__name__)


class CaseDesigner(BaseAgent):
    """Agent for designing test cases based on requirements.
    
    This agent wraps test design methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language prompts)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="case_designer",
            description="Design E2E test cases based on requirements",
            llm_provider=llm_provider
        )
        
        # Create tools from test design methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        system_prompt = "You are a helpful assistant for test case design. " \
                       "You can design E2E test cases based on requirements, analyze test frameworks, " \
                       "and generate comprehensive test designs. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from test design methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to self for closure
        designer = self
        
        @tool
        def design_test_cases_tool(
            requirement_analysis: Dict[str, Any],
            workspace_path: str,
            test_framework: Dict[str, Any] = None,
            max_test_cases: int = 3
        ) -> Dict[str, Any]:
            """Design E2E test cases based on requirements.
            
            Args:
                requirement_analysis: Requirement analysis result (dict with analysis, pr_number, keywords, etc.)
                workspace_path: Path to workspace directory
                test_framework: Detected test framework info (dict with framework, confidence, etc.)
                max_test_cases: Maximum number of test cases to generate (default: 3)
            
            Returns:
                Dict containing:
                - design: Test design dict with test_suite_name, test_cases, test_framework, coverage_areas
                - frontend_requirements: List of frontend requirements
                - changed_files_analyzed: List of changed files analyzed
                - test_files_analyzed: List of test files analyzed
                - all_test_files: List of all test files found
                - raw_design: Raw design text from LLM
            """
            import asyncio
            try:
                return asyncio.run(
                    designer.design(
                        requirement_analysis=requirement_analysis,
                        workspace_path=workspace_path,
                        test_framework=test_framework,
                        max_test_cases=max_test_cases
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    designer.design(
                        requirement_analysis=requirement_analysis,
                        workspace_path=workspace_path,
                        test_framework=test_framework,
                        max_test_cases=max_test_cases
                    )
                )
            except Exception as e:
                logger.error(f"Error designing test cases: {e}")
                return {"error": str(e)}
        
        return [design_test_cases_tool]
    
    async def design(
        self,
        requirement_analysis: Dict[str, Any],
        workspace_path: str,
        test_framework: Dict[str, Any] = None,
        save_to_markdown: bool = True,
        task_id: str = None,
        max_test_cases: int = 3
    ) -> Dict[str, Any]:
        """Design test cases.
        
        Args:
            requirement_analysis: Requirement analysis result
            workspace_path: Path to workspace
            test_framework: Detected test framework info
            save_to_markdown: Whether to save design to markdown file
            task_id: Task ID for markdown filename (optional)
            max_test_cases: Maximum number of test cases to generate (default: 3)
        """
        import logging
        import os
        logger = logging.getLogger(__name__)
        
        # Extract data from requirement analysis
        analysis = requirement_analysis.get("analysis", {})
        requirements = analysis.get("requirements", [])
        affected_areas = analysis.get("affected_areas", [])
        pr_number = requirement_analysis.get("pr_number", "unknown")
        keywords = requirement_analysis.get("keywords", [])
        changed_files = requirement_analysis.get("changed_files", [])
        
        # Step 1: Filter frontend-only requirements
        from app.mcp.tools.mid_level.file_tools import FrontendRequirementFilterTool
        filter_tool = FrontendRequirementFilterTool()
        filter_result = await filter_tool.execute(
            requirements=requirements,
            changed_files=changed_files,
            related_files=[]  # related_changed_files removed - only used in requirement_analysis stage
        )
        frontend_requirements = filter_result.get("frontend_requirements", [])
        logger.info(f"Filtered requirements: {len(requirements)} → {len(frontend_requirements)} frontend-only")
        
        # Use detected framework or default to playwright
        detected_framework = "playwright"
        framework_confidence = "default"
        test_dir = None
        frontend_path = None
        
        if test_framework and test_framework.get("framework"):
            detected_framework = test_framework["framework"]
            framework_confidence = test_framework.get("confidence", "low")
            test_dir = test_framework.get("test_dir")
            frontend_path = test_framework.get("frontend_path")
        
        logger.info(f"Test framework: {detected_framework} (confidence: {framework_confidence})")
        logger.info(f"Test directory: {test_dir or 'Not detected'}")
        logger.info(f"Frontend path: {frontend_path or 'Not detected'}")
        
        # Step 2: Search for related test files using keywords in test directory
        from app.mcp.tools.mid_level.file_tools import TestFileSearchTool
        test_search_tool = TestFileSearchTool()
        search_result = await test_search_tool.execute(
            workspace_path=workspace_path,
            keywords=keywords,
            test_dir=test_dir or frontend_path
        )
        related_test_files = search_result.get("files", [])
        logger.info(f"Found {len(related_test_files)} related test files via keyword search")
        
        # Step 3: Extract test files from changed_files only
        from app.mcp.tools.low_level.path_tools import TestFileExtractorTool
        extractor_tool = TestFileExtractorTool()
        extract_result = await extractor_tool.execute(files=changed_files)
        changed_test_files = extract_result.get("test_files", [])
        logger.info(f"Found {len(changed_test_files)} test files in changed files")
        
        # Combine and deduplicate test files
        all_test_files = list(set(related_test_files + changed_test_files))
        logger.info(f"Total test files to analyze: {len(all_test_files)}")
        
        # Step 4: Read file contents
        # Filter out backend files and config files - only process frontend source files
        config_file_patterns = [
            '.config.',  # playwright.config.ts, vite.config.ts, etc.
            'config.ts',
            'config.js',
            'package.json',
            'package-lock.json',
            'yarn.lock',
            'tsconfig.json',
            'jsconfig.json',
            '.eslintrc',
            '.prettierrc',
            'tailwind.config',
            'next.config',
            'webpack.config',
            'rollup.config',
            '.env',
            '.gitignore'
        ]
        
        frontend_changed_files = []
        for f in changed_files:  # Only use changed_files, related_changed_files removed
            # Exclude backend files
            if f.startswith('backend/'):
                continue
            # Exclude configuration files
            if any(pattern in f for pattern in config_file_patterns):
                logger.debug(f"Excluding config file: {f}")
                continue
            # Exclude test files (they are handled separately)
            if any(pattern in f for pattern in ['.spec.', '.test.', '/tests/', '/__tests__/']):
                continue
            # Only include frontend source code
            if any(pattern in f for pattern in ['src/', 'components/', 'pages/', 'lib/', 'utils/', 'hooks/', 'types/', 'app/', 'views/']):
                frontend_changed_files.append(f)
        
        from app.mcp.tools.mid_level.file_tools import FileReaderTool
        file_reader = FileReaderTool()
        
        changed_file_result = await file_reader.execute(
            workspace_path=workspace_path,
            files=frontend_changed_files,
            max_lines_per_file=200
        )
        changed_file_contents = changed_file_result.get("contents", {})
        
        test_file_result = await file_reader.execute(
            workspace_path=workspace_path,
            files=all_test_files,
            max_lines_per_file=300
        )
        test_file_contents = test_file_result.get("contents", {})
        
        logger.info(f"Read {len(changed_file_contents)} changed file contents")
        logger.info(f"Read {len(test_file_contents)} test file contents")
        
        # Build design prompt
        system_prompt = """You are a test design agent. Your task is to:
1. Design comprehensive E2E test cases based on frontend requirements
2. Analyze changed files and existing test patterns
3. Use the detected test framework
4. Generate test design in JSON format

IMPORTANT RULES:
- DO NOT create test cases for documentation-only requirements
- DO NOT create test cases for README, docs, comments, or specification documents
- ONLY create test cases for actual UI functionality and user interactions
- Focus on testing user-facing features and behaviors
- Generate MAXIMUM {max_test_cases} test cases - prioritize the most critical scenarios
- Focus on high-priority test cases that cover the most important user flows

Output format:
{
    "test_suite_name": "name",
    "test_cases": [
        {
            "name": "test case name",
            "description": "what it tests",
            "steps": ["step1", "step2", ...],
            "expected_result": "expected outcome",
            "priority": "high|medium|low"
        }
    ],
    "test_framework": "playwright|cypress|selenium",
    "coverage_areas": ["area1", "area2", ...]
}"""
        
        # Build comprehensive context
        framework_info = f"""Test Framework: {detected_framework} (confidence: {framework_confidence})
Test Directory: {test_dir or frontend_path or 'tests/'}"""
        
        # Format changed file contents
        from app.mcp.tools.low_level.path_tools import FileContentFormatterTool
        formatter = FileContentFormatterTool()
        
        changed_files_result = await formatter.execute(
            file_contents=changed_file_contents,
            title="Changed Files (git diff + keyword search)"
        )
        changed_files_section = changed_files_result.get("formatted", "")
        
        # Format test file contents
        test_files_result = await formatter.execute(
            file_contents=test_file_contents,
            title="Existing Related Test Files"
        )
        test_files_section = test_files_result.get("formatted", "")
        
        # Check frontend paths for affected areas
        from app.mcp.tools.low_level.path_tools import PathTypeCheckerTool
        path_checker = PathTypeCheckerTool()
        frontend_affected_areas = []
        for area in affected_areas:
            check_result = await path_checker.execute(area)
            if check_result.get("is_frontend", False):
                frontend_affected_areas.append(area)
        
        user_prompt = f"""# Frontend Requirements
{json.dumps(frontend_requirements, indent=2)}

# Affected Frontend Areas
{', '.join(frontend_affected_areas)}

# Keywords Extracted
{', '.join(keywords[:5])}

# {framework_info}

{changed_files_section}

{test_files_section}

Based on the above context:
1. Frontend requirements and changes
2. Changed file contents showing the actual code changes
3. Existing test file patterns and structures

Please design comprehensive E2E test cases using the {detected_framework} framework.

IMPORTANT: Generate MAXIMUM {max_test_cases} test cases. Prioritize:
1. Most critical user flows
2. High-risk areas with recent changes
3. Core functionality that impacts user experience

Ensure the test cases:
- Follow existing test patterns and structure
- Cover the most important frontend requirements
- Use appropriate selectors and assertions
- Include both happy path and edge cases
- Specify which test file to create or update
"""
        
        # Get LLM design
        design_text = await self._llm_call(
            self._format_prompt(system_prompt, user_prompt)
        )
        
        logger.info(f"Max test cases limit: {max_test_cases}")
        
        # Parse JSON response
        try:
            if "```json" in design_text:
                json_start = design_text.find("```json") + 7
                json_end = design_text.find("```", json_start)
                design_text = design_text[json_start:json_end].strip()
            elif "```" in design_text:
                json_start = design_text.find("```") + 3
                json_end = design_text.find("```", json_start)
                design_text = design_text[json_start:json_end].strip()
            
            design = json.loads(design_text)
            # Ensure framework matches detected framework
            if detected_framework and design.get("test_framework") != detected_framework:
                design["test_framework"] = detected_framework
            # Add frontend path to design if available
            if test_framework and test_framework.get("frontend_path"):
                design["frontend_path"] = test_framework.get("frontend_path")
            
            # Enforce max test cases limit
            test_cases = design.get("test_cases", [])
            if len(test_cases) > max_test_cases:
                logger.warning(f"Test cases exceed limit: {len(test_cases)} > {max_test_cases}, truncating to top {max_test_cases}")
                design["test_cases"] = test_cases[:max_test_cases]
        except json.JSONDecodeError:
            # Fallback - use detected framework
            design = {
                "test_suite_name": "e2e_tests",
                "test_cases": [
                    {
                        "name": "basic_functionality_test",
                        "description": "Test basic functionality",
                        "steps": ["Navigate to page", "Perform action", "Verify result"],
                        "expected_result": "Action completes successfully",
                        "priority": "high"
                    }
                ],
                "test_framework": detected_framework,
                "coverage_areas": affected_areas
            }
            # Add frontend path if available
            if test_framework and test_framework.get("frontend_path"):
                design["frontend_path"] = test_framework.get("frontend_path")
        
        result = {
            "design": design,
            "frontend_requirements": frontend_requirements,
            "changed_files_analyzed": list(changed_file_contents.keys()),
            "test_files_analyzed": list(test_file_contents.keys()),
            "all_test_files": all_test_files,
            "changed_file_contents": changed_file_contents,  # Pass to case_developer to avoid duplicate reads
            "changed_test_files": changed_test_files,  # Pass extracted test files to avoid duplicate extraction
            "raw_design": design_text
        }
        
        # Log test design output
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: TEST_DESIGN")
        logger.info(f"{'='*70}")
        logger.info(f"Frontend Requirements: {len(frontend_requirements)} items")
        logger.info(f"Changed Files Analyzed: {len(changed_file_contents)}")
        logger.info(f"Test Files Analyzed: {len(test_file_contents)}")
        logger.info(f"Test Suite Name: {design.get('test_suite_name', 'N/A')}")
        logger.info(f"Test Framework: {design.get('test_framework', 'N/A')}")
        logger.info(f"Frontend Path: {design.get('frontend_path', 'N/A')}")
        
        test_cases = design.get('test_cases', [])
        logger.info(f"Test Cases: {len(test_cases)} cases designed")
        for idx, case in enumerate(test_cases[:5], 1):
            logger.info(f"  {idx}. {case.get('name', 'unnamed')}")
            logger.info(f"     Description: {case.get('description', 'N/A')[:100]}")
            logger.info(f"     Priority: {case.get('priority', 'N/A')}")
            logger.info(f"     Steps: {len(case.get('steps', []))} steps")
        
        if len(test_cases) > 5:
            logger.info(f"  ... and {len(test_cases) - 5} more cases")
        
        coverage_areas = design.get('coverage_areas', [])
        logger.info(f"Coverage Areas: {', '.join(coverage_areas[:10]) if coverage_areas else 'N/A'}")
        
        # Save to markdown if requested
        if save_to_markdown:
            try:
                from app.mcp.tools.mid_level.markdown_export import MarkdownExportTool
                
                export_tool = MarkdownExportTool()
                export_result = await export_tool.execute(
                    output_data=result,
                    stage_name="test_design",
                    task_id=task_id or f"pr_{pr_number}",
                    workspace_path=workspace_path
                )
                
                if export_result.get("success"):
                    result["markdown_file"] = export_result["filepath"]
                    logger.info(f"Review file saved: {export_result['filepath']}")
            except Exception as e:
                logger.warning(f"Failed to save to markdown: {e}")
        
        logger.info(f"{'='*70}\n")
        
        return result
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Design test cases for PR #1 in workspace /path/to/workspace")
            action: Direct action name ("design")
            requirement_analysis: Requirement analysis result (required for direct action)
            workspace_path: Workspace path (required for direct action)
            test_framework: Detected test framework info (optional)
            max_test_cases: Maximum number of test cases (optional, default: 3)
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "design":
            requirement_analysis = kwargs.get("requirement_analysis", {})
            workspace_path = kwargs.get("workspace_path", "")
            test_framework = kwargs.get("test_framework")
            max_test_cases = kwargs.get("max_test_cases", 3)
            if requirement_analysis and workspace_path:
                return await self.design(
                    requirement_analysis=requirement_analysis,
                    workspace_path=workspace_path,
                    test_framework=test_framework,
                    max_test_cases=max_test_cases
                )
        
        # If prompt is provided and agent is available, use agent
        if prompt and self.agent:
            try:
                result = self.agent.invoke({
                    "messages": [{"role": "user", "content": prompt}]
                })
                return {"result": result}
            except Exception as e:
                logger.error(f"Error executing agent prompt: {e}")
                return {"error": str(e)}
        
        # Fallback to direct design if no prompt/action but requirement_analysis and workspace_path provided
        requirement_analysis = kwargs.get("requirement_analysis", {})
        workspace_path = kwargs.get("workspace_path", "")
        if requirement_analysis and workspace_path:
            logger.info("No explicit action or prompt, falling back to direct design method.")
            return await self.design(
                requirement_analysis=requirement_analysis,
                workspace_path=workspace_path,
                test_framework=kwargs.get("test_framework"),
                max_test_cases=kwargs.get("max_test_cases", 3)
            )
        
        return {"error": "No valid action or prompt provided. Provide 'prompt', 'action', or 'requirement_analysis' + 'workspace_path'."}

