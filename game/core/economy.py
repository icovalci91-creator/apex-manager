"""Bilancio: ricavi, costi, premi FOM e tetto di spesa."""
from __future__ import annotations

from .. import config as C

# quota del montepremi in base alla posizione nel costruttori
PRIZE_SHARE = [0.150, 0.130, 0.115, 0.100, 0.090, 0.080, 0.072, 0.064, 0.058, 0.052, 0.046]
PRIZE_POOL = 1150.0        # M$ distribuiti dal promoter
TRAVEL_PER_RACE = 0.42     # M$ di logistica per gara


def prize_money(gs, position: int, flatten: float = 0.0) -> float:
    idx = max(0, min(len(PRIZE_SHARE) - 1, position - 1))
    share = PRIZE_SHARE[idx]
    if flatten > 0:
        flat = 1.0 / len(gs.teams)
        share = share * (1 - flatten) + flat * flatten
    return round(PRIZE_POOL * share, 2)


def sponsor_income(gs, team, race_points: float, position: int) -> float:
    """Ricavo per gara: base contrattuale + bonus prestazione + appeal dei piloti."""
    base = team.budget_base / len(gs.tracks)
    perf = race_points * 0.055
    star = sum(gs.drivers[d].marketability for d in team.drivers if d in gs.drivers) / 200.0
    rep = team.reputation / 100.0
    return round(base * (0.72 + 0.35 * rep) + perf + star * 0.22, 3)


def cap_limit(gs) -> float:
    return float(gs.regulations.get("cost_cap_musd", 215.0))


def cap_usage(gs, team) -> tuple:
    limit = cap_limit(gs)
    return team.spent, limit, (team.spent / limit if limit else 0.0)


def race_costs(gs, team, damage_cost: float) -> list:
    """Voci di costo di un weekend. Ritorna [(etichetta, importo, dentro_il_cap)]."""
    items = [("Logistica e trasferta", TRAVEL_PER_RACE, True)]
    if damage_cost > 0.001:
        items.append(("Riparazioni e ricambi", round(damage_cost, 3), True))
    n = max(1, len(gs.tracks))
    items.append(("Stipendi staff", round(team.staff_cost / n, 3), True))
    items.append(("Gestione strutture", round(team.facility_upkeep / n, 3), True))
    if not team.works:
        items.append(("Fornitura power unit", round(team.engine_customer_cost / n, 3), False))
    drv_salaries = sum(gs.drivers[d].salary for d in team.drivers if d in gs.drivers) / n
    in_cap = not gs.regulations.get("cost_cap_excludes_driver_salaries", True)
    items.append(("Ingaggi piloti", round(drv_salaries, 3), in_cap))
    return items


def apply_race_finances(gs, team, race_points: float, position: int, damage_cost: float) -> dict:
    inc = sponsor_income(gs, team, race_points, position)
    team.add_income("Sponsor e diritti", inc)
    total_out = 0.0
    for label, amt, in_cap in race_costs(gs, team, damage_cost):
        team.add_expense(label, amt, in_cap)
        total_out += amt
    return {"in": inc, "out": round(total_out, 3), "net": round(inc - total_out, 3)}


def end_of_season_finances(gs) -> list:
    """Premi FOM e verifica del tetto di spesa. Ritorna i messaggi da mostrare."""
    msgs = []
    flatten = float(gs.regulations.get("prize_flatten", 0.0))
    limit = cap_limit(gs)
    thr = gs.regulations["sporting"].get("budget_penalty_threshold_pct", 5) / 100.0
    for pos, team in enumerate(gs.constructor_standings(), 1):
        prize = prize_money(gs, pos, flatten)
        team.add_income(f"Premio FOM ({pos}o posto)", prize)
        team.last_position = pos
        over = team.spent - limit
        if over > 0:
            if over <= limit * thr:
                fine = round(over * 1.5 + 2.0, 2)
                team.add_expense("Multa sforamento budget cap", fine, in_cap=False)
                msgs.append(f"{team.short}: sforamento lieve del cap, multa di {fine} M$.")
            else:
                fine = round(over * 3.0 + 8.0, 2)
                team.add_expense("Sanzione grave budget cap", fine, in_cap=False)
                pen = min(30, int(over / 3))
                team.points = max(0.0, team.points - pen)
                msgs.append(f"{team.short}: sforamento grave, {fine} M$ di multa e -{pen} punti.")
        if team.is_player:
            msgs.append(f"Premio FOM incassato: {prize} M$ per il {pos}o posto costruttori.")
    return msgs


def can_afford(team, amount: float, gs=None, check_cap: bool = True) -> tuple:
    if team.cash < amount:
        return False, "Liquidita' insufficiente."
    if check_cap and gs is not None:
        if team.spent + amount > cap_limit(gs):
            return False, "Supereresti il tetto di spesa (budget cap)."
    return True, ""
