"""Orchestrazione del weekend: prove libere, qualifica, griglia, gara."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .. import config as C
from .weekend import BURN_KG_PER_LAP, Entrant, RaceSim, Weather


@dataclass
class WeekendState:
    track: object
    weather: Weather
    practice_done: int = 0
    quali_done: bool = False
    grid: list = field(default_factory=list)        # driver_id in ordine
    pole: str = ""
    quali_times: dict = field(default_factory=dict)
    practice_notes: list = field(default_factory=list)
    sprint_done: bool = False
    race: RaceSim | None = None
    sprint: RaceSim | None = None
    grid_notes: list = field(default_factory=list)   # penalizzazioni scontate in griglia
    tyre_choice: dict = field(default_factory=dict)  # team_id -> set scelti per mescola
    tyre_stock: dict = field(default_factory=dict)   # driver_id -> set ancora a disposizione
    tyres_published: bool = False                    # le scelte sono state rese pubbliche


# --------------------------------------------------------------- base lap
def base_lap_for(gs, team, track, weather: Weather) -> float:
    from ..core import powertrain
    car = team.car
    # rinfrescata qui: se il reparto motori e' cambiato (ingaggi, debutto della
    # propria unita') l'integrazione deve valere gia' da questo weekend
    car.pu_integration = powertrain.integration(gs, team)
    old_fuel = car.fuel_kg
    car.fuel_kg = 0.0
    car.evaluate_setup(track)
    t, _, _ = track.lap_model(car, wet=weather.wet)
    car.fuel_kg = old_fuel
    return t / car.apply_setup_effects()


def build_entrants(gs, track, weather: Weather) -> list:
    out = []
    for team in gs.teams.values():
        base = base_lap_for(gs, team, track, weather)
        base += gs.rng.gauss(0.0, 0.13)          # come lavora il pacchetto su questa pista
        pit = (3.30 - 1.15 * (team.pit_strength / 100.0)
               + float(gs.regulations.get("pit_lane_penalty_s", 0.0)))
        for d in gs.lineup_of(team.id):
            col = _hex(team.colour)
            out.append(Entrant(
                driver_id=d.id, team_id=team.id, code=d.code, name=d.short,
                colour=col, number=d.number, base_lap=base,
                skill=d.race_rating(weather.wet) - gs.rng.gauss(0.0, 1.3),
                consistency=d.consistency,
                tyre_skill=d.tyre_mgmt, aggression=d.aggression, racecraft=d.racecraft,
                wet_skill=d.wet, stamina=d.fitness, reliability=team.car.reliability,
                pit_time=pit, strategy_skill=team.strategy_strength,
                is_player=(team.id == gs.player_team),
            ))
    return out


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------ prove libere
def practice_sessions(track) -> int:
    """Quante prove libere concede il regolamento su questo weekend.

    In un fine settimana sprint ce n'e' una sola: si va in parco chiuso subito
    dopo, quindi quello che non si e' preparato prima non si recupera piu'.
    """
    return 1 if track.sprint else 3


def run_practice(gs, ws: WeekendState, delegate_player: bool = True) -> list:
    """Una sessione di prove: la pista risponde e l'assetto si avvicina.

    Non si scopre l'assetto giusto guardandolo: si scopre girandoci. Quello che
    il reparto crede - l'assetto sulla carta preparato al simulatore - viene
    corretto da quello che dicono i piloti e i dati, e i meccanici montano sulla
    macchina quello a cui si e' arrivati.
    """
    from ..core import setup as SETUP
    track = ws.track
    notes = []
    for team in gs.teams.values():
        drivers = gs.drivers_of(team.id)
        fb = sum(d.feedback for d in drivers) / max(1, len(drivers))
        SETUP.learn_from_track(gs, team, track, fb)
        quota = 1.0
        if team.id == gs.player_team and not delegate_player:
            quota = 0.45      # il giocatore tiene in mano i regolatori
        SETUP.apply_paper(team, quota)
        team.car.evaluate_setup(track)
        team.car.wear(0.55, track)

    from ..core import tyres
    tyres.spend_practice(gs, ws)
    ws.practice_done += 1
    pt = gs.player
    q = SETUP.believed_quality(pt)
    eng = pt.role("technical_director")
    who = eng.name if eng else "Il muretto"
    if q > 0.9:
        notes.append(f"{who}: assetto in finestra, la macchina risponde bene.")
    elif q > 0.7:
        notes.append(f"{who}: ci siamo quasi, manca un po' di equilibrio in percorrenza.")
    else:
        notes.append(f"{who}: siamo fuori finestra, servono modifiche importanti.")
    notes.extend(SETUP.hints(pt, track))
    ws.practice_notes = notes
    return notes


def setup_hints(team, track) -> list:
    """Indicazioni comprensibili su cosa cambiare, secondo il reparto."""
    from ..core import setup as SETUP
    return SETUP.hints(team, track)


def auto_setup(gs, team, track, quality: float | None = None) -> None:
    """Monta l'assetto che il reparto ritiene giusto per questa pista."""
    from ..core import setup as SETUP
    SETUP.ensure_paper(gs, team, track)
    SETUP.apply_paper(team)
    team.car.evaluate_setup(track)


