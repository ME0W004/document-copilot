"""Tests for the POST /documents upload endpoint (mocked ingestion pipeline)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database.models import SourceDocument
from app.main import app
from ingest.generic import ConversionError, EmptyDocumentError, GenericIngestResult

TEST_USER = CurrentUser(id=uuid.uuid4(), email="analyst@example.com")
NOW = datetime(2026, 9, 11, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def storage_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "document_storage_dir", tmp_path / "documents")


def _result(**document_fields) -> GenericIngestResult:
    document = SourceDocument(
        id=uuid.uuid4(),
        title="Report",
        source_format="pdf",
        language="en",
        created_at=NOW,
        **document_fields,
    )
    return GenericIngestResult(
        document=document, chunks_written=4, deduplicated=False
    )


def test_upload_requires_authentication() -> None:
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post(
            "/documents", files={"file": ("report.pdf", b"%PDF-1.4 x")}
        )
    assert response.status_code == 401


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("notes.txt", b"plain text")},
    )
    assert response.status_code == 415
    assert "Unsupported file extension" in response.json()["detail"]


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/documents",
        files={"file": ("report.pdf", b"")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Uploaded file is empty"


def test_upload_rejects_oversized_file(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    response = client.post(
        "/documents",
        files={"file": ("report.pdf", b"%PDF-1.4 x")},
    )
    assert response.status_code == 413


def test_upload_rejects_content_that_contradicts_extension(
    client: TestClient, storage_dir
) -> None:
    response = client.post(
        "/documents",
        files={"file": ("report.pdf", b"definitely not a pdf")},
    )
    assert response.status_code == 415
    assert "does not match" in response.json()["detail"]


def test_upload_rejects_invalid_language(client: TestClient, storage_dir) -> None:
    response = client.post(
        "/documents",
        data={"language": "Farsi"},
        files={"file": ("report.pdf", b"%PDF-1.4 stub content")},
    )
    assert response.status_code == 422
    assert "language" in response.json()["detail"]


def test_upload_ingests_document(client: TestClient) -> None:
    with patch(
        "app.api.documents._ingest_stored", return_value=_result()
    ) as mocked:
        response = client.post(
            "/documents",
            data={"title": "Report", "language": "en"},
            files={"file": ("report.pdf", b"%PDF-1.4 x")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sourceFormat"] == "pdf"
    assert body["chunksWritten"] == 4
    assert body["deduplicated"] is False
    assert body["createdAt"] == NOW.isoformat().replace("+00:00", "Z")
    assert mocked.call_count == 1


def test_upload_returns_200_for_deduplicated_document(client: TestClient) -> None:
    deduplicated = GenericIngestResult(
        document=_result().document, chunks_written=0, deduplicated=True
    )
    with patch("app.api.documents._ingest_stored", return_value=deduplicated):
        response = client.post(
            "/documents", files={"file": ("report.pdf", b"%PDF-1.4 x")}
        )

    assert response.status_code == 200
    assert response.json()["deduplicated"] is True
    assert response.json()["chunksWritten"] == 0


def test_upload_maps_conversion_failure_to_422(client: TestClient, storage_dir) -> None:
    with patch(
        "app.api.documents._ingest_stored",
        side_effect=ConversionError("Conversion of report.pdf ended in failure"),
    ):
        response = client.post(
            "/documents", files={"file": ("report.pdf", b"%PDF-1.4 x")}
        )

    assert response.status_code == 422
    assert "ended in failure" in response.json()["detail"]


def test_upload_maps_empty_document_to_422(client: TestClient) -> None:
    with patch(
        "app.api.documents._ingest_stored",
        side_effect=EmptyDocumentError("Document converted but produced no extractable text."),
    ):
        response = client.post(
            "/documents", files={"file": ("report.pdf", b"%PDF-1.4 x")}
        )

    assert response.status_code == 422
    assert "no extractable text" in response.json()["detail"]
