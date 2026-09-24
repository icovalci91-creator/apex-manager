"""Il progettista di circuiti: disegna un tracciato pensato per passare.

Un circuito inventato non puo' essere una fila di curve a caso: da una fila di
curve a caso esce una gara in cui nessuno supera. Chi disegna le piste vere
lavora con poche regole, sempre le stesse, e sono quelle che si seguono qui.

  * Un sorpasso si fa in staccata: ci vuole un dritto lungo abbastanza da
    prendere la scia e, in fondo, una curva lenta - un tornante o un angolo
    retto - in cui chi sta dietro puo' frenare piu' tardi e infilarsi.
  * La curva *prima* di quel dritto deve essere lenta anche lei: da una curva
    lenta si esce attaccati, perche' a bassa velocita' l'aria sporca pesa
    poco. Da un curvone veloce chi segue esce staccato, e il dritto non basta.
  * Le staccate buone sono almeno due, e non una dopo l'altra: chi ha chiuso
    la porta nella prima si deve difendere di nuovo nella seconda.
  * Il rettilineo del traguardo finisce in una staccata: la prima curva e' il
    posto dove si decide la partenza.
  * Nel mezzo il misto - angoli, chicane, esse - fa la differenza fra le
    macchine, ma non ha curvoni veloci subito prima di una staccata.

Il tracciato si compone a blocchi, ognuno un dritto con quello che c'e' in
fondo. Se ne provano qualche centinaio, si chiudono con `track._chiudi`, si
scartano quelli che si incrociano, si toccano o vengono lunghi e stretti come
un ago, e fra quelli buoni si tiene quello con i posti migliori per passare.
Esce la stringa del layout, la stessa che si scrive a mano in `tracks.json`.
"""
from __future__ import annotations

import math
import random

from .. import config as C
from . import track as TR

# I blocchi: (nome, dritto minimo e massimo in quota della lunghezza, curve).
# Le curve sono (angolo, classe) con il segno: positivo a destra. Gli angoli
# dei blocchi "a" si girano dalla parte che serve a chiudere il giro.
STACCATE = ("staccata_angolo", "staccata_tornante")
STILI = {
    # in citta': angoli retti fra i palazzi, chicane, niente curvoni
    "citta": {
        "staccata_angolo": 3, "staccata_tornante": 2, "angolo": 5, "chicane": 2,
        "esse": 1, "curvone": 0.5,
    },
    # in un autodromo: piu' respiro, curvoni, esse veloci
    "permanente": {
        "staccata_angolo": 3, "staccata_tornante": 2, "angolo": 3, "chicane": 1,
        "esse": 2, "curvone": 2,
    },
}
# quanto deve essere lungo, in metri, un dritto da staccata: in citta' meno,
# perche' le macchine di citta' vanno piu' piano e i circuiti sono corti
DRITTO_STACCATA = {"citta": (300.0, 560.0), "permanente": (520.0, 950.0)}
DRITTO_CORTO = {"citta": (70.0, 170.0), "permanente": (110.0, 260.0)}
# quanto vale una staccata come posto per passare, dalla classe della curva
FRENATA = {1: 1.0, 2: 0.85, 3: 0.45, 4: 0.15, 5: 0.05}
LENTE = (1, 2)
DISTANZA_MINIMA_M = 38.0     # due pezzi di pista non si avvicinano di piu'
PROPORZIONE_MAX = 2.6        # e il circuito non e' un ago


def _blocco(tipo: str, stile: str, rng: random.Random) -> tuple:
    """Un blocco: (dritto in metri, [(angolo con segno, classe)], staccata?)."""
    corto = rng.uniform(*DRITTO_CORTO[stile])
    if tipo == "staccata_angolo":
        return rng.uniform(*DRITTO_STACCATA[stile]), [(rng.choice((85, 90, 95, 105)), 2)], True
    if tipo == "staccata_tornante":
        return rng.uniform(*DRITTO_STACCATA[stile]), [(rng.choice((130, 150, 165, 180)), 1)], True
    if tipo == "angolo":
        return corto, [(rng.choice((75, 90, 90, 90, 100)), 2 if stile == "citta" else rng.choice((2, 3)))], False
    if tipo == "chicane":
        a = rng.choice((35, 45, 50))
        return corto, [(-a, 3), (0, 25), (a, 3)], False
    if tipo == "esse":
        a = rng.choice((50, 60, 70))
        return corto, [(a, 3), (0, 50), (-a, 3)], False
    # il curvone: veloce, e quindi mai subito prima di una staccata
    return corto, [(rng.choice((25, 35, 45)), rng.choice((4, 5)))], False


