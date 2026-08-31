"""Palette, font e helper di disegno."""
from __future__ import annotations

import pygame

from .. import config as C

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

# I caratteri viaggiano col gioco invece di essere presi dal sistema: su
# Windows si vedeva il font di Windows, su Linux un altro e nel browser un
# altro ancora, e le stesse schermate venivano fuori diverse. Adesso sono tre
# facce sole, tutte a licenza aperta e impacchettate qui dentro:
#   Barlow            per il testo, stretto quel tanto che serve a far stare
#                     una tabella di ventidue righe senza tagliare i nomi
#   Barlow Condensed  per i titoli grandi, che e' il taglio dei tabelloni
#   IBM Plex Mono     per i numeri, con le cifre tutte della stessa larghezza:
#                     i tempi sul giro non ballano piu' mentre scorrono
_FONTS: dict = {}
_DIR = C.ROOT / "assets" / "fonts"
_FILE = {
    ("sans", False): "Barlow-Medium.ttf",
    ("sans", True): "Barlow-SemiBold.ttf",
    ("mono", False): "IBMPlexMono-Regular.ttf",
    ("mono", True): "IBMPlexMono-SemiBold.ttf",
    ("titolo", True): "BarlowCondensed-Bold.ttf",
}
# Il corpo resta quello di prima: misurato sull'altezza della x e sulla
# larghezza di una frase intera, Barlow allo stesso corpo si legge come il
# carattere che c'era - e le pagine, che sono tarate al pixel, non si muovono.
SCALA = 1.0
# Da qui in su una scritta in grassetto e' un titolo, e i titoli vanno in
# condensato: e' la stessa distinzione che fa una grafica televisiva.
TITOLO_DA = 20

# quando i file non ci sono - un sorgente incompleto - si torna al sistema
_FALLBACK = {"sans": "Segoe UI,Inter,DejaVu Sans,Arial",
             "mono": "Consolas,DejaVu Sans Mono,Courier New",
             "titolo": "Segoe UI Semibold,Inter,DejaVu Sans,Arial"}


def font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    key = (size, bold, mono)
    f = _FONTS.get(key)
    if f is None:
        if mono:
            faccia, corpo = "mono", size
        elif bold and size >= TITOLO_DA:
            faccia, corpo = "titolo", int(round(size * SCALA))
        else:
            faccia, corpo = "sans", int(round(size * SCALA))
        f = _carica(faccia, bold, corpo)
        _FONTS[key] = f
    return f


def _carica(faccia: str, bold: bool, corpo: int) -> pygame.font.Font:
    nome = _FILE.get((faccia, bold))
    if nome:
        strada = _DIR / nome
        if strada.exists():
            return pygame.font.Font(str(strada), corpo)
    try:
        return pygame.font.SysFont(_FALLBACK[faccia], corpo, bold=bold)
    except Exception:
        # nel browser senza font di sistema resta quello incluso in pygame
        f = pygame.font.Font(None, corpo)
        f.set_bold(bold)
        return f


# Le etichette sono quasi tutte identiche da un frame all'altro: rasterizzarle
# ogni volta era il costo principale del disegno. Il tetto tiene a bada le
# stringhe che cambiano di continuo, come i distacchi durante la gara.
_SURFS: dict = {}
_SURF_MAX = 3000


def render(s: str, size: int = 16, colour=TEXT, bold: bool = False,
           mono: bool = False) -> pygame.Surface:
    key = (s, size, bold, mono, tuple(colour))
    img = _SURFS.get(key)
    if img is None:
        if len(_SURFS) >= _SURF_MAX:
            _SURFS.clear()
        img = font(size, bold, mono).render(s, True, colour)
        _SURFS[key] = img
    return img


# --- quanto in basso arriva il disegno ------------------------------------
# Le pagine sono scritte a coordinate fisse e non sanno dire quanto sono alte.
# Invece di chiederglielo una per una - e sbagliarsi quando una cresce - si
# guarda dove arriva l'inchiostro: chi disegna accende il conto prima e lo
# legge dopo. Serve a decidere se una pagina deve scorrere.
_INK = [0.0]
_INK_ON = [False]


def ink_start() -> None:
    _INK[0] = 0.0
    _INK_ON[0] = True


def ink_stop() -> float:
    _INK_ON[0] = False
    return _INK[0]


def _ink(y: float) -> None:
    if _INK_ON[0] and y > _INK[0]:
        _INK[0] = y


def text(surf, s: str, pos, size: int = 16, colour=TEXT, bold: bool = False,
         mono: bool = False, align: str = "left", maxw: int | None = None):
    f = font(size, bold, mono)
    s = str(s)
    if maxw:
        s = ellipsize(s, f, maxw)
    img = render(s, size, colour, bold, mono)
    r = img.get_rect()
    _ink(pos[1] + r.h)
    if align == "left":
        r.topleft = pos
    elif align == "center":
        r.midtop = pos
    else:
        r.topright = pos
    surf.blit(img, r)
    return r


def width(s: str, size: int = 16, bold: bool = False, mono: bool = False) -> int:
    """Larghezza di una stringa: serve a piazzare il cursore nel campo di testo."""
    return font(size, bold, mono).size(str(s))[0]


