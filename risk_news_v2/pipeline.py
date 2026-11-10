"""Offline V2 enrichment, routing, audit, and report generation."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .classification import classify_negative
from .company_catalog import load_company_catalog
from .content_quality import validate_content
from .dates import reconcile_dates
from .deduplication import assign_article_groups, assign_event_groups
from .entity_resolution import resolve_entity


OUTPUT_FILES = (
    "company_coverage.csv",
    "articles_cleaned.jsonl",
    "articles_rejected.jsonl",
    "articles_needs_review.jsonl",
    "events_candidates.jsonl",
    "article_source_mapping.csv",
    "pipeline_audit.json",
    "quality_report.md",
)


def safe_csv(value: object) -> str:
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> tuple[list[dict], int]:
    records: list[dict] = []
    malformed = 0
    if not path.exists():
        return records, malformed
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                malformed += 1
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                malformed += 1
    return records, malformed


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def _stable_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\x00".join(values).encode("utf-8")).hexdigest()[:20]
    return prefix + digest


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _atomic_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: safe_csv(row.get(field, "")) for field in fields})
    temporary.replace(path)


def _legacy_key(company: str, url: str) -> tuple[str, str]:
    return str(company or "").strip(), str(url or "").strip()


def _base_record(candidate: dict, extracted: dict | None) -> dict:
    company = str(candidate.get("Company") or "")
    rss_url = str(candidate.get("Google News URL") or "")
    legacy = extracted or {}
    source_id = str(legacy.get("article_id") or _stable_id("rss_", company, rss_url))
    return {
        "association_id": _stable_id("assoc_", company, rss_url),
        "association_source_ids": [source_id],
        "source_ids": [source_id],
        "company": company,
        "title": str(candidate.get("Title") or legacy.get("title") or ""),
        "publisher": str(candidate.get("Publisher") or legacy.get("publisher") or ""),
        "rss_url": rss_url,
        "google_news_url": rss_url,
        "original_url": str(legacy.get("original_url") or ""),
        "final_url": str(legacy.get("final_url") or ""),
        "published_utc": str(candidate.get("Published UTC") or legacy.get("published_utc") or ""),
        "extracted_date": str(legacy.get("extracted_date") or ""),
        "article_updated_at": str(legacy.get("article_updated_at") or ""),
        "full_text": str(legacy.get("full_text") or ""),
        "fetch_status": str(legacy.get("fetch_status") or "NOT_SELECTED"),
        "fetch_error": str(legacy.get("error") or ""),
        "retrieved_utc": str(legacy.get("retrieved_utc") or ""),
        "v1_possible_negative_types": str(candidate.get("Possible Negative Types") or legacy.get("possible_negative_types") or ""),
        "v1_screening_basis": str(candidate.get("Screening Basis") or legacy.get("screening_basis") or ""),
        "has_v1_extraction_record": extracted is not None,
        "event_confidence": "UNVERIFIED",
    }


def _enrich(candidate: dict, extracted: dict | None, company_metadata: dict | None = None) -> dict:
    row = _base_record(candidate, extracted)
    metadata = company_metadata or {}
    row.update({
        "ticker": metadata.get("ticker", ""),
        "region": metadata.get("region", ""),
        "country": metadata.get("country", ""),
        "industry": metadata.get("industry", ""),
        "parent_company": metadata.get("parent_company", ""),
    })
    entity = resolve_entity(
        row["company"], row["title"], row["full_text"], row["publisher"], metadata=metadata or None
    )
    content = validate_content(row)
    negative = classify_negative(row["title"], row["full_text"], entity)
    dates = reconcile_dates(row)
    row.update(entity)
    row.update(content)
    row.update(negative)
    row.update(dates)
    return row


def _route(row: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if row["content_validation_status"] == "INVALID":
        reasons.append("invalid_content")
    if row["entity_match_status"] == "UNRELATED":
        reasons.append("unrelated_entity")
    if row["negative_screening_status"] in {"NOT_NEGATIVE", "UNRELATED"}:
        reasons.append("not_negative_or_unrelated")
    if reasons:
        return "REJECTED", reasons

    review_conditions = {
        "content_not_valid": row["content_validation_status"] != "VALID",
        "entity_uncertain": row["entity_match_status"] != "MATCHED" or float(row["entity_match_confidence"]) < 0.7,
        "relationship_uncertain": row["entity_relationship"] not in {"DIRECT", "SUBSIDIARY", "PARENT_GROUP"},
        "negative_nature_uncertain": row["negative_screening_status"] != "NEGATIVE_CANDIDATE",
        "date_conflict": row.get("date_validation_status") == "CONFLICT",
    }
    reasons.extend(name for name, present in review_conditions.items() if present)
    if reasons:
        return "NEEDS_REVIEW", reasons
    return "CLEANED", []


def _build_events(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("event_id") and row.get("negative_categories"):
            groups[row["event_id"]].append(row)
    events = []
    for event_id in sorted(groups):
        members = groups[event_id]
        dates = sorted(row["published_at"] for row in members if row.get("published_at"))
        events.append({
            "event_id": event_id,
            "company": members[0]["company"],
            "matched_entities": sorted({row["matched_entity"] for row in members if row.get("matched_entity")}),
            "negative_categories": sorted({category for row in members for category in row.get("negative_categories", [])}),
            "first_published_at": dates[0] if dates else "",
            "article_ids": sorted({row["article_id"] for row in members}),
            "source_ids": sorted({source for row in members for source in row.get("association_source_ids", [])}),
            "source_count": len({row["article_id"] for row in members}),
            "representative_title": members[0]["title"],
            "event_confidence": "UNVERIFIED",
            "review_status": "PENDING_REVIEW",
            "same_event_evidence": "deterministic company/category/date/fact similarity; requires downstream verification",
        })
    return events


def _coverage_rows(coverage: list[dict], rows: list[dict]) -> list[dict]:
    by_company: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_company[row["company"]].append(row)
    output = []
    for index, source in enumerate(coverage, 1):
        company = str(source.get("Company") or "")
        members = by_company.get(company, [])
        output.append({
            "No.": source.get("No.") or index,
            "Company": company,
            "Search Status": source.get("Search Status") or "UNKNOWN",
            "RSS Candidates": source.get("Candidate Count") or len(members),
            "Articles Processed": len(members),
            "Valid Full Text": sum(row["content_validation_status"] == "VALID" for row in members),
            "Invalid Full Text": sum(row["content_validation_status"] == "INVALID" for row in members),
            "Entity Matched": sum(row["entity_match_status"] == "MATCHED" for row in members),
            "Entity Uncertain": sum(row["entity_match_status"] == "UNCERTAIN" for row in members),
            "Unrelated Articles": sum(row["entity_match_status"] == "UNRELATED" for row in members),
            "Candidate Negative Events": len({row["event_id"] for row in members if row.get("event_id")}),
            "Cleaned Articles": sum(row["review_status"] == "CLEANED" for row in members),
            "Needs Review": sum(row["review_status"] == "NEEDS_REVIEW" for row in members),
            "Rejected": sum(row["review_status"] == "REJECTED" for row in members),
            "Missing Full Text": sum(row["content_validation_status"] == "UNAVAILABLE" for row in members),
        })
    return output


def _quality_report(counts: dict, coverage: list[dict], review: list[dict], rejected: list[dict]) -> str:
    missing = [row["Company"] for row in coverage if int(row["Cleaned Articles"] or 0) == 0]
    review_by_company = Counter(row["company"] for row in review)
    rejection_reasons = Counter(reason for row in rejected for reason in row.get("routing_reasons", []))
    count_lines = "\n".join(f"| {key} | {value} |" for key, value in counts.items())
    missing_text = ", ".join(missing) if missing else "None"
    review_text = "\n".join(f"- {company}: {amount}" for company, amount in sorted(review_by_company.items())) or "- None"
    rejection_text = "\n".join(f"- {reason}: {amount}" for reason, amount in sorted(rejection_reasons.items())) or "- None"
    return f"""# 300 家公司负面新闻监控 V2 质量报告

