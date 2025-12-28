"""Requirement analysis agent."""
from typing import Dict, Any, List, Optional
from app.agents.base import BaseAgent
import json
import logging

logger = logging.getLogger(__name__)


class RequirementAnalyzer(BaseAgent):
    """Agent for analyzing PR requirements and code.
    
    This agent wraps requirement analysis methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language prompts)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="requirement_analyzer",
            description="Analyze PR requirements and code changes",
            llm_provider=llm_provider
        )
        
        # Create tools from requirement analysis methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        system_prompt = "You are a helpful assistant for requirement analysis. " \
                       "You can analyze PR requirements, extract keywords, and understand code changes. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from requirement analysis methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to self for closure
        analyzer = self
        
        @tool
        def analyze_requirements_tool(
            pr_data: Dict[str, Any],
            workspace_path: str,
            save_to_markdown: bool = False,
            task_id: str = None
        ) -> Dict[str, Any]:
            """Analyze PR requirements and code changes.
            
            Args:
                pr_data: PR data from GitHub (dict with title, body, number, etc.)
                workspace_path: Path to workspace directory
                save_to_markdown: Whether to save analysis to markdown file (default: False)
                task_id: Task ID for markdown filename (optional)
            
            Returns:
                Dict containing analysis results with keys:
                - pr_number: PR number
                - analysis: Analysis dict with summary, requirements, affected_areas, etc.
                - changed_files: List of changed files
                - related_changed_files: List of related changed files
                - reference_files: List of reference files
                - keywords: List of extracted keywords
                - keyword_variants: Dict of keyword variants
                - raw_analysis: Raw analysis text
            """
            import asyncio
            try:
                return asyncio.run(
                    analyzer.analyze(
                        pr_data=pr_data,
                        workspace_path=workspace_path,
                        save_to_markdown=save_to_markdown,
                        task_id=task_id
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    analyzer.analyze(
                        pr_data=pr_data,
                        workspace_path=workspace_path,
                        save_to_markdown=save_to_markdown,
                        task_id=task_id
                    )
                )
            except Exception as e:
                logger.error(f"Error analyzing requirements: {e}")
                return {"error": str(e)}
        
        return [analyze_requirements_tool]
    
    async def analyze(
        self,
        pr_data: Dict[str, Any],
        workspace_path: str,
        save_to_markdown: bool = True,  # New parameter
        task_id: str = None  # New parameter for markdown export
    ) -> Dict[str, Any]:
        """Analyze PR requirements.
        
        Args:
            pr_data: PR data from GitHub
            workspace_path: Path to workspace
            save_to_markdown: Whether to save analysis to markdown file
            task_id: Task ID for markdown filename (optional)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract PR information
        pr_title = pr_data.get("title", "")
        pr_body = pr_data.get("body", "")
        pr_number = pr_data.get("number", 0)
        
        # Step 1: Extract keywords from PR title, body, and code changes using LLM
        keywords = await self._extract_keywords(pr_title, pr_body, workspace_path)
        logger.info(f"Extracted keywords (max 3): {keywords}")
        
        # Step 2: Get actual changed files from git diff --stat
        from app.mcp.tools.mid_level.git_tools import GitChangedFilesTool
        git_changed_files_tool = GitChangedFilesTool()
        changed_files_result = await git_changed_files_tool.execute(workspace_path=workspace_path)
        actual_changed_files = changed_files_result.get("files", [])
        logger.info(f"Git changed files: {len(actual_changed_files)} files")
        
        # Step 3: Generate keyword variants using keyword_variants tool (only for first and second keywords)
        from app.mcp.tools.low_level.keyword_tools import KeywordVariantsTool
        keyword_variants_tool = KeywordVariantsTool()
        variants_result = await keyword_variants_tool.execute(keywords=keywords[:2])  # Only first and second keywords
        keyword_variants = variants_result.get("variants", {})
        logger.info(f"Generated variants for first and second keywords: {keyword_variants}")
        
        # Step 4: Search for related files using keywords and variants
        from app.mcp.tools.mid_level.search_tools import KeywordSearchTool
        keyword_search_tool = KeywordSearchTool()
        search_result = await keyword_search_tool.execute(
            workspace_path=workspace_path,
            keywords=keywords,
            variants=keyword_variants
        )
        
        searched_files = search_result.get("files", [])
        logger.info(f"Found {len(searched_files)} files via keyword search")
        
        # Step 5: Analyze project structure to find E2E reference files
        # Combine actual changed files and searched files for exclusion
        all_changed_files = list(set(actual_changed_files) | set(searched_files))
        
        structure_analysis = await self._analyze_project_structure(
            workspace_path=workspace_path,
            changed_files=all_changed_files
        )
        
        reference_files_raw = structure_analysis.get("reference_files", [])
        logger.info(f"Found {len(reference_files_raw)} E2E reference files")
        
        # Step 6: Remove duplicates between changed_files, related_changed_files, and reference_files
        changed_files_set = set(actual_changed_files)
        searched_files_set = set(searched_files)
        
        # Debug logging
        logger.info(f"Debug - Git diff files: {actual_changed_files[:5]}..." if len(actual_changed_files) > 5 else f"Debug - Git diff files: {actual_changed_files}")
        logger.info(f"Debug - Searched files: {searched_files[:5]}..." if len(searched_files) > 5 else f"Debug - Searched files: {searched_files}")
        logger.info(f"Debug - Overlap files: {list(changed_files_set & searched_files_set)[:5]}")
        
        # related_changed_files = searched files - actual changed files
        related_changed_files = list(searched_files_set - changed_files_set)
        
        logger.info(f"Debug - After deduplication: related_changed_files has {len(related_changed_files)} files")
        if len(related_changed_files) == 0 and len(searched_files) > 0:
            logger.warning("⚠️  All searched files were already in git diff (no additional related files found)")
        
        # reference_files = reference files - (actual changed + related changed)
        excluded_paths = changed_files_set | searched_files_set
        reference_files = [
            ref for ref in reference_files_raw 
            if ref.get("path") not in excluded_paths
        ]
        
        # Final lists (all relative paths, no duplicates)
        changed_files = list(changed_files_set)
        
        logger.info(f"Final counts - Changed: {len(changed_files)}, Related: {len(related_changed_files)}, References: {len(reference_files)}")
        
        # Build analysis prompt
        system_prompt = """You are a requirement analysis agent. Your task is to:
1. Analyze the PR title and description
2. Identify the key requirements and changes (MAX 5 requirements)
3. Understand the code structure and affected areas
4. Consider existing E2E test framework files and patterns
5. Generate a structured requirement analysis in JSON format

IMPORTANT CONSTRAINTS:
- Extract AT MOST 5 key requirements (focus on the most important ones)
- If there are more than 5 potential requirements, prioritize and select the top 5
- Each requirement should be clear, concise, and actionable

Output format:
{
    "summary": "Brief summary of the PR",
    "requirements": ["requirement1", "requirement2", ...],  // MAX 5 items
    "affected_areas": ["area1", "area2", ...],
    "test_implications": "What needs to be tested",
    "complexity": "low|medium|high"
}"""
        
        # Prepare reference files info for prompt
        reference_info = ""
        if reference_files:
            ref_by_type = {}
            for ref in reference_files[:20]:  # Limit to top 20
                ref_type = ref.get("type", "unknown")
                if ref_type not in ref_by_type:
                    ref_by_type[ref_type] = []
                ref_by_type[ref_type].append(ref["path"])
            
            reference_info = "\n\nExisting E2E Test Framework Files:\n"
            for ref_type, paths in ref_by_type.items():
                reference_info += f"\n{ref_type.upper()}:\n"
                for path in paths[:10]:  # Max 10 per type
                    reference_info += f"  - {path}\n"
        
        user_prompt = f"""PR Title: {pr_title}
PR Description: {pr_body}
PR Number: {pr_number}
Changed Files (git diff): {', '.join(changed_files[:20])}
Related Files (keyword search): {', '.join(related_changed_files[:20])}
Keywords Extracted: {', '.join(keywords[:10])}
{reference_info}

Please analyze this PR and provide the requirement analysis."""
        
        # Get LLM analysis
        analysis_text = await self._llm_call(
            self._format_prompt(system_prompt, user_prompt)
        )
        
        # Parse JSON response
        try:
            # Debug: Log the type and content of analysis_text
            logger.debug(f"analysis_text type: {type(analysis_text)}")
            logger.debug(f"analysis_text content (first 200 chars): {str(analysis_text)[:200]}")
            
            # Handle case where OpenAI might return a list directly
            if isinstance(analysis_text, list):
                logger.warning("LLM returned a list directly, converting to JSON string")
                analysis_text = json.dumps(analysis_text)
            
            # Extract JSON from response if wrapped in markdown
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            elif "```" in analysis_text:
                json_start = analysis_text.find("```") + 3
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            
            analysis = json.loads(analysis_text)
            
            # Enforce max 5 requirements constraint
            if "requirements" in analysis and isinstance(analysis["requirements"], list):
                if len(analysis["requirements"]) > 5:
                    logger.warning(f"LLM returned {len(analysis['requirements'])} requirements, truncating to 5")
                    analysis["requirements"] = analysis["requirements"][:5]
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            analysis = {
                "summary": analysis_text[:200],
                "requirements": [pr_title],
                "affected_areas": changed_files,
                "test_implications": "E2E tests needed",
                "complexity": "medium"
            }
        
        result = {
            "pr_number": pr_number,
            "analysis": analysis,
            "changed_files": changed_files,
            "related_changed_files": related_changed_files,
            "reference_files": reference_files,
            "keywords": keywords,
            "keyword_variants": keyword_variants,
            "raw_analysis": analysis_text
        }
        
        # Log analysis output
        logger.info(f"\n{'='*70}")
        logger.info(f"Stage: REQUIREMENT_ANALYSIS")
        logger.info(f"{'='*70}")
        logger.info(f"PR Number: {pr_number}")
        logger.info(f"Summary: {analysis.get('summary', 'N/A')[:200]}...")
        logger.info(f"Requirements: {len(analysis.get('requirements', []))} items")
        for idx, req in enumerate(analysis.get('requirements', []), 1):
            logger.info(f"  {idx}. {req}")
        logger.info(f"Affected Areas: {', '.join(analysis.get('affected_areas', []))}")
        logger.info(f"Complexity: {analysis.get('complexity', 'unknown')}")
        logger.info(f"Changed Files (git diff): {len(changed_files)} files")
        logger.info(f"Related Files (keyword search): {len(related_changed_files)} files")
        logger.info(f"Reference Files (E2E framework): {len(reference_files)} files")
        
        # Save to markdown if requested
        if save_to_markdown:
            try:
                from app.mcp.tools.mid_level.markdown_export import MarkdownExportTool
                
                export_tool = MarkdownExportTool()
                export_result = await export_tool.execute(
                    output_data=result,
                    stage_name="requirement_analysis",
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
            prompt: Natural language prompt (e.g., "Analyze PR requirements for owner/repo PR #1")
            action: Direct action name ("analyze")
            pr_data: PR data from GitHub (required for direct action)
            workspace_path: Workspace path (required for direct action)
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "analyze":
            pr_data = kwargs.get("pr_data", {})
            workspace_path = kwargs.get("workspace_path", "")
            save_to_markdown = kwargs.get("save_to_markdown", False)
            task_id = kwargs.get("task_id")
            if pr_data and workspace_path:
                return await self.analyze(
                    pr_data=pr_data,
                    workspace_path=workspace_path,
                    save_to_markdown=save_to_markdown,
                    task_id=task_id
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
        
        # Fallback to direct analyze if no prompt/action but pr_data and workspace_path provided
        pr_data = kwargs.get("pr_data", {})
        workspace_path = kwargs.get("workspace_path", "")
        if pr_data and workspace_path:
            return await self.analyze(
                pr_data=pr_data,
                workspace_path=workspace_path,
                save_to_markdown=kwargs.get("save_to_markdown", False),
                task_id=kwargs.get("task_id")
            )
        
        return {"error": "No valid action or prompt provided. Provide 'prompt', 'action', or 'pr_data' + 'workspace_path'."}
    
    async def _extract_keywords(self, title: str, body: str, workspace_path: str) -> List[str]:
        """Extract keywords using LLM analysis of PR content and code changes.
        
        Args:
            title: PR title
            body: PR body/description
            workspace_path: Workspace path to get git diff
            
        Returns:
            List of extracted keywords (max 3)
        """
        import logging
        import subprocess
        logger = logging.getLogger(__name__)
        
        # Get git diff for code changes
        from app.mcp.tools.mid_level.git_tools import GitDiffTool
        git_diff_tool = GitDiffTool()
        git_diff_result = await git_diff_tool.execute(workspace_path=workspace_path)
        git_diff = git_diff_result.get("diff", "Git diff unavailable")
        
        # Build LLM prompt for keyword extraction
        system_prompt = """You are a keyword extraction expert. Your task is to:
1. Analyze the PR title, description, and code changes
2. Identify the MOST IMPORTANT keywords that represent the core changes
3. Extract MAXIMUM 3 keywords that are:
   - Specific to the changes (not generic words)
   - Useful for searching related code
   - Representative of the feature/fix being implemented

Output ONLY a JSON array of keywords, nothing else.
Example: ["user_authentication", "email_verification", "session_management"]

Rules:
- Keep underscores/hyphens if they exist in code (e.g., "user_login" not "user login")
- Focus on feature names, component names, or key functionality
- Avoid generic words like "add", "update", "fix"
- Maximum 3 keywords"""
        
        # Truncate git diff if too long
        max_diff_length = 3000
        if len(git_diff) > max_diff_length:
            git_diff = git_diff[:max_diff_length] + "\n... (diff truncated)"
        
        user_prompt = f"""PR Title: {title}

PR Description:
{body or 'No description provided'}

Code Changes (git diff):
{git_diff}

Extract maximum 3 most important keywords from this PR."""
        
        try:
            # Get LLM response
            response = await self._llm_call(
                self._format_prompt(system_prompt, user_prompt)
            )
            
            # Debug: Log the type and content of response
            logger.debug(f"keyword extraction response type: {type(response)}")
            logger.debug(f"keyword extraction response content: {str(response)[:200]}")
            
            # Handle case where OpenAI might return a list directly
            if isinstance(response, list):
                logger.info("LLM returned a list directly for keywords")
                keywords = [str(k).strip() for k in response if k][:3]
                logger.info(f"LLM extracted keywords: {keywords}")
                return keywords
            
            # Parse JSON response
            import json
            # Extract JSON from response if wrapped
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "[" in response and "]" in response:
                # Extract JSON array
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                response = response[json_start:json_end]
            
            keywords = json.loads(response)
            
            # Validate and limit
            if isinstance(keywords, list):
                keywords = [str(k).strip() for k in keywords if k][:3]
                logger.info(f"LLM extracted keywords: {keywords}")
                return keywords
            else:
                logger.warning(f"LLM returned non-list response, falling back")
                return await self._fallback_keyword_extraction(title, body)
                
        except Exception as e:
            logger.warning(f"Failed to extract keywords via LLM: {e}, using fallback")
            return await self._fallback_keyword_extraction(title, body)
    
    async def _fallback_keyword_extraction(self, title: str, body: str) -> List[str]:
        """Fallback keyword extraction using KeywordExtractionTool.
        
        Args:
            title: PR title
            body: PR body
            
        Returns:
            List of keywords (max 3)
        """
        from app.mcp.tools.low_level.keyword_tools import KeywordExtractionTool
        
        tool = KeywordExtractionTool()
        result = await tool.execute(title=title, body=body)
        return result.get("keywords", ["unknown"])
    
    async def _analyze_project_structure(
        self,
        workspace_path: str,
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """Analyze project structure to find E2E reference files.
        
        Args:
            workspace_path: Workspace path
            changed_files: List of changed files to exclude
            
        Returns:
            Structure analysis result
        """
        from app.mcp.tools.mid_level.project_structure_analyzer import ProjectStructureAnalyzerTool
        
        analyzer = ProjectStructureAnalyzerTool()
        result = await analyzer.execute(
            workspace_path=workspace_path,
            changed_files=changed_files,
            max_depth=10
        )
        
        return result

