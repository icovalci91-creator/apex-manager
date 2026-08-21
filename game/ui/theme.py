"""Palette, font e helper di disegno."""
from __future__ import annotations

import pygame

BG        = (10, 13, 20)
PANEL     = (19, 25, 35)
PANEL_2   = (26, 34, 48)
PANEL_3   = (34, 44, 61)
LINE      = (44, 56, 76)
TEXT      = (231, 238, 248)
DIM       = (137, 151, 172)
DIM_2     = (95, 107, 126)
ACCENT    = (0, 200, 255)
OK        = (53, 196, 106)
WARN      = (245, 166, 35)
BAD       = (229, 72, 77)
GOLD      = (226, 183, 78)
WHITE     = (255, 255, 255)

_FONTS: dict = {}
_FAMILIES = "Segoe UI,Inter,DejaVu Sans,Arial"
_MONO = "Consolas,DejaVu Sans Mono,Courier New"


def font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    key = (size, bold, mono)
    if key not in _FONTS:
        fam = _MONO if mono else _FAMILIES
        _FONTS[key] = pygame.font.SysFont(fam, size, bold=bold)
    return _FONTS[key]


def text(surf, s: str, pos, size: int = 16, colour=TEXT, bold: bool = False,
         mono: bool = False, align: str = "left", maxw: int | None = None):
    f = font(size, bold, mono)
    if maxw:
        s = ellipsize(s, f, maxw)
    img = f.render(str(s), True, colour)
    r = img.get_rect()
    if align == "left":
        r.topleft = pos
    elif align == "center":
        r.midtop = pos
    else:
        r.topright = pos
    surf.blit(img, r)
    return r


def ellipsize(s: str, f: pygame.font.Font, maxw: int) -> str:
    if f.size(s)[0] <= maxw:
        return s
    while s and f.size(s + "...")[0] > maxw:
        s = s[:-1]
    return s + "..."


def panel(surf, rect, colour=PANEL, radius: int = 10, border=None, width: int = 1):
    pygame.draw.rect(surf, colour, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width, border_radius=radius)


def bar(surf, rect, value: float, maxv: float = 100.0, colour=ACCENT, bg=PANEL_3, radius: int = 4):
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    frac = max(0.0, min(1.0, value / maxv if maxv else 0.0))
    if frac > 0:
        r = pygame.Rect(rect[0], rect[1], max(2, int(rect[2] * frac)), rect[3])
        pygame.draw.rect(surf, colour, r, border_radius=radius)


def stat_colour(v: float, lo: float = 55.0, hi: float = 90.0):
    if v >= hi:
        return OK
    if v >= (lo + hi) / 2:
        return (150, 200, 90)
    if v >= lo:
        return WARN
    return BAD


def hex_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def fmt_time(t: float) -> str:
    if t is None or t >= 999 or t <= 0:
        return "--:--.---"
    m, s = divmod(t, 60)
    if m >= 60:
        h, m = divmod(int(m), 60)
        return f"{h}:{int(m):02d}:{s:06.3f}"
    return f"{int(m)}:{s:06.3f}"


def fmt_gap(g: float) -> str:
    if g is None:
        return "--"
    if g >= 60:
        m, s = divmod(g, 60)
        return f"+{int(m)}:{s:06.3f}"
    return f"+{g:.3f}"


def fmt_money(m: float) -> str:
    if abs(m) >= 1000:
        return f"{m/1000:.2f} Mld$"
    return f"{m:.2f} M$"
