import piecash
from piecash import Transaction, Split, Price
from decimal import Decimal
from datetime import date, datetime
from typing import Optional


def open_book(filepath: str, readonly: bool = False) -> piecash.Book:
    """
    Open a GnuCash SQLite file.

    Args:
        filepath:  Path to the .gnucash file.
        readonly:  True to open without write access (safe for inspection).

    Returns:
        A piecash.Book context manager — use with `with` or close manually.

    Example:
        book = open_book("personal.gnucash")
        # ... do work ...
        book.save()
        book.close()

        # Or as a context manager (auto-saves on exit):
        with open_book("personal.gnucash") as book:
            ...
    """
    return piecash.open_book(filepath, readonly=readonly, open_if_lock=True)

# ─────────────────────────────────────────────
# 2. ACCOUNT HELPERS
# ─────────────────────────────────────────────

def get_account(book: piecash.Book, full_name: str) -> piecash.Account:
    """
    Retrieve an account by its full colon-separated path.

    Args:
        book:       Open GnuCash book.
        full_name:  E.g. "Assets:Current Assets:Checking Account".

    Returns:
        piecash.Account

    Raises:
        KeyError if account is not found.

    Example:
        checking = get_account(book, "Assets:Current Assets:Checking")
    """
    return book.accounts.get(fullname=full_name)


def list_accounts(book: piecash.Book, account_type: Optional[str] = None) -> list:
    """
    List all accounts, optionally filtered by type.

    Args:
        book:         Open GnuCash book.
        account_type: One of: "ASSET", "LIABILITY", "INCOME", "EXPENSE",
                      "EQUITY", "BANK", "CREDIT", "CASH", etc.
                      Pass None to list everything.

    Returns:
        List of (fullname, type, commodity) tuples.

    Example:
        for name, atype, curr in list_accounts(book, "EXPENSE"):
            print(name)
    """
    accounts = book.accounts
    result = []
    for acc in accounts:
        if account_type is None or acc.type.upper() == account_type.upper():
            result.append((acc.fullname, acc.type, acc.commodity.mnemonic))
    return sorted(result, key=lambda x: x[0])

def add_transaction(
    book: piecash.Book,
    description: str,
    post_date: date,
    amount: float,
    from_account_fullname: str,
    to_account_fullname: str,
    currency_code: str = "USD",
    num: str = "",
    notes: str = "",
) -> Transaction:
    """
    Add a simple two-split transaction (debit/credit pair).

    Args:
        book:                  Open GnuCash book (writable).
        description:           Memo / payee description shown in the register.
        post_date:             Transaction date as datetime.date.
        amount:                Positive amount (e.g. 49.99).
        from_account_fullname: Account money comes FROM (e.g. checking).
        to_account_fullname:   Account money goes TO (e.g. an expense).
        currency_code:         ISO 4217 code (must match both accounts).
        num:                   Optional cheque / reference number.
        notes:                 Optional transaction notes.

    Returns:
        The created piecash.Transaction.

    Example:
        add_transaction(
            book,
            description="Migros groceries",
            post_date=date(2024, 5, 3),
            amount=87.50,
            from_account_fullname="Assets:Bank:Checking",
            to_account_fullname="Expenses:Food:Groceries",
        )
        book.save()
    """
    commodity = book.commodities.get(mnemonic=currency_code)
    from_acc = get_account(book, from_account_fullname)
    to_acc = get_account(book, to_account_fullname)
    amt = Decimal(str(amount))

    txn = Transaction(
        currency=commodity,
        description=description,
        post_date=post_date,
        enter_date=datetime.now(),
        num=num,
        notes=notes,
        splits=[
            Split(account=from_acc, value=-amt),   # money leaves
            Split(account=to_acc,   value=+amt),   # money arrives
        ],
    )
    return txn