def _componi(stile: str, curve: int, rng: random.Random) -> list | None:
    """La sequenza dei blocchi, con i versi che fanno un giro intero."""
    pesi = STILI[stile]
    staccate = 2 if curve < 16 else 3
    tipi = [rng.choice(STACCATE) for _ in range(staccate)]
    altri = [k for k in pesi if k not in STACCATE]
    conta = sum(1 if t in STACCATE else 0 for t in tipi)
    riempitivi = []
    while conta + sum(1 if t in ("angolo", "curvone") else 2 for t in riempitivi) < curve:
        riempitivi.append(rng.choices(altri, [pesi[k] for k in altri])[0])
    # le staccate distribuite lungo il giro, la prima subito al via
    blocchi = []
    rng.shuffle(riempitivi)
    pezzi = [[] for _ in range(staccate)]
    for i, r in enumerate(riempitivi):
        pezzi[i % staccate].append(r)
    for s, dopo in zip(tipi, pezzi):
        blocchi.append(s)
        blocchi.extend(dopo)
    # la curva prima di una staccata dev'essere lenta: un curvone li' si toglie
    for i, t in enumerate(blocchi):
        if t in STACCATE and blocchi[i - 1] == "curvone":
            blocchi[i - 1] = "angolo"
    fatti = [_blocco(t, stile, rng) for t in blocchi]
    # i versi: le curve con verso libero (tutte tranne quelle delle chicane e
    # delle esse, che si annullano) si girano finche' il totale fa un giro
    verso = rng.choice((1, -1))
    liberi = [(i, j) for i, (_d, cc, _s) in enumerate(fatti) for j, (a, _c) in enumerate(cc)
              if len(cc) == 1]
    segni = {k: verso for k in liberi}
    totale = sum(fatti[i][1][j][0] * segni[(i, j)] for i, j in liberi)
    meta = 360 * verso
    ordine = [k for k in liberi]
    rng.shuffle(ordine)
    for k in ordine:
        i, j = k
        a = fatti[i][1][j][0]
        # mai girare al contrario una staccata: in fondo al dritto si va dalla
        # parte del giro, e' li' che c'e' spazio per affiancarsi
        if fatti[i][2]:
            continue
        if abs(totale - 2 * a * segni[k] - meta) < abs(totale - meta):
            totale -= 2 * a * segni[k]
            segni[k] = -segni[k]
    if abs(totale - meta) > 110:
        return None
    uscita = []
    for i, (dritto, cc, staccata) in enumerate(fatti):
        uscita.append(("S", dritto, 0, staccata))
        for j, (a, c) in enumerate(cc):
            if a == 0:
                uscita.append(("S", float(c), 0, False))
                continue
            s = segni.get((i, j), verso if len(cc) == 1 else 1)
            ang = a * s if len(cc) == 1 else a * verso
            uscita.append(("R" if ang > 0 else "L", abs(ang), c, staccata and j == 0))
    return uscita


def _stringa(pezzi: list) -> str:
    out = []
    for kind, v, c, _s in pezzi:
        out.append(f"S{int(round(v))}" if kind == "S" else f"{kind}{int(round(v))}:{c}")
    return " ".join(out)


def _segmenti(layout: str, lunghezza_m: float) -> list:
    """Il layout come lo legge il gioco, gia' chiuso: None se non si chiude."""
    t = TR.Track.__new__(TR.Track)
    t.layout = layout
    t.length_km = lunghezza_m / 1000.0
    raw = []
    for tok in layout.split():
        if tok[0] == "S":
            raw.append(TR.Segment("S", float(tok[1:]), 0.0, 0.0))
        else:
            body, _, cls_s = tok[1:].partition(":")
            r = C.CORNER_RADIUS.get(int(cls_s), 90.0)
            deg = float(body)
            raw.append(TR.Segment(tok[0], math.radians(deg) * r, r,
                                  math.radians(deg) * (1 if tok[0] == "R" else -1), int(cls_s)))
    arco = sum(s.length for s in raw if s.kind != "S")
    dritti = sum(s.length for s in raw if s.kind == "S")
    if dritti <= 0 or arco >= lunghezza_m * 0.8:
        return None
    k = (lunghezza_m - arco) / dritti
    for s in raw:
        if s.kind == "S":
            s.length *= k
    return raw if TR._chiudi(raw, lunghezza_m) else None


