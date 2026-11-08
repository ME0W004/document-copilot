"""Shared chunk persistence for SEC and generic ingestion.

Both ingestion paths (SEC HTML via chunk_and_embed, generic files via
ingest.generic) embed ChunkRecords and write document_chunks rows through
this module so transaction boundaries, search_text derivation, and
table-row persistence stay identical.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.models import DocumentChunk, DocumentTable, MessageCitation, SourceDocument
from app.text.normalize import normalize
from ingest.chunking import ChunkRecord
from ingest.embeddings import EMBED_BATCH_SIZE, embed_texts


def document_has_chunks(session: Session, document_id) -> bool:
    count = session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
    )
    return bool(count)


def delete_chunks(session: Session, document_id) -> None:
    chunk_ids = select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    session.execute(
        delete(MessageCitation).where(MessageCitation.chunk_id.in_(chunk_ids))
    )
    session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    session.execute(
        delete(DocumentTable).where(DocumentTable.document_id == document_id)
    )


def write_chunks(
    session: Session,
    document: SourceDocument,
    records: list[ChunkRecord],
) -> int:
    """Embed records, write document_chunks (+ document_tables), and commit.

    The caller's session commits exactly once here; any embedding or write
    failure leaves the session uncommitted so the caller can roll back the
    document row it added.
    """
    texts = [record.text for record in records]
    vectors = embed_texts(texts, batch_size=EMBED_BATCH_SIZE)
    document_tables = _document_tables_from_records(document.id, records)
    for table in document_tables:
        session.add(table)
    if document_tables:
        session.flush()
    table_ids_by_index = {table.table_index: str(table.id) for table in document_tables}

    for record, embedding in zip(records, vectors, strict=True):
        metadata = dict(record.chunk_metadata)
        table_index = metadata.get("table_index")
        if isinstance(table_index, int) and table_index in table_ids_by_index:
            metadata["table_id"] = table_ids_by_index[table_index]
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=record.chunk_index,
                page=record.page,
                section=record.section,
                text=record.text,
                search_text=normalize(record.text),
                embedding=embedding,
                token_count=record.token_count,
                chunk_metadata=metadata,
            )
        )

    session.commit()
    return len(records)


def _document_tables_from_records(
    document_id,
    records: list[ChunkRecord],
) -> list[DocumentTable]:
    tables_by_index: dict[int, DocumentTable] = {}
    for record in records:
        metadata = record.chunk_metadata
        if metadata.get("chunk_kind") != "table_row":
            continue
        table_data = metadata.get("table")
        table_index = metadata.get("table_index")
        if not isinstance(table_data, dict) or not isinstance(table_index, int):
            continue
        if table_index in tables_by_index:
            continue
        tables_by_index[table_index] = DocumentTable(
            document_id=document_id,
            table_index=table_index,
            title=table_data.get("title"),
            units=table_data.get("units"),
            markdown=table_data["markdown"],
            table_data=table_data,
            source_html_hash=table_data["source_html_hash"],
        )
    return list(tables_by_index.values())
