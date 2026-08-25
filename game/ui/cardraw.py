"""La monoposto vista dall'alto, disegnata a poligoni.

Serve a rendere toccabile quello che finora era una lista: si guarda la
macchina, si clicca il pezzo e si vede com'e' messo. Ogni forma sa a quale
componente corrisponde, e chi disegna decide di che colore.

Le proporzioni sono quelle vere: 5,6 metri per 2, cioe' una macchina lunga
quasi tre volte la sua larghezza. Il rettangolo che si passa puo' avere la
forma che vuole - dentro ci si ricava l'area giusta e la si centra, cosi' la
monoposto non viene mai schiacciata ne' stirata.

Le coordinate delle forme sono normalizzate 0..1 su quell'area, con x da
sinistra a destra e y dal muso alla coda.
"""
from __future__ import annotations

import pygame

from . import theme as T

# Lunghezza diviso larghezza di una monoposto moderna.
RATIO = 2.80

# Le forme non sono disegnate a mano: sono tracciate. Si e' presa una foto
# dall'alto di una monoposto, si e' separata dallo sfondo (sfocatura a
# blocchi per togliere la grana del cemento, sfondo stimato colonna per
# colonna, e la grana stessa usata per distinguere il cemento dal nero liscio
# della macchina) e si e' misurata la carrozzeria colonna per colonna: 407
# sezioni, da cui esce il profilo delle semilarghezze. I poligoni qui sotto
# sono quel profilo, campionato e reso simmetrico.
#
# Coordinate 0..1 sul rettangolo: x da un bordo all'altro (la larghezza fra le
# gomme), y dal muso alla coda.
# --- pianta dell'ala anteriore ----------------------------------------------
# Le punte stanno dentro all'ingombro delle gomme, e i due lati lunghi non
# corrono paralleli: convergono verso la punta. La corda e' profonda al centro
# e si assottiglia fuori, come su un'ala vera vista dall'alto.
ALA_MEZZA = 0.400          # semi-apertura, in frazione della larghezza
# Quanto e' profonda: il bordo d'entrata resta dov'e' e quello d'uscita si
# avvicina. Un numero solo, perche' della corda vive tutta l'ala - flap
# mobile, profili, paratie - e devono accorciarsi insieme.
ALA_CORDA = 0.70


def ala_entrata(u: float) -> float:
    """Dove passa il bordo d'entrata a quella distanza dal centro."""
    return 0.022 + 0.044 * (abs(u) / ALA_MEZZA) ** 1.7


def ala_uscita(u: float) -> float:
    """Dove passa il bordo d'uscita. Anche il retro dell'ala e' a freccia.

    Fuori sta su un piano arretrato, verso la punta rientra un poco, e verso
    il centro rientra parecchio: i flap si accorciano avvicinandosi al muso,
    ed e' la linea su cui stanno i loghi tondi nelle livree vere.
    """
    f = abs(u) / ALA_MEZZA
    fuori = 0.196 - 0.036 * max(0.0, (f - 0.72) / 0.28) ** 1.5
    dentro = 0.061 * min(1.0, max(0.0, (0.40 - f) / 0.25)) ** 1.3
    return ala_entrata(u) + (fuori - dentro - ala_entrata(u)) * ALA_CORDA


def _ala_pianta(dentro: float = 1.0, da: float = 0.0, a: float = 1.0) -> list:
    """Il poligono dell'ala, o una sua fetta fra due frazioni di corda."""
    passi = [(-1 + 2 * i / 16.0) * ALA_MEZZA * dentro for i in range(17)]
    davanti, dietro = [], []
    for u in passi:
        e, x = ala_entrata(u), ala_uscita(u)
        davanti.append((0.5 + u, e + (x - e) * da))
        dietro.append((0.5 + u, e + (x - e) * a))
    return davanti + list(reversed(dietro))


