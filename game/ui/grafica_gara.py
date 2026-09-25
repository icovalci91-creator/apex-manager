"""La grafica di gara, come in televisione: il tabellone, la riga della
cronaca, e i pezzi con cui si fanno i pannelli delle nostre macchine.

La usano il weekend di Formula 1 e l'E-Prix: la stessa torre stretta a sinistra
sopra la mappa, con la testata e una riga per macchina; la cronaca in una
riga sola che entra da sinistra; i pannelli col blocco inclinato della
posizione, le barre a tacche, le pastiglie colorate.
"""
from __future__ import annotations

import math

import pygame

from . import fx
from . import theme as T

VIOLA = (183, 96, 255)
ROSSO_TV = (225, 6, 0)
GRIGIO = (150, 160, 178)


def cognome(nome: str) -> str:
    """Il cognome in maiuscolo, con il Jr. attaccato se c'e'."""
    parti = nome.split()
    if len(parti) >= 3 and parti[-1].lower().rstrip(".") in ("jr", "sr", "ii", "iii"):
        return f"{parti[-2]} {parti[-1]}".upper()
    return (parti[-1] if parti else nome).upper()


def distacco(metri: float, giro_m: float, passo: float) -> str:
    """"+1.4", oppure "+1 GIRO" quando e' un giro o piu'."""
    giri = int(metri // giro_m)
    if giri >= 1:
        return f"+{giri} GIRO" if giri == 1 else f"+{giri} GIRI"
    return f"+{metri / max(1.0, passo):.1f}"


# ------------------------------------------------------------- il tabellone
def torre(surf, tower, testa: tuple, modo: str, righe: list) -> tuple:
    """Il tabellone: testata (etichetta, numero, dopo il numero), il modo
    in un riquadro cliccabile, e le righe. Ogni riga e' un dict con code,
    colour, mio, fuori, tag, viola, valore (testo, colore) e icona - ("gomma",
    colore, lettera) o ("batteria", quota, colore). Restituisce (riquadro del
    modo, y della prima riga, altezza di una riga)."""
    testa_h = 46
    n = max(1, len(righe))
    rh = max(13.0, min(24.0, (tower.h - testa_h - 6) / n))
    alta = int(testa_h + 4 + rh * n)
    velo = pygame.Surface((tower.w, alta), pygame.SRCALPHA)
    pygame.draw.rect(velo, (10, 11, 16, 228), velo.get_rect(), border_radius=8)
    surf.blit(velo, tower.topleft)
    pygame.draw.rect(surf, ROSSO_TV, (tower.x, tower.y, tower.w, 4),
                     border_top_left_radius=8, border_top_right_radius=8)
    etichetta, grande, dopo = testa
    T.text(surf, etichetta, (tower.x + 14, tower.y + 12), 11, (160, 168, 182), bold=True)
    x = tower.x + 18 + T.width(etichetta, 11, bold=True)
    T.text(surf, grande, (x, tower.y + 7), 22, T.WHITE, bold=True)
    T.text(surf, dopo, (x + 2 + T.width(grande, 22, bold=True), tower.y + 15), 13,
           (160, 168, 182), bold=True)
    riquadro = pygame.Rect(tower.right - 116, tower.y + 8, 108, 26)
    T.panel(surf, riquadro, (34, 36, 46), radius=5, rilievo=False)
    T.text(surf, modo, (riquadro.centerx, riquadro.y + 7), 11, T.WHITE, bold=True,
           align="center")
    y0 = tower.y + testa_h
    dim = 15 if rh >= 21 else (13 if rh >= 17 else 11)
    for i, r in enumerate(righe, 1):
        y = int(y0 + (i - 1) * rh)
        fuori = r["fuori"]
        if r["mio"]:
            acceso = pygame.Surface((tower.w - 8, int(rh) - 1), pygame.SRCALPHA)
            larga = acceso.get_width()
            for k in range(0, larga, 2):
                a = int(150 * (1.0 - k / larga) + 40)
                pygame.draw.rect(acceso, (*r["colour"][:3], a), (k, 0, 2, acceso.get_height()))
            surf.blit(acceso, (tower.x + 4, y))
        elif i % 2 == 0:
            striscia = pygame.Surface((tower.w - 8, int(rh) - 1), pygame.SRCALPHA)
            striscia.fill((255, 255, 255, 10))
            surf.blit(striscia, (tower.x + 4, y))
        ty = y + (rh - dim) / 2 - 1
        chiaro = (110, 116, 128) if fuori else T.WHITE
        if i <= 3 and not fuori:
            pygame.draw.rect(surf, (240, 242, 246), (tower.x + 8, y + 2, 26, int(rh) - 4),
                             border_radius=3)
            T.text(surf, str(i), (tower.x + 21, ty), dim, (12, 14, 20), bold=True,
                   align="center")
        else:
            T.text(surf, str(i), (tower.x + 21, ty), dim, chiaro, bold=True, align="center")
        pygame.draw.rect(surf, r["colour"], (tower.x + 40, y + 3, 4, max(6, int(rh) - 6)),
                         border_radius=2)
        T.text(surf, r["code"], (tower.x + 52, ty), dim, chiaro, bold=True)
        x_info = tower.x + 52 + T.width("WWW", dim, bold=True) + 8
        if r.get("viola"):
            pygame.draw.rect(surf, VIOLA, (x_info, y + 4, 10, int(rh) - 8), border_radius=2)
            x_info += 16
        tag = r.get("tag")
        if tag and rh >= 16:
            lw = T.width(tag[0], 10, bold=True) + 8
            pygame.draw.rect(surf, tag[1], (x_info, y + 4, lw, int(rh) - 8), border_radius=3)
            T.text(surf, tag[0], (x_info + lw // 2, y + (rh - 10) / 2 - 1), 10, (10, 12, 18),
                   bold=True, align="center")
        gx = tower.right - 16
        icona = r.get("icona")
        cy = int(y + rh / 2)
        if icona and icona[0] == "gomma":
            rg = max(5, min(8, int(rh / 2) - 3))
            pygame.draw.circle(surf, (20, 22, 28), (gx, cy), rg + 1)
            pygame.draw.circle(surf, icona[1], (gx, cy), rg, 2)
            if rg >= 7:
                T.text(surf, icona[2], (gx, y + rh / 2 - 6), 10, T.WHITE, bold=True,
                       align="center")
            xv = gx - rg - 10
        elif icona and icona[0] == "batteria":
            hb = max(8, int(rh) - 8)
            pygame.draw.rect(surf, (60, 64, 78), (gx - 5, cy - hb // 2, 10, hb), 1,
                             border_radius=2)
            pieno = int((hb - 4) * max(0.0, min(1.0, icona[1])))
            pygame.draw.rect(surf, icona[2], (gx - 3, cy + hb // 2 - 2 - pieno, 6, pieno))
            xv = gx - 14
        else:
            xv = gx
        testo, col = r["valore"]
        T.text(surf, testo, (xv, ty + 1), max(11, dim - 2), col, bold=True, mono=True,
               align="right")
    return riquadro, y0, rh


# -------------------------------------------------------- la riga di cronaca
TIPI = {"pass": ("SORPASSO", (53, 196, 106)), "team": ("SQUADRA", (0, 200, 255)),
        "dnf": ("RITIRO", (229, 72, 77)), "pit": ("BOX", (0, 200, 255)),
        "sc": ("SAFETY CAR", (245, 196, 80)), "warn": ("ATTENZIONE", (255, 150, 60)),
        "flag": ("BANDIERA", (240, 244, 250)), "pen": ("PENALITA'", (255, 120, 90)),
        "attack": ("ATTACK MODE", VIOLA)}


def riga_cronaca(surf, riga, eventi, stato) -> None:
    """L'ultimo fatto della gara in una riga, che entra da sinistra quando
    arriva, con l'etichetta del suo colore. `stato` tiene a mente quale era
    l'ultimo, per l'animazione."""
    if not eventi:
        return
    ev = eventi[0]
    chiave = (ev.get("t"), ev.get("text"))
    if chiave != getattr(stato, "_ultimo_fatto", None):
        stato._ultimo_fatto = chiave
        stato._fatto_da = fx.ora()
    entra = fx.esce(min(1.0, (fx.ora() - getattr(stato, "_fatto_da", 0.0)) / 0.35))
    tipo, col = TIPI.get(ev["kind"], ("CRONACA", (170, 180, 196)))
    larga_tipo = T.width(tipo, 12, bold=True) + 26
    r = pygame.Rect(riga.x - int((1.0 - entra) * 40), riga.y, riga.w, riga.h)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (8, 10, 16, int(225 * entra)), s.get_rect(), border_radius=6)
    pygame.draw.rect(s, (*col, int(255 * entra)), (0, 0, larga_tipo, r.h),
                     border_top_left_radius=6, border_bottom_left_radius=6)
    surf.blit(s, r.topleft)
    T.text(surf, tipo, (r.x + larga_tipo // 2, r.y + 8), 12, (10, 12, 18), bold=True,
           align="center")
    giro = f"GIRO {ev['lap']}"
    T.text(surf, ev["text"], (r.x + larga_tipo + 12, r.y + 7), 14, T.WHITE,
           maxw=r.w - larga_tipo - 30 - T.width(giro, 11, bold=True))
    T.text(surf, giro, (r.right - 12, r.y + 9), 11, (150, 160, 178), bold=True, align="right")


# --------------------------------------------------------- i pannelli
def fondo_pannello(surf, r, colore) -> None:
    """Il fondo del pannello: vetro scuro, il colore della squadra che sfuma
    da sinistra, e il filo acceso in alto."""
    T.panel(surf, r, (12, 14, 20), radius=10, border=(40, 46, 60))
    alone = pygame.Surface((int(r.w * 0.55), r.h - 4), pygame.SRCALPHA)
    larga = alone.get_width()
    for x in range(0, larga, 2):
        a = int(70 * (1.0 - x / larga) ** 1.6)
        pygame.draw.line(alone, (*colore, a), (x, 0), (x, alone.get_height()))
        pygame.draw.line(alone, (*colore, a), (x + 1, 0), (x + 1, alone.get_height()))
    surf.blit(alone, (r.x + 2, r.y + 2))
    pygame.draw.rect(surf, colore, (r.x + 10, r.y, r.w - 20, 3), border_radius=2)


def parallelogramma(surf, rect, colore) -> None:
    """Il blocco inclinato della posizione, come nelle grafiche televisive."""
    r = pygame.Rect(rect)
    k = r.h // 3
    punti = [(r.x + k, r.y), (r.right, r.y), (r.right - k, r.bottom), (r.x, r.bottom)]
    pygame.draw.polygon(surf, T.mix(colore, (0, 0, 0), 0.35), [(x + 2, y + 2) for x, y in punti])
    pygame.draw.polygon(surf, colore, punti)
    pygame.draw.line(surf, T.mix(colore, (255, 255, 255), 0.45), punti[0], punti[1], 2)


def segmenti(surf, rect, quota: float, colore, n: int) -> None:
    """Una barra a tacche: le piene accese, con il riflesso in alto."""
    r = pygame.Rect(rect)
    gap = 2
    w = (r.w - gap * (n - 1)) / n
    piene = quota * n
    for k in range(n):
        x = int(r.x + k * (w + gap))
        cella = pygame.Rect(x, r.y, max(2, int(w)), r.h)
        if k + 1 <= piene:
            c = colore
        elif k < piene:
            c = T.mix((44, 48, 60), colore, piene - k)
        else:
            c = (44, 48, 60)
        pygame.draw.rect(surf, c, cella, border_radius=2)
        if c is colore:
            pygame.draw.line(surf, T.mix(colore, (255, 255, 255), 0.45),
                             (cella.x + 1, cella.y), (cella.right - 2, cella.y))


def pastiglia(surf, x: int, y: int, testo: str, colore) -> None:
    larga = T.width(testo, 10, bold=True) + 12
    pygame.draw.rect(surf, colore, (x, y, larga, 16), border_radius=4)
    T.text(surf, testo, (x + larga // 2, y + 2), 10, (10, 12, 18), bold=True, align="center")


def gomma(surf, centro, raggio: int, colore, lettera: str) -> None:
    x, y = centro
    pygame.draw.circle(surf, (16, 18, 24), (x, y), raggio + 2)
    pygame.draw.circle(surf, colore, (x, y), raggio + 1, 3)
    T.text(surf, lettera, (x, y - 7), 11, T.WHITE, bold=True, align="center")


def arco(surf, centro, raggio: int, quota: float, colore) -> None:
    """Il tachimetro: un arco di tre quarti che si riempie."""
    x, y = centro
    inizio, giro = math.radians(225), math.radians(270)
    for k in range(28):
        a = inizio - giro * k / 27
        acceso = k / 27 <= quota
        c = colore if acceso else (44, 48, 60)
        px, py = x + math.cos(a) * raggio, y - math.sin(a) * raggio
        pygame.draw.circle(surf, c, (int(px), int(py)), 2)
