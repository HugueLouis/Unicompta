import os,re
from datetime import date

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
    if category == "Comité":
        return os.path.join(BASE_DIR_OUTFLOW, ystr , "Comité")
    return os.path.join(BASE_DIR_OUTFLOW ,ystr , "Pôles")

def target_folder( d : date,category: str, pole: str, doc_type : str) -> str:
    doc_type_folder = "2 - DDR" if doc_type =="REMB" else "3 - FACT"
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