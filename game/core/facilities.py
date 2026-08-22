"""Infrastrutture: potenziamenti, obsolescenza e investimenti delle IA.

Le regole stavano dentro la pagina che le disegnava, quindi le scuderie gestite
dal computer non potevano toccarle: restavano ferme ai valori di partenza per
sempre mentre il giocatore poteva salire indisturbato.

Qui c'e' anche l'obsolescenza. Una galleria del vento non si consuma, ma invec-
chia: quella di dieci anni fa non regge il passo con una nuova. Chi non rein-
veste scivola indietro senza fare niente di sbagliato.
"""
from __future__ import annotations

from .. import config as C
from . import economy

# Punti persi ogni stagione da una struttura lasciata com'e'. Cresce col
# livello: stare al passo in cima costa piu' che stare al passo a meta'.
DECAY = 1.10
FLOOR = 35.0          # sotto questo livello non si scende: resta un capannone


def cost(level: float, base: float) -> float:
    """Costo per alzare di un gradino una struttura.

    Le infrastrutture di una squadra di Formula 1 costano moltissimo, e ogni
    gradino in piu' costa piu' del precedente: portare una galleria del vento
    da 90 a 92 non e' come portarla da 60 a 65.
    """
    return round(base * (1.6 + (level / 100.0) ** 2.6 * 9.0), 2)


def gain(level: float) -> float:
    """Quanto sale una struttura con un potenziamento."""
    return max(1.5, 6.0 - level / 22.0)


def decay_of(level: float) -> float:
    return DECAY * (0.55 + 0.65 * level / 100.0)


def upgrade(gs, team, key: str) -> tuple:
    """Potenzia una struttura. Ritorna (riuscito, messaggio)."""
    lvl = float(team.facilities.get(key, 60.0))
    if lvl >= 99:
        return False, "Struttura gia' al massimo livello."
    price = cost(lvl, C.FACILITIES[key]["cost"])
    ok, why = economy.can_afford(team, price, gs)
    if not ok:
        return False, why
    team.add_expense(f"Potenziamento {C.FACILITIES[key]['label']}", price, in_cap=True,
                     category="strutture")
    team.facilities[key] = min(99.0, lvl + gain(lvl))
    return True, (f"{C.FACILITIES[key]['label']} portata a "
                  f"{team.facilities[key]:.0f} ({price:.2f} M$).")


def decay(gs) -> float:
    """Invecchia le strutture di tutti di una stagione.

    Ritorna quanto ha perso in media il giocatore, per poterglielo dire.
    """
    lost = 0.0
    for team in gs.teams.values():
        for k, v in team.facilities.items():
            new = max(FLOOR, float(v) - decay_of(float(v)))
            if team.is_player:
                lost += float(v) - new
            team.facilities[k] = new
    return lost / max(1, len(C.FACILITIES))


def priorities(team) -> list:
    """Su quali strutture punta una squadra, secondo la sua filosofia."""
    weights = {k: 1.0 for k in C.FACILITIES}
    focus = {
        "aero": ("windtunnel", "cfd", "aero_dept"),
        "mechanical": ("design_office", "factory", "simulator"),
        "powertrain": ("factory", "design_office", "cfd"),
    }.get(team.philosophy, ())
    for k in focus:
        weights[k] = 1.8
    # a parita' di interesse si rimette in pari quella messa peggio
    return sorted(C.FACILITIES,
                  key=lambda k: -(weights[k] * (100.0 - team.facilities.get(k, 60.0))))


def ai_invest(gs) -> None:
    """Le scuderie del computer reinvestono in strutture a fine stagione.

    Senza questo l'obsolescenza le farebbe scivolare all'infinito, e il
    giocatore resterebbe l'unico a poter costruire qualcosa.
    """
    for team in gs.teams.values():
        if team.is_player:
            continue
        # tengono da parte una riserva e spendono il resto, i piu' ricchi di piu'
        budget = max(0.0, (team.cash - 25.0) * 0.55)
        for key in priorities(team):
            price = cost(team.facilities.get(key, 60.0), C.FACILITIES[key]["cost"])
            if price > budget:
                continue
            ok, _msg = upgrade(gs, team, key)
            if ok:
                budget -= price
            if budget <= 0:
                break
