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

from ..core.penalties import INFRAZIONI as PENALTY_RULES

PENALTY_LABELS = {k: v["label"] for k, v in PENALTY_RULES.items()}

# quanto pesa un punto di valutazione pilota sul giro (secondi)
DRIVER_S_PER_POINT = 0.046
FUEL_S_PER_KG = 0.032
BURN_KG_PER_LAP = 1.75

# Modalita' di guida (0.9 conserva, 1.0 normale, 1.1 attacca). Attaccare deve
# valere poco piu' di un secondo sul giro e costare caro in gomme e benzina:
# e' una scelta, non un pulsante che regala tempo.
PUSH_S_PER_LAP = 7.5      # 0.1 di push_mode = 0.75 s sul giro
PUSH_WEAR_EXP = 2.5       # attaccare consuma circa il 27% di gomma in piu'
PUSH_FUEL_EXP = 2.5       # e altrettanta benzina
DRY_TANK_PENALTY = 8.0    # secondi al giro quando il serbatoio e' vuoto


# --------------------------------------------------------------------- meteo
@dataclass
class Weather:
    label: str = "sereno"
    wet: float = 0.0          # 0 asciutto .. 1 diluvio
    track_temp: float = 30.0
    air_temp: float = 22.0
    wind: float = 8.0         # km/h: quanto e' ballerina la macchina in curva
    cloud: float = 0.2        # 0 sole pieno .. 1 coperto: scalda l'asfalto o no
    rain_forecast: list = field(default_factory=list)

    @classmethod
    def generate(cls, track, rng: random.Random) -> "Weather":
        """Il tempo che fa dove e quando si corre davvero.

        Non e' un numero a caso fra dodici e trentaquattro gradi: Las Vegas si
        corre di notte a novembre e Singapore col buio in ottobre, e sono due
        mondi. Ogni circuito porta con se' la temperatura del suo mese, quanto
        piove da quelle parti e quanto tira vento; il resto - sole o nuvole,
        acquazzone o no - cambia da un fine settimana all'altro.
        """
        clima = getattr(track, "climate", None) or {}
        media = float(clima.get("temp", 22.0))
        oscilla = float(clima.get("swing", 6.0))
        pioggia = float(clima.get("rain", 0.20))
        vento_base = float(clima.get("wind", 10.0))

        wet = 0.0
        label = "sereno"
        cloud = max(0.0, min(1.0, rng.betavariate(2.0, 3.5)))
        r = rng.random()
        if r < pioggia * 0.40:
            wet, label, cloud = rng.uniform(0.55, 0.95), "pioggia intensa", 1.0
        elif r < pioggia:
            wet, label, cloud = rng.uniform(0.20, 0.55), "pioggia leggera", 0.9
        elif r < pioggia + 0.22:
            label, cloud = "nuvoloso", max(cloud, 0.55)
        elif r < pioggia + 0.32:
            label, cloud = "coperto", max(cloud, 0.80)
        else:
            cloud = min(cloud, 0.35)

        air = rng.gauss(media, oscilla * 0.45) - 4.0 * wet - 2.0 * cloud
        # l'asfalto prende il sole: di giorno arriva a venti gradi sopra
        # all'aria, di notte a pochi, e sotto la pioggia si raffredda
        sole = (0.30 if getattr(track, "night", False) else 1.0) * (1.0 - 0.75 * cloud)
        track_temp = air + 3.0 + 17.0 * sole - 6.0 * wet
        vento = max(0.0, rng.gauss(vento_base, vento_base * 0.45))
        w = cls(label=label, wet=wet, track_temp=round(track_temp, 1),
                air_temp=round(air, 1), wind=round(vento, 1), cloud=round(cloud, 2))
        w.rain_forecast = w._forecast(track, rng)
        return w

    # ------------------------------------------------------------- evoluzione
    def drift(self, track, rng: random.Random) -> "Weather":
        """Il tempo del turno dopo: somiglia a questo, ma non e' questo.

        Il venerdi' non e' il sabato e il sabato non e' la domenica. Le cose si
        muovono con calma - la temperatura di qualche grado, le nuvole a
        strappi - ma la pioggia arriva e se ne va, e chi ha preparato tutto il
        fine settimana sull'asciutto la domenica si ritrova un'altra pista.
        """
        clima = getattr(track, "climate", None) or {}
        pioggia = float(clima.get("rain", 0.20))
        cloud = max(0.0, min(1.0, 0.62 * self.cloud + 0.38 * rng.betavariate(2.0, 3.5)))
        wet = self.wet
        if wet > 0.05:
            if rng.random() < 0.45:
                wet = 0.0                                  # ha smesso
            else:
                wet = max(0.05, min(1.0, wet * rng.uniform(0.55, 1.35)))
        elif rng.random() < pioggia * 0.45:
            wet = rng.uniform(0.20, 0.90)
        if wet > 0.55:
            label, cloud = "pioggia intensa", 1.0
        elif wet > 0.05:
            label, cloud = "pioggia leggera", max(cloud, 0.9)
        elif cloud > 0.75:
            label = "coperto"
        elif cloud > 0.50:
            label = "nuvoloso"
        else:
            label = "sereno"
        media = float(clima.get("temp", 22.0))
        air = 0.70 * self.air_temp + 0.30 * rng.gauss(media, 2.5) - 3.0 * wet
        sole = (0.30 if getattr(track, "night", False) else 1.0) * (1.0 - 0.75 * cloud)
        w = Weather(label=label, wet=round(wet, 3), air_temp=round(air, 1),
                    track_temp=round(air + 3.0 + 17.0 * sole - 6.0 * wet, 1),
                    wind=round(max(0.0, 0.6 * self.wind
                                   + 0.4 * rng.gauss(float(clima.get("wind", 10.0)), 4.0)), 1),
                    cloud=round(cloud, 2))
        w.rain_forecast = w._forecast(track, rng)
        return w

    def _forecast(self, track, rng: random.Random) -> list:
        """Cosa dicono i radar per la gara: a che punto e quanta acqua.

        E' una previsione, non un fatto: dice che sta arrivando e quando, non
        quanto durera' esattamente. Basta a decidere se rischiare le gomme da
        asciutto o fermarsi subito.
        """
        clima = getattr(track, "climate", None) or {}
        p = float(clima.get("rain", 0.20))
        fuori = []
        if self.wet > 0.05:
            if rng.random() < 0.50:
                fuori.append((round(rng.uniform(0.15, 0.70), 2), 0.0))
        elif rng.random() < p * 0.75:
            quando = round(rng.uniform(0.10, 0.75), 2)
            fuori.append((quando, round(rng.uniform(0.25, 0.85), 2)))
            if rng.random() < 0.35:
                fuori.append((round(min(0.95, quando + rng.uniform(0.15, 0.40)), 2), 0.0))
        return fuori

    def forecast_label(self) -> str:
        """La previsione detta a parole, per il muretto."""
        if not self.rain_forecast:
            return ("continua a piovere per tutta la gara" if self.wet > 0.05
                    else "asciutto per tutta la gara")
        quota, forza = self.rain_forecast[0]
        quando = ("nei primi giri" if quota < 0.2 else
                  "verso il primo terzo" if quota < 0.4 else
                  "a meta' gara" if quota < 0.6 else
                  "nell'ultimo terzo")
        if forza <= 0.05:
            return f"la pioggia dovrebbe smettere {quando}"
        forte = "acquazzone" if forza > 0.55 else "pioggia leggera"
        return f"{forte} in arrivo {quando}"


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
    confidence: float = 65.0      # quanto si fida della macchina che ha sotto
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
    stock: dict = None            # set ancora nel camion, per mescola
    overtake_cd: float = 0.0
    dirty_air: float = 0.0
    clean_lap: float = 90.0     # passo in aria libera, usato per valutare i duelli
    damage: float = 0.0
    push_mode: float = 1.0        # 0.9 conserva .. 1.1 attacca
    fuel_warned: bool = False
    grid: int = 1
    finished_time: float = 0.0
    is_player: bool = False
    laps_led: int = 0
    penalty_pending: float = 0.0     # secondi assegnati e non ancora scontati
    penalty_total: float = 0.0       # secondi complessivi ricevuti
    penalties_given: list = field(default_factory=list)   # infrazioni contestate
    under_review: float = 0.0        # secondi di attesa prima della decisione
    review_kind: str = ""
    track_warnings: int = 0

    def compound_state(self) -> float:
        """1.0 = gomma fresca, cala fino allo 0 dopo il degrado."""
        x = self.tyre_age / max(1.0, self.tyre_life)
        if x <= 1.0:
            return 1.0 - 0.11 * x * x
        return max(0.35, 0.89 - 0.55 * (x - 1.0))


