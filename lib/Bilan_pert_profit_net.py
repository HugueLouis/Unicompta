#!/usr/bin/env python3
"""
Bilan net (Profit - Perte) du Comité et des Pôles d'activité.

Usage :
    python bilan_net.py bilan_2526
    python bilan_net.py bilan_2526 --export resultat.csv
    python bilan_net.py bilan_2526 --graphs graphiques   # génère les PNG (nécessite matplotlib)
    # Le fichier csv est obtenu en exportant le compte bilan de l'année
Principe : dans l'export GnuCash, chaque écriture de clôture a deux lignes.
On lit la ligne côté compte de fonds (02-Passifs:...:Comité ou Pôles d'activité) :
    montant > 0  ->  Profit (produits versés au fonds)
    montant < 0  ->  Perte  (charges prélevées sur le fonds)
Le bilan net d'un compte = somme de ses montants = Profit - Perte.
"""
import argparse
import re
import sys

import os

import pandas as pd

GROUPES = {
    "Comité": "02-00-01-Comité",
    "Pôles d'activité": "02-00-02-Pôles d'activité",
}


BUDGET = {
    "Evènementiel":50,
    "Cohésion":50,
    "Contribution Pôles":50,
    "Fonctionnement":50,
    "La convergence":50,
    "Local":50,
    "Logistique":50,
    "Mobility":50,
    "Reprographie EPFL":50,
    "Rebuilt":50,
    "Extraordinaire":50,
    "Apiculture":50,
    "Canard Huppé":50,
    "Castor Freegan":50,
    "E.D.A.":50,
    "Ingénieures Engagées":50,
    "Jardin":50,
    "Semaine de la durabilité":50,
    "UP Fashion Lab":50,
    "Fix N' Replace":50,
    "ScobyPoly":50,
    "CLUB(CLUB)":50,
    }

def nom_compte(full_name: str) -> str:
    """Extrait le nom lisible du sous-compte (ex: 'Evènementiel (EVENT)')."""
    m = re.search(r">-\d+-\d+-([^:]+)", full_name)
    return m.group(1).strip() if m else full_name.split(":")[-1].strip()


def charger(chemin: str) -> pd.DataFrame:
    df = pd.read_csv(chemin, thousands=",", encoding="utf-8-sig")
    df["Montant"] = pd.to_numeric(df["Amount Num."], errors="coerce")
    lignes = []
    for groupe, prefixe in GROUPES.items():
        sel = df[df["Full Account Name"].str.contains(prefixe, regex=False, na=False)].copy()
        sel["Groupe"] = groupe
        sel["Compte"] = sel["Full Account Name"].map(nom_compte)
        lignes.append(sel)
    return pd.concat(lignes, ignore_index=True)


def bilan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(
        Profit=df["Montant"].clip(lower=0),
        Perte=(-df["Montant"]).clip(lower=0),
    )
    res = (
        df.groupby(["Groupe", "Compte"], sort=False)[["Profit", "Perte"]]
        .sum()
        .assign(Net=lambda x: x["Profit"] - x["Perte"])
        .round(2)
        .reset_index()
    )
    return res


def afficher(res: pd.DataFrame) -> None:
    fmt = lambda v: f"{v:>12,.2f}".replace(",", "'")
    largeur = 34 + 3 * 13
    for groupe in GROUPES:
        sous = res[res["Groupe"] == groupe]
        if sous.empty:
            continue
        print(f"\n{groupe.upper()}")
        print("-" * largeur)
        print(f"{'Compte':<34}{'Profit':>13}{'Perte':>13}{'Net':>13}")
        print("-" * largeur)
        for _, r in sous.iterrows():
            print(f"{r['Compte'][:33]:<34} {fmt(r['Profit'])} {fmt(r['Perte'])} {fmt(r['Net'])}")
        print("-" * largeur)
        print(f"{'TOTAL ' + groupe:<34} {fmt(sous['Profit'].sum())} {fmt(sous['Perte'].sum())} {fmt(sous['Net'].sum())}")

    print("\n" + "=" * largeur)
    print(f"{'BILAN NET GLOBAL (CHF)':<34} {fmt(res['Profit'].sum())} {fmt(res['Perte'].sum())} {fmt(res['Net'].sum())}")
    print("=" * largeur)


def graphiques(res: pd.DataFrame, dossier: str) -> list:
    """Génère les graphiques PNG et retourne la liste des fichiers créés."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(dossier, exist_ok=True)
    VERT, ROUGE, NOIR, ORANGE = "#2e9e5b", "#db3b30", "#0E0D0D", "#F88F39"
    groupes = [g for g in GROUPES if not res[res["Groupe"] == g].empty]
    fichiers = []

    def etiquette(ax, barres, valeurs):
        for b, v in zip(barres, valeurs):
            ax.annotate(f"{v:,.0f}".replace(",", "'"),
                        (b.get_width(), b.get_y() + b.get_height() / 2),
                        xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                        ha="left" if v >= 0 else "right", va="center", fontsize=8)
            
    tot = res.groupby("Groupe", sort=False)[["Profit", "Perte", "Net"]].sum()
    tot.loc["Global"] = tot.sum()

     # 2) Profit / Perte / Net par compte (un graphique par groupe)
    fig, axes = plt.subplots(len(groupes), 1, figsize=(10, 6.2 * len(groupes)),
                             squeeze=False)
    for ax, g in zip(axes[:, 0], groupes):
        d = res[res["Groupe"] == g].reset_index(drop=True)
        noms = [c.split(" (")[0].strip() for c in d["Compte"]]
        budget = [BUDGET.get(n, 0) for n in noms]   # 0 si le compte n'est pas dans BUDGET
        manquants = [n for n in noms if n not in BUDGET]
        if manquants:
            print(f"Attention : pas de budget défini pour {manquants}")

        x = list(range(len(d)))
        w = 0.185
        start = - 1.5 # -1.5 fois ecartement
        ax.bar([i + start       * w for i in x], d["Profit"], w, label="Profit", color=VERT)
        ax.bar([i + (start + 1) * w for i in x], d["Perte"],  w, label="Perte",  color=ROUGE)
        ax.bar([i + (start + 2) * w for i in x], d["Net"],    w, label="Net",    color=NOIR)
        ax.bar([i + (start + 3) * w for i in x], budget,      w, label="Budget", color=ORANGE)
        ax.axhline(0, color=NOIR, lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(noms, rotation=35, ha="right", fontsize=10)
        ax.set_title(g, loc="left", fontweight="bold")
        ax.set_ylabel("CHF")
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    f = os.path.join(dossier, "2_profit_vs_perte.png")
    fig.savefig(f, dpi=150); plt.close(fig); fichiers.append(f)

    return fichiers


def main() -> None:
    p = argparse.ArgumentParser(description="Bilan net Pôles / Comité (Profit - Perte)")
    p.add_argument("fichier", help="CSV exporté de GnuCash")
    p.add_argument("--export", help="Chemin d'un CSV de sortie (optionnel)")
    p.add_argument("--graphs", metavar="DOSSIER", help="Dossier où générer les graphiques PNG")
    args = p.parse_args()

    try:
        df = charger(args.fichier)
    except Exception as e:
        sys.exit(f"Erreur de lecture : {e}")

    res = bilan(df)
    afficher(res)

    if args.export:
        res.to_csv(args.export, index=False, encoding="utf-8-sig")
        print(f"\nRésultat exporté dans {args.export}")

    if args.graphs:
        for f in graphiques(res, args.graphs):
            print(f"Graphique : {f}")


if __name__ == "__main__":
    main()