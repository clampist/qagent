"""Test case development agent."""
from typing import Dict, Any, List, Optional
from app.agents.base import BaseAgent
import os
import json
import logging

logger = logging.getLogger(__name__)

# Import MCP tools
from app.mcp.tools.low_level.code_tools import CodeCleanerTool, PathValidatorTool
from app.mcp.tools.low_level.format_tools import (
    TestFileFormatterTool,
    FrontendFileFormatterTool,
    PageObjectFormatterTool,
    GitDiffFormatterTool
)
from app.mcp.tools.mid_level.test_tools import (
    SyntaxCheckerTool,
    FileModifierTool,
    TestStructureAnalyzerTool,
    TestFilePathDeterminerTool,
    TestFileFinderTool,
    TestDirectoryTreeGeneratorTool
)
from app.mcp.tools.mid_level.file_tools import (
    TestFileReaderTool,
    FrontendFileReaderTool,
    PageObjectReaderTool
)
from app.mcp.tools.mid_level.git_tools import FrontendGitDiffTool


class CaseDeveloper(BaseAgent):
    """Agent for developing actual test case code.
    
    This agent wraps test development methods as tools and provides both:
    1. Direct method calls (for backward compatibility)
    2. LangChain agent interface (for natural language prompts)
    """
    
    def __init__(self, llm_provider: Optional[str] = None):
        super().__init__(
            name="case_developer",
            description="Develop test case code based on test design",
            llm_provider=llm_provider
        )
        
        # Create tools from test development methods
        self.tools = self._create_tools()
        
        # Create agent using LangChain (if available)
        system_prompt = "You are a helpful assistant for test case development. " \
                       "You can develop test case code based on test design, generate test files, " \
                       "and modify existing test helpers and page objects. " \
                       "Always use the appropriate tool for the requested operation."
        self.agent = self._create_langchain_agent(self.tools, system_prompt, llm_provider)
    
    def _create_tools(self):
        """Create LangChain tools from test development methods."""
        tool = self._get_langchain_tool_decorator()
        if tool is None:
            return []
        
        # Store reference to self for closure
        developer = self
        
        @tool
        def develop_test_cases_tool(
            test_design: Dict[str, Any],
            workspace_path: str,
            requirement_analysis: Dict[str, Any] = None,
            previous_feedback: str = None
        ) -> List[Dict[str, Any]]:
            """Develop test case code based on test design.
            
            Args:
                test_design: Test design output from CaseDesigner (dict with design, frontend_requirements, etc.)
                workspace_path: Path to workspace directory
                requirement_analysis: Requirement analysis output (optional, dict with analysis, changed_files, etc.)
                previous_feedback: Feedback from previous attempt (optional, for retry scenarios)
            
            Returns:
                List of dicts containing:
                - file_path: Full path to generated/modified file
                - type: "new" or "modified"
                - test_cases: List of test cases (for new files)
                - code: Generated code (for new files)
                - syntax_valid: Whether syntax check passed
                - syntax_errors: List of syntax errors (if any)
                - changes: List of changes (for modified files)
                - status: "success" or "failed" (for modified files)
            """
            import asyncio
            try:
                return asyncio.run(
                    developer.develop(
                        test_design=test_design,
                        workspace_path=workspace_path,
                        requirement_analysis=requirement_analysis,
                        previous_feedback=previous_feedback
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    developer.develop(
                        test_design=test_design,
                        workspace_path=workspace_path,
                        requirement_analysis=requirement_analysis,
                        previous_feedback=previous_feedback
                    )
                )
            except Exception as e:
                logger.error(f"Error developing test cases: {e}")
                return [{"error": str(e)}]
        
        return [develop_test_cases_tool]
    
    async def develop(
        self,
        test_design: Dict[str, Any],
        workspace_path: str,
        requirement_analysis: Dict[str, Any] = None,
        previous_feedback: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Develop test cases.
        
        Args:
            test_design: Test design output from CaseDesigner
            workspace_path: Workspace path
            requirement_analysis: Requirement analysis output (optional)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract data from test_design
        design = test_design.get("design", {})
        test_cases = design.get("test_cases", [])
        test_framework = design.get("test_framework", "playwright")
        suite_name = design.get("test_suite_name", "e2e_tests")
        coverage_areas = design.get("coverage_areas", [])
        frontend_requirements = test_design.get("frontend_requirements", [])
        test_files_analyzed = test_design.get("test_files_analyzed", [])
        all_test_files = test_design.get("all_test_files", [])
        changed_file_contents = test_design.get("changed_file_contents", {})  # Reuse from case_designer
        changed_test_files = test_design.get("changed_test_files", [])  # Reuse from case_designer
        
        # Extract data from requirement_analysis if available        
        changed_files = requirement_analysis.get("changed_files", [])
        reference_files = requirement_analysis.get("reference_files", [])
        
        logger.info(f"Frontend Requirements: {len(frontend_requirements)}")
        logger.info(f"Test Cases to Develop: {len(test_cases)}")
        logger.info(f"Test Files Analyzed: {len(test_files_analyzed)}")
        logger.info(f"Changed Files: {len(changed_files)}")
        logger.info(f"Reference Files: {len(reference_files)}")
        
        # Get frontend path from test_design if available
        frontend_path = design.get("frontend_path")
        if frontend_path:
            # Use frontend directory as base
            base_path = frontend_path
        else:
            # Fallback to workspace root
            base_path = workspace_path
        
        # Step 1: Collect all test files to read
        # Use test files from case_designer (already includes changed_test_files)
        test_files_to_read = list(set(test_files_analyzed + all_test_files))
        
        # Deduplicate
        test_files_to_read = list(set(test_files_to_read))
        
        logger.info(f"Total test files to read: {len(test_files_to_read)} (excluded backend/ files)")
        
        # Step 4: Read test file contents (first 100 lines for style reference)
        test_file_reader = TestFileReaderTool()
        test_file_contents_result = await test_file_reader.execute(
            workspace_path=workspace_path,
            test_files=test_files_to_read,
            max_lines_per_file=100,  # Only first 100 lines for style reference
            max_files=20
        )
        test_file_contents = test_file_contents_result.get("contents", {})
        
        logger.info(f"Successfully read {len(test_file_contents)} test files (first 100 lines each)")
        
        # Step 5: Use frontend changed files from case_designer (avoid duplicate reads)
        if changed_file_contents:
            # Additional safety: filter out any backend files that might have slipped through
            frontend_changed_contents = {
                path: content 
                for path, content in changed_file_contents.items() 
                if not path.startswith('backend/')
            }
            logger.info(f"Reusing {len(frontend_changed_contents)} frontend changed files from case_designer (filtered backend files)")
        else:
            # Fallback: read if not provided (backward compatibility)
            frontend_file_reader = FrontendFileReaderTool()
            frontend_changed_result = await frontend_file_reader.execute(
                workspace_path=workspace_path,
                changed_files=changed_files,
                max_lines_per_file=300,
                max_files=15
            )
            frontend_changed_contents = frontend_changed_result.get("contents", {})
            logger.info(f"Read {len(frontend_changed_contents)} frontend changed files (fallback)")
        
        # Step 6: Read page-objects and helpers (complete content from reference_files)
        # reference_files already extracted above from requirement_analysis
        page_object_reader = PageObjectReaderTool()
        po_helper_result = await page_object_reader.execute(
            workspace_path=workspace_path,
            reference_files=reference_files,
            max_files=30
        )
        po_helper_contents = po_helper_result.get("contents", {})
        
        logger.info(f"Successfully read {len(po_helper_contents)} page-objects and helpers files (complete)")
        
        # Step 6.5: Get git diff for frontend files (TS/TSX/JS/JSX)
        frontend_git_diff_tool = FrontendGitDiffTool()
        git_diff_result = await frontend_git_diff_tool.execute(workspace_path=workspace_path)
        git_diff_output = git_diff_result.get("diff", "Git diff unavailable")
        logger.info(f"Retrieved git diff output: {len(git_diff_output)} characters")
        
        # Step 7: Find reference test file for style
        # Priority: 1) Same directory test file, 2) First available test file
        reference_test_file = 'tests/e2e/emails/detail/detail-flagging.spec.ts'
        if len(test_file_contents) == 0:
            logger.warning("No related test files found, searching for reference test file")
            
            # Try to find test file in same directory first
            # Example: if coverage is emails, look for tests/e2e/emails/*.spec.ts
            if coverage_areas and len(coverage_areas) > 0:
                main_area = coverage_areas[0].lower().replace(" ", "-")
                if "/" in main_area:
                    path_parts = main_area.split("/")
                    meaningful_parts = [p for p in path_parts if p not in ["src", "app", "components", "pages"]]
                    if meaningful_parts:
                        # Try to find test in the same category directory
                        target_dir = os.path.join(base_path, "tests", "e2e", *meaningful_parts[:-1])
                        if os.path.exists(target_dir):
                            for file in os.listdir(target_dir):
                                if file.endswith(('.spec.ts', '.spec.js', '.test.ts', '.test.js')):
                                    reference_test_file = os.path.relpath(os.path.join(target_dir, file), base_path)
                                    logger.info(f"Found same-directory reference test file: {reference_test_file}")
                                    break
            
            # Fallback: find first available test file (not longest)
            if not reference_test_file:
                test_file_finder = TestFileFinderTool()
                find_result = await test_file_finder.execute(base_path=base_path, find_longest=False)
                reference_test_file = find_result.get("test_file")
                if reference_test_file:
                    logger.info(f"Using first available test file as reference: {reference_test_file}")
            
            # Read the reference test file
            if reference_test_file:
                test_file_reader = TestFileReaderTool()
                test_file_contents_result = await test_file_reader.execute(
                    workspace_path=workspace_path,
                    test_files=[reference_test_file],
                    max_lines_per_file=500,
                    max_files=1
                )
                test_file_contents = test_file_contents_result.get("contents", {})
                logger.info(f"Using reference test file: {reference_test_file}")
        else:
            # Use first test file from existing list as reference
            reference_test_file = list(test_file_contents.keys())[0] if test_file_contents else None
        
        # Analyze project structure for better file naming
        test_structure_analyzer = TestStructureAnalyzerTool()
        existing_test_structure_result = await test_structure_analyzer.execute(base_path=base_path)
        existing_test_structure = {
            "exists": existing_test_structure_result.get("exists", False),
            "examples": existing_test_structure_result.get("examples", []),
            "count": existing_test_structure_result.get("count", 0)
        }
        
        # Generate test directory tree
        test_dir_tree_generator = TestDirectoryTreeGeneratorTool()
        test_dir_tree_result = await test_dir_tree_generator.execute(base_path=base_path, max_depth=5)
        test_dir_tree = test_dir_tree_result.get("tree", "Test directory not found")
        logger.info(f"Generated test directory tree with {len(test_dir_tree.splitlines())} lines")
        
        # Determine test file path based on reference test file directory
        test_file_path_determiner = TestFilePathDeterminerTool()
        test_file_path_result = await test_file_path_determiner.execute(
            base_path=base_path,
            suite_name=suite_name,
            coverage_areas=coverage_areas,
            existing_structure=existing_test_structure,
            test_framework=test_framework,
            reference_test_file=reference_test_file  # Use reference test file to determine directory
        )
        test_file_path = test_file_path_result.get("test_file_path", "")
        
        # Build development prompt
        feedback_section = ""
        if previous_feedback:
            feedback_section = f"""

🚨 IMPORTANT - PREVIOUS ATTEMPT FEEDBACK:
The previous test generation attempt failed. Please carefully review the feedback below and fix all issues:

{previous_feedback}

CRITICAL INSTRUCTIONS FOR RETRY:
1. Read the feedback carefully and understand what went wrong
2. Fix ALL issues mentioned in the feedback
3. Pay special attention to:
   - Syntax errors (if any)
   - Logic errors in test steps
   - Missing setup or teardown
   - Incorrect method calls or imports
   - Missing assertions or incorrect expectations
4. Ensure the regenerated code addresses ALL feedback points
5. If feedback mentions specific methods don't exist, use alternative approaches
"""
        
        system_prompt = f"""You are a test case development agent. Your task is to:
1. Generate actual test code in {test_framework} format
2. Follow the EXACT style and patterns from existing test files
3. Use the SAME test utilities, helpers, and page objects as existing tests
4. Include proper assertions and error handling
5. Determine appropriate file path and name based on test content
6. Output in JSON format with new_files and optional modified_files
{feedback_section}

OUTPUT FORMAT REQUIREMENTS:
You MUST output a JSON object with the following structure:
{{
  "new_files": [
    {{
      "file_path": "tests/e2e/subdirectory/test-name.spec.ts",
      "code": "import {{ test, expect }} from '@playwright/test';\\n\\ntest.describe(...",
      "reason": "Primary test file for the new functionality"
    }}
  ],
  "modified_files": [
    {{
      "file_path": "tests/page-objects/EmailListPage.ts",
      "changes": [
        {{
          "type": "add_method",
          "location": "after_method:existingMethod",
          "code": "  async newHelperMethod() {{\n    // Implementation\n  }}",
          "reason": "Add helper method needed by new test case"
        }},
        {{
          "type": "add_property",
          "location": "after_property:highRiskButton",
          "code": "  readonly mediumRiskButton: Locator;",
          "reason": "Add locator property for Medium Risk button"
        }},
        {{
          "type": "add_code",
          "location": "after_line:this.highRiskButton = page.getByTestId(Selectors.FLAG_HIGH_RISK_BUTTON);",
          "code": "    this.mediumRiskButton = page.getByTestId(Selectors.FLAG_MEDIUM_RISK_BUTTON);",
          "reason": "Initialize the Medium Risk button locator in constructor"
        }},
        {{
          "type": "add_constant",
          "location": "inside:EmailStatus",
          "code": "  MEDIUM_RISK: \"Medium Risk\"",
          "reason": "Add new status constant to existing EmailStatus object"
        }}
      ]
    }}
  ]
}}

⚠️ CRITICAL SYNTAX FOR add_constant TYPE:
When adding properties to constant objects, follow TypeScript object property syntax:

CORRECT EXAMPLES:
✅ "code": "  MEDIUM_RISK: \"Medium Risk\""  ← Simple property, NO 'as const', NO semicolon
✅ "code": "  MAX_SIZE: 1000"  ← Number property
✅ "code": "  ENABLED: true"  ← Boolean property

WRONG EXAMPLES (will cause syntax errors):
❌ "code": "  MEDIUM_RISK: \"Medium Risk\" as const"  ← NO 'as const' on individual properties!
❌ "code": "  MEDIUM_RISK: \"Medium Risk\" as const, as const;"  ← Multiple 'as const' is wrong!
❌ "code": "  MEDIUM_RISK: \"Medium Risk\";"  ← NO semicolon inside object!
❌ "code": "export const MEDIUM_RISK = \"Medium Risk\""  ← This is for NEW const, not object property!

REMEMBER:
- Object properties use format: "KEY: value" (with comma added automatically)
- The 'as const' goes OUTSIDE the object: }} as const;
- NO 'as const' on individual properties
- NO semicolons inside object properties

⚠️ MODIFICATION TYPES EXPLAINED:

1. **add_method**: Add a new method to a class
   - location: "after_method:existingMethod" or "end_of_class"
   - code: Complete method implementation
   - Use: When test needs a new helper method in page object

2. **add_property**: Add a class property (e.g., readonly field)
   - location: "after_property:existingProperty" or "start_of_class"
   - code: Property declaration (e.g., "readonly button: Locator;")
   - Use: When adding a new UI element locator to page object

3. **add_code**: Add code at specific location (e.g., in constructor)
   - location: "after_line:exact line to search" or "inside_constructor:"
   - code: Code to insert (e.g., initialization statement)
   - Use: When initializing properties in constructor

4. **add_constant**: Add to existing constant object or create new
   - location: "inside:ConstantName" (add property) or "after_constant:ConstantName" (add new)
   - code: Property or constant definition
   - Use: When adding new constants/enums

5. **add_import**: Add import statement at top of file
   - location: (optional, auto-placed after existing imports)
   - code: Import statement
   - Use: When importing new dependencies

6. **add_helper**: Add helper function at end of file
   - location: (optional)
   - code: Complete function implementation
   - Use: When adding standalone utility functions

CRITICAL MODIFICATION RESTRICTIONS:
🚨 EXTREMELY IMPORTANT - READ CAREFULLY:

1. ALLOWED MODIFICATIONS (tests/ directory ONLY):
   ✅ tests/helpers/ - Add/modify test helper functions
   ✅ tests/page-objects/ - Add methods to existing page objects
   ✅ tests/fixtures/ - Add test fixtures
   ✅ tests/support/ - Add support utilities
   
2. FORBIDDEN MODIFICATIONS:
   ❌ src/ - NEVER modify business source code
   ❌ components/ - NEVER modify application components
   ❌ pages/ - NEVER modify application pages
   ❌ lib/ - NEVER modify application libraries
   ❌ Any file outside tests/ directory

3. MODIFICATION PRINCIPLES:
   - "Only make MINIMAL changes to support new test cases"
   - "DO NOT rewrite or refactor existing helpers unless explicitly required"
   - "Add new methods, DO NOT modify existing method signatures"
   - "Each change MUST have a clear 'reason' explaining necessity"
   - "Prefer creating NEW helpers over modifying existing ones"

4. WHEN TO MODIFY vs CREATE:
   - Modify: When adding a closely related method to existing page object
   - Create: When functionality is independent or reusable across tests

IMPORTANT FILE PATH REQUIREMENTS:
- Determine the best file path based on test content and existing structure
- Suggested starting point: {test_file_path}
- Use kebab-case naming (e.g., 'user-login.spec.ts', 'email-filtering.spec.ts')
- Reflect the actual feature/functionality being tested in the filename
- Follow existing project structure patterns
- You can adjust the path/filename if you have a better suggestion

CRITICAL IMPORT PATH REQUIREMENTS:
🚨 EXTREMELY IMPORTANT - IMPORT PATHS MUST MATCH FILE LOCATION:
- Calculate relative import paths based on your chosen file location
- page-objects/ and helpers/ are at tests/ level (not inside e2e/)
- Count '../' levels carefully from your file location to tests/

EXAMPLE: If file at tests/e2e/emails/risk-flagging.spec.ts
  → Import from tests/page-objects/: '../../../page-objects/EmailListPage'
  → Import from tests/helpers/: '../../../helpers/auth-helper'
  → Explanation: ../../../ goes emails/ → e2e/ → tests/

RECOMMENDATION:
- Follow existing directory patterns shown in test files
- Group related tests in subdirectories under e2e/
- Study the provided test file examples for correct import patterns

WRONG import paths will cause "Cannot find module" errors!

CRITICAL DEPENDENCY RESTRICTIONS:
🚨 DO NOT INSTALL OR IMPORT THIRD-PARTY LIBRARIES:
- ❌ FORBIDDEN: import {{ PrismaClient }} from '@prisma/client'
- ❌ FORBIDDEN: import axios from 'axios'
- ❌ FORBIDDEN: Any database clients (Prisma, MongoDB, MySQL, etc.)
- ❌ FORBIDDEN: HTTP clients (axios, fetch wrappers, etc.)
- ❌ FORBIDDEN: Any npm packages NOT already in the project
- ✅ ALLOWED: @playwright/test (testing framework)
- ✅ ALLOWED: Existing page objects, helpers, and fixtures in tests/ directory
- ✅ ALLOWED: Standard Playwright APIs and built-in Node.js modules

⚠️ DATABASE/API ACCESS:
- DO NOT access database directly (no Prisma, no SQL)
- DO NOT make external API calls (no axios, no fetch to external services)
- Tests should ONLY interact with the UI through Playwright
- Use Playwright's built-in page.goto(), page.locator(), etc.
- Verify test data through UI assertions, NOT database queries

CRITICAL METHOD USAGE REQUIREMENTS:
🚨 EXTREMELY IMPORTANT - READ CAREFULLY:
- You will be provided with existing test files, helpers, and page objects
- ONLY use methods, properties, and functions that ACTUALLY EXIST in those files
- DO NOT invent or assume methods exist - verify them in the provided code
- If you see a class like 'EmailListPage', check what methods it ACTUALLY has
- DO NOT call methods like 'getEmailByStatus()' unless you see it defined in the provided code

⚠️ COMMON MISTAKES TO AVOID:
- ❌ emailListPage.filterByStatus() ← method doesn't exist!
- ❌ emailListPage.waitForEmailsToLoad() ← method doesn't exist!
- ❌ emailListPage.getEmailByStatus() ← method doesn't exist!
- ❌ emailListPage.paginationInfo ← property doesn't exist!
- ✅ emailListPage.selectFilter('medium_risk') ← CORRECT, this method exists!
- ✅ emailListPage.waitForLoadState() ← CORRECT, this method exists!
- ✅ emailListPage.getEmailCount() ← CORRECT, this method exists!
- ✅ emailListPage.paginationControls ← CORRECT, this property exists!
- ✅ emailListPage.emailCards.first() ← uses actual Playwright locator methods

📋 VERIFICATION CHECKLIST BEFORE WRITING CODE:
1. Find the class definition in the provided page-objects/helpers code
2. Read through ALL available methods in that class
3. Copy the EXACT method name (including capitalization)
4. Check the method signature (parameters it accepts)
5. Only then use it in your test code

When in doubt, use standard Playwright locator methods:
- page.locator('selector')
- locator.first(), locator.nth(i), locator.filter()
- Standard Playwright assertions with expect()

Study the provided files carefully to understand available methods before using them

IMPORTANT STYLE REQUIREMENTS:
- Study the existing test files carefully
- Use the SAME imports, utilities, and helper functions
- Follow the SAME test structure and naming conventions
- Reuse existing page objects, fixtures, and selectors
- Match the coding style (indentation, quotes, semicolons, etc.)"""
        
        # Format sections
        test_file_formatter = TestFileFormatterTool()
        test_files_result = await test_file_formatter.execute(test_file_contents=test_file_contents, max_files=10)
        test_files_section = test_files_result.get("formatted", "")
        
        frontend_file_formatter = FrontendFileFormatterTool()
        frontend_changed_result = await frontend_file_formatter.execute(frontend_changed_contents=frontend_changed_contents)
        frontend_changed_section = frontend_changed_result.get("formatted", "")
        
        page_object_formatter = PageObjectFormatterTool()
        po_helper_result = await page_object_formatter.execute(po_helper_contents=po_helper_contents)
        po_helper_section = po_helper_result.get("formatted", "")
        
        git_diff_formatter = GitDiffFormatterTool()
        git_diff_result = await git_diff_formatter.execute(git_diff=git_diff_output, max_length=5000)
        git_diff_section = git_diff_result.get("formatted", "")
        
        user_prompt = f"""# Frontend Requirements
{json.dumps(frontend_requirements, indent=2)}

# Test Cases to Implement
{json.dumps(test_cases, indent=2)}

# Test Framework Configuration
Test Framework: {test_framework}
Suggested File Path: {test_file_path}
Coverage Areas: {', '.join(coverage_areas) if coverage_areas else 'General functionality'}

# Test Directory Structure
{test_dir_tree}

{frontend_changed_section}

{git_diff_section}

{po_helper_section}

{test_files_section}

Based on the above context:
1. Frontend requirements that need testing
2. Test case designs with steps and expected results
3. Git diff showing the exact code changes in frontend files
4. Test directory structure (USE THIS to calculate correct import paths!)
5. Existing test file examples showing the project's testing patterns

🚨 CRITICAL INSTRUCTION - VERIFY BEFORE USING:
Before calling ANY method on page objects, helpers, or utilities:
1. ✅ CHECK if that method EXISTS in the provided code above
2. ✅ LOOK at the actual class definition to see available methods
3. ✅ READ the method signature to understand parameters
4. ✅ VERIFY method name spelling and capitalization
5. ❌ DO NOT assume or invent methods that don't exist
6. ❌ DO NOT use similar-sounding method names without verification

🚨 CRITICAL DEPENDENCY RESTRICTIONS - READ CAREFULLY:
1. ❌ DO NOT import third-party libraries (@prisma/client, axios, etc.)
2. ❌ DO NOT access database directly (no Prisma, no SQL, no database clients)
3. ❌ DO NOT make external API calls (no axios, no fetch to external APIs)
4. ✅ ONLY use @playwright/test and existing test utilities
5. ✅ ONLY interact with UI through Playwright page/locator methods
6. ✅ Verify data through UI assertions, NOT database queries

⚠️ REAL EXAMPLES OF FORBIDDEN CODE:
- ❌ import {{ PrismaClient }} from '@prisma/client' ← FORBIDDEN!
- ❌ const prisma = new PrismaClient() ← FORBIDDEN!
- ❌ await prisma.email.findUnique(...) ← FORBIDDEN!
- ❌ await prisma.email.update(...) ← FORBIDDEN!
- ❌ import axios from 'axios' ← FORBIDDEN!
- ✅ import {{ test, expect }} from '@playwright/test' ← CORRECT!
- ✅ await page.goto('http://localhost:3000/emails') ← CORRECT!
- ✅ await expect(page.locator('[data-testid="status"]')).toContainText('Medium Risk') ← CORRECT!

⚠️ REAL EXAMPLES OF MISTAKES TO AVOID (from actual errors):
- ❌ emailListPage.filterByStatus('medium_risk') ← WRONG! Method doesn't exist
- ✅ emailListPage.selectFilter('medium_risk') ← CORRECT! Use this instead

- ❌ emailListPage.waitForEmailsToLoad() ← WRONG! Method doesn't exist
- ✅ emailListPage.waitForLoadState() ← CORRECT! Use this instead

- ❌ emailListPage.getEmailByStatus() ← WRONG! Method doesn't exist
- ✅ emailListPage.getEmailStatus(rowIndex) ← CORRECT! Takes row index parameter

- ❌ emailListPage.paginationInfo ← WRONG! Property doesn't exist
- ✅ emailListPage.paginationControls ← CORRECT! Use this property instead

- ❌ helper.findElementByText() ← WRONG! Method doesn't exist
- ✅ page.locator('selector').filter({{ hasText: 'text' }}) ← CORRECT! Standard Playwright

IF YOU'RE UNSURE:
- Use standard Playwright locator methods: .locator(), .first(), .nth(), .filter()
- Use standard Playwright assertions: expect(locator).toBeVisible()
- Don't guess method names - verify them in the provided code

Please generate:
1. Determine appropriate file paths for new test files
2. Generate complete test code
3. Identify if any helper/page-object modifications are needed (MINIMAL only)
4. Output in JSON format:

{{
  "new_files": [
    {{
      "file_path": "your/chosen/path/test-name.spec.ts",
      "code": "your test code here (NO markdown, NO backticks, PURE code)",
      "reason": "Brief explanation"
    }}
  ],
  "modified_files": [  // ONLY if absolutely necessary
    {{
      "file_path": "tests/page-objects/SomePage.ts",  // MUST be in tests/ directory
      "changes": [
        {{
          "type": "add_method",
          "location": "after_method:existingMethod",
          "code": "method implementation",
          "reason": "Why this change is necessary"
        }},
        {{
          "type": "add_property",
          "location": "after_property:existingProperty",
          "code": "  readonly newProperty: Locator;",
          "reason": "Add property for new UI element"
        }},
        {{
          "type": "add_code",
          "location": "after_line:this.existingProperty = page.locator('...');",
          "code": "    this.newProperty = page.locator('...');",
          "reason": "Initialize the new property"
        }}
      ]
    }}
  ]
}}

IMPORTANT CONSTRAINTS:
- Implement ALL the test cases from the design
- Follow the EXACT style and patterns from existing test files
- Use CORRECT relative import paths based on your chosen file location
- ONLY call methods that ACTUALLY EXIST in the provided helper/page object code
- Reuse existing test utilities, helpers, and page objects AS THEY ARE DEFINED
- modified_files is OPTIONAL - only use if new test REQUIRES new helper methods
- modified_files MUST only contain paths in tests/ directory (helpers/, page-objects/, etc.)
- DO NOT modify src/, components/, pages/, or any business logic
- Each modification MUST have a clear reason
- Output ONLY valid JSON, no markdown code blocks, no explanations
- The 'code' field should contain PURE TypeScript/JavaScript code (no ``` markers!)"""
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: Log prompts for debugging
        logger.debug("="*80)
        logger.debug("SYSTEM PROMPT:")
        logger.debug("="*80)
        logger.debug(system_prompt)
        logger.debug("="*80)
        logger.debug("USER PROMPT (first 2000 chars):")
        logger.debug("="*80)
        # logger.debug(user_prompt[:2000] + "..." if len(user_prompt) > 2000 else user_prompt)
        logger.debug(user_prompt)
        logger.debug("="*80)
        
        # Get LLM code generation
        llm_response = await self._llm_call(
            self._format_prompt(system_prompt, user_prompt)
        )
        
        # Debug: Log full LLM response
        logger.debug("="*80)
        logger.debug("LLM Response (Case Development):")
        logger.debug(f"Response length: {len(llm_response)} characters")
        logger.debug("First 1000 characters:")
        logger.debug(llm_response[:1000])
        logger.debug("="*80)
        
        # Parse LLM response (new format: new_files + modified_files)
        generated_files = []  # List to store all generated/modified files
        
        try:
            # Clean the response before parsing JSON
            # Remove common prefixes like "JSON", "```json", etc.
            cleaned_response = llm_response.strip()
            
            # Remove markdown code blocks
            if cleaned_response.startswith("```"):
                lines = cleaned_response.split("\n")
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines)
            
            # Remove leading text like "JSON", "json", "Here is the JSON:", etc.
            cleaned_response = cleaned_response.strip()
            for prefix in ["JSON", "json", "Json"]:
                if cleaned_response.startswith(prefix):
                    # Find the first { or [
                    json_start = cleaned_response.find("{")
                    if json_start == -1:
                        json_start = cleaned_response.find("[")
                    if json_start > 0:
                        cleaned_response = cleaned_response[json_start:]
                    break
            
            logger.debug(f"Cleaned response for JSON parsing (first 200 chars): {cleaned_response[:200]}")
            
            # Try to parse as JSON
            response_json = json.loads(cleaned_response)
            
            # New format: {"new_files": [...], "modified_files": [...]}
            if isinstance(response_json, dict) and "new_files" in response_json:
                logger.info("Detected new JSON format with new_files structure")
                
                # Process new_files
                new_files = response_json.get("new_files", [])
                for new_file in new_files:
                    if not isinstance(new_file, dict) or "file_path" not in new_file or "code" not in new_file:
                        logger.warning(f"Skipping invalid new_file entry: {new_file}")
                        continue
                    
                    file_path = new_file["file_path"]
                    code = new_file["code"]
                    reason = new_file.get("reason", "New test file")
                    
                    # Convert relative path to absolute
                    if not os.path.isabs(file_path):
                        base_name = os.path.basename(base_path)
                        if file_path.startswith(base_name + "/") or file_path.startswith(base_name + os.sep):
                            file_path = os.path.join(workspace_path, file_path)
                        else:
                            file_path = os.path.join(base_path, file_path)
                        logger.info(f"Converted to absolute path: {file_path}")
                    
                    logger.info(f"New file: {file_path} (reason: {reason})")
                    
                    # Clean code
                    code_cleaner = CodeCleanerTool()
                    code_result = await code_cleaner.execute(code=code)
                    code = code_result.get("cleaned_code", code)
                    
                    # Ensure directory exists
                    test_dir = os.path.dirname(file_path)
                    os.makedirs(test_dir, exist_ok=True)
                    
                    # Write file
                    with open(file_path, "w") as f:
                        f.write(code)
                    
                    logger.info(f"Wrote new test file: {file_path} ({len(code)} chars)")
                    
                    # Syntax check
                    syntax_checker = SyntaxCheckerTool()
                    # Convert absolute path to relative for syntax checker
                    rel_file_path = os.path.relpath(file_path, base_path) if os.path.isabs(file_path) else file_path
                    syntax_check_result = await syntax_checker.execute(test_file=rel_file_path, workspace_path=base_path)
                    syntax_check = {
                        "valid": syntax_check_result.get("valid", False),
                        "errors": syntax_check_result.get("errors", [])
                    }
                    
                    generated_files.append({
                        "file_path": file_path,
                        "type": "new",
                        "test_cases": test_cases,  # Include test cases for consistency with fallback mode
                        "code": code,
                        "reason": reason,
                        "syntax_valid": syntax_check.get("valid", False),
                        "syntax_errors": syntax_check.get("errors", [])
                    })
                
                # Process modified_files
                modified_files = response_json.get("modified_files", [])
                if modified_files:
                    logger.info(f"Processing {len(modified_files)} modified files")
                    
                    for mod_file in modified_files:
                        if not isinstance(mod_file, dict) or "file_path" not in mod_file:
                            logger.warning(f"Skipping invalid modified_file entry: {mod_file}")
                            continue
                        
                        file_path = mod_file["file_path"]
                        changes = mod_file.get("changes", [])
                        
                        # CRITICAL: Validate that file is in tests/ directory
                        path_validator = PathValidatorTool()
                        # Convert to relative path for validation
                        rel_file_path = os.path.relpath(file_path, base_path) if os.path.isabs(file_path) else file_path
                        validation_result = await path_validator.execute(file_path=rel_file_path)
                        if not validation_result.get("allowed", False):
                            logger.error(f"REJECTED: Attempted to modify file outside tests/: {file_path}")
                            logger.error("Modifications are only allowed in tests/ directory!")
                            continue
                        
                        # Debug: Log path info before conversion
                        logger.debug(f"Modified file - original path from LLM: {file_path}")
                        logger.debug(f"base_path: {base_path}")
                        logger.debug(f"workspace_path: {workspace_path}")
                        
                        # Convert to absolute path
                        if not os.path.isabs(file_path):
                            # Check if file_path already starts with base_path components
                            # to avoid duplication like frontend/frontend/tests
                            base_name = os.path.basename(base_path)
                            
                            # If LLM returns path like "frontend/tests/helpers/constants.ts"
                            # and base_path is "/path/to/workspace/frontend/tests"
                            # we should remove the duplicate "frontend/tests" prefix
                            if file_path.startswith(base_name + "/") or file_path.startswith(base_name + os.sep):
                                # Remove the base_name prefix to avoid duplication
                                file_path = file_path.split("/", 1)[1] if "/" in file_path else file_path.split(os.sep, 1)[1]
                                logger.info(f"Removed duplicate base_name prefix: {file_path}")
                            
                            # Also check for "tests/" prefix when base_path ends with "tests"
                            if base_path.endswith("/tests") or base_path.endswith("\\tests") or base_path.endswith("/test") or base_path.endswith("\\test"):
                                if file_path.startswith("tests/") or file_path.startswith("test/"):
                                    # Remove "tests/" prefix
                                    file_path = file_path.split("/", 1)[1] if "/" in file_path else file_path.split(os.sep, 1)[1]
                                    logger.info(f"Removed duplicate tests/ prefix: {file_path}")
                            
                            file_path = os.path.join(base_path, file_path)
                            logger.info(f"Converted to absolute path: {file_path}")
                        else:
                            logger.debug(f"Path is already absolute: {file_path}")
                        
                        logger.info(f"Modified file: {file_path} ({len(changes)} changes)")
                        
                        # Apply changes
                        file_modifier = FileModifierTool()
                        # Convert to relative path for file modifier
                        rel_file_path = os.path.relpath(file_path, base_path) if os.path.isabs(file_path) else file_path
                        mod_result = await file_modifier.execute(
                            file_path=rel_file_path,
                            changes=changes,
                            workspace_path=base_path
                        )
                        success = mod_result.get("success", False)
                        message = mod_result.get("message", "Unknown error")
                        
                        if success:
                            logger.info(f"Successfully applied modifications to {file_path}")
                            generated_files.append({
                                "file_path": file_path,
                                "type": "modified",
                                "changes": changes,
                                "status": "success",
                                "message": message
                            })
                        else:
                            logger.error(f"Failed to apply modifications to {file_path}: {message}")
                            generated_files.append({
                                "file_path": file_path,
                                "type": "modified",
                                "changes": changes,
                                "status": "failed",
                                "message": message
                            })
                
                # Return results
                return generated_files
            
            # Fallback: Old format {"file_path": "...", "code": "..."}
            elif isinstance(response_json, dict) and "file_path" in response_json and "code" in response_json:
                logger.info("Detected legacy JSON format, converting to new format")
                test_file_path_final = response_json["file_path"]
                test_code = response_json["code"]
                
                # Convert relative path to absolute
                if not os.path.isabs(test_file_path_final):
                    base_name = os.path.basename(base_path)
                    if test_file_path_final.startswith(base_name + "/") or test_file_path_final.startswith(base_name + os.sep):
                        test_file_path_final = os.path.join(workspace_path, test_file_path_final)
                    else:
                        test_file_path_final = os.path.join(base_path, test_file_path_final)
                    logger.info(f"Converted to absolute path: {test_file_path_final}")
                
                # Clean code
                code_cleaner = CodeCleanerTool()
                code_result = await code_cleaner.execute(code=test_code)
                test_code = code_result.get("cleaned_code", test_code)
                
                # Ensure directory exists and write file
                test_dir = os.path.dirname(test_file_path_final)
                os.makedirs(test_dir, exist_ok=True)
                with open(test_file_path_final, "w") as f:
                    f.write(test_code)
                
                logger.info(f"Wrote test file: {test_file_path_final}")
                
                # Syntax check
                syntax_checker = SyntaxCheckerTool()
                rel_file_path = os.path.relpath(test_file_path_final, base_path) if os.path.isabs(test_file_path_final) else test_file_path_final
                syntax_check_result = await syntax_checker.execute(test_file=rel_file_path, workspace_path=base_path)
                syntax_check = {
                    "valid": syntax_check_result.get("valid", False),
                    "errors": syntax_check_result.get("errors", [])
                }
                
                return [{
                    "file_path": test_file_path_final,
                    "type": "new",
                    "test_cases": test_cases,
                    "code": test_code,
                    "syntax_valid": syntax_check.get("valid", False),
                    "syntax_errors": syntax_check.get("errors", [])
                }]
            else:
                logger.warning("JSON response has unexpected structure, treating as raw code")
                raise json.JSONDecodeError("Unexpected JSON structure", llm_response, 0)
                
        except json.JSONDecodeError:
            logger.info("LLM response is not JSON format, treating as raw code (legacy mode)")
            
            # Fallback: treat entire response as code
            test_file_path_final = test_file_path
            code_cleaner = CodeCleanerTool()
            code_result = await code_cleaner.execute(code=llm_response)
            test_code = code_result.get("cleaned_code", llm_response)
            
            # Ensure directory exists and write file
            test_dir = os.path.dirname(test_file_path_final)
            os.makedirs(test_dir, exist_ok=True)
            with open(test_file_path_final, "w") as f:
                f.write(test_code)
            
            logger.info(f"Wrote test file: {test_file_path_final}")
            
            # Syntax check
            syntax_checker = SyntaxCheckerTool()
            rel_file_path = os.path.relpath(test_file_path_final, base_path) if os.path.isabs(test_file_path_final) else test_file_path_final
            syntax_check_result = await syntax_checker.execute(test_file=rel_file_path, workspace_path=base_path)
            syntax_check = {
                "valid": syntax_check_result.get("valid", False),
                "errors": syntax_check_result.get("errors", [])
            }
            
            return [{
                "file_path": test_file_path_final,
                "type": "new",
                "test_cases": test_cases,
                "code": test_code,
                "syntax_valid": syntax_check.get("valid", False),
                "syntax_errors": syntax_check.get("errors", [])
            }]
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task.
        
        This method can be called with natural language prompts or direct tool calls.
        
        Args:
            prompt: Natural language prompt (e.g., "Develop test cases for the test design in workspace /path/to/workspace")
            action: Direct action name ("develop")
            test_design: Test design output (required for direct action)
            workspace_path: Workspace path (required for direct action)
            requirement_analysis: Requirement analysis output (optional)
            previous_feedback: Feedback from previous attempt (optional)
            **kwargs: Additional parameters for the action
        """
        prompt = kwargs.get("prompt", "")
        action = kwargs.get("action", "")
        
        # If action is specified, call method directly
        if action == "develop":
            test_design = kwargs.get("test_design", {})
            workspace_path = kwargs.get("workspace_path", "")
            requirement_analysis = kwargs.get("requirement_analysis")
            previous_feedback = kwargs.get("previous_feedback")
            if test_design and workspace_path:
                cases = await self.develop(
                    test_design=test_design,
                    workspace_path=workspace_path,
                    requirement_analysis=requirement_analysis,
                    previous_feedback=previous_feedback
                )
                return {"test_cases": cases}
        
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
        
        # Fallback to direct develop if no prompt/action but test_design and workspace_path provided
        test_design = kwargs.get("test_design", {})
        workspace_path = kwargs.get("workspace_path", "")
        if test_design and workspace_path:
            logger.info("No explicit action or prompt, falling back to direct develop method.")
            cases = await self.develop(
                test_design=test_design,
                workspace_path=workspace_path,
                requirement_analysis=kwargs.get("requirement_analysis"),
                previous_feedback=kwargs.get("previous_feedback")
            )
            return {"test_cases": cases}
        
        return {"error": "No valid action or prompt provided. Provide 'prompt', 'action', or 'test_design' + 'workspace_path'."}