# ---------------------------------------------------------------- qualifica
def run_qualifying(gs, ws: WeekendState) -> list:
    track, weather = ws.track, ws.weather
    ents = build_entrants(gs, track, weather)
    pool = {e.driver_id: e for e in ents}
    alive = list(ents)
    times = {}
    reached = {}          # driver_id -> ultimo turno disputato (0 = Q1, 2 = Q3)
    n = len(ents)
    cuts = [max(10, n - 6), 10]

    from ..core import tyres
    for phase, keep in enumerate(cuts + [0]):
        results = []
        for e in alive:
            t = e.base_lap
            t += (85.0 - e.skill) * 0.046
            t += 8.0 * 0.032                                  # serbatoio da qualifica
            # con cosa si scende in pista dipende da cosa e' rimasto nel camion
            mescola = tyres.quali_run(gs, ws, e.driver_id) if ws.tyre_stock else "soft"
            t -= tyres.QUALI_GAIN.get(mescola, 0.35)
            t *= 1.0 - 0.0016 * phase                          # evoluzione pista tra i turni
            if weather.wet > 0.05:
                t += (85.0 - e.wet_skill) * 0.06 * weather.wet * 4.0
            t += gs.rng.gauss(0.0, 0.21 + (100.0 - e.consistency) * 0.005)
            if gs.rng.random() < 0.020 + (100.0 - e.consistency) * 0.0009:
                t += gs.rng.uniform(0.4, 2.4)                  # giro sporcato
            results.append((t, e))
        results.sort(key=lambda x: x[0])
        for t, e in results:
            times[e.driver_id] = t
            reached[e.driver_id] = phase
        if keep == 0:
            break
        alive = [e for _, e in results[:keep]]

    # chi supera il taglio parte sempre davanti a chi e' stato eliminato prima,
    # anche quando nel turno buono ha girato piu' lento
    order = sorted(times.items(), key=lambda kv: (-reached[kv[0]], kv[1]))
    ws.grid = [d for d, _ in order]
    ws.quali_times = times
    # la pole resta a chi ha fatto il tempo: le penalita' spostano la griglia,
    # non cancellano il giro
    ws.pole = ws.grid[0]
    from ..core import penalties
    ws.grid, ws.grid_notes = penalties.apply_grid_penalties(gs, ws.grid)
    ws.quali_done = True
    for team in gs.teams.values():
        team.car.wear(0.4, track)
    return ws.grid


