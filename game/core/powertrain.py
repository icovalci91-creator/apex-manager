"""Power unit: sviluppo dei motoristi e programma per costruirsene una.

Le power unit non erano un'area di sviluppo: i valori dei motoristi restavano
quelli di partenza per sempre, quindi chi correva da costruttore non vedeva
mai crescere il proprio motore. Il "progetto power unit" era un conto alla
rovescia che a scadenza consegnava un motore di livello fisso, indipendente da
quanto ci si fosse investito e da chi lo dirigeva.

Qui diventa un reparto vero: si investe, si assumono ingegneri, e il tetto
raggiungibile dipende da quanto valgono le persone e la fabbrica.
"""
from __future__ import annotations

from . import economy

# Attributi che la simulazione legge davvero: potenza ed ERS pesano sul giro,
# l'affidabilita' sui ritiri. `efficiency` resta com'e', non essendo ancora
# usata da nessuna parte.
PU_ATTRS = ("power", "ers", "reliability")
PU_MAX = 99.0

# Quanto lentamente si colma la distanza dal proprio tetto, per gara e per
# milione investito. Basso di proposito: una power unit si costruisce in anni.
CLOSE_RATE = 0.012

# Biglietto d'ingresso per fondare il reparto. Tenuto sotto la cassa di
# partenza delle squadre medie: il costo vero e' l'investimento per gara.
PROGRAM_START_COST = 18.0
PROGRAM_MIN_SEASONS = 2       # prima non si scende in pista con roba propria
PROGRAM_FLOOR = 50.0          # per quanto male vada, non si parte da zero

# Tenere in casa una power unit costa comunque, anche senza svilupparla: banchi
# prova, officina, gente. E' la spesa che rende la scelta pesante, e che chi ha
# clienti si ripaga vendendo la fornitura.
PU_OPERATING_COST = 45.0      # M$ a stagione per far girare il reparto

# Integrare la propria power unit nella vettura: chi la costruisce la impacchetta
# meglio, guadagnando in potenza sfruttata e in resistenza all'avanzamento.
INTEGRATION_WORKS = 1.0
# Un team ufficiale non nasce integrato: fra la squadra e la casa ci sono un
# oceano e un fuso orario, e ogni giro di messa a punto costa una settimana in
# piu' di quanto ne costi a chi ha il motore nel capannone accanto. Con gli anni
# le due strutture imparano a lavorare insieme e il divario si chiude quasi
# tutto, ma non subito.
INTEGRATION_PARTNER_NEW = 0.42     # primo anno di matrimonio
INTEGRATION_PARTNER_MAX = 0.85     # a regime, dopo un paio di stagioni
PARTNER_MATURITY_RACES = 48        # gare per arrivarci
EXTERNAL_DEV_PENALTY = 0.88        # la casa lontana sviluppa un po' piu' piano
INTEGRATION_CUSTOMER = 0.25
PARTNER_COST_SHARE = 0.35     # quota del listino che paga un team ufficiale
# Dentro un gruppo la fornitura e' una partita di giro: la satellite paga poco e
# riceve una power unit gia' allineata al telaio della sorella maggiore.
SISTER_COST_SHARE = 0.45
INTEGRATION_SISTER = 0.50
# Un motorista esterno e' comunque una casa automobilistica: investe come e piu'
# di una squadra works. Cio' che la rallenta non e' il portafoglio ma la
# distanza dal reparto telaio, ed e' EXTERNAL_DEV_PENALTY a rappresentarla.
EXTERNAL_BUDGET = 3.0         # M$ a gara spesi da un motorista che non corre
EXTERNAL_DEV_RATE = 1.30      # capacita' tecnica di una casa strutturata

# Le power unit sono omologate: non migliorano gara per gara, si cambia
# specifica. Quello che si fa al banco si accumula in una specifica nuova, e
# quando la si porta in pista arriva tutta insieme - o non arriva, perche' al
# banco funzionava e in gara no. Il regolamento dice quante volte all'anno lo
# si puo' fare.
SPEC_ATTRS = PU_ATTRS
SPEC_WORTH = 0.6              # sotto questo guadagno medio non vale l'omologazione


# Al banco si lavora alla cieca. Mancano i chilometri veri, le temperature
# vere, il degrado vero: si sviluppa contro un modello, e il modello sbaglia.
# Portare la power unit in pista costa prestazione subito - si corre con un
# motore acerbo - ma sblocca i dati che fanno crescere il reparto piu' in
# fretta. E' il compromesso che rende il "quando" una decisione.
BENCH_DEV_PENALTY = 0.60


