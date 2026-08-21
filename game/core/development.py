"""Sviluppo della vettura: allocazione risorse, pacchetti di aggiornamento, ATR."""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C
from . import economy

# tetto tecnico raggiungibile in un ciclo regolamentare
PERF_CEILING = 99.0


@dataclass
class Project:
    part: str
    label: str
    invested: float          # M$ gia' spesi
    budget: float            # M$ totali previsti
    races_left: int
    expected: float          # guadagno atteso in punti prestazione
    risk: float              # 0..1 probabilita' di fallimento/correlazione errata
    started_round: int = 0

    @property
    def progress(self) -> float:
        return 0.0 if self.budget <= 0 else min(1.0, self.invested / self.budget)


def atr_factor(gs, team) -> float:
    """Ore di galleria del vento consentite in base alla classifica dell'anno prima."""
    scale = gs.regulations["aero_testing_restriction"]["scale"]
    idx = max(0, min(len(scale) - 1, team.last_position - 1))
    base = scale[idx] / 100.0
    slope = float(gs.regulations.get("atr_slope", 1.0))
    return 1.0 + (base - 1.0) * slope


def dev_capacity(gs, team) -> float:
    """Punti prestazione teorici che il team puo' produrre in un weekend."""
    core = team.dev_rate * (0.55 + 0.45 * atr_factor(gs, team))
    people = 0.5 * team.aero_strength + 0.5 * team.mech_strength
    return core * (people / 100.0) * 1.05


def cost_of_upgrade(part: str, size: str) -> float:
    mult = {"piccolo": 0.9, "medio": 2.1, "grande": 4.4}[size]
    return round(C.CAR_PARTS[part]["cost"] * mult, 2)


def expected_gain(gs, team, part: str, size: str) -> float:
    mult = {"piccolo": 1.0, "medio": 2.2, "grande": 4.0}[size]
    p = C.CAR_PARTS[part]
    dept = (p["aero"] * team.aero_strength + p["mech"] * team.mech_strength
            + p["pu"] * (team.pu_strength if team.works else 55.0))
    dept /= max(0.1, p["aero"] + p["mech"] + p["pu"])
    cur = team.car.parts[part].perf
    headroom = max(0.15, (PERF_CEILING - cur) / 30.0)
    return round(mult * (dept / 100.0) * team.dev_rate * headroom * 1.6, 2)


def project_risk(team, size: str) -> float:
    base = {"piccolo": 0.06, "medio": 0.12, "grande": 0.22}[size]
    quality = (0.5 * team.aero_strength + 0.5 * team.mech_strength) / 100.0
    sim = team.facilities.get("simulator", 60) / 100.0
    return max(0.02, base * (1.55 - 0.55 * quality - 0.30 * sim))


def start_project(gs, team, part: str, size: str) -> tuple:
    cost = cost_of_upgrade(part, size)
    ok, why = economy.can_afford(team, cost, gs)
    if not ok:
        return False, why
    if len(team.dev_projects) >= 3:
        return False, "Hai gia' tre progetti in corso: il reparto e' saturo."
    races = {"piccolo": 1, "medio": 3, "grande": 6}[size]
    pr = Project(part=part, label=f"{C.CAR_PARTS[part]['label']} - pacchetto {size}",
                 invested=0.0, budget=cost, races_left=races,
                 expected=expected_gain(gs, team, part, size),
                 risk=project_risk(team, size), started_round=gs.round)
    team.dev_projects.append(pr)
    return True, f"Progetto avviato: {pr.label} (+{pr.expected:.1f} attesi in {races} gare)."


