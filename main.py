#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import date,timedelta
import tkinter as tk
import gzip , shutil, magic, fitz
from tkinter import ttk, filedialog, messagebox
from lib.unipoly_logic import *
from lib.gnucash_utils import *
from lib.ML import *
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
PREFIX_DESC_SECOND_COMPTA = "n*2 "

# ── INTERFACE ─────────────────────────────────────────────────────────────────

BLUE   = "#2563EB"
LIGHT  = "#EFF6FF"
BORDER = "#CBD5E1"
TEXT   = "#1E293B"
GRAY   = "#64748B"
WHITE  = "#FFFFFF"
GREEN  = "#16A34A"

def dprint(str):
    if DEBUG : print(str)

def get_default_pdf_folder():
    with open(CONFIG_FILE) as f :
        lines = f.readlines()
    if len(lines)>=2 :
        folder = os.path.expanduser(lines[1].strip())
    else :
        folder = "."
    if folder[-1] != '/' : folder += '/'
    return folder

def set_default_pdf_folder(folder: str):
    folder = os.path.expanduser(folder)
    with open(CONFIG_FILE, "r") as f:
        lines = f.readlines()
    while len(lines) < 2:
        lines.append("\n")
    lines[0] = BASE_DIR + "\n"
    lines[1] = folder + "\n"
    with open(CONFIG_FILE, "w") as f:
        f.writelines(lines)

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
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.book = self.session.book
        self.root_act = self.book.get_root_account()
        self.act_payable_act = find_account_including(self.root_act,ACT_PAYABLE_ACT_NAME)
        self.act_receivable_act = find_account_including(self.root_act,ACT_RECEIVABLE_ACT_NAME) 
        self.charges_act = find_account_including(self.root_act,CHARGES_ACT_NAME)
        self.transactions = []
        self.pdf_folder = tk.StringVar(value=get_default_pdf_folder())
        self.pdf_default_folder_var = tk.StringVar(value=get_default_pdf_folder())
        self.title("Dépôt PDF")
        self.configure(bg=WHITE)
        self.resizable(True, True)
        self.supposed_answers = {}
        self.pdf_path = tk.StringVar()
        self.second_compta_var = tk.BooleanVar(value = DEFAULT_SECOND_COMPTA)
        self.option_add("*TCombobox*Listbox.font", ("Helvetica", 17))
        self.option_add("*TCombobox.font", ("Helvetica", 17))
        self._build()
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - self.winfo_width()) // 2}+{(sh - self.winfo_height()) // 2}")

    def _on_cat_change(self, *_):
        try:
            d = date.fromisoformat(self.date_var.get())
        except ValueError:
            d = date.today()
        # update poles scrolling
        poles = get_poles(d, self.cat_var.get())
        self.pole_combo["values"] = poles
        self.pole_var.set("")

    def _on_pole_change(self,*_):
        # update pole_charge_types scrolling
        dprint(lambda: f"from {self.charges_act.GetName()} searching for : {"(" + pole_code(self.pole_var.get())+")"}")
        if not self.pole_var.get() == "":
            self.charge_pole_act = find_account_including(self.charges_act,"(" + pole_code(self.pole_var.get())+")")
            pole_charge_types_str = list_all_accounts_accumulate(self.charge_pole_act)
            self.pole_charge_type_var_combo["values"] = pole_charge_types_str
        self.pole_charge_type_var_str.set("") 

    def _btn(self, parent, text, cmd, bg=BLUE, fg=WHITE, **kw):
        return tk.Button(parent, text=text, command=cmd,
            bg=bg, fg=fg, font=("Helvetica", 11, "bold"),
            relief="flat", padx=14, pady=8, cursor="hand2", bd=0, **kw)

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

        # -- Folder picker row --
        folder_row = tk.Frame(outer, bg=WHITE)
        folder_row.pack(fill="x", pady=(0, 10))

        tk.Label(folder_row, text="Dossier PDF :", font=("Helvetica", 13),
                bg=WHITE, fg=TEXT).pack(side="left")
        tk.Label(folder_row, textvariable=self.pdf_default_folder_var,
                font=("Helvetica", 11), fg=GRAY, bg=WHITE).pack(side="left", padx=8)
        self._btn(folder_row, "Choisir…", self._pick_folder).pack(side="left")



        # -- PDF list --
        pdfs_headers = tk.Frame(outer, bg=WHITE)
        pdfs_headers.pack(fill="x")
        tk.Label(pdfs_headers, text="Fichiers PDF", font=("Helvetica", 13, "bold"),
                bg=WHITE, fg=TEXT).pack(anchor="w", side = 'left')
        
        # -- Refresh button --
        self._btn(pdfs_headers, "🗘", self._refresh_pdf_list).pack(side="right")
        
        pdfs = tk.Frame(outer, bg=WHITE)
        pdfs.pack(fill="x")
        self.pdf_listbox = tk.Listbox(pdfs, font=("Helvetica", 12), relief="solid",
                                    bd=1, height=6, selectmode="single")
        self.pdf_listbox.pack(fill="x", pady=(0, 10))
        self.pdf_listbox.bind("<<ListboxSelect>>", self._on_pdf_select)
        self._refresh_pdf_list()


        # --- Drag and drop zone
        self.drop = tk.Label(
            outer,
            text="📄  drag and drop PDF here\n\n Or click to browse",
            font=("Helvetica", 11), fg=GRAY, bg=LIGHT,
            cursor="hand2", padx=20, pady=10, width=80, height=2,
        )
        self.drop.pack()
        self.drop.bind("<Button-1>", self._pick)
        self.drop.bind("<Enter>", lambda e: self.drop.config(bg="#DBEAFE"))
        self.drop.bind("<Leave>", lambda e: self.drop.config(bg=LIGHT))

        if DND_FILES:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)

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
                
        # Name
        self.name_var = tk.StringVar()
        self._field(form, 4, "Nom", tk.Entry(
            form, textvariable=self.name_var, **self._entry_kw(width=40)))

        # Description
        self.desc_var = tk.StringVar()
        self._field(form, 5, "Description", tk.Entry(
            form, textvariable=self.desc_var, **self._entry_kw(width=40)))

        # Type of charge
        self.type_var = tk.StringVar(value="REMB")
        self._field(form, 6, "Charge", ttk.Combobox(
            form, textvariable=self.type_var,
            values=["REMB", "FACT"], state="readonly", width=10))

        # Amount
        self.amount_var = tk.StringVar()
        self._field(form, 7, "Montant (chf)", tk.Entry(
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
        self._field(form,8,"Inscrire la second comptabilité",self.checkButton_secondCompta)

        # Filename preview
        self.preview_var = tk.StringVar(value="")
        self.preview_lbl = tk.Label(outer, textvariable=self.preview_var,
                                    font=("Helvetica", 18), fg=TEXT, bg=WHITE)
        self.preview_lbl.pack(anchor="w")

        for v in (self.pole_var, self.type_var):
            v.trace_add("write", self._refresh_preview)
        self._refresh_preview()

        # Submit button
        btn = self._btn(outer, "  Déposer  ", self._submit, width=20, height=5)
        btn.pack(pady=(15, 15),padx=(150, 50),side = tk.LEFT)
        
        # End button
        btn_end = self._btn(outer, "  Fermer  ", lambda: exit() , activebackground="#D8811D", width=20, height=5)
        btn_end.pack(pady=(15, 15),padx=(30, 50),side = tk.LEFT)
        self._on_cat_change()  # populate on startup
        self._build_transaction_panel(paned)

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
        path = filedialog.askopenfilename(
            initialdir=self.pdf_default_folder_var.get(),   # ← add this
            filetypes=[("PDF", "*.pdf")]
        )
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
        self._reset()
        if path in self.supposed_answers and self.supposed_answers[path] != None :
            ans = self.supposed_answers[path]
            self.name_var.set(ans[0])
            self.date_var.set(ans[1])
            self.desc_var.set(ans[2])
            self.amount_var.set(ans[3])
            
        self.pdf_path.set(path)
        name = os.path.basename(path)
        self.drop.config(text=f"✅  {name}", fg=GREEN, bg="#F0FDF4")
        self._refresh_preview()
        self._load_pdf_preview(path)

    def _suppose_worker(self,path):
        dprint(lambda:f"[suppose_worker] started for '{path}'")
        def extract_all_text(path) -> str:
            """Return concatenated text from every page of the loaded PDF."""
            if path :
                _pdf_doc = fitz.open(path)
            else : 
                _pdf_doc = self._pdf_doc
            return "" if not _pdf_doc else "\n".join(
                _pdf_doc[i].get_text("text")
                for i in range(len(_pdf_doc))
        )
        full_text = extract_all_text(path)
        results =  filtered_extract(full_text)
        self.after(0, lambda: self._update_ui(results,path))

    def _suppose_async(self, path):
        self.executor.submit(self._suppose_worker, path)

    def _update_ui(self, results, path):
        self.supposed_answers[path] = results

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
        date_split = None
        if not self.pdf_path.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier PDF.")
            return
        try:
            # adaptive date selection (- / .) (EU standard or US)
            date_split = self.date_var.get().replace("/","-").replace(".","-").split("-")
            if len(date_split[0])!=4 :
                date_split = reversed(date_split) 
            d = date.fromisoformat("-".join(date_split))
        except ValueError:
            messagebox.showerror("Erreur", "Format de date invalide.\nUtilisez YYYY-MM-DD.")
            return

        category = self.cat_var.get()
        pole     = self.pole_var.get()
        doc_type = self.type_var.get()
        # adaptive matching of the amount input (, or .)
        amount_match = re.search(r"-?\d+(\.\d+)?", self.amount_var.get().replace(",","."))
        amount = Decimal(str(amount_match.group(0)))        
        folder   = target_folder(d,category, pole,doc_type)
        filename = build_filename(d, category, pole, doc_type)
        description = filename[:-len(".pdf")] + " " + self.name_var.get() + " " + self.desc_var.get()
        source = self.pdf_path.get()
        dest     = os.path.join(folder, filename)
        # prints in the google sheet format (filename name date amount) with tabs between each, newline to change line
        google_sheet_line = filename[:-len(".pdf")] + "\t" + self.name_var.get() + "\t"
        date_split = self.date_var.get().replace("-","/").replace(".","/").split("/")
        if len(date_split[0])==4 :
            date_split = reversed(date_split) 
        google_sheet_line += "/".join(date_split) + "\t" + amount_match.group(0)


        # copy and rename to the right folder
        os.makedirs(folder, exist_ok=True)
        shutil.copy2(source, dest)
        messagebox.showinfo("Succès ", f"Fichier enregistré :\n\n{dest}")

        # Rename the original source file
        source_dir = os.path.dirname(source)
        new_source_path = os.path.join(source_dir, filename)
        os.rename(source, new_source_path)

        # check if the file is compressed or not if it is compressed the decompress it
        if "gzip" in  magic.from_file(GNUCASH_FILE) : 
            # decompress
            with gzip.open(GNUCASH_FILE, "rb") as f_in:
                with open(DECOMPRESSED_GNUCASH_FILE, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    os.replace(DECOMPRESSED_GNUCASH_FILE, GNUCASH_FILE)

        print("Inserted     "+ description)
        type_pole_charge_act = find_account_including(self.charge_pole_act, self.pole_charge_type_var_str.get())
        tx = add_transaction(self.book,self.act_payable_act,type_pole_charge_act,amount,description,d)
        self.transactions.append((description, tx, dest, google_sheet_line))
        self.tx_listbox.insert("end", description)
        if DEBUG : 
            dprint(lambda:"second compta var on submit : "+ str(self.second_compta_var.get()))
            dprint(lambda:"account receivable on submit : " +self.act_receivable_act.GetName())
        if self.second_compta_var.get() :
            tx_2_desc =  PREFIX_DESC_SECOND_COMPTA + description
            print("Inserted "+ tx_2_desc)
            tx_2 = add_transaction(self.book,self.act_receivable_act,self.act_payable_act,amount,description,d + timedelta(5))
            self.transactions.append((tx_2_desc, tx_2, None, None)) # Don't add filename because the file is already set on the first
            self.tx_listbox.insert("end", tx_2_desc)
        self.session.save()
        self._reset()

    def _reset(self):
        self.pdf_path.set("")
        self.name_var.set("")
        self.desc_var.set("")
        self.drop.config(text="📄  Glisser-déposer un PDF ici\n\nou cliquer pour choisir",
                         fg=GRAY, bg=LIGHT)
        self.amount_var.set("")
        self.date_var.set(date.today().isoformat())

    def _close(self): 
        self.session.save()
        self.session.end()
        self.executor.shutdown(wait=False,cancel_futures=True)
        clean_gnucash_folder()
        for (_, _, _, t) in self.transactions :
            if t != None :
                print(t)
        exit()

    def _build_preview_panel(self, parent):
        # Internal state
        self._pdf_pages = []       # PIL images (for image view)
        self._pdf_doc = None       # fitz.Document (for text view)
        self._pdf_page_idx = 0
        self._pdf_tk_img = None
        self._view_mode = tk.StringVar(value="image")

        tk.Label(parent, text="Aperçu PDF", font=("Helvetica", 13, "bold"),
                bg=LIGHT, fg=TEXT).pack(anchor="w", pady=(0, 6))

        nav = tk.Frame(parent, bg=LIGHT)
        nav.pack(fill="x", pady=(0, 4))
        self._prev_btn = self._btn(nav, "◀", lambda: self._turn_page(-1), bg=LIGHT, fg=TEXT, state="disabled")
        self._next_btn = self._btn(nav, "▶", lambda: self._turn_page(1),  bg=LIGHT, fg=TEXT, state="disabled")
        self._prev_btn.pack(side="left")
        self._next_btn.pack(side="left")
        self._page_label = tk.Label(nav, text="", bg=LIGHT, font=("Helvetica", 11))
        self._page_label.pack(side="left", padx=8)

        # Toggle button between image and text view
        toggle_frame = tk.Frame(parent, bg=LIGHT)
        toggle_frame.pack(fill="x", pady=(0, 4))
        tk.Radiobutton(toggle_frame, text="Image", variable=self._view_mode,
                    value="image", bg=LIGHT, command=self._switch_view).pack(side="left")
        tk.Radiobutton(toggle_frame, text="Texte (copiable)", variable=self._view_mode,
                    value="text", bg=LIGHT, command=self._switch_view).pack(side="left", padx=8)

        # Container holds both widgets; only one is visible at a time
        self._preview_container = tk.Frame(parent, bg="#e2e8f0")
        self._preview_container.pack(fill="both", expand=True)

        # Image view
        self._pdf_canvas = tk.Canvas(self._preview_container, bg="#e2e8f0", highlightthickness=0)
        self._pdf_canvas.bind("<Configure>", self._render_page)

        # Text view — selectable, copy-paste works natively
        self._pdf_text = tk.Text(
            self._preview_container,
            wrap="word",
            font=("Helvetica", 11),
            relief="flat",
            bg="#fafafa",
            padx=12, pady=12,
            state="disabled",   # read-only but still selectable
        )
        # Scrollbar for text view
        self._text_scroll = tk.Scrollbar(self._preview_container, command=self._pdf_text.yview)
        self._pdf_text.configure(yscrollcommand=self._text_scroll.set)

        # Show image view by default
        self._switch_view()

    def _switch_view(self):
        mode = self._view_mode.get()
        if mode == "image":
            self._pdf_text.pack_forget()
            self._text_scroll.pack_forget()
            self._pdf_canvas.pack(fill="both", expand=True)
            self._render_page()
        else:
            self._pdf_canvas.pack_forget()
            self._text_scroll.pack(side="right", fill="y")
            self._pdf_text.pack(fill="both", expand=True)
            self._render_page_text()

    def _load_pdf_preview(self, path):
        try:
            # Image rendering (existing)
            self._pdf_pages = convert_from_path(path, dpi=120)
            # Text extraction (new)
            self._pdf_doc = fitz.open(path)
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
        if self._view_mode.get() == "text":
            self._render_page_text()

    def _render_page(self, event=None):
        if not self._pdf_pages:
            return
        canvas = self._pdf_canvas
        cw = canvas.winfo_width() or 300
        ch = canvas.winfo_height() or 400

        img = self._pdf_pages[self._pdf_page_idx].copy()
        img.thumbnail((cw, ch))
        self._pdf_tk_img = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._pdf_tk_img)


    def _render_page_text(self):
        if not self._pdf_doc:
            return
        page = self._pdf_doc[self._pdf_page_idx]
        text = page.get_text("text")

        self._pdf_text.configure(state="normal")
        self._pdf_text.delete("1.0", "end")
        self._pdf_text.insert("1.0", text)
        self._pdf_text.configure(state="disabled")

    def _turn_page(self, delta):
        self._pdf_page_idx += delta
        self._show_current_page()

    def _build_transaction_panel(self, paned):
        frame = tk.Frame(paned, bg=WHITE, padx=12, pady=12)
        paned.add(frame, minsize=250)

        tk.Label(frame, text="Transactions", font=("Helvetica", 13, "bold"),
                bg=WHITE, fg=TEXT).pack(anchor="w", pady=(0, 6))

        self.tx_listbox = tk.Listbox(frame, font=("Helvetica", 11), relief="solid",
                                    bd=1, selectmode="single", width=35)
        self.tx_listbox.pack(fill="both", expand=True)
        self._btn(frame, "🗑 Supprimer", self._delete_selected,
                bg="#DC2626").pack(fill="x", pady=(8, 0))

    def _delete_selected(self):
        def delete_tx_i(i):
            desc, tx, filepath, _ = self.transactions[i]
            if messagebox.askyesno("Confirmer", f"Supprimer :\n{desc} ?"):
                delete_transaction(tx=tx)
                if filepath : 
                    os.remove(filepath)
                    next_desc, _, _, _ = self.transactions[i+1]
                    if desc in next_desc : #if the next transaction is the next compta
                        delete_tx_i(i+1)
                dprint(lambda:"Deleted "+ desc)
                self.session.save()
                self.transactions.pop(i)
                self.tx_listbox.delete(i)
        idx = self.tx_listbox.curselection()
        if not idx:
            messagebox.showwarning("Attention", "Sélectionnez une transaction.")
            return
        i = idx[0]
        delete_tx_i(i)

    def _pick_folder(self):
        folder = filedialog.askdirectory(initialdir=self.pdf_default_folder_var.get())
        dprint(lambda:f"[pick_folder] selected = '{folder}'")
        if folder:
            self.pdf_default_folder_var.set(folder)
            set_default_pdf_folder(folder)
            self.supposed_answers.clear()
            self.executor.shutdown(wait=False,cancel_futures=True)  # Wait for pending tasks
            self.executor = ThreadPoolExecutor(max_workers=1)
            self._refresh_pdf_list()

    def _refresh_pdf_list(self):
        self.pdf_listbox.delete(0, "end")
        folder = self.pdf_default_folder_var.get()
        dprint(lambda:f"[refresh] folder = '{folder}'")
        dprint(lambda:f"[refresh] is_dir = {os.path.isdir(folder)}")
        if os.path.isdir(folder):
            pdfs = sorted(Path(folder).glob("*.pdf"))
            dprint(lambda:f"[refresh] found {len(pdfs)} PDFs: {[p.name for p in pdfs]}")
            for p in pdfs:
                self.pdf_listbox.insert("end", p.name)
                full_path = os.path.join(folder, p.name)
                if full_path not in self.supposed_answers:
                    self._suppose_async(full_path)
    def _on_pdf_select(self, _=None):
        idx = self.pdf_listbox.curselection()
        if not idx:
            return
        name = self.pdf_listbox.get(idx[0])
        path = os.path.join(self.pdf_default_folder_var.get(), name)
        self._set_file(path)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.isdir(BASE_DIR):
        print("The config file should contain a valid path to the folder UPSecretrariat.") 
        exit()
    clean_gnucash_folder()
    app = None
    try :
        app = App()
        app.mainloop()
    finally :
        # in any scenario we want to make sure that the folder is clean and the session is saved + ended
        app._close()
        
