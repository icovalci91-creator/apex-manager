"""Le bandiere, disegnate invece che caricate.

Nei dati un paese e' una sigla di due lettere, e a schermo si vedeva la sigla:
"AU", "CN", "MC". Funziona, ma una griglia di ventiquattro gare e una lista di
piloti sono esattamente i posti in cui una bandiera si riconosce prima di
leggerla - ed e' l'unica cosa colorata che manca a schermate fatte tutte di
grigio e ciano.

Non ci sono file di immagini: le bandiere si disegnano. Non e' una scorciatoia,
e' la scelta giusta per un gioco che deve girare anche nel browser - venticinque
PNG in piu' sono venticinque richieste in piu' allo scaricamento, e a otto pixel
di altezza un PNG non si vede meglio di due rettangoli. Le forme che servono
sono poche e si ripetono: bande verticali, bande orizzontali, un disco in
mezzo, una croce, un cantone in alto a sinistra. Con quelle cinque si copre
quasi tutto il calendario; le tre che non ci stanno - il Regno Unito, gli Stati
Uniti, il Brasile - hanno il loro disegno.

Di un paese che non e' in tabella si continua a scrivere la sigla, che e' quello
che si faceva prima: meglio due lettere giuste che una bandiera sbagliata.
"""
from __future__ import annotations

import pygame

# I colori sono quelli ufficiali, arrotondati: a dodici pixel di larghezza la
# differenza fra il rosso Pantone 032 e il rosso di fianco non la vede nessuno,
# ma il verde dell'Italia e quello del Messico si' - sono due bandiere diverse.
BIANCO = (255, 255, 255)
NERO = (17, 17, 17)

# "v" bande verticali, "o" bande orizzontali, poi i colori da sinistra o
# dall'alto. "disco" e' un fondo con un cerchio in mezzo, "croce" una croce
# scandinava, "cantone" un fondo con un riquadro in alto a sinistra.
BANDIERE = {
    "AE": ("ae",),
    "AR": ("o", (108, 172, 228), BIANCO, (108, 172, 228)),
    "AT": ("o", (237, 41, 57), BIANCO, (237, 41, 57)),
    "AU": ("cantone", (1, 33, 105), (0, 0, 0)),
    "AZ": ("o", (0, 155, 187), (237, 41, 57), (60, 158, 74)),
    "BE": ("v", NERO, (253, 218, 36), (239, 51, 64)),
    "BH": ("v", BIANCO, (218, 41, 28)),
    "BR": ("br",),
    "CA": ("v", (255, 0, 0), BIANCO, (255, 0, 0)),
    "CH": ("croce", (218, 37, 29), BIANCO),
    "CN": ("cn",),
    "CO": ("o", (252, 209, 22), (0, 51, 145), (206, 17, 38)),
    "DE": ("o", NERO, (221, 0, 0), (255, 206, 0)),
    "DK": ("croce", (198, 12, 48), BIANCO),
    "EE": ("o", (0, 114, 206), NERO, BIANCO),
    "IE": ("v", (22, 155, 98), BIANCO, (255, 136, 62)),
    "IN": ("o", (255, 103, 31), BIANCO, (19, 136, 8)),
    "NO": ("croce2", (186, 12, 47), BIANCO, (0, 32, 91)),
    "PL": ("o", BIANCO, (220, 20, 60)),
    "RU": ("o", BIANCO, (0, 57, 166), (213, 43, 30)),
    "SE": ("croce", (0, 106, 167), (254, 204, 0)),
    "ES": ("o", (198, 11, 30), (255, 196, 0), (198, 11, 30)),
    "EU": ("eu",),
    "FI": ("croce", BIANCO, (0, 47, 108)),
    "FR": ("v", (0, 35, 149), BIANCO, (237, 41, 57)),
    "GB": ("gb",),
    "HU": ("o", (206, 41, 57), BIANCO, (71, 112, 80)),
    "IT": ("v", (0, 140, 69), BIANCO, (205, 33, 42)),
    "JP": ("disco", BIANCO, (188, 0, 45)),
    "MC": ("o", (206, 17, 38), BIANCO),
    "MX": ("v", (0, 104, 71), BIANCO, (206, 17, 38)),
    "MY": ("cantone", (0, 0, 102), (204, 0, 0)),
    "NL": ("o", (174, 28, 40), BIANCO, (33, 70, 139)),
    "NZ": ("cantone", (0, 36, 125), (0, 0, 0)),
    "PT": ("v", (0, 102, 71), (255, 0, 0), (255, 0, 0)),
    "QA": ("v", BIANCO, (138, 21, 56)),
    "SA": ("sa",),
    "SG": ("o", (237, 41, 57), BIANCO),
    "TH": ("o", (165, 25, 49), BIANCO, (45, 42, 74)),
    "TR": ("disco", (227, 10, 23), BIANCO),
    "US": ("us",),
    "ZA": ("o", (0, 122, 77), BIANCO, (0, 35, 149)),
}

_CACHE: dict = {}


def _bande(img, w: int, h: int, colori: tuple, verticali: bool) -> None:
    n = len(colori)
    for i, c in enumerate(colori):
        if verticali:
            a, b = round(i * w / n), round((i + 1) * w / n)
            pygame.draw.rect(img, c, (a, 0, b - a, h))
        else:
            a, b = round(i * h / n), round((i + 1) * h / n)
            pygame.draw.rect(img, c, (0, a, w, b - a))


