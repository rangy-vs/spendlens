"""python -m spendlens transactions.csv [--html report.html] [--categories my.json] [--positive-is-spend]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import LoadError, load_csv
from .merchants import load_categories
from .report import html_report, text_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="spendlens", description="Spending + subscription analyzer for bank CSVs. Runs 100% locally.")
    ap.add_argument("csv")
    ap.add_argument("--html", help="also write a standalone HTML report")
    ap.add_argument("--categories", help="JSON file {category: [keywords]} to override defaults")
    ap.add_argument("--positive-is-spend", action="store_true", help="credit-card exports that list purchases as positive")
    a = ap.parse_args(argv)
    try:
        txns = load_csv(a.csv, a.positive_is_spend)
    except (LoadError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not txns:
        print("No transactions found.", file=sys.stderr)
        return 1
    cats = load_categories(a.categories)
    print(text_report(txns, cats))
    if a.html:
        Path(a.html).write_text(html_report(txns, cats), encoding="utf-8")
        print(f"\nHTML report -> {a.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
