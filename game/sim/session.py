"""Orchestrazione del weekend: prove libere, qualifica, griglia, gara."""
from __future__ import annotations

import math
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
    quali_phase: dict = field(default_factory=dict)   # fin dove e' arrivato ognuno
    sprint_phase: dict = field(default_factory=dict)
    tyre_choice: dict = field(default_factory=dict)  # team_id -> set scelti per mescola
    tyre_stock: dict = field(default_factory=dict)   # driver_id -> set ancora a disposizione
    tyres_published: bool = False                    # le scelte sono state rese pubbliche
    practice_times: dict = field(default_factory=dict)  # il meglio di ognuno nelle libere
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


def _affidabile(team, driver) -> float:
    """Quanto e' probabile che questa macchina arrivi in fondo.

    Alla base c'e' com'e' messa la vettura e quanto sono logori i componenti
    contingentati. Poi c'e' il tempo: una macchina la si rende affidabile
    capendola, e i guasti dei primi weekend non sono quelli di settembre.
    """
    from ..core import penalties
    base = team.car.reliability * penalties.health_factor(driver)
    matura = 1.20 - 0.35 * max(0.0, min(1.0, team.car_understanding))
    return max(0.10, 1.0 - (1.0 - base) * matura)


def _quote_settori(gs, team, track, cond) -> tuple:
    """Come questa vettura spezza il giro nei tre settori.

    Non e' un terzo per uno: i traguardi di settore stanno dove stanno, e
    quanto ci si mette ad arrivarci dipende da cosa c'e' in mezzo e da come e'
    fatta la macchina.
    """
    car = team.car
    salva = car.fuel_kg
    car.fuel_kg = 0.0
    try:
        quote = track.sector_shares(car, wet=cond.wet, grip=pace.surface_grip(cond),
                                    rho=cond.rho, bias=car.domain_bias)
    except Exception:
        quote = getattr(track, "sector_time", (0.3333, 0.6667))
    car.fuel_kg = salva
    return quote


def build_entrants(gs, track, cond, quali: bool = False) -> list:
    """Chi scende in pista, con che passo e in che condizioni."""
    from ..core import penalties
    from ..core.driving import FIDUCIA_BASE
    from ..core import engineering
    aff = pace.affinities(gs, track)
    # la punta di velocita' di ogni vettura, per il tachimetro in pista: e' il
    # modello di giro, non un numero scritto a mano
    try:
        punte = {t: d.get("vmax", 330.0) for t, d in
                 engineering.grid_domains(gs, track, cond).items()}
    except Exception:
        punte = {}
    out = []
    terze = terze_vetture(gs)
    for team in gs.teams.values():
        # il pacchetto lavora uguale per tutti e due, l'assetto no
        pacchetto = gs.rng.gauss(0.0, 0.13)
        quote = _quote_settori(gs, team, track, cond)
        pit = (3.30 - 1.15 * (team.pit_strength / 100.0)
               + float(gs.regulations.get("pit_lane_penalty_s", 0.0)))
        schierati = list(gs.lineup_of(team.id))
        terzo = terze.get(team.id)
        if terzo is not None:
            schierati.append(terzo)
        for d in schierati:
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
                reliability=_affidabile(team, d),
                pit_time=pit, strategy_skill=team.strategy_strength,
                vmax=float(punte.get(team.id, 330.0)),
                ers_skill=float((team.car.engine or {}).get(
                    "software", (team.car.engine or {}).get("ers", 85))),
                sector_shares=list(quote),
                is_player=(team.id == gs.player_team),
                terza=(terzo is not None and d.id == terzo.id),
            ))
    return out


def terze_vetture(gs) -> dict:
    """Le terze vetture in pista, quando il regolamento le consente.

    E' una vecchia proposta che torna ogni volta che qualcuno rischia di
    chiudere: le prime tre del costruttori schierano una macchina in piu' con
    un giovane. Corre, occupa la pista e da' fastidio, ma non porta punti a
    nessuno - se no il campionato lo deciderebbe chi ha piu' macchine.
    """
    if not gs.regulations.get("third_car"):
        return {}
    out = {}
    gia = {d for t in gs.teams.values() for d in t.drivers}
    for team in gs.constructor_standings()[:3]:
        panchina = [gs.drivers[x] for x in (list(team.reserves) + list(team.academy))
                    if x in gs.drivers and x not in gia]
        panchina = [d for d in panchina if getattr(d, "banned_races", 0) <= 0]
        if not panchina:
            continue
        panchina.sort(key=lambda d: -(d.potential + d.overall))
        out[team.id] = panchina[0]
        gia.add(panchina[0].id)
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


