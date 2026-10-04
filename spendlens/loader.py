"""Read bank/credit-card CSV exports into integer-cent transactions.

Banks disagree on everything, so this is tolerant: header names are matched by alias, dates are
tried against several formats, amounts may be '$1,234.50', '(12.00)' or split into debit/credit
columns. Money is stored as integer cents (never floats). Convention after loading:
spending is NEGATIVE, income/refunds are POSITIVE."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DATE_FMTS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%b %d, %Y", "%Y/%m/%d", "%m-%d-%Y"]
ALIASES = {
    "date": ["date", "transaction date", "posted date", "post date", "posting date", "trans date"],
    "desc": ["description", "merchant", "name", "payee", "details", "memo", "transaction"],
    "amount": ["amount", "transaction amount", "amt"],
    "debit": ["debit", "withdrawal", "withdrawals", "money out", "charge"],
    "credit": ["credit", "deposit", "deposits", "money in", "payment"],
}


class LoadError(Exception):
    pass


@dataclass(frozen=True)
class Txn:
    day: date
    desc: str
    cents: int  # negative = spending


def parse_cents(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-") or s.endswith("-")
    digits = re.sub(r"[^\d.]", "", s)
    if not digits or digits == ".":
        return None
    whole, _, frac = digits.partition(".")
    cents = int(whole or 0) * 100 + int((frac + "00")[:2])
    return -cents if neg else cents


def parse_date(raw: str) -> date:
    s = (raw or "").strip()
    for fmt in DATE_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise LoadError(f"unrecognized date format: {raw!r}")


def _find(headers: list[str], key: str) -> str | None:
    low = {h.strip().lower(): h for h in headers}
    for alias in ALIASES[key]:
        if alias in low:
            return low[alias]
    return None


def load_csv(path: str | Path, positive_is_spend: bool = False) -> list[Txn]:
    """positive_is_spend: some credit-card exports list purchases as positive numbers."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        headers = rows[0].keys() if rows else []
    if not rows:
        return []
    h = list(headers)
    c_date, c_desc = _find(h, "date"), _find(h, "desc")
    c_amt, c_deb, c_cred = _find(h, "amount"), _find(h, "debit"), _find(h, "credit")
    if not c_date or not c_desc or not (c_amt or c_deb or c_cred):
        raise LoadError(f"could not find date/description/amount columns in headers: {h}")
    out = []
    for i, r in enumerate(rows, 2):
        try:
            if c_amt:
                cents = parse_cents(r[c_amt])
                if cents is not None and positive_is_spend:
                    cents = -cents
            else:
                deb, cred = parse_cents(r.get(c_deb, "") or ""), parse_cents(r.get(c_cred, "") or "")
                cents = (cred or 0) - abs(deb or 0) if (deb or cred) else None
            if cents is None:
                continue
            out.append(Txn(parse_date(r[c_date]), (r[c_desc] or "").strip(), cents))
        except LoadError as e:
            raise LoadError(f"row {i}: {e}") from None
    return out
