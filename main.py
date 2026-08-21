"""Apex Manager - manager di Formula 1 in 2D.

Avvio:  python main.py
"""
import sys
import traceback

from game.ui.app import App
from game.ui.scenes.menu import MenuScene


def main() -> int:
    app = App()
    app.push(MenuScene(app))
    app.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        input("\nErrore. Premi Invio per chiudere...")
        sys.exit(1)
