"""Vettura: componenti, usura, assetto e statistiche derivate."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config as C

# Assetto: ogni voce va da 0 a 100. L'ottimo dipende dalla pista.
SETUP_KEYS = {
    "wing":        "Carico alare",
    "ride_height": "Altezza da terra",
    "stiffness":   "Rigidezza sospensioni",
    "camber":      "Campanatura",
    "gearing":     "Rapporti al cambio",
    "brake_bias":  "Ripartizione di frenata",
}


@dataclass
class Part:
    perf: float
    condition: float = 100.0   # 0-100, scende con usura e danni
    upgrade_progress: float = 0.0

    @property
    def effective(self) -> float:
        return self.perf * (0.55 + 0.45 * self.condition / 100.0)


@dataclass
class Car:
    parts: dict = field(default_factory=dict)     # nome -> Part
    engine: dict = field(default_factory=dict)    # stats del motorista
    setup: dict = field(default_factory=dict)     # SETUP_KEYS -> 0..100
    setup_quality: float = 0.5                    # 0..1, quanto e' azzeccato
    fuel_kg: float = 0.0
    reg_downforce_index: float = 0.70
    active_aero_allowed: bool = True
    mass_base: float = C.CAR_MASS_KG              # peso minimo regolamentare

    # ------------------------------------------------------------------ init
    @classmethod
    def build(cls, team_car: dict, engine: dict, reg: dict) -> "Car":
        parts = {k: Part(float(v)) for k, v in team_car.items()}
        aero = reg.get("aero", {})
        c = cls(
            parts=parts,
            engine=dict(engine),
            setup={k: 50.0 for k in SETUP_KEYS},
            reg_downforce_index=aero.get("downforce_index", 0.70),
            active_aero_allowed=aero.get("active_aero", True),
            mass_base=float(reg.get("min_weight_kg", C.CAR_MASS_KG)),
        )
        return c

    def p(self, key: str) -> float:
        part = self.parts.get(key)
        return part.effective if part else 60.0

    # --------------------------------------------------------- derivate base
    @property
    def mass_extra(self) -> float:
        return self.fuel_kg

    @property
    def downforce(self) -> float:
        """Moltiplicatore su ClA di riferimento."""
        base = (0.30 * self.p("floor") + 0.22 * self.p("front_wing")
                + 0.22 * self.p("rear_wing") + 0.14 * self.p("sidepods")
                + 0.12 * self.p("chassis")) / 100.0
        aa = self.p("active_aero") / 100.0 if self.active_aero_allowed else 0.0
        wing = 0.62 + 0.74 * (self.setup.get("wing", 50.0) / 100.0)
        rh = 1.0 + 0.10 * (1.0 - self.setup.get("ride_height", 50.0) / 100.0)
        idx = self.reg_downforce_index / 0.70
        return (0.62 + 0.80 * base) * wing * rh * idx * (1.0 + 0.07 * aa)

    @property
    def drag(self) -> float:
        wing = 0.80 + 0.44 * (self.setup.get("wing", 50.0) / 100.0)
        eff = (0.45 * self.p("rear_wing") + 0.30 * self.p("sidepods")
               + 0.25 * self.p("cooling")) / 100.0
        aa = 0.94 if self.active_aero_allowed else 1.0
        return wing * (1.30 - 0.42 * eff) * aa

    @property
    def power(self) -> float:
        e = self.engine
        pu = (0.62 * e.get("power", 85) + 0.38 * e.get("ers", 85)) / 100.0
        cooling = 0.96 + 0.06 * (self.p("cooling") / 100.0)
        gears = 0.97 + 0.05 * (self.p("gearbox") / 100.0)
        gearing = 0.985 + 0.03 * (self.setup.get("gearing", 50.0) / 100.0)
        return 0.80 + 0.42 * pu * cooling * gears * gearing

    @property
    def mech_grip(self) -> float:
        base = (0.50 * self.p("suspension") + 0.32 * self.p("chassis")
                + 0.18 * self.p("gearbox")) / 100.0
        stiff = 1.0 - abs(self.setup.get("stiffness", 50.0) - 50.0) / 420.0
        camber = 1.0 - abs(self.setup.get("camber", 50.0) - 50.0) / 500.0
        return (0.82 + 0.26 * base) * stiff * camber

    @property
    def braking(self) -> float:
        base = (0.70 * self.p("brakes") + 0.30 * self.p("suspension")) / 100.0
        bias = 1.0 - abs(self.setup.get("brake_bias", 50.0) - 50.0) / 460.0
        return (0.84 + 0.24 * base) * bias

    @property
    def reliability(self) -> float:
        """0..1, probabilita' di NON rompersi in una gara."""
        mech = sum(self.parts[k].condition for k in self.parts) / (100.0 * max(1, len(self.parts)))
        eng = self.engine.get("reliability", 85) / 100.0
        return max(0.30, min(0.995, 0.55 + 0.30 * mech + 0.14 * eng))

    @property
    def rating(self) -> float:
        """Indice sintetico 0-100 per le schermate di riepilogo."""
        vals = [p.effective for p in self.parts.values()]
        car = sum(vals) / max(1, len(vals))
        eng = (self.engine.get("power", 85) + self.engine.get("ers", 85)) / 2.0
        return 0.72 * car + 0.28 * eng

    # ------------------------------------------------------------- assetto
    def optimal_setup(self, track) -> dict:
        t = track.traits
        return {
            "wing":        100.0 * min(1.0, max(0.0, t["downforce"])),
            "ride_height": 100.0 * min(1.0, max(0.0, 0.28 + 0.62 * t["bumpiness"])),
            "stiffness":   100.0 * min(1.0, max(0.0, 0.72 - 0.50 * t["bumpiness"] + 0.18 * t["downforce"])),
            "camber":      100.0 * min(1.0, max(0.0, 0.35 + 0.45 * t["downforce"] - 0.15 * t["power"])),
            "gearing":     100.0 * min(1.0, max(0.0, t["power"])),
            "brake_bias":  100.0 * min(1.0, max(0.0, 0.35 + 0.40 * t["braking"])),
        }

    def evaluate_setup(self, track) -> float:
        opt = self.optimal_setup(track)
        err = sum(abs(self.setup.get(k, 50.0) - opt[k]) for k in opt) / len(opt)
        self.setup_quality = max(0.0, 1.0 - (err / 45.0) ** 1.35)
        return self.setup_quality

    def apply_setup_effects(self):
        """Penalita' di prestazione per un assetto sbagliato (0..1)."""
        return 0.988 + 0.012 * self.setup_quality

    # --------------------------------------------------------------- usura
    def wear(self, amount: float, track) -> None:
        rough = 0.6 + 0.8 * track.traits.get("bumpiness", 0.4)
        for k, part in self.parts.items():
            part.condition = max(0.0, part.condition - amount * rough * (0.6 + 0.8 * _wear_bias(k)))

    def damage(self, key: str, amount: float) -> None:
        if key in self.parts:
            self.parts[key].condition = max(0.0, self.parts[key].condition - amount)

    def repair_cost(self) -> float:
        """Costo in M$ per riportare tutto al 100%."""
        tot = 0.0
        for k, part in self.parts.items():
            missing = (100.0 - part.condition) / 100.0
            tot += missing * C.CAR_PARTS[k]["cost"] * 0.55
        return round(tot, 3)

    def repair_all(self) -> float:
        cost = self.repair_cost()
        for part in self.parts.values():
            part.condition = 100.0
        return cost


_WEAR_BIAS = {
    "front_wing": 1.3, "floor": 1.4, "brakes": 1.5, "gearbox": 1.1,
    "suspension": 1.2, "rear_wing": 0.9, "chassis": 0.5, "sidepods": 0.7,
    "cooling": 0.8, "active_aero": 1.0,
}


def _wear_bias(key: str) -> float:
    return _WEAR_BIAS.get(key, 1.0)
