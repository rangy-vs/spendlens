"""Generate a FICTIONAL 6-month statement for demos (seeded, no real data)."""
import csv
import random
from datetime import date, timedelta

random.seed(7)
rows = []
start = date(2026, 4, 1)
for m in range(6):
    y, mo = divmod(start.month - 1 + m, 12)
    base = date(start.year + y, mo + 1, 1)
    rows.append((base + timedelta(days=0), "ACME CORP PAYROLL DIRECT DEP", 2400.00))
    rows.append((base + timedelta(days=2), "NETFLIX.COM 866-579-7172 CA", -15.49 if m < 4 else -17.99))   # price hike
    rows.append((base + timedelta(days=4), "SPOTIFY USA", -11.99))
    rows.append((base + timedelta(days=9), "PLANET FITNESS #1234", -24.99))
    rows.append((base + timedelta(days=14), "COMCAST XFINITY 800-934-6489", -64.99))
    for _ in range(random.randint(5, 8)):
        rows.append((base + timedelta(days=random.randint(0, 27)), random.choice(
            ["TRADER JOE'S #123 SAN JOSE CA", "SAFEWAY STORE 0412", "STARBUCKS #8821", "CHIPOTLE 1523", "SQ *BLUE BOTTLE COFFEE",
             "UBER *TRIP", "SHELL OIL 57444", "AMAZON.COM*2K4LL1"]), -round(random.uniform(4, 70), 2)))
rows.append((date(2026, 7, 11), "AMAZON.COM*DUPLICATE", -42.10))
rows.append((date(2026, 7, 12), "AMAZON.COM*DUPLICATE", -42.10))                  # planted double charge
rows.append((date(2026, 5, 3), "UNIV BOOKSTORE TEXTBOOK", -118.35))
rows.sort()
with open("examples/sample_statement.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Date", "Description", "Amount"])
    for d, desc, amt in rows: w.writerow([d.strftime("%m/%d/%Y"), desc, f"{amt:.2f}"])
print(len(rows), "rows")
