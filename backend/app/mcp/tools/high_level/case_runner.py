"""High-level case execution tools (MCP)."""
from typing import Dict, Any, List
from app.mcp.base import MCPTool


class CaseRunnerTool(MCPTool):
    """Run tests in workspace."""
    
    def __init__(self):
        super().__init__(
            name="case_runner",
            description="Run test suite in workspace",
            tool_type="high"
        )
    
    async def execute(
        self,
        workspace_path: str,
        test_command: str = "npm test",
        timeout: int = 600
    ) -> Dict[str, Any]:
        """Run tests."""
        import subprocess
        import os
        
        try:
            result = subprocess.run(
                test_command.split(),
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "passed": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Test execution timed out after {timeout} seconds"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "test_command": {"type": "string", "description": "Test command", "default": "npm test"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 600}
            },
            "required": ["workspace_path"]
        }


class E2ECaseRunnerTool(MCPTool):
    """Run E2E tests specifically."""
    
    def __init__(self):
        super().__init__(
            name="e2e_case_runner",
            description="Run end-to-end tests",
            tool_type="high"
        )
    
    async def execute(
        self,
        workspace_path: str,
        test_file: str = None,
        frontend_path: str = None,  # New parameter
        timeout: int = 1800
    ) -> Dict[str, Any]:
        """Run E2E tests."""
        import subprocess
        import os
        
        # Use frontend path if provided, otherwise use workspace path
        exec_path = frontend_path if frontend_path else workspace_path
        
        try:
            # Check if package.json exists
            package_json_path = os.path.join(exec_path, "package.json")
            if not os.path.exists(package_json_path):
                return {
                    "success": False,
                    "error": f"No package.json found in {exec_path}. Cannot run npm/yarn commands.",
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "package.json not found"
                }
            
            # Try common E2E test commands
            # Strategy: If test_file is specified, prioritize file-specific commands
            if test_file:
                # Run specific test file only
                # Headless mode will be controlled by environment variable
                # Add verbose flags for better error reporting
                commands = [
                    ["npx", "playwright", "test", test_file, "--reporter=list"],
                    # Fallback: try npm/yarn with file parameter (may not work for all setups)
                    ["npm", "run", "test:e2e", "--", test_file],
                    ["yarn", "test:e2e", test_file],
                ]
            else:
                # Run all E2E tests
                # Headless mode will be controlled by environment variable
                # Add verbose flags for better error reporting
                commands = [
                    ["npm", "run", "test:e2e"],
                    ["npm", "run", "e2e"],
                    ["yarn", "test:e2e"],
                    ["npx", "playwright", "test", "--reporter=list"],
                ]
            
            for cmd in commands:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    logger.info(f"Attempting to run test command: {' '.join(cmd)}")
                    logger.info(f"Working directory: {exec_path}")
                    logger.info(f"Timeout: {timeout} seconds")
                    
                    # Set environment variables for Playwright
                    # PLAYWRIGHT_HEADLESS: run in headless mode (no visible browser)
                    # PW_TEST_HTML_REPORT_OPEN: auto-open HTML report after test
                    import os
                    env = os.environ.copy()
                    env["PLAYWRIGHT_HEADLESS"] = "1"  # Enable headless mode
                    env["PW_TEST_HTML_REPORT_OPEN"] = "never"  # Options: always, never, on-failure
                    logger.info("Environment: PLAYWRIGHT_HEADLESS=1 (no visible browser)")
                    logger.info("Environment: PW_TEST_HTML_REPORT_OPEN=never (auto-open report on failure)")
                    
                    # Use Popen for better control and real-time output
                    import sys
                    process = subprocess.Popen(
                        cmd,
                        cwd=exec_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,  # Line buffered
                        universal_newlines=True,
                        env=env  # Pass environment variables
                    )
                    
                    try:
                        # Wait for completion with timeout
                        stdout, stderr = process.communicate(timeout=timeout)
                        return_code = process.returncode
                        
                        logger.info(f"Test command completed with exit code: {return_code}")
                        logger.info(f"stdout length: {len(stdout)} chars")
                        logger.info(f"stderr length: {len(stderr)} chars")
                        
                        # Log detailed output for debugging
                        if return_code != 0:
                            logger.error("="*80)
                            logger.error("TEST EXECUTION FAILED")
                            logger.error(f"Command: {' '.join(cmd)}")
                            logger.error(f"Exit code: {return_code}")
                            logger.error(f"Working directory: {exec_path}")
                            logger.error("="*80)
                            logger.error("STDOUT:")
                            logger.error(stdout if stdout else "(empty)")
                            logger.error("="*80)
                            logger.error("STDERR:")
                            logger.error(stderr if stderr else "(empty)")
                            logger.error("="*80)
                        else:
                            logger.info("="*80)
                            logger.info("TEST EXECUTION SUCCESSFUL")
                            logger.info(f"Command: {' '.join(cmd)}")
                            logger.info("="*80)
                            # Log first 500 chars of stdout for successful runs
                            if stdout:
                                logger.debug(f"STDOUT (first 500 chars): {stdout[:500]}")
                        
                        return {
                            "success": return_code == 0,
                            "exit_code": return_code,
                            "stdout": stdout,
                            "stderr": stderr,
                            "command": " ".join(cmd)
                        }
                    except subprocess.TimeoutExpired:
                        logger.error(f"Test execution timed out after {timeout} seconds")
                        process.kill()
                        stdout, stderr = process.communicate()
                        
                        # Log timeout details
                        logger.error("="*80)
                        logger.error("TEST EXECUTION TIMEOUT")
                        logger.error(f"Command: {' '.join(cmd)}")
                        logger.error(f"Timeout: {timeout} seconds")
                        logger.error(f"Working directory: {exec_path}")
                        logger.error("="*80)
                        logger.error("STDOUT (before timeout):")
                        logger.error(stdout if stdout else "(empty)")
                        logger.error("="*80)
                        logger.error("STDERR (before timeout):")
                        logger.error(stderr if stderr else "(empty)")
                        logger.error("="*80)
                        
                        return {
                            "success": False,
                            "error": f"Test execution timed out after {timeout} seconds",
                            "exit_code": -1,
                            "stdout": stdout if stdout else "",
                            "stderr": stderr if stderr else "",
                            "command": " ".join(cmd)
                        }
                except FileNotFoundError:
                    logger.info(f"Command not found: {cmd[0]}, trying next command...")
                    continue
                except Exception as e:
                    logger.error(f"Error running command {' '.join(cmd)}: {str(e)}")
                    continue
            
            return {"success": False, "error": "No E2E test command found", "exit_code": 127}
        except Exception as e:
            return {"success": False, "error": str(e), "exit_code": 1}
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "test_file": {"type": "string", "description": "Specific test file to run"},
                "frontend_path": {"type": "string", "description": "Frontend project path"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 1800}
            },
            "required": ["workspace_path"]
        }