# -------------------------------------------------------------------- gara
def plan_strategy(gs, e: Entrant, track, laps: int, weather: Weather) -> list:
    """Piano soste scelto dal muretto: dipende da pista, gomme e da cosa c'e' ancora.

    Il piano non si disegna sulla lavagna: si disegna su quello che e' rimasto
    nel camion. Chi ha bruciato le morbide il venerdi' la domenica parte con
    quello che ha.
    """
    if weather.wet > 0.45:
        e.tyre = "wet"
        return []
    if weather.wet > 0.18:
        e.tyre = "inter"
        return []
    wear_t = track.traits.get("tyre_wear", 0.6)
    stops = 1 if wear_t < 0.62 else 2
    if track.id == "monaco":
        stops = 1
    if wear_t > 0.88:
        stops = 2
    noise = (100.0 - e.strategy_skill) / 100.0
    plan = []
    # i set si prenotano mano a mano: quello montato alla partenza non e' piu'
    # disponibile per la sosta, ed e' cosi' che un venerdi' speso male si paga
    # la domenica
    resto = dict(e.stock) if e.stock else None

    def prendi(prefer, diverso_da=None):
        """Prenota la prima mescola che si ha davvero, fra quelle che si vorrebbero."""
        if resto is None:
            return prefer[0]
        ordine = list(prefer) + [m for m in ("medium", "hard", "soft") if m not in prefer]
        # il regolamento vuole due mescole diverse in gara: se si puo', si cambia
        preferite = [m for m in ordine if m != diverso_da] + ([diverso_da] if diverso_da else [])
        for m in preferite:
            if m and resto.get(m, 0) > 0:
                resto[m] -= 1
                return m
        return prefer[0]

    if stops == 1:
        if wear_t > 0.5:
            start = prendi(("medium", "soft"))
            second = prendi(("hard", "medium"), diverso_da=start)
        else:
            start = prendi(("soft", "medium"))
            second = prendi(("medium", "hard"), diverso_da=start)
        lap = int(laps * gs.rng.uniform(0.36, 0.52) + gs.rng.gauss(0, 3.0 * noise))
        plan = [(max(6, min(laps - 5, lap)), second)]
    else:
        start = prendi(("soft", "medium")) if wear_t < 0.8 else prendi(("medium", "hard"))
        l1 = int(laps * gs.rng.uniform(0.24, 0.32) + gs.rng.gauss(0, 2.5 * noise))
        l2 = int(laps * gs.rng.uniform(0.58, 0.68) + gs.rng.gauss(0, 3.0 * noise))
        uno = prendi(("medium", "hard"), diverso_da=start)
        due = prendi(("hard", "medium"))
        plan = [(max(5, l1), uno), (max(l1 + 6, min(laps - 5, l2)), due)]
    e.tyre = start
    e.used_compounds.add(start)
    if e.stock:
        e.stock[start] = max(0, e.stock.get(start, 0) - 1)
    return plan


def race_laps(gs, track, kind: str = "gp") -> int:
    """Giri effettivi, ridotti secondo la durata scelta dal giocatore."""
    full = track.laps if kind == "gp" else max(10, int(100.0 / track.length_km))
    factor = float(getattr(gs, "race_distance", 1.0))
    return max(3, int(round(full * factor)))


def make_race(gs, ws: WeekendState, kind: str = "gp") -> RaceSim:
    track, weather = ws.track, ws.weather
    laps = race_laps(gs, track, kind)
    ents = build_entrants(gs, track, weather)
    by_id = {e.driver_id: e for e in ents}
    grid = ws.grid or list(by_id.keys())

    ordered = []
    for i, did in enumerate(grid):
        e = by_id.get(did)
        if not e:
            continue
        e.grid = i + 1
        e.dist = -i * 8.0
        # benzina per i giri che si corrono davvero, con un filo di margine:
        # guidando normale si arriva, attaccando tutta la gara no
        e.fuel = min(C.FUEL_MASS_KG, laps * BURN_KG_PER_LAP * 1.04)
        e.stock = ws.tyre_stock.get(did) if ws.tyre_stock else None
        e.plan = plan_strategy(gs, e, track, laps, weather) if kind == "gp" else []
        e.tyre_life = 25.0
        ordered.append(e)

    sim = RaceSim(gs, track, ordered, weather, laps, kind=kind, rng=gs.rng)
    # il serbatoio e' quello che e': il consumo si tara su di lui lasciando un
    # 10% di riserva. Basta per attaccare in un terzo dei giri, non per tutta
    # la gara: chi ci prova resta a piedi prima della bandiera.
    if ordered:
        sim.burn_per_lap = ordered[0].fuel / (laps * 1.10)
    for e in ordered:
        e.tyre_life = sim._tyre_life(e, e.tyre)
    sim.log(f"Semaforo verde a {track.name} - {laps} giri - {weather.label}", "flag")
    return sim
