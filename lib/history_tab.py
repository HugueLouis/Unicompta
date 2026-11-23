"""History tab: list the git commits and show what each one changed in the gnucash file, as transactions."""
import gzip
import threading
import tkinter as tk
from decimal import Decimal
from tkinter import ttk

from lxml import etree
from tkinter import ttk, messagebox

from lib.git_utils import git_log, git_show_file
from lib.gnucash_utils import Book
from lib.unipoly_logic import GNUCASH_FILE, GNUCASH_RELATIVE

WHITE, TEXT, GRAY = "#FFFFFF", "#1E293B", "#64748B"
C_ADD, C_DEL, C_MOD = "#16A34A", "#BB3935", "#D48217"
WORKING = "WORKING"
REL_PATH = GNUCASH_RELATIVE.replace("\\", "/")


def chf(v) -> str:
    return f"{v:,.2f}".replace(",", "'")


# ── Pure logic ────────────────────────────────────────────────────────────────

def parse_book(raw):
    if raw is None:
        return None
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return Book(etree.fromstring(raw))


def full_name(acc, book) -> str:
    parts = []
    while acc is not None and acc.type != "ROOT":
        parts.append(acc.name)
        acc = book.accounts.get(acc.parent_guid)
    return ":".join(reversed(parts))


def tx_lines(tx, book) -> list:
    return [(full_name(s.account, book), s.amount) for s in tx.splits]


def signature(tx, book):
    return (tx.date, tx.description,
            tuple(sorted((s.account.guid, s.amount) for s in tx.splits)))

def snap(t, book) -> dict:
    """Plain-data copy of a transaction, enough to rebuild it later."""
    return {"guid": t.guid, "date": t.date, "desc": t.description,
            "splits": [(s.account.guid, full_name(s.account, book), s.value) for s in t.splits]}


def snap_key(s):
    return (s["date"], s["desc"], tuple(sorted((g, v) for g, _, v in s["splits"])))


def resolve_account(book, guid, name):
    """Account by GUID, or by full name if the GUID no longer exists."""
    acc = book.accounts.get(guid)
    if acc:
        return acc
    for a in book.accounts.values():
        if full_name(a, book) == name:
            return a
    raise ValueError(f"Account not found in the current file:\n{name}")


def restore(book, s):
    legs = [(resolve_account(book, g, n), v) for g, n, v in s["splits"]]
    book.add_multi_transaction(legs, s["desc"], s["date"], guid=s["guid"])


def apply_revert(book, change) -> str:
    """Undo one change on the live book (caller saves). Raises ValueError if it can't."""
    kind, guid = change["kind"], change["guid"]
    cur = {t.guid: t for t in book.transactions}.get(guid)
    if kind == "-":                                   # re-add the removed transaction
        if cur:
            raise ValueError("This transaction already exists in the current file.")
        restore(book, change["old"])
        return "Transaction restored."
    if kind == "+":                                   # remove the added transaction
        if not cur:
            raise ValueError("This transaction no longer exists in the current file.")
        book.remove_transaction(cur)
        return "Transaction removed."
    # "~": put the old version back
    old = change["old"]
    for g, n, _ in old["splits"]:
        resolve_account(book, g, n)                   # fail BEFORE touching anything
    if cur:
        book.remove_transaction(cur)
    restore(book, old)
    return "Previous version restored."

def tx_amount(tx):
    return sum((s.amount for s in tx.splits if s.amount > 0), Decimal(0))


def net_by_account(lines, sign=1) -> dict:
    """{full account name: signed amount} from [(name, amount)]."""
    out = {}
    for name, a in lines:
        out[name] = out.get(name, Decimal(0)) + sign * a
    return out


def short_names(names) -> str:
    """Leaf name of each account, e.g. 'Banque-Principal, API (API)'."""
    return ", ".join(n.split(":")[-1].lstrip(">-0123456789") or n for n in names)


def diff_books(old, new) -> list:
    """Plain-data list of changes between two books (either may be None = empty)."""
    old_tx = {t.guid: t for t in old.transactions} if old else {}
    new_tx = {t.guid: t for t in new.transactions} if new else {}
    changes = []

    def fmt(lines, sign):
        return [f"  {sign} {chf(a):>12}  {n}" for n, a in lines]

    def add(kind, t, details, net, accounts, old=None, new=None):
        changes.append({"kind": kind, "date": t.date, "desc": t.description, "amount": tx_amount(t),
                        "details": details, "net": net, "accounts": sorted(accounts),
                        "guid": t.guid, "old": old, "new": new})

    for g, t in new_tx.items():
        if g not in old_tx:
            nl = tx_lines(t, new)
            add("+", t, fmt(nl, "+"), net_by_account(nl), {n for n, _ in nl}, new=snap(t, new))
        elif signature(old_tx[g], old) != signature(t, new):
            o = old_tx[g]
            ol, nl = tx_lines(o, old), tx_lines(t, new)
            d = []
            if o.date != t.date:
                d.append(f"date: {o.date} → {t.date}")
            if o.description != t.description:
                d.append(f"description: {o.description}")
                d.append(f"         → {t.description}")
            if sorted(ol) != sorted(nl):
                d.append("before:")
                d += fmt(ol, "-")
                d.append("after:")
                d += fmt(nl, "+")
            net = net_by_account(nl)
            for k, v in net_by_account(ol, -1).items():
                net[k] = net.get(k, Decimal(0)) + v
            add("~", t, d, net, {n for n, _ in ol} | {n for n, _ in nl},
                old=snap(o, old), new=snap(t, new))
    for g, t in old_tx.items():
        if g not in new_tx:
            ol = tx_lines(t, old)
            add("-", t, fmt(ol, "-"), net_by_account(ol, -1), {n for n, _ in ol}, old=snap(t, old))
    changes.sort(key=lambda c: (c["date"], c["desc"]), reverse=True)
    return changes


