import logging
import os

from openai import OpenAI
import requests
from langchain.output_parsers import PydanticOutputParser
from pydantic import ValidationError
from transformers import pipeline
import torch
from huggingface_hub import InferenceClient

from ollama import ChatResponse, chat

from google import genai


class LLMService:
    TIMEOUT = 600  # in seconds

    # key : model
    supported_models = {
        "L_Gemma31": "gemma3:1b",
        # Locally deployed models
        "L_Phi4": "phi4",
        "L_Phi4_Q16": "phi4:14b-fp16",
        "L_Phi3": "phi3",
        "L_Llama370Instruct_Q4": "llama3:70b-instruct",
        "L_Llama38Instruct": "llama3:8b-instruct-fp16",
        "L_Llama3170Instruct": "llama3.1:70b-instruct-fp16",
        "L_Llama3170Instruct_Q4": "llama3.1:70b-instruct-q4_0",
        "L_Llama318Instruct": "llama3.1:8b-instruct-fp16",
        "L_Mistral7B03Instruct": "mistral:7b-instruct-v0.3-fp16",
        "L_Mistral7B02Instruct": "mistral:7b-instruct-v0.2-fp16",
        "L_Mixtral8x7B01Instruct_Q4": "mixtral:8x7b-instruct-v0.1-q4_0",
        "L_Mixtral8x22B01Instruct_Q4": "mixtral:8x22b-instruct",
        "L_DeepSeekR1Qwen7": "deepseek-r1:7b-qwen-distill-fp16",
        "L_DeepSeekR1Qwen32_Q4": "deepseek-r1:32b",
        "L_DeepSeekR1Llama8": "deepseek-r1:8b-llama-distill-fp16",
        "L_DeepSeekR1Llama70_Q4": "deepseek-r1:70b",
        # Locally deployed quantized models
        "L_Llama3370Instruct_Q4": "llama3.3:70b-instruct-q4_K_M",
        "L_Mistral7B03Instruct_Q4": "mistral:7b-instruct-q4_K_M",
        "L_Phi4_Q4": "phi4:14b-q4_K_M",
        "L_Phi4_Q8": "phi4:14b-q8_0",
        "L_MiniCPMo26_Q4": "ZimaBlueAI/MiniCPM-o-2_6",
        # Other models of interest
        "Phi4": "microsoft/phi-4",
        "Phi35MiniInstruct": "microsoft/Phi-3.5-mini-instruct",
        "Phi35MoEInstruct": "microsoft/Phi-3.5-MoE-instruct",
        "Phi3MediumInstruct": "microsoft/Phi-3-medium-128k-instruct",
        "MiniCPMo26": "openbmb/MiniCPM-o-2_6",
        # 'MistralNemoInstruct2407': 'mistralai/Mistral-Nemo-Instruct-2407', included before
        "MistralSmall24BInstruct2501": "mistralai/Mistral-Small-24B-Instruct-2501",
        "MistralLargeInstruct2411": "mistralai/Mistral-Large-Instruct-2411",
        # 'Mixtral8x22B01Instruct' : 'https://huggingface.co/mistralai/Mixtral-8x22B-Instruct-v0.1' included before
        "Mistral8x7BChat": "model-hub/mistral-8x7b-chat",
        "Codestral22B01": "mistralai/Codestral-22B-v0.1",
        "Mathstral7B01": "mistralai/Mathstral-7B-v0.1",
        "Llama3370InstructGGUF": "unsloth/Llama-3.3-70B-Instruct-GGUF",
        "Phi4GGUF": "unsloth/phi-4-GGUF",
        "MistralSmall24BInstruct2501GGUF": "unsloth/Mistral-Small-24B-Instruct-2501-GGUF",
        "MiniCPMo26GGUF": "openbmb/MiniCPM-o-2_6-gguf",
        # DeepSeek
        "DeepSeekR1Qwen32": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        # cold models
        "DeepSeekR1": "deepseek-ai/DeepSeek-R1",
        "DeepSeekR1Qwen15": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "DeepSeekR1Qwen7": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "DeepSeekR1Qwen14": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "DeepSeekR1Llama70": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
        "DeepSeekR1Llama8": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        # HuggingFace Llama
        "Llama3370Instruct": "meta-llama/Llama-3.3-70B-Instruct",
        "Llama321Instruct": "meta-llama/Llama-3.2-1B-Instruct",
        "Llama321": "meta-llama/Llama-3.2-1B",
        "Llama323Instruct": "meta-llama/Llama-3.2-3B-Instruct",
        "Llama323": "meta-llama/Llama-3.2-3B",
        "Llama31405Instruct": "meta-llama/Meta-Llama-3.1-405B-Instruct",
        "Llama31405": "meta-llama/Meta-Llama-3.1-405B",
        "Llama3170Instruct": "meta-llama/Llama-3.1-70B-Instruct",
        "Llama3170": "meta-llama/Meta-Llama-3.1-70B",
        "Llama318Instruct": "meta-llama/Llama-3.1-8B-Instruct",
        "Llama318": "meta-llama/Meta-Llama-3.1-8B",
        "Llama370Instruct": "meta-llama/Meta-Llama-3-70B-Instruct",
        "Llama370": "meta-llama/Meta-Llama-3-70B",
        "Llama38Instruct": "meta-llama/Meta-Llama-3-8B-Instruct",
        "Llama38": "meta-llama/Meta-Llama-3-8B",
        "Llama27": "meta-llama/Llama-2-7b",
        "Llama270": "meta-llama/Llama-2-70b",
        # HuggingFace FlanT5
        "FlanT5Base": "google/flan-t5-base",
        "FlanT5Large": "google/flan-t5-large",
        "FlanT5Small": "google/flan-t5-small",
        "FlanT5XXL": "google/flan-t5-xxl",
        # HuggingFace MT5
        "MT5Base": "google/mt5-base",
        "MT5Large": "google/mt5-large",
        "MT5Small": "google/mt5-small",
        "MT5XL": "google/mt5-xl",
        "MT5XXL": "google/mt5-xxl",
        # HuggingFace Gemma
        "Gemma227BIT": "google/gemma-2-27b-it",
        # HuggingFace Mistral
        "Mistral7B03Instruct": "mistralai/Mistral-7B-Instruct-v0.3",
        "Mistral7B03": "mistralai/Mistral-7B-v0.3",
        "Mistral7B02Instruct": "mistralai/Mistral-7B-Instruct-v0.2",
        "MistralSmallInstruct2409": "mistralai/Mistral-Small-Instruct-2409",
        "MistralLargeInstruct2407": "mistralai/Mistral-Large-Instruct-2407",
        "MistralNemoInstruct2407": "mistralai/Mistral-Nemo-Instruct-2407",
        "Mistral7B01": "mistralai/Mistral-7B-v0.1",
        "Mixtral8x7B01Instruct": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "Mixtral8x22B01Instruct": "mistralai/Mixtral-8x22B-Instruct-v0.1",
        "Mixtral8x7B01": "mistralai/Mixtral-8x7B-v0.1",
        "Mixtral8x22B01": "mistralai/Mixtral-8x22B-v0.1",
        # HuggingFace Falcon
        "Falcon7BInstruct": "tiiuae/falcon-7b-instruct",
        "Falcon40BInstruct": "tiiuae/falcon-40b-instruct",
        "FalconMamba7BInstruct": "tiiuae/falcon-mamba-7b-instruct",
        "FalconMamba7B": "tiiuae/falcon-mamba-7b",
        # OpenAI's chat models
        "GPT4o": "gpt-4o",
        "GPT4oMini": "gpt-4o-mini",
        # 'GPTo1Mini': 'o1-mini', # Tier 5 is required
        "GPT4Turbo": "gpt-4-turbo",
        "GPT4": "gpt-4",
        "GPT35Turbo": "gpt-3.5-turbo",
        "GPT35TurboInstruct": "gpt-3.5-turbo-instruct",
        # 'GPT35Turbo0613': 'gpt-3.5-turbo-0613',  # snapshot June 13th 2023, deprecated June 13th 2024
        "GPT35Turbo1106": "gpt-3.5-turbo-1106",  # snapshot November 6th 2023
        "GPT40613": "gpt-4-0613",  # snapshot June 13th 2023
        # Google Gemini models
        "Gemini25Flash": "gemini-2.5-flash",
    }  # ["gpt-4o-mini", "meta-llama/Meta-Llama-3.1-70B-Instruct"]

    def print_supported_llms(self):
        print("List of supported LLMs:")
        for llm, url in self.supported_models.items():
            print("{} : {}".format(llm, url))

    cold_models = []
    # ['Llama31405Instruct', 'Llama27', 'Llama270', 'FlanT5Base', 'FlanT5XXL', 'MT5Base', 'MT5Large', 'MT5Small',
    #  'Gemma2BIT', 'Mistral7B02Instruct']
    error_models = []
    # ['Llama31405', 'Llama3170', 'Llama318', 'Llama370', 'Llama38', 'MT5XL', 'MT5XXL', 'Mistral7B03',
    #         'MistralLargeInstruct2407', 'Mixtral8x22B01Instruct', 'Mixtral8x7B01', 'Mixtral8x22B01',
    #         'Falcon40BInstruct', 'FalconMamba7BInstruct', 'FalconMamba7B']
    timeout_models = []

    gpt_client = OpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
        timeout=TIMEOUT,
    )

    hf_api_key = os.environ.get("API_KEY_HUGGINGFACE")

    try:
        gemini_api_key = os.environ.get("GOOGLE_API_KEY")
        if gemini_api_key:
            gemini_client = genai.Client(api_key=gemini_api_key)
        else:
            print("GOOGLE_API_KEY not set. Gemini API will not be configured.")
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")

    def get_all_models(self):
        return list(self.supported_models.keys())

    def get_model_url(self, model_id: str):
        for key in self.supported_models.keys():
            if key.upper() == model_id.upper():
                return self.supported_models.get(key)
        return ""

    def get_model_ids_startswith(self, prefix: str):
        model_ids = []
        for key in self.supported_models.keys():
            if key.upper().startswith(prefix.upper()):
                model_ids.append(key)
        return model_ids

    def execute_prompt(self, model_id, prompt: str, format_instructions=""):
        response = None
        # avoid calling models currently cold/unsupported in HF or OPENAI
        # if model_id not in self.cold_models and model_id not in self.unsupported_models:
        # print(f"Executing prompt with model: {model_id}")
        if model_id == "GPT35TurboInstruct":
            response = self.gpt_old_execute_prompt(
                model_id, prompt, format_instructions
            )
        elif model_id.startswith("GPT"):
            response = self.gpt_execute_prompt(model_id, prompt, format_instructions)
        elif model_id.startswith("L_"):
            response = self.ollama_execute_prompt(model_id, prompt, format_instructions)
        elif model_id.startswith("Gemini"):
            response = self.gemini_execute_prompt(model_id, prompt, format_instructions)
        elif model_id.startswith("Llama32"):
            response = self.hf_execute_prompt(model_id, prompt, format_instructions)
        else:  # use model from HF
            response = self.hf_execute_prompt(model_id, prompt, format_instructions)
        # else:
        #     print("Model Skipped:{}".format(model_id))
        return response

    def gpt_execute_prompt(
        self, model_id="GPT4oMini", prompt="", format_instructions=""
    ):
        model_url = self.get_model_url(model_id)
        if model_url == "":
            model_url = self.get_model_url("GPT4oMini")

        # parser = PydanticOutputParser(pydantic_object=TraitList)
        if format_instructions == "":
            format_instructions = ""  # parser.get_format_instructions()
        try:
            messages = [{"role": "user", "content": prompt + format_instructions}]
            completion = self.gpt_client.chat.completions.create(
                model=model_url, messages=messages
            )
            gpt_response = completion.choices[0].message
            if gpt_response.refusal:
                print("gpt_execute_prompt:gpt_response.refusal: ", gpt_response.refusal)
                return None
            else:
                # parsed_mc_question = parser.invoke(gpt_response.content)
                return gpt_response  # parsed_mc_question
        except ValidationError as err:
            print("gpt_execute_prompt:ValidationError: ", err)
            return None
        except Exception as exc:
            print("gpt_execute_prompt: general exception: ", exc)
            return None

    def gpt_old_execute_prompt(
        self, model_id="GPT35TurboInstruct", prompt="", format_instructions=""
    ):
        model_url = self.get_model_url(model_id)
        if model_url == "":
            model_url = self.get_model_url("GPT35TurboInstruct")

        # parser = PydanticOutputParser(pydantic_object=TraitList)
        if format_instructions == "":
            format_instructions = ""  # parser.get_format_instructions()
        try:
            messages = prompt + format_instructions
            completion = self.gpt_client.completions.create(
                model=model_url, prompt=messages
            )
            gpt_response = completion.choices[0].text

            if "error" in gpt_response:
                print("gpt_execute_prompt:gpt_response.refusal: ", gpt_response)
                return None
            else:
                # parsed_mc_question = parser.invoke(gpt_response)
                return gpt_response  # parsed_mc_question
        except ValidationError as err:
            print("gpt_execute_prompt:ValidationError: ", err)
            return None
        except Exception as exc:
            print("gpt_execute_prompt: general exception: ", exc)
            return None

    def ollama_execute_prompt(self, model_id, prompt: str, format_instructions=""):
        # Ollama models are prefixed with 'L_'
        model_url = self.get_model_url(model_id)
        if model_url == "":
            model_url = self.get_model_url("L_Phi4")
        try:
            response: ChatResponse = chat(
                model=str(model_url),
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
                    print(f"[ERROR] ollama: {model_id} error: {response['error']}")
                    return None
            return response.message.content
        except ValidationError as err:
            print("[ERROR] ollama:ValidationError: ", err)
            return None
        except Exception as exc:
            print("[ERROR] ollama: general exception: ", exc)
            return None

    def gemini_execute_prompt(self, model_id, prompt: str, format_instructions=""):
        model_url = self.get_model_url(model_id)
        if model_url == "":
            model_url = self.get_model_url("Gemini25Flash")
        try:
            full_prompt = prompt + format_instructions
            response = self.gemini_client.models.generate_content(
                model=model_url, contents=full_prompt
            )
            return response.text
        except ValidationError as err:
            print(f"[ERROR] gemini_execute_prompt:ValidationError: {err}")
            return None
        except Exception as exc:
            print(f"[ERROR] gemini_execute_prompt: Excepción general: {exc}")
            return None

    def hf_execute_prompt(self, model_id, prompt: str, format_instructions=""):
        model_url = self.get_model_url(model_id)
        if model_url == "":
            model_url = self.get_model_url("Llama323Instruct")

        try:
            client = InferenceClient(
                provider="auto",
                api_key=self.hf_api_key,
            )
            completion = client.chat.completions.create(
                model=model_url,
                messages=[{"role": "user", "content": prompt + format_instructions}],
            )
            generated_text = completion.choices[0].message.content
            if generated_text is not None and "error" in generated_text:
                print("[ERROR] hf_execute_prompt: ", generated_text)
                return None
            else:
                return generated_text
        except ValidationError as err:
            print("[ERROR] hf_execute_prompt:ValidationError: ", err)
            return None
        except Exception as exc:
            print("[ERROR] hf_execute_prompt: general exception: ", exc)
            return None