def _disegna(codice: str, w: int, h: int) -> pygame.Surface | None:
    spec = BANDIERE.get(codice)
    if not spec:
        return None
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    tipo, colori = spec[0], spec[1:]
    if tipo == "v":
        _bande(img, w, h, colori, True)
    elif tipo == "o":
        _bande(img, w, h, colori, False)
    elif tipo == "disco":
        img.fill(colori[0])
        pygame.draw.circle(img, colori[1], (w // 2, h // 2), max(2, int(h * 0.32)))
    elif tipo == "croce":
        # la croce scandinava non sta in mezzo: sta spostata verso l'asta
        img.fill(colori[0])
        sp = max(2, int(h * 0.22))
        pygame.draw.rect(img, colori[1], (0, (h - sp) // 2, w, sp))
        pygame.draw.rect(img, colori[1], (int(w * 0.34), 0, sp, h))
    elif tipo == "croce2":
        # la croce dentro la croce: e' quella di Norvegia e Islanda, e senza la
        # seconda passata sarebbero uguali a quella danese
        img.fill(colori[0])
        sp = max(3, int(h * 0.30))
        pygame.draw.rect(img, colori[1], (0, (h - sp) // 2, w, sp))
        pygame.draw.rect(img, colori[1], (int(w * 0.34), 0, sp, h))
        sp2 = max(1, sp - 3)
        pygame.draw.rect(img, colori[2], (0, (h - sp2) // 2, w, sp2))
        pygame.draw.rect(img, colori[2],
                         (int(w * 0.34) + (sp - sp2) // 2, 0, sp2, h))
    elif tipo == "cantone":
        img.fill(colori[0])
        pygame.draw.rect(img, colori[1] if colori[1] != (0, 0, 0) else (0, 36, 125),
                         (0, 0, w // 2, h // 2))
        _union_jack(img, w // 2, h // 2)
    elif tipo == "gb":
        _union_jack(img, w, h)
    elif tipo == "us":
        for i in range(7):
            pygame.draw.rect(img, (178, 34, 52) if i % 2 == 0 else BIANCO,
                             (0, round(i * h / 7), w, round(h / 7) + 1))
        pygame.draw.rect(img, (60, 59, 110), (0, 0, int(w * 0.42), int(h * 0.54)))
    elif tipo == "br":
        img.fill((0, 151, 57))
        pygame.draw.polygon(img, (254, 221, 0), [(w // 2, 2), (w - 3, h // 2),
                                                 (w // 2, h - 2), (3, h // 2)])
        pygame.draw.circle(img, (0, 39, 118), (w // 2, h // 2), max(2, int(h * 0.20)))
    elif tipo == "cn":
        img.fill((238, 28, 37))
        pygame.draw.circle(img, (255, 222, 0), (int(w * 0.22), int(h * 0.32)),
                           max(2, int(h * 0.16)))
    elif tipo == "sa":
        img.fill((0, 106, 78))
        pygame.draw.rect(img, BIANCO, (int(w * 0.18), int(h * 0.42), int(w * 0.6), 2))
    elif tipo == "ae":
        _bande(img, w, h, ((0, 115, 47), BIANCO, NERO), False)
        pygame.draw.rect(img, (255, 0, 0), (0, 0, max(3, int(w * 0.26)), h))
    elif tipo == "eu":
        img.fill((0, 51, 153))
        pygame.draw.circle(img, (255, 204, 0), (w // 2, h // 2), max(2, int(h * 0.22)), 2)
    else:
        return None
    pygame.draw.rect(img, (0, 0, 0, 90), (0, 0, w, h), 1)
    return img


def _union_jack(img, w: int, h: int) -> None:
    """L'Union Jack, per quel che ne sta in dodici pixel: le croci, non le
    diagonali sottili - a questa misura si impastano e basta."""
    pygame.draw.rect(img, (1, 33, 105), (0, 0, w, h))
    pygame.draw.line(img, BIANCO, (0, 0), (w, h), 3)
    pygame.draw.line(img, BIANCO, (w, 0), (0, h), 3)
    sp = max(2, int(h * 0.26))
    pygame.draw.rect(img, BIANCO, (0, (h - sp) // 2 - 1, w, sp + 2))
    pygame.draw.rect(img, BIANCO, ((w - sp) // 2 - 1, 0, sp + 2, h))
    pygame.draw.rect(img, (200, 16, 46), (0, (h - sp) // 2 + 1, w, sp - 2))
    pygame.draw.rect(img, (200, 16, 46), ((w - sp) // 2 + 1, 0, sp - 2, h))


def bandiera(codice: str, h: int = 11):
    """La bandiera di quel paese, alta tanto. None se non la sappiamo fare."""
    codice = (codice or "").strip().upper()
    if codice not in BANDIERE:
        return None
    w = int(round(h * 1.5))
    chiave = (codice, w, h)
    img = _CACHE.get(chiave)
    if img is None:
        img = _disegna(codice, w, h)
        _CACHE[chiave] = img
    return img


def disegna(surf, codice: str, pos, h: int = 11) -> int:
    """La disegna e dice quanto e' larga. Zero se quel paese non ce l'abbiamo."""
    img = bandiera(codice, h)
    if img is None:
        return 0
    surf.blit(img, pos)
    return img.get_width()
