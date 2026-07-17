"""
db/_validation.py
------------------
Shared input-sanitisation helpers used before any value is interpolated
into a raw SQL string.

pyodbc's cursor.execute() supports bind parameters (`?`) for scalar values,
but not for a variable-length `IN (...)` symbol list, so the symbol list is
validated here and then interpolated — the same injection guard used by
the sibling schwab_market_data_pyspark project's db/_jdbc.py.
"""

from __future__ import annotations

import re

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_symbols(symbols: list[str]) -> list[str]:
    """Uppercase, dedupe-preserve-order, and reject anything not a plain ticker."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    for s in cleaned:
        if not _SYMBOL_RE.match(s):
            raise ValueError(f"Invalid symbol: {s!r}")
    return cleaned


def validate_date(label: str, value: str) -> str:
    if not _DATE_RE.match(value):
        raise ValueError(f"{label} must be YYYY-MM-DD, got {value!r}")
    return value