def advance_projects(gs, team) -> list:
    """Fa avanzare i progetti di una gara. Ritorna i messaggi generati."""
    msgs = []
    done = []
    for pr in team.dev_projects:
        slice_cost = pr.budget / max(1, pr.races_left + (1 if pr.invested == 0 else 0))
        slice_cost = min(slice_cost, pr.budget - pr.invested)
        if slice_cost > 0:
            team.add_expense(f"Sviluppo: {pr.label}", round(slice_cost, 3), in_cap=True)
            pr.invested += slice_cost
        pr.races_left -= 1
        if pr.races_left <= 0:
            part = team.car.parts[pr.part]
            if gs.rng.random() < pr.risk:
                loss = pr.expected * gs.rng.uniform(0.0, 0.35)
                part.perf = min(PERF_CEILING, part.perf + loss)
                msgs.append(f"{C.CAR_PARTS[pr.part]['label']}: l'aggiornamento non ha correlato "
                            f"(+{loss:.1f} invece di +{pr.expected:.1f}).")
            else:
                gain = pr.expected * gs.rng.uniform(0.75, 1.30)
                part.perf = min(PERF_CEILING, part.perf + gain)
                msgs.append(f"{C.CAR_PARTS[pr.part]['label']}: aggiornamento in pista, +{gain:.1f}.")
            team.upgrades_done += 1
            done.append(pr)
    for pr in done:
        team.dev_projects.remove(pr)
    return msgs


def passive_development(gs, team, budget: float) -> None:
    """Sviluppo continuo distribuito secondo l'allocazione delle risorse."""
    if budget <= 0:
        return
    team.add_expense("Sviluppo continuo", round(budget, 3), in_cap=True)
    pts = dev_capacity(gs, team) * (budget / 2.5) * 0.55
    alloc = team.resource_alloc or {}
    tot = sum(alloc.values()) or 1.0
    for part, share in alloc.items():
        if part not in team.car.parts:
            continue
        p = team.car.parts[part]
        headroom = max(0.05, (PERF_CEILING - p.perf) / 26.0)
        p.perf = min(PERF_CEILING, p.perf + pts * (share / tot) * headroom * gs.rng.uniform(0.6, 1.4))


def budget_headroom(gs, team) -> float:
    """Quanto si puo' ancora spendere per gara restando dentro il cap."""
    races_left = max(1, len(gs.tracks) - gs.round)
    fixed = (team.staff_cost + team.facility_upkeep) / len(gs.tracks) + economy.TRAVEL_PER_RACE
    room = (economy.cap_limit(gs) - team.spent) / races_left - fixed
    return max(0.0, room)


def ai_development(gs) -> None:
    """Sviluppo delle scuderie gestite dal computer."""
    for team in gs.teams.values():
        if team.is_player:
            continue
        budget = min(team.cash * 0.10, 2.2 + team.reputation / 42.0,
                     budget_headroom(gs, team) * 0.75)
        weak = min(team.car.parts.items(), key=lambda kv: kv[1].perf)[0]
        alloc = {k: 1.0 for k in team.car.parts}
        alloc[weak] = 3.0
        if team.philosophy == "aero":
            for k in ("floor", "front_wing", "rear_wing", "active_aero"):
                alloc[k] = alloc.get(k, 1.0) + 1.2
        elif team.philosophy == "mechanical":
            for k in ("suspension", "chassis", "gearbox"):
                alloc[k] = alloc.get(k, 1.0) + 1.2
        elif team.philosophy == "powertrain":
            for k in ("cooling", "gearbox", "sidepods"):
                alloc[k] = alloc.get(k, 1.0) + 1.0
        team.resource_alloc = alloc
        passive_development(gs, team, budget)
        advance_projects(gs, team)
        if not team.dev_projects and gs.rng.random() < 0.30:
            size = gs.rng.choice(["piccolo", "medio", "medio", "grande"])
            start_project(gs, team, weak, size)


def regulation_reset(gs, strength: float) -> None:
    """Un nuovo ciclo tecnico riavvicina le prestazioni e premia chi ha struttura."""
    vals = [t.car.rating for t in gs.teams.values()]
    mean = sum(vals) / len(vals)
    for team in gs.teams.values():
        quality = (0.45 * team.aero_strength + 0.35 * team.mech_strength
                   + 0.20 * team.dev_rate * 60.0) / 100.0
        for p in team.car.parts.values():
            pull = (mean - p.perf) * strength * 0.55
            bonus = (quality - 0.75) * 22.0 * strength
            p.perf = max(45.0, min(PERF_CEILING, p.perf + pull + bonus + gs.rng.gauss(0, 2.4)))
            p.condition = 100.0
