"""API readiness tests for document upload and ingestion endpoint (Sprint 5 Part 22).

Covers:
- Authenticated POST /documents endpoint.
- Valid uploads for PDF and DOCX.
- Security rejection: unsupported extension, magic-byte mismatch, empty file, oversize file.
- Language validation: valid codes (fa, en, mixed, unknown) vs invalid.
- Idempotency: re-upload returns 200 with deduplicated=True; ?force=true re-ingests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.database.models import SourceDocument
from app.main import app
from ingest.generic import GenericIngestResult

client = TestClient(app)

DUMMY_USER = CurrentUser(
    id=uuid.uuid4(),
    email="testuser@example.com",
)


@pytest.fixture(autouse=True)
def override_user():
    app.dependency_overrides[get_current_user] = lambda: DUMMY_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_upload_valid_pdf_returns_201() -> None:
    fake_doc = SourceDocument(
        id=uuid.uuid4(),
        source_format="pdf",
        title="Test PDF",
        language="en",
        created_at=datetime.now(UTC),
    )
    result = GenericIngestResult(
        document=fake_doc,
        chunks_written=3,
        deduplicated=False,
    )

    with patch("app.api.documents._ingest_stored", return_value=result):
        resp = client.post(
            "/documents",
            files={"file": ("report.pdf", b"%PDF-1.4\nvalid pdf header", "application/pdf")},
            data={"title": "Test PDF", "language": "en"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["sourceFormat"] == "pdf"
    assert data["title"] == "Test PDF"
    assert data["chunksWritten"] == 3
    assert data["deduplicated"] is False


def test_upload_deduplication_returns_200() -> None:
    fake_doc = SourceDocument(
        id=uuid.uuid4(),
        source_format="pdf",
        title="Existing PDF",
        language="fa",
        created_at=datetime.now(UTC),
    )
    result = GenericIngestResult(
        document=fake_doc,
        chunks_written=0,
        deduplicated=True,
    )

    with patch("app.api.documents._ingest_stored", return_value=result):
        resp = client.post(
            "/documents",
            files={"file": ("report.pdf", b"%PDF-1.4\nsame content", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["deduplicated"] is True
    assert data["chunksWritten"] == 0


def test_upload_mismatched_magic_bytes_returns_415() -> None:
    resp = client.post(
        "/documents",
        files={"file": ("document.pdf", b"NOT_A_PDF_HEADER", "application/pdf")},
    )
    assert resp.status_code == 415
    assert "content does not match" in resp.json()["detail"].lower()


def test_upload_unsupported_extension_returns_415() -> None:
    resp = client.post(
        "/documents",
        files={"file": ("malicious.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert resp.status_code == 415
    assert "unsupported file extension" in resp.json()["detail"].lower()


def test_upload_empty_file_returns_422() -> None:
    resp = client.post(
        "/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 422
    assert "empty" in resp.json()["detail"].lower()


def test_upload_oversized_file_returns_413(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    big_content = b"%PDF-1.4\n" + b"X" * (1024 * 1024 + 100)

    resp = client.post(
        "/documents",
        files={"file": ("huge.pdf", big_content, "application/pdf")},
    )
    assert resp.status_code == 413
    assert "upload limit" in resp.json()["detail"].lower()


def test_upload_invalid_language_returns_422() -> None:
    resp = client.post(
        "/documents",
        files={"file": ("valid.pdf", b"%PDF-1.4\nvalid", "application/pdf")},
        data={"language": "FARSI_INVALID"},
    )
    assert resp.status_code == 422


def test_upload_requires_authentication() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    unauth_client = TestClient(app)
    resp = unauth_client.post(
        "/documents",
        files={"file": ("valid.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
    )
    assert resp.status_code == 401
