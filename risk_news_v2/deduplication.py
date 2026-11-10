"""Source-article and conservative event deduplication."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .profiles import normalize


TRACKING_PARAMS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "oc", "ref", "referrer", "source",
}
STOPWORDS = {
    "about", "after", "against", "amid", "company", "from", "into", "over", "said", "that", "the", "their",
    "this", "with", "would", "opens", "opened", "investigated", "investigation", "regulator", "regulatory",
}


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return ""
    if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
        return ""
    scheme = parts.scheme.casefold()
    host = parts.hostname.casefold()
    port = f":{parts.port}" if parts.port and not ((scheme == "https" and parts.port == 443) or (scheme == "http" and parts.port == 80)) else ""
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.casefold()
        if lower.startswith("utm_") or lower in TRACKING_PARAMS:
            continue
        query.append((key, value))
    query.sort()
    return urlunsplit((scheme, host + port, path, urlencode(query), ""))


def _hash(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _normalized_body(text: str) -> str:
    return normalize(text)


def _content_hash(text: str) -> str:
    normalized = _normalized_body(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if len(normalized) >= 100 else ""


def _tokens(text: str) -> set[str]:
    values = re.findall(r"[a-z0-9\u3400-\u9fff]{3,}", normalize(text))
    return {value for value in values if value not in STOPWORDS}


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def _parse_date(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def assign_article_groups(records: list[dict]) -> list[dict]:
    rows = [dict(record) for record in records]
    uf = _UnionFind(len(rows))
    urls: list[str] = []
    bodies: list[str] = []
    titles: list[str] = []
    dates: list[datetime | None] = []
    exact_url: dict[str, int] = {}
    exact_body: dict[str, int] = {}

    for index, row in enumerate(rows):
        url = normalize_url(
            row.get("final_url") or row.get("original_url") or row.get("rss_url") or row.get("google_news_url") or ""
        )
        body_hash = _content_hash(str(row.get("full_text") or ""))
        urls.append(url)
        bodies.append(body_hash)
        titles.append(normalize(str(row.get("title") or "")))
        dates.append(_parse_date(str(row.get("published_at") or row.get("published_utc") or "")))
        if url in exact_url and url:
            uf.union(index, exact_url[url])
        exact_url.setdefault(url, index)
        if body_hash in exact_body and body_hash:
            uf.union(index, exact_body[body_hash])
        exact_body.setdefault(body_hash, index)

    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if uf.find(left) == uf.find(right):
                continue
            date_distance = None
            if dates[left] and dates[right]:
                date_distance = abs((dates[left] - dates[right]).total_seconds())
            title_similarity = SequenceMatcher(None, titles[left], titles[right]).ratio() if titles[left] and titles[right] else 0
            title_tokens = _jaccard(_tokens(titles[left]), _tokens(titles[right]))
            if date_distance is not None and date_distance <= 36 * 3600 and title_similarity >= 0.94 and title_tokens >= 0.75:
                uf.union(left, right)

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        groups[uf.find(index)].append(index)

    for members in groups.values():
        common_body = bodies[members[0]] if bodies[members[0]] and all(bodies[i] == bodies[members[0]] for i in members) else ""
        common_url = urls[members[0]] if urls[members[0]] and all(urls[i] == urls[members[0]] for i in members) else ""
        if common_body:
            identity = "body:" + common_body
        elif common_url:
            identity = "url:" + common_url
        else:
            fingerprints = [urls[i] or bodies[i] or (titles[i] + "|" + str(rows[i].get("published_at", ""))) for i in members]
            identity = "group:" + "|".join(sorted(fingerprints))
        article_id = "art_" + _hash(identity)
        duplicate_group = "dup_" + _hash(identity, 16) if len(members) > 1 else ""
        source_ids = sorted({str(source) for i in members for source in rows[i].get("source_ids", []) if source})
        for offset, index in enumerate(sorted(members)):
            rows[index].update(
                article_id=article_id,
                normalized_url=urls[index],
                content_hash=bodies[index],
                duplicate_group_id=duplicate_group,
                is_duplicate_article=offset > 0,
                source_ids=source_ids,
            )
    return rows


def assign_event_groups(records: list[dict]) -> list[dict]:
    rows = [dict(record) for record in records]
    uf = _UnionFind(len(rows))
    dates = [_parse_date(str(row.get("published_at") or "")) for row in rows]
    title_facts = [_tokens(str(row.get("title") or "")) for row in rows]
    facts = [_tokens(str(row.get("title") or "") + " " + str(row.get("full_text") or "")[:1_200]) for row in rows]

    for left in range(len(rows)):
        left_categories = tuple(rows[left].get("negative_categories") or [])
        if not left_categories:
            continue
        for right in range(left + 1, len(rows)):
            right_categories = tuple(rows[right].get("negative_categories") or [])
            if not right_categories or rows[left].get("company") != rows[right].get("company"):
                continue
            if not set(left_categories) & set(right_categories):
                continue
            if not dates[left] or not dates[right] or abs((dates[left] - dates[right]).total_seconds()) > 3 * 86400:
                continue
            same_article = bool(rows[left].get("article_id") and rows[left].get("article_id") == rows[right].get("article_id"))
            if (
                same_article
                or _jaccard(title_facts[left], title_facts[right]) >= 0.6
                or _jaccard(facts[left], facts[right]) >= 0.45
            ):
                uf.union(left, right)

    groups: dict[int, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        if row.get("negative_categories"):
            groups[uf.find(index)].append(index)
        else:
            row.update(event_id="", event_duplicate_group_id="", is_same_event=False)

    for members in groups.values():
        company = str(rows[members[0]].get("company") or "")
        category = sorted({cat for i in members for cat in rows[i].get("negative_categories", [])})[0]
        earliest = min((dates[i] for i in members if dates[i]), default=None)
        anchors = sorted(str(rows[i].get("article_id") or rows[i].get("title") or "") for i in members)
        identity = f"{company}|{category}|{earliest.date().isoformat() if earliest else ''}|{anchors[0] if anchors else ''}"
        event_id = "evt_" + _hash(identity)
        group_id = "evdup_" + _hash(identity, 16) if len(members) > 1 else ""
        for index in members:
            rows[index].update(
                event_id=event_id,
                event_duplicate_group_id=group_id,
                is_same_event=len(members) > 1,
            )
    return rows