def run_practice(gs, ws: WeekendState, delegate_player: bool = True, turno=None) -> list:
    """Una sessione di prove: la pista risponde e l'assetto si avvicina.

    Non si scopre l'assetto giusto guardandolo: si scopre girandoci. Quello che
    il reparto crede - l'assetto sulla carta preparato al simulatore - viene
    corretto da quello che dicono i piloti e i dati, e i meccanici montano sulla
    macchina quello a cui si e' arrivati.
    """
    from ..core import setup as SETUP
    track = ws.track
    # con la sessione giocata dal vivo il tempo l'ha gia' mosso lei: qui si
    # raccoglie soltanto quello che quell'ora in pista ha insegnato
    if turno is None and ws.practice_done:
        ws.weather = ws.weather.drift(track, gs.rng)
    cond = turno.cond if turno is not None else pace.of_weekend(ws, "prove")
    notes = []
    for indice, team in enumerate(gs.teams.values()):
        drivers = gs.drivers_of(team.id)
        fb = sum(d.feedback for d in drivers) / max(1, len(drivers))
        # il turno riservato ai debuttanti: in macchina sale un ragazzo, il
        # venerdi' rende meno e in cambio lui cresce
        ragazzo = rookie_di_turno(gs, ws, team, indice)
        if ragazzo is not None:
            fb *= 0.86
        SETUP.learn_from_track(gs, team, track, fb, cond=cond)
        quota = 1.0
        if ragazzo is not None:
            quota = 0.55
            cresci_rookie(gs, team, ragazzo)
            if team.id == gs.player_team:
                notes.append(f"FP1 al debuttante: in macchina c'e' {ragazzo.short}, "
                             f"il venerdi' rende meno ma lui impara.")
        if team.id == gs.player_team and not delegate_player:
            quota = min(quota, 0.45)   # il giocatore tiene in mano i regolatori
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
    # e quello che dicono i dati: dove si perde, quanto, e a che curva si vede
    from ..core import engineering
    try:
        notes += engineering.practice_report(gs, pt, track, cond)
    except Exception:
        pass
    # e quello che la giornata sta facendo alla macchina: se il tempo non e'
    # quello che il reparto si aspettava, il riferimento del simulatore vale poco
    atteso = pace.nominal(track)
    if ws.weather.wet > 0.15:
        notes.append(f"{who}: sull'acqua serve un altro assetto - piu' carico, "
                     f"piu' alta, piu' morbida - e il riferimento del simulatore "
                     f"non vale piu'.")
    scarto = ws.weather.track_temp - atteso.track_temp
    if abs(scarto) >= 9:
        dove = "piu' caldo" if scarto > 0 else "piu' freddo"
        cosa = ("le gomme vanno oltre la finestra: si degrada"
                if scarto > 0 else "le gomme non arrivano in temperatura")
        notes.append(f"{who}: asfalto {abs(scarto):.0f} gradi {dove} del solito, {cosa}.")
    if ws.weather.wind >= 22:
        notes.append(f"{who}: con questo vento la macchina cambia a ogni passaggio.")
    ws.practice_notes = notes
    return notes


