# Risk News Monitoring V2 Design

## Intent

Upgrade the existing 300-company Google News RSS project into a conservative, auditable local cleaning pipeline for downstream AI risk analysis. V2 reuses the saved 856 RSS candidates and 559 extraction records, preserves all V1 artifacts, and does not treat a keyword hit or a successful HTTP extraction as a verified risk event.

## Goals

- Validate extracted text independently from the V1 `fetch_status`.
- Resolve each article-company association with explicit relationship, confidence, and evidence.
- Screen the 12 requested negative-event categories while handling known ambiguity cases.
- Deduplicate source articles and conservatively group likely same-event reporting without losing cross-company associations.
- reconcile RSS and article dates in UTC and expose Asia/Hong_Kong display values.
- Produce the requested `results_full_300_v2` dataset, coverage, audit, and quality report from saved data.
- Provide one CLI for offline cleaning and an explicitly authorized network-enabled full run.

## Non-goals

- No formal credit rating, event verification, or unsupported risk conclusion.
- No paywall, login, CAPTCHA, robots.txt, or anti-bot bypass.
- No automatic acceptance merely to increase cleaned-record counts.
- No first-pass re-query of all 300 companies.

## Architecture

V1 remains the acquisition layer. A new `risk_news_v2` package is a deterministic post-processing layer with focused modules for company profiles/entity resolution, content validation, negative screening, dates, deduplication, and output/report generation. `run_pipeline.py` orchestrates `clean-existing`; `full` calls the existing search and extraction entry points only when `--allow-network` is present, then runs the same cleaner.

Every input row becomes an auditable article-company association. Source-level IDs are independent of company so one article can retain multiple company associations. Routing is conservative: only `VALID` content with a sufficiently supported entity association and negative candidate status enters `articles_cleaned.jsonl`; uncertainty goes to review; demonstrably invalid, unrelated, or non-negative rows go to rejected.

## Approaches Considered

1. Replace V1 with a single new crawler and classifier. Rejected because it risks regressions, overwrites validated acquisition behavior, and requires unnecessary network access.
2. Add a local deterministic V2 cleaning layer over V1 artifacts. Selected because it preserves history, is reproducible, supports audit, and can route semantic uncertainty to later agents.
3. Batch-classify all rows with an external LLM. Rejected because it is expensive, non-deterministic, and may expose data externally; V2 instead emits review-ready evidence.

## Constraints and Calls

- Python 3.12 and standard-library-first implementation; existing acquisition dependencies remain unchanged.
- Alias evidence comes from the project canonical list plus a small curated, explicit bilingual brand/subsidiary map. Ambiguous short/common names require contextual evidence.
- Event grouping is intentionally conservative; uncertain similarity does not force a merge.
- Missing or blocked content may link to saved same-event alternatives but is never presented as the original source's full text.
- Historical V1 result directories are read-only inputs to V2.

