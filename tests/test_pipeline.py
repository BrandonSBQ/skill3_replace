import csv
import json
from pathlib import Path

import pytest

from risk_news_v2.pipeline import OUTPUT_FILES, clean_existing, safe_csv
from run_pipeline import main


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def candidate(company, title, url, publisher="Reuters"):
    return {
        "Company": company,
        "Title": title,
        "Published UTC": "2026-11-10T04:00:00+00:00",
        "Publisher": publisher,
        "Google News URL": url,
        "Possible Negative Types": "监管调查",
        "Screening Basis": "TITLE_KEYWORD",
        "Confidence": "UNVERIFIED",
        "Review Status": "PENDING_REVIEW",
    }


def extracted(row, text, status="SUCCESS", original_url=None, article_id="legacy"):
    return {
        "article_id": article_id,
        "company": row["Company"],
        "title": row["Title"],
        "publisher": row["Publisher"],
        "published_utc": row["Published UTC"],
        "google_news_url": row["Google News URL"],
        "original_url": original_url or row["Google News URL"].replace("news.google.com/rss/articles", "publisher.example"),
        "final_url": original_url or row["Google News URL"].replace("news.google.com/rss/articles", "publisher.example"),
        "possible_negative_types": row["Possible Negative Types"],
        "screening_basis": row["Screening Basis"],
        "full_text": text,
        "text_length": len(text),
        "extracted_title": row["Title"],
        "extracted_date": "2026-11-10",
        "fetch_status": status,
        "error": "" if status == "SUCCESS" else status,
        "retrieved_utc": "2026-11-10T05:00:00+00:00",
    }


