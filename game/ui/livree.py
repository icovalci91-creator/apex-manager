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


def _schema(team) -> dict:
    s = SCHEMI.get(team.id)
    if s is None:
        # una squadra nuova: i suoi due colori, e il nero dove va il nero
        s = dict(fondo=team.colour, accento=getattr(team, "accent", "") or "#202020",
                 terzo="#111111", zone={"fascia": "accento", "basso": "terzo", "ali": "fondo"})
    return {"fondo": T.hex_rgb(s["fondo"]), "accento": T.hex_rgb(s["accento"]),
            "terzo": T.hex_rgb(s["terzo"]), "zone": s["zone"]}


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
    sch = _schema(team)
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
    sp = _sponsor_ordinati(gs, team)
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
