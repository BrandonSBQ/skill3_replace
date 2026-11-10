import pytest

from risk_news_v2.entity_resolution import resolve_entity


def test_direct_company_match_uses_company_context():
    result = resolve_entity(
        "Apple",
        "Apple faces antitrust lawsuit over App Store rules",
        "The technology company said its iPhone and App Store policies comply with the law.",
        "Reuters",
    )
    assert result["entity_match_status"] == "MATCHED"
    assert result["entity_relationship"] == "DIRECT"
    assert result["entity_match_confidence"] >= 0.8
    assert "Apple" in result["entity_match_evidence"]


def test_chinese_alias_matches_canonical_company():
    result = resolve_entity(
        "Apple",
        "苹果公司因应用商店规则面临监管调查",
        "苹果公司表示将配合监管机构调查。",
        "财新",
    )
    assert result["entity_match_status"] == "MATCHED"
    assert result["matched_entity"] == "Apple"
    assert result["entity_match_confidence"] >= 0.8


@pytest.mark.parametrize(
    ("company", "title", "text"),
    [
        ("BP", "BP football league announces weekend fixtures", "The youth football league published its schedule."),
        ("Nasdaq Inc", "Technology shares fall on the Nasdaq index", "The index declined while exchange operator Nasdaq Inc was not discussed."),
        ("Apple", "Apple harvest disrupted by wet weather", "Fruit growers reported lower apple production."),
    ],
)
def test_ambiguous_names_do_not_become_direct_matches(company, title, text):
    result = resolve_entity(company, title, text, "General News")
    assert result["entity_match_status"] in {"UNRELATED", "UNCERTAIN"}
    assert result["entity_relationship"] != "DIRECT"


def test_subsidiary_relationship_is_preserved():
    result = resolve_entity(
        "Alphabet Inc",
        "Google faces a new advertising antitrust penalty",
        "Regulators fined Google after an investigation into its advertising business.",
        "Reuters",
    )
    assert result["entity_match_status"] == "MATCHED"
    assert result["matched_entity"] == "Google"
    assert result["entity_relationship"] == "SUBSIDIARY"


def test_article_without_target_evidence_is_unrelated():
    result = resolve_entity(
        "Microsoft",
        "Airline cancels flights after a winter storm",
        "The carrier warned passengers about airport delays.",
        "Travel Daily",
    )
    assert result["entity_match_status"] == "UNRELATED"
    assert result["entity_relationship"] == "UNRELATED"


def test_multi_company_story_can_match_each_company_association():
    title = "Amazon and Microsoft cut cloud jobs as spending slows"
    text = "Amazon reduced roles at AWS. Microsoft separately cut roles in its Azure cloud unit."
    amazon = resolve_entity("Amazon", title, text, "Reuters")
    microsoft = resolve_entity("Microsoft", title, text, "Reuters")
    assert amazon["entity_match_status"] == "MATCHED"
    assert microsoft["entity_match_status"] == "MATCHED"