class CaseExecutionTool(MCPTool):
    """Execute multiple test files and aggregate results."""
    
    def __init__(self):
        super().__init__(
            name="case_execution",
            description="Execute test files and return aggregated results",
            tool_type="high"
        )
    
    async def execute(
        self,
        workspace_path: str,
        test_cases: List[Dict[str, Any]],
        frontend_path: str = None,
        timeout: int = 1800,
        run_full_suite: bool = True  # New parameter: whether to run full test suite after new tests
    ) -> Dict[str, Any]:
        """Execute test files from test cases.
        
        Execution strategy:
        1. First, run only the newly generated test cases
        2. If successful and run_full_suite=True, run all E2E tests
        
        Args:
            workspace_path: Workspace root path
            test_cases: List of newly generated test cases
            frontend_path: Frontend project path
            timeout: Timeout per test execution
            run_full_suite: Whether to run full test suite after new tests pass
        
        Returns:
            Dict with test results including both new and full suite results
        """
        import logging
        logger = logging.getLogger(__name__)
        
        runner = E2ECaseRunnerTool()
        
        # Get test files from developed cases (only "new" type, exclude "modified")
        # Filter out modified page-objects/helpers - only run actual test files
        test_files = [
            case.get("file_path") 
            for case in test_cases 
            if case.get("file_path") and case.get("type") == "new"
        ]
        
        logger.info(f"Filtered test files: {len(test_files)} test files (excluded modified helpers/page-objects)")
        logger.debug(f"Test files to execute: {test_files}")
        
        if not test_files:
            return {
                "success": False,
                "error": "No test files found to execute",
                "passed": False,
                "total_tests": 0,
                "results": []
            }
        
        # Stage 1: Run only new test cases
        print(f"\n{'='*60}")
        print("Stage 1: Running newly generated test cases")
        print(f"{'='*60}")
        print(f"Test files: {len(test_files)}")
        
        new_test_results = []
        new_tests_passed = True
        
        for test_file in test_files:
            print(f"  Running: {test_file}")
            result = await runner.execute(
                workspace_path=workspace_path,
                test_file=test_file,
                frontend_path=frontend_path,
                timeout=timeout
            )
            
            # Print detailed results for each test
            if not result.get("success"):
                print(f"\n  ❌ TEST FAILED: {test_file}")
                print(f"     Exit code: {result.get('exit_code')}")
                print(f"     Command: {result.get('command', 'N/A')}")
                if result.get('stderr'):
                    print(f"\n  STDERR (first 1000 chars):")
                    print(f"  {result.get('stderr')[:1000]}")
                if result.get('stdout'):
                    print(f"\n  STDOUT (first 1000 chars):")
                    print(f"  {result.get('stdout')[:1000]}")
            else:
                print(f"  ✅ PASSED: {test_file}")
            
            new_test_results.append({
                "file": test_file,
                "success": result.get("success", False),
                "exit_code": result.get("exit_code"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "command": result.get("command", ""),
                "stage": "new_tests"
            })
            
            if not result.get("success"):
                new_tests_passed = False
                # Stop immediately on first test failure
                logger.warning(f"Test failed: {test_file}, stopping execution of remaining tests")
                print(f"\n  ⚠ Stopping execution - first test failure detected")
                break
        
        print(f"\nStage 1 Result: {'✓ PASSED' if new_tests_passed else '✗ FAILED'}")
        
        # If new tests failed, return immediately
        if not new_tests_passed:
            return {
                "success": True,
                "passed": False,
                "total_tests": len(test_files),
                "new_tests_passed": False,
                "full_suite_passed": None,
                "results": new_test_results,
                "stage_completed": "new_tests_only"
            }
        
        # Stage 2: Run full test suite (if enabled and new tests passed)
        full_suite_results = []
        full_suite_passed = None
        
        if run_full_suite:
            print(f"\n{'='*60}")
            print("Stage 2: Running full E2E test suite")
            print(f"{'='*60}")
            
            # Run all E2E tests (without specifying test_file)
            full_result = await runner.execute(
                workspace_path=workspace_path,
                test_file=None,  # Run all tests
                frontend_path=frontend_path,
                timeout=timeout * 2  # Longer timeout for full suite
            )
            
            full_suite_passed = full_result.get("success", False)
            full_suite_results.append({
                "type": "full_suite",
                "success": full_suite_passed,
                "exit_code": full_result.get("exit_code"),
                "stdout": full_result.get("stdout", ""),
                "stderr": full_result.get("stderr", ""),
                "command": full_result.get("command", ""),
                "stage": "full_suite"
            })
            
            # Print detailed results for full suite
            if not full_suite_passed:
                print(f"\n  ❌ FULL SUITE FAILED")
                print(f"     Exit code: {full_result.get('exit_code')}")
                print(f"     Command: {full_result.get('command', 'N/A')}")
                if full_result.get('stderr'):
                    print(f"\n  STDERR (first 2000 chars):")
                    print(f"  {full_result.get('stderr')[:2000]}")
                if full_result.get('stdout'):
                    print(f"\n  STDOUT (last 2000 chars):")
                    stdout_text = full_result.get('stdout', '')
                    print(f"  {stdout_text[-2000:] if len(stdout_text) > 2000 else stdout_text}")
            
            print(f"\nStage 2 Result: {'✓ PASSED' if full_suite_passed else '✗ FAILED'}")
        
        # Aggregate results
        all_results = new_test_results + full_suite_results
        overall_passed = new_tests_passed and (full_suite_passed if run_full_suite else True)
        
        return {
            "success": True,
            "passed": overall_passed,
            "total_tests": len(test_files),
            "new_tests_passed": new_tests_passed,
            "full_suite_passed": full_suite_passed,
            "results": all_results,
            "stage_completed": "both" if run_full_suite else "new_tests_only"
        }
    
    def _get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Workspace path"},
                "test_cases": {
                    "type": "array",
                    "description": "List of test case objects with file_path",
                    "items": {"type": "object"}
                },
                "frontend_path": {"type": "string", "description": "Frontend project path"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 1800},
                "run_full_suite": {
                    "type": "boolean",
                    "description": "Whether to run full test suite after new tests pass",
                    "default": True
                }
            },
            "required": ["workspace_path", "test_cases"]
        }

