import io
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

import app.main as main
from app.config import load_settings
from app.extractor import Usage
from tests.test_extractor import VALID


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def client():
    main.app.dependency_overrides[main.get_complete] = lambda: lambda _m: (VALID, Usage(10, 5))
    main.app.dependency_overrides[main.get_settings] = lambda: replace(
        load_settings(), max_upload_bytes=50_000, price_in_per_m=1.0, price_out_per_m=2.0
    )
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def upload(client, data: bytes, content_type: str = "application/pdf"):
    return client.post("/extract", files={"file": ("doc.pdf", data, content_type)})


def test_extracts_fields_and_reports_usage(client, monkeypatch):
    monkeypatch.setattr(main, "pdf_text", lambda _data: "This Services Agreement ...")

    response = upload(client, blank_pdf())

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["parties"] == ["Acme Inc", "Globex LLC"]
    assert body["meta"]["attempts"] == 1
    assert body["meta"]["estimated_cost_usd"] == pytest.approx((10 * 1 + 5 * 2) / 1_000_000)


def test_pdf_without_text_returns_422(client):
    response = upload(client, blank_pdf())

    assert response.status_code == 422
    assert "no extractable text" in response.json()["detail"]


def test_rejects_non_pdf(client):
    assert upload(client, b"hello", "text/plain").status_code == 415


def test_rejects_oversized_upload(client):
    assert upload(client, b"0" * 50_001).status_code == 413


def test_rejects_corrupt_pdf(client):
    assert upload(client, b"%PDF-1.4 garbage").status_code == 422
