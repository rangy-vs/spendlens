"""Turn noisy bank descriptions into a stable merchant key and a category."""
from __future__ import annotations

import json
import re
from pathlib import Path

PREFIXES = re.compile(r"^(sq\s*\*|tst\s*\*|pp\s*\*|paypal\s*\*|pos\s+(debit|purchase)\s*|purchase\s+authorized\s+on\s+\S+\s*|"
                      r"debit\s+card\s+purchase\s*|checkcard\s*\d*\s*|recurring\s+payment\s*)", re.I)
NOISE = [
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), " "),     # phone numbers
    (re.compile(r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b"), " "),         # embedded dates
    (re.compile(r"[#*]\s*\d+"), " "),                              # store / ref numbers
    (re.compile(r"\b\d{4,}\b"), " "),                              # long digit runs
    (re.compile(r"\b[A-Z]{2}\s*$"), " "),                          # trailing state code
    (re.compile(r"\b(www\.|https?://)", re.I), ""),
]

DEFAULT_CATEGORIES = {
    "Groceries": ["safeway", "trader joe", "whole foods", "costco", "grocery", "aldi", "kroger", "ralphs"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "chipotle", "mcdonald", "pizza", "taco", "doordash",
               "uber eats", "ubereats", "grubhub", "boba", "burger", "sushi", "peet"],
    "Transport": ["uber", "lyft", "shell", "chevron", "arco", "bart", "metro", "clipper", "parking", "gas"],
    "Subscriptions": ["netflix", "spotify", "hulu", "disney", "youtube", "apple.com/bill", "icloud", "adobe",
                      "github", "openai", "chatgpt", "claude", "notion", "dropbox", "amazon prime", "prime video", "hbo", "max.com"],
    "Shopping": ["amazon", "target", "walmart", "best buy", "ikea", "etsy", "ebay"],
    "Bills & Utilities": ["pg&e", "pge", "comcast", "xfinity", "verizon", "t-mobile", "at&t", "water", "electric", "internet"],
    "Health": ["pharmacy", "cvs", "walgreens", "clinic", "dental", "gym", "fitness"],
    "Entertainment": ["cinema", "amc", "steam", "playstation", "xbox", "ticketmaster", "concert"],
    "Education": ["bookstore", "tuition", "coursera", "udemy", "textbook", "chegg"],
    "Income": ["payroll", "direct dep", "deposit", "paycheck", "venmo cashout", "zelle from", "refund"],
}


def normalize_merchant(desc: str) -> str:
    s = desc.strip()
    s = PREFIXES.sub("", s)
    s = re.split(r"#\s*\d+", s)[0]                 # text after a store number is usually the city
    s = re.sub(r"\s*\*\s*\S*", "", s)               # "AMAZON.COM*2K4LL1" / "UBER *TRIP": drop reference codes
    for pat, repl in NOISE:
        s = pat.sub(repl, s)
    s = re.sub(r"[^A-Za-z0-9&.' /-]", " ", s)
    words = [w for w in s.upper().split() if w not in {"THE", "INC", "LLC", "CO", "COM"} or "." in w]
    return " ".join(words[:3]).strip() or desc.strip().upper()[:24]


def load_categories(path: str | Path | None = None) -> dict[str, list[str]]:
    if path:
        return json.loads(Path(path).read_text())
    return DEFAULT_CATEGORIES


def categorize(desc: str, cents: int, cats: dict[str, list[str]] | None = None) -> str:
    cats = cats or DEFAULT_CATEGORIES
    d = desc.lower()
    if cents > 0:
        return "Income" if any(k in d for k in cats.get("Income", [])) else "Refund/Other credit"
    for name, keys in cats.items():
        if name != "Income" and any(k in d for k in keys):
            return name
    return "Uncategorized"
