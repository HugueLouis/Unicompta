"""Year-end closing logic (no GUI).

For each pôle / comité that has a Fond (02-00-01-Comité / 02-00-02-Pôles d'activité, ">-0X-NN-Name (CODE)"):
  1. its charges (03-0X-NN-...) and products (04-0X-NN-...) accounts and all their sub-accounts are
     emptied into the Fond, one multi-split transaction per type: "Clôture des comptes Charges <pole>"
  2. the Fond sends the sum of products and the sum of charges to
     05-Bilan:"Pertes et profits <y> - <y+1>" as two transactions.
Accounts are matched through the "0X-NN" index in their names (the codes differ: EDA/EVA, ...),
then through the "(CODE)" as a fallback. Funds without "(CODE)" (Rebuilt) are ignored.
Balances are taken up to the closing date, so a second run finds nothing left to close.
"""
import re
from decimal import Decimal

from lib.gnucash_utils import find_account_including, get_all_subaccounts, add_multi_transaction

GROUPS = {   # category: (index, fond root, charges root, products root)
    "Comité": ("01", "02-00-01-Comité", "03-01-Comité", "04-01-Comité"),
    "Pôle":   ("02", "02-00-02-Pôles d'activité", "03-02-Pôles d'activité", "04-02-Pôles d'activité"),
}
FOND_RE = re.compile(r"^>-(\d\d)-(\d\d)-.*\(([^()]+)\)\s*$")


def clean_label(name: str) -> str:
    return re.sub(r"^>-\d\d-\d\d-", "", name)


def balance(acc, end) -> Decimal:
    return sum((s.amount for s in acc.GetSplitList() if s.tx.date <= end), Decimal(0))


def subtree_lines(acc, end) -> list:
    """[(account, balance)] for the account and its sub-accounts, non-zero balances only."""
    out = []
    for a in [acc, *get_all_subaccounts(acc)]:
        b = balance(a, end)
        if b != 0:
            out.append((a, b))
    return out


def find_child(parent, prefix, code):
    kids = parent.get_children()
    for k in kids:
        if k.GetName().startswith(prefix):
            return k
    for k in kids:
        if f"({code})" in k.GetName():
            return k
    return None


def find_bilan(root, label):
    """05-Bilan:'Pertes et profits 2025 - 2026' (case-insensitive) or None."""
    y1, y2 = label.split("-")
    target = f"pertes et profits {y1} - {y2}"
    for a in find_account_including(root, "05-Bilan").get_children():
        if a.GetName().strip().lower() == target:
            return a
    return None


def plan_closing(root, end) -> list:
    """What is left to close at `end`: one entry per fond with at least one non-zero account."""
    plan = []
    for cat, (g, fond_n, chg_n, prd_n) in GROUPS.items():
        fond_root = find_account_including(root, fond_n)
        chg_root = find_account_including(root, chg_n)
        prd_root = find_account_including(root, prd_n)
        for fond in fond_root.get_children():
            m = FOND_RE.match(fond.GetName())
            if not m or m.group(1) != g:
                continue
            nn, code = m.group(2), m.group(3)
            entry = {"category": cat, "label": clean_label(fond.GetName()), "fond": fond}
            for kind, parent, pre in (("Charges", chg_root, "03"), ("Produits", prd_root, "04")):
                acc = find_child(parent, f"{pre}-{g}-{nn}-", code)
                lines = subtree_lines(acc, end) if acc else []
                entry[kind] = {"lines": lines, "total": sum((b for _, b in lines), Decimal(0))}
            if entry["Charges"]["lines"] or entry["Produits"]["lines"]:
                plan.append(entry)
    return plan


def apply_closing(book, plan, bilan, label, end) -> int:
    """Create the transactions (caller saves the session). Returns how many were created."""
    n = 0
    for e in plan:
        for kind in ("Charges", "Produits"):
            lines, total = e[kind]["lines"], e[kind]["total"]
            if lines:   # zero every account, the opposite amount goes to the fond
                splits = [(a, -b) for a, b in lines] + [(e["fond"], total)]
                add_multi_transaction(book, splits, f"Clôture des comptes {kind} {e['label']}", end)
                n += 1
        profit, loss = -e["Produits"]["total"], e["Charges"]["total"]
        if profit:
            add_multi_transaction(book, [(e["fond"], profit), (bilan, -profit)],
                                  f"Bilan {label} Produits {e['label']}", end)
            n += 1
        if loss:
            add_multi_transaction(book, [(e["fond"], -loss), (bilan, loss)],
                                  f"Bilan {label} Charges {e['label']}", end)
            n += 1
    return n


def preview_rows(plan) -> list:
    rows = []
    for e in plan:
        details = [(f"{kind} · {a.GetName()}", b if kind == "Charges" else -b)
                   for kind in ("Charges", "Produits") for a, b in e[kind]["lines"]]
        rows.append({"category": e["category"], "label": e["label"],
                     "produits": -e["Produits"]["total"], "charges": e["Charges"]["total"],
                     "details": details})
    return rows


def closed_rows(bilan) -> list:
    """What the closing already did, read back from the Bilan account (fond side of each transaction)."""
    rows = {}
    for s in bilan.GetSplitList():
        for o in s.tx.splits:
            if o.account is bilan:
                continue
            name = o.account.GetName()
            r = rows.setdefault(o.account.guid, {
                "category": "Comité" if name.startswith(">-01") else "Pôle", "label": clean_label(name),
                "produits": Decimal(0), "charges": Decimal(0), "details": []})
            if o.amount > 0:
                r["produits"] += o.amount
            else:
                r["charges"] += -o.amount
            r["details"].append((s.tx.description, o.amount))
    return sorted(rows.values(), key=lambda r: (r["category"], r["label"]))