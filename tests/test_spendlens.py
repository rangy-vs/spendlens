from datetime import date, timedelta
from pathlib import Path

import pytest

from spendlens.analyze import by_category, by_month, find_duplicates, find_subscriptions, money
from spendlens.loader import LoadError, Txn, load_csv, parse_cents, parse_date
from spendlens.merchants import categorize, normalize_merchant
from spendlens.report import html_report, text_report


# ---------- loader ----------
@pytest.mark.parametrize("raw,cents", [
    ("12.34", 1234), ("-12.34", -1234), ("$1,234.50", 123450), ("(12.00)", -1200), ("12.3", 1230),
    ("5", 500), ("0.07", 7), ("", None), ("abc", None), ("12.00-", -1200),
])
def test_parse_cents_exact_integer_math(raw, cents):
    assert parse_cents(raw) == cents


def test_no_float_rounding_drift():
    assert sum(parse_cents("0.10") for _ in range(10)) == 100        # floats give 0.9999999999999999


@pytest.mark.parametrize("raw,d", [("2026-07-04", date(2026, 7, 4)), ("07/04/2026", date(2026, 7, 4)),
                                   ("7/4/26", date(2026, 7, 4)), ("Jul 04, 2026", date(2026, 7, 4))])
def test_parse_date_formats(raw, d):
    assert parse_date(raw) == d


def write(tmp_path, text, name="t.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8-sig")        # also exercises the Excel BOM
    return p


def test_load_signed_amount_column(tmp_path):
    p = write(tmp_path, "Date,Description,Amount\n07/01/2026,COFFEE,-4.50\n07/02/2026,PAYROLL,1000.00\n")
    t = load_csv(p)
    assert [x.cents for x in t] == [-450, 100000] and t[0].day == date(2026, 7, 1)


def test_load_debit_credit_columns(tmp_path):
    p = write(tmp_path, "Posted Date,Payee,Debit,Credit\n2026-07-01,STORE,12.00,\n2026-07-02,PAY,,500.00\n")
    assert [x.cents for x in load_csv(p)] == [-1200, 50000]


def test_positive_is_spend_flag(tmp_path):
    p = write(tmp_path, "Date,Description,Amount\n07/01/2026,STORE,12.00\n")
    assert load_csv(p, positive_is_spend=True)[0].cents == -1200


def test_load_errors_are_helpful(tmp_path):
    with pytest.raises(LoadError, match="columns"):
        load_csv(write(tmp_path, "a,b\n1,2\n"))
    with pytest.raises(LoadError, match="row 2"):
        load_csv(write(tmp_path, "Date,Description,Amount\nnot-a-date,X,1\n"))


def test_blank_amounts_skipped(tmp_path):
    p = write(tmp_path, "Date,Description,Amount\n07/01/2026,PENDING,\n07/02/2026,X,-1.00\n")
    assert len(load_csv(p)) == 1


# ---------- merchants ----------
@pytest.mark.parametrize("raw,expected", [
    ("NETFLIX.COM 866-579-7172 CA", "NETFLIX.COM"),
    ("AMAZON.COM*2K4LL1", "AMAZON.COM"),
    ("UBER *TRIP", "UBER"),
    ("TRADER JOE'S #123 SAN JOSE CA", "TRADER JOE'S"),
    ("SQ *BLUE BOTTLE COFFEE", "BLUE BOTTLE COFFEE"),
    ("PAYPAL *SPOTIFY 402-935-7733", "SPOTIFY"),
    ("PLANET FITNESS #1234", "PLANET FITNESS"),
])
def test_normalize_merchant(raw, expected):
    assert normalize_merchant(raw) == expected


def test_same_merchant_different_stores_group_together():
    assert normalize_merchant("STARBUCKS #8821 SAN JOSE CA") == normalize_merchant("STARBUCKS #1234 PALO ALTO CA")


def test_categorize():
    assert categorize("STARBUCKS #1", -500) == "Dining"
    assert categorize("ACME PAYROLL", 100000) == "Income"
    assert categorize("RANDOM THING", -500) == "Uncategorized"
    assert categorize("RETURN", 500) == "Refund/Other credit"


# ---------- subscriptions ----------
def series(desc, start, cents, n, gap=30):
    return [Txn(start + timedelta(days=gap * i), desc, -cents) for i in range(n)]


