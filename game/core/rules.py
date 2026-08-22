"""Commissione F1: proposte di modifica al regolamento e votazioni."""
from __future__ import annotations

from .. import config as C


def team_traits(gs, team) -> dict:
    """Indicatori normalizzati -1..1 usati per capire se una proposta conviene."""
    budgets = [t.budget_base for t in gs.teams.values()]
    bmin, bmax = min(budgets), max(budgets)
    bn = (team.budget_base - bmin) / max(1e-6, bmax - bmin)          # 0 piccolo, 1 grande
    pos = gs.position_of(team.id)
    n = len(gs.teams)
    posn = 1.0 - 2.0 * (pos - 1) / max(1, n - 1)                      # +1 primo, -1 ultimo
    eng = gs.engine_makers.get(team.engine, {})
    all_pw = [m.get("power", 85) for m in gs.engine_makers.values()]
    pun = (eng.get("power", 85) - min(all_pw)) / max(1e-6, max(all_pw) - min(all_pw))
    stars = max((gs.drivers[d].overall for d in team.drivers if d in gs.drivers), default=75)
    tyre = sum(gs.drivers[d].tyre_mgmt for d in team.drivers if d in gs.drivers) / 2.0
    young = sum(1 for d in team.drivers if d in gs.drivers and gs.drivers[d].age <= 23)
    return {
        "big_budget": bn * 2 - 1,
        "small_budget": 1 - bn * 2,
        "reputation": (team.reputation - 75) / 25.0,
        "grid_position_high": posn,
        "grid_position_low": -posn,
        "aero_strength": (team.aero_strength - 78) / 18.0,
        "mechanical_strength": (team.mech_strength - 78) / 18.0,
        "strategy_strength": (team.strategy_strength - 78) / 18.0,
        "pit_crew_strength": (team.pit_strength - 78) / 18.0,
        "reliability_strength": (team.reliability_strength - 78) / 18.0,
        "tyre_mgmt_strength": (tyre - 82) / 12.0,
        "power_strength": pun * 2 - 1,
        "pu_leader": pun * 2 - 1,
        "pu_laggard": 1 - pun * 2,
        "star_drivers": (stars - 84) / 12.0,
        "academy_strength": (team.facilities.get("academy", 60) - 70) / 22.0,
        "young_drivers": young - 0.6,
        "customer_team": 1.0 if not team.works else -1.0,
        "constructor_team": 1.0 if team.works else -1.0,
    }


def appeal_score(gs, team, proposal: dict) -> float:
    tr = team_traits(gs, team)
    return sum(tr.get(k, 0.0) * w for k, w in proposal.get("appeal", {}).items())


def vote_of(gs, team, proposal: dict) -> bool:
    s = appeal_score(gs, team, proposal)
    s += gs.rng.gauss(0.0, 0.32)
    return s > 0.0


def institution_votes(gs, proposal: dict) -> tuple:
    """FIA guarda a costi e sicurezza, FOM allo spettacolo."""
    eff = proposal.get("effects", {})
    fia = 0.0
    fia += -0.9 if eff.get("cost_cap_musd", 0) > 0 else 0.0
    fia += 0.9 if eff.get("cost_cap_musd", 0) < 0 else 0.0
    fia += 0.7 if eff.get("standard_parts") else 0.0
    fia += -1.2 if eff.get("refuelling") else 0.0
    fia += 0.5 if proposal.get("category") == "finanziario" else 0.0
    fom = 0.0
    fom += 1.0 if eff.get("sprint_events", 0) > 0 else 0.0
    fom += -1.0 if eff.get("sprint_events", 0) < 0 else 0.0
    fom += 0.8 if eff.get("mandatory_stops") else 0.0
    fom += 0.7 if eff.get("tyre_deg_multiplier", 0) > 0 else 0.0
    fom += 0.9 if eff.get("third_car") else 0.0
    fom += 0.6 if eff.get("points") else 0.0
    fom += -0.8 if eff.get("prize_flatten") else 0.0
    return fia + gs.rng.gauss(0, 0.3) > 0, fom + gs.rng.gauss(0, 0.3) > 0


