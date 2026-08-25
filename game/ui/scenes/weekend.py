"""Weekend di gara: prove libere, qualifica, sprint e gara con vista 2D dal vivo."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import season as SEASON
from ...core import tyres as TY
from ...sim import session as S
from ...sim import hotlap as HOT
from ...sim.weekend import Weather
from ...sim import pace as PACE
from .. import theme as T
from .. import trackdraw
from ..app import Scene
from ..widgets import Button

SPEEDS = [0, 1, 4, 12, 40]
SPEED_LABELS = ["II", "x1", "x4", "x12", "x40"]

# I colori del tabellone: viola il migliore di tutti, verde il migliore suo,
# giallo tutto il resto. Sono quelli della televisione, e si leggono senza
# doverli spiegare.
VIOLA = (183, 96, 255)
_SETT = {"viola": VIOLA, "verde": (53, 196, 106), "giallo": (245, 196, 80)}
_STATO = {"box": "ai box", "uscita": "giro di lancio", "giro": "GIRO LANCIATO",
          "rientro": "rientra ai box", "finito": "ha finito"}
_CORTO = {"uscita": "lancio", "giro": "LANCIATO", "rientro": "rientra"}
_ZONA = {"lente": "curva lenta", "medie": "curva media", "veloci": "curva veloce",
         "trazione": "in trazione", "frenata": "in frenata",
         "rettilinei": "a tutto gas", "box": "corsia box"}

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
        self.turno = None          # il turno in pista che si sta guardando
        self.speed_idx = 2
        self.result_rows = []
        self.sprint_rows = []
        self.sprint_notes = []
        self.pts = None
        self.pts_rect = None
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
        self.pts_rect = None
        if self.stage == "gomme":
            self._build_tyres(w, h)
        elif self.turno is not None:
            self._build_turno(w, h)
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
        self.turno = HOT.LapSession(self.gs, self.ws, "prove")
        self.speed_idx = 3
        self.build()

    def to_quali(self) -> None:
        # dalle prove libere di un weekend sprint non si va in qualifica: prima
        # c'e' la Sprint Qualifying, e la qualifica arriva dopo la sprint
        self.stage = "sq" if (self.sprint_pending and self.stage == "prove") else "qualifica"
        self.build()

    def do_sprint_quali(self) -> None:
        self.turno = HOT.LapSession(self.gs, self.ws, "sprint")
        self.speed_idx = 3
        self.build()

    def do_quali(self) -> None:
        self.turno = HOT.LapSession(self.gs, self.ws, "gp")
        self.speed_idx = 3
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
        if self.turno and not self.turno.finita:
            mult = SPEEDS[self.speed_idx]
            if mult:
                self.turno.update(dt * mult)
            if self.turno.finita:
                self._on_turno_end()
            return
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
        if self.turno:
            self._draw_turno(surf)
        elif self.sim:
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
        # finite le libere il disegno della pista lascia il posto ai tempi: e'
        # quello che si guarda per capire dove si e' finiti
        if self.stage == "prove" and ws.practice_times:
            self._tempi_prove(surf, pygame.Rect(left.x + 16, left.y + 12,
                                                left.w - 32, left.h - 116))
        else:
            trackdraw.draw_track(surf, tr, left.inflate(-24, -32), width=10)
        # cosa dicono i radar per la domenica: e' l'informazione su cui si
        # decide se rischiare o no
        prev = ws.weather.forecast_label()
        acqua = "pioggia" in prev or "acquazzone" in prev
        T.text(surf, f"PREVISIONE: {prev}", (left.x + 20, left.bottom - 84), 11,
               T.WARN if acqua else T.DIM_2, bold=True, maxw=left.w - 40)
        # quanta gomma c'e' sull'asfalto: e' il motivo per cui i tempi calano
        # turno dopo turno anche senza toccare niente
        gomma = max(0.0, (ws.rubber - PACE.PISTA_VERDE)
                    / (PACE.PISTA_GOMMATA - PACE.PISTA_VERDE))
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

    def _tempi_prove(self, surf, rect) -> None:
        """La classifica delle libere: chi ha girato, in quanto, e a che distacco."""
        gs, ws = self.gs, self.ws
        T.text(surf, f"TEMPI DELLE LIBERE {ws.practice_done}", (rect.x, rect.y), 11,
               T.DIM_2, bold=True)
        ordine = sorted(ws.practice_times.items(), key=lambda kv: kv[1])
        primo = ordine[0][1] if ordine else 0.0
        rh = max(14.0, min(22.0, (rect.h - 26) / max(1, len(ordine))))
        dim = 13 if rh >= 18 else 12
        y = rect.y + 24
        for i, (did, t) in enumerate(ordine, 1):
            d = gs.drivers.get(did)
            if not d:
                continue
            team = gs.teams[d.team]
            mio = (team.id == gs.player_team)
            if mio:
                T.panel(surf, (rect.x - 6, int(y) - 2, rect.w + 12, int(rh)),
                        T.PANEL_3, radius=5)
            T.text(surf, str(i), (rect.x + 20, int(y)), dim, T.DIM, align="right")
            pygame.draw.rect(surf, T.hex_rgb(team.colour),
                             (rect.x + 28, int(y) + 2, 3, max(9, int(rh) - 6)))
            T.text(surf, d.short, (rect.x + 40, int(y)), dim, T.TEXT if mio else T.DIM,
                   bold=mio, maxw=rect.w * 0.42)
            T.text(surf, T.fmt_time(t), (rect.right - 84, int(y)), dim, T.TEXT,
                   mono=True, align="right")
            if i > 1:
                T.text(surf, f"+{t - primo:.3f}", (rect.right, int(y)), dim, T.DIM_2,
                       mono=True, align="right")
            y += rh

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
    # Quanto spazio si prende la barra in basso con le due macchine, e quanto
    # ne resta alla cronaca sopra di lei.
    BARRA_H = 108
    CRONACA_H = 62

    def _draw_race(self, surf) -> None:
        w, h = surf.get_size()
        sim = self.sim
        tower_w = max(336, min(460, int(w * 0.30)))
        self._race_header(surf, w)
        barra_y = h - 84 - self.BARRA_H
        cronaca_y = barra_y - self.CRONACA_H - 8
        vista = pygame.Rect(20, 68, w - tower_w - 48, cronaca_y - 76)
        self._race_map(surf, vista)
        self._race_events(surf, pygame.Rect(20, cronaca_y, vista.w, self.CRONACA_H))
        self._race_tower(surf, pygame.Rect(w - tower_w - 20, 68, tower_w, barra_y - 76))
        self._race_bar(surf, pygame.Rect(20, barra_y, w - 40, self.BARRA_H))

    def _race_header(self, surf, w: int) -> None:
        sim = self.sim
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 58))
        lap = min(sim.leader_lap + 1, sim.laps)
        T.text(surf, f"{self.track.name.upper()}  -  GIRO {lap}/{sim.laps}", (24, 10), 20,
               T.TEXT, bold=True)
        sessione = "SPRINT" if sim.kind == "sprint" else "GRAN PREMIO"
        T.text(surf, f"{sessione}  -  {sim.weather.label}", (24, 38), 13,
               T.GOLD if sim.kind == "sprint" else T.DIM)
        x = 260
        if sim.meteo_prog:
            giro, forza = sim.meteo_prog[0]
            cosa = "pioggia" if forza > 0.05 else "asciutto"
            # i giri a schermo si contano da uno, come sul tabellone
            testo = f"previsione: {cosa} dal giro {giro + 1}"
            T.text(surf, testo, (x, 38), 13, T.WARN)
            x += T.width(testo, 13) + 24
        # il giro piu' veloce della gara sta in alto come in televisione
        if sim.best_lap > 0:
            T.text(surf, "GIRO VELOCE", (x, 40), 11, T.DIM_2, bold=True)
            T.text(surf, f"{sim.best_lap_by}  {T.fmt_time(sim.best_lap)}",
                   (x + 92, 38), 13, VIOLA, mono=True, bold=True)
        if sim.safety_car > 0:
            lab = "VIRTUAL SAFETY CAR" if sim.vsc else "SAFETY CAR"
            T.panel(surf, (w // 2 - 110, 12, 220, 34), (120, 96, 20), radius=6)
            T.text(surf, lab, (w // 2, 20), 16, (255, 235, 120), bold=True, align="center")

    # ------------------------------------------------------------ la pista 2D
    def _race_map(self, surf, vista) -> None:
        sim, gs = self.sim, self.gs
        T.panel(surf, vista, (13, 17, 24), radius=10, border=T.LINE)
        if self.pts is None or self.pts_rect != tuple(vista):
            self.pts = trackdraw.fit_points(self.track, vista.inflate(-30, -30))
            self.pts_rect = tuple(vista)
        trackdraw.draw_track(surf, self.track, vista, width=14, pts=self.pts)
        # le sigle sul disegno si danno fastidio quando le macchine sono
        # incollate: chi non ha spazio resta senza nome, il pallino basta
        self._etichette = []
        self._marca_settori(surf)
        for e in reversed(sim.order()):
            if e.status == "retired":
                continue
            # dove si trova adesso non e' "quanto tempo e' passato": in fondo al
            # rettilineo copre trecento metri in tre secondi e nel tornante ne
            # copre trenta. La mappa del giro nel tempo dice il punto giusto
            quota = self.track.pos_at(e.lap_fraction(sim.track_len))
            off = -7 if e.position % 2 == 0 else 7
            x, y = trackdraw.car_pos(self.pts, quota, off * 0.55)
            mio = (e.team_id == gs.player_team)
            r = 7 if mio else 5
            if e.status == "pitting":
                pygame.draw.circle(surf, (90, 90, 100), (int(x), int(y)), r + 2)
            pygame.draw.circle(surf, e.colour, (int(x), int(y)), r)
            pygame.draw.circle(surf, (10, 14, 20), (int(x), int(y)), r, 1)
            if (mio or e.position <= 3) and self._spazio(int(x) + 9, int(y) - 8):
                T.text(surf, e.code, (int(x) + 9, int(y) - 8), 12,
                       T.WHITE if mio else T.DIM, bold=mio)

    def _spazio(self, x: int, y: int) -> bool:
        """C'e' posto per una sigla qui, o ce n'e' gia' una addosso?"""
        for ax, ay in self._etichette:
            if abs(ax - x) < 34 and abs(ay - y) < 13:
                return False
        self._etichette.append((x, y))
        return True

    def _marca_settori(self, surf) -> None:
        """I due traguardi di settore sul disegno della pista."""
        a, b = self.track.sector_time
        for quota, lab in ((0.0, "S1"), (a, "S2"), (b, "S3")):
            x, y = trackdraw.car_pos(self.pts, self.track.pos_at(quota), 0.0)
            x2, y2 = trackdraw.car_pos(self.pts, self.track.pos_at(quota), 16.0)
            pygame.draw.line(surf, (86, 102, 128), (x, y), (x2, y2), 2)
            self._etichette.append((int(x2) + 3, int(y2) - 7))
            T.text(surf, lab, (int(x2) + 3, int(y2) - 7), 10, (110, 128, 156), bold=True)

    def _race_events(self, surf, ev) -> None:
        T.panel(surf, ev, T.PANEL, radius=10, border=T.LINE)
        cols = {"pass": T.OK, "dnf": T.BAD, "pit": T.ACCENT, "sc": T.GOLD,
                "warn": T.WARN, "flag": T.WHITE, "pen": (255, 120, 90)}
        for i, e in enumerate(self.sim.events[:3]):
            y = ev.y + 8 + i * 18
            T.text(surf, f"g{e['lap']:>2}", (ev.x + 14, y), 12, T.DIM_2, mono=True)
            T.text(surf, e["text"], (ev.x + 52, y), 13, cols.get(e["kind"], T.TEXT),
                   maxw=ev.w - 74)

    # -------------------------------------------------------- torre dei tempi
    def _race_tower(self, surf, tower) -> None:
        """Il tabellone, con le colonne al loro posto qualunque sia la finestra.

        Da destra: distacco, ultimo giro, i tre parziali colorati, quanto le
        resta alla gomma, da quanti giri e' su. Il nome per esteso compare solo
        se ci sta davvero: in televisione bastano tre lettere.
        """
        sim, gs = self.sim, self.gs
        T.panel(surf, tower, T.PANEL, radius=10, border=T.LINE)
        order = sim.order()
        x_gap = tower.right - 14
        x_lap = tower.right - 76
        x_pip = tower.right - 168
        x_bar = tower.right - 206
        x_age = tower.right - 210
        x_dot = tower.right - 236
        x_nome = tower.x + 92
        largo_nome = x_dot - 24 - x_nome
        T.text(surf, "POS  PILOTA", (tower.x + 16, tower.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "GOMMA", (x_dot - 10, tower.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "ULTIMO GIRO", (x_lap, tower.y + 12), 11, T.DIM_2, bold=True,
               align="right")
        T.text(surf, "DISTACCO", (x_gap, tower.y + 12), 11, T.DIM_2, bold=True,
               align="right")
        y = tower.y + 34
        leader = order[0] if order else None
        rh = min(26.0, (tower.h - 46) / max(1, len(order)))
        for i, e in enumerate(order, 1):
            mio = (e.team_id == gs.player_team)
            if mio:
                T.panel(surf, (tower.x + 8, y - 1, tower.w - 16, rh - 1), T.PANEL_3, radius=5)
            T.text(surf, str(i), (tower.x + 32, y), 13, T.DIM, align="right")
            pygame.draw.rect(surf, e.colour, (tower.x + 42, y + 2, 3, max(9, int(rh) - 6)))
            T.text(surf, e.code, (tower.x + 52, y), 14, T.TEXT if mio else T.DIM,
                   bold=mio, mono=True)
            # il posto accanto al codice: prima chi ha un conto aperto con i
            # commissari, poi - se ci sta - il nome per esteso
            if e.under_review > 0:
                T.text(surf, "INV", (x_nome, y + 1), 11, T.WARN, bold=True)
            elif e.penalty_pending > 0:
                T.text(surf, f"+{e.penalty_pending:.0f}s", (x_nome, y + 1), 11,
                       (255, 120, 90), bold=True)
            elif largo_nome >= 70:
                T.text(surf, e.name, (x_nome, y), 13, T.TEXT if mio else T.DIM,
                       maxw=largo_nome)
            comp = C.COMPOUNDS[e.tyre]
            pygame.draw.circle(surf, comp["colour"], (x_dot, int(y) + 8), 6)
            pygame.draw.circle(surf, (12, 16, 24), (x_dot, int(y) + 8), 6, 1)
            T.text(surf, f"{int(e.tyre_age)}", (x_age, y + 1), 11, T.DIM_2, align="right")
            wear = e.compound_state()
            T.bar(surf, (x_bar, y + 5, 30, 6), wear * 100, 100,
                  T.OK if wear > 0.9 else (T.WARN if wear > 0.78 else T.BAD))
            for k in range(3):
                col = sim.sector_colour(e, k)
                pygame.draw.rect(surf, _SETT.get(col, (46, 58, 78)),
                                 (x_pip + k * 10, int(y) + 5, 7, 7))
            if e.sectors[2] > 0 and e.status != "retired":
                giro = sum(e.sectors)
                col = VIOLA if abs(giro - sim.best_lap) < 0.002 else (
                    T.OK if abs(giro - e.best_lap) < 0.002 else T.DIM)
                T.text(surf, T.fmt_time(giro), (x_lap, y), 12, col, mono=True, align="right")
            if e.status == "retired":
                T.text(surf, "RIT", (x_gap, y), 12, T.BAD, align="right")
            elif e.status == "pitting":
                T.text(surf, "BOX", (x_gap, y), 12, T.ACCENT, align="right", bold=True)
            elif i == 1:
                T.text(surf, "leader", (x_gap, y), 12, T.GOLD, align="right")
            elif leader:
                gap_m = leader.dist - e.dist
                gap_s = gap_m / max(20.0, sim.track_len / max(30.0, e.last_lap))
                giri = int(gap_m // sim.track_len)
                txt = f"+{giri} giri" if giri >= 1 else f"+{gap_s:.1f}"
                T.text(surf, txt, (x_gap, y), 12, T.DIM, align="right", mono=True)
            y += rh

    # ------------------------------------------------- la barra delle due auto
    def _race_bar(self, surf, barra) -> None:
        """Le nostre due macchine viste da dentro il box.

        Quello che si guarda davvero mentre la gara va avanti: a quanto sta
        andando, cosa ha sotto, quanta benzina resta, che tempo ha fatto e cosa
        ha appena detto alla radio.
        """
        sim, gs = self.sim, self.gs
        nostre = [e for e in sim.entrants if e.team_id == gs.player_team]
        if not nostre:
            return
        n = len(nostre)
        larga = (barra.w - 12 * (n - 1)) / n
        for i, e in enumerate(nostre):
            self._pannello_vettura(surf, pygame.Rect(barra.x + i * (larga + 12), barra.y,
                                                     larga, barra.h), e)

    def _pannello_vettura(self, surf, r, e) -> None:
        sim = self.sim
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        pygame.draw.rect(surf, e.colour, (r.x, r.y + 8, 4, r.h - 16))
        stretto = r.w < 430
        # ---- riga uno: chi e', dov'e', a quanto va
        T.text(surf, f"P{e.position}", (r.x + 16, r.y + 8), 15, T.GOLD, bold=True)
        T.text(surf, e.name, (r.x + 54, r.y + 8), 16, T.TEXT, bold=True, maxw=150)
        stato = {"pitting": "AI BOX", "retired": "RITIRATO"}.get(e.status, "")
        if stato:
            T.text(surf, stato, (r.x + 210, r.y + 10), 12,
                   T.ACCENT if e.status == "pitting" else T.BAD, bold=True)
        elif not stretto:
            T.text(surf, _ZONA.get(sim.zone_of(e), ""), (r.x + 210, r.y + 10), 12, T.DIM_2)
        v = sim.speed_of(e)
        T.text(surf, f"{v:.0f}", (r.right - 46, r.y + 4), 24, T.TEXT, bold=True,
               mono=True, align="right")
        T.text(surf, "km/h", (r.right - 14, r.y + 14), 11, T.DIM_2, align="right")
        # ---- riga due: gomme e benzina
        y = r.y + 36
        comp = C.COMPOUNDS[e.tyre]
        pygame.draw.circle(surf, comp["colour"], (r.x + 22, y + 7), 7)
        pygame.draw.circle(surf, (12, 16, 24), (r.x + 22, y + 7), 7, 1)
        T.text(surf, f"{comp['label'].upper()}  {int(e.tyre_age)} giri",
               (r.x + 36, y), 12, T.DIM)
        stato_g = e.compound_state()
        T.bar(surf, (r.x + 150, y + 4, 74, 7), stato_g * 100, 100,
              T.OK if stato_g > 0.9 else (T.WARN if stato_g > 0.78 else T.BAD))
        giri_b = e.fuel / max(0.01, sim.burn_per_lap)
        restano = sim.laps - e.lap
        T.text(surf, "BENZINA", (r.x + 240, y + 1), 11, T.DIM_2, bold=True)
        T.bar(surf, (r.x + 300, y + 4, 70, 7), min(100.0, giri_b / max(1, restano) * 100), 100,
              T.OK if giri_b >= restano else T.BAD)
        T.text(surf, f"{e.fuel:.0f} kg", (r.x + 380, y), 12,
               T.DIM if giri_b >= restano else T.BAD)
        if r.w >= 520:
            T.text(surf, f"{giri_b:.0f} giri su {max(0, restano)}", (r.right - 14, y), 12,
                   T.DIM_2, align="right")
        # ---- riga tre: tempi e distacchi
        y = r.y + 56
        giro = sum(e.sectors) if e.sectors[2] > 0 else 0.0
        T.text(surf, "GIRO", (r.x + 16, y + 2), 11, T.DIM_2, bold=True)
        T.text(surf, T.fmt_time(giro) if giro else "--:--.---", (r.x + 56, y), 13,
               T.TEXT, mono=True)
        sx = r.x + 140
        for k in range(3):
            col = sim.sector_colour(e, k)
            T.text(surf, f"{e.sectors[k]:.3f}" if e.sectors[k] > 0 else "--.---",
                   (sx + k * 62, y + 1), 11, _SETT.get(col, T.DIM_2), mono=True)
        T.text(surf, "MIGLIORE", (r.x + 330, y + 2), 11, T.DIM_2, bold=True)
        T.text(surf, T.fmt_time(e.best_lap) if e.best_lap < 900 else "--:--.---",
               (r.x + 392, y), 13,
               VIOLA if e.best_lap and abs(e.best_lap - sim.best_lap) < 0.002 else T.TEXT,
               mono=True)
        if e.damage > 6:
            T.text(surf, f"DANNI {e.damage:.0f}%", (r.right - 14, y), 12, T.BAD,
                   bold=True, align="right")
        # ---- riga quattro: la radio
        m = sim.radio_of(e.driver_id)
        if m:
            chi = "MURETTO" if m["chi"] == "muretto" else e.code
            col = T.ACCENT if m["chi"] == "muretto" else T.GOLD
            T.text(surf, chi, (r.x + 16, r.bottom - 22), 11, col, bold=True)
            T.text(surf, m["text"], (r.x + 88, r.bottom - 23), 13, T.DIM,
                   maxw=r.w - 108)

    # ------------------------------------------------------------ turno vivo
    def _build_turno(self, w: int, h: int) -> None:
        """I comandi mentre un turno e' in corso: la velocita' e la scorciatoia."""
        bx, by = 40, h - 74
        for i, lab in enumerate(SPEED_LABELS):
            b = Button((bx + i * 62, by, 56, 34), lab, style="tab")
            b.on_click = (lambda i=i: self.set_speed(i))
            b.active = (i == self.speed_idx)
            self.widgets.append(b)
        self.widgets.append(Button((bx + 5 * 62 + 16, by, 210, 34),
                                   "Vai alla fine del turno", self.skip_turno, "ghost"))

    def skip_turno(self) -> None:
        if self.turno:
            self.turno.corri_tutto()
            self._on_turno_end()

    def _on_turno_end(self) -> None:
        turno = self.turno
        if turno is None:
            return
        turno.applica()
        self.turno = None
        if turno.kind == "prove":
            pass                                  # si resta nelle libere
        elif turno.kind == "sprint":
            self.stage = "sprint"
        else:
            self.stage = "gara"
        self.build()

    def _draw_turno(self, surf) -> None:
        w, h = surf.get_size()
        tower_w = max(336, min(460, int(w * 0.30)))
        self._turno_header(surf, w)
        barra_y = h - 84 - self.BARRA_H
        cronaca_y = barra_y - self.CRONACA_H - 8
        vista = pygame.Rect(20, 68, w - tower_w - 48, cronaca_y - 76)
        self._turno_map(surf, vista)
        self._turno_events(surf, pygame.Rect(20, cronaca_y, vista.w, self.CRONACA_H))
        self._turno_tower(surf, pygame.Rect(w - tower_w - 20, 68, tower_w, barra_y - 76))
        self._turno_bar(surf, pygame.Rect(20, barra_y, w - 40, self.BARRA_H))

    def _turno_header(self, surf, w: int) -> None:
        t = self.turno
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 58))
        titolo = t.nome_fase
        if t.kind == "prove":
            titolo = f"PROVE LIBERE {self.ws.practice_done + 1}/{S.practice_sessions(self.track)}"
        T.text(surf, f"{self.track.name.upper()}  -  {titolo}", (24, 10), 20, T.TEXT,
               bold=True)
        resta = t.resta()
        col = T.BAD if resta < 120 else (T.WARN if resta < 300 else T.TEXT)
        T.text(surf, _orologio(resta), (24, 34), 20, col, bold=True, mono=True)
        T.text(surf, f"{t.weather.label} - {t.weather.air_temp:.0f}C aria, "
                     f"{t.weather.track_temp:.0f}C asfalto, vento {t.weather.wind:.0f} km/h",
               (128, 38), 13, T.DIM, maxw=w * 0.34)
        if t.taglio_ora:
            T.text(surf, f"PASSANO IN {t.fasi[t.phase + 1][0]}: I PRIMI {t.taglio_ora}",
                   (w * 0.5, 14), 12, T.WARN, bold=True)
        if t.best_lap > 0:
            T.text(surf, "IL PIU' VELOCE", (w * 0.5, 36), 11, T.DIM_2, bold=True)
            T.text(surf, f"{t.best_by}  {T.fmt_time(t.best_lap)}", (w * 0.5 + 96, 34), 14,
                   VIOLA, mono=True, bold=True)
        gomma = max(0.0, (self.ws.rubber - PACE.PISTA_VERDE)
                    / (PACE.PISTA_GOMMATA - PACE.PISTA_VERDE))
        T.text(surf, f"PISTA GOMMATA AL {gomma * 100:.0f}%", (w - 24, 20), 11,
               T.stat_colour(gomma * 100, 25, 70), bold=True, align="right")

    def _turno_map(self, surf, vista) -> None:
        t, gs = self.turno, self.gs
        T.panel(surf, vista, (13, 17, 24), radius=10, border=T.LINE)
        if self.pts is None or self.pts_rect != tuple(vista):
            self.pts = trackdraw.fit_points(self.track, vista.inflate(-30, -30))
            self.pts_rect = tuple(vista)
        trackdraw.draw_track(surf, self.track, vista, width=14, pts=self.pts)
        self._etichette = []
        self._marca_settori(surf)
        fuori = [p for p in t.piste.values() if p.stato in ("uscita", "giro", "rientro")]
        # chi e' lanciato si disegna per ultimo: e' quello che si guarda
        fuori.sort(key=lambda p: p.stato == "giro")
        for p in fuori:
            x, y = trackdraw.car_pos(self.pts, self.track.pos_at(p.quota), 0.0)
            mio = (p.e.team_id == gs.player_team)
            lanciato = (p.stato == "giro")
            r = 7 if (mio or lanciato) else 5
            if lanciato:
                pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), r + 3, 1)
            pygame.draw.circle(surf, p.e.colour, (int(x), int(y)), r)
            pygame.draw.circle(surf, (10, 14, 20), (int(x), int(y)), r, 1)
            if (mio or lanciato) and self._spazio(int(x) + 9, int(y) - 8):
                T.text(surf, p.e.code, (int(x) + 9, int(y) - 8), 12,
                       T.WHITE if mio else T.DIM, bold=mio)
        if not fuori:
            T.text(surf, "NESSUNO IN PISTA", (vista.centerx, vista.bottom - 26), 12,
                   T.DIM_2, bold=True, align="center")

    def _turno_events(self, surf, ev) -> None:
        t = self.turno
        T.panel(surf, ev, T.PANEL, radius=10, border=T.LINE)
        cols = {"pass": T.OK, "warn": T.WARN, "flag": T.WHITE}
        for i, e in enumerate(t.eventi[:3]):
            y = ev.y + 8 + i * 18
            T.text(surf, _orologio(e["t"]), (ev.x + 14, y), 12, T.DIM_2, mono=True)
            T.text(surf, e["text"], (ev.x + 62, y), 13, cols.get(e["kind"], T.TEXT),
                   maxw=ev.w - 84)

    # ------------------------------------------------------- tabellone tempi
    def _turno_tower(self, surf, tower) -> None:
        """Il tabellone del turno: il tempo, il distacco e - soprattutto - il taglio.

        Quello che si guarda in qualifica non e' il tempo: e' quanto manca a
        quello dell'ultimo che passa il turno. Sta nell'ultima colonna, in
        verde se si e' dentro e in rosso se si e' fuori.
        """
        t, gs = self.turno, self.gs
        T.panel(surf, tower, T.PANEL, radius=10, border=T.LINE)
        righe = t.righe()
        taglio = t.tempo_taglio()
        x_cut = tower.right - 14
        x_gap = tower.right - 72
        x_lap = tower.right - 134
        x_pip = tower.right - 226
        x_dot = tower.right - 252
        T.text(surf, "POS  PILOTA", (tower.x + 16, tower.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "TEMPO", (x_lap, tower.y + 12), 11, T.DIM_2, bold=True, align="right")
        T.text(surf, "DAL 1o", (x_gap, tower.y + 12), 11, T.DIM_2, bold=True, align="right")
        if taglio:
            T.text(surf, "TAGLIO", (x_cut, tower.y + 12), 11, T.DIM_2, bold=True,
                   align="right")
        y = tower.y + 34
        rh = min(26.0, (tower.h - 46) / max(1, len(righe)))
        nomi = [f[0] for f in t.fasi]
        prima_fase = None
        for i, p in enumerate(righe, 1):
            e = p.e
            mio = (e.team_id == gs.player_team)
            if p.fuori and p.fase_uscita != prima_fase:
                prima_fase = p.fase_uscita
                eti = f"eliminati in {nomi[p.fase_uscita]}"
                largo = T.width(eti, 10, bold=True)
                pygame.draw.line(surf, T.LINE, (tower.x + 16, int(y) + 6),
                                 (tower.right - 26 - largo, int(y) + 6))
                T.text(surf, eti, (tower.right - 16, int(y)), 10, T.DIM_2, bold=True,
                       align="right")
                y += 16
            if mio:
                T.panel(surf, (tower.x + 8, y - 1, tower.w - 16, rh - 1), T.PANEL_3, radius=5)
            if p.stato == "giro":
                pygame.draw.rect(surf, VIOLA, (tower.x + 8, y - 1, 2, rh - 2))
            T.text(surf, str(i), (tower.x + 32, y), 13, T.DIM, align="right")
            pygame.draw.rect(surf, e.colour, (tower.x + 42, y + 2, 3, max(9, int(rh) - 6)))
            # chi e' lanciato si vede a colpo d'occhio anche quando la colonna
            # dello stato non ci sta: sigla accesa e riga segnata a sinistra
            col_cod = T.ACCENT if p.stato == "giro" else (T.TEXT if mio else T.DIM)
            T.text(surf, e.code, (tower.x + 52, y), 14, col_cod,
                   bold=(mio or p.stato == "giro"), mono=True)
            stato = "" if p.fuori else _CORTO.get(p.stato, "")
            if stato and x_dot - (tower.x + 94) >= 76:
                T.text(surf, stato, (tower.x + 94, y + 1), 11,
                       T.ACCENT if p.stato == "giro" else T.DIM_2,
                       bold=(p.stato == "giro"), maxw=x_dot - (tower.x + 108))
            comp = C.COMPOUNDS.get(p.mescola, C.COMPOUNDS["soft"])
            pygame.draw.circle(surf, comp["colour"], (x_dot, int(y) + 8), 6)
            pygame.draw.circle(surf, (12, 16, 24), (x_dot, int(y) + 8), 6, 1)
            for k in range(3):
                vivo = p.stato == "giro"
                val = p.live[k] if vivo else p.settori[k]
                col = t.sector_colour(p, k, val) if val > 0 else None
                pygame.draw.rect(surf, _SETT.get(col, (46, 58, 78)),
                                 (x_pip + k * 10, int(y) + 5, 7, 7))
            if p.tempo > 0:
                col = VIOLA if abs(p.tempo - t.best_lap) < 0.002 else T.TEXT
                T.text(surf, T.fmt_time(p.tempo), (x_lap, y), 12, col, mono=True,
                       align="right")
                if t.best_lap > 0 and p.tempo > t.best_lap + 0.0005:
                    T.text(surf, f"+{p.tempo - t.best_lap:.3f}", (x_gap, y), 12, T.DIM,
                           mono=True, align="right")
            else:
                T.text(surf, "senza tempo", (x_lap, y), 11, T.DIM_2, align="right")
            if p.fuori:
                T.text(surf, "OUT", (x_cut, y), 12, T.BAD, align="right", bold=True)
            elif taglio and p.tempo > 0:
                d = p.tempo - taglio
                T.text(surf, f"{d:+.3f}" if abs(d) > 0.0005 else "limite",
                       (x_cut, y), 12, T.BAD if d > 0 else T.OK, mono=True, align="right")
            y += rh

    # ------------------------------------------------- le nostre due macchine
    def _turno_bar(self, surf, barra) -> None:
        t, gs = self.turno, self.gs
        nostre = [p for p in t.righe() if p.e.team_id == gs.player_team]
        if not nostre:
            return
        larga = (barra.w - 12 * (len(nostre) - 1)) / len(nostre)
        for i, p in enumerate(nostre):
            self._pannello_turno(surf, pygame.Rect(barra.x + i * (larga + 12), barra.y,
                                                   larga, barra.h), p, i + 1)

    def _pannello_turno(self, surf, r, p, _n) -> None:
        t = self.turno
        e = p.e
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        pygame.draw.rect(surf, e.colour, (r.x, r.y + 8, 4, r.h - 16))
        posto = next((i for i, q in enumerate(t.righe(), 1) if q is p), 0)
        T.text(surf, f"P{posto}", (r.x + 16, r.y + 8), 15, T.GOLD, bold=True)
        T.text(surf, e.name, (r.x + 54, r.y + 8), 16, T.TEXT, bold=True, maxw=150)
        T.text(surf, _STATO.get(p.stato, ""), (r.x + 210, r.y + 10), 12,
               T.ACCENT if p.stato == "giro" else T.DIM_2, bold=(p.stato == "giro"))
        quante = len(p.corse)
        ora = min(quante, p.indice + (0 if p.stato == "box" else 1))
        if r.w >= 470:
            T.text(surf, f"uscita {ora} di {quante}", (r.right - 90, r.y + 11), 11,
                   T.DIM_2, align="right")
        comp = C.COMPOUNDS.get(p.mescola, C.COMPOUNDS["soft"])
        pygame.draw.circle(surf, comp["colour"], (r.right - 30, r.y + 18), 8)
        pygame.draw.circle(surf, (12, 16, 24), (r.right - 30, r.y + 18), 8, 1)
        T.text(surf, comp["label"].upper(), (r.right - 46, r.y + 11), 12, T.DIM,
               align="right")
        # ---- i tre parziali, grandi: sono quelli che si guardano
        y = r.y + 36
        vivo = (p.stato == "giro")
        for k in range(3):
            val = p.live[k] if vivo else p.settori[k]
            col = t.sector_colour(p, k, val) if val > 0 else None
            T.text(surf, f"S{k + 1}", (r.x + 16 + k * 96, y + 4), 11, T.DIM_2, bold=True)
            T.text(surf, f"{val:.3f}" if val > 0 else "--.---",
                   (r.x + 40 + k * 96, y), 15, _SETT.get(col, T.DIM_2), mono=True)
        T.text(surf, "MIGLIORE", (r.x + 306, y + 4), 11, T.DIM_2, bold=True)
        T.text(surf, T.fmt_time(p.tempo) if p.tempo > 0 else "--:--.---",
               (r.x + 370, y), 15,
               VIOLA if p.tempo > 0 and abs(p.tempo - t.best_lap) < 0.002 else T.TEXT,
               mono=True)
        # ---- riga tre: dove siamo rispetto agli altri
        y = r.y + 62
        if p.tempo > 0 and t.best_lap > 0:
            d = p.tempo - t.best_lap
            T.text(surf, "DAL PIU' VELOCE", (r.x + 16, y + 2), 11, T.DIM_2, bold=True)
            T.text(surf, f"+{d:.3f}" if d > 0.0005 else "e' il piu' veloce",
                   (r.x + 122, y), 13, T.TEXT if d > 0.0005 else VIOLA, mono=(d > 0.0005))
        taglio = t.tempo_taglio()
        if taglio and p.tempo > 0:
            d = p.tempo - taglio
            T.text(surf, "DAL TAGLIO", (r.x + 230, y + 2), 11, T.DIM_2, bold=True)
            T.text(surf, f"{d:+.3f}", (r.x + 306, y), 13, T.BAD if d > 0 else T.OK,
                   mono=True)
            T.text(surf, "fuori" if d > 0 else "dentro", (r.x + 372, y + 2), 12,
                   T.BAD if d > 0 else T.OK, bold=True)
        elif p.tempo <= 0:
            T.text(surf, "non ha ancora segnato un tempo", (r.x + 16, y), 13, T.DIM_2)
        # ---- riga quattro: quante uscite restano
        m = t.radio_of(p.e.driver_id)
        if m:
            chi = "MURETTO" if m["chi"] == "muretto" else p.e.code
            T.text(surf, chi, (r.x + 16, r.bottom - 22), 11,
                   T.ACCENT if m["chi"] == "muretto" else T.GOLD, bold=True)
            T.text(surf, m["text"], (r.x + 88, r.bottom - 23), 13, T.DIM, maxw=r.w - 108)


def _orologio(secondi: float) -> str:
    """Il tempo che resta, come lo scrive il tabellone: minuti e secondi."""
    m, sec = divmod(max(0.0, secondi), 60.0)
    return f"{int(m)}:{int(sec):02d}"
