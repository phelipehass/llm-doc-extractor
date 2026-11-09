"""Build evaluation cases from CUAD expert labels (atticusprojectai.org/cuad, CC BY 4.0).

Usage: python -m evaluation.make_cuad_cases ~/datasets/cuad/CUAD_v1 [n] [max_chars]

Picks the n shortest contracts (up to max_chars of text, to fit free-tier token limits) that
have labeled parties and a parseable effective date, copies their PDFs to evaluation/docs/ and
writes evaluation/cases.jsonl.

termination_notice_days is not scored: CUAD's "Notice Period To Terminate Renewal" is the
notice to stop an auto-renewal, a different concept.
"""

import csv
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent


def parse_parties(answer: str) -> list[str]:
    # 'PSiTech Corporation ("Licensor"); Empirical Ventures, Inc ("Licensee")'
    parties = (re.sub(r"\s*\([^)]*\)", "", p).strip(" .,") for p in answer.split(";"))
    return [p for p in parties if p]


def parse_date(answer: str) -> date | None:
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(answer.strip(), fmt).date()
        except ValueError:
            pass
    return None


def main(cuad_dir: str, n: str = "10", max_chars: str = "20000") -> None:
    root = Path(cuad_dir).expanduser()
    pdfs = {p.stem.casefold(): p for p in (root / "full_contract_pdf").rglob("*") if p.is_file()}
    candidates = []
    with open(root / "master_clauses.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stem = Path(row["Filename"]).stem
            txt = root / "full_contract_txt" / f"{stem}.txt"
            parties = parse_parties(row["Parties-Answer"])
            effective = parse_date(row["Effective Date-Answer"])
            law = row["Governing Law-Answer"].strip()
            if not (txt.exists() and stem.casefold() in pdfs and len(parties) >= 2 and effective):
                continue
            if ";" in law:  # several jurisdictions: ambiguous to score
                continue
            size = len(txt.read_text(encoding="utf-8", errors="ignore"))
            if 3_000 <= size <= int(max_chars):
                expected = {
                    "parties": parties,
                    "effective_date": effective.isoformat(),
                    "governing_law": law or None,
                }
                candidates.append((size, pdfs[stem.casefold()], expected))

    candidates.sort(key=lambda c: c[0])
    docs = HERE / "docs"
    docs.mkdir(exist_ok=True)
    with open(HERE / "cases.jsonl", "w", encoding="utf-8") as out:
        for size, pdf, expected in candidates[: int(n)]:
            shutil.copy(pdf, docs / pdf.name)
            out.write(json.dumps({"file": pdf.name, "expected": expected}) + "\n")
            print(f"{size:>6} chars  {pdf.name}")
    print(f"{min(int(n), len(candidates))} cases written ({len(candidates)} candidates)")


if __name__ == "__main__":
    main(*sys.argv[1:])
