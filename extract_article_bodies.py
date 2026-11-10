#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 Google News RSS 300家公司检索结果提取媒体原文，供后续 AI Agent 分析。

本脚本读取已有 negative_news_candidates.csv；不会重新搜索任何公司。
依赖：requests, trafilatura, gnews-decoder。只抓取可公开访问且 robots.txt 允许的正文。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import re
import socket
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from risk_news_v2.console_text import console_safe

APP_ROOT = Path(__file__).resolve().parent
USER_AGENT = "RiskNewsResearchBot/1.0 (personal research; respectful crawling)"
CHECKPOINT_NAME = "article_fetch_checkpoints.jsonl"
FIELDS = [
    "Article ID", "Company", "Title", "Publisher", "Published UTC",
    "Google News URL", "Original URL", "Final URL", "Possible Negative Types",
    "Fetch Status", "Text Length", "Extracted Title", "Extracted Date",
    "Full Text", "Error", "Retrieved UTC",
]


def timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def unique_id(row):
    value = row.get("Company", "") + "\x00" + row.get("Google News URL", "")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def is_public_url(url):
    """拒绝本地地址、IP 字面量私有地址及非 HTTP URL。"""
    try:
        u = urlparse(url)
        if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password:
            return False
        host = u.hostname.lower().strip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return True
    except ValueError:
        return False


def check_dns_is_public(host):
    """在请求前防止域名指向内网 IP；DNS 异常视作不可访问。"""
    try:
        addrs = socket.getaddrinfo(host, None)
        return bool(addrs) and all(ipaddress.ip_address(x[4][0]).is_global for x in addrs)
    except (OSError, ValueError):
        return False


class FetchProblem(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class PageFetcher:
    """域名级 robots.txt 缓存，顺序访问、超时/大小限制，绝不绕过登录/付费墙。"""

    def __init__(self, delay=2.0, timeout=18.0, max_bytes=2_500_000, session=None):
        self.delay = delay
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        })
        self.last_access = None
        self.robots_cache = {}
        self.dns_cache = {}
        self.rate_limited_hosts = set()

    def _pace(self):
        if self.last_access is not None:
            left = self.delay - (time.monotonic() - self.last_access)
            if left > 0:
                time.sleep(left)
        self.last_access = time.monotonic()

    def _guard_url(self, url):
        if not is_public_url(url):
            raise FetchProblem("INVALID_URL", "不是安全的外部 HTTP(S) 地址")
        host = urlparse(url).hostname
        if host not in self.dns_cache:
            self.dns_cache[host] = check_dns_is_public(host)
        if not self.dns_cache[host]:
            raise FetchProblem("INVALID_URL", "DNS 无法解析到公共网络地址")

    def _request(self, url):
        self._guard_url(url)
        self._pace()
        try:
            return self.session.get(url, timeout=self.timeout, allow_redirects=False, stream=True)
        except requests.Timeout as exc:
            raise FetchProblem("TIMEOUT", str(exc)[:160]) from exc
        except requests.RequestException as exc:
            raise FetchProblem("NETWORK_ERROR", str(exc)[:160]) from exc

    def _read_limited(self, response, limit):
        size = 0
        parts = []
        for piece in response.iter_content(chunk_size=32768):
            if not piece:
                continue
            size += len(piece)
            if size > limit:
                raise FetchProblem("TOO_LARGE", f"文档超过 {limit} bytes")
            parts.append(piece)
        data = b"".join(parts)
        encoding = response.encoding or "utf-8"
        return data.decode(encoding, errors="replace")

    def _robots_allowed(self, url):
        parsed = urlparse(url)
        origin = parsed.scheme + "://" + parsed.netloc.lower()
        if origin not in self.robots_cache:
            robots_url = origin + "/robots.txt"
            response = self._request(robots_url)
            try:
                if response.status_code in (404, 410):
                    self.robots_cache[origin] = True
                elif response.status_code == 200:
                    text = self._read_limited(response, 400_000)
                    parser = RobotFileParser()
                    parser.parse(text.splitlines())
                    self.robots_cache[origin] = parser
                else:
                    self.robots_cache[origin] = False
            except FetchProblem:
                self.robots_cache[origin] = False
            finally:
                response.close()
        rule = self.robots_cache[origin]
        if rule is True:
            return True
        if rule is False:
            raise FetchProblem("ROBOTS_UNAVAILABLE", "robots.txt 无法确认，保守跳过")
        if not rule.can_fetch(USER_AGENT, url):
            raise FetchProblem("ROBOTS_BLOCKED", "robots.txt 不允许抓取该 URL")
        return True

    def get_html(self, url):
        current = url
        for _ in range(5):
            self._guard_url(current)
            host = urlparse(current).hostname
            if host in self.rate_limited_hosts:
                raise FetchProblem("RATE_LIMITED", "同一媒体网站本轮已限流，跳过后续文章")
            self._robots_allowed(current)
            response = self._request(current)
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    target = response.headers.get("Location", "")
                    if not target:
                        raise FetchProblem("HTTP_ERROR", "重定向缺少 Location")
                    current = urljoin(current, target)
                    continue
                if response.status_code in (401, 402, 403, 451):
                    raise FetchProblem("ACCESS_DENIED", f"HTTP {response.status_code}")
                if response.status_code == 429:
                    self.rate_limited_hosts.add(host)
                    raise FetchProblem("RATE_LIMITED", "媒体站点 HTTP 429；本轮跳过该站点后续文章")
                if response.status_code >= 400:
                    raise FetchProblem("HTTP_ERROR", f"HTTP {response.status_code}")
                ctype = response.headers.get("Content-Type", "").lower()
                if not any(x in ctype for x in ("text/html", "application/xhtml+xml")):
                    raise FetchProblem("NOT_HTML", f"Content-Type {ctype or 'missing'}")
                raw_size = response.headers.get("Content-Length", "")
                if raw_size.isdigit() and int(raw_size) > self.max_bytes:
                    raise FetchProblem("TOO_LARGE", "Content-Length 超出大小限制")
                content = self._read_limited(response, self.max_bytes)
                return content, current
            finally:
                response.close()
        raise FetchProblem("TOO_MANY_REDIRECTS", "重定向超过4次")