def _pianta(segmenti: list, passo: float = 5.0) -> list:
    """I punti del tracciato in metri, ogni `passo`, dal traguardo."""
    x = y = th = 0.0
    pts = []
    for s in segmenti:
        n = max(1, int(round(s.length / passo)))
        dth = -s.turn / n if s.kind != "S" else 0.0
        for _ in range(n):
            th += dth
            x += math.cos(th) * s.length / n
            y += math.sin(th) * s.length / n
            pts.append((x, y))
    return pts


def _troppo_vicino(pts: list, minima: float, passo: float = 5.0) -> bool:
    """Due pezzi di pista lontani lungo il giro ma vicini sulla carta."""
    q = pts[::3]
    n = len(q)
    salto = int(max(minima * 3.0, 150.0) / (passo * 3))
    for i in range(n):
        xi, yi = q[i]
        for j in range(i + salto, n):
            if n - (j - i) < salto:
                break
            if (q[j][0] - xi) ** 2 + (q[j][1] - yi) ** 2 < minima * minima:
                return True
    return False


def valuta(segmenti: list, stile: str) -> dict:
    """Quanto e' buono per passare: le staccate, una per una, e il totale.

    Una staccata vale per quanto e' lungo il dritto che la precede - la scia
    si prende in metri - per quanto e' lenta la curva in fondo, e per quanto
    e' lenta quella da cui si esce, che dice quanto si arriva attaccati.
    """
    lungo = DRITTO_STACCATA[stile][0]
    posti = []
    n = len(segmenti)
    for i, s in enumerate(segmenti):
        if s.kind != "S":
            continue
        # il dritto vero: rettilinei e curvoni in fila fino alla prossima curva
        dritto = s.length
        j = (i + 1) % n
        while segmenti[j].kind == "S" or segmenti[j].speed_class >= 5:
            dritto += segmenti[j].length
            j = (j + 1) % n
            if j == i:
                break
        fondo = segmenti[j]
        if fondo.kind == "S":
            continue
        k = (i - 1) % n
        while segmenti[k].kind == "S" and k != i:
            k = (k - 1) % n
        prima = segmenti[k].speed_class if segmenti[k].kind != "S" else 3
        uscita = 1.0 if prima in LENTE else (0.8 if prima == 3 else 0.55)
        valore = (max(0.0, min(1.0, (dritto - 80.0) / lungo)) * FRENATA.get(fondo.speed_class, 0.3)
                  * uscita)
        if valore > 0.05:
            posti.append(round(valore, 3))
    posti.sort(reverse=True)
    punti = sum(v * w for v, w in zip(posti, (1.0, 0.8, 0.6, 0.3)))
    return {"posti": posti, "punti": round(punti, 3)}


def disegna(lunghezza_km: float, curve: int, stile: str = "citta", seme: int = 0,
            prove: int = 400) -> dict | None:
    """Il miglior tracciato fra `prove` tentativi: layout, punteggio, pianta."""
    rng = random.Random(seme)
    target = lunghezza_km * 1000.0
    migliore = None
    for _ in range(prove):
        pezzi = _componi(stile, curve, rng)
        if pezzi is None:
            continue
        layout = _stringa(pezzi)
        seg = _segmenti(layout, target)
        if seg is None:
            continue
        pts = _pianta(seg)
        if TR.incroci(pts) or _troppo_vicino(pts, DISTANZA_MINIMA_M):
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        proporzione = max(w, h) / max(1.0, min(w, h))
        if proporzione > PROPORZIONE_MAX:
            continue
        voto = valuta(seg, stile)
        # a parita' di posti, meglio compatto: un circuito cittadino sta in
        # un quartiere, non lungo un viale di tre chilometri
        punti = voto["punti"] - 0.05 * (proporzione - 1.0)
        if migliore is None or punti > migliore["punti"]:
            migliore = {"layout": layout, "punti": punti, "posti": voto["posti"],
                        "curve": sum(1 for s in seg if s.kind != "S"),
                        "proporzione": round(proporzione, 2), "pianta": pts}
    return migliore


def sorpassi_da_voto(punti: float) -> float:
    """Il carattere 'sorpasso' di un circuito, dal punteggio del progettista.

    Tarato sulle piste vere: una sola staccata buona fa un circuito dove si
    passa poco, tre staccate buone ne fanno uno dove si passa sempre.
    """
    return round(max(0.2, min(0.9, 0.12 + 0.30 * punti)), 2)
