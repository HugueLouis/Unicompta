#!/usr/bin/env python3

import os, re, shutil
from datetime import date
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import gnucash

from gnucash import (
    Account,
    Book,
    GncCommodity,
    GncNumeric,
    Transaction,
    Session,
    SessionOpenMode,
    Split,
)


try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BASE = TkinterDnD.Tk
except ImportError:
    BASE = tk.Tk
    DND_FILES = None

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

BASE_DIR_OUTFLOW = os.path.expanduser("~/Documents/UPSecretrariat/4 - Justifications Sorties (S)/")   # dossier racine
DEBUG = 0

#TODO Change the way it chooses the folder of "2 - DDR" "3 - FACT"
#TODO make it register a line in gnucash in addition to saving the file to the right place
#TODO older name wasn't "Pôles" but "Pôles d'activités"

# ── LOGIQUE DU DOSSIER ─────────────────────────────────────────────────────

def folder_for_year_category(category: str,d: date) -> str :
    y = d.year
    ystr = f"{str(y)}-{str(y + 1)}" if d.month >= 9 else f"{str(y - 1)}-{str(y)}"
    if category == "Comité": #TODO
        return os.path.join(BASE_DIR_OUTFLOW, ystr , "Comité")
    return os.path.join(BASE_DIR_OUTFLOW ,ystr , "Pôles")

def target_folder( d : date,category: str, pole: str, doc_type : str) -> str:
    doc_type_folder = "2 - DDR" if doc_type =="REMB" else "3 - FACT" #TODO
    if category == "Comité":
        return os.path.join(folder_for_year_category(category, d), pole,doc_type_folder )
    return os.path.join( folder_for_year_category(category, d), pole,doc_type_folder)

# ── LOGIQUE DU NOM ────────────────────────────────────────────────────

def year_code(d: date) -> str:
    y = d.year
    if d.month >= 9: # after september take n to n+1
        return f"S{str(y)[2:]}{str(y + 1)[2:]}"
    # otherwise take n-1 to n
    return f"S{str(y - 1)[2:]}{str(y)[2:]}"

def pole_code(pole: str) -> str:
    m = re.search(r'\((\w+)\)', pole)
    if m:
        return m.group(1)
    raise ValueError(f"Folder '{pole}' is badly formatted (expected a (CODE) suffix)")

def next_number(folder: str) -> int:
    if not os.path.exists(folder):
        return 1 # folder doesn't exist
    nums = [
        int(m.group(1))
        for f in os.listdir(folder) # go through all files
        # assign the number if the file respects the format *-$m.pdf
        if (m := re.search(r"-(\d+)\.pdf$", f))
    ]
    return max(nums) + 1 if nums else 1

def build_filename(d: date, category: str, pole: str, doc_type: str) -> str:
    folder = target_folder(d,category, pole,doc_type)
    n      = next_number(folder)
    if DEBUG : print(d,category, pole, doc_type)
    return f"{year_code(d)}-{pole_code(pole)}-{doc_type}-{n}.pdf"

# ── Search existing folders ────────────────────────────────────────────────

def get_poles(category: str, d: date) -> list[str]:
    """Return subfolder names under the relevant Pôles or Comité directory."""
    base = folder_for_year_category(category, d)
    if DEBUG : print(base)
    if not os.path.exists(base):
        print(f"Path {base} does not exist")
        return []
    return sorted([
        f for f in os.listdir(base)
        if os.path.isdir(os.path.join(base, f))
    ])

# ── INTERFACE ─────────────────────────────────────────────────────────────────

BLUE   = "#2563EB"
LIGHT  = "#EFF6FF"
BORDER = "#CBD5E1"
TEXT   = "#1E293B"
GRAY   = "#64748B"
WHITE  = "#FFFFFF"
GREEN  = "#16A34A"

