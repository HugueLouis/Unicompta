import csv
import datetime
import difflib
import io
import re
import unicodedata
from lib.gnucash_utils import list_transactions
from decimal import Decimal, InvalidOperation

# list_transactions, transaction_date, etc. come from your helper file

_BANK_NOISE = re.compile(
    r"\b(credit|debit|crédit|débit|de|a|à|paiement|international|sepa|payment)\b"
)


# ---------------------------------------------------------------- CSV parsing

def _read_text(path):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unable to decode CSV")


def _to_decimal(s):
    s = (s or "").strip().replace(" ", "").replace("'", "")
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def read_bank_csv(path):
    """
    Parse a PostFinance export. Skips the preamble lines and returns a list of
    {"date": date, "description": str, "amount": Decimal} where the amount is
    signed from the bank account's point of view (credit > 0, debit < 0).
    """
    lines = _read_text(path).splitlines()
    header_idx = next(i for i, line in enumerate(lines) if line.startswith("Date;"))

    rows = []
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])), delimiter=";")
    for r in reader:
        if not (r.get("Date") or "").strip():
            continue
        credit = _to_decimal(r.get("Credit in CHF"))
        debit = _to_decimal(r.get("Debit in CHF"))
        if credit is not None:
            amount = abs(credit)
        elif debit is not None:
            amount = -abs(debit)
        else:
            continue
        rows.append({
            "date": datetime.datetime.strptime(r["Date"].strip(), "%d.%m.%Y").date(),
            "description": (r.get("Notification text") or "").strip().strip('"'),
            "amount": amount,
        })
    return rows


# ---------------------------------------------------------------- matching helpers

def _normalize(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = text.lower()
    text = _BANK_NOISE.sub(" ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _similarity(a, b):
    """0..1 description similarity, used only as a tie-breaker."""
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def match_csv_to_gnucash(csv_path, book, account,  start_date, end_date):#TODO date
    """
    Returns a dict:
        mapped:  list of {"bank": row, "gnucash": tx_info, "day_diff": int, "similarity": float}
        missing: bank rows with no GnuCash counterpart
        extra:   GnuCash transactions (on `account`) with no bank counterpart
    A match requires the exact same signed amount.
    Each transaction is matched at most once. Closest date wins first, then
    the most similar description.
    """
    bank_rows = read_bank_csv(csv_path)
    if not bank_rows:
        return {"mapped": [], "missing": [], "extra": []}
    
    gnc_txs = list_transactions(account, start_date, end_date,False,filter_by_end_date=False)

    # Build all valid candidate pairs
    candidates = []
    for i, b in enumerate(bank_rows):
        if b["date"]<start_date:continue
        for j, g in enumerate(gnc_txs):
            if b["amount"] != g.get("amount"):
                continue
            day_diff = abs((b["date"] - g["date"]).days)
            sim = _similarity(b["description"], g["description"])
            candidates.append((day_diff, -sim, i, j))

    # Greedy one-to-one assignment: best candidates first
    candidates.sort()
    used_bank, used_gnc = set(), set()
    mapped = []
    for day_diff, neg_sim, i, j in candidates:
        if i in used_bank or j in used_gnc:
            continue
        used_bank.add(i)
        used_gnc.add(j)
        mapped.append({
            "bank": bank_rows[i],
            "gnucash": gnc_txs[j],
            "day_diff": day_diff,
            "similarity": -neg_sim,
        })

    missing = [b for i, b in enumerate(bank_rows) if i not in used_bank and b["date"]>start_date]
    extra = [g for j, g in enumerate(gnc_txs) if j not in used_gnc]
    
    missing.sort(key=lambda m: m["date"], reverse=True)
    extra.sort(key=lambda m: m["date"], reverse=True)
    mapped.sort(key=lambda m: m["bank"]["date"], reverse=True)

    return {"mapped": mapped, "missing": missing, "extra": extra}


# ---------------------------------------------------------------- display helpers

DATE_W = 10    # e.g. 2024-01-15
AMOUNT_W = 8  # e.g. -1234.56
DESC_W = 57

def _fit(text, width):
    """Flatten to one line and truncate with '...' so the field never exceeds width."""
    text = "" if text is None else str(text)
    text = " ".join(text.split())  # remove newlines and repeated whitespace
    if len(text) > width:
        text = text[:width - 3] + "..."
    return text


def _format_row(date, amount, description):
    d = _fit(date, DATE_W).ljust(DATE_W)
    a = _fit(f"{amount:.2f}", AMOUNT_W).ljust(AMOUNT_W)
    desc = _fit(description, DESC_W).ljust(DESC_W)
    return f"{d}| {a} | {desc}"


def format_bank_row(b):
    return _format_row(b["date"], b["amount"], b["description"])


def format_gnc_row(g):
    return _format_row(g["date"], g["amount"], g["description"])


def your_matching_function(csv_path, book, account,start_date, end_date):
    """Convenience wrapper returning display strings for the listboxes."""
    result = match_csv_to_gnucash(csv_path, book, account, start_date, end_date)
    missing = [format_bank_row(b) for b in result["missing"]]
    extra = [format_gnc_row(g) for g in result["extra"]]
    return missing, extra, result["mapped"]