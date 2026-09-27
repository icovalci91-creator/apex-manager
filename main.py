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


def _salva_errore(text: str) -> str:
    """Scrive l'errore in un file accanto ai salvataggi, e dice dove: e' quello
    da mandare a chi deve correggerlo."""
    try:
        from game import config as C
        cartella = C.UTENTE
    except Exception:
        import os
        cartella = os.getcwd()
    try:
        import datetime
        from pathlib import Path
        dove = Path(cartella) / "errore.txt"
        dove.parent.mkdir(parents=True, exist_ok=True)
        with open(dove, "w", encoding="utf-8") as f:
            f.write(f"Apex Manager - {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n{text}")
        return str(dove)
    except Exception:
        return ""


async def show_crash(text: str) -> None:
    """Scrive l'errore sullo schermo e ce lo tiene, finche' non si chiude.

    Usa solo pygame, senza toccare i moduli del gioco: deve funzionare anche
    quando e' proprio uno di quelli ad aver fallito. Prima sul computer la
    schermata compariva e la finestra si chiudeva subito: l'errore non lo
    leggeva nessuno. Adesso resta, e finisce anche in un file.
    """
    dove = "" if IS_WEB else _salva_errore(text)
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        surf = pygame.display.get_surface()
        if surf is None:
            surf = pygame.display.set_mode((1600, 900))
        w, h = surf.get_size()
        k = max(1.0, h / 900.0)
        surf.fill((14, 10, 12))
        big = pygame.font.Font(None, int(40 * k))
        small = pygame.font.Font(None, int(22 * k))
        x, y = int(40 * k), int(40 * k)
        surf.blit(big.render("Apex Manager si e' fermato per un errore", True,
                             (229, 72, 77)), (x, y))
        y += int(44 * k)
        if dove:
            surf.blit(small.render(f"L'errore e' salvato in: {dove}", True, (245, 196, 80)),
                      (x, y))
            y += int(24 * k)
        surf.blit(small.render("Premi Esc o chiudi la finestra per uscire.", True,
                               (150, 160, 178)), (x, y))
        y += int(36 * k)
        righe = max(10, int((h - y - 20) / (22 * k)))
        for line in text.splitlines()[-righe:]:
            surf.blit(small.render(line.rstrip()[:170], True, (231, 238, 248)), (x, y))
            y += int(22 * k)
        pygame.display.flip()
    except Exception:
        return
    # si tiene l'errore a schermo finche' non lo si chiude, cedendo il
    # controllo a ogni giro (nel browser e' il browser a volerlo)
    while True:
        try:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN
                                              and ev.key == pygame.K_ESCAPE):
                    return
            pygame.display.flip()
        except Exception:
            return
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    if "--prova-3d" in sys.argv:
        # per la build di GitHub: si accende Panda3D, si scrive com'e' andata
        # in prova3d.txt e si esce, senza aprire il gioco
        from game.ui import motore_panda
        sys.exit(motore_panda.prova_da_riga_di_comando("prova3d.txt"))
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
