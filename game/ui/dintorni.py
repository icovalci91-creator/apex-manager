"""I dintorni veri di un circuito, letti dai file di `tools/fetch_dintorni.py`.

Il file sta in `dintorni/<circuito>.json.gz` e porta le forme prese da
OpenStreetMap in gradi. Qui le si riporta nei metri del tracciato, lo stesso
riferimento in cui `pista3d` costruisce il nastro d'asfalto, cosi' una strada
che nella realta' passa sotto la curva uno ci passa anche nel gioco.

Se il file non c'e' - e all'inizio non c'e' per nessuno - `carica` risponde
None e la vista 3D si inventa i dintorni come prima.
"""
from __future__ import annotations

import gzip
import json

from .. import config as C

FONTE = "Mappa: (c) OpenStreetMap contributors"


def carica(track) -> dict | None:
    """Le forme attorno al circuito, in metri del mondo 3D (x verso est, z verso sud)."""
    percorso = C.DINTORNI / f"{track.id}.json.gz"
    if not percorso.exists() or not getattr(track, "geo", None):
        return None
    try:
        with gzip.open(percorso, "rb") as f:
            grezzo = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    s, w = grezzo["origine"]
    scala = grezzo["scala"]

    def punti(piatti):
        fuori = []
        for i in range(0, len(piatti) - 1, 2):
            x, y = track.metri_da(s + piatti[i] * scala, w + piatti[i + 1] * scala)
            fuori.append((x, -y))
        return fuori

    uscita = {"fonte": grezzo.get("fonte", FONTE)}
    for chiave in ("acqua", "bosco", "verde", "campi", "urbano", "sabbia", "parcheggi",
                   "ferrovie", "costa"):
        uscita[chiave] = [punti(p) for p in grezzo.get(chiave, [])]
    uscita["edifici"] = [(punti(e["p"]), float(e["h"])) for e in grezzo.get("edifici", [])]
    uscita["strade"] = [(punti(r["l"]), float(r["w"])) for r in grezzo.get("strade", [])]
    uscita["fiumi"] = [(punti(r["l"]), float(r["w"])) for r in grezzo.get("fiumi", [])]
    return uscita
