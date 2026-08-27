"""Il referto dei circuiti: quanto ci si puo' fidare di ognuno.

    python tools/track_report.py            # tutto il calendario
    python tools/track_report.py --tutti    # anche i candidati
    python tools/track_report.py --only monza spa

Ogni circuito porta un fattore di taratura che allunga o accorcia il giro fino
a farlo combaciare con la pole vera. Quel fattore e' comodo e pericoloso: fa
tornare i tempi e nasconde tutto il resto. Questo strumento lo spegne e guarda
cosa esce dal modello da solo.

Le colonne
----------
  errore    quanto sbaglia il giro senza taratura, con una vettura di
            riferimento da centro griglia. Sotto il tre per cento va bene: una
            macchina di meta' schieramento sta li' dietro alla pole. Sopra il
            dieci vuol dire che il tracciato o la scheda non descrivono quel
            circuito.
  punta     la velocita' massima del giro. Dove si conosce quella vera, di
            fianco c'e' lo scarto.
  curve     quante ne trova il modello contro quante ne dice la scheda. Uno o
            due di scarto sono normali - un raccordo lo si conta o no - dieci
            no.
  linea     come e' stato trovato il traguardo: dal confronto automatico, a
            mano, o per niente.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game import config as C                       # noqa: E402
from game.core.state import GameState              # noqa: E402
from game.model.car import Car                     # noqa: E402
from game.sim import pace                          # noqa: E402

# Le punte di velocita' vere, dove si conoscono: sono quelle da qualifica, non
# quelle in scia con l'ala aperta. Attenzione a leggerle: sono numeri della
# generazione precedente, presi con il DRS. Dal 2026 la spinta elettrica
# comincia a calare a 290 all'ora e si spegne a 355, e le punte scendono di
# una quindicina di km/h sui circuiti veloci: uno scarto negativo di quella
# grandezza non e' un errore del modello, e' il regolamento nuovo.
PUNTE = {
    "monza": 355, "monaco": 290, "spa": 340, "silverstone": 320, "baku": 350,
    "singapore": 310, "mexico": 350, "lasvegas": 350, "jeddah": 345,
    "suzuka": 325, "interlagos": 330, "bahrain": 330, "melbourne": 330,
    "shanghai": 330, "barcelona": 320, "montreal": 340, "hungaroring": 315,
    "zandvoort": 320, "cota": 325, "yasmarina": 330, "lusail": 320,
    "redbullring": 330, "miami": 340,
}


def referto(gs, piste) -> list:
    spec = {k: 85.0 for k in C.CAR_PARTS}
    ref = Car.build(spec, {"power": 90, "ers": 88, "reliability": 86, "efficiency": 87},
                    gs.regulations)
    righe = []
    for tr in piste:
        salva, tr.calibration = tr.calibration, 1.0
        ref.setup = ref.optimal_setup(tr)
        ref.evaluate_setup(tr)
        ref.fuel_kg = 0.0
        cond = pace.nominal(tr)
        t, _, _ = tr.lap_model(ref, grip=pace.surface_grip(cond), rho=cond.rho)
        tel = tr.telemetry(ref, grip=pace.surface_grip(cond), rho=cond.rho)
        tr.calibration = salva
        righe.append({
            "id": tr.id,
            "errore": (t - tr.ref_lap) / tr.ref_lap * 100,
            "punta": max(tr.speed_map) if tr.speed_map else 0.0,
            "vera": PUNTE.get(tr.id),
            "curve": len(tel["curve"]),
            "scheda": tr.corners,
            "linea": tr.start,
            "senso": tr.senso,
            "settori": tr.settori,
        })
    return righe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--tutti", action="store_true", help="anche i circuiti candidati")
    args = ap.parse_args()

    gs = GameState.new_game("ferrari", seed=7)
    piste = list(gs.tracks) + (list(gs.candidates) if args.tutti else [])
    if args.only:
        piste = [t for t in piste if t.id in args.only]

    righe = referto(gs, piste)
    print(f"{'pista':<13}{'errore':>8}{'punta':>7}{'vera':>7}{'curve':>7}{'scheda':>7}"
          f"  {'linea':<10}{'senso':<11}settori")
    for r in righe:
        scarto = f"{r['punta'] - r['vera']:+.0f}" if r["vera"] else "  -"
        linea = "trovata" if r["linea"] else "MANCA"
        sett = "veri" if r["settori"] else "a terzi di tempo"
        campanello = "  <<" if abs(r["errore"]) > 8 or abs(r["curve"] - r["scheda"]) > 6 else ""
        print(f"{r['id']:<13}{r['errore']:+7.1f}%{r['punta']:7.0f}{scarto:>7}"
              f"{r['curve']:7d}{r['scheda']:7d}  {linea:<10}{r['senso'] or '?':<11}"
              f"{sett}{campanello}")

    buoni = [r for r in righe if abs(r["errore"]) <= 8]
    err = [r["errore"] for r in buoni]
    print(f"\n{len(buoni)} circuiti in ordine: errore medio {statistics.mean(err):+.1f}%, "
          f"scarto tipo {statistics.stdev(err):.1f}%")
    fuori = [r["id"] for r in righe if r not in buoni]
    if fuori:
        print("da guardare: " + ", ".join(fuori))
    punte = [r["punta"] - r["vera"] for r in righe if r["vera"]]
    if punte:
        print(f"punte di velocita': scarto medio {statistics.mean(punte):+.0f} km/h, "
              f"peggiore {max(punte, key=abs):+.0f}")


if __name__ == "__main__":
    main()
