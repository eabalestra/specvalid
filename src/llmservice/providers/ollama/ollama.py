import os

from pydantic import ValidationError

try:
    from ollama import ChatResponse as OllamaChatResponse
    from ollama import Client
except ImportError as exc:
    msg = "Ollama library is not installed. Please install."
    raise ImportError(msg) from exc


class OllamaProvider:
    def __init__(self):
        self.url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def ollama_execute_prompt(self, model, prompt: str, format_instructions=""):
        try:
            # client = Client(host=self.url, timeout=kwargs.pop("timeout", None))
            client = Client(host=self.url, timeout=None)

            response: OllamaChatResponse = client.chat(
                model=str(model),
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            # if not response.done:
            #     if response.status_code == 503:  # model remains cold
            #         self.cold_models.append(model_id)
            #     elif response.status_code == 504:  # model timeout
            #         self.timeout_models.append(model_id)
            #     elif response.status_code == 429:  # Rate limit reached.
            #         print("ollama: Rate limit reached" + response.text)
            #         return "error=429"
            #     else:  # response.status_code == 403 or 400: # error model
            #         self.error_models.append(model_id)
            #     print(f"[ERROR] ollama: {model_id} not response.ok {response.text}")

            if not response["done"]:
                if response.get("error"):
                    print(f"[ERROR] ollama: {model} error: {response['error']}")
                    return None
            return response.message.content
        except ValidationError as err:
            print("[ERROR] ollama:ValidationError: ", err)
            return None
        except Exception as exc:
            print("[ERROR] ollama: general exception: ", exc)
            return None
