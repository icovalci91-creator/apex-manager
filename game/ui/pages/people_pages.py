"""Pagine: piloti e mercato, staff tecnico."""
from __future__ import annotations

import pygame

from ...core import economy, market
from ...model import people as PEOPLE
from ...model.people import STAFF_ATTRS
from .. import bandiere
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider


def _dove(gs, d) -> str:
    """Dove corre uno che non ha una scuderia di Formula 1.

    Puo' essere svincolato davvero, oppure avere un volante in Formula E: in
    quel caso il nome della squadra ci va, che e' la differenza fra uno che
    puoi chiamare domani e uno per cui devi pagare.
    """
    fe = getattr(d, "fe_squadra", "")
    if fe:
        return fe
    if getattr(d, "seat", "") == "formulae":
        return "Formula E, libero"
    return "svincolato"


class DriversPage(Page):
    """I piloti in due schermate invece che in tre colonne strette.

    La prima e' la lista: in alto i nostri - titolari e terzi piloti, uno
    per scheda grande - e sotto il mercato, largo quanto la pagina, con una
    colonna per ogni numero che conta. Un clic su un nome apre la seconda:
    la scheda del pilota a tutto schermo, con a sinistra chi e' e quanto
    vale, a destra cosa ci si puo' fare - il posto in squadra per i nostri,
    la trattativa per gli altri. "Torna ai piloti" riporta alla lista.
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
    FILTRI = (("liberi", "Svincolati"), ("tutti", "Griglia"), ("giovani", "Giovani"))
    CARTA_H = 136
    RIGA_H = 50

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.vista = "lista"                  # lista | scheda
        self.filter = "liberi"
        self.seat = "titolare"                # per quale posto si tratta
        self.neg = None                       # trattativa aperta
        self.offer = market.Offer()
        self.sliders: dict = {}
        self.seat_buttons: list = []
        self.posto_buttons: list = []
        self.carte: list = []

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        self.widgets = []
        self.sliders, self.seat_buttons, self.posto_buttons = {}, [], []
        if self.vista == "scheda" and self.sel is not None:
            self._build_scheda()
        else:
            self.vista = "lista"
            self._build_lista()

    def _nostri(self) -> list:
        """I posti della squadra, nell'ordine in cui si mostrano: due da
        titolare e due da terzo pilota, con None dove il posto e' libero."""
        gs, team = self.gs, self.team
        tit = gs.drivers_of(team.id)[:2]
        ris = gs.reserves_of(team.id)[:2]
        return ([(d, "titolare") for d in tit] + [(None, "titolare")] * (2 - len(tit))
                + [(d, "riserva") for d in ris] + [(None, "riserva")] * (2 - len(ris)))

    def _build_lista(self) -> None:
        r = self.rect
        # le schede dei nostri
        self.carte = []
        cw = (r.w - 3 * 16) / 4
        y = r.y + 30
        for i, (d, ruolo) in enumerate(self._nostri()):
            rc = pygame.Rect(int(r.x + i * (cw + 16)), y, int(cw), self.CARTA_H)
            self.carte.append((rc, d, ruolo))
            if d is not None:
                b = Button(rc, "", (lambda x=d: self.apri(x)), "invisible")
                self.widgets.append(b)
        # il mercato
        y0 = y + self.CARTA_H + 30
        self.tabs = []
        x = r.right
        for key, lab in reversed(self.FILTRI):
            larga = T.width(lab, 15, True) + 40
            x -= larga
            b = Button((x, y0 - 8, larga, 36), lab, (lambda k=key: self.set_filter(k)))
            self.tabs.append(b)
            self.widgets.append(b)
            x -= 8
        self.tabs.reverse()
        self._mark_tabs()
        self.list = ScrollList((r.x, y0 + 36, r.w, max(120, r.bottom - y0 - 36)),
                               row_h=self.RIGA_H, draw_row=self._row, header_h=34,
                               draw_header=self._testa_lista,
                               on_select=lambda i, d: self.apri(d))
        self.list.items = self._mercato()
        self.widgets.append(self.list)

    def _mercato(self) -> list:
        gs = self.gs
        if self.filter == "liberi":
            items = list(gs.free_agents)
        elif self.filter == "giovani":
            items = [d for d in list(gs.drivers.values()) + gs.free_agents
                     if d.age <= 23 and not d.ritirato and d.team != self.team.id]
        else:
            # e chi corre in Formula E sta in questa lista come tutti gli
            # altri: e' un pilota sotto contratto con una squadra vera, e come
            # da chiunque altro lo si porta via pagando l'indennizzo
            items = ([d for d in gs.drivers.values()
                      if d.team != self.team.id and not d.ritirato]
                     + list(gs.free_agents))
        items.sort(key=lambda d: -d.overall)
        return items

    def _build_scheda(self) -> None:
        r = self.rect
        self.back_btn = Button((r.x, r.y, 210, 40), "\u00ab  Torna ai piloti", self.chiudi,
                               "ghost")
        self.widgets.append(self.back_btn)
        self.pan_sx, self.pan_dx = _pannelli_scheda(r)
        c = self.pan_dx
        x0, w0 = c.x + 24, c.w - 48
        nostro = self.sel.team == self.team.id
        if nostro:
            # il posto in squadra: uno per ogni cambio possibile
            for i in range(3):
                b = Button((x0, c.y + 170 + i * 54, w0, 44), "")
                b.visible = False
                self.posto_buttons.append(b)
                self.widgets.append(b)
            self.free_btn = Button((x0, c.bottom - 68, w0, 46), "Libera il pilota",
                                   self.release, "danger")
            self.widgets.append(self.free_btn)
        else:
            sw = (w0 - 12) / 2
            for i, (key, lab) in enumerate((("titolare", "Da titolare"),
                                            ("riserva", "Da terzo pilota"))):
                b = Button((x0 + i * (sw + 12), c.y + 150, sw, 38), lab)
                b.on_click = (lambda k=key: self._pick_seat(k))
                self.seat_buttons.append(b)
                self.widgets.append(b)
            self._mark_seat()
            rows = [
                ("salary", "Ingaggio", 0.5, 70.0, "{:.1f} M$"),
                ("years", "Durata", 1, 5, "{:.0f} anni"),
                ("bonus_win", "Bonus vittoria", 0.0, 6.0, "{:.2f} M$"),
                ("bonus_podium", "Bonus podio", 0.0, 3.0, "{:.2f} M$"),
                ("bonus_points", "Bonus a punto", 0.0, 0.30, "{:.3f} M$"),
                ("release_clause", "Clausola", 0.0, 250.0, "{:.0f} M$"),
            ]
            passo = min(40, max(32, (c.bottom - 84 - (c.y + 204)) // len(rows)))
            for i, (key, lab, lo, hi, fmt) in enumerate(rows):
                sl = Slider((x0, c.y + 204 + i * passo, w0, 30), lab,
                            getattr(self.offer, key), lo, hi,
                            on_change=(lambda v, k=key: self._set(k, v)), fmt=fmt)
                self.sliders[key] = sl
                self.widgets.append(sl)
            bw = (w0 - 12) / 2
            self.neg_btn = Button((x0, c.bottom - 68, bw, 46),
                                  "Proponi" if self.neg and self.neg.open else "Apri la trattativa",
                                  self.negotiate, "primary")
            self.drop_btn = Button((x0 + bw + 12, c.bottom - 68, bw, 46), "Lascia perdere",
                                   self.drop, "ghost")
            self.widgets += [self.neg_btn, self.drop_btn]
        self._sync_buttons()

    # ------------------------------------------------------------ navigazione
    def apri(self, d) -> None:
        if self.sel is not d:
            self.neg = None
            quota = 1.0 if self.seat == "titolare" else market.RESERVE_SHARE
            self.offer = market.Offer(salary=max(0.4, d.market_value * quota), years=2,
                                      release_clause=round(d.market_value * quota * 2.5, 0))
        self.sel = d
        self.vista = "scheda"
        self.scroll = 0.0
        self.layout(self.view)

    def chiudi(self) -> None:
        self.vista = "lista"
        self.scroll = 0.0
        self.layout(self.view)

    def _pick_seat(self, k) -> None:
        self.seat = k
        self.neg = None
        if self.sel:
            quota = 1.0 if k == "titolare" else market.RESERVE_SHARE
            self.offer = market.Offer(salary=max(0.4, self.sel.market_value * quota), years=2,
                                      release_clause=round(self.sel.market_value * quota * 2.5, 0))
            self._sync_sliders()
        self._mark_seat()
        self._sync_buttons()

    def _mark_seat(self) -> None:
        for b, key in zip(self.seat_buttons, ("titolare", "riserva")):
            b.active = (key == self.seat)
            b.style = "tab" if b.active else "normal"

    def _sync_buttons(self) -> None:
        if self.vista != "scheda" or self.sel is None:
            return
        nostro = self.sel.team == self.team.id
        if not nostro:
            aperta = bool(self.neg and self.neg.driver_id == self.sel.id and self.neg.open)
            self.neg_btn.label = "Proponi" if aperta else "Apri la trattativa"
            self.drop_btn.visible = aperta
            self.drop_btn.enabled = aperta
            return
        mosse = self._mosse()
        libero = self._weekend_in_corso() is None
        for b, mossa in zip(self.posto_buttons, mosse + [None] * 3):
            b.visible = mossa is not None
            if mossa is None:
                continue
            b.label, b.style, chi, con = mossa
            b.on_click = (lambda d=chi, x=con: self.cambia_posto(d, x))
            b.enabled = libero

    def _mosse(self) -> list:
        """I cambi di posto possibili per il pilota scelto:
        (testo, stile, chi, con chi)."""
        gs, team, d = self.gs, self.team, self.sel
        out = []
        if d.id in team.drivers:
            for r in gs.reserves_of(team.id):
                out.append((f"Scambia con {r.name}  ({r.overall:.0f})", "normal", d, r))
            if len(team.reserves) < 2:
                out.append(("Manda in panchina (terzo pilota)", "normal", d, None))
        elif d.id in team.reserves:
            if len(team.drivers) < 2:
                out.append(("Promuovi a titolare", "primary", d, None))
            else:
                for t in gs.drivers_of(team.id):
                    out.append((f"Al posto di {t.name}  ({t.overall:.0f})", "normal", d, t))
        return out[:3]

    def _weekend_in_corso(self):
        return getattr(self.app, "weekend", None)

    # ------------------------------------------------------------------ azioni
    def _set(self, key, v) -> None:
        setattr(self.offer, key, int(round(v)) if key == "years" else v)

    def set_filter(self, k) -> None:
        self.filter = k
        self._mark_tabs()
        self.list.items = self._mercato()
        self.list.offset = 0.0
        self.list.selected = -1

    def _mark_tabs(self) -> None:
        for b, (key, _l) in zip(self.tabs, self.FILTRI):
            b.active = (key == self.filter)
            b.style = "tab" if b.active else "ghost"

    def _sync_sliders(self) -> None:
        for k, sl in self.sliders.items():
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
        fee = market.indennizzo(gs, d, team)
        if fee > 0:
            ok, why = economy.can_afford(team, fee, gs, check_cap=False)
            if not ok:
                self.app.toast(why)
                return
        self.neg = market.propose(gs, team, d, self.neg, self.offer)
        self.app.toast(self.neg.last)
        if self.neg.state == "accordo":
            self.gs.push(self.neg.last, "mercato")
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
            self.chiudi()

    def cambia_posto(self, chi, con) -> None:
        if self._weekend_in_corso() is not None:
            self.app.toast("Weekend in corso: i posti si cambiano a weekend finito.")
            return
        ok, msg = market.cambia_posto(self.gs, self.team, chi, con)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.neg = None
            self.build()

    def refresh(self) -> None:
        if self.sel is not None and self.vista == "scheda":
            # chi e' stato preso da un altro o si e' ritirato resta nella
            # scheda: si guarda com'e' adesso
            pass
        self.build()

    # -------------------------------------------------------------- la lista
    def _draw_lista(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        T.text(surf, "LA NOSTRA SQUADRA", (r.x + 2, r.y), 13, T.DIM, bold=True)
        costo = sum(d.salary for d in gs.drivers_of(team.id) + gs.reserves_of(team.id))
        T.text(surf, f"Titolari {len(team.drivers)}/2   \u00b7   terzi piloti "
                     f"{len(team.reserves)}/2   \u00b7   ingaggi {costo:.1f} M$ l'anno",
               (r.right, r.y), 14, T.DIM, align="right")
        for rc, d, ruolo in self.carte:
            self._carta(surf, rc, d, ruolo)
        y0 = self.list.rect.y - 36
        T.text(surf, "MERCATO PILOTI", (r.x + 2, y0), 13, T.DIM, bold=True)
        T.text(surf, f"{len(self.list.items)} nomi  \u00b7  un clic apre la scheda",
               (r.x + 150, y0), 13, T.DIM_2)

    def _carta(self, surf, rc, d, ruolo) -> None:
        team = self.team
        riserva = ruolo == "riserva"
        if d is None:
            T.panel(surf, rc, T.PANEL, radius=12, border=T.LINE, rilievo=False)
            T.text(surf, "Posto libero", (rc.centerx, rc.y + 38), 17, T.DIM, bold=True,
                   align="center")
            T.text(surf, "da titolare" if not riserva else "da terzo pilota",
                   (rc.centerx, rc.y + 62), 14, T.DIM_2, align="center")
            T.text(surf, "cercalo nel mercato qui sotto", (rc.centerx, rc.y + 86), 13,
                   T.DIM_2, align="center")
            return
        col = T.hex_rgb(team.colour)
        T.panel(surf, rc, T.mix(T.PANEL, col, 0.10 if not riserva else 0.04), radius=12,
                border=T.mix(T.LINE, col, 0.35))
        pygame.draw.rect(surf, T.squadra_viva() if not riserva else T.DIM_2,
                         (rc.x, rc.y + 16, 4, rc.h - 32), border_radius=2)
        chip = _chip(surf, (rc.x + 18, rc.y + 14),
                     "TITOLARE" if not riserva else "TERZO PILOTA",
                     T.squadra_viva() if not riserva else T.GOLD)
        voto = T.text(surf, f"{d.overall:.0f}", (rc.right - 16, rc.y + 6), 36,
                      T.stat_colour(d.overall, 70, 90), bold=True, align="right")
        if chip.right + 10 + T.width(f"#{d.number}", 16, True) < voto.x - 8:
            T.text(surf, f"#{d.number}", (chip.right + 10, rc.y + 12), 16,
                   T.squadra_viva() if not riserva else T.DIM, bold=True)
        T.text(surf, d.name, (rc.x + 18, rc.y + 44), 20, T.TEXT, bold=True,
               maxw=rc.w - 36)
        larga = bandiere.disegna(surf, d.nat, (rc.x + 18, rc.y + 78), 10)
        T.text(surf, f"{d.age} anni  \u00b7  {d.salary:.1f} M$  \u00b7  fino al "
                     f"{d.contract_until}",
               (rc.x + 18 + (larga + 8 if larga else 0), rc.y + 74), 14, T.DIM,
               maxw=rc.w - 36 - (larga + 8 if larga else 0))
        lic = d.penalty_points
        col_lic = T.BAD if lic >= 9 else (T.WARN if lic >= 6 else T.DIM_2)
        T.text(surf, f"morale {d.morale:.0f}  \u00b7  forma {d.form:+.1f}  \u00b7  "
                     f"licenza {lic}/12", (rc.x + 18, rc.y + 100), 13, col_lic,
               maxw=rc.w - 30)

    COLONNE = (("Pilota", 0.0, "left"), ("Eta'", 0.34, "left"), ("Dove corre", 0.41, "left"),
               ("Valutazione", 0.70, "right"), ("Potenziale", 0.79, "right"),
               ("Valore", 0.89, "right"), ("Contratto", 0.985, "right"))

    CORTE = {"Valutazione": "Voto", "Potenziale": "Pot.", "Contratto": "Scad.",
             "Dove corre": "Squadra"}

    def _testa_lista(self, surf, rect) -> None:
        T.panel(surf, rect, T.PANEL_2, radius=8, rilievo=False)
        stretta = rect.w < 1000
        for lab, fx_, al in self.COLONNE:
            x = rect.x + 16 + fx_ * (rect.w - 32)
            if stretta:
                lab = self.CORTE.get(lab, lab)
            T.text(surf, lab.upper(), (int(x), rect.y + 9), 12, T.DIM, bold=True, align=al)

    def _row(self, surf, rect, i, d) -> None:
        gs = self.gs
        team = gs.teams.get(d.team)
        col = T.hex_rgb(team.colour) if team else T.DIM_2
        w = rect.w - 32
        X = lambda f: int(rect.x + 16 + f * w)
        cy = rect.centery - 11
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 10, 4, rect.h - 20), border_radius=2)
        larga = bandiere.disegna(surf, d.nat, (X(0) + 4, rect.centery - 7), 10)
        T.text(surf, d.name, (X(0) + 4 + (larga + 10 if larga else 0), cy), 16, T.TEXT,
               bold=True, maxw=int(0.32 * w) - (larga + 14 if larga else 0))
        T.text(surf, f"{d.age}", (X(0.34), cy), 16, T.TEXT)
        T.text(surf, team.short if team else _dove(gs, d), (X(0.41), cy), 16,
               T.TEXT if team else T.DIM, maxw=int(0.26 * w))
        T.text(surf, f"{d.overall:.0f}", (X(0.70), cy - 2), 20,
               T.stat_colour(d.overall, 70, 90), bold=True, align="right")
        margine = max(0.0, d.potential - d.overall)
        T.text(surf, f"{d.potential:.0f}" + (f"  (+{margine:.0f})" if margine > 2
                                             and rect.w >= 1000 else ""),
               (X(0.79), cy), 16, T.OK if margine > 4 else T.DIM, align="right")
        T.text(surf, f"{d.market_value:.1f} M$", (X(0.89), cy), 16, T.GOLD, align="right")
        T.text(surf, f"{d.contract_until}" if team else "libero", (X(0.985), cy), 16,
               T.DIM if team else T.OK, align="right")

    # --------------------------------------------------------------- la scheda
    def _draw_scheda(self, surf) -> None:
        gs, team, d = self.gs, self.team, self.sel
        L, R = self.pan_sx, self.pan_dx
        squadra = gs.teams.get(d.team)
        nostro = d.team == team.id
        col = T.hex_rgb(squadra.colour) if squadra else T.DIM_2
        # --- chi e'
        T.panel(surf, L, T.PANEL, radius=14, border=T.LINE)
        testa = pygame.Rect(L.x, L.y, L.w, 108)
        fascia = pygame.Surface((testa.w, testa.h), pygame.SRCALPHA)
        for x in range(testa.w):
            a = int(90 * (1.0 - x / testa.w))
            fascia.fill((*col, a), (x, 0, 1, testa.h))
        surf.blit(fascia, testa.topleft)
        T.text(surf, f"#{d.number}", (L.right - 24, L.y + 18), 46,
               T.mix(col, T.WHITE, 0.25), bold=True, align="right")
        T.text(surf, d.name, (L.x + 24, L.y + 18), 32, T.TEXT, bold=True, maxw=L.w - 150)
        posto = ""
        if squadra is not None:
            posto = "terzo pilota" if d.seat == "riserva" else "titolare"
        if d.seat == "formulae":
            posto = "Formula E"
        larga = bandiere.disegna(surf, d.nat, (L.x + 24, L.y + 66), 12)
        T.text(surf, f"{d.age} anni  \u00b7  {d.nat}  \u00b7  "
                     f"{squadra.name if squadra else _dove(gs, d)}"
                     + (f"  \u00b7  {posto}" if posto else ""),
               (L.x + 24 + (larga + 10 if larga else 0), L.y + 62), 16, T.DIM,
               maxw=L.w - 60 - (larga + 10 if larga else 0))
        # i numeri principali, in quattro riquadri
        margine = max(0.0, d.potential - d.overall)
        if nostro:
            quarto = ("Ingaggio", f"{d.salary:.1f} M$", T.GOLD)
            quinto = ("Contratto", f"fino al {d.contract_until}", T.TEXT)
        else:
            quarto = ("Quanto vale", f"{d.market_value:.1f} M$", T.GOLD)
            if squadra:
                fee = market.buyout_cost(gs, d)
                quinto = ("Clausola" if d.release_clause > 0 else "Indennizzo",
                          f"{fee:.0f} M$", T.WARN)
            else:
                quinto = ("Situazione", "libero", T.OK)
        box = [("Valutazione", f"{d.overall:.1f}", T.stat_colour(d.overall, 70, 90)),
               ("Potenziale", f"{d.potential:.0f}" + (f"  +{margine:.0f}" if margine > 0.5
                                                     else ""),
                T.OK if margine > 4 else T.TEXT),
               quarto, quinto]
        bw = (L.w - 48 - 3 * 12) / 4
        for i, (lab, val, cc) in enumerate(box):
            b = pygame.Rect(int(L.x + 24 + i * (bw + 12)), L.y + 118, int(bw), 70)
            T.panel(surf, b, T.PANEL_2, radius=10, rilievo=False)
            T.text(surf, lab, (b.x + 14, b.y + 10), 13, T.DIM, maxw=b.w - 20)
            T.text(surf, val, (b.x + 14, b.y + 32), 22, cc, bold=True, maxw=b.w - 20)
        # attributi
        y = L.y + 210
        T.text(surf, "ATTRIBUTI", (L.x + 24, y), 13, T.DIM, bold=True)
        nota = ("in grassetto quelli che fanno la valutazione  \u00b7  la tacca e' la media "
                "della griglia")
        if T.width(nota, 12) < L.w - 190:
            T.text(surf, nota, (L.right - 24, y), 12, T.DIM_2, align="right")
        y += 26
        cw = (L.w - 48 - 24) / 2
        n_att = (len(self.ATTRS) + 1) // 2
        passo = max(26, min(34, int((L.bottom - 110 - y) / n_att)))
        medie = PEOPLE.medie(gs.drivers.values())
        for j, (a, lab, conta) in enumerate(self.ATTRS):
            v = getattr(d, a)
            cx = L.x + 24 + (j % 2) * (cw + 24)
            cy = y + (j // 2) * passo
            T.text(surf, lab, (cx, cy), 15, T.TEXT if conta else T.DIM, bold=conta,
                   maxw=int(cw * 0.45))
            T.bar(surf, (int(cx + cw * 0.47), cy + 7, int(cw * 0.40), 9), v, 100,
                  T.stat_colour(v, 65, 90), riferimento=medie.get(a))
            T.text(surf, f"{v:.0f}", (int(cx + cw), cy), 16, T.stat_colour(v, 65, 90),
                   bold=True, align="right")
        y += n_att * passo + 8
        # come sta, e cosa ha fatto
        righe = []
        lic = d.penalty_points
        righe.append((f"Morale {d.morale:.0f}   \u00b7   forma {d.form:+.1f}   \u00b7   "
                      f"punti {d.points:.0f}   \u00b7   vittorie {d.wins}   \u00b7   "
                      f"podi {d.podiums}", T.TEXT))
        if d.team:
            from ...core import driving
            fid = float(getattr(d, "confidence", driving.FIDUCIA_BASE))
            righe.append((f"Fiducia nella macchina {fid:.0f}  \u00b7  "
                          f"{driving.confidence_label(d)}", T.stat_colour(fid, 45, 75)))
            from ...core import rivalita
            rivale = rivalita.compagno(gs, d)
            if rivale is not None:
                att = float(getattr(d, "attrito_compagno", 0.0))
                stato = rivalita.descrizione(att)
                righe.append((f"Rapporto con {rivale.short}: {stato} ({att:.0f})",
                              {"rotto": T.BAD, "teso": T.WARN}.get(stato, T.DIM)))
        testo = f"Licenza {lic}/12 punti  \u00b7  in carriera {d.races} gare, " \
                f"{d.career_points:.0f} punti"
        if d.banned_races > 0:
            testo = f"SQUALIFICATO per {d.banned_races} gara  \u00b7  " + testo
        righe.append((testo, T.BAD if lic >= 9 else (T.WARN if lic >= 6 else T.DIM)))
        for testo, cc in righe:
            if y + 20 > L.bottom - 10:
                break
            T.text(surf, testo, (L.x + 24, y), 14, cc, maxw=L.w - 48)
            y += 22

        # --- cosa ci si fa
        T.panel(surf, R, T.PANEL, radius=14, border=T.LINE)
        if nostro:
            self._draw_posto(surf, d)
        else:
            self._draw_trattativa(surf, d)

    def _draw_posto(self, surf, d) -> None:
        c, team = self.pan_dx, self.team
        x0, w0 = c.x + 24, c.w - 48
        T.text(surf, "POSTO IN SQUADRA", (x0, c.y + 20), 13, T.DIM, bold=True)
        if d.id in team.drivers:
            righe = [("Titolare: corre la domenica.", T.TEXT),
                     (f"In panchina tiene contratto e stipendio, ma il morale scende di "
                      f"{market.costo_panchina(d):.0f}.", T.WARN)]
        else:
            nuovo = market.stipendio_da_titolare(d)
            if getattr(d, "contratto_titolare", False):
                soldi = f"Torna titolare con il suo contratto ({d.salary:.1f} M$)"
            else:
                soldi = (f"Da titolare chiede {nuovo:.1f} M$ l'anno"
                         + (f" (oggi {d.salary:.1f})" if nuovo > d.salary + 0.05 else ""))
            righe = [("Terzo pilota: libere, simulatore, e sostituisce chi e' squalificato.",
                      T.TEXT),
                     (soldi + f", e il morale sale di {market.PROMOZIONE_MORALE:.0f}.",
                      T.GOLD)]
        if self._weekend_in_corso() is not None:
            righe.append(("Weekend in corso: i posti si cambiano a weekend finito.", T.BAD))
        elif not self._mosse():
            righe.append(("Nessun cambio possibile adesso.", T.DIM))
        y = c.y + 48
        for testo, col in righe:
            for riga in T.wrap(testo, 15, w0):
                T.text(surf, riga, (x0, y), 15, col)
                y += 21
            y += 4
        if d.release_clause > 0:
            T.text(surf, f"Clausola nel contratto: {d.release_clause:.0f} M$",
                   (x0, self.free_btn.rect.y - 30), 14, T.WARN)

    def _draw_trattativa(self, surf, d) -> None:
        c, gs, team = self.pan_dx, self.gs, self.team
        x0, w0 = c.x + 24, c.w - 48
        T.text(surf, "TRATTATIVA", (x0, c.y + 20), 13, T.DIM, bold=True)
        mine = market.offer_value(gs, team, d, self.offer)
        T.text(surf, f"La nostra offerta vale {mine:.1f} M$ l'anno per lui", (x0, c.y + 46),
               15, T.TEXT, maxw=w0)
        if self.neg and self.neg.driver_id == d.id:
            want = market.demand_value(gs, team, d, self.neg)
            colr = T.OK if mine >= want * 0.98 else (T.WARN if mine >= want * 0.85 else T.BAD)
            T.text(surf, f"Lui ne chiede {want:.1f}", (x0, c.y + 70), 15, colr, bold=True)
            stato = {"aperta": T.TEXT, "accordo": T.OK, "rotta": T.BAD}[self.neg.state]
            for k, riga in enumerate(T.wrap(self.neg.last, 14, w0)[:2]):
                T.text(surf, riga, (x0, c.y + 96 + k * 19), 14, stato)
            if self.neg.open:
                giri = max(0, self.neg.patience - self.neg.rounds)
                T.text(surf, f"ancora {giri} giri prima che si alzi dal tavolo",
                       (c.right - 24, c.y + 70), 13, T.DIM, align="right")
        else:
            ok_posto, perche = market.can_offer_seat(gs, team, d, self.seat)
            testo = perche if not ok_posto else "Apri la trattativa per sentire cosa chiede."
            for k, riga in enumerate(T.wrap(testo, 14, w0)[:3]):
                T.text(surf, riga, (x0, c.y + 74 + k * 19), 14,
                       T.WARN if not ok_posto else T.DIM)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        if self.vista == "scheda" and self.sel is not None:
            self._draw_scheda(surf)
        else:
            self._draw_lista(surf)
        super().draw(surf)


def _pannelli_scheda(r) -> tuple:
    """I due pannelli di una scheda a tutto schermo: chi e' a sinistra, cosa
    ci si fa a destra. Su una finestra stretta stanno uno sopra l'altro, e la
    pagina scorre: meglio scorrere che leggere scritte tagliate a meta'."""
    top = r.y + 56
    if r.w < 1100:
        return (pygame.Rect(r.x, top, r.w, 500),
                pygame.Rect(r.x, top + 520, r.w, 500))
    lw = int(r.w * 0.56)
    return (pygame.Rect(r.x, top, lw, r.bottom - top),
            pygame.Rect(r.x + lw + 20, top, r.w - lw - 20, r.bottom - top))


def _chip(surf, pos, testo: str, colore) -> pygame.Rect:
    """Una pillola piccola con una parola dentro: il ruolo, lo stato."""
    img = T.render(testo, 11, colore, bold=True)
    r = pygame.Rect(pos[0], pos[1], img.get_width() + 20, img.get_height() + 6)
    pygame.draw.rect(surf, T.mix(T.PANEL, colore, 0.18), r, border_radius=r.h // 2)
    pygame.draw.rect(surf, T.mix(T.PANEL, colore, 0.55), r, 1, border_radius=r.h // 2)
    surf.blit(img, (r.x + 10, r.y + 3))
    return r


class StaffPage(Page):
    """Lo staff tecnico in due schermate, come i piloti.

    La lista ha due viste - l'organigramma della squadra e il mercato - una
    alla volta e larghe quanto la pagina, con una colonna per ogni numero. Un
    clic su un nome apre la scheda a tutto schermo: a sinistra chi e' e
    quanto vale nel suo ruolo, a destra cosa cambierebbe prendendolo e
    l'offerta, o per i nostri il contratto e la porta.
    """

    ATTR_LABEL = {
        "aero": "Aerodinamica", "mechanical": "Meccanica", "powertrain": "Powertrain",
        "development": "Sviluppo", "reliability": "Affidabilita'", "strategy": "Strategia",
        "analysis": "Analisi dati", "communication": "Comunicazione",
        "management": "Gestione", "scouting": "Scouting",
    }
    FILTRI = (("liberi", "Svincolati"), ("altre", "Sotto contratto"), ("tutti", "Tutti"))
    RIGA_H = 50

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.sel_from = "mercato"      # da quale lista arriva la scheda
        self.vista = "lista"           # lista | scheda
        self.elenco = "nostri"         # nostri | mercato
        self.filtro = "liberi"
        self.offer_salary = 2.0
        self.offer_years = 3

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        self.widgets = []
        if self.vista == "scheda" and self.sel is not None:
            self._build_scheda()
        else:
            self.vista = "lista"
            self._build_lista()

    def _build_lista(self) -> None:
        r = self.rect
        self.elenco_btn = []
        x = r.x
        for key, lab in (("nostri", f"La nostra squadra ({len(self.team.staff)})"),
                         ("mercato", "Mercato")):
            larga = T.width(lab, 16, True) + 48
            b = Button((x, r.y, larga, 40), lab, (lambda k=key: self._pick_elenco(k)))
            b.active = key == self.elenco
            b.style = "tab" if b.active else "ghost"
            self.elenco_btn.append(b)
            self.widgets.append(b)
            x += larga + 8
        self.filter_buttons = []
        if self.elenco == "mercato":
            x = r.right
            for key, lab in reversed(self.FILTRI):
                larga = T.width(lab, 15, True) + 40
                x -= larga
                b = Button((x, r.y + 2, larga, 36), lab, (lambda k=key: self._pick_filter(k)))
                self.filter_buttons.append(b)
                self.widgets.append(b)
                x -= 8
            self.filter_buttons.reverse()
            self._mark_filter()
        top = r.y + 56
        self.lista = ScrollList((r.x, top, r.w, max(120, r.bottom - top)), row_h=self.RIGA_H,
                                draw_row=(self._row_mine if self.elenco == "nostri"
                                          else self._row_market),
                                header_h=34, draw_header=self._testa_lista,
                                on_select=self._apri_da_lista)
        self.lista.items = self._voci()
        self.widgets.append(self.lista)

    def _voci(self) -> list:
        gs = self.gs
        if self.elenco == "nostri":
            ordine = list(gs.staff_roles)
            return sorted(self.team.staff, key=lambda s: ordine.index(s.role))
        liberi = list(gs.free_staff)
        # sotto contratto vuol dire sotto contratto con chiunque: anche le
        # squadre di Formula E hanno le loro teste tecniche, e anche quelle
        # si portano via pagando
        altrui = [s for t in gs.teams.values() if t.id != self.team.id for s in t.staff]
        altrui += list(getattr(gs, "fe_staff", None) or [])
        pool = {"liberi": liberi, "altre": altrui, "tutti": liberi + altrui}[self.filtro]
        pool.sort(key=lambda s: -market.role_score(gs, s, s.role))
        return pool

    def _build_scheda(self) -> None:
        r = self.rect
        self.back_btn = Button((r.x, r.y, 210, 40), "\u00ab  Torna allo staff", self.chiudi,
                               "ghost")
        self.widgets.append(self.back_btn)
        self.pan_sx, self.pan_dx = _pannelli_scheda(r)
        c = self.pan_dx
        x0, w0 = c.x + 24, c.w - 48
        if self.sel_from == "mine":
            self.fire_btn = Button((x0, c.bottom - 68, w0, 46), "Licenzia", self.fire, "danger")
            self.widgets.append(self.fire_btn)
            return
        self.sal = Slider((x0, c.bottom - 176, w0, 30), "Stipendio", self.offer_salary, 0.2,
                          18.0, on_change=lambda v: setattr(self, "offer_salary", v),
                          fmt="{:.2f} M$")
        self.yrs = Slider((x0, c.bottom - 132, w0, 30), "Durata", self.offer_years, 1, 5,
                          on_change=lambda v: setattr(self, "offer_years", int(round(v))),
                          fmt="{:.0f} anni")
        self.hire_btn = Button((x0, c.bottom - 68, w0, 46), "Contatta e assumi", self.hire,
                               "primary")
        self.hire_btn.enabled = self.team.role(self.sel.role) is not self.sel
        self.widgets += [self.sal, self.yrs, self.hire_btn]

    # ------------------------------------------------------------ navigazione
    def _apri_da_lista(self, i, s) -> None:
        self.apri(s, "mine" if self.elenco == "nostri" else "mercato")

    def apri(self, s, da: str) -> None:
        if da == "mercato" and s is not self.sel:
            self.offer_salary = max(0.2, round(s.market_value * 1.10, 2))
        self.sel, self.sel_from = s, da
        self.vista = "scheda"
        self.scroll = 0.0
        self.layout(self.view)

    def chiudi(self) -> None:
        self.vista = "lista"
        self.scroll = 0.0
        self.layout(self.view)

    def _pick_elenco(self, k) -> None:
        self.elenco = k
        self.build()

    def _pick_filter(self, k) -> None:
        self.filtro = k
        self._mark_filter()
        self.lista.items = self._voci()
        self.lista.offset = 0.0
        self.lista.selected = -1

    def _mark_filter(self) -> None:
        for b, (key, _l) in zip(self.filter_buttons, self.FILTRI):
            b.active = (key == self.filtro)
            b.style = "tab" if b.active else "ghost"

    # ------------------------------------------------------------------ azioni
    def hire(self) -> None:
        if not self.sel:
            return
        ok, msg = market.hire_staff(self.gs, self.team, self.sel,
                                    round(self.offer_salary, 2), self.offer_years)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel, self.sel_from = None, "mercato"
            self.chiudi()

    def fire(self) -> None:
        if not self.sel or self.sel_from != "mine":
            return
        ok, msg = market.fire_staff(self.gs, self.team, self.sel)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel, self.sel_from = None, "mercato"
            self.chiudi()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- la lista
    def _label(self, role) -> str:
        return self.gs.staff_roles[role]["label"]

    def _colonne(self):
        if self.elenco == "nostri":
            return (("Ruolo", 0.0, "left"), ("Nome", 0.34, "left"),
                    ("Valore nel ruolo", 0.74, "right"), ("Ingaggio", 0.87, "right"),
                    ("Contratto", 0.985, "right"))
        return (("Nome", 0.0, "left"), ("Ruolo", 0.27, "left"), ("Dove lavora", 0.55, "left"),
                ("Valore nel ruolo", 0.80, "right"), ("Quanto vale", 0.985, "right"))

    def _testa_lista(self, surf, rect) -> None:
        T.panel(surf, rect, T.PANEL_2, radius=8, rilievo=False)
        for lab, f, al in self._colonne():
            x = rect.x + 16 + f * (rect.w - 32)
            if rect.w < 1000:
                lab = {"Valore nel ruolo": "Valore", "Quanto vale": "Vale"}.get(lab, lab)
            T.text(surf, lab.upper(), (int(x), rect.y + 9), 12, T.DIM, bold=True, align=al)

    def _row_mine(self, surf, rect, i, s) -> None:
        w = rect.w - 32
        X = lambda f: int(rect.x + 16 + f * w)
        cy = rect.centery - 11
        T.text(surf, self._label(s.role), (X(0), cy), 16, T.squadra_viva(), bold=True,
               maxw=int(0.32 * w))
        T.text(surf, s.name, (X(0.34), cy), 16, T.TEXT, bold=True, maxw=int(0.36 * w))
        voto = market.role_score(self.gs, s, s.role)
        T.text(surf, f"{voto:.0f}", (X(0.74), cy - 2), 20, T.stat_colour(voto, 58, 86),
               bold=True, align="right")
        T.text(surf, f"{s.salary:.2f} M$", (X(0.87), cy), 16, T.GOLD, align="right")
        T.text(surf, f"{s.contract_until}", (X(0.985), cy), 16, T.DIM, align="right")

    def _row_market(self, surf, rect, i, s) -> None:
        t = self.gs.teams.get(s.team)
        col = T.hex_rgb(t.colour) if t else T.DIM_2
        w = rect.w - 32
        X = lambda f: int(rect.x + 16 + f * w)
        cy = rect.centery - 11
        pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 10, 4, rect.h - 20), border_radius=2)
        T.text(surf, s.name, (X(0) + 4, cy), 16, T.TEXT, bold=True, maxw=int(0.26 * w))
        T.text(surf, self._label(s.role), (X(0.27), cy), 16, T.TEXT, maxw=int(0.27 * w))
        dove = t.short if t else (getattr(s, "fe_squadra", "") or "svincolato")
        T.text(surf, dove, (X(0.55), cy), 16, T.TEXT if t else T.DIM, maxw=int(0.2 * w))
        voto = market.role_score(self.gs, s, s.role)
        T.text(surf, f"{voto:.0f}", (X(0.80), cy - 2), 20, T.stat_colour(voto, 58, 86),
               bold=True, align="right")
        T.text(surf, f"{s.market_value:.2f} M$", (X(0.985), cy), 16, T.GOLD, align="right")

    # --------------------------------------------------------------- la scheda
    def _draw_scheda(self, surf) -> None:
        gs, team, s = self.gs, self.team, self.sel
        L, R = self.pan_sx, self.pan_dx
        squadra = gs.teams.get(s.team)
        fe_nome = getattr(s, "fe_squadra", "")
        col = T.hex_rgb(squadra.colour) if squadra else T.DIM_2
        T.panel(surf, L, T.PANEL, radius=14, border=T.LINE)
        testa = pygame.Rect(L.x, L.y, L.w, 108)
        fascia = pygame.Surface((testa.w, testa.h), pygame.SRCALPHA)
        for x in range(testa.w):
            fascia.fill((*col, int(90 * (1.0 - x / testa.w))), (x, 0, 1, testa.h))
        surf.blit(fascia, testa.topleft)
        T.text(surf, s.name, (L.x + 24, L.y + 16), 32, T.TEXT, bold=True, maxw=L.w - 48)
        dove = squadra.name if squadra else (f"{fe_nome} (Formula E)" if fe_nome
                                             else "svincolato")
        T.text(surf, f"{self._label(s.role)}  \u00b7  {s.age} anni  \u00b7  {s.nat}  \u00b7  "
                     f"{dove}", (L.x + 24, L.y + 62), 16, T.DIM, maxw=L.w - 48)
        voto = market.role_score(gs, s, s.role)
        box = [("Valore nel ruolo", f"{voto:.0f} / 100", T.stat_colour(voto, 58, 86))]
        if self.sel_from == "mine":
            box += [("Ingaggio", f"{s.salary:.2f} M$", T.GOLD),
                    ("Contratto", f"fino al {s.contract_until}", T.TEXT)]
        else:
            box.append(("Quanto vale", f"{s.market_value:.2f} M$", T.GOLD))
            if squadra or fe_nome:
                fee = market.indennizzo_staff(gs, s, team)
                box.append(("Indennizzo", f"{fee:.2f} M$", T.WARN))
            else:
                box.append(("Situazione", "libero", T.OK))
        bw = (L.w - 48 - (len(box) - 1) * 12) / len(box)
        for i, (lab, val, cc) in enumerate(box):
            b = pygame.Rect(int(L.x + 24 + i * (bw + 12)), L.y + 118, int(bw), 70)
            T.panel(surf, b, T.PANEL_2, radius=10, rilievo=False)
            T.text(surf, lab, (b.x + 14, b.y + 10), 13, T.DIM, maxw=b.w - 20)
            T.text(surf, val, (b.x + 14, b.y + 32), 22, cc, bold=True, maxw=b.w - 20)
        y = L.y + 210
        pesi = gs.staff_roles.get(s.role, {}).get("weights", {})
        T.text(surf, "ATTRIBUTI", (L.x + 24, y), 13, T.DIM, bold=True)
        if T.width("in grassetto quelli che contano nel ruolo", 12) < L.w - 190:
            T.text(surf, "in grassetto quelli che contano nel ruolo", (L.right - 24, y), 12,
                   T.DIM_2, align="right")
        y += 26
        cw = (L.w - 48 - 24) / 2
        n = (len(STAFF_ATTRS) + 1) // 2
        passo = max(26, min(36, int((L.bottom - 30 - y) / n)))
        for j, a in enumerate(STAFF_ATTRS):
            v = getattr(s, a)
            conta = a in pesi
            cx = L.x + 24 + (j % 2) * (cw + 24)
            cy = y + (j // 2) * passo
            T.text(surf, self.ATTR_LABEL.get(a, a), (cx, cy), 15, T.TEXT if conta else T.DIM,
                   bold=conta, maxw=int(cw * 0.45))
            T.bar(surf, (int(cx + cw * 0.47), cy + 7, int(cw * 0.40), 9), v, 100,
                  T.stat_colour(v, 55, 85))
            T.text(surf, f"{v:.0f}", (int(cx + cw), cy), 16, T.stat_colour(v, 55, 85),
                   bold=True, align="right")

        # --- a destra
        T.panel(surf, R, T.PANEL, radius=14, border=T.LINE)
        x0, w0 = R.x + 24, R.w - 48
        y = R.y + 20
        if self.sel_from == "mine":
            T.text(surf, "CONTRATTO", (x0, y), 13, T.DIM, bold=True)
            y += 30
            resta = max(1, s.contract_until - gs.season)
            for testo in (f"Mandarlo via costa la buonuscita di quello che resta di contratto: "
                          f"{s.salary * max(0.5, resta):.2f} M$, fuori dal tetto di spesa.",
                          "Il rinnovo si fa lasciandolo scadere e riassumendolo dal mercato."):
                for riga in T.wrap(testo, 15, w0):
                    T.text(surf, riga, (x0, y), 15, T.TEXT)
                    y += 21
                y += 8
            return
        T.text(surf, "ASSUNZIONE", (x0, y), 13, T.DIM, bold=True)
        y += 30
        if fe_nome:
            from ...core import formulae as FE
            pos = [n for n, _v in FE.classifica_squadre(gs)]
            if fe_nome in pos:
                T.text(surf, f"In Formula E: {fe_nome} {pos.index(fe_nome) + 1}a su "
                             f"{len(pos)} nel mondiale squadre", (x0, y), 15,
                       T.OK if pos.index(fe_nome) < 3 else T.DIM, maxw=w0)
                y += 26
        attuale = team.role(s.role)
        if attuale is s:
            T.text(surf, "E' gia' dei nostri.", (x0, y), 15, T.DIM)
            return
        if attuale is not None:
            ora = market.role_score(gs, attuale, s.role)
            delta = voto - ora
            cc = T.OK if delta > 1 else (T.BAD if delta < -1 else T.DIM)
            T.text(surf, f"Al posto di {attuale.name} ({ora:.0f})", (x0, y), 15, T.TEXT,
                   maxw=w0)
            T.text(surf, f"{delta:+.0f} nel ruolo", (x0, y + 22), 20, cc, bold=True)
            y += 56
        else:
            T.text(surf, "Il posto e' vuoto: chiunque e' meglio di nessuno.", (x0, y), 15,
                   T.OK, maxw=w0)
            y += 30
        gradimento = market.staff_interest(gs, team, s, round(self.offer_salary, 2))
        cc = T.OK if gradimento > 0.7 else (T.WARN if gradimento > 0.4 else T.BAD)
        T.text(surf, "Accetterebbe", (x0, y), 15, T.DIM)
        T.text(surf, f"{gradimento * 100:.0f}%", (x0 + w0, y - 2), 20, cc, bold=True,
               align="right")
        T.bar(surf, (x0, y + 26, w0, 10), gradimento * 100, 100, cc)
        T.text(surf, "Alza lo stipendio per convincerlo: il gradimento si aggiorna.",
               (x0, self.sal.rect.y - 34), 13, T.DIM_2, maxw=w0)

    def _draw_lista(self, surf) -> None:
        if self.elenco == "nostri":
            T.text(surf, f"{self.team.leaders_cost:.1f} M$ l'anno in stipendi  \u00b7  un clic "
                         f"apre la scheda", (self.rect.right, self.rect.y + 10), 14, T.DIM,
                   align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        if self.vista == "scheda" and self.sel is not None:
            self._draw_scheda(surf)
        else:
            self._draw_lista(surf)
        super().draw(surf)