# ------------------------------------------------------------------ anagrafica
def maker(gs, team) -> dict:
    return gs.engine_makers.get(team.engine, {})


def builder_of(gs, engine_id: str):
    """La squadra che costruisce quella power unit, se corre in griglia."""
    for t in gs.teams.values():
        if t.works and t.engine == engine_id:
            return t
    return None


def customers_of(gs, engine_id: str) -> list:
    return [t for t in gs.teams.values() if t.engine == engine_id and not t.works]


def partner_of(gs, engine_id: str):
    """Il team ufficiale di quel motorista, se esiste."""
    for t in gs.teams.values():
        if t.engine == engine_id and t.is_partner:
            return t
    return None


def supply_cost(gs, team) -> float:
    """Quanto costa a questa squadra la fornitura di power unit, all'anno.

    Chi la costruisce non la compra. Un team ufficiale paga una frazione del
    listino: la casa ci guadagna il marchio e i dati, non il conto. Un cliente
    paga tutto.
    """
    if team.works:
        return 0.0
    full = float(gs.engine_makers.get(team.engine, {}).get("cost_per_customer", 25.0))
    if team.is_partner:
        return round(full * PARTNER_COST_SHARE, 2)
    parent = gs.teams.get(team.parent_team) if team.parent_team else None
    if parent is not None and parent.engine == team.engine:
        return round(full * SISTER_COST_SHARE, 2)
    return full


def rating(eng: dict) -> float:
    """Indice sintetico della power unit, come lo si legge nelle schermate."""
    return sum(float(eng.get(a, 85)) for a in PU_ATTRS) / len(PU_ATTRS)


# -------------------------------------------------------------- capacita' tecnica
def dev_rate(gs, team) -> float:
    """Da 0.5 a 1.6: quanto rende un milione speso in power unit."""
    return 0.50 + 1.10 * (team.pu_strength / 100.0)


def ceiling(gs, team) -> float:
    """Livello massimo raggiungibile con lo staff e la fabbrica di oggi.

    Assumere un buon responsabile powertrain alza il tetto: e' la leva con cui
    un reparto giovane puo' arrivare in alto.
    """
    return min(PU_MAX, 58.0 + 0.45 * team.pu_strength)


def locked(gs) -> bool:
    return bool(gs.regulations.get("pu_development_locked"))


def _equalisation_boost(gs, eng: dict) -> float:
    """La FIA concede sviluppo extra a chi e' indietro, se la norma e' in vigore."""
    if not gs.regulations.get("pu_equalisation"):
        return 1.0
    powers = [float(m.get("power", 85)) for m in gs.engine_makers.values()]
    lo, hi = min(powers), max(powers)
    if hi - lo < 1e-6:
        return 1.0
    deficit = (hi - float(eng.get("power", 85))) / (hi - lo)
    return 1.0 + 0.85 * deficit


# ----------------------------------------------------- la specifica in lavorazione
def specs_allowed(gs) -> int:
    return int(gs.regulations["sporting"].get("pu_specs_per_season", 2))


def spec(gs, engine_id: str) -> dict:
    """Il lavoro di banco accumulato, in attesa di diventare una specifica."""
    tutte = getattr(gs, "pu_specs", None)
    if tutte is None:
        tutte = {}
        gs.pu_specs = tutte
    sp = tutte.get(engine_id)
    if sp is None:
        sp = {"gain": {a: 0.0 for a in SPEC_ATTRS}, "invested": 0.0,
              "used": 0, "races": 0}
        tutte[engine_id] = sp
    sp.setdefault("gain", {a: 0.0 for a in SPEC_ATTRS})
    return sp


def spec_value(sp: dict) -> float:
    """Quanto vale, in media sui tre attributi, la specifica in lavorazione."""
    g = sp.get("gain", {})
    return sum(float(g.get(a, 0.0)) for a in SPEC_ATTRS) / len(SPEC_ATTRS)


def specs_left(gs, engine_id: str) -> int:
    return max(0, specs_allowed(gs) - int(spec(gs, engine_id).get("used", 0)))


