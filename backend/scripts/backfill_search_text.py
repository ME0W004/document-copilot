"""Backfill document_chunks.search_text with normalize(text).

Populates the derived normalized search representation for chunks written
before Sprint 2. Idempotent: rows whose search_text already equals the
canonical normalizer output are skipped, so the script can be re-run safely.

Never modifies `text`, embeddings, or citations; needs no OpenAI access.
The generated search_vector column updates automatically as rows change.

Usage (from backend/):
    uv run python -m scripts.backfill_search_text [--batch-size 500] [--dry-run]
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import DocumentChunk
from app.text.normalize import normalize

DEFAULT_BATCH_SIZE = 500


def backfill_search_text(
    session: Session,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Populate search_text = normalize(text). Returns (updated, already_ok)."""
    updated = 0
    already_ok = 0
    last_id = None

    while True:
        stmt = (
            select(DocumentChunk.id, DocumentChunk.text, DocumentChunk.search_text)
            .order_by(DocumentChunk.id)
            .limit(batch_size)
        )
        if last_id is not None:
            stmt = stmt.where(DocumentChunk.id > last_id)
        rows = session.execute(stmt).all()
        if not rows:
            break

        pending: list[dict] = []
        for chunk_id, text, search_text in rows:
            last_id = chunk_id
            normalized = normalize(text)
            if search_text == normalized:
                already_ok += 1
                continue
            pending.append({"id": chunk_id, "search_text": normalized})

        if pending and not dry_run:
            session.execute(update(DocumentChunk), pending)
            session.commit()
        updated += len(pending)
        print(f"  batch: {len(pending)} to update, {len(rows)} scanned (last_id={last_id})")

    return updated, already_ok


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Rows per database batch (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report without writing",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    engine = create_engine(settings.sqlalchemy_database_url)

    with Session(engine) as session:
        updated, already_ok = backfill_search_text(
            session,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

    mode = "would update (dry-run)" if args.dry_run else "updated"
    print(f"Done: {mode} {updated} row(s), {already_ok} already correct")


if __name__ == "__main__":
    main()
