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


SISTER_ALIGNMENT = 0.60      # quanto una satellite pesa l'interesse del gruppo


def vote_of(gs, team, proposal: dict) -> bool:
    s = appeal_score(gs, team, proposal)
    parent = gs.teams.get(team.parent_team) if team.parent_team else None
    if parent is not None and parent is not team:
        # La seconda squadra di un gruppo vota in larga parte con la prima: e'
        # la critica classica a chi in Commissione si ritrova due voti.
        s = s * (1.0 - SISTER_ALIGNMENT) + appeal_score(gs, parent, proposal) * SISTER_ALIGNMENT
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
    # al tavolo ordinario si discutono ritocchi: un cambiamento profondo non si
    # decide alzando la mano in una riunione, ha bisogno del suo percorso
    soglia = float(gs.commission.get("ordinary_reset_max", 0.35))
    pool = [p for p in gs.proposals
            if p["id"] not in applied and float(p.get("reset", 0.0)) <= soglia]
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
    """A quali gare si tiene una riunione della Commissione.

    Le riunioni stanno nei primi mesi della stagione, come nella realta': si
    discute entro la primavera cosa cambiare per l'anno dopo, perche' piu'
    avanti non ci sarebbe piu' il tempo di progettarci sopra.
    """
    n = len(gs.tracks)
    quante = int(gs.commission.get("meetings_per_season", 3))
    ultimo = int(gs.commission.get("meeting_last_month", 5))
    finestra = [i for i, t in enumerate(gs.tracks, 1) if getattr(t, "month", 12) <= ultimo]
    if len(finestra) < quante:
        finestra = list(range(1, n + 1))
    passo = len(finestra) / quante
    return sorted({finestra[min(len(finestra) - 1, int(round(passo * (i + 1))) - 1)]
                   for i in range(quante)})


def meeting_due(gs) -> bool:
    return (gs.round in meeting_rounds(gs)
            and gs.regulations.get("meeting_done_at") != gs.round)


def open_meeting(gs) -> list:
    """Apre la riunione: la FIA mette sul tavolo le proposte dell'anno.

    Nella stessa giornata, se e' il momento, si siede anche il tavolo tecnico
    per il regolamento che verra': sono due discussioni diverse, una sui
    ritocchi di adesso e una sul mondo di fra qualche anno.
    """
    n = int(gs.commission.get("proposals_per_meeting",
                              gs.commission.get("proposals_per_vote", 3)))
    gs.pending_votes = draw_proposals(gs, n)
    gs.regulations["meeting_done_at"] = gs.round
    if talks_due(gs):
        open_talks(gs)
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


# ==================================================== il tavolo del ciclo nuovo
# Un cambiamento profondo non si vota in una riunione. Si apre un tavolo, ci si
# siede quattro o cinque volte, ognuno tira dalla propria parte e alla fine si
# firma un compromesso che non e' la proposta di nessuno. Da quel momento
# servono ancora un paio di stagioni prima che le macchine nuove scendano in
# pista: senza quel tempo non ci sarebbe modo di progettarle.
AREE = ("pu", "aero", "chassis")

ETICHETTA_AREA = {"pu": "power unit", "aero": "aerodinamica", "chassis": "telaio"}


def team_position(gs, team) -> tuple:
    """Che regolamento vuole una scuderia: dove spostare il peso e quanto osare.

    Si spinge su cio' in cui si e' forti - e' sempre andata cosi' - e si e'
    tanto piu' disposti a rivoltare il tavolo quanto peggio si sta andando: chi
    vince vuole continuita', chi perde vuole che cambi tutto.
    """
    eng = gs.engine_makers.get(team.engine, {})
    tutte = [m.get("power", 85) for m in gs.engine_makers.values()] or [85]
    pu = (eng.get("power", 85) - min(tutte)) / max(1e-6, max(tutte) - min(tutte))
    peso = {
        "pu": 0.25 + 0.75 * pu * (1.25 if team.works else 0.75),
        "aero": 0.25 + 0.75 * max(0.0, (team.aero_strength - 68.0) / 26.0),
        "chassis": 0.25 + 0.75 * max(0.0, (team.mech_strength - 68.0) / 26.0),
    }
    # in Commissione non si porta una posizione sfumata: si va a chiedere una
    # cosa. Quello in cui si e' piu' forti diventa la richiesta, il resto e'
    # contorno
    aree = _polarizza(peso, 3.2)
    pos = gs.position_of(team.id)
    n = max(2, len(gs.teams))
    forza = 0.28 + 0.60 * ((pos - 1) / (n - 1))
    return aree, max(0.1, min(1.0, forza))


