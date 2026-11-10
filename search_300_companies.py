#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""300 家公开公司 Google News RSS 近 7 天负面新闻候选检索。

运行：python search_300_companies.py
先试 5 家：python search_300_companies.py --limit 5
无需 Google API Key；每家公司一次 RSS 搜索，不抓取新闻全文。
所有搜索结果为未核实的候选新闻；不等于已经发生负面事件。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from risk_news_v2.console_text import console_safe

RSS_URL = "https://news.google.com/rss/search"
# 控制每家公司只发一次搜索请求；负面词组检索，可能遗漏未匹配词的事件。
NEGATIVE_TERMS = (
    '(default OR bankruptcy OR insolvency OR downgrade OR liquidity OR '
    'lawsuit OR investigation OR fraud OR sanction OR restructuring OR '
    'recall OR layoffs OR penalty OR bribery OR "data breach" OR '
    '"missed payment" OR "profit warning")'
)

# 下面300家公司仅为公开演示名单，不涉及公司内部持仓信息。
RAW_COMPANY_LIST = r"""
# 01 | US technology and platforms
Apple
Microsoft
Alphabet Inc
Amazon
Meta Platforms
Nvidia
Tesla
Netflix
Uber Technologies
Airbnb
PayPal
Block Inc
Salesforce
Adobe
Oracle
IBM
Cisco Systems
ServiceNow
Snowflake
Palantir Technologies
CrowdStrike
Datadog
Cloudflare
Workday
Intuit
Shopify
Spotify
Zoom Communications
Pinterest
Snap Inc
# 02 | Software, communications and online services
Autodesk
Atlassian
HubSpot
MongoDB
Okta
Zscaler
Palo Alto Networks
Fortinet
Akamai Technologies
Twilio
DocuSign
Dropbox
Box Inc
Elastic N.V.
UiPath
Confluent
GitLab
Duolingo
Roblox
Electronic Arts
Take-Two Interactive
Match Group
Expedia Group
Booking Holdings
eBay
Etsy
DoorDash
Instacart
Reddit
The Trade Desk
# 03 | Semiconductors and hardware
Advanced Micro Devices
Intel
Qualcomm
Broadcom
Texas Instruments
Micron Technology
Applied Materials
Lam Research
KLA Corporation
Analog Devices
Marvell Technology
ON Semiconductor
Microchip Technology
NXP Semiconductors
GlobalFoundries
Arm Holdings
Western Digital
Seagate Technology
Dell Technologies
HP Inc
Hewlett Packard Enterprise
Super Micro Computer
Corning
Teradyne
Skyworks Solutions
Qorvo
Monolithic Power Systems
Lattice Semiconductor
Synopsys
Cadence Design Systems
# 04 | US finance and exchanges
JPMorgan Chase
Bank of America
Citigroup
Wells Fargo
Goldman Sachs
Morgan Stanley
U.S. Bancorp
PNC Financial Services
Truist Financial
Capital One
American Express
Visa
Mastercard
BlackRock
Blackstone
KKR
Apollo Global Management
Charles Schwab
State Street
Bank of New York Mellon
CME Group
Intercontinental Exchange
Nasdaq Inc
S&P Global
Moody's Corporation
MSCI
Berkshire Hathaway
Progressive Corporation
Allstate
Chubb Limited
# 05 | Consumer and retail
Walmart
Costco
Target Corporation
Home Depot
Lowe's
Nike
Starbucks
McDonald's
Chipotle Mexican Grill
Yum Brands
Domino's Pizza
Coca-Cola
PepsiCo
Procter & Gamble
Colgate-Palmolive
Kimberly-Clark
Kraft Heinz
Mondelez International
General Mills
Conagra Brands
Campbell's Company
Tyson Foods
Kroger
Dollar General
Dollar Tree
TJX Companies
Ross Stores
Marriott International
Hilton Worldwide
Carnival Corporation
# 06 | Healthcare and biotech
Johnson & Johnson
Pfizer
Merck & Co
Eli Lilly
AbbVie
Bristol Myers Squibb
Amgen
Gilead Sciences
Regeneron Pharmaceuticals
Vertex Pharmaceuticals
Biogen
Moderna
UnitedHealth Group
CVS Health
Cigna Group
Elevance Health
Humana
HCA Healthcare
Intuitive Surgical
Medtronic
Boston Scientific
Stryker
Becton Dickinson
Abbott Laboratories
Thermo Fisher Scientific
Danaher
Illumina
Edwards Lifesciences
Zoetis
Agilent Technologies
# 07 | Industry, transport and defense
GE Aerospace
GE Vernova
Boeing
Lockheed Martin
RTX Corporation
Northrop Grumman
General Dynamics
Honeywell
3M Company
Caterpillar
Deere & Company
Cummins
Eaton Corporation
Emerson Electric
Rockwell Automation
Parker Hannifin
Illinois Tool Works
United Parcel Service
FedEx
Union Pacific
CSX Corporation
Norfolk Southern
Delta Air Lines
United Airlines
American Airlines
Southwest Airlines
General Motors
Ford Motor Company
Rivian Automotive
Lucid Group
# 08 | Energy, chemicals and utilities
Exxon Mobil
Chevron
ConocoPhillips
Occidental Petroleum
EOG Resources
Devon Energy
Diamondback Energy
Halliburton
SLB
Baker Hughes
Marathon Petroleum
Valero Energy
Phillips 66
Kinder Morgan
Williams Companies
ONEOK
NextEra Energy
Duke Energy
Southern Company
Dominion Energy
American Electric Power
Exelon
Xcel Energy
Sempra
First Solar
Enphase Energy
Dow Inc
DuPont
Freeport-McMoRan
Newmont Corporation
# 09 | European businesses
ASML
SAP
Siemens
Schneider Electric
Airbus
Safran
Rolls-Royce Holdings
BAE Systems
Shell
BP
TotalEnergies
Equinor
Eni
Nestle
Novartis
Roche
AstraZeneca
Novo Nordisk
Sanofi
LVMH
Kering
Hermes International
L'Oreal
Unilever
Adidas
Volkswagen Group
BMW Group
Mercedes-Benz Group
Deutsche Bank
HSBC Holdings
# 10 | Asian and Pacific businesses
Taiwan Semiconductor Manufacturing Company
Samsung Electronics
SK Hynix
Sony Group
Toyota Motor
Honda Motor
Mitsubishi UFJ Financial Group
Sumitomo Mitsui Financial Group
Mizuho Financial Group
SoftBank Group
Nintendo
Hitachi
Panasonic Holdings
Alibaba Group
Tencent Holdings
Baidu
JD.com
PDD Holdings
Meituan
Xiaomi Corporation
BYD Company
CATL
NetEase
Bilibili
Trip.com Group
China Mobile
China Construction Bank
Industrial and Commercial Bank of China
Ping An Insurance
DBS Group
"""
COMPANIES = [
    line.strip() for line in RAW_COMPANY_LIST.splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
assert len(COMPANIES) == 300, f"期望300家，实际{len(COMPANIES)}"
assert len({c.casefold() for c in COMPANIES}) == 300, "存在重复公司名"

SIGNAL_PATTERNS = {
    "债务违约": r"\bdefault(?:ed)?\b|missed payment|违约|未兑付",
    "破产/重组": r"bankrupt|insolven|restructur|破产|重组|清盘",
    "流动性": r"liquidity|cash crunch|流动性|资金链",
    "评级下调": r"downgrad|rating cut|评级下调|负面展望",
    "监管调查": r"investigat|regulat|probe|penalt|\bfine\b|处罚|调查|罚款",
    "欺诈/治理": r"fraud|bribery|corruption|欺诈|贿赂|腐败",
    "诉讼": r"lawsuit|litigat|\bsued\b|诉讼|起诉",
    "财务恶化": r"profit warning|\blosses\b|impairment|亏损|减值",
    "经营风险": r"recall|layoffs?|shutdown|裁员|召回|停产",
    "制裁/安全": r"sanction|cyberattack|data breach|制裁|数据泄露",
}
PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in SIGNAL_PATTERNS.items()}
CANDIDATE_FIELDS = [
    "Company", "Title", "Published UTC", "Publisher", "Google News URL",
    "Possible Negative Types", "Screening Basis", "Confidence", "Review Status",
    "Search Query", "Query Terms", "Search Languages", "Search UTC",
]
COVERAGE_FIELDS = [
    "No.", "Company", "Search Status", "Candidate Count", "RSS Items",
    "Out of Window", "Result Capped", "Query Terms", "Search Languages",
    "Search Query", "Search UTC", "Error",
]
DONE_STATES = {"SUCCESS", "NO_CANDIDATE_FOUND", "PARTIAL_CAPPED"}


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def list_digest(items):
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def csv_safe(x):
    # 避免打开 CSV 时触发公式注入
    s = str(x if x is not None else "")
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as out:
        w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({field: csv_safe(row.get(field, "")) for field in fields})


