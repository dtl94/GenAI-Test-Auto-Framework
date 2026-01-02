import os
import json
from typing import Dict, Any
from openai import OpenAI
import ollama
import requests
import subprocess
import time
import socket


class LLMClient:
    """
    An LLM interface supporting:
    - OpenAI API
    - Ollama local models
    - DeepSeek API
    - Markdown requirement ingestion
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_client = None

        # --------------------------
        # Resolve environment variables inside config
        # --------------------------
        self._resolve_env_values()

        # --------------------------
        # Init OpenAI client
        # --------------------------
        openai_key = self.config["models"]["openai"].get("api_key")
        openai_base = self.config["models"]["openai"].get("base_url")

        if openai_key:
            self.openai_client = OpenAI(
                api_key=openai_key,
                base_url=openai_base,
            )

    # ==================================================
    # Expand ${ENV_VAR} into real environment values
    # ==================================================
    def _resolve_env_value(self, value: Any):
        """Replace ${VAR} with environment variable value."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var)
        return value

    def _resolve_env_values(self):
        """Recursively resolve values inside config dict."""
        def resolve(obj):
            if isinstance(obj, dict):
                return {k: resolve(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [resolve(v) for v in obj]
            else:
                return self._resolve_env_value(obj)

        self.config = resolve(self.config)

    # ==================================================
    # Load Markdown Requirements
    # ==================================================
    def load_requirements(self, req_path: str) -> str:
        if not os.path.exists(req_path):
            raise FileNotFoundError(f"MD file not found: {req_path}")
        with open(req_path, "r", encoding="utf-8") as f:
            return f.read()

    # ==================================================
    # Load Prompt Template
    # ==================================================
    def load_prompt_template(self, prompt_path: str) -> str:
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # ==================================================
    # OpenAI Generation
    # ==================================================
    def generate_with_openai(self, prompt: str, system_message: str = None) -> str:
        if not self.openai_client:
            raise ValueError("OpenAI client not configured")

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config["models"]["openai"]["model"],
                messages=messages,
                max_tokens=self.config["test_generation"]["max_tokens"],
                temperature=self.config["test_generation"]["temperature"],
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")

    # ==================================================
    # Ollama Local Generation
    # ==================================================
    def ollama_cfg(self):
        return self.config["models"]["ollama"]
    
    def start_ollama_server(self):
        cfg = self.ollama_cfg()

        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        start_time = time.time()
        while time.time() - start_time < cfg["startup_timeout"]:
            if self.is_ollama_running():
                return
            time.sleep(0.5)

        raise RuntimeError(
            f"Ollama server failed to start within {cfg['startup_timeout']}s"
        )

    
    def is_ollama_running(self) -> bool:
        cfg = self.ollama_cfg()
        try:
            with socket.create_connection(
                (cfg["host"], cfg["port"]), timeout=1
            ):
                return True
        except OSError:
            return False

    def is_ollama_installed(self) -> bool:
        try:
            subprocess.run(
                ["ollama", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except Exception:
            return False
        
    def ollama_healthcheck(self) -> bool:
        cfg = self.ollama_cfg()
        url = f"http://{cfg['host']}:{cfg['port']}{cfg['healthcheck_endpoint']}"

        try:
            r = requests.get(url, timeout=1)
            return r.status_code == 200
        except requests.RequestException:
            return False
    
    def ensure_model_exists(self, requested_model: str) -> str:
        """
        Ensure Ollama model exists.
        - Resolves tags automatically
        - Pulls only if missing
        - Blocks until model is available
        - Returns the resolved model name
        """

        try:
            models_info = ollama.list().get("models", [])
        except Exception as e:
            raise RuntimeError(
                "Ollama server is not responding. Ensure `ollama serve` is running."
            ) from e

        installed = []
        for m in models_info:
            name = m.get("model") or m.get("name")
            if name:
                installed.append(name)

        # Exact match
        if requested_model in installed:
            return requested_model

        # Tag resolution (llama3.1 → llama3.1:latest)
        tagged = [m for m in installed if m.startswith(requested_model + ":")]
        if tagged:
            resolved = tagged[0]
            print(f"[Ollama] Resolved '{requested_model}' → '{resolved}'")
            return resolved

        # Pull model if missing
        print(f"[Ollama] Model '{requested_model}' not found. Pulling...")
        try:
            ollama.pull(requested_model)
        except Exception as e:
            raise RuntimeError(
                f"Ollama model '{requested_model}' could not be pulled.\n"
                "Ensure Ollama is functional or switch to another model "
                "(openai, deepseek, gemini)."
            ) from e

        # Re-check after pull
        try:
            models_info = ollama.list().get("models", [])
        except Exception:
            raise RuntimeError("Ollama became unavailable after pull.")

        for m in models_info:
            name = m.get("model") or m.get("name")
            if name == requested_model or name.startswith(requested_model + ":"):
                print(f"[Ollama] Model '{name}' ready.")
                return name

        raise RuntimeError(
            f"Ollama pull completed but model '{requested_model}' still not visible."
        )

    def ensure_ollama_ready(self):
        """
        Make sure Ollama is installed, running, and healthy.
        """

        if not self.is_ollama_installed():
            raise RuntimeError(
                "Ollama is not installed.\n"
                "Install it first from https://ollama.com"
            )

        if not self.is_ollama_running():
            print("[Ollama] Server not running. Starting...")
            self.start_ollama_server()

        timeout = self.ollama_cfg().get("startup_timeout", 15)
        start = time.time()

        while time.time() - start < timeout:
            if self.ollama_healthcheck():
                print("[Ollama] Server is healthy.")
                return
            time.sleep(0.5)

        raise RuntimeError(
            "Ollama server failed healthcheck.\n"
            "If this persists, switch to another model provider "
            "(openai, deepseek, gemini)."
        )

    def generate_with_ollama(self, prompt: str, system_message: str = None) -> str:
        """
        Fully reliable Ollama generation:
        - Ensures installation
        - Ensures server is healthy
        - Resolves & pulls model if needed
        - Fails once, clearly, if Ollama is broken
        """

        full_prompt = f"{system_message}\n\n{prompt}" if system_message else prompt
        cfg = self.ollama_cfg()
        requested_model = cfg["model"]

        try:
            # Environment check
            self.ensure_ollama_ready()

            # Model check
            resolved_model = self.ensure_model_exists(requested_model)
            self.config["models"]["ollama"]["model"] = resolved_model

            # Generation
            response = ollama.generate(
                model=resolved_model,
                prompt=full_prompt,
                options={
                    "temperature": self.config["test_generation"]["temperature"],
                    "num_predict": self.config["test_generation"]["max_tokens"],
                },
            )
            return response["response"]

        except Exception as e:
            raise RuntimeError(
                "Ollama is not functional.\n"
                "You may switch to another AI provider: "
                "openai, deepseek, or gemini.\n\n"
                f"Root cause: {e}"
            ) from e


    # ==================================================
    # DeepSeek API Generation
    # ==================================================
    def generate_with_deepseek(self, prompt: str, system_message: str = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.config['models']['deepseek']['api_key']}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config["models"]["deepseek"]["model"],
            "messages": messages,
            "max_tokens": self.config["test_generation"]["max_tokens"],
            "temperature": self.config["test_generation"]["temperature"],
        }

        try:
            response = requests.post(
                f"{self.config['models']['deepseek']['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"DeepSeek generation failed: {e}")

    # ==================================================
    # Gemini API Generation
    # ==================================================
    def generate_with_gemini(self, prompt: str, system_message: str = None) -> str:
        cfg = self.config["models"]["gemini"]

        if not cfg.get("api_key"):
            raise RuntimeError("Gemini API key is missing")

        url = (
            f"{cfg['base_url']}/v1beta/models/"
            f"{cfg['model']}:generateContent"
            f"?key={cfg['api_key']}"
        )

        # Gemini uses "contents", not "messages"
        contents = []

        if system_message:
            contents.append({
                "role": "user",
                "parts": [{"text": system_message}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config["test_generation"]["temperature"],
                "maxOutputTokens": self.config["test_generation"]["max_tokens"],
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 401:
                raise RuntimeError("Gemini API key is invalid or unauthorized")

            if response.status_code == 404:
                raise RuntimeError(
                    f"Gemini model '{cfg['model']}' not found or endpoint invalid"
                )

            if response.status_code == 429:
                raise RuntimeError("Gemini quota exceeded or rate-limited")

            response.raise_for_status()

            data = response.json()

            return data["candidates"][0]["content"]["parts"][0]["text"]

        except requests.RequestException as e:
            raise RuntimeError(
                f"Gemini generation failed: Network or request error: {e}"
            ) from e

    
    # ==================================================
    # Main Test Case Generation
    # ==================================================
    def generate_test_cases(
        self,
        requirements_path: str,
        prompt_template_path: str = "prompts/generate_test_cases.txt",
        model_type: str | None = None,
    ) -> str:
        """Generate test cases from a requirements file."""

        # Load requirements from file
        requirements = self.load_requirements(requirements_path)

        # Load prompt template
        template = self.load_prompt_template(prompt_template_path)

        # Inject requirements into prompt
        system_message = template.replace("{{requirements}}", requirements)

        #if model_type == "openai":
            #return self.generate_with_openai(system_message)
        #elif model_type == "ollama":
            #return self.generate_with_ollama(system_message)
        #elif model_type == "deepseek":
            #return self.generate_with_deepseek(system_message)
        #elif model_type == "gemini":
            #return self.generate_with_gemini(system_message)
        return self.generate_with_fallback(
            prompt=system_message,
            preferred_provider=model_type,
        )
        
    # ==================================================
    # GENERATE WITH FALLBACK BETWEEN LLM CLIENTS
    # ==================================================

    def generate_with_fallback(
        self,
        prompt: str,
        system_message: str | None = None,
        preferred_provider: str | None = None,
    ) -> str:
        """
        Generate text using any available LLM with automatic fallback.

        Resolution order:
        1. preferred_provider (if provided)
        2. config.models.preferred (if set)
        3. openai → gemini → ollama → deepseek
        """

        providers = self._resolve_provider_order(preferred_provider)
        errors: dict[str, str] = {}

        for provider in providers:
            try:
                print(f"[LLM] Trying provider: {provider}")

                if provider == "openai":
                    return self.generate_with_openai(prompt, system_message)

                elif provider == "gemini":
                    return self.generate_with_gemini(prompt, system_message)

                elif provider == "ollama":
                    return self.generate_with_ollama(prompt, system_message)

                elif provider == "deepseek":
                    return self.generate_with_deepseek(prompt, system_message)

                else:
                    print(f"[LLM] Unknown provider skipped: {provider}")

            except Exception as e:
                errors[provider] = str(e)
                print(f"[LLM][{provider}] Failed → {e}")

        # All providers failed → single controlled failure
        error_report = "\n".join(
            f"- {provider}: {error}"
            for provider, error in errors.items()
        )

        raise RuntimeError(
            "All LLM providers failed.\n\n"
            "Tried providers:\n"
            f"{error_report}\n\n"
            "Actions:\n"
            "- Verify API keys\n"
            "- Check Ollama installation / model availability if enabled\n"
            "- Switch provider in config.yaml"
        )


    def _resolve_provider_order(self, preferred_provider: str | None) -> list[str]:
        """
        Resolve provider fallback order.
        """

        enabled = []

        models_cfg = self.config.get("models", {})

        def is_enabled(name: str) -> bool:
            cfg = models_cfg.get(name, {})
            return cfg.get("enabled", True)

        # Explicit preferred provider
        if preferred_provider and is_enabled(preferred_provider):
            enabled.append(preferred_provider)

        # Config preferred provider
        cfg_preferred = models_cfg.get("preferred")
        if cfg_preferred and cfg_preferred != "auto" and is_enabled(cfg_preferred):
            if cfg_preferred not in enabled:
                enabled.append(cfg_preferred)

        # Default fallback order
        for p in ("ollama", "gemini", "openai", "deepseek"):
            if is_enabled(p) and p not in enabled:
                enabled.append(p)

        return enabled