def test_detects_monthly_subscription():
    subs = find_subscriptions(series("SPOTIFY USA", date(2026, 1, 3), 1199, 6))
    assert len(subs) == 1 and subs[0].cadence == "monthly" and subs[0].monthly_cents == 1199
    assert subs[0].next_expected == date(2026, 1, 3) + timedelta(days=30 * 5 + 30)


def test_price_hike_is_flagged_and_still_detected():
    t = series("NETFLIX.COM", date(2026, 1, 2), 1549, 4) + series("NETFLIX.COM", date(2026, 5, 2), 1799, 2)
    s = find_subscriptions(t)[0]
    assert s.price_change[:2] == (1549, 1799) and s.typical_cents == 1799      # reports CURRENT price


def test_irregular_grocery_spend_is_not_a_subscription():
    t = [Txn(date(2026, 1, 1) + timedelta(days=d), "SAFEWAY #1", -a) for d, a in
         [(0, 5230), (9, 1875), (15, 8844), (31, 2210), (40, 6590)]]
    assert find_subscriptions(t) == []


def test_needs_three_charges():
    assert find_subscriptions(series("X", date(2026, 1, 1), 999, 2)) == []


def test_weekly_and_yearly_cadences():
    w = find_subscriptions(series("WEEKLY BOX", date(2026, 1, 1), 1000, 5, gap=7))[0]
    y = find_subscriptions(series("ANNUAL PLAN", date(2023, 1, 1), 12000, 3, gap=365))[0]
    assert w.cadence == "weekly" and 4300 < w.monthly_cents < 4400             # 10.00 * 52/12
    assert y.cadence == "yearly" and y.monthly_cents == 1000


def test_income_is_never_a_subscription():
    t = [Txn(date(2026, 1, 1) + timedelta(days=30 * i), "PAYROLL", 240000) for i in range(6)]
    assert find_subscriptions(t) == []


# ---------- duplicates / aggregates ----------
def test_duplicate_charge_detection():
    t = [Txn(date(2026, 7, 11), "AMAZON.COM*AB", -4210), Txn(date(2026, 7, 12), "AMAZON.COM*CD", -4210),
         Txn(date(2026, 7, 20), "AMAZON.COM*EF", -4210)]
    d = find_duplicates(t)
    assert len(d) == 1 and d[0][0].day == date(2026, 7, 11)


def test_monthly_and_category_totals():
    t = [Txn(date(2026, 1, 5), "STARBUCKS", -500), Txn(date(2026, 1, 9), "SAFEWAY", -2500),
         Txn(date(2026, 2, 1), "STARBUCKS", -700), Txn(date(2026, 2, 2), "PAYROLL", 100000)]
    assert by_month(t) == {"2026-01": 3000, "2026-02": 700}
    assert by_category(t) == {"Groceries": 2500, "Dining": 1200}


def test_money_format():
    assert money(123456) == "$1,234.56" and money(5) == "$0.05"


# ---------- reports / CLI ----------
SAMPLE = Path("examples/sample_statement.csv")


def test_sample_end_to_end():
    txns = load_csv(SAMPLE)
    out = text_report(txns)
    assert "NETFLIX.COM" in out and "PRICE CHANGE $15.49 -> $17.99" in out
    assert "Possible duplicate charges" in out and "COMCAST XFINITY" in out


def test_html_escapes_user_supplied_category_names():
    """Category names come from a user JSON file and are rendered into HTML, so they must be escaped."""
    evil = "<img src=x onerror=alert(1)>"
    t = [Txn(date(2026, 1, 1), "ACME STORE", -500)]
    html = html_report(t, cats={evil: ["acme"]})
    assert evil not in html and "&lt;img src=x onerror=alert(1)&gt;" in html


def test_merchant_markup_is_neutralised():
    t = series("<script>alert(1)</script>", date(2026, 1, 1), 999, 4)
    assert "<script>alert" not in html_report(t)


def test_cli(tmp_path):
    from spendlens.__main__ import main
    out = tmp_path / "r.html"
    assert main([str(SAMPLE), "--html", str(out)]) == 0 and out.read_text().startswith("<!doctype html>")
    assert main(["does_not_exist.csv"]) == 1