本报告由本地确定性规则从 V1 已保存结果计算。所有事件仍为未核实候选，不构成信用评级或正式风险结论。

## 验收统计

| Metric | Count |
|---|---:|
{count_lines}

## V1 与 V2 数据质量变化

- V1 以 `fetch_status == SUCCESS` 统计正文成功；本批为 {counts.get('V1 Full Text Success', 0)}。
- V2 对页面类型、挑战页、付费墙、重复内容、结构和截断再次验证；`VALID` 为 {counts.get('Valid Full Text', 0)}。
- V2 新增实体关系、12 类负面候选筛选、文章/事件去重、日期冲突和三路分流。
- V2 保持保守：只有正文 `VALID`、实体证据充分且为 `NEGATIVE_CANDIDATE` 的关联进入 cleaned。

## 仍缺少 cleaned 证据的公司

{missing_text}

这不表示公司没有风险事件，只表示本批候选未形成满足 V2 门槛的本地证据。

## 仍需人工审核的新闻

完整逐条清单见 `articles_needs_review.jsonl`；按公司数量如下：

{review_text}

## 排除原因

{rejection_text}

## 剩余未解决问题

- 确定性别名表不能覆盖全部品牌、子公司、并购及中文译名，低证据关联会留在待审核。
- 事件级去重仅使用主体、类别、日期和文本事实相似度，不能替代事实核验。
- 被 robots.txt、付费墙、登录或反爬机制阻止的原文不会被绕过。
- RSS 时间是监控时间主字段；网页日期和更新时间分别保留，冲突需要复核。
- 替代来源仅建立关联，不会伪装成原报道全文。

