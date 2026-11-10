import pytest

from risk_news_v2.classification import classify_negative
from risk_news_v2.content_quality import validate_content


def matched_entity():
    return {
        "entity_match_status": "MATCHED",
        "entity_match_confidence": 0.9,
        "entity_relationship": "DIRECT",
    }


def test_real_article_is_validated_from_structure_not_fetch_status_alone():
    text = "\n".join(
        [
            "Regulators opened an investigation into the company on Monday.",
            "The filing describes the conduct, the affected customers, and management's response.",
            "The company said it would cooperate and disclosed the matter to investors.",
            "Analysts noted that any penalty could affect future operating costs and cash flow.",
        ]
        * 4
    )
    result = validate_content({"fetch_status": "SUCCESS", "full_text": text, "title": "Company faces investigation"})
    assert result["content_validation_status"] == "VALID"
    assert result["content_quality_score"] >= 75


@pytest.mark.parametrize(
    "phrase",
    ["Client Challenge", "Pardon Our Interruption", "Enable JavaScript", "Access Denied", "Verify you are human"],
)
def test_challenge_pages_are_invalid_even_when_fetch_succeeded(phrase):
    text = (phrase + " Please complete the security check. ") * 30
    result = validate_content({"fetch_status": "SUCCESS", "full_text": text, "title": "News"})
    assert result["content_validation_status"] == "INVALID"
    assert result["content_quality_score"] < 30
    assert phrase.casefold() in result["content_validation_reason"].casefold()


def test_missing_or_blocked_text_is_unavailable():
    result = validate_content({"fetch_status": "ACCESS_DENIED", "full_text": "", "title": "Story"})
    assert result == {
        "content_validation_status": "UNAVAILABLE",
        "content_quality_score": 0,
        "content_validation_reason": "no extracted text; fetch_status=ACCESS_DENIED",
    }


def test_paywall_stub_and_truncated_story_are_not_valid():
    paywall = validate_content({"fetch_status": "SUCCESS", "full_text": "Subscribe now to continue reading this article.", "title": "Story"})
    truncated = validate_content({
        "fetch_status": "SUCCESS",
        "title": "Debt talks continue",
        "full_text": ("The company continued debt talks with lenders. " * 14) + "...",
    })
    assert paywall["content_validation_status"] == "INVALID"
    assert truncated["content_validation_status"] in {"PARTIAL", "NEEDS_REVIEW"}


def test_heavily_repeated_content_is_not_valid():
    text = "Company news navigation menu privacy policy contact us.\n" * 30
    result = validate_content({"fetch_status": "SUCCESS", "full_text": text, "title": "Company news"})
    assert result["content_validation_status"] in {"INVALID", "NEEDS_REVIEW"}
    assert "repeat" in result["content_validation_reason"].casefold()


def test_by_default_is_not_debt_default():
    result = classify_negative(
        "The feature is enabled by default in the new software release",
        "Users can change the default setting from the preferences menu.",
        matched_entity(),
    )
    assert "债务违约与偿付风险" not in result["negative_categories"]
    assert result["negative_screening_status"] == "NOT_NEGATIVE"


def test_credit_rating_downgrade_is_distinct_from_equity_analyst_rating():
    credit = classify_negative(
        "Moody's downgrades issuer credit rating after missed payment",
        "The rating agency lowered the company's senior unsecured debt rating and cited liquidity pressure.",
        matched_entity(),
    )
    equity = classify_negative(
        "Broker downgrades shares to Neutral from Buy",
        "The equity analyst cut the price target after the stock rally.",
        matched_entity(),
    )
    assert credit["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "信用评级变动" in credit["negative_categories"]
    assert "债务违约与偿付风险" in credit["negative_categories"]
    assert "信用评级变动" not in equity["negative_categories"]
    assert equity["negative_screening_status"] == "NOT_NEGATIVE"


def test_regulatory_enforcement_is_stronger_than_policy_discussion():
    enforcement = classify_negative(
        "Regulator fines company after bribery investigation",
        "The authority imposed a $20 million penalty and ordered remediation.",
        matched_entity(),
    )
    policy = classify_negative(
        "New regulation could affect technology companies",
        "Lawmakers discussed proposed rules for the industry.",
        matched_entity(),
    )
    assert enforcement["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert "监管调查及处罚" in enforcement["negative_categories"]
    assert "欺诈及公司治理" in enforcement["negative_categories"]
    assert policy["negative_screening_status"] in {"POSSIBLY_RELEVANT", "NOT_NEGATIVE"}


def test_filed_lawsuit_is_candidate_but_potential_risk_needs_review():
    filed = classify_negative(
        "Customers file class action lawsuit against company",
        "The complaint was filed in federal court and seeks damages.",
        matched_entity(),
    )
    potential = classify_negative(
        "Company may face potential legal risk",
        "No lawsuit has been filed and the discussion is hypothetical.",
        matched_entity(),
    )
    assert "重大诉讼" in filed["negative_categories"]
    assert filed["negative_screening_status"] == "NEGATIVE_CANDIDATE"
    assert potential["negative_screening_status"] == "NEEDS_REVIEW"


def test_unrelated_entity_overrides_negative_keywords():
    entity = {"entity_match_status": "UNRELATED", "entity_match_confidence": 0.05, "entity_relationship": "UNRELATED"}
    result = classify_negative("Company defaults on debt", "Bondholders filed suit.", entity)
    assert result["negative_screening_status"] == "UNRELATED"
    assert result["negative_categories"] == []

