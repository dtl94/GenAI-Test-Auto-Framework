import json
import shutil
import re
from typing import Dict
from pathlib import Path
from playwright.sync_api import sync_playwright
from src.llm_client import LLMClient


class SelectorGenerator:

    def __init__(self, llm: LLMClient):
        self.llm = llm

    # ----------------------------------------------------------
    # Fetch HTML using Playwright
    # ----------------------------------------------------------
    def fetch_html(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            html = page.content()
            browser.close()
        return html

    # ----------------------------------------------------------
    # Read prompt template
    # ----------------------------------------------------------
    def read_prompt(self, prompt_file: str) -> str:
        return Path(prompt_file).read_text()

    # ----------------------------------------------------------
    # Read element list
    # ----------------------------------------------------------
    def read_element_list(self, json_file: str):
        data = json.loads(Path(json_file).read_text())
        return data.get("elements", [])

    # ----------------------------------------------------------
    # Extract JSON block from LLM output
    # ----------------------------------------------------------
    def extract_json_block(self, text: str) -> str:
        """
        Extract the first valid JSON object or array from LLM output.
        """
        if not text or not text.strip():
            raise ValueError("LLM returned empty output")

        # Remove markdown code fences
        text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()

        # Try full parse first
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Extract JSON object or array
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON block found in LLM output")

        return match.group(1)
    # ----------------------------------------------------------
    # Generate selectors
    # ----------------------------------------------------------
    def generate_selectors(
        self,
        page_name: str,
        base_url: str,
        elements_file: str,
        prompt_file: str,
        output_dir: str
    ) -> Dict:

        html = self.fetch_html(base_url)
        prompt = self.read_prompt(prompt_file)
        elements = self.read_element_list(elements_file)

        final_prompt = (
            prompt +
            f"\nElements:\n{json.dumps(elements, indent=2)}\n\n"
            f"HTML:\n```html\n{html}\n```"
        )

        raw_output = self.llm.generate_with_fallback(final_prompt)
        try:
            json_text = self.extract_json_block(raw_output)
            selectors = json.loads(json_text)
        except Exception as e:
            raise ValueError(
                "Failed to parse selectors JSON from LLM output.\n\n"
                f"Raw output:\n{raw_output}"
            ) from e

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        output_path = output_dir_path / f"{page_name}.json"
        # If there is already a **directory** with the same name as the file, remove it
        if output_path.exists() and output_path.is_dir():
            shutil.rmtree(output_path)
        output_path.write_text(json.dumps(selectors, indent=2))

        return selectors

