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
SHAPES = {
    # il fondo: la piattaforma che tiene insieme tutto e fa il carico
    "floor": [[(0.380, 0.268), (0.255, 0.286), (0.200, 0.330), (0.170, 0.430),
               (0.178, 0.560), (0.214, 0.660), (0.250, 0.730), (0.256, 0.812),
               (0.232, 0.888), (0.768, 0.888), (0.744, 0.812), (0.750, 0.730),
               (0.786, 0.660), (0.822, 0.560), (0.830, 0.430), (0.800, 0.330),
               (0.745, 0.286), (0.620, 0.268)]],
    # ala anteriore: profilo principale largo quanto la macchina e paratie
    "front_wing": [[(0.008, 0.008), (0.992, 0.008), (0.992, 0.082), (0.008, 0.082)],
                   [(0.000, 0.000), (0.060, 0.000), (0.082, 0.128), (0.022, 0.128)]],
    # muso e cellula di sopravvivenza: sottile davanti, larga all'abitacolo
    "chassis": [[(0.478, 0.030), (0.522, 0.030), (0.540, 0.150), (0.558, 0.245),
                 (0.582, 0.335), (0.592, 0.430), (0.586, 0.530), (0.414, 0.530),
                 (0.408, 0.430), (0.418, 0.335), (0.442, 0.245), (0.460, 0.150)]],
    # sospensioni: i bracci davanti e dietro, verso le ruote
    "suspension": [[(0.425, 0.175), (0.170, 0.150), (0.170, 0.178), (0.430, 0.205)],
                   [(0.418, 0.255), (0.170, 0.235), (0.170, 0.262), (0.422, 0.285)],
                   [(0.430, 0.735), (0.200, 0.715), (0.200, 0.742), (0.434, 0.762)],
                   [(0.434, 0.815), (0.200, 0.800), (0.200, 0.826), (0.438, 0.842)]],
    # impianto frenante: le prese d'aria davanti alle ruote
    "brakes": [[(0.182, 0.165), (0.210, 0.165), (0.210, 0.270), (0.182, 0.270)],
               [(0.200, 0.725), (0.232, 0.725), (0.232, 0.845), (0.200, 0.845)]],
    # fiancate: la pancia larga a meta' vettura che si stringe dietro
    "sidepods": [[(0.412, 0.360), (0.250, 0.372), (0.182, 0.410), (0.164, 0.480),
                  (0.180, 0.575), (0.238, 0.650), (0.330, 0.706), (0.408, 0.730),
                  (0.430, 0.700), (0.430, 0.395)]],
    # raffreddamento: bocche dei radiatori e sfogo sul cofano
    "cooling": [[(0.184, 0.398), (0.360, 0.380), (0.360, 0.412), (0.178, 0.436)],
                [(0.442, 0.548), (0.558, 0.548), (0.550, 0.640), (0.450, 0.640)]],
    # trasmissione: il cambio, dietro al motore
    "gearbox": [[(0.454, 0.720), (0.546, 0.720), (0.534, 0.800), (0.528, 0.870),
                 (0.472, 0.870), (0.466, 0.800)]],
    # ala posteriore: pilone, profilo principale e paratie
    "rear_wing": [[(0.350, 0.876), (0.650, 0.876), (0.555, 0.918), (0.445, 0.918)],
                  [(0.238, 0.912), (0.762, 0.912), (0.762, 0.948), (0.238, 0.948)],
                  [(0.212, 0.888), (0.256, 0.888), (0.256, 0.996), (0.212, 0.996)]],
    # aero attiva: il profilo mobile dietro e i flap mobili davanti
    "active_aero": [[(0.256, 0.952), (0.744, 0.952), (0.744, 0.988), (0.256, 0.988)],
                    [(0.070, 0.014), (0.430, 0.014), (0.430, 0.040), (0.070, 0.040)]],
}

