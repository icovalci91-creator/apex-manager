"""Pagina Vivaio: i ragazzi che crescono in casa, e cosa costano."""
from __future__ import annotations

import pygame

from ...core import academy as AC, serie as SR
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, card


class AcademyPage(Page):
    ATTRS = (("pace", "Passo"), ("racecraft", "Duello"), ("consistency", "Costanza"),
             ("tyre_mgmt", "Gestione gomme"), ("wet", "Bagnato"),
             ("feedback", "Riscontro tecnico"))

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None

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
        bw = (c.w - 44) / 3
        self.widgets.append(Button((c.x + 16, c.bottom - 58, bw, 40),
                                   "Terzo pilota", self.to_reserve, "primary"))
        self.widgets.append(Button((c.x + 28 + bw, c.bottom - 58, bw, 40),
                                   "Titolare", self.to_race, "normal"))
        self.widgets.append(Button((c.x + 40 + 2 * bw, c.bottom - 58, bw, 40),
                                   "Lascia andare", self.let_go, "danger"))
        self._fill()

    def _fill(self) -> None:
        self.lista.items = AC.roster(self.gs, self.team)
        if self.sel not in self.lista.items:
            self.sel = self.lista.items[0] if self.lista.items else None
        if self.sel in self.lista.items:
            self.lista.selected = self.lista.items.index(self.sel)

    # ------------------------------------------------------------------ azioni
    def _select(self, i, d) -> None:
        self.sel = d

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
        T.text(surf, "SCHEDA", (self.right.x + 16, self.right.y + 12), 12, T.DIM_2, bold=True)
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
        c, gs, team = self.right, self.gs, self.team
        d = self.sel
        if d is None:
            T.text(surf, "Scegli un ragazzo dalla lista.", (c.x + 16, c.y + 48), 14, T.DIM)
            return
        T.text(surf, d.name, (c.x + 16, c.y + 34), 20, T.TEXT, bold=True, maxw=c.w - 32)
        T.text(surf, f"{d.age} anni  -  {d.nat}  -  nel programma fino al "
                     f"{d.contract_until}", (c.x + 16, c.y + 60), 13, T.DIM,
               maxw=c.w - 32)
        pygame.draw.line(surf, T.LINE, (c.x + 16, c.y + 84), (c.right - 16, c.y + 84))

        margine = max(0.0, d.potential - d.overall)
        righe = [("Vale adesso", f"{d.overall:.1f} / 100", T.stat_colour(d.overall, 62, 84)),
                 ("Potenziale", f"{d.potential:.0f}   ancora +{margine:.0f}",
                  T.OK if margine > 8 else T.DIM),
                 ("Ci costa", f"{d.salary:.2f} M$ all'anno", T.GOLD),
                 ("Se lo promuovessimo",
                  f"{d.market_value * 0.30:.2f} M$ da terzo pilota", T.DIM)]
        y = c.y + 94
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
            T.text(surf, "Non c'e' posto ne' da titolare ne' da terzo pilota: "
                         "per farlo salire va liberato qualcuno.",
                   (c.x + 16, y), 12, T.WARN, maxw=c.w - 32)
        else:
            T.text(surf, f"Posti liberi: {2 - n_tit} da titolare, "
                         f"{2 - n_ris} da terzo pilota.",
                   (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
        y += 20
        # dove corre, cosa costa quel posto e a che punto e' con la licenza
        sid = SR.serie_adatta(gs, d)
        T.text(surf, "DOVE CORRE", (c.x + 16, y), 12, T.DIM_2, bold=True)
        y += 20
        if sid:
            s = SR.scheda(sid)
            T.text(surf, s.get("nome", sid), (c.x + 16, y), 14, T.TEXT, bold=True,
                   maxw=c.w * 0.55)
            T.text(surf, f"{SR.costo_posto(sid):.2f} M$ il posto",
                   (c.right - 16, y), 13, T.GOLD, align="right")
            y += 20
            camp = SR.ultimo_campionato(gs, sid)
            riga = camp.riga_di(d.id) if camp else None
            if riga is not None:
                pos = camp.posizione_di(d.id)
                T.text(surf, f"L'anno scorso {pos}o su {len(camp.ordine)} con "
                             f"{riga.punti:.0f} punti"
                             + (f" e {riga.vittorie} vittorie" if riga.vittorie else ""),
                       (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
            else:
                T.text(surf, "Prima stagione qui: si vedra' a fine anno.",
                       (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
            y += 22
        else:
            T.paragraph(surf, "Non c'e' piu' una categoria in cui schierarlo: o gli si "
                              "trova un volante, o il percorso finisce qui.",
                        (c.x + 16, y), 12, T.WARN, c.w - 32)
            y += 34
        punti = SR.punti_licenza(d)
        col = T.OK if punti >= SR.LICENZA_SOGLIA else T.WARN
        T.text(surf, "Superlicenza", (c.x + 16, y), 13, T.DIM, maxw=140)
        T.bar(surf, (c.x + 156, y + 5, c.w - 232, 8), punti, SR.LICENZA_SOGLIA, col)
        T.text(surf, f"{punti}/{SR.LICENZA_SOGLIA}", (c.right - 16, y), 13, col,
               bold=True, align="right")
        y += 22
        T.paragraph(surf, f"Cresce con i risultati, non con il calendario: una stagione "
                          f"davanti vale il doppio di una in mezzo al gruppo. A "
                          f"{AC.LEAVE_AGE} anni il percorso finisce.",
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