# ------------------------------------------------------------------- sviluppo
def _advance(gs, engine_id: str, eng: dict, ceil: float, rate: float,
             budget: float, rng) -> float:
    """Fa lavorare il banco. Il guadagno non va sul motore: va nella specifica."""
    sp = spec(gs, engine_id)
    gained = 0.0
    push = min(2.5, max(0.0, budget) / 2.0)
    for attr in SPEC_ATTRS:
        cur = float(eng.get(attr, 85)) + float(sp["gain"].get(attr, 0.0))
        gap = ceil - cur
        if gap <= 0:
            continue
        step = gap * CLOSE_RATE * push * rate * rng.uniform(0.55, 1.45)
        sp["gain"][attr] = float(sp["gain"].get(attr, 0.0)) + step
        gained += step
    sp["races"] = int(sp.get("races", 0)) + 1
    sp["invested"] = float(sp.get("invested", 0.0)) + max(0.0, budget)
    return gained / len(SPEC_ATTRS)


# ------------------------------------------------------- portarla in pista
def spec_confidence(gs, engine_id: str) -> float:
    """Quanto ci si puo' fidare di quello che dice il banco.

    Contano il responsabile powertrain, la fabbrica che costruisce i pezzi e
    il tempo passato a validare: una specifica cotta in fretta arriva in pista
    con problemi che al banco non erano usciti.
    """
    team = builder_of(gs, engine_id) or partner_of(gs, engine_id)
    if team is None:
        forza, fabbrica = 78.0, 78.0
    else:
        forza = team.pu_strength
        fabbrica = float(team.facilities.get("factory", 65.0))
    sp = spec(gs, engine_id)
    maturita = min(1.0, int(sp.get("races", 0)) / 8.0)
    c = (0.46 * max(0.0, min(1.0, (forza - 45.0) / 50.0))
         + 0.26 * max(0.0, min(1.0, (fabbrica - 45.0) / 50.0))
         + 0.28 * maturita)
    return max(0.05, min(0.96, c))


def spec_odds(gs, engine_id: str) -> dict:
    from .development import outcome_odds
    return outcome_odds(spec_confidence(gs, engine_id), "medio")


def homologate(gs, engine_id: str, free: bool = False) -> tuple:
    """Porta in pista la specifica nuova. Da qui in poi e' quella la power unit.

    Con `free` e' l'omologazione di inizio anno: il lavoro dell'inverno diventa
    la power unit della stagione nuova e non consuma nessun gettone.
    """
    eng = gs.engine_makers.get(engine_id)
    if eng is None:
        return False, "Non e' una power unit che conosciamo."
    if locked(gs) and not free:
        return False, "Il regolamento ha congelato lo sviluppo delle power unit."
    sp = spec(gs, engine_id)
    if not free and specs_left(gs, engine_id) <= 0:
        return False, (f"Il regolamento concede {specs_allowed(gs)} specifiche a "
                       f"stagione: le abbiamo gia' usate tutte.")
    if spec_value(sp) < 0.05:
        return False, "Al banco non c'e' ancora niente che valga un'omologazione."

    from .development import BANDS, roll_outcome
    promesso = spec_value(sp)
    band = roll_outcome(gs, spec_odds(gs, engine_id))
    lo, hi = BANDS[band]
    # una specifica omologata non si butta: se non funziona si torna a girare
    # con la mappatura vecchia, quindi si perde il gettone, non la potenza
    mult = max(0.0, gs.rng.uniform(lo, hi))
    for attr in SPEC_ATTRS:
        eng[attr] = max(30.0, min(PU_MAX, float(eng.get(attr, 85))
                                  + float(sp["gain"].get(attr, 0.0)) * mult))
    # quello che si paga davvero e' l'affidabilita': i banchi non riproducono
    # le temperature vere, e le rotture arrivano in gara
    if band == "fallito":
        eng["reliability"] = max(30.0, float(eng.get("reliability", 85))
                                 - gs.rng.uniform(1.0, 3.0))
    elif band == "sottotono":
        eng["reliability"] = max(30.0, float(eng.get("reliability", 85))
                                 - gs.rng.uniform(0.0, 1.2))
    guadagno = promesso * mult
    if not free:
        sp["used"] = int(sp.get("used", 0)) + 1
    sp["gain"] = {a: 0.0 for a in SPEC_ATTRS}
    sp["races"] = 0
    sp["invested"] = 0.0
    gs.sync_engines()
    testi = {
        "fallito": (f"Specifica nuova in pista: al banco prometteva +{promesso:.1f}, "
                    f"in gara non si vede niente e l'affidabilita' peggiora. "
                    f"Gettone buttato."),
        "sottotono": f"Specifica nuova omologata: rende meno del previsto ({guadagno:+.1f}).",
        "in linea": f"Specifica nuova omologata: {guadagno:+.1f} come da programma.",
        "oltre": f"Specifica nuova omologata: meglio del banco, {guadagno:+.1f}.",
    }
    return True, testi[band]