# ------------------------------------------------------------------ simulazione
class RaceSim:
    def __init__(self, gs, track, entrants: list, weather: Weather, laps: int,
                 kind: str = "gp", rng: random.Random | None = None, cond=None):
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
        from . import pace
        self.cond = cond if cond is not None else pace.from_weather(track, weather)
        # l'asfalto che si sono trovati - freddo o caldo, verde o gommato - sta
        # gia' dentro al giro base di ognuno. Qui resta solo quel poco che la
        # pista guadagna ancora mentre si corre, che vale mezzo secondo scarso
        self.evo = 1.004
        self.wind_noise = pace.wind_noise(self.cond)
        # su un asfalto che scotta la gomma dura meno: e' la ragione per cui la
        # stessa mescola fa venti giri in Bahrain e trentacinque a Montreal
        self.temp_wear = max(0.72, min(1.55, 1.0 + 0.020 * (self.cond.track_temp - 35.0)))
        # la previsione diventa un programma: a che giro l'acqua arriva e quanta
        self.meteo_prog = [(max(1, int(q * laps)), forza)
                           for q, forza in (getattr(weather, "rain_forecast", None) or [])]
        self.meteo_target = weather.wet
        # degrado imposto dal regolamento in vigore: fisso per tutta la gara
        reg = getattr(gs, "regulations", None) or {}
        self.tyre_deg = float(reg.get("tyres", {}).get("deg_multiplier", 1.0))
        # gare accorciate: gomme e soglie di strategia si accorciano con loro,
        # altrimenti una gara al 50% si correrebbe senza mai fermarsi
        self.distance = float(getattr(gs, "race_distance", 1.0))
        # consumo tarato sul carico imbarcato: guidando normale si arriva in
        # fondo con un filo di riserva, qualunque sia la lunghezza della gara.
        # make_race lo ricalcola appena sa quanta benzina c'e' a bordo.
        self.burn_per_lap = BURN_KG_PER_LAP
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
        t *= self.evo
        t -= (max(0.90, min(1.10, e.push_mode)) - 1.0) * PUSH_S_PER_LAP
        if e.fuel <= 0.01:
            t += DRY_TANK_PENALTY
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
        var = self.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.006
                             + self.wind_noise)
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
        # la pista continua a gommarsi mentre si corre
        self.evo = max(0.9995, self.evo - dt * 0.0000030)
        self._meteo(dt)
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
            burn = self.burn_per_lap * (e.push_mode ** PUSH_FUEL_EXP)
            e.fuel = max(0.0, e.fuel - burn * dt / lt)

            self._track_limits(e, dt)

            new_lap = int(e.dist // self.track_len)
            if new_lap > e.lap:
                e.lap = new_lap
                self._on_lap_complete(e, lt)

        self._resolve_battles(dt)
        self._resolve_reviews(dt)
        self._update_positions()
        self._maybe_incident(dt)

    def _meteo(self, dt: float) -> None:
        """Il tempo cambia mentre si corre: l'acqua arriva, e poi se ne va.

        Non e' un interruttore: la pista si bagna e si asciuga in qualche giro,
        e in quei giri sta la gara - chi si ferma subito, chi resiste, chi
        sbaglia il momento.
        """
        for giro, forza in list(self.meteo_prog):
            if self.leader_lap >= giro:
                self.meteo_target = forza
                self.meteo_prog.remove((giro, forza))
                if forza > 0.05:
                    self.log("Arriva la pioggia: cominciano a cadere gocce", "warn")
                else:
                    self.log("Ha smesso di piovere: la pista si asciuga", "warn")
        w = self.weather
        if abs(w.wet - self.meteo_target) < 0.005:
            return
        passo = dt * 0.0016 * (1.0 if self.meteo_target > w.wet else 0.7)
        prima = w.wet
        w.wet = round(min(self.meteo_target, w.wet + passo) if self.meteo_target > w.wet
                      else max(self.meteo_target, w.wet - passo), 3)
        w.label = ("pioggia intensa" if w.wet > 0.55 else
                   "pioggia leggera" if w.wet > 0.05 else "pista in asciugatura"
                   if prima > 0.05 else w.label)
        # sotto l'acqua la gomma stesa se ne va, e con lei l'aderenza
        if w.wet > 0.2:
            self.evo = min(1.02, self.evo + dt * 0.0000050)

    def _wear_rate(self, e: Entrant) -> float:
        comp = C.COMPOUNDS[e.tyre]
        base = comp["wear"] * self.tyre_deg * (0.55 + 0.9 * self.track.traits.get("tyre_wear", 0.6))
        skill = 1.30 - 0.55 * (e.tyre_skill / 100.0)
        push = e.push_mode ** PUSH_WEAR_EXP
        sc = 0.45 if self.safety_car > 0 else 1.0
        wet = 1.0 - 0.35 * self.weather.wet
        return base * skill * push * sc * wet * self.temp_wear

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
        # chi non si fida di quello che ha sotto sbaglia di piu': non e' che
        # guidi peggio, e' che la macchina lo sorprende
        err *= max(0.60, 1.0 + (65.0 - e.confidence) * 0.008)
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
            if e.penalty_pending > 0:
                # non c'e' stata piu' una sosta: i secondi si aggiungono all'arrivo
                e.finished_time += e.penalty_pending
                self.log(f"{e.name}: {e.penalty_pending:.0f}s aggiunti al tempo finale", "pen")
                e.penalty_pending = 0.0
            if not self.classification:
                self.log(f"BANDIERA A SCACCHI: vince {e.name}!", "flag")
            self.classification.append(e)
            if len([x for x in self.entrants if x.status in ("finished", "retired")]) >= len(self.entrants):
                self.finished = True
            return

        self._fuel_check(e)
        self._check_pit(e)
        if all(x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True

    def _fuel_check(self, e: Entrant) -> None:
        """Avvisa quando la benzina non basta piu' per arrivare in fondo.

        Non impone niente: attaccare puo' voler dire restare a secco, ma il
        muretto lo dice prima, non dopo.
        """
        left = self.laps - e.lap
        if left <= 0 or e.fuel_warned or e.fuel >= left * self.burn_per_lap:
            return
        e.fuel_warned = True
        if e.is_player:
            self.log(f"Benzina critica per {e.name}: cosi' non arriva in fondo", "warn")

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
        if e.penalty_pending > 0:
            # i secondi si scontano fermi ai box, prima di toccare la vettura
            stop += e.penalty_pending
            self.log(f"{e.name} sconta {e.penalty_pending:.0f}s di penalita' ai box", "pen")
            e.penalty_pending = 0.0
        if self.rng.random() < 0.035:
            stop += self.rng.uniform(2.0, 9.0)
            self.log(f"Sosta lenta per {e.name}!", "warn")
        if self.rng.random() < 0.012 + (100.0 - e.consistency) * 0.0004:
            self._investigate(e, "velocita_box")
        loss = self.track.pit_loss * (0.62 if self.safety_car > 0 else 1.0)
        # la vettura resta ferma per tutta la durata della sosta mentre gli
        # altri avanzano: e' gia' l'intera perdita di tempo. Toglierle anche
        # la distanza equivalente la farebbe pagare due volte.
        e.pit_timer = stop + loss
        e.tyre = target
        e.used_compounds.add(target)
        if e.stock and target in e.stock:
            e.stock[target] = max(0, e.stock[target] - 1)
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
        if remaining <= 16 * self.distance:
            voluta = ("soft", "medium", "hard")
        elif remaining <= 30 * self.distance:
            voluta = ("medium", "hard", "soft")
        else:
            voluta = ("hard", "medium", "soft")
        if not e.stock:
            return voluta[0]
        for m in voluta:
            if e.stock.get(m, 0) > 0:
                return m
        return voluta[0]           # non resta niente: si monta l'usato

    # A che temperatura d'asfalto lavora ogni mescola. La morbida arriva in
    # temperatura subito e va oltre altrettanto in fretta; la dura sull'asfalto
    # freddo non si accende e scivola tutta la gara.
    FINESTRA = {"soft": 30.0, "medium": 37.0, "hard": 44.0, "inter": 22.0, "wet": 18.0}

    def _tyre_life(self, e: Entrant, comp: str) -> float:
        base = {"soft": 17.0, "medium": 26.0, "hard": 37.0, "inter": 22.0, "wet": 26.0}[comp]
        wear_t = self.track.traits.get("tyre_wear", 0.6)
        # non tutte le "morbide" sono uguali: quella che il fornitore porta a
        # Monaco e quella che porta a Silverstone sono due gomme diverse
        if comp in ("soft", "medium", "hard"):
            from ..core import tyres
            base *= tyres.life_scale(tyres.nomination(self.track)[comp])
        # e nemmeno la stessa mescola e' uguale a se stessa: sopra la sua
        # finestra si sfoglia, sotto non si accende
        fuori = (self.cond.track_temp - self.FINESTRA.get(comp, 37.0)) / 18.0
        finestra = 1.0 - 0.22 * max(0.0, fuori) ** 1.6 - 0.10 * max(0.0, -fuori) ** 1.6
        life = (base * (1.35 - 0.62 * wear_t) * (0.78 + 0.42 * e.tyre_skill / 100.0)
                * max(0.55, finestra))
        return life * self.distance

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
                    grave = dmg > 12
                    self._investigate(behind, "contatto" if grave else "contatto_lieve")
                    self._maybe_safety_car(0.35)

    # ------------------------------------------------------------ commissari
    def _investigate(self, e, kind: str) -> None:
        """Apre un'investigazione. I commissari non decidono subito."""
        if e.under_review > 0 or e.status != "running":
            return
        e.under_review = self.rng.uniform(25.0, 70.0)
        e.review_kind = kind
        self.log(f"{e.name} sotto investigazione: "
                 f"{PENALTY_LABELS.get(kind, kind).lower()}", "warn")

    def _resolve_reviews(self, dt: float) -> None:
        """Le decisioni arrivano dopo qualche minuto, come in pista."""
        for e in self.entrants:
            if e.under_review <= 0:
                continue
            e.under_review -= dt
            if e.under_review > 0:
                continue
            kind, e.review_kind = e.review_kind, ""
            meta = PENALTY_RULES.get(kind, {})
            # un pilota pulito viene creduto piu' facilmente
            scusante = 0.10 + 0.35 * (e.consistency / 100.0)
            if self.rng.random() < scusante:
                self.log(f"{e.name}: nessun provvedimento", "info")
                continue
            secondi = meta.get("secondi", 5.0)
            e.penalty_pending += secondi
            e.penalty_total += secondi
            e.penalties_given.append(kind)
            self.log(f"PENALITA': {secondi:.0f} secondi a {e.name} - "
                     f"{PENALTY_LABELS.get(kind, kind).lower()}", "pen")

    def _track_limits(self, e, dt: float) -> None:
        """Uscite di pista ripetute: tre avvertimenti e arriva la penalita'."""
        if e.status != "running" or self.safety_car > 0:
            return
        # Probabilita' al secondo, tarata perche' un pilota medio raccolga circa
        # un avvertimento a gara: servendone tre per la penalita', ne esce
        # qualcuna sparsa nell'arco del weekend, non una a ogni curva.
        rischio = (100.0 - e.consistency) * 0.0000052 * (0.6 + 0.9 * e.push_mode)
        rischio *= 1.0 + 0.8 * self.track.traits.get("bumpiness", 0.4)
        if self.rng.random() < rischio * dt:
            e.track_warnings += 1
            if e.track_warnings % 3 == 0:
                self._investigate(e, "limiti_pista")
            else:
                self.log(f"{e.name}: avvertimento per i limiti della pista "
                         f"({e.track_warnings})", "info")

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
