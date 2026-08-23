"""Pagina Organico: quante persone lavorano in ogni reparto, e cosa costano."""
from __future__ import annotations

import pygame

from ...core import departments as DP
from ...core import economy
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, Slider, card


class WorkforcePage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.area = "aero"
        self.quanti = 10

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.56, r.h - 96)
        self.area_buttons = []
        y = left.y + 46
        for key in DP.REPARTI:
            b = Button((left.x + 16, y, left.w - 32, 62), "")
            b.on_click = (lambda k=key: self._pick(k))
            b.draw = (lambda surf, b=b, k=key: self._draw_area(surf, b, k))
            self.area_buttons.append(b)
            self.widgets.append(b)
            y += 68
        self._mark()

        right = pygame.Rect(r.x + r.w * 0.58, r.y + 96, r.w * 0.42 - 4, r.h - 96)
        self.s_quanti = Slider((right.x + 16, right.y + 176, right.w - 32, 28), "Persone",
                               self.quanti, 1, 40,
                               on_change=self._set_quanti, fmt="{:.0f}")
        self.widgets.append(self.s_quanti)
        self.widgets.append(Button((right.x + 16, right.y + 216, (right.w - 44) / 2, 40),
                                   "Assumi", self.hire, "primary"))
        self.widgets.append(Button((right.x + 28 + (right.w - 44) / 2, right.y + 216,
                                    (right.w - 44) / 2, 40),
                                   "Manda a casa", self.release, "danger"))

    def _mark(self) -> None:
        for b, key in zip(self.area_buttons, DP.REPARTI):
            b.active = (key == self.area)

    # ------------------------------------------------------------------ azioni
    def _pick(self, k) -> None:
        self.area = k
        self._mark()

    def _set_quanti(self, v) -> None:
        self.quanti = int(round(v))

    def hire(self) -> None:
        ok, msg = DP.hire(self.gs, self.team, self.area, self.quanti)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "squadra")

    def release(self) -> None:
        ok, msg = DP.release(self.gs, self.team, self.area, self.quanti)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "squadra")

    def refresh(self) -> None:
        self.build()

    # ------------------------------------------------------- riga di reparto
    def _draw_area(self, surf, b, key) -> None:
        team, meta = self.team, DP.REPARTI[key]
        n = DP.headcount(team, key)
        f = DP.size_factor(team, key)
        bg = T.PANEL_3 if b.active else (T.PANEL_2 if b.hover else T.PANEL)
        T.panel(surf, b.rect, bg, radius=8, border=T.LINE if b.active else None)
        if b.active:
            pygame.draw.rect(surf, T.ACCENT, (b.rect.x, b.rect.y + 8, 3, b.rect.h - 16))
        T.text(surf, meta["label"], (b.rect.x + 16, b.rect.y + 8), 15, T.TEXT, bold=True)
        T.text(surf, f"{n}", (b.rect.right - 16, b.rect.y + 6), 20,
               T.TEXT, bold=True, align="right")
        T.text(surf, "persone", (b.rect.right - 16, b.rect.y + 30), 11, T.DIM_2,
               align="right")
        # il rapporto con la dimensione di riferimento, che e' quella di una
        # squadra di vertice in salute
        rif = DP.ref_for(team, key)
        col = T.OK if f >= 1.0 else (T.WARN if f >= 0.88 else T.BAD)
        T.bar(surf, (b.rect.x + 16, b.rect.y + 32, b.rect.w * 0.52, 8),
              min(n, rif * 1.4), rif * 1.4, col)
        pygame.draw.line(surf, T.DIM_2,
                         (b.rect.x + 16 + b.rect.w * 0.52 / 1.4, b.rect.y + 28),
                         (b.rect.x + 16 + b.rect.w * 0.52 / 1.4, b.rect.y + 44), 1)
        T.text(surf, f"resa x{f:.2f}   -{DP.area_cost(team, key):.1f} M$ all'anno",
               (b.rect.x + 16, b.rect.y + 44), 12, T.DIM)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        cw = (r.w - 32) / 3
        tot = DP.total_headcount(team)
        monte = DP.payroll(team)
        card(surf, (r.x, r.y, cw, 86), "Persone nei reparti", f"{tot}",
             f"piu' i {len(team.staff)} nomi dell'organigramma", accent=T.ACCENT)
        quota = monte / max(1.0, economy.cap_limit(gs))
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Monte stipendi", f"{monte:.1f} M$",
             f"il {quota*100:.0f}% del tetto di spesa", accent=T.GOLD,
             colour=T.WARN if quota > 0.45 else T.TEXT)
        peggio = min(DP.REPARTI, key=lambda a: DP.size_factor(team, a))
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Reparto piu' scoperto",
             DP.REPARTI[peggio]["label"], f"resa x{DP.size_factor(team, peggio):.2f}",
             accent=T.BAD if DP.size_factor(team, peggio) < 0.9 else T.OK)

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.56, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I REPARTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, "la tacca e' la dimensione di una squadra di vertice",
               (left.right - 16, left.y + 12), 11, T.DIM_2, align="right")

        right = pygame.Rect(r.x + r.w * 0.58, r.y + 96, r.w * 0.42 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        meta = DP.REPARTI[self.area]
        T.text(surf, meta["label"].upper(), (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        y = right.y + 36
        for riga in _wrap(meta["desc"], 52):
            T.text(surf, riga, (right.x + 16, y), 13, T.DIM, maxw=right.w - 32)
            y += 17

        capo = team.role(meta["boss"])
        T.text(surf, "Lo dirige", (right.x + 16, right.y + 96), 13, T.DIM)
        T.text(surf, capo.name if capo else "nessuno",
               (right.right - 16, right.y + 96), 13,
               T.TEXT if capo else T.BAD, bold=True, align="right")
        T.text(surf, "Assunzioni ancora possibili quest'anno",
               (right.x + 16, right.y + 118), 13, T.DIM)
        T.text(surf, f"{DP.hiring_room(team, self.area)}",
               (right.right - 16, right.y + 118), 13, T.TEXT, bold=True, align="right")
        T.text(surf, "Costo di una persona", (right.x + 16, right.y + 140), 13, T.DIM)
        T.text(surf, f"{meta['cost']:.3f} M$ all'anno",
               (right.right - 16, right.y + 140), 13, T.TEXT, bold=True, align="right")

        prezzo = DP.hire_cost(team, self.area, self.quanti)
        annuo = self.quanti * meta["cost"]
        ok, why = DP.can_hire(gs, team, self.area, self.quanti)
        T.text(surf, f"Assumerne {self.quanti} costa {prezzo:.2f} M$ subito e "
                     f"{annuo:.1f} M$ all'anno.",
               (right.x + 16, right.y + 268), 13, T.TEXT, maxw=right.w - 32)
        nuovo = DP.headcount(team, self.area) + self.quanti
        f_ora = DP.size_factor(team, self.area)
        f_poi = DP.FLOOR + DP.SPAN * (nuovo / DP.ref_for(team, self.area)) ** DP.CURVE
        T.text(surf, f"Resa del reparto da x{f_ora:.2f} a x{f_poi:.2f}.",
               (right.x + 16, right.y + 290), 13,
               T.OK if f_poi > f_ora else T.DIM, maxw=right.w - 32)
        if not ok:
            T.text(surf, why, (right.x + 16, right.y + 312), 13, T.BAD, maxw=right.w - 32)

        for i, riga in enumerate((
                "Gli stipendi stanno dentro il tetto di spesa: ogni persona in",
                "piu' e' un pezzo di aggiornamento in meno. Chi taglia risparmia",
                "subito e lo paga in pista due anni dopo, che e' esattamente",
                "quello che e' successo a mezza griglia quando il tetto e' arrivato.")):
            T.text(surf, riga, (right.x + 16, right.bottom - 76 + i * 17), 12,
                   T.DIM_2, maxw=right.w - 32)
        super().draw(surf)


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
