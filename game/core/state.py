"""Stato della partita: costruzione del mondo, calendario, classifiche, salvataggi."""
from __future__ import annotations

import json
import random
import zlib
from dataclasses import asdict, dataclass, field, fields

from .. import config as C
from ..model.car import Car
from ..model.people import Driver, Staff, generate_staff
from ..model.team import Team
from ..model.track import Track
from .development import Project, Trial

ROLE_LEVEL_FROM_REP = {
    "technical_director": 1.00, "chief_designer": 0.95, "head_of_aero": 0.97,
    "head_of_powertrain": 0.93, "head_of_strategy": 0.96, "race_engineer": 0.92,
    "performance_engineer": 0.90, "chief_mechanic": 0.90, "head_of_scouting": 0.86,
    "team_principal": 1.02, "financial_director": 0.94,
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
    penalties: list = field(default_factory=list)


@dataclass
class GameState:
    season: int = 2026
    round: int = 0                 # indice della prossima gara
    phase: str = "preseason"       # preseason | season | offseason
    player_team: str = ""
    player_is_constructor: bool = True
    seed: int = 0
    race_distance: float = 1.0     # durata delle gare rispetto alla realta'
    editor_used: bool = False      # la partita e' stata toccata con l'editor
    track_history: dict = field(default_factory=dict)   # albo d'oro per circuito

    tracks: list = field(default_factory=list)
    candidates: list = field(default_factory=list)   # circuiti fuori calendario
    private_tracks: dict = field(default_factory=dict)  # piste di proprieta' delle squadre
    teams: dict = field(default_factory=dict)
    drivers: dict = field(default_factory=dict)
    free_agents: list = field(default_factory=list)
    free_staff: list = field(default_factory=list)
    regulations: dict = field(default_factory=dict)
    proposals: list = field(default_factory=list)
    history_data: dict = field(default_factory=dict)
    engine_makers: dict = field(default_factory=dict)
    campionati: dict = field(default_factory=dict)   # come e' finita ogni categoria
    results: list = field(default_factory=list)
    inbox: list = field(default_factory=list)
    season_history: list = field(default_factory=list)
    pending_votes: list = field(default_factory=list)
    rng: random.Random = None

    # ------------------------------------------------------------- creazione
    @classmethod
    def new_game(cls, team_id: str, constructor: bool = True, seed: int | None = None,
                 founding: dict | None = None) -> "GameState":
        """Comincia una carriera.

        Con `founding` non si prende in mano una squadra che c'e' gia': se ne
        mette in griglia una nuova, che paga per entrare e parte da niente.
        """
        seed = seed if seed is not None else random.randrange(1 << 30)
        gs = cls(player_team=team_id, player_is_constructor=constructor, seed=seed)
        gs.rng = random.Random(seed)

        tdata = _load("tracks.json")
        gs.tracks = [Track.from_dict(t) for t in tdata["tracks"]]
        # circuiti che non corrono ma potrebbero entrare in calendario
        gs.candidates = [Track.from_dict(t) for t in tdata.get("candidates", [])]
        # le piste di proprieta' stanno fuori dal calendario e fuori dai
        # candidati: non correranno mai un gran premio, servono per provare
        gs.private_tracks = {t["id"]: Track.from_dict(t) for t in tdata.get("private", [])}

        regs = _load("regulations.json")
        gs.regulations = regs["current"]
        gs.proposals = regs["proposals"]
        gs.history_data = regs["history"]
        gs.commission = regs["commission"]
        gs.season = gs.regulations.get("season", 2026)

        teamdata = _load("teams.json")
        gs.engine_makers = teamdata["engine_manufacturers"]

        for td in teamdata["teams"]:
            engine = gs.engine_makers[td["engine"]]
            team = Team(
                id=td["id"], name=td["name"], short=td["short"], base=td["base"],
                colour=td["colour"], accent=td["accent"], founded=td["founded"],
                engine=td["engine"],
                works=(td.get("pu_status", "customer") == "works" if "pu_status" in td
                       else td["works"]),
                reputation=td["reputation"],
                budget_base=td["budget_base"], cash=td["cash"],
                facilities=dict(td["facilities"]), philosophy=td["philosophy"],
                titles=dict(td["titles"]),
                pu_status=td.get("pu_status", "works" if td["works"] else "customer"),
                parent_team=td.get("parent_team", ""),
                pu_capable=td.get("pu_capable", True),
                pu_reason=td.get("pu_reason", ""),
                # da qui escono ore di galleria, premi e valore per gli sponsor:
                # senza, la prima stagione tratterebbe tutti come sesti
                last_position=td.get("last_position", 6),
                track_name=td.get("private_track_name", ""),
                track_id=td.get("private_track_id", ""),
                academy_name=td.get("academy_name", ""),
                heritage=bool(td.get("heritage", False)),
            )
            team.car = Car.build(td["car"], engine, gs.regulations)
            # la filosofia non e' una scritta sulla scheda: da' alla macchina
            # una forma, e quella forma decide dove va forte
            from .engineering import shape_car
            shape_car(team, 1.5)
            team.is_player = (td["id"] == team_id)
            team.engine_customer_cost = engine.get("cost_per_customer", 25.0)
            team.resource_alloc = {k: 1.0 / len(C.CAR_PARTS) for k in C.CAR_PARTS}
            team.set_clock(gs.season, 1, 0)
            # le strutture partono a meta' del periodo di grazia: nessuna e'
            # appena costruita, nessuna e' gia' da buttare
            from .facilities import GRACE_SEASONS
            team.facility_age = {k: GRACE_SEASONS * 0.5 for k in team.facilities}
            team.setup_knowledge = {}
            # l'organico dei reparti, tarato su quanto pesa l'organigramma
            from .departments import starting_workforce
            team.workforce = starting_workforce(team)
            team.hired_this_season = {}
            gs.teams[team.id] = team

        # la dodicesima squadra: non e' nei dati, la si fonda adesso
        if founding:
            from . import newteam
            founding = dict(founding)
            founding["id"] = team_id
            gs.founding = founding
            newteam.create(gs, founding)

        gs._vivai = {td["id"]: list(td.get("academy") or []) for td in teamdata["teams"]}
        ddata = _load("drivers.json")
        for d in ddata["drivers"]:
            drv = Driver.from_dict(d)
            gs.drivers[drv.id] = drv
            if drv.team in gs.teams:
                gs.teams[drv.team].drivers.append(drv.id)
        for d in ddata["free_agents"]:
            gs.free_agents.append(Driver.from_dict(d))

        # i ragazzi dei vivai esistenti passano dagli svincolati alla squadra
        # che li segue davvero: e' li' che stanno, non sul mercato libero
        for tid, ragazzi in getattr(gs, "_vivai", {}).items():
            squadra = gs.teams.get(tid)
            if squadra is None:
                continue
            for did in ragazzi:
                drv = next((x for x in gs.free_agents if x.id == did), None)
                if drv is None:
                    continue
                gs.free_agents.remove(drv)
                gs.drivers[drv.id] = drv
                drv.team = tid
                drv.seat = "academy"
                drv.salary = round(max(0.2, drv.salary * 0.35), 2)
                squadra.academy.append(drv.id)
        # un vivaio aperto non sta mai vuoto: chi non ha ragazzi noti ne ha
        # comunque di suoi, solo che non li conosce ancora nessuno
        from . import academy as _acc
        for squadra in gs.teams.values():
            if _acc.has(squadra) and len(squadra.academy) < 2:
                _acc.intake(gs, squadra, 2 - len(squadra.academy))
        # e ognuno si porta dietro il gradino da cui arriva: senza, la prima
        # stagione li schiererebbe tutti in Formula 2
        from . import serie as _serie
        for squadra in gs.teams.values():
            for did in squadra.academy:
                drv = gs.drivers.get(did)
                if drv is not None and not getattr(drv, "ultima_serie", ""):
                    drv.ultima_serie = _serie.seme_scala(gs, drv)
        # e dove correranno quest'anno: al primo giorno decide il responsabile,
        # poi il giocatore fa quello che vuole
        _serie.pianifica(gs)

        # e i due che accettano di salirci sopra: vanno presi fra gli svincolati
        # prima che il mercato e gli sponsor guardino chi c'e' in griglia
        if founding:
            from . import newteam
            newteam.first_lineup(gs, gs.teams[team_id])

        gs.sponsor_pool = _load("sponsors.json")["sponsors"]
        gs._calibrate_tracks()
        gs._build_staff()
        gs.sync_engines()

        # il giocatore puo' partire gia' col proprio reparto motori, fondarlo
        # subito, o restare cliente e decidere piu' avanti
        from . import powertrain
        pt = gs.teams[team_id]
        gs.pu_program = {"own": pt.works, "started": pt.works, "level": 0.0,
                         "invested": 0.0, "ready_season": gs.season}
        if constructor and not pt.works:
            ok, msg = powertrain.start_program(gs, pt)
            gs.push(msg if ok else
                    f"Reparto power unit non avviato: {msg} Si puo' fondare piu' avanti "
                    f"dalla pagina Power unit.", "tecnico")

        from . import sponsors
        sponsors.bootstrap(gs)

        # il riferimento del ciclo: dove sta la griglia adesso. Da qui si misura
        # quanto costa guadagnare ancora, e a ogni regolamento nuovo si rifa'
        pezzi = [p.perf for t in gs.teams.values() for p in t.car.parts.values()]
        gs.regulations["cycle_base"] = round(sum(pezzi) / max(1, len(pezzi)), 2)

        if founding:
            from . import newteam
            newteam.welcome(gs, pt)
            gs.push(f"{pt.name} entra in Formula 1. Stagione {gs.season}: si "
                    f"comincia da zero, e da ultimi.", "team")
        else:
            gs.push(f"Benvenuto alla guida di {pt.name}. Stagione {gs.season}: "
                    f"nuovo ciclo tecnico.", "team")
        from .setup import new_weekend
        new_weekend(gs)
        return gs

    def _restore_calendar(self, calendario, candidati) -> None:
        """Rimette il calendario com'era: le gare cambiano di stagione in stagione."""
        if not calendario:
            return
        tutti = {t.id: t for t in list(self.tracks) + list(self.candidates)}
        nuovi = []
        for voce in calendario:
            t = tutti.get(voce["id"])
            if t is None:
                continue
            t.contract_until = voce.get("contract_until", t.contract_until)
            t.fee = voce.get("fee", t.fee)
            t.month = voce.get("month", t.month)
            nuovi.append(t)
        if not nuovi:
            return
        self.tracks = nuovi
        rimasti = [t for k, t in tutti.items() if t not in nuovi]
        for voce in (candidati or []):
            t = tutti.get(voce["id"])
            if t is not None and t not in nuovi:
                t.contract_until = voce.get("contract_until", t.contract_until)
                t.fee = voce.get("fee", t.fee)
        self.candidates = rimasti

    def _ref_car(self):
        """La vettura campione con cui si misurano i circuiti."""
        ref_spec = {k: 85.0 for k in C.CAR_PARTS}
        ref_engine = {"power": 90, "ers": 88, "reliability": 86, "efficiency": 87}
        return Car.build(ref_spec, ref_engine, self.regulations)

    def _calibrate_tracks(self) -> None:
        """Allinea il modello di giro ai tempi reali usando una vettura di riferimento."""
        ref = self._ref_car()
        for tr in list(self.tracks) + list(self.candidates):
            tr.calibrate(ref)

    def refresh_tracks(self) -> None:
        """Rimisura i circuiti dopo un cambio di regolamento, senza ritararli.

        La taratura allinea il modello a pole vere del passato: quella non si
        tocca, se no una regola che rende le macchine piu' lente si cancella da
        sola. Quello che si rifa' e' il resto - dove si frena, quanta energia
        si riprende, dove si apre l'ala - perche' con una macchina diversa quei
        posti si spostano davvero.
        """
        ref = self._ref_car()
        for tr in list(self.tracks) + list(self.candidates):
            tr.rimisura(ref)

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
        # un mercato degli ingegneri vero: tanta gente onesta, qualcuno molto
        # bravo, e sempre almeno un paio di nomi per ogni ruolo
        ruoli = list(self.staff_roles.keys())
        for i in range(48):
            role = ruoli[i % len(ruoli)] if i < len(ruoli) * 2 else self.rng.choice(ruoli)
            lvl = self.rng.gauss(64.0, 8.5)
            if self.rng.random() < 0.12:
                lvl = self.rng.uniform(78.0, 88.0)      # il pezzo pregiato
            self.free_staff.append(generate_staff(role, max(46.0, min(90.0, lvl)),
                                                  self.rng, pool, self.season, None))

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

    def reserves_of(self, team_id: str) -> list:
        return [self.drivers[d] for d in self.teams[team_id].reserves if d in self.drivers]

    def lineup_of(self, team_id: str) -> list:
        """Chi scende in pista davvero.

        I titolari, con la riserva che prende il posto di chi sta scontando una
        squalifica: e' esattamente per questo che un terzo pilota lo tengono
        tutti, e prima di averlo si correva in uno solo.
        """
        t = self.teams[team_id]
        panchina = [self.drivers[d] for d in t.reserves
                    if d in self.drivers and self.drivers[d].banned_races <= 0]
        out = []
        for did in t.drivers:
            d = self.drivers.get(did)
            if d is None:
                continue
            if d.banned_races > 0:
                if panchina:
                    out.append(panchina.pop(0))
                continue
            out.append(d)
        return out

    def sync_engines(self) -> None:
        """Riaggancia ogni vettura al proprio motorista.

        Le vetture puntano al dizionario del motorista, non a una copia: cosi'
        lo sviluppo della power unit arriva anche a chi la compra da cliente.
        """
        from . import powertrain
        for t in self.teams.values():
            if t.car is not None and t.engine in self.engine_makers:
                t.car.engine = self.engine_makers[t.engine]
                t.car.pu_integration = powertrain.integration(self, t)
                t.engine_customer_cost = powertrain.supply_cost(self, t)

    def view_rng(self, *key) -> random.Random:
        """Generatore per le schermate, separato da quello della partita.

        Le pagine mostrano stime e anteprime che hanno bisogno di un po' di
        casualita', ma pescarla da `self.rng` significherebbe che guardare una
        schermata cambia gare, mercato e sviluppo. Questo e' deterministico
        per stagione e gara: stabile mentre lo guardi, diverso al prossimo
        weekend, e non tocca il corso della partita.
        """
        raw = "|".join(str(x) for x in (self.seed, self.season, self.round) + key)
        return random.Random(zlib.crc32(raw.encode()))

    def push(self, text: str, kind: str = "info") -> None:
        self.inbox.insert(0, {"season": self.season, "round": self.round, "kind": kind, "text": text})
        del self.inbox[80:]

    def points_table(self) -> list:
        return self.regulations["sporting"]["points"]

    # ---------------------------------------------------------- classifiche
    def driver_standings(self) -> list:
        # nel mondiale ci sono i titolari e chi ha corso al posto loro: un
        # terzo pilota che non e' mai salito in macchina non e' in classifica
        ds = [d for d in self.drivers.values()
              if d.team and (d.seat == "titolare" or d.points or d.races)]
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
            "editor_used": bool(getattr(self, "editor_used", False)),
            "track_history": self.track_history,
            "race_distance": self.race_distance,
            "founding": getattr(self, "founding", None),
            "pu_program": getattr(self, "pu_program", {}),
            "pu_specs": getattr(self, "pu_specs", {}),
            "calendar": [{"id": t.id, "contract_until": t.contract_until, "fee": t.fee,
                          "month": t.month} for t in self.tracks],
            "candidates": [{"id": t.id, "contract_until": t.contract_until, "fee": t.fee}
                           for t in self.candidates],
            "engine_makers": self.engine_makers,
            # la classifica intera, non solo la testa: un nostro ragazzo che ha
            # chiuso ventesimo va ritrovato al ventesimo posto anche domani
            "campionati": {sid: {"stagione": c.stagione,
                                 "ordine": [[p.nome, round(p.forza, 2), p.squadra,
                                             p.driver_id, round(p.punti, 1), p.vittorie,
                                             p.podi, p.superlicenza]
                                            for p in c.ordine]}
                           for sid, c in (getattr(self, "campionati", None) or {}).items()},
            "inbox": self.inbox, "season_history": self.season_history,
            "results": [
                {"track_id": r.track_id, "round": r.round, "season": r.season, "kind": r.kind,
                 "order": r.order, "pole": r.pole, "fastest_lap": r.fastest_lap,
                 "weather": r.weather, "penalties": r.penalties}
                for r in self.results
            ],
            "drivers": {k: v.to_dict() for k, v in self.drivers.items()},
            "free_agents": [d.to_dict() for d in self.free_agents],
            "free_staff": [s.to_dict() for s in self.free_staff],
            "teams": {
                t.id: {
                    "cash": t.cash, "points": t.points, "wins": t.wins, "podiums": t.podiums,
                    "spent": t.spent, "capex_log": t.capex_log or {}, "austerity": t.austerity,
                    "track_id": t.track_id, "track_name": t.track_name,
                    "reputation": t.reputation, "facilities": t.facilities,
                    "entry_season": t.entry_season,
                    "facility_age": t.facility_age or {},
                    "test_days_used": t.test_days_used,
                    "preseason_done": list(t.preseason_done or []), "correlation": t.correlation,
                    "setup_knowledge": t.setup_knowledge or {},
                    "setup_paper": t.setup_paper or {},
                    "setup_paper_track": t.setup_paper_track,
                    "sim_sessions": t.sim_sessions,
                    "car_understanding": t.car_understanding,
                    "workforce": t.workforce or {}, "pu_building": t.pu_building,
                    "hired_this_season": t.hired_this_season or {},
                    "drivers": t.drivers, "reserves": t.reserves,
                    "academy": t.academy, "academy_name": t.academy_name,
                    "last_position": t.last_position,
                    "resource_alloc": t.resource_alloc, "upgrades_done": t.upgrades_done,
                    "upgrade_log": list(t.upgrade_log or [])[-120:],
                    "next_reg_share": t.next_reg_share, "reg_prep": t.reg_prep,
                    "arch_prog": t.arch_prog or {}, "arch_exp": t.arch_exp or {},
                    "next_car_brief": t.next_car_brief or {},
                    "next_car_work": t.next_car_work or {},
                    "ledger": t.ledger[-1500:],
                    "deals": [d.to_dict() for d in t.deals],
                    "cur_season": t.cur_season, "cur_month": t.cur_month,
                    "cur_round": t.cur_round,
                    "engine": t.engine, "works": t.works, "pu_status": t.pu_status,
                    "parent_team": t.parent_team,
                    "pu_partner_races": t.pu_partner_races,
                    "pu_partner_engine": t.pu_partner_engine,
                    "staff": [s.to_dict() for s in t.staff],
                    "dev_projects": [asdict(p) for p in t.dev_projects],
                    "spec_trials": [asdict(x) for x in t.spec_trials],
                    "car_parts": {k: {"perf": p.perf, "condition": p.condition,
                                      "focus": p.focus}
                                  for k, p in t.car.parts.items()},
                    "setup": t.car.setup, "setups": t.setups or {},
                    "auto_dev": t.auto_dev, "auto_setup": t.auto_setup,
                    "vivaio_auto": t.vivaio_auto,
                    "part_delta": t.part_delta or {},
                    "last_spec": t.last_spec or {},
                    "kits": [asdict(k) for k in (t.kits or [])],
                    "balance": t.car.balance,
                } for t in self.teams.values()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        # una squadra fondata dal giocatore non sta in teams.json: si rifonda
        # com'era e poi le si rimettono sopra i valori del salvataggio
        gs = cls.new_game(data["player_team"], data.get("player_is_constructor", True),
                          seed=data.get("seed"), founding=data.get("founding"))
        base_sprints = gs.regulations["sporting"].get("sprint_events")
        gs.season = data["season"]
        gs.round = data["round"]
        gs.phase = data["phase"]
        gs.race_distance = float(data.get("race_distance", 1.0))
        gs.editor_used = bool(data.get("editor_used", False))
        gs.track_history = dict(data.get("track_history") or {})
        gs.regulations = data["regulations"]
        gs.pu_program = data.get("pu_program", {})
        gs.pu_specs = data.get("pu_specs", {})
        gs._restore_calendar(data.get("calendar"), data.get("candidates"))
        gs.engine_makers.update(data.get("engine_makers", {}))
        from . import serie as _serie
        gs.campionati = {}
        for sid, c in (data.get("campionati") or {}).items():
            gs.campionati[sid] = _serie.Campionato(
                serie=sid, stagione=int(c.get("stagione", gs.season)),
                ordine=[_serie.Posto(nome=r[0], forza=r[1], squadra=r[2], driver_id=r[3],
                                     punti=r[4], vittorie=r[5], podi=r[6],
                                     superlicenza=r[7])
                        for r in c.get("ordine", [])])
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
            t.entry_season = int(td.get("entry_season", 0) or 0)
            t.capex_log = dict(td.get("capex_log") or {})
            t.austerity = float(td.get("austerity", 0.0))
            t.track_id = td.get("track_id", t.track_id)
            t.track_name = td.get("track_name", t.track_name)
            t.facilities = td["facilities"]
            t.facility_age = dict(td.get("facility_age") or {})
            t.test_days_used = td.get("test_days_used", 0)
            t.preseason_done = list(td.get("preseason_done") or [])
            t.correlation = td.get("correlation", 0.0)
            t.setup_knowledge = dict(td.get("setup_knowledge") or {})
            t.setup_paper = dict(td.get("setup_paper") or {})
            t.setup_paper_track = td.get("setup_paper_track", "")
            t.sim_sessions = td.get("sim_sessions", 0)
            t.car_understanding = td.get("car_understanding", 0.0)
            t.workforce = dict(td.get("workforce") or {})
            t.pu_building = bool(td.get("pu_building", False))
            t.hired_this_season = dict(td.get("hired_this_season") or {})
            if not t.workforce:
                from .departments import starting_workforce
                t.workforce = starting_workforce(t)
            t.drivers = td["drivers"]
            t.reserves = list(td.get("reserves") or [])
            t.academy = list(td.get("academy") or [])
            t.academy_name = td.get("academy_name", "")
            t.last_position = td["last_position"]; t.resource_alloc = td["resource_alloc"]
            t.upgrades_done = td.get("upgrades_done", 0)
            t.upgrade_log = list(td.get("upgrade_log") or [])
            t.next_reg_share = td.get("next_reg_share", 0.0)
            from .sponsors import Deal
            t.deals = [Deal(**x) for x in td.get("deals", [])]
            t.ledger = list(td.get("ledger", []))
            t.cur_season = td.get("cur_season", gs.season)
            t.cur_month = td.get("cur_month", 1)
            t.cur_round = td.get("cur_round", 0)
            t.reg_prep = td.get("reg_prep", 0.0)
            t.arch_prog = dict(td.get("arch_prog") or {})
            t.arch_exp = dict(td.get("arch_exp") or {})
            t.next_car_brief = dict(td.get("next_car_brief") or {})
            t.next_car_work = dict(td.get("next_car_work") or {})
            t.engine = td.get("engine", t.engine); t.works = td.get("works", t.works)
            t.pu_status = td.get("pu_status", t.pu_status)
            t.parent_team = td.get("parent_team", t.parent_team)
            t.pu_partner_races = td.get("pu_partner_races", 0)
            t.pu_partner_engine = td.get("pu_partner_engine", "")
            t.car.engine = gs.engine_makers[t.engine]
            t.staff = [Staff.from_dict(s) for s in td["staff"]]
            campi = {f.name for f in fields(Project)}
            t.dev_projects = [Project(**{k: v for k, v in p.items() if k in campi})
                              for p in td.get("dev_projects", [])]
            campi = {f.name for f in fields(Trial)}
            t.spec_trials = [Trial(**{k: v for k, v in x.items() if k in campi})
                             for x in td.get("spec_trials", [])]
            for k, p in td["car_parts"].items():
                if k in t.car.parts:
                    t.car.parts[k].perf = p["perf"]
                    t.car.parts[k].condition = p["condition"]
                    t.car.parts[k].focus = p.get("focus", "")
            t.car.setup = td.get("setup", t.car.setup)
            t.car.balance = float(td.get("balance", 0.0))
            from .kits import Kit
            t.part_delta = {k: dict(v) for k, v in (td.get("part_delta") or {}).items()}
            t.last_spec = dict(td.get("last_spec") or {})
            campi_k = {f.name for f in fields(Kit)}
            t.kits = [Kit(**{k: v for k, v in x.items() if k in campi_k})
                      for x in (td.get("kits") or [])]
            t.auto_dev = bool(td.get("auto_dev", False))
            t.auto_setup = bool(td.get("auto_setup", True))
            t.vivaio_auto = bool(td.get("vivaio_auto", True))
            t.setups = {k: dict(v) for k, v in (td.get("setups") or {}).items()}

        gs.sync_engines()
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
