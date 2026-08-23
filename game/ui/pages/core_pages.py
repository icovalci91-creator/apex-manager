"""Pagine: quartier generale, vettura e assetto, sviluppo, ingegneri."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import development, driving, economy, engineering, penalties, powertrain, rules, setup as SETUP
from ...model.car import SETUP_KEYS
from ...sim import session as S
from .. import theme as T
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, Toggle, card, stat_row


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
        # il livello non ha piu' un tetto: quello che conta e' dove sta rispetto
        # agli altri e al riferimento del ciclo tecnico
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
    if pos == 1:
        gap = team.car.rating - rank[1].car.rating
        return f"1a vettura della griglia, +{gap:.1f} sulla seconda"
    return f"{pos}a vettura della griglia, {team.car.rating - rank[0].car.rating:+.1f} dalla prima"


# ================================================================== VETTURA
class CarPage(Page):
    """Una macchina per pilota: stesso pacchetto, due assetti."""

    def __init__(self, shell):
        super().__init__(shell)
        self.sel_driver = None

    def _piloti(self) -> list:
        return self.gs.lineup_of(self.team.id)

    def _driver(self):
        piloti = self._piloti()
        if self.sel_driver is None or self.sel_driver not in piloti:
            self.sel_driver = piloti[0] if piloti else None
        return self.sel_driver

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.sliders = {}
        x = r.x + r.w * 0.42 + 16
        larg = r.w * 0.58 - 32
        d = self._driver()

        # con quale delle due macchine stiamo lavorando
        self.drv_buttons = []
        piloti = self._piloti()
        bw2 = (larg - 10) / max(1, len(piloti))
        for i, p in enumerate(piloti):
            b = Button((x + i * (bw2 + 10), r.y + 140, bw2, 28), p.short)
            b.on_click = (lambda pp=p: self._pick_driver(pp))
            self.drv_buttons.append(b)
            self.widgets.append(b)
        self._mark_driver()

        mio = driving.setup_of(self.team, d) if d else {}
        y = r.y + 182
        for k, lab in SETUP_KEYS.items():
            s = Slider((x, y, larg, 30), lab, mio.get(k, 50.0),
                       on_change=(lambda v, k=k: self._set(k, v)))
            self.sliders[k] = s
            self.widgets.append(s)
            y += 36
        y += 8
        bw = (larg - 10) / 2
        costo = SETUP.sim_cost(self.team)
        self.widgets.append(Button((x, y, bw, 38), f"Simulatore  ({costo:.2f} M$)",
                                   self.simulate, "normal"))
        self.widgets.append(Button((x + bw + 10, y, bw, 38), "Monta su questa macchina",
                                   self.delegate, "primary"))
        self.widgets.append(Button((x, y + 44, bw, 34), "Monta su tutte e due",
                                   self.delegate_all, "ghost"))
        self.widgets.append(Button((x + bw + 10, y + 44, bw, 34), "Assetto neutro",
                                   self.neutral, "ghost"))
        self.widgets.append(Toggle((x, y + 88, larg, 30),
                                   "Se ne occupano gli ingegneri di pista",
                                   self.team.auto_setup, on_change=self._set_auto_setup))

        # le parti che il regolamento conta: si cambiano quando sono finite,
        # sapendo cosa costa farlo fuori contingente
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        cy = left.bottom - 118
        for p in self._piloti():
            for i, quale in enumerate(("pu", "cambio")):
                b = Button((left.right - 96, cy + i * 24 - 2, 78, 22), "Nuovo")
                b.on_click = (lambda pp=p, q=quale: self._fit(pp, q))
                self.widgets.append(b)
            cy += 60
        self._update_markers()

    def _fit(self, driver, quale) -> None:
        ok, msg = penalties.fit_new(self.gs, self.team, driver, quale)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _set_auto_setup(self, v) -> None:
        self.team.auto_setup = bool(v)
        self.build()

    def _pick_driver(self, p) -> None:
        self.sel_driver = p
        self.build()

    def _mark_driver(self) -> None:
        for b, p in zip(self.drv_buttons, self._piloti()):
            b.active = (p is self.sel_driver)
            b.style = "tab" if b.active else "normal"

    def _set(self, k, v) -> None:
        d = self._driver()
        if d is not None:
            driving.set_value(self.team, d, k, v)

    def _update_markers(self) -> None:
        """Il triangolo mostra quello che il reparto crede, corretto per lui."""
        nt = self.gs.next_track
        d = self._driver()
        if not nt or d is None:
            return
        SETUP.ensure_paper(self.gs, self.team, nt)
        bersaglio = SETUP.target_for(self.team, d)
        for k, s in self.sliders.items():
            s.marker = bersaglio.get(k)

    def simulate(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        ok, msg = SETUP.run_simulator(self.gs, self.team, nt)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def delegate(self) -> None:
        nt, d = self.gs.next_track, self._driver()
        if not nt or d is None:
            return
        S.auto_setup(self.gs, self.team, nt, driver=d)
        self.app.toast(f"Assetto del reparto montato sulla macchina di {d.short}.")
        self.build()

    def delegate_all(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        S.auto_setup(self.gs, self.team, nt)
        self.app.toast("Assetto del reparto montato su tutte e due le macchine.")
        self.build()

    def neutral(self) -> None:
        d = self._driver()
        if d is None:
            return
        for k, s in self.sliders.items():
            driving.set_value(self.team, d, k, 50.0)
            s.value = 50.0

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, team, gs = self.rect, self.team, self.gs
        car = team.car
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "COMPONENTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, f"riferimento del ciclo {development.reference_level(gs):.0f}",
               (left.right - 16, left.y + 12), 11, T.DIM_2, align="right")
        y = left.y + 38
        rif = development.reference_level(gs)
        for k, meta in C.CAR_PARTS.items():
            p = car.parts[k]
            T.text(surf, meta["label"], (left.x + 16, y), 14, T.TEXT)
            # la scala non e' 0-100: si legge rispetto al riferimento del ciclo
            T.bar(surf, (left.x + 170, y + 5, 120, 8), p.perf - rif + 20.0, 40.0,
                  T.stat_colour(p.perf, rif - 12.0, rif))
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

        # --- power unit e cambio: quello che il regolamento conta
        reg = gs.regulations
        max_pu = int(reg["power_unit"].get("units_per_season", 4))
        max_cb = int(reg["sporting"].get("gearbox_units", 5))
        cy = left.bottom - 140
        T.text(surf, "PARTI CONTINGENTATE", (left.x + 16, cy), 12, T.DIM_2, bold=True)
        T.text(surf, f"oltre il limite: {penalties.GRIGLIA_PU} posizioni",
               (left.right - 16, cy), 11, T.DIM_2, align="right")
        cy += 22
        for d in self._piloti():
            T.text(surf, d.short, (left.x + 16, cy), 13, T.TEXT, bold=True, maxw=120)
            for i, (lab, logoro, usate, limite) in enumerate(
                    (("Power unit", d.pu_wear, d.pu_used, max_pu),
                     ("Cambio", d.gearbox_wear, d.gearbox_used, max_cb))):
                yy = cy + i * 24
                col = (T.OK if logoro > 55 else
                       T.WARN if logoro > penalties.SOGLIA_ROTTURA else T.BAD)
                T.text(surf, lab, (left.x + 130, yy), 12, T.DIM)
                T.bar(surf, (left.x + 210, yy + 5, 96, 7), logoro, 100, col)
                col_n = T.BAD if usate >= limite else T.DIM
                T.text(surf, f"{usate}/{limite}", (left.x + 330, yy), 12, col_n, bold=True)
            cy += 60

        right = pygame.Rect(r.x + r.w * 0.42 + 16, r.y, r.w * 0.58 - 16, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ASSETTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        nt = gs.next_track
        d = self._driver()
        if nt and d is not None:
            q = SETUP.believed_quality(team, d)
            qc = T.OK if q > 0.85 else (T.WARN if q > 0.6 else T.BAD)
            T.text(surf, f"per {nt.name}", (right.x + 16, right.y + 32), 16, T.TEXT, bold=True)
            T.text(surf, f"stile di {d.short}: {driving.label(d)}",
                   (right.right - 16, right.y + 34), 12, T.GOLD, align="right",
                   maxw=right.w * 0.55)
            T.text(surf, "Vicinanza al riferimento", (right.x + 16, right.y + 62), 13, T.DIM)
            T.bar(surf, (right.x + 160, right.y + 66, 220, 10), q * 100)
            T.text(surf, f"{q*100:.0f}%", (right.x + 396, right.y + 60), 15, qc, bold=True)
            err = SETUP.paper_error(team, nt, team.sim_sessions)
            fid = max(0.0, min(1.0, 1.0 - (err - SETUP.ERR_MIN) / (SETUP.ERR_MAX - SETUP.ERR_MIN)))
            T.text(surf, f"Riferimento del reparto: +/-{err:.0f} punti", (right.x + 440, right.y + 62),
                   13, T.stat_colour(fid * 100, 40, 75), bold=True)
            T.text(surf, f"Il triangolo dorato e' il riferimento del reparto gia' "
                         f"corretto per il suo stile: {team.sim_sessions} sessioni al "
                         f"simulatore su {SETUP.SIM_MAX}. Il resto lo dira' la pista.",
                   (right.x + 16, right.y + 92), 12, T.DIM_2, maxw=right.w - 32)
            car.setup = dict(driving.setup_of(team, d))
            T.text(surf, f"Downforce {car.downforce:.2f}  |  Drag {car.drag:.2f}  |  "
                         f"Potenza {car.power:.2f}  |  Grip {car.mech_grip:.2f}",
                   (right.x + 16, right.y + 118), 13, T.DIM)
        else:
            T.text(surf, "Nessuna gara in programma.", (right.x + 16, right.y + 40), 15, T.DIM)
        yy = right.y + 182 + len(SETUP_KEYS) * 36 + 140
        if nt and d is not None:
            T.text(surf, "RISCONTRO DEGLI INGEGNERI", (right.x + 16, yy), 12, T.DIM_2, bold=True)
            yy += 22
            for line in S.setup_hints(team, nt, d)[:6]:
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

        # specifiche che non hanno convinto: si rimonta la vecchia o si insiste
        self.trial_y = y + 76
        ty = self.trial_y + 26
        bw = (left.w - 42) / 2
        for tr in self.team.spec_trials[:2]:
            peggio = development.deficit(self.team, tr) < -0.05
            if peggio:
                self.widgets.append(Button((left.x + 16, ty + 62, bw, 26),
                                           "Rimonta la vecchia",
                                           (lambda t=tr: self.revert(t)), "danger"))
            if tr.state == "in prova":
                x = left.x + 26 + bw if peggio else left.x + 16
                self.widgets.append(Button((x, ty + 62, bw, 26), "Tienila e affinala",
                                           (lambda t=tr: self.keep(t)), "primary"))
            ty += 104

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        bx, by = right.x + 16, right.y + 200
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
        self.auto_toggle = Toggle((left.x + 16, y + 50, left.w - 32, 30),
                                  "Decide il reparto", self.team.auto_dev,
                                  on_change=self._set_auto)
        self.widgets.append(self.auto_toggle)
        b = Button((bx, sy + 204, right.w - 32, 40), "Avvia progetto",
                   self.start_project, "primary")
        b.enabled = not self.team.auto_dev
        self.widgets.append(b)
        self.reg_slider = None
        if development.seasons_to_reset(self.gs) not in (None,) and \
                development.seasons_to_reset(self.gs) <= 3:
            self.reg_slider = Slider(
                (bx, sy + 256, right.w - 32, 28), "Risorse sul regolamento nuovo",
                self.team.next_reg_share * 100.0, 0.0, 90.0,
                on_change=self._set_reg_share, fmt="{:.0f}%")
            self.widgets.append(self.reg_slider)

    def _set_auto(self, v) -> None:
        self.team.auto_dev = bool(v)
        self.build()

    def _alloc(self, k, v) -> None:
        self.team.resource_alloc[k] = max(0.0, v) / 100.0

    def _set_reg_share(self, v) -> None:
        """Quota del budget di sviluppo dirottata sul regolamento che verra'."""
        self.team.next_reg_share = max(0.0, min(0.90, v / 100.0))

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

    def revert(self, tr) -> None:
        ok, msg = development.revert_spec(self.gs, self.team, tr)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def keep(self, tr) -> None:
        ok, msg = development.keep_spec(self.gs, self.team, tr)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

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
        cw = (r.w - 48) / 4
        card(surf, (r.x, r.y, cw, 86), "Capacita' di sviluppo", f"{cap:.2f}",
             f"efficienza reparto {team.dev_rate:.2f}", accent=T.ACCENT)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Ore galleria (ATR)", f"{atr*100:.0f}%",
             f"{team.last_position}o nel costruttori precedente",
             colour=T.OK if atr >= 1.0 else T.WARN, accent=T.WARN)
        und = team.car_understanding
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Conoscenza della vettura",
             f"{und*100:.0f}%", "quanto sappiamo sfruttarla",
             colour=T.OK if und > 0.45 else T.TEXT, accent=T.GOLD)
        card(surf, (r.x + 3 * (cw + 16), r.y, cw, 86), "Progetti attivi",
             f"{len(team.dev_projects)} / 3",
             f"{team.upgrades_done} aggiornamenti portati in pista", accent=T.OK)

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LAVORO DI REPARTO: DOVE LIMARE", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        T.text(surf, "affinamenti, non aggiornamenti", (left.right - 16, left.y + 12), 11,
               T.DIM_2, align="right")

        ty = getattr(self, "trial_y", left.y + 460)
        if team.spec_trials:
            T.text(surf, "SPECIFICHE IN VERIFICA", (left.x + 16, ty), 12, T.WARN, bold=True)
            ty += 26
            for tr in team.spec_trials[:2]:
                buco = development.deficit(team, tr)
                col = T.BAD if buco < -0.05 else (T.OK if buco > 0.05 else T.WARN)
                T.text(surf, tr.label, (left.x + 16, ty), 14, T.TEXT, bold=True, maxw=200)
                T.text(surf, f"{buco:+.1f} sulla vecchia", (left.right - 16, ty), 13, col,
                       bold=True, align="right")
                stato = ("da decidere" if tr.state == "in prova" else
                         f"in affinamento, {max(0, development.TRIAL_RACES + 1 - tr.races)} gare")
                T.text(surf, f"{stato}  -  {tr.news}", (left.x + 16, ty + 19), 12, T.DIM,
                       maxw=left.w - 32)
                # cosa ne dicono quelli che la guidano: un pacchetto che fa
                # girare la macchina non sta bene a tutti e due allo stesso modo
                voci = []
                for d in gs.lineup_of(team.id):
                    idx, frase = development.driver_verdict(gs, team, tr, d)
                    segno = "+" if idx > 0.12 else ("-" if idx < -0.12 else "=")
                    voci.append(f"{segno} {d.short}: {frase}")
                for j, voce in enumerate(voci[:2]):
                    col_v = (T.OK if voce.startswith("+") else
                             T.BAD if voce.startswith("-") else T.DIM_2)
                    T.text(surf, voce, (left.x + 16, ty + 33 + j * 14), 11, col_v,
                           maxw=left.w - 32)
                tetto = development.trial_ceiling(gs, team, tr) - tr.old_perf
                nota = (f"insistere puo' portarla a {tetto:+.1f} sulla vecchia e costa "
                        f"{tr.cost * development.TRIAL_UPKEEP:.2f} M$ a gara, con un "
                        f"banco occupato")
                if buco < -0.05:
                    nota += (f"  -  rimontare la vecchia costa "
                             f"{tr.cost * development.REVERT_SHARE:.2f} M$")
                T.text(surf, nota, (left.x + 16, ty + 90), 11, T.DIM_2, maxw=left.w - 32)
                ty += 104
        elif team.dev_projects:
            T.text(surf, "Nessuna specifica in discussione: quello che e' arrivato "
                         "in pista ha funzionato.", (left.x + 16, ty), 12, T.DIM_2,
                   maxw=left.w - 32)

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROGETTI DI AGGIORNAMENTO", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        from ...core import season as SEASON
        dev_gara, _pu = SEASON.player_budgets(gs)
        T.text(surf, f"Il reparto lavora con {dev_gara:.2f} M$ a gara: e' quello che "
                     f"avanza dopo i costi fissi.",
               (right.x + 16, right.y + 34), 13, T.DIM, maxw=right.w - 32)
        T.text(surf, f"Restano {economy.room_left(gs, team):.0f} M$ per la stagione, "
                     f"pacchetti compresi.",
               (right.x + 16, right.y + 52), 12, T.DIM_2, maxw=right.w - 32)
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
        T.text(surf, "NUOVO PACCHETTO", (right.x + 16, right.y + 178), 12, T.DIM_2, bold=True)
        sy = right.y + 200 + 4 * 34 + 10
        st = rules.talks(gs)
        if st:
            # il tavolo e' aperto: non si sa ancora la data, ma si sa la direzione
            dom = max(st["aree"], key=st["aree"].get)
            ry = sy + 296
            T.text(surf, f"TAVOLO TECNICO  -  RIUNIONE {st['riunioni']} DI {st['servono']}",
                   (right.x + 16, ry), 12, T.GOLD, bold=True)
            T.text(surf, f"Si sta andando verso {rules.ETICHETTA_AREA[dom]} "
                         f"({st['aree'][dom]*100:.0f}%). Finche' non si firma puo' ancora "
                         f"cambiare, e prepararsi adesso e' una scommessa.",
                   (right.x + 16, ry + 18), 12, T.DIM, maxw=right.w - 32)
        left = development.seasons_to_reset(gs)
        if left is not None and left <= 3:
            era = development.next_era(gs)
            f = era.get("focus", {})
            dom = max(f, key=f.get) if f else "aero"
            nome = {"pu": "power unit", "chassis": "telaio", "aero": "aerodinamica"}[dom]
            ry = sy + 244
            T.text(surf, f"REGOLAMENTO {era['from']}  -  fra {left} "
                         f"{'stagione' if left == 1 else 'stagioni'}",
                   (right.x + 16, ry), 12, T.GOLD, bold=True)
            T.text(surf, f"{era['label']}: a decidere sara' soprattutto {nome} "
                         f"({f.get(dom, 0)*100:.0f}%).",
                   (right.x + 16, ry + 18), 12, T.DIM, maxw=right.w - 32)
            conv = development.prep_conversion(gs, team, era)
            rank = 1 + sum(1 for t in gs.teams.values()
                           if development.prep_conversion(gs, t, era) > conv)
            T.text(surf, f"Con i nostri reparti convertiamo a {conv:.2f}: "
                         f"{rank}i della griglia su questo fronte.",
                   (right.x + 16, ry + 34), 12, T.DIM, maxw=right.w - 32)
            if left == 1:
                T.text(surf, "Ultima stagione utile: dopo il cambio la preparazione non conta piu'.",
                       (right.x + 16, ry + 50), 12, T.WARN, maxw=right.w - 32)

        conto = development.cost_breakdown(gs, team, self.sel_part, self.sel_size)
        cost = conto["totale"]
        gain = development.expected_gain(gs, team, self.sel_part, self.sel_size)
        conf = development.project_confidence(gs, team, self.sel_part, self.sel_size)
        odds = development.outcome_odds(conf, self.sel_size)
        races = development.RACES_OF[self.sel_size]
        liberi = development.free_people(team, self.sel_part)
        serve = development.people_needed(self.sel_size)
        T.text(surf, f"Costo {cost:.2f} M$   |   Sulla carta +{gain:.1f}   |   "
                     f"Tempo {races} gare",
               (right.x + 16, sy + 42), 14, T.TEXT)
        col_p = T.OK if liberi >= serve else T.BAD
        T.text(surf, f"{serve} persone del reparto per {races} gare "
                     f"({liberi} libere)   -   materiali {conto['materiali']:.2f} M$, "
                     f"straordinari {conto['lavoro']:.2f}",
               (right.x + 16, sy + 62), 12, col_p, maxw=right.w - 32)
        stato, parere = economy.cap_advice(gs, team, cost)
        col_cfo = {"male": T.BAD, "attento": T.WARN, "ok": T.DIM}[stato]
        T.text(surf, parere, (right.x + 16, sy + 78), 12, col_cfo, maxw=right.w - 32)

        col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
        T.text(surf, "Fiducia del reparto", (right.x + 16, sy + 102), 13, T.DIM)
        T.bar(surf, (right.x + 170, sy + 107, right.w - 260, 8), conf * 100, 100, col)
        T.text(surf, f"{conf*100:.0f}%", (right.right - 16, sy + 102), 13, col,
               bold=True, align="right")

        # come puo' finire: quattro bande, disegnate in proporzione
        bx, bw = right.x + 16, right.w - 32
        bande = (("fallito", T.BAD), ("sottotono", T.WARN),
                 ("in linea", T.ACCENT), ("oltre", T.OK))
        x = bx
        for nome, colore in bande:
            w = bw * odds[nome]
            pygame.draw.rect(surf, colore, (int(x), sy + 130, max(2, int(w)), 10),
                             border_radius=2)
            x += w
        T.text(surf, f"fallisce {odds['fallito']*100:.0f}%   "
                     f"sotto le attese {odds['sottotono']*100:.0f}%   "
                     f"come previsto {odds['in linea']*100:.0f}%   "
                     f"oltre {odds['oltre']*100:.0f}%",
               (bx, sy + 146), 12, T.DIM_2, maxw=bw)
        T.text(surf, development.weakest_link(gs, team, self.sel_part).capitalize()
               if conf < 0.62 else
               "Reparto e strumenti sono all'altezza: quello che promettiamo, arriva.",
               (bx, sy + 164), 12, T.DIM if conf >= 0.62 else T.WARN, maxw=bw)
        # quanto lavoro d'assetto rimette in discussione, e chi lo ritrova prima
        upset = development.setup_upset(team, self.sel_size)
        quanto = "poco" if upset < 0.15 else ("parecchio" if upset < 0.32 else "molto")
        casa = (f"il simulatore e {team.private_track_name} ce lo fanno ritrovare prima"
                if team.has_private_track else "senza pista di proprieta' si ritrova il venerdi'")
        T.text(surf, f"Assetto da ritrovare: {quanto} (-{upset*100:.0f}% di quello "
                     f"che sappiamo della vettura). {casa.capitalize()}.",
               (bx, sy + 182), 12, T.GOLD, maxw=bw)
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


