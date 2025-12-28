"""Framework detection tools for MCP layer."""
from typing import Dict, Any, Optional, List
import os
import json
import fnmatch
from langchain_core.tools import tool


@tool
def check_package_json_for_framework(
    package_json_path: str,
    search_path: str
) -> Dict[str, Any]:
    """Check package.json for test framework dependencies.
    
    Args:
        package_json_path: Full path to package.json file
        search_path: Directory path where package.json is located
    
    Returns:
        Dict with framework info: framework, version, config_file, confidence, evidence
        Returns None if no framework found
    """
    try:
        with open(package_json_path, "r") as f:
            package_data = json.load(f)
        
        dependencies = {
            **package_data.get("dependencies", {}),
            **package_data.get("devDependencies", {})
        }
        
        result = {
            "framework": None,
            "version": None,
            "config_file": None,
            "confidence": "low",
            "evidence": []
        }
        
        # Check for Playwright
        if "@playwright/test" in dependencies or "playwright" in dependencies:
            result["framework"] = "playwright"
            result["version"] = dependencies.get("@playwright/test") or dependencies.get("playwright")
            result["confidence"] = "high"
            result["evidence"].append("Found in package.json dependencies")
            
            # Check for playwright config
            config_files = ["playwright.config.js", "playwright.config.ts", "playwright.config.mjs"]
            for config_file in config_files:
                config_path = os.path.join(search_path, config_file)
                if os.path.exists(config_path):
                    result["config_file"] = config_file
                    result["evidence"].append(f"Found config: {config_file}")
                    break
        
        # Check for Cypress
        elif "cypress" in dependencies:
            result["framework"] = "cypress"
            result["version"] = dependencies.get("cypress")
            result["confidence"] = "high"
            result["evidence"].append("Found in package.json dependencies")
            
            # Check for cypress config
            config_files = ["cypress.config.js", "cypress.config.ts", "cypress.json"]
            for config_file in config_files:
                config_path = os.path.join(search_path, config_file)
                if os.path.exists(config_path):
                    result["config_file"] = config_file
                    result["evidence"].append(f"Found config: {config_file}")
                    break
        
        # Check for Selenium/WebdriverIO
        elif "@wdio/cli" in dependencies or "selenium-webdriver" in dependencies:
            if "@wdio/cli" in dependencies:
                result["framework"] = "webdriverio"
                result["version"] = dependencies.get("@wdio/cli")
            else:
                result["framework"] = "selenium"
                result["version"] = dependencies.get("selenium-webdriver")
            result["confidence"] = "medium"
            result["evidence"].append("Found in package.json dependencies")
        
        # Check for Jest with E2E capabilities
        elif "jest" in dependencies:
            result["framework"] = "jest"
            result["version"] = dependencies.get("jest")
            result["confidence"] = "low"
            result["evidence"].append("Found Jest, but may not be for E2E")
        
        return result if result["framework"] else None
            
    except (json.JSONDecodeError, IOError) as e:
        return {"error": str(e), "evidence": [f"Error reading package.json: {str(e)}"]}


def _find_test_files_impl(workspace_path: str, patterns: list) -> list:
    """Internal implementation for finding test files (used by other tools)."""
    found_files = []
    
    for root, dirs, files in os.walk(workspace_path):
        # Skip node_modules and other common ignore dirs
        if "node_modules" in root or ".git" in root:
            continue
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_path)
            
            for pattern in patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(file, pattern):
                    found_files.append(file_path)
                    break
        
        if found_files:
            break
    
    return found_files


@tool
def find_test_files_by_pattern(
    workspace_path: str,
    patterns: List[str]
) -> List[str]:
    """Find test files matching patterns.
    
    Args:
        workspace_path: Root directory to search in
        patterns: List of file patterns (e.g., ["*.spec.ts", "*.test.js"])
    
    Returns:
        List of full paths to matching test files
    """
    return _find_test_files_impl(workspace_path, patterns)


@tool
def check_test_files_for_framework(
    search_path: str,
    workspace_path: str
) -> Optional[Dict[str, Any]]:
    """Check for test files to infer framework.
    
    Args:
        search_path: Directory to search in
        workspace_path: Root workspace path
    
    Returns:
        Dict with framework info: framework, confidence, test_dir, evidence
        Returns None if no framework found
    """
    test_patterns = {
        "playwright": ["*.spec.ts", "*.spec.js", "*.test.ts", "*.test.js"],
        "cypress": ["cypress/e2e/**/*.cy.{js,ts}", "cypress/integration/**/*.spec.{js,ts}"],
        "selenium": ["**/*selenium*.{js,ts}", "**/*e2e*.{js,ts}"]
    }
    
    for framework, patterns in test_patterns.items():
        # Call the function directly (not as a tool)
        found_files = _find_test_files_impl(search_path, patterns)
        if found_files:
            return {
                "framework": framework,
                "confidence": "medium",
                "test_dir": os.path.dirname(found_files[0]),
                "evidence": [f"Found test files matching {framework} patterns"]
            }
    
    return None


def _find_test_files_impl(workspace_path: str, patterns: list) -> list:
    """Internal implementation for finding test files (used by other tools)."""
    found_files = []
    
    for root, dirs, files in os.walk(workspace_path):
        # Skip node_modules and other common ignore dirs
        if "node_modules" in root or ".git" in root:
            continue
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace_path)
            
            for pattern in patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(file, pattern):
                    found_files.append(file_path)
                    break
        
        if found_files:
            break
    
    return found_files

