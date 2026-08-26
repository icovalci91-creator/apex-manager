"""Quanto vale davvero una modifica al regolamento.

    python tools/sensibilita.py                # tutte le leve
    python tools/sensibilita.py --only peso carico

In Commissione si vota su cose scritte in italiano - "abbassare il peso
minimo", "spostare la ripartizione verso l'elettrico" - ma quello che poi
succede in pista lo decide il modello di giro. Questo strumento chiude il
cerchio: prende una leva alla volta, la muove di una tacca, e misura sul
calendario vero cosa ne esce.

Serve a due cose:

  * scrivere proposte nuove con effetti della grandezza giusta, invece di
    tirare a indovinare un numero che "sembra tanto";
  * controllare che le proposte gia' scritte non facciano finta: se una
    modifica passa in Commissione e i tempi non si muovono di un millesimo,
    quella modifica non esiste.

Le colonne sono secondi sul giro, con il segno del cronometro: negativo vuol
dire piu' veloci. La punta e' in km/h.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.core.state import GameState              # noqa: E402
from game.core import rules                        # noqa: E402
from game.sim import pace                          # noqa: E402

# Le leve, con la tacca con cui si muovono. La tacca e' scelta per essere
# leggibile in Commissione: dieci chili, cinque punti di carico, un megajoule.
LEVE = [
    ("peso -10 kg", {"min_weight_kg": -10}),
    ("peso +10 kg", {"min_weight_kg": 10}),
    ("carico +0.05", {"downforce_index": 0.05}),
    ("carico -0.05", {"downforce_index": -0.05}),
    ("elettrico +5%", {"electric_share": 0.05}),
    ("elettrico -5%", {"electric_share": -0.05}),
    ("recupero -1 MJ", {"recupero_mj": -1.0}),
    ("recupero +1 MJ", {"recupero_mj": 1.0}),
    ("effetto suolo via", {"ground_effect": False}),
    ("gomme scanalate", {"grooved_tyres": True}),
]


# E le architetture di power unit: qui non si muove una tacca, si cambia il
# motore. E' il conto che serve quando in Commissione si discute se tornare
# agli otto o ai dieci cilindri.
ARCHITETTURE = ("v8_turbo_leggero", "v10_aspirato", "v8_aspirato_kers")


def misura(gs) -> dict:
    """Il giro della vettura campione su ogni circuito, con il regolamento di adesso."""
    ref = gs._ref_car()
    out = {}
    for tr in gs.tracks:
        ref.setup = ref.optimal_setup(tr)
        ref.evaluate_setup(tr)
        ref.fuel_kg = 0.0
        cond = pace.nominal(tr)
        t, punta, _ = tr.lap_model(ref, grip=pace.surface_grip(cond), rho=cond.rho)
        out[tr.id] = (t, punta, tr.energia_giro, tr.ers_secondi)
    return out


def orfane() -> list:
    """Le voci che una proposta puo' cambiare e che poi non legge nessuno.

    Una modifica al regolamento che non arriva a nessun modulo e' una modifica
    che in pista non esiste: si vota, passa, e non cambia niente. Qui si
    cercano quelle: per ogni chiave che le proposte toccano si guarda se
    qualcuno, fuori dalla Commissione, la legge davvero.
    """
    import json
    reg = json.loads((ROOT / "data" / "regulations.json").read_text())
    chiavi = set()
    for pr in reg.get("proposals", []):
        chiavi.update(pr.get("effects", {}))
    morte = sorted(k for k in chiavi if rules.DESTINAZIONE.get(k, "?") is None)
    ignote = sorted(k for k in chiavi if k not in rules.DESTINAZIONE)
    return morte, ignote


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="filtra le leve per nome")
    args = ap.parse_args()

    base_gs = GameState.new_game("ferrari", seed=7)
    base = misura(base_gs)
    print(f"riferimento: {len(base)} circuiti, giro medio "
          f"{statistics.mean(t for t, _, _, _ in base.values()):.2f} s\n")
    print(f"{'leva':<20}{'giro medio':>11}{'minimo':>9}{'massimo':>9}"
          f"{'punta':>8}{'energia':>9}{'valore':>8}")
    for nome, eff in LEVE:
        if args.only and not any(k in nome for k in args.only):
            continue
        gs = GameState.new_game("ferrari", seed=7)
        rules.apply_effects(gs, {"id": f"sens_{nome}", "effects": dict(eff)})
        dopo = misura(gs)
        dt = [dopo[k][0] - base[k][0] for k in base]
        dv = [dopo[k][1] - base[k][1] for k in base]
        de = [dopo[k][2] - base[k][2] for k in base]
        dr = [dopo[k][3] - base[k][3] for k in base]
        print(f"{nome:<20}{statistics.mean(dt):+11.3f}{min(dt):+9.3f}{max(dt):+9.3f}"
              f"{statistics.mean(dv):+8.1f}{statistics.mean(de):+9.2f}{statistics.mean(dr):+8.2f}")
    print("\ngiro medio/minimo/massimo in secondi, punta in km/h, energia in MJ a giro,")
    print("valore = quanto vale la spinta elettrica su un giro, in secondi.")
    print(f"\n{'architettura':<20}{'giro medio':>11}{'punta':>8}{'peso':>7}"
          f"{'benzina':>9}{'energia':>9}")
    from game.core import architetture as AR
    for aid in ARCHITETTURE:
        gs = GameState.new_game("ferrari", seed=7)
        AR.applica(gs, aid)
        gs.refresh_tracks()
        dopo = misura(gs)
        dt = [dopo[k][0] - base[k][0] for k in base]
        dv = [dopo[k][1] - base[k][1] for k in base]
        a = AR.scheda(gs, aid)
        print(f"{a['breve']:<20}{statistics.mean(dt):+11.3f}{statistics.mean(dv):+8.1f}"
              f"{gs.regulations['min_weight_kg']:7.0f}{a['benzina_kg']:9.0f}"
              f"{statistics.mean(x[2] for x in dopo.values()):9.2f}")
    print("il confronto e' con il V6 turbo ibrido del 2026: 768 kg, 70 kg di benzina,")
    print("5.70 MJ recuperati a giro.")

    morte, ignote = orfane()
    if morte:
        print(f"\nvoci che il regolamento registra e nessuno legge ({len(morte)}):")
        print("  " + ", ".join(morte))
        print("  una proposta che tocca solo queste passa e in pista non cambia niente.")
    if ignote:
        print(f"\nvoci senza destinazione dichiarata ({len(ignote)}): " + ", ".join(ignote))
        print("  vanno aggiunte a rules.DESTINAZIONE, che dice chi legge cosa.")


if __name__ == "__main__":
    main()
