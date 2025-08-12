from prompt.prompt_template import Prompt


class CompilationFixPrompt(Prompt):
    def generate_prompt(self) -> str:
        NOT_COMPILABLE_PROMPT_TEMPLATE = """
SYSTEM: You are a Java developer whose job is to FIX previously generated test code so it compiles. Return only corrected Java code (either the single test method or a full test class if necessary). No commentary.

PROMPT:
- Original LLM response + compilation errors:
{llm_response}

- Class under test (do not modify):
{class_code}

- Method under test:
{method_code}

INSTRUCTIONS:
1) Produce corrected, compilable Java test code. If the original response lacked imports or a test class wrapper, add them.
2) If the test uses 'old(...)', replace it with captured local vars (e.g., int oldX = x;).
3) If the class under test is in a package, add the correct import or use fully-qualified class names.
4) Keep the original test's intent (the concrete input values) unless those values caused compile-time errors; if so, pick equivalent values that preserve the counterexample.
5) Do not change the class under test.
6) Output only the corrected Java source (compilable).
"""
        formatted_prompt = NOT_COMPILABLE_PROMPT_TEMPLATE.format(
            llm_response=self.spec,
            class_code=self.class_code,
            method_code=self.method_code,
        )
        return formatted_prompt