def decode_urls(urls, decode_many_func=None):
    if not urls:
        return {}
    if decode_many_func is None:
        from gnews_decoder import decode_many as decode_many_func
    google = [u for u in urls if urlparse(u).hostname in {"news.google.com", "news.google.co.uk"}]
    result = {u: u for u in urls if u not in google}
    if google:
        # 每批最多10条，低并发，减少对Google内部非正式解码接口的压力。
        result.update(decode_many_func(google, concurrency=2, timeout=15.0))
    return result


def extract_text(page, extract_func=None):
    if extract_func is None:
        from trafilatura import extract as extract_func
    raw = extract_func(page, output_format="json", with_metadata=True, include_comments=False)
    if not raw:
        return None
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        return None
    return {
        "text": "\n".join(line.strip() for line in data.get("text", "").splitlines() if line.strip()) if data.get("text") else "",
        "title": data.get("title") or "",
        "date": data.get("date") or "",
    }


def build_result(row, url, fetcher, min_chars, extract_func=None):
    result = {
        "article_id": unique_id(row),
        "company": row.get("Company", ""),
        "title": row.get("Title", ""),
        "publisher": row.get("Publisher", ""),
        "published_utc": row.get("Published UTC", ""),
        "google_news_url": row.get("Google News URL", ""),
        "original_url": url or "",
        "final_url": "",
        "possible_negative_types": row.get("Possible Negative Types", ""),
        "screening_basis": row.get("Screening Basis", ""),
        "confidence": "UNVERIFIED",
        "review_status": "PENDING_REVIEW",
        "full_text": "",
        "text_length": 0,
        "extracted_title": "",
        "extracted_date": "",
        "fetch_status": "PENDING",
        "error": "",
        "retrieved_utc": timestamp(),
    }
    if not url or not is_public_url(url) or urlparse(url).hostname in {"news.google.com", "news.google.co.uk"}:
        result.update(fetch_status="RESOLVE_FAILED", error="Google News 原始新闻网址解析失败")
        return result
    try:
        page, final_url = fetcher.get_html(url)
        result["final_url"] = final_url
        extracted = extract_text(page, extract_func)
        if not extracted or not extracted["text"]:
            raise FetchProblem("EXTRACTION_FAILED", "未从 HTML 中提取到新闻正文")
        result.update(
            full_text=extracted["text"], text_length=len(extracted["text"]),
            extracted_title=extracted["title"], extracted_date=extracted["date"],
        )
        if result["text_length"] < min_chars:
            raise FetchProblem("SHORT_TEXT", f"正文只有{result['text_length']}字符；可能是摘要、付费墙或反爬页面")
        result["fetch_status"] = "SUCCESS"
    except FetchProblem as exc:
        result.update(fetch_status=exc.status, error=str(exc)[:250])
    except Exception as exc:
        result.update(fetch_status="EXTRACTION_ERROR", error=f"{type(exc).__name__}: {str(exc)[:180]}")
    return result


