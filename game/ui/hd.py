"""L'alta definizione: il gioco disegnato alla risoluzione vera dello schermo.

Le schermate sono scritte in pixel "logici": una pagina e' larga 1600, un
pulsante e' alto 38, una scritta e' da 15. Prima quei pixel erano quelli dello
schermo, e su un monitor con lo scaling di Windows al 125 o 150% ci pensava
Windows a ingrandire la finestra - stirando l'immagine, e sfocando tutto.

Adesso il gioco dice a Windows che l'ingrandimento lo fa da se', e disegna su
una `Tela`: una superficie grande quanto lo schermo vero che si presenta alle
pagine con la misura logica. Chi disegna non si accorge di niente - chiede un
rettangolo a (100, 40) largo 200 e lo ottiene - ma sotto il rettangolo e'
disegnato a (150, 60) largo 300, con i bordi netti. Le scritte si scrivono al
corpo vero (una da 15 su una scala 1.5 e' un carattere da 22), le linee, i
cerchi e i poligoni pure. Solo le immagini gia' pronte a misura logica - le
luci, le ombre, le sfumature - si ingrandiscono, e sono morbide comunque.

La scala la sceglie il gioco (quella di Windows, o quella che fa tornare
l'altezza attorno ai 1080 pixel logici) oppure chi gioca, dalle impostazioni.
Nel browser non c'e': li' ci pensa il browser.
"""
from __future__ import annotations

import json
import math
import os
import sys
import weakref

import pygame

WEB = sys.platform == "emscripten"
SCALE = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
IMPOSTAZIONI = {"scala": 0.0, "schermo_intero": False,   # scala 0 = automatica
                "qualita": ""}                              # qualita' 3D, "" = automatica


# ------------------------------------------------------------ le immagini HD
class Immagine(pygame.Surface):
    """Un'immagine gia' alla risoluzione vera, che si presenta con la misura
    logica: la `Tela` la incolla com'e', senza ingrandirla."""

    def __init__(self, fisica: tuple, logica: tuple, flags=pygame.SRCALPHA):
        super().__init__(fisica, flags)
        self.logica = (int(logica[0]), int(logica[1]))

    def get_size(self):
        return self.logica

    def get_width(self):
        return self.logica[0]

    def get_height(self):
        return self.logica[1]

    def get_rect(self, **kw):
        return _rect_con(pygame.Rect((0, 0), self.logica), kw)


def _rect_con(r: pygame.Rect, kw: dict) -> pygame.Rect:
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def avvolgi(img: pygame.Surface, scala: float) -> Immagine:
    """Un'immagine disegnata a misura vera, con la sua misura logica."""
    w, h = pygame.Surface.get_size(img)
    out = Immagine((w, h), (math.ceil(w / scala), math.ceil(h / scala)))
    out.blit(img, (0, 0))
    return out


# ------------------------------------------------------------------ la tela
class Tela(pygame.Surface):
    """La superficie su cui si disegna tutto: grande quanto lo schermo vero,
    si presenta con la misura logica."""

    def __init__(self, logica: tuple, scala: float):
        self.S = float(scala)
        self.logica = (int(logica[0]), int(logica[1]))
        super().__init__((max(1, round(self.logica[0] * self.S)),
                          max(1, round(self.logica[1] * self.S))))

    # --- la misura che vedono le pagine
    def get_size(self):
        return self.logica

    def get_width(self):
        return self.logica[0]

    def get_height(self):
        return self.logica[1]

    def get_rect(self, **kw):
        r = pygame.Rect((0, 0), self.logica)
        return _rect_con(r, kw) if kw else r

    # --- da logico a vero e ritorno
    def v(self, x: float) -> int:
        return int(round(x * self.S))

    def punto(self, p) -> tuple:
        return (int(round(p[0] * self.S)), int(round(p[1] * self.S)))

    def rett(self, r) -> pygame.Rect:
        r = pygame.Rect(r)
        x0, y0 = round(r.x * self.S), round(r.y * self.S)
        x1, y1 = round(r.right * self.S), round(r.bottom * self.S)
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)

    def logico(self, r) -> pygame.Rect:
        r = pygame.Rect(r)
        x0, y0 = math.floor(r.x / self.S), math.floor(r.y / self.S)
        x1, y1 = math.ceil(r.right / self.S), math.ceil(r.bottom / self.S)
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)

    # --- le operazioni
    def blit(self, src, dest, area=None, special_flags=0):
        if isinstance(dest, pygame.Rect) or (hasattr(dest, "__len__") and len(dest) == 4):
            dest = pygame.Rect(dest).topleft
        pos = self.punto(dest)
        if isinstance(src, (Immagine, Tela)):
            if area is not None:
                area = self.rett(area) if isinstance(src, Tela) else _rett_immagine(src, area)
            r = pygame.Surface.blit(self, src, pos, area, special_flags)
            return self.logico(r)
        grande = _ingrandita(src, self.S)
        if area is not None:
            area = self.rett(area)
        r = pygame.Surface.blit(self, grande, pos, area, special_flags)
        return self.logico(r)

    def blits(self, sequenza, doreturn=True):
        out = [self.blit(*voce) for voce in sequenza]
        return out if doreturn else None

    def fill(self, color, rect=None, special_flags=0):
        r = pygame.Surface.fill(self, color, self.rett(rect) if rect is not None else None,
                                special_flags)
        return self.logico(r)

    def set_clip(self, rect=None):
        pygame.Surface.set_clip(self, self.rett(rect) if rect is not None else None)

    def get_clip(self):
        return self.logico(pygame.Surface.get_clip(self))

    def copy(self):
        """Una copia a misura logica: serve a chi la rimaneggia (il passaggio
        fra una schermata e l'altra), e che la rimette giu' ingrandita."""
        return pygame.transform.smoothscale(self, self.logica)

    def subsurface(self, rect):
        return pygame.Surface.subsurface(self, self.rett(rect))


