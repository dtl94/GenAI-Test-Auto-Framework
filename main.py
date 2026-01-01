import os
import glob
import yaml
from dotenv import load_dotenv
from src.llm_client import LLMClient
from src.excel_handler import ExcelHandler
from src.testcase_generator import TestGenerator
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
        self.test_generator = TestGenerator(self.config, self.llm_client, self.excel_handler)
        self.web_runner = WebTestRunner(self.config['paths']['generated_web_tests_dir'])
        self.api_runner = APITestRunner(self.config['paths']['generated_api_tests_dir'])
        
        # Create directories
        os.makedirs(self.config['paths']['generated_web_tests_dir'], exist_ok=True)
        os.makedirs(self.config['paths']['generated_api_tests_dir'], exist_ok=True)
        os.makedirs('reports', exist_ok=True)
    
    def generate_from_requirements_folder(self, requirements_folder: str, model_type: str = "openai"):
        """Generate test cases for all .md requirement files in a folder."""
        requirements_files = glob.glob(os.path.join(requirements_folder, "*.md"))
        if not requirements_files:
            print(f"No .md files found in {requirements_folder}")
            return

        for rq_file in requirements_files:
            print(f"\nProcessing requirements: {rq_file}")
            # Pass the file path to TestGenerator (LLMClient expects a file path)
            excel_output = self.test_generator.generate_from_requirements(rq_file, model_type)
            print(f"Test cases saved to Excel: {excel_output}")

            # Generate executable tests
            self.generate_executable_tests()
    
    def generate_executable_tests(self):
        """Generate executable test files from Excel"""
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
    
    def run_web_tests(self, test_file: str = None):
        """Run web tests"""
        return self.web_runner.run_tests(test_file)
    
    def run_api_tests(self, test_file: str = None):
        """Run API tests"""
        return self.api_runner.run_tests(test_file)


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    framework = GenAITestFramework()
    
    # Folder containing all .md requirement files
    requirements_folder = "requirements"
    
    # Generate test cases and executable tests for all requirements
    framework.generate_from_requirements_folder(requirements_folder, model_type="openai")
    
    # Run the generated tests
    print("Running web tests...")
    framework.run_web_tests()
    
    print("Running API tests...")
    framework.run_api_tests()
