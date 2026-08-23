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
    """Organigramma, mercato e la scheda di chi si sta guardando.

    Prima si assumeva alla cieca: una lista di nomi, un paio di barre senza
    numeri e un pulsante. Adesso di chiunque - dei nostri e di quelli che si
    provano a contattare - si vede la scheda intera, con i valori scritti
    accanto alle barre, quanto vale nel suo ruolo e cosa cambierebbe rispetto
    a chi quel posto ce l'ha adesso.
    """

    ATTR_LABEL = {
        "aero": "Aerodinamica", "mechanical": "Meccanica", "powertrain": "Powertrain",
        "development": "Sviluppo", "reliability": "Affidabilita'", "strategy": "Strategia",
        "analysis": "Analisi dati", "communication": "Comunicazione",
        "management": "Gestione", "scouting": "Scouting",
    }
    FILTRI = (("liberi", "Svincolati"), ("altre", "Sotto contratto"), ("tutti", "Tutti"))

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.sel_from = "mercato"      # da quale lista arriva la scheda
        self.filtro = "liberi"
        self.offer_salary = 2.0
        self.offer_years = 3

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        wA = r.w * 0.32
        wB = r.w * 0.29
        self.colA = pygame.Rect(r.x, r.y, wA, r.h)
        self.colB = pygame.Rect(r.x + wA + 16, r.y, wB, r.h)
        self.colC = pygame.Rect(r.x + wA + wB + 32, r.y, r.w - wA - wB - 32, r.h)

        self.mine = ScrollList((self.colA.x + 10, self.colA.y + 40, self.colA.w - 20,
                                self.colA.h - 56), row_h=44,
                               draw_row=self._row_mine, on_select=self._sel_mine)
        self.widgets.append(self.mine)

        self.filter_buttons = []
        bw = (self.colB.w - 28) / 3
        for i, (key, lab) in enumerate(self.FILTRI):
            b = Button((self.colB.x + 10 + i * (bw + 4), self.colB.y + 36, bw, 26), lab)
            b.on_click = (lambda k=key: self._pick_filter(k))
            self.filter_buttons.append(b)
            self.widgets.append(b)
        self._mark_filter()
        self.market_list = ScrollList((self.colB.x + 10, self.colB.y + 70, self.colB.w - 20,
                                       self.colB.h - 86), row_h=44,
                                      draw_row=self._row_market, on_select=self._sel_market)
        self.widgets.append(self.market_list)

        # --- controlli della scheda, in fondo alla terza colonna
        c = self.colC
        self.sal = Slider((c.x + 16, c.bottom - 150, c.w - 32, 28), "Stipendio",
                          self.offer_salary, 0.2, 18.0,
                          on_change=lambda v: setattr(self, "offer_salary", v),
                          fmt="{:.2f} M$")
        self.yrs = Slider((c.x + 16, c.bottom - 114, c.w - 32, 28), "Durata",
                          self.offer_years, 1, 5,
                          on_change=lambda v: setattr(self, "offer_years", int(round(v))),
                          fmt="{:.0f} anni")
        self.hire_btn = Button((c.x + 16, c.bottom - 72, c.w - 32, 40), "Contatta e assumi",
                               self.hire, "primary")
        self.fire_btn = Button((c.x + 16, c.bottom - 72, c.w - 32, 40),
                               "Licenzia", self.fire, "danger")
        self.widgets += [self.sal, self.yrs, self.hire_btn, self.fire_btn]
        self._fill()
        self._sync_controls()

    def _fill(self) -> None:
        gs = self.gs
        ordine = list(gs.staff_roles)
        self.mine.items = sorted(self.team.staff, key=lambda s: ordine.index(s.role))
        liberi = list(gs.free_staff)
        altrui = [s for t in gs.teams.values() if t.id != self.team.id for s in t.staff]
        pool = {"liberi": liberi, "altre": altrui, "tutti": liberi + altrui}[self.filtro]
        pool.sort(key=lambda s: -market.role_score(gs, s, s.role))
        self.market_list.items = pool
        if self.sel is None and pool:
            self._sel_market(0, pool[0])
        if self.sel in pool:
            self.market_list.selected = pool.index(self.sel)
        if self.sel in self.mine.items:
            self.mine.selected = self.mine.items.index(self.sel)

    def _sync_controls(self) -> None:
        """I comandi in fondo cambiano a seconda di chi si sta guardando."""
        nostro = self.sel_from == "mine"
        for w in (self.sal, self.yrs, self.hire_btn):
            w.visible = not nostro
            w.enabled = not nostro
        self.fire_btn.visible = nostro
        self.fire_btn.enabled = nostro

    # ------------------------------------------------------------------ azioni
    def _pick_filter(self, k) -> None:
        self.filtro = k
        self._mark_filter()
        self._fill()

    def _mark_filter(self) -> None:
        for b, (key, _l) in zip(self.filter_buttons, self.FILTRI):
            b.active = (key == self.filtro)
            b.style = "tab" if b.active else "normal"

    def _sel_mine(self, i, s) -> None:
        self.sel, self.sel_from = s, "mine"
        self._sync_controls()

    def _sel_market(self, i, s) -> None:
        self.sel, self.sel_from = s, "mercato"
        self.offer_salary = max(0.2, round(s.market_value * 1.10, 2))
        self.sal.value = self.offer_salary
        self._sync_controls()

    def hire(self) -> None:
        if not self.sel:
            return
        ok, msg = market.hire_staff(self.gs, self.team, self.sel,
                                    round(self.offer_salary, 2), self.offer_years)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel, self.sel_from = None, "mercato"
            self.build()

    def fire(self) -> None:
        if not self.sel or self.sel_from != "mine":
            return
        ok, msg = market.fire_staff(self.gs, self.team, self.sel)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel, self.sel_from = None, "mercato"
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- le righe
    def _label(self, role) -> str:
        return self.gs.staff_roles[role]["label"]

    def _row_mine(self, surf, rect, i, s) -> None:
        T.text(surf, self._label(s.role), (rect.x + 12, rect.y + 4), 12, T.ACCENT, bold=True,
               maxw=rect.w - 110)
        T.text(surf, s.name, (rect.x + 12, rect.y + 20), 14, T.TEXT, maxw=rect.w - 150)
        voto = market.role_score(self.gs, s, s.role)
        T.text(surf, f"{voto:.0f}", (rect.right - 12, rect.y + 6), 17,
               T.stat_colour(voto, 58, 86), bold=True, align="right")
        T.text(surf, f"{s.salary:.2f} M$  fino {s.contract_until}",
               (rect.right - 12, rect.y + 26), 11, T.DIM, align="right")

    def _row_market(self, surf, rect, i, s) -> None:
        t = self.gs.teams.get(s.team)
        col = T.hex_rgb(t.colour) if t else T.DIM_2
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, s.name, (rect.x + 16, rect.y + 4), 14, T.TEXT, maxw=rect.w - 90)
        T.text(surf, f"{self._label(s.role)} - {t.short if t else 'svincolato'}",
               (rect.x + 16, rect.y + 23), 11, T.DIM, maxw=rect.w - 90)
        voto = market.role_score(self.gs, s, s.role)
        T.text(surf, f"{voto:.0f}", (rect.right - 12, rect.y + 5), 16,
               T.stat_colour(voto, 58, 86), bold=True, align="right")
        T.text(surf, f"{s.market_value:.2f} M$", (rect.right - 12, rect.y + 26), 11,
               T.GOLD, align="right")

    # --------------------------------------------------------------- la scheda
    def _draw_card(self, surf) -> None:
        c, gs, team = self.colC, self.gs, self.team
        s = self.sel
        if s is None:
            T.text(surf, "Scegli una persona da una delle due liste.",
                   (c.x + 16, c.y + 48), 14, T.DIM, maxw=c.w - 32)
            return
        squadra = gs.teams.get(s.team)
        T.text(surf, s.name, (c.x + 16, c.y + 34), 20, T.TEXT, bold=True, maxw=c.w - 32)
        T.text(surf, f"{self._label(s.role)}", (c.x + 16, c.y + 60), 14, T.ACCENT,
               maxw=c.w - 32)
        T.text(surf, f"{s.age} anni  -  {s.nat}  -  "
                     f"{squadra.short if squadra else 'svincolato'}",
               (c.x + 16, c.y + 80), 13, T.DIM, maxw=c.w - 32)
        pygame.draw.line(surf, T.LINE, (c.x + 16, c.y + 104), (c.right - 16, c.y + 104))

        voto = market.role_score(gs, s, s.role)
        righe = [("Valore nel ruolo", f"{voto:.0f} / 100", T.stat_colour(voto, 58, 86))]
        if self.sel_from == "mine":
            righe.append(("Ingaggio", f"{s.salary:.2f} M$ all'anno", T.GOLD))
            righe.append(("Contratto", f"fino al {s.contract_until}", T.TEXT))
        else:
            righe.append(("Quanto vale", f"{s.market_value:.2f} M$ all'anno", T.GOLD))
            if squadra:
                righe.append(("Sotto contratto", f"{squadra.short} fino al {s.contract_until}",
                              T.WARN))
                righe.append(("Indennizzo alla squadra", f"{s.salary * 0.8:.2f} M$", T.DIM))
            else:
                righe.append(("Situazione", "libero, nessun indennizzo", T.OK))
        y = c.y + 114
        for lab, val, col in righe:
            T.text(surf, lab, (c.x + 16, y), 13, T.DIM)
            T.text(surf, val, (c.right - 16, y), 13, col, bold=True, align="right",
                   maxw=c.w * 0.55)
            y += 21

        # --- attributi, con il numero accanto alla barra
        y += 10
        T.text(surf, "ATTRIBUTI", (c.x + 16, y), 12, T.DIM_2, bold=True)
        pesi = gs.staff_roles.get(s.role, {}).get("weights", {})
        T.text(surf, "in grassetto quelli che contano nel ruolo",
               (c.right - 16, y), 11, T.DIM_2, align="right")
        y += 20
        # quanto spazio resta prima dei comandi in fondo: su una finestra bassa
        # gli attributi si mettono su due colonne invece di stringersi fino a
        # diventare illeggibili
        fondo = c.bottom - (72 if self.sel_from == "mine" else 150) - 58
        spazio = max(60, fondo - y)
        n = len(STAFF_ATTRS)
        due_colonne = spazio < n * 20
        if due_colonne:
            passo = max(16, min(22, spazio // ((n + 1) // 2)))
            cw = (c.w - 32) / 2
            for j, a in enumerate(STAFF_ATTRS):
                v = getattr(s, a)
                cx = c.x + 16 + (j % 2) * cw
                cy = y + (j // 2) * passo
                conta = a in pesi
                T.text(surf, self.ATTR_LABEL.get(a, a), (cx, cy), 12,
                       T.TEXT if conta else T.DIM, bold=conta, maxw=cw - 40)
                T.text(surf, f"{v:.0f}", (cx + cw - 12, cy), 12,
                       T.stat_colour(v, 55, 85), bold=True, align="right")
            y += ((n + 1) // 2) * passo
        else:
            passo = max(18, min(22, spazio // n))
            for a in STAFF_ATTRS:
                v = getattr(s, a)
                conta = a in pesi
                T.text(surf, self.ATTR_LABEL.get(a, a), (c.x + 16, y), 13,
                       T.TEXT if conta else T.DIM, bold=conta, maxw=120)
                T.bar(surf, (c.x + 146, y + 5, c.w - 218, 8), v, 100,
                      T.stat_colour(v, 55, 85))
                T.text(surf, f"{v:.0f}", (c.right - 16, y), 13,
                       T.stat_colour(v, 55, 85), bold=True, align="right")
                y += passo

        # --- cosa cambierebbe, e se accetterebbe
        y += 6
        if self.sel_from == "mine":
            resta = max(1, s.contract_until - gs.season)
            for riga in (f"Mandarlo via costa la buonuscita di quello che resta di",
                         f"contratto: {s.salary * max(0.5, resta):.2f} M$, fuori dal tetto di spesa.",
                         "Il rinnovo si fa lasciandolo scadere e riassumendolo dal mercato."):
                T.text(surf, riga, (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
                y += 17
            return
        attuale = team.role(s.role)
        if attuale is s:
            T.text(surf, "E' gia' dei nostri.", (c.x + 16, y), 13, T.DIM)
            return
        if attuale is not None:
            ora = market.role_score(gs, attuale, s.role)
            delta = voto - ora
            col = T.OK if delta > 1 else (T.BAD if delta < -1 else T.DIM)
            T.text(surf, f"Al posto di {attuale.name} ({ora:.0f}): {delta:+.0f} nel ruolo",
                   (c.x + 16, y), 13, col, maxw=c.w - 32)
        else:
            T.text(surf, "Il posto e' vuoto: chiunque e' meglio di nessuno.",
                   (c.x + 16, y), 13, T.OK, maxw=c.w - 32)
        y += 20
        gradimento = market.staff_interest(gs, team, s, round(self.offer_salary, 2))
        col = T.OK if gradimento > 0.7 else (T.WARN if gradimento > 0.4 else T.BAD)
        T.text(surf, "Accetterebbe", (c.x + 16, y), 13, T.DIM)
        T.bar(surf, (c.x + 146, y + 5, c.w - 218, 8), gradimento * 100, 100, col)
        T.text(surf, f"{gradimento*100:.0f}%", (c.right - 16, y), 13, col, bold=True,
               align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        for col in (self.colA, self.colB, self.colC):
            T.panel(surf, col, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ORGANIGRAMMA", (self.colA.x + 16, self.colA.y + 12), 12,
               T.DIM_2, bold=True)
        T.text(surf, f"{team.leaders_cost:.1f} M$/anno",
               (self.colA.right - 16, self.colA.y + 12), 11, T.DIM_2, align="right")
        T.text(surf, "MERCATO", (self.colB.x + 16, self.colB.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, f"{len(self.market_list.items)} nomi",
               (self.colB.right - 16, self.colB.y + 12), 11, T.DIM_2, align="right")
        T.text(surf, "SCHEDA", (self.colC.x + 16, self.colC.y + 12), 12, T.DIM_2, bold=True)
        self._draw_card(surf)
        super().draw(surf)
