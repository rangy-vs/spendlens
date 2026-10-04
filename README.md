# spendlens

![ci](https://github.com/rangy-vs/spendlens/actions/workflows/ci.yml/badge.svg)

Find where your money goes and which subscriptions are quietly billing you, from the CSV your bank already lets you export. **Runs 100% locally: no network calls, no accounts, no dependencies beyond the standard library.**

```bash
python examples/make_sample.py                       # generates a FICTIONAL 6-month statement
python -m spendlens examples/sample_statement.csv --html report.html
```
```
Recurring charges (4): about $119.96/month, $1,439.52/year
  COMCAST XFINITY   $64.99 monthly   next ~2026-10-16
  PLANET FITNESS    $24.99 monthly   next ~2026-10-11
  NETFLIX.COM       $17.99 monthly   next ~2026-10-04  PRICE CHANGE $15.49 -> $17.99 (since 2026-08-03)
  SPOTIFY USA       $11.99 monthly   next ~2026-10-06
Possible duplicate charges
  2026-07-11 & 2026-07-12  $42.10  AMAZON.COM*DUPLICATE
```
Also prints spending by month and category, and `--html` writes a standalone report (no JavaScript, dark-mode aware).

## What it does
- **Tolerant CSV loader:** header aliases, several date formats, `$1,234.50` / `(12.00)` amounts, separate debit/credit columns, Excel BOM, `--positive-is-spend` for card exports. **Money is integer cents**, never floats (a test shows why).
- **Merchant normalization:** `SQ *BLUE BOTTLE COFFEE`, `PAYPAL *SPOTIFY 402-935-7733`, `STARBUCKS #8821 SAN JOSE CA` → stable merchant keys, so different stores group together.
- **Subscription detection:** needs ≥3 charges, regular weekly/monthly/quarterly/yearly gaps, and stable consecutive amounts, so groceries and coffee don't qualify. A price hike doesn't hide a subscription; it's flagged instead.
- **Duplicate-charge finder** and **custom categories** (`--categories my.json`, `{"Dining": ["taqueria", ...]}`).

## Testing
42 tests: parsing edge cases, normalization table, subscription true/false positives, cadence math, report output, HTML escaping of user-supplied text, and an end-to-end run on the sample data.

## Limits
Category rules are keyword-based and tuned for common US merchants; unknown merchants land in "Uncategorized" (extend with `--categories`). Tested on generated data, not real statements. Don't commit your own statements: `.gitignore` excludes `examples/report.html`, and you should keep personal CSVs outside the repo.
