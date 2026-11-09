import json

import pytest

from app.extractor import ExtractionError, Message, Usage, extract

VALID = json.dumps(
    {
        "title": "Services Agreement",
        "parties": ["Acme Inc", "Globex LLC"],
        "effective_date": "2019-03-01",
        "governing_law": "Delaware",
        "term": "2 years",
        "termination_notice_days": 30,
        "payment_terms": "Net 30",
    }
)


def scripted(*replies: str):
    """Fake LLM that returns the given replies in order and records what it was sent."""
    calls: list[list[Message]] = []

    def complete(messages: list[Message]) -> tuple[str, Usage]:
        calls.append(list(messages))
        return replies[len(calls) - 1], Usage(prompt_tokens=100, completion_tokens=20)

    return complete, calls


def test_valid_output_is_parsed_on_first_attempt():
    complete, calls = scripted(VALID)

    result = extract("contract text", complete)

    assert result.attempts == 1
    assert result.fields.governing_law == "Delaware"
    assert str(result.fields.effective_date) == "2019-03-01"
    assert result.usage == Usage(100, 20)
    assert len(calls) == 1


def test_invalid_output_is_retried_with_the_validation_error():
    bad = json.dumps(
        {"parties": ["Acme"], "effective_date": "March 1st", "termination_notice_days": -5}
    )
    complete, calls = scripted(bad, VALID)

    result = extract("contract text", complete)

    assert result.attempts == 2
    assert result.usage == Usage(200, 40)
    feedback = calls[1][-1]["content"]
    assert "effective_date" in feedback and "termination_notice_days" in feedback


def test_gives_up_after_max_attempts():
    complete, _ = scripted("not json", "still not json")

    with pytest.raises(ExtractionError, match="2 attempts"):
        extract("contract text", complete)


def test_empty_text_fails_without_calling_the_model():
    complete, calls = scripted(VALID)

    with pytest.raises(ExtractionError, match="no extractable text"):
        extract("   \n ", complete)
    assert calls == []
