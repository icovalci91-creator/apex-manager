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

# Ogni componente e' fatto di uno o piu' poligoni. Sono scritti a mano
# guardando una monoposto a effetto suolo: muso stretto attaccato all'ala,
# pance che si stringono verso il retrotreno, fondo largo che lavora fino al
# diffusore, ali a piu' profili.
# Le forme vengono da una foto dall'alto di una monoposto, letta sezione per
# sezione: per ogni fetta della macchina si e' guardato dove comincia e dove
# finisce la carrozzeria. Il numero che ha cambiato tutto e' la larghezza a
# meta' vettura: il corpo arriva al 74% della larghezza totale, non a meta'
# come si tende a disegnarlo. Da li' in poi il resto viene da se'.
#
# Coordinate 0..1 sul rettangolo: x da un bordo all'altro (che e' anche la
# distanza fra le due gomme), y dal muso alla coda.
SHAPES = {
    # il fondo: la piattaforma piu' larga di tutto, si stringe davanti per far
    # passare le ruote anteriori e si riapre nel diffusore
    "floor": [[(0.350, 0.256), (0.286, 0.272), (0.224, 0.304), (0.170, 0.358),
               (0.124, 0.432), (0.104, 0.512), (0.107, 0.598), (0.132, 0.666),
               (0.178, 0.722), (0.224, 0.770), (0.242, 0.820), (0.234, 0.882),
               (0.766, 0.882), (0.758, 0.820), (0.776, 0.770), (0.822, 0.722),
               (0.868, 0.666), (0.893, 0.598), (0.896, 0.512), (0.876, 0.432),
               (0.830, 0.358), (0.776, 0.304), (0.714, 0.272), (0.650, 0.256)]],
    # ala anteriore: larga quanto la macchina, con le paratie inclinate
    "front_wing": [[(0.012, 0.012), (0.988, 0.012), (0.988, 0.098), (0.012, 0.098)],
                   [(0.000, 0.002), (0.056, 0.006), (0.078, 0.138), (0.018, 0.142)]],
    # muso e cellula: sottile davanti, largo all'abitacolo
    "chassis": [[(0.478, 0.022), (0.522, 0.022), (0.534, 0.100), (0.548, 0.180),
                 (0.566, 0.250), (0.590, 0.320), (0.614, 0.396), (0.626, 0.456),
                 (0.622, 0.530), (0.378, 0.530), (0.374, 0.456), (0.386, 0.396),
                 (0.410, 0.320), (0.434, 0.250), (0.452, 0.180), (0.466, 0.100)]],
    # sospensioni: i bracci fino al mozzo
    "suspension": [[(0.408, 0.172), (0.128, 0.148), (0.128, 0.176), (0.414, 0.202)],
                   [(0.400, 0.252), (0.128, 0.234), (0.128, 0.260), (0.406, 0.282)],
                   [(0.310, 0.752), (0.146, 0.738), (0.146, 0.764), (0.316, 0.778)],
                   [(0.300, 0.816), (0.146, 0.804), (0.146, 0.828), (0.306, 0.842)]],
    # impianto frenante: le prese d'aria sulle ruote
    "brakes": [[(0.178, 0.180), (0.212, 0.180), (0.212, 0.282), (0.178, 0.282)],
               [(0.214, 0.788), (0.250, 0.788), (0.250, 0.884), (0.214, 0.884)]],
    # fiancate e cofano: una goccia sola, larghissima a meta' macchina e
    # strettissima al cambio. E' la forma che si riconosce da lontano
    "sidepods": [[(0.432, 0.376), (0.368, 0.388), (0.296, 0.408), (0.232, 0.440),
                  (0.180, 0.486), (0.146, 0.544), (0.144, 0.598), (0.166, 0.648),
                  (0.210, 0.694), (0.272, 0.732), (0.348, 0.758), (0.416, 0.774),
                  (0.446, 0.742), (0.444, 0.404)]],
    # raffreddamento: la bocca del radiatore e lo sfogo lungo la schiena
    "cooling": [[(0.236, 0.442), (0.334, 0.408), (0.366, 0.434), (0.272, 0.478)],
                [(0.436, 0.542), (0.564, 0.542), (0.556, 0.702), (0.444, 0.702)]],
    # trasmissione: il cambio, che chiude la macchina
    "gearbox": [[(0.452, 0.740), (0.548, 0.740), (0.536, 0.808), (0.528, 0.876),
                 (0.472, 0.876), (0.464, 0.808)]],
    # ala posteriore: pilone, profilo e paratie. Larga poco piu' di meta'
    # macchina, contro l'anteriore che e' larga quanto tutta
    "rear_wing": [[(0.368, 0.878), (0.632, 0.878), (0.556, 0.912), (0.444, 0.912)],
                  [(0.284, 0.908), (0.716, 0.908), (0.716, 0.944), (0.284, 0.944)],
                  [(0.258, 0.884), (0.304, 0.884), (0.304, 0.996), (0.258, 0.996)]],
    # aero attiva: il profilo mobile dietro e i flap mobili davanti
    "active_aero": [[(0.304, 0.948), (0.696, 0.948), (0.696, 0.986), (0.304, 0.986)],
                    [(0.078, 0.018), (0.430, 0.018), (0.430, 0.050), (0.078, 0.050)]],
}

