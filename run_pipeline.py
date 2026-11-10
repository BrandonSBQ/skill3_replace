#!/usr/bin/env python3
"""Unified entry point for offline V2 cleaning and explicitly authorized full runs."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from risk_news_v2.pipeline import clean_existing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="300-company negative-news monitoring pipeline V2")
    parser.add_argument("--mode", choices=("clean-existing", "full"), required=True)
    parser.add_argument("--input", default="results_full_300", help="V1 input directory for clean-existing")
    parser.add_argument("--output", default="results_full_300_v2", help="V2 output directory")
    parser.add_argument("--acquisition-output", default="results_full_300_refresh", help="V1 acquisition directory for full mode")
    parser.add_argument("--company-file", default="", help="optional structured company catalog CSV for full mode")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--per-company", type=int, default=5)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--allow-network", action="store_true", help="required for full mode; authorizes RSS and public-page requests")
    return parser


def _configure_logging(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(output / "pipeline.log", encoding="utf-8")],
        force=True,
    )


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mode == "full" and not args.allow_network:
        parser.error("full mode requires explicit --allow-network authorization")
    if not 1 <= args.limit <= 300:
        parser.error("--limit must be between 1 and 300")
    if not 1 <= args.days <= 30:
        parser.error("--days must be between 1 and 30")
    if args.per_company < 1:
        parser.error("--per-company must be at least 1")

    output = Path(args.output).expanduser().resolve()
    _configure_logging(output)
    input_dir = Path(args.input).expanduser().resolve()
    network_used = False
    if args.mode == "full":
        from extract_article_bodies import main as extract_main
        from search_300_companies import main as search_main

        acquisition = Path(args.acquisition_output).expanduser().resolve()
        logging.info("Starting authorized RSS acquisition into %s", acquisition)
        search_args = [
            "--limit", str(args.limit), "--days", str(args.days), "--delay", str(args.delay), "--output", str(acquisition)
        ]
        if args.company_file:
            search_args.extend(["--company-file", str(Path(args.company_file).expanduser().resolve())])
        search_code = search_main(search_args)
        candidates = acquisition / "negative_news_candidates.csv"
        if search_code not in (0, 2, 130) or not candidates.exists():
            logging.error("Search did not produce a candidate file (exit %s)", search_code)
            return int(search_code or 2)
        logging.info("Starting compliant body extraction with existing checkpoints")
        extract_main([
            "--input", str(candidates), "--output", str(acquisition), "--per-company", str(args.per_company),
            "--delay", str(max(1.0, args.delay)),
        ])
        input_dir = acquisition
        network_used = True

    logging.info("Running deterministic V2 cleaning from %s", input_dir)
    counts = clean_existing(input_dir, output, network_used=network_used)
    logging.info("V2 complete: %s", json.dumps(counts, ensure_ascii=False, sort_keys=True))
    print(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)

