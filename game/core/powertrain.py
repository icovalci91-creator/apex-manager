"""Power unit: sviluppo dei motoristi e programma per costruirsene una.

Le power unit non erano un'area di sviluppo: i valori dei motoristi restavano
quelli di partenza per sempre, quindi chi correva da costruttore non vedeva
mai crescere il proprio motore. Il "progetto power unit" era un conto alla
rovescia che a scadenza consegnava un motore di livello fisso, indipendente da
quanto ci si fosse investito e da chi lo dirigeva.

Qui diventa un reparto vero: si investe, si assumono ingegneri, e il tetto
raggiungibile dipende da quanto valgono le persone e la fabbrica.
"""
from __future__ import annotations

from . import economy

# Attributi che la simulazione legge davvero: potenza ed ERS pesano sul giro,
# l'affidabilita' sui ritiri. `efficiency` resta com'e', non essendo ancora
# usata da nessuna parte.
PU_ATTRS = ("power", "ers", "reliability")
PU_MAX = 99.0

# Quanto lentamente si colma la distanza dal proprio tetto, per gara e per
# milione investito. Basso di proposito: una power unit si costruisce in anni.
CLOSE_RATE = 0.012

# Biglietto d'ingresso per fondare il reparto. Tenuto sotto la cassa di
# partenza delle squadre medie: il costo vero e' l'investimento per gara.
PROGRAM_START_COST = 18.0
PROGRAM_MIN_SEASONS = 2       # prima non si scende in pista con roba propria
PROGRAM_FLOOR = 50.0          # per quanto male vada, non si parte da zero


# ------------------------------------------------------------------ anagrafica
def maker(gs, team) -> dict:
    return gs.engine_makers.get(team.engine, {})


def builder_of(gs, engine_id: str):
    """La squadra che costruisce quella power unit, se corre in griglia."""
    for t in gs.teams.values():
        if t.works and t.engine == engine_id:
            return t
    return None


def customers_of(gs, engine_id: str) -> list:
    return [t for t in gs.teams.values() if t.engine == engine_id and not t.works]


def rating(eng: dict) -> float:
    """Indice sintetico della power unit, come lo si legge nelle schermate."""
    return sum(float(eng.get(a, 85)) for a in PU_ATTRS) / len(PU_ATTRS)


# -------------------------------------------------------------- capacita' tecnica
def dev_rate(gs, team) -> float:
    """Da 0.5 a 1.6: quanto rende un milione speso in power unit."""
    return 0.50 + 1.10 * (team.pu_strength / 100.0)


def ceiling(gs, team) -> float:
    """Livello massimo raggiungibile con lo staff e la fabbrica di oggi.

    Assumere un buon responsabile powertrain alza il tetto: e' la leva con cui
    un reparto giovane puo' arrivare in alto.
    """
    return min(PU_MAX, 58.0 + 0.45 * team.pu_strength)


def locked(gs) -> bool:
    return bool(gs.regulations.get("pu_development_locked"))


def _equalisation_boost(gs, eng: dict) -> float:
    """La FIA concede sviluppo extra a chi e' indietro, se la norma e' in vigore."""
    if not gs.regulations.get("pu_equalisation"):
        return 1.0
    powers = [float(m.get("power", 85)) for m in gs.engine_makers.values()]
    lo, hi = min(powers), max(powers)
    if hi - lo < 1e-6:
        return 1.0
    deficit = (hi - float(eng.get("power", 85))) / (hi - lo)
    return 1.0 + 0.85 * deficit


# ------------------------------------------------------------------- sviluppo
def _advance(eng: dict, ceil: float, rate: float, budget: float, rng) -> float:
    """Avvicina una power unit al suo tetto. Ritorna il guadagno medio."""
    gained = 0.0
    push = min(2.5, max(0.0, budget) / 2.0)
    for attr in PU_ATTRS:
        cur = float(eng.get(attr, 85))
        gap = ceil - cur
        if gap <= 0:
            continue
        step = gap * CLOSE_RATE * push * rate * rng.uniform(0.55, 1.45)
        eng[attr] = min(PU_MAX, cur + step)
        gained += step
    return gained / len(PU_ATTRS)


def ai_budget(gs, team) -> float:
    """Quanto ci mette un motorista gestito dal computer."""
    return min(max(0.0, team.cash * 0.06), 1.2 + team.reputation / 55.0)


