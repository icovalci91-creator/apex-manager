"""Controlla che i tracciati non finiscano a schermo specchiati.

    python tools/verso_tracciati.py

La proiezione da gradi a metri mette il nord in y positiva, come una carta
geografica. Lo schermo, al contrario, fa crescere la y verso il basso: se i
punti del disegno arrivano cosi' come sono, ogni circuito esce ribaltato - che
non e' una rotazione, e' uno specchio. Le curve vanno dalla parte sbagliata e
le vetture girano al contrario del verso di gara, e chi conosce Monza se ne
accorge al primo sguardo.

Il controllo e' meccanico e non serve guardare niente: si calcola l'area con
segno del tracciato *come viene disegnato* - dove, con la y verso il basso,
area positiva vuol dire che a vederlo gira in senso orario - e la si confronta
con il `senso` dichiarato nei dati del circuito. Se i due non coincidono,
quella pista si sta vedendo a specchio.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game.core.state import GameState              # noqa: E402


def area_con_segno(pts: list) -> float:
    """Il doppio dell'area racchiusa, con il segno del verso di percorrenza."""
    a = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return a


def main() -> None:
    gs = GameState.new_game("ferrari", seed=1)
    print(f"{'pista':<14}{'verso vero':<14}{'come si vede':<14}")
    sbagliate = quante = 0
    for tr in gs.tracks:
        if not tr.points or not tr.senso:
            continue
        quante += 1
        visto = "orario" if area_con_segno(tr.points) > 0 else "antiorario"
        male = visto != tr.senso
        sbagliate += male
        print(f"{tr.id:<14}{tr.senso:<14}{visto:<14}"
              f"{'  <-- specchiata' if male else ''}")
    print(f"\nspecchiate: {sbagliate} su {quante}")
    if sbagliate:
        print("il ribaltamento del disegno sta in game.model.track._normalise")
    sys.exit(1 if sbagliate else 0)


if __name__ == "__main__":
    main()