def tally(gs, proposal: dict, player_vote: bool | None = None) -> dict:
    com = gs.commission
    yes = 0
    total = len(gs.teams) * com["team_votes"] + com["fia_votes"] + com["fom_votes"]
    detail = []
    for t in gs.teams.values():
        if t.is_player and player_vote is not None:
            v = player_vote
        else:
            v = vote_of(gs, t, proposal)
        yes += com["team_votes"] if v else 0
        detail.append((t.short, v))
    fia, fom = institution_votes(gs, proposal)
    yes += com["fia_votes"] if fia else 0
    yes += com["fom_votes"] if fom else 0
    detail.append(("FIA", fia))
    detail.append(("FOM", fom))
    need = com["threshold_next_season_pct"]
    passed = yes / total >= need
    return {"yes": yes, "total": total, "need": need, "passed": passed, "detail": detail}


def apply_effects(gs, proposal: dict) -> list:
    """Applica gli effetti di una proposta approvata."""
    eff = proposal.get("effects", {})
    reg = gs.regulations
    sport = reg["sporting"]
    notes = []
    for k, v in eff.items():
        if k == "cost_cap_musd":
            reg["cost_cap_musd"] = max(90.0, reg.get("cost_cap_musd", 215.0) + v)
            notes.append(f"Budget cap: {reg['cost_cap_musd']:.0f} M$")
        elif k == "cost_cap_excludes_driver_salaries":
            reg[k] = v
        elif k == "driver_salary_cap_musd":
            reg[k] = v
        elif k == "min_weight_kg":
            reg["min_weight_kg"] = reg.get("min_weight_kg", C.CAR_MASS_KG) + v
            for t in gs.teams.values():
                t.car.mass_base = float(reg["min_weight_kg"])
            notes.append(f"Peso minimo: {reg['min_weight_kg']} kg")
        elif k == "active_aero":
            reg["aero"]["active_aero"] = v
            for t in gs.teams.values():
                t.car.active_aero_allowed = v
            notes.append("Aero attiva " + ("consentita" if v else "abolita"))
        elif k == "downforce_index":
            reg["aero"]["downforce_index"] = max(0.35, reg["aero"]["downforce_index"] + v)
            for t in gs.teams.values():
                t.car.reg_downforce_index = reg["aero"]["downforce_index"]
        elif k == "points":
            sport["points"] = list(v)
            notes.append("Nuovo sistema di punteggio")
        elif k == "fastest_lap_point":
            sport["fastest_lap_point"] = v
        elif k == "sprint_events":
            sport["sprint_events"] = max(0, sport.get("sprint_events", 6) + v)
            _resync_sprints(gs, sport["sprint_events"])
            notes.append(f"Sprint in calendario: {sport['sprint_events']}")
        elif k == "mandatory_stops":
            sport["mandatory_stops"] = v
        elif k == "mandatory_compounds":
            sport["mandatory_compounds"] = v
        elif k == "units_per_season":
            reg["power_unit"]["units_per_season"] += v
        elif k == "pu_development_locked":
            reg["pu_development_locked"] = v
        elif k == "pu_equalisation":
            reg["pu_equalisation"] = v
        elif k == "atr_slope":
            reg["atr_slope"] = v
            notes.append("Nuova scala per le ore di galleria del vento")
        elif k == "testing_days":
            sport["testing_days"] = sport.get("testing_days", 3) + v
        elif k == "rookie_fp1_sessions":
            sport["rookie_fp1_sessions"] = sport.get("rookie_fp1_sessions", 4) + v
        elif k == "tyre_deg_multiplier":
            # il moltiplicatore vive nel regolamento della partita: la gara lo
            # legge da li'. Scalare C.COMPOUNDS sporcherebbe anche le altre
            # carriere aperte nella stessa sessione.
            reg["tyres"]["deg_multiplier"] = max(0.5, reg["tyres"].get("deg_multiplier", 1.0) + v)
            notes.append(f"Degrado gomme: x{reg['tyres']['deg_multiplier']:.2f}")
        elif k == "standard_parts":
            reg["standard_parts"] = v
        elif k == "customer_cars_allowed":
            reg["customer_cars_allowed"] = v
        elif k == "third_car":
            reg["third_car"] = v
        elif k == "refuelling":
            reg["refuelling"] = v
        elif k == "prize_flatten":
            reg["prize_flatten"] = v
        elif k == "cap_carryover_musd":
            reg["cap_carryover_musd"] = v
        elif k == "income_bonus_musd":
            for t in gs.teams.values():
                t.budget_base = max(60.0, t.budget_base + v)
        elif k == "reliability_risk":
            reg["reliability_risk"] = v
        elif k == "reset_strength":
            reg["pending_reset"] = v
        elif k == "electric_share":
            pu = reg["power_unit"]
            tot = pu["ice_kw"] + pu["electric_kw"]
            quota = min(0.75, max(0.25, pu["electric_kw"] / tot + v))
            pu["electric_kw"] = round(tot * quota)
            pu["ice_kw"] = round(tot * (1 - quota))
            notes.append(f"Ripartizione: {pu['ice_kw']} kW termico / {pu['electric_kw']} kW elettrico")
        elif k == "ground_effect":
            reg["aero"]["ground_effect"] = v
            if not v:
                reg["aero"]["downforce_index"] = max(0.35, reg["aero"]["downforce_index"] - 0.12)
                for t in gs.teams.values():
                    t.car.reg_downforce_index = reg["aero"]["downforce_index"]
            notes.append("Effetto suolo " + ("consentito" if v else "abolito"))
        elif k == "grooved_tyres":
            reg["grip_multiplier"] = 0.93 if v else 1.0
            notes.append("Gomme scanalate: meno aderenza meccanica" if v else "Ritorno alle slick")
        elif k == "tyre_war":
            reg["tyre_war"] = v
            notes.append("Piu' fornitori di gomme in gara")
        elif k == "tyre_warmers":
            reg["tyre_warmers"] = v
            notes.append("Termocoperte vietate" if not v else "Termocoperte consentite")
        elif k == "drs":
            reg["aero"]["drs"] = v
            notes.append("Ala mobile " + ("introdotta" if v else "abolita"))
        elif k == "traction_control":
            reg["traction_control"] = v
            notes.append("Controllo di trazione " + ("consentito" if v else "vietato"))
        elif k == "active_suspension":
            reg["active_suspension"] = v
            notes.append("Sospensioni attive " + ("consentite" if v else "vietate"))
        elif k == "pu_reset":
            _rimescola_motori(gs)
            notes.append("Le power unit ripartono da zero")
        elif k in ("standard_hybrid", "pu_bench_limit", "reverse_grid",
                   "aggregate_quali", "supply_obligation"):
            reg[k] = v
    reg.setdefault("applied", []).append(proposal["id"])
    return notes


