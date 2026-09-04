"""Progressione della stagione: risultati, fine gara, fine anno."""
from __future__ import annotations

from .. import config as C
from ..model.car import Part
from . import (academy, architetture, calendar, departments, development, economy,
               facilities, market, nextcar, penalties,
               powertrain, rules, setup, sponsors, testing)
from .state import RaceResult


# ------------------------------------------------------------------- risultati
def points_for(gs, pos: int, kind: str = "gp") -> float:
    sport = gs.regulations["sporting"]
    table = sport["points"] if kind == "gp" else sport.get("sprint_points", [8, 7, 6, 5, 4, 3, 2, 1])
    return float(table[pos - 1]) if 1 <= pos <= len(table) else 0.0


def apply_result(gs, ws, sim, kind: str = "gp") -> RaceResult:
    """Registra il risultato, assegna punti, applica usura, danni e finanze."""
    track = ws.track
    order = sim.result_order()
    fastest = min((e for e in sim.entrants if e.best_lap < 900), key=lambda e: e.best_lap, default=None)
    # la sprint ha la sua pole, quella della Sprint Qualifying del venerdi'
    pole = getattr(ws, "sprint_pole", "") if kind == "sprint" else ws.pole
    rr = RaceResult(track_id=track.id, round=gs.round, season=gs.season, kind=kind,
                    pole=pole, fastest_lap=fastest.driver_id if fastest else "",
                    weather=ws.weather.label)

    mese = int(getattr(track, "month", 3))
    for t in gs.teams.values():
        t.set_clock(gs.season, mese, gs.round + 1)

    team_points = {tid: 0.0 for tid in gs.teams}
    # le terze vetture corrono ma non prendono punti, e nemmeno li tolgono a
    # chi le segue: per il punteggio si contano solo le macchine che ne danno
    posto_punti = 0
    for pos, e in enumerate(order, 1):
        d = gs.drivers.get(e.driver_id)
        team = gs.teams[e.team_id]
        terza = bool(getattr(e, "terza", False))
        if not terza:
            posto_punti += 1
        pts = 0.0 if terza else (points_for(gs, posto_punti, kind)
                                 if e.status == "finished" else 0.0)
        if (kind == "gp" and not terza and gs.regulations["sporting"].get("fastest_lap_point")
                and fastest and e.driver_id == fastest.driver_id and posto_punti <= 10):
            pts += 1
        if d:
            d.points += pts
            d.career_points += pts
            # la sprint porta punti, ma non e' un gran premio: non entra nelle
            # statistiche di gare, vittorie e podi
            if kind == "gp":
                d.races += 1
                if e.status != "finished":
                    d.dnfs += 1
                if pos == 1 and e.status == "finished":
                    d.wins += 1
                    team.wins += 1
                if pos <= 3 and e.status == "finished":
                    d.podiums += 1
                    team.podiums += 1
                if ws.pole == d.id:
                    d.poles += 1
            _update_morale(gs, d, team, pos, e.status)
            _shake_confidence(gs, team, d, e, track)
            _pay_bonuses(gs, d, team, pos, pts, e.status, kind)
        team.points += pts
        team_points[team.id] = team_points.get(team.id, 0.0) + pts
        rr.order.append({
            "driver": e.driver_id, "team": e.team_id, "pos": pos,
            "status": e.status, "reason": e.dnf_reason, "time": round(e.finished_time, 3),
            "laps": e.lap, "stops": e.stops, "best": round(e.best_lap, 3),
            "grid": e.grid, "points": pts, "damage": round(e.damage, 1),
        })

    # un cedimento non e' un guaio da un giorno: quel pezzo e' da buttare, e
    # il pezzo dopo lo si monta col contingente che si ha
    for e in sim.entrants:
        if e.status != "retired":
            continue
        d = gs.drivers.get(e.driver_id)
        if d is None:
            continue
        if "power unit" in e.dnf_reason or "olio" in e.dnf_reason or "surriscald" in e.dnf_reason:
            d.pu_wear = 0.0
        elif "cambio" in e.dnf_reason:
            d.gearbox_wear = 0.0

    # usura e danni sulla vettura di ogni squadra
    for team in gs.teams.values():
        dmg = 0.0
        for e in sim.entrants:
            if e.team_id != team.id:
                continue
            dmg += e.damage
            if e.damage > 0:
                _distribute_damage(gs, team, e.damage, gs.drivers.get(e.driver_id))
        # l'usura segue i chilometri percorsi: la sprint e' circa un terzo di GP
        team.car.wear(2.6 * min(1.0, sim.laps / max(1, track.laps)), track)
        # i costi fissi del weekend (logistica, stipendi, strutture) e i ricavi
        # si contano una volta sola: alla domenica, sprint o non sprint
        if kind == "gp":
            cost = team.car.repair_all()
            economy.apply_race_finances(gs, team, team_points.get(team.id, 0.0),
                                        gs.position_of(team.id), cost)

    if kind == "gp":
        for pos, e in enumerate(order, 1):
            if e.status == "finished" and pos <= 3:
                sponsors.register_result(gs.teams[e.team_id], pos)

    # chi ha saltato il weekend sconta una gara di squalifica
    corsi = {x["driver"] for x in rr.order}
    for d in gs.drivers.values():
        if d.banned_races > 0 and d.id not in corsi:
            d.banned_races -= 1

    if kind == "gp":
        rr.penalties = penalties.apply_race_penalties(gs, sim)
        for m in rr.penalties:
            gs.push(m, "gara")

    gs.results.append(rr)
    if kind == "gp":
        _albo(gs, ws, rr, order, fastest)
    return rr


