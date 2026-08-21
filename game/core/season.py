"""Progressione della stagione: risultati, fine gara, fine anno."""
from __future__ import annotations

from .. import config as C
from ..model.car import Part
from . import development, economy, facilities, market, powertrain, rules
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
    rr = RaceResult(track_id=track.id, round=gs.round, season=gs.season, kind=kind,
                    pole=ws.pole, fastest_lap=fastest.driver_id if fastest else "",
                    weather=ws.weather.label)

    team_points = {tid: 0.0 for tid in gs.teams}
    for pos, e in enumerate(order, 1):
        d = gs.drivers.get(e.driver_id)
        team = gs.teams[e.team_id]
        pts = points_for(gs, pos, kind) if e.status == "finished" else 0.0
        if (kind == "gp" and gs.regulations["sporting"].get("fastest_lap_point")
                and fastest and e.driver_id == fastest.driver_id and pos <= 10):
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
        team.points += pts
        team_points[team.id] = team_points.get(team.id, 0.0) + pts
        rr.order.append({
            "driver": e.driver_id, "team": e.team_id, "pos": pos,
            "status": e.status, "reason": e.dnf_reason, "time": round(e.finished_time, 3),
            "laps": e.lap, "stops": e.stops, "best": round(e.best_lap, 3),
            "grid": e.grid, "points": pts, "damage": round(e.damage, 1),
        })

    # usura e danni sulla vettura di ogni squadra
    for team in gs.teams.values():
        dmg = 0.0
        for e in sim.entrants:
            if e.team_id != team.id:
                continue
            dmg += e.damage
            if e.damage > 0:
                _distribute_damage(gs, team, e.damage)
        # l'usura segue i chilometri percorsi: la sprint e' circa un terzo di GP
        team.car.wear(2.6 * min(1.0, sim.laps / max(1, track.laps)), track)
        # i costi fissi del weekend (logistica, stipendi, strutture) e i ricavi
        # si contano una volta sola: alla domenica, sprint o non sprint
        if kind == "gp":
            cost = team.car.repair_all()
            economy.apply_race_finances(gs, team, team_points.get(team.id, 0.0),
                                        gs.position_of(team.id), cost)

    gs.results.append(rr)
    return rr


def _distribute_damage(gs, team, amount: float) -> None:
    keys = list(team.car.parts.keys())
    hits = gs.rng.sample(keys, k=min(3, len(keys)))
    for k in hits:
        team.car.damage(k, amount * gs.rng.uniform(0.2, 0.5))


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
def after_race(gs, dev_budget: float = 1.5, pu_budget: float = 0.0) -> list:
    """Sviluppo, notizie e avanzamento del calendario."""
    msgs = []
    player = gs.player
    development.passive_development(gs, player, dev_budget)
    msgs += development.advance_projects(gs, player)
    development.ai_development(gs)
    powertrain.running_costs(gs)
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

    report["finance"] = economy.end_of_season_finances(gs)

    # crescita/declino dei piloti
    for d in list(gs.drivers.values()) + list(gs.free_agents):
        team = gs.teams.get(d.team)
        quality = 0.5
        if team:
            quality = (0.45 * (team.facilities.get("simulator", 60) / 100.0)
                       + 0.35 * (team.facilities.get("academy", 60) / 100.0)
                       + 0.20 * (team.role("race_engineer").communication / 100.0
                                 if team.role("race_engineer") else 0.6))
        notes = d.progress(quality, gs.rng)
        if team and team.is_player and notes:
            report["progress"].append(f"{d.name}: {', '.join(notes)} (valutazione {d.overall:.0f})")

    for s in [s for t in gs.teams.values() for s in t.staff] + gs.free_staff:
        s.age += 1

    report["market"] = market.run_transfer_window(gs)
    market.new_talents(gs)

    # votazioni in Commissione: le proposte estratte vengono decise dal giocatore
    gs.pending_votes = rules.draw_proposals(gs, gs.commission.get("proposals_per_vote", 3))

    # invecchiamento: chi non reinveste arretra senza sbagliare niente
    lost_car = development.technological_decay(gs)
    lost_fac = facilities.decay(gs)
    facilities.ai_invest(gs)
    report["progress"].append(
        f"Un anno di progresso altrui: la vettura perde {lost_car:.2f} punti di "
        f"competitivita' e le strutture {lost_fac:.1f}. Si recupera solo investendo.")

    # nuovo ciclo tecnico
    reset = float(gs.regulations.pop("pending_reset", 0.0))
    era = _era_for(gs, gs.season + 1)
    if era and era["from"] == gs.season + 1:
        reset = max(reset, era.get("reset_strength", 0.6))
        report["rules"].append(f"Nuovo ciclo tecnico: {era['label']}.")
    if reset > 0:
        development.regulation_reset(gs, reset)
        report["rules"].append("Il nuovo regolamento ha rimescolato i valori in campo.")

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
    for d in gs.drivers.values():
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
    gs.season += 1
    gs.regulations["season"] = gs.season
    gs.round = 0
    gs.phase = "preseason"
    gs.results = [r for r in gs.results if r.season >= gs.season - 3]
    return report


def _era_for(gs, season: int) -> dict | None:
    for era in gs.history_data.get("eras", []):
        if era["from"] <= season <= era["to"]:
            return era
    return None
