"""add search_text and normalized search_vector

Revision ID: b8e3d5a1f4c2
Revises: d2e4b7a9c1f3
Create Date: 2026-09-10 00:00:00.000000

Adds the derived normalized search representation `document_chunks.search_text`
(app-level `normalize(text)`, backfilled by backend/scripts/backfill_search_text.py)
and repoints the generated `search_vector` at it. The FTS configuration stays
'english' on both sides: the english snowball stemmer leaves non-ASCII (Persian)
tokens unchanged and english.stop contains no Persian words, so 'english' and
'simple' behave identically for Persian while 'english' preserves the existing
English stemming and query-side stopword removal.

The FTS config 'english' cannot be switched to a Postgres-native Persian
configuration (none ships with Postgres); Persian matching comes from the
application-level normalization, not from the dictionary.

pg_trgm and a GIN trigram index on search_text are created here for a future
fuzzy/OCR retrieval sprint; no query uses them yet.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8e3d5a1f4c2"
down_revision: Union[str, Sequence[str], None] = "d2e4b7a9c1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("ALTER TABLE document_chunks ADD COLUMN search_text TEXT")

    # Generated columns cannot be altered in place: drop and re-add. The old
    # GIN index lives on search_vector and goes down with the column, but it
    # is dropped explicitly first for clarity.
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector_gin")
    op.execute("ALTER TABLE document_chunks DROP COLUMN search_vector")
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_text, text))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_search_vector_gin
        ON document_chunks
        USING gin (search_vector)
        """
    )

    # Supplementary lexical capability for a later fuzzy/OCR sprint; unused by
    # the current tsquery-based retrieval (see docs/sprint-2-persian-retrieval.md).
    op.execute(
        """
        CREATE INDEX ix_document_chunks_search_text_trgm
        ON document_chunks
        USING gin (search_text gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector_gin")
    op.execute("ALTER TABLE document_chunks DROP COLUMN search_vector")
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_chunks_search_vector_gin
        ON document_chunks
        USING gin (search_vector)
        """
    )
    op.execute("ALTER TABLE document_chunks DROP COLUMN search_text")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
