"""Pagina Test privati: dove girare, con chi, e per ottenere cosa."""
from __future__ import annotations

import pygame

from ...core import testing as TT
from .. import theme as T
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, card


# Le due note in fondo al pannello: servono a scriverle e, prima, a misurarle.
NOTA_COLLETTIVE = ("Si gira con la macchina di quest'anno, l'unica volta in "
                   "tutto l'anno: e' li' che si capisce com'e' fatta. Non "
                   "tolgono giornate di test privati.")
NOTA_REGOLE = ("Il regolamento vieta di provare con la vettura dell'anno: "
               "si gira con monoposto di due stagioni fa. Serve ai piloti e "
               "alla correlazione, non a rendere piu' veloce la macchina di "
               "adesso.")


class TestingPage(Page):
    def __init__(self, shell):
        super().__init__(shell)
        self.track = None
        self.driver = None
        self.programme = "giovani"
        self.days = 2

    # ------------------------------------------------------------ costruzione
    def _pannelli(self) -> tuple:
        """I due pannelli, alti quanto la finestra o quanto serve a destra."""
        r = self.rect
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.42, r.h - 96)
        right = pygame.Rect(r.x + r.w * 0.44, r.y + 96, r.w * 0.56 - 4, r.h - 96)
        self.q = self._quote(right.w - 32)
        left.h = right.h = max(right.h, self.q["alto"])
        return left, right

    def _quote(self, larga: int) -> dict:
        """Dove cade ogni blocco del pannello di destra, dal suo bordo alto.

        Erano quote fisse, e ognuna dava per scontato quanto fosse alto il
        blocco sopra: la descrizione del programma andava a due righe e CHI
        MANDIAMO finiva dentro la lista dei piloti; il motivo per cui non si
        puo' girare si scriveva sopra il nome del circuito; e su una finestra
        bassa tutto usciva dal pannello. Qui ogni blocco parte da dove finisce
        quello sopra, e la stessa misura serve ai comandi e alle scritte.
        """
        q = {}
        # la descrizione cambia col programma senza rifare la pagina: si tiene
        # il posto della piu' lunga, cosi' sotto non si muove niente
        righe = max(len(T.wrap(m["desc"], 13, larga)) for m in TT.PROGRAMMI.values())
        y = 106 + righe * T.line_h(13) + 8
        q["chi"] = y
        y += 22
        q["piloti"] = y
        y += 122 + 16
        q["giornate"] = y
        y += 36
        q["manda"] = y
        y += 40 + 16
        q["conto"] = y
        # il conto, le sue tre voci, "e' casa nostra" e il motivo per cui non
        # si puo' girare hanno ognuno la sua riga, anche quando sono vuote:
        # cambiano scegliendo la pista, e la pagina non si rifa' per questo
        y += 20 + 18 + 18
        q["perche"] = y
        y += T.line_h(13) + 8
        q["mappa"] = y
        y += 150 + 10
        q["dopo"] = y
        if self.gs.phase == "preseason":
            blocco = 20
            for ses in TT.preseason_sessions(self.gs):
                blocco += len(T.wrap(f"{ses['track'].name}: {ses['days']} giorni, "
                                     f"00.00 M$  gia' fatte", 12, larga)) * T.line_h(12)
            blocco += 6 + 44 + len(T.wrap(NOTA_COLLETTIVE, 12, larga)) * T.line_h(12)
        else:
            blocco = len(T.wrap(NOTA_REGOLE, 12, larga)) * T.line_h(12)
        q["blocco"] = blocco
        q["alto"] = y + blocco + 14
        return q

    def build(self) -> None:
        self.widgets = []
        left, right = self._pannelli()
        q = self.q
        self.piste = ScrollList((left.x + 12, left.y + 40, left.w - 24, left.h - 56),
                                row_h=34, draw_row=self._row_track, on_select=self._pick_track)
        self.widgets.append(self.piste)

        self.prog_buttons = []
        bw = (right.w - 44) / 2
        for i, (key, meta) in enumerate(TT.PROGRAMMI.items()):
            b = Button((right.x + 16 + (i % 2) * (bw + 8),
                        right.y + 34 + (i // 2) * 36, bw, 30), meta["label"])
            b.on_click = (lambda k=key: self._pick_prog(k))
            self.prog_buttons.append(b)
            self.widgets.append(b)
        self._mark_prog()

        self.piloti = ScrollList((right.x + 16, right.y + q["piloti"], right.w - 32, 122),
                                 row_h=30, draw_row=self._row_driver, on_select=self._pick_driver)
        self.widgets.append(self.piloti)

        self.s_days = Slider((right.x + 16, right.y + q["giornate"], right.w - 32, 28),
                             "Giornate", self.days, 1,
                             max(1, TT.days_left(self.gs, self.team)),
                             on_change=self._set_days, fmt="{:.0f}")
        self.widgets.append(self.s_days)
        self.widgets.append(Button((right.x + 16, right.y + q["manda"], 250, 40),
                                   "Manda la squadra in pista", self.run, "primary"))

        # prove collettive: ci sono solo prima che cominci il campionato
        self.pre_buttons = []
        if self.gs.phase == "preseason":
            y = right.bottom - 150
            for i, ses in enumerate(TT.preseason_sessions(self.gs)):
                fatta = TT.preseason_done(self.team, i)
                b = Button((right.x + 16 + i * ((right.w - 44) / 2 + 12), y,
                            (right.w - 44) / 2, 36),
                           ("Fatto: " if fatta else "Vai a ") + ses["track"].name,
                           style="ghost" if fatta else "primary")
                b.on_click = (lambda k=i: self.run_preseason(k))
                b.enabled = not fatta
                self.pre_buttons.append((b, ses, fatta))
                self.widgets.append(b)
        self._fill()

    def run_preseason(self, idx: int) -> None:
        ok, msg = TT.run_preseason(self.gs, self.team, idx, self.programme)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _mark_prog(self) -> None:
        """L'attivo si stacca dagli altri: sul pannello scuro il tab spento sparisce."""
        for b, key in zip(self.prog_buttons, TT.PROGRAMMI):
            b.active = (key == self.programme)
            b.style = "tab" if b.active else "normal"

    def _fill(self) -> None:
        gs = self.gs
        piste = sorted(TT.venues(gs, self.team), key=lambda t: t.name)
        self.piste.items = piste
        if piste and self.track not in piste:
            self.track = piste[0]
        if self.track in piste:
            self.piste.selected = piste.index(self.track)
        # in pista ci si porta la propria gente: titolari, terzo pilota e
        # ragazzi del vivaio. Un pilota di un'altra squadra non sale sulla
        # nostra macchina
        self.piloti.items = (gs.drivers_of(self.team.id) + gs.reserves_of(self.team.id)
                             + [gs.drivers[d] for d in self.team.academy
                                if d in gs.drivers])
        if self.piloti.items and self.driver not in self.piloti.items:
            # per difetto proponiamo chi ha ancora margine: i chilometri servono a lui
            self.driver = max(self.piloti.items, key=lambda d: d.potential - d.overall)
        if self.driver in self.piloti.items:
            self.piloti.selected = self.piloti.items.index(self.driver)

    # ------------------------------------------------------------------ azioni
    def _pick_track(self, i, t) -> None:
        self.track = t

    def _pick_driver(self, i, d) -> None:
        self.driver = d

    def _pick_prog(self, k) -> None:
        self.programme = k
        self._mark_prog()

    def _set_days(self, v) -> None:
        self.days = int(round(v))

    def run(self) -> None:
        if not self.track:
            return
        ok, msg = TT.run(self.gs, self.team, self.track, self.driver,
                         self.programme, self.days)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def refresh(self) -> None:
        self.build()

    # -------------------------------------------------------------- righe
    def _row_track(self, surf, rect, i, t) -> None:
        gs = self.gs
        in_cal = t in gs.tracks
        T.text(surf, t.name, (rect.x + 14, rect.y + 8), 14, T.TEXT, maxw=250)
        T.text(surf, t.flag, (rect.x + 278, rect.y + 9), 12, T.DIM)
        sapere = TT.setup_bonus(self.team, t)
        if sapere > 0.01:
            T.bar(surf, (rect.x + 310, rect.y + 13, 60, 7), sapere * 100, 100, T.OK)
        prezzo = TT.cost_of(gs, self.team, t, self.programme, self.days)
        T.text(surf, f"{prezzo:.1f} M$", (rect.right - 14, rect.y + 8), 13,
               T.GOLD, align="right")
        if not in_cal:
            T.text(surf, "fuori calendario", (rect.x + 14, rect.y + 22), 10, T.DIM_2)

    def _row_driver(self, surf, rect, i, d) -> None:
        proprio = True
        T.text(surf, d.name, (rect.x + 12, rect.y + 6), 14,
               T.TEXT if proprio else T.DIM, maxw=200)
        T.text(surf, f"{d.age}a", (rect.x + 220, rect.y + 7), 12, T.DIM)
        margine = max(0.0, d.potential - d.overall)
        col = T.OK if margine > 6 else (T.WARN if margine > 2 else T.DIM_2)
        T.text(surf, f"margine {margine:.0f}", (rect.right - 14, rect.y + 6), 12,
               col, align="right")
        etichetta = {"riserva": "terzo pilota", "academy": "vivaio"}.get(d.seat, "")
        if etichetta:
            T.text(surf, etichetta, (rect.x + 250, rect.y + 7), 11, T.GOLD)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        cw = (r.w - 32) / 3
        restano = TT.days_left(gs, team)
        card(surf, (r.x, r.y, cw, 86), "Giornate di test",
             f"{restano} su {TT.days_allowed(gs, team)}",
             (f"due in piu': abbiamo {team.private_track_name}"
              if team.has_private_track else "il regolamento non ne concede altre"),
             colour=T.OK if restano > 2 else T.WARN, accent=T.ACCENT)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Correlazione",
             f"{team.correlation*100:.0f}%",
             "quanto la galleria dice il vero", accent=T.GOLD,
             colour=T.OK if team.correlation > 0.2 else T.TEXT)
        note = len([k for k, v in (team.setup_knowledge or {}).items() if v > 0.05])
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Circuiti studiati",
             str(note), "assetto gia' nella finestra giusta", accent=T.OK)

        left, right = self._pannelli()
        q = self.q
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "DOVE GIRARE", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, "costo per la sessione scelta", (left.right - 16, left.y + 12), 11,
               T.DIM_2, align="right")

        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROGRAMMA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        meta = TT.PROGRAMMI[self.programme]
        T.paragraph(surf, meta["desc"], (right.x + 16, right.y + 106), 13, T.DIM,
                    right.w - 32)
        T.text(surf, "CHI MANDIAMO", (right.x + 16, right.y + q["chi"]), 12, T.DIM_2,
               bold=True)
        if self.programme != "giovani":
            T.text(surf, "(per questo programma il pilota conta poco)",
                   (right.x + 150, right.y + q["chi"]), 11, T.DIM_2,
                   maxw=right.w - 176)

        if self.track:
            voci = TT.cost_breakdown(gs, team, self.track, self.programme, self.days)
            prezzo = sum(voci.values())
            ok, why = TT.can_run(gs, team, self.track, self.programme, self.days)
            casa = TT.is_home(team, self.track)
            y = right.y + q["conto"]
            T.text(surf, f"{self.days} giornate a {self.track.name}: {prezzo:.2f} M$ "
                         f"dentro il tetto di spesa",
                   (right.x + 16, y), 14, T.TEXT, maxw=right.w - 32)
            # le tre voci separate: i materiali sono uguali dappertutto, il
            # resto lo si paga solo andando a casa d'altri
            x = right.x + 16
            for chiave, etichetta in (("materiali", "materiali"), ("noleggio", "noleggio pista"),
                                      ("trasferta", "trasferta")):
                v = voci[chiave]
                col = T.DIM_2 if v <= 0.001 else (T.TEXT if chiave == "materiali" else T.WARN)
                T.text(surf, f"{etichetta} {v:.2f}", (x, y + 20), 12, col)
                x += 150
            if casa:
                T.text(surf, "e' casa nostra: si paga solo quello che si consuma",
                       (right.x + 16, y + 38), 12, T.OK, maxw=right.w - 32)
            if not ok:
                T.text(surf, why, (right.x + 16, right.y + q["perche"]), 13, T.BAD,
                       maxw=right.w - 32)
            y = right.y + q["mappa"]
            trackdraw.draw_minimap(surf, self.track,
                                   (right.x + 16, y, 210, 150),
                                   colour=(58, 70, 92), width=3)
            T.text(surf, self.track.name, (right.x + 244, y + 8), 16, T.TEXT,
                   bold=True, maxw=right.w - 268)
            T.text(surf, f"{self.track.length_km:.3f} km - {self.track.country}",
                   (right.x + 244, y + 30), 13, T.DIM)
            sapere = TT.setup_bonus(team, self.track)
            T.text(surf, f"conoscenza accumulata {sapere*100:.0f}%",
                   (right.x + 244, y + 52), 13,
                   T.OK if sapere > 0.3 else T.DIM)
            if self.track not in gs.tracks:
                T.text(surf, "fuori dal calendario: si gira e basta",
                       (right.x + 244, y + 74), 12, T.DIM_2)

        # le prove collettive vengono dopo la scheda del circuito, non a una
        # distanza fissa dal fondo: su una finestra bassa ci finivano sopra.
        # Su una finestra alta scendono in fondo, alte quanto sono davvero
        py = max(right.y + (q["dopo"] if self.track else q["conto"]),
                 right.bottom - 14 - q["blocco"])
        if gs.phase == "preseason" and getattr(self, "pre_buttons", None):
            T.text(surf, "PROVE COLLETTIVE DI INIZIO STAGIONE", (right.x + 16, py),
                   12, T.GOLD, bold=True)
            yy = py + 20
            for _b, ses, fatta in self.pre_buttons:
                prezzo = TT.preseason_cost(gs, team, ses)
                riga = (f"{ses['track'].name}: {ses['days']} giorni, {prezzo:.2f} M$"
                        + ("  gia' fatte" if fatta else ""))
                yy += T.paragraph(surf, riga, (right.x + 16, yy), 12, T.DIM,
                                  right.w - 32)
            yy += 6
            for b, _ses, _f in self.pre_buttons:
                b.rect.y = int(yy)
            yy += 44
            T.paragraph(surf, NOTA_COLLETTIVE, (right.x + 16, yy), 12, T.DIM_2,
                        right.w - 32)
        else:
            T.paragraph(surf, NOTA_REGOLE, (right.x + 16, py), 12, T.DIM_2,
                        right.w - 32)
        super().draw(surf)
