"""Publication-date parsing, reconciliation, and display conversion."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo


UTC = timezone.utc
HONG_KONG = ZoneInfo("Asia/Hong_Kong")


def _parse(value: object) -> tuple[datetime | None, str]:
    raw = str(value or "").strip()
    if not raw:
        return None, "MISSING"
    precision = "DATE" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else "DATETIME"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None, "INVALID"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC), precision


def _iso(value: datetime | None) -> str:
    return value.replace(microsecond=0).isoformat() if value else ""


def reconcile_dates(record: dict) -> dict:
    rss, rss_precision = _parse(record.get("published_utc") or record.get("rss_published_at"))
    article, article_precision = _parse(record.get("extracted_date") or record.get("article_published_at"))
    updated, _ = _parse(record.get("article_updated_at"))
    discrepancy = int(abs((rss - article).total_seconds())) if rss and article else None

    if rss and article:
        status = "CONSISTENT" if discrepancy <= 36 * 3600 else "CONFLICT"
        reason = (
            f"RSS and article dates differ by {discrepancy} seconds; "
            + ("within tolerance" if status == "CONSISTENT" else "sources conflict; RSS retained as monitoring timestamp")
        )
    elif rss:
        status = "RSS_ONLY"
        reason = "article publication date unavailable; using RSS timestamp"
    elif article:
        status = "ARTICLE_ONLY"
        reason = "RSS timestamp unavailable; using article publication date"
    else:
        status = "UNAVAILABLE"
        reason = "no parseable RSS or article publication date"

    chosen = rss or article
    return {
        "rss_published_at": _iso(rss),
        "article_published_at": _iso(article),
        "article_updated_at": _iso(updated),
        "published_at": _iso(chosen),
        "published_at_hong_kong": _iso(chosen.astimezone(HONG_KONG)) if chosen else "",
        "rss_date_precision": rss_precision,
        "article_date_precision": article_precision,
        "date_discrepancy_seconds": discrepancy,
        "date_validation_status": status,
        "date_validation_reason": reason,
    }

