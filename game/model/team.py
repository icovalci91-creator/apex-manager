"""Scuderia: struttura, reparti, finanze."""
from __future__ import annotations

from dataclasses import dataclass, field

from .car import Car
from .people import Staff


@dataclass
class Team:
    id: str
    name: str
    short: str
    base: str
    colour: str
    accent: str
    founded: int
    engine: str
    works: bool
    reputation: float
    budget_base: float
    cash: float
    facilities: dict
    philosophy: str
    titles: dict
    pu_status: str = "customer"  # works = costruisce | partner = team ufficiale | customer
    pu_capable: bool = True     # puo' fondare un reparto motori proprio?
    pu_partner_races: int = 0   # gare passate a lavorare con questa casa
    pu_partner_engine: str = "" # con quale: se cambia, si riparte da capo
    pu_reason: str = ""         # perche' si o perche' no, mostrato al giocatore

    car: Car = None
    drivers: list = field(default_factory=list)      # id piloti
    staff: list = field(default_factory=list)        # oggetti Staff
    points: float = 0.0
    wins: int = 0
    podiums: int = 0
    last_position: int = 6

    spent: float = 0.0          # speso nel cap questa stagione
    income_log: list = field(default_factory=list)
    expense_log: list = field(default_factory=list)
    dev_projects: list = field(default_factory=list)
    upgrades_done: int = 0
    is_player: bool = False
    engine_customer_cost: float = 0.0
    resource_alloc: dict = field(default_factory=dict)   # area -> quota 0..1

    @property
    def is_partner(self) -> bool:
        """Team ufficiale di una casa che non corre in proprio.

        Non costruisce la power unit ma la riceve disegnata attorno alla sua
        vettura, a condizioni da partner e non da cliente. E' il caso di Aston
        Martin con Honda: sulla carta un cliente, nei fatti una squadra works.
        """
        return self.pu_status == "partner"

    # ------------------------------------------------------------ organico
    def role(self, role_id: str) -> Staff | None:
        for s in self.staff:
            if s.role == role_id:
                return s
        return None

    def roles(self, role_id: str) -> list:
        return [s for s in self.staff if s.role == role_id]

    def engineer_for(self, driver_id: str) -> Staff | None:
        for s in self.staff:
            if s.role == "race_engineer" and s.assigned_driver == driver_id:
                return s
        eng = self.roles("race_engineer")
        return eng[0] if eng else None

    def _s(self, role_id: str, attr: str, default: float = 60.0) -> float:
        s = self.role(role_id)
        return getattr(s, attr, default) if s else default

    def _fac(self, key: str) -> float:
        return float(self.facilities.get(key, 60.0))

    # ------------------------------------------------------------- reparti
    @property
    def aero_strength(self) -> float:
        people = 0.55 * self._s("head_of_aero", "aero") + 0.45 * self._s("technical_director", "aero")
        tools = (0.42 * self._fac("windtunnel") + 0.30 * self._fac("cfd") + 0.28 * self._fac("aero_dept"))
        return 0.58 * people + 0.42 * tools

    @property
    def mech_strength(self) -> float:
        people = 0.55 * self._s("chief_designer", "mechanical") + 0.45 * self._s("technical_director", "mechanical")
        tools = 0.55 * self._fac("design_office") + 0.45 * self._fac("factory")
        return 0.60 * people + 0.40 * tools

    @property
    def pu_strength(self) -> float:
        return 0.70 * self._s("head_of_powertrain", "powertrain") + 0.30 * self._fac("factory")

    @property
    def strategy_strength(self) -> float:
        return (0.55 * self._s("head_of_strategy", "strategy")
                + 0.25 * self._s("team_principal", "strategy")
                + 0.20 * self._s("head_of_strategy", "analysis"))

    @property
    def pit_strength(self) -> float:
        return 0.55 * self._fac("pit_crew") + 0.45 * self._s("chief_mechanic", "reliability")

    @property
    def reliability_strength(self) -> float:
        return (0.40 * self._s("chief_designer", "reliability")
                + 0.30 * self._s("chief_mechanic", "reliability")
                + 0.30 * self._fac("factory"))

    @property
    def setup_strength(self) -> float:
        pe = self.roles("performance_engineer")
        pe_v = sum(p.analysis for p in pe) / len(pe) if pe else 60.0
        return 0.42 * pe_v + 0.30 * self._fac("simulator") + 0.28 * self._s("technical_director", "analysis")

    @property
    def dev_rate(self) -> float:
        """Quanto efficacemente le risorse diventano prestazione (0.5..1.6)."""
        td = self._s("technical_director", "development")
        mgmt = self._s("team_principal", "management")
        fac = 0.5 * self._fac("factory") + 0.5 * self._fac("design_office")
        raw = 0.45 * td + 0.20 * mgmt + 0.35 * fac
        return 0.50 + 1.10 * (raw / 100.0)

    @property
    def scouting_strength(self) -> float:
        return 0.65 * self._s("head_of_scouting", "scouting") + 0.35 * self._fac("academy")

    @property
    def staff_cost(self) -> float:
        return round(sum(s.salary for s in self.staff), 2)

    @property
    def facility_upkeep(self) -> float:
        """Costo annuo di far girare le strutture.

        Cresce piu' che proporzionalmente al livello: una galleria del vento di
        prim'ordine non si mantiene con il budget di un capannone.
        """
        tot = 0.0
        for v in self.facilities.values():
            tot += 1.1 + 5.2 * (float(v) / 100.0) ** 2.3
        return round(tot, 2)

    def rating(self) -> float:
        return 0.5 * (self.car.rating if self.car else 60.0) + 0.5 * (
            0.4 * self.aero_strength + 0.3 * self.mech_strength + 0.3 * self.dev_rate * 60.0)

    # ------------------------------------------------------------- finanze
    def add_income(self, label: str, amount: float) -> None:
        self.cash += amount
        self.income_log.append((label, round(amount, 3)))

    def add_expense(self, label: str, amount: float, in_cap: bool = True) -> None:
        self.cash -= amount
        self.expense_log.append((label, round(amount, 3)))
        if in_cap:
            self.spent += amount

    def reset_season_finances(self) -> None:
        self.spent = 0.0
        self.income_log.clear()
        self.expense_log.clear()
