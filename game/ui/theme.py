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
        try:
            f = pygame.font.SysFont(fam, size, bold=bold)
        except Exception:
            # nel browser non ci sono font di sistema: si usa quello incluso
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
        _FONTS[key] = f
    return _FONTS[key]


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


def text(surf, s: str, pos, size: int = 16, colour=TEXT, bold: bool = False,
         mono: bool = False, align: str = "left", maxw: int | None = None):
    f = font(size, bold, mono)
    s = str(s)
    if maxw:
        s = ellipsize(s, f, maxw)
    img = render(s, size, colour, bold, mono)
    r = img.get_rect()
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


def line_h(size: int, bold: bool = False) -> int:
    """Altezza di una riga di testo, interlinea compresa."""
    return font(size, bold).get_linesize()


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
