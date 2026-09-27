"""I dintorni veri di un circuito, letti dai file di `tools/fetch_dintorni.py`.

Il file sta in `dintorni/<circuito>.json.gz` e porta le forme prese da
OpenStreetMap in gradi. Qui le si riporta nei metri del tracciato, lo stesso
riferimento in cui `pista3d` costruisce il nastro d'asfalto, cosi' una strada
che nella realta' passa sotto la curva uno ci passa anche nel gioco.

Se il file non c'e' - e all'inizio non c'e' per nessuno - `carica` risponde
None e la vista 3D si inventa i dintorni come prima. I circuiti di Formula E
sono disegnati e non hanno coordinate: il loro file porta anche la `posa`,
dove poggiare il disegno sulla carta perche' corra sulle strade vere.
"""
from __future__ import annotations

import gzip
import json
import math

from .. import config as C

FONTE = "Mappa: (c) OpenStreetMap contributors"


def _posato(posa: dict):
    """Per un circuito disegnato (la Formula E): da gradi a metri del
    tracciato, con la posa che `tools/fetch_dintorni.py` ha trovato mettendo
    il disegno sulle strade vere - dove sta il centro, di quanto e' girato."""
    lat0, lon0 = float(posa["lat"]), float(posa["lon"])
    cx, cy = (float(v) for v in posa["centro"])
    a = math.radians(float(posa["angolo"]))
    c, s = math.cos(a), math.sin(a)
    mx = 111320.0 * math.cos(math.radians(lat0))

    def metri_da(lat: float, lon: float) -> tuple:
        x, y = (lon - lon0) * mx, (lat - lat0) * 110540.0
        # la posa gira il disegno sulla carta: qui si torna indietro
        return (x * c + y * s + cx, -x * s + y * c + cy)
    return metri_da


def carica(track) -> dict | None:
    """Le forme attorno al circuito, in metri del mondo 3D (x verso est, z verso sud)."""
    percorso = C.DINTORNI / f"{track.id}.json.gz"
    if not percorso.exists():
        return None
    try:
        with gzip.open(percorso, "rb") as f:
            grezzo = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    s, w = grezzo["origine"]
    scala = grezzo["scala"]
    if getattr(track, "geo", None):
        metri_da = track.metri_da
    elif grezzo.get("posa") and getattr(track, "_metri", None):
        metri_da = _posato(grezzo["posa"])
    else:
        return None

    def punti(piatti):
        fuori = []
        for i in range(0, len(piatti) - 1, 2):
            x, y = metri_da(s + piatti[i] * scala, w + piatti[i + 1] * scala)
            fuori.append((x, -y))
        return fuori

    uscita = {"fonte": grezzo.get("fonte", FONTE)}
    for chiave in ("acqua", "bosco", "verde", "campi", "urbano", "sabbia", "parcheggi",
                   "ferrovie", "costa", "piazzali"):
        uscita[chiave] = [punti(p) for p in grezzo.get(chiave, [])]
    uscita["edifici"] = [(punti(e["p"]), float(e["h"])) for e in grezzo.get("edifici", [])]
    uscita["strade"] = [(punti(r["l"]), float(r["w"])) for r in grezzo.get("strade", [])]
    uscita["fiumi"] = [(punti(r["l"]), float(r["w"])) for r in grezzo.get("fiumi", [])]
    return uscita