SHAPES = {
    # il fondo: sotto tutto, sporge di poco dalla carrozzeria e si riapre nel
    # diffusore
    "floor": [[(0.620, 0.255), (0.715, 0.310), (0.800, 0.360),
               (0.862, 0.420), (0.892, 0.500), (0.895, 0.580),
               (0.876, 0.660), (0.832, 0.720), (0.786, 0.780),
               (0.766, 0.840), (0.796, 0.885), (0.204, 0.885),
               (0.234, 0.840), (0.214, 0.780), (0.168, 0.720),
               (0.124, 0.660), (0.105, 0.580), (0.108, 0.500),
               (0.138, 0.420), (0.200, 0.360), (0.285, 0.310),
               (0.380, 0.255)]],
    # ala anteriore: non e' una tavola dritta. Il bordo d'entrata e' a freccia
    # - avanti al centro, indietro alle estremita' - e la corda e' profonda,
    # un settimo della macchina. Misurata sulla foto stazione per stazione
    "front_wing": [None],          # riempito sotto: viene dalla pianta
    # muso e cellula: dal tracciato, ripulito dai sobbalzi delle sospensioni
    "chassis": [[(0.526, 0.018), (0.550, 0.060), (0.560, 0.120),
                 (0.572, 0.200), (0.590, 0.280), (0.606, 0.340),
                 (0.620, 0.400), (0.630, 0.460), (0.632, 0.520),
                 (0.626, 0.570), (0.374, 0.570), (0.368, 0.520),
                 (0.370, 0.460), (0.380, 0.400), (0.394, 0.340),
                 (0.410, 0.280), (0.428, 0.200), (0.440, 0.120),
                 (0.450, 0.060), (0.474, 0.018)]],
    # sospensioni: i bracci fino al mozzo
    "suspension": [[(0.408, 0.172), (0.128, 0.148), (0.128, 0.176), (0.414, 0.202)],
                   [(0.400, 0.252), (0.128, 0.234), (0.128, 0.260), (0.406, 0.282)],
                   [(0.322, 0.752), (0.146, 0.738), (0.146, 0.764), (0.328, 0.778)],
                   [(0.312, 0.816), (0.146, 0.804), (0.146, 0.828), (0.318, 0.842)]],
    # impianto frenante: le prese d'aria sulle ruote
    "brakes": [[(0.178, 0.180), (0.212, 0.180), (0.212, 0.282), (0.178, 0.282)],
               [(0.214, 0.788), (0.250, 0.788), (0.250, 0.884), (0.214, 0.884)]],
    # fiancate e cofano: il pezzo tracciato piu' fedelmente, perche' e' quello
    # che si riconosce. Larghissimo a meta' macchina, e finisce di colpo
    "sidepods": [[(0.738, 0.385), (0.823, 0.410), (0.826, 0.440),
                  (0.852, 0.470), (0.863, 0.500), (0.869, 0.530),
                  (0.869, 0.560), (0.860, 0.600), (0.843, 0.640),
                  (0.831, 0.680), (0.794, 0.710), (0.735, 0.735),
                  (0.658, 0.755), (0.342, 0.755), (0.265, 0.735),
                  (0.206, 0.710), (0.169, 0.680), (0.157, 0.640),
                  (0.140, 0.600), (0.131, 0.560), (0.131, 0.530),
                  (0.137, 0.500), (0.148, 0.470), (0.174, 0.440),
                  (0.177, 0.410), (0.262, 0.385)]],
    # raffreddamento: la bocca del radiatore e lo sfogo lungo la schiena
    "cooling": [[(0.212, 0.418), (0.318, 0.392), (0.348, 0.420), (0.244, 0.452)],
                [(0.436, 0.560), (0.564, 0.560), (0.556, 0.716), (0.444, 0.716)]],
    # trasmissione: quello che resta dietro le fiancate
    "gearbox": [[(0.658, 0.752), (0.616, 0.800), (0.584, 0.845),
                 (0.563, 0.875), (0.545, 0.900), (0.455, 0.900),
                 (0.437, 0.875), (0.416, 0.845), (0.384, 0.800),
                 (0.342, 0.752)]],
    # ala posteriore: larga poco piu' di meta' macchina, contro l'anteriore
    # che e' larga quanto tutta
    "rear_wing": [[(0.380, 0.892), (0.620, 0.892), (0.556, 0.918), (0.444, 0.918)],
                  [(0.284, 0.914), (0.716, 0.914), (0.716, 0.950), (0.284, 0.950)],
                  [(0.258, 0.890), (0.304, 0.890), (0.304, 0.998), (0.258, 0.998)]],
    # aero attiva: il profilo mobile dietro e i flap mobili davanti
    # aero attiva: il profilo mobile dietro e il flap mobile davanti, che e'
    # l'ultima fetta dell'ala anteriore e ne segue la forma
    "active_aero": [[(0.304, 0.952), (0.696, 0.952), (0.696, 0.990), (0.304, 0.990)],
                    None],
}

# l'ala e il suo flap si ricavano dalla pianta, cosi' non possono discordare
SHAPES["front_wing"] = [_ala_pianta(), _ala_pianta(1.0, 0.86, 1.0)]
SHAPES["active_aero"][1] = _ala_pianta(0.96, 0.60, 0.86)


