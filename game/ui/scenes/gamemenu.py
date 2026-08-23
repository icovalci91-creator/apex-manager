"""Il menu che si apre dal tasto Menu, senza uscire dalla partita.

Prima quel tasto buttava fuori dalla carriera e riportava alla schermata di
avvio: una partita non salvata spariva senza chiedere niente. Adesso apre un
menu vero, sopra al gioco, da cui si comincia una partita nuova, si salva, si
carica e si accende l'editor.
"""
from __future__ import annotations

import pygame

from ... import storage
from ...core.state import GameState
from .. import theme as T
from ..app import Scene
from ..widgets import Button, ScrollList, TextInput, Toggle


class GameMenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.gs = app.gs
        self.modo = "principale"        # principale | salva | carica | nuova
        self.saves = _elenco()
        self.scelto = self.saves[0] if self.saves else ""
        self.nome = TextInput((0, 0, 10, 10), self._nome_predefinito(),
                              on_commit=lambda _v: self.salva())
        self.build()

    def _nome_predefinito(self) -> str:
        gs = self.gs
        return f"{gs.player_team}_{gs.season}"

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        cx = w // 2
        y = 200
        if self.modo == "principale":
            voci = [
                ("Riprendi la partita", self.chiudi, "primary"),
                ("Nuova partita", lambda: self.vai("nuova"), "normal"),
                ("Salva partita", lambda: self.vai("salva"), "normal"),
                ("Carica partita", lambda: self.vai("carica"), "normal"),
            ]
            for lab, azione, stile in voci:
                self.widgets.append(Button((cx - 200, y, 400, 48), lab, azione, stile))
                y += 58
            y += 10
            self.widgets.append(Toggle((cx - 200, y, 400, 34), "Editor di gioco",
                                       bool(getattr(self.app, "editor", False)),
                                       self.set_editor))
            y += 44
            b = Button((cx - 200, y, 400, 44), "Apri l'editor", self.apri_editor,
                       "normal" if getattr(self.app, "editor", False) else "ghost")
            b.enabled = bool(getattr(self.app, "editor", False))
            self.widgets.append(b)
            y += 62
            self.widgets.append(Button((cx - 200, y, 400, 40), "Torna alla schermata iniziale",
                                       self.al_menu_iniziale, "ghost"))
        elif self.modo == "salva":
            self.nome.rect = pygame.Rect(cx - 200, 210, 400, 44)
            self.widgets.append(self.nome)
            self.widgets.append(Button((cx - 200, 264, 195, 44), "Salva", self.salva, "primary"))
            self.widgets.append(Button((cx + 5, 264, 195, 44), "Indietro",
                                       lambda: self.vai("principale"), "ghost"))
            self._lista(cx, 330, h, self.scegli_nome)
        elif self.modo == "carica":
            self._lista(cx, 210, h, self.scegli_nome)
            b = Button((cx - 200, h - 150, 195, 44), "Carica", self.carica, "primary")
            b.enabled = bool(self.scelto)
            self.widgets.append(b)
            self.widgets.append(Button((cx + 5, h - 150, 195, 44), "Indietro",
                                       lambda: self.vai("principale"), "ghost"))
        else:   # nuova
            self.widgets.append(Button((cx - 200, 300, 400, 48),
                                       "Si, comincia una partita nuova",
                                       self.nuova, "danger"))
            self.widgets.append(Button((cx - 200, 360, 400, 44), "No, torno indietro",
                                       lambda: self.vai("principale"), "ghost"))

    def _lista(self, cx, y, h, on_select) -> None:
        self.lista = ScrollList((cx - 200, y, 400, max(120, h - y - 170)), row_h=34,
                                draw_row=self._riga, on_select=on_select)
        self.lista.items = list(self.saves)
        self.widgets.append(self.lista)

    def _riga(self, surf, rect, i, item) -> None:
        col = T.TEXT if item == self.scelto else T.DIM
        T.text(surf, str(item), (rect.x + 12, rect.centery - 9), 15, col,
               bold=item == self.scelto, maxw=rect.w - 24)

    def on_resize(self) -> None:
        self.build()

    # ------------------------------------------------------------------ azioni
    def vai(self, modo: str) -> None:
        self.modo = modo
        self.saves = _elenco()
        self.build()

    def scegli_nome(self, i, item) -> None:
        self.scelto = item
        if self.modo == "salva":
            self.nome.value = str(item)
        self.build()

    def set_editor(self, valore: bool) -> None:
        self.app.editor = bool(valore)
        self.app.toast("Editor attivo: lo trovi nel menu e nella barra laterale."
                       if valore else "Editor disattivato.")
        self.build()

    def apri_editor(self) -> None:
        if not getattr(self.app, "editor", False):
            return
        from .editor import EditorScene
        self.app.push(EditorScene(self.app))

    def salva(self) -> None:
        nome = (self.nome.value or self._nome_predefinito()).strip()
        nome = "".join(c for c in nome if c.isalnum() or c in "._- ") or "partita"
        try:
            dove = storage.write_save(nome, self.gs.to_dict())
        except Exception as exc:
            self.app.toast(f"Salvataggio non riuscito: {exc}")
            return
        self.app.toast(f"Partita salvata in {dove}.")
        self.vai("principale")

    def carica(self) -> None:
        if not self.scelto:
            return
        try:
            gs = GameState.from_dict(storage.read_save(self.scelto))
        except Exception as exc:
            self.app.toast(f"Salvataggio non leggibile: {exc}")
            return
        self.app.gs = gs
        self.app.pop()
        from .shell import GameShell
        self.app.replace(GameShell(self.app))

    def nuova(self) -> None:
        self.app.pop()
        from .menu import TeamSelectScene
        self.app.replace(TeamSelectScene(self.app))

    def al_menu_iniziale(self) -> None:
        self.app.pop()
        from .menu import MenuScene
        self.app.replace(MenuScene(self.app))

    def chiudi(self) -> None:
        self.app.pop()

    # -------------------------------------------------------------------- loop
    def handle(self, ev) -> None:
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and self.modo == "principale":
            self.chiudi()
            return
        super().handle(ev)

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        velo = pygame.Surface((w, h), pygame.SRCALPHA)
        velo.fill((6, 9, 14, 232))
        surf.blit(velo, (0, 0))
        gs = self.gs
        titoli = {"principale": "MENU", "salva": "SALVA PARTITA",
                  "carica": "CARICA PARTITA", "nuova": "NUOVA PARTITA"}
        T.text(surf, titoli[self.modo], (w // 2, 96), 40, T.TEXT, bold=True, align="center")
        sotto = {
            "principale": f"{gs.player.name} - stagione {gs.season}, gara {min(gs.round + 1, len(gs.tracks))} di {len(gs.tracks)}",
            "salva": "Scegli il nome, o un salvataggio esistente da sovrascrivere",
            "carica": "La partita in corso verra' abbandonata",
            "nuova": "La partita in corso non e' stata salvata: si perde tutto",
        }[self.modo]
        T.text(surf, sotto, (w // 2, 150), 15, T.DIM, align="center")
        if self.modo == "principale":
            T.text(surf, "L'editor permette di modificare qualunque valore della partita: "
                         "squadre, piloti, vetture, circuiti, regolamento e costanti di "
                         "taratura. Da usare sapendo che si sta barando.",
                   (w // 2 - 200, h - 92), 12, T.DIM_2, maxw=400)
        if self.modo == "carica" and not self.saves:
            T.text(surf, "Nessun salvataggio.", (w // 2, 260), 16, T.DIM, align="center")
        super().draw(surf)


def _elenco() -> list:
    try:
        return storage.list_saves()
    except Exception:
        return []
