from abc import ABC, abstractmethod
from enum import Enum


class PromptID(Enum):
    General_V1 = 0
    General_V2 = 1
    General_V3 = 2

    @classmethod
    def all(cls):
        return list(map(lambda c: c, cls))

    @classmethod
    def print_supported_prompts(cls):
        print("List of supported Prompts:")
        for p in cls.all():
            print("{} : {}".format(p.name, p))


class Prompt(ABC):
    id: PromptID
    template: str
    prompt: str
    format_instructions: str

    class_code: str
    method_code: str
    spec: str

    def __init__(
        self,
        id: PromptID,
        class_code="",
        method_code="",
        spec="",
        format_instructions="",
    ):
        self.id = id
        self.class_code = class_code
        self.method_code = method_code
        self.spec = spec
        self.format_instructions = format_instructions

    @abstractmethod
    def generate_prompt(self):
        raise NotImplementedError("Subclasses must implement this method.")
