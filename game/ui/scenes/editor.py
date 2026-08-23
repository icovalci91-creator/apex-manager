"""Editor di gioco: si entra dentro la partita e si cambia quello che si vuole.

Non c'e' un elenco di cose modificabili scelto da qualcuno. C'e' un percorso:
si parte dalle radici - squadre, piloti, circuiti, regolamento, costanti di
taratura - si scende dentro finche' non si arriva a un valore, e quel valore si
riscrive. Se una cosa esiste nella partita, di qui ci si arriva.
"""
from __future__ import annotations

import pygame

from ... import editor as E
from .. import theme as T
from ..app import Scene
from ..widgets import Button, ScrollList, TextInput, Toggle

RIGA_H = 30


class EditorScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.gs = app.gs
        self.radici = E.radici(self.gs)
        # il percorso: (etichetta, oggetto, chiave nel genitore, genitore).
        # Chiave e genitore servono per le tuple, che non si scrivono sul posto
        self.percorso = [("Editor", dict(self.radici), None, None)]
        self.sel = None            # (chiave, etichetta, valore) selezionato
        self.filtro = ""
        self.storia: list = []     # cosa e' stato cambiato, per poterlo dire
        self.campo = None
        self.build()

    # ------------------------------------------------------------ costruzione
    @property
    def corrente(self):
        return self.percorso[-1][1]

    @property
    def catena(self) -> list:
        """(oggetto, chiave nel genitore) dalla radice fino a qui."""
        return [(p[1], p[2]) for p in self.percorso]

    def voci(self) -> list:
        voci = E.entries(self.corrente)
        if self.filtro:
            f = self.filtro.lower()
            voci = [v for v in voci if f in str(v[1]).lower()]
        return voci

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        self.cerca = TextInput((w - 620, 22, 240, 34), self.filtro,
                               on_commit=self.set_filtro, placeholder="cerca in questo livello")
        self.widgets.append(self.cerca)
        self.widgets.append(Button((w - 366, 22, 120, 34), "Filtra",
                                   lambda: self.set_filtro(self.cerca.value), "normal"))
        self.widgets.append(Button((w - 238, 22, 100, 34), "Indietro", self.indietro, "ghost"))
        self.widgets.append(Button((w - 130, 22, 100, 34), "Chiudi", self.chiudi, "primary"))

        lista = pygame.Rect(24, 118, int(w * 0.56), h - 150)
        self.lista = ScrollList(lista, row_h=RIGA_H, draw_row=self._riga,
                                on_select=self._scegli)
        self.lista.items = self.voci()
        self.widgets.append(self.lista)

        # pannello di modifica
        px = lista.right + 20
        pw = w - px - 24
        if self.sel is not None:
            chiave, etichetta, valore = self.sel
            if chiave is None:
                pass                                  # calcolato: sola lettura
            elif isinstance(valore, bool):
                self.widgets.append(Toggle((px + 16, 210, pw - 32, 34), etichetta,
                                           valore, self.scrivi_bool))
            elif E.is_scalar(valore):
                self.campo = TextInput((px + 16, 210, pw - 32, 40),
                                       "" if valore is None else str(valore),
                                       on_commit=self.scrivi_testo)
                self.widgets.append(self.campo)
                self.widgets.append(Button((px + 16, 258, (pw - 44) / 2, 38), "Applica",
                                           lambda: self.scrivi_testo(self.campo.value),
                                           "primary"))
                self.widgets.append(Button((px + 28 + (pw - 44) / 2, 258, (pw - 44) / 2, 38),
                                           "Annulla", self.deseleziona, "ghost"))
                if isinstance(valore, (int, float)):
                    x = px + 16
                    larg = (pw - 32 - 3 * 8) / 4
                    for lab, f in (("-10%", 0.9), ("-1", None), ("+1", None), ("+10%", 1.1)):
                        b = Button((x, 306, larg, 34), lab, style="normal")
                        b.on_click = (lambda l=lab, ff=f: self.passo(l, ff))
                        self.widgets.append(b)
                        x += larg + 8
            else:
                self.widgets.append(Button((px + 16, 210, pw - 32, 40), "Entra qui dentro",
                                           lambda: self.entra(self.sel), "primary"))
        # scorciatoie utili in fondo
        self.widgets.append(Button((px + 16, h - 116, pw - 32, 34),
                                   "Torna alle radici", self.alle_radici, "ghost"))

    def on_resize(self) -> None:
        self.build()

    def _riga(self, surf, rect, i, item) -> None:
        chiave, etichetta, valore = item
        scelto = self.sel is not None and self.sel[1] == etichetta
        if scelto:
            T.panel(surf, (rect.x + 2, rect.y + 1, rect.w - 4, rect.h - 2), T.PANEL_3, radius=5)
        col = T.DIM_2 if chiave is None else T.TEXT
        T.text(surf, str(etichetta), (rect.x + 12, rect.centery - 9), 14, col,
               maxw=rect.w * 0.55)
        cont = E.is_container(valore)
        T.text(surf, E.descrivi(valore), (rect.right - 34, rect.centery - 9), 14,
               T.GOLD if cont else T.ACCENT, align="right", maxw=rect.w * 0.4)
        if cont:
            T.text(surf, ">", (rect.right - 14, rect.centery - 9), 14, T.DIM)

    def _scegli(self, i, item) -> None:
        chiave, etichetta, valore = item
        if E.is_container(valore):
            self.entra(item)
            return
        self.sel = item
        self.build()

    # ------------------------------------------------------------------ azioni
    def entra(self, item) -> None:
        chiave, etichetta, valore = item
        if not E.is_container(valore):
            return
        self.percorso.append((str(etichetta), valore, chiave, self.corrente))
        self.sel = None
        self.filtro = ""
        self.build()

    def indietro(self) -> None:
        if len(self.percorso) > 1:
            self.percorso.pop()
            self.sel = None
            self.filtro = ""
            self.build()
        else:
            self.chiudi()

    def alle_radici(self) -> None:
        self.percorso = self.percorso[:1]
        self.sel = None
        self.filtro = ""
        self.build()

    def set_filtro(self, testo: str) -> None:
        self.filtro = (testo or "").strip()
        self.build()

    def deseleziona(self) -> None:
        self.sel = None
        self.build()

    def passo(self, lab: str, fattore) -> None:
        """I pulsanti rapidi: piu' uno, meno uno, un dieci per cento in su o in giu'."""
        if self.sel is None:
            return
        chiave, etichetta, valore = self.sel
        if not isinstance(valore, (int, float)) or isinstance(valore, bool):
            return
        if fattore is None:
            nuovo = valore + (1 if lab == "+1" else -1)
        else:
            nuovo = valore * fattore
        if isinstance(valore, int):
            nuovo = int(round(nuovo))
        self._applica(chiave, etichetta, nuovo)

    def scrivi_bool(self, valore: bool) -> None:
        if self.sel is None:
            return
        chiave, etichetta, _v = self.sel
        self._applica(chiave, etichetta, bool(valore))

    def scrivi_testo(self, testo: str) -> None:
        if self.sel is None:
            return
        chiave, etichetta, valore = self.sel
        try:
            nuovo = E.converti(valore, testo)
        except ValueError:
            self.app.toast(f"'{testo}' non e' un valore valido per {etichetta}.")
            return
        self._applica(chiave, etichetta, nuovo)

    def _applica(self, chiave, etichetta, nuovo) -> None:
        vecchio = E.leggi(self.corrente, chiave)
        try:
            E.scrivi_annidato(self.catena, chiave, nuovo)
            if isinstance(self.corrente, tuple):
                # la tupla e' stata ricostruita: il percorso deve puntare a quella nuova
                p = self.percorso[-1]
                nuova = self.corrente[:chiave] + (nuovo,) + self.corrente[chiave + 1:]
                self.percorso[-1] = (p[0], nuova, p[2], p[3])
        except Exception as exc:
            self.app.toast(f"Non si puo' scrivere {etichetta}: {exc}")
            return
        dove = " / ".join(p[0] for p in self.percorso[1:]) or "radice"
        self.storia.append(f"{dove} / {etichetta}: {E.descrivi(vecchio)} -> {E.descrivi(nuovo)}")
        self.gs.editor_used = True
        self.app.toast(f"{etichetta}: {E.descrivi(vecchio)} -> {E.descrivi(nuovo)}")
        self.sel = (chiave, etichetta, nuovo)
        self.build()

    def chiudi(self) -> None:
        self.app.pop()
        from .shell import GameShell
        if isinstance(self.app.scene, GameShell):
            self.app.scene.enter()

    # -------------------------------------------------------------------- loop
    def handle(self, ev) -> None:
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            fuoco = any(isinstance(w, TextInput) and w.focused for w in self.widgets)
            if not fuoco:
                self.indietro()
                return
        super().handle(ev)

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        pygame.draw.rect(surf, T.BG, (0, 0, w, h))
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 76))
        T.text(surf, "EDITOR DI GIOCO", (24, 18), 26, T.TEXT, bold=True)
        T.text(surf, "qualunque valore della partita, senza distinzione",
               (24, 48), 13, T.DIM)

        # il percorso, cliccabile all'indietro con il tasto Indietro
        briciole = " / ".join(p[0] for p in self.percorso)
        T.text(surf, briciole, (24, 88), 14, T.GOLD, bold=True, maxw=w - 300)
        voci = self.voci()
        T.text(surf, f"{len(voci)} voci", (w - 24, 88), 13, T.DIM, align="right")

        lista = pygame.Rect(24, 118, int(w * 0.56), h - 150)
        T.panel(surf, lista, T.PANEL, radius=8, border=T.LINE)

        px = lista.right + 20
        pw = w - px - 24
        pannello = pygame.Rect(px, 118, pw, h - 150)
        T.panel(surf, pannello, T.PANEL, radius=8, border=T.LINE)
        if self.sel is None:
            T.text(surf, "Scegli una voce a sinistra.", (px + 16, 140), 15, T.DIM)
            T.text(surf, "Le voci con la freccia contengono altre cose: cliccale per "
                         "scendere. Le altre sono valori e si riscrivono qui.",
                   (px + 16, 166), 13, T.DIM_2, maxw=pw - 32)
        else:
            chiave, etichetta, valore = self.sel
            T.text(surf, str(etichetta), (px + 16, 140), 20, T.TEXT, bold=True, maxw=pw - 32)
            tipo = type(valore).__name__ if valore is not None else "vuoto"
            T.text(surf, f"valore attuale: {E.descrivi(valore)}   ({tipo})",
                   (px + 16, 172), 13, T.DIM, maxw=pw - 32)
            if chiave is None:
                T.text(surf, "E' un valore calcolato dal gioco a partire da altri: si "
                             "guarda, non si scrive. Cambia quelli da cui dipende.",
                       (px + 16, 210), 13, T.WARN, maxw=pw - 32)

        # cosa e' stato cambiato in questa sessione
        y = h - 96 - min(4, len(self.storia)) * 18
        if self.storia:
            T.text(surf, "MODIFICHE DI QUESTA SESSIONE", (px + 16, y - 22), 11,
                   T.DIM_2, bold=True)
            for riga in self.storia[-4:]:
                T.text(surf, riga, (px + 16, y), 12, T.OK, maxw=pw - 32)
                y += 18
        super().draw(surf)
