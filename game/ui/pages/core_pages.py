"""Pagine: quartier generale, vettura e assetto, sviluppo, ingegneri."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import development, economy, engineering
from ...model.car import SETUP_KEYS
from ...sim import session as S
from .. import theme as T
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, card, stat_row


# =========================================================== QUARTIER GENERALE
class HQPage(Page):
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.news = ScrollList((r.x + r.w * 0.68, r.y + 190, r.w * 0.32 - 4, r.h - 200),
                               row_h=54, draw_row=self._draw_news)
        self.widgets.append(self.news)

    def refresh(self) -> None:
        self.build()
        self.news.items = list(self.gs.inbox)

    def _draw_news(self, surf, rect, i, item) -> None:
        colours = {"tecnico": T.ACCENT, "gara": T.GOLD, "team": T.OK,
                   "mercato": (200, 140, 255), "regole": T.WARN}
        c = colours.get(item.get("kind"), T.DIM)
        pygame.draw.rect(surf, c, (rect.x + 4, rect.y + 8, 3, rect.h - 16))
        T.text(surf, item.get("kind", "info").upper(), (rect.x + 16, rect.y + 6), 11, c, bold=True)
        words = item["text"].split()
        line, lines = "", []
        f = T.font(13)
        for wd in words:
            if f.size(line + " " + wd)[0] > rect.w - 30:
                lines.append(line)
                line = wd
            else:
                line = (line + " " + wd).strip()
        lines.append(line)
        for j, ln in enumerate(lines[:2]):
            T.text(surf, ln, (rect.x + 16, rect.y + 21 + j * 15), 13, T.TEXT)

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        col = T.hex_rgb(team.colour)
        cw = (r.w - 48) / 4
        card(surf, (r.x, r.y, cw, 86), "Liquidita'", T.fmt_money(team.cash),
             f"budget annuo {team.budget_base:.0f} M$", accent=T.OK)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Valutazione vettura",
             f"{team.car.rating:.1f}", _car_rank_text(gs, team), accent=col)
        spent, limit, frac = economy.cap_usage(gs, team)
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Budget cap",
             f"{frac*100:.0f}%", f"{spent:.1f} di {limit:.0f} M$",
             colour=T.BAD if frac > 1 else T.TEXT, accent=T.WARN)
        nt = gs.next_track
        card(surf, (r.x + 3 * (cw + 16), r.y, cw, 86), "Prossimo appuntamento",
             nt.name if nt else "-", nt.gp if nt else "stagione conclusa", accent=T.ACCENT)

        # prossima gara con tracciato
        left = pygame.Rect(r.x, r.y + 92, r.w * 0.33, r.h - 100)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROSSIMA GARA", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        if nt:
            T.text(surf, nt.gp, (left.x + 16, left.y + 30), 18, T.TEXT, bold=True, maxw=left.w - 32)
            trackdraw.draw_track(surf, nt, (left.x + 10, left.y + 58, left.w - 20, left.h * 0.42),
                                 width=7, colour=(58, 70, 92))
            y = left.y + 58 + left.h * 0.42 + 10
            info = [("Lunghezza", f"{nt.length_km:.3f} km"), ("Giri", str(nt.laps)),
                    ("Curve", str(nt.corners)), ("Perdita ai box", f"{nt.pit_loss:.1f} s"),
                    ("Sprint", "si" if nt.sprint else "no")]
            for k, v in info:
                T.text(surf, k, (left.x + 16, y), 13, T.DIM)
                T.text(surf, v, (left.right - 16, y), 13, T.TEXT, bold=True, align="right")
                y += 19
            y += 6
            for k, lab in (("downforce", "Carico"), ("power", "Potenza"),
                           ("tyre_wear", "Degrado"), ("overtaking", "Sorpassi")):
                T.text(surf, lab, (left.x + 16, y), 12, T.DIM)
                T.bar(surf, (left.x + 100, y + 3, left.w - 130, 7), nt.traits[k] * 100)
                y += 18

        # piloti e reparti
        mid = pygame.Rect(r.x + r.w * 0.34, r.y + 92, r.w * 0.32, r.h - 100)
        T.panel(surf, mid, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I NOSTRI PILOTI", (mid.x + 16, mid.y + 12), 12, T.DIM_2, bold=True)
        y = mid.y + 34
        for d in gs.drivers_of(team.id):
            T.panel(surf, (mid.x + 10, y, mid.w - 20, 92), T.PANEL_2, radius=8)
            T.text(surf, f"{d.number}", (mid.x + 22, y + 10), 22, col, bold=True)
            T.text(surf, d.name, (mid.x + 60, y + 10), 17, T.TEXT, bold=True, maxw=mid.w - 150)
            T.text(surf, f"{d.nat} - {d.age} anni - {d.salary:.1f} M$/anno",
                   (mid.x + 60, y + 32), 12, T.DIM)
            T.text(surf, f"{d.overall:.0f}", (mid.right - 22, y + 10), 22,
                   T.stat_colour(d.overall, 70, 90), bold=True, align="right")
            bx = mid.x + 20
            for lab, v in (("Passo", d.pace), ("Duello", d.racecraft),
                           ("Costanza", d.consistency), ("Gomme", d.tyre_mgmt)):
                T.text(surf, lab, (bx, y + 54), 10, T.DIM_2)
                T.bar(surf, (bx, y + 68, 66, 6), v, 100, T.stat_colour(v, 65, 90))
                bx += 74
            T.text(surf, f"morale {d.morale:.0f}", (mid.right - 22, y + 62), 12,
                   T.stat_colour(d.morale, 40, 75), align="right")
            y += 100
        y += 6
        T.text(surf, "REPARTI", (mid.x + 16, y), 12, T.DIM_2, bold=True)
        y += 20
        for lab, v in (("Aerodinamica", team.aero_strength), ("Progettazione", team.mech_strength),
                       ("Strategia", team.strategy_strength), ("Pit crew", team.pit_strength),
                       ("Affidabilita'", team.reliability_strength), ("Simulatore/assetto", team.setup_strength)):
            stat_row(surf, pygame.Rect(mid.x + 16, y, mid.w - 32, 22), lab, v)
            y += 24

        right = pygame.Rect(r.x + r.w * 0.68, r.y + 92, r.w * 0.32 - 4, r.h - 100)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "NOTIZIE DALLA SQUADRA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        super().draw(surf)


def _car_rank_text(gs, team) -> str:
    rank = sorted(gs.teams.values(), key=lambda t: -t.car.rating)
    pos = [t.id for t in rank].index(team.id) + 1
    return f"{pos}a vettura della griglia"


# ================================================================== VETTURA
class CarPage(Page):
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.sliders = {}
        x = r.x + r.w * 0.42 + 16
        y = r.y + 150
        for k, lab in SETUP_KEYS.items():
            s = Slider((x, y, r.w * 0.58 - 32, 30), lab, self.team.car.setup.get(k, 50.0),
                       on_change=(lambda v, k=k: self._set(k, v)))
            self.sliders[k] = s
            self.widgets.append(s)
            y += 36
        y += 8
        bw = (r.w * 0.58 - 42) / 2
        self.widgets.append(Button((x, y, bw, 38), "Delega agli ingegneri", self.delegate, "primary"))
        self.widgets.append(Button((x + bw + 10, y, bw, 38), "Assetto neutro", self.neutral, "ghost"))
        self._update_markers()

    def _set(self, k, v) -> None:
        self.team.car.setup[k] = v
        nt = self.gs.next_track
        if nt:
            self.team.car.evaluate_setup(nt)

    def _update_markers(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        opt = self.team.car.optimal_setup(nt)
        known = min(1.0, 0.30 + 0.70 * self.team.setup_strength / 100.0)
        for k, s in self.sliders.items():
            s.marker = opt[k] if known > 0.55 else None
        self.team.car.evaluate_setup(nt)

    def delegate(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        S.auto_setup(self.gs, self.team, nt)
        for k, s in self.sliders.items():
            s.value = self.team.car.setup[k]
        self.app.toast("Gli ingegneri hanno impostato la vettura.")

    def neutral(self) -> None:
        for k, s in self.sliders.items():
            self.team.car.setup[k] = 50.0
            s.value = 50.0
        self._set("wing", 50.0)

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, team, gs = self.rect, self.team, self.gs
        car = team.car
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "COMPONENTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, "prestazione / condizione", (left.right - 16, left.y + 12), 11, T.DIM_2,
               align="right")
        y = left.y + 38
        for k, meta in C.CAR_PARTS.items():
            p = car.parts[k]
            T.text(surf, meta["label"], (left.x + 16, y), 14, T.TEXT)
            T.bar(surf, (left.x + 170, y + 5, 120, 8), p.perf, 100, T.stat_colour(p.perf, 60, 88))
            T.text(surf, f"{p.perf:.0f}", (left.x + 300, y), 13, T.TEXT, bold=True)
            cond_col = T.OK if p.condition > 80 else (T.WARN if p.condition > 55 else T.BAD)
            T.bar(surf, (left.x + 330, y + 5, 90, 8), p.condition, 100, cond_col)
            T.text(surf, f"{p.condition:.0f}%", (left.right - 16, y), 13, cond_col,
                   bold=True, align="right")
            y += 26
        y += 10
        T.text(surf, "PRESTAZIONI DERIVATE", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        prof = engineering.car_profile(team, gs)
        for key, lab in engineering.AREAS.items():
            stat_row(surf, pygame.Rect(left.x + 16, y, left.w - 32, 22), lab, prof[key])
            y += 24
        y += 8
        cost = car.repair_cost()
        T.text(surf, f"Costo di ripristino stimato: {cost:.2f} M$", (left.x + 16, y), 13,
               T.WARN if cost > 0.5 else T.DIM)

        right = pygame.Rect(r.x + r.w * 0.42 + 16, r.y, r.w * 0.58 - 16, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ASSETTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        nt = gs.next_track
        if nt:
            q = car.setup_quality
            qc = T.OK if q > 0.85 else (T.WARN if q > 0.6 else T.BAD)
            T.text(surf, f"per {nt.name}", (right.x + 16, right.y + 32), 16, T.TEXT, bold=True)
            T.text(surf, "Efficacia assetto", (right.x + 16, right.y + 62), 13, T.DIM)
            T.bar(surf, (right.x + 160, right.y + 66, 220, 10), q * 100)
            T.text(surf, f"{q*100:.0f}%", (right.x + 396, right.y + 60), 15, qc, bold=True)
            lost = (1.0 - car.apply_setup_effects() / 1.0) * 0
            T.text(surf, "Il triangolo dorato indica il valore suggerito dal reparto.",
                   (right.x + 16, right.y + 92), 12, T.DIM_2)
            T.text(surf, f"Downforce {car.downforce:.2f}  |  Drag {car.drag:.2f}  |  "
                         f"Potenza {car.power:.2f}  |  Grip {car.mech_grip:.2f}",
                   (right.x + 16, right.y + 114), 13, T.DIM)
        else:
            T.text(surf, "Nessuna gara in programma.", (right.x + 16, right.y + 40), 15, T.DIM)
        yy = right.y + 150 + len(SETUP_KEYS) * 36 + 60
        if nt:
            T.text(surf, "RISCONTRO DEGLI INGEGNERI", (right.x + 16, yy), 12, T.DIM_2, bold=True)
            yy += 22
            for line in S.setup_hints(car, nt)[:6]:
                T.text(surf, line, (right.x + 16, yy), 13, T.DIM, maxw=right.w - 32)
                yy += 20
        super().draw(surf)


# ================================================================= SVILUPPO
class DevPage(Page):
    SIZES = ["piccolo", "medio", "grande"]

    def __init__(self, shell):
        super().__init__(shell)
        self.sel_part = "floor"
        self.sel_size = "medio"

    @property
    def dev_budget(self) -> float:
        return self.app.dev_budget

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.alloc_sliders = {}
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        y = left.y + 40
        for k, meta in C.CAR_PARTS.items():
            s = Slider((left.x + 16, y, left.w - 32, 28), meta["label"],
                       self.team.resource_alloc.get(k, 0.1) * 100.0, 0, 100,
                       on_change=(lambda v, k=k: self._alloc(k, v)), fmt="{:.0f}%")
            self.alloc_sliders[k] = s
            self.widgets.append(s)
            y += 32
        self.widgets.append(Button((left.x + 16, y + 8, (left.w - 42) / 2, 34),
                                   "Bilancia", self.balance, "ghost"))
        self.widgets.append(Button((left.x + 26 + (left.w - 42) / 2, y + 8, (left.w - 42) / 2, 34),
                                   "Consiglio ingegneri", self.suggest, "primary"))

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        self.budget_slider = Slider((right.x + 16, right.y + 34, right.w - 32, 28),
                                    "Budget sviluppo per gara", self.dev_budget, 0.0, 6.0,
                                    on_change=self._set_budget, fmt="{:.2f} M$")
        self.widgets.append(self.budget_slider)
        bx, by = right.x + 16, right.y + 150
        self.part_buttons = []
        for i, (k, meta) in enumerate(C.CAR_PARTS.items()):
            b = Button((bx + (i % 3) * ((right.w - 44) / 3 + 6), by + (i // 3) * 34,
                        (right.w - 44) / 3, 30), meta["label"], style="tab")
            b.on_click = (lambda k=k: self._pick_part(k))
            b.active = (k == self.sel_part)
            self.part_buttons.append(b)
            self.widgets.append(b)
        sy = by + 4 * 34 + 10
        self.size_buttons = []
        for i, sz in enumerate(self.SIZES):
            b = Button((bx + i * ((right.w - 44) / 3 + 6), sy, (right.w - 44) / 3, 30),
                       sz.capitalize(), style="tab")
            b.on_click = (lambda s=sz: self._pick_size(s))
            b.active = (sz == self.sel_size)
            self.size_buttons.append(b)
            self.widgets.append(b)
        self.widgets.append(Button((bx, sy + 76, right.w - 32, 40), "Avvia progetto",
                                   self.start_project, "primary"))

    def _alloc(self, k, v) -> None:
        self.team.resource_alloc[k] = max(0.0, v) / 100.0

    def _set_budget(self, v) -> None:
        # il weekend di gara legge il budget dall'App: e' li' che va scritto
        self.app.dev_budget = v

    def _pick_part(self, k) -> None:
        self.sel_part = k
        for b, key in zip(self.part_buttons, C.CAR_PARTS.keys()):
            b.active = (key == k)

    def _pick_size(self, s) -> None:
        self.sel_size = s
        for b, sz in zip(self.size_buttons, self.SIZES):
            b.active = (sz == s)

    def balance(self) -> None:
        n = len(C.CAR_PARTS)
        for k in C.CAR_PARTS:
            self.team.resource_alloc[k] = 1.0 / n
            self.alloc_sliders[k].value = 100.0 / n

    def suggest(self) -> None:
        sug = engineering.suggested_allocation(self.gs)
        for k, v in sug.items():
            self.team.resource_alloc[k] = v
            if k in self.alloc_sliders:
                self.alloc_sliders[k].value = v * 100.0
        self.app.toast("Allocazione aggiornata secondo il parere del reparto tecnico.")

    def start_project(self) -> None:
        ok, msg = development.start_project(self.gs, self.team, self.sel_part, self.sel_size)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        atr = development.atr_factor(gs, team)
        cap = development.dev_capacity(gs, team)
        cw = (r.w - 32) / 3
        card(surf, (r.x, r.y, cw, 86), "Capacita' di sviluppo", f"{cap:.2f}",
             f"efficienza reparto {team.dev_rate:.2f}", accent=T.ACCENT)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Ore galleria (ATR)", f"{atr*100:.0f}%",
             f"{team.last_position}o nel costruttori precedente",
             colour=T.OK if atr >= 1.0 else T.WARN, accent=T.WARN)
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Progetti attivi",
             f"{len(team.dev_projects)} / 3",
             f"{team.upgrades_done} aggiornamenti portati in pista", accent=T.OK)

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ALLOCAZIONE DELLE RISORSE", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROGETTI DI AGGIORNAMENTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        y = right.y + 76
        if team.dev_projects:
            for pr in team.dev_projects:
                T.panel(surf, (right.x + 16, y, right.w - 32, 30), T.PANEL_2, radius=6)
                T.text(surf, pr.label, (right.x + 26, y + 7), 13, T.TEXT, maxw=right.w - 200)
                T.bar(surf, (right.right - 170, y + 12, 90, 8), pr.progress * 100)
                T.text(surf, f"{pr.races_left} gare", (right.right - 26, y + 7), 12, T.DIM,
                       align="right")
                y += 34
        else:
            T.text(surf, "Nessun progetto in corso.", (right.x + 16, y + 4), 13, T.DIM)
            y += 34
        T.text(surf, "NUOVO PACCHETTO", (right.x + 16, right.y + 128), 12, T.DIM_2, bold=True)
        sy = right.y + 150 + 4 * 34 + 10
        cost = development.cost_of_upgrade(self.sel_part, self.sel_size)
        gain = development.expected_gain(gs, team, self.sel_part, self.sel_size)
        risk = development.project_risk(team, self.sel_size)
        races = {"piccolo": 1, "medio": 3, "grande": 6}[self.sel_size]
        T.text(surf, f"Costo {cost:.2f} M$   |   Guadagno atteso +{gain:.1f}   |   "
                     f"Tempo {races} gare   |   Rischio {risk*100:.0f}%",
               (right.x + 16, sy + 44), 14, T.TEXT)
        super().draw(surf)


# ================================================================ INGEGNERI
class EngineersPage(Page):
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.widgets.append(Button((r.right - 300, r.y + 8, 300, 36),
                                   "Applica il piano suggerito", self.apply_plan, "primary"))
        self._brief = None
        self._report = None

    def apply_plan(self) -> None:
        sug = engineering.suggested_allocation(self.gs)
        self.team.resource_alloc = sug
        self.app.toast("Piano di sviluppo aggiornato secondo gli ingegneri.")

    def refresh(self) -> None:
        self.build()
        self._brief = engineering.briefing(self.gs)
        self._report = engineering.field_report(self.gs)

    def draw(self, surf) -> None:
        r = self.rect
        if self._brief is None:
            self.refresh()
        T.text(surf, "CONFRONTO TECNICO", (r.x, r.y + 10), 22, T.TEXT, bold=True)
        left = pygame.Rect(r.x, r.y + 56, r.w * 0.46, r.h - 56)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "RIUNIONE CON I RESPONSABILI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        y = left.y + 40
        for speaker, line in self._brief:
            T.text(surf, speaker, (left.x + 16, y), 14, T.ACCENT, bold=True)
            y += 20
            f = T.font(13)
            words, cur = line.split(), ""
            for wd in words:
                if f.size(cur + " " + wd)[0] > left.w - 44:
                    T.text(surf, cur, (left.x + 24, y), 13, T.TEXT)
                    y += 18
                    cur = wd
                else:
                    cur = (cur + " " + wd).strip()
            T.text(surf, cur, (left.x + 24, y), 13, T.TEXT)
            y += 30

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 56, r.w * 0.52 - 4, r.h - 56)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "DOVE SIAMO RISPETTO ALLA GRIGLIA", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        hy = right.y + 40
        for lab, x in (("AREA", 16), ("NOI", 250), ("MIGLIORE", 320), ("GAP", 440), ("POS", 520)):
            T.text(surf, lab, (right.x + x, hy), 11, T.DIM_2, bold=True)
        y = hy + 22
        for area, lab in engineering.AREAS.items():
            d = self._report[area]
            T.text(surf, lab, (right.x + 16, y), 14, T.TEXT, maxw=220)
            T.text(surf, f"{d['mine']:.0f}", (right.x + 250, y), 14,
                   T.stat_colour(d["mine"], 40, 80), bold=True)
            T.text(surf, f"{d['best']:.0f} {d['best_team']}", (right.x + 320, y), 13, T.DIM,
                   maxw=110)
            gap = d["delta"]
            T.text(surf, f"{gap:+.0f}", (right.x + 440, y), 14,
                   T.OK if gap >= -2 else (T.WARN if gap > -14 else T.BAD), bold=True)
            T.text(surf, f"{d['rank']}o", (right.x + 520, y), 14, T.TEXT)
            T.bar(surf, (right.x + 16, y + 20, right.w - 40, 5), d["mine"], 100,
                  T.stat_colour(d["mine"], 40, 80))
            y += 40
        T.text(surf, "Le stime sugli avversari migliorano con lo scouting e con le gare disputate.",
               (right.x + 16, right.bottom - 30), 12, T.DIM_2)
        super().draw(surf)
