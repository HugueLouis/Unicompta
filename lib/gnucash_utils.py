import gnucash
from gnucash import Session, Transaction, Split, GncNumeric
from gnucash.gnucash_core_c import ACCT_TYPE_ASSET, ACCT_TYPE_EXPENSE  # etc.
from decimal import Decimal
import datetime

def list_accounts_rec(account,max, indent=0):
    print("  " * indent+ f"{indent} : " + account.GetName())
    if indent >= max :
        return
    else:
        for child in account.get_children():
            list_accounts_rec(child, max, indent + 1)

def list_all_accounts(abs_file_path,max):
    session = gnucash.Session("xml://"+ abs_file_path)
    try :
        book = session.book
        root = book.get_root_account()
        list_accounts_rec(root,max)
    finally : 
        session.end()

def find_account(root, name):
    if root.GetName() == name:
        return root
    for child in root.get_children():
        result = find_account(child, name)
        if result:
            return result
    return None

def add_transaction(book, from_account, to_account, amount_decimal, description, date=None):
    if date is None:
        date = datetime.date.today()

    currency = book.get_table().lookup("ISO4217", "CHF")  # adapt to your currency

    tx = Transaction(book)
    tx.BeginEdit()

    tx.SetCurrency(currency)
    tx.SetDescription(description)
    tx.SetDate(date.day, date.month, date.year)

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