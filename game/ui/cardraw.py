"""La monoposto vista dall'alto, disegnata a poligoni.

Serve a rendere toccabile quello che finora era una lista: si guarda la
macchina, si clicca il pezzo e si vede com'e' messo. Le forme sono
approssimate ma riconoscibili - muso, ali, pance, fondo, cambio - e ognuna sa
a quale componente corrisponde.

Le coordinate sono normalizzate 0..1 sul rettangolo che si passa: la stessa
macchina sta bene in un pannello grande o piccolo senza toccare i numeri.
"""
from __future__ import annotations

import pygame

from . import theme as T

# Ogni componente e' un poligono in coordinate 0..1, con x da sinistra a destra
# e y dal muso alla coda. Sono scritti a mano per somigliare a una monoposto
# moderna: muso stretto, pance rastremate, fondo che le tiene insieme.
SHAPES = {
    "floor": [(0.27, 0.27), (0.73, 0.27), (0.78, 0.45), (0.78, 0.79),
              (0.65, 0.855), (0.35, 0.855), (0.22, 0.79), (0.22, 0.45)],
    "front_wing": [(0.08, 0.030), (0.92, 0.030), (0.92, 0.105), (0.56, 0.105),
                   (0.53, 0.135), (0.47, 0.135), (0.44, 0.105), (0.08, 0.105)],
    "chassis": [(0.470, 0.105), (0.530, 0.105), (0.575, 0.32), (0.575, 0.58),
                (0.425, 0.58), (0.425, 0.32)],
    "suspension": [(0.215, 0.190), (0.44, 0.245), (0.44, 0.285), (0.215, 0.240)],
    "brakes": [(0.245, 0.155), (0.300, 0.155), (0.300, 0.265), (0.245, 0.265)],
    "sidepods": [(0.290, 0.330), (0.420, 0.330), (0.430, 0.600), (0.300, 0.620)],
    "cooling": [(0.460, 0.320), (0.540, 0.320), (0.555, 0.620), (0.445, 0.620)],
    "gearbox": [(0.460, 0.620), (0.540, 0.620), (0.530, 0.800), (0.470, 0.800)],
    "active_aero": [(0.360, 0.830), (0.640, 0.830), (0.640, 0.872), (0.360, 0.872)],
    "rear_wing": [(0.240, 0.885), (0.760, 0.885), (0.760, 0.955), (0.240, 0.955)],
}

# Alcuni pezzi stanno su tutti e due i lati: si disegnano specchiati.
MIRRORED = ("sidepods", "suspension", "brakes")

# Le ruote non sono un componente ma senza non si capisce cos'e'.
WHEELS = [(0.120, 0.135, 0.105, 0.155), (0.775, 0.135, 0.105, 0.155),
          (0.110, 0.645, 0.115, 0.180), (0.775, 0.645, 0.115, 0.180)]


def _pts(poly, rect, mirror=False):
    out = []
    for x, y in poly:
        xx = (1.0 - x) if mirror else x
        out.append((rect.x + xx * rect.w, rect.y + y * rect.h))
    return out


def polygons(part: str, rect) -> list:
    """I poligoni di quel componente sul rettangolo dato (uno o due)."""
    base = SHAPES.get(part)
    if not base:
        return []
    fuori = [_pts(base, rect)]
    if part in MIRRORED:
        fuori.append(_pts(base, rect, mirror=True))
    return fuori


# In che ordine si cerca chi e' stato cliccato: prima i pezzi piccoli che
# stanno sopra, per ultimi telaio e fondo che fanno da base a tutto.
HIT_ORDER = ("brakes", "suspension", "sidepods", "cooling", "gearbox",
             "active_aero", "rear_wing", "front_wing", "chassis", "floor")


def hit(rect, pos) -> str | None:
    """Quale componente sta sotto quel punto. Il fondo e' l'ultimo a rispondere."""
    ordine = [k for k in HIT_ORDER if k in SHAPES]
    for part in ordine:
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


def draw(surf, rect, colours: dict, selected: str = "", badges: dict = None) -> None:
    """Disegna la monoposto colorando ogni componente come si e' chiesto.

    `colours` da' il colore di riempimento per componente, `badges` un pallino
    d'accento su quelli che hanno qualcosa da dire - un pezzo nuovo montato,
    uno che sta per cedere.
    """
    rect = pygame.Rect(rect)
    badges = badges or {}
    # il fondo sta sotto tutto: si disegna per primo e scurito, altrimenti
    # copre la macchina invece di farle da base
    fondo = colours.get("floor", T.PANEL_3)
    scuro = tuple(int(c * 0.42) for c in fondo)
    for poly in polygons("floor", rect):
        pygame.draw.polygon(surf, scuro, poly)
        bordo = T.WHITE if selected == "floor" else (30, 36, 48)
        pygame.draw.polygon(surf, bordo, poly, 3 if selected == "floor" else 2)
    for part in [k for k in SHAPES if k != "floor"]:
        col = colours.get(part, T.PANEL_3)
        for poly in polygons(part, rect):
            pygame.draw.polygon(surf, col, poly)
            bordo = T.WHITE if part == selected else (18, 22, 30)
            pygame.draw.polygon(surf, bordo, poly, 3 if part == selected else 1)
        segno = badges.get(part)
        if segno:
            poly = polygons(part, rect)[0]
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            pygame.draw.circle(surf, segno, (int(cx), int(cy)), 5)
            pygame.draw.circle(surf, (10, 14, 20), (int(cx), int(cy)), 5, 1)


def wheels(surf, rect) -> None:
    """Le gomme, disegnate per ultime: non sono un componente ma senza non si
    capisce che quello e' una monoposto."""
    rect = pygame.Rect(rect)
    for wx, wy, ww, wh in WHEELS:
        r = pygame.Rect(rect.x + wx * rect.w, rect.y + wy * rect.h,
                        ww * rect.w, wh * rect.h)
        raggio = max(2, int(r.w * 0.30))
        pygame.draw.rect(surf, (22, 24, 29), r, border_radius=raggio)
        pygame.draw.rect(surf, (52, 56, 64), r, 1, border_radius=raggio)


def floor_badge(surf, rect, colour) -> None:
    """Il pallino del fondo, che si disegna dopo tutto il resto per vedersi."""
    poly = polygons("floor", pygame.Rect(rect))[0]
    cx = sum(p[0] for p in poly) / len(poly)
    cy = max(p[1] for p in poly) - 14
    pygame.draw.circle(surf, colour, (int(cx), int(cy)), 5)
    pygame.draw.circle(surf, (10, 14, 20), (int(cx), int(cy)), 5, 1)


def label_pos(part: str, rect) -> tuple:
    """Il centro del componente, per attaccarci una scritta."""
    poly = polygons(part, pygame.Rect(rect))
    if not poly:
        return (rect.centerx, rect.centery)
    p = poly[0]
    return (int(sum(q[0] for q in p) / len(p)), int(sum(q[1] for q in p) / len(p)))