def read_checkpoints(path, allowed_companies=None):
    records = {}
    allowed = set(COMPANIES if allowed_companies is None else allowed_companies)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
                if obj.get("company") in allowed and isinstance(obj.get("articles"), list):
                    records[obj["company"]] = obj
            except (ValueError, TypeError):
                pass
    return records


def checkpoint(path, result):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
        f.flush()


def parse_rss(xml_bytes):
    """解析真实 RSS XML；任何异常格式都不能视为'无新闻'。"""
    root = ET.fromstring(xml_bytes)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("返回内容不是 Google News RSS，可能是限流、验证码或登录页")
    articles = []
    for item in root.findall("channel/item"):
        title = html.unescape(" ".join((item.findtext("title") or "").split()))
        link = (item.findtext("link") or "").strip()
        publisher = (item.findtext("source") or "").strip()
        raw_date = (item.findtext("pubDate") or "").strip()
        if not title or not link or urlsplit(link).scheme not in {"https", "http"}:
            continue
        try:
            published = parsedate_to_datetime(raw_date).astimezone(timezone.utc) if raw_date else None
        except (TypeError, ValueError, IndexError):
            published = None
        articles.append({"title": title, "link": link, "publisher": publisher, "published": published})
    return articles


class RSSRateLimited(RuntimeError):
    pass


