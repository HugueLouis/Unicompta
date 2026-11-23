"""Budget tab: set a yearly budget per pôle / comité and compare it with what left the bank account.

Spending is read from Actif:Banque principal. Each transaction is attributed with its name,
e.g. "S2526-API-REMB-3 Name description" -> year 2025-2026, pole API.

Budgets are stored in <repo>/budget.json (repo root, NOT in "1 - Comptabilite/" because
clean_gnucash_folder() wipes everything there). git_add() uses `git add .`, so the file
is pushed with the rest and shared between treasurers.
"""
import json
import os
import re
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from tkinter import ttk, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from lib.gnucash_utils import list_transactions
from lib.unipoly_logic import APP_DIR, YEAR_CHANGE_MONTH, YEAR_CHANGE_DAY, get_poles, pole_code

BUDGET_FILE = os.path.join(APP_DIR, "budget.json")
WHITE, TEXT = "#FFFFFF", "#1E293B"
C_BUDGET, C_OK, C_OVER = "#F88F39", "#2e9e5b", "#db3b30"


# ── Pure logic ────────────────────────────────────────────────────────────────

def current_year_label(today=None) -> str:
    today = today or date.today()
    after_change = (today.month, today.day) > (YEAR_CHANGE_MONTH, YEAR_CHANGE_DAY)
    y = today.year if after_change else today.year - 1
    return f"{y}-{y + 1}"


def year_labels() -> list:
    y0 = int(current_year_label()[:4])
    return [f"{y}-{y + 1}" for y in range(y0 + 1, y0 - 4, -1)]


def fiscal_year_bounds(label: str):
    """'2025-2026' -> (2025-09-01, 2026-08-31)"""
    y = int(label[:4])
    return date(y, YEAR_CHANGE_MONTH + 1, 1), date(y + 1, YEAR_CHANGE_MONTH, YEAR_CHANGE_DAY)


def load_budgets() -> dict:
    """{ "2025-2026": { "API": 500.0, ... }, ... }"""
    try:
        with open(BUDGET_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_budgets(data: dict):
    tmp = BUDGET_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, BUDGET_FILE)


# Bank transactions are named like "S2526-API-REMB-3 Name description"
# (see build_filename + _submit); a second-compta copy may carry an "n*2 " prefix.
NAME_RE = re.compile(r"^(?:n\*2 )?S(\d{4})-(\w+)-(?:REMB|FACT)-\d+")


def bank_spending(act_bank, label) -> dict:
    """{pole_code: (paid, pending)} for the fiscal year, read from Actif:Banque principal.

    The pole and the year come from the transaction name. Second-compta entries are dated
    YEAR_BUMP_S_C years in the future until "Fix all dates" matches them with the bank csv:
    those are counted as 'pending' (booked, not yet debited by the bank).
    """
    year = f"{label[2:4]}{label[7:9]}"                      # "2025-2026" -> "2526"
    pending_after = date.today() + timedelta(days=365 * 20)
    totals = {}
    for t in list_transactions(act_bank, date(2000, 1, 1), date(2300, 1, 1)):
        m = NAME_RE.match(t["description"])
        if not m or m.group(1) != year:
            continue
        paid, pending = totals.get(m.group(2), (Decimal(0), Decimal(0)))
        amount = -t["amount"]                               # money leaving the bank = spent
        if t["date"] > pending_after:
            pending += amount
        else:
            paid += amount
        totals[m.group(2)] = (paid, pending)
    return totals


def collect_rows(act_bank, categories, label, budgets) -> list:
    """One row per pôle/comité folder: budget (json) and spent/pending (bank account in GnuCash)."""
    start, _ = fiscal_year_bounds(label)
    totals = bank_spending(act_bank, label)
    rows = []
    for cat in categories:
        for folder in get_poles(start, cat):
            try:
                code = pole_code(folder)
            except ValueError:
                continue  # badly named folder
            paid, pending = totals.get(code, (Decimal(0), Decimal(0)))
            rows.append({"category": cat, "name": folder, "code": code,
                         "budget": float(budgets.get(code, 0)),
                         "spent": float(paid), "pending": float(pending)})
    return rows


def is_over(r) -> bool:
    return r["budget"] > 0 and r["spent"] + r["pending"] > r["budget"]


# ── Tab ───────────────────────────────────────────────────────────────────────