def _rett_immagine(src: Immagine, area) -> pygame.Rect:
    fx = pygame.Surface.get_width(src) / max(1, src.logica[0])
    fy = pygame.Surface.get_height(src) / max(1, src.logica[1])
    r = pygame.Rect(area)
    return pygame.Rect(round(r.x * fx), round(r.y * fy), round(r.w * fx), round(r.h * fy))


# Le immagini a misura logica si ingrandiscono una volta sola, finche' esistono:
# un pannello o una luce si ridisegnano a ogni fotogramma, ma sono sempre le
# stesse. Quelle fatte al volo si ingrandiscono ogni volta, e costano poco.
_INGRANDITE: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _ingrandita(src: pygame.Surface, scala: float) -> pygame.Surface:
    if scala == 1.0:
        return src
    voce = _INGRANDITE.get(src)
    w, h = src.get_size()
    misura = (max(1, round(w * scala)), max(1, round(h * scala)))
    if voce is not None and voce[0] == misura and voce[1] == scala:
        return voce[2]
    try:
        grande = pygame.transform.smoothscale(src, misura)
    except (ValueError, pygame.error):
        grande = pygame.transform.scale(src, misura)
    try:
        _INGRANDITE[src] = (misura, scala, grande)
    except TypeError:
        pass
    return grande


def attiva(surf) -> bool:
    """Si sta disegnando sulla tela ad alta definizione?"""
    return isinstance(surf, Tela) and surf.S != 1.0


# ------------------------------------------------ pygame.draw, sulla tela
_ORIG: dict = {}


def _spessore(t, w) -> int:
    return max(1, int(round(w * t.S))) if w > 0 else 0


_RAGGI = ("border_radius", "border_top_left_radius", "border_top_right_radius",
          "border_bottom_left_radius", "border_bottom_right_radius")


def _rect(surface, color, rect, *a, **k):
    if not isinstance(surface, Tela):
        return _ORIG["rect"](surface, color, rect, *a, **k)
    s = surface.S
    g = lambda v: v if v <= 0 else int(round(v * s))
    a = list(a)
    if a:
        a[0] = _spessore(surface, a[0])
    for i in range(1, len(a)):
        a[i] = g(a[i])
    if "width" in k:
        k["width"] = _spessore(surface, k["width"])
    for nome in _RAGGI:
        if nome in k:
            k[nome] = g(k[nome])
    return surface.logico(_ORIG["rect"](surface, color, surface.rett(rect), *a, **k))


def _circle(surface, color, center, radius, *a, **k):
    if not isinstance(surface, Tela):
        return _ORIG["circle"](surface, color, center, radius, *a, **k)
    a = list(a)
    if a:
        a[0] = _spessore(surface, a[0])
    if "width" in k:
        k["width"] = _spessore(surface, k["width"])
    r = _ORIG["circle"](surface, color, surface.punto(center), radius * surface.S, *a, **k)
    return surface.logico(r)


def _line(surface, color, start_pos, end_pos, width=1):
    if not isinstance(surface, Tela):
        return _ORIG["line"](surface, color, start_pos, end_pos, width)
    r = _ORIG["line"](surface, color, surface.punto(start_pos), surface.punto(end_pos),
                      _spessore(surface, width))
    return surface.logico(r)


def _lines(surface, color, closed, points, width=1):
    if not isinstance(surface, Tela):
        return _ORIG["lines"](surface, color, closed, points, width)
    r = _ORIG["lines"](surface, color, closed, [surface.punto(p) for p in points],
                       _spessore(surface, width))
    return surface.logico(r)


def _polygon(surface, color, points, width=0):
    if not isinstance(surface, Tela):
        return _ORIG["polygon"](surface, color, points, width)
    r = _ORIG["polygon"](surface, color, [surface.punto(p) for p in points],
                         _spessore(surface, width))
    return surface.logico(r)


