import pytest

from app.config import settings
from app.storage import ensure_storage_dir, resolve_stored_path, store_document_bytes


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_dir", tmp_path / "documents")
    return tmp_path / "documents"


def test_store_document_bytes_uses_content_hash_name(storage_dir) -> None:
    stored = store_document_bytes(b"document bytes", ".pdf")

    assert len(stored.content_hash) == 64
    int(stored.content_hash, 16)  # hex digest
    assert stored.relative_path == f"{stored.content_hash}.pdf"
    assert (storage_dir / stored.relative_path).read_bytes() == b"document bytes"


def test_store_document_bytes_is_idempotent_for_identical_content(storage_dir) -> None:
    first = store_document_bytes(b"same bytes", ".pdf")
    path = storage_dir / first.relative_path
    path.write_bytes(b"tampered")

    second = store_document_bytes(b"same bytes", ".pdf")

    assert second.relative_path == first.relative_path
    assert path.read_bytes() == b"tampered"


def test_store_document_bytes_separates_different_content(storage_dir) -> None:
    first = store_document_bytes(b"one", ".pdf")
    second = store_document_bytes(b"two", ".pdf")
    assert first.relative_path != second.relative_path


def test_resolve_stored_path_joins_under_storage_root(storage_dir) -> None:
    path = resolve_stored_path("abc.pdf")
    assert path == (storage_dir / "abc.pdf").resolve()


def test_resolve_stored_path_rejects_path_traversal(storage_dir) -> None:
    with pytest.raises(ValueError, match="escapes"):
        resolve_stored_path("../outside.pdf")


def test_ensure_storage_dir_creates_missing_root(storage_dir) -> None:
    assert not storage_dir.exists()
    created = ensure_storage_dir()
    assert created.is_dir()