class App(BASE):
    def __init__(self):
        super().__init__()
        self.title("Dépôt PDF")
        self.configure(bg=WHITE)
        self.resizable(True, True)
        self.pdf_path = tk.StringVar()
        self.option_add("*TCombobox*Listbox.font", ("Helvetica", 18))
        self.option_add("*TCombobox.font", ("Helvetica", 18))
        self._build()
        self._center()

    def _on_cat_change(self, *_):
        try:
            d = date.fromisoformat(self.date_var.get())
        except ValueError:
            d = date.today()
        poles = get_poles(self.cat_var.get(), d)
        self.pole_combo["values"] = poles
        self.pole_var.set(poles[0] if poles else "")
        self._refresh_preview()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self, bg=WHITE, padx=28, pady=24)
        outer.pack(fill="both", expand=True)

        # Title
        tk.Label(outer, text="Dépôt de fichier PDF", font=("Helvetica", 16, "bold"),
                 bg=WHITE, fg=TEXT).pack(anchor="w", pady=(0, 18))

        form = tk.Frame(outer, bg=WHITE)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        # Date
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self._field(form, 0, "Date (YYYY-MM-DD)", tk.Entry(
            form, textvariable=self.date_var, **self._entry_kw(width=10)))

        # Catégorie
        self.cat_var = tk.StringVar(value="Pôle")
        self._field(form, 1, "Catégorie", ttk.Combobox(
            form, textvariable=self.cat_var,
            values=["Pôle", "Comité"], state="readonly", width=10))

        # Pôle
        self.pole_var = tk.StringVar()
        self.pole_combo = ttk.Combobox(
            form, textvariable=self.pole_var, state="readonly", width=20)
        self._field(form, 2, "Pôle / Comité", self.pole_combo)

        # Update poles when date or category changes
        self.date_var.trace_add("write", self._on_cat_change)
        self.cat_var.trace_add("write", self._on_cat_change)
        
        # Description
        self.desc_var = tk.StringVar()
        self._field(form, 3, "Description", tk.Entry(
            form, textvariable=self.desc_var, **self._entry_kw(width=40)))

        # Type of charge
        self.type_var = tk.StringVar(value="REMB") # TODO
        self._field(form, 4, "Charge", ttk.Combobox(
            form, textvariable=self.type_var,
            values=["REMB", "FACT"], state="readonly", width=10))

        # Amount
        self.amount_var = tk.StringVar()
        self._field(form, 5, "Montant (chf)", tk.Entry(
            form, textvariable=self.amount_var, **self._entry_kw(width=14)))

        # Separator
        sep = tk.Frame(outer, height=1, bg=BORDER)
        sep.pack(fill="x", pady=16)

        # Drop zone
        self.drop = tk.Label(
            outer,
            text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
            font=("Helvetica", 11), fg=GRAY, bg=LIGHT,
            relief="flat", bd=0, cursor="hand2",
            width=70, height=6,
        )
        self.drop.pack(pady=(0, 6))
        self.drop.bind("<Button-1>", self._pick)
        self.drop.bind("<Enter>", lambda e: self.drop.config(bg="#DBEAFE"))
        self.drop.bind("<Leave>", lambda e: self.drop.config(bg=LIGHT))

        # Draw dashed border manually via a surrounding frame
        border_frame = tk.Frame(outer, bg=BORDER, padx=1, pady=1)
        self.drop.pack_forget()
        border_frame.pack(pady=(0, 6))
        self.drop = tk.Label(
            border_frame,
            text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
            font=("Helvetica", 11), fg=GRAY, bg=LIGHT,
            cursor="hand2", padx=20, pady=16, width=80, height=5,
        )
        self.drop.pack()
        self.drop.bind("<Button-1>", self._pick)
        self.drop.bind("<Enter>", lambda e: self.drop.config(bg="#DBEAFE"))
        self.drop.bind("<Leave>", lambda e: self.drop.config(bg=LIGHT))

        if DND_FILES:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)

        # Filename preview
        self.preview_var = tk.StringVar(value="")
        self.preview_lbl = tk.Label(outer, textvariable=self.preview_var,
                                    font=("Helvetica", 18), fg=TEXT, bg=WHITE)
        self.preview_lbl.pack(anchor="w")

        for v in (self.date_var, self.cat_var, self.pole_var, self.type_var):
            v.trace_add("write", self._refresh_preview)
        self._refresh_preview()

        # Submit button
        btn = tk.Button(
            outer, text="  Déposer  ", command=self._submit,
            bg=BLUE, fg=WHITE, activebackground="#1D4ED8", activeforeground=WHITE,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", bd=0, width=20, height=5
        )
        btn.pack(pady=(14, 0))
        self._on_cat_change()  # populate on startup


    def _field(self, parent, row, label, widget):
        tk.Label(parent, text=label, font=("Helvetica", 18),
                 bg=WHITE, fg=TEXT, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        widget.grid(row=row, column=1, sticky="w", pady=5)

    def _entry_kw(self, width=30):
        return dict(
            font=("Helvetica", 18), fg=TEXT, bg=WHITE,
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE,
            width=width, insertbackground=BLUE,
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def _pick(self, _=None):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self._set_file(path)

    def _on_drop(self, event):
        # tkinterdnd2 wraps paths with spaces in braces
        path = event.data.strip().strip("{}")
        if path.lower().endswith(".pdf"):
            self._set_file(path)
        else:
            messagebox.showerror("Erreur", "Veuillez déposer un fichier PDF.")

    def _set_file(self, path):
        self.pdf_path.set(path)
        name = os.path.basename(path)
        self.drop.config(text=f"✅  {name}", fg=GREEN, bg="#F0FDF4")
        self._refresh_preview()

    def _refresh_preview(self, *_):
        try:
            d = date.fromisoformat(self.date_var.get())
            name = build_filename(d, self.cat_var.get(),
                                self.pole_var.get(), self.type_var.get())
            folder = target_folder(d, self.cat_var.get(), self.pole_var.get(),self.type_var.get())
            self.preview_var.set(f"→  {os.path.join(folder, name)[len(BASE_DIR_OUTFLOW):]}")
        except Exception:
            self.preview_var.set("")

    def _submit(self):
        if not self.pdf_path.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier PDF.")
            return
        try:
            d = date.fromisoformat(self.date_var.get())
        except ValueError:
            messagebox.showerror("Erreur", "Format de date invalide.\nUtilisez YYYY-MM-DD.")
            return

        date = self.date_var.get()
        category = self.cat_var.get()
        pole     = self.pole_var.get()
        doc_type = self.type_var.get()
        folder   = target_folder(date,category, pole,doc_type)
        filename = build_filename(d, category, pole, doc_type)
        dest     = os.path.join(folder, filename)

        os.makedirs(folder, exist_ok=True)
        shutil.copy2(self.pdf_path.get(), dest)

        messagebox.showinfo("Succès ", f"Fichier enregistré :\n\n{dest}")
        self._reset()

    def _reset(self):
        self.pdf_path.set("")
        self.drop.config(text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
                         fg=GRAY, bg=LIGHT)
        self.date_var.set(date.today().isoformat())
        self._refresh_preview()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()