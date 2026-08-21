"""Simulazione del fine settimana di gara.

La gara e' continua: ogni vettura avanza in metri e i sorpassi si risolvono
quando due monoposto sono realmente a contatto, cosi' l'animazione 2D e il
risultato provengono dalla stessa simulazione.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .. import config as C

# quanto pesa un punto di valutazione pilota sul giro (secondi)
DRIVER_S_PER_POINT = 0.046
FUEL_S_PER_KG = 0.032
BURN_KG_PER_LAP = 1.75


# --------------------------------------------------------------------- meteo
@dataclass
class Weather:
    label: str = "sereno"
    wet: float = 0.0          # 0 asciutto .. 1 diluvio
    track_temp: float = 30.0
    air_temp: float = 22.0
    rain_forecast: list = field(default_factory=list)

    @classmethod
    def generate(cls, track, rng: random.Random) -> "Weather":
        t = track.traits
        base_wet_chance = 0.18 + 0.12 * (1.0 - t.get("power", 0.5))
        if track.id in ("spa", "silverstone", "interlagos", "suzuka", "zandvoort", "shanghai"):
            base_wet_chance += 0.14
        if track.id in ("bahrain", "jeddah", "lusail", "yasmarina", "lasvegas"):
            base_wet_chance -= 0.14
        wet = 0.0
        label = "sereno"
        r = rng.random()
        if r < base_wet_chance * 0.45:
            wet, label = rng.uniform(0.55, 0.95), "pioggia intensa"
        elif r < base_wet_chance:
            wet, label = rng.uniform(0.20, 0.55), "pioggia leggera"
        elif r < base_wet_chance + 0.25:
            label = "nuvoloso"
        elif r < base_wet_chance + 0.35:
            label = "coperto"
        air = rng.uniform(12, 34) - 8 * wet
        return cls(label=label, wet=wet, track_temp=air + rng.uniform(6, 18) - 10 * wet, air_temp=air)


# ------------------------------------------------------------------ concorrente
@dataclass
class Entrant:
    driver_id: str
    team_id: str
    code: str
    name: str
    colour: tuple
    number: int

    base_lap: float = 90.0        # giro di riferimento a secco, serbatoio vuoto
    skill: float = 80.0
    consistency: float = 80.0
    tyre_skill: float = 80.0
    aggression: float = 70.0
    racecraft: float = 80.0
    wet_skill: float = 80.0
    stamina: float = 90.0
    reliability: float = 0.95
    pit_time: float = 2.6
    strategy_skill: float = 75.0

    # stato in gara
    dist: float = 0.0
    lap: int = 0
    position: int = 1
    tyre: str = "medium"
    tyre_age: float = 0.0
    tyre_life: float = 25.0
    fuel: float = 100.0
    total_time: float = 0.0
    last_lap: float = 0.0
    best_lap: float = 999.0
    status: str = "running"       # running | pitting | retired | finished
    dnf_reason: str = ""
    pit_timer: float = 0.0
    stops: int = 0
    plan: list = field(default_factory=list)     # [(giro, mescola)]
    used_compounds: set = field(default_factory=set)
    overtake_cd: float = 0.0
    dirty_air: float = 0.0
    clean_lap: float = 90.0     # passo in aria libera, usato per valutare i duelli
    damage: float = 0.0
    push_mode: float = 1.0        # 0.9 conserva .. 1.1 attacca
    grid: int = 1
    finished_time: float = 0.0
    is_player: bool = False
    laps_led: int = 0

    def compound_state(self) -> float:
        """1.0 = gomma fresca, cala fino allo 0 dopo il degrado."""
        x = self.tyre_age / max(1.0, self.tyre_life)
        if x <= 1.0:
            return 1.0 - 0.11 * x * x
        return max(0.35, 0.89 - 0.55 * (x - 1.0))


# ------------------------------------------------------------------ simulazione
class RaceSim:
    def __init__(self, gs, track, entrants: list, weather: Weather, laps: int,
                 kind: str = "gp", rng: random.Random | None = None):
        self.gs = gs
        self.track = track
        self.entrants = entrants
        self.weather = weather
        self.laps = laps
        self.kind = kind
        self.rng = rng or random.Random()
        self.time = 0.0
        self.track_len = track.length_km * 1000.0
        self.safety_car = 0.0
        self.sc_laps = 0
        self.vsc = False
        self.events: list = []
        self.finished = False
        self.classification: list = []
        self.grip = 0.965          # evoluzione pista
        self.leader_lap = 0
        self._order_cache = list(entrants)

    # ------------------------------------------------------------ utilita'
    def log(self, text: str, kind: str = "info") -> None:
        self.events.insert(0, {"lap": self.leader_lap + 1, "text": text, "kind": kind})
        del self.events[60:]

    def order(self) -> list:
        live = [e for e in self.entrants if e.status != "retired"]
        live.sort(key=lambda e: -e.dist)
        done = [e for e in self.entrants if e.status == "retired"]
        done.sort(key=lambda e: -e.dist)
        return live + done

    # -------------------------------------------------------- tempo sul giro
    def lap_time_of(self, e: Entrant) -> float:
        t = e.base_lap
        t += (85.0 - e.skill) * DRIVER_S_PER_POINT
        t += e.fuel * FUEL_S_PER_KG
        comp = C.COMPOUNDS[e.tyre]
        t += (1.0 - comp["grip"]) * 28.0
        t += (1.0 - e.compound_state()) * 22.0
        t += e.damage * 0.06
        t *= (2.0 - self.grip) if self.grip < 1.0 else 1.0
        t *= 1.0 / max(0.90, min(1.10, e.push_mode))
        clean = t
        t += e.dirty_air * 0.42
        if self.weather.wet > 0.05:
            mismatch = 0.0
            if self.weather.wet > 0.45 and e.tyre != "wet":
                mismatch = 12.0 if e.tyre in ("soft", "medium", "hard") else 2.5
            elif 0.15 < self.weather.wet <= 0.45 and e.tyre not in ("inter", "wet"):
                mismatch = 7.0
            elif self.weather.wet <= 0.15 and e.tyre in ("inter", "wet"):
                mismatch = 4.0
            t += mismatch
            t += (85.0 - e.wet_skill) * 0.06 * self.weather.wet * 4.0
        if self.safety_car > 0:
            t *= 1.42 if not self.vsc else 1.30
        var = self.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.006)
        e.clean_lap = clean
        return max(20.0, t + var)

    # ----------------------------------------------------------------- passo
    def update(self, dt: float) -> None:
        if self.finished:
            return
        if self.classification and all(
                x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True
            return
        self.time += dt
        self.grip = min(1.0, self.grip + dt * 0.000045)
        if self.safety_car > 0:
            self.safety_car = max(0.0, self.safety_car - dt)
            if self.safety_car == 0.0:
                self.log("Safety car rientrata: si riparte!", "sc")
                self.vsc = False

        for e in self.entrants:
            if e.status in ("retired", "finished"):
                continue
            if e.status == "pitting":
                e.pit_timer -= dt
                e.total_time += dt
                if e.pit_timer <= 0:
                    e.status = "running"
                continue

            lt = self.lap_time_of(e)
            e.last_lap = lt
            v = self.track_len / lt
            e.dist += v * dt
            e.total_time += dt
            e.overtake_cd = max(0.0, e.overtake_cd - dt)

            wear_rate = self._wear_rate(e)
            e.tyre_age += wear_rate * dt / lt
            e.fuel = max(0.0, e.fuel - BURN_KG_PER_LAP * dt / lt)

            new_lap = int(e.dist // self.track_len)
            if new_lap > e.lap:
                e.lap = new_lap
                self._on_lap_complete(e, lt)

        self._resolve_battles(dt)
        self._update_positions()
        self._maybe_incident(dt)

    def _wear_rate(self, e: Entrant) -> float:
        comp = C.COMPOUNDS[e.tyre]
        base = comp["wear"] * (0.55 + 0.9 * self.track.traits.get("tyre_wear", 0.6))
        skill = 1.30 - 0.55 * (e.tyre_skill / 100.0)
        push = 0.75 + 0.55 * e.push_mode
        sc = 0.45 if self.safety_car > 0 else 1.0
        wet = 1.0 - 0.35 * self.weather.wet
        return base * skill * push * sc * wet

    def _on_lap_complete(self, e: Entrant, lt: float) -> None:
        if lt < e.best_lap:
            e.best_lap = lt
        if e.position == 1:
            e.laps_led += 1
        self.leader_lap = max(self.leader_lap, min(e.lap, self.laps))

        # rottura meccanica
        risk = (1.0 - e.reliability) * 0.030 * (1.0 + e.damage / 70.0)
        if self.rng.random() < risk:
            e.status = "retired"
            e.dnf_reason = self.rng.choice([
                "problema idraulico", "cedimento power unit", "surriscaldamento",
                "guasto al cambio", "perdita di pressione olio", "rottura sospensione"])
            self.log(f"RITIRO: {e.name} - {e.dnf_reason}", "dnf")
            self._maybe_safety_car(0.30)
            return

        # errore del pilota
        err = (100.0 - e.consistency) * 0.00013 * (0.6 + 0.8 * e.push_mode)
        err *= 1.0 + 2.2 * self.weather.wet
        err *= 1.0 + (1.0 - e.compound_state()) * 1.2
        if self.rng.random() < err:
            if self.rng.random() < 0.14:
                e.status = "retired"
                e.dnf_reason = "incidente"
                self.log(f"INCIDENTE: {e.name} finisce contro le barriere!", "dnf")
                self._maybe_safety_car(0.65)
            else:
                loss = self.rng.uniform(1.5, 6.0)
                e.dist -= loss * (self.track_len / lt)
                e.damage = min(100.0, e.damage + self.rng.uniform(2, 14))
                self.log(f"Errore di {e.name}: perde {loss:.1f}s", "warn")

        if e.lap >= self.laps:
            e.status = "finished"
            over = e.dist - self.laps * self.track_len
            e.finished_time = e.total_time - over / max(1.0, self.track_len / max(30.0, lt))
            if not self.classification:
                self.log(f"BANDIERA A SCACCHI: vince {e.name}!", "flag")
            self.classification.append(e)
            if len([x for x in self.entrants if x.status in ("finished", "retired")]) >= len(self.entrants):
                self.finished = True
            return

        self._check_pit(e)
        if all(x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True

    # ------------------------------------------------------------- strategia
    def _check_pit(self, e: Entrant) -> None:
        target = None
        for lap, comp in list(e.plan):
            if e.lap >= lap:
                target = comp
                e.plan.remove((lap, comp))
                break
        # sosta d'emergenza se la gomma e' andata
        if target is None and e.tyre_age > e.tyre_life * 1.35 and e.lap < self.laps - 2:
            target = self._pick_compound(e)
        # cambio per la pioggia
        if target is None:
            if self.weather.wet > 0.45 and e.tyre != "wet":
                target = "wet"
            elif 0.18 < self.weather.wet <= 0.45 and e.tyre not in ("inter", "wet"):
                target = "inter"
            elif self.weather.wet < 0.10 and e.tyre in ("inter", "wet") and e.lap < self.laps - 3:
                target = self._pick_compound(e)
        if target is None:
            return
        # opportunismo: sotto safety car si guadagna tempo
        e.status = "pitting"
        stop = e.pit_time + max(0.0, self.rng.gauss(0.25, 0.35))
        if self.rng.random() < 0.035:
            stop += self.rng.uniform(2.0, 9.0)
            self.log(f"Sosta lenta per {e.name}!", "warn")
        loss = self.track.pit_loss * (0.62 if self.safety_car > 0 else 1.0)
        e.pit_timer = stop + loss
        e.dist -= (stop + loss) * (self.track_len / max(30.0, e.last_lap))
        e.tyre = target
        e.used_compounds.add(target)
        e.tyre_age = 0.0
        e.tyre_life = self._tyre_life(e, target)
        e.stops += 1
        self.log(f"{e.name} ai box: monta {C.COMPOUNDS[target]['label']}", "pit")

    def _pick_compound(self, e: Entrant) -> str:
        remaining = self.laps - e.lap
        if self.weather.wet > 0.45:
            return "wet"
        if self.weather.wet > 0.18:
            return "inter"
        if remaining <= 16:
            return "soft"
        if remaining <= 30:
            return "medium"
        return "hard"

    def _tyre_life(self, e: Entrant, comp: str) -> float:
        base = {"soft": 17.0, "medium": 26.0, "hard": 37.0, "inter": 22.0, "wet": 26.0}[comp]
        wear_t = self.track.traits.get("tyre_wear", 0.6)
        return base * (1.35 - 0.62 * wear_t) * (0.78 + 0.42 * e.tyre_skill / 100.0)

    # --------------------------------------------------------------- duelli
    def _resolve_battles(self, dt: float) -> None:
        live = [e for e in self.entrants if e.status == "running"]
        live.sort(key=lambda e: -e.dist)
        ot_track = self.track.traits.get("overtaking", 0.5)
        for i in range(1, len(live)):
            ahead, behind = live[i - 1], live[i]
            gap_m = ahead.dist - behind.dist
            if gap_m > 90.0 or gap_m < 0:
                behind.dirty_air = max(0.0, behind.dirty_air - dt * 1.5)
                continue
            behind.dirty_air = min(1.0, behind.dirty_air + dt * 0.9) * (1.0 - 0.55 * ot_track)
            if self.safety_car > 0 or behind.overtake_cd > 0 or gap_m > 45.0:
                continue
            pace = ahead.clean_lap - behind.clean_lap
            if pace <= -0.15:
                continue
            chance = dt * (0.20 + 0.85 * ot_track) * min(1.0, max(0.08, pace + 0.15) / 0.9)
            chance *= 0.65 + 0.7 * (behind.racecraft / 100.0)
            chance *= 0.8 + 0.5 * (behind.aggression / 100.0)
            chance /= max(0.55, 0.6 + 0.6 * (ahead.racecraft / 100.0))
            if self.rng.random() < chance:
                behind.dist, ahead.dist = ahead.dist + 4.0, behind.dist - 4.0
                behind.overtake_cd = 4.0
                ahead.overtake_cd = 2.0
                self.log(f"SORPASSO: {behind.name} passa {ahead.name}", "pass")
                if self.rng.random() < 0.016 * (behind.aggression / 100.0) * (1.0 + self.weather.wet):
                    dmg = self.rng.uniform(4, 22)
                    behind.damage = min(100.0, behind.damage + dmg)
                    ahead.damage = min(100.0, ahead.damage + dmg * 0.8)
                    self.log(f"Contatto tra {behind.name} e {ahead.name}!", "warn")
                    self._maybe_safety_car(0.35)

    def _update_positions(self) -> None:
        for i, e in enumerate(self.order(), 1):
            e.position = i

    def _maybe_incident(self, dt: float) -> None:
        if self.safety_car > 0:
            return
        base = 0.000018 * (1.0 + 2.2 * self.weather.wet)
        base *= 1.0 + 1.4 * (1.0 - self.track.traits.get("overtaking", 0.5))
        if self.rng.random() < base * dt * 0.55:
            self._maybe_safety_car(0.45, forced=True)

    def _maybe_safety_car(self, p: float, forced: bool = False) -> None:
        if self.safety_car > 0:
            return
        if forced or self.rng.random() < p:
            vsc = self.rng.random() < 0.45
            self.vsc = vsc
            self.safety_car = self.rng.uniform(120.0, 260.0)
            self.log("Virtual Safety Car" if vsc else "SAFETY CAR IN PISTA", "sc")

    # -------------------------------------------------------------- risultati
    def fast_forward(self, max_steps: int = 60000, dt: float = 1.0) -> None:
        steps = 0
        while not self.finished and steps < max_steps:
            self.update(dt)
            steps += 1
        self.finished = True

    def result_order(self) -> list:
        fin = [e for e in self.entrants if e.status == "finished"]
        fin.sort(key=lambda e: e.finished_time)
        ret = [e for e in self.entrants if e.status not in ("finished",)]
        ret.sort(key=lambda e: (-e.lap, -e.dist))
        return fin + ret
