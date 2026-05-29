"""FastAPI application entrypoint for the Pharma OCR Extraction MVP."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.extract import router as extract_router


def configure_logging() -> None:
    """Configure basic structured-enough logging for local and container runs."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


configure_logging()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Pharma OCR Extraction API",
    description=(
        "MVP backend for extracting expiration dates, lot/batch numbers, "
        "and manufacture dates from pharmaceutical package images."
    ),
    version="0.1.0",
)

app.include_router(extract_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
async def web_ui() -> FileResponse:
    """Serve the lightweight OCR workbench UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Lightweight health endpoint for local checks and containers."""
    return {"status": "ok"}
