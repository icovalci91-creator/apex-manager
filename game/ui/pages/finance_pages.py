"""Pagina Finanze: bilancio mese per mese, per anno, e accordi commerciali."""
from __future__ import annotations

import pygame

from ...core import economy, sponsors as SP
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, Tabs, card


class FinancePage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.tab = 0
        self.sel_sponsor = None
        self.sel_deal = None
        self.ask = 10.0
        self.years = 3

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.tabs = Tabs((r.x, r.y, r.w, 34), ["Bilancio", "Sponsor"],
                         on_change=self._switch, w=170)
        self.tabs.index = self.tab
        for i, b in enumerate(self.tabs.buttons):
            b.active = (i == self.tab)
        self.widgets.append(self.tabs)
        if self.tab == 0:
            self._build_bilancio()
        else:
            self._build_sponsor()

    def _switch(self, i: int) -> None:
        self.tab = i
        self.build()

    def _build_bilancio(self) -> None:
        pass

    def _build_sponsor(self) -> None:
        r = self.rect
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 46, r.w * 0.52 - 4, r.h - 46)
        self.market = ScrollList((right.x + 12, right.y + 40, right.w - 24, r.h * 0.40),
                                 row_h=42, draw_row=self._row_sponsor,
                                 on_select=self._pick_sponsor)
        self.widgets.append(self.market)
        oy = right.y + 46 + r.h * 0.40
        self.s_val = Slider((right.x + 16, oy + 54, right.w - 32, 28), "Cifra richiesta",
                            self.ask, 0.5, 110.0, on_change=self._set_ask, fmt="{:.1f} M$")
        self.s_yrs = Slider((right.x + 16, oy + 90, right.w - 32, 28), "Durata",
                            self.years, 1, 6, on_change=self._set_years, fmt="{:.0f} anni")
        self.widgets += [self.s_val, self.s_yrs]
        self.widgets.append(Button((right.x + 16, oy + 130, 230, 38),
                                   "Presenta la proposta", self.offer, "primary"))

        left = pygame.Rect(r.x, r.y + 46, r.w * 0.46, r.h - 46)
        self.mine = ScrollList((left.x + 12, left.y + 40, left.w - 24, left.h - 100),
                               row_h=46, draw_row=self._row_deal, on_select=self._pick_deal)
        self.widgets.append(self.mine)
        self.widgets.append(Button((left.x + 12, left.bottom - 50, 250, 36),
                                   "Rescindi il selezionato", self.terminate, "danger"))
        self._fill()

    def _fill(self) -> None:
        gs, team = self.gs, self.team
        self.mine.items = sorted(team.deals, key=lambda d: -d.value)
        pool = [s for s in gs.sponsor_pool if SP.will_talk(gs, team, s)[0]]
        pool.sort(key=lambda s: -SP.offer_value(gs, team, s))
        self.market.items = pool
        if pool and self.sel_sponsor not in pool:
            self._pick_sponsor(0, pool[0])

    # ------------------------------------------------------------------ azioni
    def _set_ask(self, v) -> None:
        self.ask = v

    def _set_years(self, v) -> None:
        self.years = int(round(v))

    def _pick_sponsor(self, i, s) -> None:
        self.sel_sponsor = s
        self.ask = SP.offer_value(self.gs, self.team, s)
        self.s_val.value = self.ask
        lo, hi = s.get("years", [2, 4])
        self.years = lo
        self.s_yrs.value = lo

    def _pick_deal(self, i, d) -> None:
        self.sel_deal = d

    def offer(self) -> None:
        if not self.sel_sponsor:
            return
        esito, msg = SP.negotiate(self.gs, self.team, self.sel_sponsor,
                                  round(self.ask, 1), self.years)
        self.app.toast(msg)
        if esito == "accepted":
            self.gs.push(msg, "team")
            self.build()

    def terminate(self) -> None:
        if not self.sel_deal or self.sel_deal not in self.team.deals:
            self.app.toast("Seleziona prima un accordo in corso.")
            return
        ok, msg = SP.terminate(self.gs, self.team, self.sel_deal)
        self.app.toast(msg)
        if ok:
            self.sel_deal = None
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- righe
    def _row_deal(self, surf, rect, i, d) -> None:
        gs = self.gs
        s = SP.find(gs, d.sponsor)
        col = {"title": T.GOLD, "primary": T.ACCENT,
               "secondary": T.OK, "technical": T.DIM}.get(d.tier, T.DIM)
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, s["name"] if s else d.sponsor, (rect.x + 18, rect.y + 4), 15,
               T.TEXT, bold=True, maxw=210)
        T.text(surf, SP.TIER_LABEL.get(d.tier, ""), (rect.x + 18, rect.y + 24), 12, col)
        T.text(surf, f"{d.value:.1f} M$/anno", (rect.right - 14, rect.y + 4), 15,
               T.GOLD, bold=True, align="right")
        anni = "ultimo anno" if d.years_left <= 1 else f"ancora {d.years_left} anni"
        T.text(surf, anni, (rect.right - 14, rect.y + 25), 12,
               T.WARN if d.years_left <= 1 else T.DIM, align="right")

    def _row_sponsor(self, surf, rect, i, s) -> None:
        gs, team = self.gs, self.team
        col = {"title": T.GOLD, "primary": T.ACCENT,
               "secondary": T.OK, "technical": T.DIM}.get(s["tier"], T.DIM)
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, s["name"], (rect.x + 18, rect.y + 3), 15, T.TEXT, maxw=190)
        T.text(surf, f"{SP.TIER_LABEL[s['tier']]} - {s['sector']}",
               (rect.x + 18, rect.y + 23), 12, T.DIM, maxw=230)
        T.text(surf, f"{SP.offer_value(gs, team, s):.1f} M$", (rect.right - 14, rect.y + 3),
               15, T.GOLD, bold=True, align="right")
        lo, hi = s.get("years", [2, 4])
        T.text(surf, f"{lo}-{hi} anni", (rect.right - 14, rect.y + 24), 12, T.DIM,
               align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        if self.tab == 0:
            self._draw_bilancio(surf)
        else:
            self._draw_sponsor(surf)
        super().draw(surf)

    def _draw_bilancio(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        anno = gs.season
        tot = economy.season_summary(team, anno)
        cw = (r.w - 48) / 4
        y0 = r.y + 46
        card(surf, (r.x, y0, cw, 86), "Liquidita'", T.fmt_money(team.cash),
             "cassa disponibile oggi", accent=T.OK if team.cash > 0 else T.BAD,
             colour=T.TEXT if team.cash > 0 else T.BAD)
        card(surf, (r.x + cw + 16, y0, cw, 86), f"Entrate {anno}",
             f"{tot['in']:.1f} M$", "sponsor, premi, cessioni", accent=T.OK)
        card(surf, (r.x + 2 * (cw + 16), y0, cw, 86), f"Uscite {anno}",
             f"{tot['out']:.1f} M$", "tutte le voci di costo", accent=T.BAD)
        prev = economy.cap_forecast(gs, team)
        col_r = (T.BAD if prev["rischio"] > 0.4 else
                 T.WARN if prev["rischio"] > 0.12 else T.OK)
        card(surf, (r.x + 3 * (cw + 16), y0, cw, 86), "Tetto di spesa a fine anno",
             f"{prev['previsto']:.0f} / {prev['limite']:.0f}",
             f"+/-{prev['errore']:.0f} M$  -  rischio di sforare {prev['rischio']*100:.0f}%",
             colour=col_r, accent=T.GOLD)

        # ---- mese per mese
        left = pygame.Rect(r.x, y0 + 100, r.w * 0.46, r.h - 146)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, f"MESE PER MESE - {anno}", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        for lab, x in (("MESE", 16), ("ENTRATE", 150), ("USCITE", 232), ("SALDO", 320)):
            T.text(surf, lab, (left.x + x, left.y + 32), 11, T.DIM_2, bold=True)
        righe = [m for m in economy.by_month(team, anno) if m["in"] or m["out"]]
        picco = max([max(m["in"], m["out"]) for m in righe] + [1.0])
        yy = left.y + 52
        for m in righe:
            T.text(surf, m["label"], (left.x + 16, yy), 13, T.TEXT)
            T.text(surf, f"{m['in']:.2f}", (left.x + 222, yy), 13, T.OK, align="right")
            T.text(surf, f"{m['out']:.2f}", (left.x + 305, yy), 13, T.BAD, align="right")
            T.text(surf, f"{m['net']:+.2f}", (left.x + 400, yy), 13,
                   T.OK if m["net"] >= 0 else T.BAD, bold=True, align="right")
            # barra a due colori: entrate sopra, uscite sotto
            bw = left.w - 440
            if bw > 40:
                T.bar(surf, (left.x + 416, yy + 3, int(bw * m["in"] / picco), 6), 100, 100, T.OK)
                T.bar(surf, (left.x + 416, yy + 11, int(bw * m["out"] / picco), 6), 100, 100, T.BAD)
            yy += 22
        yy += 8
        T.text(surf, "ANNO PER ANNO", (left.x + 16, yy), 12, T.DIM_2, bold=True)
        yy += 22
        for a in economy.by_year(team)[-6:]:
            T.text(surf, str(a["season"]), (left.x + 16, yy), 13, T.TEXT, bold=True)
            T.text(surf, f"{a['in']:.1f}", (left.x + 222, yy), 13, T.OK, align="right")
            T.text(surf, f"{a['out']:.1f}", (left.x + 305, yy), 13, T.BAD, align="right")
            T.text(surf, f"{a['net']:+.1f}", (left.x + 400, yy), 13,
                   T.OK if a["net"] >= 0 else T.BAD, bold=True, align="right")
            yy += 20

        # ---- il conto del direttore finanziario
        right = pygame.Rect(r.x + r.w * 0.48, y0 + 100, r.w * 0.52 - 4, r.h - 146)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        cfo = team.role("financial_director")
        T.text(surf, "TETTO DI SPESA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, cfo.name if cfo else "nessun direttore finanziario",
               (right.right - 16, right.y + 12), 11,
               T.DIM_2 if cfo else T.BAD, align="right")
        yy = right.y + 36
        for lab, val, colr in (
                ("Gia' speso", f"{prev['speso']:.1f} M$", T.TEXT),
                ("Impegnato sui pacchetti aperti", f"{prev['impegnato']:.1f} M$", T.WARN),
                (f"Costi fissi delle {prev['gare']} gare che restano",
                 f"{prev['fissi']:.1f} M$", T.DIM),
                ("Previsione a fine stagione",
                 f"{prev['previsto']:.1f} su {prev['limite']:.0f}", col_r),
                ("Margine", f"{prev['margine']:+.1f} M$  (+/-{prev['errore']:.0f})", col_r),
                ("Si puo' ancora impegnare",
                 f"{economy.spendable(gs, team):.1f} M$", T.OK)):
            T.text(surf, lab, (right.x + 16, yy), 13, T.DIM, maxw=right.w * 0.6)
            T.text(surf, val, (right.right - 16, yy), 13, colr, bold=True, align="right")
            yy += 22
        # la barra: quanto del tetto e' gia' impegnato, e dove finisce la stima
        bar = pygame.Rect(right.x + 16, yy + 8, right.w - 32, 14)
        T.panel(surf, bar, T.PANEL_3, radius=4)
        lim = max(1.0, prev["limite"])
        pygame.draw.rect(surf, T.ACCENT,
                         (bar.x, bar.y, int(bar.w * min(1.0, prev["speso"] / lim)), bar.h),
                         border_radius=4)
        pygame.draw.rect(surf, T.WARN,
                         (bar.x + int(bar.w * min(1.0, prev["speso"] / lim)), bar.y,
                          int(bar.w * min(1.0, prev["impegnato"] / lim)), bar.h))
        px = bar.x + int(bar.w * min(1.15, prev["previsto"] / lim))
        pygame.draw.line(surf, col_r, (px, bar.y - 5), (px, bar.bottom + 5), 3)
        yy += 34
        _c, frase = economy.cap_advice(gs, team)
        T.text(surf, frase, (right.x + 16, yy), 13, col_r, maxw=right.w - 32)
        yy += 30

        T.text(surf, "DA DOVE ARRIVANO", (right.x + 16, yy), 12, T.DIM_2, bold=True)
        entrate = economy.by_category(team, anno, "in")
        mx_in = max([v["amount"] for v in entrate] + [1.0])
        yy += 24
        for v in entrate:
            T.text(surf, v["label"], (right.x + 16, yy), 13, T.TEXT, maxw=250)
            T.bar(surf, (right.x + 280, yy + 4, right.w - 380, 8), v["amount"], mx_in, T.OK)
            T.text(surf, f"{v['amount']:.1f}", (right.right - 16, yy), 13, T.TEXT,
                   bold=True, align="right")
            yy += 22
        yy += 14
        T.text(surf, "DOVE VANNO", (right.x + 16, yy), 12, T.DIM_2, bold=True)
        yy += 24
        uscite = economy.by_category(team, anno, "out")
        mx_out = max([v["amount"] for v in uscite] + [1.0])
        for v in uscite:
            T.text(surf, v["label"], (right.x + 16, yy), 13, T.TEXT, maxw=250)
            T.bar(surf, (right.x + 280, yy + 4, right.w - 380, 8), v["amount"], mx_out, T.BAD)
            T.text(surf, f"{v['amount']:.1f}", (right.right - 16, yy), 13, T.TEXT,
                   bold=True, align="right")
            yy += 22


    def _draw_sponsor(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        left = pygame.Rect(r.x, r.y + 46, r.w * 0.46, r.h - 46)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        tot = SP.annual_income(team)
        T.text(surf, f"I NOSTRI ACCORDI  -  {tot:.1f} M$ ALL'ANNO",
               (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 46, r.w * 0.52 - 4, r.h - 46)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CHI SI SIEDE AL TAVOLO", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        appeal = SP.team_appeal(gs, team)
        T.text(surf, f"appeal commerciale {appeal*100:.0f}/100",
               (right.right - 16, right.y + 12), 12,
               T.stat_colour(appeal * 100, 40, 75), bold=True, align="right")

        oy = right.y + 46 + r.h * 0.40
        s = self.sel_sponsor
        if s:
            equo = SP.offer_value(gs, team, s)
            T.text(surf, s["name"], (right.x + 16, oy), 18, T.TEXT, bold=True)
            T.text(surf, s["desc"], (right.x + 16, oy + 24), 12, T.DIM, maxw=right.w - 32)
            col = T.OK if self.ask <= equo * 1.05 else (
                T.WARN if self.ask <= equo * 1.35 else T.BAD)
            giudizio = ("dovrebbe accettare" if self.ask <= equo * 1.05 else
                        "proveranno a trattare" if self.ask <= equo * 1.35 else
                        "si alzeranno dal tavolo")
            T.text(surf, f"Valutazione equa {equo:.1f} M$/anno - {giudizio}",
                   (right.x + 16, oy + 182), 13, col, bold=True)
            bonus = (f"bonus: {s['bonus_win']:.2f} a vittoria, {s['bonus_podium']:.2f} "
                     f"a podio, {s['bonus_title']:.1f} per il titolo")
            T.text(surf, bonus, (right.x + 16, oy + 202), 12, T.DIM, maxw=right.w - 32)
        else:
            T.text(surf, "Nessuno sponsor disponibile: hai gli spazi pieni oppure "
                         "i marchi liberi non trattano con noi.",
                   (right.x + 16, oy), 13, T.DIM, maxw=right.w - 32)
