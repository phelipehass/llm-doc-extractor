"""Measure extraction accuracy against hand-labeled contracts.

Usage: python -m evaluation.run [evaluation/cases.jsonl] [pause_seconds]

Each line of the cases file: {"file": "name.pdf", "expected": {<field>: <value>, ...}}
PDFs live in evaluation/docs/. Only the fields present in "expected" are scored.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

from app.config import load_settings
from app.extractor import ExtractionError, extract
from app.llm import openai_compatible
from app.pdf import pdf_text
from app.schema import ContractFields

SCORED = ("parties", "effective_date", "governing_law", "termination_notice_days")
DOCS = Path(__file__).parent / "docs"


def _norm(value: Any) -> str:
    return " ".join(str(value).casefold().replace(",", " ").replace(".", " ").split())


def _same_party(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    return a in b or b in a  # "Acme Inc" matches "Acme Inc, a Delaware corporation"


def score(expected: dict[str, Any], got: ContractFields) -> dict[str, bool]:
    actual = got.model_dump(mode="json")
    result: dict[str, bool] = {}
    for field in SCORED:
        if field not in expected:
            continue
        want, have = expected[field], actual[field]
        if field == "parties":
            result[field] = len(want) == len(have) and all(
                any(_same_party(w, h) for h in have) for w in want
            )
        elif field == "governing_law":
            result[field] = (want is None and have is None) or (
                want is not None and have is not None and _norm(want) in _norm(have)
            )
        else:
            result[field] = want == have
    return result


def main(cases_path: str = "evaluation/cases.jsonl", pause_seconds: str = "0") -> None:
    s = load_settings()
    complete = openai_compatible(s.base_url, s.api_key, s.model)
    hits: dict[str, list[bool]] = {f: [] for f in SCORED}
    latencies: list[int] = []
    tokens = failures = 0

    for line in Path(cases_path).read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        time.sleep(float(pause_seconds))  # stay under per-minute token limits on free tiers
        try:
            result = extract(pdf_text((DOCS / case["file"]).read_bytes()), complete)
        except ExtractionError as exc:
            failures += 1
            print(f"FAIL {case['file']}: {exc}", file=sys.stderr)
            continue
        latencies.append(result.latency_ms)
        tokens += result.usage.prompt_tokens + result.usage.completion_tokens
        got = result.fields.model_dump(mode="json")
        for field, ok in score(case["expected"], result.fields).items():
            hits[field].append(ok)
            if not ok:
                want = case["expected"][field]
                print(
                    f"MISS {case['file'][:50]} {field}: want={want!r} got={got[field]!r}",
                    file=sys.stderr,
                )

    print(f"Model: `{s.model}`\n\n| Field | Accuracy | n |\n|---|---|---|")
    for field, oks in hits.items():
        if oks:
            print(f"| {field} | {sum(oks) / len(oks):.0%} | {len(oks)} |")
    if latencies:
        print(f"\nAvg latency: {sum(latencies) // len(latencies)} ms · total tokens: {tokens}")
    print(f"Failed documents: {failures}")


if __name__ == "__main__":
    main(*sys.argv[1:])