# Alcuni pezzi stanno su tutti e due i lati: si disegnano specchiati. I
# poligoni gia' simmetrici si ricalcano su se stessi e non cambia niente.
MIRRORED = ("sidepods", "suspension", "brakes", "cooling", "front_wing",
            "rear_wing", "active_aero")

# Le ruote non sono un componente ma senza non si capisce cos'e'.
WHEELS = [(0.025, 0.145, 0.155, 0.145), (0.820, 0.145, 0.155, 0.145),
          (0.030, 0.705, 0.200, 0.160), (0.770, 0.705, 0.200, 0.160)]


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
                        _pts([(0.430, 0.470), (0.570, 0.470), (0.556, 0.640),
                              (0.546, 0.740), (0.454, 0.740), (0.444, 0.640)], r))

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
                        _pts([(0.370, 0.276), (0.190, 0.338), (0.160, 0.430),
                              (0.168, 0.560), (0.242, 0.740), (0.248, 0.820),
                              (0.224, 0.900), (0.776, 0.900), (0.752, 0.820),
                              (0.758, 0.740), (0.832, 0.560), (0.840, 0.430),
                              (0.810, 0.338), (0.630, 0.276)], r))


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


def _abitacolo(surf, r) -> None:
    """Pozzetto e halo: non si sviluppano, ma senza non si capisce cos'e'."""
    raggio = max(3, int(0.062 * r.w))
    cx = r.x + int(0.5 * r.w)
    cy = r.y + int(0.432 * r.h)
    box = (cx - raggio, cy - int(raggio * 1.5), raggio * 2, int(raggio * 3.0))
    pygame.draw.ellipse(surf, (12, 16, 24), box)
    pygame.draw.ellipse(surf, (168, 178, 196), box, 2)
    pygame.draw.line(surf, (168, 178, 196),
                     (cx, r.y + int(0.352 * r.h)), (cx, r.y + int(0.396 * r.h)), 3)
    if r.w > 90:
        for x in (0.392, 0.608):     # specchietti
            pygame.draw.rect(surf, (120, 130, 150),
                             (int(r.x + x * r.w - 0.022 * r.w),
                              int(r.y + 0.396 * r.h),
                              max(2, int(0.044 * r.w)), max(2, int(0.018 * r.h))),
                             border_radius=2)


def _livrea(surf, r, colore) -> None:
    """Il colore della squadra: sul muso e sulle paratie, non sui pezzi.

    Sui componenti il colore dice come stanno messi: metterci sopra anche
    quello della scuderia vorrebbe dire non capire piu' ne' l'uno ne' l'altro.
    """
    colore = tuple(colore)
    pygame.draw.polygon(surf, colore, _pts([(0.486, 0.062), (0.514, 0.062),
                                            (0.526, 0.330), (0.474, 0.330)], r))
    pygame.draw.polygon(surf, colore, _pts([(0.490, 0.664), (0.510, 0.664),
                                            (0.510, 0.896), (0.490, 0.896)], r))
    for poly in ([(0.212, 0.900), (0.256, 0.900), (0.256, 0.996), (0.212, 0.996)],
                 [(0.788, 0.900), (0.744, 0.900), (0.744, 0.996), (0.788, 0.996)],
                 [(0.000, 0.040), (0.060, 0.040), (0.075, 0.128), (0.022, 0.128)],
                 [(1.000, 0.040), (0.940, 0.040), (0.925, 0.128), (0.978, 0.128)]):
        pygame.draw.polygon(surf, colore, _pts(poly, r))


def _diffusore(surf, r, colore) -> None:
    """L'ultimo pezzo di fondo, quello che chiude il lavoro."""
    scuro = tuple(int(c * 0.35) for c in colore)
    pygame.draw.polygon(surf, scuro, _pts([(0.250, 0.852), (0.750, 0.852),
                                           (0.768, 0.888), (0.232, 0.888)], r))
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
