#!/usr/bin/env python3
"""
Extract all payment amounts from a PostFinance "Edit payments" PDF export.

Usage:
    python extract_amounts.py path/to/file.pdf [--csv output.csv]

For each payment row it pulls out the currency (CHF/EUR) and the amount,
prints a running list, and reports totals per currency plus a grand count.
"""

import argparse
import csv
import re
import sys
import pdfplumber

# Matches things like "CHF 159.00", "EUR 74.20", "CHF 1'359.90"
AMOUNT_RE = re.compile(r"\b(CHF|EUR)\s+([\d']+\.\d{2})\b")
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")

def parse_amount(raw: str) -> float:
    """Convert "1'359.90" -> 1359.90"""
    return float(raw.replace("'", ""))


def extract_amounts(pdf_path: str):
    """Return a list of dicts: {currency, amount, date, line} for every amount found."""
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if "cancelled" in line.lower():
                    continue
                dates = DATE_RE.findall(line)
                date = dates[0] if dates else None
                for currency, raw_amount in AMOUNT_RE.findall(line):
                    results.append(
                        {
                            "currency": currency,
                            "amount": parse_amount(raw_amount),
                            "date": date,
                            "line": line.strip(),
                        }
                    )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the input PDF")
    parser.add_argument("--csv", help="Optional path to write results as CSV")
    args = parser.parse_args()

    amounts = extract_amounts(args.pdf_path)

    if not amounts:
        print("No amounts found.")
        sys.exit(0)

    # Skip the "Total CHF ..." / "Total EUR ..." summary rows already printed
    # by the statement itself, so we don't double count. They contain the word
    # "Total" in the line.
    line_items = [a for a in amounts if not a["line"].lower().startswith("total")]

    print(f"Found {len(line_items)} payment amounts:\n")
    for a in line_items:
        print(f"  {a['currency']} {a['amount']:.2f}")

    totals = {}
    for a in line_items:
        totals[a["currency"]] = totals.get(a["currency"], 0.0) + a["amount"]

    print("\n--- Totals ---")
    for currency, total in totals.items():
        print(f"{currency}: {total:,.2f}  ({sum(1 for a in line_items if a['currency'] == currency)} payments)")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["currency", "amount", "line"])
            writer.writeheader()
            writer.writerows(line_items)
        print(f"\nSaved details to {args.csv}")

if __name__ == "__main__":
    main()