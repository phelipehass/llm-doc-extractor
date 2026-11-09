# llm-doc-extractor

![CI](https://github.com/phelipehass/llm-doc-extractor/actions/workflows/ci.yml/badge.svg)

Extract **validated, structured fields** from contract PDFs with any OpenAI-compatible LLM
(Groq, OpenAI, OpenRouter, Ollama…), and **measure** how accurate the extraction is.

Most LLM extraction demos stop at "the model returned JSON". This one is built around the
parts that matter in production: strict validation, self-correcting retries, cost and
latency tracking, provider independence, and an evaluation you can rerun after every
prompt or model change.

## What it does

`POST /extract` with a PDF returns:

```json
{
  "fields": {
    "title": "Master Services Agreement",
    "parties": ["Acme Inc.", "Globex LLC"],
    "effective_date": "2019-03-01",
    "governing_law": "Delaware",
    "term": "2 years",
    "termination_notice_days": 30,
    "payment_terms": "Net 30 from invoice date"
  },
  "meta": {
    "model": "openai/gpt-oss-120b",
    "attempts": 1,
    "latency_ms": 1840,
    "prompt_tokens": 9120,
    "completion_tokens": 160,
    "estimated_cost_usd": 0.0
  }
}
```
*(Illustrative response shape.)*

## How it works

```
PDF ──► text (pypdf) ──► LLM, JSON mode, schema in the prompt
                              │
                              ▼
                  Pydantic validation ──✗──► errors fed back to the model, one retry
                              │✓
                              ▼
                   fields + tokens + cost + latency
```

- **Strict schema.** `app/schema.py` is the single source of truth: it generates the JSON
  schema sent to the model and validates the answer (ISO dates, non-negative integers…).
- **Self-correction.** When the output fails validation, the exact errors go back to the
  model ("effective_date: Input should be a valid date…") and it gets one more attempt.
  Failures surface as a clear `422`, never as silently wrong data.
- **"Never guess."** The prompt requires `null` for anything the contract doesn't state;
  the evaluation checks it.
- **Provider-agnostic.** The extraction core depends on one function signature
  (`Complete`), so switching providers is a config change, and every test runs offline
  with a fake model.
- **Cost-aware.** Every response reports token usage and an estimated cost.

## Quick start (free, with Groq)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # paste your Groq key: https://console.groq.com/keys
uvicorn app.main:app --reload
curl -F "file=@contract.pdf;type=application/pdf" http://localhost:8000/extract
```

Interactive docs: http://localhost:8000/docs

To use another provider, change `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`.

## Evaluation

Measured against expert lawyer labels from the
[CUAD dataset](https://www.atticusprojectai.org/cuad) (The Atticus Project, CC BY 4.0):
10 real commercial contracts filed with the SEC.

| Field | Accuracy | n |
|---|---|---|
| parties | 70% | 10 |
| effective_date | 100% | 10 |
| governing_law | 100% (incl. correctly returning `null` when no clause exists) | 10 |

Model `openai/gpt-oss-120b` on Groq's free tier · ~2.8 s per document · 0 failed documents.

**Error analysis.** All three `parties` misses trace back to the data, not the model:

- one label lists "EWSD 1, LLC … and Gridiron BioNutrients" as a third party (it is just
  the other two combined); the model returned the two real parties;
- one label merges "Food For Athletes, Inc./ Gridiron BioNutrients" into a single party;
  the model split it in two (a judgement call);
- one PDF has a garbled text layer ("PRIMEEVERG'CORPORATION"), copied by both the label
  and the model.

The scorer was deliberately **not** loosened to hide these.

**Eval-driven fix.** The first run scored 90% on `effective_date`: a contract effective
"as of the date below" had only signature dates, and the model (told never to guess)
returned `null` while the lawyers used the latest signature date. One prompt rule encoding
that convention took it to 100%.

`termination_notice_days` is not scored against CUAD: its closest label ("Notice Period
To Terminate Renewal") is the notice to stop an auto-renewal, a different concept.

Caveat: 10 short contracts (≤7k characters, chosen to fit the free tier's 8k tokens/minute)
is a smoke test, not a benchmark.

### Reproduce

```bash
# download CUAD_v1.zip from https://zenodo.org/records/4595826 and unzip it
python -m evaluation.make_cuad_cases ~/datasets/cuad/CUAD_v1 10   # writes cases.jsonl, copies PDFs
python -m evaluation.run evaluation/cases.jsonl 20                # 20 s pause per doc (free tier)
```

Misses are printed per document (expected vs. extracted). You can also write your own
`evaluation/cases.jsonl` (see `cases.example.jsonl`) with PDFs in `evaluation/docs/`.

## Tests

```bash
pytest
ruff check .
```

The tests cover parsing, the retry-with-feedback loop, giving up after the attempt limit,
empty/scanned PDFs, upload limits, corrupt files and cost math. No network calls.

## Project layout

```
app/schema.py      fields to extract (single source of truth)
app/extractor.py   prompt, validation and retry loop (provider-free)
app/llm.py         OpenAI-compatible client adapter
app/pdf.py         PDF → text
app/main.py        FastAPI: /extract, /health, error → status mapping
evaluation/run.py  accuracy measurement against labeled contracts
evaluation/make_cuad_cases.py  builds cases from CUAD expert labels
```

## Limitations

- Scanned PDFs (images) are rejected: there is no OCR step.
- Very long contracts are truncated at 60k characters rather than chunked. On Groq's free
  tier (8k tokens/minute) the practical limit is ~20k characters per document.
- One document type (commercial contracts). New document types mean a new schema.

## License

MIT
