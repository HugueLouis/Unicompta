#!/usr/bin/env python3

import shutil
from datetime import date,timedelta
import tkinter as tk
import gzip
import magic
from tkinter import ttk, filedialog, messagebox
from lib.unipoly_logic import *
from lib.gnucash_utils import *
from decimal import Decimal
from pathlib import Path
from pdf2image import convert_from_path
from PIL import ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BASE = TkinterDnD.Tk
except ImportError:
    BASE = tk.Tk
    DND_FILES = None

DEFAULT_SECOND_COMPTA = True

# ── INTERFACE ─────────────────────────────────────────────────────────────────

BLUE   = "#2563EB"
LIGHT  = "#EFF6FF"
BORDER = "#CBD5E1"
TEXT   = "#1E293B"
GRAY   = "#64748B"
WHITE  = "#FFFFFF"
GREEN  = "#16A34A"

def clean_gnucash_folder():
    """ Delete all the files that aren't the gnucash file
    This is to get rid of all the locks"""
    for path in Path(BASE_GNUCASH_FOLDER).glob("*"):
        if path.resolve()==Path(GNUCASH_FILE).resolve() :
            continue
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)

class App(BASE):
    def __init__(self):
        super().__init__()
        self.session = gnucash.Session("xml://"+ GNUCASH_FILE)
        self.book = self.session.book
        self.root_act = self.book.get_root_account()
        self.act_payable_act = find_account_including(self.root_act,ACT_PAYABLE_ACT_NAME)
        self.act_receivable_act = find_account_including(self.root_act,ACT_RECEIVABLE_ACT_NAME) 
        self.charges_act = find_account_including(self.root_act,CHARGES_ACT_NAME)
        self.title("Dépôt PDF")
        self.configure(bg=WHITE)
        self.resizable(True, True)
        self.pdf_path = tk.StringVar()
        self.second_compta_var = tk.BooleanVar(value = DEFAULT_SECOND_COMPTA)
        self.option_add("*TCombobox*Listbox.font", ("Helvetica", 17))
        self.option_add("*TCombobox.font", ("Helvetica", 17))
        self._build()
        self._center()

    def _on_cat_change(self, *_):
        try:
            d = date.fromisoformat(self.date_var.get())
        except ValueError:
            d = date.today()
        # update poles scrolling
        poles = get_poles(d, self.cat_var.get())
        self.pole_combo["values"] = poles
        self.pole_var.set(poles[0] if poles else "")
        self._on_pole_change

    def _on_pole_change(self,*_):
        # update pole_charge_types scrolling
        if DEBUG: print( f"from {self.charges_act.GetName()} searching for : {"(" + pole_code(self.pole_var.get())+")"}")
        self.charge_pole_act = find_account_including(self.charges_act,"(" + pole_code(self.pole_var.get())+")")
        pole_charge_types_str = list_all_accounts_accumulate(self.charge_pole_act)
        self.pole_charge_type_var_combo["values"] = pole_charge_types_str
        self.pole_charge_type_var_str.set(pole_charge_types_str[0] if pole_charge_types_str else "")
        self._refresh_preview()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=WHITE, sashwidth=4)
        paned.pack(fill="both", expand=True)

        # Left: form
        outer = tk.Frame(paned, bg=WHITE, padx=28, pady=24)
        paned.add(outer, minsize=480)

        # Right: PDF preview
        right = tk.Frame(paned, bg=LIGHT, padx=8, pady=8)
        paned.add(right, minsize=300)
        self._build_preview_panel(right)

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

        # For what type of charge in the pole 
        self.pole_charge_type_var_str = tk.StringVar()
        self.pole_charge_type_var_combo = ttk.Combobox(
            form, textvariable=self.pole_charge_type_var_str, state="readonly", width=40)
        self._field(form, 3, "Type of charge of pole", self.pole_charge_type_var_combo)
        # Update the type of charge type when date or category changes
        self.pole_var.trace_add("write", self._on_pole_change)
        
        # Description
        self.desc_var = tk.StringVar()
        self._field(form, 4, "Name + Description", tk.Entry(
            form, textvariable=self.desc_var, **self._entry_kw(width=40)))

        # Type of charge
        self.type_var = tk.StringVar(value="REMB")
        self._field(form, 5, "Charge", ttk.Combobox(
            form, textvariable=self.type_var,
            values=["REMB", "FACT"], state="readonly", width=10))

        # Amount
        self.amount_var = tk.StringVar()
        self._field(form, 6, "Montant (chf)", tk.Entry(
            form, textvariable=self.amount_var, **self._entry_kw(width=14)))
        
        # Second inscription compta
        self.checkButton_secondCompta = tk.Checkbutton( 
            form,
            variable = self.second_compta_var , 
            onvalue = True, 
            offvalue = False, 
            height = 2, 
            width = 5,
            font= ("Helvetica", 15, "bold")
            )
        self._field(form,7,"Inscrire la second comptabilité",self.checkButton_secondCompta)

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
        # End button
        btn_end = tk.Button(
            outer, text="  Fermer  ", command=lambda: exit(),
            bg=BLUE, fg=WHITE, activebackground="#D8811D", activeforeground=WHITE,
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=14, pady=8, cursor="hand2", bd=0, width=20, height=5
        )
        btn.pack(pady=(15, 15),padx=(150, 50),side = tk.LEFT)
        btn_end.pack(pady=(15, 15),padx=(30, 50),side = tk.LEFT)
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
        self._load_pdf_preview(path)

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

        category = self.cat_var.get()
        pole     = self.pole_var.get()
        doc_type = self.type_var.get()
        amount = Decimal(str(self.amount_var.get()))
        folder   = target_folder(d,category, pole,doc_type)
        filename = build_filename(d, category, pole, doc_type)
        description = filename[:-len(".pdf")] + " " + self.desc_var.get()
        dest     = os.path.join(folder, filename)

        os.makedirs(folder, exist_ok=True)
        shutil.copy2(self.pdf_path.get(), dest)
        messagebox.showinfo("Succès ", f"Fichier enregistré :\n\n{dest}")
        
        # check if the file is compressed or not 
        type_of_gnucashfile = magic.from_file(GNUCASH_FILE)
        # if it is compressed the decompress it
        if "gzip" in type_of_gnucashfile : 
            # decompress
            with gzip.open(GNUCASH_FILE, "rb") as f_in:
                with open(DECOMPRESSED_GNUCASH_FILE, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    os.replace(DECOMPRESSED_GNUCASH_FILE, GNUCASH_FILE)

        print(description)
        type_pole_charge_act = find_account_including(self.charge_pole_act, self.pole_charge_type_var_str.get())
        add_transaction(self.book,self.act_payable_act,type_pole_charge_act,amount,description,d)
        if DEBUG : 
            print("second compta var on submit : "+ str(self.second_compta_var))
            print("account receivable on submit : " +self.act_receivable_act.GetName())
        if self.second_compta_var :
            add_transaction(self.book,self.act_receivable_act,self.act_payable_act,amount,description,d + timedelta(5))
            
        self.session.save()
        self._reset()

    def _reset(self):
        self.pdf_path.set("")
        self.desc_var.set("")
        self.drop.config(text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
                         fg=GRAY, bg=LIGHT)
        self.date_var.set(date.today().isoformat())
        self._refresh_preview()

    def _close(self): 
        self.session.save()
        self.session.end()
        clean_gnucash_folder()
        exit()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_preview_panel(self, parent):
        tk.Label(parent, text="Aperçu PDF", font=("Helvetica", 13, "bold"),
                bg=LIGHT, fg=TEXT).pack(anchor="w", pady=(0, 6))

        # Navigation row
        nav = tk.Frame(parent, bg=LIGHT)
        nav.pack(fill="x", pady=(0, 4))
        self._prev_btn = tk.Button(nav, text="◀", command=self._prev_page,
                                state="disabled", relief="flat", bg=LIGHT)
        self._prev_btn.pack(side="left")
        self._page_label = tk.Label(nav, text="", bg=LIGHT, font=("Helvetica", 11))
        self._page_label.pack(side="left", padx=8)
        self._next_btn = tk.Button(nav, text="▶", command=self._next_page,
                                state="disabled", relief="flat", bg=LIGHT)
        self._next_btn.pack(side="left")

        # Canvas for the page image
        self._pdf_canvas = tk.Canvas(parent, bg="#e2e8f0", highlightthickness=0)
        self._pdf_canvas.pack(fill="both", expand=True)
        self._pdf_canvas.bind("<Configure>", self._on_canvas_resize)

        # Internal state
        self._pdf_pages = []
        self._pdf_page_idx = 0
        self._pdf_tk_img = None

    def _load_pdf_preview(self, path):
        try:
            # Render at a reasonable DPI; lower = faster
            self._pdf_pages = convert_from_path(path, dpi=120)
            self._pdf_page_idx = 0
            self._show_current_page()
        except Exception as e:
            self._pdf_canvas.delete("all")
            self._pdf_canvas.create_text(10, 10, anchor="nw",
                text=f"Aperçu indisponible:\n{e}", fill=GRAY)

    def _show_current_page(self):
        if not self._pdf_pages:
            return
        idx = self._pdf_page_idx
        total = len(self._pdf_pages)

        self._page_label.config(text=f"Page {idx+1} / {total}")
        self._prev_btn.config(state="normal" if idx > 0 else "disabled")
        self._next_btn.config(state="normal" if idx < total-1 else "disabled")
        self._render_page()

    def _render_page(self):
        if not self._pdf_pages:
            return
        canvas = self._pdf_canvas
        cw = canvas.winfo_width() or 300
        ch = canvas.winfo_height() or 400

        img = self._pdf_pages[self._pdf_page_idx].copy()
        img.thumbnail((cw, ch))   # fits inside canvas, keeps aspect ratio

        self._pdf_tk_img = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._pdf_tk_img)

    def _on_canvas_resize(self, _=None):
        self._render_page()   # re-fit on window resize

    def _prev_page(self):
        self._pdf_page_idx -= 1
        self._show_current_page()

    def _next_page(self):
        self._pdf_page_idx += 1
        self._show_current_page()

# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.isdir(BASE_DIR):
        print("The config file should contain a valid path to the folder UPSecretrariat.") 
        exit()
    clean_gnucash_folder()
    try :
        app = App()
        app.mainloop()
    finally :
        # in any scenario we want to make sure that the folder is clean and the session is saved + ended
        App._close(app)
        
