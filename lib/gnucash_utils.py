"""
Pure-Python GnuCash XML backend (no `gnucash` bindings needed).
Requires:  pip install lxml
Reads plain or gzip-compressed .gnucash XML files, always saves uncompressed
(better git diffs).  Same public function names as the previous version.
"""
import datetime
import gzip
import os
import uuid
from decimal import Decimal

from lxml import etree

NS = {
    "gnc": "http://www.gnucash.org/XML/gnc",
    "act": "http://www.gnucash.org/XML/act",
    "trn": "http://www.gnucash.org/XML/trn",
    "split": "http://www.gnucash.org/XML/split",
    "ts": "http://www.gnucash.org/XML/ts",
    "cmdty": "http://www.gnucash.org/XML/cmdty",
    "cd": "http://www.gnucash.org/XML/cd",
}


def _q(tag):
    prefix, name = tag.split(":")
    return "{%s}%s" % (NS[prefix], name)


def _sub(parent, tag, text=None, **attrs):
    e = etree.SubElement(parent, _q(tag), **attrs)
    if text is not None:
        e.text = text
    return e


def _to_decimal(frac):
    num, _, den = (frac or "0/1").partition("/")
    return Decimal(num) / Decimal(den or 1)


def _to_frac(d):
    return f"{int((Decimal(d) * 100).to_integral_value())}/100"


def _now_ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")


def _date_ts(d):
    return f"{d.isoformat()} 10:59:00 +0000"   # same convention as GnuCash


def _parse_ts(text):
    return datetime.date.fromisoformat(text.strip()[:10])


# ── Data model ────────────────────────────────────────────────────────────────

class Account:
    def __init__(self, el):
        self.el = el
        self.guid = el.findtext("act:id", namespaces=NS)
        self.name = el.findtext("act:name", default="", namespaces=NS)
        self.type = el.findtext("act:type", default="", namespaces=NS)
        self.parent_guid = el.findtext("act:parent", namespaces=NS)
        self.children = []
        self.splits = []

    def GetName(self):
        return self.name

    def get_children(self):
        return list(self.children)

    def GetSplitList(self):
        return list(self.splits)


class Split:
    def __init__(self, el, book, tx):
        self.el = el
        self.tx = tx
        self.account = book.accounts[el.findtext("split:account", namespaces=NS)]
        self.value = _to_decimal(el.findtext("split:value", namespaces=NS))
        self.amount = _to_decimal(el.findtext("split:quantity", namespaces=NS))
        self.memo = el.findtext("split:memo", default="", namespaces=NS)
        self.account.splits.append(self)


class Transaction:
    def __init__(self, el, book):
        self.el = el
        self.book = book
        self.guid = el.findtext("trn:id", namespaces=NS)
        self.description = el.findtext("trn:description", default="", namespaces=NS)
        self.num = el.findtext("trn:num", default="", namespaces=NS)
        self.currency = el.findtext("trn:currency/cmdty:id", default="CHF", namespaces=NS)
        self.date = _parse_ts(el.findtext("trn:date-posted/ts:date", namespaces=NS))
        self.splits = [Split(s, book, self) for s in el.findall("trn:splits/trn:split", NS)]


class Book:
    def __init__(self, root):
        self.root = root
        self.el = root.find("gnc:book", NS)
        self.accounts = {}
        for el in self.el.findall("gnc:account", NS):   # direct children only (skips templates)
            a = Account(el)
            self.accounts[a.guid] = a
        for a in self.accounts.values():
            parent = self.accounts.get(a.parent_guid)
            if parent:
                parent.children.append(a)
        self.transactions = [Transaction(el, self) for el in self.el.findall("gnc:transaction", NS)]

    def get_root_account(self):
        return next(a for a in self.accounts.values() if a.type == "ROOT")

    def add_multi_transaction(self, legs, description, date, guid=None):
        """legs = [(account, value), ...]; the values must sum to 0."""
        if sum(v for _, v in legs) != 0:
            raise ValueError("unbalanced transaction: " + description)
        tx = _sub(self.el, "gnc:transaction", version="2.0.0")
        _sub(tx, "trn:id", guid or uuid.uuid4().hex, type="guid")
        cur = _sub(tx, "trn:currency")
        _sub(cur, "cmdty:space", "CURRENCY")
        _sub(cur, "cmdty:id", "CHF")
        _sub(_sub(tx, "trn:date-posted"), "ts:date", _date_ts(date))
        _sub(_sub(tx, "trn:date-entered"), "ts:date", _now_ts())
        _sub(tx, "trn:description", description)
        splits = _sub(tx, "trn:splits")
        for acc, val in legs:
            s = _sub(splits, "trn:split")
            _sub(s, "split:id", uuid.uuid4().hex, type="guid")
            _sub(s, "split:reconciled-state", "n")
            _sub(s, "split:value", _to_frac(val))
            _sub(s, "split:quantity", _to_frac(val))
            _sub(s, "split:account", acc.guid, type="guid")

        # place it after the last existing transaction (or last account), GnuCash-style indentation
        etree.indent(tx, space=" ", level=2)
        existing = self.el.findall("gnc:transaction", NS)
        last = next(e for e in reversed(existing) if e is not tx) if len(existing) > 1 \
            else self.el.findall("gnc:account", NS)[-1]
        self.el.insert(self.el.index(last) + 1, tx)
        tx.tail = last.tail or "\n "
        last.tail = "\n  "

        obj = Transaction(tx, self)
        self.transactions.append(obj)
        return obj

    def add_transaction(self, from_account, to_account, amount, description, date):
        return self.add_multi_transaction([(to_account, amount), (from_account, -amount)], description, date)

    def remove_transaction(self, tx):
        for s in tx.splits:
            s.account.splits.remove(s)
        self.transactions.remove(tx)
        prev = tx.el.getprevious()
        if prev is not None:
            prev.tail = tx.el.tail
        tx.el.getparent().remove(tx.el)


