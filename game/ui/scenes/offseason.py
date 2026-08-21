"""Fine stagione: bilanci, votazioni in Commissione, mercato."""
from __future__ import annotations

import pygame

from ...core import rules, season as SEASON
from .. import theme as T
from ..app import Scene
from ..widgets import Button


class OffseasonScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.gs = app.gs
        self.report = SEASON.end_season(self.gs)
        self.votes: dict = {}
        self.results: list = []
        self.step = "riepilogo"       # riepilogo | voto | esito
        self.build()

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        if self.step == "riepilogo":
            self.widgets.append(Button((w // 2 - 140, h - 92, 280, 46),
                                       "Vai alla Commissione F1", self.to_vote, "primary"))
        elif self.step == "voto":
            for i, p in enumerate(self.gs.pending_votes):
                y = 190 + i * 150
                yb = Button((w - 420, y + 66, 130, 38), "Favorevole", style="tab")
                nb = Button((w - 280, y + 66, 130, 38), "Contrario", style="tab")
                yb.on_click = (lambda k=p["id"]: self.vote(k, True))
                nb.on_click = (lambda k=p["id"]: self.vote(k, False))
                yb.active = self.votes.get(p["id"]) is True
                nb.active = self.votes.get(p["id"]) is False
                self.widgets += [yb, nb]
            self.widgets.append(Button((w // 2 - 140, h - 92, 280, 46),
                                       "Chiudi le votazioni", self.tally, "primary"))
        else:
            self.widgets.append(Button((w // 2 - 140, h - 92, 280, 46),
                                       f"Inizia la stagione {self.gs.season}", self.done, "primary"))

    def on_resize(self) -> None:
        self.build()

    def to_vote(self) -> None:
        self.step = "voto"
        self.build()

    def vote(self, pid: str, value: bool) -> None:
        self.votes[pid] = value
        self.build()

    def tally(self) -> None:
        gs = self.gs
        for p in gs.pending_votes:
            res = rules.tally(gs, p, self.votes.get(p["id"]))
            notes = rules.apply_effects(gs, p) if res["passed"] else []
            self.results.append((p, res, notes))
            msg = (f"APPROVATA: {p['title']}" if res["passed"] else f"RESPINTA: {p['title']}")
            gs.push(msg + f" ({res['yes']}/{res['total']} voti)", "regole")
        gs.pending_votes = []
        self.step = "esito"
        self.build()

    def done(self) -> None:
        self.app.pop()
        from .shell import GameShell
        if isinstance(self.app.scene, GameShell):
            self.app.scene.build()
            self.app.scene.enter()

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        gs = self.gs
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 76))
        titles = {"riepilogo": f"FINE STAGIONE {gs.season - 1}",
                  "voto": "COMMISSIONE F1 - VOTAZIONI",
                  "esito": "ESITO DELLE VOTAZIONI"}
        T.text(surf, titles[self.step], (32, 22), 26, T.TEXT, bold=True)

        if self.step == "riepilogo":
            self._draw_summary(surf, w, h)
        elif self.step == "voto":
            self._draw_vote(surf, w, h)
        else:
            self._draw_outcome(surf, w, h)
        super().draw(surf)

    def _draw_summary(self, surf, w, h) -> None:
        gs, rep = self.gs, self.report
        left = pygame.Rect(32, 100, w * 0.46, h - 210)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CAMPIONI", (left.x + 20, left.y + 16), 12, T.DIM_2, bold=True)
        ch = rep.get("champions", {})
        if ch.get("driver"):
            d = ch["driver"]
            T.text(surf, "Campione del mondo piloti", (left.x + 20, left.y + 44), 13, T.DIM)
            T.text(surf, d.name, (left.x + 20, left.y + 62), 24, T.GOLD, bold=True)
        if ch.get("constructor"):
            t = ch["constructor"]
            T.text(surf, "Campione costruttori", (left.x + 20, left.y + 104), 13, T.DIM)
            T.text(surf, t.name, (left.x + 20, left.y + 122), 20, T.hex_rgb(t.colour), bold=True)
        y = left.y + 172
        T.text(surf, "BILANCIO", (left.x + 20, y), 12, T.DIM_2, bold=True)
        y += 24
        for m in rep.get("finance", [])[:8]:
            T.text(surf, "- " + m, (left.x + 20, y), 13, T.TEXT, maxw=left.w - 40)
            y += 20
        y += 10
        T.text(surf, "CRESCITA DEI NOSTRI PILOTI", (left.x + 20, y), 12, T.DIM_2, bold=True)
        y += 22
        for m in rep.get("progress", [])[:6]:
            T.text(surf, "- " + m, (left.x + 20, y), 13, T.DIM, maxw=left.w - 40)
            y += 20

        right = pygame.Rect(w * 0.5 + 16, 100, w * 0.5 - 48, h - 210)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "MERCATO", (right.x + 20, right.y + 16), 12, T.DIM_2, bold=True)
        y = right.y + 42
        for m in rep.get("market", [])[:14]:
            T.text(surf, "- " + m, (right.x + 20, y), 13, T.TEXT, maxw=right.w - 40)
            y += 20
        y += 14
        T.text(surf, "REGOLAMENTO", (right.x + 20, y), 12, T.DIM_2, bold=True)
        y += 22
        for m in rep.get("rules", []):
            T.text(surf, "- " + m, (right.x + 20, y), 13, T.WARN, maxw=right.w - 40)
            y += 20
        y += 14
        T.text(surf, "CLASSIFICA FINALE COSTRUTTORI", (right.x + 20, y), 12, T.DIM_2, bold=True)
        y += 22
        hist = self.gs.season_history[-1] if self.gs.season_history else None
        if hist:
            for name, pos in hist["standings"]:
                hl = (name == self.gs.player.short)
                T.text(surf, f"{pos}o", (right.x + 44, y), 13, T.DIM, align="right")
                T.text(surf, name, (right.x + 56, y), 13, T.TEXT if hl else T.DIM, bold=hl)
                y += 19

    def _draw_vote(self, surf, w, h) -> None:
        gs = self.gs
        T.text(surf, "Ogni scuderia ha un voto; FIA e FOM ne hanno dieci ciascuna. "
                     "Serve il 60% per approvare una modifica per la stagione seguente.",
               (32, 108), 14, T.DIM, maxw=w - 64)
        for i, p in enumerate(gs.pending_votes):
            y = 190 + i * 150
            r = pygame.Rect(32, y, w - 64, 132)
            T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
            T.text(surf, p["title"], (r.x + 20, r.y + 14), 19, T.TEXT, bold=True, maxw=r.w - 460)
            T.text(surf, p["category"].upper(), (r.x + 20, r.y + 40), 11, T.ACCENT, bold=True)
            T.text(surf, p["desc"], (r.x + 20, r.y + 60), 14, T.DIM, maxw=r.w - 460)
            score = rules.appeal_score(gs, gs.player, p)
            col = T.OK if score > 0.2 else (T.BAD if score < -0.2 else T.WARN)
            verdict = ("Il nostro reparto e' favorevole" if score > 0.2 else
                       "Il nostro reparto e' contrario" if score < -0.2 else
                       "Impatto sostanzialmente neutro per noi")
            T.text(surf, verdict, (r.x + 20, r.y + 96), 14, col, bold=True)
            likely = sum(1 for t in gs.teams.values()
                         if not t.is_player and rules.appeal_score(gs, t, p) > 0)
            T.text(surf, f"altre scuderie favorevoli: {likely}/{len(gs.teams) - 1}",
                   (r.x + 340, r.y + 98), 13, T.DIM)
            T.text(surf, "Il tuo voto", (r.right - 420, r.y + 40), 12, T.DIM_2, bold=True)

    def _draw_outcome(self, surf, w, h) -> None:
        y = 120
        for p, res, notes in self.results:
            r = pygame.Rect(32, y, w - 64, 140)
            T.panel(surf, r, T.PANEL, radius=10, border=T.OK if res["passed"] else T.LINE)
            T.text(surf, p["title"], (r.x + 20, r.y + 14), 19, T.TEXT, bold=True, maxw=r.w - 300)
            state = "APPROVATA" if res["passed"] else "RESPINTA"
            T.text(surf, state, (r.right - 20, r.y + 14), 19, T.OK if res["passed"] else T.BAD,
                   bold=True, align="right")
            pct = res["yes"] / res["total"] * 100
            T.text(surf, f"{res['yes']} voti su {res['total']} ({pct:.0f}%) - "
                         f"soglia {res['need']*100:.0f}%", (r.x + 20, r.y + 42), 14, T.DIM)
            T.bar(surf, (r.x + 20, r.y + 64, r.w - 40, 10), pct, 100,
                  T.OK if res["passed"] else T.BAD)
            x = r.x + 20
            for name, v in res["detail"]:
                T.text(surf, name, (x, r.y + 84), 11, T.OK if v else T.DIM_2, bold=v)
                x += 96
            for j, n in enumerate(notes[:2]):
                T.text(surf, "-> " + n, (r.x + 20, r.y + 106 + j * 16), 13, T.WARN)
            y += 150
