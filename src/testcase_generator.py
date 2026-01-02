import os
import json
import re
from typing import Dict, List, Any
from utils.page_object_manager import PageObjectManager
from src.step_maps.login_steps import LOGIN_STEPS
from src.step_maps.product_steps import PRODUCT_STEPS

ALL_STEPS = LOGIN_STEPS + PRODUCT_STEPS


class TestGenerator:

    def __init__(self, config, llm_client, excel_handler):
        self.config = config
        self.llm_client = llm_client
        self.excel_handler = excel_handler
        self.po = PageObjectManager()


    # ----------------------------------------------------------
    # GENERATE TEST CASES FROM REQUIREMENTS
    # ----------------------------------------------------------
    def generate_from_requirements(self, requirements, model_type):
        json_response = self.llm_client.generate_test_cases(
            requirements_path=requirements,
            model_type=model_type
        )
        return self.excel_handler.json_to_excel(json_response)
    
    # ----------------------------------------------------------
    def resolve_step(self, step_text: str, step_definitions: list = ALL_STEPS):

        if not isinstance(step_text, str):
            raise TypeError(f"Step must be string, got {type(step_text)}")

        step_text = step_text.strip()
        
        # Ignore garbage / JSON artifacts
        if step_text in ("[", "]", "{", "}", ",", ""):
            raise ValueError(f"Ignoring invalid step token: '{step_text}'")

        step_text = step_text.lower().strip()

        for step_def in step_definitions:

            # ----------------------------
            # FORMAT 1: (pattern, page, action, assertion)
            # ----------------------------
            if len(step_def) == 4:
                pattern, page, action, assertion = step_def
                match = re.search(pattern, step_text)
                if match:
                    return {
                        "page": page,
                        "action": action,
                        "assertion": assertion,
                        "args": list(match.groups()),
                        "raw_code": None,
                    }

            # ----------------------------
            # FORMAT 2: (pattern, raw_code)
            # ----------------------------
            elif len(step_def) == 2:
                pattern, raw_code = step_def
                match = re.search(pattern, step_text)
                if match:
                    return {
                        "page": None,
                        "action": None,
                        "assertion": None,
                        "args": [],
                        "raw_code": raw_code,
                    }

            # ----------------------------
            # FORMAT 3: (pattern, raw_code, assertion)
            # ----------------------------
            elif len(step_def) == 3:
                pattern, raw_code, assertion = step_def
                match = re.search(pattern, step_text)
                if match:
                    return {
                        "page": None,
                        "action": None,
                        "assertion": assertion,
                        "args": [],
                        "raw_code": raw_code,
                    }

            else:
                raise ValueError(
                    f"Invalid step definition format: {step_def}. "
                    "Expected (pattern, page, action, assertion) or (pattern, raw_code)"
                )

        raise ValueError(f"No step definition found for: '{step_text}'")




    # ----------------------------------------------------------
    # WEB TEST GENERATION USING PAGE OBJECTS
    # ----------------------------------------------------------
    def generate_playwright_test(self, test_case: dict) -> str:
        test_id = test_case["test_id"].lower()
        steps = test_case.get("steps", [])

        # Normalize steps (LLM safety)
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except Exception:
                raise ValueError(
                    f"Invalid steps format for test {test_case.get('test_id')}: {steps}"
                )

        if not isinstance(steps, list):
            raise ValueError(
                f"'steps' must be a list for test {test_case.get('test_id')}"
            )


        # Load config values
        base_url = self.config["project"]["base_url"]
        credentials = self.config.get("credentials", {})

        out = [
            "from playwright.sync_api import Page, expect",
            "from config.config_loader import get_config",  # helper
            "",
            f"def test_{test_id}(page: Page):",
            "    config = get_config()",
        ]

        page_objects_used = set()

        for step in steps:
            resolved = self.resolve_step(step)

            # Direct raw Playwright code
            if resolved.get("raw_code"):
                out.append(f"    {resolved['raw_code']}")
                if resolved.get("assertion"):
                    out.append(f"    {resolved['assertion']}")
                continue

            # Instantiate page object if needed
            if resolved.page:
                self.po.generate_page_object(resolved.page)
                class_name = resolved.page.title().replace("_", "") + "Page"
                var_name = resolved.page.lower()

                if resolved.page not in page_objects_used:
                    out.insert(
                        0,
                        f"from page_objects.{resolved.page}_page import {class_name}"
                    )
                    out.append(f"    {var_name} = {class_name}(page)")
                    page_objects_used.add(resolved.page)

            # Handle navigation
            if resolved.action == "open":
                out.append(f"    page.goto(config['project']['base_url'])")

            # Handle credential-based inputs
            elif resolved.action == "enter_username":
                out.append(
                    f"    {var_name}.enter_username(config['credentials']['username'])"
                )

            elif resolved.action == "enter_password":
                out.append(
                    f"    {var_name}.enter_password(config['credentials']['password'])"
                )

            # Generic actions
            elif resolved.action:
                args = ", ".join(f'"{a}"' for a in resolved.args)
                out.append(f"    {var_name}.{resolved.action}({args})")

            # Assertions
            if resolved.assertion:
                out.append(f"    {resolved.assertion}")

        return "\n".join(out)

    # ===================================================== 
    # PYTEST API TEST GENERATOR 
    # =====================================================
    def generate_pytest_api_test(self, test_case: dict) -> str:
        """
        Generate a pytest API test script from a structured test_case dict.

        Expected fields in test_case:
        - test_id
        - description
        - method
        - url
        - payload (optional)
        - expected_status
        - expected_response (optional)
        - expected_keys (optional, list of keys expected in JSON response)
        """
        test_id = test_case['test_id'].upper()
        test_description = test_case.get('description', '')
        
        # Default payload to empty dict if not provided
        payload = test_case.get("payload", {})
        expected_keys = test_case.get("expected_keys", [])
        # Serialize payload properly for embedding in the script
        payload_str = json.dumps(payload, indent=4)

        # Create the test code
        test_code = f"""
import pytest
import requests

def test_{test_case['test_id'].lower()}():
        test_id = "{test_id}"
        \"\"\"{test_description}\"\"\"
        try:
            url = "{test_case['url']}"
            method = "{test_case['method'].upper()}"
            payload = {payload_str}

            # Send request based on method
            if method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, json=payload)
            elif method == "PUT":
                response = requests.put(url, json=payload)
            elif method == "DELETE":
                response = requests.delete(url)
            else:
                pytest.fail(f"Unsupported HTTP method: {{method}}")

            # Assert expected status code
            assert response.status_code == {test_case['expected_status']}, f"Expected {test_case['expected_status']}, got {{response.status_code}}"

            # Assert API-level responseCode in JSON if exists
            try:
                data = response.json()
                if "responseCode" in data:
                    assert data["responseCode"] == {test_case['expected_response']}, f"Expected responseCode {test_case['expected_response']}, got {{data['responseCode']}}"
            except ValueError:
                # Response not JSON, skip
                data = None

            
            # Check for expected keys in JSON
            expected_keys = {expected_keys}
            for key in expected_keys:
                assert key in data, f"Key '{{key}}' not found in response JSON"

            print(f"API Test {{test_id}} passed")

        except Exception as e:
            pytest.fail(f"API Test {{test_id}} failed: {{e}}")
    """

        return test_code



    # =====================================================
    # HELPER FOR EXTRACTING METHODS
    # =====================================================
    def _extract_element_from_step(self, step: str) -> str:
        
        step_lower = step.lower()
        if "submit" in step_lower:
            return 'button:has-text("Submit")'
        if "button" in step_lower:
            return "button"
        if "email" in step_lower:
            return 'input[type="email"]'
        if "username" in step_lower:
            return 'input[type="username"]'
        if "password" in step_lower:
            return 'input[type="password"]'
        if "field" in step_lower or "input" in step_lower:
            return 'input[type="text"]'
        return "body"

    def _extract_type_info(self, step: str) -> tuple:
        """
        Extract input element + text from typing step.
        """
        if "email" in step.lower():
            return ('input[type="email"]', "test@example.com")
        if "password" in step.lower():
            return ('input[type="password"]', "Password123!")
        return ('input[type="text"]', "sample_text")

    def _extract_url_from_step(self, step: str) -> str:
        """Return a detected URL or fallback."""
        for token in step.split():
            if token.startswith("http"):
                return token
        return "https://example.com"

    def _extract_endpoint(self, step: str) -> str:
        """Detect API endpoint or return fallback."""
        if "/api/" in step:
            return step.split("/api/", 1)[1]
        return "/api/v1/default"

    def _extract_status_code(self, step: str) -> str:
        """Find status code in step."""
        for word in step.split():
            if word.isdigit() and len(word) == 3:
                return word
        return "200"