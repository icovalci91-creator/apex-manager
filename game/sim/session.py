"""Orchestrazione del weekend: prove libere, qualifica, griglia, gara."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .. import config as C
from ..model.car import SETUP_KEYS
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


# --------------------------------------------------------------- base lap
def base_lap_for(gs, team, track, weather: Weather) -> float:
    car = team.car
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
        pit = 3.30 - 1.15 * (team.pit_strength / 100.0)
        for did in team.drivers:
            d = gs.drivers.get(did)
            if not d:
                continue
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
def run_practice(gs, ws: WeekendState, delegate_player: bool = True) -> list:
    """Una sessione di prove: affina l'assetto e produce riscontri tecnici."""
    track = ws.track
    notes = []
    for team in gs.teams.values():
        car = team.car
        opt = car.optimal_setup(track)
        drivers = gs.drivers_of(team.id)
        fb = sum(d.feedback for d in drivers) / max(1, len(drivers))
        quality = 0.35 + 0.45 * (team.setup_strength / 100.0) + 0.20 * (fb / 100.0)
        quality = min(0.97, quality * (0.75 + 0.25 * (ws.practice_done + 1) / 3.0))
        if team.id == gs.player_team and not delegate_player:
            quality *= 0.55        # il giocatore lavora da solo: gli ingegneri aiutano meno
        for k in SETUP_KEYS:
            cur = car.setup.get(k, 50.0)
            car.setup[k] = cur + (opt[k] - cur) * quality * gs.rng.uniform(0.6, 1.0)
        car.evaluate_setup(track)
        car.wear(0.55, track)

    ws.practice_done += 1
    pt = gs.player
    q = pt.car.setup_quality
    eng = pt.role("technical_director")
    who = eng.name if eng else "Il muretto"
    if q > 0.9:
        notes.append(f"{who}: assetto in finestra, la macchina risponde bene.")
    elif q > 0.7:
        notes.append(f"{who}: ci siamo quasi, manca un po' di equilibrio in percorrenza.")
    else:
        notes.append(f"{who}: siamo fuori finestra, servono modifiche importanti.")
    notes.extend(setup_hints(pt.car, track))
    ws.practice_notes = notes
    return notes


def setup_hints(car, track) -> list:
    """Indicazioni comprensibili su cosa cambiare nell'assetto."""
    opt = car.optimal_setup(track)
    hints = []
    phrase = {
        "wing": ("troppo carico: siamo lenti sui rettilinei", "poco carico: la macchina scivola in curva"),
        "ride_height": ("troppo alta: perdiamo carico dal fondo", "troppo bassa: strisciamo sui cordoli"),
        "stiffness": ("troppo rigida: salta sulle sconnessioni", "troppo morbida: rolla e consuma le gomme"),
        "camber": ("campanatura eccessiva: surriscalda l'anteriore", "campanatura scarsa: manca inserimento"),
        "gearing": ("rapporti troppo lunghi: non spinge in uscita", "rapporti troppo corti: tocchiamo il limitatore"),
        "brake_bias": ("freno troppo indietro: instabile in staccata", "freno troppo avanti: blocca l'anteriore"),
    }
    for k, (hi, lo) in phrase.items():
        d = car.setup.get(k, 50.0) - opt[k]
        if d > 14:
            hints.append(f"- {SETUP_KEYS[k]}: {hi}")
        elif d < -14:
            hints.append(f"- {SETUP_KEYS[k]}: {lo}")
    if not hints:
        hints.append("- Nessuna correzione rilevante: possiamo lavorare sul passo gara.")
    return hints


def auto_setup(gs, team, track, quality: float | None = None) -> None:
    """Delega completamente l'assetto agli ingegneri."""
    car = team.car
    opt = car.optimal_setup(track)
    q = quality if quality is not None else min(0.98, 0.55 + 0.45 * (team.setup_strength / 100.0))
    for k in SETUP_KEYS:
        car.setup[k] = opt[k] + gs.rng.gauss(0.0, (1.0 - q) * 22.0)
        car.setup[k] = max(0.0, min(100.0, car.setup[k]))
    car.evaluate_setup(track)


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

    for phase, keep in enumerate(cuts + [0]):
        results = []
        for e in alive:
            t = e.base_lap
            t += (85.0 - e.skill) * 0.046
            t += 8.0 * 0.032                                  # serbatoio da qualifica
            t -= 0.35                                          # gomma nuova soft, pista gommata
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
    ws.pole = ws.grid[0]
    ws.quali_done = True
    for team in gs.teams.values():
        team.car.wear(0.4, track)
    return ws.grid


# -------------------------------------------------------------------- gara
def plan_strategy(gs, e: Entrant, track, laps: int, weather: Weather) -> list:
    """Piano soste scelto dal muretto: dipende da pista, gomme e qualita' dello stratega."""
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
    if stops == 1:
        start, second = ("medium", "hard") if wear_t > 0.5 else ("soft", "medium")
        lap = int(laps * gs.rng.uniform(0.36, 0.52) + gs.rng.gauss(0, 3.0 * noise))
        plan = [(max(6, min(laps - 5, lap)), second)]
    else:
        start = "soft" if wear_t < 0.8 else "medium"
        l1 = int(laps * gs.rng.uniform(0.24, 0.32) + gs.rng.gauss(0, 2.5 * noise))
        l2 = int(laps * gs.rng.uniform(0.58, 0.68) + gs.rng.gauss(0, 3.0 * noise))
        plan = [(max(5, l1), "medium"), (max(l1 + 6, min(laps - 5, l2)), "hard")]
    e.tyre = start
    e.used_compounds.add(start)
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