def account_summary(changes) -> list:
    """[(account, nb_transactions, net_change)] sorted by account name."""
    rows = {}
    for c in changes:
        for acc in c["accounts"]:
            n, net = rows.get(acc, (0, Decimal(0)))
            rows[acc] = (n + 1, net + c["net"].get(acc, Decimal(0)))
    return [(a, n, net) for a, (n, net) in sorted(rows.items())]


def compute_commit_diff(h) -> dict:
    if h == WORKING:
        old = git_show_file("HEAD", REL_PATH)
        try:
            with open(GNUCASH_FILE, "rb") as f:
                new = f.read()
        except FileNotFoundError:
            new = None
    else:
        new = git_show_file(h, REL_PATH)
        old = git_show_file(h + "^1", REL_PATH)     # None for the first commit -> everything is "added"
    if old == new:
        return {"same": True, "changes": []}
    return {"same": False, "changes": diff_books(parse_book(old), parse_book(new))}


# ── Tab ───────────────────────────────────────────────────────────────────────

class HistoryTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=WHITE, padx=20, pady=20)
        self.app, self.changes, self.cache, self._token = app, [], {}, 0
        self.summary, self.filter_acc = [], None

        top = tk.Frame(self, bg=WHITE)
        top.pack(fill="x", pady=(0, 8))
        app._btn(top, "🗘 Actualiser", self.refresh).pack(side="left")
        self.status_var = tk.StringVar(value="Select a commit")
        tk.Label(top, textvariable=self.status_var, bg=WHITE, fg=GRAY,
                 font=("Helvetica", 11)).pack(side="left", padx=12)

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=WHITE, sashwidth=4)
        paned.pack(fill="both", expand=True)
        left, right = tk.Frame(paned, bg=WHITE), tk.Frame(paned, bg=WHITE)
        paned.add(left, minsize=380)
        paned.add(right, minsize=620)

        # commits
        cols = (("hash", "Commit", 70), ("date", "Date", 85), ("author", "Auteur", 90), ("msg", "Message", 220))
        self.commits = ttk.Treeview(left, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for key, title, width in cols:
            self.commits.heading(key, text=title)
            self.commits.column(key, width=width, anchor="w")
        sb = tk.Scrollbar(left, command=self.commits.yview)
        self.commits.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.commits.pack(fill="both", expand=True)
        self.commits.bind("<<TreeviewSelect>>", self._on_commit)

        # changes
        cols = (("k", "", 25), ("date", "Date", 80), ("amount", "Montant", 80),
                ("desc", "Description", 230), ("accs", "Comptes", 200))
        self.tree = ttk.Treeview(right, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse", height=8)
        for key, title, width in cols:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="e" if key == "amount" else "w")
        self.tree.tag_configure("+", foreground=C_ADD)
        self.tree.tag_configure("-", foreground=C_DEL)
        self.tree.tag_configure("~", foreground=C_MOD)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_change)

        # affected accounts (click = filter the list above)
        hdr = tk.Frame(right, bg=WHITE)
        hdr.pack(fill="x", pady=(8, 2))
        tk.Label(hdr, text="Comptes affectés (cliquer pour filtrer)", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11, "bold")).pack(side="left")
        app._btn(hdr, "Tout afficher", self._clear_filter, bg=GRAY).pack(side="right")
        cols = (("acc", "Compte", 400), ("n", "Nb tx", 50), ("net", "Variation", 90))
        self.acc_tree = ttk.Treeview(right, columns=[c[0] for c in cols], show="headings",
                                     selectmode="browse", height=6)
        for key, title, width in cols:
            self.acc_tree.heading(key, text=title)
            self.acc_tree.column(key, width=width, anchor="w" if key == "acc" else "e")
        self.acc_tree.tag_configure("pos", foreground=C_ADD)
        self.acc_tree.tag_configure("neg", foreground=C_DEL)
        self.acc_tree.pack(fill="both", expand=True)
        self.acc_tree.bind("<<TreeviewSelect>>", self._on_account)

        hdr2 = tk.Frame(right, bg=WHITE)
        hdr2.pack(fill="x", pady=(8, 2))
        tk.Label(hdr2, text="Détail", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11, "bold")).pack(side="left")
        app._btn(hdr2, "↩ Annuler ce changement", self._revert, bg=C_DEL).pack(side="right")

        self.detail = tk.Listbox(right, font=("Courier", 10), relief="solid", bd=1, height=7)
        self.detail.pack(fill="both", expand=True)

    # -- commits --------------------------------------------------------------

    def refresh(self, *_):
        self.cache.clear()                      # HEAD / working copy may have changed
        self.commits.delete(*self.commits.get_children())
        self.commits.insert("", "end", iid=WORKING, values=("●", "", "", "Working copy (not pushed)"))
        for h, d, a, s in git_log():
            self.commits.insert("", "end", iid=h, values=(h, d, a, s))
        self._clear()

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self.acc_tree.delete(*self.acc_tree.get_children())
        self.detail.delete(0, "end")
        self.changes, self.summary, self.filter_acc = [], [], None

    def _on_commit(self, _=None):
        sel = self.commits.selection()
        if not sel:
            return
        h = sel[0]
        self._token += 1
        if h in self.cache:
            self._show(self.cache[h])
            return
        self._clear()
        self.status_var.set("Loading…")
        threading.Thread(target=self._work, args=(h, self._token), daemon=True).start()

    def _work(self, h, token):
        try:
            result = compute_commit_diff(h)
        except Exception as e:
            result = {"error": str(e)}
        self.after(0, lambda: self._done(h, token, result))

    def _done(self, h, token, result):
        if "error" not in result:
            self.cache[h] = result
        if token == self._token:                # ignore results of a commit that is no longer selected
            self._show(result)

    # -- display --------------------------------------------------------------

    def _show(self, result):
        self._clear()
        if "error" in result:
            self.status_var.set("Error: " + result["error"])
            return
        if result["same"]:
            self.status_var.set("This commit doesn't change the gnucash file.")
            return
        self.changes = result["changes"]
        self.summary = account_summary(self.changes)
        n = {k: sum(1 for c in self.changes if c["kind"] == k) for k in "+-~"}
        self.status_var.set(f"{n['+']} added, {n['-']} removed, {n['~']} modified, "
                            f"{len(self.summary)} account(s) affected")
        for i, (acc, cnt, net) in enumerate(self.summary):
            self.acc_tree.insert("", "end", iid=str(i), tags=("pos" if net > 0 else "neg" if net < 0 else "",),
                                 values=(acc, cnt, chf(net)))
        self._fill_changes()

    def _fill_changes(self):
        self.tree.delete(*self.tree.get_children())
        self.detail.delete(0, "end")
        for i, c in enumerate(self.changes):
            if self.filter_acc and self.filter_acc not in c["accounts"]:
                continue
            self.tree.insert("", "end", iid=str(i), tags=(c["kind"],),
                             values=(c["kind"], c["date"], chf(c["amount"]), c["desc"],
                                     short_names(c["accounts"])))

    def _on_account(self, _=None):
        sel = self.acc_tree.selection()
        if sel:
            self.filter_acc = self.summary[int(sel[0])][0]
            self._fill_changes()

    def _clear_filter(self):
        self.filter_acc = None
        self.acc_tree.selection_remove(*self.acc_tree.selection())
        self._fill_changes()

    def _on_change(self, _=None):
        sel = self.tree.selection()
        self.detail.delete(0, "end")
        if sel:
            for line in self.changes[int(sel[0])]["details"]:
                self.detail.insert("end", line)

    def _revert(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attention", "Select a change in the list first.")
            return
        c = self.changes[int(sel[0])]
        if any(e.tx.guid == c["guid"] for e in self.app.transactions):
            messagebox.showwarning("Attention", "This transaction was created in this session.\n"
                                                "Use « Supprimer » in the Transactions list instead.")
            return
        what = {"-": "Re-add this transaction", "+": "Delete this transaction",
                "~": "Restore the previous version of this transaction"}[c["kind"]]
        text = f"{what} ?\n\n{c['date']}  {chf(c['amount'])}\n{c['desc']}"
        cur = {t.guid: t for t in self.app.book.transactions}.get(c["guid"])
        if cur and c["kind"] in "+~" and snap_key(snap(cur, self.app.book)) != snap_key(c["new"]):
            text += "\n\n⚠ It has changed since this commit: the current version will be overwritten."
        if not messagebox.askyesno("Annuler ce changement", text):
            return
        try:
            msg = apply_revert(self.app.book, c)
            self.app.session.save()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self.cache.pop(WORKING, None)
        messagebox.showinfo("Succès", msg + "\n\nCheck « Working copy », then press Push.")
