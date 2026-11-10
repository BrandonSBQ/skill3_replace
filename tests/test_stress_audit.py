import csv
import json
from pathlib import Path

from risk_news_v2.stress_audit import deterministic_sample, run_stress_audit


def record(index, bucket):
    statuses = {
        "CLEANED": ("VALID", "MATCHED", "NEGATIVE_CANDIDATE"),
        "NEEDS_REVIEW": ("UNAVAILABLE", "MATCHED", "NEGATIVE_CANDIDATE"),
        "REJECTED": ("INVALID", "UNRELATED", "UNRELATED"),
    }
    content, entity, negative = statuses[bucket]
    return {
        "association_id": f"assoc-{bucket}-{index:03d}",
        "article_id": f"art-{index:03d}",
        "event_id": f"evt-{index // 2:03d}" if negative == "NEGATIVE_CANDIDATE" else "",
        "company": f"Company {index % 20:02d}",
        "title": f"Deterministic sample story {index:03d}",
        "publisher": "Example Wire",
        "published_at": "2026-11-10T04:00:00+00:00",
        "rss_published_at": "2026-11-10T04:00:00+00:00",
        "article_published_at": "2026-11-10T00:00:00+00:00",
        "content_validation_status": content,
        "content_quality_score": 90 if content == "VALID" else 0,
        "content_validation_reason": "fixture reason",
        "entity_match_status": entity,
        "entity_match_confidence": 0.9 if entity == "MATCHED" else 0.05,
        "entity_relationship": "DIRECT" if entity == "MATCHED" else "UNRELATED",
        "entity_match_evidence": "fixture entity evidence",
        "negative_screening_status": negative,
        "negative_categories": ["监管调查及处罚"] if negative == "NEGATIVE_CANDIDATE" else [],
        "negative_screening_evidence": "fixture negative evidence",
        "date_validation_status": "CONSISTENT",
        "date_validation_reason": "fixture date evidence",
        "source_ids": [f"source-{index:03d}"],
        "association_source_ids": [f"source-{index:03d}"],
        "review_status": bucket,
        "routing_reasons": [],
        "full_text": "Detailed article facts. " * 20 if content == "VALID" else "",
        "fetch_status": "SUCCESS" if content == "VALID" else "ACCESS_DENIED",
    }


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def build_output(path):
    path.mkdir()
    cleaned = [record(index, "CLEANED") for index in range(20)]
    review = [record(100 + index, "NEEDS_REVIEW") for index in range(18)]
    rejected = [record(200 + index, "REJECTED") for index in range(12)]
    rejected[0]["negative_screening_status"] = "NEGATIVE_CANDIDATE"
    rejected[0]["negative_categories"] = ["债务违约与偿付风险"]
    rejected[0]["entity_match_status"] = "MATCHED"
    write_jsonl(path / "articles_cleaned.jsonl", cleaned)
    write_jsonl(path / "articles_needs_review.jsonl", review)
    write_jsonl(path / "articles_rejected.jsonl", rejected)
    write_jsonl(path / "events_candidates.jsonl", [{"event_id": f"evt-{i:03d}", "company": "Company"} for i in range(10)])
    coverage_fields = ["Company", "Search Status", "RSS Candidates", "Valid Full Text", "Entity Matched", "Entity Uncertain", "Unrelated Articles", "Missing Full Text"]
    with (path / "company_coverage.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=coverage_fields)
        writer.writeheader()
        for index in range(100):
            writer.writerow({"Company": f"Company {index:02d}", "Search Status": "SUCCESS", "RSS Candidates": 1, "Valid Full Text": 1, "Entity Matched": 1, "Entity Uncertain": 0, "Unrelated Articles": 0, "Missing Full Text": 0})
    (path / "pipeline_audit.json").write_text(json.dumps({
        "counts": {
            "Total Companies": 100,
            "Search Completed": 100,
            "Search Partial": 0,
            "Total RSS Candidates": 50,
            "Total Articles Processed": 50,
            "Articles With V1 Extraction Record": 50,
            "V1 Full Text Success": 20,
            "Valid Full Text": 20,
            "Entity Matched": 38,
            "Entity Uncertain": 0,
            "Unrelated Articles": 12,
            "Duplicate Articles": 0,
            "Candidate Negative Events": 10,
            "Needs Review": 18,
            "Rejected": 12,
            "Missing Full Text": 18,
            "Cleaned": 20,
        }
    }), encoding="utf-8")
    (path / "article_fetch_summary.json").write_text(json.dumps({"selected_articles": 50, "processed_articles": 50, "full_text_success": 20}), encoding="utf-8")
    return cleaned, review, rejected


def test_deterministic_sample_is_reproducible_and_stratified():
    cleaned = [record(index, "CLEANED") for index in range(20)]
    review = [record(100 + index, "NEEDS_REVIEW") for index in range(18)]
    rejected = [record(200 + index, "REJECTED") for index in range(12)]
    first = deterministic_sample(cleaned, review, rejected)
    second = deterministic_sample(cleaned, review, rejected)
    assert first == second
    assert sum(row["sample_bucket"] == "CLEANED" for row in first) == 15
    assert sum(row["sample_bucket"] == "NEEDS_REVIEW" for row in first) == 15
    assert sum(row["sample_bucket"] == "REJECTED" for row in first) == 10
    assert all(row["evidence_basis"] for row in first)


def test_stress_audit_writes_issues_samples_and_required_report(tmp_path):
    output = tmp_path / "results"
    build_output(output)
    report = tmp_path / "V2_100_TEST_FINAL_REPORT.md"
    summary = run_stress_audit(output, final_report_path=report)
    assert summary["sample_counts"] == {"CLEANED": 15, "NEEDS_REVIEW": 15, "REJECTED": 10}
    assert (output / "test_issues.csv").exists()
    assert (output / "sample_review.csv").exists()
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    for heading in ("全流程实际统计", "错误与修复报告", "V1 与 V2 结果比较", "真实新闻抽样", "最终结论"):
        assert heading in text
    issues = list(csv.DictReader((output / "test_issues.csv").open(encoding="utf-8-sig")))
    assert any(row["Problem"] == "Severe-risk candidate routed to REJECTED" for row in issues)


def test_reconciliation_mismatch_becomes_explicit_issue(tmp_path):
    output = tmp_path / "results"
    build_output(output)
    audit_path = output / "pipeline_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["counts"]["Total RSS Candidates"] = 51
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    run_stress_audit(output, final_report_path=tmp_path / "report.md")
    issues = list(csv.DictReader((output / "test_issues.csv").open(encoding="utf-8-sig")))
    assert any(row["Problem"] == "Route totals do not reconcile" and row["Severity"] == "CRITICAL" for row in issues)


def test_repeated_audit_produces_same_sample_file(tmp_path):
    output = tmp_path / "results"
    build_output(output)
    report = tmp_path / "report.md"
    run_stress_audit(output, final_report_path=report)
    first = (output / "sample_review.csv").read_bytes()
    run_stress_audit(output, final_report_path=report)
    assert (output / "sample_review.csv").read_bytes() == first