class Session:
    """Replacement for gnucash.Session. Pass the plain file path (no 'xml://')."""

    def __init__(self, path):
        self.path = path
        self.closed = False
        self.reload()

    def reload(self):
        """Re-read the file from disk (call after git pull / reset). Re-fetch your accounts afterwards."""
        with open(self.path, "rb") as f:
            raw = f.read()
        if raw[:2] == b"\x1f\x8b":                      # gzip magic bytes
            raw = gzip.decompress(raw)
        self.book = Book(etree.fromstring(raw))
        self.closed = False

    def save(self):
        if self.closed:
            return
        for cd in self.book.el.xpath('gnc:count-data[@cd:type="transaction"]', namespaces=NS):
            cd.text = str(len(self.book.transactions))
        data = (b'<?xml version="1.0" encoding="utf-8" ?>\n'
                + etree.tostring(self.book.root, encoding="utf-8") + b"\n")
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, self.path)

    def end(self):
        self.closed = True   # later save() calls become no-ops (avoids overwriting a pulled file)


# ── Public helpers (same names as before) ─────────────────────────────────────

def print_all_accounts(account, max, indent=0):
    print("  " * indent + f"{indent} : " + account.GetName())
    if indent >= max:
        return
    for child in account.get_children():
        print_all_accounts(child, max, indent + 1)


def list_all_accounts_accumulate(account, prefix=""):
    """Return a list of all sub account names."""
    names = [account.GetName()]
    for child in account.get_children():
        names.extend(list_all_accounts_accumulate(child))
    return names


def find_account_including(root, substring, children=False):
    """Do not use children=True. Returns the first account whose name contains substring."""
    if substring in root.GetName():
        return root
    for child in root.get_children():
        result = find_account_including(child, substring, True)
        if result:
            return result
    if not children:
        raise Exception(f"oh ohh a tech bro stole your {substring} account")
    return None


def add_transaction(book, from_account, to_account, amount_decimal, description, date=None) -> Transaction:
    """Add a transaction (to_account gets +amount, from_account -amount). Call session.save() afterwards."""
    if date is None:
        date = datetime.date.today()
    return book.add_transaction(from_account, to_account, Decimal(amount_decimal), description, date)


def add_multi_transaction(book, splits, description, date=None) -> Transaction:
    """Several splits in one transaction: splits = [(account, value), ...], values sum to 0."""
    if date is None:
        date = datetime.date.today()
    return book.add_multi_transaction([(a, Decimal(v)) for a, v in splits], description, date)


def delete_transaction(tx=None):
    tx.book.remove_transaction(tx)


def set_transaction_date(tx, d: datetime.date):
    tx.el.find("trn:date-posted/ts:date", NS).text = _date_ts(d)
    tx.date = d


def _parse_date(d):
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date type: {type(d)}")


def transaction_date(tx) -> datetime.date:
    return tx.date


def get_split_amount(split) -> Decimal:
    return split.amount


def get_split_value(split) -> Decimal:
    return split.value


def get_all_subaccounts(account):
    subs = []
    for child in account.get_children():
        subs.append(child)
        subs.extend(get_all_subaccounts(child))
    return subs


def get_transaction_info(tx, account=None) -> dict:
    info = {
        "date": tx.date,
        "description": tx.description,
        "num": tx.num,
        "currency": tx.currency,
        "splits": [{"account": s.account.GetName(), "amount": s.amount,
                    "value": s.value, "memo": s.memo} for s in tx.splits],
        "transaction": tx,
    }
    if account is not None:
        for s in tx.splits:
            if s.account is account:
                info["amount"] = s.amount
                break
    return info


def list_transactions(account, start_date, end_date, include_subaccounts=False, filter_by_end_date=True) -> list:
    start_date = _parse_date(start_date)
    end_date = _parse_date(end_date)
    accounts = [account] + (get_all_subaccounts(account) if include_subaccounts else [])

    seen, results = set(), []
    for acc in accounts:
        for split in acc.GetSplitList():
            tx = split.tx
            if tx.guid in seen:
                continue
            if start_date <= tx.date and (not filter_by_end_date or tx.date <= end_date):
                seen.add(tx.guid)
                results.append(get_transaction_info(tx, acc))
    results.sort(key=lambda d: d["date"])
    return results


def print_transactions(transactions):
    for t in transactions:
        amt = t.get("amount")
        amt_str = f"{amt:.2f}" if amt is not None else ""
        print(f"{t['date']} | {amt_str:>10} | {t['description']}")