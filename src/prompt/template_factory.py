from prompt.prompt_template import Prompt, PromptID
from prompt.templates.general.general_prompt import GeneralPrompt
from prompt.templates.verification_only.verification_only_prompt import (
    VerificationOnlyPrompt,
)
from prompt.templates.zero_shot.zero_shot_prompt import ZeroShotPrompt


class PromptTemplateFactory:
    @staticmethod
    def create_prompt(prompt_id, class_code, method_code, spec) -> Prompt:
        if prompt_id == PromptID.General_V1:
            return GeneralPrompt(PromptID.General_V1, class_code, method_code, spec)
        if prompt_id == PromptID.General_V2:
            return ZeroShotPrompt(PromptID.General_V2, class_code, method_code, spec)
        if prompt_id == PromptID.General_V3:
            return VerificationOnlyPrompt(
                PromptID.General_V3, class_code, method_code, spec
            )
        raise ValueError(f"Unknown prompt ID: {prompt_id}")

    @staticmethod
    def create_fix_prompt(unit_test, error_msg, subject):
        template = """
I need you to fix an error in a unit test, an error occurred while compiling

The unit test is:
```
{unit_test}
```

The error message is:
```
{error_message}
```

The unit test is testing the method `{method_sig}` in the class `{class_name}`,
the source code of the method under test and its class is:
```
{full_fm}
```

```
The signatures of other methods in its class are `{other_method_sigs}`
```

Please fix the error in the unit test and return the whole fixed unit test.
You can use Junit 4. No explanation is needed.
        """

        return template.format(
            unit_test=unit_test,
            error_message=error_msg,
            method_sig=subject.method_sig,
            class_name=subject.class_name,
            full_fm=subject.class_code,
            other_method_sigs=subject.other_method_sigs,
        )