def _polarizza(peso: dict, gamma: float) -> dict:
    """Accentua la differenza fra le voci e normalizza a somma 1."""
    forte = {k: max(0.001, v) ** gamma for k, v in peso.items()}
    tot = sum(forte.values()) or 1.0
    return {k: v / tot for k, v in forte.items()}


def _posizioni(gs, spinta: str | None = None, radicale: float | None = None) -> list:
    """Tutti quelli che siedono al tavolo, con il loro peso."""
    voci = []
    for t in gs.teams.values():
        aree, forza = team_position(gs, t)
        if t.is_player and spinta in AREE:
            # la nostra squadra porta al tavolo la linea che abbiamo scelto
            aree = {k: (0.74 if k == spinta else 0.13) for k in AREE}
            if radicale is not None:
                forza = max(0.1, min(1.0, radicale))
        # al tavolo tutti hanno un voto, ma non tutti hanno la stessa voce:
        # una squadra storica che minaccia di andarsene pesa piu' di un'altra
        peso = 0.60 + 0.80 * (t.reputation / 100.0)
        voci.append((aree, forza, peso, t.short))
    # la FIA guarda ai costi e alla sicurezza: vuole cambiamenti contenuti e
    # spalmati, la FOM vuole spettacolo e quindi che la griglia si rimescoli
    voci.append(({"pu": 0.34, "aero": 0.33, "chassis": 0.33}, 0.35, 4.0, "FIA"))
    voci.append(({"pu": 0.30, "aero": 0.42, "chassis": 0.28}, 0.85, 3.0, "FOM"))
    return voci


def _media(voci: list) -> tuple:
    """Dove converge il tavolo.

    Non e' la media aritmetica delle richieste: un regolamento non e' mai un
    terzo per uno. Chi raccoglie piu' sostegno detta la direzione e agli altri
    si concede qualcosa, quindi la coalizione piu' larga pesa piu' di quanto
    dicano i numeri nudi.
    """
    tot = sum(v[2] for v in voci) or 1.0
    aree = {k: sum(v[0].get(k, 0.0) * v[2] for v in voci) / tot for k in AREE}
    return _polarizza(aree, 3.0), sum(v[1] * v[2] for v in voci) / tot


def _distanza(voci: list, aree: dict) -> float:
    """Quanto sono lontane le posizioni: da qui dipende se bastano 4 riunioni."""
    tot = sum(v[2] for v in voci) or 1.0
    return sum(sum(abs(v[0].get(k, 0.0) - aree[k]) for k in AREE) * v[2]
               for v in voci) / tot


def talks(gs) -> dict | None:
    return gs.regulations.get("cycle_talks")


def last_cycle_season(gs) -> int:
    ere = [e["from"] for e in gs.history_data.get("eras", []) if e["from"] <= gs.season]
    return max(ere) if ere else int(gs.regulations.get("first_season", gs.season))


def _era_corrente(gs) -> dict | None:
    for era in gs.history_data.get("eras", []):
        if era["from"] <= gs.season <= era.get("to", era["from"]):
            return era
    return None


def talks_due(gs) -> bool:
    """E' ora di aprire il tavolo per il regolamento nuovo?

    Si comincia con l'anticipo che serve: fra le riunioni e le stagioni di
    progettazione passano anni, quindi un ciclo che finisce nel 2030 si discute
    dal 2028. Se invece si e' gia' approvato tanto da rendere il cambiamento
    inevitabile, il tavolo si apre prima.
    """
    if talks(gs) or (gs.regulations.get("pending_cycle") or {}).get("season"):
        return False
    anticipo = max(2, int(gs.commission.get("cycle_lead_seasons", 2)))
    era = _era_corrente(gs)
    if era and era.get("to"):
        if gs.season >= int(era["to"]) - anticipo:
            return True
    minimo = int(gs.commission.get("cycle_min_seasons", 4))
    if gs.season - last_cycle_season(gs) >= minimo:
        return True
    # oppure sono gia' passate tante norme tecniche da renderlo inevitabile
    ciclo = gs.regulations.get("pending_cycle") or {}
    return ciclo.get("pressure", 0.0) >= float(gs.commission.get("cycle_reset_threshold", 1.2))


