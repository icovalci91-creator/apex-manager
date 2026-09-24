"""Ridisegna i circuiti inventati con il progettista di `game/model/disegno.py`.

Per ogni circuito prova qualche centinaio di tracciati, tiene i migliori per il
progettista e li fa girare al modello di giro: vince quello dove il modello
trova i posti migliori per passare. Da li' si ricava anche il carattere
"sorpasso" del circuito, con la stessa scala delle piste vere.

    python tools/disegna_piste.py                 # mostra e basta
    python tools/disegna_piste.py --scrivi        # e scrive in data/tracks.json
    python tools/disegna_piste.py --only genova   # uno solo

Scrive solo le tre righe che cambiano - layout, curve, sorpasso - lasciando il
file com'e' per tutto il resto.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.model import disegno as D          # noqa: E402
from game.model.track import Track           # noqa: E402

# chi si ridisegna, e in che stile. Gli altri circuiti senza GPS seguono la
# forma di quelli veri, disegnata a mano, e restano come sono.
PISTE = {
    "genova": "citta", "osaka": "citta", "reforma": "citta", "kalasatama": "citta",
    "pista_privata": "permanente", "buenosaires": "permanente",
}
FINALISTI = 16

# Il carattere "sorpasso" dalla misura del modello di giro: la retta che passa
# meglio fra le piste vere (Formula E per i circuiti di Formula E, Formula 1
# per gli altri). La misura e' quanto giro e' buono per passare, pesato per
# quanto e' buono.
RETTA_FE = (0.133, 0.447)
RETTA_F1 = (0.229, 0.286)


def _misura(voce: dict, layout: str, rif, fe: bool) -> tuple:
    """(misura, carattere) del tracciato secondo il modello di giro."""
    d = dict(voce)
    d["layout"] = layout
    t = Track.from_dict(d)
    t.calibrate(rif)
    if fe:
        mappa = t.mappa_corta
        m = 10.0 * sum(mappa) / max(1, len(mappa))
        a, b = RETTA_FE
    else:
        q = sorted((z["qualita"] for z in t.zone_ala), reverse=True)
        m = sum(v * w for v, w in zip(q, (1.0, 0.8, 0.6, 0.3)))
        a, b = RETTA_F1
    return m, round(max(0.2, min(0.9, a + b * m)), 2)


def _scrivi(testo: str, tid: str, layout: str, curve: int, sorpasso: float) -> str:
    i = testo.index(f'"id": "{tid}"')
    j = testo.find('"id": ', i + 10)
    j = len(testo) if j < 0 else j
    blocco = testo[i:j]
    blocco = re.sub(r'"layout": "[^"]*"', f'"layout": "{layout}"', blocco, count=1)
    blocco = re.sub(r'"corners": \d+', f'"corners": {curve}', blocco, count=1)
    blocco = re.sub(r'"overtaking": [0-9.]+', f'"overtaking": {sorpasso}', blocco, count=1)
    return testo[:i] + blocco + testo[j:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scrivi", action="store_true", help="aggiorna data/tracks.json")
    ap.add_argument("--only", help="solo questi circuiti, separati da virgola")
    ap.add_argument("--prove", type=int, default=1600)
    args = ap.parse_args()

    percorso = ROOT / "data" / "tracks.json"
    testo = percorso.read_text(encoding="utf-8")
    dati = json.loads(testo)
    voci = {t["id"]: (t, g) for g in ("tracks", "candidates", "private", "formulae")
            for t in dati.get(g, [])}
    from game.core.state import GameState
    rif = GameState.new_game(next(iter(json.loads(
        (ROOT / "data" / "teams.json").read_text(encoding="utf-8"))["teams"]))["id"],
        True, seed=1)._ref_car()

    scelti = args.only.split(",") if args.only else list(PISTE)
    for tid in scelti:
        voce, gruppo = voci[tid]
        stile = PISTE.get(tid, "citta")
        fe = gruppo == "formulae"
        seme = zlib.crc32(tid.encode())
        candidati = []
        for k in range(FINALISTI):
            r = D.disegna(float(voce["length_km"]), int(voce["corners"]), stile,
                          seme + k * 7919, args.prove // FINALISTI)
            if r:
                candidati.append(r)
        if not candidati:
            print(f"{tid}: nessun tracciato buono")
            continue
        misurati = [(_misura(voce, r["layout"], rif, fe), r) for r in candidati]
        (m, sorpasso), r = max(misurati, key=lambda x: x[0][0])
        prima = voce["traits"].get("overtaking")
        print(f"{tid:<14} {stile:<10} curve {r['curve']:>2}  staccate {r['posti']}  "
              f"misura {m:.2f}  sorpasso {prima} -> {sorpasso}")
        print(f"    {r['layout']}")
        if args.scrivi:
            testo = _scrivi(testo, tid, r["layout"], r["curve"], sorpasso)
    if args.scrivi:
        percorso.write_text(testo, encoding="utf-8")
        print("scritto", percorso)


if __name__ == "__main__":
    main()
