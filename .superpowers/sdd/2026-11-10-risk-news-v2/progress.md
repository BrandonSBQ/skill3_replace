# SDD ledger — plan: docs/superpowers/plans/2026-11-10-risk-news-v2.md

Ruling: The supplied project is not a Git repository, so worktree creation, task commits, and Git-range review packages are unavailable — use an in-project V1 backup, per-task RED/GREEN test evidence, and final fresh review of the complete files instead — cost if wrong: rollback is file-based rather than commit-based.
Pre-flight: Task 1 `resolve_entity` feeds Task 2 screening and Task 4 routing; keep status/relationship/confidence keys stable.
Pre-flight: Tasks 2 and 3 enrich the association records consumed by Task 4; all enrichment functions return dictionaries merged without deleting source fields.
Pre-flight: Task 4 CLI produces the artifacts consumed by Task 5 full local processing and verification.

Task 1: Ruling: Chinese corporate-form aliases such as `苹果公司` count as strong evidence even when an English ambiguity guard exists — otherwise valid bilingual evidence is systematically downgraded — cost if wrong: a misleading corporate-form alias could create a false match.
Task 1: complete (no Git commits; tests: `python -m pytest tests/test_entity_resolution.py -q` -> 8 passed; full suite with workspace basetemp -> 17 passed).
Task 2: Ruling: extreme repeated boilerplate is always `INVALID` even when raw length inflates the numeric score — repetition is direct evidence that length is misleading — cost if wrong: legitimate intentionally repeated transcripts could be rejected.
Task 2: complete (no Git commits; tests: `python -m pytest tests/test_content_and_classification.py -q` -> 14 passed; full suite -> 31 passed).
Task 3: Ruling: the monitoring `published_at` prefers the exact RSS timestamp while retaining article publication and update fields separately — V1 article dates are often date-only and must not silently replace a precise source timestamp — cost if wrong: RSS syndication delay may be shown as the primary publication time.
Task 3: complete (no Git commits; tests: `python -m pytest tests/test_dates_and_deduplication.py -q` -> 8 passed; full suite -> 39 passed).
Task 4: Ruling: same-event alternative linking uses title-fact similarity as an independent path when one source has no body — comparing a long full text against a title-only blocked source unfairly dilutes overlap — cost if wrong: unusually similar headlines about separate events within three days may be grouped and must remain `UNVERIFIED`.
Task 4: complete (no Git commits; tests: `python -m pytest tests/test_pipeline.py -q` -> 4 passed; full suite -> 43 passed).
Task 5: complete (no Git commits; offline full-data run processed 856 associations into 108 cleaned, 252 review, 496 rejected; 300 coverage rows and 169 candidate events).
Final review: self-review (subagent review prohibited for this turn; project has no Git range).
Final: fixed full-mode audit falsely recording `network_used=false` — `test_audit_records_when_inputs_came_from_authorized_network_run` RED→GREEN, suite 45/45.
Final: fixed rejected invalid pages contributing sources to event candidates — `test_rejected_invalid_content_does_not_feed_event_candidates` RED→GREEN, suite 45/45.
Final: fixed rejected cross-company association IDs leaking through article-level source aggregation into valid event candidates — `test_event_sources_exclude_rejected_cross_company_association` RED→GREEN, suite 46/46.
Final: minor (deferred): similarity-group event IDs can change when a new lexicographically earlier source article is added; IDs are stable for identical inputs.
Final: minor (deferred): JSONL/CSV outputs are atomic, but interruption during the small audit/report writes can leave truncated V2 metadata until the safe offline rerun repairs it.