def open_talks(gs) -> dict:
    """Apre il tavolo tecnico e dice quante riunioni serviranno."""
    voci = _posizioni(gs)
    aree, forza = _media(voci)
    lontani = _distanza(voci, aree)
    servono = 5 if lontani > float(gs.commission.get("talks_split", 0.36)) else 4
    st = {"aperto": True, "riunioni": 0, "servono": servono,
          "aree": aree, "forza": forza, "storia": []}
    gs.regulations["cycle_talks"] = st
    gs.push(f"La FIA apre il tavolo per il prossimo ciclo tecnico: se ne parlera' in "
            f"{servono} riunioni prima di arrivare a un accordo.", "regole")
    return st


def talks_round(gs, spinta: str | None = None, radicale: float | None = None) -> dict:
    """Una riunione del tavolo. Ritorna com'e' andata."""
    st = talks(gs)
    if not st or not st.get("aperto"):
        return {}
    voci = _posizioni(gs, spinta, radicale)
    obiettivo, forza_media = _media(voci)
    # il compromesso si avvicina, non si salta: e' il senso di sedersi piu' volte
    passo = 0.45
    st["aree"] = {k: st["aree"][k] * (1 - passo) + obiettivo[k] * passo for k in AREE}
    st["forza"] = st["forza"] * (1 - passo) + forza_media * passo
    st["riunioni"] += 1
    dom = max(st["aree"], key=st["aree"].get)
    riga = (f"Riunione {st['riunioni']} di {st['servono']}: il tavolo si sta orientando "
            f"verso {ETICHETTA_AREA[dom]} ({st['aree'][dom]*100:.0f}%).")
    st["storia"].append(riga)
    esito = {"riga": riga, "accordo": False, "stagione": None}
    if st["riunioni"] >= st["servono"]:
        esito.update(_accordo(gs, st))
    gs.push(riga, "regole")
    return esito


def _accordo(gs, st: dict) -> dict:
    """Si firma. Da qui in avanti si sa cosa arrivera' e quando."""
    anticipo = max(2, int(gs.commission.get("cycle_lead_seasons", 2)))
    stagione = gs.season + anticipo
    ciclo = gs.regulations.setdefault(
        "pending_cycle", {"pressure": 0.0, "areas": {k: 0.0 for k in AREE},
                          "season": None, "titles": []})
    ciclo["areas"] = {k: st["aree"][k] for k in AREE}
    ciclo["pressure"] = max(ciclo.get("pressure", 0.0), st["forza"] * 1.25)
    ciclo["season"] = stagione
    dom = max(st["aree"], key=st["aree"].get)
    ciclo["titles"] = ciclo.get("titles", []) + [f"accordo sul ciclo {stagione}"]
    gs.regulations.pop("cycle_talks", None)
    msg = (f"Accordo raggiunto: il nuovo regolamento entra in vigore nel {stagione} e a "
           f"decidere sara' soprattutto {ETICHETTA_AREA[dom]} ({st['aree'][dom]*100:.0f}%). "
           f"Da adesso si puo' cominciare a prepararlo.")
    gs.push(msg, "regole")
    return {"accordo": True, "stagione": stagione, "riga": msg}


def cycle_focus(gs) -> dict:
    """Da cosa dipendera' la prestazione nel prossimo ciclo.

    Finche' il tavolo e' aperto e' quello che sta emergendo dalle riunioni, e
    puo' ancora cambiare: e' il motivo per cui prepararsi troppo presto e'
    rischioso.
    """
    st = talks(gs)
    if st and st.get("aree"):
        tot = sum(st["aree"].values()) or 1.0
        return {k: v / tot for k, v in st["aree"].items()}
    ciclo = gs.regulations.get("pending_cycle") or {}
    aree = ciclo.get("areas") or {}
    tot = sum(aree.values())
    if tot <= 0:
        return {"pu": 0.34, "chassis": 0.33, "aero": 0.33}
    return {k: v / tot for k, v in aree.items()}
