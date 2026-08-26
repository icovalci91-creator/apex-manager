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
        self.motore = None          # e che architettura chiediamo
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
            g = self._geometria(w, h)
            larga = g["larga"]
            x = g["sx"]
            for key, lab in (("pu", "Power unit"), ("aero", "Aerodinamica"),
                             ("chassis", "Telaio")):
                b = Button((x, g["y_linea"], larga, 38), lab, style="tab")
                b.on_click = (lambda k=key: self.set_spinta(k))
                b.active = (self.spinta == key)
                self.widgets.append(b)
                x += larga + 10
            x = g["sx"]
            for val, lab in ((0.25, "Graduale"), (0.55, "Equilibrato"),
                             (0.90, "Rivoltiamo tutto")):
                b = Button((x, g["y_radicale"], larga, 38), lab, style="tab")
                b.on_click = (lambda v=val: self.set_radicale(v))
                b.active = abs(self.radicale - val) < 0.01
                self.widgets.append(b)
                x += larga + 10
            # e che motore chiediamo: e' la parte della bozza su cui si puo'
            # cominciare a lavorare anni prima
            from ...core import architetture as AR
            for i, aid in enumerate(AR.catalogo()):
                bx = g["dx"] + (i % 2) * (g["larga_m"] + 12)
                by = g["y_motori"] + (i // 2) * g["passo_m"]
                b = Button((bx, by, g["larga_m"], 30), AR.etichetta(self.gs, aid),
                           style="tab")
                b.on_click = (lambda k=aid: self.set_motore(k))
                b.active = (self.motore == aid)
                self.widgets.append(b)
            self.widgets.append(Button((w // 2 - 140, h - 78, 280, 46),
                                       "Porta la nostra linea", self.do_talks, "primary"))
        else:
            self.widgets.append(Button((w // 2 - 140, h - 78, 280, 46),
                                       "Torna alla squadra", self.done, "primary"))

    def _geometria(self, w: int, h: int) -> dict:
        """Dove sta ogni cosa nella schermata del tavolo, a qualunque misura.

        Due colonne: a sinistra dove sta andando il tavolo e la linea che ci
        portiamo, a destra il motore - che e' la parte su cui si decide se
        cominciare a spendere anni prima.
        """
        sx = 32
        dx = w // 2 + 16
        larga = int((w // 2 - 48 - 20) / 3)
        return {"sx": sx, "dx": dx, "larga": larga,
                "larga_m": int((w - dx - 32 - 12) / 2),
                "passo_m": 46,
                "y_aree": 190, "y_linea": 318, "y_radicale": 400,
                "y_motori": 186, "y_altri": 494}

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

    def set_motore(self, aid) -> None:
        self.motore = None if self.motore == aid else aid
        self.build()

    def do_talks(self) -> None:
        self.talks_esito = rules.talks_round(self.gs, self.spinta, self.radicale,
                                             self.motore)
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
        titolo = {"voto": "COMMISSIONE F1 - RIUNIONE",
                  "tavolo": "COMMISSIONE F1 - TAVOLO TECNICO"}.get(
                      self.step, "COMMISSIONE F1 - ESITO")
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
        from ...core import architetture as AR
        from ...core import powertrain as PT
        gs = self.gs
        st = rules.talks(gs)
        if not st:
            return
        g = self._geometria(w, h)
        sx, dx = g["sx"], g["dx"]
        T.text(surf, "TAVOLO TECNICO PER IL PROSSIMO REGOLAMENTO", (sx, 96), 12,
               T.GOLD, bold=True)
        T.text(surf, "Qui non si vota: si tratta. Dopo "
                     f"{st['servono']} riunioni esce un compromesso che non e' la "
                     "proposta di nessuno, e da li' servono ancora due stagioni prima "
                     "che le macchine nuove vadano in pista.",
               (sx, 116), 13, T.DIM, maxw=w - 64)

        # ---- colonna sinistra: dove sta andando il tavolo
        T.text(surf, "DOVE STA ANDANDO IL TAVOLO", (sx, 164), 12, T.DIM_2, bold=True)
        y = g["y_aree"]
        for k, lab in (("pu", "Power unit"), ("aero", "Aerodinamica"), ("chassis", "Telaio")):
            v = st["aree"].get(k, 0.33)
            T.text(surf, lab, (sx, y), 13, T.TEXT)
            T.bar(surf, (sx + 110, y + 5, 180, 9), v * 100, 100, T.ACCENT)
            T.text(surf, f"{v*100:.0f}%", (sx + 330, y), 13, T.TEXT, bold=True,
                   align="right")
            y += 24
        forza = st.get("forza", 0.5)
        T.text(surf, "Quanto rimescolera'", (sx, y), 13, T.DIM)
        T.bar(surf, (sx + 130, y + 5, 160, 9), forza * 100, 100, T.WARN)

        T.text(surf, "LA LINEA CHE PORTIAMO", (sx, g["y_linea"] - 24), 12, T.DIM_2, bold=True)
        T.text(surf, "QUANTO VOGLIAMO CHE CAMBI", (sx, g["y_radicale"] - 24), 12,
               T.DIM_2, bold=True)

        # ---- colonna destra: il motore, e chi ci sta gia' lavorando
        motori = st.get("motori") or {}
        T.text(surf, "CHE MOTORE CHIEDIAMO", (dx, 164), 12, T.DIM_2, bold=True)
        if motori:
            ordinati = sorted(motori.items(), key=lambda kv: -kv[1])
            testa = ordinati[0][0]
            for i, aid in enumerate(AR.catalogo()):
                bx = dx + (i % 2) * (g["larga_m"] + 12)
                by = g["y_motori"] + (i // 2) * g["passo_m"] + 32
                quota = motori.get(aid, 0.0)
                T.bar(surf, (bx, by, g["larga_m"] - 46, 7), quota * 100, 100,
                      T.GOLD if aid == testa else T.PANEL_3)
                T.text(surf, f"{quota*100:.0f}%", (bx + g["larga_m"], by - 5), 11,
                       T.GOLD if aid == testa else T.DIM_2, bold=True, align="right")
            y = g["y_motori"] + g["passo_m"] * 4 + 12
            T.text(surf, f"La bozza dice {AR.etichetta(gs, testa)}: "
                         f"{AR.descrizione(gs, testa)}.", (dx, y), 13, T.DIM,
                   maxw=w - dx - 32)
            y += 34
            prog = PT.programma_arch(gs.player)
            if prog.get("arch"):
                col = T.OK if prog["arch"] == testa else T.WARN
                T.text(surf, f"Noi lavoriamo al {AR.etichetta(gs, prog['arch'])} dal "
                             f"{prog.get('da', gs.season)}: "
                             f"{float(prog.get('investito', 0.0)):.0f} M$ spesi.",
                       (dx, y), 13, col, maxw=w - dx - 32)
            else:
                T.text(surf, "Nessun programma aperto: dalla pagina Power unit si puo' "
                             "cominciare a lavorare sull'architettura che si pensa "
                             "arrivera', anche prima che il tavolo decida.",
                       (dx, y), 12, T.DIM_2, maxw=w - dx - 32)

        # ---- cosa chiedono gli altri, sotto la colonna sinistra
        y = g["y_altri"]
        T.text(surf, "COSA CHIEDONO GLI ALTRI", (sx, y), 12, T.DIM_2, bold=True)
        y += 22
        righe = []
        for t in gs.teams.values():
            if t.is_player:
                continue
            aree, f = rules.team_position(gs, t)
            dom = max(aree, key=aree.get)
            righe.append((t.short, rules.ETICHETTA_AREA[dom], f))
        righe.sort(key=lambda r: -r[2])
        colonne = 2 if w < 1200 else 3
        passo = int((w - 64) / colonne)
        for i, (nome, area, f) in enumerate(righe):
            col = sx + (i % colonne) * passo
            riga = y + (i // colonne) * 21
            if riga > h - 120:
                break
            T.text(surf, f"{nome}: {area}", (col, riga), 13, T.DIM, maxw=passo - 110)
            T.text(surf, "rivoluzione" if f > 0.65 else ("ritocco" if f < 0.4 else "misura"),
                   (col + passo - 100, riga), 12, T.WARN if f > 0.65 else T.DIM_2)
        y += ((len(righe) + colonne - 1) // colonne) * 21 + 10
        for riga in st.get("storia", [])[-2:]:
            if y > h - 112:
                break
            T.text(surf, "- " + riga, (sx, y), 13, T.GOLD, maxw=w - 64)
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
