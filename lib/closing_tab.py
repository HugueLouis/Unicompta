"""Year-end tab: preview what the closing will do, run it, and look at the result per pôle / comité."""
import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from lib.budget_tab import year_labels, fiscal_year_bounds
from lib.closing import plan_closing, apply_closing, find_bilan, preview_rows, closed_rows

WHITE, TEXT, GRAY = "#FFFFFF", "#1E293B", "#64748B"
C_PROFIT, C_LOSS, C_NET, C_WARN = "#2e9e5b", "#db3b30", "#0E0D0D", "#BB3935"


def chf(v) -> str:
    return f"{v:,.2f}".replace(",", "'")


class ClosingTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=WHITE, padx=20, pady=20)
        self.app, self.rows, self.plan, self.bilan, self.label = app, [], [], None, None

        top = tk.Frame(self, bg=WHITE)
        top.pack(fill="x")
        tk.Label(top, text="Année à clôturer", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 6))
        self.year_var = tk.StringVar(value=year_labels()[2])      # the year that just ended
        cb = ttk.Combobox(top, textvariable=self.year_var, values=year_labels(),
                          state="readonly", width=12)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.refresh)
        app._btn(top, "🗘 Actualiser", self.refresh).pack(side="left", padx=10)
        app._btn(top, "Clôturer l'année", self._close_year, bg="#BB3935").pack(side="right")

        self.status_var = tk.StringVar()
        self.status_lbl = tk.Label(self, textvariable=self.status_var, bg=WHITE, fg=GRAY,
                                   font=("Helvetica", 11), anchor="w", justify="left")
        self.status_lbl.pack(fill="x", pady=(8, 8))

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=WHITE, sashwidth=4)
        paned.pack(fill="both", expand=True)
        left, right = tk.Frame(paned, bg=WHITE), tk.Frame(paned, bg=WHITE)
        paned.add(left, minsize=520)
        paned.add(right, minsize=400)

        cols = (("cat", "Catégorie", 70), ("name", "Compte", 190), ("prod", "Produits", 90),
                ("chg", "Charges", 90), ("net", "Résultat", 90))
        self.tree = ttk.Treeview(left, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse", height=12)
        for key, title, width in cols:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w" if key in ("cat", "name") else "e")
        self.tree.tag_configure("loss", foreground=C_LOSS)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        tk.Label(left, text="Détail de la sélection", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(8, 2))
        self.detail = tk.Listbox(left, font=("Courier", 10), relief="solid", bd=1, height=9)
        self.detail.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # -- data -----------------------------------------------------------------

    def refresh(self, *_):
        label = self.year_var.get()
        _, end = fiscal_year_bounds(label)
        try:
            plan = plan_closing(self.app.act_root, end)
            bilan = find_bilan(self.app.act_root, label)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self.plan, self.bilan, self.label = plan, bilan, label
        already = bool(bilan and bilan.GetSplitList())
        if plan:
            self.rows = preview_rows(plan)
        else:
            self.rows = closed_rows(bilan) if already else []

        warn = False
        if bilan is None:
            warn = True
            msg = (f"⚠ Compte « Pertes et profits {label.replace('-', ' - ')} » introuvable sous 05-Bilan : "
                   "créez-le dans GnuCash avant de clôturer.")
        elif plan:
            msg = (f"Aperçu : {len(plan)} pôle(s)/comité(s) à clôturer au {end.strftime('%d.%m.%Y')}."
                   + (" Des écritures de bilan existent déjà pour cette année (clôture partielle ?)." if already else ""))
        elif already:
            msg = "Année clôturée : plus rien à clôturer. Résultats lus dans le compte Pertes et profits."
        else:
            msg = "Aucune écriture de charges/produits à clôturer pour cette année."
        self.status_var.set(msg)
        self.status_lbl.config(fg=C_WARN if warn else GRAY)

        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            net = r["produits"] - r["charges"]
            self.tree.insert("", "end", iid=str(i), tags=("loss",) if net < 0 else (),
                             values=(r["category"], r["label"], chf(r["produits"]),
                                     chf(r["charges"]), chf(net)))
        self.detail.delete(0, "end")
        self._draw()

    def _on_select(self, _=None):
        sel = self.tree.selection()
        self.detail.delete(0, "end")
        if sel:
            for text, amount in self.rows[int(sel[0])]["details"]:
                self.detail.insert("end", f"{chf(amount):>12}  {text}")

    # -- closing --------------------------------------------------------------

    def _close_year(self):
        self.refresh()
        if self.bilan is None:
            messagebox.showerror("Erreur", "Le compte Pertes et profits de cette année n'existe pas.")
            return
        if not self.plan:
            messagebox.showinfo("Clôture", "Rien à clôturer pour cette année.")
            return
        _, end = fiscal_year_bounds(self.label)
        if not messagebox.askyesno(
                "Clôturer l'année",
                f"Clôturer {self.label} au {end.strftime('%d.%m.%Y')} ?\n\n"
                f"{len(self.plan)} pôle(s)/comité(s) : charges et produits vidés vers les Fonds, puis "
                "Fonds → Pertes et profits.\nRien n'est poussé sur git tant que vous n'appuyez pas sur Push."):
            return
        try:
            n = apply_closing(self.app.book, self.plan, self.bilan, self.label, end)
            self.app.session.save()
        except Exception as e:
            messagebox.showerror("Erreur", f"Clôture interrompue :\n{e}\n\n"
                                           "Le fichier n'a pas été sauvegardé. Redémarrez ou faites Reset repo.")
            return
        self.refresh()
        messagebox.showinfo("Succès", f"{n} transaction(s) créée(s).")

    # -- plot -----------------------------------------------------------------

    def _draw(self):
        self.fig.clear()
        if self.rows:
            ax = self.fig.add_subplot(111)
            x, w = list(range(len(self.rows))), 0.27
            ax.bar([i - w for i in x], [float(r["produits"]) for r in self.rows], w,
                   label="Produits", color=C_PROFIT)
            ax.bar(x, [float(r["charges"]) for r in self.rows], w, label="Charges", color=C_LOSS)
            ax.bar([i + w for i in x], [float(r["produits"] - r["charges"]) for r in self.rows], w,
                   label="Résultat", color=C_NET)
            ax.axhline(0, color="black", lw=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels([r["label"].split(" (")[0] for r in self.rows],
                               rotation=40, ha="right", fontsize=8)
            ax.set_ylabel("CHF")
            ax.set_title(f"Résultat {self.label}", loc="left", fontweight="bold")
            ax.legend(frameon=False)
            ax.spines[["top", "right"]].set_visible(False)
            self.fig.tight_layout()
        self.canvas.draw()