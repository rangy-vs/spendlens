from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from .loader import Txn
from .merchants import categorize, normalize_merchant

CADENCES = [("weekly", 6, 8, 52 / 12), ("monthly", 26, 35, 1.0), ("quarterly", 85, 97, 1 / 3), ("yearly", 350, 380, 1 / 12)]


@dataclass
class Subscription:
    merchant: str
    cadence: str
    typical_cents: int
    last_charge: date
    next_expected: date
    monthly_cents: int
    charges: int
    price_change: tuple[int, int, date] | None  # (old, new, date of the most recent >5% change)


def spending(txns: list[Txn]) -> list[Txn]:
    return [t for t in txns if t.cents < 0]


def by_month(txns: list[Txn]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for t in spending(txns):
        out[f"{t.day:%Y-%m}"] += -t.cents
    return dict(sorted(out.items()))


def by_category(txns: list[Txn], cats=None) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for t in spending(txns):
        out[categorize(t.desc, t.cents, cats)] += -t.cents
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def top_merchants(txns: list[Txn], n: int = 8) -> list[tuple[str, int, int]]:
    agg: dict[str, list[int]] = defaultdict(list)
    for t in spending(txns):
        agg[normalize_merchant(t.desc)].append(-t.cents)
    rows = [(m, sum(v), len(v)) for m, v in agg.items()]
    return sorted(rows, key=lambda r: -r[1])[:n]


def find_subscriptions(txns: list[Txn], min_charges: int = 3, amount_tol: float = 0.15) -> list[Subscription]:
    groups: dict[str, list[Txn]] = defaultdict(list)
    for t in spending(txns):
        groups[normalize_merchant(t.desc)].append(t)
    subs = []
    for merchant, ts in groups.items():
        ts.sort(key=lambda t: t.day)
        if len(ts) < min_charges:
            continue
        gaps = [(b.day - a.day).days for a, b in zip(ts, ts[1:])]
        gap = statistics.median(gaps)
        cadence = next(((n, per) for n, lo, hi, per in CADENCES if lo <= gap <= hi), None)
        if not cadence:
            continue
        amounts = [-t.cents for t in ts]
        med = statistics.median(amounts)
        # reject grocery/coffee-style merchants: amounts must be stable. Compare CONSECUTIVE charges,
        # not each charge to the median, so one price hike doesn't hide a real subscription.
        pairs = list(zip(amounts, amounts[1:]))
        if sum(abs(b - a) <= amount_tol * a for a, b in pairs) < len(pairs) * 0.8:
            continue
        lo, hi = next((lo, hi) for n, lo, hi, _ in CADENCES if n == cadence[0])
        if sum(lo <= g <= hi for g in gaps) < len(gaps) * 0.75:
            continue
        last = ts[-1]
        change = None
        for prev, cur in reversed(list(zip(ts, ts[1:]))):   # most recent >5% step in the charge history
            if abs(cur.cents - prev.cents) > 0.05 * abs(prev.cents):
                change = (-prev.cents, -cur.cents, cur.day)
                break
        subs.append(Subscription(merchant, cadence[0], -last.cents, last.day, last.day + timedelta(days=round(gap)),
                                 int(round(-last.cents * cadence[1])), len(ts), change))
    return sorted(subs, key=lambda s: -s.monthly_cents)


def find_duplicates(txns: list[Txn], window_days: int = 2) -> list[tuple[Txn, Txn]]:
    """Same merchant + same amount within a couple of days: possible double charge."""
    by_key: dict[tuple, list[Txn]] = defaultdict(list)
    for t in spending(txns):
        by_key[(normalize_merchant(t.desc), t.cents)].append(t)
    dups = []
    for ts in by_key.values():
        ts.sort(key=lambda t: t.day)
        dups += [(a, b) for a, b in zip(ts, ts[1:]) if (b.day - a.day).days <= window_days]
    return sorted(dups, key=lambda p: p[0].day)


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"
