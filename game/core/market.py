"""Mercato piloti e staff: trattative, contratti, finestra di mercato."""
from __future__ import annotations

from dataclasses import dataclass

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
    """Quanto costa portarlo via.

    Se nel contratto c'e' una clausola rescissoria, e' lei a fare il prezzo:
    e' esattamente il senso di averla scritta.
    """
    if getattr(driver, "release_clause", 0.0) > 0.0:
        return round(float(driver.release_clause), 2)
    years = max(0, driver.contract_until - gs.season)
    return round(driver.salary * (0.55 + 0.45 * years), 2)


def offer_contract(gs, team, driver: Driver, salary: float, years: int) -> tuple:
    """Ritorna (esito, messaggio). Esito: accepted | rejected | counter."""
    if len(team.drivers) >= 2 and driver.id not in team.drivers:
        return "rejected", "Hai gia' due piloti sotto contratto: liberane uno prima."
    # solo l'indennizzo va pagato subito: lo stipendio e' un impegno annuale
    # che il bilancio spalma sulle gare
    if driver.team and driver.team != team.id:
        ok, why = economy.can_afford(team, buyout_cost(gs, driver), gs, check_cap=False)
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
        team.add_expense(f"Buyout {driver.last}", fee, in_cap=False, category="cessioni")
        old.add_income(f"Buyout {driver.last}", fee, category="cessioni")
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
    team.add_expense(f"Rescissione {driver.last}", fee, in_cap=False,
                     category="cessioni")
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
        team.add_expense(f"Indennizzo {person.last}", fee, in_cap=True,
                         category="personale")
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
    team.add_expense(f"Buonuscita {person.last}", fee, in_cap=False,
                     category="personale")
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

    # una squadra maggiore guarda prima nel proprio vivaio: e' a questo che
    # serve avere una seconda squadra nel gruppo
    for team in gs.teams.values():
        sat = [t for t in gs.teams.values() if t.parent_team == team.id]
        if team.is_player or not sat or len(team.drivers) >= 2:
            continue
        pesca = []
        for s2 in sat:
            pesca += [gs.drivers[x] for x in s2.drivers if x in gs.drivers]
        if not pesca:
            continue
        promosso = max(pesca, key=lambda x: x.overall + x.potential * 0.4)
        casa = gs.teams.get(promosso.team)
        if casa and promosso.id in casa.drivers:
            casa.drivers.remove(promosso.id)
        promosso.team = team.id
        promosso.salary = round(promosso.market_value * gs.rng.uniform(1.0, 1.3), 1)
        promosso.contract_until = gs.season + gs.rng.randint(1, 3)
        team.drivers.append(promosso.id)
        news.append(f"{promosso.name} promosso da {casa.short if casa else '-'} "
                    f"a {team.short}.")

    # le scuderie con sedili liberi pescano dal mercato
    order = sorted(gs.teams.values(), key=lambda t: -seat_quality(gs, t))
    for team in order:
        if team.is_player:
            continue
        while len(team.drivers) < 2 and gs.free_agents:
            pool = sorted(gs.free_agents, key=lambda d: -(d.overall + d.potential * 0.35))
            pick = None
            fame = economy.spending_appetite(gs, team)
            for cand in pool[:6]:
                # una squadra con la cassa piena si compra il pilota che vuole:
                # e' cosi' che si spiegano gli ingaggi che fanno notizia
                salary = round(cand.market_value * gs.rng.uniform(0.95, 1.2)
                               * (1.0 + 0.40 * fame), 1)
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
    news += ai_staff_market(gs)
    return news


# ------------------------------------------------------- il mercato degli uomini
# I ruoli che spostano davvero qualcosa: da questi escono la forza dei reparti,
# la fiducia nei pacchetti e il modo in cui si legge una gara.
KEY_ROLES = ("technical_director", "head_of_aero", "chief_designer",
             "head_of_powertrain", "head_of_strategy", "chief_mechanic",
             "team_principal")


def role_score(gs, person, role: str) -> float:
    """Quanto vale una persona in quel ruolo, con i pesi del ruolo stesso."""
    if person is None:
        return 0.0
    w = gs.staff_roles.get(role, {}).get("weights", {})
    tot = sum(w.values()) or 1.0
    return round(sum(getattr(person, a, 60.0) * k for a, k in w.items()) / tot, 2)


def ai_staff_market(gs) -> list:
    """Le scuderie del computer si rinforzano anche fuori dalla pista.

    Senza questo l'organigramma delle IA restava quello del primo giorno per
    sempre: potevano accumulare denaro senza nessun modo di trasformarlo in
    ingegneri, che e' poi la leva piu' diretta che ha una squadra per andare
    piu' forte. Chi ha capitale in cassa sceglie per primo e paga di piu', ed
    e' cosi' che nella realta' un reparto si svuota e un altro si riempie.
    """
    news = []
    ruoli = [r for r in KEY_ROLES if r in gs.staff_roles]
    ordine = sorted((t for t in gs.teams.values() if not t.is_player),
                    key=lambda t: -economy.spending_appetite(gs, t))
    for team in ordine:
        fame = economy.spending_appetite(gs, team)
        if fame < 0.20 or gs.rng.random() > 0.25 + 0.55 * fame:
            continue
        # si interviene dove si e' messi peggio, non dove si e' gia' forti
        voti = {r: role_score(gs, team.role(r), r) for r in ruoli}
        if not voti:
            continue
        role = min(voti, key=voti.get)
        candidati = [p for p in gs.free_staff if p.role == role]
        if not candidati:
            continue
        best = max(candidati, key=lambda p: role_score(gs, p, role))
        if role_score(gs, best, role) < voti[role] + 3.0:
            continue                     # cambiare per cambiare non serve
        salario = round(best.market_value * (1.05 + 0.35 * fame), 2)
        ok, _msg = hire_staff(gs, team, best, salario, gs.rng.randint(2, 4))
        if ok:
            news.append(f"{team.short}: {best.name} arriva come "
                        f"{gs.staff_roles[role]['label']} ({salario:.1f} M$).")
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


# =========================================================== trattative vere
@dataclass
class Offer:
    """Un contratto sul tavolo: non solo quanto, ma come."""
    salary: float = 5.0
    years: int = 2
    bonus_win: float = 0.0
    bonus_podium: float = 0.0
    bonus_points: float = 0.0
    release_clause: float = 0.0

    def copy(self) -> "Offer":
        return Offer(self.salary, self.years, self.bonus_win, self.bonus_podium,
                     self.bonus_points, self.release_clause)


@dataclass
class Negotiation:
    driver_id: str
    team_id: str
    offer: Offer
    demand: Offer
    rounds: int = 0
    patience: int = 4
    state: str = "aperta"          # aperta | accordo | rotta
    last: str = ""

    @property
    def open(self) -> bool:
        return self.state == "aperta"


def season_outlook(gs, team) -> tuple:
    """Quante vittorie, podi e punti ci si aspetta da quel sedile in un anno.

    Serve a dare un prezzo ai bonus: promettere un milione a vittoria vale
    molto in una squadra che ne vince dieci e quasi niente in fondo alla
    griglia. E' il motivo per cui i bonus non sono soldi gratis.
    """
    rank = sorted(gs.teams.values(), key=lambda t: -t.car.rating)
    idx = [t.id for t in rank].index(team.id)
    n = max(1, len(gs.tracks))
    share = max(0.0, 1.0 - idx / max(1.0, len(rank) - 1))     # 1 il migliore, 0 l'ultimo
    # esponenti alti di proposito: in Formula 1 vittorie e podi si concentrano
    # in cima, e un sedile di meta' gruppo non ne vede quasi
    wins = n * 0.62 * share ** 5.0
    podiums = n * 1.40 * share ** 4.0
    points = 30.0 * n * share ** 3.5 + 6.0
    return wins, podiums, points


def offer_value(gs, team, driver, offer: Offer) -> float:
    """Quanto vale l'offerta per il pilota, in milioni all'anno.

    Ai bonus si dà il valore atteso, non quello nominale, e la clausola pesa
    in negativo quando è alta: essere incatenati costa, poter andarsene vale.
    """
    wins, podiums, points = season_outlook(gs, team)
    val = offer.salary
    val += offer.bonus_win * wins
    val += offer.bonus_podium * podiums
    val += offer.bonus_points * points
    fair = max(1.0, offer.salary * 2.5)
    if offer.release_clause <= 0.0:
        val -= 0.10 * offer.salary            # nessuna via d'uscita: piccolo sconto
    else:
        val += 0.14 * offer.salary * (1.0 - min(2.0, offer.release_clause / fair))
    return val


