

from re import search
import re


def _strip_outer_parentheses(spec: str) -> str:
    spec = spec.strip()
    if spec.startswith('(') and spec.endswith(')'):
        depth = 0
        for i, ch in enumerate(spec):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if depth == 0 and i < len(spec) - 1:
                return spec
        return spec[1:-1].strip()
    return spec


class Specs:

    def __init__(self, spec_file: str, class_path_src: str, method_name: str):
        self.assertions_file_path = spec_file
        self.class_path_src = class_path_src
        self.method_name = method_name

    def parse_and_collect_specs(self) -> set:
        specs = []
        with open(self.assertions_file_path, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()
            for line in lines:
                if self._is_inv_line(line):
                    specs.append(line)
        return set(specs)

    def transform_specification_vars(self, spec: str) -> str:
        class_name = self.class_path_src.split("/")[-1].replace(".java", "")
        processed_spec = spec.replace("FuzzedInvariant", "").strip()

        if "holds for:" in processed_spec:
            processed_spec, vars_section = processed_spec.split("holds for:")
            processed_spec = processed_spec.strip()
            variable_names = vars_section.strip().strip("<>").split(",")

            quantified_pattern = re.compile(
                r'\b(?:some|all|no)\s+n\b', re.IGNORECASE)
            if quantified_pattern.search(processed_spec):
                variable_names = variable_names[1:]

            variable_iter = iter(variable_names)
            for var in variable_iter:
                if (var == "this" or var == "orig(this)") and class_name in spec:
                    processed_spec = processed_spec.replace(class_name, var)
                    var = next(variable_iter, var)
                match = re.search(r'\w+_Variable_\d+', processed_spec)
                if match:
                    processed_spec = processed_spec.replace(
                        match.group(0), var.strip())

        processed_spec = processed_spec.replace("daikon.Quant.", "")
        processed_spec = processed_spec.replace("orig(", r"\old(")
        processed_spec = processed_spec.replace("\\", "")
        return _strip_outer_parentheses(processed_spec).strip()

    def _is_inv_line(self, line: str) -> bool:
        return not (search(":::OBJECT", line) or
                    search("==============", line) or
                    search(":::POSTCONDITION", line) or
                    search(":::ENTER", line) or
                    search("buckets=", line) or
                    search("specs=", line))
