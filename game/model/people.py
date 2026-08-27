"""Piloti e personale tecnico."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict

DRIVER_ATTRS = ["pace", "racecraft", "consistency", "tyre_mgmt", "wet",
                "feedback", "aggression", "stamina", "estro"]

STAFF_ATTRS = ["aero", "mechanical", "powertrain", "development", "reliability",
               "strategy", "analysis", "communication", "management", "scouting"]


@dataclass
class Driver:
    id: str
    first: str
    last: str
    nat: str
    age: int
    number: int
    team: str | None
    pace: float
    racecraft: float
    consistency: float
    tyre_mgmt: float
    wet: float
    feedback: float
    aggression: float
    stamina: float
    potential: float
    marketability: float
    salary: float
    contract_until: int
    # Quanto un pilota si inventa qualcosa. Non e' il passo e non e'
    # l'aggressivita': e' la traiettoria che nessuno aveva provato, la staccata
    # tenuta mezzo metro piu' in la', il giro che non doveva venire e viene.
    # Regala tempo e sorpassi che il modello non prevedeva, e ogni tanto manda
    # tutto a monte: e' la stessa qualita' che fa le pole e i testacoda.
    estro: float = 60.0
    # che posto occupa in squadra: si corre in due, ma un terzo pilota lo
    # tengono tutti - per le prove libere, per i test e per il giorno in cui
    # un titolare non e' in condizione di salire in macchina
    seat: str = "titolare"        # titolare | riserva | academy

    # voci del contratto oltre all'ingaggio fisso
    bonus_win: float = 0.0        # M$ per vittoria
    bonus_podium: float = 0.0     # M$ per podio
    bonus_points: float = 0.0     # M$ per punto iridato
    release_clause: float = 0.0   # M$ per portarlo via: 0 = nessuna clausola

    morale: float = 70.0
    form: float = 0.0          # -10..+10, oscilla nella stagione
    # quanto si fida della macchina che ha sotto: non e' il morale (quello
    # riguarda la squadra) ed e' quello che decide se in curva quattro alza il
    # piede o no. Si costruisce girando, si perde in un attimo
    confidence: float = 65.0
    fitness: float = 100.0
    points: float = 0.0
    wins: int = 0
    podiums: int = 0
    poles: int = 0
    races: int = 0
    dnfs: int = 0
    career_points: float = 0.0
    penalty_points: int = 0      # punti sulla licenza: a dodici si salta una gara
    banned_races: int = 0        # gare di squalifica ancora da scontare
    grid_penalty: int = 0        # posizioni da scontare alla prossima partenza
    pu_used: int = 1             # unita' di power unit gia' impiegate
    gearbox_used: int = 1
    # quanto e' consumata l'unita' che ha montata adesso: 100 e' nuova, sotto
    # i 30 comincia a rompersi, a zero non finisce la gara
    pu_wear: float = 100.0
    gearbox_wear: float = 100.0
    happiness_notes: list = field(default_factory=list)
    # i punti superlicenza raccolti nelle categorie minori, stagione per
    # stagione: ne servono quaranta in tre anni per guidare in Formula 1
    superlicenza: list = field(default_factory=list)
    ultima_serie: str = ""       # in che categoria ha corso l'anno scorso
    # dove correra' la prossima stagione: la sceglie il giocatore, oppure il
    # responsabile del vivaio se gli e' stata lasciata la mano
    serie_scelta: str = ""
    titoli: list = field(default_factory=list)   # i campionati gia' vinti

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def short(self) -> str:
        return f"{self.first[0]}. {self.last}"

    @property
    def code(self) -> str:
        return self.last[:3].upper()

    @property
    def overall(self) -> float:
        return (0.34 * self.pace + 0.20 * self.racecraft + 0.16 * self.consistency
                + 0.13 * self.tyre_mgmt + 0.09 * self.wet + 0.08 * self.feedback)

    @property
    def market_value(self) -> float:
        """Ingaggio richiesto in M$/anno."""
        ov = self.overall
        # sotto la soglia l'esponente frazionario darebbe un numero complesso:
        # un pilota da 55 di valutazione vale semplicemente il minimo sindacale
        base = max(0.8, max(0.0, (ov - 62.0) / 8.0) ** 2.4 * 0.9)
        youth = 1.0 + max(0.0, (self.potential - ov)) / 55.0
        star = 1.0 + self.marketability / 260.0
        age_pen = 1.0 - max(0, self.age - 35) * 0.035
        return round(max(0.6, base * youth * star * age_pen), 1)

    def race_rating(self, wet_level: float = 0.0) -> float:
        """Rendimento nel weekend, tra 0 e 1 circa."""
        core = self.overall + self.form * 0.55 + (self.morale - 70.0) * 0.025
        core += (self.wet - self.overall) * wet_level * 0.75
        core *= 0.90 + 0.10 * (self.fitness / 100.0)
        return core

    def progress(self, quality: float, rng: random.Random) -> list:
        """Crescita/declino di fine stagione. `quality` 0..1 = qualita' del programma."""
        notes = []
        peak = 27
        for a in DRIVER_ATTRS:
            cur = getattr(self, a)
            if self.age < peak:
                room = max(0.0, self.potential - self.overall)
                gain = rng.uniform(0.2, 1.6) * (0.35 + 0.65 * quality) * (0.4 + room / 22.0)
            elif self.age <= 33:
                gain = rng.uniform(-0.3, 0.6) * (0.5 + quality)
            else:
                decline = (self.age - 33) * 0.32
                gain = rng.uniform(-decline, 0.25) * (1.2 - 0.4 * quality)
                if a in ("stamina", "pace"):
                    gain -= 0.35 * (self.age - 33) * 0.20
            setattr(self, a, max(30.0, min(99.0, cur + gain)))
        self.age += 1
        if self.age <= peak:
            notes.append("in crescita")
        elif self.age >= 36:
            notes.append("in fase calante")
        return notes

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Driver":
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)


