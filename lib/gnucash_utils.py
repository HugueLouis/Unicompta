import gnucash
from gnucash import Session, Transaction, Split, GncNumeric
from gnucash.gnucash_core_c import ACCT_TYPE_ASSET, ACCT_TYPE_EXPENSE  # etc.
from decimal import Decimal
import datetime

def print_all_accounts(account,max, indent=0):
    print("  " * indent+ f"{indent} : " + account.GetName())
    if indent >= max :
        return
    else:
        for child in account.get_children():
            print_all_accounts(child, max, indent + 1)

def list_all_accounts_accumulate(account,prefix=""):
    """Return a list of all sub account names with their full path."""
    full_name =  account.GetName() #prefix + account.GetName()
    names = [full_name]
    for child in account.get_children():
        names.extend(list_all_accounts_accumulate(child)) #, full_name + " "))
    return names

def find_account_including(root, substring, children = False):
    """ Do not use children True
    Be carefull it only returns the first one found with the substring, or None if there aren't any"""
    if substring in root.GetName():
        return root
    for child in root.get_children():
        result = find_account_including(child, substring,True)
        if result:
            return result
    if not children : raise Exception(f"oh ohh a tech bro stole your {substring} account")
    else : return None

def add_transaction(book, from_account, to_account, amount_decimal, description, date=None) -> Transaction :
    """
    Adds a transaction to the book, do not forget to save the gnucash :)
    """
    if date is None:
        date = datetime.date.today()

    currency = book.get_table().lookup("ISO4217", "CHF")  # adapt to your currency

    tx = Transaction(book)
    tx.BeginEdit()

    tx.SetDate(date.day, date.month, date.year)
    tx.SetDescription(description)
    tx.SetCurrency(currency)

    # Helper: convert Decimal to GncNumeric (e.g. 12.50 → 1250/100)
    def to_gnc(d):
        cents = int(d * 100)
        return GncNumeric(cents, 100)

    # Debit split (money goes TO this account)
    split_to = Split(book)
    split_to.SetParent(tx)
    split_to.SetAccount(to_account)
    split_to.SetValue(to_gnc(amount_decimal))
    split_to.SetAmount(to_gnc(amount_decimal))

    # Credit split (money comes FROM this account)
    split_from = Split(book)
    split_from.SetParent(tx)
    split_from.SetAccount(from_account)
    split_from.SetValue(to_gnc(-amount_decimal))
    split_from.SetAmount(to_gnc(-amount_decimal))
    tx.CommitEdit()
    return tx


def delete_transaction(tx=None):
    """
    Delete a transaction from the book.
    """
    tx.BeginEdit()
    tx.Destroy()
    tx.CommitEdit()


def gnc_numeric_to_decimal(gnc_numeric: GncNumeric) -> Decimal:
    """Convert a GncNumeric (num/denom fraction) into a Decimal."""
    return Decimal(gnc_numeric.num()) / Decimal(gnc_numeric.denom())
 
 
def _parse_date(d):
    """Accept a datetime.date, datetime.datetime, or 'YYYY-MM-DD' string."""
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date type: {type(d)}")
 
 
def transaction_date(tx: Transaction) -> datetime.date:
    """Return the posted date of a transaction as a datetime.date.

    Depending on the gnucash python bindings version, tx.GetDate() may
    return either a Unix timestamp (int) or a datetime.datetime already.
    """
    raw = tx.GetDate()
    if isinstance(raw, datetime.datetime):
        return raw.date()
    if isinstance(raw, datetime.date):
        return raw
    return datetime.datetime.fromtimestamp(raw).date()
 
 
def get_split_amount(split: Split) -> Decimal:
    """Amount in the split's own account currency/commodity."""
    return gnc_numeric_to_decimal(split.GetAmount())
 
 
def get_split_value(split: Split) -> Decimal:
    """Value in the transaction's currency."""
    return gnc_numeric_to_decimal(split.GetValue())
 
 
def get_all_subaccounts(account):
    """Recursively collect all descendant accounts (not including `account` itself)."""
    subs = []
    for child in account.get_children():
        subs.append(child)
        subs.extend(get_all_subaccounts(child))
    return subs
 
 
def get_transaction_info(tx: Transaction, account=None) -> dict:
    """
    Extract the useful info from a transaction.
 
    Returns a dict with:
        date, description, num, currency, splits (list of per-split dicts),
        and, if `account` is given, 'amount' = the signed amount for that account.
    """
    info = {
        "date": transaction_date(tx),
        "description": tx.GetDescription(),
        "num": tx.GetNum(),
        "currency": tx.GetCurrency().get_mnemonic(),
        "splits": [],
    }
 
    for split in tx.GetSplitList():
        split_account = split.GetAccount()
        info["splits"].append({
            "account": split_account.GetName(),
            "amount": get_split_amount(split),
            "value": get_split_value(split),
            "memo": split.GetMemo(),
        })
 
    if account is not None:
        target_guid = account.GetGUID().to_string()
        for split in tx.GetSplitList():
            if split.GetAccount().GetGUID().to_string() == target_guid:
                info["amount"] = get_split_amount(split)
                break
 
    return info

def list_transactions(account, start_date, end_date, include_subaccounts=False) -> list:
    """
    List all transactions touching `account` (and optionally its sub-accounts)
    between start_date and end_date (inclusive).
 
    start_date / end_date can be datetime.date, datetime.datetime, or 'YYYY-MM-DD' strings.
 
    Returns a list of dicts (see get_transaction_info), sorted by date,
    each including an 'amount' entry = the signed amount posted to the
    matching account for that transaction.
    """
    start_date = _parse_date(start_date)
    end_date = _parse_date(end_date)
 
    accounts = [account]
    if include_subaccounts:
        accounts += get_all_subaccounts(account)
 
    seen_tx_guids = set()
    results = []
 
    for acc in accounts:
        for split in acc.GetSplitList():
            tx = split.GetParent()
            guid = tx.GetGUID().to_string()
            if guid in seen_tx_guids:
                continue
 
            tx_date = transaction_date(tx)
            if start_date <= tx_date <= end_date:
                seen_tx_guids.add(guid)
                results.append(get_transaction_info(tx, acc))
 
    results.sort(key=lambda d: d["date"])
    return results
 
 
def print_transactions(transactions):
    """Pretty-print the output of list_transactions()."""
    for t in transactions:
        amt = t.get("amount")
        amt_str = f"{amt:.2f}" if amt is not None else ""
        print(f"{t['date']} | {amt_str:>10} | {t['description']}")
