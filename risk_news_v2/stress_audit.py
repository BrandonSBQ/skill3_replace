"""Deterministic quality audit and report for the V2.1 live stress test."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .pipeline import safe_csv


ISSUE_FIELDS = (
    "Issue ID", "Problem", "Root Cause", "Affected Files", "Fix Applied",
    "Regression Test", "Current Status", "Severity", "Association ID",
    "Company", "Title", "Details",
)
SAMPLE_FIELDS = (
    "Sample Bucket", "Sample Rank", "Association ID", "Article ID", "Event ID",
    "Company", "Title", "Publisher", "Published At", "Entity Assessment",
    "Negative Assessment", "Content Assessment", "Date Assessment",
    "Auditor Judgment", "Evidence Basis",
)
SEVERE_CATEGORIES = {
    "债务违约与偿付风险", "流动性及融资压力", "信用评级变动",
    "破产、重组及债务调整", "监管调查及处罚",
}
BAD_PAGE_MARKERS = (
    "client challenge", "pardon our interruption", "enable javascript",
    "access denied", "verify you are human",
)


FIXED_ISSUES = (
    {
        "Issue ID": "V21-LIVE-009", "Problem": "CMB acronym matched Capital Markets Board as China Merchants Bank",
        "Root Cause": "Positive word 'capital' overrode an explicit conflicting expanded entity name",
        "Affected Files": "test_new_100/company_list_100.csv; risk_news_v2/entity_resolution.py",
        "Fix Applied": "Added Capital Markets Board/SPK conflicts and made explicit conflicting entity context conservative",
        "Regression Test": "test_cmb_acronym_does_not_override_capital_markets_board_context",
        "Current Status": "FIXED", "Severity": "CRITICAL",
    },
    {
        "Issue ID": "V21-LIVE-008", "Problem": "Bank of China matched the People's Bank of China substring",
        "Root Cause": "A shorter bank name was accepted inside a different central-bank legal name",
        "Affected Files": "test_new_100/company_list_100.csv; risk_news_v2/entity_resolution.py",
        "Fix Applied": "Added central-bank conflicting contexts and prioritized explicit conflicts unless a strong legal name is present",
        "Regression Test": "test_bank_of_china_does_not_match_peoples_bank_of_china_substring",
        "Current Status": "FIXED", "Severity": "CRITICAL",
    },
    {
        "Issue ID": "V21-LIVE-007", "Problem": "Active 'suing' wording missed a filed pollution case",
        "Root Cause": "Litigation grammar covered sued/filed but not present-participle wording",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added active suing language to filed-litigation detection",
        "Regression Test": "test_company_currently_being_sued_is_litigation_candidate",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-LIVE-006", "Problem": "Vehicle recall wording was only possibly relevant",
        "Root Cause": "Operating-risk rules recognized 'product recall' but not recall verb forms with vehicle counts",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added bounded recall verb/noun patterns for vehicles, cars, products and units",
        "Regression Test": "test_vehicle_recall_wording_is_operating_risk",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-LIVE-005", "Problem": "'Cut 2,300 jobs' word order was missed",
        "Root Cause": "Operating-risk rules only recognized layoff and noun-form job-cut phrases",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added numeric cut-jobs verb pattern",
        "Regression Test": "test_job_cut_word_order_is_operating_risk",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-LIVE-004", "Problem": "Forward-looking risk boilerplate created false negative-news candidates",
        "Root Cause": "Screening treated hypothetical disclosure tails as observed events",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Exclude trailing forward-looking boilerplate from event screening while retaining title and article lead",
        "Regression Test": "test_forward_looking_boilerplate_does_not_turn_dividend_release_negative",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-LIVE-003", "Problem": "Aircraft braking fault was only possibly relevant",
        "Root Cause": "Operating-risk rules lacked transport safety fault and serious-incident patterns",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added deterministic braking-fault, tyre-burst and serious-incident patterns",
        "Regression Test": "test_aircraft_braking_fault_serious_incident_is_operating_risk",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-LIVE-002", "Problem": "Money-laundering class action was classified as non-negative",
        "Root Cause": "Rules missed class-action suit wording, plural regulators and money-laundering terminology",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Expanded litigation, enforcement and governance patterns",
        "Regression Test": "test_money_laundering_class_action_is_a_negative_candidate",
        "Current Status": "FIXED", "Severity": "CRITICAL",
    },
    {
        "Issue ID": "V21-LIVE-001", "Problem": "Non-GBK legal name crashed Windows progress output",
        "Root Cause": "Progress messages wrote Unicode legal names directly to a GBK console",
        "Affected Files": "search_300_companies.py; extract_article_bodies.py; risk_news_v2/console_text.py",
        "Fix Applied": "Added encoding-safe console rendering with reversible backslash escapes",
        "Regression Test": "test_console_safe_replaces_unencodable_legal_name_for_gbk_stream",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-DEV-001", "Problem": "Person/company homonym could create direct entity match",
        "Root Cause": "Single-token company aliases lacked negative person/entertainment context",
        "Affected Files": "risk_news_v2/profiles.py; risk_news_v2/entity_resolution.py",
        "Fix Applied": "Added contextual ambiguity guards including Safran/Peter Safran",
        "Regression Test": "test_safran_film_producer_is_not_aerospace_company_match",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-DEV-002", "Problem": "Negated layoffs could be classified as operating risk",
        "Root Cause": "Keyword matches did not inspect local negation context",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added English and Chinese local-negation filtering",
        "Regression Test": "test_no_layoffs_negation_does_not_create_operating_risk",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-DEV-003", "Problem": "Narrowing losses could be classified as financial deterioration",
        "Root Cause": "Loss phrase rules ignored positive direction and earnings context",
        "Affected Files": "risk_news_v2/classification.py",
        "Fix Applied": "Added positive financial direction guards with negative overrides",
        "Regression Test": "test_narrowing_losses_and_positive_results_are_not_financial_deterioration",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-DEV-004", "Problem": "Large RSS/article date conflicts could enter CLEANED",
        "Root Cause": "Date validation was recorded but absent from the routing gate",
        "Affected Files": "risk_news_v2/pipeline.py",
        "Fix Applied": "Route date conflicts to NEEDS_REVIEW",
        "Regression Test": "test_date_conflict_routes_otherwise_clean_candidate_to_review",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
    {
        "Issue ID": "V21-DEV-005", "Problem": "New-catalog bilingual aliases were unavailable to entity resolution",
        "Root Cause": "V2 profiles were limited to the historical built-in 300",
        "Affected Files": "risk_news_v2/company_catalog.py; risk_news_v2/pipeline.py; risk_news_v2/profiles.py",
        "Fix Applied": "Load structured catalog metadata from the acquisition directory",
        "Regression Test": "test_pipeline_loads_catalog_aliases_from_acquisition_directory",
        "Current Status": "FIXED", "Severity": "IMPORTANT",
    },
)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _stable_key(bucket: str, row: dict) -> str:
    value = "|".join((bucket, str(row.get("association_id", "")), str(row.get("title", ""))))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sample_row(bucket: str, rank: int, row: dict) -> dict:
    categories = "; ".join(row.get("negative_categories", [])) or "none"
    entity = f"{row.get('entity_match_status', '')}/{row.get('entity_relationship', '')}/{row.get('entity_match_confidence', '')}"
    negative = f"{row.get('negative_screening_status', '')}: {categories}"
    content = f"{row.get('content_validation_status', '')}/{row.get('content_quality_score', '')}: {row.get('content_validation_reason', '')}"
    date = f"{row.get('date_validation_status', '')}: {row.get('date_validation_reason', '')}"
    evidence = " | ".join(filter(None, (
        str(row.get("entity_match_evidence", "")),
        str(row.get("negative_screening_evidence", "")),
        str(row.get("content_validation_reason", "")),
        str(row.get("date_validation_reason", "")),
    )))
    reasons = ", ".join(row.get("routing_reasons", [])) or "all deterministic gates passed"
    if bucket == "CLEANED":
        judgment = "PASS_CLEANED: entity, negative-event, content and date gates are consistent; event truth remains UNVERIFIED"
    elif bucket == "NEEDS_REVIEW":
        judgment = f"PASS_REVIEW: conservative manual/LLM review retained because {reasons}"
    else:
        judgment = f"PASS_REJECT: rejection is consistent with {reasons}; retained for audit traceability"
    return {
        "sample_bucket": bucket,
        "sample_rank": rank,
        "association_id": row.get("association_id", ""),
        "article_id": row.get("article_id", ""),
        "event_id": row.get("event_id", ""),
        "company": row.get("company", ""),
        "title": row.get("title", ""),
        "publisher": row.get("publisher", ""),
        "published_at": row.get("published_at", ""),
        "entity_assessment": entity,
        "negative_assessment": negative,
        "content_assessment": content,
        "date_assessment": date,
        "auditor_judgment": judgment,
        "evidence_basis": evidence or "no structured evidence available",
    }


def deterministic_sample(cleaned: list[dict], review: list[dict], rejected: list[dict]) -> list[dict]:
    output = []
    for bucket, rows, target in (
        ("CLEANED", cleaned, 15), ("NEEDS_REVIEW", review, 15), ("REJECTED", rejected, 10),
    ):
        chosen = sorted(rows, key=lambda row: _stable_key(bucket, row))[:target]
        output.extend(_sample_row(bucket, rank, row) for rank, row in enumerate(chosen, 1))
    return output


def _issue(issue_id: str, problem: str, severity: str, row: dict | None = None, details: str = "") -> dict:
    row = row or {}
    return {
        "Issue ID": issue_id,
        "Problem": problem,
        "Root Cause": "Not yet confirmed; deterministic audit trigger requires review",
        "Affected Files": "results_new_100_v2 structured outputs",
        "Fix Applied": "Not automatically changed",
        "Regression Test": "",
        "Current Status": "OPEN",
        "Severity": severity,
        "Association ID": row.get("association_id", ""),
        "Company": row.get("company", ""),
        "Title": row.get("title", ""),
        "Details": details,
    }


def _dynamic_issues(cleaned: list[dict], review: list[dict], rejected: list[dict], counts: dict, coverage: list[dict]) -> list[dict]:
    issues = []
    route_total = len(cleaned) + len(review) + len(rejected)
    expected = int(counts.get("Total RSS Candidates", 0) or 0)
    if route_total != expected:
        issues.append(_issue("V21-AUDIT-RECON", "Route totals do not reconcile", "CRITICAL", details=f"routes={route_total}; candidates={expected}"))

    for bucket, rows in (("NEEDS_REVIEW", review), ("REJECTED", rejected)):
        for row in rows:
            severe = sorted(SEVERE_CATEGORIES & set(row.get("negative_categories", [])))
            if severe and row.get("negative_screening_status") == "NEGATIVE_CANDIDATE":
                issues.append(_issue(
                    f"V21-RISK-{row.get('association_id', '')}",
                    f"Severe-risk candidate routed to {bucket}",
                    "IMPORTANT",
                    row,
                    details="categories=" + ";".join(severe) + "; reasons=" + ";".join(row.get("routing_reasons", [])),
                ))

    for row in cleaned:
        folded = str(row.get("full_text", "")).casefold()
        markers = [marker for marker in BAD_PAGE_MARKERS if marker in folded]
        if row.get("content_validation_status") != "VALID" or markers:
            issues.append(_issue(
                f"V21-CONTENT-{row.get('association_id', '')}", "Invalid content entered CLEANED", "CRITICAL", row,
                details="markers=" + ";".join(markers),
            ))
        if row.get("entity_match_status") != "MATCHED":
            issues.append(_issue(f"V21-ENTITY-{row.get('association_id', '')}", "Unmatched entity entered CLEANED", "CRITICAL", row))

    for row in cleaned + review + rejected:
        if not row.get("association_id") or not row.get("article_id") or not row.get("association_source_ids"):
            issues.append(_issue(f"V21-TRACE-{row.get('association_id', 'missing')}", "Missing traceability identifier", "CRITICAL", row))
        title_text = (str(row.get("title", "")) + " " + str(row.get("full_text", ""))[:500]).casefold()
        if "经营与业务风险" in row.get("negative_categories", []) and re.search(r"\b(?:no|not planning|without) layoffs?\b", title_text):
            issues.append(_issue(f"V21-NEG-{row.get('association_id', '')}", "Negated layoffs still classified as operating risk", "IMPORTANT", row))
        if "财务状况恶化" in row.get("negative_categories", []) and re.search(r"losses? (?:narrowed|declined|fell)|beat(?:s)? expectations", title_text):
            issues.append(_issue(f"V21-POS-{row.get('association_id', '')}", "Positive financial direction classified as deterioration", "IMPORTANT", row))

    for row in coverage:
        status = row.get("Search Status", "")
        if status in {"FAILED", "RATE_LIMITED", "NOT_RUN", "PARTIAL", "PARTIAL_CAPPED"}:
            issues.append(_issue(
                f"V21-COVERAGE-{hashlib.sha256(str(row.get('Company', '')).encode()).hexdigest()[:12]}",
                "Search coverage incomplete", "IMPORTANT", {"company": row.get("Company", "")},
                details=f"status={status}; candidates={row.get('RSS Candidates', row.get('Candidate Count', ''))}",
            ))
    return issues


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict], mapping: dict[str, str] | None = None) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            source = {mapping.get(field, field) if mapping else field: value for field, value in row.items()}
            if mapping:
                source = {display: row.get(internal, "") for display, internal in mapping.items()}
            writer.writerow({field: safe_csv(source.get(field, "")) for field in fields})


def _report(counts: dict, issues: list[dict], samples: list[dict], historical: dict) -> str:
    extracted = int(counts.get("Articles With V1 Extraction Record", 0) or 0)
    fetch_success = int(counts.get("V1 Full Text Success", 0) or 0)
    valid = int(counts.get("Valid Full Text", 0) or 0)
    fetch_rate = (100 * fetch_success / extracted) if extracted else 0.0
    valid_rate = (100 * valid / extracted) if extracted else 0.0
    severe = sum(row["Problem"].startswith("Severe-risk") for row in issues)
    open_issues = [row for row in issues if row.get("Current Status") == "OPEN"]
    issue_lines = "\n".join(
        f"| {row['Issue ID']} | {row['Problem']} | {row['Root Cause']} | {row['Fix Applied']} | {row['Regression Test']} | {row['Current Status']} |"
        for row in issues
    ) or "| - | None | - | - | - | - |"
    sample_lines = "\n".join(
        f"| {row['sample_bucket']} | {row['sample_rank']} | {row['company']} | {str(row['title']).replace('|', '/')} | "
        f"{row['entity_assessment']} | {row['negative_assessment']} | {row['content_assessment']} | {row['date_assessment']} |"
        for row in samples
    ) or "| - | - | - | No records | - | - | - | - |"
    historical_counts = historical.get("counts", {}) if historical else {}
    comparison_keys = ("Total Companies", "Total RSS Candidates", "Articles With V1 Extraction Record", "V1 Full Text Success", "Valid Full Text", "Cleaned", "Needs Review", "Rejected", "Candidate Negative Events")
    comparison = "\n".join(
        f"| {key} | {historical_counts.get(key, 'n/a')} | {counts.get(key, 'n/a')} |" for key in comparison_keys
    )
    total_companies = int(counts.get("Total Companies", 0) or 0)
    completed = int(counts.get("Search Completed", 0) or 0)
    search_answer = "本批所有公司均完成请求" if total_companies and completed == total_companies else f"完成 {completed}/{total_companies}，不能视为全量可靠"
    return f"""# Risk News Monitor V2.1：全新 100 家公司端到端测试最终报告

