"""Disegno del tracciato 2D.

Un circuito visto dall'alto non e' un filo grigio su fondo nero: e' un nastro
d'asfalto appoggiato su qualcosa. Attorno c'e' la via di fuga, dove chi sbaglia
finisce; ai bordi delle curve ci sono i cordoli; dentro c'e' il prato, e lungo
il rettilineo del traguardo corrono le caselle della griglia e la corsia dei
box con i suoi garage. Sono le cose che si vedono in una ripresa dall'elicottero
e che dicono a colpo d'occhio dove si sta guardando.

Tutto quello che non si muove - e' quasi tutto - si disegna una volta su una
superficie e poi si incolla: sopra ci vanno solo le vetture.
"""
from __future__ import annotations

import math
import pygame

from . import theme as T

# I colori del contorno. Restano scuri e poco contrastati di proposito: la
# mappa serve a seguire venti pallini colorati, e un prato acceso se li
# mangerebbe.
PRATO = (24, 38, 30)
PRATO_INT = (21, 33, 27)
FUGA = (58, 55, 52)
BORDO = (30, 46, 34)
ASFALTO = (52, 63, 82)
CORDOLO_A = (176, 62, 62)
CORDOLO_B = (222, 222, 226)
BOX_ASFALTO = (36, 43, 57)
BOX_MURO = (116, 130, 154)
BOX_GARAGE = (58, 68, 88)
GRIGLIA = (150, 163, 184)

# Sotto questo raggio - in frazioni del lato del disegno - un pezzo di pista e'
# una curva, e una curva ha i cordoli.
K_CURVA = 26.0
CORDOLO_PASSO = 7          # ogni quanti punti si alterna il colore
CASELLE_GRIGLIA = 10       # quante caselle si disegnano prima del traguardo


def fit_points(track, rect, pad: int = 26) -> list:
    inner = pygame.Rect(rect).inflate(-pad * 2, -pad * 2)
    side = min(inner.w, inner.h)
    ox = inner.centerx - side // 2
    oy = inner.centery - side // 2
    return [(ox + px * side, oy + py * side) for px, py in track.points]


def fit_pit(track, rect, pad: int = 26) -> list:
    """La corsia dei box, nella stessa inquadratura del tracciato."""
    box = getattr(track, "pit_points", None)
    if not box:
        return []
    inner = pygame.Rect(rect).inflate(-pad * 2, -pad * 2)
    side = min(inner.w, inner.h)
    ox = inner.centerx - side // 2
    oy = inner.centery - side // 2
    return [(ox + px * side, oy + py * side) for px, py in box]


def _normali(pts: list) -> list:
    """La perpendicolare a destra della direzione di marcia, punto per punto."""
    n = len(pts)
    fuori = []
    for i in range(n):
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        d = math.hypot(tx, ty) or 1.0
        fuori.append((ty / d, -tx / d))
    return fuori


