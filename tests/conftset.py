import os
import yaml
import pytest
from playwright.sync_api import sync_playwright, Page
from page_objects.login_page import LoginPage

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/config.yaml")
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)

@pytest.fixture(scope="session")
def base_url():
    return CONFIG["project"]["base_url"]

@pytest.fixture(scope="session")
def credentials():
    return CONFIG["credentials"]

@pytest.fixture(scope="session")
def login_selectors():
    selectors_path = CONFIG["selectors"]["login"]
    full_path = os.path.join(os.path.dirname(__file__), "../", selectors_path)
    import json
    with open(full_path, "r") as f:
        return json.load(f)

@pytest.fixture(scope="function")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        yield page
        browser.close()

@pytest.fixture(scope="function")
def login_page(page: Page, base_url, login_selectors):
    lp = LoginPage(page, base_url, login_selectors)
    return lp

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    outcome = yield
    rep = outcome.get_result()

    if rep.failed:
        page = item.funcargs.get("page")
        if page:
            page.screenshot(path=f"reports/{item.name}.png")



