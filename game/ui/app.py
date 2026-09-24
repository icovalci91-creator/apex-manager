"""Loop principale e gestione delle schermate."""
from __future__ import annotations

import asyncio
import sys

import pygame

from .. import config as C
from . import fx
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


def _web_viewport_size() -> tuple | None:
    """Quanto spazio c'e' davvero nella pagina che ospita il canvas.

    La build si fa con una misura di riferimento (1600x900 di norma), ma
    quella e' solo il punto di partenza del pacchetto: un iPad in orizzontale
    e' largo circa 1180 punti, non 1600, e un canvas piu' grande viene scalato
    dal browser - sfocato, e disallineato rispetto a dove il dito tocca
    davvero lo schermo. Si chiede al browser quanto spazio c'e' per aprire il
    canvas a quella misura, non a quella scritta nel pacchetto. None se non si
    riesce a chiederlo (fuori dal browser, o il pygame di questa build non
    espone il ponte verso il JavaScript della pagina).
    """
    try:
        import platform          # iniettato da pygbag, non la stdlib
        w = int(platform.window.innerWidth)
        h = int(platform.window.innerHeight)
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return w, h


def _window_size() -> tuple:
    """La finestra piu' grande che ci sta davvero sullo schermo.

    La misura di riferimento e' 1600x900, ma un portatile a 1920x1080 con lo
    scaling di Windows al 125% ha un desktop da 1536x864: aprire piu' grandi
    del desktop taglia fuori il bordo destro e il fondo, e il gioco sembra
    disallineato quando invece e' solo fuori dallo schermo. Si lascia anche il
    posto per la barra del titolo e per quella delle applicazioni.
    """
    if IS_WEB:
        vp = _web_viewport_size()
        if vp is None:
            return C.SCREEN_W, C.SCREEN_H
        return (max(C.MIN_SCREEN_W, min(C.SCREEN_W, vp[0])),
                max(C.MIN_SCREEN_H, min(C.SCREEN_H, vp[1])))
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
        # anche nel browser il canvas puo' cambiare misura - un iPad che gira
        # da orizzontale a verticale, o la pagina che ridimensiona la finestra
        # - e RESIZABLE e' quello che permette al ciclo qui sotto di
        # accorgersene e riaprire il canvas alla misura giusta invece di
        # restare fermo a quella con cui si e' avviato
        self.screen = pygame.display.set_mode(_window_size(), pygame.RESIZABLE)
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
            T.sfondo(self.screen)
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

    def _passaggio(self) -> None:
        """Si fotografa quello che c'e' adesso: la nuova schermata ci passera'
        sopra con la lama del colore della squadra."""
        fx.entra()
        if getattr(self, "screen", None) is None or not self.scenes:
            return
        try:
            self.passaggio = fx.Passaggio(self.screen.copy(), T.squadra_viva())
        except pygame.error:
            self.passaggio = None

    def push(self, scene: Scene) -> None:
        self._passaggio()
        if self.scene:
            self.scene.leave()
        self.scenes.append(scene)
        scene.enter()

    def pop(self) -> None:
        self._passaggio()
        if self.scenes:
            self.scenes.pop().leave()
        if self.scene:
            self.scene.enter()

    def replace(self, scene: Scene) -> None:
        self._passaggio()
        while self.scenes:
            self.scenes.pop().leave()
        self.scenes.append(scene)
        scene.enter()

    def toast(self, msg: str, seconds: float = 3.0) -> None:
        self.toast_text = msg
        self.toast_t = seconds
        self._toast_durata = seconds

    # ------------------------------------------------------------------ loop
    async def run(self) -> None:
        """Loop di gioco.

        E' asincrono perche' la build web gira dentro il browser: senza cedere
        il controllo a ogni frame la pagina resterebbe congelata.
        """
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            fx.tick(dt)
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
                T.sfondo(self.screen)
                self.scene.draw(self.screen)
            passaggio = getattr(self, "passaggio", None)
            if passaggio is not None:
                passaggio.update(dt)
                passaggio.draw(self.screen)
                if passaggio.finito:
                    self.passaggio = None
            if self.toast_t > 0:
                self.toast_t -= dt
                self._draw_toast()
            pygame.display.flip()
            await asyncio.sleep(0)
        pygame.quit()

    def _draw_toast(self) -> None:
        """Il messaggio in basso: sale, resta, e scende via."""
        f = T.font(16, True)
        img = f.render(self.toast_text, True, T.TEXT)
        w, h = img.get_size()
        sw, sh = self.screen.get_size()
        # entra nei primi due decimi, esce negli ultimi tre
        passato = getattr(self, "_toast_durata", self.toast_t) - self.toast_t
        dentro = fx.esce(min(1.0, passato / 0.22)) * fx.dolce(min(1.0, self.toast_t / 0.3))
        r = pygame.Rect(sw // 2 - w // 2 - 26, sh - 60 - int(22 * dentro), w + 52, h + 22)
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (20, 27, 40, int(236 * dentro)), s.get_rect(), border_radius=r.h // 2)
        pygame.draw.rect(s, (*T.squadra_viva(), int(255 * dentro)), s.get_rect(), 1,
                         border_radius=r.h // 2)
        fx.proietta(self.screen, r, r.h // 2, 16, 6, int(150 * dentro))
        self.screen.blit(s, r.topleft)
        pygame.draw.circle(self.screen, T.squadra_viva(), (r.x + 16, r.centery), 4)
        img.set_alpha(int(255 * dentro))
        self.screen.blit(img, (r.x + 30, r.y + 11))
