"""Pagina Formula E: il secondo campionato della casa.

Quello che si guarda qui non e' la Formula 1 in piccolo. Il programma ha un
tetto di spesa suo, una manopola sola - quanti ingegneri ci lavorano - e un
bilancio che si chiude o non si chiude a seconda di come e' andata. E in cima
c'e' il regolamento, per esteso, perche' una gara di Formula E si capisce solo
sapendo quanto dura, quanta energia c'e' e cosa fanno Attack Mode e Pit Boost.
"""
from __future__ import annotations

import pygame

from ...core import formulae as FE
from .. import theme as T
from ..scenes.shell import Page
from ..widgets import Button, Slider, Tabs, Toggle, card


class FormulaEPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.tab = 0     # 0 = il programma, 1 = il mondiale

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.left = pygame.Rect(r.x, r.y + 92, r.w * 0.50, r.h - 92)
        self.right = pygame.Rect(r.x + r.w * 0.52, r.y + 92, r.w * 0.48 - 4, r.h - 92)
        team = self.team
        if not FE.ha(team):
            b = Button((self.left.x + 16, self.left.y + 250, self.left.w - 32, 44),
                       f"Iscrivi la squadra ({FE.costo_ingresso(team):.0f} M$)",
                       self.apri, "primary")
            ok, _ = FE.puo_aprire(self.gs, team)
            b.enabled = ok
            self.widgets.append(b)
            self.costruttore = Toggle((self.left.x + 16, self.left.y + 204, 24, 24),
                                      "Propulsore costruito in casa",
                                      value=False)
            self.widgets.append(self.costruttore)
            return
        self.costruttore = None
        self.tabs = Tabs((self.left.x + 12, self.left.y - 32, 396, 26),
                         ("Il programma", "I piloti", "Il mondiale"),
                         on_change=self._switch, w=128)
        self.tabs.index = self.tab
        for i, b in enumerate(self.tabs.buttons):
            b.active = (i == self.tab)
        self.widgets.append(self.tabs)
        if self.tab == 1:
            self._build_piloti()
            return
        if self.tab == 2:
            self._build_corri()
            return
        massimo = FE.ingegneri_massimi(self.gs, team)
        self.slider = Slider((self.left.x + 16, self.left.y + 148, self.left.w - 32, 34),
                             "Ingegneri del programma", value=FE.ingegneri(team),
                             lo=FE.INGEGNERI_MIN, hi=massimo, step=1, fmt="{:.0f}",
                             on_change=self.set_ingegneri)
        self.widgets.append(self.slider)
        # i due sedili: chi ci mettiamo. Un professionista della serie fa il suo
        # e non cresce; un ragazzo del vivaio costa risultati e cresce davvero
        y = self.left.bottom - 108
        larg = (self.left.w - 44) / 2
        for i in range(2):
            self.widgets.append(Button(
                (self.left.x + 16 + i * (larg + 12), y, larg, 32),
                self._etichetta_sedile(i), (lambda k=i: self.gira_pilota(k)), "normal"))
        larg2 = (self.left.w - 44) / 2
        self._build_corri(larg2)
        self.widgets.append(Button((self.left.x + 28 + larg2, self.left.bottom - 58,
                                    larg2, 40),
                                   "Chiudi il programma", self.chiudi, "danger"))

    def _build_corri(self, larg: float = 0.0) -> None:
        larg = larg or (self.left.w - 32)
        pista, _ = FE.prossima(self.gs, self.team)
        eti = ("CORRI L'E-PRIX" if pista is not None else "STAGIONE FINITA")
        b = Button((self.left.x + 16, self.left.bottom - 58, larg, 40), eti,
                   self.corri, "primary",
                   tip="La prossima gara del mondiale, dal muretto")
        b.enabled = pista is not None
        self.widgets.append(b)

    def _switch(self, i: int) -> None:
        self.tab = i
        self.shell.build()

    def _candidati(self) -> list:
        """Chi puo' guidare li': nessuno, le riserve, i ragazzi del vivaio."""
        team, gs = self.team, self.gs
        fuori = [""]
        for did in list(team.reserves) + list(team.academy):
            if did in gs.drivers and did not in fuori:
                fuori.append(did)
        return fuori

    def _etichetta_sedile(self, i: int) -> str:
        ids = list(getattr(self.team, "fe_piloti", []) or [])
        did = ids[i] if i < len(ids) else ""
        d = self.gs.drivers.get(did)
        return d.short if d is not None else "ingaggiato"

    def gira_pilota(self, i: int) -> None:
        """Gira fra i piloti possibili per quel sedile."""
        team = self.team
        ids = list(getattr(team, "fe_piloti", []) or [])
        while len(ids) < 2:
            ids.append("")
        cand = self._candidati()
        # chi guida l'altra macchina non puo' guidare anche questa
        altro = ids[1 - i]
        scelta = ids[i]
        pos = cand.index(scelta) if scelta in cand else 0
        for _ in range(len(cand)):
            pos = (pos + 1) % len(cand)
            if cand[pos] == "" or cand[pos] != altro:
                break
        ids[i] = cand[pos]
        team.fe_piloti = [x for x in ids if x] + [""] * ids.count("")
        team.fe_piloti = ids
        self.shell.build()

    # ------------------------------------------------------------------ azioni
    def apri(self) -> None:
        team = self.team
        nome = f"{team.short} Formula E"
        costruttore = bool(self.costruttore and self.costruttore.value)
        self.app.toast(FE.apri(self.gs, team, nome, costruttore))
        self.shell.build()

    def set_ingegneri(self, v: float) -> None:
        self.team.fe_ingegneri = int(round(v))

    def chiudi(self) -> None:
        self.app.toast(FE.chiudi(self.gs, self.team))
        self.shell.build()

    def corri(self) -> None:
        """Il prossimo E-Prix, corso dal muretto invece che contato.

        Quale gara sia lo dice il calendario: si gira su di esso stagione dopo
        stagione, cosi' chi corre due E-Prix di fila non li corre nello stesso
        posto.
        """
        pista, formato = FE.prossima(self.gs, self.team)
        if pista is None:
            self.app.toast("Il campionato di quest'anno e' finito.")
            return
        from ..scenes.eprix import EPrixScene
        self.app.push(EPrixScene(self.app, pista, formato))

    # ----------------------------------------------------------------- disegno
    def draw(self, surf) -> None:
        r = self.rect
        T.text(surf, "FORMULA E", (r.x + 4, r.y + 4), 22, T.TEXT, bold=True)
        reg = FE.corrente()
        T.text(surf, f"{reg.get('etichetta','')} - {reg.get('gare',0)} gare in "
                     f"{reg.get('sedi',0)} citta', {reg.get('vetture',0)} macchine",
               (r.x + 4, r.y + 34), 13, T.DIM)
        T.text(surf, "Un campionato a parte: gente sua, tetto di spesa suo, bilancio suo. "
                     "Non toglie niente alla Formula 1.",
               (r.x + 4, r.y + 54), 12, T.DIM_2, maxw=r.w - 20)
        # il calendario: quello che cambia da una stagione all'altra, ed e' la
        # ragione per cui il campionato non e' sempre lo stesso
        piste = FE.calendario(self.gs)
        if piste:
            nomi = ", ".join(t.gp.replace("E-Prix di ", "") for t in piste)
            T.text(surf, f"{len(piste)} sedi: {nomi}", (r.x + 4, r.y + 72), 12, T.DIM,
                   maxw=r.w - 20)
        if not FE.ha(self.team):
            self._invito(surf)
        elif self.tab == 1:
            self._sedili(surf, self.left)
        elif self.tab == 2:
            self._mondiale(surf, self.left)
        else:
            self._programma(surf)
        if not FE.ha(self.team) or self.tab == 0:
            self._regolamento(surf, self.right)
        elif self.tab == 1:
            self._mercato(surf, self.right)
        else:
            self._calendario(surf, self.right)
        self.content_h = max(self.left.bottom, self.right.bottom) - r.y + 12

    def _invito(self, surf) -> None:
        c = self.left
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "NON SIAMO ISCRITTI", (c.x + 16, c.y + 14), 15, T.TEXT, bold=True)
        ok, perche = FE.puo_aprire(self.gs, self.team)
        T.paragraph(surf,
                    "Iscriversi vuol dire comprare due monoposto, aprire una sede e "
                    "trovare la gente. Il costo grosso pero' non e' quello: e' tenerlo "
                    "aperto ogni anno. Il tetto della serie e' un decimo di quello della "
                    "Formula 1, stipendi dei piloti compresi, e chi non vince quei soldi "
                    "non li rivede.",
                    (c.x + 16, c.y + 44), 13, T.DIM, maxw=c.w - 32)
        T.text(surf, perche, (c.x + 16, c.y + 160), 13,
               T.OK if ok else T.BAD, maxw=c.w - 32)
        sconto = getattr(self.team, "proprieta", "") == "costruttore"
        if sconto:
            T.paragraph(surf, "Sei un costruttore: la casa madre ci mette la sua parte "
                              "sull'ingresso, e il consiglio lo vuole.",
                        (c.x + 16, c.y + 182), 12, T.ACCENT, maxw=c.w - 32)

    def _programma(self, surf) -> None:
        c, team, gs = self.left, self.team, self.gs
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, team.fe_nome.upper(), (c.x + 16, c.y + 12), 16, T.TEXT, bold=True)
        chi = "propulsore costruito in casa" if team.fe_costruttore else "propulsore cliente"
        T.text(surf, chi, (c.x + 16, c.y + 34), 12, T.DIM_2)
        larg = (c.w - 44) / 3
        card(surf, (c.x + 16, c.y + 56, larg, 62), "PROGRAMMA",
             f"{FE.livello(team):.0f}", f"tetto {FE.muro(gs, team):.0f}")
        pos = int(getattr(team, "fe_posizione", 0) or 0)
        card(surf, (c.x + 28 + larg, c.y + 56, larg, 62), "MONDIALE",
             f"{pos}o" if pos else "-", f"{getattr(team,'fe_punti',0):.0f} punti")
        conto = FE.bilancio(gs, team)
        card(surf, (c.x + 40 + 2 * larg, c.y + 56, larg, 62), "BILANCIO",
             f"{conto:+.1f}", "M$ a stagione", colour=T.OK if conto >= 0 else T.BAD)
        # la manopola, che e' una sola: quanta gente ci si mette
        y = c.y + 190
        T.text(surf, "Piu' ingegneri, piu' performance, piu' costi. Il tetto della serie "
                     "dice fin dove ci si puo' spingere.",
               (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
        y += 26
        for eti, val, col in (
                ("Gestione, trasferte, ricambi", FE.GESTIONE_BASE, T.DIM),
                (f"Ingegneri ({FE.ingegneri(team)})",
                 FE.ingegneri(team) * FE.COSTO_INGEGNERE, T.DIM),
                ("Propulsore",
                 FE.COSTRUTTORE_COSTO if team.fe_costruttore else 0.9, T.DIM)):
            T.text(surf, eti, (c.x + 16, y), 12, col)
            T.text(surf, f"{val:.1f} M$", (c.right - 16, y), 12, col, mono=True,
                   align="right")
            y += 18
        spesa = FE.costo_stagione(gs, team)
        t = FE.tetto(gs)
        T.text(surf, "Totale", (c.x + 16, y + 4), 13, T.TEXT, bold=True)
        T.text(surf, f"{spesa:.1f} di {t:.1f} M$", (c.right - 16, y + 4), 13,
               T.OK if spesa <= t else T.BAD, mono=True, align="right", bold=True)
        T.bar(surf, (c.x + 16, y + 26, c.w - 32, 8), min(spesa, t * 1.2), t * 1.2,
              T.OK if spesa <= t else T.BAD)
        y += 44
        entrate = FE.entrate(gs, team)
        T.text(surf, f"Sponsor e montepremi: {entrate:.1f} M$", (c.x + 16, y), 12, T.OK)
        y += 18
        # la spiegazione solo se ci sta: su una finestra bassa il pannello e'
        # corto e sotto ci sono i due sedili
        if c.bottom - 132 - y > 22:
            T.text(surf, "Un marchio noto firma contratti che una squadra sconosciuta "
                         "non vede, e vincere ne porta altri.",
                   (c.x + 16, y), 12, T.DIM_2, maxw=c.w - 32)
        # i sedili
        T.text(surf, "CHI GUIDA", (c.x + 16, c.bottom - 128), 11, T.DIM_2, bold=True)
        nostri = FE.piloti(gs, team)
        if nostri:
            forze = "  ".join(f"{d.short} {FE.forza_macchina(gs, team, d):.0f}"
                              for d in nostri)
            T.text(surf, forze, (c.right - 16, c.bottom - 128), 11, T.DIM,
                   mono=True, align="right")
        else:
            T.text(surf, "professionisti della serie", (c.right - 16, c.bottom - 128),
                   11, T.DIM, align="right")

    # ---------------------------------------------------------------- i piloti
    def _build_piloti(self) -> None:
        """I due sedili a sinistra, il mercato della serie a destra."""
        gs, team = self.gs, self.team
        larg = (self.left.w - 44) / 2
        for i in range(2):
            self.widgets.append(Button(
                (self.left.x + 16 + i * (larg + 12), self.left.y + 150, larg, 32),
                "LIBERA IL SEDILE", (lambda k=i: self.libera(k)), "ghost"))
        self.sel_btn = []
        c = self.right
        y = c.y + 44
        for d in FE.mercato(gs)[:9]:
            for i in range(2):
                b = Button((c.right - 16 - (2 - i) * 46, y, 42, 22),
                           f"M{i + 1}", (lambda dd=d, k=i: self.firma(dd, k)),
                           "normal", tip=f"Metti {d.short} sulla macchina {i + 1}")
                b.enabled = d.salary <= (FE.tetto(gs) - FE.spesa_nel_tetto(gs, team)
                                         + self._costo_sedile(i)) 
                self.widgets.append(b)
            y += 26
        self._build_corri()

    def _costo_sedile(self, i: int) -> float:
        """Quanto costa adesso chi occupa quel sedile: liberandolo, si recupera."""
        ids = list(getattr(self.team, "fe_piloti", []) or [])
        d = self.gs.drivers.get(ids[i] if i < len(ids) else "")
        return float(getattr(d, "salary", 0.0)) if d is not None else 0.0

    def firma(self, d, posto: int) -> None:
        self.app.toast(FE.ingaggia(self.gs, self.team, d, posto))
        self.shell.build()

    def libera(self, posto: int) -> None:
        self.app.toast(FE.libera(self.gs, self.team, posto))
        self.shell.build()

    def _sedili(self, surf, c) -> None:
        """Chi guida le nostre due macchine, e cosa costa al tetto."""
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LE NOSTRE DUE MACCHINE", (c.x + 16, c.y + 12), 14, T.TEXT,
               bold=True)
        T.paragraph(surf,
                    "Nel tetto della Formula E ci stanno dentro anche gli ingaggi: "
                    "un campione da due milioni sono ventitre ingegneri che non "
                    "assumi. Un ragazzo del vivaio invece non pesa, paga in "
                    "risultati - ma cresce.",
                    (c.x + 16, c.y + 36), 12, T.DIM, maxw=c.w - 32)
        ids = list(getattr(team, "fe_piloti", []) or [])
        larg = (c.w - 44) / 2
        for i in range(2):
            r = pygame.Rect(c.x + 16 + i * (larg + 12), c.y + 90, larg, 54)
            T.panel(surf, r, T.PANEL_2, radius=8, border=T.LINE)
            d = gs.drivers.get(ids[i] if i < len(ids) else "")
            T.text(surf, f"MACCHINA {i + 1}", (r.x + 12, r.y + 8), 11, T.DIM_2,
                   bold=True)
            if d is None:
                T.text(surf, "professionista ingaggiato", (r.x + 12, r.y + 26), 13,
                       T.DIM, maxw=r.w - 24)
                continue
            T.text(surf, d.name, (r.x + 12, r.y + 24), 14, T.TEXT, bold=True,
                   maxw=r.w - 24)
            casa = getattr(d, "seat", "") != "formulae"
            T.text(surf, f"{d.overall:.0f} di valore, {d.age} anni - "
                         + ("dal vivaio, non pesa sul tetto" if casa
                            else f"{d.salary:.2f} M$"),
                   (r.x + 12, r.y + 40), 11, T.OK if casa else T.WARN, maxw=r.w - 24)
        # il conto del tetto, che e' la ragione per cui questa scelta esiste
        y = c.y + 196
        nel = FE.spesa_nel_tetto(gs, team)
        t = FE.tetto(gs)
        T.text(surf, "Ingaggi", (c.x + 16, y), 12, T.DIM_2)
        T.text(surf, f"{FE.monte_ingaggi(gs, team):.2f} M$", (c.right - 16, y), 12,
               T.TEXT, mono=True, align="right")
        y += 20
        T.text(surf, "Tutto il resto sotto tetto", (c.x + 16, y), 12, T.DIM_2)
        T.text(surf, f"{nel - FE.monte_ingaggi(gs, team):.2f} M$",
               (c.right - 16, y), 12, T.TEXT, mono=True, align="right")
        y += 22
        T.text(surf, "Tetto della serie", (c.x + 16, y), 13, T.TEXT, bold=True)
        T.text(surf, f"{nel:.1f} di {t:.1f}", (c.right - 16, y), 13,
               T.OK if nel <= t else T.BAD, mono=True, align="right", bold=True)
        T.bar(surf, (c.x + 16, y + 24, c.w - 32, 8), min(nel, t * 1.2), t * 1.2,
              T.OK if nel <= t else T.BAD)
        y += 46
        T.text(surf, f"Con questi ingaggi puoi tenere al massimo "
                     f"{FE.ingegneri_massimi(gs, team)} ingegneri.",
               (c.x + 16, y), 12, T.ACCENT, maxw=c.w - 32)

    def _mercato(self, surf, c) -> None:
        """Chi c'e' sul mercato della serie."""
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "IL MERCATO DELLA SERIE", (c.x + 16, c.y + 12), 14, T.TEXT,
               bold=True)
        T.text(surf, "professionisti, non ragazzi: gente che dalla Formula 1 ci e' "
                     "passata o ci e' arrivata vicino",
               (c.x + 16, c.y + 30), 11, T.DIM_2, maxw=c.w - 32)
        y = c.y + 50
        for d in FE.mercato(gs)[:9]:
            T.text(surf, d.name, (c.x + 16, y), 13, T.TEXT, maxw=c.w - 220)
            T.text(surf, f"{d.age}", (c.right - 210, y + 1), 11, T.DIM_2)
            T.text(surf, f"{d.overall:.0f}", (c.right - 176, y), 12, T.DIM,
                   mono=True)
            T.text(surf, f"{d.salary:.2f}", (c.right - 116, y), 12, T.WARN,
                   mono=True)
            y += 26
        T.text(surf, "eta' - valore - milioni a stagione", (c.x + 16, c.bottom - 26),
               11, T.DIM_2)

    # -------------------------------------------------------------- il mondiale
    def _mondiale(self, surf, c) -> None:
        """La classifica: piloti a sinistra, costruttori sotto."""
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        st = FE.stato(gs, team)
        corse = int(st.get("round", 0))
        totali = len(st.get("calendario") or [])
        dal_muretto = sum(1 for x in st.get("storia", []) if x.get("corsa"))
        T.text(surf, "CLASSIFICA PILOTI", (c.x + 16, c.y + 12), 14, T.TEXT, bold=True)
        T.text(surf, f"{corse} gare su {totali}"
                     + (f", {dal_muretto} corse dal muretto" if dal_muretto else ""),
               (c.right - 16, c.y + 14), 12, T.DIM_2, align="right")
        righe = FE.classifica(gs, team)
        y = c.y + 38
        rh = min(21, (c.h - 130) / max(1, len(righe)))
        for i, (r, punti, vitt, podi) in enumerate(righe, 1):
            mio = r["squadra"] == team.fe_nome
            if mio:
                T.panel(surf, (c.x + 8, y - 1, c.w - 16, rh - 1), T.PANEL_3, radius=4)
            col = T.TEXT if mio else T.DIM
            T.text(surf, str(i), (c.x + 34, y), 12, T.GOLD if i <= 3 else T.DIM_2,
                   align="right")
            T.text(surf, r["nome"], (c.x + 44, y), 12, col, bold=mio, maxw=150)
            T.text(surf, r["squadra"], (c.x + 200, y + 1), 11, T.DIM_2, maxw=120)
            if vitt:
                T.text(surf, f"{vitt}v", (c.right - 74, y), 11, T.GOLD, mono=True,
                       align="right")
            T.text(surf, f"{punti:.0f}", (c.right - 16, y), 12, col, mono=True,
                   align="right", bold=mio)
            y += rh
        # e i costruttori, che sono quelli che pagano
        y = c.bottom - 96
        T.text(surf, "COSTRUTTORI", (c.x + 16, y), 12, T.DIM_2, bold=True)
        y += 20
        for i, (nome, v) in enumerate(FE.classifica_squadre(gs, team)[:4], 1):
            mio = nome == team.fe_nome
            T.text(surf, f"{i}. {nome}", (c.x + 16, y), 12,
                   T.TEXT if mio else T.DIM, bold=mio, maxw=c.w - 90)
            T.text(surf, f"{v['punti']:.0f}", (c.right - 16, y), 12,
                   T.TEXT if mio else T.DIM, mono=True, align="right")
            y += 18

    def _calendario(self, surf, c) -> None:
        """Il calendario: dove si e' corso, dove si corre, e chi ha vinto."""
        gs, team = self.gs, self.team
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CALENDARIO", (c.x + 16, c.y + 12), 14, T.TEXT, bold=True)
        st = FE.stato(gs, team)
        cal = st.get("calendario") or []
        formati = st.get("formati") or []
        storia = {x["round"]: x for x in st.get("storia", [])}
        campo = {x["id"]: x for x in st.get("campo") or []}
        piste = {t.id: t for t in getattr(gs, "fe_tracks", []) or []}
        y = c.y + 38
        rh = min(20, (c.h - 60) / max(1, len(cal)))
        for i, tid in enumerate(cal, 1):
            t = piste.get(tid)
            fatta = storia.get(i)
            nome = (t.gp.replace("E-Prix di ", "") if t is not None else tid)
            corta = (formati[i - 1] if i - 1 < len(formati) else "eprix") == "unleashed"
            col = T.DIM if fatta else (60, 70, 88)
            T.text(surf, str(i), (c.x + 30, y), 11, T.DIM_2, align="right")
            T.text(surf, nome, (c.x + 40, y), 12, col, maxw=130)
            if corta:
                T.text(surf, "SPRINT", (c.x + 178, y + 1), 10, T.ACCENT
                       if fatta else (60, 70, 88), bold=True)
            if fatta:
                primo = campo.get((fatta.get("ordine") or [""])[0], {})
                mio = primo.get("squadra") == team.fe_nome
                T.text(surf, primo.get("nome", ""), (c.right - 16, y), 12,
                       T.GOLD if mio else T.DIM, align="right", maxw=c.w - 250,
                       bold=mio)
                if fatta.get("corsa"):
                    T.text(surf, "*", (c.x + 24, y), 12, T.ACCENT)
            y += rh
        T.text(surf, "* corsa dal muretto", (c.x + 16, c.bottom - 26), 11, T.DIM_2)

    # ------------------------------------------------------------ il regolamento
    def _regolamento(self, surf, c) -> None:
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        reg, tec = FE.corrente(), FE.tecnico()
        T.text(surf, "IL REGOLAMENTO", (c.x + 16, c.y + 12), 15, T.TEXT, bold=True)
        y = c.y + 40
        for eti, val in (
                ("Potenza in gara", f"{tec.get('potenza_gara_kw')} kW"),
                ("Attack Mode", f"{tec.get('potenza_attack_kw')} kW"),
                ("Recupero in frenata", f"{tec.get('recupero_max_kw')} kW"),
                ("Batteria", f"{tec.get('batteria_kwh')} kWh"),
                ("Peso minimo", f"{tec.get('peso_min_kg')} kg con pilota"),
                ("Trazione", tec.get("trazione", "")),
                ("Gomme", f"{(tec.get('gomme') or {}).get('fornitore','')} "
                          f"{(tec.get('gomme') or {}).get('asciutto','')}")):
            T.text(surf, eti, (c.x + 16, y), 12, T.DIM_2)
            T.text(surf, str(val), (c.right - 16, y), 12, T.TEXT, align="right")
            y += 19
        y += 8
        for chiave in ("eprix", "unleashed"):
            f = (reg.get("formati") or {}).get(chiave, {})
            if not f:
                continue
            boost = "con Pit Boost" if f.get("pit_boost") else "senza sosta"
            T.text(surf, f.get("nome", chiave), (c.x + 16, y), 13, T.ACCENT, bold=True)
            T.text(surf, f"{f.get('durata_min')} min + 1 giro, {boost}",
                   (c.right - 16, y), 12, T.TEXT, align="right")
            y += 19
        y += 8
        am = reg.get("attack_mode") or {}
        pb = reg.get("pit_boost") or {}
        en = reg.get("energia") or {}
        T.text(surf, "ATTACK MODE", (c.x + 16, y), 12, T.GOLD, bold=True)
        y += 17
        T.paragraph(surf,
                    f"{am.get('potenza_kw')} kW per {am.get('minuti_totali')} minuti in "
                    f"tutto, in {'-'.join(str(x) for x in am.get('attivazioni', []))} "
                    f"attivazioni decise dalla FIA un'ora prima. Si prende passando "
                    f"fuori traiettoria: costa tempo subito per averne dopo. Vietato nei "
                    f"primi {am.get('vietato_primi_giri')} giri e sotto neutralizzazione.",
                    (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
        y += 74
        T.text(surf, "PIT BOOST", (c.x + 16, y), 12, T.GOLD, bold=True)
        y += 17
        T.paragraph(surf,
                    f"Ricarica rapida obbligatoria nell'E-Prix: {pb.get('energia_kwh')} kWh "
                    f"a {pb.get('potenza_ricarica_kw')} kW in {pb.get('durata_s')} secondi "
                    f"fermi, e solo con la batteria fra il "
                    f"{pb.get('carica_min', 0) * 100:.0f}% e il "
                    f"{pb.get('carica_max', 0) * 100:.0f}%. Non e' una sosta che si "
                    f"sceglie quando si vuole: e' una finestra, e ci si arriva gestendo.",
                    (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
        y += 74
        T.text(surf, "NEUTRALIZZAZIONI", (c.x + 16, y), 12, T.GOLD, bold=True)
        y += 17
        T.paragraph(surf,
                    f"Sotto safety car si toglie a tutti "
                    f"{en.get('penale_neutralizzazione_kwh_min')} kWh al minuto. E' il "
                    f"contrario della Formula 1: li' la neutralizzazione regala tempo, "
                    f"qui toglie energia.",
                    (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
        y += 56
        q = reg.get("qualifica") or {}
        T.text(surf, "QUALIFICA", (c.x + 16, y), 12, T.GOLD, bold=True)
        y += 17
        T.paragraph(surf,
                    f"{q.get('gruppi')} gruppi, i primi {q.get('passano_per_gruppo')} di "
                    f"ognuno passano ai duelli a eliminazione diretta. Dal 2026/27 "
                    f"arrivare ai duelli da' punti iridati.",
                    (c.x + 16, y), 12, T.DIM, maxw=c.w - 32)
