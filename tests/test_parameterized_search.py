import csv
import json
from datetime import datetime, timezone

from risk_news_v2.company_catalog import load_company_catalog
from search_300_companies import (
    build_search_query,
    export,
    main,
    process_one,
    read_checkpoints,
)
from run_pipeline import build_parser


def profile(name="Bank of China Limited"):
    return {
        "legal_name": name,
        "display_name": "Bank of China",
        "aliases": ["BOC", "中国银行"],
        "ticker": "3988.HK",
        "parent_company": "",
        "region": "China/Hong Kong",
        "country": "China",
        "industry": "Banking",
        "languages": ["en", "zh-CN"],
        "positive_context": ["bank"],
        "negative_context": [],
    }


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def fetch(self, company, days, terms=None):
        self.calls.append((company, days, list(terms or [])))
        return list(self.items)


def config(max_records=100):
    return {
        "days": 7,
        "max_records": max_records,
        "start_utc": "2026-11-03T00:00:00+00:00",
        "end_utc": "2026-11-10T23:59:59+00:00",
    }


def item(title="Bank of China faces regulatory investigation"):
    return {
        "title": title,
        "link": "https://news.google.com/rss/articles/example",
        "publisher": "Reuters",
        "published": datetime(2026, 11, 10, 4, tzinfo=timezone.utc),
    }


def test_bilingual_query_contains_legal_name_aliases_negative_terms_and_window():
    query = build_search_query(profile(), 7)
    assert '"Bank of China Limited"' in query
    assert '"中国银行"' in query
    assert "default OR bankruptcy" in query
    assert "when:7d" in query


def test_successful_empty_response_is_no_candidate_found_not_failed():
    client = FakeClient([])
    result = process_one(profile(), client, config())
    assert result["status"] == "NO_CANDIDATE_FOUND"
    assert result["found"] == 0
    assert result["query_terms"] == ["Bank of China Limited", "Bank of China", "BOC", "中国银行"]
    assert result["languages"] == ["en", "zh-CN"]
    assert client.calls[0][2] == result["query_terms"]


def test_result_at_configured_limit_is_partial_capped():
    client = FakeClient([item("Bank of China defaults on bond payment"), item("Bank of China faces lawsuit")])
    result = process_one(profile(), client, config(max_records=2))
    assert result["status"] == "PARTIAL_CAPPED"
    assert len(result["articles"]) == 2
    assert all(row["Search Query"] == result["search_query"] for row in result["articles"])


def test_dynamic_export_uses_custom_company_count_and_metadata(tmp_path):
    profiles = [profile(), profile("Example Energy Limited")]
    profiles[1].update(display_name="Example Energy", aliases=["Example Energy"], ticker="EXE", region="Europe", country="France", industry="Energy", languages=["en"])
    records = {
        profiles[0]["legal_name"]: process_one(profiles[0], FakeClient([]), config()),
        profiles[1]["legal_name"]: process_one(profiles[1], FakeClient([item("Example Energy faces fine")]), config()),
    }
    summary = export(tmp_path, records, config(), profiles=profiles)
    assert summary["company_count"] == 2
    assert summary["counts"]["NO_CANDIDATE_FOUND"] == 1
    assert (tmp_path / "company_list_2.csv").exists()
    coverage = list(csv.DictReader((tmp_path / "coverage_300.csv").open(encoding="utf-8-sig")))
    assert len(coverage) == 2
    assert {row["Company"] for row in coverage} == {"Bank of China Limited", "Example Energy Limited"}


def test_checkpoint_reader_accepts_only_current_catalog_companies(tmp_path):
    checkpoint = tmp_path / "checkpoints.jsonl"
    checkpoint.write_text(
        json.dumps({"company": "Bank of China Limited", "status": "SUCCESS", "articles": []}) + "\n"
        + json.dumps({"company": "Apple", "status": "SUCCESS", "articles": []}) + "\n",
        encoding="utf-8",
    )
    records = read_checkpoints(checkpoint, allowed_companies={"Bank of China Limited"})
    assert set(records) == {"Bank of China Limited"}


def test_custom_catalog_dry_run_exports_all_100_without_network(tmp_path):
    catalog = "test_new_100/company_list_100.csv"
    assert len(load_company_catalog(catalog)) == 100
    assert main(["--company-file", catalog, "--limit", "100", "--output", str(tmp_path), "--dry-run"]) == 0
    coverage = list(csv.DictReader((tmp_path / "coverage_300.csv").open(encoding="utf-8-sig")))
    assert len(coverage) == 100
    assert all(row["Search Status"] == "NOT_RUN" for row in coverage)


def test_full_pipeline_parser_accepts_company_catalog():
    args = build_parser().parse_args([
        "--mode", "full", "--company-file", "test_new_100/company_list_100.csv", "--allow-network"
    ])
    assert args.company_file.endswith("company_list_100.csv")

