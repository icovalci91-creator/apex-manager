"""Sviluppo della vettura: allocazione risorse, pacchetti di aggiornamento, ATR."""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C
from . import economy

# tetto tecnico raggiungibile in un ciclo regolamentare
PERF_CEILING = 99.0

# Quanto invecchia la vettura in una stagione se non ci si investe. Tarato su
# quello che rende lo sviluppo: con circa 1,6 M$ a gara si sta in pari, sotto
# si arretra, sopra si guadagna. Una monoposto ferma non resta competitiva.
TECH_DECAY = 0.45


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


def next_era(gs):
    """Il prossimo ciclo tecnico.

    Oltre l'ultimo ciclo scritto nei dati la carriera continua, quindi i cicli
    successivi vengono immaginati: cadenza e natura seguono il ritmo storico,
    dove a una rivoluzione della power unit segue di solito un periodo di
    motori congelati in cui a decidere e' l'aerodinamica.
    """
    ciclo = gs.regulations.get("pending_cycle")
    if ciclo and ciclo.get("season"):
        from . import rules
        return {"from": ciclo["season"], "to": ciclo["season"] + 5,
                "label": "Ciclo in preparazione", "focus": rules.cycle_focus(gs),
                "reset_strength": min(0.95, 0.35 + 0.45 * ciclo["pressure"]),
                "in_discussione": True}
    eras = gs.history_data.setdefault("eras", [])
    for era in eras:
        if era["from"] > gs.season:
            return era
    return None


def seasons_to_reset(gs):
    era = next_era(gs)
    return None if era is None else era["from"] - gs.season


def prep_conversion(gs, team, era: dict) -> float:
    """Quanto rende un milione speso sul regolamento che verra'.

    Non tutti i reset premiano le stesse cose. Nel 2014 contava la power unit
    e chi non ce l'aveva ha inseguito per anni; nel 2022 i motori erano
    congelati e l'unica leva era il concetto aerodinamico. Una squadra forte
    nell'area giusta converte molto meglio le stesse risorse.
    """
    focus = era.get("focus") or {"pu": 0.34, "chassis": 0.33, "aero": 0.33}
    pu = team.pu_strength if team.works else 55.0
    val = (focus.get("aero", 0.0) * team.aero_strength
           + focus.get("chassis", 0.0) * team.mech_strength
           + focus.get("pu", 0.0) * pu)
    return val / 100.0


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
    rischio = base * (1.55 - 0.55 * quality - 0.30 * sim)
    # i chilometri di correlazione fatti in test tolgono rischio: e' il loro
    # scopo, misurare in pista quello che la galleria promette
    rischio *= 1.0 - 0.55 * max(0.0, min(1.0, team.correlation))
    return max(0.02, rischio)


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
            team.add_expense(f"Sviluppo: {pr.label}", round(slice_cost, 3), in_cap=True,
                             category="sviluppo")
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
    """Sviluppo continuo, diviso fra la vettura di oggi e il regolamento di domani.

    E' il dilemma classico della Formula 1: ogni milione speso sul progetto
    dell'anno prossimo e' un milione che non finisce sulla macchina con cui si
    corre adesso. La Brawn 2009 nacque da una stagione buttata via; la McLaren
    2013 dal non averlo fatto.
    """
    if budget <= 0:
        return
    team.add_expense("Sviluppo continuo", round(budget, 3), in_cap=True,
                     category="sviluppo")
    era = next_era(gs)
    share = max(0.0, min(0.90, team.next_reg_share)) if era is not None else 0.0
    if share > 0:
        reg_budget = budget * share
        team.reg_prep += reg_budget * team.dev_rate * prep_conversion(gs, team, era)
        budget -= reg_budget
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
        team.next_reg_share = ai_reg_share(gs, team)
        team.resource_alloc = alloc
        passive_development(gs, team, budget)
        advance_projects(gs, team)
        if not team.dev_projects and gs.rng.random() < 0.30:
            size = gs.rng.choice(["piccolo", "medio", "medio", "grande"])
            start_project(gs, team, weak, size)


def technological_decay(gs) -> float:
    """Invecchia le vetture di tutti di una stagione.

    Non e' usura: e' il resto del mondo che va avanti. Restare fermi significa
    arretrare, ed e' quello che rende obbligatorio reinvestire.
    """
    lost = 0.0
    for team in gs.teams.values():
        for p in team.car.parts.values():
            # chi sta in alto fa piu' fatica a restarci: il fronte si muove
            step = TECH_DECAY * (0.60 + 0.60 * p.perf / PERF_CEILING)
            new = max(40.0, p.perf - step)
            if team.is_player:
                lost += p.perf - new
            p.perf = new
    return lost / max(1, len(C.CAR_PARTS))


