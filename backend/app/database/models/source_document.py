from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, UniqueConstraint, text as sql_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.document_table import DocumentTable


class SourceDocument(Base, TimestampMixin):
    """Registered document stored for chunking, retrieval, and citation.

    Two shapes share this table. SEC filings (source_format="sec_html") fill
    the SEC-specific columns (ticker, cik, form, filing_date, accession_number,
    primary_document, source_url). Generic documents (source_format="pdf" |
    "docx" | "html" | "image") carry title/language/file_path instead and must
    not invent SEC metadata; the SEC columns are nullable for them.
    """

    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_source_documents_accession_number"),
        Index("ix_source_documents_ticker_fiscal_year", "ticker", "fiscal_year"),
        Index(
            "uq_source_documents_content_hash",
            "content_hash",
            unique=True,
            postgresql_where=sql_text("content_hash IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # SEC-specific identity; nullable for generic documents.
    ticker: Mapped[str | None] = mapped_column(String(16))
    cik: Mapped[str | None] = mapped_column(String(10))
    company_name: Mapped[str | None] = mapped_column(String(255))
    form: Mapped[str | None] = mapped_column(String(16))
    filing_date: Mapped[date | None] = mapped_column(Date)
    report_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    accession_number: Mapped[str | None] = mapped_column(String(32))
    primary_document: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    # Generic document metadata (SEC rows keep NULL here except source_format).
    title: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16))
    source_format: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="sec_html", default="sec_html"
    )
    # Stored file path relative to settings.document_storage_dir; SEC filings
    # stay resolved via the manifest and leave this NULL.
    file_path: Mapped[str | None] = mapped_column(Text)
    # SHA-256 of the stored file bytes; deterministic dedup identity.
    content_hash: Mapped[str | None] = mapped_column(String(64))
    markdown_content: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tables: Mapped[list[DocumentTable]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
