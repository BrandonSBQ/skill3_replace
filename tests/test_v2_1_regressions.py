import csv
import json

from risk_news_v2.classification import classify_negative
from risk_news_v2.company_catalog import write_company_catalog
from risk_news_v2.entity_resolution import resolve_entity
from risk_news_v2.pipeline import _route, clean_existing


def matched_entity():
    return {
        "entity_match_status": "MATCHED",
        "entity_match_confidence": 0.9,
        "entity_relationship": "DIRECT",
    }


def test_safran_film_producer_is_not_aerospace_company_match():
    result = resolve_entity(
        "Safran",
        "Peter Safran discusses the next DC Studios film slate",
        "Producer Peter Safran spoke in Hollywood about upcoming superhero movies.",
        "Entertainment Weekly",
    )
    assert result["entity_match_status"] in {"UNRELATED", "UNCERTAIN"}
    assert result["entity_relationship"] != "DIRECT"


def test_catalog_chinese_alias_and_context_resolve_new_company():
    metadata = {
        "legal_name": "Bank of China Limited",
        "display_name": "Bank of China",
        "aliases": ["BOC", "中国银行"],
        "positive_context": ["bank", "银行", "贷款"],
        "negative_context": [],
    }
    result = resolve_entity(
        "Bank of China Limited",
        "中国银行因贷款业务接受监管调查",
        "监管机构表示调查涉及该银行的贷款业务。",
        "财新",
        metadata=metadata,
    )
    assert result["entity_match_status"] == "MATCHED"
    assert result["matched_entity"] == "Bank of China Limited"
    assert result["entity_match_confidence"] >= 0.8


def test_bank_of_china_does_not_match_peoples_bank_of_china_substring():
    metadata = {
        "display_name": "Bank of China",
        "aliases": ["BOC", "中国银行"],
        "positive_context": ["bank", "lending", "deposits"],
        "negative_context": ["People's Bank of China", "中国人民银行", "central bank"],
    }
    result = resolve_entity(
        "Bank of China Limited",
        "China authorities halt a cryptocurrency campaign",
        "The People's Bank of China said the central bank is preparing an investigation.",
        metadata=metadata,
    )
    assert result["entity_match_status"] != "MATCHED"
    assert result["entity_relationship"] != "DIRECT"


def test_cmb_acronym_does_not_override_capital_markets_board_context():
    metadata = {
        "display_name": "China Merchants Bank",
        "aliases": ["CMB", "招商银行"],
        "positive_context": ["bank", "lending", "deposits", "capital"],
        "negative_context": ["Capital Markets Board", "SPK"],
    }
    result = resolve_entity(
        "China Merchants Bank Co., Ltd.",
        "Former CMB deputy chairman arrested in fund investigation",
        "The former Capital Markets Board (SPK) deputy chairman was arrested in Istanbul.",
        metadata=metadata,
    )
    assert result["entity_match_status"] != "MATCHED"
    assert result["entity_relationship"] != "DIRECT"


def test_no_layoffs_negation_does_not_create_operating_risk():
    result = classify_negative(
        "Company says there will be no layoffs after the merger",
        "Management said it is not planning layoffs and will retain all employees.",
        matched_entity(),
    )
    assert "经营与业务风险" not in result["negative_categories"]
    assert result["negative_screening_status"] == "NOT_NEGATIVE"


def test_narrowing_losses_and_positive_results_are_not_financial_deterioration():
    result = classify_negative(
        "Company beats expectations as losses narrow sharply",
        "Quarterly material losses narrowed by 80 percent, revenue rose and management expects a return to profit.",
        matched_entity(),
    )
    assert "财务状况恶化" not in result["negative_categories"]
    assert result["negative_screening_status"] == "NOT_NEGATIVE"