def rookie_di_turno(gs, ws: WeekendState, team, indice: int):
    """Chi sale in macchina nella prima libera, se tocca al debuttante.

    Il regolamento obbliga ogni squadra a un tot di prime libere all'anno con
    un pilota senza esperienza. Le si spalmano sulla stagione e le squadre non
    le fanno tutte lo stesso venerdi': cosi' chi ci passa perde un'ora di
    lavoro sull'assetto mentre gli altri no.
    """
    quante = int(gs.regulations["sporting"].get("rookie_fp1_sessions") or 0)
    # nei weekend con la sprint c'e' una sola libera e non la si regala
    if quante <= 0 or ws.practice_done or getattr(ws.track, "sprint", False):
        return None
    # i turni si spalmano sui weekend senza sprint, sfalsati da squadra a
    # squadra: cosi' ognuna ne fa esattamente quanti ne chiede il regolamento
    liberi = [r for r, t in enumerate(gs.tracks, 1) if not getattr(t, "sprint", False)]
    if not liberi:
        return None
    scelti = {liberi[(k * len(liberi) // quante + indice) % len(liberi)]
              for k in range(quante)}
    if gs.round not in scelti:
        return None
    titolari = set(team.drivers)
    panchina = [gs.drivers[x] for x in (list(team.reserves) + list(team.academy))
                if x in gs.drivers and x not in titolari]
    panchina = [d for d in panchina if getattr(d, "races", 0) < 12
                and getattr(d, "banned_races", 0) <= 0]
    if not panchina:
        return None
    panchina.sort(key=lambda d: -(d.potential - d.overall))
    return panchina[0]


def cresci_rookie(gs, team, d) -> None:
    """Un'ora vera in macchina vale piu' di una stagione al simulatore."""
    from ..model.people import DRIVER_ATTRS
    margine = max(0.0, d.potential - d.overall)
    if margine < 0.3:
        return
    passo = (0.30 + 0.25 * float(team.facilities.get("academy", 60.0)) / 100.0) \
        * (margine / 12.0) * gs.rng.uniform(0.8, 1.5)
    for a in DRIVER_ATTRS:
        cur = getattr(d, a)
        setattr(d, a, min(99.0, cur + min(passo, max(0.0, d.potential - cur))))


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
# I tre turni stanno in sim.hotlap insieme al turno che li gioca: qui resta il
# nome con cui li chiamano le schermate.
from .hotlap import SEGMENTI, LapSession    # noqa: E402


def run_qualifying(gs, ws: WeekendState, kind: str = "gp") -> list:
    """La qualifica, nel formato vero: tre turni a eliminazione.

    Il gran premio ha Q1 da diciotto minuti, Q2 da quindici e Q3 da dodici: si
    fa in tempo a uscire due volte in tutti e tre. La Sprint Qualifying del
    venerdi' e' un'altra cosa - dodici, dieci e otto minuti - e il regolamento
    non lascia nemmeno scegliere le gomme: media nei primi due turni, morbida
    nell'ultimo. Meno tempo, meno tentativi, piu' peso al primo giro buono.

    In tutti e due i casi si eliminano sei macchine per turno finche' ne
    restano dieci a giocarsi la pole; chi e' uscito prima parte comunque dietro
    a chi e' andato avanti, anche se nel suo turno ha girato piu' forte.

    Il turno lo gioca sim.hotlap sul suo orologio: qui lo si fa correre tutto
    d'un fiato. Guardarlo minuto per minuto porta esattamente allo stesso
    tabellone.
    """
    turno = LapSession(gs, ws, kind)
    turno.corri_tutto()
    return turno.applica()


def ordina_griglia(gs, griglia: list, tempi: dict, kind: str) -> tuple:
    """La griglia dopo che il regolamento ci ha messo mano.

    Il formato normale mette davanti chi ha girato piu' forte. Ma in
    Commissione tornano ogni tanto due idee che lo cambiano di netto: la
    qualifica a tempo aggregato, in cui conta la somma dei due piloti di una
    squadra - e allora nessuno puo' piu' permettersi una seconda guida - e la
    griglia invertita nelle sprint, in cui si parte al contrario della
    classifica. Se sono in vigore, e' qui che l'ordine cambia.
    """
    reg = gs.regulations
    note = []
    if reg.get("aggregate_quali"):
        squadre = {}
        for d in griglia:
            drv = gs.drivers.get(d)
            if drv is None:
                continue
            squadre.setdefault(getattr(drv, "team", ""), []).append(d)
        ordine = sorted(squadre.items(),
                        key=lambda kv: sum(tempi.get(d, 999.0) for d in kv[1]) / max(1, len(kv[1])))
        nuova = []
        for _, piloti in ordine:
            nuova.extend(sorted(piloti, key=lambda d: tempi.get(d, 999.0)))
        if nuova:
            griglia = nuova
            note.append("Griglia a tempo aggregato: contano i due piloti insieme.")
    if kind == "sprint" and reg.get("reverse_grid"):
        # al contrario della classifica piloti: chi non ha punti davanti a tutti
        punti = {d: getattr(gs.drivers.get(d), "points", 0.0) for d in griglia}
        # a parita' di punti - a inizio stagione sono tutti a zero - si
        # rovescia il tempo: la griglia esce esattamente al contrario
        griglia = sorted(griglia, key=lambda d: (punti.get(d, 0.0), -tempi.get(d, 999.0)))
        note.append("Griglia invertita: si parte al contrario della classifica.")
    return griglia, note


def _regola_107(gs, times: dict, reached: dict, primo: str) -> list:
    """La regola del 107 per cento: chi resta fuori dal tempo va dai commissari.

    Nella pratica il permesso lo danno sempre - basta aver girato su quei tempi
    nelle libere - ma la riga sul foglio resta, e a chi si e' qualificato per il
    rotto della cuffia ricorda quanto e' stato vicino a restare a casa.
    """
    q1 = [t for d, t in times.items() if reached[d] == 0]
    if not q1:
        return []
    limite = min(times.values()) * 1.07
    fuori = [d for d, t in times.items() if reached[d] == 0 and t > limite]
    if not fuori:
        return []
    nomi = ", ".join(gs.drivers[d].short for d in fuori if d in gs.drivers)
    return [f"Oltre il 107% in {primo}: {nomi}. I commissari li ammettono al via."]


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
    # e se il regolamento ne impone un numero minimo, quello viene prima di
    # qualunque conto sul degrado
    stops = max(stops, int(gs.regulations["sporting"].get("mandatory_stops") or 0))
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
    """Giri effettivi, ridotti secondo la durata scelta dal giocatore.

    La sprint e' sui cento chilometri: si prende il primo numero di giri che li
    supera, che e' esattamente come li conta il regolamento - diciannove giri a
    Shanghai, ventiquattro a Interlagos, quindici a Spa.
    """
    if kind == "gp":
        full = track.laps
    else:
        full = max(10, int(math.ceil(100.0 / track.length_km)))
    factor = float(getattr(gs, "race_distance", 1.0))
    return max(3, int(round(full * factor)))


def make_race(gs, ws: WeekendState, kind: str = "gp") -> RaceSim:
    track = ws.track
    ws.weather = ws.weather.drift(track, gs.rng)
    weather = ws.weather
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
        # in griglia la batteria e' piena: e' l'unico giro in cui lo e' per tutti
        e.carica = float((gs.regulations.get("power_unit", {}) or {}).get(
            "batteria_mj", C.BATTERIA_MJ))
        e.stock = ws.tyre_stock.get(did) if ws.tyre_stock else None
        e.plan = plan_strategy(gs, e, track, laps, weather) if kind == "gp" else []
        # benzina per i giri che si corrono davvero, con un filo di margine:
        # guidando normale si arriva, attaccando tutta la gara no
        serbatoio = float((gs.regulations.get("power_unit", {}) or {}).get(
            "fuel_race_target_kg", C.FUEL_MASS_KG))
        # e un motore che consuma meno parte piu' leggero: sono chili veri, e
        # su una gara valgono decimi
        consumo = float(getattr(gs.teams[e.team_id].car, "consumo_rel", 1.0))
        e.fuel = min(serbatoio, laps * BURN_KG_PER_LAP * 1.04 * consumo)
        if gs.regulations.get("refuelling"):
            # col rifornimento non si parte pieni: si carica quello che serve
            # per arrivare alla prima sosta, e li' se ne rimette dell'altra
            prima = e.plan[0][0] if e.plan else laps
            e.fuel = min(e.fuel, (prima + 1) * BURN_KG_PER_LAP * 1.06)
        e.tyre_life = 25.0
        ordered.append(e)

    sim = RaceSim(gs, track, ordered, weather, laps, kind=kind, rng=gs.rng, cond=cond)
    # il serbatoio e' quello che e': il consumo si tara su di lui lasciando un
    # 10% di riserva. Basta per attaccare in un terzo dei giri, non per tutta
    # la gara: chi ci prova resta a piedi prima della bandiera.
    if ordered:
        # il consumo si tara sul pieno di una gara intera, non su quello che
        # ognuno ha nel serbatoio adesso: col rifornimento si parte leggeri
        pieno = min(float((gs.regulations.get("power_unit", {}) or {}).get(
            "fuel_race_target_kg", C.FUEL_MASS_KG)), laps * BURN_KG_PER_LAP * 1.04)
        sim.burn_per_lap = pieno / (laps * 1.10)
    for e in ordered:
        e.tyre_life = sim._tyre_life(e, e.tyre)
    sim.log(f"Semaforo verde a {track.name} - {laps} giri - {weather.label}", "flag")
    return sim
