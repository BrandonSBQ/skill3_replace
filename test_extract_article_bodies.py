"""离线单测；不访问Google，不访问新闻媒体。"""
import csv
import json
from pathlib import Path
import pytest

import extract_article_bodies as mod


def make_row(company="Apple", link="https://news.google.com/rss/articles/CBMiTEST"):
    return {"Company": company, "Title": "Example negative report", "Publisher": "Sample media",
            "Published UTC": "2026-11-10T00:00:00+00:00", "Google News URL": link,
            "Possible Negative Types": "监管调查", "Screening Basis": "TITLE_KEYWORD"}


def test_selection_no_cross_company_loss():
    rows = [make_row("Apple", f"https://news.google.com/rss/articles/CBMI{i}") for i in range(7)]
    rows += [make_row("Microsoft", f"https://news.google.com/rss/articles/ABC{i}") for i in range(3)]
    assert len(mod.choose_rows(rows, 2, 0)) == 4
    assert len(mod.choose_rows(rows, 2, 3)) == 3


def test_decode_retains_unresolved():
    urls = ["https://news.google.com/rss/articles/CBMI123", "https://publisher.example/article"]
    resolved = mod.decode_urls(urls, lambda l, **kw: {l[0]: None})
    assert resolved[urls[0]] is None
    assert resolved[urls[1]] == urls[1]


def test_url_safety():
    assert not mod.is_public_url("file:///etc/passwd")
    assert not mod.is_public_url("http://127.0.0.1/foo")
    assert not mod.is_public_url("http://localhost:5000/")
    assert not mod.is_public_url("https://192.168.1.1/admin")
    assert mod.is_public_url("https://www.reuters.com/world/story")


class FakeFetcher:
    def get_html(self, url):
        return "<article><h1>News</h1><p>words</p></article>", url


def test_success_preserves_text():
    row = make_row()
    body = "First paragraph reporting facts.\nSecond paragraph about the event " + "details " * 40
    result = mod.build_result(row, "https://publisher.example/a", FakeFetcher(), 180,
                              lambda page, **kw: json.dumps({"title":"Article", "date":"2026-11-09", "text":body}))
    assert result["fetch_status"] == "SUCCESS"
    assert result["full_text"].startswith("First paragraph")
    assert "\nSecond paragraph" in result["full_text"]
    assert result["original_url"] == "https://publisher.example/a"
    assert result["confidence"] == "UNVERIFIED"


def test_unresolved_does_not_create_fake_text():
    result = mod.build_result(make_row(), None, FakeFetcher(), 100)
    assert result["fetch_status"] == "RESOLVE_FAILED"
    assert result["full_text"] == ""


def test_short_text_is_flagged():
    result = mod.build_result(make_row(), "https://publisher.example/a", FakeFetcher(), 100,
                              lambda page, **kw: '{"text":"Subscribe now"}')
    assert result["fetch_status"] == "SHORT_TEXT"
    assert result["text_length"] == len("Subscribe now")


def test_checkpoint_export_resume(tmp_path):
    row = make_row()
    result = mod.build_result(row, "https://publisher.example/a", FakeFetcher(), 10,
                              lambda page, **kw: '{"text":"A long descriptive paragraph about risk and relevant company details"}')
    checkpoint = tmp_path / mod.CHECKPOINT_NAME
    mod.store_checkpoint(checkpoint, result)
    loaded = mod.read_checkpoints(checkpoint)
    assert loaded[result["article_id"]]["fetch_status"] == "SUCCESS"
    source = tmp_path / "negative_news_candidates.csv"
    with source.open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(row))
        wr.writeheader(); wr.writerow(row)
    with (tmp_path / "coverage_300.csv").open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=["Company","Search Status","Candidate Count"])
        wr.writeheader(); wr.writerow({"Company":"Apple","Search Status":"SUCCESS","Candidate Count":1})
    summary = mod.export(tmp_path, [row], loaded, source)
    assert summary["full_text_success"] == 1
    lines = (tmp_path / "articles_with_content.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["full_text"]
    coverage = (tmp_path / "article_text_coverage_300.csv").read_text(encoding="utf-8-sig")
    assert "Apple" in coverage and "1" in coverage


def test_empty_candidates_export(tmp_path):
    source = tmp_path / "negative_news_candidates.csv"
    source.write_text("Company,Title,Google News URL\n", encoding="utf-8-sig")
    assert mod.load_source(source) == []
    assert mod.main(["--input", str(source), "--dry-run"]) == 0
    summary = json.loads((tmp_path / "article_fetch_summary.json").read_text(encoding="utf-8"))
    assert summary["selected_articles"] == 0


def test_end_to_end_with_fake_dependencies(monkeypatch, tmp_path):
    """模拟 Google 解码+媒体正文，测试完整 CSV->JSONL->恢复链路。"""
    import sys
    import types
    import extract_article_bodies as m
    row = make_row()
    input_csv = tmp_path / "negative_news_candidates.csv"
    with input_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader(); w.writerow(row)
    calls = []

    def fake_decode_many(urls, **kwargs):
        calls.append(list(urls))
        return {u: "https://publisher.example/news" for u in urls}

    def fake_extract(page, **kwargs):
        return json.dumps({"text": "Detailed statement about the issuer. " * 9,
                           "title": "Corporate news", "date": "2026-11-10"})

    monkeypatch.setitem(sys.modules, "gnews_decoder", types.SimpleNamespace(decode_many=fake_decode_many))
    monkeypatch.setitem(sys.modules, "trafilatura", types.SimpleNamespace(extract=fake_extract))
    monkeypatch.setattr(m, "PageFetcher", lambda **kwargs: FakeFetcher())
    args = ["--input", str(input_csv), "--per-company", "5", "--max-total", "1"]
    assert m.main(args) == 0
    output_rows = (tmp_path / "articles_with_content.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(output_rows) == 1
    article = json.loads(output_rows[0])
    assert article["fetch_status"] == "SUCCESS"
    assert article["original_url"] == "https://publisher.example/news"
    assert article["full_text"]
    assert len(calls) == 1
    # 同一数据再次运行无需再次请求Google或媒体网站
    assert m.main(args) == 0
    assert len(calls) == 1
