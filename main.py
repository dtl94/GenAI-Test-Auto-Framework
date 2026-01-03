import os
import glob
import yaml
from dotenv import load_dotenv
from src.llm_client import LLMClient
from src.excel_handler import ExcelHandler
from src.testcase_generator import TestGenerator
from utils.selectors_generator import SelectorGenerator
from utils.page_object_manager import PageObjectManager

from test_runners.web_runner import WebTestRunner
from test_runners.api_runner import APITestRunner


class GenAITestFramework:
    def __init__(self, config_path: str = "config/config.yaml"):
        load_dotenv()

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # ---------------------------------
        # Core components for the framework
        # ---------------------------------
        self.llm_client = LLMClient(self.config)
        self.excel_handler = ExcelHandler(self.config["paths"]["excel_output"])
        self.test_generator = TestGenerator(
            self.config, self.llm_client, self.excel_handler
        )
        self.selectors_generator = SelectorGenerator(self.llm_client)
        self.page_object_generator = PageObjectManager(
            selectors_dir=self.config['paths']['selectors_dir'],
            po_dir=self.config['paths']['page_objects_dir']
        )

        self.web_runner = WebTestRunner(
            self.config["paths"]["generated_web_tests_dir"]
        )
        self.api_runner = APITestRunner(
            self.config["paths"]["generated_api_tests_dir"]
        )

        # ---------------------------------
        # Ensure required directories exist
        # ---------------------------------
        for path in [
            self.config["paths"]["generated_web_tests_dir"],
            self.config["paths"]["generated_api_tests_dir"],
            self.config["paths"]["selectors_dir"],
            self.config["paths"]["page_objects_dir"],
            "reports",
        ]:
            os.makedirs(path, exist_ok=True)

    # ============================================================
    # REQUIREMENTS → EXCEL
    # ============================================================
    def generate_from_requirements_folder(
        self, requirements_folder: str, model: str = None
    ):
        """Generate test cases from all requirement .md files under requirements folder"""
        files = glob.glob(os.path.join(requirements_folder, "*.md"))
        if not files:
            print(f"No requirement files found in {requirements_folder}")
            return

        for rq_file in files:
            print(f"\n Processing requirements: {rq_file}")
            excel_path = self.test_generator.generate_from_requirements(
                rq_file, model
            )
            print(f"Test cases saved to Excel: {excel_path}")

    # ============================================================
    # GENERATE SELECTORS & PAGE OBJECTS
    # ============================================================
    def generate_ui_artifacts(self):
        """
        Generate selectors and page objects based on generated test cases.
        This follows the same flow as demo.py and does NOT fetch DOM separately.
        """

        # Read generated test cases from Excel
        data = self.excel_handler.read_test_cases()
        if not data or "test_cases" not in data:
            print("No web test cases found to generate UI artifacts.")
            return

        processed_pages = set()
        configured_pages = set(self.config.get("pages", {}).keys())

        for test_case in data.get("test_cases", []):
            page_name = test_case.get("page")

            if not page_name:
                print(f"Test case {test_case.get('test_id')} has no page defined → skipped")
                continue
            if page_name not in configured_pages:
                print(f"Page '{page_name}' not found in config.yaml → skipped")
                continue

            # Avoid regenerating artifacts
            if page_name in processed_pages:
                continue

            base_url = self.config["pages"].get(page_name, {}).get("url", "")
            if not base_url:
                print(f"No URL configured for page: {page_name}")
                continue

            # Page-specific elements definition from requirements
            elements_file = os.path.join(
                self.config["paths"]["requirements_dir"],
                f"{page_name}_elements.json"
            )

            print(f"\nGenerating selectors for page: {page_name}")

            self.selectors_generator.generate_selectors(
                page_name=page_name,
                base_url=base_url,
                elements_file=elements_file if os.path.exists(elements_file) else None,
                prompt_file=self.config["selectors"]["prompt"],
                output_dir=self.config["paths"]["selectors_dir"]
            )

            print(f"Generating page objects for page: {page_name}")
            self.page_object_generator.generate_page_object(page_name)

            processed_pages.add(page_name)


    # ============================================================
    # EXCEL → EXECUTABLE TEST FILES
    # ============================================================
    def generate_executable_tests(self):
        """Generate Playwright and API test scripts"""
        data = self.excel_handler.read_test_cases()

        # -------------------------
        # WEB TESTS
        # -------------------------
        for test_case in data.get("test_cases", []):
            test_id = test_case["test_id"].lower()
            code = self.test_generator.generate_playwright_test(test_case)

            path = os.path.join(
                self.config["paths"]["generated_web_tests_dir"],
                f"test_{test_id}.py",
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)

            print(f"Generated WEB test: {path}")

        # -------------------------
        # API TESTS
        # -------------------------
        for test_case in data.get("api_tests", []):
            test_id = test_case["test_id"].lower()
            code = self.test_generator.generate_pytest_api_test(test_case)

            path = os.path.join(
                self.config["paths"]["generated_api_tests_dir"],
                f"test_{test_id}.py",
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)

            print(f"Generated API test: {path}")

    # ============================================================
    # TESTS EXECUTION
    # ============================================================
    def run_web_tests(self, test_file: str = None):
        print("\nRunning WEB tests...")
        return self.web_runner.run_tests(test_file)

    def run_api_tests(self, test_file: str = None):
        print("\nRunning API tests...")
        return self.api_runner.run_tests(test_file)

    # ============================================================
    # FULL PIPELINE EXECUTION
    # ============================================================
    def run_full_pipeline(self, requirements_folder: str, model: str | None = None):
        """
        Execute the complete GenAI testing pipeline
        """
        print("\nStarting full GenAI test pipeline")

        self.generate_from_requirements_folder(
            requirements_folder=requirements_folder,
            model=model,
        )

        self.generate_ui_artifacts()

        self.generate_executable_tests()

        self.run_web_tests()
        self.run_api_tests()

        print("\nPipeline execution completed")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    framework = GenAITestFramework()

    requirements_folder = "requirements"

    framework.run_full_pipeline(
        requirements_folder=requirements_folder,
        model="openai"
    )
