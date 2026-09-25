"""Le livree delle monoposto: i colori della squadra e le scritte degli sponsor.

Ogni squadra ha il suo schema - dove va il colore di fondo, dove le fasce,
dove il nero del fondo - ripreso da com'e' la sua macchina nel 2026. Sopra ci
vanno le scritte degli sponsor che ha sotto contratto *adesso*, nei posti dove
stanno sulle macchine vere: il title sponsor sul cofano, sull'ala posteriore
e sulle paratie, i partner principali sulle pance e sul muso, i secondari
sull'ala anteriore e sui fianchi dell'abitacolo. Se in partita si firma con
un marchio nuovo, alla gara dopo la macchina lo porta.

La livrea e' un'immagine sola per squadra, dipinta qui con pygame e divisa in
tre parti che lo shader di `vista3d` proietta sulla macchina:

  * i due fianchi (quello destro e quello sinistro, che si legge al contrario)
  * la vista da sopra: muso, cofano, pance
  * le due ali, viste da sopra: la posteriore e l'anteriore

Le misure sono quelle della macchina di `monoposto`, in metri.
"""
from __future__ import annotations

import pygame

from . import theme as T

# la tela: larga come due fianchi, alta come le tre parti
LARGA, ALTA = 2048, 1024
FIANCO_H = 384          # righe dei fianchi
SOPRA_H = 384           # righe della vista da sopra
ALI_H = 256             # righe delle ali
X0, X1 = -2.9, 3.0      # la macchina in lunghezza
Y1 = 1.1                # e in altezza

# Gli schemi. `fondo` e' il colore di tutto, `accento` e `terzo` le altre
# due tinte; `zone` dice dove vanno, con dei nomi che valgono per tutti:
#   basso      la parte bassa dei fianchi, scura come il fondo vettura
#   spina      la fascia sul dorso, dal muso al cofano
#   pance      le pance, dall'imbocco in giu'
#   cofano     il cofano dietro alla presa d'aria
#   muso       la punta del muso
#   ali        i piani delle ali
#   fascia     una lama obliqua lungo il fianco
#   meta       la meta' posteriore della macchina
SCHEMI = {
    "ferrari": dict(fondo="#D40000", accento="#FFFFFF", terzo="#111111",
                    zone={"basso": "terzo", "spina": "accento", "ali": "fondo", "muso": "fondo"}),
    "mclaren": dict(fondo="#FF8000", accento="#1E1E1E", terzo="#47C7FC",
                    zone={"pance": "accento", "cofano": "accento", "basso": "accento",
                          "ali": "fondo", "muso": "fondo"}),
    "mercedes": dict(fondo="#101010", accento="#C8CCCE", terzo="#00A19C",
                     zone={"cofano": "accento", "spina": "terzo", "fascia": "terzo",
                           "ali": "fondo", "muso": "accento"}),
    "redbull": dict(fondo="#1B2A5B", accento="#D81E3A", terzo="#FFC906",
                    zone={"fascia": "accento", "muso": "terzo", "basso": "fondo",
                          "ali": "fondo"}),
    "astonmartin": dict(fondo="#00594F", accento="#CEDC00", terzo="#0B2A26",
                        zone={"fascia": "accento", "basso": "terzo", "ali": "fondo",
                              "muso": "fondo"}),
    "alpine": dict(fondo="#0A64B4", accento="#EC008C", terzo="#0A0F23",
                   zone={"meta": "accento", "basso": "terzo", "ali": "accento"}),
    "williams": dict(fondo="#041E42", accento="#00A0DE", terzo="#FFFFFF",
                     zone={"fascia": "accento", "cofano": "accento", "ali": "fondo"}),
    "racingbulls": dict(fondo="#F2F2F4", accento="#1634CC", terzo="#E4002B",
                        zone={"pance": "accento", "cofano": "accento", "fascia": "terzo",
                              "ali": "accento"}),
    "haas": dict(fondo="#F4F4F4", accento="#151515", terzo="#E6002B",
                 zone={"basso": "accento", "fascia": "terzo", "muso": "terzo",
                       "ali": "accento"}),
    "audi": dict(fondo="#9EA3A6", accento="#141414", terzo="#F50537",
                 zone={"meta": "accento", "fascia": "terzo", "ali": "accento"}),
    "cadillac": dict(fondo="#F2F2F2", accento="#0E0E0E", terzo="#B8B8B8",
                     zone={"meta": "accento", "basso": "accento", "ali": "accento"}),
}


