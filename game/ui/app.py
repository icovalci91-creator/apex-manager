"""Loop principale e gestione delle schermate."""
from __future__ import annotations

import asyncio
import sys

import pygame

from .. import config as C
from . import theme as T

IS_WEB = sys.platform == "emscripten"


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


def _window_size() -> tuple:
    """La finestra piu' grande che ci sta davvero sullo schermo.

    La misura di riferimento e' 1600x900, ma un portatile a 1920x1080 con lo
    scaling di Windows al 125% ha un desktop da 1536x864: aprire piu' grandi
    del desktop taglia fuori il bordo destro e il fondo, e il gioco sembra
    disallineato quando invece e' solo fuori dallo schermo. Si lascia anche il
    posto per la barra del titolo e per quella delle applicazioni.
    """
    if IS_WEB:
        return C.SCREEN_W, C.SCREEN_H
    try:
        dw, dh = pygame.display.get_desktop_sizes()[0]
    except Exception:
        return C.SCREEN_W, C.SCREEN_H
    return (max(C.MIN_SCREEN_W, min(C.SCREEN_W, dw - 16)),
            max(C.MIN_SCREEN_H, min(C.SCREEN_H, dh - 72)))


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{C.GAME_TITLE} {C.GAME_VERSION}")
        # nel browser la finestra e' la canvas della pagina, di dimensione
        # fissa: chiedere RESIZABLE non serve e puo' lasciarla vuota
        flags = 0 if IS_WEB else pygame.RESIZABLE
        self.screen = pygame.display.set_mode(_window_size(), flags)
        self._splash()
        self.clock = pygame.time.Clock()
        self.running = True
        self.scenes: list = []
        self.gs = None
        self.weekend = None         # weekend di gara aperto, se ce n'e' uno
        self.editor = False         # editor di gioco: si accende dal menu
        self.toast_text = ""
        self.toast_t = 0.0

    def _splash(self) -> None:
        """Dipinge subito qualcosa, appena lo schermo esiste.

        Serve da segnale: se questa scritta compare, Python sta girando e la
        canvas riceve i disegni: qualunque problema successivo e' nel gioco,
        non nell'avvio della pagina.
        """
        try:
            self.screen.fill(T.BG)
            T.text(self.screen, f"{C.GAME_TITLE} - caricamento...",
                   (self.screen.get_width() // 2, self.screen.get_height() // 2 - 20),
                   32, T.TEXT, bold=True, align="center")
            pygame.display.flip()
        except Exception:
            pass

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
    async def run(self) -> None:
        """Loop di gioco.

        E' asincrono perche' la build web gira dentro il browser: senza cedere
        il controllo a ogni frame la pagina resterebbe congelata.
        """
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.VIDEORESIZE:
                    # sotto una certa misura le schermate non ci stanno piu':
                    # meglio una finestra piu' grande della richiesta che una
                    # in cui i pannelli finiscono uno sopra l'altro
                    self.screen = pygame.display.set_mode(
                        (max(C.MIN_SCREEN_W, ev.w), max(C.MIN_SCREEN_H, ev.h)),
                        pygame.RESIZABLE)
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
            await asyncio.sleep(0)
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
