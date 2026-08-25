"""Orchestrazione del weekend: prove libere, qualifica, griglia, gara."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .. import config as C
from . import pace
from .weekend import BURN_KG_PER_LAP, DRIVER_S_PER_POINT, Entrant, RaceSim, Weather


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
    grid_notes: list = field(default_factory=list)   # penalizzazioni scontate in griglia
    # il fine settimana con la sprint ha due qualifiche e due griglie: la
    # Sprint Qualifying del venerdi' schiera la sprint, la qualifica del sabato
    # schiera il gran premio, e fra le due si puo' rimettere mano alla macchina
    sprint_quali_done: bool = False
    sprint_done: bool = False
    sprint_grid: list = field(default_factory=list)
    sprint_pole: str = ""
    sprint_times: dict = field(default_factory=dict)
    tyre_choice: dict = field(default_factory=dict)  # team_id -> set scelti per mescola
    tyre_stock: dict = field(default_factory=dict)   # driver_id -> set ancora a disposizione
    tyres_published: bool = False                    # le scelte sono state rese pubbliche
    # quanta gomma e' stata stesa sull'asfalto: cresce turno dopo turno e la
    # pioggia la porta via. E' il motivo per cui la domenica si gira piu' forte
    # del venerdi' anche con la stessa macchina
    rubber: float = pace.PISTA_VERDE


# Quanto lascia un turno in pista. Girare e' la sola cosa che insegna davvero:
# i dati del venerdi' valgono per la domenica, e quello che si e' capito del
# circuito vale per l'anno prossimo. Sono numeri piccoli di proposito - un
# weekend non e' una giornata di prove private - ma sono ventiquattro l'anno.
CAPIRE_TURNO = 0.014       # della macchina: quota del divario ancora da colmare
CIRCUITO_TURNO = 0.035     # del circuito: si somma, e invecchia di anno in anno


def _learn_from_running(gs, ws, quota: float = 1.0) -> None:
    """Quello che tutte le squadre si portano a casa da un turno in pista.

    La conoscenza della vettura non cresce leggendo: cresce girandoci. Quanto se
    ne porta a casa dipende da chi legge i dati e da chi li racconta - un pilota
    che sa spiegare cosa fa la macchina vale un pomeriggio di lavoro.
    """
    from ..core import driving
    track = ws.track
    for team in gs.teams.values():
        piloti = gs.lineup_of(team.id)
        if not piloti:
            continue
        fb = sum(d.feedback for d in piloti) / len(piloti)
        resa = 0.30 + 0.70 * (0.55 * fb + 0.45 * team.setup_strength) / 100.0
        passo = CAPIRE_TURNO * quota * resa
        team.car_understanding = min(1.0, team.car_understanding
                                     + passo * (1.0 - team.car_understanding))
        if team.setup_knowledge is None:
            team.setup_knowledge = {}
        prima = float(team.setup_knowledge.get(track.id, 0.0))
        team.setup_knowledge[track.id] = min(
            1.0, prima + CIRCUITO_TURNO * quota * resa * (1.0 - 0.6 * prima))
        # e i piloti si fanno un'idea di cosa hanno sotto
        for d in piloti:
            driving.settle_confidence(gs, team, d, track, 0.10 + 0.22 * quota)


# --------------------------------------------------------------- base lap
def base_lap_for(gs, team, track, weather=None, driver=None, cond=None) -> float:
    """Il giro di riferimento di questa vettura, con l'assetto di questo pilota.

    Il conto vero sta in sim.pace: qui resta solo il nome con cui lo chiamano
    le schermate, che ragionano ancora in termini di meteo.
    """
    if cond is None:
        cond = pace.nominal(track)
        if weather is not None:
            cond.wet = weather.wet
            cond.air_temp = weather.air_temp
            cond.track_temp = weather.track_temp
            cond.wind = float(getattr(weather, "wind", cond.wind))
            cond.rho = pace.air_density(weather.air_temp, getattr(track, "altitude", 0.0))
    return pace.lap_base(gs, team, track, driver, cond)


def build_entrants(gs, track, cond, quali: bool = False) -> list:
    """Chi scende in pista, con che passo e in che condizioni."""
    from ..core import penalties
    from ..core.driving import FIDUCIA_BASE
    aff = pace.affinities(gs, track)
    out = []
    for team in gs.teams.values():
        # il pacchetto lavora uguale per tutti e due, l'assetto no
        pacchetto = gs.rng.gauss(0.0, 0.13)
        pit = (3.30 - 1.15 * (team.pit_strength / 100.0)
               + float(gs.regulations.get("pit_lane_penalty_s", 0.0)))
        for d in gs.lineup_of(team.id):
            base = pace.lap_base(gs, team, track, d, cond, aff.get(team.id, 0.0)) + pacchetto
            reso = pace.quali_rating(d, cond) if quali else pace.race_rating(d, cond)
            col = _hex(team.colour)
            out.append(Entrant(
                driver_id=d.id, team_id=team.id, code=d.code, name=d.short,
                colour=col, number=d.number, base_lap=base,
                skill=reso - gs.rng.gauss(0.0, 1.3),
                consistency=d.consistency,
                tyre_skill=d.tyre_mgmt, aggression=d.aggression, racecraft=d.racecraft,
                wet_skill=d.wet, stamina=d.fitness,
                confidence=float(getattr(d, "confidence", FIDUCIA_BASE)),
                reliability=team.car.reliability * penalties.health_factor(d),
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
    cond = pace.of_weekend(ws, "prove")
    notes = []
    for team in gs.teams.values():
        drivers = gs.drivers_of(team.id)
        fb = sum(d.feedback for d in drivers) / max(1, len(drivers))
        SETUP.learn_from_track(gs, team, track, fb, cond=cond)
        quota = 1.0
        if team.id == gs.player_team and not delegate_player:
            quota = 0.45      # il giocatore tiene in mano i regolatori
        SETUP.apply_paper(gs, team, quota)
        team.car.wear(0.55, track)
        # e ogni tanto qualcuno ci finisce dentro: e' l'unico modo in cui una
        # squadra che porta sempre due pezzi uguali si ritrova con le macchine
        # diverse
        from ..core import kits
        for d in drivers:
            riga = kits.practice_off(gs, team, d, track, ws.weather)
            if not riga:
                continue
            if team.id == gs.player_team:
                notes.append(riga)
            gs.push(f"{team.name}: {riga}", "tecnico")

    from ..core import tyres
    tyres.spend_practice(gs, ws)
    ws.practice_done += 1
    # la pista si gomma e il weekend insegna: sono le due cose che rendono la
    # domenica diversa dal venerdi'
    pace.rubber_in(ws, 0.014)
    _learn_from_running(gs, ws, 1.0)
    pt = gs.player
    piloti = gs.lineup_of(pt.id)
    eng = pt.role("technical_director")
    who = eng.name if eng else "Il muretto"
    for d in piloti:
        q = SETUP.believed_quality(pt, d)
        if q > 0.9:
            notes.append(f"{who} su {d.short}: in finestra, la macchina risponde bene.")
        elif q > 0.7:
            notes.append(f"{who} su {d.short}: ci siamo quasi, manca equilibrio.")
        else:
            notes.append(f"{who} su {d.short}: fuori finestra, servono modifiche.")
        for riga in SETUP.hints(pt, track, d)[:2]:
            notes.append(riga)
    ws.practice_notes = notes
    return notes


def learn_from_sprint(gs, ws: WeekendState) -> list:
    """Quello che la sprint ha insegnato, prima della qualifica del sabato.

    Sono cento chilometri di gara vera, non una sessione di prove: si scopre
    meno di un turno libero, ma si scopre sulla macchina carica. Fra sprint e
    qualifica il parco chiuso si riapre, quindi quello che si e' capito si fa
    ancora in tempo a montarlo.
    """
    from ..core import setup as SETUP
    track = ws.track
    for team in gs.teams.values():
        drivers = gs.drivers_of(team.id)
        fb = sum(d.feedback for d in drivers) / max(1, len(drivers))
        SETUP.learn_from_track(gs, team, track, fb, share=0.55,
                               cond=pace.of_weekend(ws, "sprint"))
        SETUP.apply_paper(gs, team, 1.0)
    pt = gs.player
    eng = pt.role("race_engineer") or pt.role("technical_director")
    chi = eng.name if eng else "Il muretto"
    note = []
    for d in gs.lineup_of(pt.id):
        q = SETUP.believed_quality(pt, d)
        if q > 0.9:
            note.append(f"{chi} su {d.short}: in gara la macchina ha risposto, ci siamo.")
        elif q > 0.7:
            note.append(f"{chi} su {d.short}: in gara mancava equilibrio, si puo' sistemare.")
        else:
            note.append(f"{chi} su {d.short}: fuori finestra, cosi' la qualifica la buttiamo.")
        for riga in SETUP.hints(pt, track, d)[:1]:
            note.append(riga)
    return note


def setup_hints(team, track, driver=None) -> list:
    """Indicazioni comprensibili su cosa cambiare, secondo il reparto."""
    from ..core import setup as SETUP
    return SETUP.hints(team, track, driver)


def auto_setup(gs, team, track, quality: float | None = None, driver=None) -> None:
    """Monta l'assetto che il reparto ritiene giusto, per uno o per tutti e due."""
    from ..core import setup as SETUP
    SETUP.ensure_paper(gs, team, track)
    SETUP.apply_paper(gs, team, 1.0, driver)


