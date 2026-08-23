"""La monoposto vista dall'alto, disegnata pezzo per pezzo.

Serve a guardare la macchina, non a decorare la schermata: ogni zona e' un
componente vero - ala, fondo, fiancate, sospensioni - colorata per come sta
messa rispetto al riferimento del ciclo tecnico. Un'occhiata e si vede dove la
macchina e' buona e dove no, senza leggere dieci barre.

Le proporzioni sono quelle di una monoposto moderna: 5,6 metri per 2, muso
stretto attaccato all'ala anteriore, fondo largo che lavora fino al
diffusore, fiancate che si stringono verso il retrotreno.
"""
from __future__ import annotations

import pygame

from . import theme as T

# Rapporto fra lunghezza e larghezza: 5,6 m per 2,0 m.
RATIO = 2.80

# Ordine di disegno: quello che sta sotto per primo.
ORDINE = ("floor", "front_wing", "rear_wing", "suspension", "brakes", "chassis",
          "sidepods", "cooling", "gearbox", "active_aero")


class _Map:
    """Da coordinate della macchina a pixel.

    u va da -0.5 a 0.5 sulla larghezza, v da 0 (punta del muso) a 1 (fine
    diffusore). Cosi' la geometria si scrive una volta e vale a ogni scala.
    """

    def __init__(self, rect):
        rect = pygame.Rect(rect)
        scale = min(rect.w, rect.h / RATIO)
        self.sx = scale
        self.sy = scale * RATIO
        self.cx = rect.centerx
        self.top = rect.centery - self.sy / 2

    def __call__(self, u: float, v: float) -> tuple:
        return (int(self.cx + u * self.sx), int(self.top + v * self.sy))

    def poly(self, pts) -> list:
        return [self(u, v) for u, v in pts]

    def box(self, u0: float, v0: float, u1: float, v1: float) -> pygame.Rect:
        x0, y0 = self(u0, v0)
        x1, y1 = self(u1, v1)
        return pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


# Il corpo vettura si disegna grigio, non del colore della squadra: il colore
# qui vuol dire quanto quel pezzo e' buono, e mescolare il rosso Ferrari con il
# verde "sopra il riferimento" darebbe un marrone che non dice niente. Il
# colore della squadra torna sulla livrea e sulle paratie.
CORPO = (62, 71, 88)


def _tinta(v) -> tuple:
    """Colore di una zona, da -1 (ultimi della griglia) a +1 (i migliori)."""
    if v is None:
        return CORPO
    d = max(-1.0, min(1.0, float(v)))
    if d >= 0:
        return T.mix(CORPO, T.OK, 0.22 + 0.60 * d)
    return T.mix(CORPO, T.BAD, 0.22 + 0.60 * -d)


