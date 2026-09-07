"""Scarica tutto quello che ai tracciati manca, in un colpo solo.

    python tools/aggiorna_tracciati.py            # guarda cosa manca e lo dice
    python tools/aggiorna_tracciati.py --scarica  # e poi lo scarica davvero

A cosa serve. Alcuni pezzi dei tracciati non stanno nel gioco perche' vanno
chiesti a dei server esterni - OpenStreetMap per la forma dei circuiti,
Copernicus per il rilievo - e da certe reti quei server non si raggiungono.
Questo script mette in fila i tre strumenti che gia' ci sono, dice cosa manca
prima di partire, e va lanciato da una rete che ci arriva.

Cosa fa, in ordine:

  1. `fetch_layouts.py --pool tutti`  scarica da OpenStreetMap la forma dei
     circuiti che ancora non ce l'hanno, compresi quelli veri di Formula E,
     che oggi sono disegnati a mano dalle misure ufficiali;
  2. `anchor_tracks.py`  su ogni tracciato appena scaricato mette la linea del
     traguardo dove sta davvero e stabilisce da che parte si corre;
  3. `fetch_quote.py`  chiede il rilievo lungo il tracciato, cosi' le salite e
     le discese entrano nel modello di giro.

Tutto quello che scrive finisce in data/tracks.json. Prima di lanciarlo con
--scarica conviene avere il repository pulito, cosi' `git diff` mostra
esattamente cosa e' cambiato e si puo' tornare indietro con `git checkout`.

I dati di OpenStreetMap sono sotto licenza ODbL e vanno citati: il README lo
fa gia'.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "data" / "tracks.json"


def manca(dati: dict) -> tuple:
    """Cosa non c'e' ancora: (senza tracciato, senza rilievo)."""
    senza_geo, senza_quota = [], []
    for pool in ("tracks", "candidates", "private", "formulae"):
        for t in dati.get(pool, []):
            if t.get("debutto"):
                continue          # i circuiti inventati non stanno su nessuna mappa
            if not t.get("geo"):
                senza_geo.append((pool, t["id"]))
            elif not t.get("quota"):
                senza_quota.append((pool, t["id"]))
    return senza_geo, senza_quota


def lancia(argomenti: list) -> int:
    print("\n$ " + " ".join(argomenti))
    return subprocess.call([sys.executable] + argomenti, cwd=str(RADICE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scarica", action="store_true",
                    help="scarica davvero; senza questo dice solo cosa manca")
    ap.add_argument("--only", nargs="*", default=None,
                    help="limita a questi circuiti")
    args = ap.parse_args()

    dati = json.loads(DATI.read_text(encoding="utf-8"))
    senza_geo, senza_quota = manca(dati)
    print(f"circuiti senza tracciato: {len(senza_geo)}")
    for pool, tid in senza_geo:
        print(f"   {tid:<14} [{pool}]")
    print(f"circuiti con tracciato ma senza rilievo: {len(senza_quota)}")
    for pool, tid in senza_quota:
        print(f"   {tid:<14} [{pool}]")
    if not args.scarica:
        print("\nNiente e' stato scaricato. Rilancia con --scarica da una rete che "
              "arriva a overpass-api.de e a Copernicus.")
        return 0
    solo = (["--only"] + list(args.only)) if args.only else []
    for passo in (["tools/fetch_layouts.py", "--pool", "tutti"] + solo,
                  ["tools/anchor_tracks.py"] + solo,
                  ["tools/fetch_quote.py"] + solo):
        if lancia(passo) != 0:
            print(f"\nfermato su {passo[0]}: guarda l'errore qui sopra.")
            return 1
    dati = json.loads(DATI.read_text(encoding="utf-8"))
    senza_geo, senza_quota = manca(dati)
    print(f"\nfatto. Restano senza tracciato {len(senza_geo)}, "
          f"senza rilievo {len(senza_quota)}.")
    print("Controlla con `git diff --stat data/tracks.json` e, se qualcosa non "
          "torna, `git checkout data/tracks.json`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
