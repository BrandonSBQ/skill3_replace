"""Explainable company-article association rules."""
from __future__ import annotations

import re

from .profiles import CompanyProfile, get_profile, normalize


def _contains(text: str, alias: str) -> bool:
    haystack = normalize(text)
    needle = normalize(alias)
    if not needle:
        return False
    if re.search(r"[\u3400-\u9fff]", needle):
        return needle in haystack.replace(" ", "")
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _hits(text: str, values: tuple[str, ...]) -> list[str]:
    return [value for value in values if _contains(text, value)]


def _negated_canonical(profile: CompanyProfile, text: str) -> bool:
    normalized = normalize(text)
    canonical = normalize(profile.canonical)
    patterns = (
        rf"{re.escape(canonical)} (?:was |is )?not (?:discussed|mentioned|involved|related)",
        rf"not (?:about|related to|involving) {re.escape(canonical)}",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _is_strong_corporate_alias(alias: str, canonical: str) -> bool:
    value = normalize(alias)
    markers = (" inc", " corp", " plc", " limited", " holdings", "公司", "集团", "控股", "银行", "保险")
    if value == normalize(canonical):
        return any(marker in value for marker in markers)
    return any(marker in value for marker in markers)


def resolve_entity(company: str, title: str, text: str, publisher: str = "", metadata: dict | None = None) -> dict:
    """Resolve one target-company association without claiming event truth."""
    profile = get_profile(company, metadata=metadata)
    title = title or ""
    text = text or ""
    combined = " ".join((title, text, publisher or ""))

    title_aliases = _hits(title, profile.aliases)
    body_aliases = _hits(text, profile.aliases)
    positive = _hits(combined, profile.positive_context)
    negative = _hits(combined, profile.negative_context)

    subsidiary_hits: list[tuple[str, str]] = []
    for entity, aliases in profile.subsidiaries.items():
        for alias in aliases:
            if _contains(combined, alias):
                subsidiary_hits.append((entity, alias))
                break

    direct_hits = list(dict.fromkeys(title_aliases + body_aliases))
    has_direct = bool(direct_hits) and not _negated_canonical(profile, combined)
    has_strong_alias = any(_is_strong_corporate_alias(alias, company) for alias in direct_hits)
    is_ambiguous = bool(profile.positive_context or profile.negative_context)

    evidence = []
    if title_aliases:
        evidence.append("title alias: " + ", ".join(title_aliases[:3]))
    if body_aliases:
        evidence.append("body alias: " + ", ".join(body_aliases[:3]))
    if positive:
        evidence.append("company context: " + ", ".join(positive[:3]))
    if negative:
        evidence.append("conflicting context: " + ", ".join(negative[:3]))

    if subsidiary_hits and not has_direct:
        matched, alias = subsidiary_hits[0]
        return {
            "entity_match_status": "MATCHED",
            "entity_match_confidence": 0.86 if _contains(title, alias) else 0.78,
            "matched_entity": matched,
            "entity_relationship": "SUBSIDIARY",
            "entity_match_evidence": f"subsidiary alias: {alias}; parent: {company}",
        }

    if not has_direct:
        status = "UNCERTAIN" if subsidiary_hits or direct_hits else "UNRELATED"
        return {
            "entity_match_status": status,
            "entity_match_confidence": 0.42 if status == "UNCERTAIN" else 0.05,
            "matched_entity": subsidiary_hits[0][0] if subsidiary_hits else "",
            "entity_relationship": "UNCERTAIN" if status == "UNCERTAIN" else "UNRELATED",
            "entity_match_evidence": "; ".join(evidence) or "no supported company alias found",
        }

    if is_ambiguous and negative and not has_strong_alias:
        return {
            "entity_match_status": "UNRELATED" if title_aliases else "UNCERTAIN",
            "entity_match_confidence": 0.15 if title_aliases else 0.4,
            "matched_entity": "",
            "entity_relationship": "UNRELATED" if title_aliases else "UNCERTAIN",
            "entity_match_evidence": "; ".join(evidence),
        }

    if is_ambiguous and not positive and not has_strong_alias:
        return {
            "entity_match_status": "UNCERTAIN",
            "entity_match_confidence": 0.48,
            "matched_entity": company,
            "entity_relationship": "UNCERTAIN",
            "entity_match_evidence": "; ".join(evidence) + "; ambiguous name lacks company context",
        }

    confidence = 0.9 if title_aliases and (body_aliases or positive) else 0.82 if title_aliases else 0.72
    return {
        "entity_match_status": "MATCHED",
        "entity_match_confidence": confidence,
        "matched_entity": company,
        "entity_relationship": "DIRECT",
        "entity_match_evidence": "; ".join(evidence),
    }

