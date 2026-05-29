"""REST endpoint for single-image OCR extraction."""

from __future__ import annotations

import logging

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.schemas.response_schema import ExtractionResult
from app.services.ocr_service import OCRService, OCRServiceError
from app.services.parser_service import ParserService
from app.services.preprocess_service import PreprocessService
from app.utils.image import ImageValidationError, read_image_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extraction"])

preprocess_service = PreprocessService()
ocr_service = OCRService()
parser_service = ParserService()

def _process_image(image: np.ndarray, filename: str) -> ExtractionResult:
    """Run preprocessing, OCR, parsing, and response assembly for one image."""
    processed_image = preprocess_service.preprocess(image)
    ocr_result = ocr_service.extract_text(processed_image)
    parsed = parser_service.parse(ocr_result.raw_text)

    return ExtractionResult(
        filename=filename,
        lot_number=parsed.lot_number,
        expiration_date=parsed.expiration_date,
        manufacture_date=parsed.manufacture_date,
        raw_text=ocr_result.raw_text,
        confidence=ocr_result.average_confidence,
    )


async def _read_and_process_upload(file: UploadFile) -> ExtractionResult:
    filename = file.filename or "upload"

    try:
        image = await read_image_upload(file)
        return await run_in_threadpool(_process_image, image, filename)
    except ImageValidationError as exc:
        logger.info("Rejected image upload %s: %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except OCRServiceError as exc:
        logger.exception("OCR processing failed for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - final guardrail for API safety
        logger.exception("Unexpected extraction failure for %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected extraction failure.",
        ) from exc


@router.post("/single", response_model=ExtractionResult)
async def extract_single(file: UploadFile = File(...)) -> ExtractionResult:
    """Extract package fields from a single uploaded image."""
    return await _read_and_process_upload(file)
