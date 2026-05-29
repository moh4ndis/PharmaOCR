"""OpenCV preprocessing for OCR-friendly package images."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class PreprocessConfig:
    """Tunable preprocessing settings kept in one place for MVP extension."""

    resize_enabled: bool = True
    max_side: int = 1600
    denoise_strength: int = 10
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple[int, int] = (8, 8)


class PreprocessService:
    """Applies lightweight OpenCV image cleanup before OCR."""

    def __init__(self, config: PreprocessConfig | None = None) -> None:
        self.config = config or PreprocessConfig()

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Return a preprocessed BGR image suitable for PaddleOCR."""
        resized = self._resize_if_needed(image)
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(
            grayscale,
            None,
            h=self.config.denoise_strength,
            templateWindowSize=7,
            searchWindowSize=21,
        )
        enhanced = self._enhance_contrast(denoised)

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        if not self.config.resize_enabled:
            return image

        height, width = image.shape[:2]
        longest_side = max(height, width)
        if longest_side <= self.config.max_side:
            return image

        scale = self.config.max_side / float(longest_side)
        new_size = (int(width * scale), int(height * scale))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    def _enhance_contrast(self, grayscale: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_tile_grid_size,
        )
        return clahe.apply(grayscale)

