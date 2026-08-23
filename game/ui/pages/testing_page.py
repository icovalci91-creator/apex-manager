"""Pagina Test privati: dove girare, con chi, e per ottenere cosa."""
from __future__ import annotations

import pygame

from ...core import testing as TT
from .. import theme as T
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, card


class TestingPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.track = None
        self.driver = None
        self.programme = "giovani"
        self.days = 2

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.42, r.h - 96)
        self.piste = ScrollList((left.x + 12, left.y + 40, left.w - 24, left.h - 56),
                                row_h=34, draw_row=self._row_track, on_select=self._pick_track)
        self.widgets.append(self.piste)

        right = pygame.Rect(r.x + r.w * 0.44, r.y + 96, r.w * 0.56 - 4, r.h - 96)
        self.prog_buttons = []
        bw = (right.w - 44) / 2
        for i, (key, meta) in enumerate(TT.PROGRAMMI.items()):
            b = Button((right.x + 16 + (i % 2) * (bw + 8),
                        right.y + 34 + (i // 2) * 36, bw, 30), meta["label"])
            b.on_click = (lambda k=key: self._pick_prog(k))
            self.prog_buttons.append(b)
            self.widgets.append(b)
        self._mark_prog()

        self.piloti = ScrollList((right.x + 16, right.y + 154, right.w - 32, 122),
                                 row_h=30, draw_row=self._row_driver, on_select=self._pick_driver)
        self.widgets.append(self.piloti)

        self.s_days = Slider((right.x + 16, right.y + 292, right.w - 32, 28), "Giornate",
                             self.days, 1, max(1, TT.days_left(self.gs, self.team)),
                             on_change=self._set_days, fmt="{:.0f}")
        self.widgets.append(self.s_days)
        self.widgets.append(Button((right.x + 16, right.y + 328, 250, 40),
                                   "Manda la squadra in pista", self.run, "primary"))
        self._fill()

    def _mark_prog(self) -> None:
        """L'attivo si stacca dagli altri: sul pannello scuro il tab spento sparisce."""
        for b, key in zip(self.prog_buttons, TT.PROGRAMMI):
            b.active = (key == self.programme)
            b.style = "tab" if b.active else "normal"

    def _fill(self) -> None:
        gs = self.gs
        piste = sorted(TT.venues(gs, self.team), key=lambda t: t.name)
        self.piste.items = piste
        if piste and self.track not in piste:
            self.track = piste[0]
        if self.track in piste:
            self.piste.selected = piste.index(self.track)
        drs = self.gs.drivers_of(self.team.id)
        riserve = sorted(gs.free_agents, key=lambda d: -(d.potential))[:4]
        self.piloti.items = drs + riserve
        if self.piloti.items and self.driver not in self.piloti.items:
            # per difetto proponiamo chi ha ancora margine: i chilometri servono a lui
            self.driver = max(self.piloti.items, key=lambda d: d.potential - d.overall)
        if self.driver in self.piloti.items:
            self.piloti.selected = self.piloti.items.index(self.driver)

    # ------------------------------------------------------------------ azioni
    def _pick_track(self, i, t) -> None:
        self.track = t

    def _pick_driver(self, i, d) -> None:
        self.driver = d

    def _pick_prog(self, k) -> None:
        self.programme = k
        self._mark_prog()

    def _set_days(self, v) -> None:
        self.days = int(round(v))

    def run(self) -> None:
        if not self.track:
            return
        ok, msg = TT.run(self.gs, self.team, self.track, self.driver,
                         self.programme, self.days)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- righe
    def _row_track(self, surf, rect, i, t) -> None:
        gs = self.gs
        in_cal = t in gs.tracks
        T.text(surf, t.name, (rect.x + 14, rect.y + 8), 14, T.TEXT, maxw=250)
        T.text(surf, t.flag, (rect.x + 278, rect.y + 9), 12, T.DIM)
        sapere = TT.setup_bonus(self.team, t)
        if sapere > 0.01:
            T.bar(surf, (rect.x + 310, rect.y + 13, 60, 7), sapere * 100, 100, T.OK)
        prezzo = TT.cost_of(gs, self.team, t, self.programme, self.days)
        T.text(surf, f"{prezzo:.1f} M$", (rect.right - 14, rect.y + 8), 13,
               T.GOLD, align="right")
        if not in_cal:
            T.text(surf, "fuori calendario", (rect.x + 14, rect.y + 22), 10, T.DIM_2)

    def _row_driver(self, surf, rect, i, d) -> None:
        proprio = d.team == self.team.id
        T.text(surf, d.name, (rect.x + 12, rect.y + 6), 14,
               T.TEXT if proprio else T.DIM, maxw=200)
        T.text(surf, f"{d.age}a", (rect.x + 220, rect.y + 7), 12, T.DIM)
        margine = max(0.0, d.potential - d.overall)
        col = T.OK if margine > 6 else (T.WARN if margine > 2 else T.DIM_2)
        T.text(surf, f"margine {margine:.0f}", (rect.right - 14, rect.y + 6), 12,
               col, align="right")
        if not proprio:
            T.text(surf, "svincolato", (rect.x + 262, rect.y + 7), 11, T.DIM_2)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        cw = (r.w - 32) / 3
        restano = TT.days_left(gs, team)
        card(surf, (r.x, r.y, cw, 86), "Giornate di test",
             f"{restano} su {TT.days_allowed(gs, team)}",
             (f"due in piu': abbiamo {team.private_track_name}"
              if team.has_private_track else "il regolamento non ne concede altre"),
             colour=T.OK if restano > 2 else T.WARN, accent=T.ACCENT)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Correlazione",
             f"{team.correlation*100:.0f}%",
             "quanto la galleria dice il vero", accent=T.GOLD,
             colour=T.OK if team.correlation > 0.2 else T.TEXT)
        note = len([k for k, v in (team.setup_knowledge or {}).items() if v > 0.05])
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Circuiti studiati",
             str(note), "assetto gia' nella finestra giusta", accent=T.OK)

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.42, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "DOVE GIRARE", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, "costo per la sessione scelta", (left.right - 16, left.y + 12), 11,
               T.DIM_2, align="right")

        right = pygame.Rect(r.x + r.w * 0.44, r.y + 96, r.w * 0.56 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROGRAMMA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        meta = TT.PROGRAMMI[self.programme]
        T.text(surf, meta["desc"], (right.x + 16, right.y + 112), 13, T.DIM,
               maxw=right.w - 32)
        T.text(surf, "CHI MANDIAMO", (right.x + 16, right.y + 136), 12, T.DIM_2, bold=True)
        if self.programme != "giovani":
            T.text(surf, "(per questo programma il pilota conta poco)",
                   (right.x + 150, right.y + 136), 11, T.DIM_2)

        if self.track:
            voci = TT.cost_breakdown(gs, team, self.track, self.programme, self.days)
            prezzo = sum(voci.values())
            ok, why = TT.can_run(gs, team, self.track, self.programme, self.days)
            casa = TT.is_home(team, self.track)
            T.text(surf, f"{self.days} giornate a {self.track.name}: {prezzo:.2f} M$ "
                         f"dentro il tetto di spesa",
                   (right.x + 16, right.y + 384), 14, T.TEXT, maxw=right.w - 32)
            # le tre voci separate: i materiali sono uguali dappertutto, il
            # resto lo si paga solo andando a casa d'altri
            x = right.x + 16
            for chiave, etichetta in (("materiali", "materiali"), ("noleggio", "noleggio pista"),
                                      ("trasferta", "trasferta")):
                v = voci[chiave]
                col = T.DIM_2 if v <= 0.001 else (T.TEXT if chiave == "materiali" else T.WARN)
                T.text(surf, f"{etichetta} {v:.2f}", (x, right.y + 404), 12, col)
                x += 150
            if casa:
                T.text(surf, "e' casa nostra: si paga solo quello che si consuma",
                       (right.x + 16, right.y + 422), 12, T.OK, maxw=right.w - 32)
            if not ok:
                T.text(surf, why, (right.x + 16, right.y + 440), 13, T.BAD,
                       maxw=right.w - 32)
            trackdraw.draw_minimap(surf, self.track,
                                   (right.x + 16, right.y + 440, 210, 150),
                                   colour=(58, 70, 92), width=3)
            T.text(surf, self.track.name, (right.x + 244, right.y + 448), 16, T.TEXT,
                   bold=True, maxw=right.w - 268)
            T.text(surf, f"{self.track.length_km:.3f} km - {self.track.country}",
                   (right.x + 244, right.y + 470), 13, T.DIM)
            sapere = TT.setup_bonus(team, self.track)
            T.text(surf, f"conoscenza accumulata {sapere*100:.0f}%",
                   (right.x + 244, right.y + 492), 13,
                   T.OK if sapere > 0.3 else T.DIM)
            if self.track not in gs.tracks:
                T.text(surf, "fuori dal calendario: si gira e basta",
                       (right.x + 244, right.y + 514), 12, T.DIM_2)

        T.text(surf, "Il regolamento vieta di provare con la vettura dell'anno:",
               (right.x + 16, right.bottom - 52), 12, T.DIM_2, maxw=right.w - 32)
        T.text(surf, "si gira con monoposto di due stagioni fa. Serve ai piloti e alla",
               (right.x + 16, right.bottom - 36), 12, T.DIM_2, maxw=right.w - 32)
        T.text(surf, "correlazione, non a rendere piu' veloce la macchina di adesso.",
               (right.x + 16, right.bottom - 20), 12, T.DIM_2, maxw=right.w - 32)
        super().draw(surf)
