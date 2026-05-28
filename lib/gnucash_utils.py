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
