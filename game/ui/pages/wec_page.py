"""Pagina Endurance: il terzo campionato, e il piu' caro.

Quello che si guarda qui non e' la Formula E con altri nomi. Li' c'e' un tetto
di spesa che protegge anche chi va piano; qui non c'e' niente che protegga
nessuno. Si sceglie una classe - Hypercar o LMGT3 - si mette dentro la gente
che si vuole, e si scopre a dicembre se il conto torna.

E c'e' una cosa che gli altri due campionati non hanno: quello che si impara
qui torna dentro alla monoposto di Formula 1. Non velocita': roba che dura.
"""
from __future__ import annotations

import pygame

from ...core import wec as WEC
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, Slider, card


class WecPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.classe = "lmgt3"

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.left = pygame.Rect(r.x, r.y + 92, r.w * 0.50, r.h - 92)
        self.right = pygame.Rect(r.x + r.w * 0.52, r.y + 92, r.w * 0.48 - 4, r.h - 92)
        team = self.team
        if not WEC.ha(team):
            larg = (self.left.w - 44) / 2
            for i, cl in enumerate(WEC.classi()):
                b = Button((self.left.x + 16 + i * (larg + 12), self.left.y + 210,
                            larg, 30), WEC.scheda(cl).get("nome", cl).upper(),
                           (lambda k=cl: self.scegli(k)), "tab")
                b.active = (self.classe == cl)
                self.widgets.append(b)
            b = Button((self.left.x + 16, self.left.y + 252, self.left.w - 32, 44),
                       f"ISCRIVI LA SQUADRA ({WEC.costo_ingresso(team, self.classe):.0f} M$)",
                       self.apri, "primary")
            b.enabled = WEC.puo_aprire(self.gs, team, self.classe)[0]
            self.widgets.append(b)
            return
        self.slider = Slider((self.left.x + 16, self.left.y + 150, self.left.w - 32, 34),
                             "Ingegneri del programma",
                             value=WEC.ingegneri(team), lo=WEC.ingegneri_minimi(team),
                             hi=WEC.ingegneri_massimi(team), step=1, fmt="{:.0f}",
                             on_change=self.set_ingegneri)
        self.widgets.append(self.slider)
        self.widgets.append(Button((self.left.x + 16, self.left.bottom - 58,
                                    self.left.w - 32, 40),
                                   "Chiudi il programma", self.chiudi, "danger"))

    # ------------------------------------------------------------------ azioni
    def scegli(self, cl: str) -> None:
        self.classe = cl
        self.shell.build()

    def apri(self) -> None:
        nome = f"{self.team.short} Endurance"
        self.app.toast(WEC.apri(self.gs, self.team, nome, self.classe))
        self.shell.build()

    def set_ingegneri(self, v: float) -> None:
        self.team.wec_ingegneri = int(round(v))

    def chiudi(self) -> None:
        self.app.toast(WEC.chiudi(self.gs, self.team))
        self.shell.build()

    # ----------------------------------------------------------------- disegno
    def draw(self, surf) -> None:
        r = self.rect
        T.text(surf, "MONDIALE ENDURANCE", (r.x + 4, r.y + 4), 22, T.TEXT, bold=True)
        reg = WEC.corrente()
        T.text(surf, f"{reg.get('etichetta','')} - {reg.get('gare',0)} gare, "
                     f"da sei a ventiquattro ore",
               (r.x + 4, r.y + 34), 13, T.DIM)
        T.text(surf, "Qui non si vince col giro secco: si vince arrivando. "
                     "E quello che si impara torna dentro alla monoposto.",
               (r.x + 4, r.y + 56), 12, T.DIM_2, maxw=r.w - 20)
        if WEC.ha(self.team):
            self._programma(surf, self.left)
            self._classifica(surf, self.right)
        else:
            self._invito(surf, self.left)
            self._classi(surf, self.right)
        self.content_h = max(self.left.bottom, self.right.bottom) - r.y + 12

    def _invito(self, surf, c) -> None:
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "NON SIAMO ISCRITTI", (c.x + 16, c.y + 14), 15, T.TEXT, bold=True)
        T.paragraph(surf,
                    "L'endurance non ha un tetto di spesa: ha un mercato, e i numeri "
                    "sono grossi in tutte e due le direzioni. Un programma Hypercar "
                    "che vince Le Mans firma contratti che ripagano i quaranta "
                    "milioni e avanza; uno che arriva quinto di classe li brucia "
                    "tutti. In LMGT3 si rischia un quinto e si impara la meta'.",
                    (c.x + 16, c.y + 44), 13, T.DIM, maxw=c.w - 32)
        s = WEC.scheda(self.classe)
        ok, perche = WEC.puo_aprire(self.gs, self.team, self.classe)
        T.text(surf, s.get("nome", "").upper(), (c.x + 16, c.y + 140), 14, T.ACCENT,
               bold=True)
        T.paragraph(surf, s.get("nota", ""), (c.x + 16, c.y + 160), 12, T.DIM,
                    maxw=c.w - 32)
        T.text(surf, perche, (c.x + 16, c.y + 310), 13, T.OK if ok else T.BAD,
               maxw=c.w - 32)

    def _classi(self, surf, c) -> None:
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LE DUE CLASSI", (c.x + 16, c.y + 12), 14, T.TEXT, bold=True)
        y = c.y + 44
        for cl, s in WEC.classi().items():
            T.text(surf, s.get("nome", cl), (c.x + 16, y), 14, T.ACCENT, bold=True)
            y += 20
            for eti, val in (
                    ("Ingresso", f"{float(s.get('ingresso_meur', 0)) * WEC.cambio():.1f} M$"),
                    ("Gestione a stagione",
                     f"{float(s.get('gestione_meur', 0)) * WEC.cambio():.0f} M$ "
                     f"piu' gli ingegneri"),
                    ("Ingegneri", f"da {(s.get('ingegneri') or [0, 0])[0]} "
                                  f"a {(s.get('ingegneri') or [0, 0])[1]}"),
                    ("In pista", f"{s.get('vetture', 0)} vetture, "
                                 f"{s.get('costruttori', 0)} marchi")):
                T.text(surf, eti, (c.x + 24, y), 12, T.DIM_2)
                T.text(surf, str(val), (c.right - 16, y), 12, T.TEXT, align="right")
                y += 18
            y += 10
        # e cosa lascia alla Formula 1, che e' il motivo vero per farlo
        r = WEC.corrente().get("resa", {}) or {}
        T.text(surf, "COSA TORNA IN FORMULA 1", (c.x + 16, y + 8), 12, T.GOLD,
               bold=True)
        T.paragraph(surf, str(r.get("_nota", "")), (c.x + 16, y + 28), 12, T.DIM,
                    maxw=c.w - 32)

    def _programma(self, surf, c) -> None:
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        s = WEC.scheda(WEC.classe(team))
        T.text(surf, team.wec_nome.upper(), (c.x + 16, c.y + 12), 16, T.TEXT, bold=True)
        T.text(surf, f"classe {s.get('nome', '')}", (c.x + 16, c.y + 34), 12, T.DIM_2)
        if getattr(team, "wec_lemans", 0):
            T.text(surf, "CAMPIONI A LE MANS", (c.right - 16, c.y + 14), 13, T.GOLD,
                   bold=True, align="right")
        larg = (c.w - 44) / 3
        card(surf, (c.x + 16, c.y + 56, larg, 62), "PROGRAMMA",
             f"{WEC.livello(team):.0f}", f"tetto {WEC.muro(gs, team):.0f}")
        pos = int(getattr(team, "wec_posizione", 0) or 0)
        card(surf, (c.x + 28 + larg, c.y + 56, larg, 62), "MONDIALE",
             f"{pos}o" if pos else "-", f"{getattr(team, 'wec_punti', 0):.0f} punti")
        conto = WEC.bilancio(gs, team)
        card(surf, (c.x + 40 + 2 * larg, c.y + 56, larg, 62), "BILANCIO",
             f"{conto:+.1f}", "M$ a stagione", colour=T.OK if conto >= 0 else T.BAD)
        y = c.y + 194
        T.text(surf, "Qui non c'e' un tetto che fermi il conto: si puo' spendere "
                     "quanto si vuole, e si puo' fallire.",
               (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
        y += 28
        costo = WEC.costo_stagione(gs, team)
        for eti, val in (("Struttura, trasferte, equipaggi",
                          float(s.get("gestione_meur", 0)) * WEC.cambio()),
                         (f"Ingegneri ({WEC.ingegneri(team)})",
                          costo - float(s.get("gestione_meur", 0)) * WEC.cambio())):
            T.text(surf, eti, (c.x + 16, y), 12, T.DIM)
            T.text(surf, f"{val:.1f} M$", (c.right - 16, y), 12, T.DIM, mono=True,
                   align="right")
            y += 19
        T.text(surf, "Totale", (c.x + 16, y + 4), 13, T.TEXT, bold=True)
        T.text(surf, f"{costo:.1f} M$", (c.right - 16, y + 4), 13, T.TEXT, mono=True,
               align="right", bold=True)
        y += 30
        T.text(surf, f"Sponsor e montepremi: {WEC.entrate(gs, team):.1f} M$",
               (c.x + 16, y), 12, T.OK)
        y += 20
        imparato = WEC.resa(gs, team)
        if imparato:
            T.text(surf, "COSA PORTIAMO IN FORMULA 1", (c.x + 16, y), 11, T.GOLD,
                   bold=True)
            y += 18
            for eti, chiave in (("Affidabilita'", "affidabilita"),
                                ("Efficienza", "efficienza"),
                                ("Squadra ai box", "meccanici")):
                T.text(surf, eti, (c.x + 16, y), 12, T.DIM_2)
                T.text(surf, f"+{imparato.get(chiave, 0):.2f} a stagione",
                       (c.right - 16, y), 12, T.ACCENT, mono=True, align="right")
                y += 18

    def _classifica(self, surf, c) -> None:
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        cl = WEC.classe(team)
        T.text(surf, f"MONDIALE {WEC.scheda(cl).get('nome', '').upper()}",
               (c.x + 16, c.y + 12), 14, T.TEXT, bold=True)
        st = WEC.stato(gs)
        T.text(surf, f"{st.get('round', 0)} gare su {WEC.corrente().get('gare', 8)}",
               (c.right - 16, c.y + 14), 12, T.DIM_2, align="right")
        righe = WEC.classifica(gs, cl)
        y = c.y + 44
        rh = min(24, (c.h - 140) / max(1, len(righe)))
        for i, (r, punti, vitt) in enumerate(righe, 1):
            mio = r.get("team_id") == team.id
            if mio:
                T.panel(surf, (c.x + 8, y - 1, c.w - 16, rh - 1), T.PANEL_3, radius=4)
            col = T.TEXT if mio else T.DIM
            T.text(surf, str(i), (c.x + 34, y), 12, T.GOLD if i <= 3 else T.DIM_2,
                   align="right")
            T.text(surf, r["nome"], (c.x + 44, y), 13, col, bold=mio, maxw=c.w - 140)
            if vitt:
                T.text(surf, f"{vitt}v", (c.right - 74, y), 11, T.GOLD, mono=True,
                       align="right")
            T.text(surf, f"{punti:.0f}", (c.right - 16, y), 12, col, mono=True,
                   align="right", bold=mio)
            y += rh
        T.paragraph(surf,
                    "Le gare lunghe - Le Mans, il Bahrain, il Qatar - pagano una "
                    "volta e mezza, ed e' li' che il mondiale si decide. Le "
                    "ventiquattro ore contano il triplo in affidabilita': una "
                    "macchina fragile non le finisce.",
                    (c.x + 16, c.bottom - 72), 12, T.DIM_2, maxw=c.w - 32)