# Alcuni pezzi stanno su tutti e due i lati: si disegnano specchiati. I
# poligoni gia' simmetrici si ricalcano su se stessi e non cambia niente.
MIRRORED = ("sidepods", "suspension", "brakes", "cooling", "front_wing",
            "rear_wing", "active_aero")

# Le ruote non sono un componente ma senza non si capisce cos'e'.
# Misure vere: gomma anteriore larga 305 mm, posteriore 405, diametro 720 su
# una macchina larga 2 metri e lunga 5,6. Vista dall'alto sono rettangoli molto
# piu' lunghi che larghi, ed e' per questo che una monoposto si riconosce.
WHEELS = [(0.026, 0.166, 0.152, 0.130), (0.822, 0.166, 0.152, 0.130),
          (0.010, 0.776, 0.212, 0.136), (0.778, 0.776, 0.212, 0.136)]


# Il corpo vettura si disegna grigio: il colore qui vuol dire quanto quel pezzo
# e' buono rispetto agli altri, e mescolarlo con quello della squadra darebbe
# un marrone che non dice niente. Il colore della scuderia torna sulla livrea.
CORPO = (62, 71, 88)


def tinta(quanto, acceso: bool = False) -> tuple:
    """Colore di un componente: da -1 (ultimi della griglia) a +1 (i migliori)."""
    if quanto is None:
        return CORPO if acceso else tuple(int(c * 0.8) for c in CORPO)
    d = max(-1.0, min(1.0, float(quanto)))
    col = T.mix(CORPO, T.OK if d >= 0 else T.BAD, 0.22 + 0.58 * abs(d))
    return col if acceso else tuple(int(c * 0.78) for c in col)


def area(rect) -> pygame.Rect:
    """L'area con le proporzioni giuste, centrata dentro il rettangolo dato.

    Se il riquadro e' piu' largo che alto la macchina non si allarga: si
    restringe e si mette in mezzo. E' l'unico modo perche' una monoposto
    somigli a una monoposto in un pannello di forma qualunque.
    """
    rect = pygame.Rect(rect)
    w = min(rect.w, rect.h / RATIO)
    h = w * RATIO
    return pygame.Rect(int(rect.centerx - w / 2), int(rect.centery - h / 2),
                       max(1, int(w)), max(1, int(h)))


def _pts(poly, r, mirror=False):
    out = []
    for x, y in poly:
        xx = (1.0 - x) if mirror else x
        out.append((r.x + xx * r.w, r.y + y * r.h))
    return out


def polygons(part: str, rect) -> list:
    """I poligoni di quel componente sul rettangolo dato."""
    base = SHAPES.get(part)
    if not base:
        return []
    r = area(rect)
    fuori = [_pts(p, r) for p in base]
    if part in MIRRORED:
        fuori += [_pts(p, r, mirror=True) for p in base]
    return fuori


# In che ordine si cerca chi e' stato cliccato: prima i pezzi piccoli che
# stanno sopra, per ultimi telaio e fondo che fanno da base a tutto.
# Chi risponde per primo al clic. Le fiancate adesso sono un pezzo solo - la
# goccia che comprende anche il cofano - e coprono anche il centro della
# macchina: percio' muso e raffreddamento si cercano prima, se no cliccando
# sull'abitacolo si sceglierebbe una fiancata.
HIT_ORDER = ("brakes", "suspension", "cooling", "chassis", "gearbox",
             "sidepods", "active_aero", "rear_wing", "front_wing", "floor")


def hit(rect, pos) -> str | None:
    """Quale componente sta sotto quel punto. Il fondo e' l'ultimo a rispondere."""
    for part in [k for k in HIT_ORDER if k in SHAPES]:
        for poly in polygons(part, rect):
            if _inside(poly, pos):
                return part
    return None


def _inside(poly, pos) -> bool:
    x, y = pos
    dentro = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xx = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < xx:
                dentro = not dentro
    return dentro


# In quest'ordine si dipinge: quello che sta sotto per primo.
ORDINE = ("floor", "front_wing", "rear_wing", "suspension", "brakes", "chassis",
          "sidepods", "cooling", "gearbox", "active_aero")


