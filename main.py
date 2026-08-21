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
    app = App()
    app.push(MenuScene(app))
    await app.run()
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        # nel browser non c'e' una console su cui attendere: bloccarsi su
        # input() lascerebbe la pagina appesa senza dire niente
        if not IS_WEB:
            input("\nErrore. Premi Invio per chiudere...")
        sys.exit(1)
    sys.exit(0)