def end_season(gs) -> list:
    """L'inverno chiude i conti del banco.

    Quello che i motoristi hanno accumulato e non hanno portato in pista
    diventa la power unit dell'anno nuovo: e' l'omologazione di inizio
    stagione, quella che non costa gettoni. Poi i gettoni tornano pieni.
    """
    msgs = []
    for eid in list(gs.engine_makers):
        sp = spec(gs, eid)
        if spec_value(sp) > 0.05:
            ok, msg = homologate(gs, eid, free=True)
            if ok and gs.player.engine == eid:
                msgs.append(f"Omologazione invernale. {msg}")
        sp["used"] = 0
    return msgs


def ai_budget(gs, team) -> float:
    """Quanto ci mette un motorista gestito dal computer."""
    return min(max(0.0, team.cash * 0.06), 1.2 + team.reputation / 55.0)


def develop(gs, player_budget: float = 0.0) -> list[str]:
    """Fa avanzare tutte le power unit di una gara.

    Lo sviluppo motori sta fuori dal tetto di spesa della squadra, come nella
    realta', dove i motoristi hanno un limite tutto loro.
    """
    if locked(gs):
        return []
    msgs = []
    for eid, eng in gs.engine_makers.items():
        team = builder_of(gs, eid)
        if team is None:
            # Motorista esterno: non ha una squadra propria in griglia (Honda con
            # Aston Martin). Sviluppa lo stesso, a spese sue: senza questo la sua
            # power unit resterebbe ferma mentre le altre crescono.
            partner = partner_of(gs, eid)
            if partner is None and not customers_of(gs, eid):
                continue
            ref = partner or max(gs.teams.values(), key=lambda t: t.reputation)
            _advance(gs, eid, eng, min(PU_MAX, 58.0 + 0.45 * max(70.0, ref.reputation)),
                     EXTERNAL_DEV_RATE * EXTERNAL_DEV_PENALTY * _equalisation_boost(gs, eng),
                     EXTERNAL_BUDGET, gs.rng)
            ai_homologate(gs, eid)
            continue
        if team.is_player:
            budget = max(0.0, float(player_budget))
            if budget > 0:
                if team.cash < budget:
                    budget = max(0.0, team.cash)
                if budget > 0:
                    team.add_expense("Sviluppo power unit", round(budget, 3), in_cap=False,
                             category="powertrain")
        else:
            budget = ai_budget(gs, team)
            team.add_expense("Sviluppo power unit", round(budget, 3), in_cap=False,
                             category="powertrain")
        if budget <= 0:
            continue
        rate = dev_rate(gs, team) * _equalisation_boost(gs, eng)
        _advance(gs, eid, eng, ceiling(gs, team), rate, budget, gs.rng)
        if team.is_player:
            sp = spec(gs, eid)
            valore, rimaste = spec_value(sp), specs_left(gs, eid)
            gare_restanti = len(gs.tracks) - gs.round
            if rimaste > 0 and valore > SPEC_WORTH and sp["races"] == 6:
                msgs.append(f"Al banco c'e' una specifica che vale {valore:+.1f}: "
                            f"quando la vogliamo omologare?")
            elif rimaste > 0 and valore > 0.3 and gare_restanti == 3:
                msgs.append(f"Restano {rimaste} omologazioni e tre gare: quello che non "
                            f"portiamo in pista adesso ({valore:+.1f}) lo avremo solo "
                            f"l'anno prossimo.")
        else:
            ai_homologate(gs, eid)
    return msgs


def ai_homologate(gs, engine_id: str) -> None:
    """Quando un motorista del computer decide di cambiare specifica.

    Non si omologa appena si ha qualcosa: si aspetta che il pacchetto valga il
    gettone, perche' i gettoni sono contati. Ma non si arriva neanche a
    dicembre con una specifica pronta in cantina.
    """
    left = specs_left(gs, engine_id)
    if left <= 0:
        return
    sp = spec(gs, engine_id)
    valore = spec_value(sp)
    gare_restanti = max(0, len(gs.tracks) - gs.round)
    # una soglia che si abbassa mano a mano che la stagione finisce
    soglia = SPEC_WORTH * (0.5 + 1.4 * min(1.0, gare_restanti / (5.0 * max(1, left))))
    if valore < max(0.15, soglia):
        return
    if sp.get("races", 0) < 4 and gare_restanti > 4:
        return                     # lasciamola maturare ancora un po'
    prima = rating(gs.engine_makers[engine_id])
    ok, _ = homologate(gs, engine_id)
    if not ok:
        return
    dopo = rating(gs.engine_makers[engine_id])
    # se e' il motore che montiamo noi, la notizia ci riguarda comunque
    if gs.player.engine == engine_id:
        nome = gs.engine_makers[engine_id].get("name", "Il motorista")
        if dopo - prima > 0.15:
            gs.push(f"{nome} porta una specifica nuova: {dopo - prima:+.1f} "
                    f"sulla power unit che montiamo.", "tecnico")
        else:
            gs.push(f"{nome} ha cambiato specifica, ma in pista non si vede "
                    f"({dopo - prima:+.1f}).", "tecnico")