@dataclass
class Staff:
    id: str
    first: str
    last: str
    nat: str
    age: int
    team: str | None
    role: str
    aero: float = 60.0
    mechanical: float = 60.0
    powertrain: float = 60.0
    development: float = 60.0
    reliability: float = 60.0
    strategy: float = 60.0
    analysis: float = 60.0
    communication: float = 60.0
    management: float = 60.0
    scouting: float = 60.0
    salary: float = 1.0
    contract_until: int = 2027
    morale: float = 70.0
    assigned_driver: str | None = None

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    def score(self, weights: dict) -> float:
        tot = sum(weights.values()) or 1.0
        return sum(getattr(self, k, 60.0) * w for k, w in weights.items()) / tot

    @property
    def market_value(self) -> float:
        best = max(getattr(self, a) for a in STAFF_ATTRS)
        avg = sum(getattr(self, a) for a in STAFF_ATTRS) / len(STAFF_ATTRS)
        # meta' di prima: il costo di un reparto adesso lo paga l'organico, e
        # quello che si legge qui e' l'ingaggio di una persona sola
        v = max(0.0, ((0.6 * best + 0.4 * avg) - 55.0) / 10.0)
        return round(max(0.2, v ** 2.1 * 0.27), 2)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Staff":
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)


def generate_staff(role: str, level: float, rng: random.Random, pool: dict,
                   season: int, team: str | None = None, uid: str = "") -> Staff:
    """Crea una figura tecnica plausibile attorno a un livello medio."""
    first = rng.choice(pool["first"])
    last = rng.choice(pool["last"])
    s = Staff(
        id=uid or f"{last.lower()}_{rng.randrange(1000, 9999)}",
        first=first, last=last, nat=rng.choice(["IT", "GB", "FR", "DE", "ES", "NL", "JP", "US", "BR", "SE"]),
        age=rng.randint(30, 60), team=team, role=role,
        contract_until=season + rng.randint(1, 4),
    )
    for a in STAFF_ATTRS:
        s.__dict__[a] = max(35.0, min(96.0, rng.gauss(level, 8.0)))
    s.salary = s.market_value
    return s