# ---------------------------------------------------------------- qualifica
# Quanti tentativi si fanno in ogni turno: vale il migliore, come in pista.
GIRI_PER_TURNO = 2
def run_qualifying(gs, ws: WeekendState, kind: str = "gp") -> list:
    """Un turno di qualifica: schiera il gran premio, o la sprint del sabato.

    Nel weekend sprint se ne corrono due, e non sono la stessa cosa: la Sprint
    Qualifying del venerdi' decide la griglia della sprint e basta, mentre le
    penalizzazioni in griglia si scontano nel gran premio.
    """
    track, weather = ws.track, ws.weather
    cond = pace.of_weekend(ws, "quali")
    ents = build_entrants(gs, track, cond, quali=True)
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
            t += (85.0 - e.skill) * DRIVER_S_PER_POINT
            t += 8.0 * 0.032                                  # serbatoio da qualifica
            # con cosa si scende in pista dipende da cosa e' rimasto nel camion
            mescola = tyres.quali_run(gs, ws, e.driver_id) if ws.tyre_stock else "soft"
            t -= tyres.QUALI_GAIN.get(mescola, 0.35)
            # la pista si gomma turno dopo turno: in Q3 si gira sull'asfalto
            # migliore di tutto il fine settimana
            t *= 1.0 - 0.0022 * phase
            if weather.wet > 0.05:
                t += (85.0 - e.wet_skill) * 0.06 * weather.wet * 4.0
            # in un turno di qualifica non si fa un giro solo: se ne fanno due e
            # vale il migliore. E' per questo che il tempo di un pilota regolare
            # somiglia a quello che vale davvero, e chi ne butta uno lo rifa'
            giri = []
            for _ in range(GIRI_PER_TURNO):
                giro = t + gs.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.0028
                                        + pace.wind_noise(cond))
                # chi non si fida della macchina il giro perfetto non lo trova
                sporco = 0.055 + (100.0 - e.consistency) * 0.0022
                sporco *= 1.0 + (65.0 - e.confidence) * 0.009
                if gs.rng.random() < max(0.010, sporco):
                    giro += gs.rng.uniform(0.4, 2.4)           # giro sporcato
                giri.append(giro)
            results.append((min(giri), e))
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
    griglia = [d for d, _ in order]
    # la pole resta a chi ha fatto il tempo: le penalita' spostano la griglia,
    # non cancellano il giro
    pole = griglia[0]
    for team in gs.teams.values():
        team.car.wear(0.4, track)
    # un turno in piu' sull'asfalto, e quello che si e' imparato girandoci
    pace.rubber_in(ws, 0.006)
    _learn_from_running(gs, ws, 0.55)
    if kind == "sprint":
        ws.sprint_grid, ws.sprint_times, ws.sprint_pole = griglia, times, pole
        ws.sprint_quali_done = True
        return ws.sprint_grid
    from ..core import penalties
    ws.quali_times = times
    ws.pole = pole
    ws.grid, ws.grid_notes = penalties.apply_grid_penalties(gs, griglia)
    ws.quali_done = True
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
    cond = pace.of_weekend(ws, kind)
    ents = build_entrants(gs, track, cond)
    by_id = {e.driver_id: e for e in ents}
    grid = (ws.sprint_grid if kind == "sprint" else ws.grid) or list(by_id.keys())

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

    sim = RaceSim(gs, track, ordered, weather, laps, kind=kind, rng=gs.rng, cond=cond)
    # il serbatoio e' quello che e': il consumo si tara su di lui lasciando un
    # 10% di riserva. Basta per attaccare in un terzo dei giri, non per tutta
    # la gara: chi ci prova resta a piedi prima della bandiera.
    if ordered:
        sim.burn_per_lap = ordered[0].fuel / (laps * 1.10)
    for e in ordered:
        e.tyre_life = sim._tyre_life(e, e.tyre)
    sim.log(f"Semaforo verde a {track.name} - {laps} giri - {weather.label}", "flag")
    return sim
