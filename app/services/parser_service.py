"""Rule-based parser for pharmaceutical package OCR text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedPackageInfo:
    """Normalized pharmaceutical fields parsed from OCR text."""

    lot_number: str | None = None
    expiration_date: str | None = None
    manufacture_date: str | None = None


class ParserService:
    """Regex and heuristic parser for common pharma label patterns."""

    LOT_LABEL_RE = re.compile(
        r"\b(?:L[O0]T(?:\s*(?:NO|NUMBER|#))?|BATCH(?:\s*(?:NO|NUMBER|#))?|"
        r"B\.?\s*NO|B/N|BN)\b",
        re.IGNORECASE,
    )
    EXP_LABEL_RE = re.compile(
        r"\b(?:EXP(?:IRY|IRATION)?(?:\s*DATE)?|EXPIRES?|USE\s*BY|PER|EMP)\b",
        re.IGNORECASE,
    )
    MFG_LABEL_RE = re.compile(
        r"\b(?:DOM|FAB|MFG(?:\s*DATE)?|MFD(?:\s*DATE)?|MANUFACTURE(?:D)?(?:\s*DATE)?)\b",
        re.IGNORECASE,
    )

    LOT_VALUE_RE = re.compile(
        r"[:#\-\s]*([A-Z0-9](?:[A-Z0-9\-\s]{1,}[A-Z0-9])?)",
        re.IGNORECASE,
    )

    MONTH_YEAR_RE = re.compile(
        r"(?<!\d)(?P<month>0?[1-9]|1[0-2])\s*[/\-. ]\s*(?P<year>20\d{2}|\d{2})(?!\d)"
    )
    YEAR_MONTH_RE = re.compile(
        r"(?<!\d)(?P<year>20\d{2})\s*[/\-. ]\s*(?P<month>0?[1-9]|1[0-2])(?!\d)"
    )
    COMPACT_MONTH_YEAR_RE = re.compile(
        r"(?<!\d)(?P<month>0[1-9]|1[0-2])(?P<year>20\d{2})(?!\d)"
    )

    def parse(self, raw_text: list[str]) -> ParsedPackageInfo:
        """Parse normalized package fields from OCR text lines."""
        lines = [self._normalize_line(line) for line in raw_text if line.strip()]
        expiration_date = self._find_date_by_label(lines, self.EXP_LABEL_RE)

        return ParsedPackageInfo(
            lot_number=self._find_lot_number(lines),
            expiration_date=expiration_date or self._find_unlabeled_expiration_date(lines),
            manufacture_date=self._find_date_by_label(lines, self.MFG_LABEL_RE),
        )

    def _find_lot_number(self, lines: list[str]) -> str | None:
        fallback_candidates: list[str] = []

        for index, line in enumerate(lines):
            label_match = self.LOT_LABEL_RE.search(line)
            if not label_match:
                continue

            search_segments = [line[label_match.end() :]]
            if index > 0:
                search_segments.append(lines[index - 1])
            search_segments.extend(lines[index + 1 :])

            for segment in search_segments:
                if self.EXP_LABEL_RE.search(segment) or self.MFG_LABEL_RE.search(segment):
                    continue

                value = self._extract_lot_candidate(segment, allow_numeric=True)
                if value:
                    if any(char.isalpha() for char in value) and any(
                        char.isdigit() for char in value
                    ):
                        return value
                    fallback_candidates.append(value)

        if fallback_candidates:
            return fallback_candidates[0]

        return None

    def _find_date_by_label(self, lines: list[str], label_re: re.Pattern[str]) -> str | None:
        for index, line in enumerate(lines):
            label_match = label_re.search(line)
            if not label_match:
                continue

            search_segments = [line[label_match.end() :], line]
            if index + 1 < len(lines):
                search_segments.append(f"{line} {lines[index + 1]}")
            if index + 2 < len(lines):
                search_segments.append(f"{line} {lines[index + 1]} {lines[index + 2]}")

            for segment in search_segments:
                parsed_date = self._extract_date(segment)
                if parsed_date:
                    return parsed_date

        return None

    def _find_unlabeled_expiration_date(self, lines: list[str]) -> str | None:
        """Use standalone month/year dates as expiration fallback for MVP labels."""
        for line in lines:
            if self.MFG_LABEL_RE.search(line):
                continue

            parsed_date = self._extract_date(line)
            if parsed_date:
                return parsed_date

        return None

    def _extract_lot_candidate(self, segment: str, *, allow_numeric: bool = False) -> str | None:
        match = self.LOT_VALUE_RE.search(segment)
        if not match:
            return None

        candidate = re.sub(r"[^A-Z0-9]", "", match.group(1).upper())
        if len(candidate) < 3:
            return None
        if candidate.isdigit() and (not allow_numeric or len(candidate) < 4):
            return None
        if not any(char.isdigit() for char in candidate):
            return None
        if self._extract_date(candidate):
            return None
        if candidate in {"LOT", "BATCH", "EXP", "MFG", "DOM", "DATE"}:
            return None

        return candidate

    def _extract_date(self, text: str) -> str | None:
        # OCR often reads zero as O inside date strings.
        normalized = text.upper().replace("O", "0")

        for regex in (self.MONTH_YEAR_RE, self.YEAR_MONTH_RE, self.COMPACT_MONTH_YEAR_RE):
            match = regex.search(normalized)
            if match:
                return self._format_year_month(
                    year=match.group("year"),
                    month=match.group("month"),
                )

        return None

    @staticmethod
    def _format_year_month(year: str, month: str) -> str | None:
        if len(year) == 2:
            year = f"20{year}"

        month_int = int(month)
        if not 1 <= month_int <= 12:
            return None

        return f"{year}-{month_int:02d}"

    @staticmethod
    def _normalize_line(line: str) -> str:
        cleaned = line.strip().upper()
        cleaned = cleaned.replace("：", ":").replace("|", " ")
        return " ".join(cleaned.split())
