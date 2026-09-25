"""La mappa della gara in 3D, per le scene che la mostrano.

Il weekend di Formula 1 e l'E-Prix la usano uguale: la pista vista
dall'elicottero, i pallini sopra, un clic per seguire una macchina, il mouse
per girarci attorno. Oppure la regia: la gara come in televisione, con le
telecamere a bordo pista, le camere car e i replay dei sorpassi (`regia`).
Chi la usa deve avere `app`, `track`, `widgets`, `build()` e `_spazio(x, y)`,
chiamare `_init_3d()` nel costruttore,
`self.v3d.aggiorna(dt)` nell'update e `_mano_3d(ev)` in `handle`.
"""
from __future__ import annotations

import math

import pygame

from . import theme as T
from . import audio, pista3d, regia, trackdraw, vista3d
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
        # le macchine senza strappi, e il regista per la vista TV
        self._continua = regia.Continuita()
        self._t_sim_3d = None
        self.regista = None
        self._replay_prima = False
        self._stacco = 9.0          # da quanto e' partito o finito il replay
        # per il suono: com'era l'ultimo fotogramma 3D, e chi accelera
        self._audio_3d = None
        self._accel: dict = {}
        self._v_prec: dict = {}

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
        """(seconda tinta, schema, indice della tela o -1) di questa macchina."""
        scura = tuple(int(c * 0.25) for c in colore[:3])
        return (scura, 0, -1)

    def _livree_3d(self) -> tuple:
        """Le tele delle livree e, per squadra, l'indice di ognuna."""
        return [], {}

    def _gomma_3d(self, driver_id) -> tuple:
        """Il colore della mescola montata, per la fascia sulla spalla."""
        from .. import config as C
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        mescola = getattr(e, "tyre", "") if e is not None else ""
        return tuple(C.COMPOUNDS.get(mescola, {}).get("colour", (255, 214, 0)))

    def _tempo_3d(self) -> float:
        """Il cronometro della gara, in secondi."""
        sim = getattr(self, "sim", None)
        return float(getattr(sim, "time", 0.0)) if sim else 0.0

    def _eventi_3d(self) -> list:
        """La cronaca: la regia ci legge i sorpassi."""
        sim = getattr(self, "sim", None)
        return list(getattr(sim, "events", []) or []) if sim else []

    def _elettrico_3d(self) -> bool:
        """Motori elettrici (la Formula E) o il V6 turbo."""
        return False

    def _alone_3d(self, driver_id):
        """Un colore attorno al pallino, per chi ha qualcosa da far vedere."""
        return None

    def _modo_vista(self) -> str:
        """2d, plastico, 3d o tv. La scelta resta per tutta la partita; si
        comincia dal plastico, che e' la vista da cui si gioca."""
        modo = getattr(self.app, "vista_gara", None)
        if modo not in ("2d", "plastico", "3d", "tv"):
            modo = "plastico" if vista3d.disponibile() else "2d"
        return modo if (modo == "2d" or vista3d.disponibile()) else "2d"

    def _in_3d(self) -> bool:
        """La pista in 3D: il plastico, l'elicottero o la regia."""
        return self._modo_vista() in ("plastico", "3d", "tv") and vista3d.disponibile()

    def _in_plastico(self) -> bool:
        return self._modo_vista() == "plastico" and vista3d.disponibile()

    def _in_tv(self) -> bool:
        return self._modo_vista() == "tv" and vista3d.disponibile()

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
                                 ("plastico", "PLASTICO", "Il circuito come un plastico sul "
                                                          "tavolo, con le schede dei piloti"),
                                 ("3d", "3D", "Il circuito dall'elicottero"),
                                 ("tv", "TV", "La regia: la gara come in televisione, "
                                              "con i replay dei sorpassi")):
            larga = max(44, T.width(lab, 15) + 22)
            b = Button((x, mappa.y + 10, larga, 26), lab, style="tab", tip=tip)
            b.on_click = (lambda m=chiave: self.set_vista(m))
            b.active = (modo == chiave and not (chiave in ("3d", "plastico") and self.segui_id))
            self.widgets.append(b)
            x += larga + 6
        if modo == "tv":
            x += 6

            def largo(testo):
                return T.width(testo, 15) + 24
            if self.segui_id:
                lab = f"REGIA SU {self._codice(self.segui_id)}"
                b = Button((x, mappa.y + 10, largo(lab), 26), lab, style="tab",
                           tip="Le telecamere guardano solo questa macchina")
                b.active = True
                self.widgets.append(b)
                x += largo(lab) + 6
                self.widgets.append(Button((x, mappa.y + 10, largo("REGIA LIBERA"), 26),
                                           "REGIA LIBERA", lambda: self.segui(None), "ghost",
                                           tip="Il regista torna a scegliere da solo"))
                x += largo("REGIA LIBERA") + 6
            self.widgets.append(Button((x, mappa.y + 10, largo("REPLAY"), 26), "REPLAY",
                                       self.replay_tv, "ghost",
                                       tip="Rivedi l'ultimo sorpasso. Durante un replay: "
                                           "torna in diretta"))
            return
        if modo in ("3d", "plastico") and self.segui_id:
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

    def replay_tv(self) -> None:
        """Il pulsante REPLAY: rivede l'ultimo sorpasso, o torna in diretta."""
        r = self.regista
        if r is None:
            return
        if r.replay is not None:
            r.salta()
        elif not r.rivedi():
            self.app.toast("Nessun sorpasso da rivedere, per ora")

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
        metri = pista3d.MEZZA_PISTA - 1.2
        forzati = self._manovre()
        if self.v3d is not None and self.v3d.geo.track is self.track:
            # chi e' ai box scorre nella corsia accanto alla pista
            for a in auto:
                if a[5]:
                    lato = self._lato_box_3d(a[1])
                    if lato is not None:
                        forzati[a[0]] = lato / metri
        lat = self._laterali([(a[0], a[1]) for a in auto], forzati)
        t_sim = self._tempo_3d()
        dt_sim = 0.0 if self._t_sim_3d is None else max(0.0, t_sim - self._t_sim_3d)
        self._t_sim_3d = t_sim
        tv = self._in_tv()
        seguita = next((a for a in auto if a[0] == self.segui_id), None)
        if self.segui_id and seguita is None:
            # ritirata, o il turno e' finito: si torna sul circuito
            self.segui_id = None
            self.build()
        try:
            tipo = "fe" if self._elettrico_3d() else "f1"
            if (self.v3d is None or self.v3d.geo.track is not self.track
                    or getattr(self.v3d, "tipo", "f1") != tipo):
                if self.v3d is not None:
                    self.v3d.rilascia()
                self.v3d = vista3d.Vista3D(self.track, tipo)
                # le livree si dipingono una volta per weekend, con gli
                # sponsor che le squadre hanno adesso
                tele, self._indice_livree = self._livree_3d()
                self.v3d.carica_livree(tele)
                self.regista = None
            self.v3d.plastico = self._modo_vista() == "plastico"
            meteo = self._meteo_3d()
            self.v3d.nuvole = max(getattr(meteo, "cloud", 0.0), getattr(meteo, "wet", 0.0) * 1.3)
            self.v3d.bagnato = getattr(meteo, "wet", 0.0)
            # dove stanno, senza gli strappi dei sorpassi: da vicino si vedrebbero
            giro = regia.lunghezza(self.v3d.geo)
            pos = self._continua.applica({a[0]: (a[1], lat[a[0]] * metri) for a in auto},
                                         dt_sim, giro)
            if dt_sim > 0:
                for chi in pos:
                    v = self._continua.velocita(chi)
                    a = (v - self._v_prec.get(chi, v)) / dt_sim
                    self._accel[chi] = self._accel.get(chi, 0.0) * 0.6 + a * 0.4
                    self._v_prec[chi] = v
            if tv:
                pos = self._regia(pos, auto, t_sim)
                self.v3d.segui(None)
            else:
                self.v3d.camera = None
                self.v3d.replay = 0.0
                if seguita:
                    self.v3d.segui(seguita[0], *pos[seguita[0]])
                else:
                    self.v3d.segui(None)
            # le monoposto vere, con la livrea di ognuna
            self.v3d.auto = [(pos[a[0]][0], pos[a[0]][1], a[2]) + self._livrea_3d(a[0], a[2])[:2]
                             + (self._gomma_3d(a[0]), self._livrea_3d(a[0], a[2])[2])
                             for a in auto if a[0] in pos]
            # e la safety car, davanti al primo
            sc = self._safety_car() if not (tv and self.regista and self.regista.replay) else None
            if sc is not None:
                self.v3d.auto.append((sc, self.track.linea_a(sc) * metri, (250, 176, 20),
                                      (24, 24, 28), 0, (250, 176, 20), -1))
            img = self.v3d.disegna(vista.size)
            self._audio_3d = (pygame.time.get_ticks(), pos, tv, dt_sim, vista.w)
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
        if sc is not None:
            q = self.v3d.proietta(sc, self.track.linea_a(sc) * metri, 1.8)
            if q is not None and vista.collidepoint(vista.x + q[0], vista.y + q[1]):
                self._etichetta_sc(surf, int(vista.x + q[0]), int(vista.y + q[1]))
        if tv:
            self._grafica_tv(surf, vista, auto, pos)
            return True
        # i pallini, sulla traiettoria: in fila, e affiancati solo quando
        # sono davvero ruota a ruota
        prima = surf.get_clip()
        surf.set_clip(vista.clip(prima) if prima else vista)
        self._etichette = []
        self._pallini = []
        punti = []
        schede = []
        plastico = self.v3d.plastico
        vicino = self.segui_id is not None
        for chi, _f, col, mio, code, box, nome in auto:
            f, laterale = pos[chi]
            p = self.v3d.proietta(f, laterale)
            if p is None:
                continue
            x, y = int(vista.x + p[0]), int(vista.y + p[1])
            r = (7 if mio else 5) + (2 if vicino else 0)
            # quando la macchina e' abbastanza grande da vedersi, il pallino
            # lascia il posto alla monoposto: resta la sigla, e l'anello per
            # chi si sta seguendo
            scala = self.v3d.scala_auto
            grande = plastico or (self.v3d.pixel_per_metro(f, laterale) * 5.4 * scala
                                  >= MACCHINA_PX)
            if grande:
                # la sigla va sopra alla macchina, non addosso
                sopra = self.v3d.proietta(f, laterale, 1.6 * scala) or p
                if vista.collidepoint(x, y):
                    self._pallini.append((x, y, chi))
                sx, sy = int(vista.x + sopra[0]), int(vista.y + sopra[1])
                if plastico:
                    # sul plastico: una puntina del colore della squadra sopra a
                    # ognuna, la sigla per chi conta, la scheda per le nostre
                    if mio:
                        schede.append((chi, f, laterale))
                        continue
                    pygame.draw.circle(surf, (10, 12, 16), (sx, sy - 3), 5)
                    pygame.draw.circle(surf, col, (sx, sy - 3), 4)
                    if nome or chi == self.segui_id:
                        punti.append((sx - 8, sy - 2, code, mio, True))
                    continue
                punti.append((sx - 8, sy + 4, code, mio, True))
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
        for k, (chi, f, laterale) in enumerate(schede):
            self._scheda(surf, vista, chi, f, laterale, k)
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
        if self._in_tv():
            return self._mano_tv(ev)
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

    # ------------------------------------------------------------- la regia
    def _regia(self, pos: dict, auto: list, t_sim: float) -> dict:
        """Il regista guarda la gara e dice cosa far vedere: la diretta, o un
        replay preso dal suo registro."""
        r = self.regista
        if r is None:
            r = self.regista = regia.Regista(sum(map(ord, self.track.id)))
            r.velocita = self._continua.velocita
        info = {a[0]: {"pos": len(auto) - k, "mio": a[3], "box": a[5]}
                for k, a in enumerate(auto)}
        r.fissa(self.segui_id)
        r.aggiorna(self.v3d.geo, self._dt, t_sim, pos, info, self._eventi_3d())
        self.v3d.camera = r
        in_replay = r.replay is not None
        if in_replay != self._replay_prima:
            self._stacco = 0.0
            self._replay_prima = in_replay
        self._stacco += self._dt
        self.v3d.replay = 1.0 if in_replay else 0.0
        # nel replay ci sono solo quelli che il registro ricorda
        in_pista = set(info)
        return {c: v for c, v in r.pos.items() if c in in_pista}

    def _grafica_tv(self, surf, vista, auto: list, pos: dict) -> None:
        """La grafica della televisione: chi si sta guardando, la camera, il
        replay. E i punti dove cliccare per scegliere una macchina."""
        r = self.regista
        d = r.didascalia() if r is not None else None
        per_id = {a[0]: a for a in auto}
        prima = surf.get_clip()
        surf.set_clip(vista.clip(prima) if prima else vista)
        self._pallini = []
        for chi in pos:
            p = self.v3d.proietta(*pos[chi])
            if p is not None:
                x, y = int(vista.x + p[0]), int(vista.y + p[1])
                if vista.collidepoint(x, y):
                    self._pallini.append((x, y, chi))
        if d is not None:
            # la sigla sopra alle macchine inquadrate, se non ci si e' seduti dentro
            if d["nome"] != regia.TCam.nome:
                for chi in [d["chi"]] + d["altri"]:
                    a = per_id.get(chi)
                    if a is None or chi not in pos:
                        continue
                    p = self.v3d.proietta(pos[chi][0], pos[chi][1], 1.2)
                    if p is None:
                        continue
                    x, y = int(vista.x + p[0]), int(vista.y + p[1])
                    larga = T.width(a[4], 12, bold=True) + 14
                    y -= 8
                    T.panel(surf, (x - larga // 2, y - 18, larga, 18), (12, 16, 24),
                            radius=4, rilievo=False)
                    pygame.draw.rect(surf, a[2], (x - larga // 2, y - 18, 4, 18),
                                     border_top_left_radius=4, border_bottom_left_radius=4)
                    T.text(surf, a[4], (x + 2, y - 17), 12, T.WHITE, bold=True, align="center")
            self._terzo_basso(surf, vista, d, per_id)
            self._etichetta_camera(surf, vista, d)
        if self._stacco < 0.5:
            self._stinger(surf, vista, self._stacco / 0.5)
        surf.set_clip(prima)
        T.text(surf, "clic su una macchina o sul tabellone: la regia la segue",
               (vista.right - 12, vista.bottom - 22), 11, (225, 230, 240), align="right")

    def _terzo_basso(self, surf, vista, d, per_id) -> None:
        """In basso a sinistra: posizione, colore della squadra, sigla. Se
        c'e' una battaglia, anche chi c'e' davanti."""
        a = per_id.get(d["chi"])
        if a is None:
            return
        info = self.regista.info.get(d["chi"], {})
        x, y = vista.x + 14, vista.bottom - 70
        riga = [(info.get("pos"), a)]
        for c in d["altri"]:
            b = per_id.get(c)
            if b is not None:
                riga.append((self.regista.info.get(c, {}).get("pos"), b))
        if d["replay"] and d["sorpasso"]:
            titolo = "IL SORPASSO"
        elif len(riga) > 1:
            posti = sorted(p for p, _ in riga if p)
            titolo = f"BATTAGLIA PER P{posti[0]}" if posti else "BATTAGLIA"
        else:
            titolo = "IN PISTA"
        T.text(surf, titolo, (x + 2, y - 16), 11, (235, 240, 250), bold=True)
        for posto, b in riga:
            larga = 44 + T.width(b[4], 16, bold=True) + 18
            T.panel(surf, (x, y, larga, 30), (10, 14, 22), radius=5, rilievo=False)
            T.panel(surf, (x, y, 30, 30), T.WHITE if b[3] else (232, 236, 244), radius=5,
                    rilievo=False)
            T.text(surf, str(posto or "-"), (x + 15, y + 6), 15, (10, 14, 22), bold=True,
                   align="center")
            pygame.draw.rect(surf, b[2], (x + 32, y + 5, 4, 20))
            T.text(surf, b[4], (x + 44, y + 5), 16, T.squadra_viva() if b[3] else T.WHITE,
                   bold=True)
            x += larga + 8

    def _etichetta_camera(self, surf, vista, d) -> None:
        """In alto a destra: DIRETTA o REPLAY, e da che camera."""
        x = vista.right - 12
        y = vista.y + 12
        if d["replay"]:
            T.panel(surf, (x - 96, y, 96, 26), (196, 30, 40), radius=5, rilievo=False)
            T.text(surf, "REPLAY", (x - 48, y + 5), 14, T.WHITE, bold=True, align="center")
            # quanto manca, sotto
            pygame.draw.rect(surf, (40, 44, 56), (x - 96, y + 30, 96, 3))
            pygame.draw.rect(surf, (255, 90, 90), (x - 96, y + 30, int(96 * d["avanzato"]), 3))
            T.text(surf, d["nome"], (x, y + 38), 11, (235, 240, 250), bold=True, align="right")
            return
        larga = T.width(d["nome"], 11, bold=True) + 44
        T.panel(surf, (x - larga, y, larga, 22), (10, 14, 22), radius=5, rilievo=False)
        acceso = (pygame.time.get_ticks() // 600) % 2 == 0
        pygame.draw.circle(surf, (235, 50, 60) if acceso else (120, 30, 36),
                           (x - larga + 14, y + 11), 4)
        T.text(surf, d["nome"], (x - larga + 26, y + 4), 11, T.WHITE, bold=True)

    def _stinger(self, surf, vista, t: float) -> None:
        """Il lampo che apre e chiude il replay: una fascia che attraversa il quadro."""
        larga = int(vista.w * 0.45)
        x = int(vista.x - larga + (vista.w + larga * 2) * t)
        fascia = pygame.Surface((larga, vista.h), pygame.SRCALPHA)
        fascia.fill((*T.ACCENT, 200))
        pygame.draw.rect(fascia, (255, 255, 255, 230), (larga - 10, 0, 10, vista.h))
        surf.blit(fascia, (x, vista.y))
        T.text(surf, "REPLAY" if self._replay_prima else "DIRETTA",
               (x + larga // 2, vista.centery - 14), 26, T.WHITE, bold=True, align="center")

    def _mano_tv(self, ev) -> bool:
        """Con la regia il mouse non gira la camera: sceglie chi guardare."""
        if ev.type != pygame.MOUSEBUTTONDOWN or ev.button != 1:
            return False
        if any(w.rect.collidepoint(ev.pos) for w in self.widgets):
            return False
        if self._mappa.collidepoint(ev.pos):
            vicini = [(math.hypot(x - ev.pos[0], y - ev.pos[1]), chi)
                      for x, y, chi in self._pallini]
            if vicini:
                d, chi = min(vicini, key=lambda v: v[0])
                if d <= 40 and chi != self.segui_id:
                    self.segui(chi)
                    return True
            return True
        if self._righe_torre:
            torre, y0, rh, ids = self._righe_torre
            if torre.collidepoint(ev.pos) and ev.pos[1] >= y0:
                i = int((ev.pos[1] - y0) // rh)
                if 0 <= i < len(ids):
                    self.segui(ids[i])
                    return True
        return False

    # ------------------------------------------------------------- il suono
    def _semaforo_acceso(self) -> bool:
        sem = getattr(self, "semaforo", None)
        return sem is not None and sem.ferma

    def _suono_pista(self) -> None:
        """Quello che si sente in pista, chiesto a ogni fotogramma.

        In 3D il motore della macchina inquadrata - dal bordo pista con
        l'effetto Doppler e il volume che sale man mano che arriva, dall'onboard
        a tutto volume col vento, dall'elicottero lontano - e se c'e' una
        battaglia anche quello di chi le sta davanti. Sotto, la folla, il rombo
        del gruppo che gira, la pioggia quando piove. In 2D restano i fondi.
        """
        if not audio.attivo():
            return
        meteo = self._meteo_3d()
        bagnato = float(getattr(meteo, "wet", 0.0) or 0.0)
        ultimo = self._audio_3d
        in_3d = (ultimo is not None and self.v3d is not None
                 and pygame.time.get_ticks() - ultimo[0] < 300)
        if bagnato > 0.05:
            audio.ambiente("pioggia", min(1.0, bagnato) * (0.7 if in_3d else 0.45))
        if not in_3d:
            audio.ambiente("folla", 0.12)
            audio.ambiente("campo", 0.25)
            return
        _, pos, tv, dt_sim, larga = ultimo
        fermo = dt_sim <= 0.0 and not self._semaforo_acceso()
        elettrico = self._elettrico_3d()
        geo = self.v3d.geo
        soggetti = []           # (chi, volume, pan, doppler)
        folla, campo = 0.18, 0.15
        replay = None
        cam = None
        if tv and self.regista is not None:
            cam = self.regista.camera
            replay = self.regista.replay
        if cam is not None:
            chi_ = [c for c in [cam.chi] + cam.altri[:1] if c in pos]
            for k, chi in enumerate(chi_):
                if isinstance(cam, regia.Bordo):
                    (x, y, z), fw = geo.sul_giro(*pos[chi])
                    ox, oy, oz = cam.occhio
                    dx, dy, dz = ox - x, oy - y, oz - z
                    d = max(1.0, math.sqrt(dx * dx + dy * dy + dz * dz))
                    v = self._velocita_suono(chi, replay)[0]
                    verso = (fw[0] * dx + fw[1] * dy + fw[2] * dz) / d * v
                    doppler = 343.0 / max(150.0, 343.0 - verso)
                    vol = min(1.0, (24.0 / d) ** 0.8)
                    soggetti.append((chi, vol, self._pan_di(pos[chi], larga), doppler))
                    folla = 0.32
                elif isinstance(cam, regia.TCam):
                    soggetti.append((chi, 1.0 if k == 0 else 0.5, 0.0, 1.0))
                    v = self._velocita_suono(chi, replay)[0]
                    audio.ambiente("vento", 0.55 * min(1.0, v / 80.0))
                    folla = 0.1
                elif isinstance(cam, regia.Segue):
                    soggetti.append((chi, 0.85 if k == 0 else 0.45, 0.0, 1.0))
                else:
                    soggetti.append((chi, 0.32 if k == 0 else 0.22,
                                     self._pan_di(pos[chi], larga), 1.0))
                    campo = 0.3
        elif not tv and self.segui_id in pos:
            zoom = self.v3d.elicottero.zoom_auto
            soggetti.append((self.segui_id, max(0.15, min(0.9, 0.22 / max(0.03, zoom))),
                             self._pan_di(pos[self.segui_id], larga), 1.0))
        else:
            campo = 0.45
            folla = 0.22
        audio.ambiente("folla", folla * (0.7 if replay else 1.0))
        audio.ambiente("campo", campo)
        if fermo:
            return
        veloce = getattr(self, "regista", None) is not None and self.regista.ritmo > 8.0
        for k, (chi, vol, pan, doppler) in enumerate(soggetti[:2]):
            v, a = self._velocita_suono(chi, replay)
            if self._semaforo_acceso():
                # sulla griglia col rosso: fermi, col motore su di giri
                v, a = 0.0, 5.0
            audio.motore(k, chi, v, a, vol * (0.5 if veloce else 1.0) * (0.8 if replay else 1.0),
                         pan, doppler, elettrico)

    def _velocita_suono(self, chi, replay) -> tuple:
        """(velocita' m/s, accelerazione m/s2) di una macchina: dal vivo, o dal
        registro della regia se si sta guardando un replay."""
        if replay is None:
            return self._continua.velocita(chi), self._accel.get(chi, 0.0)
        reg, t = self.regista.registro, replay["t"]
        giro = regia.lunghezza(self.v3d.geo)
        punti = [reg.a(t - k * 0.1).get(chi) for k in range(3)]
        if any(p is None for p in punti):
            return self._continua.velocita(chi), 0.0
        v1 = regia._avanti(punti[1][0], punti[0][0], giro) / 0.1
        v0 = regia._avanti(punti[2][0], punti[1][0], giro) / 0.1
        return max(0.0, v1), (v1 - v0) / 0.1

    def _pan_di(self, p, larga: int) -> float:
        """Da che parte dello schermo sta: il suono viene da li'."""
        q = self.v3d.proietta(*p) if self.v3d is not None else None
        if q is None or larga <= 0:
            return 0.0
        return max(-0.8, min(0.8, (q[0] / larga - 0.5) * 1.6))

    # ---------------------------------------------------- box e safety car
    def _lato_box_3d(self, f: float):
        """Di quanti metri spostarsi di lato per stare nella corsia box."""
        geo = self.v3d.geo
        box = getattr(geo, "box_P", None) or []
        if len(box) < 2:
            return None
        (x, _y, z), _fw = geo.sul_giro(f, 0.0)
        q = trackdraw.piu_vicino([(b[0], b[2]) for b in box], x, z)
        if q is None:
            return None
        r = geo.R[int((f % 1.0) * geo.n) % geo.n]
        return (q[0] - x) * r[0] + (q[1] - z) * r[2]

    def _forzati_2d(self, quote: dict, vista, mezzo: float) -> dict:
        """Chi si e' spostato di lato sulla mappa 2D: le manovre, e chi e' ai
        box, che scorre nella corsia."""
        forzati = self._manovre()
        box = [e.driver_id for e in self._entranti_3d()
               if e.status == "pitting" and e.driver_id in quote]
        if box and mezzo > 0 and self.pts:
            chiave = tuple(vista)
            if getattr(self, "_pit_px", (None, None))[0] != chiave:
                self._pit_px = (chiave, trackdraw.fit_pit(self.track, vista.inflate(-30, -30)))
            for chi in box:
                lato = trackdraw.lato_box(self.pts, self._pit_px[1], quote[chi])
                if lato is not None:
                    forzati[chi] = lato / mezzo
        return forzati

    def _safety_car(self):
        """Dove sta la safety car sul giro (frazione in distanza), o None."""
        sim = getattr(self, "sim", None)
        dove = getattr(sim, "safety_car_dist", None)
        d = dove() if dove else None
        if d is None:
            return None
        giro = max(1.0, sim.track_len)
        return self.track.pos_at((d % giro) / giro)

    def _etichetta_sc(self, surf, x: int, y: int) -> None:
        larga = T.width("SAFETY CAR", 11, bold=True) + 12
        T.panel(surf, (x - larga // 2, y - 20, larga, 17), (250, 176, 20), radius=4,
                rilievo=False)
        T.text(surf, "SAFETY CAR", (x, y - 19), 11, (20, 20, 24), bold=True, align="center")

    def _safety_car_2d(self, surf, mezzo: float) -> None:
        """La safety car sulla mappa 2D: un pallino arancione davanti al gruppo."""
        f = self._safety_car()
        if f is None or not self.pts:
            return
        x, y = trackdraw.car_pos(self.pts, f, self.track.linea_a(f) * mezzo)
        x, y = int(x), int(y)
        acceso = (pygame.time.get_ticks() // 350) % 2 == 0
        pygame.draw.circle(surf, (8, 10, 14), (x + 1, y + 2), 7)
        pygame.draw.circle(surf, (250, 176, 20) if acceso else (200, 120, 10), (x, y), 6)
        pygame.draw.circle(surf, (20, 20, 24), (x, y), 6, 1)
        self._etichetta_sc(surf, x, y - 4)

    # ---------------------------------------------------------- le schede
    def _scheda_3d(self, driver_id):
        """Cosa scrivere sulla scheda di una nostra macchina, sul plastico:
        dict con pos, nome, dato (e colore), distacco. None: niente scheda."""
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        if e is None:
            return None
        return {"pos": getattr(e, "position", ""), "nome": e.name.split()[-1].upper(),
                "dato": "", "colore": T.WHITE, "distacco": ""}

    def _scheda(self, surf, vista, chi, f: float, laterale: float, k: int) -> None:
        """La scheda appesa sopra una nostra macchina, col filo che la lega."""
        info = self._scheda_3d(chi)
        if info is None:
            return
        scala = self.v3d.scala_auto
        base = self.v3d.proietta(f, laterale, 1.0 * scala)
        if base is None:
            return
        bx, by = int(vista.x + base[0]), int(vista.y + base[1])
        # le due schede non si coprono: la seconda sta piu' in alto
        alto = 46 + k * 40
        nome = info["nome"]
        pos = str(info["pos"])
        larga = (30 + T.width(nome, 13, bold=True) + 12 + T.width(info["dato"], 12, bold=True)
                 + 12 + T.width(info["distacco"], 12, mono=True) + 12)
        x0 = max(vista.x + 4, min(vista.right - larga - 4, bx - larga // 2))
        y0 = max(vista.y + 40, by - alto)
        pygame.draw.line(surf, (240, 244, 250), (bx, by), (bx, y0 + 26), 2)
        pygame.draw.circle(surf, (240, 244, 250), (bx, by), 3)
        T.panel(surf, (x0, y0, larga, 26), (14, 18, 26), radius=5, rilievo=False)
        colore = next((a for a in [self._colore_di(chi)] if a), T.squadra_viva())
        T.panel(surf, (x0, y0, 26, 26), colore, radius=5, rilievo=False)
        T.text(surf, pos, (x0 + 13, y0 + 5), 13, T.WHITE, bold=True, align="center")
        x = x0 + 32
        T.text(surf, nome, (x, y0 + 5), 13, T.WHITE, bold=True)
        x += T.width(nome, 13, bold=True) + 12
        if info["dato"]:
            T.text(surf, info["dato"], (x, y0 + 6), 12, info["colore"], bold=True)
            x += T.width(info["dato"], 12, bold=True) + 12
        if info["distacco"]:
            T.text(surf, info["distacco"], (x, y0 + 6), 12, (200, 210, 225), mono=True)

    def _colore_di(self, driver_id):
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        return tuple(e.colour[:3]) if e is not None and getattr(e, "colour", None) else None