# ------------------------------------------------------------ le zone
def _zone(m: _Map) -> dict:
    """Poligoni e rettangoli di ogni componente, in coordinate macchina."""
    z = {}

    # ala anteriore: larga quanto la macchina, quattro profili
    z["front_wing"] = [
        m.poly([(-0.492, 0.008), (0.492, 0.008), (0.492, 0.082), (-0.492, 0.082)]),
        m.poly([(-0.500, 0.000), (-0.440, 0.000), (-0.418, 0.128), (-0.478, 0.128)]),
        m.poly([(0.500, 0.000), (0.440, 0.000), (0.418, 0.128), (0.478, 0.128)]),
    ]
    # muso e cellula di sopravvivenza: sottile davanti, larga all'abitacolo
    z["chassis"] = [
        m.poly([(-0.022, 0.030), (0.022, 0.030), (0.040, 0.150), (0.058, 0.245),
                (0.082, 0.335), (0.092, 0.430), (0.086, 0.530), (-0.086, 0.530),
                (-0.092, 0.430), (-0.082, 0.335), (-0.058, 0.245), (-0.040, 0.150)]),
    ]
    # sospensioni: bracci davanti e dietro
    z["suspension"] = [
        m.poly([(-0.075, 0.175), (-0.330, 0.150), (-0.330, 0.178), (-0.070, 0.205)]),
        m.poly([(-0.082, 0.255), (-0.330, 0.235), (-0.330, 0.262), (-0.078, 0.285)]),
        m.poly([(0.075, 0.175), (0.330, 0.150), (0.330, 0.178), (0.070, 0.205)]),
        m.poly([(0.082, 0.255), (0.330, 0.235), (0.330, 0.262), (0.078, 0.285)]),
        m.poly([(-0.070, 0.735), (-0.300, 0.715), (-0.300, 0.742), (-0.066, 0.762)]),
        m.poly([(-0.066, 0.815), (-0.300, 0.800), (-0.300, 0.826), (-0.062, 0.842)]),
        m.poly([(0.070, 0.735), (0.300, 0.715), (0.300, 0.742), (0.066, 0.762)]),
        m.poly([(0.066, 0.815), (0.300, 0.800), (0.300, 0.826), (0.062, 0.842)]),
    ]
    # fiancate: pancia larga a meta' vettura che si stringe verso il retrotreno
    z["sidepods"] = [
        m.poly([(-0.088, 0.360), (-0.250, 0.372), (-0.318, 0.410), (-0.336, 0.480),
                (-0.320, 0.575), (-0.262, 0.650), (-0.170, 0.706), (-0.092, 0.730),
                (-0.070, 0.700), (-0.070, 0.395)]),
        m.poly([(0.088, 0.360), (0.250, 0.372), (0.318, 0.410), (0.336, 0.480),
                (0.320, 0.575), (0.262, 0.650), (0.170, 0.706), (0.092, 0.730),
                (0.070, 0.700), (0.070, 0.395)]),
    ]
    # raffreddamento: bocche dei radiatori e sfoghi sul cofano
    z["cooling"] = [
        m.poly([(-0.316, 0.398), (-0.140, 0.380), (-0.140, 0.412), (-0.322, 0.436)]),
        m.poly([(0.316, 0.398), (0.140, 0.380), (0.140, 0.412), (0.322, 0.436)]),
        m.poly([(-0.058, 0.548), (0.058, 0.548), (0.050, 0.640), (-0.050, 0.640)]),
    ]
    # trasmissione e cofano motore verso il retrotreno
    z["gearbox"] = [
        m.poly([(-0.046, 0.720), (0.046, 0.720), (0.034, 0.800), (0.028, 0.870),
                (-0.028, 0.870), (-0.034, 0.800)]),
    ]
    # fondo: la piattaforma che lavora sotto, con i bordi e il diffusore
    z["floor"] = [
        m.poly([(-0.120, 0.268), (-0.245, 0.286), (-0.300, 0.330), (-0.330, 0.430),
                (-0.322, 0.560), (-0.286, 0.660), (-0.250, 0.730), (-0.244, 0.812),
                (-0.268, 0.888), (0.268, 0.888), (0.244, 0.812), (0.250, 0.730),
                (0.286, 0.660), (0.322, 0.560), (0.330, 0.430), (0.300, 0.330),
                (0.245, 0.286), (0.120, 0.268)]),
    ]
    # impianto frenante: le prese sulle ruote
    z["brakes"] = [
        m.poly([(-0.318, 0.165), (-0.290, 0.165), (-0.290, 0.270), (-0.318, 0.270)]),
        m.poly([(0.318, 0.165), (0.290, 0.165), (0.290, 0.270), (0.318, 0.270)]),
        m.poly([(-0.300, 0.725), (-0.268, 0.725), (-0.268, 0.845), (-0.300, 0.845)]),
        m.poly([(0.300, 0.725), (0.268, 0.725), (0.268, 0.845), (0.300, 0.845)]),
    ]
    # ala posteriore: profilo principale, flap e paratie
    z["rear_wing"] = [
        m.poly([(-0.150, 0.876), (0.150, 0.876), (0.055, 0.918), (-0.055, 0.918)]),
        m.poly([(-0.262, 0.912), (0.262, 0.912), (0.262, 0.948), (-0.262, 0.948)]),
        m.poly([(-0.288, 0.888), (-0.244, 0.888), (-0.244, 0.996), (-0.288, 0.996)]),
        m.poly([(0.288, 0.888), (0.244, 0.888), (0.244, 0.996), (0.288, 0.996)]),
    ]
    # aero attiva: il profilo mobile dietro e i flap mobili davanti
    z["active_aero"] = [
        m.poly([(-0.244, 0.952), (0.244, 0.952), (0.244, 0.988), (-0.244, 0.988)]),
        m.poly([(-0.430, 0.014), (-0.070, 0.014), (-0.070, 0.040), (-0.430, 0.040)]),
        m.poly([(0.430, 0.014), (0.070, 0.014), (0.070, 0.040), (0.430, 0.040)]),
    ]
    return z


def _gomme(m: _Map) -> list:
    """Le quattro coperture: non sono un componente, ma senza non e' una macchina."""
    return [m.box(-0.475, 0.145, -0.320, 0.290),
            m.box(0.320, 0.145, 0.475, 0.290),
            m.box(-0.470, 0.705, -0.270, 0.865),
            m.box(0.270, 0.705, 0.470, 0.865)]


