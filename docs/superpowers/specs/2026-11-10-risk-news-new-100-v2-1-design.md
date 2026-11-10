# Risk News Monitor V2.1 New-100 Stress Test Design

## Intent

Run a real, resumable, seven-day end-to-end network test on 100 public companies that do not overlap the historical 300, while preserving all historical data. The test must exercise bilingual/alias search, compliant body acquisition, V2 cleaning, deterministic sampling, content-level QA, regression repair, and auditable reconciliation.

## Selected approach

Extend the existing acquisition code instead of creating a second crawler. A structured company catalog supplies legal name, aliases, ticker, parent, region, country, industry, languages, and disambiguation context. `search_300_companies.py` remains backward compatible but accepts `--company-file`; `run_pipeline.py` passes that catalog through full mode. A separate stress-audit module produces reproducible issue samples and the V2.1 final report without weakening V2 gates.

Alternatives rejected: copying the 300-company script and replacing its constant would create divergent logic; using an LLM for all classifications would be non-deterministic and unnecessarily externalize data; manually reviewing only easy records would bias the audit.

## Goals

- Exactly 100 real companies, 25 per requested macro-region, no internal normalized/alias/ticker duplicates and no overlap with the historical 300.
- One auditable bilingual/alias RSS query per company, conservative completion states, checkpoint resume, and rate-limit stop behavior.
- At most five body attempts per company using the existing robots-aware extractor.
- V2 cleaning for arbitrary company counts and catalog-provided aliases/context.
- Regression coverage for negation, positive performance, ambiguous people/company names, date conflicts, source traceability, and network audit flags.
- Reproducible stratified review of up to 15 cleaned, 15 review, and 10 rejected records.

## Non-goals and constraints

- No access to private holdings, issuer lists, credentials, or internal data.
- No paywall, robots.txt, CAPTCHA, login, or anti-bot bypass.
- Google News RSS and extracted text remain unverified candidate evidence.
- Historical `results_full_300` and `results_full_300_v2` are immutable inputs/baselines.
- Network steps resume from checkpoints and are not repeated unless affected by a proven acquisition defect.

