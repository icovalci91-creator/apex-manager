"""Pagina Vivaio: i ragazzi che crescono in casa, e cosa costano."""
from __future__ import annotations

import pygame

from ...core import academy as AC, serie as SR
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Toggle, card
from .people_pages import _pannelli_scheda


class AcademyPage(Page):
    """Il vivaio in due schermate, come i piloti.

    La lista: in cima quanto costa e che gente arriva, sotto i ragazzi in una
    tabella larga quanto la pagina. Un clic apre la scheda del ragazzo a
    tutto schermo: a sinistra chi e', come e' messo, come e' andato il suo
    campionato e i pulsanti per promuoverlo; a destra dove corre, con le
    categorie una sotto l'altra.
    """

    ATTRS = (("pace", "Passo"), ("racecraft", "Duello"), ("consistency", "Costanza"),
             ("tyre_mgmt", "Gestione gomme"), ("wet", "Bagnato"),
             ("feedback", "Riscontro tecnico"))
    RIGA_H = 50
    CAT_H = 58

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None
        self.vista = "lista"          # lista | scheda
        self.cat_btn = {}

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.cat_btn = {}
        self.left = pygame.Rect(r.x, r.y + 104, r.w * 0.42, r.h - 104)
        self.right = pygame.Rect(r.x + r.w * 0.44, r.y + 104, r.w * 0.56 - 4, r.h - 104)
        if not AC.has(self.team):
            self.found_btn = Button((self.left.x + 16, self.left.bottom - 70,
                                     self.left.w - 32, 48),
                                    f"Fonda il vivaio ({AC.FOUND_COST:.0f} M$)",
                                    self.found, "primary")
            ok, _w = AC.can_found(self.gs, self.team)
            self.found_btn.enabled = ok
            self.widgets.append(self.found_btn)
            return
        if self.vista == "scheda" and self.sel is not None \
                and self.sel in AC.roster(self.gs, self.team):
            self._build_scheda()
        else:
            self.vista = "lista"
            self._build_lista()

    def _build_lista(self) -> None:
        r = self.rect
        top = r.y + 136
        self.delega_tg = Toggle((r.right - 380, r.y + 100, 380, 28),
                                "Le categorie le decide il responsabile",
                                bool(self.team.vivaio_auto), self._set_delega)
        self.widgets.append(self.delega_tg)
        self.lista = ScrollList((r.x, top, r.w, max(120, r.bottom - top)), row_h=self.RIGA_H,
                                draw_row=self._row, header_h=34, draw_header=self._testa,
                                on_select=lambda i, d: self.apri(d))
        self.lista.items = AC.roster(self.gs, self.team)
        self.widgets.append(self.lista)

    def _build_scheda(self) -> None:
        r = self.rect
        self.widgets.append(Button((r.x, r.y, 210, 40), "\u00ab  Torna al vivaio",
                                   self.chiudi, "ghost"))
        self.pan_sx, self.pan_dx = _pannelli_scheda(r)
        L, c = self.pan_sx, self.pan_dx
        bw = (L.w - 48 - 24) / 3
        for i, (lab, cb, stile) in enumerate((("Terzo pilota", self.to_reserve, "primary"),
                                              ("Titolare", self.to_race, "normal"),
                                              ("Lascia andare", self.let_go, "danger"))):
            self.widgets.append(Button((L.x + 24 + i * (bw + 12), L.bottom - 66, bw, 44),
                                       lab, cb, stile))
        self.delega_tg = Toggle((c.x + 24, c.y + 50, c.w - 48, 28),
                                "Decide il responsabile del vivaio",
                                bool(self.team.vivaio_auto), self._set_delega)
        self.widgets.append(self.delega_tg)
        y = self.riga_y()
        for sid in SR.scala():
            b = Button((c.x + 24, y + 6, 84, 34), SR.sigla(sid),
                       (lambda s=sid: self.set_serie(s)), "normal")
            self.cat_btn[sid] = b
            self.widgets.append(b)
            y += self.CAT_H
        self._sync_cat()

    def riga_y(self) -> int:
        """Dove comincia l'elenco delle categorie: sotto l'interruttore e la spiega."""
        return int(self.pan_dx.y + 140)

    # ------------------------------------------------------------ navigazione
    def apri(self, d) -> None:
        self.sel = d
        self.vista = "scheda"
        self.scroll = 0.0
        self.layout(self.view)

    def chiudi(self) -> None:
        self.vista = "lista"
        self.scroll = 0.0
        self.layout(self.view)

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
            b.style = "tab" if b.active else "normal"

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

    # ------------------------------------------------------------------ azioni
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
            self.chiudi()

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
            self.chiudi()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- la lista
    COLONNE = (("Ragazzo", 0.0, "left"), ("Eta'", 0.30, "left"), ("Categoria", 0.38, "left"),
               ("Vale", 0.66, "right"), ("Potenziale", 0.78, "right"),
               ("Superlicenza", 0.89, "right"), ("Fino al", 0.985, "right"))

    def _testa(self, surf, rect) -> None:
        T.panel(surf, rect, T.PANEL_2, radius=8, rilievo=False)
        for lab, f, al in self.COLONNE:
            if rect.w < 1000:
                lab = {"Potenziale": "Pot.", "Superlicenza": "Licenza"}.get(lab, lab)
            T.text(surf, lab.upper(), (int(rect.x + 16 + f * (rect.w - 32)), rect.y + 9), 12,
                   T.DIM, bold=True, align=al)

    def _row(self, surf, rect, i, d) -> None:
        w = rect.w - 32
        X = lambda f: int(rect.x + 16 + f * w)
        cy = rect.centery - 11
        T.text(surf, d.name, (X(0), cy), 16, T.TEXT, bold=True, maxw=int(0.28 * w))
        T.text(surf, f"{d.age}", (X(0.30), cy), 16, T.TEXT)
        sid = SR.serie_adatta(self.gs, d)
        T.text(surf, SR.scheda(sid).get("nome", sid) if sid else "fuori scala", (X(0.38), cy),
               16, T.GOLD if sid else T.BAD, maxw=int(0.25 * w))
        T.text(surf, f"{d.overall:.0f}", (X(0.66), cy - 2), 20,
               T.stat_colour(d.overall, 62, 84), bold=True, align="right")
        margine = max(0.0, d.potential - d.overall)
        T.text(surf, f"{d.potential:.0f}" + (f"  (+{margine:.0f})" if rect.w >= 1000 else ""),
               (X(0.78), cy), 16, T.OK if margine > 8 else T.DIM, align="right")
        punti = SR.punti_licenza(d)
        T.text(surf, f"{punti}/{SR.LICENZA_SOGLIA}", (X(0.89), cy), 16,
               T.OK if punti >= SR.LICENZA_SOGLIA else T.DIM, align="right")
        T.text(surf, f"{d.contract_until}", (X(0.985), cy), 16, T.DIM, align="right")

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        cw = (r.w - 32) / 3
        if not AC.has(team):
            self._draw_none(surf, cw)
            super().draw(surf)
            return
        if self.vista == "scheda" and self.sel is not None:
            self._draw_scheda(surf)
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
        T.text(surf, "I NOSTRI RAGAZZI", (r.x + 2, r.y + 106), 13, T.DIM, bold=True)
        T.text(surf, "un clic apre la scheda", (r.x + 170, r.y + 106), 13, T.DIM_2)
        if not ragazzi:
            T.text(surf, "Nessuno in rosa: i prossimi arrivano a fine stagione.",
                   (r.x + 16, self.lista.rect.y + 50), 15, T.DIM)
        super().draw(surf)

    def _draw_scheda(self, surf) -> None:
        gs, team, d = self.gs, self.team, self.sel
        L, c = self.pan_sx, self.pan_dx
        # --- il ragazzo
        T.panel(surf, L, T.PANEL, radius=14, border=T.LINE)
        T.text(surf, d.name, (L.x + 24, L.y + 18), 30, T.TEXT, bold=True, maxw=L.w - 48)
        T.text(surf, f"{d.age} anni  \u00b7  {d.nat}  \u00b7  nel programma fino al "
                     f"{d.contract_until}", (L.x + 24, L.y + 60), 16, T.DIM, maxw=L.w - 48)
        margine = max(0.0, d.potential - d.overall)
        box = [("Vale adesso", f"{d.overall:.1f}", T.stat_colour(d.overall, 62, 84)),
               ("Potenziale", f"{d.potential:.0f}  +{margine:.0f}",
                T.OK if margine > 8 else T.TEXT),
               ("Ci costa", f"{d.salary:.2f} M$", T.GOLD),
               ("Da terzo pilota", f"{d.market_value * 0.30:.2f} M$", T.DIM)]
        bw = (L.w - 48 - 36) / 4
        for i, (lab, val, cc) in enumerate(box):
            b = pygame.Rect(int(L.x + 24 + i * (bw + 12)), L.y + 96, int(bw), 68)
            T.panel(surf, b, T.PANEL_2, radius=10, rilievo=False)
            T.text(surf, lab, (b.x + 12, b.y + 9), 13, T.DIM, maxw=b.w - 18)
            T.text(surf, val, (b.x + 12, b.y + 31), 20, cc, bold=True, maxw=b.w - 18)
        y = L.y + 182
        T.text(surf, "COM'E' MESSO", (L.x + 24, y), 13, T.DIM, bold=True)
        y += 26
        cw = (L.w - 48 - 24) / 2
        for j, (a, lab) in enumerate(self.ATTRS):
            v = getattr(d, a)
            cx = L.x + 24 + (j % 2) * (cw + 24)
            cy = y + (j // 2) * 30
            T.text(surf, lab, (cx, cy), 15, T.TEXT, maxw=int(cw * 0.45))
            T.bar(surf, (int(cx + cw * 0.47), cy + 7, int(cw * 0.40), 9), v, 100,
                  T.stat_colour(v, 62, 86))
            T.text(surf, f"{v:.0f}", (int(cx + cw), cy), 16, T.stat_colour(v, 62, 86),
                   bold=True, align="right")
        y += 3 * 30 + 12
        y = self._draw_campionato(surf, L, y)
        n_ris, n_tit = len(team.reserves), len(team.drivers)
        testo = ("Non c'e' posto ne' da titolare ne' da terzo pilota."
                 if n_ris >= 2 and n_tit >= 2 else
                 f"Posti liberi in prima squadra: {2 - n_tit} da titolare, "
                 f"{2 - n_ris} da terzo pilota.")
        T.text(surf, testo, (L.x + 24, L.bottom - 96), 14,
               T.WARN if n_ris >= 2 and n_tit >= 2 else T.DIM, maxw=L.w - 48)

        # --- dove corre
        T.panel(surf, c, T.PANEL, radius=14, border=T.LINE)
        auto = bool(team.vivaio_auto)
        T.text(surf, "DOVE CORRE", (c.x + 24, c.y + 20), 13, T.DIM, bold=True)
        adesso = SR.serie_adatta(gs, d)
        T.text(surf, f"quest'anno in {SR.sigla(adesso)}" if adesso else "senza una categoria",
               (c.right - 24, c.y + 18), 15, T.GOLD if adesso else T.BAD, bold=True,
               align="right")
        T.paragraph(surf, ("Sceglie lui: mette ognuno dove pensa che debba stare, e quanto "
                           "ci prende dipende da quanto vale." if auto else
                           "Decidi tu: un gradino alla volta, dentro l'eta' giusta, e un "
                           "campionato vinto non si rifa'."),
                    (c.x + 24, c.y + 90), 14, T.DIM, c.w - 48)
        y = self.riga_y()
        for sid in SR.scala():
            s = SR.scheda(sid)
            ok, why = SR.verifica(gs, d, sid)
            scelto = sid == adesso
            col = T.GOLD if scelto else (T.TEXT if ok else T.DIM_2)
            x = c.x + 124
            T.text(surf, s.get("nome", sid), (x, y + 4), 16, col, bold=True, maxw=c.w * 0.45)
            T.text(surf, f"{SR.costo_posto(sid):.2f} M$", (c.right - 24, y + 4), 16,
                   T.GOLD if ok else T.DIM_2, bold=True, align="right")
            emin, emax = s.get("eta", [15, 24])
            T.text(surf, f"{s.get('gare', 0)} gare  \u00b7  {s.get('vetture', 0)} al via  "
                         f"\u00b7  {emin}-{emax} anni", (x, y + 27), 13, T.DIM,
                   maxw=int(c.w * 0.40))
            T.text(surf, why if not ok else SR.nota(gs, d, sid), (c.right - 24, y + 27), 13,
                   T.BAD if not ok else T.DIM, align="right", maxw=int(c.w * 0.36))
            y += self.CAT_H
        y += 8
        punti = SR.punti_licenza(d)
        col = T.OK if punti >= SR.LICENZA_SOGLIA else T.WARN
        T.text(surf, "Superlicenza", (c.x + 24, y), 15, T.TEXT)
        T.bar(surf, (c.x + 170, y + 7, c.w - 270, 9), punti, SR.LICENZA_SOGLIA, col)
        T.text(surf, f"{punti}/{SR.LICENZA_SOGLIA}", (c.right - 24, y), 16, col, bold=True,
               align="right")
        y += 30
        T.text(surf, f"I posti di tutto il vivaio costano {AC.running_cost(gs, team):.2f} M$ "
                     f"l'anno.", (c.x + 24, y), 14, T.DIM_2, maxw=c.w - 48)

    def _draw_campionato(self, surf, L, y) -> int:
        """Come e' finito il campionato dove corre il ragazzo.

        Un vivaio non e' una lista di valutazioni: e' gente che corre da
        qualche parte contro qualcun altro, e quel qualcun altro ha un nome e
        una squadra. Senza la classifica, "settantadue di overall" non vuol
        dire niente.
        """
        gs, d = self.gs, self.sel
        sid = SR.serie_adatta(gs, d) if d is not None else ""
        camp = SR.ultimo_campionato(gs, sid) if sid else None
        x0, largo = L.x + 24, L.w - 48
        if camp is None or not camp.ordine:
            T.text(surf, "CAMPIONATO", (x0, y), 13, T.DIM, bold=True)
            T.paragraph(surf, "La prima stagione di categorie si corre a fine anno: da li' in "
                              "poi qui c'e' la classifica.", (x0, y + 24), 14, T.DIM_2, largo)
            return y + 70
        s = SR.scheda(sid)
        T.text(surf, f"{s.get('nome', sid).upper()}  {camp.stagione}", (x0, y), 13, T.GOLD,
               bold=True)
        T.text(surf, f"{len(camp.ordine)} al via", (x0 + largo, y), 13, T.DIM_2,
               align="right")
        y += 24
        mia = camp.posizione_di(d.id)
        righe = list(enumerate(camp.ordine[:3], 1))
        if mia > 3:
            righe.append((mia, camp.ordine[mia - 1]))
        for pos, riga in righe:
            nostro = bool(riga.driver_id)
            col = T.GOLD if nostro else T.TEXT
            T.text(surf, f"{pos}", (x0 + 18, y), 15, col, align="right")
            T.text(surf, riga.nome, (x0 + 30, y), 15, col, bold=nostro, maxw=int(largo * 0.45))
            T.text(surf, riga.squadra, (x0 + 30 + int(largo * 0.47), y), 14, T.DIM_2,
                   maxw=int(largo * 0.33))
            T.text(surf, f"{riga.punti:.0f}", (x0 + largo, y), 15, col, bold=True,
                   align="right")
            y += 22
        return y + 8

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
