import glob
import os
import re

from utils.utils import Utils


class JavaTestFixer:
    def __init__(self, path_to_class: str, path_to_suite: str):
        self.path_to_class = path_to_class
        self.path_to_suite = path_to_suite
        self.class_package = Utils.get_java_package_from_path(path_to_class)
        self.class_directory = os.path.dirname(path_to_class)
        self.class_package_files = glob.glob(
            os.path.join(self.class_directory, "*.java")
        )
        self._simple_to_fqn = self._build_class_name_map()

    def _build_class_name_map(self) -> dict[str, str]:
        mapping = {}
        prefix = f"{self.class_package}." if self.class_package else ""
        for file_path in self.class_package_files:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            if file_name in {"package-info", "module-info"}:
                continue
            mapping[file_name] = f"{prefix}{file_name}"
        return mapping

    def repair_java_test(self, test_code: str) -> str:
        if test_code.strip() == "":
            return test_code
        test = self._sanitize_llm_artifacts(test_code)
        if test.strip() == "":
            return test
        test = self._rewrite_stray_expressions(test)
        test = self._add_throws_signature(test)
        test = self._replace_class_references(test)
        return self._add_test_annotation(test)

    @staticmethod
    def _is_probable_prose_line(line: str) -> bool:
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

    @staticmethod
    def _comment_out(line: str) -> str:
        if not line.strip():
            return line
        indent = line[: len(line) - len(line.lstrip())]
        return f"{indent}// {line.lstrip()}"

    def _sanitize_llm_artifacts(self, test_code: str) -> str:
        if re.search(r"\bvoid\s+\w+\s*\([^)]*\)\s*\.\.\.", test_code):
            return ""

        cleaned_lines = []
        for line in test_code.split("\n"):
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue
            if "```" in stripped or "`" in stripped:
                cleaned_lines.append(self._comment_out(line))
                continue
            if re.match(r"^\s*(?:package|import)\s+", stripped):
                cleaned_lines.append(self._comment_out(line))
                continue
            if re.match(r"^\s*(?:-|\*)\s+\w", stripped) or re.match(
                r"^\s*\d+\.\s+\w", stripped
            ):
                cleaned_lines.append(self._comment_out(line))
                continue
            if "..." in stripped and '"' not in stripped and "'" not in stripped:
                cleaned_lines.append(self._comment_out(line))
                continue
            if self._is_probable_prose_line(stripped):
                cleaned_lines.append(self._comment_out(line))
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _rewrite_stray_expressions(self, test_code: str) -> str:
        lines = test_code.split("\n")
        rewritten = []
        counter = 0
        in_block_comment = False
        keywords = (
            "if",
            "for",
            "while",
            "switch",
            "case",
            "return",
            "throw",
            "try",
            "catch",
            "do",
            "else",
            "synchronized",
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                rewritten.append(line)
                continue

            if in_block_comment:
                rewritten.append(line)
                if "*/" in line:
                    in_block_comment = False
                continue

            if stripped.startswith("/*"):
                rewritten.append(line)
                if "*/" not in line:
                    in_block_comment = True
                continue

            if stripped.startswith(("//", "*", "*/")):
                rewritten.append(line)
                continue

            if '"' in line or "'" in line:
                rewritten.append(line)
                continue

            match = re.match(r"^(\s*)([^;]+);(\s*//.*)?$", line)
            if not match:
                rewritten.append(line)
                continue

            expr = match.group(2).strip()
            if expr.startswith(keywords):
                rewritten.append(line)
                continue

            if re.search(r"(?<![=!<>])=(?!=)", expr):
                rewritten.append(line)
                continue

            if re.match(r"^[\w$.]+\s*(\+\+|--)\s*$", expr) or re.match(
                r"^(\+\+|--)\s*[\w$.]+\s*$", expr
            ):
                rewritten.append(line)
                continue

            if re.match(r"^\s*new\s+[\w$.<>\[\],\s]+\s*\(.*\)\s*$", expr):
                rewritten.append(line)
                continue

            if re.match(r"^[\w$.]+\s*\(.*\)\s*$", expr):
                rewritten.append(line)
                continue

            if not re.search(r"(\&\&|\|\||==|!=|<=|>=|<|>|\?|:)", expr):
                rewritten.append(line)
                continue

            counter += 1
            indent = match.group(1)
            comment = match.group(3) or ""
            rewritten.append(
                f"{indent}Object __sv_expr_{counter} = ({expr});{comment}"
            )

        return "\n".join(rewritten)

    def _add_test_annotation(self, test_code: str) -> str:
        # Add @Test annotation if not present
        if "@Test" not in test_code:
            test_code = f"@Test\n{test_code}"
        return test_code

    def _add_throws_signature(self, test_code: str) -> str:
        pattern = r"((public\s+)?void \w+\s*\([^)]*\))\s*(?:throws\s+[^\\{]*)?\s*\{"
        replacement = r"\1 throws Throwable {"
        return re.sub(pattern, replacement, test_code)

    def _replace_class_references(self, test_code: str) -> str:
        if not self._simple_to_fqn:
            return test_code

        def is_ident_start(ch: str) -> bool:
            return ch.isalpha() or ch in "_$"

        def is_ident_part(ch: str) -> bool:
            return ch.isalnum() or ch in "_$"

        out = []
        i = 0
        n = len(test_code)
        in_sl_comment = False
        in_ml_comment = False
        in_squote = False
        in_dquote = False
        escape = False
        line_start = 0

        while i < n:
            ch = test_code[i]

            if ch == "\n":
                in_sl_comment = False
                out.append(ch)
                i += 1
                line_start = i
                continue

            if (
                not in_sl_comment
                and not in_ml_comment
                and not in_squote
                and not in_dquote
                and i == line_start
            ):
                if test_code.startswith("package ", i) or test_code.startswith(
                    "import ", i
                ):
                    j = test_code.find("\n", i)
                    if j == -1:
                        out.append(test_code[i:])
                        break
                    out.append(test_code[i:j])
                    i = j
                    continue

            if escape:
                out.append(ch)
                escape = False
                i += 1
                continue

            if (in_squote or in_dquote) and ch == "\\":
                out.append(ch)
                escape = True
                i += 1
                continue

            if not (in_squote or in_dquote) and not in_ml_comment and not in_sl_comment:
                if test_code.startswith("//", i):
                    in_sl_comment = True
                    out.append("//")
                    i += 2
                    continue
                if test_code.startswith("/*", i):
                    in_ml_comment = True
                    out.append("/*")
                    i += 2
                    continue

            if in_ml_comment:
                if test_code.startswith("*/", i):
                    out.append("*/")
                    i += 2
                    in_ml_comment = False
                    continue
                out.append(ch)
                i += 1
                continue

            if in_sl_comment:
                out.append(ch)
                i += 1
                continue

            if not in_dquote and ch == "'" and not in_squote:
                in_squote = True
                out.append(ch)
                i += 1
                continue
            if in_squote and ch == "'":
                in_squote = False
                out.append(ch)
                i += 1
                continue

            if not in_squote and ch == '"' and not in_dquote:
                in_dquote = True
                out.append(ch)
                i += 1
                continue
            if in_dquote and ch == '"':
                in_dquote = False
                out.append(ch)
                i += 1
                continue

            if in_squote or in_dquote:
                out.append(ch)
                i += 1
                continue

            if is_ident_start(ch):
                j = i + 1
                while j < n and is_ident_part(test_code[j]):
                    j += 1
                token = test_code[i:j]

                prev = test_code[i - 1] if i > 0 else ""
                if prev == ".":
                    out.append(token)
                    i = j
                    continue

                fqn = self._simple_to_fqn.get(token)
                next_char = test_code[j] if j < n else ""
                if fqn and (not next_char or not is_ident_part(next_char)):
                    out.append(fqn)
                    i = j
                    continue

                out.append(token)
                i = j
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    @staticmethod
    def _contains_method_calls(expression: str) -> bool:
        """Check if an expression contains method calls that should be executed."""

        # Pattern to detect method calls
        method_call_pattern = (
            r"[a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*\s*\("
        )

        # Check if expression contains method calls
        has_method_calls = bool(re.search(method_call_pattern, expression))

        if not has_method_calls:
            return False

        # Additional check: if it contains comparison operators,
        # it's likely a boolean expression that should be commented
        comparison_operators = ["==", "!=", "<=", ">=", "<", ">", "&&", "||"]
        has_comparisons = any(op in expression for op in comparison_operators)

        # If it has both method calls and comparisons, treat as boolean expression
        if has_comparisons:
            return False

        # If it's just method calls without comparisons, treat as executable
        return True

    @staticmethod
    def _has_top_level_comma(expression: str) -> bool:
        depth = 0
        in_single_quote = False
        in_double_quote = False
        escape = False

        for ch in expression:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue
            if ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue
            if in_single_quote or in_double_quote:
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(depth - 1, 0)
            elif ch == "," and depth == 0:
                return True
        return False

    @staticmethod
    def remove_assertions_from_test(test: str) -> str:
        counter = 0

        def next_temp_var() -> str:
            nonlocal counter
            counter += 1
            return f"__sv_ignore_{counter}"

        def split_top_level_args(arg_str: str) -> list[str]:
            args = []
            depth = 0
            in_single_quote = False
            in_double_quote = False
            escape = False
            start = 0

            for i, ch in enumerate(arg_str):
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                    continue
                if ch == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                    continue
                if in_single_quote or in_double_quote:
                    continue
                if ch in "([{<":
                    depth += 1
                elif ch in ")]}>":
                    depth = max(depth - 1, 0)
                elif ch == "," and depth == 0:
                    args.append(arg_str[start:i].strip())
                    start = i + 1

            tail = arg_str[start:].strip()
            if tail:
                args.append(tail)
            return args

        def extract_lambda_body(expr: str) -> str | None:
            if "->" not in expr:
                return None
            _, right = expr.split("->", 1)
            body = right.strip()
            if body.startswith("{"):
                return body
            if body.endswith(";"):
                return body
            return f"{body};"

        def contains_operator(expr: str) -> bool:
            return bool(
                re.search(
                    r"(\&\&|\|\||==|!=|<=|>=|<|>|\?|:|\+|-|\*|/|%|\binstanceof\b)",
                    expr,
                )
            )

        def is_assignment_expr(expr: str) -> bool:
            return bool(
                re.search(
                    r"(?<![=!<>])=(?!=)|\+=|-=|\*=|/=|%=|<<=|>>=|>>>=|&=|\|=|\^=",
                    expr,
                )
            )

        def is_statement_expr(expr: str) -> bool:
            if re.search(r"\+\+|--", expr):
                return True
            if is_assignment_expr(expr):
                return True
            if re.match(r"^\s*new\s+[\w$.<>\[\]]+\s*\(.*\)\s*$", expr):
                return True
            if re.match(r"^[\w$.]+\s*\(.*\)\s*$", expr):
                return True
            return False

        def eval_expr(expr: str) -> str:
            expr = expr.strip()
            if not expr:
                return "// assertion removed;"
            if expr.endswith(";"):
                expr = expr[:-1].strip()
            if re.search(r"->|::", expr):
                body = extract_lambda_body(expr)
                if body:
                    if body.startswith("{"):
                        return f"try {body} catch (Throwable t) {{ /* assertion removed */ }}"
                    return f"try {{ {body} }} catch (Throwable t) {{ /* assertion removed */ }}"
                return f"// assertion removed: {expr};"
            if is_statement_expr(expr) and not contains_operator(expr):
                return expr if expr.endswith(";") else f"{expr};"
            return f"Object {next_temp_var()} = ({expr});"

        def eval_many(exprs: list[str]) -> str:
            cleaned = []
            for expr in exprs:
                expr = expr.strip()
                if not expr:
                    continue
                if expr.endswith(";"):
                    expr = expr[:-1].strip()
                if expr:
                    cleaned.append(expr)
            if not cleaned:
                return "// assertion removed;"
            if len(cleaned) == 1:
                return eval_expr(cleaned[0])
            return f"Object[] {next_temp_var()} = new Object[]{{ {', '.join(cleaned)} }};"

        def repl_assert_throws(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            if len(args) < 2:
                return "// assertion removed;"
            executable = args[1]
            body = extract_lambda_body(executable)
            if body:
                if body.startswith("{"):
                    return f"try {body} catch (Throwable t) {{ /* assertion removed */ }}"
                return f"try {{ {body} }} catch (Throwable t) {{ /* assertion removed */ }}"
            return eval_expr(executable)

        def repl_assert_all(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            statements = []
            for arg in args:
                body = extract_lambda_body(arg)
                if body:
                    if body.startswith("{"):
                        statements.append(
                            f"try {body} catch (Throwable t) {{ /* assertion removed */ }}"
                        )
                    else:
                        statements.append(
                            f"try {{ {body} }} catch (Throwable t) {{ /* assertion removed */ }}"
                        )
                else:
                    statements.append(eval_expr(arg))
            return "\n".join(statements) if statements else "// assertion removed;"

        def repl_assuming_that(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            statements = []
            if args:
                statements.append(eval_expr(args[0]))
            if len(args) > 1:
                body = extract_lambda_body(args[1])
                if body:
                    if body.startswith("{"):
                        statements.append(
                            f"try {body} catch (Throwable t) {{ /* assertion removed */ }}"
                        )
                    else:
                        statements.append(
                            f"try {{ {body} }} catch (Throwable t) {{ /* assertion removed */ }}"
                        )
                else:
                    statements.append(eval_expr(args[1]))
            return "\n".join(statements) if statements else "// assertion removed;"

        def repl_assertj_chain(match: re.Match) -> str:
            inner = match.group("inner").strip()
            return eval_expr(inner)

        result = test

        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertThrows|assertThrowsExactly|assertDoesNotThrow)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_assert_throws,
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertTimeout|assertTimeoutPreemptively)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_assert_throws,
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertAll)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_assert_all,
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertThat|then)\s*\(\s*(?P<inner>.*?)\s*\)\s*\.[^;]*;",
            repl_assertj_chain,
            result,
            flags=re.DOTALL,
        )

        def repl_true_false(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            expr = args[-1] if args else ""
            return eval_expr(expr)

        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertTrue|assertFalse|assumeTrue|assumeFalse)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_true_false,
            result,
            flags=re.DOTALL,
        )

        def repl_unary(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            expr = args[-1] if args else ""
            return eval_expr(expr)

        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertNull|assertNotNull|assertInstanceOf|assumeNotNull|assumeNoException)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_unary,
            result,
            flags=re.DOTALL,
        )

        def repl_binary(match: re.Match) -> str:
            args = split_top_level_args(match.group("args"))
            if len(args) >= 2:
                return eval_many([args[-2], args[-1]])
            return eval_many(args)

        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertEquals|assertNotEquals|assertSame|assertNotSame|"
            r"assertArrayEquals|assertIterableEquals|assertLinesMatch)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_binary,
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assertThat|assumeThat)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_binary,
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r"\b(?:[\w$]+\.)*(?:assumingThat)\s*\(\s*(?P<args>.*?)\s*\)\s*;",
            repl_assuming_that,
            result,
            flags=re.DOTALL,
        )

        result = re.sub(
            r"\bassert\s+(?P<expr>.*?)(?:\s*:\s*.*?)?\s*;",
            lambda m: eval_expr(m.group("expr")),
            result,
            flags=re.DOTALL,
        )

        result = re.sub(
            r"\b(?:[\w$]+\.)*fail\s*\(.*?\)\s*;",
            "// fail removed;",
            result,
            flags=re.DOTALL,
        )

        assertion_prefixes = (
            r"(?:org\.junit\.Assert|org\.junit\.Assume|junit\.framework\.Assert|"
            r"org\.junit\.jupiter\.api\.Assertions|org\.junit\.jupiter\.api\.Assumptions|"
            r"org\.testng\.Assert|org\.testng\.AssertJUnit|"
            r"org\.assertj\.core\.api\.Assertions|org\.assertj\.core\.api\.BDDAssertions|"
            r"org\.hamcrest\.MatcherAssert|"
            r"Assert|Assertions|Assume|Assumptions|MatcherAssert|BDDAssertions)"
        )
        result = re.sub(
            rf"\b{assertion_prefixes}\.\s*(//\s*(?:assertion|fail)\s+removed[:;])",
            r"\1",
            result,
        )
        result = re.sub(
            rf"\b{assertion_prefixes}\.\s*(?!(?:assert|assume|fail)\w*)",
            "",
            result,
        )

        return result
