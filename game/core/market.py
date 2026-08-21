"""Mercato piloti e staff: trattative, contratti, finestra di mercato."""
from __future__ import annotations

from ..model.people import Driver, Staff, generate_staff
from . import economy


# --------------------------------------------------------------- valutazioni
def seat_quality(gs, team) -> float:
    """Quanto e' appetibile un sedile: risultati, struttura, reputazione."""
    pos = gs.position_of(team.id)
    n = len(gs.teams)
    standing = 1.0 - (pos - 1) / max(1, n - 1)
    return 100.0 * (0.45 * standing + 0.30 * (team.reputation / 100.0)
                    + 0.25 * (team.car.rating / 100.0))


def driver_interest(gs, driver: Driver, team, salary: float, years: int) -> float:
    """0..1: quanto il pilota gradisce l'offerta."""
    q = seat_quality(gs, team) / 100.0
    cur = gs.teams.get(driver.team)
    cur_q = seat_quality(gs, cur) / 100.0 if cur else 0.18
    money = salary / max(0.4, driver.market_value)
    ambition = 0.5 + 0.5 * max(0.0, (driver.potential - driver.overall)) / 20.0
    score = 0.0
    score += 1.45 * (q - cur_q) * ambition
    score += 0.85 * (money - 1.0)
    score += 0.30 * (team.reputation - 70) / 30.0
    score += 0.12 * (3 - abs(years - 3))
    if driver.age > 34:
        score += 0.30 * (money - 1.0)          # i veterani guardano piu' al portafoglio
    if cur is None:
        score += 0.55                          # uno svincolato accetta piu' facilmente
    score -= 0.20 * max(0, driver.contract_until - gs.season)
    return max(0.0, min(1.0, 0.5 + score * 0.42))


def buyout_cost(gs, driver: Driver) -> float:
    years = max(0, driver.contract_until - gs.season)
    return round(driver.salary * (0.55 + 0.45 * years), 2)


def offer_contract(gs, team, driver: Driver, salary: float, years: int) -> tuple:
    """Ritorna (esito, messaggio). Esito: accepted | rejected | counter."""
    if len(team.drivers) >= 2 and driver.id not in team.drivers:
        return "rejected", "Hai gia' due piloti sotto contratto: liberane uno prima."
    cost = salary
    if driver.team and driver.team != team.id:
        cost += buyout_cost(gs, driver)
    ok, why = economy.can_afford(team, cost, gs, check_cap=False)
    if not ok:
        return "rejected", why
    interest = driver_interest(gs, driver, team, salary, years)
    roll = gs.rng.random()
    if roll < interest:
        _sign(gs, team, driver, salary, years)
        return "accepted", f"{driver.name} firma per {years} stagioni a {salary:.1f} M$/anno."
    if roll < interest + 0.28:
        want = round(driver.market_value * gs.rng.uniform(1.08, 1.35), 1)
        return "counter", f"{driver.name} ci pensa: chiede {want:.1f} M$/anno."
    return "rejected", f"{driver.name} rifiuta: non ritiene il progetto all'altezza."


def _sign(gs, team, driver: Driver, salary: float, years: int) -> None:
    old = gs.teams.get(driver.team)
    if old and driver.id in old.drivers:
        old.drivers.remove(driver.id)
        fee = buyout_cost(gs, driver)
        team.add_expense(f"Buyout {driver.last}", fee, in_cap=False)
        old.add_income(f"Buyout {driver.last}", fee)
    if driver in gs.free_agents:
        gs.free_agents.remove(driver)
    gs.drivers[driver.id] = driver
    driver.team = team.id
    driver.salary = salary
    driver.contract_until = gs.season + years
    if driver.id not in team.drivers:
        team.drivers.append(driver.id)


def release_driver(gs, team, driver: Driver) -> tuple:
    fee = buyout_cost(gs, driver)
    ok, why = economy.can_afford(team, fee, gs, check_cap=False)
    if not ok:
        return False, why
    team.add_expense(f"Rescissione {driver.last}", fee, in_cap=False)
    if driver.id in team.drivers:
        team.drivers.remove(driver.id)
    driver.team = None
    gs.free_agents.append(driver)
    return True, f"{driver.name} liberato per {fee:.1f} M$."


