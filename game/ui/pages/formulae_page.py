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
from ..widgets import Button, Slider, Toggle, card


class FormulaEPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.tab = 0

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
        self.widgets.append(Button((self.left.x + 16, self.left.bottom - 58,
                                    self.left.w - 32, 40),
                                   "Chiudi il programma", self.chiudi, "danger"))

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
        if FE.ha(self.team):
            self._programma(surf)
        else:
            self._invito(surf)
        self._regolamento(surf, self.right)
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
