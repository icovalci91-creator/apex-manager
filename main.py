"""Apex Manager - manager di Formula 1 in 2D.

Avvio:  python main.py

Lo stesso file e' il punto di ingresso della build web (pygbag), che richiede
un `asyncio.run` su una coroutine di primo livello.
"""
import asyncio
import sys
import traceback

IS_WEB = sys.platform == "emscripten"


async def main() -> int:
    try:
        # importati qui dentro, non in cima: un errore di importazione fuori
        # dal try non verrebbe mai mostrato, e nel browser si vedrebbe solo
        # una schermata muta
        from game.ui.app import App
        from game.ui.scenes.menu import MenuScene
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

    Usa solo pygame, senza toccare i moduli del gioco: deve funzionare anche
    quando e' proprio uno di quelli ad aver fallito.
    """
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        surf = pygame.display.get_surface()
        if surf is None:
            surf = pygame.display.set_mode((1600, 900))
        surf.fill((14, 10, 12))
        big = pygame.font.Font(None, 40)
        small = pygame.font.Font(None, 22)
        surf.blit(big.render("Apex Manager si e' fermato all'avvio", True, (229, 72, 77)), (40, 40))
        y = 100
        for line in text.splitlines()[-28:]:
            surf.blit(small.render(line.rstrip()[:150], True, (231, 238, 248)), (40, y))
            y += 22
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
    # Se e' andata male si tiene la finestra del terminale aperta, cosi' chi ha
    # lanciato il gioco da riga di comando fa in tempo a leggere l'errore.
    # L'eseguibile impacchettato pero' il terminale non ce l'ha - e' una
    # finestra e basta - e chiedere Invio a un programma senza tastiera di
    # sistema lo farebbe morire una seconda volta, sull'errore dell'errore.
    if code and not IS_WEB and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nErrore. Premi Invio per chiudere...")
        except Exception:
            pass
    sys.exit(code)
