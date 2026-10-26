"""Data normalization utilities for financial amounts, dates, and currencies."""

import re
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "MXN": "MXN",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "CAD": "CAD",
    "COP": "COP",
    "CLP": "CLP",
    "BRL": "BRL",
}


def detect_currency(raw_text: str) -> str:
    """Detect monetary currency from raw text or symbol."""
    if not raw_text:
        return "USD"

    upper = raw_text.upper()
    for code in ["USD", "EUR", "MXN", "GBP", "CAD", "COP", "CLP", "BRL"]:
        if code in upper:
            return code

    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in raw_text:
            return code

    return "USD"


def normalize_amount(raw_val: Any) -> tuple[float | None, bool, str]:
    """Parse raw financial string into (absolute_amount, is_negative, currency).

    Handles:
    - Standard US format: 1,234.56
    - European format: 1.234,56
    - Accounting parentheses: (1,234.50) -> negative
    - Explicit signs: +500.00 / -500.00
    - Text qualifiers: 100.00 CR / 100.00 DR
    - Currencies: $1,234.56, 1200.00 EUR
    """
    if raw_val is None:
        return None, False, "USD"

    val_str = str(raw_val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null", "-", ""]:
        return None, False, "USD"

    # Detect currency
    currency = detect_currency(val_str)

    # Detect negative indicator
    is_negative = False
    upper = val_str.upper()

    # Accounting parentheses check: e.g. (1,234.50) or ( 50.00 )
    if re.search(r"^\s*\(.+\)\s*$", val_str):
        is_negative = True
    elif "-" in val_str or "DR" in upper or "CARGO" in upper or "DEBIT" in upper:
        is_negative = True

    # Strip currency symbols, letters, parenthetical wrappers, and spaces
    clean = re.sub(r"[^\d,\.\-\+]", "", val_str).strip()
    clean = clean.replace("+", "").replace("-", "")

    if not clean:
        return None, False, currency

    # Handle thousands vs decimal separators
    if "," in clean and "." in clean:
        first_comma = clean.find(",")
        first_dot = clean.find(".")
        if first_comma < first_dot:
            # Format: 1,234,567.89 -> Comma is thousands, dot is decimal
            clean = clean.replace(",", "")
        else:
            # Format: 1.234.567,89 -> Dot is thousands, comma is decimal
            clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        parts = clean.split(",")
        if len(parts) == 2 and len(parts[1]) in [1, 2]:
            # Format: 1234,50 or 1234,5 -> comma is decimal
            clean = clean.replace(",", ".")
        elif len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            # Format: 1,000 or 1,234,000 -> comma is thousands
            clean = clean.replace(",", "")
        else:
            # Fallback assume decimal
            clean = clean.replace(",", ".")
    elif "." in clean:
        parts = clean.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0):
            # European thousands separator without decimals: 1.000 or 12.500
            # If parts[1] is 3 digits and parts[0] is not 0, check if integer
            clean = clean.replace(".", "")

    try:
        amount = round(abs(float(clean)), 2)
        return amount, is_negative, currency
    except ValueError:
        return None, False, currency


# Spanish month name replacements for dateutil compatibility
SPANISH_MONTHS = {
    "ENE": "JAN",
    "FEB": "FEB",
    "MAR": "MAR",
    "ABR": "APR",
    "MAY": "MAY",
    "JUN": "JUN",
    "JUL": "JUL",
    "AGO": "AUG",
    "SEP": "SEP",
    "OCT": "OCT",
    "NOV": "NOV",
    "DIC": "DEC",
}


def normalize_date(raw_date: Any) -> str | None:
    """Parse raw date representations into standard ISO 8601 (YYYY-MM-DD).

    Supports:
    - ISO formats: YYYY-MM-DD, YYYY/MM/DD
    - European formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    - Named months: 15-Ene-2024, 15-Jan-2024
    - Timestamps: 2024-05-12 14:22:00
    """
    if raw_date is None:
        return None

    date_str = str(raw_date).strip()
    if not date_str or date_str.lower() in ["nan", "none", "null", "-"]:
        return None

    # Fast match: already ISO YYYY-MM-DD
    iso_match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", date_str)
    if iso_match:
        year, month, day = iso_match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Replace Spanish month abbreviations if present
    processed_date = date_str
    for es_month, en_month in SPANISH_MONTHS.items():
        processed_date = re.sub(rf"\b{es_month}\b", en_month, processed_date, flags=re.IGNORECASE)

    # Try common European / Latam formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    dmy_match = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", processed_date)
    if dmy_match:
        d1, d2, yr = dmy_match.groups()
        if len(yr) == 2:
            yr = f"20{yr}"
        # Bank statements are typically day-first in Latam/EU
        day, month, year = int(d1), int(d2), int(yr)
        if day > 12 and month <= 12:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                pass
        elif month > 12 and day <= 12:
            # Swapped MM/DD/YYYY
            try:
                return datetime(year, day, month).strftime("%Y-%m-%d")
            except ValueError:
                pass
        else:
            # Default to day-first for banking
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Fallback to dateutil parser
    try:
        parsed = date_parser.parse(processed_date, dayfirst=True)
        return parsed.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None
