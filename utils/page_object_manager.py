import json
from pathlib import Path
from typing import Dict

ACTION_MAP = {
    "input": "fill",
    "button": "click",
    "checkbox": "check",
    "link": "click",
    "text": "text_content"
}

class PageObjectManager:

    def __init__(self, selectors_dir="selectors", po_dir="page_objects"):
        self.selectors_dir = Path(selectors_dir)
        self.po_dir = Path(po_dir)
        self.po_dir.mkdir(exist_ok=True)

    def load_selectors(self, page_name: str) -> Dict:
        path = self.selectors_dir / f"{page_name}.json"
        return json.loads(path.read_text())

    def generate_page_object(self, page_name: str):
        selectors = self.load_selectors(page_name)
        class_name = page_name.title().replace("_", "") + "Page"

        lines = [
            "from playwright.sync_api import Page",
            "",
            f"class {class_name}:",
            "    def __init__(self, page: Page):",
            "        self.page = page",
            ""
        ]

        # Locators
        for name, selector in selectors.items():
            attr = name.replace(" ", "_")
            lines.append(f"        self._{attr} = '{selector}'")

        lines.append("")

        # Actions
        for name in selectors:
            attr = name.replace(" ", "_")

            if "input" in name or "field" in name:
                lines += [
                    f"    def enter_{attr}(self, value):",
                    f"        self.page.fill(self._{attr}, value)",
                    ""
                ]
            elif "button" in name or "login" in name:
                lines += [
                    f"    def click_{attr}(self):",
                    f"        self.page.click(self._{attr})",
                    ""
                ]
            elif "error" in name:
                lines += [
                    f"    def get_{attr}_text(self):",
                    f"        return self.page.locator(self._{attr}).text_content()",
                    ""
                ]

        file = self.po_dir / f"{page_name}_page.py"
        file.write_text("\n".join(lines))

        return str(file)