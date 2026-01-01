
import pytest
import requests

def test_tcapi001():
        test_id = "TCAPI001"
        """GET all products successfully"""
        try:
            url = "https://automationexercise.com/api/productsList"
            method = "GET"
            payload = ""

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
                pytest.fail(f"Unsupported HTTP method: {method}")

            # Assert expected status code
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            # Assert API-level responseCode in JSON if exists
            try:
                data = response.json()
                if "responseCode" in data:
                    assert data["responseCode"] == 200, f"Expected responseCode 200, got {data['responseCode']}"
            except ValueError:
                # Response not JSON, skip
                data = None

            
            # Check for expected keys in JSON
            expected_keys = []
            for key in expected_keys:
                assert key in data, f"Key '{key}' not found in response JSON"

            print(f"API Test {test_id} passed")

        except Exception as e:
            pytest.fail(f"API Test {test_id} failed: {e}")
    