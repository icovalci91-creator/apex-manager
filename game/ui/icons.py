"""Le icone della barra di navigazione, disegnate invece che caricate.

Stessa scelta delle bandiere in `bandiere.py`: niente file da scaricare, e
niente che si sfoca quando lo schermo cambia misura, perche' non e' una
bitmap - e' una manciata di `pygame.draw` che si ridisegnano alla misura del
rettangolo che gli si da'. Diciotto voci di menu erano diciotto righe di
testo tutte uguali: un occhio che scorre la barra in fretta le riconosceva
solo leggendole una per una. Una sagoma per ognuna si riconosce prima di
leggerla, come una bandiera.

Ogni funzione disegna dentro al rettangolo che le si passa, con un margine
implicito: le coordinate sono frazioni di quel rettangolo, non pixel fissi,
cosi' la stessa icona serve alla barra laterale piccola e a una versione
piu' grande senza bisogno di un secondo disegno.
"""
from __future__ import annotations

import pygame


def _pt(r: pygame.Rect, x: float, y: float) -> tuple:
    """Un punto dentro al rettangolo, da coordinate 0..1."""
    return (r.x + r.w * x, r.y + r.h * y)


def _linee(surf, r, colore, largh, *serie) -> None:
    """Piu' spezzate, una per tupla di coordinate 0..1."""
    for punti in serie:
        pygame.draw.lines(surf, colore, False, [_pt(r, x, y) for x, y in punti], largh)


def _home(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.10, 0.55), (0.5, 0.12), (0.90, 0.55)])
    _linee(surf, r, c, w, [(0.22, 0.42), (0.22, 0.90), (0.78, 0.90), (0.78, 0.42)])
    _linee(surf, r, c, w, [(0.40, 0.90), (0.40, 0.64), (0.60, 0.64), (0.60, 0.90)])


def _car(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.06, 0.62), (0.18, 0.32), (0.38, 0.24), (0.62, 0.24),
                           (0.80, 0.32), (0.94, 0.62)])
    _linee(surf, r, c, w, [(0.06, 0.62), (0.94, 0.62), (0.94, 0.74), (0.06, 0.74), (0.06, 0.62)])
    for x in (0.26, 0.74):
        pygame.draw.circle(surf, c, _pt(r, x, 0.80), r.w * 0.09, max(1, w - 1))


def _spark(surf, r, c, w) -> None:
    pts = [(0.5, 0.05), (0.60, 0.40), (0.95, 0.5), (0.60, 0.60),
           (0.5, 0.95), (0.40, 0.60), (0.05, 0.5), (0.40, 0.40)]
    pygame.draw.polygon(surf, c, [_pt(r, x, y) for x, y in pts], w)


def _bolt(surf, r, c, w) -> None:
    pts = [(0.58, 0.05), (0.20, 0.55), (0.46, 0.55), (0.40, 0.95),
           (0.82, 0.42), (0.54, 0.42)]
    pygame.draw.polygon(surf, c, [_pt(r, x, y) for x, y in pts], w)


def _gear(surf, r, c, w) -> None:
    cx, cy = _pt(r, 0.5, 0.5)
    corpo = r.w * 0.30
    import math
    denti = 6
    for i in range(denti):
        a = i * (2 * math.pi / denti)
        x1, y1 = cx + corpo * 1.5 * math.cos(a), cy + corpo * 1.5 * math.sin(a)
        x2, y2 = cx + corpo * 0.9 * math.cos(a), cy + corpo * 0.9 * math.sin(a)
        pygame.draw.line(surf, c, (x2, y2), (x1, y1), w + 1)
    pygame.draw.circle(surf, c, (cx, cy), corpo, w)
    pygame.draw.circle(surf, c, (cx, cy), corpo * 0.32, 0)


def _stopwatch(surf, r, c, w) -> None:
    cx, cy = _pt(r, 0.5, 0.56)
    rad = r.w * 0.36
    pygame.draw.circle(surf, c, (cx, cy), rad, w)
    _linee(surf, r, c, w, [(0.40, 0.06), (0.60, 0.06)])
    _linee(surf, r, c, w, [(0.5, 0.10), (0.5, 0.20)])
    pygame.draw.line(surf, c, (cx, cy), (cx, cy - rad * 0.6), w)


def _helmet(surf, r, c, w) -> None:
    cx, cy = _pt(r, 0.5, 0.5)
    rad = r.w * 0.42
    pygame.draw.arc(surf, c, (cx - rad, cy - rad, rad * 2, rad * 2), 3.4, 6.3, w)
    _linee(surf, r, c, w, [(0.10, 0.52), (0.10, 0.66), (0.90, 0.66), (0.90, 0.52)])
    _linee(surf, r, c, w, [(0.18, 0.44), (0.82, 0.44)])


def _cap(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.08, 0.42), (0.5, 0.18), (0.92, 0.42), (0.5, 0.66), (0.08, 0.42)])
    _linee(surf, r, c, w, [(0.30, 0.52), (0.30, 0.74), (0.5, 0.86), (0.70, 0.74), (0.70, 0.52)])
    _linee(surf, r, c, w, [(0.86, 0.42), (0.86, 0.68)])


def _bolt_circle(surf, r, c, w) -> None:
    cx, cy = _pt(r, 0.5, 0.5)
    pygame.draw.circle(surf, c, (cx, cy), r.w * 0.42, w)
    pts = [(0.58, 0.28), (0.40, 0.52), (0.53, 0.52), (0.44, 0.76),
           (0.68, 0.46), (0.54, 0.46)]
    pygame.draw.polygon(surf, c, [_pt(r, x, y) for x, y in pts], 0)