def build_fixture(input_dir):
    input_dir.mkdir()
    rows = [
        candidate("Apple", "Regulator opens Apple App Store investigation", "https://news.google.com/rss/articles/apple1"),
        candidate("Apple", "Apple App Store regulator investigation continues", "https://news.google.com/rss/articles/apple2"),
        candidate("Alphabet Inc", "Google faces advertising regulator investigation", "https://news.google.com/rss/articles/google1"),
        candidate("Microsoft", "Microsoft enables security feature by default", "https://news.google.com/rss/articles/ms1"),
        candidate("BP", "BP football league announces weekend fixtures", "https://news.google.com/rss/articles/bp1", "Sports Daily"),
    ]
    write_csv(
        input_dir / "negative_news_candidates.csv",
        list(rows[0]),
        rows,
    )
    coverage = [
        {"No.": 1, "Company": "Apple", "Search Status": "SUCCESS", "Candidate Count": 2, "RSS Items": 2, "Out of Window": 0, "Result Capped": "NO", "Error": ""},
        {"No.": 2, "Company": "Alphabet Inc", "Search Status": "SUCCESS", "Candidate Count": 1, "RSS Items": 1, "Out of Window": 0, "Result Capped": "NO", "Error": ""},
        {"No.": 3, "Company": "Microsoft", "Search Status": "PARTIAL_CAPPED", "Candidate Count": 1, "RSS Items": 100, "Out of Window": 0, "Result Capped": "YES", "Error": ""},
        {"No.": 4, "Company": "BP", "Search Status": "SUCCESS", "Candidate Count": 1, "RSS Items": 1, "Out of Window": 0, "Result Capped": "NO", "Error": ""},
        {"No.": 5, "Company": "Tesla", "Search Status": "SUCCESS", "Candidate Count": 0, "RSS Items": 0, "Out of Window": 0, "Result Capped": "NO", "Error": ""},
    ]
    write_csv(input_dir / "coverage_300.csv", list(coverage[0]), coverage)
    apple_text = "\n".join([
        "Regulators opened an App Store investigation into Apple on Monday.",
        "The authority said the investigation concerns the company's distribution rules.",
        "Apple said it would cooperate and described its response to the allegations.",
        "The proceeding could lead to a penalty and changes to business practices.",
    ] * 4)
    google_text = "\n".join([
        "A regulator opened an advertising investigation into Google on Tuesday.",
        "The authority is examining conduct in the digital advertising market.",
        "Google said it would cooperate with the formal investigation.",
        "The case could result in penalties and required changes to the business.",
    ] * 4)
    microsoft_text = "\n".join([
        "Microsoft enables the security feature by default in its software release.",
        "Administrators can change the default setting in the preferences menu.",
        "The company documented the feature and provided deployment instructions.",
        "No debt, credit, liquidity, legal, or regulatory event was reported.",
    ] * 4)
    records = [
        extracted(rows[0], apple_text, original_url="https://publisher.example/apple-investigation", article_id="legacy-apple-good"),
        extracted(rows[1], "", status="ACCESS_DENIED", original_url="https://blocked.example/apple", article_id="legacy-apple-blocked"),
        extracted(rows[2], google_text, original_url="https://publisher.example/google-investigation", article_id="legacy-google"),
        extracted(rows[3], microsoft_text, original_url="https://publisher.example/microsoft-default", article_id="legacy-ms"),
    ]
    with (input_dir / "articles_with_content.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.write("{malformed json\n")
    (input_dir / "run_summary.json").write_text(json.dumps({"candidate_articles": 5}), encoding="utf-8")
    (input_dir / "article_fetch_summary.json").write_text(
        json.dumps({"selected_articles": 4, "processed_articles": 4, "full_text_success": 3}), encoding="utf-8"
    )
    return rows


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_clean_existing_emits_auditable_routed_dataset(tmp_path):
    input_dir = tmp_path / "v1"
    output_dir = tmp_path / "v2"
    build_fixture(input_dir)

    audit = clean_existing(input_dir, output_dir)
    assert set(OUTPUT_FILES) == {path.name for path in output_dir.iterdir() if path.name in OUTPUT_FILES}
    cleaned = read_jsonl(output_dir / "articles_cleaned.jsonl")
    rejected = read_jsonl(output_dir / "articles_rejected.jsonl")
    review = read_jsonl(output_dir / "articles_needs_review.jsonl")
    assert len(cleaned) + len(rejected) + len(review) == 5
    assert all(row["content_validation_status"] == "VALID" for row in cleaned)
    assert all(row["negative_screening_status"] == "NEGATIVE_CANDIDATE" for row in cleaned)
    assert {row["review_status"] for row in cleaned} == {"CLEANED"}
    assert not ({row["association_id"] for row in cleaned} & {row["association_id"] for row in review})

    blocked = next(row for row in review if row["source_ids"] == ["legacy-apple-blocked"])
    assert blocked["content_validation_status"] == "UNAVAILABLE"
    assert blocked["alternative_source_article_ids"]
    subsidiary = next(row for row in cleaned if row["company"] == "Alphabet Inc")
    assert subsidiary["matched_entity"] == "Google"
    assert subsidiary["entity_relationship"] == "SUBSIDIARY"

    assert audit["Total RSS Candidates"] == 5
    assert audit["Total Articles Processed"] == 5
    assert audit["Articles With V1 Extraction Record"] == 4
    assert audit["Malformed Extraction Records"] == 1
    assert audit["Search Completed"] == 4
    assert audit["Search Partial"] == 1
    assert audit["No Candidate Found"] == 1
    assert audit["Cleaned"] == len(cleaned)
    assert audit["Needs Review"] == len(review)
    assert audit["Rejected"] == len(rejected)
    assert json.loads((output_dir / "pipeline_audit.json").read_text(encoding="utf-8"))["counts"] == audit

    coverage = list(csv.DictReader((output_dir / "company_coverage.csv").open(encoding="utf-8-sig")))
    assert len(coverage) == 5
    assert next(row for row in coverage if row["Company"] == "Tesla")["RSS Candidates"] == "0"
    report = (output_dir / "quality_report.md").read_text(encoding="utf-8")
    assert "V1 与 V2" in report
    assert "后续 Agent" in report
    assert "Tesla" in report


def test_empty_inputs_still_emit_complete_zero_count_artifacts(tmp_path):
    input_dir = tmp_path / "empty"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "negative_news_candidates.csv").write_text("Company,Title,Google News URL\n", encoding="utf-8-sig")
    (input_dir / "coverage_300.csv").write_text(
        "No.,Company,Search Status,Candidate Count\n1,Apple,SUCCESS,0\n", encoding="utf-8-sig"
    )
    (input_dir / "articles_with_content.jsonl").write_text("", encoding="utf-8")
    audit = clean_existing(input_dir, output_dir)
    assert all((output_dir / name).exists() for name in OUTPUT_FILES)
    assert audit["Total RSS Candidates"] == 0
    assert audit["Total Articles Processed"] == 0
    assert read_jsonl(output_dir / "articles_cleaned.jsonl") == []


def test_csv_formula_values_are_escaped():
    assert safe_csv("=1+1") == "'=1+1"
    assert safe_csv(" normal") == " normal"


def test_full_mode_requires_explicit_network_authorization(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["--mode", "full", "--input", str(tmp_path / "input"), "--output", str(tmp_path / "out")])
    assert error.value.code == 2


def test_audit_records_when_inputs_came_from_authorized_network_run(tmp_path):
    input_dir = tmp_path / "v1"
    output_dir = tmp_path / "v2"
    build_fixture(input_dir)
    clean_existing(input_dir, output_dir, network_used=True)
    audit = json.loads((output_dir / "pipeline_audit.json").read_text(encoding="utf-8"))
    assert audit["rules"]["network_used"] is True


def test_rejected_invalid_content_does_not_feed_event_candidates(tmp_path):
    input_dir = tmp_path / "v1"
    output_dir = tmp_path / "v2"
    build_fixture(input_dir)
    path = input_dir / "articles_with_content.jsonl"
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record["article_id"] == "legacy-apple-good":
            record["full_text"] = "Client Challenge Verify you are human. " * 30
            record["text_length"] = len(record["full_text"])
        records.append(record)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    clean_existing(input_dir, output_dir)
    rejected = read_jsonl(output_dir / "articles_rejected.jsonl")
    assert any(row["source_ids"] == ["legacy-apple-good"] for row in rejected)
    events = read_jsonl(output_dir / "events_candidates.jsonl")
    assert all("legacy-apple-good" not in event["source_ids"] for event in events)


def test_event_sources_exclude_rejected_cross_company_association(tmp_path):
    input_dir = tmp_path / "v1"
    output_dir = tmp_path / "v2"
    rows = build_fixture(input_dir)
    path = input_dir / "articles_with_content.jsonl"
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            pass
    apple = next(record for record in records if record["article_id"] == "legacy-apple-good")
    bp = extracted(
        rows[4],
        apple["full_text"],
        original_url=apple["original_url"],
        article_id="legacy-bp-wrong-association",
    )
    records.append(bp)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    clean_existing(input_dir, output_dir)
    rejected = read_jsonl(output_dir / "articles_rejected.jsonl")
    assert any(row["company"] == "BP" and "legacy-bp-wrong-association" in row["source_ids"] for row in rejected)
    apple_event = next(event for event in read_jsonl(output_dir / "events_candidates.jsonl") if event["company"] == "Apple")
    assert "legacy-bp-wrong-association" not in apple_event["source_ids"]