# ------------------------------------------------------------ la Formula E
# Le undici squadre del mondiale elettrico, con i loro colori e i marchi che
# portano: il title, i partner, e il costruttore del motore dove non e' gia'
# nel nome. Non hanno un mercato degli sponsor nel gioco: la livrea e' questa.
def _m(scritta, *colori):
    return {"name": scritta, "scritta": scritta, "colori": list(colori)}


SCHEMI_FE = {
    "Porsche": dict(fondo="#F2F2F2", accento="#101010", terzo="#D5001C",
                    zone={"meta": "accento", "fascia": "terzo", "ali": "accento"},
                    sponsor={"title": [_m("TAG HEUER", "#101010", "#FFFFFF")],
                             "primary": [_m("PORSCHE", "#D5001C", "#FFFFFF"),
                                         _m("MOBIL 1", "#E4002B", "#FFFFFF")],
                             "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Jaguar": dict(fondo="#0B0B0B", accento="#FFFFFF", terzo="#1F6FEB",
                   zone={"basso": "accento", "fascia": "terzo", "ali": "fondo"},
                   sponsor={"title": [_m("TCS", "#FFFFFF", "#0B0B0B")],
                            "primary": [_m("JAGUAR", "#FFFFFF", "#0B0B0B"),
                                        _m("CASTROL", "#009343", "#FFFFFF")],
                            "secondary": [_m("DOW", "#E80033", "#FFFFFF"),
                                          _m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Nissan": dict(fondo="#F4F4F4", accento="#C3002F", terzo="#141414",
                   zone={"meta": "terzo", "fascia": "accento", "muso": "accento",
                         "ali": "terzo"},
                   sponsor={"title": [_m("NISSAN", "#C3002F", "#FFFFFF")],
                            "primary": [_m("NISMO", "#141414", "#FFFFFF"),
                                        _m("SHISEIDO", "#C3002F", "#FFFFFF")],
                            "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Stellantis": dict(fondo="#0C1B3A", accento="#FFFFFF", terzo="#6CA8E0",
                       zone={"fascia": "accento", "basso": "terzo", "ali": "fondo"},
                       sponsor={"title": [_m("MASERATI", "#FFFFFF", "#0C1B3A")],
                                "primary": [_m("MSG", "#6CA8E0", "#0C1B3A"),
                                            _m("STELLANTIS", "#FFFFFF", "#0C1B3A")],
                                "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Lola": dict(fondo="#101010", accento="#E10600", terzo="#FFFFFF",
                 zone={"pance": "accento", "cofano": "accento", "muso": "terzo",
                       "ali": "accento"},
                 sponsor={"title": [_m("LOLA", "#FFFFFF", "#101010")],
                          "primary": [_m("YAMAHA", "#FFFFFF", "#4B1E78"),
                                      _m("ABT", "#FFFFFF", "#101010")],
                          "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Citroen": dict(fondo="#F5F5F5", accento="#DA291C", terzo="#1A1A1A",
                    zone={"meta": "accento", "basso": "terzo", "ali": "accento"},
                    sponsor={"title": [_m("CITROEN", "#DA291C", "#FFFFFF")],
                             "primary": [_m("STELLANTIS", "#1A1A1A", "#FFFFFF"),
                                         _m("TOTALENERGIES", "#ED0000", "#FFFFFF")],
                             "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Mahindra": dict(fondo="#141414", accento="#B87333", terzo="#E31837",
                     zone={"fascia": "accento", "cofano": "accento", "ali": "fondo"},
                     sponsor={"title": [_m("MAHINDRA", "#FFFFFF", "#141414")],
                              "primary": [_m("TECH MAHINDRA", "#E31837", "#FFFFFF"),
                                          _m("CLUB MAHINDRA", "#B87333", "#141414")],
                              "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Opel": dict(fondo="#F7D117", accento="#111111", terzo="#FFFFFF",
                 zone={"basso": "accento", "fascia": "accento", "ali": "accento"},
                 sponsor={"title": [_m("OPEL", "#111111", "#F7D117")],
                          "primary": [_m("GSE", "#111111", "#FFFFFF"),
                                      _m("STELLANTIS", "#111111", "#FFFFFF")],
                          "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Envision": dict(fondo="#0A2240", accento="#7AC143", terzo="#00A9E0",
                     zone={"pance": "accento", "fascia": "terzo", "ali": "fondo"},
                     sponsor={"title": [_m("ENVISION", "#7AC143", "#0A2240")],
                              "primary": [_m("AESC", "#FFFFFF", "#0A2240"),
                                          _m("JAGUAR POWERED", "#FFFFFF", "#0A2240")],
                              "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "Andretti": dict(fondo="#FFFFFF", accento="#002D72", terzo="#D22630",
                     zone={"basso": "accento", "fascia": "terzo", "muso": "accento",
                           "ali": "accento"},
                     sponsor={"title": [_m("ANDRETTI", "#002D72", "#FFFFFF")],
                              "primary": [_m("PORSCHE POWERED", "#D22630", "#FFFFFF"),
                                          _m("MAPEI", "#004B93", "#FFFFFF")],
                              "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
    "ERT": dict(fondo="#111111", accento="#00C2C7", terzo="#FF3E8A",
                zone={"meta": "accento", "fascia": "terzo", "ali": "fondo"},
                sponsor={"title": [_m("ERT", "#00C2C7", "#111111")],
                         "primary": [_m("NIO 333", "#FFFFFF", "#111111"),
                                     _m("BIOLIFE", "#FF3E8A", "#FFFFFF")],
                         "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]}),
}


def _tinte(s: dict) -> dict:
    return {"fondo": T.hex_rgb(s["fondo"]), "accento": T.hex_rgb(s["accento"]),
            "terzo": T.hex_rgb(s["terzo"]), "zone": s["zone"]}


def schema_fe(squadra: str, colore=None) -> dict | None:
    """Lo schema di una squadra di Formula E; una sconosciuta prende il suo colore."""
    s = SCHEMI_FE.get(squadra)
    if s is None:
        if colore is None:
            return None
        s = dict(fondo="#%02x%02x%02x" % tuple(colore[:3]), accento="#141414",
                 terzo="#FFFFFF", zone={"fascia": "accento", "basso": "accento",
                                        "ali": "accento"},
                 sponsor={"title": [_m(squadra.upper(), "#FFFFFF", "#141414")],
                          "secondary": [_m("HANKOOK", "#F47B20", "#FFFFFF")]})
    return s


def colore_fe(squadra: str):
    """Il colore della squadra sul tabellone e sulla mappa: quello della
    livrea, ma che si veda sul fondo scuro (non il bianco, non il nero)."""
    s = SCHEMI_FE.get(squadra)
    if s is None:
        return None
    for k in ("fondo", "accento", "terzo"):
        c = T.hex_rgb(s[k])
        luce = (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0
        if 0.12 <= luce <= 0.80:
            return c
    return T.hex_rgb(s["fondo"])


def livrea_fe(squadra: str, colore) -> tuple:
    """(seconda tinta, schema) di una macchina di Formula E."""
    s = schema_fe(squadra, colore)
    return (_tinte(s)["accento"], 2)


def disegna_fe(squadra: str, colore=None) -> pygame.Surface:
    """La livrea di una squadra di Formula E, con i suoi marchi."""
    s = schema_fe(squadra, colore or (120, 120, 130))
    sp = {"title": [], "primary": [], "secondary": [], "technical": []}
    sp.update({k: list(v) for k, v in s.get("sponsor", {}).items()})
    return _dipingi(_tinte(s), sp)


def _schema(team) -> dict:
    s = SCHEMI.get(team.id)
    if s is None:
        # una squadra nuova: i suoi due colori, e il nero dove va il nero
        s = dict(fondo=team.colour, accento=getattr(team, "accent", "") or "#202020",
                 terzo="#111111", zone={"fascia": "accento", "basso": "terzo", "ali": "fondo"})
    return _tinte(s)


def livrea_di(team) -> tuple:
    """(seconda tinta, schema) per la livrea semplice, quella senza immagine."""
    s = _schema(team)
    return (s["accento"], 2)


# ------------------------------------------------------------------ geometria
def _fianco(x: float, y: float, sinistro: bool) -> tuple:
    """Il punto (x, y) del fianco, in pixel della tela."""
    u = (x - X0) / (X1 - X0)
    if sinistro:
        u = 1.0 - u
    px = (LARGA // 2) * (1 if sinistro else 0) + u * (LARGA // 2)
    py = (1.0 - y / Y1) * FIANCO_H
    return (px, py)


def _sopra(x: float, z: float) -> tuple:
    u = (x - X0) / (X1 - X0)
    return (u * LARGA, FIANCO_H + (z + 1.0) / 2.0 * SOPRA_H)


def _poligono_fianco(tela, punti, colore) -> None:
    for sinistro in (False, True):
        pygame.draw.polygon(tela, colore, [_fianco(x, y, sinistro) for x, y in punti])


def _poligono_sopra(tela, punti, colore) -> None:
    pygame.draw.polygon(tela, colore, [_sopra(x, z) for x, z in punti])


# ------------------------------------------------------------------ le scritte
def _contrasto(fondo) -> tuple:
    return (15, 15, 18) if T._luminanza(fondo) > 0.35 else (245, 245, 245)


def _scritta(tela, testo: str, box: pygame.Rect, colore, fondo=None, badge=None) -> None:
    """Una scritta che sta dentro al riquadro, il piu' grande possibile."""
    if not testo:
        return
    alta = max(8, int(box.h * 0.82))
    img = T.render(testo, alta, colore, bold=True)
    if img.get_width() > box.w * 0.94:
        k = box.w * 0.94 / img.get_width()
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)),
                                                 max(1, int(img.get_height() * k))))
    r = img.get_rect(center=box.center)
    if badge is not None:
        pygame.draw.rect(tela, badge, r.inflate(int(r.h * 0.5), int(r.h * 0.25)),
                         border_radius=max(2, r.h // 5))
    tela.blit(img, r)


def _marchio(gs, deal) -> dict | None:
    for s in getattr(gs, "sponsor_pool", []) or []:
        if s["id"] == deal.sponsor:
            return s
    return None


def _sponsor_ordinati(gs, team) -> dict:
    """Gli sponsor della squadra per fascia, dal piu' ricco."""
    out = {"title": [], "primary": [], "secondary": [], "technical": []}
    for d in sorted(getattr(team, "deals", []) or [], key=lambda d: -d.value):
        s = _marchio(gs, d)
        if s is not None:
            out.setdefault(d.tier, []).append(s)
    return out


def _metti(tela, s, box: pygame.Rect, fondo, grande: bool = False) -> None:
    """Il marchio nel riquadro: il title direttamente sulla vernice, gli altri
    nel loro rettangolo con i loro colori, come un adesivo."""
    colori = [T.hex_rgb(c) for c in (s.get("colori") or ["#FFFFFF", "#000000"])]
    testo = s.get("scritta") or s["name"]
    if grande:
        # sulla vernice: il colore del marchio se si legge, se no bianco o nero
        c = colori[0] if T.contrasto(colori[0], fondo) >= 2.6 else _contrasto(fondo)
        _scritta(tela, testo, box, c)
    else:
        _scritta(tela, testo, box.inflate(-box.w // 8, -box.h // 4), colori[1], badge=colori[0])


# ------------------------------------------------------------------ la tela
def disegna(gs, team) -> pygame.Surface:
    """La livrea intera della squadra, con gli sponsor di adesso."""
    return _dipingi(_schema(team), _sponsor_ordinati(gs, team))


def _dipingi(sch: dict, sp: dict) -> pygame.Surface:
    """La tela: i colori dello schema e i marchi `sp` (per fascia)."""
    tinta = {k: sch[k] for k in ("fondo", "accento", "terzo")}
    zone = sch["zone"]
    fondo = tinta["fondo"]
    tela = pygame.Surface((LARGA, ALTA))
    tela.fill(fondo)
    # --- i fianchi
    if "meta" in zone:
        _poligono_fianco(tela, [(-0.35, 0.0), (X0, 0.0), (X0, Y1), (0.05, Y1)], tinta[zone["meta"]])
    if "basso" in zone:
        _poligono_fianco(tela, [(X0, 0.0), (X1, 0.0), (X1, 0.20), (1.2, 0.20), (0.4, 0.30),
                                (-1.6, 0.30), (X0, 0.24)], tinta[zone["basso"]])
    if "pance" in zone:
        _poligono_fianco(tela, [(0.75, 0.18), (0.75, 0.62), (0.2, 0.62), (-1.9, 0.32),
                                (-1.9, 0.14)], tinta[zone["pance"]])
    if "cofano" in zone:
        _poligono_fianco(tela, [(-0.3, 0.80), (-0.3, Y1), (X0, Y1), (X0, 0.40), (-1.9, 0.48)],
                         tinta[zone["cofano"]])
    if "fascia" in zone:
        _poligono_fianco(tela, [(2.4, 0.30), (2.4, 0.36), (0.6, 0.58), (-1.6, 0.74),
                                (-1.8, 0.66), (0.5, 0.48)], tinta[zone["fascia"]])
    if "muso" in zone:
        _poligono_fianco(tela, [(2.35, 0.0), (X1, 0.0), (X1, 0.5), (2.35, 0.5)], tinta[zone["muso"]])
    if "spina" in zone:
        _poligono_fianco(tela, [(2.9, 0.26), (1.3, 0.58), (0.5, 0.70), (0.5, 0.74), (1.3, 0.62),
                                (2.9, 0.30)], tinta[zone["spina"]])
    # --- da sopra: la spina dorsale, le pance, la meta'
    if "meta" in zone:
        _poligono_sopra(tela, [(-0.35, -1.0), (X0, -1.0), (X0, 1.0), (-0.35, 1.0)], tinta[zone["meta"]])
    if "pance" in zone:
        for lato in (-1, 1):
            _poligono_sopra(tela, [(0.75, lato * 0.3), (0.75, lato * 0.8), (-1.9, lato * 0.25),
                                   (-1.9, lato * 0.14)], tinta[zone["pance"]])
    if "cofano" in zone:
        _poligono_sopra(tela, [(-0.3, -0.2), (-0.3, 0.2), (-2.5, 0.1), (-2.5, -0.1)],
                        tinta[zone["cofano"]])
    if "spina" in zone or "fascia" in zone:
        c = tinta[zone.get("spina", zone.get("fascia"))]
        _poligono_sopra(tela, [(2.95, -0.03), (2.95, 0.03), (-2.4, 0.03), (-2.4, -0.03)], c)
    if "muso" in zone:
        _poligono_sopra(tela, [(2.35, -1.0), (X1, -1.0), (X1, 1.0), (2.35, 1.0)], tinta[zone["muso"]])
    # --- le ali: tinta piena
    ali = tinta[zone.get("ali", "fondo")]
    pygame.draw.rect(tela, ali, (0, FIANCO_H + SOPRA_H, LARGA, ALI_H))

    # --- gli sponsor, dove stanno sulle macchine vere
    title = sp["title"][:1]
    primari = sp["primary"][:2]
    secondari = sp["secondary"][:3]
    tecnici = sp["technical"][:1]
    principale = (title or primari or secondari or [None])[0]

    def box_fianco(x0, x1, y0, y1, sinistro):
        a, b = _fianco(x0, y1, sinistro), _fianco(x1, y0, sinistro)
        return pygame.Rect(int(min(a[0], b[0])), int(min(a[1], b[1])),
                           int(abs(b[0] - a[0])), int(abs(b[1] - a[1])))

    for sinistro in (False, True):
        if principale:
            _metti(tela, principale, box_fianco(-1.75, -0.50, 0.60, 0.84, sinistro),
                   _sotto(zone, tinta, "cofano"), True)
            # le paratie dell'ala posteriore
            _metti(tela, principale, box_fianco(-2.78, -2.28, 0.60, 0.86, sinistro),
                   fondo, True)
        if primari:
            _metti(tela, primari[0], box_fianco(-0.95, 0.30, 0.30, 0.46, sinistro), fondo)
        if len(primari) > 1:
            _metti(tela, primari[1], box_fianco(1.30, 2.30, 0.24, 0.38, sinistro), fondo)
        elif secondari:
            _metti(tela, secondari[0], box_fianco(1.30, 2.30, 0.24, 0.38, sinistro), fondo)
        if secondari:
            _metti(tela, secondari[-1], box_fianco(2.32, 2.95, 0.10, 0.26, sinistro), fondo)
        if len(secondari) > 1:
            _metti(tela, secondari[1], box_fianco(0.10, 0.50, 0.60, 0.69, sinistro), fondo)
        if tecnici:
            _metti(tela, tecnici[0], box_fianco(-1.55, -1.05, 0.20, 0.28, sinistro), fondo)
    # da sopra: il title lungo il cofano (se non c'e' la fascia sul dorso a
    # coprirlo), un partner sul muso, i secondari sulle pance
    if principale and "spina" not in zone and "fascia" not in zone:
        a, b = _sopra(-1.9, -0.13), _sopra(-0.55, 0.13)
        _metti(tela, principale, pygame.Rect(int(a[0]), int(a[1]), int(b[0] - a[0]),
                                             int(b[1] - a[1])), fondo, True)
    if primari:
        a, b = _sopra(1.3, -0.12), _sopra(2.5, 0.12)
        _metti(tela, primari[0], pygame.Rect(int(a[0]), int(a[1]), int(b[0] - a[0]),
                                             int(b[1] - a[1])), fondo)
    for k, s in enumerate(secondari[:2]):
        lato = -1 if k == 0 else 1
        a, b = _sopra(-0.9, lato * 0.62 - 0.1), _sopra(0.3, lato * 0.62 + 0.1)
        _metti(tela, s, pygame.Rect(int(a[0]), int(min(a[1], b[1])), int(b[0] - a[0]),
                                    int(abs(b[1] - a[1]))), fondo)
    # le ali: il title grande sulla posteriore, un altro marchio sull'anteriore
    y_post = FIANCO_H + SOPRA_H
    if principale:
        _metti(tela, principale, pygame.Rect(0, y_post, LARGA, ALI_H // 2), ali, True)
    ant = (primari[1:] or secondari or primari or [None])[0]
    if ant:
        _metti(tela, ant, pygame.Rect(LARGA // 4, y_post + ALI_H // 2, LARGA // 2, ALI_H // 2),
               ali, True)
    return tela


def _sotto(zone, tinta, nome) -> tuple:
    """Il colore che c'e' sotto una scritta, per scegliere quello della scritta."""
    return tinta[zone[nome]] if nome in zone else tinta["fondo"]
