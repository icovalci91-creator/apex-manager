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
    parent_team: str = ""        # squadra maggiore dello stesso gruppo
    pu_capable: bool = True     # puo' fondare un reparto motori proprio?
    pu_partner_races: int = 0   # gare passate a lavorare con questa casa
    pu_partner_engine: str = "" # con quale: se cambia, si riparte da capo
    pu_reason: str = ""         # perche' si o perche' no, mostrato al giocatore

    facility_age: dict = None    # stagioni dall'ultimo intervento, per struttura
    track_name: str = ""         # come si chiama la pista di proprieta', se c'e'
    track_id: str = ""           # e quale circuito e', per andarci a provare
    heritage: bool = False       # premio di anzianita' dal promoter
    entry_season: int = 0        # stagione di ingresso, se e' una squadra nuova
    test_days_used: int = 0      # giornate di test private gia' spese
    preseason_done: list = field(default_factory=list)  # prove collettive gia' fatte
    correlation: float = 0.0     # quanto la galleria del vento dice il vero
    setup_knowledge: dict = None # conoscenza d'assetto accumulata, per circuito
    setup_paper: dict = None     # l'assetto sulla carta per il weekend in corso
    setup_paper_track: str = ""  # per quale pista vale
    sim_sessions: int = 0        # sessioni di simulatore fatte per quel weekend
    car_understanding: float = 0.0  # quanto abbiamo capito la macchina di quest'anno
    car_memoria: float = 0.0     # e quanto ne abbiamo messo da parte con l'ultimo pacchetto
    workforce: dict = None       # quanti ingegneri lavorano in ogni reparto
    hired_this_season: dict = None  # quanti se ne sono assunti quest'anno, per reparto
    pu_building: bool = False    # ha fondato il reparto motori e lo sta costruendo
    car: Car = None
    drivers: list = field(default_factory=list)      # id piloti titolari
    reserves: list = field(default_factory=list)     # terzo pilota e collaudatori
    academy: list = field(default_factory=list)      # ragazzi del vivaio
    academy_name: str = ""       # come si chiama il vivaio, se c'e'
    vivaio_auto: bool = True     # il responsabile del vivaio sceglie le categorie
    setups: dict = None          # assetto montato, pilota per pilota
    kits: list = None            # pezzi nuovi usciti dalla fabbrica, da montare
    part_delta: dict = None      # specifiche montate su una macchina sola
    last_spec: dict = None       # la specifica precedente, se un pezzo si distrugge
    auto_dev: bool = False       # il reparto tecnico decide da solo gli aggiornamenti
    auto_setup: bool = True      # gli ingegneri di pista preparano l'assetto da soli
    staff: list = field(default_factory=list)        # oggetti Staff
    points: float = 0.0
    wins: int = 0
    podiums: int = 0
    last_position: int = 6

    spent: float = 0.0          # speso nel cap tecnico questa stagione
    capex_log: dict = field(default_factory=dict)  # speso in costruzioni, per stagione
    austerity: float = 0.0      # quanto si tira la cinghia dopo una stagione in perdita
    deals: list = field(default_factory=list)    # accordi commerciali firmati
    ledger: list = field(default_factory=list)   # movimenti datati
    cur_season: int = 0                          # quando siamo, per datare i movimenti
    cur_month: int = 1
    cur_round: int = 0
    dev_projects: list = field(default_factory=list)
    spec_trials: list = field(default_factory=list)  # specifiche in verifica
    upgrades_done: int = 0
    # Storia degli aggiornamenti portati in pista: cosa era stato promesso e
    # cosa e' arrivato davvero. Serve a guardarsi indietro e capire se il
    # reparto mantiene quello che dice, non solo quanti pacchetti ha fatto.
    upgrade_log: list = field(default_factory=list)
    is_player: bool = False
    engine_customer_cost: float = 0.0
    resource_alloc: dict = field(default_factory=dict)   # area -> quota 0..1
    next_reg_share: float = 0.0   # quota di sviluppo dirottata sull'anno prossimo
    reg_prep: float = 0.0         # preparazione accumulata per il prossimo ciclo
    arch_prog: dict = None        # programma sull'architettura di power unit futura
    arch_exp: dict = None         # mestiere accumulato: termico ed elettrico
    next_car_brief: dict = None   # la linea data al reparto per la vettura nuova
    next_car_work: dict = None    # lavoro gia' fatto sul progetto dell'anno prossimo

    @property
    def is_satellite(self) -> bool:
        """Seconda squadra di un gruppo che ne ha gia' una in griglia."""
        return bool(self.parent_team)

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

    @property
    def private_track_name(self) -> str:
        return self.track_name or "pista di proprieta'"

    # ------------------------------------------------------------- reparti
    @property
    def aero_strength(self) -> float:
        people = 0.55 * self._s("head_of_aero", "aero") + 0.45 * self._s("technical_director", "aero")
        people *= self._org("aero")
        tools = (0.42 * self._fac("windtunnel") + 0.30 * self._fac("cfd") + 0.28 * self._fac("aero_dept"))
        return 0.58 * people + 0.42 * tools

    @property
    def mech_strength(self) -> float:
        people = 0.55 * self._s("chief_designer", "mechanical") + 0.45 * self._s("technical_director", "mechanical")
        people *= self._org("progetto")
        tools = 0.55 * self._fac("design_office") + 0.45 * self._fac("factory")
        return 0.60 * people + 0.40 * tools

    @property
    def pu_strength(self) -> float:
        return (0.70 * self._s("head_of_powertrain", "powertrain") * self._org("powertrain")
                + 0.30 * self._fac("factory"))

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
        return ((0.40 * self._s("chief_designer", "reliability")
                 + 0.30 * self._s("chief_mechanic", "reliability")) * self._org("affidabilita")
                + 0.30 * self._fac("factory"))

    @property
    def setup_strength(self) -> float:
        pe = self.roles("performance_engineer")
        pe_v = sum(p.analysis for p in pe) / len(pe) if pe else 60.0
        base = (0.42 * pe_v * self._org("simulazione") + 0.30 * self._fac("simulator")
                + 0.28 * self._s("technical_director", "analysis"))
        # chi ha una pista propria ci gira quando vuole: arriva al weekend con
        # meno da scoprire
        return base * (1.0 + 0.16 * self.facilities.get("private_track", 0.0) / 100.0)

    @property
    def has_private_track(self) -> bool:
        return float(self.facilities.get("private_track", 0.0)) > 0.0

    @property
    def dev_rate(self) -> float:
        """Quanto efficacemente le risorse diventano prestazione (0.5..1.6)."""
        td = self._s("technical_director", "development")
        mgmt = self._s("team_principal", "management")
        fac = 0.5 * self._fac("factory") + 0.5 * self._fac("design_office")
        raw = 0.45 * td + 0.20 * mgmt + 0.35 * fac
        return 0.50 + 1.10 * (raw / 100.0)

    @property
    def finance_strength(self) -> float:
        """Quanto la squadra sa dove sono i suoi soldi.

        Un direttore finanziario bravo non fa risparmiare: fa sapere in
        anticipo quanto si sta per spendere, che nel tetto di spesa e' la
        stessa cosa. Senza di lui si naviga a vista e si sfora per sbaglio.
        """
        return (0.62 * self._s("financial_director", "management", 48.0)
                + 0.38 * self._s("financial_director", "analysis", 48.0))

    @property
    def scouting_strength(self) -> float:
        return 0.65 * self._s("head_of_scouting", "scouting") + 0.35 * self._fac("academy")

    def _org(self, area: str) -> float:
        """Quanto l'organico di quel reparto moltiplica i suoi responsabili."""
        from ..core import departments
        return departments.size_factor(self, area)

    @property
    def staff_cost(self) -> float:
        """I responsabili piu' tutte le persone che lavorano sotto di loro."""
        from ..core import departments
        return round(sum(s.salary for s in self.staff) + departments.payroll(self), 2)

    @property
    def leaders_cost(self) -> float:
        """Solo i nomi dell'organigramma, senza l'organico che dirigono."""
        return round(sum(s.salary for s in self.staff), 2)

    @property
    def facility_upkeep(self) -> float:
        """Costo annuo di far girare le strutture.

        Cresce piu' che proporzionalmente al livello: una galleria del vento di
        prim'ordine non si mantiene con il budget di un capannone.
        """
        tot = 0.0
        for v in self.facilities.values():
            if float(v) <= 0.0:
                continue        # una struttura che non esiste non si mantiene
            tot += 1.1 + 5.2 * (float(v) / 100.0) ** 2.3
        return round(tot, 2)

    def rating(self) -> float:
        return 0.5 * (self.car.rating if self.car else 60.0) + 0.5 * (
            0.4 * self.aero_strength + 0.3 * self.mech_strength + 0.3 * self.dev_rate * 60.0)

    # ------------------------------------------------------------- finanze
    def set_clock(self, season: int, month: int, rnd: int) -> None:
        """Da qui in poi i movimenti verranno datati cosi'."""
        self.cur_season, self.cur_month, self.cur_round = season, month, rnd

    def _record(self, verso: str, label: str, amount: float,
                category: str, in_cap: bool) -> None:
        self.ledger.append({
            "season": self.cur_season, "month": self.cur_month, "round": self.cur_round,
            "kind": verso, "category": category, "label": label,
            "amount": round(float(amount), 3), "in_cap": bool(in_cap),
        })
        del self.ledger[4000:]

    def add_income(self, label: str, amount: float, category: str = "altro") -> None:
        self.cash += amount
        self._record("in", label, amount, category, False)

    def add_expense(self, label: str, amount: float, in_cap: bool = True,
                    category: str = "altro", capex: bool = False) -> None:
        """`capex` marca la spesa in conto capitale: sta fuori dal tetto tecnico
        e dentro il limite delle costruzioni, che si conta su piu' stagioni."""
        self.cash -= amount
        self._record("out", label, amount, category, in_cap)
        if in_cap:
            self.spent += amount
        if capex:
            if self.capex_log is None:
                self.capex_log = {}
            k = str(self.cur_season)
            self.capex_log[k] = round(self.capex_log.get(k, 0.0) + amount, 3)

    # compatibilita' con il codice che leggeva i due registri separati
    @property
    def income_log(self) -> list:
        return [(m["label"], m["amount"]) for m in self.ledger if m["kind"] == "in"]

    @property
    def expense_log(self) -> list:
        return [(m["label"], m["amount"]) for m in self.ledger if m["kind"] == "out"]

    def reset_season_finances(self) -> None:
        """Azzera il contatore del cap. Il libro mastro resta: serve allo storico."""
        self.spent = 0.0