def _curve(pts: list, soglia: float) -> list:
    """Dove il nastro gira davvero, e da che parte: serve ai cordoli."""
    n = len(pts)
    fuori = []
    for i in range(n):
        a, b, c = pts[(i - 2) % n], pts[i], pts[(i + 2) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        d = (math.hypot(*v1) * math.hypot(*v2)) or 1.0
        fuori.append(cross / d)
    # una media mobile corta toglie il tremolio del rilievo
    liscio = [sum(fuori[(i + k) % n] for k in (-2, -1, 0, 1, 2)) / 5.0 for i in range(n)]
    return [x if abs(x) > soglia else 0.0 for x in liscio]


# Il nastro d'asfalto e' fatto di centinaia di punti e non cambia mai: si
# disegna una volta su una superficie e poi si incolla. Sopra ci vanno solo le
# vetture, che invece si muovono.
_ASPHALT: dict = {}


def _fascia(img, pts, colore, largo: int) -> None:
    """Una fascia larga attorno al nastro, con gli angoli tondi.

    Le linee spesse di pygame hanno le giunzioni squadrate, e su una curva
    stretta si vedono gli scalini: si ripassa con un cerchio ogni pochi punti e
    il bordo torna liscio, come una via di fuga vera.
    """
    pygame.draw.lines(img, colore, True, pts, largo)
    r = max(1, largo // 2)
    passo = max(1, len(pts) // 260)
    for i in range(0, len(pts), passo):
        pygame.draw.circle(img, colore, (int(pts[i][0]), int(pts[i][1])), r)


def _cordoli(img, pts, curve, width: int) -> None:
    """I cordoli, solo dove si gira, dalla parte interna della curva."""
    n = len(pts)
    normali = _normali(pts)
    off = width / 2.0 + 2.0
    lungo = max(2, CORDOLO_PASSO)
    i = 0
    acceso = 0
    while i < n:
        if not curve[i]:
            i += 1
            acceso = 0
            continue
        verso = -1.0 if curve[i] > 0 else 1.0      # l'interno della curva
        j = min(i + lungo, n)
        seg = []
        for k in range(i, j + 1):
            q = k % n
            nx, ny = normali[q]
            seg.append((pts[q][0] + nx * off * verso, pts[q][1] + ny * off * verso))
        if len(seg) >= 2:
            pygame.draw.lines(img, CORDOLO_A if acceso % 2 else CORDOLO_B,
                              False, seg, 3)
        acceso += 1
        i = j


def _griglia(img, pts, width: int) -> None:
    """Le caselle della griglia, in fila prima della linea del traguardo."""
    n = len(pts)
    normali = _normali(pts)
    off = width / 2.0 - 1.0
    for k in range(1, CASELLE_GRIGLIA + 1):
        i = (-k * 3) % n
        nx, ny = normali[i]
        lato = 1.0 if k % 2 else -1.0
        x, y = pts[i][0] + nx * off * lato * 0.55, pts[i][1] + ny * off * lato * 0.55
        pygame.draw.line(img, GRIGLIA, (x - nx * 3, y - ny * 3),
                         (x + nx * 3, y + ny * 3), 2)


def _box(img, pit, pista, width: int) -> None:
    """La corsia dei box: i garage, l'asfalto, il muretto.

    Da che parte sta la pista non lo si deduce dalla direzione di marcia - con
    il disegno ribaltato ci si sbaglia - lo si guarda: per ogni punto della
    corsia si cerca il punto di pista piu' vicino, e quella e' la parte del
    muretto. Dall'altra ci vanno i garage, che e' l'unico posto dove possono
    stare.
    """
    if len(pit) < 6 or len(pista) < 8:
        return
    largo = max(5, int(width * 0.70))
    verso = []
    passo_p = max(1, len(pista) // 400)
    for x, y in pit:
        px, py = min(((p[0], p[1]) for p in pista[::passo_p]),
                     key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
        dx, dy = px - x, py - y
        d = math.hypot(dx, dy) or 1.0
        verso.append((dx / d, dy / d))

    def sposta(k, quanto):
        return (pit[k][0] + verso[k][0] * quanto, pit[k][1] + verso[k][1] * quanto)

    # la palazzina dei box, dietro la corsia: un rettangolo lungo, non una
    # linea spessa - le linee spesse di pygame fanno gli scalini in curva
    dentro = [sposta(k, -largo * 0.55) for k in range(3, len(pit) - 3)]
    fuori = [sposta(k, -largo * 1.55) for k in range(3, len(pit) - 3)]
    if len(dentro) >= 2:
        pygame.draw.polygon(img, BOX_GARAGE, dentro + fuori[::-1])
    # fra la pista e la corsia c'e' erba: senza, le due strisce d'asfalto si
    # attaccano e non si capisce piu' dove finisce una e comincia l'altra
    pygame.draw.lines(img, BORDO, False, pit, largo + 6)
    pygame.draw.lines(img, BOX_ASFALTO, False, pit, largo)
    # e le porte dei garage, una ogni dodici metri buoni
    quanti = max(8, min(24, len(pit) - 8))
    salto = max(1, (len(pit) - 8) // quanti)
    for k in range(4, len(pit) - 4, salto):
        pygame.draw.line(img, BOX_ASFALTO, sposta(k, -largo * 0.60),
                         sposta(k, -largo * 1.50), 1)
    # e il muretto verso la pista, con l'apertura per l'ingresso e l'uscita
    muro = [sposta(k, largo * 0.60) for k in range(6, len(pit) - 6)]
    if len(muro) >= 2:
        pygame.draw.lines(img, BOX_MURO, False, muro, 2)


def draw_track(surf, track, rect, width: int = 12, colour=ASFALTO,
               kerb: bool = True, start_line: bool = True, pts=None):
    rect = pygame.Rect(rect)
    key = (track.id, rect.w, rect.h, width, tuple(colour), kerb, start_line)
    img = _ASPHALT.get(key)
    if img is None:
        img = pygame.Surface(rect.size, pygame.SRCALPHA)
        base = pygame.Rect(0, 0, rect.w, rect.h)
        local = fit_points(track, base)
        pit = fit_pit(track, base)
        if len(local) >= 3:
            lato = min(base.w, base.h)
            # il prato dentro l'anello, che e' quello che si vede in mezzo
            pygame.draw.polygon(img, PRATO_INT, local)
            # e attorno al nastro: prima l'erba, poi la via di fuga, poi il
            # bordo, poi l'asfalto. Sono quattro passate una dentro l'altra
            _fascia(img, local, PRATO, width + 30)
            _fascia(img, local, FUGA, width + 16)
            _fascia(img, local, BORDO, width + 6)
            _fascia(img, local, colour, width)
            if kerb and width >= 8:
                _cordoli(img, local, _curve(local, K_CURVA / lato), width)
            if pit and width >= 8:
                _box(img, pit, local, width)
            if start_line:
                if width >= 8:
                    _griglia(img, local, width)
                a, b = local[0], local[3 % len(local)]
                ang = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
                dx, dy = math.cos(ang) * (width / 2 + 2), math.sin(ang) * (width / 2 + 2)
                pygame.draw.line(img, T.WHITE, (a[0] - dx, a[1] - dy),
                                 (a[0] + dx, a[1] + dy), 3)
        _ASPHALT[key] = img
    surf.blit(img, rect.topleft)
    return pts or fit_points(track, rect)


def car_pos(pts, frac: float, offset: float = 0.0):
    """Posizione lungo il tracciato con uno scostamento laterale in pixel."""
    n = len(pts)
    f = frac % 1.0
    i = int(f * n) % n
    j = (i + 1) % n
    t = f * n - int(f * n)
    x = pts[i][0] + (pts[j][0] - pts[i][0]) * t
    y = pts[i][1] + (pts[j][1] - pts[i][1]) * t
    if offset:
        dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        d = math.hypot(dx, dy) or 1.0
        x += -dy / d * offset
        y += dx / d * offset
    return x, y


_MINIMAPS: dict = {}


def draw_minimap(surf, track, rect, colour=(60, 72, 94), width: int = 4):
    """La miniatura: qui il contorno non ci sta, serve solo la forma."""
    rect = pygame.Rect(rect)
    key = (track.id, rect.w, rect.h, tuple(colour), width)
    img = _MINIMAPS.get(key)
    if img is None:
        img = pygame.Surface(rect.size, pygame.SRCALPHA)
        local = fit_points(track, pygame.Rect(0, 0, rect.w, rect.h), pad=10)
        if len(local) >= 3:
            pygame.draw.lines(img, colour, True, local, width)
        _MINIMAPS[key] = img
    surf.blit(img, rect.topleft)
