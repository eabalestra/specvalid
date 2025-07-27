

import re


class JavaTestSuite:

    def __init__(self, path_to_suite: str):
        self.path_to_suite = path_to_suite

    def remove_assertions_from_test(self, test_code: str) -> str:
        assertion_regex = re.compile(
            r'^\s*(?:[a-zA-Z0-9_.]+\.)?(?:assert\w*\b.*?;|fail\w*\b.*?;).*$',
            re.MULTILINE | re.IGNORECASE
        )
        return re.sub(assertion_regex, '', test_code)
