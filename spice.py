import ollama, json, re, time
from examples import *


PROMPT = """This form has two sections: first all the labels listed top to bottom, then all the values listed top to bottom in the same order.
Return JSON only, no explanation:
{"prenom_nom": ..., "date_demande": ..., "pole_activite": ..., "motif": ..., "montant_chf": ...}
"""

TEXT_MODEL = "gemma3:1b"
TEXT_MODEL_TOO_MUCH  = "gemma3:4b"   # text only, fast & light
IMAGE_MODEL = "moondream" 
TEXT_AND_IMAGE_MODEL = "llava"

def extract(text=None, image=None):
    model = IMAGE_MODEL if image else TEXT_MODEL
    msg = {"role": "user", "content": PROMPT + (text or "")}
    if image:
        msg["images"] = [image]
    r = ollama.chat(model=model, messages=[msg])
    raw = re.sub(r"```json|```", "", r["message"]["content"]).strip()
    return raw


# ── Examples ──────────────────────────────────────────────────────────────────

start_time = time.time()
for ex in EXAMPLES:
    print()
    print(ex)
    print(extract(text=ex))
delta = time.time() - start_time
print("--- %s seconds ---" % (delta))
print(f"for {len(EXAMPLES)} examples, so {delta/len(EXAMPLES)} on average")