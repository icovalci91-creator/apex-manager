"""Loop principale e gestione delle schermate."""
from __future__ import annotations

import pygame

from .. import config as C
from . import theme as T


class Scene:
    def __init__(self, app):
        self.app = app
        self.widgets: list = []

    def enter(self) -> None:
        pass

    def leave(self) -> None:
        pass

    def handle(self, ev) -> None:
        for w in self.widgets:
            if w.handle(ev):
                return

    def update(self, dt: float) -> None:
        for w in self.widgets:
            w.update(dt)

    def draw(self, surf) -> None:
        for w in self.widgets:
            w.draw(surf)


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{C.GAME_TITLE} {C.GAME_VERSION}")
        self.screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scenes: list = []
        self.gs = None
        self.dev_budget = 1.5       # M$ per gara, impostato dalla pagina Sviluppo
        self.toast_text = ""
        self.toast_t = 0.0

    # ------------------------------------------------------------- schermate
    @property
    def scene(self) -> Scene | None:
        return self.scenes[-1] if self.scenes else None

    def push(self, scene: Scene) -> None:
        if self.scene:
            self.scene.leave()
        self.scenes.append(scene)
        scene.enter()

    def pop(self) -> None:
        if self.scenes:
            self.scenes.pop().leave()
        if self.scene:
            self.scene.enter()

    def replace(self, scene: Scene) -> None:
        while self.scenes:
            self.scenes.pop().leave()
        self.push(scene)

    def toast(self, msg: str, seconds: float = 3.0) -> None:
        self.toast_text = msg
        self.toast_t = seconds

    # ------------------------------------------------------------------ loop
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
                    if self.scene and hasattr(self.scene, "on_resize"):
                        self.scene.on_resize()
                elif self.scene:
                    self.scene.handle(ev)
            if self.scene:
                self.scene.update(dt)
                self.screen.fill(T.BG)
                self.scene.draw(self.screen)
            if self.toast_t > 0:
                self.toast_t -= dt
                self._draw_toast()
            pygame.display.flip()
        pygame.quit()

    def _draw_toast(self) -> None:
        f = T.font(16, True)
        img = f.render(self.toast_text, True, T.TEXT)
        w, h = img.get_size()
        sw = self.screen.get_width()
        r = pygame.Rect(sw // 2 - w // 2 - 20, self.screen.get_height() - 78, w + 40, h + 20)
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        s.fill((26, 34, 48, 240))
        self.screen.blit(s, r.topleft)
        pygame.draw.rect(self.screen, T.ACCENT, r, 1, border_radius=8)
        self.screen.blit(img, (r.x + 20, r.y + 10))
