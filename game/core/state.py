"""Stato della partita: costruzione del mondo, calendario, classifiche, salvataggi."""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

from .. import config as C
from ..model.car import Car
from ..model.people import Driver, Staff, generate_staff
from ..model.team import Team
from ..model.track import Track
from .development import Project

ROLE_LEVEL_FROM_REP = {
    "technical_director": 1.00, "chief_designer": 0.95, "head_of_aero": 0.97,
    "head_of_powertrain": 0.93, "head_of_strategy": 0.96, "race_engineer": 0.92,
    "performance_engineer": 0.90, "chief_mechanic": 0.90, "head_of_scouting": 0.86,
    "team_principal": 1.02,
}


def _load(name: str) -> dict:
    with open(C.DATA / name, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class RaceResult:
    track_id: str
    round: int
    season: int
    kind: str                      # "gp" | "sprint"
    order: list = field(default_factory=list)   # [{driver, team, pos, time, status, ...}]
    pole: str = ""
    fastest_lap: str = ""
    weather: str = "sereno"


@dataclass
class GameState:
    season: int = 2026
    round: int = 0                 # indice della prossima gara
    phase: str = "preseason"       # preseason | season | offseason
    player_team: str = ""
    player_is_constructor: bool = True
    seed: int = 0

    tracks: list = field(default_factory=list)
    teams: dict = field(default_factory=dict)
    drivers: dict = field(default_factory=dict)
    free_agents: list = field(default_factory=list)
    free_staff: list = field(default_factory=list)
    regulations: dict = field(default_factory=dict)
    proposals: list = field(default_factory=list)
    history_data: dict = field(default_factory=dict)
    engine_makers: dict = field(default_factory=dict)
    results: list = field(default_factory=list)
    inbox: list = field(default_factory=list)
    season_history: list = field(default_factory=list)
    pending_votes: list = field(default_factory=list)
    rng: random.Random = None

    # ------------------------------------------------------------- creazione
    @classmethod
    def new_game(cls, team_id: str, constructor: bool = True, seed: int | None = None) -> "GameState":
        seed = seed if seed is not None else random.randrange(1 << 30)
        gs = cls(player_team=team_id, player_is_constructor=constructor, seed=seed)
        gs.rng = random.Random(seed)

        tdata = _load("tracks.json")
        gs.tracks = [Track.from_dict(t) for t in tdata["tracks"]]

        regs = _load("regulations.json")
        gs.regulations = regs["current"]
        gs.proposals = regs["proposals"]
        gs.history_data = regs["history"]
        gs.commission = regs["commission"]
        gs.season = gs.regulations.get("season", 2026)

        teamdata = _load("teams.json")
        gs.engine_makers = teamdata["engine_manufacturers"]

        for td in teamdata["teams"]:
            engine = dict(gs.engine_makers[td["engine"]])
            team = Team(
                id=td["id"], name=td["name"], short=td["short"], base=td["base"],
                colour=td["colour"], accent=td["accent"], founded=td["founded"],
                engine=td["engine"], works=td["works"], reputation=td["reputation"],
                budget_base=td["budget_base"], cash=td["cash"],
                facilities=dict(td["facilities"]), philosophy=td["philosophy"],
                titles=dict(td["titles"]),
            )
            team.car = Car.build(td["car"], engine, gs.regulations)
            team.is_player = (td["id"] == team_id)
            team.engine_customer_cost = 0.0 if td["works"] else engine.get("cost_per_customer", 25.0)
            team.resource_alloc = {k: 1.0 / len(C.CAR_PARTS) for k in C.CAR_PARTS}
            gs.teams[team.id] = team

        ddata = _load("drivers.json")
        for d in ddata["drivers"]:
            drv = Driver.from_dict(d)
            gs.drivers[drv.id] = drv
            if drv.team in gs.teams:
                gs.teams[drv.team].drivers.append(drv.id)
        for d in ddata["free_agents"]:
            gs.free_agents.append(Driver.from_dict(d))

        gs._calibrate_tracks()
        gs._build_staff()

        # il giocatore puo' decidere di costruirsi il motore o restare cliente
        pt = gs.teams[team_id]
        if constructor and not pt.works:
            gs.pu_program = {"own": False, "level": 55.0, "invested": 0.0, "ready_season": gs.season + 2}
            gs.push(f"Progetto power unit avviato: prima unita' propria attesa per il {gs.season + 2}.",
                    "tecnico")
        else:
            gs.pu_program = {"own": pt.works, "level": 100.0 if pt.works else 0.0,
                             "invested": 0.0, "ready_season": gs.season}

        gs.push(f"Benvenuto alla guida di {pt.name}. Stagione {gs.season}: nuovo ciclo tecnico.", "team")
        return gs

    def _calibrate_tracks(self) -> None:
        """Allinea il modello di giro ai tempi reali usando una vettura di riferimento."""
        ref_spec = {k: 85.0 for k in C.CAR_PARTS}
        ref_engine = {"power": 90, "ers": 88, "reliability": 86, "efficiency": 87}
        ref = Car.build(ref_spec, ref_engine, self.regulations)
        for tr in self.tracks:
            tr.calibrate(ref)

    def _build_staff(self) -> None:
        sdata = _load("staff.json")
        self.staff_roles = sdata["roles"]
        pool = sdata["name_pool"]
        named = {}
        for s in sdata["named_staff"]:
            st = Staff.from_dict(s)
            named.setdefault(st.team, []).append(st)

        for team in self.teams.values():
            have = named.get(team.id, [])
            team.staff.extend(have)
            filled = {s.role for s in have}
            level = 44.0 + team.reputation * 0.42
            for role, meta in self.staff_roles.items():
                slots = meta.get("slots", 1)
                existing = len([s for s in team.staff if s.role == role])
                lvl = level * ROLE_LEVEL_FROM_REP.get(role, 0.95)
                for i in range(slots - existing):
                    st = generate_staff(role, lvl, self.rng, pool, self.season, team.id)
                    team.staff.append(st)
            # assegna gli ingegneri di pista ai due piloti
            engs = team.roles("race_engineer")
            for i, drv_id in enumerate(team.drivers[:len(engs)]):
                engs[i].assigned_driver = drv_id

        for s in sdata["free_staff"]:
            self.free_staff.append(Staff.from_dict(s))
        for _ in range(14):
            role = self.rng.choice(list(self.staff_roles.keys()))
            self.free_staff.append(generate_staff(role, self.rng.uniform(52, 76), self.rng,
                                                  pool, self.season, None))

    # -------------------------------------------------------------- utility
    @property
    def player(self) -> Team:
        return self.teams[self.player_team]

    @property
    def next_track(self) -> Track | None:
        return self.tracks[self.round] if self.round < len(self.tracks) else None

    def team_of(self, driver_id: str) -> Team | None:
        d = self.drivers.get(driver_id)
        return self.teams.get(d.team) if d and d.team else None

    def drivers_of(self, team_id: str) -> list:
        return [self.drivers[d] for d in self.teams[team_id].drivers if d in self.drivers]

    def push(self, text: str, kind: str = "info") -> None:
        self.inbox.insert(0, {"season": self.season, "round": self.round, "kind": kind, "text": text})
        del self.inbox[80:]

    def points_table(self) -> list:
        return self.regulations["sporting"]["points"]

    # ---------------------------------------------------------- classifiche
    def driver_standings(self) -> list:
        ds = [d for d in self.drivers.values() if d.team]
        ds.sort(key=lambda d: (-d.points, -d.wins, -d.podiums))
        return ds

    def constructor_standings(self) -> list:
        ts = list(self.teams.values())
        ts.sort(key=lambda t: (-t.points, -t.wins, -t.podiums))
        return ts

    def position_of(self, team_id: str) -> int:
        for i, t in enumerate(self.constructor_standings(), 1):
            if t.id == team_id:
                return i
        return len(self.teams)

    # ------------------------------------------------------------ salvataggi
    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False)

    @classmethod
    def load(cls, path) -> "GameState":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict:
        return {
            "season": self.season, "round": self.round, "phase": self.phase,
            "player_team": self.player_team, "player_is_constructor": self.player_is_constructor,
            "seed": self.seed, "regulations": self.regulations,
            "pu_program": getattr(self, "pu_program", {}),
            "engine_makers": self.engine_makers,
            "inbox": self.inbox, "season_history": self.season_history,
            "results": [
                {"track_id": r.track_id, "round": r.round, "season": r.season, "kind": r.kind,
                 "order": r.order, "pole": r.pole, "fastest_lap": r.fastest_lap, "weather": r.weather}
                for r in self.results
            ],
            "drivers": {k: v.to_dict() for k, v in self.drivers.items()},
            "free_agents": [d.to_dict() for d in self.free_agents],
            "free_staff": [s.to_dict() for s in self.free_staff],
            "teams": {
                t.id: {
                    "cash": t.cash, "points": t.points, "wins": t.wins, "podiums": t.podiums,
                    "spent": t.spent, "reputation": t.reputation, "facilities": t.facilities,
                    "drivers": t.drivers, "last_position": t.last_position,
                    "resource_alloc": t.resource_alloc, "upgrades_done": t.upgrades_done,
                    "engine": t.engine, "works": t.works,
                    "staff": [s.to_dict() for s in t.staff],
                    "dev_projects": [asdict(p) for p in t.dev_projects],
                    "car_parts": {k: {"perf": p.perf, "condition": p.condition}
                                  for k, p in t.car.parts.items()},
                    "setup": t.car.setup,
                } for t in self.teams.values()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        gs = cls.new_game(data["player_team"], data.get("player_is_constructor", True),
                          seed=data.get("seed"))
        base_sprints = gs.regulations["sporting"].get("sprint_events")
        gs.season = data["season"]
        gs.round = data["round"]
        gs.phase = data["phase"]
        gs.regulations = data["regulations"]
        gs.pu_program = data.get("pu_program", {})
        gs.engine_makers.update(data.get("engine_makers", {}))
        gs.inbox = data.get("inbox", [])
        gs.season_history = data.get("season_history", [])
        gs.results = [RaceResult(**r) for r in data.get("results", [])]

        gs.drivers = {k: Driver.from_dict(v) for k, v in data["drivers"].items()}
        gs.free_agents = [Driver.from_dict(d) for d in data.get("free_agents", [])]
        gs.free_staff = [Staff.from_dict(s) for s in data.get("free_staff", [])]

        for tid, td in data["teams"].items():
            t = gs.teams[tid]
            t.cash = td["cash"]; t.points = td["points"]; t.wins = td["wins"]
            t.podiums = td["podiums"]; t.spent = td["spent"]; t.reputation = td["reputation"]
            t.facilities = td["facilities"]; t.drivers = td["drivers"]
            t.last_position = td["last_position"]; t.resource_alloc = td["resource_alloc"]
            t.upgrades_done = td.get("upgrades_done", 0)
            t.engine = td.get("engine", t.engine); t.works = td.get("works", t.works)
            t.car.engine = dict(gs.engine_makers[t.engine])
            t.staff = [Staff.from_dict(s) for s in td["staff"]]
            t.dev_projects = [Project(**p) for p in td.get("dev_projects", [])]
            for k, p in td["car_parts"].items():
                if k in t.car.parts:
                    t.car.parts[k].perf = p["perf"]
                    t.car.parts[k].condition = p["condition"]
            t.car.setup = td.get("setup", t.car.setup)

        gs._sync_to_regulations(base_sprints)
        return gs

    def _sync_to_regulations(self, base_sprints=None) -> None:
        """Riporta vetture e calendario in linea col regolamento caricato.

        Le vetture nascono dal regolamento di `data/`: senza questo passaggio
        ogni norma votata in Commissione (aero, peso, sprint) si perderebbe al
        primo caricamento.
        """
        aero = self.regulations.get("aero", {})
        for t in self.teams.values():
            t.car.reg_downforce_index = aero.get("downforce_index", t.car.reg_downforce_index)
            t.car.active_aero_allowed = aero.get("active_aero", t.car.active_aero_allowed)
            t.car.mass_base = float(self.regulations.get("min_weight_kg", t.car.mass_base))

        want = self.regulations["sporting"].get("sprint_events")
        if want is not None and base_sprints is not None and want != base_sprints:
            from . import rules
            rules._resync_sprints(self, want)
