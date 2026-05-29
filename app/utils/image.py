"""Image upload validation and decoding helpers."""

from __future__ import annotations

import cv2
import numpy as np
from fastapi import UploadFile


class ImageValidationError(ValueError):
    """Raised when an uploaded file is not a supported image."""


ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


async def read_image_upload(file: UploadFile) -> np.ndarray:
    """Validate and decode an uploaded image into an OpenCV BGR array."""
    if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ImageValidationError(
            f"Unsupported file type '{file.content_type}'. "
            "Upload a JPEG, PNG, WEBP, BMP, or TIFF image."
        )

    content = await file.read()
    if not content:
        raise ImageValidationError("Uploaded file is empty.")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise ImageValidationError(f"Uploaded image exceeds the {max_mb} MB size limit.")

    image_array = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageValidationError("Uploaded file could not be decoded as an image.")

    return image