# ================================================================ POWER UNIT
class PowerUnitPage(Page):
    """Il reparto motori: sviluppo, confronto coi motoristi, programma proprio."""

    def build(self) -> None:
        self.found_note = ""
        r = self.rect
        self.widgets = []
        gs, team = self.gs, self.team
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        if self._can_homologate():
            self.widgets.append(Button((left.x + 16, left.bottom - 58, left.w - 32, 40),
                                       "Omologa la specifica nuova",
                                       self.homologate, "primary"))
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        y = right.y + 300
        if powertrain.ready_to_debut(gs):
            self.widgets.append(Button((right.x + 16, y, right.w - 32, 42),
                                       "Porta in pista la nostra power unit",
                                       self.debut, "primary"))
        elif not team.works and not powertrain.has_program(gs):
            can, why = powertrain.can_found(team)
            b = Button(
                (right.x + 16, y, right.w - 32, 42),
                f"Fonda il reparto motori ({powertrain.PROGRAM_START_COST:.0f} M$)"
                if can else "Reparto motori fuori dalla nostra portata",
                self.start_program, "primary" if can else "ghost")
            b.enabled = can
            b.tip = why
            self.widgets.append(b)
            self.found_note = "" if can else why

    def refresh(self) -> None:
        self.build()

    def start_program(self) -> None:
        ok, msg = powertrain.start_program(self.gs, self.team)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _can_homologate(self) -> bool:
        """La specifica la decide chi il motore lo costruisce."""
        gs, team = self.gs, self.team
        if not team.works or powertrain.locked(gs):
            return False
        sp = powertrain.spec(gs, team.engine)
        return (powertrain.spec_value(sp) > 0.05
                and powertrain.specs_left(gs, team.engine) > 0)

    def homologate(self) -> None:
        ok, msg = powertrain.homologate(self.gs, self.team.engine)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def debut(self) -> None:
        ok, msg = powertrain.debut(self.gs)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        eng = powertrain.maker(gs, team)
        T.text(surf, "POWER UNIT", (r.x, r.y + 10), 22, T.TEXT, bold=True)
        status = ("costruttore" if team.works else
                  "team ufficiale" if team.is_partner else
                  "cliente, reparto in costruzione" if powertrain.has_program(gs) else "cliente")
        T.text(surf, f"{eng.get('name', '-')} - {status}", (r.x, r.y + 42), 14, T.DIM)

        # --- confronto fra i motoristi -----------------------------------
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I MOTORISTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        y = left.y + 42
        ranked = sorted(gs.engine_makers.items(), key=lambda kv: -powertrain.rating(kv[1]))
        for eid, m in ranked:
            mine = (eid == team.engine)
            builder = powertrain.builder_of(gs, eid)
            col = T.ACCENT if mine else T.TEXT
            T.text(surf, m.get("name", eid), (left.x + 16, y), 14, col, bold=mine,
                   maxw=left.w * 0.55)
            T.text(surf, f"{powertrain.rating(m):.1f}", (left.right - 16, y), 14, col,
                   bold=True, align="right")
            who = builder.short if builder else "nessuna squadra ufficiale"
            n = len(powertrain.customers_of(gs, eid))
            T.text(surf, f"{who} - {n} client{'e' if n == 1 else 'i'}",
                   (left.x + 16, y + 18), 11, T.DIM_2, maxw=left.w - 32)
            T.bar(surf, (left.x + 16, y + 34, left.w - 32, 6), powertrain.rating(m), 100,
                  T.ACCENT if mine else T.PANEL_3)
            y += 52

        y += 4
        sp = powertrain.spec(gs, team.engine)
        # i numeri del banco li vede solo chi il motore lo costruisce
        nostro = team.works
        T.text(surf, "LA NOSTRA UNITA'", (left.x + 16, y), 12, T.DIM_2, bold=True)
        if nostro:
            T.text(surf, "in banco", (left.right - 16, y), 11, T.DIM_2, align="right")
        y += 22
        for attr, label in (("power", "Potenza termica"), ("ers", "Ibrido ed ERS"),
                            ("reliability", "Affidabilita'")):
            T.text(surf, label, (left.x + 16, y), 13, T.DIM)
            T.text(surf, f"{float(eng.get(attr, 85)):.1f}",
                   (left.right - (96 if nostro else 16), y), 13, T.TEXT,
                   bold=True, align="right")
            g = float(sp["gain"].get(attr, 0.0))
            if nostro and g > 0.01:
                T.text(surf, f"+{g:.1f}", (left.right - 16, y), 13, T.OK,
                       bold=True, align="right")
            y += 20

        # --- la specifica che sta crescendo al banco ----------------------
        y += 12
        T.text(surf, "SPECIFICA IN LAVORAZIONE", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        if powertrain.locked(gs):
            T.text(surf, "Sviluppo congelato: si corre con quello che c'e'.",
                   (left.x + 16, y), 13, T.WARN, maxw=left.w - 32)
        elif not team.works:
            costruttore = powertrain.builder_of(gs, team.engine)
            chi = costruttore.short if costruttore else eng.get("name", "il motorista")
            T.text(surf, f"La specifica la decide {chi}: noi la montiamo e basta. "
                         f"E' il prezzo di comprare il motore invece di farlo.",
                   (left.x + 16, y), 13, T.DIM, maxw=left.w - 32)
        else:
            valore = powertrain.spec_value(sp)
            conf = powertrain.spec_confidence(gs, team.engine)
            odds = powertrain.spec_odds(gs, team.engine)
            rimaste = powertrain.specs_left(gs, team.engine)
            T.text(surf, f"Vale {valore:+.2f} dopo {sp.get('races', 0)} gare di banco",
                   (left.x + 16, y), 13, T.TEXT if valore > 0.05 else T.DIM,
                   maxw=left.w - 32)
            T.text(surf, f"{rimaste} su {powertrain.specs_allowed(gs)}",
                   (left.right - 16, y), 13, T.GOLD if rimaste else T.BAD,
                   bold=True, align="right")
            y += 22
            col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
            T.text(surf, "Fiducia del banco", (left.x + 16, y), 13, T.DIM)
            T.bar(surf, (left.x + 160, y + 5, left.w - 250, 8), conf * 100, 100, col)
            T.text(surf, f"{conf*100:.0f}%", (left.right - 16, y), 13, col,
                   bold=True, align="right")
            y += 24
            T.text(surf, f"fallisce {odds['fallito']*100:.0f}%   "
                         f"sotto le attese {odds['sottotono']*100:.0f}%   "
                         f"oltre {odds['oltre']*100:.0f}%",
                   (left.x + 16, y), 12, T.DIM_2, maxw=left.w - 32)
            y += 20
            if rimaste <= 0:
                T.text(surf, "Gettoni finiti: il resto del lavoro va all'anno prossimo.",
                       (left.x + 16, y), 12, T.WARN, maxw=left.w - 32)
            elif sp.get("races", 0) < 5:
                T.text(surf, "Piu' resta al banco, meno sorprese in pista.",
                       (left.x + 16, y), 12, T.DIM_2, maxw=left.w - 32)

        # --- reparto e programma -----------------------------------------
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "IL NOSTRO REPARTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)

        hop = team.role("head_of_powertrain")
        ceil = powertrain.ceiling(gs, team)
        clients = powertrain.customers_of(gs, team.engine) if team.works else []
        y = right.y + 96
        from ...core import season as SEASON
        rows = [
            ("Budget del reparto", f"{SEASON.player_budgets(gs)[1]:.2f} M$ a gara"),
            ("Responsabile powertrain", hop.name if hop else "nessuno"),
            ("Qualita' del reparto", f"{team.pu_strength:.0f} / 100"),
            ("Resa dell'investimento", f"x{powertrain.dev_rate(gs, team):.2f}"),
            ("Tetto raggiungibile", f"{ceil:.1f}"),
            ("Integrazione nella vettura", f"{powertrain.integration(gs, team) * 100:.0f}%"),
        ]
        if team.works:
            rows.append(("Gestione del reparto", f"-{powertrain.PU_OPERATING_COST:.0f} M$ all'anno"))
            income = sum(c.engine_customer_cost for c in clients)
            rows.append(("Forniture ai clienti",
                         f"+{income:.0f} M$ da {len(clients)}" if clients else "nessun cliente"))
        else:
            rows.append(("Fornitura che paghiamo", f"-{team.engine_customer_cost:.0f} M$ all'anno"))
        for k, v in rows:
            T.text(surf, k, (right.x + 16, y), 13, T.DIM)
            T.text(surf, v, (right.right - 16, y), 13, T.TEXT, bold=True, align="right",
                   maxw=right.w * 0.5)
            y += 22

        y += 10
        if powertrain.locked(gs):
            T.text(surf, "Sviluppo power unit congelato dal regolamento.",
                   (right.x + 16, y), 13, T.WARN, bold=True, maxw=right.w - 32)
            y += 24
        if gs.regulations.get("pu_equalisation"):
            T.text(surf, "Equalizzazione in vigore: chi e' indietro sviluppa di piu'.",
                   (right.x + 16, y), 12, T.DIM, maxw=right.w - 32)
            y += 22

        p = powertrain.program(gs)
        if powertrain.has_program(gs):
            T.text(surf, "PROGRAMMA IN CORSO", (right.x + 16, y), 12, T.DIM_2, bold=True)
            y += 22
            T.text(surf, f"Livello raggiunto {p['level']:.1f} su un tetto di {ceil:.1f}",
                   (right.x + 16, y), 13, T.TEXT, maxw=right.w - 32)
            T.bar(surf, (right.x + 16, y + 22, right.w - 32, 8), p["level"], 100, T.OK)
            y += 40
            T.text(surf, f"Investiti {p['invested']:.0f} M$ - in pista dal {p['ready_season']}",
                   (right.x + 16, y), 12, T.DIM, maxw=right.w - 32)
            y += 26
            from ...core import season as SEASON
            o = powertrain.debut_outlook(gs, SEASON.player_budgets(gs)[1])
            T.text(surf, "QUANDO PORTARLA IN PISTA", (right.x + 16, y), 12, T.DIM_2, bold=True)
            y += 22
            gap = o["gap_now"]
            T.text(surf, "Oggi il nostro motore vale", (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['now']:.1f}", (right.x + 240, y), 13, T.TEXT, bold=True)
            T.text(surf, f"contro il {o['supplied']:.1f} che compriamo ({gap:+.1f})",
                   (right.x + 280, y), 13, T.OK if gap >= 0 else T.BAD)
            y += 22
            T.text(surf, f"Fra {o['horizon']} gare, se debutta subito",
                   (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['if_debut_now']:.1f}", (right.x + 240, y), 13, T.OK, bold=True)
            y += 20
            T.text(surf, f"Fra {o['horizon']} gare, se resta al banco",
                   (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['if_wait']:.1f}", (right.x + 240, y), 13, T.WARN, bold=True)
            y += 24
            for line in (f"Al banco si sviluppa al {o['bench_penalty']*100:.0f}% del ritmo: "
                         f"mancano i dati veri.",
                         "Correre con un motore acerbo costa punti adesso, ma lo fa",
                         "crescere piu' in fretta."):
                T.text(surf, line, (right.x + 16, y), 12, T.DIM_2, maxw=right.w - 32)
                y += 16
        elif not team.works:
            for riga in (f"Compriamo la power unit da {eng.get('name', '-')} per "
                         f"{team.engine_customer_cost:.0f} M$ a stagione, e ci teniamo",
                         "la specifica che decidono loro. Fondando un reparto nostro",
                         "potremmo svilupparla in casa, ma servono anni e un buon",
                         "responsabile powertrain."):
                T.text(surf, riga, (right.x + 16, y), 13, T.DIM, maxw=right.w - 32)
                y += 18
        else:
            for riga in ("Costruiamo la nostra power unit: il budget qui sopra e' quello",
                         "che il reparto motori spende a ogni gara. Sta fuori dal tetto di",
                         "spesa della squadra, come nella realta'."):
                T.text(surf, riga, (right.x + 16, y), 13, T.DIM, maxw=right.w - 32)
                y += 18
        if getattr(self, "found_note", ""):
            T.text(surf, self.found_note, (r.x + 16, r.bottom - 26), 13, T.WARN,
                   maxw=r.w - 32)
        super().draw(surf)
