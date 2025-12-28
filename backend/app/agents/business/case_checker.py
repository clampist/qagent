"""Case result checker agent."""
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent
from app.mcp.tools.high_level.case_result_checker import CaseResultCheckerTool
from app.mcp.tools.low_level.format_tools import (
    FailedTestFormatterTool,
    TestCaseFormatterTool,
    TestDesignFormatterTool,
    RequirementAnalysisFormatterTool,
    SyntaxCheckResultFormatterTool,
    ResponseParserTool
)
from app.mcp.tools.mid_level.test_tools import BatchSyntaxCheckerTool
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class CaseCheckerAgent(BaseAgent):
    """Agent for reviewing test results and providing feedback for improvement.
    
    This agent wraps test review methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language prompts)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        # Use dedicated model for test checker (configured in .env)
        # This is a critical review step, so we want the best model
        # Use explicit parameter if provided, otherwise use global default from settings
        provider = llm_provider if llm_provider else settings.llm_provider
        
        # Get dedicated model for test checker
        if provider.lower() == "anthropic":
            model_name = settings.anthropic_model_for_check
            temperature = settings.anthropic_temperature_for_check
        else:
            # Use OpenAI model for check if configured, otherwise use default OpenAI model
            model_name = settings.openai_model_for_check or settings.openai_model
            # Use OpenAI temperature for check if configured, otherwise use Anthropic temperature setting
            temperature = settings.openai_temperature_for_check or settings.anthropic_temperature_for_check
        
        super().__init__(
            name="case_checker",
            description="Review test execution results and provide detailed feedback for improvement",
            llm_provider=provider,
            model_name=model_name,  # Use dedicated model
            temperature=temperature  # Use dedicated temperature
        )
        self.case_result_checker = CaseResultCheckerTool()
        self.failed_test_formatter = FailedTestFormatterTool()
        self.test_case_formatter = TestCaseFormatterTool()
        self.test_design_formatter = TestDesignFormatterTool()
        self.requirement_analysis_formatter = RequirementAnalysisFormatterTool()
        self.syntax_check_result_formatter = SyntaxCheckResultFormatterTool()
        self.response_parser = ResponseParserTool()
        self.batch_syntax_checker = BatchSyntaxCheckerTool()
        
        # Create tools from test review methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        system_prompt = "You are a helpful assistant for test result review. " \
                       "You can review test execution results, analyze failures, " \
                       "and provide detailed feedback for improving test cases. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, provider)
    
    def _create_tools(self):
        """Create LangChain tools from test review methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to self for closure
        checker = self
        
        @tool
        def review_test_results_tool(
            test_results: Dict[str, Any],
            test_cases: list,
            test_design: Dict[str, Any],
            requirement_analysis: Dict[str, Any] = None,
            retry_count: int = 0,
            max_retries: int = 3,
            workspace_path: str = None
        ) -> Dict[str, Any]:
            """Review test execution results and provide feedback for improvement.
            
            Args:
                test_results: Test execution results from CaseExecutionTool (dict with success, passed, total_tests, results)
                test_cases: List of generated test cases (list of dicts with file_path, code, etc.)
                test_design: Original test design (dict with design, test_cases, etc.)
                requirement_analysis: Requirement analysis (optional, dict with analysis, changed_files, etc.)
                retry_count: Current retry attempt number (default: 0)
                max_retries: Maximum retries allowed (default: 3)
                workspace_path: Workspace path for syntax checking (optional)
            
            Returns:
                Dict containing:
                - approved: bool - Whether tests are approved
                - action: str - Next action ("create_pr", "retry", "error")
                - summary: dict - Test execution summary
                - feedback: dict or None - Detailed feedback for improvement (if not approved)
                - retry_count: int - Updated retry count
                - retry_reason: str - Reason for retry (if applicable)
            """
            import asyncio
            try:
                return asyncio.run(
                    checker.review(
                        test_results=test_results,
                        test_cases=test_cases,
                        test_design=test_design,
                        requirement_analysis=requirement_analysis,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        workspace_path=workspace_path
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    checker.review(
                        test_results=test_results,
                        test_cases=test_cases,
                        test_design=test_design,
                        requirement_analysis=requirement_analysis,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        workspace_path=workspace_path
                    )
                )
            except Exception as e:
                logger.error(f"Error reviewing test results: {e}")
                return {"error": str(e), "approved": False, "action": "error"}
        
        return [review_test_results_tool]
    
    async def review(
        self,
        test_results: Dict[str, Any],
        test_cases: list,
        test_design: Dict[str, Any],
        requirement_analysis: Dict[str, Any] = None,
        retry_count: int = 0,
        max_retries: int = 3,
        workspace_path: str = None  # Add workspace_path for syntax checking
    ) -> Dict[str, Any]:
        """Review test results and provide feedback.
        
        Args:
            test_results: Test execution results from CaseExecutionTool
            test_cases: List of generated test cases
            test_design: Original test design
            requirement_analysis: Requirement analysis (optional)
            retry_count: Current retry attempt number
            max_retries: Maximum retries allowed
        
        Returns:
            Dict with review decision and feedback
        """
        # First, use the tool to check basic pass/fail
        tool_result = await self.case_result_checker.execute(
            test_results=test_results,
            retry_count=retry_count,
            max_retries=max_retries
        )
        
        # If tests passed, no need for detailed review
        if tool_result.get("ready_for_pr", False):
            return {
                "approved": True,
                "action": "create_pr",
                "summary": tool_result.get("summary"),
                "feedback": None
            }
        
        # If max retries reached, return error
        if retry_count >= max_retries:
            return {
                "approved": False,
                "action": "error",
                "summary": tool_result.get("summary"),
                "feedback": f"Maximum retries ({max_retries}) reached. Test execution failed.",
                "error": tool_result.get("error")
            }
        
        # Tests failed - need detailed review and feedback
        # Step 1: Check syntax for each test case file
        syntax_check_result = await self.batch_syntax_checker.execute(
            test_cases=test_cases,
            workspace_path=workspace_path
        )
        syntax_check_results = syntax_check_result
        
        # Step 2: Use LLM to analyze failures and provide actionable feedback
        system_prompt = """You are a senior QA engineer reviewing test execution results.
Your task is to:
1. Analyze test failures in detail
2. Identify root causes (code issues, test logic problems, environment issues, syntax errors, etc.)
3. Provide specific, actionable feedback for improving the test cases
4. Focus on what needs to be fixed in the test code itself

Be thorough but concise. Your feedback will be used to regenerate better test cases."""
        
        # Extract failure details from test results
        failed_tests = []
        error_messages = []
        
        for result in test_results.get("results", []):
            if not result.get("success", False):
                failed_tests.append({
                    "file": result.get("file", "unknown"),
                    "exit_code": result.get("exit_code"),
                    "stdout": result.get("stdout", "")[:1000],  # First 1000 chars
                    "stderr": result.get("stderr", "")[:2000]   # First 2000 chars
                })
                if result.get("stderr"):
                    error_messages.append(result.get("stderr")[:500])
        
        user_prompt = f"""# Test Execution Results Review

## Test Results Summary
- Total tests: {test_results.get('total_tests', 0)}
- Passed: {tool_result.get('summary', {}).get('passed_count', 0)}
- Failed: {tool_result.get('summary', {}).get('failed_count', 0)}
- Retry attempt: {retry_count + 1} / {max_retries}

## Syntax Check Results
{(await self.syntax_check_result_formatter.execute(syntax_results=syntax_check_results)).get('formatted', '')}

## Failed Test Details
{(await self.failed_test_formatter.execute(failed_tests=failed_tests)).get('formatted', '')}

## Generated Test Cases
{(await self.test_case_formatter.execute(test_cases=test_cases)).get('formatted', '')}

## Original Test Design
{(await self.test_design_formatter.execute(test_design=test_design)).get('formatted', '')}

## Requirement Analysis
{(await self.requirement_analysis_formatter.execute(requirement_analysis=requirement_analysis)).get('formatted', 'N/A') if requirement_analysis else 'N/A'}

## Your Task
Analyze the test failures and provide:
1. **Root Cause Analysis**: What went wrong? (syntax errors, logic errors, missing setup, etc.)
2. **Specific Issues**: List each specific problem found
3. **Actionable Feedback**: What should be changed in the test code?
4. **Recommendations**: How to fix the test cases?

Format your response as:
{{
  "root_causes": ["cause1", "cause2", ...],
  "specific_issues": ["issue1", "issue2", ...],
  "feedback": "Detailed feedback for improving test cases",
  "recommendations": ["recommendation1", "recommendation2", ...]
}}

Be specific and actionable. The feedback will be used to regenerate the test cases."""
        
        # Get LLM review
        review_response = await self._llm_call(
            self._format_prompt(system_prompt, user_prompt)
        )
        
        # Parse review response (may be JSON or text)
        parse_result = await self.response_parser.execute(response=review_response)
        feedback = {
            "root_causes": parse_result.get("root_causes", []),
            "specific_issues": parse_result.get("specific_issues", []),
            "feedback": parse_result.get("feedback", review_response),
            "recommendations": parse_result.get("recommendations", [])
        }
        
        logger.info(f"Test review completed. Approved: {feedback.get('approved', False)}")
        if not feedback.get("approved", False):
            logger.info(f"Feedback provided: {feedback.get('feedback', '')}...")
        
        return {
            "approved": False,
            "action": "retry",
            "summary": tool_result.get("summary"),
            "feedback": feedback,
            "retry_count": retry_count + 1,
            "retry_reason": "Test execution failed - feedback provided for regeneration"
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Review test results for the test cases in workspace /path/to/workspace")
            action: Direct action name ("review")
            test_results: Test execution results (required for direct action)
            test_cases: List of generated test cases (required for direct action)
            test_design: Original test design (required for direct action)
            requirement_analysis: Requirement analysis (optional)
            retry_count: Current retry attempt number (optional, default: 0)
            max_retries: Maximum retries allowed (optional, default: 3)
            workspace_path: Workspace path for syntax checking (optional)
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "review":
            test_results = kwargs.get("test_results", {})
            test_cases = kwargs.get("test_cases", [])
            test_design = kwargs.get("test_design", {})
            requirement_analysis = kwargs.get("requirement_analysis")
            retry_count = kwargs.get("retry_count", 0)
            max_retries = kwargs.get("max_retries", 3)
            workspace_path = kwargs.get("workspace_path")
            if test_results and test_cases and test_design:
                return await self.review(
                    test_results=test_results,
                    test_cases=test_cases,
                    test_design=test_design,
                    requirement_analysis=requirement_analysis,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    workspace_path=workspace_path
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
        
        # Fallback to direct review if no prompt/action but required params provided
        test_results = kwargs.get("test_results", {})
        test_cases = kwargs.get("test_cases", [])
        test_design = kwargs.get("test_design", {})
        if test_results and test_cases and test_design:
            logger.info("No explicit action or prompt, falling back to direct review method.")
            return await self.review(
                test_results=test_results,
                test_cases=test_cases,
                test_design=test_design,
                requirement_analysis=kwargs.get("requirement_analysis"),
                retry_count=kwargs.get("retry_count", 0),
                max_retries=kwargs.get("max_retries", 3),
                workspace_path=kwargs.get("workspace_path")
            )
        
        return {"error": "No valid action or prompt provided. Provide 'prompt', 'action', or 'test_results' + 'test_cases' + 'test_design'."}