def draw(surf, rect, colours: dict, selected: str = "", badges: dict = None,
         livery=None) -> None:
    """Disegna la monoposto colorando ogni componente come si e' chiesto.

    `colours` da' il colore di riempimento per componente, `badges` un pallino
    d'accento su quelli che hanno qualcosa da dire - un pezzo nuovo montato,
    uno che sta per cedere. `livery` e' il colore della squadra, che va sul
    muso e sulle paratie e non c'entra con come sta messo un pezzo.
    """
    rect = pygame.Rect(rect)
    r = area(rect)
    badges = badges or {}

    _ombra(surf, r)
    # cofano motore e airbox: non sono un componente da sviluppare, ma senza
    # di loro fra abitacolo e cambio ci sarebbe un buco
    base = colours.get("chassis", T.PANEL_3)
    pygame.draw.polygon(surf, tuple(int(c * 0.72) for c in base),
                        _pts([(0.424, 0.462), (0.576, 0.462), (0.560, 0.640),
                              (0.548, 0.742), (0.452, 0.742), (0.440, 0.640)], r))

    for part in ORDINE:
        if part not in SHAPES:
            continue
        col = colours.get(part, T.PANEL_3)
        if part == "floor":
            # il fondo sta sotto tutto: scurito, se no copre la macchina
            col = tuple(int(c * 0.55) for c in col)
        for poly in polygons(part, rect):
            pygame.draw.polygon(surf, col, poly)
            bordo = T.WHITE if part == selected else tuple(int(c * 0.55) for c in col)
            pygame.draw.polygon(surf, bordo, poly, 2 if part == selected else 1)

    # le gomme vanno sopra le ali: nella realta' l'ala anteriore arriva fin
    # sotto la ruota, e a disegnarla per ultima sembrava che la coprisse
    _gomme(surf, r)
    _profili(surf, r, colours)
    _abitacolo(surf, r)
    if livery:
        _livrea(surf, r, livery)
    _diffusore(surf, r, colours.get("floor", T.PANEL_3))

    for part, segno in badges.items():
        if part == "floor" or part not in SHAPES:
            continue
        cx, cy = label_pos(part, rect)
        pygame.draw.circle(surf, segno, (cx, cy), 5)
        pygame.draw.circle(surf, (10, 14, 20), (cx, cy), 5, 1)


def _ombra(surf, r) -> None:
    """Un'ombra che segue il fondo: stacca la macchina dal pannello."""
    pygame.draw.polygon(surf, T.mix(T.PANEL, (0, 0, 0), 0.45),
                        _pts([(0.376, 0.270), (0.194, 0.330), (0.160, 0.420),
                              (0.168, 0.560), (0.240, 0.730), (0.246, 0.812),
                              (0.222, 0.898), (0.778, 0.898), (0.754, 0.812),
                              (0.760, 0.730), (0.832, 0.560), (0.840, 0.420),
                              (0.806, 0.330), (0.624, 0.270)], r))


def _gomme(surf, r) -> None:
    for wx, wy, ww, wh in WHEELS:
        g = pygame.Rect(int(r.x + wx * r.w), int(r.y + wy * r.h),
                        max(2, int(ww * r.w)), max(2, int(wh * r.h)))
        raggio = max(2, int(g.w * 0.28))
        pygame.draw.rect(surf, (24, 26, 31), g, border_radius=raggio)
        pygame.draw.rect(surf, (54, 58, 66), g, 1, border_radius=raggio)
        if g.w > 12:
            pygame.draw.line(surf, (44, 48, 56), (g.centerx, g.y + 3),
                             (g.centerx, g.bottom - 3))


def _profili(surf, r, colours) -> None:
    """I profili delle ali: si vedono solo se la macchina e' disegnata grande.

    Da lontano sarebbero sporco; da vicino sono quello che distingue un'ala da
    una tavola.
    """
    if r.w < 150:
        return
    # i profili dell'ala anteriore seguono la corda: nascono e finiscono dove
    # nasce e finisce l'ala, percio' non possono sbordare
    col = colours.get("front_wing", T.PANEL_3)
    scuro = tuple(int(c * 0.45) for c in col)
    for quota in (0.24, 0.46, 0.68):
        punti = []
        for i in range(25):
            u = (-1 + 2 * i / 24.0) * ALA_MEZZA * 0.97
            e, x = ala_entrata(u), ala_uscita(u)
            punti.append((int(r.x + (0.5 + u) * r.w),
                          int(r.y + (e + (x - e) * quota) * r.h)))
        pygame.draw.lines(surf, scuro, False, punti)
    col = colours.get("rear_wing", T.PANEL_3)
    scuro = tuple(int(c * 0.45) for c in col)
    for v in (0.924, 0.938):
        pygame.draw.line(surf, scuro, (int(r.x + 0.294 * r.w), int(r.y + v * r.h)),
                         (int(r.x + 0.706 * r.w), int(r.y + v * r.h)))


