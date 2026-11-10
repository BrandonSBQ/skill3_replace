"""Encoding-safe console text for Windows code pages."""
from __future__ import annotations

import sys


def console_safe(value: object, encoding: str | None = None) -> str:
    text = str(value)
    target = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(target)
        return text
    except (UnicodeEncodeError, LookupError):
        return text.encode(target, errors="backslashreplace").decode(target, errors="strict")