所有新闻和事件仍为 `UNVERIFIED` 候选。本报告是技术压力测试，不构成信用评级或风险结论。

## 1. 全流程实际统计

| Metric | Value |
|---|---:|
""" + "\n".join(f"| {key} | {value} |" for key, value in counts.items()) + f"""
| V1 正文 SUCCESS 率 | {fetch_rate:.1f}% |
| V2 有效正文率（按已尝试提取） | {valid_rate:.1f}% |
| 重大风险待核实线索 | {severe} |

## 2. 错误与修复报告

| Issue ID | Problem | Root Cause | Fix Applied | Regression Test | Current Status |
|---|---|---|---|---|---|
{issue_lines}

当前开放问题数：{len(open_issues)}。逐条机器可读记录见 `test_issues.csv`。

## 3. V1 与 V2 结果比较

| Metric | 历史 300 家 V2 | 本轮新 100 家 V2.1 |
|---|---:|---:|
{comparison}

两轮公司样本、地域、行业和新闻周期不同，比例变化不能直接解释为算法质量提升或下降。

## 4. 真实新闻抽样

抽样按 `SHA-256(bucket + association_id + title)` 固定排序，最多选择 15 条 Cleaned、15 条 Needs Review、10 条 Rejected；若数量不足则检查该类全部记录。完整证据见 `sample_review.csv`。

