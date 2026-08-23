"""Pagine: piloti e mercato, staff tecnico."""
from __future__ import annotations

import pygame

from ...core import economy, market
from ...model.people import STAFF_ATTRS
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, card


class DriversPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.filter = "nostri"
        self.neg = None                       # trattativa aperta
        self.offer = market.Offer()

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        right = pygame.Rect(r.x + r.w * 0.42 + 16, r.y, r.w * 0.58 - 16, r.h)
        self.tabs = []
        for i, (key, lab) in enumerate([("nostri", "I nostri (rinnovo)"), ("liberi", "Svincolati"),
                                        ("tutti", "Tutta la griglia"), ("giovani", "Giovani")]):
            b = Button((right.x + 16 + i * 118, right.y + 36, 112, 30), lab, style="tab")
            b.on_click = (lambda k=key: self.set_filter(k))
            b.active = (key == self.filter)
            self.tabs.append(b)
            self.widgets.append(b)
        self.list = ScrollList((right.x + 12, right.y + 74, right.w - 24, r.h * 0.42),
                               row_h=40, draw_row=self._row, on_select=self._select)
        self.widgets.append(self.list)
        oy = right.y + 74 + r.h * 0.42 + 10
        self.offer_y = oy
        half = (right.w - 44) / 2
        rows = [
            ("salary", "Ingaggio fisso", 0.5, 70.0, "{:.1f} M$"),
            ("years", "Durata", 1, 5, "{:.0f} anni"),
            ("bonus_win", "Bonus vittoria", 0.0, 6.0, "{:.2f} M$"),
            ("bonus_podium", "Bonus podio", 0.0, 3.0, "{:.2f} M$"),
            ("bonus_points", "Bonus a punto", 0.0, 0.30, "{:.3f} M$"),
            ("release_clause", "Clausola", 0.0, 250.0, "{:.0f} M$"),
        ]
        self.sliders = {}
        for i, (key, lab, lo, hi, fmt) in enumerate(rows):
            x = right.x + 16 + (i % 2) * (half + 12)
            y = oy + 34 + (i // 2) * 34
            sl = Slider((x, y, half, 26), lab, getattr(self.offer, key), lo, hi,
                        on_change=(lambda v, k=key: self._set(k, v)), fmt=fmt)
            self.sliders[key] = sl
            self.widgets.append(sl)
        by = oy + 34 + 3 * 34 + 8
        bw = (right.w - 44) / 3
        self.widgets.append(Button((right.x + 16, by, bw, 36),
                                   "Proponi" if self.neg and self.neg.open else "Apri trattativa",
                                   self.negotiate, "primary"))
        self.widgets.append(Button((right.x + 28 + bw, by, bw, 36), "Lascia perdere",
                                   self.drop, "ghost"))
        self.widgets.append(Button((right.x + 40 + 2 * bw, by, bw, 36), "Libera il pilota",
                                   self.release, "danger"))
        self._fill()

    def _set(self, key, v) -> None:
        setattr(self.offer, key, int(round(v)) if key == "years" else v)

    def set_filter(self, k) -> None:
        self.filter = k
        for b, key in zip(self.tabs, ("nostri", "liberi", "tutti", "giovani")):
            b.active = (key == k)
        self._fill()

    def _fill(self) -> None:
        gs = self.gs
        if self.filter == "nostri":
            items = gs.drivers_of(self.team.id)
        elif self.filter == "liberi":
            items = list(gs.free_agents)
        elif self.filter == "giovani":
            items = [d for d in list(gs.drivers.values()) + gs.free_agents if d.age <= 23]
        else:
            items = [d for d in gs.drivers.values() if d.team != self.team.id] + list(gs.free_agents)
        items.sort(key=lambda d: -d.overall)
        self.list.items = items
        if items and self.sel not in items:
            self._select(0, items[0])

    def _select(self, i, item) -> None:
        if self.sel is not item:
            self.neg = None
        self.sel = item
        self.offer = market.Offer(salary=max(0.5, item.market_value), years=2,
                                  release_clause=round(item.market_value * 2.5, 0))
        self._sync_sliders()

    def _sync_sliders(self) -> None:
        for k, sl in getattr(self, "sliders", {}).items():
            sl.value = getattr(self.offer, k)

    def _row(self, surf, rect, i, d) -> None:
        team = self.gs.teams.get(d.team)
        col = T.hex_rgb(team.colour) if team else T.DIM_2
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, d.name, (rect.x + 18, rect.y + 4), 14, T.TEXT, maxw=180)
        T.text(surf, f"{d.age}a", (rect.x + 208, rect.y + 4), 13, T.DIM)
        T.text(surf, team.short if team else "svincolato", (rect.x + 244, rect.y + 4), 13, T.DIM,
               maxw=110)
        T.text(surf, f"{d.overall:.0f}", (rect.x + 372, rect.y + 3), 15,
               T.stat_colour(d.overall, 70, 90), bold=True)
        T.text(surf, f"pot {d.potential:.0f}", (rect.x + 412, rect.y + 5), 12, T.DIM)
        T.text(surf, f"{d.market_value:.1f} M$", (rect.right - 14, rect.y + 4), 13, T.GOLD,
               bold=True, align="right")
        T.text(surf, f"contratto fino al {d.contract_until}", (rect.x + 18, rect.y + 21), 11, T.DIM_2)

    def negotiate(self) -> None:
        if not self.sel:
            return
        gs, team, d = self.gs, self.team, self.sel
        if self.neg is None or not self.neg.open or self.neg.driver_id != d.id:
            if len(team.drivers) >= 2 and d.id not in team.drivers:
                self.app.toast("Hai gia' due piloti sotto contratto: liberane uno prima.")
                return
            self.neg = market.open_negotiation(gs, team, d)
            self.offer = self.neg.demand.copy()
            self._sync_sliders()
            self.app.toast(self.neg.last)
            self.build()
            return
        # in cassa serve solo l'indennizzo per portarlo via: l'ingaggio si paga
        # gara per gara, non in un colpo alla firma
        fee = market.buyout_cost(gs, d) if d.team and d.team != team.id else 0.0
        if fee > 0:
            ok, why = economy.can_afford(team, fee, gs, check_cap=False)
            if not ok:
                self.app.toast(why)
                return
        self.neg = market.propose(gs, team, d, self.neg, self.offer)
        self.app.toast(self.neg.last)
        if self.neg.state == "accordo":
            self.gs.push(self.neg.last, "mercato")
            self._fill()
            self.shell.build()
        self.build()

    def drop(self) -> None:
        self.neg = None
        self.build()

    def release(self) -> None:
        drs = self.gs.drivers_of(self.team.id)
        if not drs:
            return
        target = self.sel if (self.sel and self.sel.team == self.team.id) else drs[-1]
        ok, msg = market.release_driver(self.gs, self.team, target)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self._fill()

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I NOSTRI PILOTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        y = left.y + 40
        col = T.hex_rgb(team.colour)
        for d in gs.drivers_of(team.id):
            T.panel(surf, (left.x + 12, y, left.w - 24, 176), T.PANEL_2, radius=8)
            T.text(surf, d.name, (left.x + 24, y + 10), 18, T.TEXT, bold=True, maxw=left.w - 110)
            T.text(surf, f"#{d.number}", (left.right - 24, y + 10), 18, col, bold=True, align="right")
            T.text(surf, f"{d.nat}  -  {d.age} anni  -  contratto fino al {d.contract_until}",
                   (left.x + 24, y + 34), 12, T.DIM)
            T.text(surf, f"ingaggio {d.salary:.1f} M$   valore {d.market_value:.1f} M$",
                   (left.x + 24, y + 50), 12, T.GOLD)
            yy = y + 72
            stats = [("Passo", d.pace), ("Duello", d.racecraft), ("Costanza", d.consistency),
                     ("Gomme", d.tyre_mgmt), ("Bagnato", d.wet), ("Riscontro", d.feedback)]
            for j, (lab, v) in enumerate(stats):
                cx = left.x + 24 + (j % 2) * ((left.w - 60) / 2)
                cy = yy + (j // 2) * 22
                T.text(surf, lab, (cx, cy), 12, T.DIM)
                T.bar(surf, (cx + 74, cy + 4, 90, 7), v, 100, T.stat_colour(v, 65, 90))
                T.text(surf, f"{v:.0f}", (cx + 172, cy - 1), 12, T.TEXT, bold=True)
            T.text(surf, f"Morale {d.morale:.0f}   Forma {d.form:+.1f}   "
                         f"Punti {d.points:.0f}   Vittorie {d.wins}",
                   (left.x + 24, y + 146), 12, T.DIM)
            lic = d.penalty_points
            col_lic = T.BAD if lic >= 9 else (T.WARN if lic >= 6 else T.DIM)
            testo = f"Licenza: {lic}/12 punti"
            if d.banned_races > 0:
                testo += f"  -  SQUALIFICATO per {d.banned_races} gara"
                col_lic = T.BAD
            T.text(surf, testo, (left.x + 24, y + 162), 12, col_lic)
            y += 186

        right = pygame.Rect(r.x + r.w * 0.42 + 16, r.y, r.w * 0.58 - 16, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "MERCATO PILOTI", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        oy = getattr(self, "offer_y", right.y + 74 + r.h * 0.42 + 10)
        if self.sel:
            d, gs = self.sel, self.gs
            T.text(surf, f"TRATTATIVA: {d.name.upper()}", (right.x + 16, oy), 13,
                   T.TEXT, bold=True, maxw=right.w * 0.5)
            # quanto costerebbe portarlo via, con o senza clausola
            if d.team and d.team != team.id:
                fee = market.buyout_cost(gs, d)
                has = getattr(d, "release_clause", 0.0) > 0
                T.text(surf, f"{'clausola' if has else 'indennizzo'} {fee:.0f} M$",
                       (right.right - 16, oy), 12, T.GOLD, align="right", bold=True)
            elif not d.team:
                T.text(surf, "svincolato", (right.right - 16, oy), 12, T.OK, align="right")

            # il valore complessivo di quello che stiamo offrendo, come lo vede lui
            mine = market.offer_value(gs, team, d, self.offer)
            T.text(surf, f"la nostra offerta vale {mine:.1f} M$ l'anno per lui",
                   (right.x + 16, oy + 16), 12, T.DIM, maxw=right.w * 0.55)
            if self.neg and self.neg.driver_id == d.id:
                want = market.demand_value(gs, team, d, self.neg)
                col = T.OK if mine >= want * 0.98 else (T.WARN if mine >= want * 0.85 else T.BAD)
                T.text(surf, f"lui ne chiede {want:.1f}", (right.right - 16, oy + 16), 12,
                       col, align="right", bold=True)

            by = oy + 34 + 3 * 34 + 8
            if self.neg and self.neg.driver_id == d.id:
                colour = {"aperta": T.TEXT, "accordo": T.OK, "rotta": T.BAD}[self.neg.state]
                T.text(surf, self.neg.last, (right.x + 16, by + 42), 13, colour,
                       maxw=right.w - 32)
                if self.neg.open:
                    left_r = max(0, self.neg.patience - self.neg.rounds)
                    T.text(surf, f"ancora {left_r} giri di trattativa prima che si alzi dal tavolo",
                           (right.x + 16, by + 62), 11, T.DIM_2, maxw=right.w - 32)
            else:
                T.text(surf, "Apri la trattativa per sentire cosa chiede: ingaggio, durata, "
                             "premi e clausola si negoziano tutti insieme.",
                       (right.x + 16, by + 42), 12, T.DIM_2, maxw=right.w - 32)
        super().draw(surf)


class StaffPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.offer_salary = 2.0
        self.offer_years = 3

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        left = pygame.Rect(r.x, r.y, r.w * 0.5, r.h)
        self.mine = ScrollList((left.x + 12, left.y + 40, left.w - 24, left.h - 100),
                               row_h=44, draw_row=self._row_mine, on_select=self._sel_mine)
        self.widgets.append(self.mine)
        self.widgets.append(Button((left.x + 12, left.bottom - 50, 220, 36),
                                   "Licenzia il selezionato", self.fire, "danger"))
        right = pygame.Rect(r.x + r.w * 0.5 + 16, r.y, r.w * 0.5 - 16, r.h)
        self.market_list = ScrollList((right.x + 12, right.y + 40, right.w - 24, r.h * 0.5),
                                      row_h=44, draw_row=self._row_market, on_select=self._sel_market)
        self.widgets.append(self.market_list)
        oy = right.y + 40 + r.h * 0.5 + 20
        self.sal = Slider((right.x + 16, oy + 40, right.w - 32, 28), "Stipendio proposto",
                          self.offer_salary, 0.3, 18.0,
                          on_change=lambda v: setattr(self, "offer_salary", v), fmt="{:.2f} M$")
        self.yrs = Slider((right.x + 16, oy + 76, right.w - 32, 28), "Durata",
                          self.offer_years, 1, 5,
                          on_change=lambda v: setattr(self, "offer_years", int(round(v))),
                          fmt="{:.0f} anni")
        self.widgets += [self.sal, self.yrs]
        self.widgets.append(Button((right.x + 16, oy + 116, 240, 38), "Assumi", self.hire, "primary"))
        self._fill()

    def _fill(self) -> None:
        self.mine.items = sorted(self.team.staff, key=lambda s: list(self.gs.staff_roles).index(s.role))
        pool = list(self.gs.free_staff) + [s for t in self.gs.teams.values()
                                           if t.id != self.team.id for s in t.staff]
        pool.sort(key=lambda s: -s.market_value)
        self.market_list.items = pool
        if pool and self.sel is None:
            self.sel = pool[0]
            self.offer_salary = max(0.3, self.sel.market_value * 1.1)
            self.sal.value = self.offer_salary

    def _label(self, role) -> str:
        return self.gs.staff_roles[role]["label"]

    def _row_mine(self, surf, rect, i, s) -> None:
        T.text(surf, self._label(s.role), (rect.x + 14, rect.y + 4), 12, T.ACCENT, bold=True)
        T.text(surf, s.name, (rect.x + 14, rect.y + 20), 14, T.TEXT, maxw=190)
        best = max(STAFF_ATTRS, key=lambda a: getattr(s, a))
        T.text(surf, f"{best} {getattr(s, best):.0f}", (rect.x + 216, rect.y + 20), 12, T.DIM)
        T.text(surf, f"{s.salary:.2f} M$", (rect.right - 100, rect.y + 12), 13, T.GOLD,
               bold=True, align="right")
        T.text(surf, f"fino {s.contract_until}", (rect.right - 12, rect.y + 14), 12, T.DIM,
               align="right")

    def _row_market(self, surf, rect, i, s) -> None:
        t = self.gs.teams.get(s.team)
        col = T.hex_rgb(t.colour) if t else T.DIM_2
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, s.name, (rect.x + 18, rect.y + 4), 14, T.TEXT, maxw=180)
        T.text(surf, self._label(s.role), (rect.x + 18, rect.y + 22), 12, T.DIM)
        T.text(surf, t.short if t else "libero", (rect.x + 210, rect.y + 22), 12, T.DIM_2, maxw=100)
        T.text(surf, f"{s.market_value:.2f} M$", (rect.right - 12, rect.y + 12), 13, T.GOLD,
               bold=True, align="right")

    def _sel_mine(self, i, s) -> None:
        self.sel_mine_item = s

    def _sel_market(self, i, s) -> None:
        self.sel = s
        self.offer_salary = max(0.3, s.market_value * 1.1)
        self.sal.value = self.offer_salary

    def hire(self) -> None:
        if not self.sel:
            return
        ok, msg = market.hire_staff(self.gs, self.team, self.sel,
                                    round(self.offer_salary, 2), self.offer_years)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self._fill()

    def fire(self) -> None:
        item = getattr(self, "sel_mine_item", None)
        if not item:
            self.app.toast("Seleziona prima una persona del tuo organico.")
            return
        ok, msg = market.fire_staff(self.gs, self.team, item)
        self.app.toast(msg)
        if ok:
            self._fill()

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, team = self.rect, self.team
        left = pygame.Rect(r.x, r.y, r.w * 0.5, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, f"ORGANIGRAMMA  -  costo {team.staff_cost:.2f} M$/anno",
               (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        right = pygame.Rect(r.x + r.w * 0.5 + 16, r.y, r.w * 0.5 - 16, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "MERCATO DEL PERSONALE", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        oy = right.y + 40 + r.h * 0.5 + 20
        if self.sel:
            s = self.sel
            T.text(surf, s.name, (right.x + 16, oy), 17, T.TEXT, bold=True)
            T.text(surf, f"{self._label(s.role)}  -  {s.age} anni  -  {s.nat}",
                   (right.x + 16, oy + 20), 13, T.DIM)
            bx = right.x + 16
            for j, a in enumerate(STAFF_ATTRS):
                cx = bx + (j % 2) * ((right.w - 60) / 2)
                cy = oy + 160 + (j // 2) * 20
                if cy > right.bottom - 20:
                    break
                v = getattr(s, a)
                T.text(surf, a, (cx, cy), 11, T.DIM)
                T.bar(surf, (cx + 96, cy + 4, 80, 6), v, 100, T.stat_colour(v, 55, 85))
        super().draw(surf)
