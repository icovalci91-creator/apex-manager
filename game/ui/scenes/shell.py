"""Schermata principale del gioco: barra superiore, navigazione e pagine."""
from __future__ import annotations

import time
import pygame

from ... import config as C
from ...core import economy
from .. import theme as T
from ..app import Scene
from ..widgets import Button

NAV = [
    ("hq",        "Quartier Generale"),
    ("car",       "Vettura e assetto"),
    ("dev",       "Sviluppo"),
    ("engineers", "Ingegneri"),
    ("drivers",   "Piloti e mercato"),
    ("staff",     "Staff tecnico"),
    ("facilities", "Infrastrutture"),
    ("rules",     "Regolamento"),
    ("standings", "Classifiche"),
    ("calendar",  "Calendario"),
    ("history",   "Storico"),
]

TOPBAR_H = 64
NAV_W = 212


class Page:
    """Base per le pagine del gestionale."""

    def __init__(self, shell):
        self.shell = shell
        self.app = shell.app
        self.widgets: list = []
        self.rect = pygame.Rect(0, 0, 10, 10)

    @property
    def gs(self):
        return self.app.gs

    @property
    def team(self):
        return self.app.gs.player

    def layout(self, rect) -> None:
        self.rect = pygame.Rect(rect)
        self.build()

    def build(self) -> None:
        pass

    def handle(self, ev) -> None:
        for w in self.widgets:
            if w.handle(ev):
                return

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf) -> None:
        for w in self.widgets:
            w.draw(surf)

    def refresh(self) -> None:
        self.build()


class GameShell(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.page_id = "hq"
        self.pages: dict = {}
        self.nav_buttons: list = []
        self._make_pages()
        self.build()

    # -------------------------------------------------------------- costruzione
    def _make_pages(self) -> None:
        from ..pages import core_pages, people_pages, world_pages
        self.pages = {
            "hq": core_pages.HQPage(self),
            "car": core_pages.CarPage(self),
            "dev": core_pages.DevPage(self),
            "engineers": core_pages.EngineersPage(self),
            "drivers": people_pages.DriversPage(self),
            "staff": people_pages.StaffPage(self),
            "facilities": world_pages.FacilitiesPage(self),
            "rules": world_pages.RulesPage(self),
            "standings": world_pages.StandingsPage(self),
            "calendar": world_pages.CalendarPage(self),
            "history": world_pages.HistoryPage(self),
        }

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        self.nav_buttons = []
        y = TOPBAR_H + 16
        for pid, label in NAV:
            b = Button((12, y, NAV_W - 24, 38), label, style="tab")
            b.on_click = (lambda p=pid: self.go(p))
            b.active = (pid == self.page_id)
            self.nav_buttons.append(b)
            self.widgets.append(b)
            y += 42
        self.race_btn = Button((12, h - 116, NAV_W - 24, 48), "WEEKEND DI GARA",
                               self.goto_weekend, "primary")
        self.widgets.append(self.race_btn)
        self.widgets.append(Button((12, h - 60, (NAV_W - 28) // 2, 34), "Salva", self.save, "ghost"))
        self.widgets.append(Button((12 + (NAV_W - 24) // 2, h - 60, (NAV_W - 28) // 2, 34),
                                   "Menu", self.to_menu, "ghost"))
        content = pygame.Rect(NAV_W, TOPBAR_H, w - NAV_W, h - TOPBAR_H)
        for p in self.pages.values():
            p.layout(content.inflate(-32, -28))

    def on_resize(self) -> None:
        self.build()

    # ------------------------------------------------------------------ azioni
    def go(self, pid: str) -> None:
        self.page_id = pid
        for b, (p, _l) in zip(self.nav_buttons, NAV):
            b.active = (p == pid)
        self.pages[pid].refresh()

    def goto_weekend(self) -> None:
        gs = self.app.gs
        if gs.phase == "offseason" or gs.round >= len(gs.tracks):
            from .offseason import OffseasonScene
            self.app.push(OffseasonScene(self.app))
            return
        from .weekend import WeekendScene
        self.app.push(WeekendScene(self.app))

    def save(self) -> None:
        C.SAVES.mkdir(exist_ok=True)
        gs = self.app.gs
        path = C.SAVES / f"{gs.player_team}_{gs.season}.json"
        gs.save(path)
        self.app.toast(f"Partita salvata: {path.name}")

    def to_menu(self) -> None:
        from .menu import MenuScene
        self.app.replace(MenuScene(self.app))

    # ------------------------------------------------------------------- loop
    def enter(self) -> None:
        gs = self.app.gs
        if gs.phase == "offseason" or gs.round >= len(gs.tracks):
            self.race_btn.label = "FINE STAGIONE"
        else:
            t = gs.next_track
            self.race_btn.label = f"GARA {gs.round + 1}: {t.flag}" if t else "WEEKEND"
        self.pages[self.page_id].refresh()

    def handle(self, ev) -> None:
        self.pages[self.page_id].handle(ev)
        super().handle(ev)

    def update(self, dt: float) -> None:
        self.pages[self.page_id].update(dt)

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        gs = self.app.gs
        team = gs.player
        col = T.hex_rgb(team.colour)

        # barra laterale
        pygame.draw.rect(surf, T.PANEL, (0, TOPBAR_H, NAV_W, h - TOPBAR_H))
        pygame.draw.line(surf, T.LINE, (NAV_W, TOPBAR_H), (NAV_W, h))

        # barra superiore
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, TOPBAR_H))
        pygame.draw.rect(surf, col, (0, 0, 6, TOPBAR_H))
        T.text(surf, team.short.upper(), (22, 12), 21, T.TEXT, bold=True)
        T.text(surf, f"Stagione {gs.season}", (22, 38), 13, T.DIM)

        spent, limit, frac = economy.cap_usage(gs, team)
        _kv(surf, 250, "LIQUIDITA'", T.fmt_money(team.cash),
            T.OK if team.cash > 5 else T.BAD)
        _kv(surf, 420, "BUDGET CAP", f"{spent:.1f} / {limit:.0f} M$",
            T.BAD if frac > 1.0 else (T.WARN if frac > 0.85 else T.TEXT))
        pos = gs.position_of(team.id)
        _kv(surf, 610, "COSTRUTTORI", f"{pos}o  -  {team.points:.0f} pt", T.TEXT)
        nt = gs.next_track
        if nt:
            _kv(surf, 780, f"GARA {gs.round + 1}/{len(gs.tracks)}", nt.name, T.TEXT, maxw=280)
        else:
            _kv(surf, 780, "STAGIONE", "conclusa", T.WARN)
        drs = gs.drivers_of(team.id)
        if drs:
            names = "  |  ".join(f"{d.last} {d.points:.0f}" for d in drs)
            _kv(surf, 1090, "PILOTI", names, T.TEXT, maxw=330)
        pygame.draw.line(surf, T.LINE, (0, TOPBAR_H), (w, TOPBAR_H))

        self.pages[self.page_id].draw(surf)
        super().draw(surf)


def _kv(surf, x: int, label: str, value: str, colour=T.TEXT, maxw: int = 200) -> None:
    T.text(surf, label, (x, 13), 11, T.DIM_2, bold=True)
    T.text(surf, value, (x, 30), 17, colour, bold=True, maxw=maxw)
