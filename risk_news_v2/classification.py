"""Conservative deterministic screening for negative-news candidates."""
from __future__ import annotations

import re


CATEGORIES = (
    "债务违约与偿付风险",
    "流动性及融资压力",
    "信用评级变动",
    "破产、重组及债务调整",
    "财务状况恶化",
    "监管调查及处罚",
    "欺诈及公司治理",
    "重大诉讼",
    "经营与业务风险",
    "证券市场异常",
    "制裁与地缘政治",
    "其他重大负面事件",
)


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("债务违约与偿付风险", (
        r"\bdefault(?:ed|ing)?\s+(?:on|under)\s+(?:its\s+)?(?:debt|bond|loan|payment)",
        r"\bdebt default\b", r"\bpayment default\b", r"\bmissed (?:a )?(?:debt |bond |interest )?payment\b",
        r"\bfailed to (?:pay|repay|service)\b", r"违约", r"未兑付", r"未偿付",
    )),
    ("流动性及融资压力", (
        r"\bliquidity (?:pressure|crisis|shortfall|concern|risk)\b", r"\bcash crunch\b",
        r"\bfinancing pressure\b", r"\bunable to refinance\b", r"\bfunding shortfall\b", r"流动性", r"资金链", r"融资压力",
    )),
    ("破产、重组及债务调整", (
        r"\bbankrupt(?:cy)?\b", r"\binsolven(?:cy|t)\b", r"\bchapter 11\b", r"\bdebt restructuring\b",
        r"\brestructur(?:ing|ed) its debt\b", r"破产", r"债务重组", r"清盘",
    )),
    ("财务状况恶化", (
        r"\bprofit warning\b", r"\bmaterial loss(?:es)?\b", r"\bimpairment charge\b", r"\bgoing concern\b",
        r"\bearnings collapse\b", r"财务恶化", r"盈利预警", r"巨额亏损", r"减值",
    )),
    ("监管调查及处罚", (
        r"\bregulator(?:y)? (?:investigation|probe|enforcement|action)\b", r"\binvestigation by (?:the )?[a-z ]*regulator\b",
        r"\bregulators?.{0,80}\b(?:opened?|opens?|launched?) (?:an? )?.{0,40}\binvestigation\b",
        r"\b(?:regulators?|authorit(?:y|ies)) (?:fined|fines|penalized|charged)\b", r"\bimposed (?:a |an )?\$?[\d,.]+.*penalty\b",
        r"\bsubpoena(?:ed)?\b", r"监管调查", r"监管处罚", r"罚款", r"立案调查",
    )),
    ("欺诈及公司治理", (
        r"\bfraud(?:ulent)?\b", r"\bbriber(?:y|ies)\b", r"\bcorruption\b", r"\baccounting misconduct\b",
        r"\bmoney laundering\b", r"\bgovernance failure\b", r"欺诈", r"贿赂", r"腐败", r"财务造假", r"洗钱",
    )),
    ("经营与业务风险", (
        r"\blayoffs?\b", r"\bjob cuts?\b", r"\bcut(?:ting)?\s+[\d,]+\s+jobs?\b", r"\bproduct recall\b",
        r"\brecall(?:s|ed|ing)?\s+(?:of\s+)?(?:[\d,]+\s+)?(?:[\w-]+\s+){0,3}(?:vehicles?|cars?|products?|units?)\b",
        r"\brecall of\s+(?:[\d,]+\s+)?(?:[\w-]+\s+){0,3}(?:vehicles?|cars?|products?|units?)\b",
        r"\bshutdown\b", r"\bproduction halt\b",
        r"\bcyberattack\b", r"\bdata breach\b", r"\boperational disruption\b",
        r"\b(?:braking|anti-skid) system (?:fault|failure)\b", r"\btyres? burst\b", r"\bserious (?:safety )?incident\b",
        r"裁员", r"召回", r"停产", r"数据泄露", r"制动系统故障", r"严重事故",
    )),
    ("证券市场异常", (
        r"\btrading halt(?:ed)?\b", r"\bshares? (?:plunged|collapsed|tumbled)\b", r"\bstock (?:plunged|collapsed|tumbled)\b",
        r"\babnormal trading\b", r"停牌", r"股价暴跌", r"异常交易",
    )),
    ("制裁与地缘政治", (
        r"\bsanction(?:ed|s)?\b", r"\bexport ban\b", r"\bblacklist(?:ed)?\b", r"\bgeopolitical risk\b",
        r"制裁", r"出口禁令", r"地缘政治",
    )),
    ("其他重大负面事件", (
        r"\bmajor accident\b", r"\bfatal explosion\b", r"\benvironmental disaster\b", r"重大事故", r"重大负面事件",
    )),
)

