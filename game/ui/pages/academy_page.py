"""Pagina Vivaio: i ragazzi che crescono in casa, e cosa costano."""
from __future__ import annotations

import pygame

from ...core import academy as AC, serie as SR
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Tabs, Toggle, card


class AcademyPage(Page):
    ATTRS = (("pace", "Passo"), ("racecraft", "Duello"), ("consistency", "Costanza"),
             ("tyre_mgmt", "Gestione gomme"), ("wet", "Bagnato"),
             ("feedback", "Riscontro tecnico"))

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.tab = 0
        self.cat_btn = {}

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.left = pygame.Rect(r.x, r.y + 96, r.w * 0.42, r.h - 96)
        self.right = pygame.Rect(r.x + r.w * 0.44, r.y + 96, r.w * 0.56 - 4, r.h - 96)
        if not AC.has(self.team):
            self.found_btn = Button((self.left.x + 16, self.left.y + 220,
                                     self.left.w - 32, 44),
                                    f"Fonda il vivaio ({AC.FOUND_COST:.0f} M$)",
                                    self.found, "primary")
            ok, _w = AC.can_found(self.gs, self.team)
            self.found_btn.enabled = ok
            self.widgets.append(self.found_btn)
            return

        self.camp_h = 116
        self.lista = ScrollList((self.left.x + 12, self.left.y + 40, self.left.w - 24,
                                 self.left.h - 56 - self.camp_h), row_h=52,
                                draw_row=self._row, on_select=self._select)
        self.widgets.append(self.lista)
        c = self.right
        self.tabs = Tabs((c.x + 12, c.y + 8, c.w - 24, 26), ("Il ragazzo", "Dove corre"),
                         on_change=self._switch, w=min(150, (c.w - 32) / 2))
        self.tabs.index = self.tab
        for i, b in enumerate(self.tabs.buttons):
            b.active = (i == self.tab)
        self.widgets.append(self.tabs)
        bw = (c.w - 44) / 3
        self.widgets.append(Button((c.x + 16, c.bottom - 58, bw, 40),
                                   "Terzo pilota", self.to_reserve, "primary"))
        self.widgets.append(Button((c.x + 28 + bw, c.bottom - 58, bw, 40),
                                   "Titolare", self.to_race, "normal"))
        self.widgets.append(Button((c.x + 40 + 2 * bw, c.bottom - 58, bw, 40),
                                   "Lascia andare", self.let_go, "danger"))
        self.cat_btn = {}
        self.delega_tg = None
        if self.tab == 1:
            self.delega_tg = Toggle((c.x + 16, c.y + 70, c.w - 32, 26),
                                    "Decide il responsabile del vivaio",
                                    bool(self.team.vivaio_auto), self._set_delega)
            self.widgets.append(self.delega_tg)
            y = self.riga_y()
            for sid in SR.scala():
                b = Button((c.x + 16, y + 2, 78, 28), SR.sigla(sid),
                           (lambda s=sid: self.set_serie(s)), "normal")
                self.cat_btn[sid] = b
                self.widgets.append(b)
                y += self.RIGA_H
        self._fill()
        self._sync_cat()

    RIGA_H = 42

    def riga_y(self) -> int:
        """Dove comincia l'elenco delle categorie: sotto l'interruttore e la spiega."""
        return int(self.right.y + 140)

    def _switch(self, i: int) -> None:
        self.tab = i
        self.build()

    def _sync_cat(self) -> None:
        """Quale categoria e' scelta adesso, e quali si possono ancora premere."""
        if not self.cat_btn:
            return
        d = self.sel
        auto = bool(self.team.vivaio_auto)
        adesso = SR.serie_adatta(self.gs, d) if d is not None else ""
        for sid, b in self.cat_btn.items():
            ok = d is not None and SR.verifica(self.gs, d, sid)[0]
            b.enabled = ok and not auto
            b.active = (sid == adesso)

    def _set_delega(self, v) -> None:
        self.team.vivaio_auto = bool(v)
        if v:
            for msg in SR.pianifica(self.gs, self.team):
                self.gs.push(msg, "mercato")
            self.app.toast("Il responsabile del vivaio decide le categorie.")
        else:
            self.app.toast("Le categorie le scegli tu.")
        self._sync_cat()

    def set_serie(self, sid: str) -> None:
        if self.sel is None:
            return
        ok, msg = SR.scegli(self.gs, self.sel, sid)
        self.app.toast(msg)
        self._sync_cat()

    def _fill(self) -> None:
        self.lista.items = AC.roster(self.gs, self.team)
        if self.sel not in self.lista.items:
            self.sel = self.lista.items[0] if self.lista.items else None
        if self.sel in self.lista.items:
            self.lista.selected = self.lista.items.index(self.sel)

    # ------------------------------------------------------------------ azioni
    def _select(self, i, d) -> None:
        self.sel = d
        self._sync_cat()

    def found(self) -> None:
        ok, msg = AC.found(self.gs, self.team)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
        self.build()

    def _promote(self, seat) -> None:
        if not self.sel:
            return
        ok, msg = AC.promote(self.gs, self.team, self.sel, seat)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "mercato")
            self.sel = None
            self.build()

    def to_reserve(self) -> None:
        self._promote("riserva")

    def to_race(self) -> None:
        self._promote("titolare")

    def let_go(self) -> None:
        if not self.sel:
            return
        ok, msg = AC.release(self.gs, self.team, self.sel)
        self.app.toast(msg)
        if ok:
            self.sel = None
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- la riga
    def _row(self, surf, rect, i, d) -> None:
        T.text(surf, d.name, (rect.x + 14, rect.y + 6), 15, T.TEXT, bold=True,
               maxw=rect.w - 130)
        sid = SR.serie_adatta(self.gs, d)
        dove = SR.sigla(sid) if sid else "fuori scala"
        T.text(surf, f"{dove}  -  {d.age} anni  -  {d.nat}  -  fino al {d.contract_until}",
               (rect.x + 14, rect.y + 26), 11, T.DIM, maxw=rect.w - 130)
        T.text(surf, f"{d.overall:.0f}", (rect.right - 66, rect.y + 8), 17,
               T.stat_colour(d.overall, 62, 84), bold=True, align="right")
        margine = max(0.0, d.potential - d.overall)
        T.text(surf, f"pot {d.potential:.0f}", (rect.right - 12, rect.y + 10), 13,
               T.OK if margine > 8 else T.DIM, align="right")
        T.text(surf, f"+{margine:.0f} da fare", (rect.right - 12, rect.y + 28), 11,
               T.DIM_2, align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        cw = (r.w - 32) / 3
        if not AC.has(team):
            self._draw_none(surf, cw)
            super().draw(surf)
            return
        ragazzi = AC.roster(gs, team)
        card(surf, (r.x, r.y, cw, 86), "Vivaio", team.academy_name,
             f"{len(ragazzi)} ragazzi su {AC.MAX_ROSTER} posti", accent=T.GOLD)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Costa",
             f"{AC.running_cost(gs, team):.1f} M$", "all'anno, fuori dal tetto di spesa",
             accent=T.WARN)
        liv = AC.scout_level(gs, team)
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Che gente arriva",
             f"{liv:.0f} / 100", "struttura, osservatori e nome della squadra",
             colour=T.stat_colour(liv, 60, 78), accent=T.ACCENT)

        T.panel(surf, self.left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I NOSTRI RAGAZZI", (self.left.x + 16, self.left.y + 12), 12,
               T.DIM_2, bold=True)
        if not ragazzi:
            T.text(surf, "Nessuno in rosa: i prossimi arrivano a fine stagione.",
                   (self.left.x + 16, self.left.y + 48), 13, T.DIM,
                   maxw=self.left.w - 32)

        self._draw_campionato(surf)

        T.panel(surf, self.right, T.PANEL, radius=10, border=T.LINE)
        self._draw_card(surf)
        super().draw(surf)

    def _draw_campionato(self, surf) -> None:
        """Come e' finito il campionato dove corre il ragazzo che stiamo guardando.

        Un vivaio non e' una lista di valutazioni: e' gente che corre da
        qualche parte contro qualcun altro, e quel qualcun altro ha un nome e
        una squadra. Senza la classifica, "settantadue di overall" non vuol
        dire niente.
        """
        gs = self.gs
        d = self.sel
        y = self.left.bottom - self.camp_h + 6
        sid = SR.serie_adatta(gs, d) if d is not None else ""
        camp = SR.ultimo_campionato(gs, sid) if sid else None
        if camp is None or not camp.ordine:
            T.text(surf, "CAMPIONATO", (self.left.x + 16, y), 12, T.DIM_2, bold=True)
            T.paragraph(surf, "La prima stagione di categorie si corre a fine anno: da "
                              "li' in poi qui c'e' la classifica.",
                        (self.left.x + 16, y + 20), 12, T.DIM_2, self.left.w - 32)
            return
        s = SR.scheda(sid)
        T.text(surf, f"{s.get('nome', sid).upper()}  {camp.stagione}",
               (self.left.x + 16, y), 12, T.GOLD, bold=True)
        T.text(surf, f"{len(camp.ordine)} al via", (self.left.right - 16, y), 11,
               T.DIM_2, align="right")
        y += 20
        mia = camp.posizione_di(d.id)
        righe = list(enumerate(camp.ordine[:3], 1))
        if mia > 3:
            righe.append((mia, camp.ordine[mia - 1]))
        for pos, riga in righe:
            nostro = bool(riga.driver_id)
            col = T.GOLD if nostro else T.TEXT
            T.text(surf, f"{pos}", (self.left.x + 22, y), 12, col, align="right")
            T.text(surf, riga.nome, (self.left.x + 34, y), 13, col, bold=nostro,
                   maxw=self.left.w * 0.42)
            T.text(surf, riga.squadra, (self.left.x + 34 + self.left.w * 0.44, y), 11,
                   T.DIM_2, maxw=self.left.w * 0.28)
            T.text(surf, f"{riga.punti:.0f}", (self.left.right - 16, y), 12, col,
                   bold=True, align="right")
            y += 19

    def _draw_card(self, surf) -> None:
        if self.tab == 1:
            self._draw_dove(surf)
        else:
            self._draw_ragazzo(surf)

    def _draw_ragazzo(self, surf) -> None:
        c, team = self.right, self.team
        d = self.sel
        if d is None:
            T.text(surf, "Scegli un ragazzo dalla lista.", (c.x + 16, c.y + 58), 14, T.DIM)
            return
        T.text(surf, d.name, (c.x + 16, c.y + 44), 20, T.TEXT, bold=True, maxw=c.w - 32)
        T.text(surf, f"{d.age} anni  -  {d.nat}  -  nel programma fino al "
                     f"{d.contract_until}", (c.x + 16, c.y + 70), 13, T.DIM,
               maxw=c.w - 32)
        pygame.draw.line(surf, T.LINE, (c.x + 16, c.y + 94), (c.right - 16, c.y + 94))

        margine = max(0.0, d.potential - d.overall)
        righe = [("Vale adesso", f"{d.overall:.1f} / 100", T.stat_colour(d.overall, 62, 84)),
                 ("Potenziale", f"{d.potential:.0f}   ancora +{margine:.0f}",
                  T.OK if margine > 8 else T.DIM),
                 ("Ci costa", f"{d.salary:.2f} M$ all'anno", T.GOLD),
                 ("Se lo promuovessimo",
                  f"{d.market_value * 0.30:.2f} M$ da terzo pilota", T.DIM)]
        y = c.y + 104
        for lab, val, colr in righe:
            T.text(surf, lab, (c.x + 16, y), 13, T.DIM, maxw=c.w * 0.5)
            T.text(surf, val, (c.right - 16, y), 13, colr, bold=True, align="right",
                   maxw=c.w * 0.5)
            y += 21

        y += 10
        T.text(surf, "COM'E' MESSO", (c.x + 16, y), 12, T.DIM_2, bold=True)
        y += 20
        for a, lab in self.ATTRS:
            v = getattr(d, a)
            T.text(surf, lab, (c.x + 16, y), 13, T.DIM, maxw=140)
            T.bar(surf, (c.x + 156, y + 5, c.w - 232, 8), v, 100, T.stat_colour(v, 62, 86))
            T.text(surf, f"{v:.0f}", (c.right - 16, y), 13, T.stat_colour(v, 62, 86),
                   bold=True, align="right")
            y += 22

        y += 8
        n_ris, n_tit = len(team.reserves), len(team.drivers)
        if n_ris >= 2 and n_tit >= 2:
            T.text(surf, "Non c'e' posto ne' da titolare ne' da terzo pilota.",
                   (c.x + 16, y), 12, T.WARN, maxw=c.w - 32)
        else:
            T.text(surf, f"Posti liberi: {2 - n_tit} da titolare, "
                         f"{2 - n_ris} da terzo pilota.",
                   (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)

    def _draw_dove(self, surf) -> None:
        """La pagina in cui si decide dove correra' il ragazzo.

        E' la scelta che conta piu' di tutte in un vivaio: la stessa stagione
        vale il doppio se e' corsa nella categoria giusta e non vale niente se
        e' corsa in quella sbagliata. Chi non vuole occuparsene lascia la mano
        al responsabile, che decide come deciderebbe uno bravo quanto lui.
        """
        c, gs, team = self.right, self.gs, self.team
        d = self.sel
        if d is None:
            T.text(surf, "Scegli un ragazzo dalla lista.", (c.x + 16, c.y + 58), 14, T.DIM)
            return
        auto = bool(team.vivaio_auto)
        T.text(surf, d.name, (c.x + 16, c.y + 44), 15, T.TEXT, bold=True, maxw=c.w * 0.55)
        adesso = SR.serie_adatta(gs, d)
        T.text(surf, f"quest'anno in {SR.sigla(adesso)}" if adesso
               else "senza una categoria", (c.right - 16, c.y + 44), 13,
               T.GOLD if adesso else T.BAD, bold=True, align="right")
        # l'interruttore lo disegna il widget: qui sotto va solo la spiega
        T.paragraph(surf, ("Sceglie lui: mette ognuno dove pensa che debba stare, e "
                           "quanto ci prende dipende da quanto vale."
                           if auto else
                           "Decidi tu: un gradino alla volta, dentro l'eta' giusta, "
                           "e un campionato vinto non si rifa'."),
                    (c.x + 16, c.y + 102), 12, T.DIM_2, c.w - 32)

        y = self.riga_y()
        for sid in SR.scala():
            s = SR.scheda(sid)
            ok, why = SR.verifica(gs, d, sid)
            scelto = (sid == adesso)
            col = T.GOLD if scelto else (T.TEXT if ok else T.DIM_2)
            T.text(surf, s.get("nome", sid), (c.x + 104, y), 14, col, bold=scelto,
                   maxw=c.w * 0.40)
            T.text(surf, f"{SR.costo_posto(sid):.2f} M$", (c.right - 16, y), 13,
                   T.GOLD if ok else T.DIM_2, align="right")
            emin, emax = s.get("eta", [15, 24])
            T.text(surf, f"{s.get('gare', 0)} gare, {s.get('vetture', 0)} al via, "
                         f"{emin}-{emax} anni",
                   (c.x + 104, y + 18), 11, T.DIM_2, maxw=c.w * 0.36)
            T.text(surf, why if not ok else SR.nota(gs, d, sid),
                   (c.right - 16, y + 18), 11, T.BAD if not ok else T.DIM,
                   align="right", maxw=c.w * 0.32)
            y += self.RIGA_H

        y += 4
        punti = SR.punti_licenza(d)
        col = T.OK if punti >= SR.LICENZA_SOGLIA else T.WARN
        T.text(surf, "Superlicenza", (c.x + 16, y), 13, T.DIM, maxw=140)
        T.bar(surf, (c.x + 156, y + 5, c.w - 232, 8), punti, SR.LICENZA_SOGLIA, col)
        T.text(surf, f"{punti}/{SR.LICENZA_SOGLIA}", (c.right - 16, y), 13, col,
               bold=True, align="right")
        y += 24
        camp = SR.ultimo_campionato(gs, d.ultima_serie) if d.ultima_serie else None
        riga = camp.riga_di(d.id) if camp else None
        if riga is not None:
            pos = camp.posizione_di(d.id)
            T.text(surf, f"L'anno scorso {pos}o su {len(camp.ordine)} in "
                         f"{SR.sigla(camp.serie)} con {riga.punti:.0f} punti"
                         + (f" e {riga.vittorie} vittorie" if riga.vittorie else ""),
                   (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
        else:
            T.text(surf, "Non ha ancora corso una stagione con noi.",
                   (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
        y += 20
        T.text(surf, f"I posti di tutto il vivaio costano "
                     f"{AC.running_cost(gs, team):.2f} M$ l'anno.",
               (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
        y += 26
        if y < c.bottom - 110:      # solo dove lo schermo lo lascia stare
            T.paragraph(surf, "Le categorie corrono insieme al mondiale e la classifica "
                              "si chiude a fine anno: quello che si decide qui si vede "
                              "allora. Una stagione nella categoria giusta vale una "
                              "crescita intera, una in una categoria che ha gia' dato "
                              "ne vale un quarto - e i punti superlicenza li danno solo "
                              "i primi, con le categorie in alto che ne valgono di piu'.",
                        (c.x + 16, y), 12, T.DIM_2, c.w - 32)

    def _draw_none(self, surf, cw) -> None:
        r, gs, team = self.rect, self.gs, self.team
        card(surf, (r.x, r.y, cw, 86), "Vivaio", "non ce l'abbiamo",
             "i piloti si comprano sul mercato", accent=T.DIM_2)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Aprirlo costa",
             f"{AC.FOUND_COST:.0f} M$", "una volta sola, piu' la gestione", accent=T.WARN)
        annuo = (AC.RUN_BASE * (0.55 + 0.75 * float(team.facilities.get("academy", 60.0))
                                / 100.0)
                 + SR.costo_posto("f3") + 2 * SR.costo_posto("fregional"))
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "E tenerlo aperto",
             f"{annuo:.1f} M$", "ogni anno, piu' i posti nelle categorie",
             accent=T.BAD)

        T.panel(surf, self.left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "APRIRE UN VIVAIO", (self.left.x + 16, self.left.y + 12), 12,
               T.DIM_2, bold=True)
        y = self.left.y + 44
        for riga in ("Le squadre grandi non aspettano che un pilota si liberi",
                     "sul mercato: se lo crescono. Ferrari ha la Driver Academy",
                     "dal 2009, la Red Bull il suo programma junior da vent'anni,",
                     "e chi ci ha investito si e' ritrovato in casa Leclerc,",
                     "Verstappen, Norris e Antonelli senza pagarli a peso d'oro.",
                     "",
                     "Ma e' un conto che torna solo se lo si regge per anni: un",
                     "ragazzo entra a sedici anni e ne serve almeno tre prima",
                     "che valga qualcosa. Nel frattempo si paga e basta."):
            T.text(surf, riga, (self.left.x + 16, y), 13, T.DIM, maxw=self.left.w - 32)
            y += 18
        ok, why = AC.can_found(gs, team)
        if not ok:
            yy = self.left.y + 284
            for riga in _wrap(why, 54):
                T.text(surf, riga, (self.left.x + 16, yy), 13, T.BAD,
                       maxw=self.left.w - 32)
                yy += 18

        T.panel(surf, self.right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CHI CE L'HA", (self.right.x + 16, self.right.y + 12), 12,
               T.DIM_2, bold=True)
        y = self.right.y + 44
        for t in sorted(gs.teams.values(), key=lambda x: x.last_position):
            if not AC.has(t):
                continue
            ragazzi = AC.roster(gs, t)
            T.text(surf, t.academy_name, (self.right.x + 16, y), 14, T.TEXT,
                   maxw=self.right.w * 0.55)
            T.text(surf, f"{len(ragazzi)} ragazzi", (self.right.right - 16, y), 13,
                   T.DIM, align="right")
            migliore = max(ragazzi, key=lambda d: d.potential, default=None)
            if migliore is not None:
                T.text(surf, f"il migliore e' {migliore.short}, {migliore.age} anni, "
                             f"{migliore.potential:.0f} di potenziale",
                       (self.right.x + 16, y + 19), 12, T.DIM_2,
                       maxw=self.right.w - 32)
            y += 44


def _wrap(testo: str, n: int) -> list:
    fuori, riga = [], ""
    for parola in testo.split():
        if len(riga) + len(parola) + 1 > n:
            fuori.append(riga)
            riga = parola
        else:
            riga = f"{riga} {parola}".strip()
    if riga:
        fuori.append(riga)
    return fuori
