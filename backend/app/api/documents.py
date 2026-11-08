"""Document upload/registration endpoint for generic (non-SEC) ingestion.

Authenticated users upload PDF/DOCX/HTML/image files; the original is stored
locally under a content-hash name (app.storage) and ingested synchronously
through the generic Docling pipeline (ingest.generic). Documents are a shared
corpus — the endpoint authenticates the uploader but does not attach
ownership, because source_documents has no user dimension and retrieval is
global (same as SEC filings).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database.session import get_session
from app.schemas.documents import DocumentResponse
from app.storage import resolve_stored_path, store_document_bytes
from ingest.formats import UnsupportedFormatError, format_for_suffix
from ingest.generic import (
    ConversionError,
    EmptyDocumentError,
    GenericIngestResult,
    ingest_file,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _ingest_stored(content: bytes, suffix: str, title: str | None, language: str | None, force: bool) -> GenericIngestResult:
    stored = store_document_bytes(content, suffix)
    file_path = resolve_stored_path(stored.relative_path)
    with get_session() as session:
        return ingest_file(
            session,
            file_path,
            relative_path=stored.relative_path,
            title=title,
            language=language,
            force=force,
        )


def _response_from(result: GenericIngestResult, *, deduplicated: bool) -> DocumentResponse:
    document = result.document
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_format=document.source_format,
        language=document.language,
        chunks_written=result.chunks_written,
        deduplicated=deduplicated,
        created_at=document.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    response: Response,
    title: str | None = Form(default=None),
    language: str | None = Form(default=None),
    force: bool = Query(default=False),
    _user: CurrentUser = Depends(get_current_user),
) -> DocumentResponse:
    try:
        suffix = format_for_suffix(Path(file.filename or "").suffix)
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb}MB upload limit",
        )

    try:
        result = await run_in_threadpool(
            _ingest_stored, content, suffix, title, language, force
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except (ConversionError, EmptyDocumentError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with identical content was registered concurrently",
        ) from exc

    if result.deduplicated:
        # Same content re-registered: nothing re-ingested.
        response.status_code = status.HTTP_200_OK
    return _response_from(result, deduplicated=result.deduplicated)
