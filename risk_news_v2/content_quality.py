"""Independent validation of extracted article text."""
from __future__ import annotations

import re
from collections import Counter


BLOCKER_PHRASES = (
    "Client Challenge",
    "Pardon Our Interruption",
    "Enable JavaScript",
    "Access Denied",
    "Verify you are human",
    "Checking your browser",
    "Just a moment...",
    "captcha",
)

PAYWALL_PHRASES = (
    "subscribe now",
    "subscription required",
    "sign in to continue",
    "log in to continue",
    "already a subscriber",
    "purchase a subscription",
)

NAVIGATION_PHRASES = (
    "privacy policy",
    "cookie policy",
    "terms of use",
    "contact us",
    "navigation menu",
    "all rights reserved",
)


def _repeat_metrics(text: str) -> tuple[float, float]:
    lines = [" ".join(line.casefold().split()) for line in text.splitlines() if len(line.strip()) >= 20]
    if len(lines) < 4:
        return 1.0, 0.0
    counts = Counter(lines)
    return len(counts) / len(lines), counts.most_common(1)[0][1] / len(lines)


def validate_content(record: dict) -> dict:
    text = str(record.get("full_text") or "").strip()
    fetch_status = str(record.get("fetch_status") or "UNKNOWN")
    if not text:
        return {
            "content_validation_status": "UNAVAILABLE",
            "content_quality_score": 0,
            "content_validation_reason": f"no extracted text; fetch_status={fetch_status}",
        }

    folded = text.casefold()
    blockers = [phrase for phrase in BLOCKER_PHRASES if phrase.casefold() in folded]
    if blockers:
        return {
            "content_validation_status": "INVALID",
            "content_quality_score": 5,
            "content_validation_reason": "block/access page marker: " + ", ".join(blockers),
        }

    reasons: list[str] = []
    score = 40
    char_count = len(text)
    word_count = len(re.findall(r"\b\w+\b", text, re.UNICODE))
    sentence_count = len(re.findall(r"[.!?。！？](?:\s|$)", text))
    paragraphs = len([part for part in text.splitlines() if len(part.strip()) >= 40])

    if char_count >= 500:
        score += 25
    elif char_count >= 180:
        score += 10
    else:
        score -= 35
        reasons.append(f"short extracted text ({char_count} chars)")
    if char_count >= 1_000:
        score += 10
    if sentence_count >= 4:
        score += 10
    if paragraphs >= 3:
        score += 10
    if word_count >= 120:
        score += 5

    paywall = [phrase for phrase in PAYWALL_PHRASES if phrase in folded]
    if paywall:
        score -= 60 if char_count < 500 else 25
        reasons.append("paywall/login marker: " + ", ".join(paywall))

    unique_ratio, dominant_ratio = _repeat_metrics(text)
    extreme_repetition = unique_ratio < 0.1 or dominant_ratio > 0.8
    if unique_ratio < 0.15 or dominant_ratio > 0.5:
        score -= 50
        reasons.append(f"repeated content (unique_lines={unique_ratio:.2f}, dominant={dominant_ratio:.2f})")

    nav_hits = [phrase for phrase in NAVIGATION_PHRASES if phrase in folded]
    if len(nav_hits) >= 2:
        score -= 20
        reasons.append("navigation/footer markers: " + ", ".join(nav_hits))

    if re.search(r"(?:\.\.\.|…|\[continued\]|read more)\s*$", text, re.IGNORECASE):
        score -= 20
        reasons.append("text appears truncated")

    title_words = {w for w in re.findall(r"[a-z0-9]{4,}", str(record.get("title") or "").casefold())}
    body_words = set(re.findall(r"[a-z0-9]{4,}", folded[:2_000]))
    if title_words and title_words & body_words:
        score += 5
    elif title_words and char_count >= 500:
        score -= 10
        reasons.append("title and extracted text have little lexical overlap")

    score = max(0, min(100, score))
    if extreme_repetition:
        status = "INVALID"
    elif score >= 75:
        status = "VALID"
    elif score >= 55:
        status = "NEEDS_REVIEW"
    elif score >= 30:
        status = "PARTIAL"
    else:
        status = "INVALID"
    if not reasons:
        reasons.append(f"article-like text structure; fetch_status={fetch_status}")
    return {
        "content_validation_status": status,
        "content_quality_score": score,
        "content_validation_reason": "; ".join(reasons),
    }

