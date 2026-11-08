"""Local filesystem storage for uploaded document binaries.

Files live under settings.document_storage_dir (DOCUMENT_STORAGE_DIR) with
server-controlled names: the SHA-256 content hash plus the validated original
suffix. Identical bytes therefore map to one file, and no client-supplied
path ever reaches the filesystem. Original filenames survive only as the
document title (ingest.generic.ingest_file).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass(frozen=True, slots=True)
class StoredFile:
    content_hash: str
    # Path relative to settings.document_storage_dir, as recorded in
    # source_documents.file_path.
    relative_path: str


def ensure_storage_dir() -> Path:
    root = Path(settings.document_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_document_bytes(content: bytes, suffix: str) -> StoredFile:
    """Store uploaded bytes under a content-hash name (idempotent)."""
    root = ensure_storage_dir()
    content_hash = hashlib.sha256(content).hexdigest()
    relative_path = f"{content_hash}{suffix}"
    path = root / relative_path
    if not path.exists():
        path.write_bytes(content)
    return StoredFile(content_hash=content_hash, relative_path=relative_path)


def resolve_stored_path(relative_path: str) -> Path:
    """Resolve a recorded file_path under the storage root, refusing escapes."""
    root = Path(settings.document_storage_dir).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Stored path escapes the document storage root: {relative_path!r}")
    return path
