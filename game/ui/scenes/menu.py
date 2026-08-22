"""Menu principale e scelta della scuderia."""
from __future__ import annotations

import json
import math
import pygame

from ... import config as C
from ... import storage
from ...core.state import GameState
from .. import theme as T
from ..app import Scene
from ..widgets import Button, Toggle


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.build()

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        cx = w // 2
        self.widgets = []
        y = h // 2 - 40
        self.widgets.append(Button((cx - 150, y, 300, 52), "Nuova carriera", self.new_game, "primary"))
        saves = storage.list_saves()
        self.widgets.append(Button((cx - 150, y + 64, 300, 46), "Continua",
                                   self.load_game, "normal" if saves else "ghost"))
        self.widgets[-1].enabled = bool(saves)
        if not storage.IS_WEB:
            self.widgets.append(Button((cx - 150, y + 120, 300, 46), "Esci", self.quit, "ghost"))

    def on_resize(self) -> None:
        self.build()

    def new_game(self) -> None:
        self.app.push(TeamSelectScene(self.app))

    def load_game(self) -> None:
        saves = storage.list_saves()
        if not saves:
            return
        try:
            gs = GameState.from_dict(storage.read_save(saves[0]))
        except Exception as exc:                      # salvataggio incompatibile
            self.app.toast(f"Salvataggio non leggibile: {exc}")
            return
        self.app.gs = gs
        from .shell import GameShell
        self.app.replace(GameShell(self.app))

    def quit(self) -> None:
        self.app.running = False

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        for i in range(h // 3):
            c = T.mix((10, 13, 20), (18, 26, 42), i / max(1, h // 3))
            pygame.draw.line(surf, c, (0, i * 3), (w, i * 3), 3)
        for i in range(7):
            y = h * 0.62 + i * 26 + math.sin(self.t * 0.6 + i) * 5
            pygame.draw.line(surf, (18, 24, 34), (0, y), (w, y), 2)
        T.text(surf, C.GAME_TITLE.upper(), (w // 2, h // 2 - 190), 78, T.TEXT, bold=True, align="center")
        T.text(surf, "MANAGER DI FORMULA 1", (w // 2, h // 2 - 110), 22, T.ACCENT, bold=True, align="center")
        T.text(surf, f"versione {C.GAME_VERSION}", (w // 2, h - 40), 13, T.DIM_2, align="center")
        super().draw(surf)


class TeamSelectScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.gs_preview = GameState.new_game("ferrari", True, seed=1)
        self.teams = sorted(self.gs_preview.teams.values(), key=lambda t: -t.reputation)
        self.sel = 0
        self.constructor = True
        self.build()

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        self.cards = []
        cols, cw, ch, gap = 4, 300, 132, 16
        x0 = (w - (cols * cw + (cols - 1) * gap)) // 2
        y0 = 130
        for i, t in enumerate(self.teams):
            r = pygame.Rect(x0 + (i % cols) * (cw + gap), y0 + (i // cols) * (ch + gap), cw, ch)
            self.cards.append((r, t))
        self.toggle = Toggle((w // 2 - 300, h - 150, 380, 34),
                             "Costruttore completo (telaio + power unit)", self.constructor,
                             self.set_mode)
        self.widgets.append(self.toggle)
        self._sync_toggle()
        self.widgets.append(Button((w // 2 + 110, h - 156, 220, 46), "Inizia la carriera",
                                   self.start, "primary"))
        self.widgets.append(Button((40, h - 156, 150, 46), "Indietro", self.app.pop, "ghost"))

    def on_resize(self) -> None:
        self.build()

    def set_mode(self, v: bool) -> None:
        self.constructor = v

    def _sync_toggle(self) -> None:
        """La scelta ha senso solo per un cliente che potrebbe farsi il motore."""
        t = self.teams[self.sel]
        self.toggle.enabled = (not t.works) and t.pu_capable
        if t.works:
            self.toggle.label = "Gia' motorista: telaio e power unit in casa"
            self.toggle.value = True
        elif not t.pu_capable:
            self.toggle.label = "Solo telaio: reparto motori fuori portata"
            self.toggle.value = False
        else:
            self.toggle.label = "Fonda il reparto power unit"
            self.toggle.value = self.constructor

    def effective_constructor(self, t) -> bool:
        return t.works or (t.pu_capable and self.constructor)

    def start(self) -> None:
        team = self.teams[self.sel]
        gs = GameState.new_game(team.id, self.effective_constructor(team))
        self.app.gs = gs
        from .shell import GameShell
        self.app.replace(GameShell(self.app))

    def handle(self, ev) -> None:
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, (r, _t) in enumerate(self.cards):
                if r.collidepoint(ev.pos):
                    self.sel = i
                    self._sync_toggle()
                    return
        super().handle(ev)

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        T.text(surf, "SCEGLI LA TUA SCUDERIA", (w // 2, 44), 34, T.TEXT, bold=True, align="center")
        T.text(surf, "La reputazione determina budget, strutture e qualita' dello staff di partenza.",
               (w // 2, 88), 15, T.DIM, align="center")
        mouse = pygame.mouse.get_pos()
        for i, (r, t) in enumerate(self.cards):
            col = T.hex_rgb(t.colour)
            sel = (i == self.sel)
            hov = r.collidepoint(mouse)
            T.panel(surf, r, T.PANEL_2 if (sel or hov) else T.PANEL, radius=10,
                    border=col if sel else T.LINE, width=2 if sel else 1)
            pygame.draw.rect(surf, col, (r.x, r.y, r.w, 5), border_top_left_radius=10,
                             border_top_right_radius=10)
            T.text(surf, t.short, (r.x + 14, r.y + 16), 20, T.TEXT, bold=True, maxw=r.w - 28)
            eng = self.gs_preview.engine_makers[t.engine]["name"]
            stato = ("Motorista" if t.works else
                     "Team ufficiale" if t.is_partner else "Cliente")
            T.text(surf, f"{stato} - {eng}",
                   (r.x + 14, r.y + 42), 13, T.DIM, maxw=r.w - 28)
            drs = self.gs_preview.drivers_of(t.id)
            T.text(surf, " / ".join(d.last for d in drs), (r.x + 14, r.y + 62), 13, T.DIM_2,
                   maxw=r.w - 28)
            T.text(surf, "Reputazione", (r.x + 14, r.y + 88), 12, T.DIM_2)
            T.bar(surf, (r.x + 100, r.y + 90, r.w - 160, 8), t.reputation, 100, col)
            T.text(surf, f"{t.reputation:.0f}", (r.right - 14, r.y + 86), 14, T.TEXT,
                   bold=True, align="right")
            diff = _difficulty(t)
            T.text(surf, diff[0], (r.x + 14, r.y + 106), 12, diff[1], bold=True)
            T.text(surf, f"budget {t.budget_base:.0f} M$", (r.right - 14, r.y + 106), 12,
                   T.DIM, align="right")
        t = self.teams[self.sel]
        T.text(surf, t.name, (w // 2, h - 208), 22, T.hex_rgb(t.colour), bold=True, align="center")
        colour = T.DIM
        if t.works:
            note = ("Sei gia' motorista: costruisci in casa telaio e power unit, "
                    "con i costi e il controllo che ne derivano.")
        elif t.is_partner:
            note = (f"Team ufficiale {eng_name(self.gs_preview, t)}: non costruisci la power "
                    f"unit ma te la disegnano attorno alla vettura, a condizioni da partner. "
                    f"{t.pu_reason}.")
        elif not t.pu_capable:
            note = f"Solo telaio: {t.pu_reason}."
            colour = T.WARN
        elif self.constructor:
            note = ("Fonderai il reparto motori: la prima unita' nostra scendera' in pista "
                    "fra due stagioni, nel frattempo resti cliente.")
        else:
            note = "Comprerai la power unit da un motorista: meno costi fissi, prestazione non tua."
        T.text(surf, note, (w // 2, h - 180), 14, colour, align="center", maxw=w - 160)
        super().draw(surf)


def eng_name(gs, t) -> str:
    return gs.engine_makers.get(t.engine, {}).get("name", "?")


def _difficulty(t) -> tuple:
    if t.reputation >= 90:
        return "Difficolta': facile", T.OK
    if t.reputation >= 74:
        return "Difficolta': media", (150, 200, 90)
    if t.reputation >= 62:
        return "Difficolta': difficile", T.WARN
    return "Difficolta': estrema", T.BAD
