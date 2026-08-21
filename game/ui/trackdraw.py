"""Disegno del tracciato 2D."""
from __future__ import annotations

import math
import pygame

from . import theme as T


def fit_points(track, rect, pad: int = 26) -> list:
    inner = pygame.Rect(rect).inflate(-pad * 2, -pad * 2)
    side = min(inner.w, inner.h)
    ox = inner.centerx - side // 2
    oy = inner.centery - side // 2
    return [(ox + px * side, oy + py * side) for px, py in track.points]


def draw_track(surf, track, rect, width: int = 12, colour=(52, 63, 82),
               kerb: bool = True, start_line: bool = True, pts=None):
    pts = pts or fit_points(track, rect)
    if len(pts) < 3:
        return pts
    pygame.draw.lines(surf, (16, 20, 28), True, pts, width + 8)
    if kerb:
        pygame.draw.lines(surf, (78, 92, 118), True, pts, width + 3)
    pygame.draw.lines(surf, colour, True, pts, width)
    if start_line:
        a, b = pts[0], pts[3 % len(pts)]
        ang = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
        dx, dy = math.cos(ang) * (width / 2 + 2), math.sin(ang) * (width / 2 + 2)
        pygame.draw.line(surf, T.WHITE, (a[0] - dx, a[1] - dy), (a[0] + dx, a[1] + dy), 3)
    return pts


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


def draw_minimap(surf, track, rect, colour=(60, 72, 94), width: int = 4):
    pts = fit_points(track, rect, pad=10)
    if len(pts) >= 3:
        pygame.draw.lines(surf, colour, True, pts, width)
    return pts