def _rimescola_motori(gs) -> None:
    """Una rivoluzione motoristica riavvicina tutti i motoristi."""
    from .powertrain import PU_ATTRS
    vals = [sum(float(m.get(a, 85)) for a in PU_ATTRS) / len(PU_ATTRS)
            for m in gs.engine_makers.values()]
    media = sum(vals) / max(1, len(vals))
    for m in gs.engine_makers.values():
        for a in PU_ATTRS:
            cur = float(m.get(a, 85))
            m[a] = max(45.0, cur + (media - cur) * 0.75 + gs.rng.gauss(0, 3.0))


def _resync_sprints(gs, count: int) -> None:
    for t in gs.tracks:
        t.sprint = False
    ranked = sorted(gs.tracks, key=lambda t: -t.traits.get("overtaking", 0.5))
    for t in ranked[:count]:
        t.sprint = True


def draw_proposals(gs, n: int = 3, rng=None) -> list:
    """Estrae le proposte da mettere ai voti.

    `rng` permette alle schermate di mostrarne un'anteprima senza consumare il
    generatore della partita: il voto vero usa quello di gioco.
    """
    applied = set(gs.regulations.get("applied", []))
    pool = [p for p in gs.proposals if p["id"] not in applied]
    if not pool:
        return []
    r = rng or gs.rng

    # Non e' un sorteggio cieco: si discute cio' che in quel momento e' un
    # problema. Se una squadra sta scappando si parla di riequilibrio, se i
    # conti sono tesi si parla di costi, e le rivoluzioni tecniche arrivano
    # di rado.
    standings = gs.constructor_standings()
    dominio = 0.0
    if len(standings) > 1 and standings[0].points > 0:
        dominio = 1.0 - standings[1].points / max(1.0, standings[0].points)
    poveri = sum(1 for t in gs.teams.values() if t.cash < 8.0) / max(1, len(gs.teams))

    def peso(pr):
        w = 1.0
        if dominio > 0.35:
            w += (1.8 if pr.get("reset", 0.0) > 0.3 else 0.4) * dominio
        if poveri > 0.25 and pr.get("area") == "financial":
            w += 1.5 * poveri
        if pr.get("reset", 0.0) > 0.5:
            w *= 0.55
        return max(0.05, w)

    scelte, resto = [], list(pool)
    for _ in range(min(n, len(resto))):
        pesi = [peso(x) for x in resto]
        soglia = r.uniform(0.0, sum(pesi))
        acc = 0.0
        for i, x in enumerate(resto):
            acc += pesi[i]
            if acc >= soglia:
                scelte.append(resto.pop(i))
                break
    return scelte


