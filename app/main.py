from functools import lru_cache
from typing import Annotated, Any

import openai
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pypdf.errors import PdfReadError

from app.config import Settings, load_settings
from app.extractor import Complete, ExtractionError, extract
from app.llm import openai_compatible
from app.pdf import pdf_text

app = FastAPI(title="llm-doc-extractor", version="0.1.0")


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_complete() -> Complete:
    s = get_settings()
    if not s.api_key:
        raise RuntimeError("LLM_API_KEY is not set (copy .env.example to .env)")
    return openai_compatible(s.base_url, s.api_key, s.model)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract")
async def extract_contract(
    file: UploadFile,
    settings: Annotated[Settings, Depends(get_settings)],
    complete: Annotated[Complete, Depends(get_complete)],
) -> dict[str, Any]:
    if file.content_type != "application/pdf":
        raise HTTPException(415, "upload a PDF file")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"file exceeds {settings.max_upload_bytes} bytes")

    try:
        text = await run_in_threadpool(pdf_text, data)
    except (PdfReadError, ValueError) as exc:
        raise HTTPException(422, "could not read the PDF") from exc

    try:
        result = await run_in_threadpool(extract, text, complete)
    except ExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    except openai.APIError as exc:
        raise HTTPException(502, "LLM provider error, try again") from exc

    u = result.usage
    cost = (
        u.prompt_tokens * settings.price_in_per_m + u.completion_tokens * settings.price_out_per_m
    ) / 1_000_000
    return {
        "fields": result.fields.model_dump(mode="json"),
        "meta": {
            "model": settings.model,
            "attempts": result.attempts,
            "latency_ms": result.latency_ms,
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "estimated_cost_usd": round(cost, 6),
        },
    }
