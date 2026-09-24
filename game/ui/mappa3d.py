"""La mappa della gara in 3D, per le scene che la mostrano.

Il weekend di Formula 1 e l'E-Prix la usano uguale: la pista vista
dall'elicottero, i pallini sopra, un clic per seguire una macchina, il mouse
per girarci attorno. Chi la usa deve avere `app`, `track`, `widgets`,
`build()` e `_spazio(x, y)`, chiamare `_init_3d()` nel costruttore,
`self.v3d.aggiorna(dt)` nell'update e `_mano_3d(ev)` in `handle`.
"""
from __future__ import annotations

import math

import pygame

from . import theme as T
from . import pista3d, trackdraw, vista3d
from .widgets import Button


# da quanti pixel di lunghezza in su una macchina si vede da sola
MACCHINA_PX = 26


class Mappa3D:
    """I pezzi della vista 3D che non dipendono dal tipo di gara."""

    def _init_3d(self) -> None:
        # la pista in 3D: si carica sulla scheda video la prima volta che serve
        self.v3d = None
        self._trascina = None
        self.segui_id = None        # la macchina a cui e' agganciata la ripresa 3D
        self._pallini = []          # dove stanno i pallini sullo schermo, per il clic
        self._righe_torre = None    # le righe del tabellone, per sceglierci chi seguire
        self._mappa = None          # dove sta la mappa, per il mouse
        self._dt = 1 / 60

    # -- quello che cambia da una scena all'altra
    def _entranti_3d(self) -> list:
        """Le macchine in pista adesso."""
        sim = getattr(self, "sim", None)
        return list(sim.entrants) if sim else []

    def _meteo_3d(self):
        sim = getattr(self, "sim", None)
        return sim.weather if sim else None

    def _mano_bloccata(self) -> bool:
        """Se sopra alla mappa c'e' aperto qualcos'altro, il mouse e' suo."""
        return False

    def _livrea_3d(self, driver_id, colore) -> tuple:
        """(seconda tinta, schema) della livrea di questa macchina."""
        scura = tuple(int(c * 0.25) for c in colore[:3])
        return (scura, 0)

    def _gomma_3d(self, driver_id) -> tuple:
        """Il colore della mescola montata, per la fascia sulla spalla."""
        from .. import config as C
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        mescola = getattr(e, "tyre", "") if e is not None else ""
        return tuple(C.COMPOUNDS.get(mescola, {}).get("colour", (255, 214, 0)))

    def _alone_3d(self, driver_id):
        """Un colore attorno al pallino, per chi ha qualcosa da far vedere."""
        return None

    def _modo_vista(self) -> str:
        """2d o 3d. La scelta resta per tutta la partita."""
        modo = getattr(self.app, "vista_gara", None)
        if modo not in ("2d", "3d"):
            modo = "3d" if vista3d.disponibile() else "2d"
        return modo if (modo == "2d" or vista3d.disponibile()) else "2d"

    def _in_3d(self) -> bool:
        return self._modo_vista() == "3d" and vista3d.disponibile()

    def set_vista(self, modo: str) -> None:
        self.app.vista_gara = modo
        self.build()

    def _comandi_vista(self, mappa) -> None:
        """2D e 3D, in alto a sinistra sulla mappa. Senza OpenGL non ci sono."""
        if not vista3d.disponibile():
            return
        modo = self._modo_vista()
        x = mappa.x + 10
        for chiave, lab, tip in (("2d", "2D", "La mappa vista da sopra"),
                                 ("3d", "3D", "Il circuito dall'elicottero")):
            b = Button((x, mappa.y + 10, 44, 26), lab, style="tab", tip=tip)
            b.on_click = (lambda m=chiave: self.set_vista(m))
            b.active = (modo == chiave and not (chiave == "3d" and self.segui_id))
            self.widgets.append(b)
            x += 50
        if modo == "3d" and self.segui_id:
            codice = self._codice(self.segui_id)
            b = Button((x + 6, mappa.y + 10, 104, 26), f"SEGUI {codice}", style="tab",
                       tip="La ripresa resta sopra a questa macchina")
            b.active = True
            self.widgets.append(b)
            self.widgets.append(Button((x + 116, mappa.y + 10, 96, 26), "CIRCUITO",
                                       lambda: self.segui(None), "ghost",
                                       tip="Torna a guardare tutto il circuito"))

    def _laterali(self, auto: list, forzati: dict | None = None) -> dict:
        """Le posizioni sulla larghezza della pista, senza scatti.

        Chi cambia lato - per difendere, per attaccare, per rientrare in
        traiettoria - ci va in un attimo ma non di colpo: in un quarto di
        secondo circa, come si vede in pista.
        """
        mete = trackdraw.laterali(self.track, auto, forzati)
        prima = getattr(self, "_lat_prec", {})
        k = min(1.0, self._dt * 4.0)
        ora = {c: prima.get(c, v) + (v - prima.get(c, v)) * k for c, v in mete.items()}
        self._lat_prec = ora
        return ora

    def _manovre(self) -> dict:
        """Chi si e' spostato per attaccare o difendere, e dove."""
        return {e.driver_id: e.manovra for e in self._entranti_3d()
                if getattr(e, "manovra_t", 0.0) > 0.0 and e.status == "running"}

    def _codice(self, driver_id) -> str:
        return next((e.code for e in self._entranti_3d() if e.driver_id == driver_id), "")

    def segui(self, driver_id) -> None:
        """Aggancia la ripresa 3D a una macchina, o la rimette sul circuito."""
        self.segui_id = driver_id
        self.build()

    def _mappa_3d(self, surf, vista, auto: list) -> bool:
        """La pista in 3D con i pallini delle macchine sopra.

        `auto` e' una lista di (pilota, frazione del giro, colore, nostra,
        sigla, ai box, con l'etichetta), dall'ultimo al primo: chi e' davanti
        si disegna per ultimo e resta sopra. False se la scheda video non ce
        la fa: chi chiama torna alla mappa 2D.
        """
        lat = self._laterali([(a[0], a[1]) for a in auto], self._manovre())
        metri = pista3d.MEZZA_PISTA - 1.2
        seguita = next((a for a in auto if a[0] == self.segui_id), None)
        if self.segui_id and seguita is None:
            # ritirata, o il turno e' finito: si torna sul circuito
            self.segui_id = None
            self.build()
        try:
            if self.v3d is None or self.v3d.geo.track is not self.track:
                self.v3d = vista3d.Vista3D(self.track)
            meteo = self._meteo_3d()
            self.v3d.nuvole = max(getattr(meteo, "cloud", 0.0), getattr(meteo, "wet", 0.0) * 1.3)
            self.v3d.bagnato = getattr(meteo, "wet", 0.0)
            if seguita:
                self.v3d.segui(seguita[0], seguita[1], lat[seguita[0]] * metri)
            else:
                self.v3d.segui(None)
            # le monoposto vere, con la livrea di ognuna
            self.v3d.auto = [(a[1], lat[a[0]] * metri, a[2]) + self._livrea_3d(a[0], a[2])
                             + (self._gomma_3d(a[0]),) for a in auto]
            img = self.v3d.disegna(vista.size)
        except Exception as exc:          # driver, memoria: la scheda video dice di no
            vista3d.spegni()
            self.v3d = None
            self.app.toast(f"Vista 3D non disponibile ({type(exc).__name__}): torno alla mappa")
            self.build()
            return False
        self._mappa = pygame.Rect(vista)
        maschera = getattr(self, "_maschera", None)
        if maschera is None or maschera.get_size() != vista.size:
            maschera = pygame.Surface(vista.size, pygame.SRCALPHA)
            pygame.draw.rect(maschera, (255, 255, 255, 255), maschera.get_rect(), border_radius=10)
            self._maschera = maschera
        img = img.convert_alpha()
        img.blit(maschera, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(img, vista.topleft)
        pygame.draw.rect(surf, T.LINE, vista, 1, border_radius=10)
        # i pallini, sulla traiettoria: in fila, e affiancati solo quando
        # sono davvero ruota a ruota
        prima = surf.get_clip()
        surf.set_clip(vista.clip(prima) if prima else vista)
        self._etichette = []
        self._pallini = []
        punti = []
        vicino = self.segui_id is not None
        for chi, f, col, mio, code, box, nome in auto:
            p = self.v3d.proietta(f, lat[chi] * metri)
            if p is None:
                continue
            x, y = int(vista.x + p[0]), int(vista.y + p[1])
            r = (7 if mio else 5) + (2 if vicino else 0)
            # quando la macchina e' abbastanza grande da vedersi, il pallino
            # lascia il posto alla monoposto: resta la sigla, e l'anello per
            # chi si sta seguendo
            grande = self.v3d.pixel_per_metro(f, lat[chi] * metri) * 5.4 >= MACCHINA_PX
            if grande:
                # la sigla va sopra alla macchina, non addosso
                sopra = self.v3d.proietta(f, lat[chi] * metri, 1.6) or p
                if vista.collidepoint(x, y):
                    self._pallini.append((x, y, chi))
                punti.append((int(vista.x + sopra[0]) - 8, int(vista.y + sopra[1]) + 4,
                              code, mio, True))
                continue
            if chi == self.segui_id:
                pygame.draw.circle(surf, (255, 255, 255), (x, y), r + 5, 2)
            pygame.draw.circle(surf, (8, 10, 14), (x + 1, y + 2), r + 1)
            if box:
                pygame.draw.circle(surf, (150, 150, 160), (x, y), r + 2)
            alone = self._alone_3d(chi)
            if alone:
                pygame.draw.circle(surf, alone, (x, y), r + 3)
            pygame.draw.circle(surf, col, (x, y), r)
            pygame.draw.circle(surf, (255, 255, 255) if mio else (10, 14, 20), (x, y), r,
                               2 if mio else 1)
            if vista.collidepoint(x, y):
                self._pallini.append((x, y, chi))
            punti.append((x, y, code, mio, nome or chi == self.segui_id or vicino))
        for x, y, code, mio, nome in reversed(punti):
            if not nome or not self._spazio(x + 9, y - 10):
                continue
            larga = T.width(code, 12, bold=True) + 10
            T.panel(surf, (x + 8, y - 20, larga, 17),
                    T.squadra_viva() if mio else (16, 20, 30), radius=4, rilievo=False)
            T.text(surf, code, (x + 8 + larga // 2, y - 19), 12, T.WHITE, bold=True,
                   align="center")
        surf.set_clip(prima)
        aiuto = ("trascina: gira attorno  -  rotella: zoom" if self.segui_id else
                 "clic su un pallino o sul tabellone: segui  -  trascina: gira  -  "
                 "destro: sposta  -  rotella: zoom")
        T.text(surf, aiuto, (vista.right - 12, vista.bottom - 22), 11, (225, 230, 240),
               align="right")
        if self.v3d.geo.fonte:
            # la licenza dei dati chiede di dire da dove vengono, e sulla mappa
            T.text(surf, "Mappa: (c) OpenStreetMap contributors",
                   (vista.x + 12, vista.bottom - 22), 11, (225, 230, 240))
        return True

    def _mano_3d(self, ev) -> bool:
        """Il mouse sulla vista 3D: girarla, spostarla, avvicinarsi."""
        if not (self._in_3d() and self.v3d is not None and self._mappa is not None):
            return False
        if self._mano_bloccata():
            return False
        cam = self.v3d.elicottero
        if ev.type == pygame.MOUSEWHEEL:
            if self._mappa.collidepoint(pygame.mouse.get_pos()):
                cam.rotella(ev.y)
                return True
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            sopra_pulsante = any(w.rect.collidepoint(ev.pos) for w in self.widgets)
            if sopra_pulsante:
                return False
            if ev.button == 1 and self._mappa.collidepoint(ev.pos):
                # un clic su un pallino aggancia la ripresa a quella macchina
                vicini = [(math.hypot(x - ev.pos[0], y - ev.pos[1]), chi)
                          for x, y, chi in self._pallini]
                if vicini:
                    d, chi = min(vicini, key=lambda v: v[0])
                    if d <= 12 and chi != self.segui_id:
                        self.segui(chi)
                        return True
            if self._mappa.collidepoint(ev.pos):
                self._trascina = (ev.pos, ev.button)
                return True
            if ev.button == 1 and self._righe_torre:
                torre, y0, rh, ids = self._righe_torre
                if torre.collidepoint(ev.pos) and ev.pos[1] >= y0:
                    i = int((ev.pos[1] - y0) // rh)
                    if 0 <= i < len(ids):
                        self.segui(ids[i])
                        return True
            return False
        if ev.type == pygame.MOUSEMOTION and self._trascina is not None:
            (x0, y0), tasto = self._trascina
            dx, dy = ev.pos[0] - x0, ev.pos[1] - y0
            self._trascina = (ev.pos, tasto)
            if tasto == 1:
                cam.trascina(dx, dy)
            else:
                cam.sposta(dx, dy, self.v3d.geo)
            return True
        if ev.type == pygame.MOUSEBUTTONUP and self._trascina is not None:
            self._trascina = None
            return True
        return False