def _albo(gs, ws, rr, order, fastest) -> None:
    """Segna il gran premio nell'albo d'oro del circuito.

    I risultati veri si tengono solo per tre stagioni, altrimenti il salvataggio
    cresce senza fine: l'albo e' la riga che resta per sempre, come sta scritta
    sui muri dei circuiti.
    """
    vincitore = gs.drivers.get(order[0].driver_id) if order else None
    pole = gs.drivers.get(ws.pole)
    veloce = gs.drivers.get(fastest.driver_id) if fastest else None
    riga = {
        "season": gs.season,
        "vincitore": vincitore.name if vincitore else "",
        "squadra": gs.teams[order[0].team_id].short if order else "",
        "pole": pole.name if pole else "",
        "pole_squadra": gs.teams[pole.team].short if pole and pole.team in gs.teams else "",
        "giro_veloce": veloce.name if veloce else "",
        "tempo_pole": round(ws.quali_times.get(ws.pole, 0.0), 3),
        "meteo": ws.weather.label,
    }
    storia = gs.track_history.setdefault(ws.track.id, [])
    storia[:] = [x for x in storia if x.get("season") != gs.season] + [riga]
    storia.sort(key=lambda x: -x["season"])


def _pay_bonuses(gs, d, team, pos: int, pts: float, status: str, kind: str) -> None:
    """Paga i premi scritti nel contratto del pilota.

    Sono soldi veri quanto l'ingaggio: e' la ragione per cui in trattativa
    conviene spostare peso sui bonus quando la squadra non e' da vittorie.
    """
    due = float(getattr(d, "bonus_points", 0.0)) * pts
    if kind == "gp" and status == "finished":
        if pos == 1:
            due += float(getattr(d, "bonus_win", 0.0))
        if pos <= 3:
            due += float(getattr(d, "bonus_podium", 0.0))
    if due > 0.001:
        in_cap = not gs.regulations.get("cost_cap_excludes_driver_salaries", True)
        team.add_expense(f"Premi contratto {d.last}", round(due, 3), in_cap=in_cap)


def _distribute_damage(gs, team, amount: float, driver=None) -> None:
    from . import kits
    keys = list(team.car.parts.keys())
    hits = gs.rng.sample(keys, k=min(3, len(keys)))
    for k in hits:
        team.car.damage(k, amount * gs.rng.uniform(0.2, 0.5))
    # un contatto leggero si raddrizza, una botta vera porta via il pezzo: e se
    # quel pezzo era la specifica nuova, quella macchina torna indietro
    if driver is not None and amount >= 26.0:
        riga = kits.wreck(gs, team, driver, kits._pezzo_colpito(gs))
        if riga:
            gs.push(f"{team.name}: {riga}", "tecnico")


def _shake_confidence(gs, team, d, e, track) -> None:
    """Come finisce la gara cambia il modo in cui ci si sale sopra la prossima volta.

    Un botto lo si porta dietro: si rientra piu' morbidi, si aspetta che la
    macchina faccia di nuovo quello che ci si aspetta. Un cedimento pesa meno -
    non e' colpa di chi guida - ma nemmeno zero: la fiducia e' anche sapere che
    quello che si ha sotto arriva in fondo.
    """
    from . import driving
    if e.dnf_reason == "incidente":
        driving.shake_confidence(d, 15.0)
    elif e.status == "retired":
        driving.shake_confidence(d, 6.0)
    elif e.damage > 20.0:
        driving.shake_confidence(d, 4.0)
    else:
        driving.settle_confidence(gs, team, d, track, 0.30)