# Alcuni pezzi stanno su tutti e due i lati: si disegnano specchiati. I
# poligoni gia' simmetrici si ricalcano su se stessi e non cambia niente.
MIRRORED = ("sidepods", "suspension", "brakes", "cooling", "front_wing",
            "rear_wing", "active_aero")

# Le ruote non sono un componente ma senza non si capisce cos'e'.
# Misure vere: gomma anteriore larga 305 mm, posteriore 405, diametro 720 su
# una macchina larga 2 metri e lunga 5,6. Vista dall'alto sono rettangoli molto
# piu' lunghi che larghi, ed e' per questo che una monoposto si riconosce.
WHEELS = [(0.025, 0.166, 0.150, 0.129), (0.825, 0.166, 0.150, 0.129),
          (0.013, 0.780, 0.200, 0.129), (0.787, 0.780, 0.200, 0.129)]


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
HIT_ORDER = ("brakes", "suspension", "cooling", "sidepods", "gearbox",
             "active_aero", "rear_wing", "front_wing", "chassis", "floor")


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
    _gomme(surf, r)
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
    for parte, quote in (("front_wing", (0.026, 0.044, 0.062)),
                         ("rear_wing", (0.918, 0.930))):
        col = colours.get(parte, T.PANEL_3)
        scuro = tuple(int(c * 0.45) for c in col)
        largo = 0.492 if parte == "front_wing" else 0.226
        for v in quote:
            pygame.draw.line(surf, scuro,
                             (int(r.x + (0.5 - largo) * r.w), int(r.y + v * r.h)),
                             (int(r.x + (0.5 + largo) * r.w), int(r.y + v * r.h)))


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
    pygame.draw.polygon(surf, colore, _pts([(0.491, 0.048), (0.509, 0.048),
                                            (0.524, 0.300), (0.476, 0.300)], r))
    pygame.draw.polygon(surf, colore, _pts([(0.490, 0.664), (0.510, 0.664),
                                            (0.510, 0.896), (0.490, 0.896)], r))
    for poly in ([(0.246, 0.898), (0.292, 0.898), (0.292, 0.996), (0.246, 0.996)],
                 [(0.754, 0.898), (0.708, 0.898), (0.708, 0.996), (0.754, 0.996)],
                 [(0.006, 0.046), (0.062, 0.049), (0.078, 0.124), (0.020, 0.130)],
                 [(0.994, 0.046), (0.938, 0.049), (0.922, 0.124), (0.980, 0.130)]):
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