def test_money_laundering_class_action_is_a_negative_candidate():
    result = classify_negative(
        "Court certifies class-action suit against TD Bank regarding money laundering",
        "The lawsuit alleges deficiencies in the anti-money laundering program and says regulators fined the bank.",
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert set(result["negative_categories"]) & {"监管调查及处罚", "欺诈及公司治理", "重大诉讼"}


def test_aircraft_braking_fault_serious_incident_is_operating_risk():
    result = classify_negative(
        "Airline aircraft tyres burst after braking system fault, investigation finds",
        "The safety authority found a serious incident after the anti-skid system was disabled by a persistent fault.",
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "经营与业务风险" in result["negative_categories"]


def test_forward_looking_boilerplate_does_not_turn_dividend_release_negative():
    result = classify_negative(
        "Company declares quarterly dividend",
        (
            "The company announced a quarterly dividend following solid performance. "
            "Forward-Looking Statements: future results may be affected by corruption, "
            "litigation, shutdowns, sanctions and other hypothetical risks."
        ),
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NOT_NEGATIVE"
    assert result["negative_categories"] == []


def test_job_cut_word_order_is_operating_risk():
    result = classify_negative(
        "Vodafone to cut 2,300 jobs in restructuring",
        "",
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "经营与业务风险" in result["negative_categories"]


def test_vehicle_recall_wording_is_operating_risk():
    result = classify_negative(
        "Commerce ministry recalls 2,371 Kia vehicles over fuel leakage defect",
        "The ministry announced the recall because leakage could increase the risk of fire.",
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "经营与业务风险" in result["negative_categories"]


def test_company_currently_being_sued_is_litigation_candidate():
    result = classify_negative(
        "Mining company faces pollution lawsuit",
        "Residents are suing the company over alleged pollution in a 6.3 million dollar claim.",
        matched_entity(),
    )
    assert result["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "重大诉讼" in result["negative_categories"]


def test_date_conflict_routes_otherwise_clean_candidate_to_review():
    row = {
        "content_validation_status": "VALID",
        "entity_match_status": "MATCHED",
        "entity_match_confidence": 0.9,
        "entity_relationship": "DIRECT",
        "negative_screening_status": "NEGATIVE_CANDIDATE",
        "date_validation_status": "CONFLICT",
    }
    route, reasons = _route(row)
    assert route == "NEEDS_REVIEW"
    assert "date_conflict" in reasons


def test_pipeline_loads_catalog_aliases_from_acquisition_directory(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    metadata = {
        "legal_name": "Bank of China Limited",
        "display_name": "Bank of China",
        "aliases": ["BOC", "中国银行"],
        "ticker": "3988.HK",
        "parent_company": "",
        "region": "China/Hong Kong",
        "country": "China",
        "industry": "Banking",
        "languages": ["en", "zh-CN"],
        "positive_context": ["bank", "银行", "贷款"],
        "negative_context": [],
    }
    write_company_catalog(input_dir / "company_list_1.csv", [metadata])
    candidate = {
        "Company": "Bank of China Limited",
        "Title": "中国银行因贷款业务接受监管调查",
        "Published UTC": "2026-11-10T04:00:00+00:00",
        "Publisher": "财新",
        "Google News URL": "https://news.google.com/rss/articles/boc",
        "Possible Negative Types": "监管调查",
        "Screening Basis": "TITLE_KEYWORD",
        "Confidence": "UNVERIFIED",
        "Review Status": "PENDING_REVIEW",
    }
    with (input_dir / "negative_news_candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidate))
        writer.writeheader()
        writer.writerow(candidate)
    (input_dir / "coverage_300.csv").write_text(
        "No.,Company,Search Status,Candidate Count\n1,Bank of China Limited,SUCCESS,1\n", encoding="utf-8-sig"
    )
    body = "\n".join([
        "中国银行因贷款业务接受监管机构正式调查。",
        "监管机构称调查涉及该银行部分贷款审批流程。",
        "中国银行表示将配合调查并向投资者披露进展。",
        "有关程序可能导致处罚及业务整改要求。",
    ] * 8)
    extraction = {
        "article_id": "legacy-boc",
        "company": "Bank of China Limited",
        "title": candidate["Title"],
        "publisher": "财新",
        "published_utc": candidate["Published UTC"],
        "google_news_url": candidate["Google News URL"],
        "original_url": "https://publisher.example/boc",
        "final_url": "https://publisher.example/boc",
        "full_text": body,
        "text_length": len(body),
        "extracted_date": "2026-11-10",
        "fetch_status": "SUCCESS",
        "error": "",
    }
    (input_dir / "articles_with_content.jsonl").write_text(json.dumps(extraction, ensure_ascii=False) + "\n", encoding="utf-8")
    clean_existing(input_dir, output_dir)
    records = [
        json.loads(line)
        for name in ("articles_cleaned.jsonl", "articles_needs_review.jsonl", "articles_rejected.jsonl")
        for line in (output_dir / name).read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["entity_match_status"] == "MATCHED"
    assert records[0]["matched_entity"] == "Bank of China Limited"
    assert records[0]["region"] == "China/Hong Kong"