def integration(gs, team) -> float:
    """Da 0 a 1: quanto bene la power unit e' sposata alla vettura.

    Chi si costruisce il motore lo disegna insieme al telaio e ne conosce ogni
    dettaglio; chi lo compra riceve una scatola con le sue quote e ci lavora
    attorno. La differenza vale qualche decimo sul giro.
    """
    if team.is_partner:
        return partner_integration(team)
    if not team.works:
        parent = gs.teams.get(team.parent_team) if team.parent_team else None
        if parent is not None and parent.engine == team.engine:
            return INTEGRATION_SISTER
        return INTEGRATION_CUSTOMER
    return INTEGRATION_CUSTOMER + (INTEGRATION_WORKS - INTEGRATION_CUSTOMER) * min(
        1.0, team.pu_strength / 90.0)


def partner_integration(team) -> float:
    """Quanto e' maturato il rapporto fra la squadra e la sua casa motoristica."""
    m = min(1.0, max(0, team.pu_partner_races) / float(PARTNER_MATURITY_RACES))
    return INTEGRATION_PARTNER_NEW + (INTEGRATION_PARTNER_MAX - INTEGRATION_PARTNER_NEW) * m


def advance_partnership(gs) -> None:
    """Una gara in piu' di lavoro comune. Cambiando casa si ricomincia."""
    for team in gs.teams.values():
        if not team.is_partner:
            continue
        if team.pu_partner_engine != team.engine:
            team.pu_partner_engine = team.engine
            team.pu_partner_races = 0
        team.pu_partner_races += 1


def running_costs(gs) -> list[str]:
    """Costo fisso del reparto motori e incasso dalle forniture, per gara.

    Chi corre col motore proprio paga il reparto tutto l'anno; chi lo vende ai
    clienti se lo ripaga in parte. E' il conto che rende l'autonomia una scelta
    e non un regalo.
    """
    races = max(1, len(gs.tracks))
    msgs = []
    for team in gs.teams.values():
        if not team.works:
            continue
        team.add_expense("Gestione reparto power unit",
                         round(PU_OPERATING_COST / races, 3), in_cap=False,
                         category="powertrain")
        for client in customers_of(gs, team.engine):
            team.add_income(f"Fornitura power unit a {client.short}",
                            round(client.engine_customer_cost / races, 3),
                            category="powertrain")
    return msgs


# ------------------------------------------------- programma di chi e' cliente
def program(gs) -> dict:
    prog = getattr(gs, "pu_program", None)
    if prog is None:
        prog = {"own": False, "level": 0.0, "invested": 0.0, "ready_season": 0,
                "started": False}
        gs.pu_program = prog
    return prog


def base_level(gs) -> float:
    """Da dove parte un reparto nuovo.

    Non da zero: chi apre un reparto motori assume gente che i motori li ha
    gia' fatti, e parte dietro all'ultimo dei motoristi, non fuori scala.
    """
    ratings = [rating(m) for m in gs.engine_makers.values()] or [80.0]
    return max(PROGRAM_FLOOR, min(ratings) - 6.0)


def has_program(gs) -> bool:
    p = program(gs)
    return bool(p.get("started")) and not p.get("own")


def can_found(team) -> tuple:
    """Se questa squadra puo' realisticamente aprire un reparto motori.

    Costruire power unit non e' una spesa in piu': e' un'azienda dentro
    l'azienda, con banchi prova, fonderia e centinaia di persone, che costa
    una fondazione piu' decine di milioni l'anno di sola gestione. In Formula 1
    lo fanno case automobilistiche e gruppi industriali; una squadra
    indipendente compra il motore e concentra tutto sul telaio.
    """
    if getattr(team, "pu_capable", True):
        return True, getattr(team, "pu_reason", "")
    why = getattr(team, "pu_reason", "") or "non ha una casa automobilistica alle spalle"
    return False, f"{team.short} non aprira' mai un reparto motori: {why}."