## 后续 Agent 安全读取方式

- `articles_cleaned.jsonl`：可作为高质量正文证据输入，但事件真实性和信用影响仍需核实。
- `events_candidates.jsonl`：用于候选事件聚合，不是已确认事件清单。
- `articles_needs_review.jsonl`：交给轻量语义 Agent 或人工复核实体、负面性质、正文或日期。
- `articles_rejected.jsonl`：保留排除依据，通常不要用于风险结论。
- `pipeline_audit.json` 与 `company_coverage.csv`：用于核对范围、缺口和统计。
"""


def clean_existing(input_dir: str | Path, output_dir: str | Path, *, network_used: bool = False) -> dict:
    input_path = Path(input_dir).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"input directory not found: {input_path}")
    candidates_path = input_path / "negative_news_candidates.csv"
    if not candidates_path.exists():
        raise FileNotFoundError(f"candidate file not found: {candidates_path}")
    output_path.mkdir(parents=True, exist_ok=True)

    candidates = _read_csv(candidates_path)
    coverage = _read_csv(input_path / "coverage_300.csv")
    extractions, malformed = _read_jsonl(input_path / "articles_with_content.jsonl")
    company_metadata: dict[str, dict] = {}
    for catalog_path in sorted(input_path.glob("company_list_*.csv")):
        try:
            catalog_rows = load_company_catalog(catalog_path)
        except (ValueError, OSError):
            continue
        company_metadata.update({row["legal_name"]: row for row in catalog_rows})
    extraction_by_key = {
        _legacy_key(row.get("company", ""), row.get("google_news_url", "")): row for row in extractions
    }
    enriched = []
    for candidate in candidates:
        key = _legacy_key(candidate.get("Company", ""), candidate.get("Google News URL", ""))
        enriched.append(_enrich(candidate, extraction_by_key.get(key), company_metadata.get(key[0])))

    enriched = assign_article_groups(enriched)
    enriched = assign_event_groups(enriched)
    valid_by_event: dict[str, set[str]] = defaultdict(set)
    for row in enriched:
        if row.get("event_id") and row["content_validation_status"] == "VALID":
            valid_by_event[row["event_id"]].add(row["article_id"])
    for row in enriched:
        alternatives = valid_by_event.get(row.get("event_id", ""), set()) - {row["article_id"]}
        row["alternative_source_article_ids"] = sorted(alternatives)
        route, reasons = _route(row)
        row["review_status"] = route
        row["routing_reasons"] = reasons

    cleaned = [row for row in enriched if row["review_status"] == "CLEANED"]
    rejected = [row for row in enriched if row["review_status"] == "REJECTED"]
    review = [row for row in enriched if row["review_status"] == "NEEDS_REVIEW"]
    events = _build_events([
        row for row in enriched
        if row["review_status"] != "REJECTED"
        and row["negative_screening_status"] not in {"NOT_NEGATIVE", "UNRELATED"}
    ])
    coverage_output = _coverage_rows(coverage, enriched)

    _atomic_jsonl(output_path / "articles_cleaned.jsonl", cleaned)
    _atomic_jsonl(output_path / "articles_rejected.jsonl", rejected)
    _atomic_jsonl(output_path / "articles_needs_review.jsonl", review)
    _atomic_jsonl(output_path / "events_candidates.jsonl", events)
    coverage_fields = [
        "No.", "Company", "Search Status", "RSS Candidates", "Articles Processed", "Valid Full Text",
        "Invalid Full Text", "Entity Matched", "Entity Uncertain", "Unrelated Articles",
        "Candidate Negative Events", "Cleaned Articles", "Needs Review", "Rejected", "Missing Full Text",
    ]
    _atomic_csv(output_path / "company_coverage.csv", coverage_fields, coverage_output)

    mapping_rows = []
    for row in enriched:
        for source_id in row.get("association_source_ids", []):
            mapping_rows.append({
                "Legacy Source ID": source_id,
                "Association ID": row["association_id"],
                "Article ID": row["article_id"],
                "Event ID": row.get("event_id", ""),
                "Company": row["company"],
                "Entity Relationship": row["entity_relationship"],
                "Original URL": row["original_url"],
                "Alternative Source Article IDs": ";".join(row["alternative_source_article_ids"]),
                "Duplicate Group ID": row["duplicate_group_id"],
                "Is Duplicate Article": row["is_duplicate_article"],
                "Is Same Event": row.get("is_same_event", False),
            })
    mapping_fields = [
        "Legacy Source ID", "Association ID", "Article ID", "Event ID", "Company", "Entity Relationship",
        "Original URL", "Alternative Source Article IDs", "Duplicate Group ID", "Is Duplicate Article", "Is Same Event",
    ]
    _atomic_csv(output_path / "article_source_mapping.csv", mapping_fields, mapping_rows)

    search_counts = Counter(row.get("Search Status", "UNKNOWN") for row in coverage)
    fetch_summary = _read_json(input_path / "article_fetch_summary.json")
    counts = {
        "Total Companies": len(coverage_output),
        "Search Completed": search_counts["SUCCESS"] + search_counts["NO_CANDIDATE_FOUND"],
        "Search Partial": search_counts["PARTIAL_CAPPED"],
        "No Candidate Found": sum(int(row.get("Candidate Count") or 0) == 0 for row in coverage),
        "Total RSS Candidates": len(candidates),
        "Total Articles Processed": len(enriched),
        "Articles With V1 Extraction Record": sum(row["has_v1_extraction_record"] for row in enriched),
        "V1 Full Text Success": int(fetch_summary.get("full_text_success") or sum(row.get("fetch_status") == "SUCCESS" for row in extractions)),
        "Valid Full Text": sum(row["content_validation_status"] == "VALID" for row in enriched),
        "Invalid Full Text": sum(row["content_validation_status"] == "INVALID" for row in enriched),
        "Entity Matched": sum(row["entity_match_status"] == "MATCHED" for row in enriched),
        "Entity Uncertain": sum(row["entity_match_status"] == "UNCERTAIN" for row in enriched),
        "Unrelated Articles": sum(row["entity_match_status"] == "UNRELATED" for row in enriched),
        "Duplicate Articles": sum(bool(row["is_duplicate_article"]) for row in enriched),
        "Candidate Negative Events": len(events),
        "Needs Review": len(review),
        "Rejected": len(rejected),
        "Missing Full Text": sum(row["content_validation_status"] == "UNAVAILABLE" for row in enriched),
        "Cleaned": len(cleaned),
        "Malformed Extraction Records": malformed,
    }
    audit = {
        "pipeline_version": "2.0.0",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_directory": str(input_path),
        "output_directory": str(output_path),
        "counts": counts,
        "status_counts": {
            "content_validation": dict(sorted(Counter(row["content_validation_status"] for row in enriched).items())),
            "entity_match": dict(sorted(Counter(row["entity_match_status"] for row in enriched).items())),
            "negative_screening": dict(sorted(Counter(row["negative_screening_status"] for row in enriched).items())),
            "routing": dict(sorted(Counter(row["review_status"] for row in enriched).items())),
        },
        "input_sha256": {
            "coverage_300.csv": _sha256(input_path / "coverage_300.csv"),
            "negative_news_candidates.csv": _sha256(candidates_path),
            "articles_with_content.jsonl": _sha256(input_path / "articles_with_content.jsonl"),
        },
        "rules": {
            "cleaned_gate": "content VALID + entity MATCHED >=0.70 + supported relationship + NEGATIVE_CANDIDATE",
            "event_confidence": "UNVERIFIED",
            "network_used": bool(network_used),
        },
    }
    (output_path / "pipeline_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_path / "quality_report.md").write_text(
        _quality_report(counts, coverage_output, review, rejected), encoding="utf-8"
    )
    return counts

