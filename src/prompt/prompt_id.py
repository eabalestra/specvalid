from enum import Enum


class PromptID(Enum):
    General_V1 = 0
    General_V2 = 1
    NOT_COMPILABLE = 2

    @classmethod
    def all(cls):
        return list(map(lambda c: c, cls))

    @classmethod
    def print_supported_prompts(cls):
        print("List of supported Prompts:")
        for p in cls.all():
            print("{} : {}".format(p.name, p))
