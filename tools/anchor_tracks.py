"""Trova la linea del traguardo sui tracciati e scrive dove sta.

    python tools/anchor_tracks.py                 # tutti quelli che si possono fare
    python tools/anchor_tracks.py --only monza spa
    python tools/anchor_tracks.py --dry-run       # stampa e basta

Il problema
-----------
I tracciati vengono da OpenStreetMap: sono strade disegnate da qualcuno, e
cominciano dal punto da cui quel qualcuno le ha disegnate. Non e' la linea del
traguardo, e il verso in cui sono state disegnate non e' per forza il verso in
cui si corre. Il gioco pero' conta i giri da quella linea: i settori, i
distacchi, il punto in cui si accende il semaforo, la posizione delle vetture
sul disegno. Se la linea sta nel posto sbagliato, sbaglia tutto il resto.

Come si trova
-------------
La banca dati dei circuiti del Politecnico di Monaco di Baviera
(TUMFTM/racetrack-database, licenza LGPL) contiene le linee mediane di una
ventina di circuiti, e quelle cominciano dal traguardo e vanno nel verso di
gara. Non si copia niente da li': si prende il profilo di curvatura - dove
gira a destra, dove a sinistra, per quanti metri - e lo si confronta con il
nostro, provando tutte le rotazioni e tutti e due i versi. La rotazione che
somiglia di piu' dice dove sta il traguardo sul nostro tracciato, e se la
strada di OpenStreetMap e' disegnata al contrario.

Il risultato e' un punto sul nostro tracciato: due coordinate che finiscono in
tracks.json come `start`, e il verso di gara come `senso`. Dei dati altrui non
resta niente.

Quello che il confronto non copre
---------------------------------
I circuiti che quella banca dati non ha - le cittadine soprattutto - hanno le
coordinate scritte a mano in ANCORE_A_MANO, prese dalla posizione reale della
linea del traguardo. Lo strumento le aggancia al punto piu' vicino del
tracciato e dice di quanto ha dovuto spostarle: se sono decine di metri la
coordinata e' buona, se sono centinaia va corretta.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TRACKS = ROOT / "data" / "tracks.json"
CACHE = Path(__file__).resolve().parent / "_cache"

from game.model.track import _project, _resample, _smooth, _path_length   # noqa: E402

FONTE = "https://raw.githubusercontent.com/TUMFTM/racetrack-database/master/tracks/"
UA = "ApexManager/0.1 (gestionale F1 open source; allineamento traguardi)"

# I nostri circuiti e come si chiamano nella banca dati del TUM.
RIFERIMENTI = {
    "melbourne": "Melbourne", "shanghai": "Shanghai", "suzuka": "Suzuka",
    "bahrain": "Sakhir", "barcelona": "Catalunya", "montreal": "Montreal",
    "redbullring": "Spielberg", "silverstone": "Silverstone",
    "hungaroring": "Budapest", "zandvoort": "Zandvoort", "spa": "Spa",
    "monza": "Monza", "cota": "Austin", "mexico": "MexicoCity",
    "interlagos": "SaoPaulo", "yasmarina": "YasMarina",
    "sepang": "Sepang", "nurburgring": "Nuerburgring",
}
# Hockenheim non c'e': la banca dati ha il vecchio anello lungo e il confronto
# non trova niente (correlazione 0.31 contro un secondo picco di 0.29).

# Sotto questa somiglianza il confronto non ha trovato il circuito: meglio
# lasciare la linea dov'e' che metterla a caso. Serve anche che il picco sia
# nettamente il migliore, non uno fra tanti.
CORR_MINIMA = 0.55
STACCO_MINIMO = 1.5

# Dove sta il traguardo sui circuiti che la banca dati non ha, e in che verso
# si corre. Sono posizioni reali: lo strumento le aggancia al tracciato e dice
# di quanto le ha spostate, cosi' si vede subito se una e' sbagliata.
ANCORE_A_MANO = {
    "monaco": (43.73470, 7.42120, "orario"),
    "jeddah": (21.63190, 39.10440, "antiorario"),
    "miami": (25.95810, -80.23890, "orario"),
    "baku": (40.37250, 49.85330, "antiorario"),
    "singapore": (1.29140, 103.86370, "antiorario"),
    "lasvegas": (36.11500, -115.16500, "antiorario"),
    "lusail": (25.49000, 51.45420, "orario"),
    "imola": (44.34120, 11.71330, "antiorario"),
    "portimao": (37.22930, -8.62680, "orario"),
    "mugello": (43.99750, 11.37160, "orario"),
    "istanbul": (40.95170, 29.40500, "antiorario"),
    "kyalami": (-25.99860, 28.07660, "orario"),
    "paulricard": (43.25070, 5.79180, "orario"),
    "tsukuba": (36.15370, 140.07680, "orario"),
    "hockenheim": (49.32780, 8.56580, "orario"),
}

# Quanto lontano dal tracciato puo' cadere una coordinata scritta a mano prima
# di dire che non e' quella giusta: qualche decina di metri e' mira imprecisa,
# qualche chilometro vuol dire che il tracciato scaricato non e' quel circuito.
SCARTO_SOSPETTO = 300.0
SCARTO_ROTTO = 1500.0

N = 480          # punti su cui si confrontano i due profili


# ------------------------------------------------------------------ profili
def _curva_segno(pts: list) -> list:
    """Quanto gira e da che parte, punto per punto."""
    n = len(pts)
    passo = _path_length(pts) / n
    span = max(1, int(round(20.0 / max(1.0, passo))))
    out = []
    for i in range(n):
        a, b, c = pts[(i - span) % n], pts[i], pts[(i + span) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        out.append(math.atan2(v1[0] * v2[1] - v1[1] * v2[0],
                              v1[0] * v2[0] + v1[1] * v2[1]) / (span * passo * 2))
    return out


def profilo(pts: list) -> list:
    """Il profilo di curvatura, lisciato e normalizzato, su N punti."""
    p = _resample(_smooth(pts, 2), N)
    k = _curva_segno(p)
    m = 7
    k = [sum(k[(i + j - m // 2) % N] for j in range(m)) / m for i in range(N)]
    med = sum(k) / N
    s = math.sqrt(sum((x - med) ** 2 for x in k) / N) or 1.0
    return [(x - med) / s for x in k]


def area_con_segno(pts: list) -> float:
    a = 0.0
    for i in range(len(pts) - 1):
        a += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
    return a / 2.0


# ------------------------------------------------------------- riferimento
def scarica(nome: str) -> list:
    """La linea mediana del TUM, dalla cache o dalla rete."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{nome}.csv"
    if not f.exists():
        req = urllib.request.Request(FONTE + nome + ".csv", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            f.write_bytes(r.read())
    pts = []
    for riga in f.read_text().splitlines():
        if riga.startswith("#") or not riga.strip():
            continue
        x, y = riga.split(",")[:2]
        pts.append((float(x), float(y)))
    return pts


# --------------------------------------------------------------- geometria
def punto_a(track: dict, quota: float) -> tuple:
    """Le coordinate del punto del tracciato a quella quota di percorso."""
    geo = [(float(a), float(b)) for a, b in track["geo"]]
    xy = [(p[1], p[0]) for p in geo]
    obiettivo = _path_length(xy) * (quota % 1.0)
    acc = 0.0
    for i in range(len(xy) - 1):
        d = math.dist(xy[i], xy[i + 1])
        if acc + d >= obiettivo and d > 0:
            f = (obiettivo - acc) / d
            return (round(geo[i][0] + (geo[i + 1][0] - geo[i][0]) * f, 6),
                    round(geo[i][1] + (geo[i + 1][1] - geo[i][1]) * f, 6))
        acc += d
    return geo[0]


def aggancia(track: dict, lat: float, lon: float) -> tuple:
    """Il punto del tracciato piu' vicino a una coordinata. Ritorna (quota, metri)."""
    geo = [(float(a), float(b)) for a, b in track["geo"]]
    xy = _project(geo + [[lat, lon]])
    bersaglio = xy[-1]
    linea = xy[:-1]
    tot = _path_length(linea)
    meglio, acc = None, 0.0
    for i in range(len(linea) - 1):
        a, b = linea[i], linea[i + 1]
        seg = math.dist(a, b)
        if seg <= 1e-9:
            continue
        t = max(0.0, min(1.0, ((bersaglio[0] - a[0]) * (b[0] - a[0])
                               + (bersaglio[1] - a[1]) * (b[1] - a[1])) / (seg * seg)))
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        d = math.dist(bersaglio, (px, py))
        if meglio is None or d < meglio[0]:
            meglio = (d, (acc + seg * t) / tot)
        acc += seg
    return (meglio[1], meglio[0]) if meglio else (0.0, 0.0)


# ------------------------------------------------------------ allineamento
def allinea(track: dict) -> dict:
    """Confronta il nostro profilo con quello del riferimento."""
    nostro = profilo(_project(track["geo"]))
    loro = profilo(scarica(RIFERIMENTI[track["id"]]))
    punteggi = []
    for verso in (1, -1):
        b = loro if verso == 1 else [-x for x in reversed(loro)]
        for s in range(N):
            punteggi.append((sum(nostro[(i + s) % N] * b[i] for i in range(N)) / N, verso, s))
    punteggi.sort(reverse=True)
    corr, verso, shift = punteggi[0]
    # il secondo picco vero: serve a capire se il primo e' una risposta o un caso
    secondo = next(p for p in punteggi
                   if p[1] != verso or min(abs(p[2] - shift), N - abs(p[2] - shift)) > N * 0.06)
    antiorario = area_con_segno(_project(track["geo"])) > 0
    if verso < 0:
        antiorario = not antiorario
    return {"quota": shift / N, "corr": corr, "secondo": secondo[0],
            "senso": "antiorario" if antiorario else "orario", "fonte": "confronto"}


def a_mano(track: dict) -> dict:
    lat, lon, senso = ANCORE_A_MANO[track["id"]]
    quota, metri = aggancia(track, lat, lon)
    return {"quota": quota, "scarto_m": metri, "senso": senso, "fonte": "a mano"}


def stimata(track: dict) -> dict:
    """Senza riferimenti: la linea va in fondo al rettilineo piu' lungo.

    E' dove sta quasi sempre - si parte in fondo a un dritto e si arriva alla
    prima curva dopo qualche centinaio di metri - ma resta una supposizione, e
    il verso di gara qui non lo sa nessuno: si tiene quello del disegno.
    """
    pts = _resample(_smooth(_project(track["geo"]), 2), N)
    k = _curva_segno(pts)
    dritto = [abs(x) < 1.0 / 200.0 for x in k]
    meglio, inizio, lungo = (0, 0), None, 0
    for i in range(2 * N):
        if dritto[i % N]:
            if inizio is None:
                inizio = i
            lungo = i - inizio + 1
            if lungo > meglio[1]:
                meglio = (i % N, lungo)
        else:
            inizio, lungo = None, 0
    fine, _ = meglio
    passo = track["length_km"] * 1000.0 / N
    indietro = int(round(300.0 / passo))          # la linea sta prima della curva
    antiorario = area_con_segno(pts) > 0
    return {"quota": ((fine - indietro) % N) / N, "senso": "antiorario" if antiorario else "orario",
            "fonte": "stimata"}


# ----------------------------------------------------------------- verifica
def controlla(track: dict, quota: float, senso: str) -> str:
    """Cosa si trova appena dopo la linea: dritto o curva, e da che parte.

    Una linea del traguardo sta su un rettilineo, e la prima curva arriva dopo
    qualche centinaio di metri. Se il conto dice altro, l'ancoraggio e' sbagliato.
    """
    pts = _resample(_smooth(_project(track["geo"]), 2), N)
    k = _curva_segno(pts)
    passo = track["length_km"] * 1000.0 / N
    avanti = 1 if (area_con_segno(pts) > 0) == (senso == "antiorario") else -1
    i0 = int(quota * N)
    soglia = 1.0 / 120.0        # sotto questo raggio non e' piu' un rettilineo
    for j in range(1, N):
        i = (i0 + avanti * j) % N
        if abs(k[i]) > soglia:
            dove = "destra" if (k[i] < 0) == (avanti > 0) else "sinistra"
            return f"prima curva a {j * passo:4.0f} m, a {dove}"
    return "nessuna curva trovata"


# --------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dati = json.loads(TRACKS.read_text(encoding="utf-8"))
    tutti = dati["tracks"] + dati["candidates"] + dati.get("private", [])
    tocchi = 0
    print(f"{'pista':<13}{'fonte':<10}{'qualita':>18}  {'senso':<11}{'traguardo':<24}verifica")
    for t in tutti:
        if args.only and t["id"] not in args.only:
            continue
        if not t.get("geo"):
            continue
        if t["id"] in RIFERIMENTI:
            try:
                r = allinea(t)
            except Exception as e:                      # rete assente, file mancante
                print(f"{t['id']:<13}confronto non riuscito: {e}")
                continue
            qualita = f"corr {r['corr']:.2f} (2o {r['secondo']:.2f})"
            if r["corr"] < CORR_MINIMA or r["corr"] < r["secondo"] * STACCO_MINIMO:
                print(f"{t['id']:<13}confronto senza risposta ({qualita}): "
                      f"la linea resta dov'e'")
                continue
        elif t["id"] in ANCORE_A_MANO:
            r = a_mano(t)
            qualita = f"agganciata a {r['scarto_m']:.0f} m"
            if r["scarto_m"] > SCARTO_ROTTO:
                print(f"{t['id']:<13}la coordinata cade a {r['scarto_m']/1000:.1f} km dal "
                      f"tracciato: o la coordinata o il tracciato non e' quel circuito")
                continue
            if r["scarto_m"] > SCARTO_SOSPETTO:
                qualita += " (da controllare)"
        else:
            r = stimata(t)
            qualita = "in fondo al dritto"
        lat, lon = punto_a(t, r["quota"])
        prova = controlla(t, r["quota"], r["senso"])
        print(f"{t['id']:<13}{r['fonte']:<10}{qualita:>18}  {r['senso']:<11}"
              f"{lat:.5f}, {lon:.5f}   {prova}")
        t["start"] = [lat, lon]
        t["senso"] = r["senso"]
        tocchi += 1

    if args.dry_run:
        print(f"\n{tocchi} circuiti (nessuna scrittura: --dry-run)")
        return
    TRACKS.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{tocchi} circuiti scritti in {TRACKS}")


if __name__ == "__main__":
    main()
