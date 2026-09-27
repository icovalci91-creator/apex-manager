"""Panda3D come motore della vista 3D, fuori schermo.

La finestra resta di pygame, e con lei tutto il resto del gioco: pannelli,
tabellone, pulsanti. Panda3D disegna la scena in un buffer della scheda video
che non si vede, e se ne legge il risultato come un'immagine qualunque da
incollare nel riquadro della mappa - lo stesso patto della vista in moderngl,
con un motore vero dietro: il grafo della scena, i livelli di dettaglio, il
caricamento dei modelli, i filtri.

Qui sta solo l'accensione e il buffer: prima di tutto la configurazione
(Panda3D la legge una volta, all'importazione), poi la scelta della scheda
video, e il buffer fuori schermo da cui si leggono i fotogrammi. La scena la
costruisce `vista_panda`.

Se Panda3D non c'e' - non installato, nel browser, una scheda senza OpenGL
3.3 - `disponibile()` risponde di no e la vista 3D resta quella di prima.
"""
from __future__ import annotations

import os
import sys

_STATO = {"provato": False, "ok": False, "pipe": None, "motore": None,
          "scheda": "", "errore": ""}


def _configura() -> None:
    """La configurazione di Panda3D, prima di importare il resto.

    Il mondo del gioco ha la y in alto (x a est, z a sud): Panda3D lavora con
    lo stesso riferimento, cosi' le coordinate passano tali e quali. Niente
    finestra sua, niente audio (lo fa pygame), niente attesa del monitor.
    Nell'eseguibile i pezzi di Panda3D stanno accanto al gioco, nella
    cartella panda3d/: il modulo di OpenGL si carica da li'."""
    interno = getattr(sys, "_MEIPASS", None)
    if interno:
        # nell'eseguibile non c'e' la cartella etc/ di Panda3D: glielo si dice,
        # se no all'avvio avvisa che non trova i file di configurazione
        os.environ.setdefault("PANDA_PRC_DIR", interno)
    from panda3d.core import loadPrcFileData
    righe = [
        "load-display pandagl",
        "window-type none",
        "audio-library-name null",
        "sync-video false",
        "coordinate-system yup-right",
        "notify-level warning",
        "notify-level-display fatal",
        "gl-version 3 3",
        "textures-power-2 none",
        "model-cache-dir",
    ]
    if interno:
        righe.append(f"plugin-path {os.path.join(interno, 'panda3d')}")
    loadPrcFileData("apex", "\n".join(righe))


def disponibile() -> bool:
    """Si puo' disegnare con Panda3D? Si prova una volta sola."""
    s = _STATO
    if s["provato"]:
        return s["ok"]
    s["provato"] = True
    if sys.platform == "emscripten" or os.environ.get("APEX_NO_PANDA"):
        return False
    try:
        _configura()
        from panda3d.core import GraphicsEngine, GraphicsPipeSelection
        pipe = GraphicsPipeSelection.get_global_ptr().make_default_pipe()
        if pipe is None:
            s["errore"] = "nessun modulo grafico"
            return False
        s["pipe"], s["motore"] = pipe, GraphicsEngine.get_global_ptr()
        prova = Uscita((64, 64))
        gsg = prova.buffer.get_gsg()
        s["scheda"] = gsg.get_driver_renderer()
        versione = (gsg.get_driver_version_major(), gsg.get_driver_version_minor())
        prova.chiudi()
        if versione < (3, 3) or not gsg.get_supports_glsl():
            s["errore"] = f"OpenGL {versione[0]}.{versione[1]}: serve il 3.3"
            return False
        s["ok"] = True
        # all'uscita si chiudono i buffer prima che Python smonti i moduli: se
        # no Panda3D li chiude da solo troppo tardi e il programma finisce con
        # un errore invece che in silenzio
        import atexit
        atexit.register(chiudi_tutto)
    except Exception as ex:           # una DLL che manca, un driver rotto
        s["errore"] = f"{type(ex).__name__}: {ex}"
        s["ok"] = False
    return s["ok"]


def chiudi_tutto() -> None:
    m = _STATO["motore"]
    if m is not None:
        try:
            m.remove_all_windows()
        except Exception:
            pass
    _HOST[0] = None


def scheda() -> str:
    return _STATO["scheda"]


def errore() -> str:
    return _STATO["errore"]


def motore():
    return _STATO["motore"]


