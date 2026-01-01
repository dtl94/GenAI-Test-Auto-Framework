import os
import json
import re
import pandas as pd
from typing import List, Dict, Any, Callable, Optional


class ExcelHandler:
    """
    Converts LLM-generated JSON test cases into Excel files
    with strong fault tolerance.

    Guarantees:
    - Never crashes on malformed/truncated JSON
    - Extracts only complete test objects
    - Supports retry-once JSON continuation
    """

    REQUIRED_TEST_FIELDS = ["test_id", "description", "steps", "expected_result"]
    REQUIRED_API_FIELDS = ["test_id", "method", "url", "expected_status"]

    def __init__(
        self,
        output_dir: str = "outputs",
        requirements_file: Optional[str] = None,
        json_continue_callback: Optional[Callable[[str], str]] = None,
    ):
        self.json_continue_callback = json_continue_callback

        base_name = "test_cases"
        if requirements_file:
            base_name = os.path.splitext(os.path.basename(requirements_file))[0]

        self.output_path = os.path.join(output_dir, f"{base_name}.xlsx")
        os.makedirs(output_dir, exist_ok=True)

        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    # ---------------------------------------------------------
    # JSON utilities
    # ---------------------------------------------------------
    def _strip_markdown(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 1)[1]
            text = text.rsplit("```", 1)[0]
        return text.strip()

    def _extract_complete_objects(self, array_text: str) -> List[dict]:
        """
        Extract only fully closed JSON objects from an array body.
        """
        objects = []
        depth = 0
        buffer = ""

        for ch in array_text:
            if ch == "{":
                depth += 1
            if depth > 0:
                buffer += ch
            if ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        objects.append(json.loads(buffer))
                    except json.JSONDecodeError:
                        pass  # skip invalid object
                    buffer = ""

        return objects

    def _extract_array(self, text: str, key: str) -> List[dict]:
        """
        Extract a single JSON array safely.
        """
        pattern = rf'"{key}"\s*:\s*\[(.*)'
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return []

        array_body = match.group(1)
        return self._extract_complete_objects(array_body)

    def _merge_json_outputs(self, original: str, continuation: str) -> str:
        return original.rstrip() + "\n" + continuation.lstrip()

    # ---------------------------------------------------------
    # Core parsing logic
    # ---------------------------------------------------------
    def _parse_with_retry(self, raw_json: str) -> Dict[str, List[Dict]]:
        """
        Parse JSON with one retry using continuation callback.
        """
        raw_json = self._strip_markdown(raw_json)

        for attempt in range(2):
            test_cases = self._extract_array(raw_json, "test_cases")
            api_tests = self._extract_array(raw_json, "api_tests")

            if test_cases or api_tests:
                return {
                    "test_cases": test_cases,
                    "api_tests": api_tests,
                }

            if attempt == 0 and self.json_continue_callback:
                try:
                    continuation = self.json_continue_callback(raw_json)
                    raw_json = self._merge_json_outputs(raw_json, continuation)
                except Exception:
                    break

        return {"test_cases": [], "api_tests": []}

    # ---------------------------------------------------------
    # JSON → Excel
    # ---------------------------------------------------------
    def json_to_excel(self, llm_output: str) -> str:
        if not llm_output or not llm_output.strip():
            raise ValueError("LLM returned empty output")

        parsed = self._parse_with_retry(llm_output)

        test_cases = self._filter_valid(
            parsed["test_cases"], self.REQUIRED_TEST_FIELDS
        )
        api_tests = self._filter_valid(
            parsed["api_tests"], self.REQUIRED_API_FIELDS
        )

        if not test_cases and not api_tests:
            raise ValueError("No valid test cases found after recovery")

        with pd.ExcelWriter(self.output_path, engine="openpyxl") as writer:
            self._write_sheet(
                writer, "test_cases", test_cases, self.REQUIRED_TEST_FIELDS
            )
            self._write_sheet(
                writer, "api_tests", api_tests, self.REQUIRED_API_FIELDS
            )

        return self.output_path

    def _filter_valid(self, items: List[dict], required_fields: List[str]) -> List[dict]:
        valid = []
        for item in items:
            if all(field in item for field in required_fields):
                valid.append(item)
        return valid

    def _write_sheet(
        self,
        writer: pd.ExcelWriter,
        name: str,
        rows: List[dict],
        columns: List[str],
    ):
        if rows:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=name)
        else:
            pd.DataFrame([], columns=columns).to_excel(
                writer, index=False, sheet_name=name
            )

    # ---------------------------------------------------------
    # Excel → dict
    # ---------------------------------------------------------
    def read_test_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        if not os.path.exists(self.output_path):
            raise FileNotFoundError(f"Excel not found: {self.output_path}")

        sheets = pd.read_excel(self.output_path, sheet_name=None)
        return {
            "test_cases": sheets.get("test_cases", pd.DataFrame())
            .fillna("")
            .to_dict("records"),
            "api_tests": sheets.get("api_tests", pd.DataFrame())
            .fillna("")
            .to_dict("records"),
            }
