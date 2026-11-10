"""Structured company catalogs and deterministic overlap auditing."""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .profiles import CURATED_ALIASES, SUBSIDIARIES, normalize


CATALOG_FIELDS = (
    "legal_name",
    "display_name",
    "aliases",
    "ticker",
    "parent_company",
    "region",
    "country",
    "industry",
    "languages",
    "positive_context",
    "negative_context",
)
LIST_FIELDS = {"aliases", "languages", "positive_context", "negative_context"}
REGIONS = ("China/Hong Kong", "Japan/Korea/APAC", "Europe", "US/Canada")
SUFFIXES = {
    "ag", "as", "asa", "ab", "co", "company", "corp", "corporation", "inc", "incorporated",
    "kg", "kgaa", "limited", "ltd", "nv", "oyj", "plc", "sa", "se", "spa", "group", "holdings",
}


def _split(value: object) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in str(value or "").split("|") if part.strip()))


def identity_key(value: str) -> str:
    words = normalize(value).split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def load_company_catalog(path: str | Path) -> list[dict]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(CATALOG_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("company catalog missing fields: " + ", ".join(sorted(missing)))
        rows = []
        for raw in reader:
            row = {field: (raw.get(field) or "").strip() for field in CATALOG_FIELDS}
            for field in LIST_FIELDS:
                row[field] = _split(row[field])
            if row["legal_name"]:
                rows.append(row)
    return rows


def query_terms(row: dict) -> list[str]:
    values = [row.get("legal_name", ""), row.get("display_name", ""), *(row.get("aliases") or [])]
    output = []
    seen = set()
    for value in values:
        key = normalize(str(value))
        if value and key not in seen:
            output.append(str(value))
            seen.add(key)
    return output


def historical_identity_keys(historical_names: list[str] | tuple[str, ...]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for company in historical_names:
        values = [company, *CURATED_ALIASES.get(company, ())]
        for subsidiary_aliases in SUBSIDIARIES.get(company, {}).values():
            values.extend(subsidiary_aliases)
        for value in values:
            key = identity_key(value)
            if key:
                owners.setdefault(key, company)
    return owners


def validate_catalog(rows: list[dict], historical_names: list[str] | tuple[str, ...]) -> dict:
    duplicate_details: list[dict] = []
    overlap_details: list[dict] = []
    identity_owners: dict[str, set[str]] = defaultdict(set)
    ticker_owners: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        legal = str(row.get("legal_name") or "")
        for value in [legal, row.get("display_name", ""), *(row.get("aliases") or [])]:
            key = identity_key(str(value))
            if key:
                identity_owners[key].add(legal)
        ticker = normalize(str(row.get("ticker") or ""))
        if ticker:
            ticker_owners[ticker].add(legal)

    for key, owners in sorted(identity_owners.items()):
        if len(owners) > 1:
            duplicate_details.append({"kind": "alias", "value": key, "companies": sorted(owners)})
    for key, owners in sorted(ticker_owners.items()):
        if len(owners) > 1:
            duplicate_details.append({"kind": "ticker", "value": key, "companies": sorted(owners)})

    for row in rows:
        parent = identity_key(str(row.get("parent_company") or ""))
        legal = str(row.get("legal_name") or "")
        if parent and parent in identity_owners and any(owner != legal for owner in identity_owners[parent]):
            duplicate_details.append({
                "kind": "parent_company",
                "value": parent,
                "companies": sorted({legal, *identity_owners[parent]}),
            })

    historical = historical_identity_keys(historical_names)
    seen_overlaps = set()
    for row in rows:
        legal = str(row.get("legal_name") or "")
        values = [legal, row.get("display_name", ""), *(row.get("aliases") or []), row.get("parent_company", "")]
        matches = sorted({historical[key] for value in values if (key := identity_key(str(value))) in historical})
        if matches and legal not in seen_overlaps:
            overlap_details.append({"company": legal, "historical_companies": matches})
            seen_overlaps.add(legal)

    regional_counts = dict(sorted(Counter(str(row.get("region") or "") for row in rows).items()))
    required_regions = {region: regional_counts.get(region, 0) for region in REGIONS}
    audit = {
        "Total Companies": len(rows),
        "Internal Duplicates": len(duplicate_details),
        "Overlap With Previous 300": len(overlap_details),
        "Regional Counts": dict(sorted(required_regions.items())),
        "duplicate_details": duplicate_details,
        "overlap_details": overlap_details,
    }
    audit["is_valid"] = (
        audit["Total Companies"] == 100
        and audit["Internal Duplicates"] == 0
        and audit["Overlap With Previous 300"] == 0
        and all(count == 25 for count in required_regions.values())
        and not (set(regional_counts) - set(REGIONS))
    )
    return audit


def write_catalog_audit(path: str | Path, audit: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_company_catalog(path: str | Path, rows: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                field: "|".join(row.get(field, [])) if field in LIST_FIELDS else row.get(field, "")
                for field in CATALOG_FIELDS
            })