# ------------------------------------------------------------------- staff
def hire_staff(gs, team, person: Staff, salary: float, years: int) -> tuple:
    ok, why = economy.can_afford(team, salary, gs)
    if not ok:
        return False, why
    interest = 0.42 + 0.30 * (team.reputation / 100.0) + 0.42 * (salary / max(0.2, person.market_value) - 1.0)
    if gs.rng.random() > max(0.05, min(0.95, interest)):
        return False, f"{person.name} declina l'offerta."
    old = gs.teams.get(person.team)
    if old:
        for s in list(old.staff):
            if s.id == person.id:
                old.staff.remove(s)
        fee = round(person.salary * 0.8, 2)
        team.add_expense(f"Indennizzo {person.last}", fee, in_cap=True)
    if person in gs.free_staff:
        gs.free_staff.remove(person)
    # una sola persona per ruolo (tranne ingegneri e performance)
    if person.role not in ("race_engineer", "performance_engineer"):
        for s in list(team.staff):
            if s.role == person.role:
                team.staff.remove(s)
                s.team = None
                gs.free_staff.append(s)
    person.team = team.id
    person.salary = salary
    person.contract_until = gs.season + years
    team.staff.append(person)
    return True, f"{person.name} entra in squadra come {gs.staff_roles[person.role]['label']}."


def fire_staff(gs, team, person: Staff) -> tuple:
    fee = round(person.salary * max(0.5, person.contract_until - gs.season), 2)
    ok, why = economy.can_afford(team, fee, gs, check_cap=False)
    if not ok:
        return False, why
    team.add_expense(f"Buonuscita {person.last}", fee, in_cap=False)
    team.staff.remove(person)
    person.team = None
    gs.free_staff.append(person)
    return True, f"{person.name} lascia la squadra ({fee:.1f} M$)."


# ------------------------------------------------------- finestra di mercato
def run_transfer_window(gs) -> list:
    """Movimenti delle scuderie IA fra una stagione e l'altra."""
    news = []
    # contratti scaduti: chi non e' stato rinnovato torna sul mercato
    for team in gs.teams.values():
        for did in list(team.drivers):
            d = gs.drivers.get(did)
            if not d or d.contract_until > gs.season:
                continue
            if team.is_player:
                continue
            keep = 0.55 + 0.4 * ((d.overall - 78) / 16.0) - 0.25 * max(0, d.age - 35) * 0.1
            if gs.rng.random() < max(0.1, min(0.92, keep)):
                d.contract_until = gs.season + gs.rng.randint(1, 3)
                d.salary = round(d.market_value * gs.rng.uniform(0.9, 1.15), 1)
            else:
                team.drivers.remove(did)
                d.team = None
                gs.free_agents.append(d)
                news.append(f"{d.name} lascia {team.short}.")

    # le scuderie con sedili liberi pescano dal mercato
    order = sorted(gs.teams.values(), key=lambda t: -seat_quality(gs, t))
    for team in order:
        if team.is_player:
            continue
        while len(team.drivers) < 2 and gs.free_agents:
            pool = sorted(gs.free_agents, key=lambda d: -(d.overall + d.potential * 0.35))
            pick = None
            for cand in pool[:6]:
                salary = round(cand.market_value * gs.rng.uniform(0.95, 1.2), 1)
                if driver_interest(gs, cand, team, salary, 2) > gs.rng.random():
                    pick = (cand, salary)
                    break
            if not pick:
                pick = (pool[0], round(pool[0].market_value * 1.25, 1))
            _sign(gs, team, pick[0], pick[1], gs.rng.randint(1, 3))
            news.append(f"{pick[0].name} firma per {team.short}.")

    # ricambio dello staff libero
    from .state import _load
    pool = _load("staff.json")["name_pool"]
    for _ in range(4):
        role = gs.rng.choice(list(gs.staff_roles.keys()))
        gs.free_staff.append(generate_staff(role, gs.rng.uniform(50, 80), gs.rng,
                                            pool, gs.season, None))
    del gs.free_staff[40:]
    return news


def new_talents(gs) -> list:
    """Giovani promesse che salgono dalle categorie minori."""
    from .state import _load
    pool = _load("staff.json")["name_pool"]
    out = []
    for _ in range(gs.rng.randint(2, 4)):
        first = gs.rng.choice(pool["first"])
        last = gs.rng.choice(pool["last"])
        base = gs.rng.uniform(68, 79)
        d = Driver(
            id=f"{last.lower()}{gs.rng.randrange(100, 999)}", first=first, last=last,
            nat=gs.rng.choice(["IT", "GB", "FR", "DE", "ES", "BR", "JP", "US", "NL", "AR"]),
            age=gs.rng.randint(18, 21), number=gs.rng.randint(20, 99), team=None,
            pace=base + gs.rng.uniform(-3, 4), racecraft=base - gs.rng.uniform(2, 7),
            consistency=base - gs.rng.uniform(4, 10), tyre_mgmt=base - gs.rng.uniform(2, 8),
            wet=base - gs.rng.uniform(0, 6), feedback=base - gs.rng.uniform(2, 8),
            aggression=gs.rng.uniform(60, 85), stamina=gs.rng.uniform(80, 92),
            potential=min(97.0, base + gs.rng.uniform(6, 18)),
            marketability=gs.rng.uniform(35, 65), salary=gs.rng.uniform(0.8, 1.8),
            contract_until=gs.season,
        )
        gs.free_agents.append(d)
        out.append(d)
    return out
