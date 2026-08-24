"""Schermata principale del gioco: barra superiore, navigazione e pagine."""
from __future__ import annotations

import time
import pygame

from ... import storage
from ...core import economy
from .. import theme as T
from ..app import Scene
from ..widgets import Button

NAV = [
    ("hq",        "Quartier Generale"),
    ("car",       "Vettura e assetto"),
    ("dev",       "Sviluppo"),
    ("powerunit", "Power unit"),
    ("engineers", "Ingegneri"),
    ("testing",   "Test privati"),
    ("drivers",   "Piloti e mercato"),
    ("academy",   "Vivaio"),
    ("staff",     "Staff tecnico"),
    ("workforce", "Organico reparti"),
    ("finance",   "Finanze e sponsor"),
    ("facilities", "Infrastrutture"),
    ("rules",     "Regolamento"),
    ("standings", "Classifiche"),
    ("calendar",  "Calendario"),
    ("history",   "Storico"),
]

TOPBAR_H = 64
NAV_W = 212


class Page:
    """Base per le pagine del gestionale.

    Una pagina puo' avere piu' roba di quanta ne stia nello schermo: su un
    portatile la finestra e' 1180x680, e le stesse pagine che a 1600x900 ci
    stavano comode finiscono sotto il bordo. Invece di riscrivere ogni
    schermata si sposta il foglio: la pagina viene costruita e disegnata a
    partire da un rettangolo alzato di `scroll`, cosi' quello che si disegna e
    quello che risponde al mouse restano la stessa cosa senza che le pagine
    debbano saperne niente.

    Chi disegna dice quanto spazio ha usato davvero scrivendo `content_h` alla
    fine del proprio `draw`; chi non lo scrive non scorre, come prima.
    """

    def __init__(self, shell):
        self.shell = shell
        self.app = shell.app
        self.widgets: list = []
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.view = pygame.Rect(0, 0, 10, 10)   # quello che si vede davvero
        self.scroll = 0.0
        self.content_h = 0                       # 0 = non lo sa: niente scorrimento

    @property
    def gs(self):
        return self.app.gs

    @property
    def team(self):
        return self.app.gs.player

    @property
    def scroll_max(self) -> float:
        if not self.content_h:
            return 0.0
        return max(0.0, self.content_h - self.view.h)

    def layout(self, rect) -> None:
        self.view = pygame.Rect(rect)
        self.scroll = min(self.scroll, self.scroll_max)
        self.rect = self.view.move(0, -int(self.scroll))
        self.build()

    def set_scroll(self, valore: float) -> None:
        valore = max(0.0, min(self.scroll_max, valore))
        if abs(valore - self.scroll) < 0.5:
            return
        self.scroll = valore
        self.rect = self.view.move(0, -int(self.scroll))
        self.build()

    def build(self) -> None:
        pass

    def handle(self, ev) -> None:
        # quello che e' scorso fuori dalla finestra non si vede e non si clicca:
        # senza questo, un cursore finito sotto la barra in alto rispondeva
        # ancora al mouse
        if hasattr(ev, "pos") and not self.view.collidepoint(ev.pos):
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                for w in self.widgets:
                    if hasattr(w, "drag") or hasattr(w, "pressed"):
                        w.handle(ev)          # un trascinamento si chiude ovunque
                self._presa = None
                return
        for w in self.widgets:
            if w.handle(ev):
                return
        # nessun widget se l'e' presa: se la pagina sfora, si scorre
        if self.scroll_max <= 0:
            return
        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.view.collidepoint(mx, my):
                self.set_scroll(self.scroll - ev.y * 60)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.view.collidepoint(ev.pos):
                self._presa = ev.pos[1]
                self._presa_scroll = self.scroll
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._presa = None
        elif ev.type == pygame.MOUSEMOTION and getattr(self, "_presa", None) is not None:
            self.set_scroll(self._presa_scroll - (ev.pos[1] - self._presa))

    def update(self, dt: float) -> None:
        # serve ai pulsantini dei cursori, che tenuti premuti ripetono
        for w in self.widgets:
            w.update(dt)

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
        from ..pages import (academy_page, core_pages, finance_pages, people_pages,
                             testing_page, workforce_page, world_pages)
        self.pages = {
            "hq": core_pages.HQPage(self),
            "car": core_pages.CarPage(self),
            "dev": core_pages.DevPage(self),
            "powerunit": core_pages.PowerUnitPage(self),
            "engineers": core_pages.EngineersPage(self),
            "testing": testing_page.TestingPage(self),
            "drivers": people_pages.DriversPage(self),
            "academy": academy_page.AcademyPage(self),
            "staff": people_pages.StaffPage(self),
            "workforce": workforce_page.WorkforcePage(self),
            "finance": finance_pages.FinancePage(self),
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
        # il blocco in fondo si misura prima, cosi' le voci del menu sanno
        # quanto spazio hanno davvero: su un desktop da 864 pixel le quindici
        # voci a passo fisso finivano sotto il pulsante del weekend
        editor = bool(getattr(self.app, "editor", False))
        save_y = h - 60                     # la riga Salva/Menu sta in fondo
        editor_y = save_y - 44
        race_y = (editor_y if editor else save_y) - 12 - 48
        y = TOPBAR_H + 16
        spazio = max(120, (race_y - 12) - y)
        # sotto i 24 pixel una voce non si legge e non si clicca: prima di
        # arrivarci si accetta di stringere, poi ci si ferma
        passo = max(24, min(42, spazio // max(1, len(NAV))))
        for pid, label in NAV:
            b = Button((12, y, NAV_W - 24, max(20, passo - 4)), label, style="tab")
            b.on_click = (lambda p=pid: self.go(p))
            b.active = (pid == self.page_id)
            self.nav_buttons.append(b)
            self.widgets.append(b)
            y += passo
        self.race_btn = Button((12, race_y, NAV_W - 24, 48), "WEEKEND DI GARA",
                               self.goto_weekend, "primary")
        self.widgets.append(self.race_btn)
        if editor:
            self.widgets.append(Button((12, editor_y, NAV_W - 24, 32), "EDITOR",
                                       self.open_editor, "danger"))
        self.widgets.append(Button((12, save_y, (NAV_W - 28) // 2, 34), "Salva", self.save, "ghost"))
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
        gs = self.app.gs
        try:
            where = storage.write_save(f"{gs.player_team}_{gs.season}", gs.to_dict())
        except Exception as exc:
            self.app.toast(f"Salvataggio non riuscito: {exc}")
            return
        self.app.toast(f"Partita salvata: {where}")

    def to_menu(self) -> None:
        """Apre il menu sopra la partita: nuova, salva, carica, editor."""
        from .gamemenu import GameMenuScene
        self.app.push(GameMenuScene(self.app))

    def open_editor(self) -> None:
        from .editor import EditorScene
        self.app.push(EditorScene(self.app))

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

        # la pagina si disegna dentro la sua finestra: se e' piu' alta, quello
        # che esce sopra e sotto viene tagliato invece di finire sulla barra
        pagina = self.pages[self.page_id]
        prev = surf.get_clip()
        # si taglia sull'area dei contenuti, non su quella della pagina: sopra
        # c'e' la barra con liquidita' e punti, e quando si scorre le pagine
        # ci finivano sopra
        vista = pygame.Rect(NAV_W + 1, TOPBAR_H + 1, w - NAV_W - 1, h - TOPBAR_H - 1)
        surf.set_clip(vista.clip(prev) if prev else vista)
        T.ink_start()
        pagina.draw(surf)
        fondo = T.ink_stop()
        for wd in pagina.widgets:
            if wd.visible:
                fondo = max(fondo, wd.rect.bottom)
        # si misura dall'origine del foglio, non da quella della finestra: se
        # no, appena si scorre l'altezza sembra rimpicciolita e lo scorrimento
        # si mangia da solo
        pagina.content_h = max(pagina.view.h, fondo - pagina.rect.y + 8)
        surf.set_clip(prev)
        if pagina.scroll_max > 0:
            v = pagina.view
            alt = max(30, int(v.h * v.h / max(1.0, pagina.content_h)))
            y = v.y + int((v.h - alt) * pagina.scroll / pagina.scroll_max)
            pygame.draw.rect(surf, T.PANEL_3, (w - 9, y, 4, alt), border_radius=2)
        super().draw(surf)


def _kv(surf, x: int, label: str, value: str, colour=T.TEXT, maxw: int = 200) -> None:
    T.text(surf, label, (x, 13), 11, T.DIM_2, bold=True)
    T.text(surf, value, (x, 30), 17, colour, bold=True, maxw=maxw)
