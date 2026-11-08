"""add generic document metadata for multi-format ingestion

Revision ID: e9f2b3c8d4a1
Revises: b8e3d5a1f4c2
Create Date: 2026-09-11 00:00:00.000000

Extends the SEC-shaped source_documents table so generic documents (PDF, DOCX,
HTML, image) can be registered without fake SEC metadata:

- source_format distinguishes "sec_html" (default, applied to all existing
  rows) from the generic formats; NOT NULL with a constant default, so the
  add is metadata-only (no table rewrite).
- title / language / file_path / content_hash describe generic documents.
  file_path is relative to settings.document_storage_dir; content_hash
  (SHA-256 of the stored bytes) is the deterministic dedup identity, unique
  via a partial index (NULLs — i.e. SEC rows — are exempt).
- SEC identity columns become nullable; existing SEC rows are untouched.
- message_citations mirrors the nullable display metadata (ticker/form/
  filing_date) and gains title, because citations of generic documents have
  no SEC metadata to snapshot.

Downgrade restores NOT NULL on the SEC columns and will fail if generic
documents/citations already exist — reverting after real generic ingestion is
not a supported path.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e9f2b3c8d4a1"
down_revision: Union[str, Sequence[str], None] = "b8e3d5a1f4c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE_SEC_COLUMNS = (
    "ticker",
    "cik",
    "form",
    "filing_date",
    "accession_number",
    "primary_document",
    "source_url",
)


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column(
            "source_format",
            sa.String(length=32),
            nullable=False,
            server_default="sec_html",
        ),
    )
    op.add_column(
        "source_documents", sa.Column("title", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "source_documents", sa.Column("language", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "source_documents", sa.Column("file_path", sa.Text(), nullable=True)
    )
    op.add_column(
        "source_documents", sa.Column("content_hash", sa.String(length=64), nullable=True)
    )
    op.create_index(
        "uq_source_documents_content_hash",
        "source_documents",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )

    for column in _NULLABLE_SEC_COLUMNS:
        op.alter_column("source_documents", column, nullable=True)

    op.add_column(
        "message_citations", sa.Column("title", sa.String(length=255), nullable=True)
    )
    op.alter_column("message_citations", "ticker", nullable=True)
    op.alter_column("message_citations", "form", nullable=True)
    op.alter_column("message_citations", "filing_date", nullable=True)


def downgrade() -> None:
    op.alter_column("message_citations", "filing_date", nullable=False)
    op.alter_column("message_citations", "form", nullable=False)
    op.alter_column("message_citations", "ticker", nullable=False)
    op.drop_column("message_citations", "title")

    for column in _NULLABLE_SEC_COLUMNS:
        op.alter_column("source_documents", column, nullable=False)

    op.drop_index("uq_source_documents_content_hash", table_name="source_documents")
    op.drop_column("source_documents", "content_hash")
    op.drop_column("source_documents", "file_path")
    op.drop_column("source_documents", "language")
    op.drop_column("source_documents", "title")
    op.drop_column("source_documents", "source_format")