def _ellipse(surface, color, rect, width=0):
    if not isinstance(surface, Tela):
        return _ORIG["ellipse"](surface, color, rect, width)
    return surface.logico(_ORIG["ellipse"](surface, color, surface.rett(rect),
                                           _spessore(surface, width)))


def _arc(surface, color, rect, start_angle, stop_angle, width=1):
    if not isinstance(surface, Tela):
        return _ORIG["arc"](surface, color, rect, start_angle, stop_angle, width)
    return surface.logico(_ORIG["arc"](surface, color, surface.rett(rect), start_angle,
                                       stop_angle, _spessore(surface, width)))


def _aaline(surface, color, start_pos, end_pos, *a, **k):
    if not isinstance(surface, Tela):
        return _ORIG["aaline"](surface, color, start_pos, end_pos, *a, **k)
    return surface.logico(_ORIG["aaline"](surface, color, surface.punto(start_pos),
                                          surface.punto(end_pos), *a, **k))


def _aalines(surface, color, closed, points, *a, **k):
    if not isinstance(surface, Tela):
        return _ORIG["aalines"](surface, color, closed, points, *a, **k)
    return surface.logico(_ORIG["aalines"](surface, color, closed,
                                           [surface.punto(p) for p in points], *a, **k))


_TELA_ATTUALE: list = [None]


def _mouse_pos():
    x, y = _ORIG["get_pos"]()
    t = _TELA_ATTUALE[0]
    if t is None or t.S == 1.0:
        return (x, y)
    return (int(x / t.S), int(y / t.S))


def installa() -> None:
    """Sostituisce le funzioni di disegno di pygame con quelle che sanno della
    tela. Si fa una volta sola; su una superficie qualunque si comportano
    esattamente come prima."""
    if _ORIG:
        return
    for nome, f in (("rect", _rect), ("circle", _circle), ("line", _line),
                    ("lines", _lines), ("polygon", _polygon), ("ellipse", _ellipse),
                    ("arc", _arc), ("aaline", _aaline), ("aalines", _aalines)):
        _ORIG[nome] = getattr(pygame.draw, nome)
        setattr(pygame.draw, nome, f)
    _ORIG["get_pos"] = pygame.mouse.get_pos
    pygame.mouse.get_pos = _mouse_pos


def evento(ev, tela):
    """Un evento del mouse con le coordinate logiche."""
    if tela is None or tela.S == 1.0 or not hasattr(ev, "pos"):
        return ev
    d = dict(ev.dict)
    d["pos"] = (int(ev.pos[0] / tela.S), int(ev.pos[1] / tela.S))
    if "rel" in d:
        d["rel"] = (ev.rel[0] / tela.S, ev.rel[1] / tela.S)
    return pygame.event.Event(ev.type, d)


# ------------------------------------------------------------ lo schermo vero
def dpi_windows() -> None:
    """Prima di aprire la finestra: si dice a Windows che l'ingrandimento lo
    fa il gioco. Senza, Windows stira la finestra e sfoca tutto."""
    if WEB or not sys.platform.startswith("win"):
        return
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def scala_sistema() -> float:
    """L'ingrandimento che ha scelto Windows (125% -> 1.25), 1 altrove."""
    if not sys.platform.startswith("win"):
        return 1.0
    try:
        import ctypes
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


def scala_per(fisico: tuple) -> float:
    """La scala da usare su uno schermo di questa misura (in pixel veri).

    Se chi gioca ne ha scelta una, quella. Se no, la piu' grande fra quella di
    Windows e quella che porta l'altezza attorno ai 1080 pixel logici - un
    monitor 1440p a scaling 100% ha scritte minuscole altrimenti - e comunque
    tale che la finestra logica non scenda sotto la misura minima."""
    from .. import config as C
    scelta = float(IMPOSTAZIONI.get("scala") or 0.0)
    if scelta <= 0:
        auto = max(scala_sistema(), fisico[1] / 1080.0)
        scelta = max(1.0, math.floor(auto * 4 + 0.15) / 4.0)
    massima = min(fisico[0] / C.MIN_SCREEN_W, fisico[1] / C.MIN_SCREEN_H)
    return max(1.0, min(scelta, massima))


def _file():
    from .. import config as C
    return C.UTENTE / "video.json"


def carica() -> None:
    try:
        with open(_file(), encoding="utf-8") as f:
            dati = json.load(f)
        for k in IMPOSTAZIONI:
            if k in dati:
                IMPOSTAZIONI[k] = type(IMPOSTAZIONI[k])(dati[k])
    except Exception:
        pass


def salva() -> None:
    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        with open(_file(), "w", encoding="utf-8") as f:
            json.dump(IMPOSTAZIONI, f)
    except Exception:
        pass