def read_checkpoints(path):
    records = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if row.get("article_id"):
                        records[row["article_id"]] = row
                except (ValueError, TypeError):
                    continue
    return records


def store_checkpoint(path, record):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def safe_csv(value):
    value = str(value or "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: safe_csv(row.get(field, "")) for field in fields})


def load_source(input_csv):
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        rows = list(reader)
    required = {"Company", "Title", "Google News URL"}
    if not required.issubset(headers):
        raise ValueError("候选文件缺少列: " + ", ".join(sorted(required - headers)))
    return [r for r in rows if r.get("Google News URL", "").strip()]


def choose_rows(rows, per_company, max_total):
    selected = []
    counts = Counter()
    for row in rows:
        name = row.get("Company", "")
        if counts[name] >= per_company:
            continue
        selected.append(row)
        counts[name] += 1
        if max_total and len(selected) >= max_total:
            break
    return selected


def export(output, selected, records, original_csv):
    output.mkdir(parents=True, exist_ok=True)
    results = [records[unique_id(r)] for r in selected if unique_id(r) in records]
    with (output / "articles_with_content.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    values = []
    for r in results:
        values.append({
            "Article ID": r["article_id"], "Company": r["company"],
            "Title": r["title"], "Publisher": r["publisher"],
            "Published UTC": r["published_utc"], "Google News URL": r["google_news_url"],
            "Original URL": r["original_url"], "Final URL": r["final_url"],
            "Possible Negative Types": r["possible_negative_types"],
            "Fetch Status": r["fetch_status"], "Text Length": r["text_length"],
            "Extracted Title": r["extracted_title"], "Extracted Date": r["extracted_date"],
            "Full Text": r["full_text"], "Error": r["error"],
            "Retrieved UTC": r["retrieved_utc"],
        })
    write_csv(output / "articles_with_content.csv", FIELDS, values)

    by_company = defaultdict(list)
    for result in results:
        by_company[result["company"]].append(result)
    source_coverage = original_csv.parent / "coverage_300.csv"
    if source_coverage.exists():
        with source_coverage.open("r", encoding="utf-8-sig", newline="") as f:
            source_rows = list(csv.DictReader(f))
        companies = [(r.get("Company", ""), r.get("Search Status", "UNKNOWN"),
                      r.get("Candidate Count", "")) for r in source_rows]
    else:
        companies = [(c, "UNKNOWN", "") for c in sorted({r.get("Company", "") for r in selected})]
    coverage_rows = []
    for i, (company, search_status, source_count) in enumerate(companies, 1):
        group = by_company[company]
        cnt = Counter(x["fetch_status"] for x in group)
        coverage_rows.append({
            "No.": i, "Company": company, "RSS Search Status": search_status,
            "RSS Candidates": source_count, "Selected for Extraction": sum(r.get("Company") == company for r in selected),
            "Processed": len(group), "Full Text Success": cnt["SUCCESS"],
            "Extraction Failed": len(group) - cnt["SUCCESS"],
            "Pending": sum(r.get("Company") == company for r in selected) - len(group),
        })
    write_csv(output / "article_text_coverage_300.csv",
              ["No.", "Company", "RSS Search Status", "RSS Candidates", "Selected for Extraction",
               "Processed", "Full Text Success", "Extraction Failed", "Pending"], coverage_rows)
    counts = dict(Counter(r["fetch_status"] for r in results))
    summary = {
        "generated_utc": timestamp(), "input": str(original_csv),
        "selected_articles": len(selected), "processed_articles": len(results),
        "full_text_success": counts.get("SUCCESS", 0), "status_counts": counts,
        "note": "正文仅用于有权使用的本地研究；不代表全文可用或新闻已核实。短正文、付费墙、robots阻断保留失败状态。",
    }
    (output / "article_fetch_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="从现有 Google News RSS 候选结果抓取媒体原文")
    parser.add_argument("--input", default=str(APP_ROOT / "results_300_google_rss" / "negative_news_candidates.csv"))
    parser.add_argument("--output", default="", help="结果目录；默认与输入CSV同目录")
    parser.add_argument("--per-company", type=int, default=5, help="每家公司最多提取文章数，默认5")
    parser.add_argument("--max-total", type=int, default=0, help="本轮最多处理的文章数，0代表按每家公司上限处理全部")
    parser.add_argument("--delay", type=float, default=2.0, help="网页请求的最小间隔秒数")
    parser.add_argument("--min-chars", type=int, default=180)
    parser.add_argument("--retry-failed", action="store_true", help="重复尝试此前抓取失败的文章")
    parser.add_argument("--dry-run", action="store_true", help="只检查候选条数和参数，不联网")
    args = parser.parse_args(argv)
    if args.per_company < 1 or args.max_total < 0 or args.min_chars < 10 or args.delay < 1:
        parser.error("参数需满足 per-company>=1, max-total>=0, min-chars>=10, delay>=1")

    original_csv = Path(args.input).expanduser().resolve()
    if not original_csv.exists():
        parser.error(f"未找到候选新闻: {original_csv}。先运行 python search_300_companies.py")
    output = Path(args.output).expanduser().resolve() if args.output else original_csv.parent
    output.mkdir(parents=True, exist_ok=True)
    rows = load_source(original_csv)
    selected = choose_rows(rows, args.per_company, args.max_total)
    records = read_checkpoints(output / CHECKPOINT_NAME)
    print(f"[START] RSS候选 {len(rows)} 条 | 选中 {len(selected)} 条 | 每公司最多 {args.per_company} 条")
    print(f"[OUTPUT] {output}")
    if args.dry_run:
        export(output, selected, records, original_csv)
        print("[DRY RUN] 未进行链接解析或网页请求")
        return 0
    if not selected:
        export(output, [], records, original_csv)
        print("[EMPTY] 候选CSV中没有新闻；请检查搜索覆盖率。未进行正文请求。")
        return 0
    try:
        import trafilatura  # noqa: F401
        import gnews_decoder  # noqa: F401
    except ImportError as exc:
        parser.error(f"缺少正文抓取依赖: {exc}; 请运行 python -m pip install -r requirements.txt")

    fetcher = PageFetcher(delay=args.delay)
    cache = {}
    for r in records.values():
        if r.get("original_url") and r.get("fetch_status") == "SUCCESS":
            cache[r["original_url"]] = r
    total = len(selected)
    # 分批10条URL解析，避免大量并发调用Google非公开接口。
    stop_google = False
    for start in range(0, total, 10):
        batch = selected[start:start + 10]
        todo = [r for r in batch if unique_id(r) not in records or
                (args.retry_failed and records[unique_id(r)].get("fetch_status") != "SUCCESS")]
        if not todo:
            continue
        urls = list(dict.fromkeys(r["Google News URL"] for r in todo))
        try:
            decoded = decode_urls(urls)
        except Exception as exc:
            print("[WARN] Google链接批量解析异常：" + str(exc)[:180])
            decoded = {}
        if urls and all(not decoded.get(u) for u in urls):
            print("[STOP] 本批全部链接解析失败；可能被限流或接口变更，保留进度供以后续跑")
            stop_google = True
            break
        for local_i, row in enumerate(todo):
            index = start + batch.index(row) + 1
            url = decoded.get(row["Google News URL"])
            if url in cache:
                source = cache[url]
                result = build_result(row, None, fetcher, args.min_chars)
                for key in ("original_url", "final_url", "full_text", "text_length", "extracted_title",
                            "extracted_date", "fetch_status", "error"):
                    result[key] = source[key]
                result["retrieved_utc"] = timestamp()
            else:
                result = build_result(row, url, fetcher, args.min_chars)
                if result["fetch_status"] == "SUCCESS":
                    cache[url] = result
            records[result["article_id"]] = result
            store_checkpoint(output / CHECKPOINT_NAME, result)
            print(console_safe(f"[BODY {index:04d}/{total}] {row['Company'][:24]} | "
                  f"{result['fetch_status']} | chars={result['text_length']}"), flush=True)
            if result["fetch_status"] == "RATE_LIMITED":
                print("[SKIP HOST] 该媒体网站限流；继续处理其他媒体", flush=True)
        export(output, selected, records, original_csv)
        if stop_google:
            break
    summary = export(output, selected, records, original_csv)
    print("[RESULT] " + json.dumps({
        "selected": summary["selected_articles"], "processed": summary["processed_articles"],
        "full_text_success": summary["full_text_success"], "status_counts": summary["status_counts"],
    }, ensure_ascii=False))
    print("[FILES] articles_with_content.jsonl / articles_with_content.csv / article_text_coverage_300.csv")
    return 2 if stop_google else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(console_safe("\n[INTERRUPTED] 检查点已保留；同一命令可续跑"), file=sys.stderr)
        sys.exit(130)