# Componenti che il regolamento consente di comprare dalla squadra maggiore:
# nella realta' sono cambio, sospensione posteriore e impianto frenante.
TRANSFERABLE = ("gearbox", "suspension", "brakes")


def sister_transfer(gs) -> list:
    """Le satellite montano i componenti trasferibili della sorella maggiore.

    Non e' un regalo: si comprano, e restano indietro di un passo rispetto
    all'originale. Ma per una squadra piccola vale piu' di quanto potrebbe
    progettare da sola.
    """
    msgs = []
    for team in gs.teams.values():
        parent = gs.teams.get(team.parent_team) if team.parent_team else None
        if parent is None or parent is team:
            continue
        for k in TRANSFERABLE:
            if k not in team.car.parts or k not in parent.car.parts:
                continue
            mio = team.car.parts[k]
            suo = parent.car.parts[k].perf * 0.97      # un passo indietro
            if suo > mio.perf:
                mio.perf = min(PERF_CEILING, mio.perf + (suo - mio.perf) * 0.8)
        if team.is_player:
            msgs.append(f"Dal gruppo {parent.short} arrivano cambio, sospensione "
                        f"posteriore e freni della stagione nuova.")
    return msgs


def ai_reg_share(gs, team) -> float:
    """Quanto il computer dirotta sul regolamento che verra'.

    Piu' il reset e' vicino, piu' si sposta. E chi non ha piu' niente da
    giocarsi nel campionato in corso stacca prima la spina alla vettura
    attuale: e' quello che fece la Brawn nel 2008.
    """
    # Il reset scatta a fine stagione, quindi l'ultimo anno utile per
    # prepararsi e' quello con left == 1: da li' in poi e' troppo tardi.
    left = seasons_to_reset(gs)
    if left is None or left > 3:
        return 0.0
    base = {3: 0.10, 2: 0.25, 1: 0.60}.get(left, 0.0)
    standings = gs.constructor_standings()
    leader = standings[0].points if standings else 0.0
    pos = gs.position_of(team.id)
    in_lotta = pos <= 3 and team.points > leader * 0.60
    tardi = gs.round > len(gs.tracks) * 0.55
    if in_lotta:
        base *= 0.55                       # si difende il campionato in corso
    elif tardi and pos > 4:
        base = min(0.85, base + 0.25)      # niente da perdere: tutto sull'anno nuovo
    return base


def regulation_reset(gs, strength: float, era: dict | None = None) -> list:
    """Un nuovo ciclo tecnico rimescola la griglia.

    Conta chi ci ha lavorato prima e quanto la squadra e' forte nell'area che
    il nuovo regolamento premia. Chi non ha preparato nulla il reset lo subisce
    invece di sfruttarlo.
    """
    vals = [t.car.rating for t in gs.teams.values()]
    mean = sum(vals) / len(vals)
    preps = [t.reg_prep for t in gs.teams.values()]
    best_prep = max(preps) or 1.0
    avg_prep = (sum(preps) / len(preps)) or 1.0
    news = []
    for team in gs.teams.values():
        quality = (0.45 * team.aero_strength + 0.35 * team.mech_strength
                   + 0.20 * team.dev_rate * 60.0) / 100.0
        # preparazione rispetto agli altri: negativa se sotto la media
        rel = (team.reg_prep - avg_prep) / max(best_prep, 1e-6)
        prep_bonus = rel * 16.0 * strength
        for p in team.car.parts.values():
            pull = (mean - p.perf) * strength * 0.55
            bonus = (quality - 0.75) * 14.0 * strength
            p.perf = max(45.0, min(PERF_CEILING,
                                   p.perf + pull + bonus + prep_bonus + gs.rng.gauss(0, 2.4)))
            p.condition = 100.0
        if team.is_player:
            if rel > 0.25:
                news.append("Il lavoro sul nuovo regolamento paga: siamo fra i piu' pronti.")
            elif rel < -0.25:
                news.append("Ci siamo fatti sorprendere: altri avevano cominciato molto prima.")
        team.reg_prep = 0.0
        team.next_reg_share = 0.0
    return news
