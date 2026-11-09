import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import ValidationError

from app.schema import ContractFields

Message = dict[str, str]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


# Any function that sends chat messages to an LLM and returns (raw text, token usage).
# Keeping the provider behind this one signature is what makes the core testable offline.
Complete = Callable[[list[Message]], tuple[str, Usage]]


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class Extraction:
    fields: ContractFields
    attempts: int
    usage: Usage
    latency_ms: int


SYSTEM_PROMPT = f"""You extract facts from legal contracts.
Reply with ONE JSON object and nothing else, matching this JSON schema:
{json.dumps(ContractFields.model_json_schema())}

Rules:
- Use null (or [] for parties) when the contract does not state the value. Never guess.
- Dates must be YYYY-MM-DD.
- If the contract is effective "as of the date below" or upon signature, effective_date
  is the latest signature date.
- termination_notice_days is an integer number of days (convert "thirty (30) days", "1 month" = 30).
- parties are the legal names of the contracting entities, as written."""

# shortcut: long contracts are truncated, not chunked; add chunking when docs exceed the context.
MAX_CHARS = 60_000


def extract(text: str, complete: Complete, max_attempts: int = 2) -> Extraction:
    if not text.strip():
        raise ExtractionError("document has no extractable text (scanned PDF? OCR not supported)")

    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text[:MAX_CHARS]},
    ]
    prompt_tokens = completion_tokens = 0
    start = time.perf_counter()

    for attempt in range(1, max_attempts + 1):
        raw, usage = complete(messages)
        prompt_tokens += usage.prompt_tokens
        completion_tokens += usage.completion_tokens
        try:
            fields = ContractFields.model_validate_json(raw)
        except ValidationError as exc:
            # Feed the validation errors back so the model can fix its own output.
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
            )
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": f"That JSON is invalid ({problems}). "
                    "Reply again with only the corrected JSON object.",
                },
            ]
            continue
        return Extraction(
            fields=fields,
            attempts=attempt,
            usage=Usage(prompt_tokens, completion_tokens),
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    raise ExtractionError(f"model output failed validation after {max_attempts} attempts")