def draw_car(surf, rect, colour=(120, 140, 170), valori=None, selected=None) -> dict:
    """Disegna la monoposto e restituisce le zone cliccabili per componente.

    `valori` e' come sta messo ogni pezzo, da -1 a +1: chi lo chiama decide
    rispetto a cosa - la media della griglia, il migliore, il riferimento del
    ciclo - e qui si traduce solo in colore. `selected` e' il componente da
    mettere in evidenza.
    """
    m = _Map(rect)
    zone = _zone(m)
    base = CORPO

    # ombra sotto: segue il fondo, cosi' stacca senza sembrare una scatola
    ombra = m.poly([(-0.130, 0.276), (-0.310, 0.338), (-0.340, 0.430),
                    (-0.332, 0.560), (-0.258, 0.740), (-0.252, 0.820),
                    (-0.276, 0.900), (0.276, 0.900), (0.252, 0.820),
                    (0.258, 0.740), (0.332, 0.560), (0.340, 0.430),
                    (0.310, 0.338), (0.130, 0.276)])
    pygame.draw.polygon(surf, T.mix(T.PANEL, (0, 0, 0), 0.45), ombra)

    for rgomma in _gomme(m):
        pygame.draw.rect(surf, (26, 26, 30), rgomma, border_radius=5)
        pygame.draw.rect(surf, (52, 54, 60), rgomma, 1, border_radius=5)
        pygame.draw.line(surf, (70, 72, 80), (rgomma.centerx, rgomma.y + 4),
                         (rgomma.centerx, rgomma.bottom - 4))

    # cofano motore e airbox: non sono un componente da sviluppare, ma senza
    # di loro fra abitacolo e cambio ci sarebbe un buco
    cofano = m.poly([(-0.070, 0.470), (0.070, 0.470), (0.056, 0.640),
                     (0.046, 0.740), (-0.046, 0.740), (-0.056, 0.640)])
    pygame.draw.polygon(surf, T.mix(base, (0, 0, 0), 0.12), cofano)
    pinna = m.poly([(-0.010, 0.660), (0.010, 0.660), (0.010, 0.900), (-0.010, 0.900)])
    pygame.draw.polygon(surf, T.mix(base, T.WHITE, 0.10), pinna)

    aree = {}
    for key in ORDINE:
        polys = zone.get(key)
        if not polys:
            continue
        col = _tinta((valori or {}).get(key))
        if selected and key != selected:
            col = T.mix(col, T.PANEL, 0.45)
        xs, ys = [], []
        for poly in polys:
            pygame.draw.polygon(surf, col, poly)
            pygame.draw.polygon(surf, T.mix(col, T.WHITE, 0.18), poly, 1)
            xs += [p[0] for p in poly]
            ys += [p[1] for p in poly]
        aree[key] = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        if selected == key:
            for poly in polys:
                pygame.draw.polygon(surf, T.GOLD, poly, 2)

    # abitacolo e halo: non si sviluppano, ma senza non si capisce cos'e'
    hx, hy = m(0.0, 0.432)
    rr = max(3, int(0.062 * m.sx))
    pygame.draw.ellipse(surf, (12, 16, 24), (hx - rr, hy - int(rr * 1.5), rr * 2, int(rr * 3.0)))
    pygame.draw.ellipse(surf, (168, 178, 196), (hx - rr, hy - int(rr * 1.5), rr * 2,
                                                int(rr * 3.0)), 2)
    pygame.draw.line(surf, (168, 178, 196), m(0.0, 0.352), m(0.0, 0.396), 3)
    # specchietti
    for u in (-0.108, 0.108):
        pygame.draw.rect(surf, T.mix(base, T.WHITE, 0.30),
                         m.box(u - 0.022, 0.396, u + 0.022, 0.414), border_radius=2)

    # livrea: il colore della squadra resta qui, dove non falsa la lettura
    liv = tuple(colour)
    pygame.draw.polygon(surf, liv, m.poly([(-0.014, 0.062), (0.014, 0.062),
                                           (0.026, 0.330), (-0.026, 0.330)]))
    pygame.draw.polygon(surf, liv, m.poly([(-0.010, 0.664), (0.010, 0.664),
                                           (0.010, 0.896), (-0.010, 0.896)]))
    for poly in (m.poly([(-0.288, 0.900), (-0.244, 0.900), (-0.244, 0.996), (-0.288, 0.996)]),
                 m.poly([(0.288, 0.900), (0.244, 0.900), (0.244, 0.996), (0.288, 0.996)]),
                 m.poly([(-0.500, 0.040), (-0.440, 0.040), (-0.425, 0.128), (-0.478, 0.128)]),
                 m.poly([(0.500, 0.040), (0.440, 0.040), (0.425, 0.128), (0.478, 0.128)])):
        pygame.draw.polygon(surf, liv, poly)

    # diffusore: l'ultimo pezzo di fondo, quello che chiude il lavoro
    pygame.draw.polygon(surf, T.mix(base, (0, 0, 0), 0.45),
                        m.poly([(-0.250, 0.852), (0.250, 0.852),
                                (0.268, 0.888), (-0.268, 0.888)]))
    for u in (-0.170, -0.085, 0.085, 0.170):
        pygame.draw.line(surf, T.mix(base, (0, 0, 0), 0.65),
                         m(u, 0.856), m(u, 0.886))

    # dettagli che si vedono solo se la macchina e' disegnata grande
    if m.sx > 150:
        for v in (0.024, 0.042, 0.060):
            pygame.draw.line(surf, T.mix(base, (0, 0, 0), 0.35),
                             m(-0.470, v), m(0.470, v))
        for u in (-0.316, 0.316):
            pygame.draw.line(surf, T.mix(base, (0, 0, 0), 0.30),
                             m(u, 0.470), m(u * 0.86, 0.700), 2)
    return aree