EQUITY_RATING = re.compile(
    r"(?:analyst|broker|investment bank).{0,60}(?:downgrad|cut).{0,60}(?:stock|shares?|price target|buy|neutral|hold|sell)|"
    r"(?:downgrad|cut).{0,40}(?:shares?|stock).{0,40}(?:neutral|hold|sell|buy|price target)",
    re.IGNORECASE | re.DOTALL,
)
CREDIT_RATING = re.compile(
    r"(?:moody'?s|s&p|standard & poor'?s|fitch|rating agency).{0,80}(?:downgrad|rating cut|negative outlook)|"
    r"(?:downgrad|rating cut|negative outlook).{0,80}(?:issuer|credit|debt|bond|senior unsecured).{0,20}rating|"
    r"(?:issuer|corporate|credit|debt|bond).{0,20}rating.{0,40}(?:downgrad|lowered|cut)|信用评级(?:下调|降低)|负面展望",
    re.IGNORECASE | re.DOTALL,
)
FILED_LITIGATION = re.compile(
    r"\b(?:filed?|files?) (?:a |an )?(?:class action )?(?:lawsuit|complaint|claim)\b|"
    r"\b(?:lawsuit|complaint|claim) (?:was |has been )?filed\b|\b(?:sued|suing)\b|\bclass[- ]action (?:lawsuit|suit)\b|"
    r"提起诉讼|起诉|诉至法院",
    re.IGNORECASE,
)
HYPOTHETICAL_LITIGATION = re.compile(
    r"\bmay face (?:a )?(?:potential )?(?:lawsuit|legal risk)\b|\bpotential legal risk\b|"
    r"\bno (?:lawsuit|complaint) (?:has been |was )?filed\b|潜在法律风险",
    re.IGNORECASE,
)
POLICY_DISCUSSION = re.compile(
    r"\b(?:proposed|new|draft) (?:regulation|rules?|policy)\b|\blawmakers? discussed\b|监管政策|征求意见",
    re.IGNORECASE,
)
GENERIC_NEGATIVE = re.compile(
    r"\brisk\b|\bconcern\b|\bwarning\b|\bdecline\b|\bpressure\b|\binvestigat|诉讼|风险|调查",
    re.IGNORECASE,
)
POSITIVE_FINANCIAL = re.compile(
    r"\bloss(?:es)? (?:narrowed|declined|fell|shrunk)\b|\breturned? to profit\b|"
    r"\bprofit (?:rose|increased|grew)\b|\brecord (?:profit|revenue|earnings)\b|"
    r"\bbeat(?:s|ing)? expectations\b|亏损(?:收窄|减少)|扭亏为盈|利润(?:增长|上升)",
    re.IGNORECASE,
)
NEGATIVE_FINANCIAL_OVERRIDE = re.compile(
    r"\bprofit warning\b|\bgoing concern\b|\bimpairment charge\b|"
    r"\bloss(?:es)? (?:widened|increased|grew)\b|盈利预警|持续经营|亏损扩大",
    re.IGNORECASE,
)

FORWARD_LOOKING_MARKER = re.compile(
    r"(?:^|\n|\.\s+)\s*(?:cautionary statement (?:on|regarding) )?forward[- ]looking (?:information|statements?)\s*:?",
    re.IGNORECASE,
)


