import ollama, json, re, time

PROMPT = """same order
Return JSON for these fields, no explanation:
{"name", "date", "description", "amount"}
"""
COMMON=["*Si ce n′est pas votre première demande, ces champs ne sont pas obligatoires.<3",
        "*Si ce n′est pas votre première demande, ces champs ne sont pas obligatoires. <3",
        "NPA, Localité * :",
        "IBAN * :",
        "Signature :", "Pôle d′activité :","Date de la demande :", "Prénom NOM :","Motif :",
        "Montant(CHF) :","Demande de Remboursement"]

TEXT_MODEL = "gemma3:1b"
ML_NONE = (None, None, None, None)


def remove_substrings(main_string, substrings = COMMON):
    for sub in substrings:
        main_string = main_string.replace(sub, "")
    return main_string

def extract(text=None):
    msg = {"role": "user", "content": PROMPT + text}
    r = ollama.chat(model=TEXT_MODEL, messages=[msg],format="json")
    raw = re.sub(r"```json|```", "", r["message"]["content"]).strip()
    return raw

def filtered_extract(text=None):
    """
    returns the tupple (name, date, description, amount)
    """
    f_text = remove_substrings(text)
    raw = extract(f_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ML_NONE
    return (
        data.get("name"),
        "-".join(reversed(data.get("date").replace("/","-").replace(".","-").split("-"))),
        data.get("description"),
        data.get("amount"),
    )