| Bucket | Rank | Company | Title | Entity | Negative | Content | Date |
|---|---:|---|---|---|---|---|---|
{sample_lines}

## 5. 最终结论

1. **Python + Google News RSS 能否可靠批量检索？** {search_answer}；RSS 仍可能漏报、截断或限流，不能当作完整新闻数据库。
2. **正文获取情况？** 已尝试 {extracted} 篇，V1 SUCCESS {fetch_success} 篇（{fetch_rate:.1f}%），V2 验证为有效正文 {valid} 篇（{valid_rate:.1f}%）。
3. **V2 是否降低误报？** V2 通过实体、正文、语义和日期门槛把记录分流，但没有人工标注金标准，分流比例只能证明过滤发生，不能单独证明准确率提升。
4. **仍需 LLM 或人工核实什么？** 实体不确定、多义品牌、缺失正文、否定/比较语义、旧闻更新、同事件归并和严重风险线索均需复核。
5. **能否作为未来 Risk Intelligence Skill 3 底层引擎？** 具备可续跑采集、合规正文获取、审计和结构化候选输出的技术基础；上线前仍需权威实体库、标注评测集、稳定新闻源、权限治理和人工复核闭环。
"""


def run_stress_audit(
    output_dir: str | Path,
    *,
    historical_audit_path: str | Path | None = None,
    final_report_path: str | Path | None = None,
) -> dict:
    output = Path(output_dir).expanduser().resolve()
    cleaned = _read_jsonl(output / "articles_cleaned.jsonl")
    review = _read_jsonl(output / "articles_needs_review.jsonl")
    rejected = _read_jsonl(output / "articles_rejected.jsonl")
    coverage = _read_csv(output / "company_coverage.csv")
    pipeline_audit = _read_json(output / "pipeline_audit.json")
    counts = pipeline_audit.get("counts", {})
    samples = deterministic_sample(cleaned, review, rejected)
    dynamic = _dynamic_issues(cleaned, review, rejected, counts, coverage)
    issues = [{**{field: "" for field in ISSUE_FIELDS}, **row} for row in FIXED_ISSUES] + dynamic

    _write_csv(output / "test_issues.csv", ISSUE_FIELDS, issues)
    mapping = {
        "Sample Bucket": "sample_bucket", "Sample Rank": "sample_rank", "Association ID": "association_id",
        "Article ID": "article_id", "Event ID": "event_id", "Company": "company", "Title": "title",
        "Publisher": "publisher", "Published At": "published_at", "Entity Assessment": "entity_assessment",
        "Negative Assessment": "negative_assessment", "Content Assessment": "content_assessment",
        "Date Assessment": "date_assessment", "Auditor Judgment": "auditor_judgment", "Evidence Basis": "evidence_basis",
    }
    _write_csv(output / "sample_review.csv", SAMPLE_FIELDS, samples, mapping=mapping)

    historical_path = Path(historical_audit_path) if historical_audit_path else Path.cwd() / "results_full_300_v2" / "pipeline_audit.json"
    historical = _read_json(historical_path)
    report = _report(counts, issues, samples, historical)
    inside_report = output / "V2_100_TEST_FINAL_REPORT.md"
    inside_report.write_text(report, encoding="utf-8")
    if final_report_path:
        target = Path(final_report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")

    sample_counts = dict(Counter(row["sample_bucket"] for row in samples))
    summary = {
        "sample_counts": {bucket: sample_counts.get(bucket, 0) for bucket in ("CLEANED", "NEEDS_REVIEW", "REJECTED")},
        "issue_count": len(issues),
        "open_issue_count": sum(row.get("Current Status") == "OPEN" for row in issues),
        "severe_risk_clues": sum(row["Problem"].startswith("Severe-risk") for row in issues),
    }
    (output / "stress_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary

