"""Il vivaio: i ragazzi che un giorno guideranno, e quanto costa tenerli.

Le squadre grandi non aspettano che un pilota si liberi sul mercato: se lo
crescono. Ferrari ha la Driver Academy dal 2009, la Red Bull il suo programma
junior da vent'anni, e chi ci ha investito si e' ritrovato in casa Leclerc,
Verstappen, Norris e Antonelli senza pagarli a peso d'oro.

Non lo fanno tutti, e non e' una scelta di gusto: aprire un vivaio costa una
cifra secca e poi si porta dietro un conto annuo che cresce con ogni ragazzo -
monoposto, gomme, trasferte, ingegneri, tutto per gente che non porta un punto.
Una squadra che fatica a riempire il budget della sua monoposto quel conto non
lo regge, ed e' il motivo per cui in fondo alla griglia il vivaio non ce l'ha
nessuno.
"""
from __future__ import annotations

from ..model.people import Driver
from . import economy

FOUND_COST = 15.0         # aprire il programma: strutture, contratti, gente
RUN_BASE = 2.6            # costo fisso annuo del programma
COST_PER_JUNIOR = 0.85    # e quanto costa tenerne uno in pista tutto l'anno
MAX_ROSTER = 6
LEAVE_AGE = 24            # oltre questa eta' o si promuove o si lascia andare


def has(team) -> bool:
    return bool(team.academy_name)


def roster(gs, team) -> list:
    return [gs.drivers[d] for d in team.academy if d in gs.drivers]


def running_cost(gs, team) -> float:
    """Quanto costa il vivaio in una stagione.

    C'e' la struttura - ingegneri, sede, gente che gira per i kart - e poi ci
    sono i posti in pista, che sono la voce grossa: un sedile in Formula 2
    costa quanto sette stagioni di Formula 4, ed e' il motivo per cui nessuno
    tiene sei ragazzi tutti in alto.
    """
    if not has(team):
        return 0.0
    from . import serie
    fac = float(team.facilities.get("academy", 60.0))
    fisso = RUN_BASE * (0.55 + 0.75 * fac / 100.0)
    posti = sum(serie.costo_posto(sid) for sid in
                (serie.serie_adatta(gs, d) for d in roster(gs, team)) if sid)
    return round(fisso + posti, 2)


def can_found(gs, team) -> tuple:
    """Se questa squadra puo' permettersi di aprirlo. Ritorna (si puo', perche')."""
    if has(team):
        return False, f"Il vivaio esiste gia': {team.academy_name}."
    ok, why = economy.can_afford(team, FOUND_COST, gs, check_cap=False)
    if not ok:
        return False, why
    # il conto vero non e' l'apertura: e' tenerlo aperto ogni anno
    annuo = RUN_BASE * (0.55 + 0.75 * float(team.facilities.get("academy", 60.0)) / 100.0)
    annuo += 3 * COST_PER_JUNIOR
    if economy.season_room(gs, team) < annuo * 2.2:
        return False, (f"Un vivaio costa circa {annuo:.1f} M$ l'anno di gestione: "
                       f"con quello che avanza adesso non lo si tiene aperto.")
    return True, ""


def found(gs, team, nome: str = "") -> tuple:
    ok, why = can_found(gs, team)
    if not ok:
        return False, why
    team.add_expense("Fondazione vivaio", FOUND_COST, in_cap=False, category="piloti")
    team.academy_name = nome or f"{team.short} Driver Academy"
    msgs = intake(gs, team, quanti=2)
    nomi = ", ".join(d.short for d in msgs)
    return True, (f"{team.academy_name} aperta. Primi ingaggi: {nomi}."
                  if nomi else f"{team.academy_name} aperta.")


# ------------------------------------------------------------------- ingaggi
def _giovane(gs, team, livello: float) -> Driver:
    """Un ragazzo nuovo, con quello che si riesce a vedere di lui adesso."""
    from .state import _load
    pool = _load("staff.json")["name_pool"]
    first = gs.rng.choice(pool["first"])
    last = gs.rng.choice(pool["last"])
    base = max(56.0, min(80.0, gs.rng.gauss(livello, 3.6)))
    eta = gs.rng.randint(16, 19)
    d = Driver(
        id=f"{last.lower()}{gs.rng.randrange(1000, 9999)}", first=first, last=last,
        nat=gs.rng.choice(["IT", "GB", "FR", "DE", "ES", "BR", "JP", "US", "NL",
                           "AR", "AU", "FI", "DK", "MX", "PL"]),
        age=eta, number=gs.rng.randint(20, 99), team=team.id,
        pace=base + gs.rng.uniform(-2, 3), racecraft=base - gs.rng.uniform(2, 7),
        consistency=base - gs.rng.uniform(4, 10), tyre_mgmt=base - gs.rng.uniform(3, 8),
        wet=base - gs.rng.uniform(0, 6), feedback=base - gs.rng.uniform(3, 8),
        aggression=gs.rng.uniform(58, 88), stamina=gs.rng.uniform(80, 94),
        potential=min(97.0, base + gs.rng.uniform(8, 22)),
        marketability=gs.rng.uniform(30, 58),
        salary=round(gs.rng.uniform(0.15, 0.45), 2),
        contract_until=gs.season + gs.rng.randint(2, 4),
        seat="academy",
    )
    gs.drivers[d.id] = d
    team.academy.append(d.id)
    return d


def scout_level(gs, team) -> float:
    """Quanto in alto arriva il vivaio: chi cerca bene e ha un nome trova meglio.

    Un ragazzo forte lo vogliono tutti: se ne va dove c'e' la struttura, dove
    c'e' chi lo sa guardare e dove sa che un giorno un volante c'e'.
    """
    q = (0.45 * team.scouting_strength + 0.30 * float(team.facilities.get("academy", 60.0))
         + 0.25 * team.reputation)
    return 46.0 + 0.34 * q


def intake(gs, team, quanti: int = 1) -> list:
    """I ragazzi che entrano nel programma."""
    if not has(team):
        return []
    posti = max(0, MAX_ROSTER - len(team.academy))
    fuori = []
    for _ in range(min(quanti, posti)):
        fuori.append(_giovane(gs, team, scout_level(gs, team)))
    return fuori


# ---------------------------------------------------------------- crescita
def grow(gs, team) -> list:
    """Crescita alla vecchia maniera, senza campionato.

    Resta per i casi in cui una stagione di categorie non c'e' stata - una
    partita caricata a meta' anno, un ragazzo entrato dopo - ma la strada
    normale adesso e' game.core.serie, dove si corre davvero.
    """
    msgs = []
    from ..model.people import DRIVER_ATTRS
    spinta = (0.55 + 0.45 * float(team.facilities.get("academy", 60.0)) / 100.0)
    for d in roster(gs, team):
        margine = max(0.0, d.potential - d.overall)
        if margine < 0.5:
            continue
        passo = spinta * (margine / 12.0) * gs.rng.uniform(0.7, 1.6)
        for a in DRIVER_ATTRS:
            cur = getattr(d, a)
            setattr(d, a, min(99.0, cur + min(passo, max(0.0, d.potential - cur))))
        # il potenziale vero si scopre guidando: puo' essere piu' alto o meno
        d.potential = max(d.overall, min(97.0, d.potential + gs.rng.gauss(0.0, 1.6)))
        if team.is_player and passo > 1.2:
            msgs.append(f"Vivaio: {d.short} ha fatto un salto, adesso vale "
                        f"{d.overall:.0f} con {d.potential:.0f} di potenziale.")
    return msgs


