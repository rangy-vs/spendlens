"""Terminal and self-contained HTML reports (no JS, no external assets)."""
from __future__ import annotations

from html import escape

from .analyze import Subscription, by_category, by_month, find_duplicates, find_subscriptions, money, top_merchants
from .loader import Txn


def text_report(txns: list[Txn], cats=None) -> str:
    spend = sum(-t.cents for t in txns if t.cents < 0)
    income = sum(t.cents for t in txns if t.cents > 0)
    lines = [f"{len(txns)} transactions | spent {money(spend)} | income {money(income)} | net {money(income - spend)}", ""]
    lines.append("Spending by month")
    lines += [f"  {m}  {money(c):>12}" for m, c in by_month(txns).items()]
    lines += ["", "Spending by category"]
    lines += [f"  {k:<22}{money(v):>12}  {v / spend:>5.0%}" for k, v in by_category(txns, cats).items()] if spend else []
    subs = find_subscriptions(txns)
    lines += ["", f"Recurring charges ({len(subs)}): about {money(sum(s.monthly_cents for s in subs))}/month, "
                  f"{money(12 * sum(s.monthly_cents for s in subs))}/year"]
    for s in subs:
        note = f"  PRICE CHANGE {money(s.price_change[0])} -> {money(s.price_change[1])} (since {s.price_change[2]})" if s.price_change else ""
        lines.append(f"  {s.merchant:<24}{money(s.typical_cents):>10} {s.cadence:<9} next ~{s.next_expected}{note}")
    dups = find_duplicates(txns)
    if dups:
        lines += ["", "Possible duplicate charges"]
        lines += [f"  {a.day} & {b.day}  {money(-a.cents)}  {a.desc[:40]}" for a, b in dups]
    return "\n".join(lines)


def _bars(items: list[tuple[str, int]]) -> str:
    top = max((v for _, v in items), default=1) or 1
    return "".join(f'<div class="row"><span class="lbl">{escape(k)}</span>'
                   f'<span class="bar" style="width:{v / top * 100:.1f}%"></span>'
                   f'<span class="val">{money(v)}</span></div>' for k, v in items)


def html_report(txns: list[Txn], cats=None, title: str = "Spending report") -> str:
    spend = sum(-t.cents for t in txns if t.cents < 0)
    subs: list[Subscription] = find_subscriptions(txns)
    sub_rows = "".join(
        f"<tr><td>{escape(s.merchant)}</td><td>{money(s.typical_cents)}</td><td>{s.cadence}</td>"
        f"<td>{money(s.monthly_cents)}</td><td>{s.next_expected}</td>"
        f"<td>{'⚠ ' + money(s.price_change[0]) + ' → ' + money(s.price_change[1]) if s.price_change else ''}</td></tr>"
        for s in subs)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{font-size:1.5rem}}h2{{margin-top:2rem;font-size:1.1rem}} .stat{{font-size:1.8rem;font-weight:600}}
.row{{display:flex;align-items:center;gap:.6rem;margin:.25rem 0}}.lbl{{width:11rem;flex:none}}
.bar{{height:.9rem;background:#3b82f6;border-radius:3px;min-width:2px}}.val{{margin-left:auto;font-variant-numeric:tabular-nums}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.35rem .5rem;border-bottom:1px solid #ddd;text-align:left}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#eee}}td,th{{border-color:#333}}}}
</style><h1>{escape(title)}</h1>
<div class="stat">{money(spend)} <small>spent across {len(txns)} transactions</small></div>
<h2>By month</h2>{_bars(list(by_month(txns).items()))}
<h2>By category</h2>{_bars(list(by_category(txns, cats).items()))}
<h2>Top merchants</h2>{_bars([(m, c) for m, c, _ in top_merchants(txns)])}
<h2>Recurring charges: {money(sum(s.monthly_cents for s in subs))}/month, {money(12 * sum(s.monthly_cents for s in subs))}/year</h2>
<table><tr><th>Merchant</th><th>Charge</th><th>Cadence</th><th>≈ Monthly</th><th>Next</th><th>Note</th></tr>{sub_rows}</table>
</html>"""
