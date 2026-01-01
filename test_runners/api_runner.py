import subprocess
import sys
import os

class APITestRunner:
    def __init__(self, tests_dir: str):
        self.tests_dir = tests_dir
    
    def run_tests(self, test_file: str = None) -> bool:
        """Run API tests"""
        cmd = [sys.executable, "-m", "pytest"]
        
        if test_file:
            cmd.append(os.path.join(self.tests_dir, test_file))
        else:
            cmd.append(self.tests_dir)
        
        cmd.extend(["-v", "--html=reports/api_report.html", "--self-contained-html"])
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("API Tests passed!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"API Tests failed: {e}")
            return False