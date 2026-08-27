"""Controlla che la linea del traguardo sia dove deve stare, circuito per circuito.

    python tools/verifica_traguardi.py
    python tools/verifica_traguardi.py --only monza spa

`anchor_tracks.py` la linea la mette; questo strumento la controlla, e lo fa
senza scrivere niente. Serve perche' un traguardo spostato non si vede: i tempi
sul giro restano quelli, il disegno resta quello, e intanto i settori cadono
nel posto sbagliato, la griglia si forma dove non deve e le vetture sul
tracciato sono avanti o indietro di qualche centinaio di metri rispetto a dove
dovrebbero essere.

Due prove, indipendenti fra loro.

**Il confronto con la banca dati.** Le linee mediane del TUM cominciano dal
traguardo e vanno nel verso di gara: il loro punto zero *e'* la linea. Per i
circuiti che quella banca dati ha, si guarda cosa si incontra nei primi due
chilometri dopo il traguardo - a che metro comincia ogni curva e da che parte
gira - e si confronta con quello che si incontra dopo il nostro. Se le due
descrizioni coincidono, la linea e' nel posto giusto; se il nostro elenco e'
spostato in avanti di trecento metri, la linea e' spostata di trecento metri.

**La prova del rettilineo.** Per gli altri - le cittadine soprattutto, che
quella banca dati non ha - non c'e' un riferimento, ma c'e' una regola che non
sbaglia mai: una linea del traguardo sta su un rettilineo. Si misura quanto
dritto c'e' prima e quanto ce n'e' dopo. Se la curva precedente finisce a
venti metri dalla linea, o se la successiva comincia subito, quella linea e'
finita dentro una curva e va rifatta.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from game.model.track import (_centro, _path_length, _project,   # noqa: E402
                              _resample, _smooth)
from anchor_tracks import CACHE, RIFERIMENTI                     # noqa: E402

TRACKS = ROOT / "data" / "tracks.json"

N = 600                  # punti su cui si guarda il tracciato
SOGLIA = 1.0 / 300.0     # sotto i trecento metri di raggio non e' piu' dritto
DISTINTE = 80.0          # due curve piu' vicine di cosi' sono la stessa cosa
QUANTE = 4               # quante curve dopo la linea si confrontano

# Quanto puo' scostarsi il nostro elenco da quello della banca dati prima di
# dire che la linea e' spostata. Si guarda la prima curva dopo il traguardo, che
# e' il confronto piu' solido: piu' avanti i due disegni cominciano a chiamare
# curva cose diverse - uno e' la mediana rilevata, l'altro una strada di
# OpenStreetMap - e il confronto si sporca da solo. Qualche decina di metri di
# differenza la fanno i due tracciati, non il traguardo.
SCARTO_BUONO = 90.0
SCARTO_MALE = 200.0

# E quanto dritto ci vuole attorno a una linea del traguardo. Non tanto quanto
# si crederebbe: a Budapest la linea sta a una quarantina di metri dall'uscita
# dell'ultima curva e a Silverstone a una cinquantina, e sono giuste tutte e
# due. Sotto i venticinque metri pero' la linea e' proprio dentro la curva, e
# un circuito cosi' non esiste.
DRITTO_MINIMO = 25.0


def _curvatura(pts: list, passo: float) -> list:
    """Quanto gira e da che parte, punto per punto."""
    n = len(pts)
    span = max(1, int(round(20.0 / max(1.0, passo))))
    out = []
    for i in range(n):
        a, b, c = pts[(i - span) % n], pts[i], pts[(i + span) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        out.append(math.atan2(v1[0] * v2[1] - v1[1] * v2[0],
                              v1[0] * v2[0] + v1[1] * v2[1]) / (span * passo * 2))
    return out


def _area(pts: list) -> float:
    a = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return a


def curve_dopo(pts: list, i0: int, avanti: int, passo: float, quante: int = QUANTE) -> list:
    """Le prime curve dopo il punto zero: [(metri, 'dx'|'sx'), ...]."""
    k = _curvatura(pts, passo)
    n = len(pts)
    fuori: list = []
    ultimo = 0
    j = 1
    while j < n and len(fuori) < quante:
        i = (i0 + avanti * j) % n
        if abs(k[i]) > SOGLIA and (j - ultimo) * passo > DISTINTE:
            fuori.append((j * passo, "dx" if (k[i] < 0) == (avanti > 0) else "sx"))
            ultimo = j
        j += 1
    return fuori


def dritto_attorno(pts: list, i0: int, avanti: int, passo: float) -> tuple:
    """Quanti metri di rettilineo ci sono prima della linea e quanti dopo."""
    k = _curvatura(pts, passo)
    n = len(pts)
    dopo = next((j for j in range(1, n) if abs(k[(i0 + avanti * j) % n]) > SOGLIA), n)
    prima = next((j for j in range(1, n) if abs(k[(i0 - avanti * j) % n]) > SOGLIA), n)
    return prima * passo, dopo * passo


def nostro(track: dict) -> tuple:
    """Il nostro tracciato in metri, con l'indice della linea e il verso."""
    geo = [(float(p[0]), float(p[1])) for p in track["geo"]]
    pts = _resample(_smooth(_project(geo), 2), N)
    passo = float(track["length_km"]) * 1000.0 / N
    linea = _project([list(track["start"])], origine=_centro(geo))[0]
    i0 = min(range(N), key=lambda i: math.dist(pts[i], linea))
    avanti = 1 if (_area(pts) > 0) == (track.get("senso") == "antiorario") else -1
    return pts, i0, avanti, passo