def promote(gs, team, driver, seat: str = "riserva") -> tuple:
    """Porta un ragazzo del vivaio in prima squadra."""
    from . import market
    if driver.id not in team.academy:
        return False, "Non e' uno dei nostri ragazzi."
    posti = market.seats_of(team, seat)
    if len(posti) >= 2:
        return False, ("Non c'e' posto fra i titolari." if seat == "titolare"
                       else "Hai gia' due terzi piloti.")
    team.academy.remove(driver.id)
    driver.seat = seat
    driver.salary = round(max(driver.salary, driver.market_value *
                              (1.0 if seat == "titolare" else market.RESERVE_SHARE)), 2)
    driver.contract_until = max(driver.contract_until, gs.season + 2)
    posti.append(driver.id)
    quale = "titolare" if seat == "titolare" else "terzo pilota"
    return True, f"{driver.name} promosso a {quale}: {driver.salary:.2f} M$ all'anno."


def release(gs, team, driver) -> tuple:
    if driver.id not in team.academy:
        return False, "Non e' uno dei nostri ragazzi."
    team.academy.remove(driver.id)
    driver.team = None
    driver.seat = "titolare"
    gs.free_agents.append(driver)
    return True, f"{driver.name} lascia il vivaio."


# -------------------------------------------------------------- fine stagione
def end_season(gs) -> list:
    """Le categorie minori corrono, poi si tirano le somme del vivaio."""
    from . import serie
    msgs = list(serie.stagione(gs))
    for team in gs.teams.values():
        if not has(team):
            continue
        for d in list(roster(gs, team)):
            if d.age >= LEAVE_AGE:
                team.academy.remove(d.id)
                d.team = None
                d.seat = "titolare"
                gs.free_agents.append(d)
                if team.is_player:
                    msgs.append(f"Vivaio: {d.short} ha finito il percorso e "
                                f"lascia il programma.")
        quanti = 1 + int(gs.rng.random() < float(team.facilities.get("academy", 60.0)) / 130.0)
        nuovi = intake(gs, team, quanti)
        if nuovi and team.is_player:
            msgs.append("Vivaio: entrano " + ", ".join(d.short for d in nuovi) + ".")
    msgs += _poach(gs)
    return msgs


def _poach(gs) -> list:
    """Chi non ha vivaio si prende i ragazzi degli altri, pagandoli.

    E' quello che succede davvero: un giovane che va forte in Formula 2 lo
    guardano tutti, e chi ha un volante libero se lo compra.
    """
    msgs = []
    for team in gs.teams.values():
        if team.is_player or has(team) or team.reserves or gs.rng.random() > 0.35:
            continue
        candidati = [(t, d) for t in gs.teams.values() if has(t) and not t.is_player
                     for d in roster(gs, t) if d.overall > 68.0 and d.age >= 19]
        if not candidati:
            continue
        casa, ragazzo = max(candidati, key=lambda x: x[1].potential)
        prezzo = round(max(1.5, ragazzo.market_value * 1.8), 2)
        ok, _w = economy.can_afford(team, prezzo, gs, check_cap=False)
        if not ok:
            continue
        team.add_expense(f"Acquisto {ragazzo.last} dal vivaio {casa.short}", prezzo,
                         in_cap=False, category="cessioni")
        casa.add_income(f"Cessione {ragazzo.last}", prezzo, category="cessioni")
        casa.academy.remove(ragazzo.id)
        from . import market
        market._sign(gs, team, ragazzo,
                     round(max(0.4, ragazzo.market_value * market.RESERVE_SHARE), 2),
                     3, "riserva")
        msgs.append(f"{team.short} compra {ragazzo.name} dal vivaio di "
                    f"{casa.short} per {prezzo:.1f} M$.")
    return msgs


def ai_found(gs) -> list:
    """Le scuderie del computer aprono il vivaio quando se lo possono permettere."""
    msgs = []
    for team in gs.teams.values():
        if team.is_player or has(team) or gs.rng.random() > 0.30:
            continue
        ok, _why = can_found(gs, team)
        if not ok:
            continue
        done, msg = found(gs, team, f"{team.short} Driver Academy")
        if done:
            msgs.append(f"{team.short} apre il suo vivaio.")
    return msgs