def start_program(gs, team) -> tuple:
    """Fonda il reparto motori. Da qui in poi si costruisce, non si compra."""
    p = program(gs)
    if p.get("own") or team.works:
        return False, "Costruiamo gia' la nostra power unit."
    if p.get("started"):
        return False, "Il programma e' gia' avviato."
    ok, why = can_found(team)
    if not ok:
        return False, why
    ok, why = economy.can_afford(team, PROGRAM_START_COST, gs, check_cap=False)
    if not ok:
        return False, why
    team.add_expense("Fondazione reparto power unit", PROGRAM_START_COST,
                     in_cap=False, category="powertrain")
    # da adesso il reparto motori va riempito di gente come quello di chiunque
    # altro: comprarlo era un'altra cosa
    team.pu_building = True
    p.update({"own": False, "started": True, "level": base_level(gs),
              "invested": PROGRAM_START_COST, "ready_season": gs.season + PROGRAM_MIN_SEASONS})
    return True, (f"Reparto power unit fondato: la prima unita' nostra non potra' "
                  f"scendere in pista prima del {p['ready_season']}.")


def advance_program(gs, budget: float) -> list[str]:
    """Fa crescere il reparto in costruzione di una gara."""
    if not has_program(gs) or locked(gs):
        return []
    p = program(gs)
    team = gs.player
    budget = max(0.0, float(budget))
    if budget > team.cash:
        budget = max(0.0, team.cash)
    if budget <= 0:
        return []
    team.add_expense("Programma power unit", round(budget, 3), in_cap=False,
                     category="powertrain")
    p["invested"] = p.get("invested", 0.0) + budget
    ceil = ceiling(gs, team)
    gap = ceil - p["level"]
    if gap <= 0:
        return []
    step = (gap * CLOSE_RATE * min(2.5, budget / 2.0)
            * dev_rate(gs, team) * BENCH_DEV_PENALTY)
    p["level"] = min(PU_MAX, p["level"] + step * gs.rng.uniform(0.6, 1.4))
    return []


def debut_outlook(gs, budget: float = 2.0, horizon: int = 24) -> dict:
    """Cosa succede a debuttare adesso invece che fra una stagione.

    Serve a rendere visibile il compromesso: chi debutta subito corre peggio
    oggi ma sviluppa piu' in fretta, chi aspetta arriva con un motore migliore
    ma ha perso mesi di dati veri.
    """
    p = program(gs)
    team = gs.player
    now = float(p.get("level", 0.0))
    ceil = ceiling(gs, team)
    rate = CLOSE_RATE * min(2.5, max(0.0, budget) / 2.0) * dev_rate(gs, team)

    def grow(level, races, penalty):
        for _ in range(races):
            level = min(PU_MAX, level + max(0.0, ceil - level) * rate * penalty)
        return level

    supplied = rating(maker(gs, team))
    return {
        "now": now,
        "supplied": supplied,
        "gap_now": now - supplied,
        "if_debut_now": grow(now, horizon, 1.0),
        "if_wait": grow(now, horizon, BENCH_DEV_PENALTY),
        "ceiling": ceil,
        "bench_penalty": BENCH_DEV_PENALTY,
        "horizon": horizon,
    }


def ready_to_debut(gs) -> bool:
    p = program(gs)
    return has_program(gs) and gs.season >= p.get("ready_season", 9999)


def debut(gs) -> tuple:
    """Manda in pista la power unit costruita in casa."""
    if not ready_to_debut(gs):
        return False, "Il reparto non e' ancora pronto per la pista."
    p = program(gs)
    team = gs.player
    lvl = float(p.get("level", base_level(gs)))
    eid = f"{team.id}_pu"
    gs.engine_makers[eid] = {
        "name": f"{team.name} Powertrains",
        "power": lvl, "ers": max(40.0, lvl - 2.0),
        "reliability": max(35.0, lvl - 6.0),
        "efficiency": max(40.0, lvl - 3.0),
        "cost_per_customer": 24.0,
    }
    team.engine = eid
    team.works = True
    team.engine_customer_cost = 0.0
    p["own"] = True
    gs.sync_engines()
    return True, (f"La nostra power unit debutta: {rating(gs.engine_makers[eid]):.0f} "
                  f"di valutazione dopo {p['invested']:.0f} M$ investiti.")