_ELLIPSIS: dict = {}


def ellipsize(s: str, f: pygame.font.Font, maxw: int) -> str:
    # il taglio misura la stringa un carattere alla volta: senza cache lo
    # rifarebbe a ogni frame per ogni etichetta troncata
    key = (s, id(f), maxw)
    out = _ELLIPSIS.get(key)
    if out is None:
        if len(_ELLIPSIS) >= _SURF_MAX:
            _ELLIPSIS.clear()
        out = s
        if f.size(s)[0] > maxw:
            while out and f.size(out + "...")[0] > maxw:
                out = out[:-1]
            out += "..."
        _ELLIPSIS[key] = out
    return out


_WRAP: dict = {}


def wrap(s: str, size: int = 13, maxw: int = 200, bold: bool = False,
         mono: bool = False) -> list:
    """Spezza un testo in righe che ci stanno in `maxw`.

    Prima ogni pagina si spezzava le frasi per conto suo, a mano, contando le
    righe a occhio: e' cosi' che due blocchi finivano uno sopra l'altro. Qui la
    misura si fa una volta sola e si tiene in cache, e chi scrive sa quante
    righe occupera'.
    """
    key = (s, size, maxw, bold, mono)
    out = _WRAP.get(key)
    if out is not None:
        return out
    if len(_WRAP) >= _SURF_MAX:
        _WRAP.clear()
    f = font(size, bold, mono)
    righe, cur = [], ""
    for parola in str(s).split():
        prova = (cur + " " + parola).strip()
        if cur and f.size(prova)[0] > maxw:
            righe.append(cur)
            cur = parola
        else:
            cur = prova
    if cur or not righe:
        righe.append(cur)
    _WRAP[key] = righe
    return righe


def paragraph(surf, s: str, pos, size: int = 12, colour=DIM_2, maxw: int = 200,
              bold: bool = False, leading: int = 0) -> int:
    """Scrive un testo mandandolo a capo, e dice quanto spazio ha occupato.

    `text(..., maxw=...)` taglia la frase con i puntini: va bene per
    un'etichetta, non per una spiegazione. Qui la frase si legge tutta.
    """
    y = pos[1]
    passo = line_h(size, bold) + leading
    for riga in wrap(s, size, maxw, bold):
        text(surf, riga, (pos[0], y), size, colour, bold=bold)
        y += passo
    return y - pos[1]


# L'interlinea non si chiede al carattere: cambiando faccia cambierebbe, e
# tutte le pagine sono misurate su quella. Un quinto in piu' del corpo e' il
# passo con cui sono state scritte, e con cui restano leggibili.
INTERLINEA = 1.16


def line_h(size: int, bold: bool = False) -> int:
    """Altezza di una riga di testo, interlinea compresa."""
    return int(round(size * INTERLINEA))


def panel(surf, rect, colour=PANEL, radius: int = 10, border=None, width: int = 1):
    _ink(rect[1] + rect[3])
    pygame.draw.rect(surf, colour, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width, border_radius=radius)


# Il segno del riferimento sulla barra: la tacca che dice dov'e' la media
# della griglia. Senza, una barra risponde solo a "quanto", che e' meta' della
# domanda: ottantacinque di aerodinamica non vuol dire niente finche' non si sa
# se gli altri stanno a settanta o a novantadue. Con la tacca la risposta si
# legge senza pensarci.
# Due colori e non uno: la tacca cade sopra il riempimento quando si sta sopra
# la media e sul fondo vuoto quando si sta sotto, e un grigio solo sparisce in
# uno dei due casi. Quella scura si vede sul verde, quella chiara sul fondo.
TACCA = (150, 164, 188)
TACCA_SOPRA = (18, 24, 34)


def bar(surf, rect, value: float, maxv: float = 100.0, colour=ACCENT, bg=PANEL_3,
        radius: int = 4, riferimento: float | None = None):
    _ink(rect[1] + rect[3])
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    frac = max(0.0, min(1.0, value / maxv if maxv else 0.0))
    if frac > 0:
        r = pygame.Rect(rect[0], rect[1], max(2, int(rect[2] * frac)), rect[3])
        pygame.draw.rect(surf, colour, r, border_radius=radius)
    if riferimento is not None and maxv and rect[2] >= 30:
        q = max(0.02, min(0.98, riferimento / maxv))
        x = int(rect[0] + rect[2] * q)
        # la tacca sborda di un pixel sopra e sotto: dentro alla barra si
        # confonderebbe con il riempimento proprio dove serve leggerla
        col = TACCA_SOPRA if q <= frac else TACCA
        pygame.draw.rect(surf, col, (x, rect[1] - 1, 2, rect[3] + 2))


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


def fmt_race(t: float) -> str:
    """Durata di una gara: ore, minuti, secondi.

    fmt_time e' fatto per i giri e sopra i 999 secondi si arrende: il tempo del
    vincitore di un gran premio non e' un giro, sono quasi due ore.
    """
    if t is None or t <= 0:
        return "--:--.---"
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    if h >= 1:
        return f"{int(h)}:{int(m):02d}:{s:06.3f}"
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
