#!/usr/bin/env python3
"""Execute or resume the authorized V2.1 new-100 network stress test."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from risk_news_v2.company_catalog import load_company_catalog, validate_catalog, write_catalog_audit
from risk_news_v2.stress_audit import run_stress_audit
from run_pipeline import main as pipeline_main
from search_300_companies import COMPANIES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the V2.1 new-100 end-to-end stress test")
    parser.add_argument("--catalog", default="test_new_100/company_list_100.csv")
    parser.add_argument("--output", default="results_new_100_v2")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--per-company", type=int, default=5)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    catalog = Path(args.catalog).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    rows = load_company_catalog(catalog)
    audit = validate_catalog(rows, COMPANIES)
    if not audit["is_valid"]:
        parser.error("company catalog failed validation: " + json.dumps(audit, ensure_ascii=False))
    write_catalog_audit(catalog.parent / "company_list_audit.json", audit)

    if not args.audit_only:
        if not args.allow_network:
            parser.error("network run requires explicit --allow-network")
        code = pipeline_main([
            "--mode", "full", "--company-file", str(catalog), "--limit", str(len(rows)),
            "--days", str(args.days), "--per-company", str(args.per_company), "--delay", str(args.delay),
            "--acquisition-output", str(output), "--output", str(output), "--allow-network",
        ])
        if code != 0:
            return code
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(catalog.parent / "company_list_audit.json", output / "company_list_audit.json")
    summary = run_stress_audit(output, final_report_path=Path.cwd() / "V2_100_TEST_FINAL_REPORT.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

