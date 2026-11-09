from openai import OpenAI

from app.extractor import Complete, Message, Usage


def openai_compatible(base_url: str, api_key: str, model: str) -> Complete:
    """Works with Groq, OpenAI, OpenRouter, Ollama or any OpenAI-compatible endpoint."""
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=60, max_retries=2)

    def complete(messages: list[Message]) -> tuple[str, Usage]:
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            response_format={"type": "json_object"},
        )
        u = response.usage
        usage = Usage(u.prompt_tokens, u.completion_tokens) if u else Usage()
        return response.choices[0].message.content or "", usage

    return complete
