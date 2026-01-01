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
        
        with open(config_path, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
        
        # Initialize components
        self.llm_client = LLMClient(self.config)
        self.excel_handler = ExcelHandler(self.config['paths']['excel_output'])
        self.test_generator = TestGenerator(self.config,self.llm_client, self.excel_handler)
        self.web_runner = WebTestRunner(self.config['paths']['generated_web_tests_dir'])
        self.api_runner = APITestRunner(self.config['paths']['generated_api_tests_dir'])
        self.selector_generator = SelectorGenerator(self.llm_client)
        self.po_manager = PageObjectManager(
            selectors_dir=self.config['paths']['selectors_dir'],
            po_dir=self.config['paths']['page_objects_dir']
        )

        # Create directories
        for path in [
            self.config['paths']['generated_web_tests_dir'],
            self.config['paths']['generated_api_tests_dir'],
            self.config['paths']['selectors_dir'],
            self.config['paths']['page_objects_dir'],
            'reports'
        ]:
            os.makedirs(path, exist_ok=True)
    
    # -----------------------------------
    # Generate all test cases from requirements folder
    # -----------------------------------
    def generate_from_requirements_folder(self, requirements_folder: str, model_type: str = "openai"):
        requirements_files = glob.glob(os.path.join(requirements_folder, "*.md"))
        if not requirements_files:
            print(f"No .md files found in {requirements_folder}")
            return

        for rq_file in requirements_files:
            print(f"\nProcessing requirement: {rq_file}")

            # Parse requirements and generate Excel test cases
            excel_output = self.test_generator.generate_from_requirements(rq_file, model_type)
            print(f"Test cases saved to Excel: {excel_output}")

            # Generate selectors and page objects for all pages in this requirements
            data = self.excel_handler.read_test_cases()

            # For each web test case, generate selectors and page objects dynamically
            for test_case in data.get("test_cases", []):
                page_name = test_case.get("page", "login")  # default page

                # Build elements JSON for this page if provided in requirements
                elements_file = os.path.join(requirements_folder, f"{page_name}_elements.json")
                if os.path.exists(elements_file):
                    self.selector_generator.generate_selectors(
                        page_name=page_name,
                        base_url=self.config["pages"].get(page_name, {}).get("url", ""),
                        elements_file=elements_file,
                        prompt_file=self.config["selectors"]["prompt"],
                        output_dir=self.config['paths']['selectors_dir']
                    )

                    # Generate the page object using the generated selectors
                    self.po_manager.generate_page_object(page_name)

            # Generate executable test scripts
            self.generate_executable_tests()
    
    # -----------------------------------
    # Generate executable test files
    # -----------------------------------
    def generate_executable_tests(self):
        data = self.excel_handler.read_test_cases()

        # -------------------------
        # WEB TESTS
        # -------------------------
        for test_case in data.get("test_cases", []):
            test_id = test_case["test_id"].lower()
            test_code = self.test_generator.generate_playwright_test(test_case)
            file_path = os.path.join(
                self.config["paths"]["generated_web_tests_dir"],
                f"test_{test_id}.py"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            print(f"Generated WEB test: {file_path}")

        # -------------------------
        # API TESTS
        # -------------------------
        for test_case in data.get("api_tests", []):
            test_id = test_case["test_id"].lower()
            test_code = self.test_generator.generate_pytest_api_test(test_case)
            file_path = os.path.join(
                self.config["paths"]["generated_api_tests_dir"],
                f"test_{test_id}.py"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            print(f"Generated API test: {file_path}")
    
    # -----------------------------------
    # Run web tests
    # -----------------------------------
    def run_web_tests(self, test_file: str = None):
        return self.web_runner.run_tests(test_file)
    
    # -----------------------------------
    # Run API tests
    # -----------------------------------
    def run_api_tests(self, test_file: str = None):
        return self.api_runner.run_tests(test_file)


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    framework = GenAITestFramework()
    
    requirements_folder = "requirements"
    
    # Generate test cases and executable tests
    framework.generate_from_requirements_folder(requirements_folder, model_type="openai")
    
    # Run the generated tests
    print("Running web tests...")
    framework.run_web_tests()
    
    print("Running API tests...")
    framework.run_api_tests()
