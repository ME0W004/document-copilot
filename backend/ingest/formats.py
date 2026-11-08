"""Format detection for multi-format ingestion.

Maps an uploaded/local file to a DocumentFormat using its extension, then
verifies content with magic bytes where a reliable signature exists (PDF, DOCX
zip containers, images). HTML has no usable signature, so the extension is
authoritative there. SEC filings never pass through here — they are resolved
via the manifest by accession number (ingest/chunking.py).
"""

from __future__ import annotations

import enum
from pathlib import Path


class UnsupportedFormatError(ValueError):
    """Raised when a file is not a supported ingestion format."""


class DocumentFormat(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    IMAGE = "image"


_MAGIC_CHECKS: dict[DocumentFormat, tuple[tuple[bytes, ...], int]] = {
    # PDF: "%PDF-" within the first bytes (some writers prepend junk).
    DocumentFormat.PDF: ((b"%PDF-",), 0),
    # DOCX is an OPC package: a ZIP local-file header at offset 0.
    DocumentFormat.DOCX: ((b"PK\x03\x04",), 0),
    # Images: signatures in the header.
    DocumentFormat.IMAGE: (
        (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"BM", b"II*\x00", b"MM\x00*", b"RIFF"),
        0,
    ),
}

_EXTENSIONS: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".docm": DocumentFormat.DOCX,
    ".dotx": DocumentFormat.DOCX,
    ".html": DocumentFormat.HTML,
    ".htm": DocumentFormat.HTML,
    ".xhtml": DocumentFormat.HTML,
    ".jpg": DocumentFormat.IMAGE,
    ".jpeg": DocumentFormat.IMAGE,
    ".png": DocumentFormat.IMAGE,
    ".tif": DocumentFormat.IMAGE,
    ".tiff": DocumentFormat.IMAGE,
    ".bmp": DocumentFormat.IMAGE,
    ".webp": DocumentFormat.IMAGE,
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSIONS)


def format_for_suffix(suffix: str) -> DocumentFormat:
    """Map a filename suffix (e.g. '.pdf') to its DocumentFormat."""
    fmt = _EXTENSIONS.get(suffix.lower())
    if fmt is None:
        raise UnsupportedFormatError(
            f"Unsupported file extension {suffix!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return fmt


def detect_format(path: Path) -> DocumentFormat:
    """Return the DocumentFormat for a file, verifying magic bytes.

    Raises UnsupportedFormatError for unknown extensions and for files whose
    content contradicts their extension (e.g. a renamed empty file).
    """
    fmt = format_for_suffix(path.suffix)
    checks = _MAGIC_CHECKS.get(fmt)
    if checks is not None:
        signatures, offset = checks
        header = path.open("rb").read(offset + max(len(sig) for sig in signatures))
        if not any(header[offset : offset + len(sig)] == sig for sig in signatures):
            raise UnsupportedFormatError(
                f"File content does not match {fmt.value} extension {path.suffix!r}."
            )
    return fmt
