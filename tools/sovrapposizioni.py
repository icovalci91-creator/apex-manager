"""Cerca scritte che finiscono addosso a qualcos'altro, pagina per pagina.

    python tools/sovrapposizioni.py
    python tools/sovrapposizioni.py --only drivers hq

Una scritta sopra un'altra, o sopra una barra, o sopra un pulsante, non e' un
dettaglio estetico: e' un numero che non si legge piu'. Succede perche' le
pagine sono scritte a coordinate fisse, e basta un pannello un po' piu' stretto
o un valore un po' piu' lungo perche' due cose finiscano nello stesso posto.

Il controllo e' meccanico: si intercetta chi disegna testo e chi disegna barre,
si tiene il rettangolo di ognuno, e si guarda se due si pestano. Non serve
guardare niente a schermo.

Tre categorie, e servono tutte e tre:

  * **testo su testo**, che e' quella evidente;
  * **testo su barra**, che era il buco piu' grosso: una barra non e' un widget
    e non e' una scritta, quindi non veniva controllata da nessuna parte - ed e'
    esattamente il caso di "morale 70" scritto sopra la barra delle gomme;
  * **testo su pulsante**, cursore o interruttore, che rende il comando
    illeggibile e a volte non cliccabile.

E si controlla ogni pagina in piu' di uno stato. Una pagina appena aperta e'
quella che si rompe di meno: e' quando si sceglie un pilota, si apre una
trattativa o si scorre in fondo che le cose si accavallano. Qui si prova con
la selezione vuota e con la prima voce scelta, in cima e in fondo allo scorrimento, e a due
misure di finestra - quella minima e quella piena.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                        # noqa: E402
from game.ui import theme as T                       # noqa: E402
from game.ui import widgets as WD                    # noqa: E402

# Sotto questa sovrapposizione non e' un difetto: e' l'antialiasing di due
# scritte che si sfiorano, o il bordo di una barra sotto la sua etichetta.
# L'altezza sta bassa apposta: la sovrapposizione fra "Appeal commerciale" e il
# titolo TRATTATIVA era di cinque pixel, si vedeva benissimo a schermo, e con
# la soglia a sei passava liscia.
MIN_W, MIN_H = 10, 4
MIN_BARRA_W, MIN_BARRA_H = 8, 4

scritte: list = []
barre: list = []
dentro = [0]

_text, _bar = T.text, T.bar


def text(surf, s, pos, size=16, *a, **k):
    r = _text(surf, s, pos, size, *a, **k)
    if not dentro[0] and str(s).strip():
        scritte.append((pygame.Rect(r), str(s)))
    return r


def bar(surf, rect, *a, **k):
    if not dentro[0]:
        barre.append(pygame.Rect(rect))
    return _bar(surf, rect, *a, **k)


T.text, T.bar = text, bar

for _cls in (WD.Button, WD.Slider, WD.Toggle, WD.TextInput, WD.ScrollList):
    _orig = _cls.draw

    def _fatto(self, surf, _o=_orig):
        dentro[0] += 1
        try:
            _o(self, surf)
        finally:
            dentro[0] -= 1

    _cls.draw = _fatto

from game.ui.app import App                          # noqa: E402
from game.core.state import GameState                # noqa: E402
from game.core import development as D               # noqa: E402
from game.ui.scenes.shell import GameShell, NAV      # noqa: E402

CLICCABILI = (WD.Button, WD.Slider, WD.Toggle, WD.TextInput)


def stati(pagina) -> list:
    """Gli stati in cui vale la pena guardare questa pagina.

    Il primo e' sempre "come si apre". Gli altri sono le selezioni: una scheda
    con dentro un pilota vero e' molto piu' facile da rompere di una vuota.
    """
    fuori = [("aperta", lambda: None)]
    lista = getattr(pagina, "list", None)
    if lista is not None and getattr(lista, "items", None):
        def scegli(p=pagina, l=lista):
            if hasattr(p, "_select"):
                p._select(0, l.items[0])
        fuori.append(("primo scelto", scegli))
    mie = getattr(pagina, "mine", None)
    if mie is not None and getattr(mie, "items", None):
        def scegli_mio(p=pagina, l=mie):
            if hasattr(p, "_select_mine"):
                p._select_mine(0, l.items[0])
        fuori.append(("nostro scelto", scegli_mio))
    return fuori


def guarda(surf, shell, pid: str, nome_stato: str, W: int, H: int) -> list:
    p = shell.pages[pid]
    trovati = []
    for quota in (0.0, 1.0):
        p.set_scroll(p.scroll_max * quota)
        scritte.clear()
        barre.clear()
        surf.fill(T.BG)
        shell.draw(surf)
        vive = [(r, t) for r, t in scritte if r.y >= p.view.y - 2]
        for i, (ra, sa) in enumerate(vive):
            for rb, sb in vive[i + 1:]:
                c = ra.clip(rb)
                if c.w > MIN_W and c.h > MIN_H:
                    trovati.append(f"testo su testo: \"{sa[:30]}\" / \"{sb[:30]}\"")
            for rb in barre:
                c = ra.clip(rb)
                if c.w > MIN_BARRA_W and c.h > MIN_BARRA_H:
                    trovati.append(f"testo su barra: \"{sa[:30]}\"")
            for w in p.widgets:
                if not isinstance(w, CLICCABILI) or not getattr(w, "visible", True):
                    continue
                wr = pygame.Rect(w.rect)
                c = ra.clip(wr)
                if not (c.w > MIN_W and c.h > MIN_H):
                    continue
                lab = str(getattr(w, "label", "") or "")
                # un pulsante senza etichetta che contiene tutta la scritta non
                # e' un comando su cui si e' scritto sopra: e' una scheda
                # cliccabile, e la scritta e' il suo contenuto. Le carte del
                # calendario sono fatte cosi', e sono ventiquattro
                if not lab.strip() and wr.contains(ra):
                    continue
                trovati.append(f"testo su comando: \"{sa[:30]}\" / "
                               f"{lab or type(w).__name__}")
    return [f"{W}x{H} {pid:11s} [{nome_stato}] {x}" for x in dict.fromkeys(trovati)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    problemi = []
    # la misura minima, quella piena, e quella con cui il gioco si apre: e' in
    # quest'ultima che si sono trovati i difetti veri, perche' e' l'unica in cui
    # qualcuno guarda davvero le pagine
    from game import config as C
    for W, H in ((C.MIN_SCREEN_W, C.MIN_SCREEN_H), (1600, 900),
                 (C.SCREEN_W, C.SCREEN_H), (1180, 696)):
        app = App()
        app.screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
        gs = GameState.new_game("ferrari", True, seed=7)
        app.gs = gs
        # una squadra a meta' stagione ha piu' roba da mostrare di una appena
        # nata: progetti in corso, specifiche in verifica, un pacchetto andato
        # male. E' li' che le pagine si riempiono e si rompono
        D.start_project(gs, gs.player, "floor", "grande")
        part = gs.player.car.parts["rear_wing"]
        prima = part.perf
        part.perf -= 0.8
        gs.player.spec_trials.append(D.Trial(
            part="rear_wing", label="Ala posteriore", old_perf=prima, expected=4.4,
            size="grande", cost=6.0, news="va peggio della vecchia di 0.8"))
        shell = GameShell(app)
        app.push(shell)
        surf = pygame.Surface((W, H))
        for pid, _lab in NAV:
            if args.only and pid not in args.only:
                continue
            shell.go(pid)
            surf.fill(T.BG)
            shell.draw(surf)
            for nome, applica in stati(shell.pages[pid]):
                applica()
                shell.go(pid)
                problemi += guarda(surf, shell, pid, nome, W, H)

    for riga in problemi:
        print(riga)
    print(f"\nsovrapposizioni: {len(problemi)}")
    sys.exit(1 if problemi else 0)


if __name__ == "__main__":
    main()
