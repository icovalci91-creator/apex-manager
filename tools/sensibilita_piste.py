"""Quanto pesano qui benzina, aderenza, scia e pilota - circuito per circuito.

    python tools/sensibilita_piste.py
    python tools/sensibilita_piste.py --only monza lusail

La gara, giro dopo giro, somma al passo un po' di cose: i chili di benzina
ancora nel serbatoio, la mescola che si ha sotto e quanto e' consumata, l'aria
sporca di chi sta davanti, quanto e' bravo chi guida. Per anni erano quattro
numeri unici, uguali dalle Ardenne a Monte Carlo - l'unico pezzo di
simulazione che non guardava il circuito.

Adesso il livello di quei quattro numeri resta tarato sul mondo vero, ma la
forma la misura il modello di giro quando la pista si tara: si cambia una cosa
sola - settanta chili, tre punti di aderenza, il carico che lascia chi ti
precede - e si guarda il cronometro. Quello che resta appeso al circuito e' un
moltiplicatore attorno a uno.

Questo strumento fa vedere quei quattro moltiplicatori e, soprattutto, ricalcola
le medie del calendario: sono loro che centrano i moltiplicatori su uno, e
stanno scritte in `game/model/track.py` come BENZINA_RIF, GRIP_RIF, SCIA_RIF e
PILOTA_RIF. Se il calendario cambia parecchio quelle medie si spostano, e da
qui si legge di quanto. Non scrive niente.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game.model import track as T                    # noqa: E402
from game.core.state import GameState                # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    gs = GameState.new_game("ferrari", True, seed=13)
    piste = [t for t in gs.tracks if not args.only or t.id in args.only]

    print(f"{'pista':<14}{'benzina':>9}{'aderenza':>10}{'scia':>8}{'pilota':>9}")
    print(f"{'':<14}{'s/kg':>9}{'s/unita':>10}{'s':>8}{'quota':>9}")
    col = {"benzina": [], "aderenza": [], "scia": [], "pilota": []}
    for t in piste:
        v = {"benzina": t.benzina_rel * T.BENZINA_RIF,
             "aderenza": t.grip_rel * T.GRIP_RIF,
             "scia": t.scia_rel * T.SCIA_RIF,
             "pilota": t.pilota_rel * T.PILOTA_RIF}
        for k, x in v.items():
            col[k].append(x)
        print(f"{t.id:<14}{v['benzina']:9.4f}{v['aderenza']:10.1f}"
              f"{v['scia']:8.2f}{v['pilota']:9.3f}")

    print(f"\n{'':<14}{'misurata':>10}{'scritta':>10}{'scarto':>9}")
    rif = {"benzina": T.BENZINA_RIF, "aderenza": T.GRIP_RIF,
           "scia": T.SCIA_RIF, "pilota": T.PILOTA_RIF}
    nome = {"benzina": "BENZINA_RIF", "aderenza": "GRIP_RIF",
            "scia": "SCIA_RIF", "pilota": "PILOTA_RIF"}
    fuori = []
    for k, vals in col.items():
        media = statistics.mean(vals)
        scarto = media / rif[k] - 1.0
        if abs(scarto) > 0.05 and not args.only:
            fuori.append((nome[k], media))
        print(f"{nome[k]:<14}{media:10.4f}{rif[k]:10.4f}{100*scarto:+8.1f}%")

    if fuori:
        print("\nqueste medie si sono spostate di piu' del cinque per cento: in"
              "\ngame/model/track.py andrebbero riscritte cosi'")
        for n, m in fuori:
            print(f"   {n} = {m:.4f}")
    elif not args.only:
        print("\nle medie del calendario sono ancora quelle scritte nel modello.")


if __name__ == "__main__":
    main()