def develop(gs, player_budget: float = 0.0) -> list[str]:
    """Fa avanzare tutte le power unit di una gara.

    Lo sviluppo motori sta fuori dal tetto di spesa della squadra, come nella
    realta', dove i motoristi hanno un limite tutto loro.
    """
    if locked(gs):
        return []
    msgs = []
    for eid, eng in gs.engine_makers.items():
        team = builder_of(gs, eid)
        if team is None:
            continue                    # motorista senza squadra in griglia
        if team.is_player:
            budget = max(0.0, float(player_budget))
            if budget > 0:
                if team.cash < budget:
                    budget = max(0.0, team.cash)
                if budget > 0:
                    team.add_expense("Sviluppo power unit", round(budget, 3), in_cap=False)
        else:
            budget = ai_budget(gs, team)
            team.add_expense("Sviluppo power unit", round(budget, 3), in_cap=False)
        if budget <= 0:
            continue
        rate = dev_rate(gs, team) * _equalisation_boost(gs, eng)
        gain = _advance(eng, ceiling(gs, team), rate, budget, gs.rng)
        if team.is_player and gain > 0.05:
            msgs.append(f"Power unit: progressi in banco prova (+{gain:.2f}).")
    return msgs


# ------------------------------------------------- programma di chi e' cliente
def program(gs) -> dict:
    prog = getattr(gs, "pu_program", None)
    if prog is None:
        prog = {"own": False, "level": 0.0, "invested": 0.0, "ready_season": 0,
                "started": False}
        gs.pu_program = prog
    return prog


def base_level(gs) -> float:
    """Da dove parte un reparto nuovo.

    Non da zero: chi apre un reparto motori assume gente che i motori li ha
    gia' fatti, e parte dietro all'ultimo dei motoristi, non fuori scala.
    """
    ratings = [rating(m) for m in gs.engine_makers.values()] or [80.0]
    return max(PROGRAM_FLOOR, min(ratings) - 6.0)


def has_program(gs) -> bool:
    p = program(gs)
    return bool(p.get("started")) and not p.get("own")


def start_program(gs, team) -> tuple:
    """Fonda il reparto motori. Da qui in poi si costruisce, non si compra."""
    p = program(gs)
    if p.get("own") or team.works:
        return False, "Costruiamo gia' la nostra power unit."
    if p.get("started"):
        return False, "Il programma e' gia' avviato."
    ok, why = economy.can_afford(team, PROGRAM_START_COST, gs, check_cap=False)
    if not ok:
        return False, why
    team.add_expense("Fondazione reparto power unit", PROGRAM_START_COST, in_cap=False)
    p.update({"own": False, "started": True, "level": base_level(gs),
              "invested": PROGRAM_START_COST, "ready_season": gs.season + PROGRAM_MIN_SEASONS})
    return True, (f"Reparto power unit fondato: la prima unita' nostra non potra' "
                  f"scendere in pista prima del {p['ready_season']}.")


def advance_program(gs, budget: float) -> list[str]:
    """Fa crescere il reparto in costruzione di una gara."""
    if not has_program(gs) or locked(gs):
        return []
    p = program(gs)
    team = gs.player
    budget = max(0.0, float(budget))
    if budget > team.cash:
        budget = max(0.0, team.cash)
    if budget <= 0:
        return []
    team.add_expense("Programma power unit", round(budget, 3), in_cap=False)
    p["invested"] = p.get("invested", 0.0) + budget
    ceil = ceiling(gs, team)
    gap = ceil - p["level"]
    if gap <= 0:
        return []
    step = gap * CLOSE_RATE * min(2.5, budget / 2.0) * dev_rate(gs, team)
    p["level"] = min(PU_MAX, p["level"] + step * gs.rng.uniform(0.6, 1.4))
    return []


def ready_to_debut(gs) -> bool:
    p = program(gs)
    return has_program(gs) and gs.season >= p.get("ready_season", 9999)


def debut(gs) -> tuple:
    """Manda in pista la power unit costruita in casa."""
    if not ready_to_debut(gs):
        return False, "Il reparto non e' ancora pronto per la pista."
    p = program(gs)
    team = gs.player
    lvl = float(p.get("level", base_level(gs)))
    eid = f"{team.id}_pu"
    gs.engine_makers[eid] = {
        "name": f"{team.name} Powertrains",
        "power": lvl, "ers": max(40.0, lvl - 2.0),
        "reliability": max(35.0, lvl - 6.0),
        "efficiency": max(40.0, lvl - 3.0),
        "cost_per_customer": 24.0,
    }
    team.engine = eid
    team.works = True
    team.engine_customer_cost = 0.0
    p["own"] = True
    gs.sync_engines()
    return True, (f"La nostra power unit debutta: {rating(gs.engine_makers[eid]):.0f} "
                  f"di valutazione dopo {p['invested']:.0f} M$ investiti.")
