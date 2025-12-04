from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, RootModel, ValidationError

from prompt.prompt_template import PromptID

VerdictLiteral = Literal["VALID", "INVALID"]


class InvalidVerificationResponseError(ValueError):
    """Raised when an LLM response cannot be parsed as a verdict payload."""


class _SpecVerdictPayload(RootModel[dict[str, VerdictLiteral]]):
    root: dict[str, VerdictLiteral]


class VerificationVerdict(BaseModel):
    spec: str
    raw_spec: str
    verdict: VerdictLiteral
    model_id: str
    prompt_id: str
    raw_response: str


def _unwrap_json_candidate(response_text: str) -> str:
    """Remove common wrappers (e.g., code fences) around JSON payloads."""

    stripped = response_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove the opening fence
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        return candidate.strip()

    return stripped


def parse_verification_response(
    response_text: str,
    *,
    expected_spec: str,
    raw_spec: str,
    model_id: str,
    prompt_id: PromptID,
) -> list[VerificationVerdict]:
    """Parse a JSON response into one or more :class:`VerificationVerdict` entries."""

    cleaned = _unwrap_json_candidate(response_text)
    try:
        payload = _SpecVerdictPayload.model_validate_json(cleaned)
    except ValidationError as exc:
        raise InvalidVerificationResponseError(str(exc)) from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise InvalidVerificationResponseError(str(exc)) from exc

    if not payload.root:
        raise InvalidVerificationResponseError("Empty verification payload")

    verdicts: list[VerificationVerdict] = []
    for spec_from_llm, verdict_value in payload.root.items():
        normalized_spec = expected_spec
        verdicts.append(
            VerificationVerdict(
                spec=normalized_spec,
                raw_spec=raw_spec,
                verdict=verdict_value,
                model_id=model_id,
                prompt_id=prompt_id.name,
                raw_response=cleaned,
            )
        )

    return verdicts
