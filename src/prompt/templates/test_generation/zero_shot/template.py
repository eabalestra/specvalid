BASE_TEMPLATE = """
You are a Java developer writing professional unit tests. Generate **only** unit test methods. Do NOT add anything else. Do NOT use Markdown. Do NOT add comments or explanations to the code.

Placeholders:
Postcondition to override: {spec}
Target method: {method_code}
Class containing the method: {class_code}

Instructions:
1. Write each test in JUnit format (@Test).
2. Do NOT invoke methods of the class under test within any of the assertion methods that are part of the JUnit API.
3. Each generated test must have a trace that overrides the {spec} postcondition.

Generate tests that **intentionally** override the `{spec}` postcondition for the `{method_code}` method of the class. `{class_code}`.
"""
