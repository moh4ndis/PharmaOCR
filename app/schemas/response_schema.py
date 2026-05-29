"""Response models returned by extraction endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Structured extraction result for one uploaded image."""

    filename: str
    lot_number: str | None = None
    expiration_date: str | None = None
    manufacture_date: str | None = None
    raw_text: list[str] = Field(default_factory=list)
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Average OCR confidence across recognized text lines.",
    )


class BatchExtractionResponse(BaseModel):
    """Batch endpoint response containing one result per uploaded image."""

    results: list[ExtractionResult]

