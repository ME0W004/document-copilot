"""Pydantic models for the document upload/registration API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    title: str | None
    source_format: str = Field(alias="sourceFormat")
    language: str | None
    chunks_written: int = Field(default=0, alias="chunksWritten")
    deduplicated: bool = False
    created_at: datetime = Field(alias="createdAt")
