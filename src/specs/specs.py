

from re import search


class Specs:

    def __init__(self, spec_file: str):
        self.assertions_file_path = spec_file

    def is_inv_line(self, line: str) -> bool:
        return not (search(":::OBJECT", line) or
                    search("==============", line) or
                    search(":::POSTCONDITION", line) or
                    search(":::ENTER", line) or
                    search("buckets=", line) or
                    search("specs=", line))

    def parse_and_collect_specs(self) -> set:
        specs = []
        with open(self.assertions_file_path, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()
            for line in lines:
                if self.is_inv_line(line):
                    specs.append(line)
        return set(specs)
