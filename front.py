#!/usr/bin/env python3

import os, re, shutil
from datetime import date
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BASE = TkinterDnD.Tk
except ImportError:
    BASE = tk.Tk
    DND_FILES = None

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

BASE_DIR_OUTFLOW = os.path.expanduser("~/Documents/UPSecretariat/4 - Justifications Sorties (S)")   # dossier racine


#TODO Change the way it chooses the folder of the pole inside Pole/Comite
#TODO
#TODO make it register a line in gnucash in addition to saving the file to the right place

POLES = {
    "Apiculture":    "API",
    "Bibliojets": "BIBLIO",
    "Canard huppé":  "CANARD",
    "Castor freegan":  "CASTOR",
    "CLUB":    "CLUB",
    "EVA/EDA/PBU":    "EVA",
    "Fix N Replace FNR":"(FNR)",
    "Ingénieur·e·s Engagé·e·s IE":"(IE)",
    "Jardin ":"(JARDIN)",
    "LowTech Lab ":"(LOWTECH)",
    "Meubléco ":"(MEUBLE)",
    "ScobyPoly ":"(SCOBY)",
    "Semaine de la durablité DUDU ":"(DUDU)",
    "UP Fashion Lab UPFL":"(UPFL)",
}   
POLES_COMITE = {
    "Charges extraordinaires (EXTRA)":"EXTRA",
    "Cohésion (COHE)":"COHE",
    "Communication (COM)":"COM",
    "Événementiel (EVENT)":"EVENT",
    "Fédérond (FED)":"FED",
    "Fonctionnement (FONCT)":"FONCT",
    "La Convergence (CONVER)":"CONVER",
    "Local (LOCAL)":"LOCAL",
    "Logistique (LOG)":"LOG",
    "Mobility (MOBILITY)":"MOBILITY",
    "On a les crocs (OALC)":"OALC",
    "Politique (POL)":"POL",
    "Reprographie (REPRO)":"REPRO",
}

# ── LOGIQUE DU DOSSIER ─────────────────────────────────────────────────────
def folder_outflow_for_year(d: date) -> str :
    y = d.year
    if d.month >= 9:
        return os.path.join(BASE_DIR_OUTFLOW, f"{str(y)}-{str(y + 1)}")
    return os.path.join(BASE_DIR_OUTFLOW, f"{str(y - 1)}-{str(y)}")

def target_folder(category: str, pole: str, d : date) -> str:
    if category == "comité":
        return os.path.join( folder_outflow_for_year(d) , "Comité", ... ) #TODO
    return os.path.join( folder_outflow_for_year(d) , "Pôles", ... )

# ── LOGIQUE DU NOM ────────────────────────────────────────────────────

def year_code(d: date) -> str:
    """S2526 pour l'année académique 2025-2026."""
    y = d.year
    if d.month >= 9:
        return f"S{str(y)[2:]}{str(y + 1)[2:]}"
    return f"S{str(y - 1)[2:]}{str(y)[2:]}"

def pole_code(pole: str) -> str:
    return POLES.get(pole)

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
    folder = target_folder(category, pole)
    n      = next_number(folder)
    return f"{year_code(d)}-{pole_code(pole)}-{doc_type}-{n}.pdf"


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
        self.resizable(False, False)
        self.pdf_path = tk.StringVar()
        self._build()
        self._center()

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
            form, textvariable=self.date_var, **self._entry_kw()))

        # Catégorie
        self.cat_var = tk.StringVar(value="pôle")
        self._field(form, 1, "Catégorie", ttk.Combobox(
            form, textvariable=self.cat_var,
            values=["pôle", "comité"], state="readonly", width=14))

        # Pôle
        if (self.cat_var == "pôle"):
            self.pole_var = tk.StringVar(value=list(POLES.keys())[0])
            self._field(form, 2, "Pôle", ttk.Combobox(
            form, textvariable=self.pole_var,
            values=list(POLES.keys()), state="readonly", width=18))
        else :
            self.pole_var = tk.StringVar(value=list(POLES_COMITE.keys())[0])
            self._field(form, 2, "Pôle du comité", ttk.Combobox(
            form, textvariable=self.pole_var,
            values=list(POLES_COMITE.keys()), state="readonly", width=18))
        
        # Description
        self.desc_var = tk.StringVar(value=" pouet ...")
        self._field(form, 3, "Description", tk.Entry(
            form, textvariable=self.desc_var, **self._entry_kw(width=28)))

        # Type of charge
        self.type_var = tk.StringVar(value="REMB")
        self._field(form, 4, "Charge", ttk.Combobox(
            form, textvariable=self.type_var,
            values=["REMB", "FACT"], state="readonly", width=10))

        # Montant
        #self.amount_var = tk.StringVar(value="0")
        #self._field(form, 5, "Montant (chf)", tk.Entry(
        #    form, textvariable=self.amount_var, **self._entry_kw(width=14)))

        # Separator
        sep = tk.Frame(outer, height=1, bg=BORDER)
        sep.pack(fill="x", pady=16)

        # Drop zone
        self.drop = tk.Label(
            outer,
            text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
            font=("Helvetica", 11), fg=GRAY, bg=LIGHT,
            relief="flat", bd=0, cursor="hand2",
            width=36, height=6,
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
            cursor="hand2", padx=20, pady=16, width=32, height=5,
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
                                    font=("Courier", 9), fg=GRAY, bg=WHITE)
        self.preview_lbl.pack(anchor="w")

        for v in (self.date_var, self.cat_var, self.pole_var, self.type_var):
            v.trace_add("write", self._refresh_preview)
        self._refresh_preview()

        # Submit button
        btn = tk.Button(
            outer, text="  Déposer  ", command=self._submit,
            bg=BLUE, fg=WHITE, activebackground="#1D4ED8", activeforeground=WHITE,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", bd=0,
        )
        btn.pack(pady=(14, 0))

    def _field(self, parent, row, label, widget):
        tk.Label(parent, text=label, font=("Helvetica", 10),
                 bg=WHITE, fg=TEXT, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        widget.grid(row=row, column=1, sticky="w", pady=5)

    def _entry_kw(self, width=16):
        return dict(
            font=("Helvetica", 10), fg=TEXT, bg=WHITE,
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
            folder = target_folder(self.cat_var.get(), self.pole_var.get())
            self.preview_var.set(f"→  {os.path.join(folder, name)}")
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

        category = self.cat_var.get()
        pole     = self.pole_var.get()
        doc_type = self.type_var.get()
        folder   = target_folder(category, pole)
        filename = build_filename(d, category, pole, doc_type)
        dest     = os.path.join(folder, filename)

        os.makedirs(folder, exist_ok=True)
        shutil.copy2(self.pdf_path.get(), dest)

        messagebox.showinfo("Succès ✓", f"Fichier enregistré :\n\n{dest}")
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