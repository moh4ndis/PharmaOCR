"""Standard PaddleOCR integration layer.

This module intentionally hides PaddleOCR-specific result shapes from the
application. The rest of the API only deals with text lines and confidence
scores, which keeps future OCR swaps or upgrades contained here.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

logger = logging.getLogger(__name__)


class OCRServiceError(RuntimeError):
    """Raised when the OCR engine cannot initialize or run."""


@dataclass(frozen=True)
class OCRTextLine:
    """One recognized text line with its OCR confidence."""

    text: str
    confidence: float


@dataclass(frozen=True)
class OCRExtraction:
    """Normalized OCR output consumed by parser and API layers."""

    lines: list[OCRTextLine]

    @property
    def raw_text(self) -> list[str]:
        return [line.text for line in self.lines]

    @property
    def average_confidence(self) -> float | None:
        if not self.lines:
            return None

        confidence = sum(line.confidence for line in self.lines) / len(self.lines)
        return round(confidence, 4)


class OCRService:
    """Lazy-loaded standard PaddleOCR service with safe single-process inference."""

    def __init__(self) -> None:
        self._ocr: Any | None = None
        self._api_mode: str | None = None
        self._init_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def extract_text(self, image: np.ndarray) -> OCRExtraction:
        """Run PaddleOCR and normalize the result into text lines."""
        engine = self._get_engine()

        try:
            with self._inference_lock:
                raw_result = self._run_engine(engine, image)
        except Exception as exc:  # pragma: no cover - depends on Paddle runtime
            raise OCRServiceError("OCR inference failed.") from exc

        lines = self._extract_lines(raw_result)
        logger.info("OCR extracted %d text lines", len(lines))
        return OCRExtraction(lines=lines)

    def _get_engine(self) -> Any:
        if self._ocr is not None:
            return self._ocr

        with self._init_lock:
            if self._ocr is not None:
                return self._ocr

            self._ocr = self._build_engine()
            logger.info("PaddleOCR initialized using %s configuration", self._api_mode)
            return self._ocr

    def _build_engine(self) -> Any:
        try:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PaddleOCR
        except Exception as exc:  # pragma: no cover - import depends on install
            raise OCRServiceError(
                "PaddleOCR is not installed or failed to import. "
                "Install the project dependencies with `uv sync`."
            ) from exc

        v3_kwargs: dict[str, Any] = {
            "device": "cpu",
            "enable_mkldnn": False,
            "cpu_threads": int(os.getenv("PADDLEOCR_CPU_THREADS", "4")),
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": True,
        }
        detection_model = os.getenv("PADDLEOCR_DET_MODEL")
        recognition_model = os.getenv("PADDLEOCR_REC_MODEL")
        if detection_model or recognition_model:
            v3_kwargs["text_detection_model_name"] = (
                detection_model or "PP-OCRv5_mobile_det"
            )
            v3_kwargs["text_recognition_model_name"] = (
                recognition_model or "en_PP-OCRv5_mobile_rec"
            )
        else:
            v3_kwargs["lang"] = "en"
            v3_kwargs["ocr_version"] = os.getenv("PADDLEOCR_VERSION", "PP-OCRv5")

        # PaddleOCR 3.x renamed angle classification to text-line orientation.
        # PaddleOCR 2.x uses use_angle_cls and cls=True at inference time.
        attempts: tuple[tuple[str, dict[str, Any]], ...] = (
            ("paddleocr-v3", v3_kwargs),
            (
                "paddleocr-v2",
                {
                    "lang": "en",
                    "use_angle_cls": True,
                    "show_log": False,
                },
            ),
        )

        errors: list[str] = []
        for mode, kwargs in attempts:
            try:
                self._api_mode = mode
                return PaddleOCR(**kwargs)
            except TypeError as exc:
                errors.append(f"{mode}: {exc}")
                continue
            except Exception as exc:  # pragma: no cover - depends on Paddle runtime
                raise OCRServiceError("PaddleOCR initialization failed.") from exc

        raise OCRServiceError(
            "PaddleOCR initialization failed because no supported constructor "
            f"matched this installed version: {'; '.join(errors)}"
        )

    def _run_engine(self, engine: Any, image: np.ndarray) -> Any:
        if hasattr(engine, "predict"):
            try:
                return engine.predict(image)
            except TypeError:
                return engine.predict(input=image)

        if hasattr(engine, "ocr"):
            return engine.ocr(image, cls=True)

        raise OCRServiceError("Installed PaddleOCR engine has no supported API.")

    def _extract_lines(self, raw_result: Any) -> list[OCRTextLine]:
        lines = self._extract_v3_lines(raw_result)
        if not lines:
            lines = self._extract_v2_lines(raw_result)

        cleaned: list[OCRTextLine] = []
        for line in lines:
            text = " ".join(line.text.strip().split())
            if text:
                cleaned.append(OCRTextLine(text=text, confidence=line.confidence))

        return cleaned

    def _extract_v3_lines(self, raw_result: Any) -> list[OCRTextLine]:
        lines: list[OCRTextLine] = []

        for item in self._as_iterable(raw_result):
            payload = self._result_to_mapping(item)
            if not payload:
                continue

            result = payload.get("res", payload)
            if not isinstance(result, dict):
                continue

            texts = self._coerce_sequence(
                self._first_present(result, ("rec_texts", "texts", "ocr_texts", "text"))
            )
            scores = self._coerce_sequence(
                self._first_present(
                    result,
                    ("rec_scores", "scores", "confidences", "confidence"),
                )
            )

            for index, text in enumerate(texts):
                if not isinstance(text, str):
                    continue

                confidence = self._safe_float(scores[index] if index < len(scores) else 1.0)
                lines.append(OCRTextLine(text=text, confidence=confidence))

        return lines

    def _extract_v2_lines(self, raw_result: Any) -> list[OCRTextLine]:
        lines: list[OCRTextLine] = []

        def walk(node: Any) -> None:
            if self._looks_like_v2_line(node):
                text, confidence = node[1][0], self._safe_float(node[1][1])
                lines.append(OCRTextLine(text=str(text), confidence=confidence))
                return

            if isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)

        walk(raw_result)
        return lines

    @staticmethod
    def _looks_like_v2_line(node: Any) -> bool:
        return (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and isinstance(node[1], (list, tuple))
            and len(node[1]) >= 2
            and isinstance(node[1][0], str)
        )

    @staticmethod
    def _as_iterable(value: Any) -> Iterable[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return value
        return [value]

    @staticmethod
    def _coerce_sequence(value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    @staticmethod
    def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value is not None:
                return value
        return None

    @staticmethod
    def _result_to_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        for attr in ("to_dict", "dict"):
            method = getattr(value, attr, None)
            if callable(method):
                result = method()
                if isinstance(result, dict):
                    return result

        json_attr = getattr(value, "json", None)
        if json_attr is not None:
            result = json_attr() if callable(json_attr) else json_attr
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    return parsed
            if isinstance(result, dict):
                return result

        return getattr(value, "__dict__", {}) if hasattr(value, "__dict__") else {}

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 1.0

        return max(0.0, min(confidence, 1.0))
