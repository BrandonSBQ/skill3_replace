import json
from pathlib import Path

from risk_news_v2.company_catalog import (
    load_company_catalog,
    query_terms,
    validate_catalog,
    write_catalog_audit,
)
from search_300_companies import COMPANIES


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "test_new_100" / "company_list_100.csv"


def test_actual_catalog_has_100_unique_non_overlapping_companies():
    rows = load_company_catalog(CATALOG)
    audit = validate_catalog(rows, COMPANIES)
    assert audit["Total Companies"] == 100
    assert audit["Internal Duplicates"] == 0
    assert audit["Overlap With Previous 300"] == 0
    assert audit["Regional Counts"] == {
        "China/Hong Kong": 25,
        "Europe": 25,
        "Japan/Korea/APAC": 25,
        "US/Canada": 25,
    }
    assert audit["is_valid"] is True


def test_duplicate_alias_ticker_parent_and_historical_name_are_reported():
    rows = [
        {
            "legal_name": "Fresh Holdings Limited",
            "display_name": "Fresh",
            "aliases": ["Fresh Brand"],
            "ticker": "NEW",
            "parent_company": "",
            "region": "US/Canada",
            "country": "United States",
            "industry": "Retail",
            "languages": ["en"],
            "positive_context": [],
            "negative_context": [],
        },
        {
            "legal_name": "Second Corporation",
            "display_name": "Second",
            "aliases": ["Fresh Brand"],
            "ticker": "NEW",
            "parent_company": "Fresh Holdings Limited",
            "region": "US/Canada",
            "country": "United States",
            "industry": "Retail",
            "languages": ["en"],
            "positive_context": [],
            "negative_context": [],
        },
        {
            "legal_name": "Apple Inc.",
            "display_name": "Apple",
            "aliases": [],
            "ticker": "FAKE",
            "parent_company": "",
            "region": "US/Canada",
            "country": "United States",
            "industry": "Technology",
            "languages": ["en"],
            "positive_context": [],
            "negative_context": [],
        },
    ]
    audit = validate_catalog(rows, COMPANIES)
    assert audit["Internal Duplicates"] >= 3
    assert audit["Overlap With Previous 300"] == 1
    kinds = {item["kind"] for item in audit["duplicate_details"]}
    assert {"alias", "ticker", "parent_company"}.issubset(kinds)


def test_query_terms_include_legal_name_and_bilingual_aliases_without_duplicates():
    row = {
        "legal_name": "Bank of China Limited",
        "display_name": "Bank of China",
        "aliases": ["Bank of China", "中国银行", "BOC", "中国银行"],
    }
    assert query_terms(row) == ["Bank of China Limited", "Bank of China", "中国银行", "BOC"]


def test_audit_writer_round_trips_computed_values(tmp_path):
    rows = load_company_catalog(CATALOG)
    audit = validate_catalog(rows, COMPANIES)
    output = tmp_path / "audit.json"
    write_catalog_audit(output, audit)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["Total Companies"] == 100
    assert saved["Overlap With Previous 300"] == 0