def riferimento(nome: str):
    """La mediana della banca dati, che comincia dal traguardo."""
    f = CACHE / f"{nome}.csv"
    if not f.exists():
        return None
    pts = []
    for riga in f.read_text().splitlines():
        if riga.startswith("#") or not riga.strip():
            continue
        x, y, *_ = riga.split(",")
        pts.append((float(x), float(y)))
    if len(pts) < 32:
        return None
    b = _resample(_smooth(pts, 2), N)
    passo = (_path_length(b) + math.dist(b[-1], b[0])) / N
    return b, passo


def _fmt(curve: list) -> str:
    return "  ".join(f"{m:.0f}m {v}" for m, v in curve) or "nessuna curva"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    dati = json.loads(TRACKS.read_text(encoding="utf-8"))
    tutti = dati["tracks"] + dati["candidates"] + dati.get("private", [])
    sospetti, rotti, controllati = [], [], 0

    print(f"{'pista':<13}{'dritto prima':>13}{'dritto dopo':>12}{'confronto':>12}   "
          f"prime curve dopo il traguardo")
    for t in tutti:
        if args.only and t["id"] not in args.only:
            continue
        if not t.get("geo") or len(t.get("start", [])) != 2:
            continue
        controllati += 1
        pts, i0, avanti, passo = nostro(t)
        prima, dopo = dritto_attorno(pts, i0, avanti, passo)
        mie = curve_dopo(pts, i0, avanti, passo)

        scarto = None
        rif = riferimento(RIFERIMENTI[t["id"]]) if t["id"] in RIFERIMENTI else None
        if rif is not None:
            b, passo_b = rif
            loro = curve_dopo(b, 0, 1, passo_b)
            # la prima curva dopo la linea, e solo quella: e' l'unica che i due
            # disegni chiamano di sicuro allo stesso modo
            if mie and loro and mie[0][1] == loro[0][1]:
                scarto = mie[0][0] - loro[0][0]

        # la banca dati, quando c'e', decide: e' una misura, non un indizio.
        # La prova del rettilineo vale per gli altri
        note, grave = [], False
        if scarto is not None:
            if abs(scarto) > SCARTO_MALE:
                note.append(f"spostata di {scarto:+.0f} m rispetto alla banca dati")
                grave = True
            elif abs(scarto) > SCARTO_BUONO:
                note.append(f"{scarto:+.0f} m rispetto alla banca dati")
        else:
            if prima < DRITTO_MINIMO:
                note.append(f"la linea e' dentro la curva precedente ({prima:.0f} m)")
                grave = True
            if dopo < DRITTO_MINIMO:
                note.append(f"la curva dopo e' addosso alla linea ({dopo:.0f} m)")
                grave = True
        if note:
            (rotti if grave else sospetti).append((t["id"], "; ".join(note)))

        col = f"{scarto:+.0f} m" if scarto is not None else "-"
        print(f"{t['id']:<13}{prima:11.0f} m{dopo:10.0f} m{col:>12}   {_fmt(mie)}")

    print(f"\ncontrollati: {controllati}")
    if rotti:
        print(f"da rifare ({len(rotti)}):")
        for tid, perche in rotti:
            print(f"   {tid:<13}{perche}")
    if sospetti:
        print(f"da guardare ({len(sospetti)}):")
        for tid, perche in sospetti:
            print(f"   {tid:<13}{perche}")
    if not rotti and not sospetti:
        print("tutte le linee stanno dove devono stare.")
    sys.exit(1 if rotti else 0)


if __name__ == "__main__":
    main()
