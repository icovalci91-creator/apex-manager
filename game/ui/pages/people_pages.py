"""Pagine: piloti e mercato, staff tecnico."""
from __future__ import annotations

import pygame

from ...core import economy, market
from ...model.people import STAFF_ATTRS
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, card


class DriversPage(Page):
    """I nostri piloti, il mercato e la scheda di chiunque sia selezionato.

    Stessa impostazione della pagina dello staff: la scheda vale per i nostri
    come per quelli che si prova a prendere, con i numeri scritti accanto alle
    barre e, sotto, il tavolo della trattativa.
    """

    ATTRS = (
        ("pace", "Passo", True),
        ("racecraft", "Duello", True),
        ("consistency", "Costanza", True),
        ("tyre_mgmt", "Gestione gomme", True),
        ("wet", "Bagnato", True),
        ("feedback", "Riscontro tecnico", True),
        ("aggression", "Aggressivita'", False),
        ("stamina", "Resistenza", False),
        ("marketability", "Appeal commerciale", False),
    )
    FILTRI = (("nostri", "I nostri"), ("liberi", "Svincolati"),
              ("tutti", "Griglia"), ("giovani", "Giovani"))

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.filter = "liberi"
        self.seat = "titolare"                # per quale posto si tratta
        self.neg = None                       # trattativa aperta
        self.offer = market.Offer()

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        wA = r.w * 0.27
        wB = r.w * 0.31
        self.colA = pygame.Rect(r.x, r.y, wA, r.h)
        self.colB = pygame.Rect(r.x + wA + 16, r.y, wB, r.h)
        self.colC = pygame.Rect(r.x + wA + wB + 32, r.y, r.w - wA - wB - 32, r.h)

        self.mine = ScrollList((self.colA.x + 10, self.colA.y + 40, self.colA.w - 20,
                                self.colA.h - 76), row_h=64,
                               draw_row=self._row_mine, on_select=self._select_mine)
        self.widgets.append(self.mine)

        self.tabs = []
        bw = (self.colB.w - 28) / 4
        for i, (key, lab) in enumerate(self.FILTRI):
            b = Button((self.colB.x + 10 + i * (bw + 4), self.colB.y + 36, bw, 26), lab)
            b.on_click = (lambda k=key: self.set_filter(k))
            self.tabs.append(b)
            self.widgets.append(b)
        self._mark_tabs()
        self.list = ScrollList((self.colB.x + 10, self.colB.y + 70, self.colB.w - 20,
                                self.colB.h - 86), row_h=44,
                               draw_row=self._row, on_select=self._select)
        self.widgets.append(self.list)

        # --- il tavolo della trattativa, ancorato in fondo alla scheda
        c = self.colC
        self.sliders = {}
        rows = [
            ("salary", "Ingaggio", 0.5, 70.0, "{:.1f} M$"),
            ("years", "Durata", 1, 5, "{:.0f} anni"),
            ("bonus_win", "Bonus vittoria", 0.0, 6.0, "{:.2f} M$"),
            ("bonus_podium", "Bonus podio", 0.0, 3.0, "{:.2f} M$"),
            ("bonus_points", "Bonus a punto", 0.0, 0.30, "{:.3f} M$"),
            ("release_clause", "Clausola", 0.0, 250.0, "{:.0f} M$"),
        ]
        # una colonna sola: su due il numero finiva sopra il pulsantino del piu'
        self.sy = c.bottom - 68 - len(rows) * 28
        for i, (key, lab, lo, hi, fmt) in enumerate(rows):
            sl = Slider((c.x + 16, self.sy + i * 28, c.w - 32, 26), lab,
                        getattr(self.offer, key), lo, hi,
                        on_change=(lambda v, k=key: self._set(k, v)), fmt=fmt)
            self.sliders[key] = sl
            self.widgets.append(sl)
        self.seat_buttons = []
        sw = (c.w - 44) / 2
        for i, (key, lab) in enumerate((("titolare", "Titolare"),
                                        ("riserva", "Terzo pilota"))):
            b = Button((c.x + 16 + i * (sw + 12), self.sy - 36, sw, 26), lab)
            b.on_click = (lambda k=key: self._pick_seat(k))
            self.seat_buttons.append(b)
            self.widgets.append(b)
        self._mark_seat()
        by = c.bottom - 58
        bw = (c.w - 44) / 3
        self.neg_btn = Button((c.x + 16, by, bw, 38),
                              "Proponi" if self.neg and self.neg.open else "Trattativa",
                              self.negotiate, "primary")
        self.drop_btn = Button((c.x + 28 + bw, by, bw, 38), "Lascia perdere", self.drop, "ghost")
        self.free_btn = Button((c.x + 40 + 2 * bw, by, bw, 38), "Libera il pilota",
                               self.release, "danger")
        self.widgets += [self.neg_btn, self.drop_btn, self.free_btn]
        self._fill()

    def _fill(self) -> None:
        gs = self.gs
        self.mine.items = gs.drivers_of(self.team.id) + gs.reserves_of(self.team.id)
        if self.filter == "nostri":
            items = list(self.mine.items)
        elif self.filter == "liberi":
            items = list(gs.free_agents)
        elif self.filter == "giovani":
            items = [d for d in list(gs.drivers.values()) + gs.free_agents if d.age <= 23]
        else:
            items = ([d for d in gs.drivers.values() if d.team != self.team.id]
                     + list(gs.free_agents))
        items.sort(key=lambda d: -d.overall)
        self.list.items = items
        if self.sel is None and items:
            self._select(0, items[0])
        if self.sel in items:
            self.list.selected = items.index(self.sel)
        if self.sel in self.mine.items:
            self.mine.selected = self.mine.items.index(self.sel)
        self._sync_buttons()

    def _pick_seat(self, k) -> None:
        self.seat = k
        self.neg = None
        if self.sel:
            self._select(0, self.sel)
        self._mark_seat()
        self._sync_buttons()

    def _mark_seat(self) -> None:
        for b, key in zip(self.seat_buttons, ("titolare", "riserva")):
            b.active = (key == self.seat)
            b.style = "tab" if b.active else "normal"

    def _sync_buttons(self) -> None:
        nostro = bool(self.sel and self.sel.team == self.team.id)
        self.free_btn.visible = nostro
        self.free_btn.enabled = nostro
        aperta = bool(self.neg and self.sel and self.neg.driver_id == self.sel.id
                      and self.neg.open)
        self.neg_btn.label = "Proponi" if aperta else "Trattativa"
        self.drop_btn.visible = aperta
        self.drop_btn.enabled = aperta

    # ------------------------------------------------------------------ azioni
    def _set(self, key, v) -> None:
        setattr(self.offer, key, int(round(v)) if key == "years" else v)

    def set_filter(self, k) -> None:
        self.filter = k
        self._mark_tabs()
        self._fill()

    def _mark_tabs(self) -> None:
        for b, (key, _l) in zip(self.tabs, self.FILTRI):
            b.active = (key == self.filter)
            b.style = "tab" if b.active else "normal"

    def _select(self, i, item) -> None:
        if self.sel is not item:
            self.neg = None
        self.sel = item
        quota = 1.0 if self.seat == "titolare" else market.RESERVE_SHARE
        self.offer = market.Offer(salary=max(0.4, item.market_value * quota), years=2,
                                  release_clause=round(item.market_value * quota * 2.5, 0))
        self._sync_sliders()
        self._sync_buttons()

    def _select_mine(self, i, item) -> None:
        self._select(i, item)
        self.list.selected = (self.list.items.index(item)
                              if item in self.list.items else -1)

    def _sync_sliders(self) -> None:
        for k, sl in getattr(self, "sliders", {}).items():
            sl.value = getattr(self.offer, k)

    def negotiate(self) -> None:
        if not self.sel:
            return
        gs, team, d = self.gs, self.team, self.sel
        if self.neg is None or not self.neg.open or self.neg.driver_id != d.id:
            ok, why = market.can_offer_seat(gs, team, d, self.seat)
            if not ok:
                self.app.toast(why)
                return
            self.neg = market.open_negotiation(gs, team, d, self.seat)
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
        if not self.sel or self.sel.team != self.team.id:
            return
        ok, msg = market.release_driver(self.gs, self.team, self.sel)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel = None
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- le righe
    def _row_mine(self, surf, rect, i, d) -> None:
        riserva = d.seat == "riserva"
        col = T.DIM_2 if riserva else T.hex_rgb(self.team.colour)
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        if riserva:
            T.text(surf, "TERZO PILOTA", (rect.x + 18, rect.y + 2), 10, T.GOLD, bold=True)
        T.text(surf, d.name, (rect.x + 18, rect.y + (12 if riserva else 6)), 15, T.TEXT,
               bold=True, maxw=rect.w - 110)
        T.text(surf, f"#{d.number}", (rect.right - 12, rect.y + 4), 15, col, bold=True,
               align="right")
        T.text(surf, f"{d.age} anni  -  fino al {d.contract_until}  -  "
                     f"{d.salary:.1f} M$", (rect.x + 18, rect.y + 26), 11, T.DIM,
               maxw=rect.w - 100)
        T.text(surf, f"{d.overall:.0f}", (rect.right - 12, rect.y + 24), 16,
               T.stat_colour(d.overall, 70, 90), bold=True, align="right")
        lic = d.penalty_points
        col_lic = T.BAD if lic >= 9 else (T.WARN if lic >= 6 else T.DIM_2)
        T.text(surf, f"morale {d.morale:.0f}   forma {d.form:+.1f}   licenza {lic}/12",
               (rect.x + 18, rect.y + 44), 11, col_lic, maxw=rect.w - 30)

    def _row(self, surf, rect, i, d) -> None:
        team = self.gs.teams.get(d.team)
        col = T.hex_rgb(team.colour) if team else T.DIM_2
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 8, 3, rect.h - 16))
        T.text(surf, d.name, (rect.x + 16, rect.y + 4), 14, T.TEXT, maxw=rect.w - 96)
        T.text(surf, f"{d.age}a  -  {team.short if team else 'svincolato'}",
               (rect.x + 16, rect.y + 23), 11, T.DIM, maxw=rect.w - 96)
        T.text(surf, f"{d.overall:.0f}", (rect.right - 12, rect.y + 4), 16,
               T.stat_colour(d.overall, 70, 90), bold=True, align="right")
        margine = max(0.0, d.potential - d.overall)
        T.text(surf, f"{d.market_value:.1f} M$" + (f"  +{margine:.0f}" if margine > 2 else ""),
               (rect.right - 12, rect.y + 25), 11, T.GOLD, align="right")

    # --------------------------------------------------------------- la scheda
    def _draw_card(self, surf) -> None:
        c, gs, team = self.colC, self.gs, self.team
        d = self.sel
        if d is None:
            T.text(surf, "Scegli un pilota da una delle due liste.",
                   (c.x + 16, c.y + 48), 14, T.DIM, maxw=c.w - 32)
            return
        squadra = gs.teams.get(d.team)
        nostro = d.team == team.id
        col = T.hex_rgb(squadra.colour) if squadra else T.DIM_2
        T.text(surf, d.name, (c.x + 16, c.y + 32), 20, T.TEXT, bold=True, maxw=c.w - 90)
        T.text(surf, f"#{d.number}", (c.right - 16, c.y + 32), 20, col, bold=True,
               align="right")
        posto = ""
        if squadra is not None:
            posto = "  -  terzo pilota" if d.seat == "riserva" else "  -  titolare"
        T.text(surf, f"{d.age} anni  -  {d.nat}  -  "
                     f"{squadra.name if squadra else 'svincolato'}{posto}",
               (c.x + 16, c.y + 60), 13, T.DIM, maxw=c.w - 32)
        pygame.draw.line(surf, T.LINE, (c.x + 16, c.y + 84), (c.right - 16, c.y + 84))

        margine = max(0.0, d.potential - d.overall)
        righe = [("Valutazione", f"{d.overall:.1f} / 100", T.stat_colour(d.overall, 70, 90)),
                 ("Potenziale", f"{d.potential:.0f}" + (f"   ancora +{margine:.0f}" if margine > 0.5
                                                        else "   e' al suo massimo"),
                  T.OK if margine > 4 else T.DIM)]
        if nostro:
            righe.append(("Ingaggio", f"{d.salary:.1f} M$ all'anno", T.GOLD))
            righe.append(("Contratto", f"fino al {d.contract_until}", T.TEXT))
            if d.release_clause > 0:
                righe.append(("Clausola nel contratto", f"{d.release_clause:.0f} M$", T.WARN))
        else:
            righe.append(("Quanto vale", f"{d.market_value:.1f} M$ all'anno", T.GOLD))
            if squadra:
                fee = market.buyout_cost(gs, d)
                voce = "Clausola" if d.release_clause > 0 else "Indennizzo"
                righe.append((f"{voce} per portarlo via", f"{fee:.0f} M$", T.WARN))
            else:
                righe.append(("Situazione", "libero, nessun indennizzo", T.OK))
        # da qui in giu' comincia il tavolo della trattativa: la scheda si
        # stringe per starci sopra, invece di scriverci dentro
        limite = self.sy - 78
        n_att = (len(self.ATTRS) + 1) // 2
        spazio = limite - (c.y + 94)
        largo = spazio >= len(righe) * 21 + 28 + n_att * 22 + 26
        p_r = 21 if largo else 17
        p_a = 22 if largo else 18

        y = c.y + 94
        for lab, val, colr in righe:
            if y + p_r > limite:
                break
            T.text(surf, lab, (c.x + 16, y), 13, T.DIM, maxw=c.w * 0.5)
            T.text(surf, val, (c.right - 16, y), 13, colr, bold=True, align="right",
                   maxw=c.w * 0.5)
            y += p_r

        # --- attributi su due colonne, con il numero accanto alla barra
        y += 8
        if y + 20 + n_att * p_a <= limite:
            T.text(surf, "ATTRIBUTI", (c.x + 16, y), 12, T.DIM_2, bold=True)
            if largo:
                T.text(surf, "in grassetto quelli che fanno la valutazione",
                       (c.right - 16, y), 11, T.DIM_2, align="right")
            y += 20
            cw = (c.w - 32) / 2
            barra = cw - 168 >= 44       # sotto questa soglia la barra e' un moncone
            for j, (a, lab, conta) in enumerate(self.ATTRS):
                v = getattr(d, a)
                cx = c.x + 16 + (j % 2) * cw
                cy = y + (j // 2) * p_a
                T.text(surf, lab, (cx, cy), 12, T.TEXT if conta else T.DIM, bold=conta,
                       maxw=cw - (46 if barra else 34))
                if barra:
                    T.bar(surf, (cx + 122, cy + 5, cw - 168, 7), v, 100,
                          T.stat_colour(v, 65, 90))
                T.text(surf, f"{v:.0f}", (cx + cw - 14, cy), 12, T.stat_colour(v, 65, 90),
                       bold=True, align="right")
            y += n_att * p_a + 8

        # --- come sta, e cosa ha fatto
        lic = d.penalty_points
        col_lic = T.BAD if lic >= 9 else (T.WARN if lic >= 6 else T.DIM)
        if y + 18 <= limite:
            T.text(surf, f"Morale {d.morale:.0f}   Forma {d.form:+.1f}   "
                         f"Punti {d.points:.0f}   Vittorie {d.wins}   Podi {d.podiums}",
                   (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
            y += 18
        # quanto si fida della macchina che ha sotto: cambia il giro secco piu'
        # di quanto cambi il passo gara
        if y + 18 <= limite and d.team:
            from ...core import driving
            fid = float(getattr(d, "confidence", driving.FIDUCIA_BASE))
            T.text(surf, f"Fiducia nella macchina {fid:.0f}   -   {driving.confidence_label(d)}",
                   (c.x + 16, y), 12, T.stat_colour(fid, 45, 75), maxw=c.w - 32)
            y += 18
        if y + 18 <= limite:
            testo = f"Licenza {lic}/12 punti   -   in carriera {d.races} gare, "
            testo += f"{d.career_points:.0f} punti"
            if d.banned_races > 0:
                testo = f"SQUALIFICATO per {d.banned_races} gara   -   " + testo
            T.text(surf, testo, (c.x + 16, y), 12, col_lic, maxw=c.w - 32)

        # --- il tavolo
        # un po' piu' in alto di prima: sotto il titolo ci va anche il motivo
        # per cui un posto non e' disponibile, e finiva sopra i due pulsanti
        ty = self.sy - 96
        T.text(surf, "TRATTATIVA", (c.x + 16, ty), 12, T.DIM_2, bold=True)
        ok_posto, perche = market.can_offer_seat(gs, team, d, self.seat)
        if not ok_posto:
            T.text(surf, perche, (c.x + 16, ty + 36), 12, T.WARN, maxw=c.w - 32)
        mine = market.offer_value(gs, team, d, self.offer)
        T.text(surf, f"la nostra offerta vale {mine:.1f} M$ l'anno per lui",
               (c.x + 16, ty + 18), 12, T.DIM, maxw=c.w * 0.6)
        if self.neg and self.neg.driver_id == d.id:
            want = market.demand_value(gs, team, d, self.neg)
            colr = T.OK if mine >= want * 0.98 else (T.WARN if mine >= want * 0.85 else T.BAD)
            T.text(surf, f"lui ne chiede {want:.1f}", (c.right - 16, ty + 18), 12, colr,
                   bold=True, align="right")
            stato = {"aperta": T.TEXT, "accordo": T.OK, "rotta": T.BAD}[self.neg.state]
            T.text(surf, self.neg.last, (c.x + 16, ty - 22), 12, stato, maxw=c.w - 32)
            if self.neg.open:
                giri = max(0, self.neg.patience - self.neg.rounds)
                T.text(surf, f"ancora {giri} giri prima che si alzi dal tavolo",
                       (c.right - 16, ty), 11, T.DIM_2, align="right")
        elif c.w > 470:
            T.text(surf, "Apri la trattativa per sentire cosa chiede.",
                   (c.right - 16, ty + 18), 11, T.DIM_2, align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        team = self.team
        for col in (self.colA, self.colB, self.colC):
            T.panel(surf, col, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I NOSTRI PILOTI", (self.colA.x + 16, self.colA.y + 12), 12,
               T.DIM_2, bold=True)
        T.text(surf, "MERCATO", (self.colB.x + 16, self.colB.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, f"{len(self.list.items)} nomi",
               (self.colB.right - 16, self.colB.y + 12), 11, T.DIM_2, align="right")
        T.text(surf, "SCHEDA", (self.colC.x + 16, self.colC.y + 12), 12, T.DIM_2, bold=True)
        self._draw_card(surf)
        # sotto i nostri piloti resta il conto di quanto costano
        drs = self.mine.items
        costo = sum(x.salary for x in drs)
        n_tit, n_ris = len(team.drivers), len(team.reserves)
        T.text(surf, f"Titolari {n_tit}/2   -   terzi piloti {n_ris}/2",
               (self.colA.x + 16, self.colA.bottom - 46), 12,
               T.DIM if n_ris else T.WARN, maxw=self.colA.w - 32)
        T.text(surf, f"Ingaggi {costo:.1f} M$ all'anno, fuori dal tetto di spesa",
               (self.colA.x + 16, self.colA.bottom - 28), 12, T.DIM_2,
               maxw=self.colA.w - 32)
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