def _update_morale(gs, d, team, pos: int, status: str) -> None:
    expected = _expected_position(gs, team)
    delta = (expected - pos) * 1.7
    if status != "finished":
        delta -= 4.0
    d.morale = max(5.0, min(100.0, d.morale + delta * 0.55))
    d.form = max(-5.0, min(5.0, d.form * 0.70 + delta * 0.13))


def _expected_position(gs, team) -> float:
    rank = sorted(gs.teams.values(), key=lambda t: -t.car.rating)
    idx = [t.id for t in rank].index(team.id)
    return 1.6 + idx * 2.0


# ---------------------------------------------------------------- post gara
def player_budgets(gs) -> tuple:
    """Quanto mette sul tavolo il giocatore, per gara, senza doverlo decidere.

    Prima c'era una barra da trascinare, e non era una decisione: non esiste il
    motivo per metterla piu' bassa del possibile. Adesso il conto e' quello che
    fanno anche le squadre del computer - quello che avanza dopo i costi fissi,
    diviso per le gare che restano - e la scelta vera resta dov'era: come
    ripartire il lavoro fra le aree, quali pacchetti aprire e quando omologare
    una specifica di motore.
    """
    team = gs.player
    gare = max(1, len(gs.tracks) - gs.round)
    resta = economy.room_left(gs, team)
    dev = max(0.0, min(resta / gare * 0.55, development.budget_headroom(gs, team) * 0.5))
    dev *= economy.spending_room(gs, team)
    pu = 0.0
    if team.works or powertrain.has_program(gs):
        # il reparto motori ha un budget suo, fuori dal tetto di spesa
        pu = max(0.0, min(team.cash * 0.05, 1.1 + team.reputation / 55.0))
        pu *= economy.spending_room(gs, team)
    return round(dev, 3), round(pu, 3)


def after_race(gs, dev_budget: float | None = None, pu_budget: float | None = None) -> list:
    """Sviluppo, notizie e avanzamento del calendario."""
    msgs = []
    player = gs.player
    if dev_budget is None or pu_budget is None:
        auto_dev, auto_pu = player_budgets(gs)
        dev_budget = auto_dev if dev_budget is None else dev_budget
        pu_budget = auto_pu if pu_budget is None else pu_budget
    if player.auto_dev:
        # delega al reparto: decide lui allocazione, pacchetti e taglie, e
        # quanto viene bene dipende da chi ci sta dentro
        development.run_department(gs, player)
    else:
        development.passive_development(gs, player, dev_budget)
    # prima il verdetto su quello che gia' gira, poi quello che arriva adesso:
    # una specifica nuova non puo' essere giudicata dalla gara appena corsa
    msgs += development.check_trials(gs, player)
    msgs += development.advance_projects(gs, player)
    development.ai_development(gs)
    from . import kits
    for t in gs.teams.values():
        for m in kits.produce(gs, t):
            msgs.append(m)
        if not t.is_player or t.auto_dev:
            kits.ai_fit(gs, t)
    testing.ai_plan(gs)
    for t in gs.teams.values():          # usura di power unit e cambi
        for m in penalties.wear_components(gs, t):
            if t.is_player:
                msgs.append(m)
    powertrain.advance_partnership(gs)
    powertrain.running_costs(gs)
    # e la rata di chi sta gia' lavorando sul motore del regolamento che verra'
    powertrain.investi_arch(gs)
    powertrain.ai_arch(gs)
    msgs += powertrain.develop(gs, pu_budget)
    msgs += powertrain.advance_program(gs, pu_budget)
    if powertrain.ready_to_debut(gs):
        gs.push("Il reparto puo' portare in pista la nostra power unit quando vogliamo.",
                "tecnico")
    for m in msgs:
        gs.push(m, "tecnico")
    gs.round += 1
    if gs.round >= len(gs.tracks):
        gs.phase = "offseason"
    elif rules.meeting_due(gs):
        rules.open_meeting(gs)
    # nuovo appuntamento, foglio bianco: l'assetto di domenica scorsa non dice
    # niente sulla pista di domenica prossima
    setup.new_weekend(gs)
    return msgs


