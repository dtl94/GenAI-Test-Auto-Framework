import subprocess
import sys
import os

class WebTestRunner:
    def __init__(self, tests_dir: str):
        self.tests_dir = tests_dir
    
    def run_tests(self, test_file: str = None) -> bool:
        """Run Playwright tests"""
        cmd = [sys.executable, "-m", "pytest"]
        
        if test_file:
            cmd.append(os.path.join(self.tests_dir, test_file))
        else:
            cmd.append(self.tests_dir)
        
        cmd.extend(["--html=reports/report.html", "--self-contained-html"])
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Tests passed!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Tests failed: {e}")
            return False