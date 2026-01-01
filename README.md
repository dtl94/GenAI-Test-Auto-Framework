# GenAI Test Automation Framework

A GenAI-powered test automation framework that converts requirements into structured test cases, Excel artifacts, Playwright tests, selectors, and Page Objects using multiple AI providers with automatic fallback.

---

## Key Features

- **Multi-LLM Support**
  - OpenAI
  - Deepseek
  - Ollama (local)
  - Gemini
  - Automatic fallback between LLM models

- **Automation Outputs**
  - Excel test cases (`.xlsx`)
  - Selectors dynamic generation from HTML
  - Playwright tests (Python) for web automation
  - Page Object Model (POM)
  - PyTest tests for API

- **Fully Config-driven**
  - YAML configuration
  - Provider switching without code changes
---


## Running the Framework
```bash
python demo.py
```

**Outputs**

Excel test cases

Playwright tests

PyTest tests

Page Objects

Selectors under JSON files

Reports

**Dependencies**
```bash
pip install -r requirements.txt
```