def add_split_transaction(
    book: piecash.Book,
    description: str,
    post_date: date,
    splits: list[dict],
    currency_code: str = "USD",
    num: str = "",
    notes: str = "",
) -> Transaction:
    """
    Add a transaction with an arbitrary number of splits.
    The sum of all split values MUST be zero (GnuCash requirement).

    Args:
        book:          Open GnuCash book (writable).
        description:   Transaction description.
        post_date:     Transaction date.
        splits:        List of dicts with keys:
                         - "account": full account name (str)
                         - "value":   signed decimal amount (float)
                         - "memo":    optional per-split memo (str)
        currency_code: ISO 4217 code.
        num:           Optional reference number.
        notes:         Optional notes.

    Returns:
        The created piecash.Transaction.

    Example:
        # Pay a CHF 500 invoice split across two expense categories
        add_split_transaction(
            book,
            description="Office supplies invoice #1042",
            post_date=date(2024, 5, 10),
            currency_code="CHF",
            splits=[
                {"account": "Assets:Bank:UBS", "value": -500.00},
                {"account": "Expenses:Office:Stationery", "value": 320.00,
                 "memo": "Paper & pens"},
                {"account": "Expenses:Office:Equipment", "value": 180.00,
                 "memo": "USB hub"},
            ],
        )
        book.save()
    """
    commodity = book.commodities.get(mnemonic=currency_code)
    piecash_splits = []
    for s in splits:
        acc = get_account(book, s["account"])
        memo = s.get("memo", "")
        piecash_splits.append(
            Split(account=acc, value=Decimal(str(s["value"])), memo=memo)
        )

    total = sum(Decimal(str(s["value"])) for s in splits)
    if total != 0:
        raise ValueError(f"Split values must sum to zero; got {total}")

    txn = Transaction(
        currency=commodity,
        description=description,
        post_date=post_date,
        enter_date=datetime.now(),
        num=num,
        notes=notes,
        splits=piecash_splits,
    )
    return txn

# ─────────────────────────────────────────────
# 4. QUERY / REPORTING
# ─────────────────────────────────────────────

def get_account_balance(book: piecash.Book, full_name: str) -> Decimal:
    """
    Return the current balance of an account.

    Example:
        bal = get_account_balance(book, "Assets:Bank:Checking")
        print(f"Balance: {bal}")
    """
    acc = get_account(book, full_name)
    return acc.get_balance()


def get_transactions(
    book: piecash.Book,
    account_fullname: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[dict]:
    """
    Retrieve transactions for an account, optionally filtered by date range.

    Returns:
        List of dicts with keys: date, description, amount, splits.

    Example:
        txns = get_transactions(book, "Assets:Bank:Checking",
                                date(2024, 1, 1), date(2024, 12, 31))
        for t in txns:
            print(t["date"], t["description"], t["amount"])
    """
    acc = get_account(book, account_fullname)
    results = []
    for split in acc.splits:
        txn = split.transaction
        if start_date and txn.post_date < start_date:
            continue
        if end_date and txn.post_date > end_date:
            continue
        results.append({
            "date": txn.post_date,
            "description": txn.description,
            "num": txn.num,
            "amount": split.value,
            "currency": txn.currency.mnemonic,
            "splits": [
                {"account": s.account.fullname, "value": s.value, "memo": s.memo}
                for s in txn.splits
            ],
        })
    return sorted(results, key=lambda x: x["date"])


# ─────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    with open_book("personal.gnucash") as book:

        # --- Print all expense accounts ---
        print("=== Expense accounts ===")
        for name, atype, curr in list_accounts(book, "EXPENSE"):
            print(f"  {name} ({curr})")

        # --- Add a single transaction ---
        add_transaction(
            book,
            description="Migros weekly shop",
            post_date=date.today(),
            amount=123.45,
            from_account_fullname="Assets:Bank:Checking",
            to_account_fullname="Expenses:Food:Groceries",
            currency_code="CHF",
        )

        # --- Add a split transaction ---
        add_split_transaction(
            book,
            description="IKEA run",
            post_date=date.today(),
            currency_code="CHF",
            splits=[
                {"account": "Assets:Bank:Checking",    "value": -250.00},
                {"account": "Expenses:Home:Furniture", "value": 180.00, "memo": "Chair"},
                {"account": "Expenses:Home:Decor",     "value":  70.00, "memo": "Candles"},
            ],
        )

        book.save()
        print("\nSaved.")