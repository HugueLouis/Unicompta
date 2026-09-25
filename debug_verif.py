#!/usr/bin/env python3
from lib.unipoly_logic import *
from lib.gnucash_utils import *
from lib.ML import *
import tkinter as tk
import csv

"""
Extract all payment amounts from a Gnucash and the 
CREDITS (Postfinance) from a csv and compares the 2 lists
"""
START_DATE = "2025-09-01"
END_DATE = "2026-09-14"

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BASE = TkinterDnD.Tk
except ImportError:
    BASE = tk.Tk
    DND_FILES = None

DEFAULT_SECOND_COMPTA = True
PREFIX_DESC_SECOND_COMPTA = "n*2 "
CATEGORIES = ["Pôle", "Comité"]


def filter_common_numbers(list1, list2):
    groups1 = {}
    for n in list1:
        n = float(n)
        key = abs(n)
        groups1.setdefault(key, []).append(n)

    groups2 = {}
    for n in list2:
        n = float(n)
        key = abs(n)
        groups2.setdefault(key, []).append(n)

    remaining1 = []
    remaining2 = []

    all_keys = set(groups1) | set(groups2)

    for key in all_keys:
        g1 = groups1.get(key, [])
        g2 = groups2.get(key, [])

        shared_count = min(len(g1), len(g2))

        remaining1.extend(g1[shared_count:])
        remaining2.extend(g2[shared_count:])

    combined = remaining1 + remaining2

    return remaining1, remaining2, combined
 
if __name__ == "__main__":
    with open("amounts.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with  gnucash.Session("xml://"+ GNUCASH_FILE) as session:
            book = session.book
            root = book.get_root_account()
    
            account = find_account_including(root, ACT_BANQUE_ACTIF)
    
            transactions = list_transactions(
                account,
                start_date=START_DATE,
                end_date=END_DATE,
                include_subaccounts=False,
            )

            gnucash_list = [float(t["amount"]) for t in transactions]
            post_finance_amounts = booked_only = [
                        float(row["amount"])
                        for row in reader
                        if "cancelled" not in row["line"].lower()
                    ]

            remaining1, remaining2, combined = filter_common_numbers(gnucash_list, post_finance_amounts)
        
            print(f"List 1: {gnucash_list}\n")
            print(f"List 2: {post_finance_amounts}\n")
            print(f"Leftover from list 1 (not cancelled out): {remaining1}\n")
            print(f"Leftover from list 2 (not cancelled out): {remaining2}\n")