class RSSClient:
    def __init__(self, delay=3.0, retries=2, timeout=30):
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.last_request = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; PersonalNewsRSSResearch/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
        })

    def fetch(self, company, days, terms=None):
        query_profile = {
            "legal_name": company,
            "display_name": company,
            "aliases": list(terms or [])[1:],
        }
        params = {
            "q": build_search_query(query_profile, days),
            "hl": "en-US", "gl": "US", "ceid": "US:en",
        }
        for attempt in range(self.retries + 1):
            if self.last_request is not None:
                wait = self.delay - (time.monotonic() - self.last_request)
                if wait > 0:
                    time.sleep(wait)
            if self.delay:
                time.sleep(random.uniform(0.0, min(self.delay * .15, .5)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(RSS_URL, params=params, timeout=self.timeout)
                if response.status_code in (429, 403):
                    # 不请求后续299家公司，防止连续碰壁。
                    raise RSSRateLimited(f"Google RSS HTTP {response.status_code}：出现限流/访问拒绝，已停止批次")
                if response.status_code in (500, 502, 503, 504):
                    raise requests.HTTPError(f"Google RSS HTTP {response.status_code}")
                response.raise_for_status()
                if not response.content:
                    raise ValueError("RSS 响应为空，不能认定为无新闻")
                return parse_rss(response.content)
            except RSSRateLimited:
                raise
            except (requests.RequestException, ET.ParseError, ValueError) as exc:
                if attempt == self.retries:
                    raise RuntimeError(f"RSS 请求失败（重试{self.retries}次）: {str(exc)[:160]}") from exc
                time.sleep(min(20.0, 4.0 * (2 ** attempt)))
        return []  # 不会到达


def _profile(value):
    if isinstance(value, dict):
        profile = dict(value)
        profile.setdefault("legal_name", profile.get("Company", ""))
        profile.setdefault("display_name", profile["legal_name"])
        for field in ("aliases", "languages", "positive_context", "negative_context"):
            raw = profile.get(field, [])
            profile[field] = list(raw) if isinstance(raw, (list, tuple)) else [x.strip() for x in str(raw).split("|") if x.strip()]
        return profile
    return {
        "legal_name": str(value), "display_name": str(value), "aliases": [],
        "languages": ["en"], "ticker": "", "parent_company": "", "region": "",
        "country": "", "industry": "", "positive_context": [], "negative_context": [],
    }


def company_query_terms(value):
    profile = _profile(value)
    values = [profile["legal_name"], profile.get("display_name", ""), *profile.get("aliases", [])]
    output = []
    seen = set()
    for value in values:
        cleaned = " ".join(str(value or "").replace('"', " ").split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            output.append(cleaned)
            seen.add(key)
    return output


def build_search_query(company, days):
    terms = company_query_terms(company)
    entity_query = "(" + " OR ".join(f'"{term}"' for term in terms) + ")"
    return f"{entity_query} {NEGATIVE_TERMS} when:{days}d"


def process_one(company, client, config):
    profile = _profile(company)
    name = profile["legal_name"]
    terms = company_query_terms(profile)
    search_query = build_search_query(profile, config["days"])
    items = client.fetch(name, config["days"], terms)
    start = datetime.fromisoformat(config["start_utc"])
    # 如果本次运行耗时很长，同一批次仍按冻结窗口统计。
    end = datetime.fromisoformat(config["end_utc"])
    selected = []
    seen = set()
    outside = 0
    for item in items:
        published = item["published"]
        if published is None or not (start <= published <= end):
            outside += 1
            continue
        # 通过标题、媒体名、链接去除RSS中的明显重复项
        key = (" ".join(item["title"].casefold().split()), item["publisher"].casefold())
        if key in seen:
            continue
        seen.add(key)
        kinds = [name for name, pattern in PATTERNS.items() if pattern.search(item["title"])]
        selected.append({
            "Company": name,
            "Title": item["title"],
            "Published UTC": published.isoformat(),
            "Publisher": item["publisher"],
            "Google News URL": item["link"],
            "Possible Negative Types": "; ".join(kinds) if kinds else "待核实",
            "Screening Basis": "TITLE_KEYWORD" if kinds else "SEARCH_QUERY_ONLY",
            "Confidence": "UNVERIFIED",
            "Review Status": "PENDING_REVIEW",
            "Search Query": search_query,
            "Query Terms": " | ".join(terms),
            "Search Languages": " | ".join(profile.get("languages", []) or ["en"]),
            "Search UTC": utc_now().isoformat(),
        })
    capped = len(items) >= config["max_records"]
    status = "PARTIAL_CAPPED" if capped else ("SUCCESS" if selected else "NO_CANDIDATE_FOUND")
    return {
        "company": name,
        "status": status,
        "found": len(selected),
        "rss_items": len(items),
        "outside": outside,
        "capped": capped,
        "error": "",
        "articles": selected[:config["max_records"]],
        "query_terms": terms,
        "languages": profile.get("languages", []) or ["en"],
        "search_query": search_query,
        "search_utc": utc_now().isoformat(),
        "completed_utc": utc_now().isoformat(),
    }


def failure_result(company, exc, config=None):
    profile = _profile(company)
    terms = company_query_terms(profile)
    return {
        "company": profile["legal_name"], "status": "RATE_LIMITED" if isinstance(exc, RSSRateLimited) else "FAILED",
        "found": 0, "rss_items": 0, "outside": 0, "capped": False,
        "error": str(exc)[:300], "articles": [], "completed_utc": utc_now().isoformat(),
        "query_terms": terms, "languages": profile.get("languages", []) or ["en"],
        "search_query": build_search_query(profile, (config or {}).get("days", 7)),
        "search_utc": utc_now().isoformat(),
    }


def export(out, records, config, profiles=None):
    profiles = [_profile(row) for row in (profiles or COMPANIES)]
    companies = [row["legal_name"] for row in profiles]
    profile_by_name = {row["legal_name"]: row for row in profiles}
    coverage = []
    all_articles = []
    for i, company in enumerate(companies, 1):
        record = records.get(company)
        profile = profile_by_name[company]
        if record is None:
            coverage.append({"No.": i, "Company": company, "Search Status": "NOT_RUN",
                             "Candidate Count": 0, "RSS Items": 0,
                             "Out of Window": 0, "Result Capped": "",
                             "Query Terms": " | ".join(company_query_terms(profile)),
                             "Search Languages": " | ".join(profile.get("languages", []) or ["en"]),
                             "Search Query": build_search_query(profile, config["days"]),
                             "Search UTC": "", "Error": ""})
            continue
        coverage.append({"No.": i, "Company": company, "Search Status": record["status"],
                         "Candidate Count": len(record.get("articles", [])),
                         "RSS Items": record.get("rss_items", 0),
                         "Out of Window": record.get("outside", 0),
                         "Result Capped": "YES" if record.get("capped") else "NO",
                         "Query Terms": " | ".join(record.get("query_terms", [])),
                         "Search Languages": " | ".join(record.get("languages", [])),
                         "Search Query": record.get("search_query", ""),
                         "Search UTC": record.get("search_utc", ""),
                         "Error": record.get("error", "")})
        all_articles.extend(record.get("articles", []))
    if len(profiles) == 300 and all(not row.get("ticker") for row in profiles):
        write_csv(out / "company_list_300.csv", ["No.", "Company"],
                  [{"No.": i, "Company": c} for i, c in enumerate(companies, 1)])
    else:
        from risk_news_v2.company_catalog import write_company_catalog
        write_company_catalog(out / f"company_list_{len(profiles)}.csv", profiles)
    write_csv(out / "coverage_300.csv", COVERAGE_FIELDS, coverage)
    write_csv(out / "negative_news_candidates.csv", CANDIDATE_FIELDS, all_articles)
    counts = {status: sum(r["Search Status"] == status for r in coverage)
              for status in ("SUCCESS", "NO_CANDIDATE_FOUND", "PARTIAL", "PARTIAL_CAPPED", "FAILED", "RATE_LIMITED", "NOT_RUN")}
    summary = {
        "source": "Google News RSS (unofficial)",
        "rss_url": RSS_URL,
        "updated_utc": utc_now().isoformat(),
        "window_start_utc": config["start_utc"],
        "window_end_utc": config["end_utc"],
        "company_count": len(companies),
        "counts": counts,
        "candidate_articles": len(all_articles),
        "warning": "Google RSS不是正式搜索API；可能限流、结果截断、漏报、误报；RSS链接可能跳转Google News。所有事件均需人工核实。",
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description="300家公开公司，Google News RSS 最近7天负面新闻候选搜索")
    p.add_argument("--limit", "--max-companies", dest="limit", type=int, default=300)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--delay", type=float, default=3.0, help="每次请求最小间隔秒数，建议至少3秒")
    p.add_argument("--max-records", type=int, default=100, help="单家公司最多保留条数，RSS实际返回量由Google决定")
    p.add_argument("--output", default="", help="结果文件夹，默认results_300_google_rss")
    p.add_argument("--company-file", default="", help="可选公司目录CSV；省略时使用内置300家公司")
    p.add_argument("--dry-run", action="store_true", help="仅生成完整名单及空覆盖清单，不联网")
    args = p.parse_args(argv)
    if args.limit < 1:
        p.error("--limit 必须至少为1")
    if not 1 <= args.days <= 30:
        p.error("--days 必须在1~30之间")
    if not 1 <= args.max_records <= 100:
        p.error("--max-records 必须在1~100之间")
    if not args.dry_run and args.delay < 1.5:
        p.error("--delay 不应低于1.5秒，请勿快速批量请求")
    out = (Path(args.output).expanduser().resolve() if args.output else
           Path(__file__).resolve().parent / "results_300_google_rss")
    out.mkdir(parents=True, exist_ok=True)
    if args.company_file:
        from risk_news_v2.company_catalog import load_company_catalog
        profiles = load_company_catalog(Path(args.company_file).expanduser().resolve())
    else:
        profiles = [_profile(company) for company in COMPANIES]
    if not profiles:
        p.error("公司目录为空")
    run_count = min(args.limit, len(profiles))
    companies = [row["legal_name"] for row in profiles]
    catalog_signature = [json.dumps({
        "legal_name": row["legal_name"], "terms": company_query_terms(row),
        "languages": row.get("languages", []),
    }, ensure_ascii=False, sort_keys=True) for row in profiles]
    catalog_digest = list_digest(catalog_signature) if args.company_file else list_digest(COMPANIES)
    config_path = out / "search_window.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if (config.get("source") != "google_rss" or
            config.get("company_digest") != catalog_digest or
            config.get("days") != args.days or config.get("max_records") != args.max_records):
            p.error("此输出目录参数不同或属于其他公司目录；请指定新 --output 文件夹")
    else:
        end = utc_now()
        config = {
            "source": "google_rss", "company_digest": catalog_digest,
            "company_count": len(profiles),
            "days": args.days, "max_records": args.max_records,
            "start_utc": (end - timedelta(days=args.days)).isoformat(),
            "end_utc": end.isoformat(),
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    cp_path = out / "checkpoints.jsonl"
    records = read_checkpoints(cp_path, allowed_companies=set(companies))
    print(f"[START] GOOGLE NEWS RSS | 公司总数{len(profiles)} | 本次{run_count}家 | 最近{args.days}天", flush=True)
    print(f"[OUTPUT] {out}", flush=True)
    if args.dry_run:
        export(out, records, config, profiles=profiles)
        print(f"[DRY RUN] 未联网，已生成{len(profiles)}家公司清单及覆盖记录。")
        return 0
    client = RSSClient(delay=args.delay)
    interrupted = False
    consecutive_failures = 0
    try:
        for i, profile in enumerate(profiles[:run_count], 1):
            company = profile["legal_name"]
            prev = records.get(company)
            if prev and prev.get("status") in DONE_STATES:
                print(console_safe(f"[{i:03d}/{run_count}] SKIP {company}（此前成功）"), flush=True)
                continue
            print(console_safe(f"[{i:03d}/{run_count}] SEARCH {company}"), flush=True)
            try:
                result = process_one(profile, client, config)
                consecutive_failures = 0
            except (RSSRateLimited, requests.RequestException, RuntimeError, ValueError, ET.ParseError) as exc:
                result = failure_result(profile, exc, config)
                consecutive_failures += 1
            checkpoint(cp_path, result)
            records[company] = result
            print(console_safe(f"    {result['status']} | candidates={len(result['articles'])}" +
                  (f" | {result['error']}" if result["error"] else "")), flush=True)
            if result["status"] == "RATE_LIMITED":
                print("[STOP] 服务端限流，已停止后续查询；稍后可使用同一命令续跑。", flush=True)
                break
            if consecutive_failures >= 3:
                print("[STOP] 连续3家公司请求失败，疑似网络或服务故障，停止批次。", flush=True)
                break
            if i % 10 == 0:
                export(out, records, config, profiles=profiles)
    except KeyboardInterrupt:
        interrupted = True
        print("\n[INTERRUPTED] 已保存进度，重新运行会跳过已成功公司。", flush=True)
    summary = export(out, records, config, profiles=profiles)
    print("[RESULT] " + json.dumps({"counts": summary["counts"],
                                    "candidate_articles": summary["candidate_articles"]}, ensure_ascii=False), flush=True)
    print("[FILES] coverage_300.csv | negative_news_candidates.csv | run_summary.json", flush=True)
    return 130 if interrupted else (2 if summary["counts"]["FAILED"] or summary["counts"]["RATE_LIMITED"] else 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(console_safe("[ERROR] " + str(exc)), file=sys.stderr)
        sys.exit(1)
