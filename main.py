"""Apex Manager - manager di Formula 1 in 2D.

Avvio:  python main.py

Lo stesso file e' il punto di ingresso della build web (pygbag), che richiede
un `asyncio.run` su una coroutine di primo livello.
"""
import asyncio
import sys
import traceback

from game.ui.app import App
from game.ui.scenes.menu import MenuScene

IS_WEB = sys.platform == "emscripten"


async def main() -> int:
    try:
        app = App()
        app.push(MenuScene(app))
        await app.run()
    except Exception:
        report = traceback.format_exc()
        print(report)
        await show_crash(report)
        return 1
    return 0


async def show_crash(text: str) -> None:
    """Scrive l'errore sullo schermo e ce lo tiene.

    Nel browser non c'e' una console a cui guardare: senza questo, qualunque
    eccezione all'avvio si vede come una schermata grigia e muta.
    """
    try:
        import pygame
        from game import config as C
        from game.ui import theme as T
        surf = pygame.display.get_surface()
        if surf is None:
            pygame.init()
            surf = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
        surf.fill((14, 10, 12))
        T.text(surf, "Apex Manager si e' fermato all'avvio", (40, 40), 30, T.BAD, bold=True)
        y = 100
        for line in text.splitlines()[-26:]:
            T.text(surf, line.rstrip(), (40, y), 14, T.TEXT, mono=True)
            y += 20
        pygame.display.flip()
    except Exception:
        return
    if not IS_WEB:
        return
    # la pagina non ha altro da fare: si tiene l'errore a schermo finche' non
    # la si chiude, cedendo il controllo al browser a ogni giro
    while True:
        pygame.event.pump()
        pygame.display.flip()
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    code = 1
    try:
        code = asyncio.run(main())
    except Exception:
        traceback.print_exc()
    if code and not IS_WEB:
        input("\nErrore. Premi Invio per chiudere...")
    sys.exit(code)
