import logging
import os

import requests

try:
    from ollama import ChatResponse as OllamaChatResponse
    from ollama import Client, ResponseError
except ImportError as exc:
    msg = "Ollama library is not installed. Please install."
    raise ImportError(msg) from exc


class OllamaProvider:
    def __init__(self):
        self.url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ccad_token = os.environ.get("CCAD_API_KEY")
        self.with_ccad = os.getenv("WITH_CCAD", "false").lower() == "true"
        if self.with_ccad and not self.ccad_token:
            msg = "CCAD integration is enabled (WITH_CCAD=true) but CCAD_API_KEY environment variable is not set."
            raise RuntimeError(msg)

    def ollama_execute_prompt(self, model, prompt: str, format_instructions=""):
        try:
            response = None
            if self.with_ccad:
                response = self.chat_with_ccad_model(model, prompt)
            else:
                response = self.chat_with_ollama_model(model, prompt)

            if response is None:
                logging.warning(f"OllamaProvider: No response from model {model}")

            return response
        except Exception as exc:
            print("[ERROR] ollama: general exception: ", exc)
            return None

    def chat_with_ollama_model(self, model, prompt):
        client = Client(host=self.url, timeout=None)
        try:
            response: OllamaChatResponse = client.chat(
                model=str(model),
                messages=[{"role": "user", "content": prompt}],
            )
        except ResponseError as e:
            logging.error(
                f"[ERROR] ollama: {model} error: {e.error} (status={e.status_code})"
            )
            print(f"[ERROR] ollama: {model} error: {e}")
            return None
        return response.message.content

    def chat_with_ccad_model(self, model, prompt):
        url = "https://chat.ccad.unc.edu.ar/api/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.ccad_token}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"[ERROR] ccad: {model} error: {e}")
            print(f"[ERROR] ccad: {model} error: {e}")
            return None

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except ValueError as e:
            logging.error(f"[ERROR] ccad: {model} invalid JSON response: {e}")
            print(f"[ERROR] ccad: {model} invalid JSON response: {e}")
            return None