def _negated(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 60):start].casefold()
    suffix = text[end:end + 45].casefold()
    english_prefix = re.search(
        r"(?:\bno\b|\bnot\b|\bwithout\b|\bnever\b|\bwon't\b|\bwill not\b)(?:\W+\w+){0,5}\W*$",
        prefix,
    )
    chinese_prefix = re.search(r"(?:不|未|没有|不会|并无)[^，。！？]{0,12}$", prefix)
    english_suffix = re.search(r"^\W*(?:was |were |is |are |will be )?(?:not planned|ruled out|avoided|denied)", suffix)
    return bool(english_prefix or chinese_prefix or english_suffix)


def _matches(patterns: tuple[str, ...], text: str) -> list[str]:
    hits = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            if not _negated(text, match.start(), match.end()):
                hits.append(match.group(0)[:100])
                break
    return hits


def _screening_text(title: str, text: str) -> str:
    """Exclude trailing hypothetical-risk boilerplate while retaining the article lead."""
    body = text or ""
    marker = FORWARD_LOOKING_MARKER.search(body)
    if marker and marker.start() >= 40:
        body = body[:marker.start()]
    return " ".join((title or "", body))


def classify_negative(title: str, text: str, entity_result: dict) -> dict:
    entity_status = entity_result.get("entity_match_status")
    if entity_status == "UNRELATED":
        return {
            "negative_screening_status": "UNRELATED",
            "negative_categories": [],
            "negative_screening_evidence": "entity resolver marked association unrelated",
        }

    combined = _screening_text(title, text)
    categories: list[str] = []
    evidence: list[str] = []

    folded = combined.casefold()
    default_exclusion = bool(re.search(r"\b(?:by default|default (?:setting|search|browser|option|configuration))\b", folded))
    for category, patterns in RULES:
        hits = _matches(patterns, combined)
        if category == "债务违约与偿付风险" and default_exclusion and not any(
            phrase in folded for phrase in ("debt default", "payment default", "missed payment", "违约", "未兑付")
        ):
            hits = []
        if hits:
            categories.append(category)
            evidence.append(f"{category}: {hits[0]}")

    if CREDIT_RATING.search(combined) and not (EQUITY_RATING.search(combined) and "credit" not in folded and "debt" not in folded):
        if "信用评级变动" not in categories:
            categories.append("信用评级变动")
        evidence.append("信用评级变动: explicit issuer/debt/rating-agency context")

    equity_only = bool(EQUITY_RATING.search(combined)) and "信用评级变动" not in categories
    hypothetical_law = bool(HYPOTHETICAL_LITIGATION.search(combined))
    if FILED_LITIGATION.search(combined) and not hypothetical_law:
        if "重大诉讼" not in categories:
            categories.append("重大诉讼")
        evidence.append("重大诉讼: filed complaint/lawsuit language")

    if POSITIVE_FINANCIAL.search(combined) and not NEGATIVE_FINANCIAL_OVERRIDE.search(combined):
        categories = [category for category in categories if category != "财务状况恶化"]
        evidence = [item for item in evidence if not item.startswith("财务状况恶化:")]

    categories = [category for category in CATEGORIES if category in categories]
    if entity_status != "MATCHED":
        status = "NEEDS_REVIEW"
    elif hypothetical_law:
        status = "NEEDS_REVIEW"
    elif categories:
        status = "NEGATIVE_CANDIDATE"
    elif POLICY_DISCUSSION.search(combined):
        status = "POSSIBLY_RELEVANT"
        evidence.append("policy discussion without enforcement evidence")
    elif equity_only or default_exclusion:
        status = "NOT_NEGATIVE"
        evidence.append("excluded non-credit rating/default usage")
    elif GENERIC_NEGATIVE.search(combined):
        status = "POSSIBLY_RELEVANT"
        evidence.append("generic negative language without a deterministic event rule")
    else:
        status = "NOT_NEGATIVE"
        evidence.append("no supported negative-event evidence")

    return {
        "negative_screening_status": status,
        "negative_categories": categories,
        "negative_screening_evidence": "; ".join(evidence),
    }

