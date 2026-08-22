"""Importa valutazioni piloti da una fonte esterna dentro data/drivers.json.

    python tools/import_ratings.py valutazioni.json --dry-run
    python tools/import_ratings.py valutazioni.json
    python tools/import_ratings.py valutazioni.json --formato diretto

Serve a mettere i numeri che ritieni giusti senza toccare il codice: quelli di
una stagione che hai visto, o quelli di un'altra fonte usata come controprova.

Due formati accettati.

**quattro** (predefinito) - le quattro categorie usate dai giochi ufficiali:

    {"verstappen": {"pace": 95, "racecraft": 94, "awareness": 92, "experience": 90},
     "norris":     {"pace": 94, "racecraft": 89, "awareness": 88, "experience": 82}}

Vengono tradotte negli otto attributi del gioco con le formule qui sotto, che
sono esplicite di proposito: se non ti convincono, si cambiano.

**diretto** - gli attributi del gioco, uno per uno, per il controllo totale:

    {"verstappen": {"pace": 97, "racecraft": 95, "consistency": 93,
                    "tyre_mgmt": 91, "wet": 97, "feedback": 90}}

In entrambi i casi si scrivono solo i piloti e i campi presenti nel file: tutto
il resto resta com'e'.

Nota sulle fonti: le valutazioni di un gioco commerciale sono un giudizio di
terzi, non un dato pubblico. Usarle come riferimento per una partita privata e'
una cosa, ridistribuirle e' un'altra: questo strumento legge un file che tieni
tu, e non porta con se' nessun dato altrui.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVERS = ROOT / "data" / "drivers.json"

# Come le quattro categorie diventano i nostri otto attributi. Ogni riga e' una
# somma pesata: "consistency" nasce soprattutto dalla lucidita' in pista, con
# un contributo dell'esperienza, e cosi' via.
FORMULE = {
    "pace":        {"pace": 1.00},
    "racecraft":   {"racecraft": 1.00},
    "consistency": {"awareness": 0.60, "experience": 0.40},
    "tyre_mgmt":   {"awareness": 0.50, "experience": 0.30, "racecraft": 0.20},
    "wet":         {"racecraft": 0.50, "experience": 0.30, "pace": 0.20},
    "feedback":    {"experience": 0.70, "awareness": 0.30},
}
# aggression, stamina e potential non hanno un corrispettivo nelle quattro
# categorie: restano quelli che sono, perche' inventarli sarebbe peggio.

NOSTRI = ("pace", "racecraft", "consistency", "tyre_mgmt", "wet", "feedback",
          "aggression", "stamina", "potential", "marketability")


def converti(voci: dict) -> dict:
    """Dalle quattro categorie agli otto attributi."""
    out = {}
    for nostro, pesi in FORMULE.items():
        tot = sum(pesi.values())
        somma = 0.0
        manca = False
        for chiave, peso in pesi.items():
            if chiave not in voci:
                manca = True
                break
            somma += float(voci[chiave]) * peso
        if not manca:
            out[nostro] = round(somma / tot, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="json con le valutazioni, per id pilota")
    ap.add_argument("--formato", choices=("quattro", "diretto"), default="quattro")
    ap.add_argument("--dry-run", action="store_true", help="mostra e non scrive")
    args = ap.parse_args()

    sorgente = Path(args.file)
    if not sorgente.exists():
        print(f"File non trovato: {sorgente}")
        return 1
    nuovi = json.loads(sorgente.read_text(encoding="utf-8"))

    data = json.loads(DRIVERS.read_text(encoding="utf-8"),
                      object_pairs_hook=collections.OrderedDict)
    per_id = {}
    for gruppo in ("drivers", "free_agents"):
        for d in data.get(gruppo, []):
            per_id[d["id"]] = d

    aggiornati, ignoti = 0, []
    for pid, voci in nuovi.items():
        drv = per_id.get(pid)
        if drv is None:
            ignoti.append(pid)
            continue
        campi = converti(voci) if args.formato == "quattro" else {
            k: float(v) for k, v in voci.items() if k in NOSTRI}
        if not campi:
            continue
        prima = {k: drv.get(k) for k in campi}
        drv.update(campi)
        aggiornati += 1
        cambi = ", ".join(f"{k} {prima[k]}->{v}" for k, v in campi.items()
                          if prima[k] != v)
        print(f"  {drv['first']} {drv['last']}: {cambi or 'nessun cambiamento'}")

    if ignoti:
        print(f"\nId non riconosciuti (ignorati): {', '.join(sorted(ignoti))}")
        print("Gli id sono quelli in data/drivers.json, per esempio 'verstappen'.")
    print(f"\nPiloti aggiornati: {aggiornati}")

    if args.dry_run:
        print("Prova a vuoto: data/drivers.json non e' stato toccato.")
        return 0
    if aggiornati:
        DRIVERS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        print(f"Scritto {DRIVERS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