# ------------------------------------------------------------------ riunioni
def meeting_rounds(gs) -> list:
    """A quali gare si tiene una riunione della Commissione."""
    n = len(gs.tracks)
    quante = int(gs.commission.get("meetings_per_season", 3))
    if quante <= 1:
        return [n]
    passo = n / quante
    return [int(round(passo * (i + 1))) for i in range(quante)]


def meeting_due(gs) -> bool:
    return (gs.round in meeting_rounds(gs)
            and gs.regulations.get("meeting_done_at") != gs.round)


def open_meeting(gs) -> list:
    """Apre la riunione: la FIA mette sul tavolo le proposte."""
    n = int(gs.commission.get("proposals_per_meeting",
                              gs.commission.get("proposals_per_vote", 3)))
    gs.pending_votes = draw_proposals(gs, n)
    gs.regulations["meeting_done_at"] = gs.round
    return gs.pending_votes


def close_meeting(gs, player_votes: dict) -> list:
    """Conta i voti, applica cio' che passa, accumula la spinta al cambiamento."""
    esiti = []
    for pr in list(gs.pending_votes):
        res = tally(gs, pr, (player_votes or {}).get(pr["id"]))
        note = apply_effects(gs, pr) if res["passed"] else []
        if res["passed"]:
            _accumula_ciclo(gs, pr)
        esiti.append((pr, res, note))
        gs.push(("APPROVATA: " if res["passed"] else "RESPINTA: ") + pr["title"]
                + f" ({res['yes']}/{res['total']} voti)", "regole")
    gs.pending_votes = []
    return esiti


def _accumula_ciclo(gs, proposal: dict) -> None:
    """Ogni norma tecnica approvata avvicina il prossimo ciclo tecnico.

    Quando la somma supera la soglia i cambiamenti sono cosi' tanti da fare
    un'era nuova: viene fissata due stagioni piu' avanti, e la sua natura e'
    la somma delle aree toccate da cio' che e' passato. Non c'e' un calendario
    dei cicli: escono da quello che le squadre approvano.
    """
    reset = float(proposal.get("reset", 0.0))
    if reset <= 0.0:
        return
    ciclo = gs.regulations.setdefault(
        "pending_cycle", {"pressure": 0.0,
                          "areas": {"pu": 0.0, "aero": 0.0, "chassis": 0.0},
                          "season": None, "titles": []})
    ciclo["pressure"] += reset
    area = proposal.get("area", "chassis")
    if area in ciclo["areas"]:
        ciclo["areas"][area] += reset
    ciclo["titles"].append(proposal["title"])
    soglia = float(gs.commission.get("cycle_reset_threshold", 1.2))
    if ciclo["season"] is None and ciclo["pressure"] >= soglia:
        ciclo["season"] = gs.season + int(gs.commission.get("cycle_lead_seasons", 2))
        gs.push(f"Le norme approvate sono ormai tante da fare un'era nuova: il ciclo "
                f"tecnico cambia nel {ciclo['season']}.", "regole")


def cycle_focus(gs) -> dict:
    """Da cosa dipendera' la prestazione nel prossimo ciclo."""
    ciclo = gs.regulations.get("pending_cycle") or {}
    aree = ciclo.get("areas") or {}
    tot = sum(aree.values())
    if tot <= 0:
        return {"pu": 0.34, "chassis": 0.33, "aero": 0.33}
    return {k: v / tot for k, v in aree.items()}
