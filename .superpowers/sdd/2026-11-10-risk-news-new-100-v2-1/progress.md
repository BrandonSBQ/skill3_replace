# SDD ledger — plan: docs/superpowers/plans/2026-11-10-risk-news-new-100-v2-1.md

Ruling: The project is not a Git repository, so V2.0 source files will be backed up and every task will use RED/GREEN tests plus the ledger instead of commits — cost if wrong: rollback is file-based rather than commit-based.
Pre-flight: Task 1 catalog fields feed Task 2 query generation and Task 3 entity metadata; field names are fixed in the catalog tests.
Pre-flight: Task 2 acquisition output remains compatible with the existing extractor and Task 3 cleaner; new columns are additive.
Pre-flight: Task 3 enriched records feed Task 4 issue audit and report; existing V2 output keys remain stable.
Pre-flight: Task 4 report consumes Task 5 live outputs and must derive every statistic from files rather than parameters.

Task 1: complete (catalog 100; regional counts 25/25/25/25; internal duplicates 0; historical overlap 0; suite 50 passed).
Task 2: Ruling: bilingual names are combined into one quoted OR query per company rather than two requests — this tests cross-language recall while halving rate-limit exposure — cost if wrong: Google may rank a combined query differently than separate locale queries.
Task 2: complete (parameterized search tests 7 passed; full suite 57 passed).
Task 3: complete (catalog-aware entity resolution, negation/positive-direction guards, date-conflict routing; full suite 63 passed).
Task 4: complete (deterministic 15/15/10 sampling, issue CSV, stress summary and final report; full suite 67 passed).
Task 5 live acquisition: RSS requests completed 100/100; 42 SUCCESS and 58 NO_CANDIDATE_FOUND; 131 candidates. Body extraction attempted 108; 85 V1 SUCCESS; no robots/paywall bypass.
Task 5 live ruling: a GBK console crash at company 70 was fixed with encoding-safe output and the checkpointed run resumed without repeating completed companies — cost if wrong: escaped progress labels are less readable on legacy consoles but source data remains Unicode.
Task 5 content audit: fixed six observed classifier gaps (money laundering/class-action wording, aircraft safety faults, forward-looking boilerplate, cut-jobs word order, vehicle recalls, active suing wording). Each fix was RED then GREEN and was recorded in test_issues.csv.
Task 5 final cleaning: 131 routed records = 18 CLEANED + 74 NEEDS_REVIEW + 39 REJECTED; candidate negative events 31; 83 V2-valid bodies; suite 77 passed; stress audit open issues 0.
Task 5 final entity audit: fixed Bank of China vs People's Bank of China substring collision and CMB vs Capital Markets Board acronym collision; both reproduced RED, fixed generically with conflicting contexts, and rerouted conservatively.
Preservation check: all 20 pre-recorded SHA-256 hashes under results_full_300 and results_full_300_v2 are unchanged.

