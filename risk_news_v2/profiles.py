"""Company aliases and context guards used by deterministic entity resolution.

The project company list is the canonical source.  Curated aliases below are
limited to widely used corporate brands, bilingual names, and controlled
subsidiary relationships.  They are deliberately small: an omitted alias
routes an article to review instead of creating an unsupported match.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from search_300_companies import COMPANIES


CORPORATE_SUFFIXES = re.compile(
    r"\s+(?:incorporated|inc|corporation|corp|company|co|limited|ltd|holdings?|group|"
    r"n\.?v\.?|plc|ag|s\.?a\.?)$",
    re.IGNORECASE,
)


CURATED_ALIASES: dict[str, tuple[str, ...]] = {
    "Apple": ("Apple Inc", "苹果", "苹果公司"),
    "Microsoft": ("Microsoft Corp", "微软", "微软公司"),
    "Alphabet Inc": ("Alphabet", "Alphabet Inc.", "字母表公司"),
    "Amazon": ("Amazon.com", "Amazon.com Inc", "亚马逊", "亚马逊公司"),
    "Meta Platforms": ("Meta", "Meta Platforms Inc", "元宇宙平台公司"),
    "Nvidia": ("NVIDIA", "NVIDIA Corp", "英伟达"),
    "Tesla": ("Tesla Inc", "特斯拉"),
    "Block Inc": ("Block, Inc.", "Block Inc.", "布洛克公司"),
    "Nasdaq Inc": ("Nasdaq, Inc.", "Nasdaq Inc.", "纳斯达克公司"),
    "BP": ("BP plc", "British Petroleum", "英国石油", "英国石油公司"),
    "Shell": ("Shell plc", "Royal Dutch Shell", "壳牌", "壳牌公司"),
    "Toyota Motor": ("Toyota", "Toyota Motor Corp", "丰田", "丰田汽车"),
    "Samsung Electronics": ("Samsung Electronics Co", "三星电子"),
    "Taiwan Semiconductor Manufacturing Company": ("TSMC", "台积电", "台湾积体电路制造"),
    "Alibaba Group": ("Alibaba", "阿里巴巴", "阿里巴巴集团"),
    "Tencent Holdings": ("Tencent", "腾讯", "腾讯控股"),
    "Baidu": ("Baidu Inc", "百度"),
    "JD.com": ("JD.com Inc", "京东", "京东集团"),
    "PDD Holdings": ("PDD", "Pinduoduo", "拼多多", "拼多多控股"),
    "Meituan": ("Meituan Dianping", "美团"),
    "Xiaomi Corporation": ("Xiaomi", "小米", "小米集团"),
    "BYD Company": ("BYD", "比亚迪", "比亚迪股份"),
    "CATL": ("Contemporary Amperex Technology", "宁德时代"),
    "NetEase": ("NetEase Inc", "网易"),
    "Bilibili": ("Bilibili Inc", "哔哩哔哩", "B站"),
    "China Mobile": ("中国移动",),
    "China Construction Bank": ("CCB", "中国建设银行", "建设银行"),
    "Industrial and Commercial Bank of China": ("ICBC", "中国工商银行", "工商银行"),
    "Ping An Insurance": ("Ping An", "中国平安", "平安保险"),
    "DBS Group": ("DBS", "星展集团", "星展银行"),
    "Sony Group": ("Sony", "索尼", "索尼集团"),
    "Honda Motor": ("Honda", "本田", "本田汽车"),
    "SoftBank Group": ("SoftBank", "软银", "软银集团"),
    "Nintendo": ("Nintendo Co", "任天堂"),
    "Volkswagen Group": ("Volkswagen", "VW Group", "大众汽车", "大众集团"),
    "BMW Group": ("BMW", "宝马", "宝马集团"),
    "Mercedes-Benz Group": ("Mercedes-Benz", "Mercedes", "梅赛德斯-奔驰", "奔驰集团"),
    "Deutsche Bank": ("德意志银行",),
    "HSBC Holdings": ("HSBC", "汇丰", "汇丰控股"),
}


SUBSIDIARIES: dict[str, dict[str, tuple[str, ...]]] = {
    "Alphabet Inc": {
        "Google": ("Google", "谷歌"),
        "YouTube": ("YouTube", "油管"),
        "Waymo": ("Waymo",),
    },
    "Amazon": {"AWS": ("AWS", "Amazon Web Services", "亚马逊云科技")},
    "Microsoft": {
        "LinkedIn": ("LinkedIn", "领英"),
        "GitHub": ("GitHub",),
        "Xbox": ("Xbox",),
    },
    "Meta Platforms": {
        "Facebook": ("Facebook", "脸书"),
        "Instagram": ("Instagram",),
        "WhatsApp": ("WhatsApp",),
    },
    "Block Inc": {"Square": ("Square",), "Cash App": ("Cash App",)},
    "Toyota Motor": {"Lexus": ("Lexus", "雷克萨斯")},
    "Booking Holdings": {"Booking.com": ("Booking.com",), "Priceline": ("Priceline",)},
    "Expedia Group": {"Vrbo": ("Vrbo",), "Hotels.com": ("Hotels.com",)},
}


AMBIGUOUS_CONTEXT: dict[str, dict[str, tuple[str, ...]]] = {
    "Apple": {
        "positive": ("iphone", "ipad", "mac", "app store", "ios", "technology company", "apple inc", "shares", "antitrust"),
        "negative": ("fruit", "orchard", "harvest", "grower", "crop", "juice"),
    },
    "Amazon": {
        "positive": ("aws", "e-commerce", "warehouse", "prime", "amazon.com", "retailer", "cloud"),
        "negative": ("rainforest", "river basin", "jungle"),
    },
    "BP": {
        "positive": ("bp plc", "british petroleum", "oil", "gas", "energy", "refinery", "petroleum"),
        "negative": ("football", "league", "blood pressure", "systolic", "diastolic"),
    },
    "Nasdaq Inc": {
        "positive": ("nasdaq inc", "exchange operator", "market operator", "listing business", "exchange company"),
        "negative": ("nasdaq index", "nasdaq composite", "tech-heavy nasdaq", "stocks on nasdaq", "nasdaq rose", "nasdaq fell"),
    },
    "Shell": {
        "positive": ("shell plc", "oil", "gas", "energy", "lng", "refinery"),
        "negative": ("seashell", "egg shell", "command shell", "shell script"),
    },
    "Block Inc": {
        "positive": ("block inc", "cash app", "square", "fintech", "payments"),
        "negative": ("city block", "road block", "building block", "block trade"),
    },
    "Target Corporation": {
        "positive": ("target corp", "retailer", "retail chain", "target store"),
        "negative": ("target price", "price target", "military target", "target audience"),
    },
    "Visa": {
        "positive": ("visa inc", "payments", "payment network", "credit card", "debit card"),
        "negative": ("travel visa", "work visa", "student visa", "immigration"),
    },
    "Snap Inc": {
        "positive": ("snap inc", "snapchat", "social media", "shares"),
        "negative": ("cold snap", "snap election", "snap decision"),
    },
    "Safran": {
        "positive": ("safran sa", "aerospace", "aircraft", "engine", "defense", "landing gear"),
        "negative": ("peter safran", "film", "producer", "hollywood", "dc studios", "movie"),
    },
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[^\w\u3400-\u9fff]+", " ", value)
    return " ".join(value.split())


def _default_aliases(company: str) -> tuple[str, ...]:
    aliases = [company]
    stripped = CORPORATE_SUFFIXES.sub("", company).strip()
    if stripped != company and len(normalize(stripped)) >= 4:
        aliases.append(stripped)
    aliases.extend(CURATED_ALIASES.get(company, ()))
    return tuple(dict.fromkeys(x for x in aliases if x))


@dataclass(frozen=True)
class CompanyProfile:
    canonical: str
    aliases: tuple[str, ...]
    subsidiaries: dict[str, tuple[str, ...]]
    positive_context: tuple[str, ...]
    negative_context: tuple[str, ...]


def get_profile(company: str, metadata: dict | None = None) -> CompanyProfile:
    metadata = metadata or {}
    if metadata:
        aliases = [company, metadata.get("display_name", ""), *(metadata.get("aliases") or [])]
        aliases = tuple(dict.fromkeys(str(value) for value in aliases if value))
        return CompanyProfile(
            canonical=company,
            aliases=aliases,
            subsidiaries=metadata.get("subsidiaries", {}) or {},
            positive_context=tuple(metadata.get("positive_context", []) or []),
            negative_context=tuple(metadata.get("negative_context", []) or []),
        )
    if company not in COMPANIES:
        return CompanyProfile(company, (company,), {}, (), ())
    context = AMBIGUOUS_CONTEXT.get(company, {})
    return CompanyProfile(
        canonical=company,
        aliases=_default_aliases(company),
        subsidiaries=SUBSIDIARIES.get(company, {}),
        positive_context=context.get("positive", ()),
        negative_context=context.get("negative", ()),
    )