# ------------------------------------------------------------- fine stagione
def end_season(gs) -> dict:
    """Chiude l'anno: premi, crescita, mercato, votazioni, nuovo regolamento."""
    report = {"finance": [], "market": [], "rules": [], "champions": {}, "progress": []}

    ds = gs.driver_standings()
    cs = gs.constructor_standings()
    if ds:
        report["champions"]["driver"] = ds[0]
    if cs:
        report["champions"]["constructor"] = cs[0]
        cs[0].titles["constructors"] = cs[0].titles.get("constructors", 0) + 1
        if ds:
            t = gs.teams.get(ds[0].team)
            if t:
                t.titles["drivers"] = t.titles.get("drivers", 0) + 1

    for t in gs.teams.values():          # i conti di fine anno cadono a dicembre
        t.set_clock(gs.season, 12, len(gs.tracks))
    report["finance"] = economy.end_of_season_finances(gs)
    campione = cs[0] if cs else None
    for t in gs.teams.values():
        premi = sponsors.pay_bonuses(gs, t, champion=(t is campione))
        if t.is_player and premi > 0.01:
            report["finance"].append(f"Bonus di risultato dagli sponsor: {premi:.2f} M$.")

    # il nome della squadra segue i risultati, con calma: una stagione buona
    # non fa una scuderia importante, cinque si'
    from . import newteam
    report["finance"] += newteam.drift_reputation(gs)

    # crescita/declino dei piloti
    for d in list(gs.drivers.values()) + list(gs.free_agents):
        team = gs.teams.get(d.team)
        if d.seat == "academy" and team is not None:
            # i ragazzi del vivaio non crescono qui: crescono correndo, e la
            # loro stagione si gioca piu' avanti (game.core.serie). Anche
            # l'anno in piu' se lo prendono li', dopo aver corso
            continue
        quality = 0.5
        if team:
            quality = (0.38 * (team.facilities.get("simulator", 60) / 100.0)
                       + 0.30 * (team.facilities.get("academy", 60) / 100.0)
                       + 0.15 * (team.facilities.get("private_track", 0) / 100.0)
                       + 0.17 * (team.role("race_engineer").communication / 100.0
                                 if team.role("race_engineer") else 0.6))
        notes = d.progress(quality, gs.rng)
        if team and team.is_player and notes:
            report["progress"].append(f"{d.name}: {', '.join(notes)} (valutazione {d.overall:.0f})")

    for s in [s for t in gs.teams.values() for s in t.staff] + gs.free_staff:
        s.age += 1

    for t in gs.teams.values():
        msgs_sp = sponsors.roll_season(gs, t)
        if t.is_player:
            report["finance"] += msgs_sp
    sponsors.ai_fill(gs)
    report["market"] = market.run_transfer_window(gs)
    market.new_talents(gs)

    # ultima riunione dell'anno: le altre si sono tenute durante la stagione
    rules.open_meeting(gs)

    # invecchiamento: chi non reinveste arretra senza sbagliare niente
    lost_car = development.technological_decay(gs)
    lost_fac = facilities.decay(gs)
    facilities.ai_invest(gs)
    report["progress"].append(
        f"Un anno di progresso altrui: la vettura perde {lost_car:.2f} punti di "
        f"competitivita' e le strutture {lost_fac:.1f}. Si recupera solo investendo.")

    # Nuovo ciclo tecnico: non c'e' piu' un calendario: il ciclo arriva quando
    # le squadre hanno approvato abbastanza cambiamenti da farne una nuova era.
    reset = float(gs.regulations.pop("pending_reset", 0.0))
    era = None
    ciclo = gs.regulations.get("pending_cycle")
    if ciclo and ciclo.get("season") == gs.season + 1:
        reset = max(reset, min(0.95, 0.35 + 0.45 * ciclo["pressure"]))
        era = {"from": gs.season + 1, "to": gs.season + 6,
               "label": _nome_ciclo(gs, ciclo), "dominant": [],
               "reset_strength": round(reset, 2), "focus": rules.cycle_focus(gs),
               "arch": ciclo.get("arch", ""),
               "nota": "Nato da " + ", ".join(ciclo["titles"][:3]).lower() + "."}
        gs.history_data.setdefault("eras", []).append(era)
        gs.regulations.pop("pending_cycle", None)
        report["rules"].append(f"Nuovo ciclo tecnico: {era['label']}.")
        # l'architettura nuova entra in vigore prima del rimescolamento: la
        # macchina del ciclo nuovo la si giudica con il motore del ciclo nuovo
        arch = ciclo.get("arch") or ""
        if arch and arch != architetture.corrente(gs):
            report["rules"] += architetture.applica(gs, arch)
            gs.refresh_tracks()
        # e chi ci aveva scommesso sopra incassa adesso
        for team in gs.teams.values():
            punti, nota = powertrain.resa_arch(gs, team, arch)
            if punti > 0:
                team.reg_prep += punti
            if nota and (team.is_player or punti > 8.0):
                report["rules"].append(nota)
    if reset > 0:
        report["rules"] += development.regulation_reset(gs, reset, era)
        if era and era.get("nota"):
            report["rules"].append(era["nota"])
        report["rules"].append("Il nuovo regolamento ha rimescolato i valori in campo.")

    # i componenti che arrivano dalla sorella maggiore si montano sulla vettura
    # dell'anno nuovo, quindi dopo l'eventuale rimescolamento regolamentare
    report["rules"] += development.sister_transfer(gs)

    # reset della stagione: le posizioni vanno lette tutte prima di azzerare i
    # punti, altrimenti ogni squadra ripulita falsa la classifica di quelle dopo
    final_positions = {t.id: pos for pos, t in enumerate(gs.constructor_standings(), 1)}
    for t in gs.teams.values():
        t.last_position = final_positions[t.id]
        t.points = 0.0
        t.wins = 0
        t.podiums = 0
        t.reset_season_finances()
        t.car.repair_all()
    report["market"] += academy.end_season(gs)
    report["market"] += academy.ai_found(gs)
    report["market"] += departments.ai_plan(gs)
    departments.new_season(gs)
    testing.end_season(gs)
    development.new_car_season(gs)
    report["rules"] += powertrain.end_season(gs)
    # la vettura dell'anno prossimo: quello che il reparto ha preparato durante
    # la stagione scende in pista adesso
    report["progress"] += nextcar.end_season(gs)
    # e poi c'e' l'inverno vero e proprio: quattro mesi in cui non si corre e
    # tutti i reparti lavorano insieme su quello che l'anno appena finito ha
    # detto che non andava. E' un lavoro diverso da quello di stagione, e
    # arriva dopo la macchina nuova perche' e' su quella che si interviene
    from . import inverno
    report["progress"] += inverno.stagione_finita(gs)
    # e adesso che tutti hanno fatto il loro inverno, il metro si aggiorna: il
    # riferimento del ciclo insegue quello che la griglia ha davvero raggiunto
    salito = development.aggiorna_riferimento(gs)
    if salito > 0.05:
        report["progress"].append(
            f"Il riferimento tecnico sale di {salito:.1f}: quello che l'anno scorso "
            f"era una buona macchina adesso e' la norma.")
    penalties.decay_points(gs)
    for d in gs.drivers.values():
        d.pu_used = 1
        d.gearbox_used = 1
        d.pu_wear = 100.0
        d.gearbox_wear = 100.0
        d.grid_penalty = 0
        d.points = 0.0
        d.wins = 0
        d.podiums = 0
        d.poles = 0
        d.form = 0.0

    gs.season_history.append({
        "season": gs.season,
        "driver_champion": report["champions"]["driver"].name if ds else "",
        "constructor_champion": report["champions"]["constructor"].short if cs else "",
        "standings": [(t.short, t.last_position) for t in cs],
    })
    report["calendar"] = calendar.roll_contracts(gs)

    gs.season += 1
    gs.regulations["season"] = gs.season
    # quello che era stato votato per quest'anno entra in vigore adesso, non
    # il giorno in cui e' stato approvato
    report["rules"] += rules.apply_pending(gs)
    for t in gs.teams.values():          # anno nuovo: si riparte da gennaio
        t.set_clock(gs.season, 1, 0)
    gs.round = 0
    gs.phase = "preseason"
    # le prove collettive di inizio anno: ci vanno tutti, e le squadre del
    # computer non stanno ad aspettare che qualcuno glielo dica
    testing.ai_preseason(gs)
    gs.results = [r for r in gs.results if r.season >= gs.season - 3]
    return report


def _nome_ciclo(gs, ciclo: dict) -> str:
    aree = ciclo.get("areas", {})
    dom = max(aree, key=aree.get) if aree else "chassis"
    return {"pu": "Nuova era delle power unit",
            "aero": "Nuova era aerodinamica",
            "chassis": "Nuova era di telaio e meccanica"}.get(dom, "Nuovo ciclo tecnico")


def _era_for(gs, season: int) -> dict | None:
    for era in gs.history_data.get("eras", []):
        if era["from"] <= season <= era["to"]:
            return era
    return None