def opening_demand(gs, team, driver) -> Offer:
    """Da dove parte il pilota: chiede piu' del suo valore, come sempre."""
    q = seat_quality(gs, team) / 100.0
    ambition = 1.0 + 0.35 * max(0.0, driver.potential - driver.overall) / 20.0
    greed = 1.30 - 0.35 * q                    # in una squadra forte si accontenta
    base = driver.market_value * greed * ambition
    wins, podiums, points = season_outlook(gs, team)
    return Offer(
        salary=round(base * 0.80, 1),
        years=2 if driver.age < 33 else 1,
        bonus_win=round(base * 0.10 / max(1.0, wins), 2),
        bonus_podium=round(base * 0.06 / max(1.0, podiums), 2),
        bonus_points=round(base * 0.04 / max(1.0, points), 3),
        release_clause=round(base * 2.2, 1),
    )


def open_negotiation(gs, team, driver) -> Negotiation:
    demand = opening_demand(gs, team, driver)
    neg = Negotiation(driver_id=driver.id, team_id=team.id,
                      offer=demand.copy(), demand=demand,
                      patience=3 + int(driver.consistency > 85) + int(driver.team is None))
    tot = offer_value(gs, team, driver, demand)
    neg.last = (f"{driver.name} apre a {demand.salary:.1f} M$ di fisso per "
                f"{demand.years} stagioni: col resto del pacchetto vale "
                f"{tot:.1f} M$ l'anno.")
    return neg


def demand_value(gs, team, driver, neg: "Negotiation") -> float:
    """Quanto vale, tutto compreso, quello che il pilota chiede adesso."""
    return offer_value(gs, team, driver, neg.demand)


def propose(gs, team, driver, neg: Negotiation, offer: Offer) -> Negotiation:
    """Presenta un'offerta e raccoglie la risposta del pilota."""
    if not neg.open:
        return neg
    neg.offer = offer.copy()
    neg.rounds += 1
    want = offer_value(gs, team, driver, neg.demand)
    give = offer_value(gs, team, driver, offer)
    ratio = give / max(0.1, want)

    if offer.years > neg.demand.years + 2:
        ratio *= 0.94                          # troppo lungo: si sente legato
    if driver.team and driver.team != team.id:
        cur = gs.teams.get(driver.team)
        if cur and seat_quality(gs, cur) > seat_quality(gs, team) + 12:
            ratio *= 0.90                      # lascerebbe un sedile migliore

    if ratio >= 0.98:
        _sign_offer(gs, team, driver, offer)
        neg.state = "accordo"
        neg.last = f"{driver.name} firma: {offer.salary:.1f} M$ per {offer.years} stagioni."
        return neg

    if neg.rounds >= neg.patience:
        neg.state = "rotta"
        neg.last = f"{driver.name} chiude la trattativa: troppa distanza."
        return neg

    # concede qualcosa, ma meno se l'offerta e' lontana
    give_up = 0.10 if ratio > 0.88 else (0.05 if ratio > 0.72 else 0.02)
    neg.demand.salary = round(max(0.5, neg.demand.salary * (1.0 - give_up)), 1)
    neg.demand.release_clause = round(neg.demand.release_clause * (1.0 - give_up * 0.5), 1)
    gap = (1.0 - ratio) * 100.0
    now = offer_value(gs, team, driver, neg.demand)
    if ratio > 0.88:
        neg.last = (f"{driver.name}: ci siamo quasi, manca il {gap:.0f}%. "
                    f"Scenderebbe a {now:.1f} M$ complessivi.")
    elif ratio > 0.72:
        neg.last = (f"{driver.name}: non ci siamo, manca il {gap:.0f}%. "
                    f"Chiede {now:.1f} M$ complessivi.")
    else:
        neg.last = (f"{driver.name} giudica l'offerta fuori mercato ({gap:.0f}% "
                    f"sotto). Chiede {now:.1f} M$ complessivi.")
    return neg


def _sign_offer(gs, team, driver, offer: Offer) -> None:
    _sign(gs, team, driver, offer.salary, offer.years)
    driver.bonus_win = offer.bonus_win
    driver.bonus_podium = offer.bonus_podium
    driver.bonus_points = offer.bonus_points
    driver.release_clause = offer.release_clause
