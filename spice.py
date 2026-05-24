import ollama, json, re

PROMPT = """Extract these fields from the reimbursement form. Return JSON only, null for missing optional fields.

Fields: prenom_nom, npa_localite (optional), iban (optional), date_demande, pole_activite, motif, montant_chf

The text or image may be out of order — match labels to values by context.

"""

TEXT_MODEL  = "gemma3:4b"   # text only, fast & light
IMAGE_MODEL = "moondream" 
TEXT_AND_IMAGE_MODEL = "llava"

def extract(text=None, image=None):
    model = IMAGE_MODEL if image else TEXT_MODEL
    msg = {"role": "user", "content": PROMPT + (text or "")}
    if image:
        msg["images"] = [image]
    r = ollama.chat(model=model, messages=[msg])
    raw = re.sub(r"```json|```", "", r["message"]["content"]).strip()
    return json.loads(raw)


# ── Examples ──────────────────────────────────────────────────────────────────

text_scrambled = """Prénom NOM :
NPA, Localité * : | IBAN * : | Date de la demande : | Pôle d′activité : | Motif : | Montant(CHF) :
John Doe | 1721 Garange | CH22 0385 3243 7278 3601 T | 14.09.2024 | Apiculture | Achat matériel apiculture | 129.0"""

print(json.dumps(extract(text=text_scrambled), indent=2, ensure_ascii=False))

# With image only  → uses moondream automatically:
# print(json.dumps(extract(image="form.jpg"), indent=2, ensure_ascii=False))

# With both text + image → moondream reads the image, gemma3 handles the text:
# print(json.dumps(extract(text=text_scrambled, image="form.jpg"), indent=2, ensure_ascii=False))