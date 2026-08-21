"""Commissione F1: proposte di modifica al regolamento e votazioni."""
from __future__ import annotations

from .. import config as C


def team_traits(gs, team) -> dict:
    """Indicatori normalizzati -1..1 usati per capire se una proposta conviene."""
    budgets = [t.budget_base for t in gs.teams.values()]
    bmin, bmax = min(budgets), max(budgets)
    bn = (team.budget_base - bmin) / max(1e-6, bmax - bmin)          # 0 piccolo, 1 grande
    pos = gs.position_of(team.id)
    n = len(gs.teams)
    posn = 1.0 - 2.0 * (pos - 1) / max(1, n - 1)                      # +1 primo, -1 ultimo
    eng = gs.engine_makers.get(team.engine, {})
    all_pw = [m.get("power", 85) for m in gs.engine_makers.values()]
    pun = (eng.get("power", 85) - min(all_pw)) / max(1e-6, max(all_pw) - min(all_pw))
    stars = max((gs.drivers[d].overall for d in team.drivers if d in gs.drivers), default=75)
    tyre = sum(gs.drivers[d].tyre_mgmt for d in team.drivers if d in gs.drivers) / 2.0
    young = sum(1 for d in team.drivers if d in gs.drivers and gs.drivers[d].age <= 23)
    return {
        "big_budget": bn * 2 - 1,
        "small_budget": 1 - bn * 2,
        "reputation": (team.reputation - 75) / 25.0,
        "grid_position_high": posn,
        "grid_position_low": -posn,
        "aero_strength": (team.aero_strength - 78) / 18.0,
        "mechanical_strength": (team.mech_strength - 78) / 18.0,
        "strategy_strength": (team.strategy_strength - 78) / 18.0,
        "pit_crew_strength": (team.pit_strength - 78) / 18.0,
        "reliability_strength": (team.reliability_strength - 78) / 18.0,
        "tyre_mgmt_strength": (tyre - 82) / 12.0,
        "power_strength": pun * 2 - 1,
        "pu_leader": pun * 2 - 1,
        "pu_laggard": 1 - pun * 2,
        "star_drivers": (stars - 84) / 12.0,
        "academy_strength": (team.facilities.get("academy", 60) - 70) / 22.0,
        "young_drivers": young - 0.6,
        "customer_team": 1.0 if not team.works else -1.0,
        "constructor_team": 1.0 if team.works else -1.0,
    }


def appeal_score(gs, team, proposal: dict) -> float:
    tr = team_traits(gs, team)
    return sum(tr.get(k, 0.0) * w for k, w in proposal.get("appeal", {}).items())


def vote_of(gs, team, proposal: dict) -> bool:
    s = appeal_score(gs, team, proposal)
    s += gs.rng.gauss(0.0, 0.32)
    return s > 0.0


def institution_votes(gs, proposal: dict) -> tuple:
    """FIA guarda a costi e sicurezza, FOM allo spettacolo."""
    eff = proposal.get("effects", {})
    fia = 0.0
    fia += -0.9 if eff.get("cost_cap_musd", 0) > 0 else 0.0
    fia += 0.9 if eff.get("cost_cap_musd", 0) < 0 else 0.0
    fia += 0.7 if eff.get("standard_parts") else 0.0
    fia += -1.2 if eff.get("refuelling") else 0.0
    fia += 0.5 if proposal.get("category") == "finanziario" else 0.0
    fom = 0.0
    fom += 1.0 if eff.get("sprint_events", 0) > 0 else 0.0
    fom += -1.0 if eff.get("sprint_events", 0) < 0 else 0.0
    fom += 0.8 if eff.get("mandatory_stops") else 0.0
    fom += 0.7 if eff.get("tyre_deg_multiplier", 0) > 0 else 0.0
    fom += 0.9 if eff.get("third_car") else 0.0
    fom += 0.6 if eff.get("points") else 0.0
    fom += -0.8 if eff.get("prize_flatten") else 0.0
    return fia + gs.rng.gauss(0, 0.3) > 0, fom + gs.rng.gauss(0, 0.3) > 0


def tally(gs, proposal: dict, player_vote: bool | None = None) -> dict:
    com = gs.commission
    yes = 0
    total = len(gs.teams) * com["team_votes"] + com["fia_votes"] + com["fom_votes"]
    detail = []
    for t in gs.teams.values():
        if t.is_player and player_vote is not None:
            v = player_vote
        else:
            v = vote_of(gs, t, proposal)
        yes += com["team_votes"] if v else 0
        detail.append((t.short, v))
    fia, fom = institution_votes(gs, proposal)
    yes += com["fia_votes"] if fia else 0
    yes += com["fom_votes"] if fom else 0
    detail.append(("FIA", fia))
    detail.append(("FOM", fom))
    need = com["threshold_next_season_pct"]
    passed = yes / total >= need
    return {"yes": yes, "total": total, "need": need, "passed": passed, "detail": detail}


