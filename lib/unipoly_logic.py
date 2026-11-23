import os,re
from datetime import date
import sys

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(APP_DIR, "config")

DEBUG = 0
GNUCASH_RELATIVE = os.path.join("1 - Comptabilite", "Unipoly.gnucash")


def is_valid_repo(folder: str) -> bool:
    """A valid repo folder contains 1 - Comptabilite/Unipoly.gnucash"""
    return bool(folder) and os.path.isfile(os.path.join(os.path.expanduser(folder), GNUCASH_RELATIVE))


def set_config_line(index: int, value: str):
    """Write one line of the config file (0 = repo folder, 1 = pdf folder), keeping the other."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    defaults = ["", os.path.join(os.path.expanduser("~"), "Downloads") + "/"]
    while len(lines) <= max(index, 1):
        lines.append(defaults[len(lines)] if len(lines) < 2 else "")
    lines[index] = value
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _ask_repo_folder() -> str:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Unicompta", "Select the UPSecretrariat folder (the cloned repository).\n"
                                     f"It must contain: {GNUCASH_RELATIVE}")
    folder = filedialog.askdirectory(title="UPSecretrariat folder")
    root.destroy()
    return folder


def _load_base_dir() -> str:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            base = os.path.expanduser(f.readline().strip())
    except FileNotFoundError:
        base = ""
    changed = False
    while not is_valid_repo(base):          # missing config or wrong path -> ask instead of failing
        base = _ask_repo_folder()
        if not base:
            sys.exit(1)
        changed = True
    if not base.endswith(("/", "\\")):
        base += "/"
    if changed:
        set_config_line(0, base)
    return base


BASE_DIR = _load_base_dir()

BASE_DIR_OUTFLOW    = os.path.expanduser(BASE_DIR + ("4 - Justifications Sorties (S)/"))   # dossier racine
BASE_GNUCASH_FOLDER = os.path.expanduser( BASE_DIR +"1 - Comptabilite/")
GNUCASH_FILE        = os.path.expanduser(BASE_GNUCASH_FOLDER+"Unipoly.gnucash")
# if need to decompress we decompress into a temp file and delete it after
DECOMPRESSED_GNUCASH_FILE = GNUCASH_FILE + ".temp"
CHARGES_ACT_NAME    = "03-Charges"
ACT_PAYABLE_ACT_NAME = "02-01-Account Payables (AP)"
ACT_RECEIVABLE_ACT_NAME = "01-01-Account Receivables (AR)"
ACT_BANQUE_ACTIF = "01-02-01-Banque-Principal"
ACT_IMBALANCE = "Imbalance-CHF"
YEAR_CHANGE_MONTH=8
YEAR_CHANGE_DAY=31
YEAR_BUMP_S_C = 40
COMITE = "Comité"
GIT_BRANCH_NAME = "main"


# ── LOGIQUE DU DOSSIER ─────────────────────────────────────────────────────

def folder_for_year_category(d: date, category: str) -> str :
    y = d.year
    if d.month > YEAR_CHANGE_MONTH or (d.month == YEAR_CHANGE_MONTH and d.day > YEAR_CHANGE_DAY):
        y_str = f"{str(y)}-{str(y + 1)}"
    else :
        y_str = f"{str(y - 1)}-{str(y)}"
    if category == COMITE:
        return os.path.join(BASE_DIR_OUTFLOW, y_str , COMITE)
    return os.path.join(BASE_DIR_OUTFLOW ,y_str , "Pôles")

def target_folder( d : date,category: str, pole: str, doc_type : str) -> str:
    doc_type_folder = "2 - DDR" if doc_type =="REMB" else "3 - Factures"
    return os.path.join( folder_for_year_category(d,category), pole,doc_type_folder)

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
    if DEBUG : print(f"date : {d},category : {category}, pole : {pole}, doc_type : {doc_type}")
    return f"{year_code(d)}-{pole_code(pole)}-{doc_type}-{n}.pdf"

# ── Search existing folders ────────────────────────────────────────────────

def get_poles( d: date,category: str) -> list[str]:
    """Return subfolder names under the relevant Pôles or Comité directory."""
    base = folder_for_year_category(d, category)
    if DEBUG : print("folder for year and category : " + base)
    if not os.path.exists(base):
        print(f"Path {base} does not exist")
        return []
    return sorted([
        f for f in os.listdir(base)
        if os.path.isdir(os.path.join(base, f))
    ])