class Uscita:
    """Un buffer fuori schermo grande `misura`, da cui si leggono i fotogrammi.

    La scena la disegna chi ci attacca una camera (`regione`); `leggi` fa girare
    il motore e restituisce il fotogramma come Surface di pygame."""

    def __init__(self, misura, campioni: int = 0, profondita: bool = True):
        from panda3d.core import (FrameBufferProperties, GraphicsOutput, GraphicsPipe,
                                  Texture, WindowProperties)
        self.misura = (int(misura[0]), int(misura[1]))
        fb = FrameBufferProperties()
        fb.set_rgb_color(True)
        fb.set_rgba_bits(8, 8, 8, 8)
        fb.set_depth_bits(24 if profondita else 0)
        if campioni:
            fb.set_multisamples(campioni)
        wp = WindowProperties.size(*self.misura)
        m = _STATO["motore"]
        self.buffer = m.make_output(_STATO["pipe"], "apex", 0, fb, wp,
                                    GraphicsPipe.BF_refuse_window, None, None)
        if self.buffer is None:
            raise RuntimeError("Panda3D non riesce ad aprire un buffer fuori schermo")
        self.tex = Texture("fotogramma")
        self.buffer.add_render_texture(self.tex, GraphicsOutput.RTM_copy_ram)
        self.buffer.set_clear_color_active(True)
        self.buffer.set_clear_color((0, 0, 0, 1))
        # la regione di base non disegna niente: le camere si attaccano dopo
        self.buffer.get_display_region(0).set_active(False)

    def regione(self, camera, ordine: int = 0):
        dr = self.buffer.make_display_region()
        dr.set_camera(camera)
        dr.set_sort(ordine)
        return dr

    def leggi(self):
        """Fa girare il motore e restituisce il fotogramma (pygame.Surface)."""
        import pygame
        _STATO["motore"].render_frame()
        dati = self.tex.get_ram_image_as("RGB")
        img = pygame.image.frombuffer(bytes(dati), self.misura, "RGB")
        # le righe arrivano dal fondo, come in OpenGL
        return pygame.transform.flip(img, False, True)

    def chiudi(self) -> None:
        if self.buffer is not None:
            _STATO["motore"].remove_window(self.buffer)
            self.buffer = None


_HOST = [None]


def host():
    """Il buffer d'appoggio: piccolo, sempre acceso e mai disegnato. Tutti gli
    altri buffer nascono su di lui e ne condividono la scheda video, cosi' le
    texture passano dall'uno all'altro senza copie."""
    if _HOST[0] is None:
        u = Uscita((16, 16))
        u.buffer.set_active(False)
        _HOST[0] = u
    return _HOST[0].buffer


def buffer(nome: str, misura, ordine: int, *, campioni: int = 0, virgola: bool = True,
           profondita: bool = True, ram: bool = False, solo_profondita: bool = False):
    """Un buffer fuori schermo (un framebuffer object) con la sua texture.

    `virgola`: colori a mezza precisione, che vanno oltre l'1 (servono al
    bagliore); `ram`: la texture si copia in memoria a ogni fotogramma, per
    leggerla; `solo_profondita`: niente colore, solo la profondita' (le
    ombre). Restituisce (buffer, texture), o (None, None) se la scheda dice di
    no - per esempio a troppi campioni di antialiasing."""
    from panda3d.core import (FrameBufferProperties, GraphicsOutput, GraphicsPipe,
                              Texture, WindowProperties)
    h = host()
    fb = FrameBufferProperties()
    if solo_profondita:
        fb.set_rgba_bits(0, 0, 0, 0)
    elif virgola and not ram:
        fb.set_rgba_bits(16, 16, 16, 16)
        fb.set_float_color(True)
    else:
        fb.set_rgba_bits(8, 8, 8, 8)
    fb.set_depth_bits(24 if (profondita or solo_profondita) else 0)
    if campioni:
        fb.set_multisamples(campioni)
    b = _STATO["motore"].make_output(
        _STATO["pipe"], nome, ordine, fb, WindowProperties.size(int(misura[0]), int(misura[1])),
        GraphicsPipe.BF_refuse_window, h.get_gsg(), h)
    if b is None:
        return None, None
    t = Texture(nome)
    if solo_profondita:
        t.set_format(Texture.F_depth_component24)
        b.add_render_texture(t, GraphicsOutput.RTM_bind_or_copy, GraphicsOutput.RTP_depth)
    else:
        b.add_render_texture(t, GraphicsOutput.RTM_copy_ram if ram
                             else GraphicsOutput.RTM_bind_or_copy, GraphicsOutput.RTP_color)
    b.get_display_region(0).set_active(False)
    return b, t


def togli(b) -> None:
    if b is not None:
        _STATO["motore"].remove_window(b)


def prova_da_riga_di_comando(percorso: str) -> int:
    """`ApexManager.exe --prova-3d`: dice se Panda3D si accende, e con che
    scheda. Serve alla build di GitHub per controllare che l'eseguibile si
    porti dietro tutti i pezzi. Scrive il risultato in `percorso`."""
    ok = False
    righe = []
    try:
        import panda3d
        righe.append(f"panda3d {getattr(panda3d, '__version__', '?')} importato")
        ok = disponibile()
        righe.append(f"scheda: {scheda() or '-'}")
        if errore():
            righe.append(f"errore: {errore()}")
        # la macchina di GitHub non ha una scheda video: che si arrivi ad
        # aprire il modulo di OpenGL basta a dire che i pezzi ci sono tutti
        caricato = _STATO["pipe"] is not None
        righe.append(f"modulo OpenGL: {'caricato' if caricato else 'MANCA'}")
        righe.append(f"disegno 3D: {'si' if ok else 'no'}")
        ok = caricato
    except Exception as ex:
        righe.append(f"ERRORE {type(ex).__name__}: {ex}")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")
    return 0 if ok else 1