def apply_effects(gs, proposal: dict) -> list:
    """Applica gli effetti di una proposta approvata."""
    eff = proposal.get("effects", {})
    reg = gs.regulations
    sport = reg["sporting"]
    notes = []
    for k, v in eff.items():
        if k == "cost_cap_musd":
            reg["cost_cap_musd"] = max(90.0, reg.get("cost_cap_musd", 215.0) + v)
            notes.append(f"Budget cap: {reg['cost_cap_musd']:.0f} M$")
        elif k == "cost_cap_excludes_driver_salaries":
            reg[k] = v
        elif k == "driver_salary_cap_musd":
            reg[k] = v
        elif k == "min_weight_kg":
            reg["min_weight_kg"] = reg.get("min_weight_kg", 768) + v
            C.CAR_MASS_KG = float(reg["min_weight_kg"])
            notes.append(f"Peso minimo: {reg['min_weight_kg']} kg")
        elif k == "active_aero":
            reg["aero"]["active_aero"] = v
            for t in gs.teams.values():
                t.car.active_aero_allowed = v
            notes.append("Aero attiva " + ("consentita" if v else "abolita"))
        elif k == "downforce_index":
            reg["aero"]["downforce_index"] = max(0.35, reg["aero"]["downforce_index"] + v)
            for t in gs.teams.values():
                t.car.reg_downforce_index = reg["aero"]["downforce_index"]
        elif k == "points":
            sport["points"] = list(v)
            notes.append("Nuovo sistema di punteggio")
        elif k == "fastest_lap_point":
            sport["fastest_lap_point"] = v
        elif k == "sprint_events":
            sport["sprint_events"] = max(0, sport.get("sprint_events", 6) + v)
            _resync_sprints(gs, sport["sprint_events"])
            notes.append(f"Sprint in calendario: {sport['sprint_events']}")
        elif k == "mandatory_stops":
            sport["mandatory_stops"] = v
        elif k == "mandatory_compounds":
            sport["mandatory_compounds"] = v
        elif k == "units_per_season":
            reg["power_unit"]["units_per_season"] += v
        elif k == "pu_development_locked":
            reg["pu_development_locked"] = v
        elif k == "pu_equalisation":
            reg["pu_equalisation"] = v
        elif k == "atr_slope":
            reg["atr_slope"] = v
            notes.append("Nuova scala per le ore di galleria del vento")
        elif k == "testing_days":
            sport["testing_days"] = sport.get("testing_days", 3) + v
        elif k == "rookie_fp1_sessions":
            sport["rookie_fp1_sessions"] = sport.get("rookie_fp1_sessions", 4) + v
        elif k == "tyre_deg_multiplier":
            reg["tyres"]["deg_multiplier"] = max(0.5, reg["tyres"].get("deg_multiplier", 1.0) + v)
            for comp in C.COMPOUNDS.values():
                comp["wear"] *= (1.0 + v * 0.5)
        elif k == "standard_parts":
            reg["standard_parts"] = v
        elif k == "customer_cars_allowed":
            reg["customer_cars_allowed"] = v
        elif k == "third_car":
            reg["third_car"] = v
        elif k == "refuelling":
            reg["refuelling"] = v
        elif k == "prize_flatten":
            reg["prize_flatten"] = v
        elif k == "cap_carryover_musd":
            reg["cap_carryover_musd"] = v
        elif k == "income_bonus_musd":
            for t in gs.teams.values():
                t.budget_base = max(60.0, t.budget_base + v)
        elif k == "reliability_risk":
            reg["reliability_risk"] = v
        elif k == "reset_strength":
            reg["pending_reset"] = v
    reg.setdefault("applied", []).append(proposal["id"])
    return notes


def _resync_sprints(gs, count: int) -> None:
    for t in gs.tracks:
        t.sprint = False
    ranked = sorted(gs.tracks, key=lambda t: -t.traits.get("overtaking", 0.5))
    for t in ranked[:count]:
        t.sprint = True


def draw_proposals(gs, n: int = 3) -> list:
    applied = set(gs.regulations.get("applied", []))
    pool = [p for p in gs.proposals if p["id"] not in applied]
    gs.rng.shuffle(pool)
    return pool[:n]
