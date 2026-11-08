from pathlib import Path

import pytest

from ingest.formats import DocumentFormat, UnsupportedFormatError, detect_format, format_for_suffix

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        (".pdf", DocumentFormat.PDF),
        (".PDF", DocumentFormat.PDF),
        (".docx", DocumentFormat.DOCX),
        (".html", DocumentFormat.HTML),
        (".htm", DocumentFormat.HTML),
        (".png", DocumentFormat.IMAGE),
        (".jpg", DocumentFormat.IMAGE),
        (".webp", DocumentFormat.IMAGE),
    ],
)
def test_format_for_suffix_maps_supported_extensions(suffix: str, expected: DocumentFormat) -> None:
    assert format_for_suffix(suffix) is expected


@pytest.mark.parametrize("suffix", [".txt", ".md", ".exe", ""])
def test_format_for_suffix_rejects_unsupported_extensions(suffix: str) -> None:
    with pytest.raises(UnsupportedFormatError):
        format_for_suffix(suffix)


def test_detect_format_accepts_matching_fixtures() -> None:
    assert detect_format(FIXTURES / "sample.pdf") is DocumentFormat.PDF
    assert detect_format(FIXTURES / "sample.docx") is DocumentFormat.DOCX
    assert detect_format(FIXTURES / "sample.png") is DocumentFormat.IMAGE


def test_detect_format_rejects_content_that_contradicts_extension(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_text("this is not a pdf", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError, match="does not match pdf"):
        detect_format(fake_pdf)


def test_detect_format_rejects_empty_file_with_supported_extension(tmp_path: Path) -> None:
    empty_docx = tmp_path / "empty.docx"
    empty_docx.write_bytes(b"")
    with pytest.raises(UnsupportedFormatError):
        detect_format(empty_docx)


def test_detect_format_accepts_html_by_extension(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text("<html><body>hi</body></html>", encoding="utf-8")
    assert detect_format(html) is DocumentFormat.HTML
