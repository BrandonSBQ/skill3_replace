from copy import deepcopy

from risk_news_v2.dates import reconcile_dates
from risk_news_v2.deduplication import assign_article_groups, assign_event_groups, normalize_url


def test_date_only_and_offset_timestamps_are_normalized_to_utc_and_hong_kong():
    result = reconcile_dates({
        "published_utc": "2026-11-10T04:00:00+00:00",
        "extracted_date": "2026-11-10",
    })
    assert result["rss_published_at"] == "2026-11-10T04:00:00+00:00"
    assert result["article_published_at"] == "2026-11-10T00:00:00+00:00"
    assert result["published_at_hong_kong"] == "2026-11-10T12:00:00+08:00"
    assert result["date_validation_status"] == "CONSISTENT"
    assert result["article_date_precision"] == "DATE"


def test_large_rss_article_date_difference_is_recorded_as_conflict():
    result = reconcile_dates({
        "published_utc": "2026-11-10T04:00:00Z",
        "extracted_date": "2026-11-01T09:00:00-05:00",
    })
    assert result["date_validation_status"] == "CONFLICT"
    assert result["date_discrepancy_seconds"] == 741600
    assert "RSS" in result["date_validation_reason"]


def test_article_update_date_is_not_used_as_initial_publication_date():
    result = reconcile_dates({
        "published_utc": "2026-11-10T04:00:00Z",
        "extracted_date": "2026-11-10T03:30:00Z",
        "article_updated_at": "2026-11-11T08:00:00Z",
    })
    assert result["published_at"] == "2026-11-10T04:00:00+00:00"
    assert result["article_updated_at"] == "2026-11-11T08:00:00+00:00"


def test_url_normalization_removes_tracking_and_sorts_query():
    left = "HTTPS://Example.COM/news/story/?utm_source=rss&b=2&a=1#section"
    right = "https://example.com/news/story?a=1&b=2"
    assert normalize_url(left) == normalize_url(right) == "https://example.com/news/story?a=1&b=2"


def article(company, url, title, text, date="2026-11-10T04:00:00+00:00", source_id="src"):
    return {
        "company": company,
        "original_url": url,
        "title": title,
        "full_text": text,
        "published_at": date,
        "negative_categories": ["监管调查及处罚"],
        "source_ids": [source_id],
    }


def test_same_url_and_body_are_one_article_without_losing_company_associations():
    text = "Regulators opened an investigation and the company disclosed the matter. " * 12
    rows = [
        article("Apple", "https://news.example/a?utm_source=rss", "Regulator opens tech probe", text, source_id="one"),
        article("Microsoft", "https://news.example/a", "Regulator opens tech probe", text, source_id="two"),
    ]
    grouped = assign_article_groups(rows)
    assert [row["company"] for row in grouped] == ["Apple", "Microsoft"]
    assert grouped[0]["article_id"] == grouped[1]["article_id"]
    assert grouped[0]["duplicate_group_id"] == grouped[1]["duplicate_group_id"]
    assert sum(row["is_duplicate_article"] for row in grouped) == 1
    assert grouped[0]["source_ids"] == ["one", "two"]


def test_identical_body_deduplicates_different_urls():
    text = "A court filing describes the same detailed facts and response. " * 15
    rows = [
        article("Apple", "https://wire.example/a", "Apple faces court claim", text, source_id="one"),
        article("Apple", "https://paper.example/reprint", "Apple faces court claim", text, source_id="two"),
    ]
    grouped = assign_article_groups(rows)
    assert grouped[0]["article_id"] == grouped[1]["article_id"]
    assert grouped[1]["is_duplicate_article"] is True


def test_similar_titles_on_distant_dates_are_not_forced_into_one_article_or_event():
    rows = [
        article("Apple", "https://news.example/old", "Regulator opens Apple investigation", "First matter facts. " * 20, "2026-01-01T00:00:00+00:00", "one"),
        article("Apple", "https://news.example/new", "Regulator opens Apple investigation", "Different matter facts. " * 20, "2026-11-10T00:00:00+00:00", "two"),
    ]
    articles = assign_article_groups(rows)
    assert articles[0]["article_id"] != articles[1]["article_id"]
    events = assign_event_groups(articles)
    assert events[0]["event_id"] != events[1]["event_id"]
    assert not any(row["is_same_event"] for row in events)


def test_same_company_category_date_and_facts_can_form_one_event():
    rows = [
        article("Apple", "https://wire.example/a", "Regulator opens Apple App Store investigation", "The authority opened an App Store investigation on Monday. " * 10, source_id="one"),
        article("Apple", "https://paper.example/b", "Apple App Store investigated by regulator", "On Monday the regulator opened an investigation into the App Store. " * 10, source_id="two"),
    ]
    events = assign_event_groups(assign_article_groups(rows))
    assert events[0]["event_id"] == events[1]["event_id"]
    assert all(row["is_same_event"] for row in events)