def _flag_check(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.20, 0.05), (0.20, 0.95)])
    quad = r.w * 0.14
    x0, y0 = _pt(r, 0.20, 0.10)
    for row in range(3):
        for col in range(3):
            if (row + col) % 2 == 0:
                pygame.draw.rect(surf, c, (x0 + col * quad, y0 + row * quad, quad, quad))


def _people(surf, r, c, w) -> None:
    pygame.draw.circle(surf, c, _pt(r, 0.33, 0.32), r.w * 0.16, w)
    _linee(surf, r, c, w, [(0.06, 0.90), (0.10, 0.66), (0.33, 0.56), (0.56, 0.66), (0.60, 0.90)])
    pygame.draw.circle(surf, c, _pt(r, 0.70, 0.38), r.w * 0.13, w)
    _linee(surf, r, c, w, [(0.55, 0.90), (0.58, 0.70), (0.70, 0.62), (0.85, 0.68), (0.94, 0.90)])


def _org(surf, r, c, w) -> None:
    for x in (0.10, 0.66):
        pygame.draw.rect(surf, c, (*_pt(r, x, 0.62), r.w * 0.24, r.h * 0.24), w)
    pygame.draw.rect(surf, c, (*_pt(r, 0.38, 0.10), r.w * 0.24, r.h * 0.24), w)
    _linee(surf, r, c, w, [(0.5, 0.34), (0.5, 0.50), (0.22, 0.50), (0.22, 0.62)])
    _linee(surf, r, c, w, [(0.5, 0.50), (0.78, 0.50), (0.78, 0.62)])


def _coin(surf, r, c, w) -> None:
    pygame.draw.circle(surf, c, _pt(r, 0.42, 0.42), r.w * 0.30, w)
    pygame.draw.circle(surf, c, _pt(r, 0.60, 0.62), r.w * 0.30, w)


def _building(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.14, 0.94), (0.14, 0.10), (0.66, 0.10), (0.66, 0.94)])
    _linee(surf, r, c, w, [(0.66, 0.36), (0.90, 0.30), (0.90, 0.94)])
    for x, y in ((0.26, 0.24), (0.44, 0.24), (0.26, 0.46), (0.44, 0.46), (0.26, 0.68), (0.44, 0.68)):
        pygame.draw.rect(surf, c, (*_pt(r, x, y), r.w * 0.10, r.h * 0.10), max(1, w - 1))


def _book(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.5, 0.14), (0.5, 0.88)])
    _linee(surf, r, c, w, [(0.5, 0.20), (0.12, 0.14), (0.10, 0.80), (0.5, 0.88)])
    _linee(surf, r, c, w, [(0.5, 0.20), (0.88, 0.14), (0.90, 0.80), (0.5, 0.88)])


def _trophy(surf, r, c, w) -> None:
    _linee(surf, r, c, w, [(0.22, 0.14), (0.78, 0.14), (0.72, 0.48), (0.5, 0.58), (0.28, 0.48), (0.22, 0.14)])
    _linee(surf, r, c, w, [(0.22, 0.20), (0.08, 0.22), (0.10, 0.40), (0.28, 0.44)])
    _linee(surf, r, c, w, [(0.78, 0.20), (0.92, 0.22), (0.90, 0.40), (0.72, 0.44)])
    _linee(surf, r, c, w, [(0.5, 0.58), (0.5, 0.76)])
    _linee(surf, r, c, w, [(0.32, 0.90), (0.68, 0.90)])
    _linee(surf, r, c, w, [(0.5, 0.76), (0.32, 0.90)])
    _linee(surf, r, c, w, [(0.5, 0.76), (0.68, 0.90)])


def _calendar(surf, r, c, w) -> None:
    pygame.draw.rect(surf, c, (*_pt(r, 0.10, 0.20), r.w * 0.80, r.h * 0.72), w, border_radius=2)
    _linee(surf, r, c, w, [(0.10, 0.38), (0.90, 0.38)])
    _linee(surf, r, c, w, [(0.30, 0.10), (0.30, 0.28)])
    _linee(surf, r, c, w, [(0.70, 0.10), (0.70, 0.28)])
    for x, y in ((0.26, 0.54), (0.48, 0.54), (0.70, 0.54), (0.26, 0.72), (0.48, 0.72)):
        pygame.draw.circle(surf, c, _pt(r, x, y), max(1.4, r.w * 0.045), 0)


def _clock(surf, r, c, w) -> None:
    cx, cy = _pt(r, 0.5, 0.5)
    rad = r.w * 0.42
    pygame.draw.circle(surf, c, (cx, cy), rad, w)
    pygame.draw.line(surf, c, (cx, cy), (cx, cy - rad * 0.62), w)
    pygame.draw.line(surf, c, (cx, cy), (cx + rad * 0.46, cy + rad * 0.20), w)


_ICONE = {
    "hq": _home, "car": _car, "dev": _spark, "powerunit": _bolt,
    "engineers": _gear, "testing": _stopwatch, "drivers": _helmet,
    "academy": _cap, "formulae": _bolt_circle, "wec": _flag_check,
    "staff": _people, "workforce": _org, "finance": _coin,
    "facilities": _building, "rules": _book, "standings": _trophy,
    "calendar": _calendar, "history": _clock,
}


def draw(surf, nome: str, rect, colore, largh: int = 2) -> None:
    """Disegna l'icona `nome` dentro `rect`. Se non c'e', non disegna niente:
    meglio un vuoto che un errore in mezzo alla barra di navigazione."""
    fn = _ICONE.get(nome)
    if fn is not None:
        fn(surf, pygame.Rect(rect), colore, largh)