def _abitacolo(surf, r) -> None:
    """Pozzetto e halo: non si sviluppano, ma senza non si capisce cos'e'."""
    raggio = max(3, int(0.082 * r.w))
    cx = r.x + int(0.5 * r.w)
    cy = r.y + int(0.446 * r.h)
    box = (cx - raggio, cy - int(raggio * 1.35), raggio * 2, int(raggio * 2.7))
    pygame.draw.ellipse(surf, (12, 16, 24), box)
    pygame.draw.ellipse(surf, (168, 178, 196), box, 2)
    pygame.draw.line(surf, (168, 178, 196),
                     (cx, r.y + int(0.360 * r.h)), (cx, r.y + int(0.408 * r.h)), 3)
    if r.w > 90:
        for x in (0.360, 0.640):     # specchietti
            pygame.draw.rect(surf, (120, 130, 150),
                             (int(r.x + x * r.w - 0.030 * r.w),
                              int(r.y + 0.402 * r.h),
                              max(2, int(0.060 * r.w)), max(2, int(0.016 * r.h))),
                             border_radius=2)


def _livrea(surf, r, colore) -> None:
    """Il colore della squadra: sul muso e sulle paratie, non sui pezzi.

    Sui componenti il colore dice come stanno messi: metterci sopra anche
    quello della scuderia vorrebbe dire non capire piu' ne' l'uno ne' l'altro.
    """
    colore = tuple(colore)
    pygame.draw.polygon(surf, colore, _pts([(0.492, 0.060), (0.508, 0.060),
                                            (0.530, 0.330), (0.470, 0.330)], r))
    pygame.draw.polygon(surf, colore, _pts([(0.490, 0.700), (0.510, 0.700),
                                            (0.510, 0.900), (0.490, 0.900)], r))
    for poly in ([(0.258, 0.906), (0.304, 0.906), (0.304, 0.998), (0.258, 0.998)],
                 [(0.742, 0.906), (0.696, 0.906), (0.696, 0.998), (0.742, 0.998)],
                 # le paratie si appoggiano alla punta dell'ala, dovunque stia
                 [(0.5 - ALA_MEZZA, ala_entrata(ALA_MEZZA)),
                  (0.534 - ALA_MEZZA, ala_entrata(ALA_MEZZA - 0.034)),
                  (0.534 - ALA_MEZZA, ala_uscita(ALA_MEZZA - 0.034)),
                  (0.5 - ALA_MEZZA, ala_uscita(ALA_MEZZA))],
                 [(0.5 + ALA_MEZZA, ala_entrata(ALA_MEZZA)),
                  (0.466 + ALA_MEZZA, ala_entrata(ALA_MEZZA - 0.034)),
                  (0.466 + ALA_MEZZA, ala_uscita(ALA_MEZZA - 0.034)),
                  (0.5 + ALA_MEZZA, ala_uscita(ALA_MEZZA))]):
        pygame.draw.polygon(surf, colore, _pts(poly, r))


def _diffusore(surf, r, colore) -> None:
    """L'ultimo pezzo di fondo, quello che chiude il lavoro."""
    scuro = tuple(int(c * 0.35) for c in colore)
    pygame.draw.polygon(surf, scuro, _pts([(0.256, 0.848), (0.744, 0.848),
                                           (0.766, 0.884), (0.234, 0.884)], r))
    if r.w > 90:
        for x in (0.330, 0.415, 0.585, 0.670):
            pygame.draw.line(surf, tuple(int(c * 0.2) for c in colore),
                             (int(r.x + x * r.w), int(r.y + 0.856 * r.h)),
                             (int(r.x + x * r.w), int(r.y + 0.884 * r.h)))


def wheels(surf, rect) -> None:
    """Le gomme si disegnano dentro `draw`: resta per chi la chiamava prima."""
    return None


def floor_badge(surf, rect, colour) -> None:
    """Il pallino del fondo, che si disegna dopo tutto il resto per vedersi."""
    r = area(rect)
    cx = r.x + int(0.5 * r.w)
    cy = r.y + int(0.83 * r.h)
    pygame.draw.circle(surf, colour, (cx, cy), 5)
    pygame.draw.circle(surf, (10, 14, 20), (cx, cy), 5, 1)


def label_pos(part: str, rect) -> tuple:
    """Il centro del componente, per attaccarci una scritta."""
    poly = polygons(part, rect)
    if not poly:
        r = pygame.Rect(rect)
        return (r.centerx, r.centery)
    p = poly[0]
    return (int(sum(q[0] for q in p) / len(p)), int(sum(q[1] for q in p) / len(p)))
