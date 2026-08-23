"""Riunione della Commissione F1: la FIA propone, le squadre votano.

Si tiene nei primi mesi della stagione e tratta i ritocchi al regolamento in
vigore. Quando e' il momento, nella stessa giornata si siede anche il tavolo
tecnico per il ciclo che verra': li' non si vota, si tratta, e ci vogliono
quattro o cinque riunioni prima che esca un compromesso.
"""
from __future__ import annotations

import pygame

from ...core import development, rules
from .. import theme as T
from ..app import Scene
from ..widgets import Button


class CommissionScene(Scene):
    def __init__(self, app, on_close=None):
        super().__init__(app)
        self.gs = app.gs
        self.on_close = on_close
        self.votes: dict = {}
        self.results: list = []
        self.step = "voto"          # voto | tavolo | esito
        self.spinta = None          # su cosa spingiamo al tavolo tecnico
        self.radicale = 0.5         # quanto vogliamo che cambi
        self.talks_esito = None
        self.build()

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        if self.step == "voto":
            for i, p in enumerate(self.gs.pending_votes):
                y = 176 + i * 150
                voto = self.votes.get(p["id"])
                si = Button((w - 420, y + 66, 130, 38), "Favorevole",
                            style="tab" if voto is True else "ghost")
                no = Button((w - 280, y + 66, 130, 38), "Contrario",
                            style="tab" if voto is False else "ghost")
                si.on_click = (lambda k=p["id"]: self.vote(k, True))
                no.on_click = (lambda k=p["id"]: self.vote(k, False))
                si.active = self.votes.get(p["id"]) is True
                no.active = self.votes.get(p["id"]) is False
                self.widgets += [si, no]
            self.widgets.append(Button((w // 2 - 140, h - 78, 280, 46),
                                       "Chiudi la votazione", self.tally, "primary"))
        elif self.step == "tavolo":
            x = 40
            for key, lab in (("pu", "Power unit"), ("aero", "Aerodinamica"),
                             ("chassis", "Telaio")):
                b = Button((x, 300, 210, 40), lab, style="tab")
                b.on_click = (lambda k=key: self.set_spinta(k))
                b.active = (self.spinta == key)
                self.widgets.append(b)
                x += 222
            x = 40
            for val, lab in ((0.25, "Cambiamento graduale"), (0.55, "Equilibrato"),
                             (0.90, "Rivoltiamo il tavolo")):
                b = Button((x, 392, 210, 40), lab, style="tab")
                b.on_click = (lambda v=val: self.set_radicale(v))
                b.active = abs(self.radicale - val) < 0.01
                self.widgets.append(b)
                x += 222
            self.widgets.append(Button((w // 2 - 140, h - 78, 280, 46),
                                       "Porta la nostra linea", self.do_talks, "primary"))
        else:
            self.widgets.append(Button((w // 2 - 140, h - 78, 280, 46),
                                       "Torna alla squadra", self.done, "primary"))

    def on_resize(self) -> None:
        self.build()

    def vote(self, pid: str, value: bool) -> None:
        self.votes[pid] = value
        self.build()

    def set_spinta(self, key) -> None:
        self.spinta = key
        self.build()

    def set_radicale(self, val) -> None:
        self.radicale = val
        self.build()

    def do_talks(self) -> None:
        self.talks_esito = rules.talks_round(self.gs, self.spinta, self.radicale)
        self.step = "esito"
        self.build()

    def tally(self) -> None:
        self.results = rules.close_meeting(self.gs, self.votes)
        if rules.talks(self.gs):
            st = rules.talks(self.gs)
            if self.spinta is None:
                aree, forza = rules.team_position(self.gs, self.gs.player)
                self.spinta = max(aree, key=aree.get)
                self.radicale = round(forza, 2)
            self.step = "tavolo"
        else:
            self.step = "esito"
        self.build()

    def done(self) -> None:
        self.app.pop()
        if self.on_close:
            self.on_close()
        from .shell import GameShell
        if isinstance(self.app.scene, GameShell):
            self.app.scene.enter()

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        w, h = surf.get_size()
        gs = self.gs
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 76))
        titolo = ("COMMISSIONE F1 - RIUNIONE" if self.step == "voto"
                  else "COMMISSIONE F1 - ESITO")
        T.text(surf, titolo, (32, 16), 26, T.TEXT, bold=True)
        gara = min(gs.round, len(gs.tracks))
        T.text(surf, f"Stagione {gs.season}, dopo la gara {gara} di {len(gs.tracks)}",
               (32, 48), 13, T.DIM)
        st = rules.talks(gs)
        ciclo = gs.regulations.get("pending_cycle")
        if st:
            T.text(surf, f"Tavolo tecnico aperto: riunione {st['riunioni'] + 1} "
                         f"di {st['servono']}", (w - 32, 24), 14, T.GOLD, bold=True,
                   align="right")
            T.bar(surf, (w - 232, 46, 200, 8), st["riunioni"], st["servono"], T.GOLD)
        elif ciclo and ciclo.get("season"):
            T.text(surf, f"Nuovo ciclo tecnico fissato per il {ciclo['season']}",
                   (w - 32, 24), 14, T.GOLD, bold=True, align="right")
        elif ciclo:
            soglia = float(gs.commission.get("cycle_reset_threshold", 1.2))
            T.text(surf, f"Spinta verso un nuovo ciclo: {ciclo['pressure']:.2f} "
                         f"su {soglia:.2f}", (w - 32, 24), 14, T.DIM, align="right")
            T.bar(surf, (w - 232, 46, 200, 8), ciclo["pressure"], soglia, T.GOLD)

        if self.step == "voto":
            self._draw_vote(surf, w, h)
        elif self.step == "tavolo":
            self._draw_talks(surf, w, h)
        else:
            self._draw_outcome(surf, w, h)
        super().draw(surf)

    def _draw_vote(self, surf, w, h) -> None:
        gs = self.gs
        T.text(surf, "La FIA porta al tavolo queste proposte. Ogni scuderia ha un voto, "
                     "FIA e FOM ne hanno dieci ciascuna: serve il 60%.",
               (32, 96), 14, T.DIM, maxw=w - 64)
        for i, p in enumerate(gs.pending_votes):
            y = 176 + i * 150
            r = pygame.Rect(32, y, w - 64, 132)
            T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
            T.text(surf, p["title"], (r.x + 20, r.y + 14), 19, T.TEXT, bold=True,
                   maxw=r.w - 460)
            area = p.get("area", "sporting")
            etichetta = {"pu": "POWER UNIT", "aero": "AERODINAMICA", "chassis": "TELAIO",
                         "sporting": "SPORTIVO", "financial": "FINANZIARIO"}.get(area, "")
            T.text(surf, etichetta, (r.x + 20, r.y + 40), 11, T.ACCENT, bold=True)
            reset = float(p.get("reset", 0.0))
            if reset > 0.3:
                T.text(surf, "CAMBIAMENTO PROFONDO", (r.x + 150, r.y + 40), 11, T.WARN, bold=True)
            T.text(surf, p["desc"], (r.x + 20, r.y + 60), 14, T.DIM, maxw=r.w - 460)
            score = rules.appeal_score(gs, gs.player, p)
            col = T.OK if score > 0.2 else (T.BAD if score < -0.2 else T.WARN)
            verdetto = ("Ci conviene" if score > 0.2 else
                        "Ci penalizza" if score < -0.2 else "Impatto neutro per noi")
            T.text(surf, verdetto, (r.x + 20, r.y + 100), 14, col, bold=True)
            favorevoli = sum(1 for t in gs.teams.values()
                             if not t.is_player and rules.appeal_score(gs, t, p) > 0)
            T.text(surf, f"altre scuderie favorevoli: {favorevoli}/{len(gs.teams) - 1}",
                   (r.x + 340, r.y + 102), 13, T.DIM)
            T.text(surf, "Il tuo voto", (r.right - 420, r.y + 40), 12, T.DIM_2, bold=True)

    def _draw_talks(self, surf, w, h) -> None:
        gs = gs_ = self.gs
        st = rules.talks(gs)
        if not st:
            return
        T.text(surf, "TAVOLO TECNICO PER IL PROSSIMO REGOLAMENTO", (32, 96), 12,
               T.GOLD, bold=True)
        T.text(surf, "Qui non si vota: si tratta. Ognuno tira dalla propria parte e dopo "
                     f"{st['servono']} riunioni esce un compromesso che non e' la proposta "
                     "di nessuno. Da quel momento servono ancora due stagioni prima che le "
                     "macchine nuove vadano in pista.",
               (32, 118), 14, T.DIM, maxw=w - 64)

        # dove sta il compromesso adesso
        T.text(surf, "Dove sta andando il tavolo", (32, 176), 13, T.DIM_2, bold=True)
        x = 32
        for k, lab in (("pu", "POWER UNIT"), ("aero", "AERODINAMICA"), ("chassis", "TELAIO")):
            v = st["aree"].get(k, 0.33)
            T.text(surf, lab, (x, 200), 12, T.TEXT, bold=True)
            T.bar(surf, (x, 220, 200, 10), v * 100, 100, T.ACCENT)
            T.text(surf, f"{v*100:.0f}%", (x + 210, 216), 13, T.TEXT, bold=True)
            x += 260
        forza = st.get("forza", 0.5)
        T.text(surf, "Quanto rimescolera'", (x, 200), 12, T.DIM_2, bold=True)
        T.bar(surf, (x, 220, 180, 10), forza * 100, 100, T.WARN)

        T.text(surf, "La linea che portiamo al tavolo", (32, 276), 13, T.DIM_2, bold=True)
        T.text(surf, "Quanto vogliamo che cambi", (32, 368), 13, T.DIM_2, bold=True)

        # cosa vorrebbero gli altri, per capire dove si va a finire
        y = 452
        T.text(surf, "COSA CHIEDONO GLI ALTRI", (32, y), 12, T.DIM_2, bold=True)
        y += 24
        righe = []
        for t in gs_.teams.values():
            if t.is_player:
                continue
            aree, f = rules.team_position(gs_, t)
            dom = max(aree, key=aree.get)
            righe.append((t.short, rules.ETICHETTA_AREA[dom], f))
        righe.sort(key=lambda r: -r[2])
        for i, (nome, area, f) in enumerate(righe):
            col = 32 + (i % 3) * 320
            riga = y + (i // 3) * 22
            T.text(surf, f"{nome}: {area}", (col, riga), 13, T.DIM, maxw=200)
            T.text(surf, "rivoluzione" if f > 0.65 else ("ritocco" if f < 0.4 else "misura"),
                   (col + 210, riga), 12, T.WARN if f > 0.65 else T.DIM_2)
        y += ((len(righe) + 2) // 3) * 22 + 12
        for riga in st.get("storia", [])[-3:]:
            T.text(surf, "- " + riga, (32, y), 13, T.GOLD, maxw=w - 64)
            y += 20

    def _draw_outcome(self, surf, w, h) -> None:
        y = 110
        for p, res, note in self.results:
            r = pygame.Rect(32, y, w - 64, 132)
            T.panel(surf, r, T.PANEL, radius=10,
                    border=T.OK if res["passed"] else T.LINE)
            T.text(surf, p["title"], (r.x + 20, r.y + 12), 19, T.TEXT, bold=True,
                   maxw=r.w - 300)
            stato = "APPROVATA" if res["passed"] else "RESPINTA"
            T.text(surf, stato, (r.right - 20, r.y + 12), 19,
                   T.OK if res["passed"] else T.BAD, bold=True, align="right")
            pct = res["yes"] / res["total"] * 100
            T.text(surf, f"{res['yes']} voti su {res['total']} ({pct:.0f}%) - "
                         f"soglia {res['need']*100:.0f}%", (r.x + 20, r.y + 40), 14, T.DIM)
            T.bar(surf, (r.x + 20, r.y + 62, r.w - 40, 10), pct, 100,
                  T.OK if res["passed"] else T.BAD)
            x = r.x + 20
            for nome, v in res["detail"]:
                T.text(surf, nome, (x, r.y + 82), 11, T.OK if v else T.DIM_2, bold=v)
                x += 96
            for j, n in enumerate(note[:2]):
                T.text(surf, "-> " + n, (r.x + 20, r.y + 102 + j * 15), 13, T.WARN,
                       maxw=r.w - 40)
            y += 142

        if self.talks_esito:
            T.text(surf, self.talks_esito.get("riga", ""), (32, y + 8), 16,
                   T.GOLD, bold=True, maxw=w - 64)
            y += 46
        era = development.next_era(self.gs)
        if era and era.get("in_discussione"):
            f = era.get("focus", {})
            dom = max(f, key=f.get) if f else "aero"
            nome = {"pu": "la power unit", "chassis": "il telaio",
                    "aero": "l'aerodinamica"}[dom]
            T.text(surf, f"Con quanto approvato finora, dal {era['from']} a decidere "
                         f"sara' soprattutto {nome}.", (32, y + 8), 15, T.GOLD, bold=True)
