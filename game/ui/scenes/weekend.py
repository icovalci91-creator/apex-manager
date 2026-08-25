"""Weekend di gara: prove libere, qualifica, sprint e gara con vista 2D dal vivo."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import season as SEASON
from ...core import tyres as TY
from ...sim import session as S
from ...sim.weekend import Weather
from ...sim import pace as PACE
from .. import theme as T
from .. import trackdraw
from ..app import Scene
from ..widgets import Button

SPEEDS = [0, 1, 4, 12, 40]
SPEED_LABELS = ["II", "x1", "x4", "x12", "x40"]

STAGE_LAB = {"prove": "PROVE LIBERE", "sq": "SPRINT QUALIFYING", "sprint": "SPRINT",
             "assetto": "ASSETTO E VETTURA", "qualifica": "QUALIFICA", "gara": "GARA",
             "fine": "RISULTATI"}


class WeekendScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        gs = app.gs
        self.gs = gs
        self.track = gs.next_track
        self.ws = S.WeekendState(track=self.track, weather=Weather.generate(self.track, gs.rng))
        # il weekend comincia prima di scendere in pista: si scelgono le gomme.
        # Con la sprint in programma il fine settimana ha due qualifiche: la
        # Sprint Qualifying schiera la sprint, poi si rimette mano alla macchina
        # e la qualifica vera schiera il gran premio.
        self.stage = "gomme"   # gomme|prove|sq|sprint|assetto|qualifica|gara|fine
        self.tyre_pick = TY.suggested(self.track)
        self.sim = None
        self.speed_idx = 2
        self.result_rows = []
        self.sprint_rows = []
        self.sprint_notes = []
        self.pts = None
        self.applied = False
        self.sprint_pending = self.track.sprint
        # la scena resta viva anche se si esce a cambiare l'assetto: il weekend
        # non si ricomincia da capo solo per essere passati dalla pagina Vettura
        app.weekend = self
        # la preparazione delle squadre del computer e' gia' stata fatta quando
        # il calendario e' avanzato: qui si corre e basta
        self.build()

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        self.pts = None
        if self.stage == "gomme":
            self._build_tyres(w, h)
        elif self.sim is not None:
            self._build_race(w, h)
        else:
            self._build_prep(w, h)

    def _build_prep(self, w: int, h: int) -> None:
        bw, bh = 260, 44
        x = w - bw - 40
        y = h - 140
        if self.stage == "prove":
            tot = S.practice_sessions(self.track)
            self.widgets.append(Button((x, y - 56, bw, bh),
                                       f"Prove libere {min(tot, self.ws.practice_done + 1)}/{tot}",
                                       self.do_practice, "normal"))
            avanti = "Vai alla Sprint Qualifying" if self.sprint_pending else "Vai alla qualifica"
            self.widgets.append(Button((x, y, bw, bh), avanti, self.to_quali, "primary"))
            self.widgets.append(Button((x - bw - 16, y, bw, bh), "Assetto e vettura",
                                       self.open_setup, "ghost"))
            self._build_distance(x - bw - 16, y - 56, bw)
        elif self.stage == "sq":
            self.widgets.append(Button((x, y, bw, bh), "Disputa la Sprint Qualifying",
                                       self.do_sprint_quali, "primary"))
        elif self.stage == "assetto":
            # fra sprint e qualifica il parco chiuso si riapre: e' l'ultima
            # occasione per correggere quello che la sprint ha fatto vedere
            self.widgets.append(Button((x, y, bw, bh), "Vai alla qualifica",
                                       self.to_quali, "primary"))
            self.widgets.append(Button((x - bw - 16, y, bw, bh), "Assetto e vettura",
                                       self.open_setup, "ghost"))
        elif self.stage == "qualifica":
            self.widgets.append(Button((x, y, bw, bh), "Disputa la qualifica",
                                       self.do_quali, "primary"))
        elif self.stage in ("sprint", "gara"):
            lab = "Vai alla Sprint" if self.stage == "sprint" else "Vai in griglia"
            self.widgets.append(Button((x, y, bw, bh), lab, self.start_race, "primary"))
        elif self.stage == "fine":
            self.widgets.append(Button((x, y, bw, bh), "Torna al quartier generale",
                                       self.finish, "primary"))
        self.widgets.append(Button((40, h - 96, 180, 40), "Abbandona", self.app.pop, "ghost"))

    # ------------------------------------------------------------- gomme
    def _build_tyres(self, w: int, h: int) -> None:
        left = pygame.Rect(28, 92, w * 0.42, h - 190)
        self.tyre_buttons = []
        if not self.ws.tyres_published:
            y = left.y + 120
            for m in TY.MESCOLE:
                # ancorati al bordo destro del pannello: su finestre strette la
                # colonna "quanti set in tutto" arrivava a coprirli
                meno = Button((left.right - 250, y, 34, 30), "-")
                meno.on_click = (lambda k=m: self._bump(k, -1))
                piu = Button((left.right - 190, y, 34, 30), "+")
                piu.on_click = (lambda k=m: self._bump(k, +1))
                self.widgets += [meno, piu]
                y += 40
            self.widgets.append(Button((left.x + 20, left.bottom - 118, 240, 38),
                                       "Consiglio degli ingegneri", self.suggest_tyres,
                                       "ghost"))
            b = Button((left.x + 20, left.bottom - 68, 300, 44),
                       "Consegna la scelta", self.confirm_tyres, "primary")
            b.enabled = TY.is_valid(self.track, self.tyre_pick)[0]
            self.widgets.append(b)
        else:
            self.widgets.append(Button((w - 300, h - 140, 260, 44),
                                       "Vai alle prove libere", self.to_practice,
                                       "primary"))
        self.widgets.append(Button((40, h - 96, 180, 40), "Abbandona", self.app.pop, "ghost"))

    def _bump(self, mescola: str, verso: int) -> None:
        n = self.tyre_pick.get(mescola, 0) + verso
        liberi = TY.free_sets(self.track)
        usati = sum(self.tyre_pick.values()) - self.tyre_pick.get(mescola, 0)
        self.tyre_pick[mescola] = max(0, min(liberi - usati, n))
        self.build()

    def suggest_tyres(self) -> None:
        self.tyre_pick = TY.suggested(self.track)
        self.build()

    def confirm_tyres(self) -> None:
        ok, why = TY.is_valid(self.track, self.tyre_pick)
        if not ok:
            self.app.toast(why)
            return
        TY.allocate(self.gs, self.ws, self.tyre_pick)
        self.app.toast("Scelte consegnate: adesso sono pubbliche per tutti.")
        self.build()

    def to_practice(self) -> None:
        self.stage = "prove"
        self.build()

    DISTANCES = [0.25, 0.50, 0.75, 1.00]

    def _build_distance(self, x: int, y: int, bw: int) -> None:
        """Scelta della durata della gara, in percentuale su quella reale."""
        self.dist_label_at = (x, y - 22)
        n = len(self.DISTANCES)
        gap = 6
        cw = (bw - gap * (n - 1)) / n
        for i, f in enumerate(self.DISTANCES):
            b = Button((x + i * (cw + gap), y, cw, 34), f"{f * 100:.0f}%", style="tab")
            b.on_click = (lambda v=f: self.set_distance(v))
            b.active = abs(self.gs.race_distance - f) < 0.01
            self.widgets.append(b)

    def set_distance(self, value: float) -> None:
        self.gs.race_distance = value
        laps = S.race_laps(self.gs, self.track, "gp")
        self.app.toast(f"Gare al {value * 100:.0f}%: {self.track.gp} su {laps} giri")
        self.build()

    def _build_race(self, w: int, h: int) -> None:
        bx = 40
        by = h - 74
        for i, lab in enumerate(SPEED_LABELS):
            b = Button((bx + i * 62, by, 56, 34), lab, style="tab")
            b.on_click = (lambda i=i: self.set_speed(i))
            b.active = (i == self.speed_idx)
            self.widgets.append(b)
        self.widgets.append(Button((bx + 5 * 62 + 16, by, 190, 34), "Simula fino alla fine",
                                   self.skip_to_end, "ghost"))
        px = bx + 5 * 62 + 226
        for i, did in enumerate(self.gs.player.drivers):
            d = self.gs.drivers.get(did)
            if not d:
                continue
            self.widgets.append(Button((px, by, 90, 34), f"BOX {d.code}",
                                       (lambda k=did: self.force_pit(k)), "normal"))
            px += 96
            for lab, val in (("-", 0.90), ("=", 1.0), ("+", 1.10)):
                b = Button((px, by, 32, 34), lab, style="tab")
                b.on_click = (lambda k=did, v=val, bb=None: self.set_push(k, v))
                b.active = (val == 1.0)
                self.widgets.append(b)
                px += 34
            px += 14

    def on_resize(self) -> None:
        self.build()

    def enter(self) -> None:
        # si puo' rientrare dopo essere passati dalla pagina Vettura: la
        # finestra potrebbe essere cambiata, e i pulsanti vanno rifatti
        self.build()

    # ------------------------------------------------------------------ azioni
    def open_setup(self) -> None:
        """Torna alla pagina Vettura senza chiudere il weekend.

        La scena resta appesa all'app: rientrando dal pulsante "Vai al weekend"
        si riprende da dove si era, con le gomme gia' consegnate e le prove
        gia' fatte.
        """
        from .shell import GameShell
        for s in self.app.scenes:
            if isinstance(s, GameShell):
                s.go("car")
                self.app.pop()
                return

    def do_practice(self) -> None:
        if self.ws.practice_done >= S.practice_sessions(self.track):
            self.app.toast("Prove libere terminate: in un weekend sprint ce n'e' una sola."
                           if self.track.sprint else "Prove libere terminate.")
            return
        S.run_practice(self.gs, self.ws)
        self.build()

    def to_quali(self) -> None:
        # dalle prove libere di un weekend sprint non si va in qualifica: prima
        # c'e' la Sprint Qualifying, e la qualifica arriva dopo la sprint
        self.stage = "sq" if (self.sprint_pending and self.stage == "prove") else "qualifica"
        self.build()

    def do_sprint_quali(self) -> None:
        S.run_qualifying(self.gs, self.ws, kind="sprint")
        self.stage = "sprint"
        self.build()

    def do_quali(self) -> None:
        S.run_qualifying(self.gs, self.ws)
        self.stage = "gara"
        self.build()

    def start_race(self) -> None:
        kind = "sprint" if self.stage == "sprint" else "gp"
        self.sim = S.make_race(self.gs, self.ws, kind=kind)
        self.applied = False
        self.speed_idx = 2
        self.build()

    def set_speed(self, i: int) -> None:
        self.speed_idx = i
        self.build()

    def skip_to_end(self) -> None:
        if self.sim:
            self.sim.fast_forward()
            self._on_race_end()

    def force_pit(self, driver_id: str) -> None:
        if not self.sim:
            return
        for e in self.sim.entrants:
            if e.driver_id == driver_id and e.status == "running":
                e.plan.insert(0, (e.lap, self.sim._pick_compound(e)))
                self.app.toast(f"{e.name}: box al prossimo passaggio.")

    def set_push(self, driver_id: str, value: float) -> None:
        if not self.sim:
            return
        for e in self.sim.entrants:
            if e.driver_id == driver_id:
                e.push_mode = value
        self.build()

    def finish(self) -> None:
        self.app.weekend = None
        self.app.pop()
        from .shell import GameShell
        if isinstance(self.app.scene, GameShell):
            self.app.scene.enter()
        if self.gs.pending_votes and self.gs.phase != "offseason":
            from .commission import CommissionScene
            self.app.push(CommissionScene(self.app))

    # ------------------------------------------------------------------- loop
    def update(self, dt: float) -> None:
        if self.sim and not self.sim.finished:
            mult = SPEEDS[self.speed_idx]
            if mult:
                step = dt * mult
                n = max(1, int(step / 0.6) + 1)
                for _ in range(n):
                    self.sim.update(step / n)
            if self.sim.finished:
                self._on_race_end()

    def _on_race_end(self) -> None:
        if self.applied or not self.sim:
            return
        self.applied = True
        kind = self.sim.kind
        SEASON.apply_result(self.gs, self.ws, self.sim, kind=kind)
        win = self.sim.result_order()[0]
        dove = f"Sprint di {self.track.gp}" if kind == "sprint" else self.track.gp
        self.gs.push(f"{dove}: vince {win.name} ({self.gs.teams[win.team_id].short}).", "gara")
        self.result_rows = self.sim.result_order()
        if kind == "sprint":
            self.sprint_pending = False
            self.ws.sprint_done = True
            self.sprint_rows = self.result_rows
            # la gara ha detto qualcosa sulla macchina: si arriva alla qualifica
            # sapendone di piu', e c'e' ancora tempo per cambiare
            self.sprint_notes = S.learn_from_sprint(self.gs, self.ws)
            self.sim = None
            self.stage = "assetto"
            self.build()
        else:
            SEASON.after_race(self.gs)
            self.stage = "fine"
            self.sim = None
            self.build()

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        if self.stage == "gomme":
            self._draw_tyres(surf)
            super().draw(surf)
            return
        if self.sim:
            self._draw_race(surf)
        else:
            self._draw_prep(surf)
        super().draw(surf)

    # ------------------------------------------------------------ preparazione
    def _draw_tyres(self, surf) -> None:
        w, h = surf.get_size()
        gs, tr, ws = self.gs, self.track, self.ws
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 72))
        T.text(surf, tr.gp.upper(), (28, 12), 24, T.TEXT, bold=True)
        T.text(surf, f"{tr.name} - mescole portate dal fornitore: "
                     f"{TY.nomination_label(tr)}", (28, 42), 14, T.DIM)
        T.text(surf, "SCELTA DELLE GOMME", (w - 28, 20), 22, T.ACCENT, bold=True,
               align="right")

        left = pygame.Rect(28, 92, w * 0.42, h - 190)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LA NOSTRA SCELTA", (left.x + 20, left.y + 16), 12, T.DIM_2, bold=True)
        liberi = TY.free_sets(tr)
        messi = sum(self.tyre_pick.values())
        nom = TY.nomination(tr)
        T.text(surf, f"{liberi} set liberi da assegnare, piu' i {sum(TY.OBBLIGATORI.values())} "
                     f"che decide il regolamento", (left.x + 20, left.y + 44), 13, T.DIM,
               maxw=left.w - 40)
        T.text(surf, f"assegnati {messi} su {liberi}", (left.right - 20, left.y + 44), 13,
               T.OK if messi == liberi else T.WARN, bold=True, align="right")

        y = left.y + 120
        for m in TY.MESCOLE:
            n = self.tyre_pick.get(m, 0)
            tot = n + TY.OBBLIGATORI[m]
            col = {"soft": (225, 6, 0), "medium": (255, 214, 0),
                   "hard": (235, 235, 235)}[m]
            pygame.draw.circle(surf, col, (left.x + 34, y + 15), 11, 4)
            T.text(surf, TY.LABEL[m], (left.x + 56, y + 6), 16, T.TEXT, bold=True)
            T.text(surf, TY.GAMMA[nom[m] - 1], (left.x + 180, y + 8), 14, T.DIM,
                   maxw=left.w - 440)
            if not ws.tyres_published:
                T.text(surf, f"{n}", (left.right - 200, y + 4), 18, T.TEXT, bold=True,
                       align="right")
            T.text(surf, f"{tot} set in tutto", (left.right - 20, y + 8), 13, T.DIM,
                   align="right")
            y += 40

        if not ws.tyres_published:
            T.text(surf, "Chi carica morbide fa un giro secco migliore e finisce le gomme",
                   (left.x + 20, left.bottom - 176), 12, T.DIM_2, maxw=left.w - 40)
            T.text(surf, "in gara; chi carica dure vive peggio il venerdi' e meglio la",
                   (left.x + 20, left.bottom - 160), 12, T.DIM_2, maxw=left.w - 40)
            T.text(surf, "domenica. Consegnata la scelta non si torna indietro.",
                   (left.x + 20, left.bottom - 144), 12, T.DIM_2, maxw=left.w - 40)
        else:
            T.text(surf, "Scelta consegnata e pubblicata.", (left.x + 20, left.bottom - 144),
                   13, T.OK, maxw=left.w - 40)

        right = pygame.Rect(w * 0.44 + 28, 92, w * 0.56 - 60, h - 190)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "SCELTE DI TUTTI", (right.x + 20, right.y + 16), 12, T.DIM_2, bold=True)
        if not ws.tyres_published:
            T.text(surf, "Le scelte si consegnano insieme e vengono pubblicate tutte",
                   (right.x + 20, right.y + 60), 14, T.DIM, maxw=right.w - 40)
            T.text(surf, "in una volta: finche' non consegniamo la nostra, cosa hanno",
                   (right.x + 20, right.y + 80), 14, T.DIM, maxw=right.w - 40)
            T.text(surf, "in mano gli altri non lo sa nessuno.",
                   (right.x + 20, right.y + 100), 14, T.DIM, maxw=right.w - 40)
            return
        T.text(surf, "morbide   medie   dure", (right.right - 20, right.y + 16), 11,
               T.DIM_2, align="right")
        yy = right.y + 46
        ordine = sorted(gs.teams.values(), key=lambda t: t.last_position)
        for team in ordine:
            st = TY.full_stock_from(ws.tyre_choice.get(team.id, {}))
            mio = team.is_player
            T.panel(surf, (right.x + 16, yy, right.w - 32, 26),
                    T.PANEL_3 if mio else T.PANEL_2, radius=6)
            pygame.draw.rect(surf, T.hex_rgb(team.colour), (right.x + 20, yy + 5, 3, 16))
            T.text(surf, team.short, (right.x + 32, yy + 5), 14,
                   T.TEXT if mio else T.DIM, bold=mio, maxw=right.w * 0.4)
            x = right.right - 150
            for m, col in (("soft", (225, 6, 0)), ("medium", (255, 214, 0)),
                           ("hard", (235, 235, 235))):
                T.text(surf, f"{st[m]}", (x, yy + 5), 15, col, bold=True, align="right")
                x += 48
            yy += 30

    def _draw_prep(self, surf) -> None:
        w, h = surf.get_size()
        gs, tr, ws = self.gs, self.track, self.ws
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 72))
        T.text(surf, tr.gp.upper(), (28, 12), 24, T.TEXT, bold=True)
        # nelle fasi della sprint la distanza che conta e' quella della sprint
        if self.stage in ("sq", "sprint"):
            dist = f"sprint su {S.race_laps(gs, tr, 'sprint')} giri"
        else:
            laps = S.race_laps(gs, tr, "gp")
            dist = f"{laps} giri" if laps == tr.laps else f"{laps} giri su {tr.laps}"
        # il programma del weekend occupa la destra della barra: la riga delle
        # condizioni si ferma prima invece di finirci sopra
        largo = self._programma(surf, w)
        T.text(surf, f"{tr.name} - {tr.length_km:.3f} km - {dist} - {ws.weather.label}, "
                     f"{ws.weather.air_temp:.0f}C aria, {ws.weather.track_temp:.0f}C "
                     f"asfalto, vento {ws.weather.wind:.0f} km/h",
               (28, 42), 14, T.DIM, maxw=w - 68 - largo)
        # se un componente contingentato e' agli sgoccioli lo si deve sapere
        # prima di scendere in pista, non quando si rompe
        from ...core import penalties as PEN
        allarmi = []
        for d in gs.lineup_of(gs.player_team):
            if d.pu_wear <= PEN.SOGLIA_ROTTURA:
                allarmi.append(f"{d.short}: power unit al {d.pu_wear:.0f}%")
            if d.gearbox_wear <= PEN.SOGLIA_ROTTURA:
                allarmi.append(f"{d.short}: cambio al {d.gearbox_wear:.0f}%")
        if allarmi:
            T.text(surf, "DA SOSTITUIRE:  " + "   ".join(allarmi[:3]),
                   (28, 62), 12, T.BAD, bold=True, maxw=w * 0.6)
        if self.stage == "prove" and getattr(self, "dist_label_at", None):
            T.text(surf, "DURATA DELLA GARA", self.dist_label_at, 11, T.DIM_2, bold=True)
        T.text(surf, STAGE_LAB.get(self.stage, ""), (w - 28, 14), 22, T.ACCENT,
               bold=True, align="right")

        left = pygame.Rect(28, 92, w * 0.42, h - 190)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        trackdraw.draw_track(surf, tr, left.inflate(-24, -32), width=10)
        # cosa dicono i radar per la domenica: e' l'informazione su cui si
        # decide se rischiare o no
        prev = ws.weather.forecast_label()
        acqua = "pioggia" in prev or "acquazzone" in prev
        T.text(surf, f"PREVISIONE: {prev}", (left.x + 20, left.bottom - 84), 11,
               T.WARN if acqua else T.DIM_2, bold=True, maxw=left.w - 40)
        # quanta gomma c'e' sull'asfalto: e' il motivo per cui i tempi calano
        # turno dopo turno anche senza toccare niente
        gomma = (ws.rubber - PACE.PISTA_VERDE) / (PACE.PISTA_GOMMATA - PACE.PISTA_VERDE)
        T.text(surf, f"PISTA GOMMATA AL {gomma*100:.0f}%", (left.right - 20, left.bottom - 62),
               11, T.stat_colour(gomma * 100, 25, 70), bold=True, align="right")
        # quello che resta nel camion: da qui in poi non se ne aggiunge
        if ws.tyre_stock:
            T.text(surf, f"GOMME RIMASTE  ({TY.nomination_label(tr)})",
                   (left.x + 20, left.bottom - 62), 11, T.DIM_2, bold=True)
            x = left.x + 20
            for d in gs.drivers_of(gs.player_team):
                st = TY.stock_of(ws, d.id)
                T.text(surf, d.short, (x, left.bottom - 40), 13, T.DIM, maxw=110)
                xx = x + 96
                for m, col in (("soft", (225, 6, 0)), ("medium", (255, 214, 0)),
                               ("hard", (235, 235, 235))):
                    T.text(surf, f"{st.get(m, 0)}", (xx, left.bottom - 40), 15, col,
                           bold=True)
                    xx += 26
                x += 200

        right = pygame.Rect(w * 0.44 + 28, 92, w * 0.56 - 60, h - 190)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)

        if self.stage == "prove":
            T.text(surf, "LAVORO SULL'ASSETTO", (right.x + 20, right.y + 16), 12, T.DIM_2, bold=True)
            from ...core import setup as SETUP
            pt = gs.player
            q = SETUP.believed_quality(pt)
            err = SETUP.paper_error(pt, tr, pt.sim_sessions)
            T.text(surf, f"Sessioni completate: {ws.practice_done}/{S.practice_sessions(tr)}",
                   (right.x + 20, right.y + 40), 16, T.TEXT)
            T.text(surf, f"{pt.sim_sessions} al simulatore prima di partire",
                   (right.right - 20, right.y + 42), 13, T.DIM_2, align="right")
            T.text(surf, "Vicinanza al riferimento", (right.x + 20, right.y + 70), 14, T.DIM)
            T.bar(surf, (right.x + 220, right.y + 74, 220, 12), q * 100)
            T.text(surf, f"{q*100:.0f}%", (right.x + 456, right.y + 66), 17,
                   T.stat_colour(q * 100, 60, 88), bold=True)
            T.text(surf, f"e il riferimento stesso vale +/-{err:.0f} punti: la pista lo "
                         f"corregge sessione dopo sessione",
                   (right.x + 20, right.y + 92), 12, T.DIM_2, maxw=right.w - 40)
            y = right.y + 122
            for line in (ws.practice_notes or ["Nessuna sessione ancora disputata."]):
                T.text(surf, line, (right.x + 20, y), 14, T.TEXT if not line.startswith("-") else T.DIM,
                       maxw=right.w - 40)
                y += 22
            y += 12
            T.text(surf, "Puoi regolare l'assetto dalla pagina Vettura, oppure delegare al reparto.",
                   (right.x + 20, y), 13, T.DIM_2, maxw=right.w - 40)
        elif self.stage == "sprint" and ws.sprint_quali_done:
            self._draw_grid(surf, right, "GRIGLIA DELLA SPRINT", ws.sprint_grid,
                            ws.sprint_times, ws.sprint_pole, [], ws.sprint_phase,
                            "sprint")
        elif self.stage == "gara" and ws.quali_done:
            self._draw_grid(surf, right, "GRIGLIA DI PARTENZA", ws.grid,
                            ws.quali_times, ws.pole, ws.grid_notes, ws.quali_phase,
                            "gp")
        elif self.stage == "assetto":
            self._draw_results(surf, right, self.sprint_rows, "sprint",
                               "ORDINE D'ARRIVO DELLA SPRINT", self.sprint_notes[:3])
        elif self.stage == "sq":
            T.text(surf, "SPRINT QUALIFYING", (right.x + 20, right.y + 16), 12, T.DIM_2,
                   bold=True)
            alto = T.paragraph(surf, "Si decide la griglia della sprint, e basta quella.",
                               (right.x + 20, right.y + 44), 16, T.TEXT, maxw=right.w - 40)
            yy = self._pannello_turni(surf, right, right.y + 56 + alto, "sprint")
            self._pannello_programma(surf, right, yy + 10)
        elif self.stage == "qualifica":
            T.text(surf, "QUALIFICA DEL GRAN PREMIO", (right.x + 20, right.y + 16), 12,
                   T.DIM_2, bold=True)
            testo = ("Da qui in poi la macchina e' in parco chiuso: quello che c'era da "
                     "cambiare andava cambiato adesso." if ws.sprint_done
                     else "Si decide la griglia del gran premio.")
            alto = T.paragraph(surf, testo, (right.x + 20, right.y + 44), 16, T.TEXT,
                               maxw=right.w - 40)
            yy = self._pannello_turni(surf, right, right.y + 56 + alto, "gp")
            self._pannello_programma(surf, right, yy + 10)
        elif self.stage == "fine":
            self._draw_results(surf, right, self.result_rows, "gp", "ORDINE D'ARRIVO")

    def _pannello_turni(self, surf, right, y: int, quale: str) -> int:
        """I tre turni della qualifica, con durata, tagli e gomme obbligate."""
        turni = S.SEGMENTI["sprint" if quale == "sprint" else "gp"]
        T.text(surf, "COME FUNZIONA", (right.x + 20, y), 11, T.DIM_2, bold=True)
        y += 22
        for i, (nome, minuti, giri, mescola) in enumerate(turni):
            T.text(surf, nome, (right.x + 20, y), 13, T.ACCENT, bold=True, maxw=60)
            fuori = ("si eliminano gli ultimi sei" if i < 2
                     else "si gioca la pole position")
            gomma = (f" - obbligo di {TY.LABEL[mescola].lower()}" if mescola else "")
            T.text(surf, f"{minuti} minuti, {fuori}{gomma}", (right.x + 80, y + 1), 12,
                   T.DIM, maxw=right.w - 110)
            y += 22
        return y

    def _pannello_programma(self, surf, right, y: int) -> None:
        """Il programma del fine settimana spiegato riga per riga."""
        gs = self.gs
        n_punti = len(gs.regulations["sporting"].get("sprint_points",
                                                     [8, 7, 6, 5, 4, 3, 2, 1]))
        tot = S.practice_sessions(self.track)
        prove = "una sola, poi si va in parco chiuso" if tot == 1 else f"{tot} sessioni"
        voci = [("prove", "PROVE LIBERE", prove)]
        if self.track.sprint:
            voci += [
                ("sq", "SPRINT QUALIFYING", "decide la griglia della sprint"),
                ("sprint", "SPRINT", f"cento chilometri senza soste, punti ai primi {n_punti}"),
                ("assetto", "ASSETTO", "il parco chiuso si riapre: ultima occasione "
                                       "per correggere la macchina"),
            ]
        voci += [("qualifica", "QUALIFICA", "decide la griglia del gran premio, "
                                            "e qui si scontano le penalizzazioni"),
                 ("gara", "GRAN PREMIO", "la domenica")]
        chiavi = [k for k, _, _ in voci]
        ora = chiavi.index(self.stage) if self.stage in chiavi else len(chiavi)
        T.text(surf, "PROGRAMMA DEL FINE SETTIMANA", (right.x + 20, y), 11, T.DIM_2,
               bold=True)
        y += 24
        for i, (_k, lab, spiega) in enumerate(voci):
            col = T.ACCENT if i == ora else (T.OK if i < ora else T.TEXT)
            T.text(surf, lab, (right.x + 20, y), 13, col, bold=True, maxw=180)
            T.text(surf, spiega, (right.x + 210, y + 1), 12,
                   T.DIM if i >= ora else T.DIM_2, maxw=right.w - 236)
            y += 26

    def _programma(self, surf, w: int) -> int:
        """Il programma del fine settimana, con la sessione di adesso accesa.

        Ritorna quanto spazio ha preso, cosi' chi scrive a sinistra sa dove
        deve fermarsi.
        """
        tappe = [("prove", "PROVE")]
        if self.track.sprint:
            tappe += [("sq", "SPRINT QUALIFYING"), ("sprint", "SPRINT"),
                      ("assetto", "ASSETTO")]
        tappe += [("qualifica", "QUALIFICA"), ("gara", "GARA")]
        fatte = [k for k, _ in tappe]
        ora = fatte.index(self.stage) if self.stage in fatte else len(fatte)
        pezzi = []
        for i, (_k, lab) in enumerate(tappe):
            col = T.ACCENT if i == ora else (T.DIM_2 if i > ora else T.OK)
            pezzi.append((lab, col))
        largo = sum(T.width(lab, 11, bold=True) for lab, _ in pezzi) + 14 * (len(pezzi) - 1)
        x = w - 28 - largo
        for i, (lab, col) in enumerate(pezzi):
            T.text(surf, lab, (x, 46), 11, col, bold=True)
            x += T.width(lab, 11, bold=True)
            if i < len(pezzi) - 1:
                T.text(surf, "-", (x + 5, 46), 11, T.DIM_2)
                x += 14
        return largo

    @staticmethod
    def _riga_alta(rect, righe: int, riservato: int = 0) -> float:
        """Altezza di riga che fa stare tutte le righe dentro il pannello.

        Una griglia di ventidue macchine non ci sta a passo fisso: meglio
        stringere le righe che finire sotto ai pulsanti. Si tolgono l'altezza
        dell'intestazione e la striscia dei pulsanti in fondo.
        """
        return max(14.0, min(25.0, (rect.h - 98 - riservato) / max(1, righe)))

    def _draw_grid(self, surf, right, titolo: str, griglia: list, tempi: dict,
                   pole: str, note: list, fasi: dict | None = None,
                   quale: str = "gp") -> None:
        gs = self.gs
        T.text(surf, titolo, (right.x + 20, right.y + 16), 12, T.DIM_2, bold=True)
        note = note[:4]
        if note:
            T.text(surf, "PENALIZZAZIONI IN GRIGLIA", (right.right - 20, right.y + 16),
                   11, T.WARN, bold=True, align="right")
        y = right.y + 44
        fasi = fasi or {}
        nomi = [x[0] for x in S.SEGMENTI["sprint" if quale == "sprint" else "gp"]]
        # una riga di stacco dove finisce un turno: si vede a colpo d'occhio chi
        # e' uscito in Q1 e chi si e' giocato la pole
        stacchi = 0
        if fasi:
            stacchi = len({fasi.get(d, 0) for d in griglia}) - 1
        rh = self._riga_alta(right, len(griglia), 20 * len(note) + 18 * stacchi)
        dim = 14 if rh >= 20 else 13
        p0 = tempi.get(pole, 0)
        prima = None
        for i, did in enumerate(griglia, 1):
            fase = fasi.get(did)
            if fase is not None and prima is not None and fase != prima:
                eti = f"eliminati in {nomi[fase]}"
                largo = T.width(eti, 10, bold=True)
                pygame.draw.line(surf, T.LINE, (right.x + 20, int(y) + 8),
                                 (right.right - 32 - largo, int(y) + 8))
                T.text(surf, eti, (right.right - 20, int(y) + 2), 10, T.DIM_2,
                       bold=True, align="right")
                y += 18
            prima = fase
            d = gs.drivers[did]
            t = gs.teams[d.team]
            hl = (t.id == gs.player_team)
            if hl:
                T.panel(surf, (right.x + 12, int(y) - 2, right.w - 24, int(rh)),
                        T.PANEL_3, radius=5)
            T.text(surf, f"{i}", (right.x + 40, int(y)), dim, T.DIM, align="right")
            pygame.draw.rect(surf, T.hex_rgb(t.colour),
                             (right.x + 50, int(y) + 2, 3, max(10, int(rh) - 6)))
            T.text(surf, d.name, (right.x + 62, int(y)), dim, T.TEXT, maxw=170)
            T.text(surf, t.short, (right.x + 246, int(y) + 1), 12, T.DIM, maxw=110)
            tt = tempi.get(did, 0)
            T.text(surf, T.fmt_time(tt), (right.x + 430, int(y)), 13, T.TEXT, mono=True)
            if i > 1:
                T.text(surf, f"+{tt - p0:.3f}", (right.right - 20, int(y)), 13, T.DIM,
                       mono=True, align="right")
            y += rh
        for nota in note:
            T.text(surf, "- " + nota, (right.x + 20, int(y) + 6), 12, T.WARN,
                   maxw=right.w - 40)
            y += 18

    def _draw_results(self, surf, rect, rows: list, kind: str = "gp",
                      titolo: str = "ORDINE D'ARRIVO", note: list | None = None) -> None:
        """La classifica di una gara, sprint o gran premio che sia."""
        gs = self.gs
        T.text(surf, titolo, (rect.x + 20, rect.y + 16), 12, T.DIM_2, bold=True)
        if kind == "sprint":
            T.text(surf, "il parco chiuso si riapre fino alla qualifica",
                   (rect.right - 20, rect.y + 16), 11, T.OK, bold=True, align="right")
        note = note or []
        alte = (18 * len(note) + 12) if note else 0
        y = rect.y + 44
        rh = self._riga_alta(rect, len(rows), alte)
        dim = 14 if rh >= 20 else 13
        lead = rows[0].finished_time if rows and rows[0].status == "finished" else 0
        for i, e in enumerate(rows, 1):
            d = gs.drivers.get(e.driver_id)
            t = gs.teams[e.team_id]
            hl = (t.id == gs.player_team)
            if hl:
                T.panel(surf, (rect.x + 12, int(y) - 2, rect.w - 24, int(rh)),
                        T.PANEL_3, radius=5)
            T.text(surf, f"{i}", (rect.x + 40, int(y)), dim, T.DIM, align="right")
            pygame.draw.rect(surf, T.hex_rgb(t.colour),
                             (rect.x + 50, int(y) + 2, 3, max(10, int(rh) - 6)))
            T.text(surf, d.name if d else e.name, (rect.x + 62, int(y)), dim, T.TEXT, maxw=170)
            T.text(surf, t.short, (rect.x + 246, int(y) + 1), 12, T.DIM, maxw=100)
            if e.status == "finished":
                txt = T.fmt_race(e.finished_time) if i == 1 else f"+{e.finished_time - lead:.3f}"
                T.text(surf, txt, (rect.x + 420, int(y)), 13, T.TEXT, mono=True)
            else:
                T.text(surf, f"RIT - {e.dnf_reason}", (rect.x + 420, int(y)), 12, T.BAD, maxw=170)
            pts = SEASON.points_for(gs, i, kind) if e.status == "finished" else 0
            if pts:
                T.text(surf, f"{pts:.0f}", (rect.right - 20, int(y)), dim, T.GOLD,
                       bold=True, align="right")
            y += rh
        y += 10
        for riga in note:
            T.text(surf, riga, (rect.x + 20, int(y)), 12,
                   T.DIM if riga.startswith("-") else T.TEXT, maxw=rect.w - 40)
            y += 18

    # ------------------------------------------------------------------- gara
    def _draw_race(self, surf) -> None:
        w, h = surf.get_size()
        sim, gs = self.sim, self.gs
        tower_w = 400
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 58))
        lap = min(sim.leader_lap + 1, sim.laps)
        T.text(surf, f"{self.track.name.upper()}  -  GIRO {lap}/{sim.laps}", (24, 10), 20,
               T.TEXT, bold=True)
        sessione = "SPRINT" if sim.kind == "sprint" else "GRAN PREMIO"
        T.text(surf, f"{sessione}  -  {sim.weather.label}", (24, 38), 13,
               T.GOLD if sim.kind == "sprint" else T.DIM)
        if sim.meteo_prog:
            giro, forza = sim.meteo_prog[0]
            cosa = "pioggia" if forza > 0.05 else "asciutto"
            T.text(surf, f"previsione: {cosa} dal giro {giro}", (260, 38), 13, T.WARN)
        if sim.safety_car > 0:
            lab = "VIRTUAL SAFETY CAR" if sim.vsc else "SAFETY CAR"
            T.panel(surf, (w // 2 - 110, 12, 220, 34), (120, 96, 20), radius=6)
            T.text(surf, lab, (w // 2, 20), 16, (255, 235, 120), bold=True, align="center")

        view = pygame.Rect(20, 68, w - tower_w - 48, h - 240)
        T.panel(surf, view, (13, 17, 24), radius=10, border=T.LINE)
        if self.pts is None:
            self.pts = trackdraw.fit_points(self.track, view.inflate(-30, -30))
        trackdraw.draw_track(surf, self.track, view, width=14, pts=self.pts)

        order = sim.order()
        for e in reversed(order):
            if e.status == "retired":
                continue
            frac = (e.dist % sim.track_len) / sim.track_len
            off = -7 if e.position % 2 == 0 else 7
            x, y = trackdraw.car_pos(self.pts, frac, off * 0.55)
            is_player = (e.team_id == gs.player_team)
            r = 7 if is_player else 5
            if e.status == "pitting":
                pygame.draw.circle(surf, (90, 90, 100), (int(x), int(y)), r + 2)
            pygame.draw.circle(surf, e.colour, (int(x), int(y)), r)
            pygame.draw.circle(surf, (10, 14, 20), (int(x), int(y)), r, 1)
            if is_player or e.position <= 3:
                T.text(surf, e.code, (int(x) + 9, int(y) - 8), 12,
                       T.WHITE if is_player else T.DIM, bold=is_player)

        # eventi
        ev = pygame.Rect(20, h - 164, w - tower_w - 48, 74)
        T.panel(surf, ev, T.PANEL, radius=10, border=T.LINE)
        cols = {"pass": T.OK, "dnf": T.BAD, "pit": T.ACCENT, "sc": T.GOLD,
                "warn": T.WARN, "flag": T.WHITE, "pen": (255, 120, 90)}
        for i, e in enumerate(sim.events[:3]):
            T.text(surf, f"g{e['lap']:>2}", (ev.x + 14, ev.y + 10 + i * 20), 13, T.DIM_2, mono=True)
            T.text(surf, e["text"], (ev.x + 56, ev.y + 10 + i * 20), 14,
                   cols.get(e["kind"], T.TEXT), maxw=ev.w - 80)

        # torre dei tempi
        tower = pygame.Rect(w - tower_w - 20, 68, tower_w, h - 158)
        T.panel(surf, tower, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "POS  PILOTA", (tower.x + 16, tower.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "DISTACCO", (tower.right - 100, tower.y + 12), 11, T.DIM_2, bold=True)
        y = tower.y + 34
        leader = order[0] if order else None
        row_h = min(26, (tower.h - 50) / max(1, len(order)))
        for i, e in enumerate(order, 1):
            hl = (e.team_id == gs.player_team)
            if hl:
                T.panel(surf, (tower.x + 8, y - 2, tower.w - 16, row_h), T.PANEL_3, radius=5)
            T.text(surf, str(i), (tower.x + 34, y), 13, T.DIM, align="right")
            pygame.draw.rect(surf, e.colour, (tower.x + 44, y + 2, 3, int(row_h) - 6))
            T.text(surf, e.code, (tower.x + 56, y), 14, T.TEXT if hl else T.DIM, bold=hl, mono=True)
            T.text(surf, e.name, (tower.x + 96, y), 13, T.TEXT if hl else T.DIM, maxw=110)
            comp = C.COMPOUNDS[e.tyre]
            pygame.draw.circle(surf, comp["colour"], (tower.x + 218, int(y) + 8), 6)
            pygame.draw.circle(surf, (12, 16, 24), (tower.x + 218, int(y) + 8), 6, 1)
            wear = e.compound_state()
            T.bar(surf, (tower.x + 230, y + 5, 34, 6), wear * 100, 100,
                  T.OK if wear > 0.9 else (T.WARN if wear > 0.75 else T.BAD))
            if e.under_review > 0:
                T.text(surf, "INV", (tower.x + 270, y), 11, T.WARN, bold=True)
            elif e.penalty_pending > 0:
                T.text(surf, f"+{e.penalty_pending:.0f}s", (tower.x + 268, y), 11,
                       (255, 120, 90), bold=True)
            if e.status == "retired":
                T.text(surf, "RIT", (tower.right - 16, y), 12, T.BAD, align="right")
            elif e.status == "pitting":
                T.text(surf, "BOX", (tower.right - 16, y), 12, T.ACCENT, align="right", bold=True)
            elif i == 1:
                T.text(surf, "leader", (tower.right - 16, y), 12, T.GOLD, align="right")
            elif leader:
                gap_m = leader.dist - e.dist
                gap_s = gap_m / max(20.0, sim.track_len / max(30.0, e.last_lap))
                laps_down = int(gap_m // sim.track_len)
                txt = f"+{laps_down} giri" if laps_down >= 1 else f"+{gap_s:.1f}"
                T.text(surf, txt, (tower.right - 16, y), 12, T.DIM, align="right", mono=True)
            y += row_h
