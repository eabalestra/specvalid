import re
from typing import List, Set, Tuple


class JavaCodeExtractor:
    def __init__(self) -> None:
        pass

    def extract_tests_from_response(self, llm_response: str) -> List[str]:
        """Enhanced test extraction with multiple strategies."""
        llm_response = self._strip_markdown_fences(llm_response)

        # Strategy 1: Original method
        tests = self._try_original_extraction(llm_response)
        tests = self._sanitize_and_filter_tests(tests)
        if tests:
            return tests

        # Strategy 2: Extract from code blocks
        tests = self._try_code_block_extraction(llm_response)
        tests = self._sanitize_and_filter_tests(tests)
        if tests:
            return tests

        # Strategy 3: More aggressive pattern matching
        tests = self._try_aggressive_extraction(llm_response)
        return self._sanitize_and_filter_tests(tests)

    def _strip_markdown_fences(self, text: str) -> str:
        return re.sub(r"(?m)^\s*```.*$", "", text)

    def _sanitize_and_filter_tests(self, tests: List[str]) -> List[str]:
        cleaned_tests = []
        for test in tests:
            cleaned = self._sanitize_test_method(test)
            if self._is_valid_test(cleaned) and not self._has_invalid_artifacts(cleaned):
                cleaned_tests.append(cleaned)
        return cleaned_tests

    def _sanitize_test_method(self, test_method: str) -> str:
        cleaned_lines = []
        for line in test_method.split("\n"):
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue
            if stripped.startswith("```"):
                continue
            if re.match(r"^(?:import|package)\s+", stripped):
                continue
            if re.match(r"^\d+\.\s+", stripped):
                continue
            if re.match(r"^[-*]\s+\w", stripped):
                continue
            if "..." in stripped and '"' not in stripped and "'" not in stripped:
                continue
            if "`" in stripped and not stripped.startswith("//"):
                continue
            if self._looks_like_prose_line(stripped):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    @staticmethod
    def _looks_like_prose_line(line: str) -> bool:
        if not line:
            return False
        if line.startswith(("//", "/*", "*", "*/")):
            return False
        if line.startswith("@"):
            return False
        if re.search(r"[;{}()=<>\\[\\]]", line):
            return False
        if re.search(
            r"\b(public|protected|private|static|final|class|void|new|if|for|while|"
            r"try|catch|throw|return|switch|case|else)\b",
            line,
        ):
            return False
        return bool(re.search(r"[A-Za-z].*\s+[A-Za-z]", line))

    def _has_invalid_artifacts(self, test_method: str) -> bool:
        if "```" in test_method:
            return True
        if "`" in test_method:
            return True
        if re.search(r"(?m)^\s*(?:import|package)\s+", test_method):
            return True
        if re.search(r"(?m)^\s*\.{3,}", test_method):
            return True
        if re.search(r"(?m)^\s*\d+\.\s+", test_method):
            return True
        if re.search(
            r"(?m)^\s*public\s+void\s+\w+\s*\([^)]*\)\s*\.+", test_method
        ):
            return True
        return False

    def _try_original_extraction(self, llm_response: str) -> List[str]:
        """Try the original extraction method."""
        try:
            code = self.extract_test_from_string(llm_response)
            return self.parse_test_from_string(code)
        except Exception:
            return []

    def _try_code_block_extraction(self, llm_response: str) -> List[str]:
        """Extract tests from markdown code blocks."""
        # Pattern to find code blocks
        code_pattern = r"```(?:java)?\s*\n(.*?)\n```"
        matches = re.findall(code_pattern, llm_response, re.DOTALL | re.IGNORECASE)

        all_tests = []
        for code_block in matches:
            # Clean and parse each code block
            cleaned_code = self._clean_code_block(code_block)
            tests = self.parse_test_from_string(cleaned_code)
            all_tests.extend(tests)

        return all_tests

    def _clean_code_block(self, code_block: str) -> str:
        """Clean a code block by removing problematic comments."""
        lines = code_block.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip lines that are purely explanatory
            if re.match(r"^\s*//.*(?:This|Assuming|However|Same logic)", line):
                continue

            # Truncate overly long inline comments
            if "//" in line:
                code_part, comment_part = line.split("//", 1)
                if len(comment_part.strip()) > 40:
                    line = code_part.rstrip()

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _try_aggressive_extraction(self, llm_response: str) -> List[str]:
        """More aggressive extraction for difficult cases."""
        tests = []

        # Find @Test annotations
        test_pattern = r"@Test(?:\([^)]*\))?"
        test_positions = [m.start() for m in re.finditer(test_pattern, llm_response)]

        for start_pos in test_positions:
            # Try to extract a complete test method
            test_method = self._extract_single_test(llm_response, start_pos)
            if test_method and self._is_valid_test(test_method):
                tests.append(test_method)

        return tests

    def _extract_single_test(self, text: str, start_pos: int) -> str:
        """Extract a single test method starting from @Test annotation."""
        # Look for method signature after @Test
        remaining_text = text[start_pos:]
        method_pattern = (
            r"@Test(?:\([^)]*\))?\s*(?:public\s+)?void\s+(\w+)\s*\([^)]*\)"
            r"(?:\s*throws[^{]*)?\s*\{"
        )

        match = re.search(method_pattern, remaining_text, re.MULTILINE | re.DOTALL)
        if not match:
            return ""

        method_start = start_pos + match.end() - 1  # Position of opening brace
        method_body = self._extract_balanced_braces(text, method_start)

        if method_body:
            full_method = text[start_pos:method_start] + method_body
            return self._clean_test_method(full_method)

        return ""

    def _extract_balanced_braces(self, text: str, start_pos: int) -> str:
        """Extract text with balanced braces starting from given position."""
        brace_count = 0
        i = start_pos

        while i < len(text):
            char = text[i]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[start_pos : i + 1]
            i += 1

        return ""

    def _clean_test_method(self, test_method: str) -> str:
        """Clean up a test method by removing problematic content."""
        # Remove lines with "sic." artifacts
        test_method = re.sub(r".*sic\..*\n?", "", test_method)

        # Clean up excessively long comments
        lines = test_method.split("\n")
        cleaned_lines = []

        for line in lines:
            if "//" in line:
                code_part, comment_part = line.split("//", 1)
                # Keep only short, relevant comments
                if len(comment_part.strip()) <= 30:
                    cleaned_lines.append(line)
                else:
                    cleaned_lines.append(code_part.rstrip())
            else:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _is_valid_test(self, test_method: str) -> bool:
        """Check if a test method has valid structure."""
        # Must have @Test annotation
        if not re.search(r"@Test", test_method):
            return False

        # Must have balanced braces
        open_braces = test_method.count("{")
        close_braces = test_method.count("}")
        if open_braces != close_braces or open_braces == 0:
            return False

        # Must have method signature
        if not re.search(r"void\s+\w+\s*\([^)]*\)", test_method):
            return False

        return True

    def extract_test_with_comments_from_string(self, text: str) -> str:
        lines = text.split("\n")
        comments, extracted_test = self.parse_comments_and_test(lines)
        return "\n".join(comments + extracted_test)

    def extract_test_from_string(self, text: str) -> str:
        lines = text.split("\n")
        comments, extracted_test = self.parse_comments_and_test(lines)
        return "\n".join(extracted_test)

    def parse_comments_and_test(self, lines: List[str]) -> Tuple[List[str], List[str]]:
        test_case_started = False
        test_method_ended = False
        extracted_test = []
        comments = []
        brace_count = 0
        test_start_pattern = re.compile(r"^\s*@Test")

        for line in lines:
            if test_start_pattern.match(line):
                test_case_started = True
                test_method_ended = False

            if test_case_started and not test_method_ended:
                extracted_test.append(line)
                brace_count += line.count("{") - line.count("}")
                # Check if this line ends the test method
                if brace_count == 0 and "}" in line:
                    # Check if there's content after the closing brace
                    closing_brace_index = line.rfind("}")
                    content_after_brace = line[closing_brace_index + 1 :].strip()

                    if content_after_brace:
                        # Split the line: part before and including '}'
                        # stays in test, rest becomes comment
                        test_part = line[: closing_brace_index + 1]
                        comment_part = content_after_brace

                        # Replace the last line in extracted_test with just
                        # the test part
                        extracted_test[-1] = test_part
                        extracted_test.append("\n")
                        test_method_ended = True

                        # Add the remaining part as a comment
                        if comment_part:
                            comments.append(f"// {comment_part}")
                    else:
                        # Normal case: line ends cleanly with '}'
                        extracted_test.append("\n")
                        test_method_ended = True
            else:
                # Comment out everything that's not part of a test method
                if line.strip():  # Only comment non-empty lines
                    comments.append(f"// {line}")
                else:
                    comments.append(line)  # Keep empty lines as they are
        return comments, extracted_test

    def parse_test_from_string(self, content: str) -> List[str]:
        brace_count = 0
        test_methods = []
        extracted_test = []
        test_case_started = False
        entered_body = False
        in_block_comment = False
        found_signature = False
        lines_since_start = 0
        lines_since_signature = 0
        max_signature_lines = 8
        max_body_lines = 8
        lines = content.split("\n")
        test_start_pattern = re.compile(
            r"@\s*(?:\w+\.)*(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b"
        )
        signature_pattern = re.compile(r"\bvoid\s+\w+\s*\([^)]*\)")

        for line in lines:
            sanitized, in_block_comment = self._strip_comments_and_strings(
                line, in_block_comment
            )
            if test_start_pattern.search(sanitized):
                if test_case_started and not entered_body:
                    extracted_test = []
                    brace_count = 0
                    entered_body = False
                    found_signature = False
                    lines_since_start = 0
                    lines_since_signature = 0
                if not test_case_started:
                    test_case_started = True
                    brace_count = 0
                    entered_body = False
                    found_signature = False
                    lines_since_start = 0
                    lines_since_signature = 0
                    extracted_test = []

            if test_case_started:
                extracted_test.append(line)
                lines_since_start += 1
                if not found_signature and signature_pattern.search(sanitized):
                    found_signature = True
                    lines_since_signature = 0
                if found_signature:
                    lines_since_signature += 1
                    brace_count += sanitized.count("{") - sanitized.count("}")
                    if brace_count > 0:
                        entered_body = True

                if not found_signature and lines_since_start > max_signature_lines:
                    test_case_started = False
                    extracted_test = []
                    brace_count = 0
                    entered_body = False
                    found_signature = False
                    lines_since_start = 0
                    lines_since_signature = 0
                    continue

                if found_signature and not entered_body and lines_since_signature > max_body_lines:
                    test_case_started = False
                    extracted_test = []
                    brace_count = 0
                    entered_body = False
                    found_signature = False
                    lines_since_start = 0
                    lines_since_signature = 0
                    continue

                if entered_body and brace_count == 0:
                    test_case_started = False
                    test_methods.append("\n".join(extracted_test))
                    extracted_test = []
                    brace_count = 0
                    entered_body = False
                    found_signature = False
                    lines_since_start = 0
                    lines_since_signature = 0

        return test_methods

    @staticmethod
    def _strip_comments_and_strings(
        line: str, in_block_comment: bool
    ) -> Tuple[str, bool]:
        out = []
        i = 0
        in_single_quote = False
        in_double_quote = False
        escape = False

        while i < len(line):
            ch = line[i]
            if in_block_comment:
                end = line.find("*/", i)
                if end == -1:
                    return "", True
                i = end + 2
                in_block_comment = False
                continue

            if in_single_quote:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "'":
                    in_single_quote = False
                i += 1
                continue

            if in_double_quote:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_double_quote = False
                i += 1
                continue

            if line.startswith("/*", i):
                in_block_comment = True
                i += 2
                continue
            if line.startswith("//", i):
                break
            if ch == "'":
                in_single_quote = True
                i += 1
                continue
            if ch == '"':
                in_double_quote = True
                i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out), in_block_comment

    def extract_method_code(self, class_code: str, method_name: str) -> str:
        pattern = (
            r"^\s*(?:(?:public)|(?:private)|(?:static)|(?:protected)\s+)*.*\s+"
            + method_name
            + r"\s*\(.*\)\s*(?:throws\s+[\w\s,]+)?\s*{"
        )

        match = re.search(pattern, class_code, re.MULTILINE)
        if not match:
            return ""

        start_index = match.start()
        brace_count = 0
        end_index = start_index

        for i in range(start_index, len(class_code)):
            if class_code[i] == "{":
                brace_count += 1
            elif class_code[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_index = i + 1
                    break

        return class_code[start_index:end_index]

    @staticmethod
    def extract_other_method_signatures(class_code: str) -> List[str]:
        def _strip_comments(code: str) -> str:
            without_block = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
            return re.sub(r"(?m)^\s*//.*$", "", without_block)

        cleaned_code = _strip_comments(class_code)
        class_match = re.search(r"\bclass\s+([A-Za-z_][\w$]*)", cleaned_code)
        class_name = class_match.group(1) if class_match else ""

        method_pattern = re.compile(
            r"""
            ^\s*
            (?P<modifiers>(?:public|protected|private|static|final|abstract|synchronized|default|native|strictfp)\s+)*
            (?P<generics><[^>]+>\s+)?
            (?:
                (?P<return_type>(?:[\w$.<>?\[\],&]+(?:\s+[\w$.<>?\[\],&]+)*))\s+
                (?P<method_name>[A-Za-z_][\w$]*)
                |
                (?P<constructor_name>[A-Za-z_][\w$]*)
            )
            \s*\(
                (?P<params>[^)]*)
            \)\s*
            (?:throws\s+[^{]*)?
            \{
            """,
            re.MULTILINE | re.VERBOSE,
        )

        signatures: List[str] = []
        seen: Set[str] = set()

        for match in method_pattern.finditer(cleaned_code):
            method_name = match.group("method_name")
            constructor_name = match.group("constructor_name")

            if constructor_name:
                if not class_name or constructor_name != class_name:
                    continue
                name = constructor_name
            else:
                name = method_name

            if not name:
                continue

            params = match.group("params").strip()
            params = re.sub(r"\s+", " ", params)
            signature = f"{name}({params})" if params else f"{name}()"

            if signature not in seen:
                seen.add(signature)
                signatures.append(signature)

        return signatures

    @staticmethod
    def extract_method_signature(method_code: str) -> str:
        pattern = r"^\s*(?:(?:public)|(?:private)|(?:static)|(?:protected)\s+)*.*\s+(\w+)\s*\(.*\)\s*(?:throws\s+[\w\s,]+)?\s*{"
        match = re.search(pattern, method_code, re.MULTILINE)
        if match:
            return match.group(1)
        return ""