class BudgetTab(tk.Frame):
    def __init__(self, parent, app, categories):
        super().__init__(parent, bg=WHITE, padx=20, pady=20)
        self.app, self.categories, self.rows = app, categories, []

        top = tk.Frame(self, bg=WHITE)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Année (sept → août)", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 6))
        self.year_var = tk.StringVar(value=current_year_label())
        cb = ttk.Combobox(top, textvariable=self.year_var, values=year_labels(),
                          state="readonly", width=12)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.refresh)
        app._btn(top, "🗘 Actualiser", self.refresh).pack(side="left", padx=10)

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=WHITE, sashwidth=4)
        paned.pack(fill="both", expand=True)
        left = tk.Frame(paned, bg=WHITE)
        right = tk.Frame(paned, bg=WHITE)
        paned.add(left, minsize=520)
        paned.add(right, minsize=400)

        # Table
        cols = (("cat", "Catégorie", 70), ("name", "Compte", 190),
                ("budget", "Budget", 80), ("spent", "Dépensé", 80),
                ("pending", "En attente", 80), ("left", "Reste", 80))
        self.tree = ttk.Treeview(left, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse")
        for key, title, width in cols:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w" if key in ("cat", "name") else "e")
        self.tree.tag_configure("over", foreground=C_OVER)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Budget editor
        edit = tk.Frame(left, bg=WHITE)
        edit.pack(fill="x", pady=8)
        self.sel_var = tk.StringVar(value="Sélectionnez un compte")
        tk.Label(edit, textvariable=self.sel_var, bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11)).pack(side="left")
        self.budget_var = tk.StringVar()
        entry = tk.Entry(edit, textvariable=self.budget_var, width=10, font=("Helvetica", 12))
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", self._set_budget)
        app._btn(edit, "Définir le budget (CHF)", self._set_budget).pack(side="left")

        # Plot
        self.fig = Figure(figsize=(7, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # -- data -----------------------------------------------------------------

    def refresh(self, *_):
        label = self.year_var.get()
        try:
            self.rows = collect_rows(self.app.act_banque_actif, self.categories,
                                     label, load_budgets().get(label, {}))
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            self.tree.insert("", "end", iid=str(i), tags=("over",) if is_over(r) else (),
                             values=(r["category"], r["name"], f"{r['budget']:.2f}",
                                     f"{r['spent']:.2f}", f"{r['pending']:.2f}",
                                     f"{r['budget'] - r['spent'] - r['pending']:.2f}"))
        self._draw()

    def _on_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.rows[int(sel[0])]
        self.sel_var.set(r["name"])
        self.budget_var.set(f"{r['budget']:.2f}" if r["budget"] else "")

    def _set_budget(self, *_):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attention", "Sélectionnez un compte.")
            return
        r = self.rows[int(sel[0])]
        txt = self.budget_var.get().replace(",", ".").replace("'", "").strip()
        try:
            value = float(Decimal(txt)) if txt else 0.0
        except InvalidOperation:
            messagebox.showerror("Erreur", "Montant invalide.")
            return
        data = load_budgets()
        data.setdefault(self.year_var.get(), {})[r["code"]] = value
        save_budgets(data)
        self.refresh()
        self.tree.selection_set(sel[0])

    # -- plot -----------------------------------------------------------------

    def _draw(self):
        self.fig.clear()
        cats = [c for c in self.categories if any(r["category"] == c for r in self.rows)]
        if cats:
            axes = self.fig.subplots(len(cats), 1, squeeze=False)[:, 0]
            for ax, cat in zip(axes, cats):
                d = [r for r in self.rows if r["category"] == cat]
                x, w = list(range(len(d))), 0.38
                cols = [C_OVER if is_over(r) else C_OK for r in d]
                ax.bar([i - w / 2 for i in x], [r["budget"] for r in d], w, color=C_BUDGET)
                spent = ax.bar([i + w / 2 for i in x], [r["spent"] for r in d], w, color=cols)
                ax.bar_label(spent, fmt="%.0f", fontsize=7)
                # booked but not yet debited by the bank: hatched, stacked on top of spent
                ax.bar([i + w / 2 for i in x], [r["pending"] for r in d], w,
                       bottom=[r["spent"] for r in d], facecolor="white",
                       edgecolor=cols, hatch="//")
                ax.axhline(0, color="black", lw=0.8)
                ax.set_xticks(x)
                ax.set_xticklabels([r["name"].split(" (")[0] for r in d],
                                   rotation=35, ha="right", fontsize=9)
                ax.set_title(cat, loc="left", fontweight="bold")
                ax.set_ylabel("CHF")
                ax.spines[["top", "right"]].set_visible(False)
            axes[0].legend(handles=[Patch(color=C_BUDGET, label="Budget"),
                                    Patch(color=C_OK, label="Dépensé"),
                                    Patch(color=C_OVER, label="Dépassement"),
                                    Patch(facecolor="white", edgecolor=C_OK, hatch="//",
                                          label="En attente")], frameon=False)
            self.fig.tight_layout()
        self.canvas.draw()