"""Bilancio: ricavi, costi, premi FOM e tetto di spesa."""
from __future__ import annotations

from .. import config as C

# Il montepremi non e' una scala sola. Nella realta' ha due colonne: una parte
# uguale per tutte le squadre che ne hanno diritto, e una legata al piazzamento
# nel costruttori. Meta' del piatto non dipende da dove sei arrivato, ed e' il
# motivo per cui una squadra di coda sta in piedi: senza quella colonna il
# rapporto fra primo e ultimo era 3,26, cioe' l'ultima incassava meno di un
# terzo della prima e in fondo alla griglia non tornavano i conti.
PRIZE_POOL = 1150.0        # M$ distribuiti dal promoter
PRIZE_EQUAL_SHARE = 0.45   # quota del piatto divisa in parti uguali
# quota della seconda colonna, quella legata al piazzamento
PRIZE_SHARE = [0.150, 0.130, 0.115, 0.100, 0.090, 0.080, 0.072, 0.064, 0.058,
               0.052, 0.046, 0.043]
# Il premio di anzianita': chi c'e' da sempre porta pubblico e sponsor a tutto
# il campionato, e da sempre se lo fa pagare. E' il caso della Ferrari.
PRIZE_HERITAGE = 0.05
TRAVEL_PER_RACE = 0.42     # M$ di logistica per gara
DAMAGE_RESERVE = 8.0       # M$ a stagione di riparazioni, che arrivano sempre


def prize_money(gs, position: int, flatten: float = 0.0, team=None) -> float:
    """Quanto incassa dal promoter chi chiude in quella posizione."""
    n = max(1, len(gs.teams))
    quota_uguale = PRIZE_POOL * PRIZE_EQUAL_SHARE / n
    idx = max(0, min(len(PRIZE_SHARE) - 1, position - 1))
    share = PRIZE_SHARE[idx]
    if flatten > 0:
        flat = 1.0 / n
        share = share * (1 - flatten) + flat * flatten
    # la seconda colonna si normalizza sulle quote in gioco, cosi' il piatto
    # distribuito resta quello indipendentemente da quante squadre ci sono
    tot = sum(PRIZE_SHARE[:n]) or 1.0
    # il premio di anzianita' esce dal piatto, non si aggiunge: quello che
    # prende la Ferrari lo mettono tutti gli altri
    merito = PRIZE_POOL * (1.0 - PRIZE_EQUAL_SHARE - PRIZE_HERITAGE) * share / tot
    extra = PRIZE_POOL * PRIZE_HERITAGE if team is not None and heritage(team) else 0.0
    # chi e' appena entrato non ha diritto alla colonna uguale per tutti: quella
    # si divide fra chi si e' classificato nei campionati scorsi, e lui non
    # c'era. E' la cosa che piu' di ogni altra rende dura la prima stagione
    if team is not None:
        from . import newteam
        f = newteam.prize_factor(gs, team)
        if f < 1.0:
            return round((quota_uguale + merito) * f, 2)
    return round(quota_uguale + merito + extra, 2)


def heritage(team) -> bool:
    """Chi ha il premio di anzianita'."""
    return bool(getattr(team, "heritage", False))


def sponsor_income(gs, team, race_points: float, position: int) -> float:
    """Ricavo commerciale per gara.

    La parte grossa arriva dagli accordi firmati; resta una quota di ricavi
    minori (biglietteria, ospitalita', merchandising) legata alla notorieta'
    della squadra e ai punti appena portati a casa.
    """
    from . import sponsors
    contratti = sponsors.race_income(gs, team)
    minori = team.budget_base * 0.18 / len(gs.tracks) * (0.7 + 0.3 * team.reputation / 100.0)
    return round(contratti + minori + race_points * 0.03, 3)


def cap_limit(gs, team=None) -> float:
    """Il tetto di spesa della stagione, per tutti o per una squadra sola.

    Se il regolamento permette di riportare avanti quello che non si e' speso,
    chi l'anno prima e' stato sotto si porta dietro un pezzo di margine: e' il
    solo motivo per cui il tetto puo' essere diverso da una squadra all'altra.
    """
    base = float(gs.regulations.get("cost_cap_musd", 215.0))
    if team is None:
        return base
    riporto = (gs.regulations.get("cap_carry") or {}).get(team.id, 0.0)
    return round(base + float(riporto), 2)


# ------------------------------------------------------- spesa in conto capitale
# Il tetto di spesa non copre quello che si costruisce. Una galleria del vento,
# un simulatore, un capannone nuovo sono spesa in conto capitale, e stanno fuori
# dal budget tecnico: hanno un limite loro, contato su piu' stagioni invece che
# anno per anno, con una scala che concede di piu' a chi ha le strutture messe
# peggio - serve proprio a lasciargli modo di rimettersi in pari.
#
# Quello che resta dentro il tetto tecnico e' far girare le strutture: energia,
# manutenzione, chi ci lavora. Costruire sta fuori, usare sta dentro.
CAPEX_WINDOW = 4         # stagioni su cui si conta il limite
CAPEX_SCALE = 0.55       # quanto in piu' ne ha l'ultima rispetto alla prima


def capex_limit(gs, team) -> float:
    """Quanto puo' spendere in costruzioni una squadra nel periodo."""
    base = float(gs.regulations.get("capex_limit_musd", 45.0))
    n = max(2, len(gs.teams))
    quota = (max(1, min(n, team.last_position)) - 1) / (n - 1)
    # a chi entra da zero il regolamento concede di piu': senza, una fabbrica
    # non si tira su prima che la squadra sia gia' morta
    from . import newteam
    return round(base * (1.0 + CAPEX_SCALE * quota) + newteam.capex_bonus(gs, team), 2)


def capex_spent(gs, team) -> float:
    """Quanto ne ha gia' speso nelle stagioni che contano."""
    log = team.capex_log or {}
    prima = gs.season - CAPEX_WINDOW
    return round(sum(v for k, v in log.items() if prima < int(k) <= gs.season), 3)


def capex_left(gs, team) -> float:
    return round(max(0.0, capex_limit(gs, team) - capex_spent(gs, team)), 3)


def can_afford_capex(gs, team, amount: float) -> tuple:
    """Serve la liquidita' e serve il margine nel limite capitale."""
    if team.cash < amount:
        return False, "Liquidita' insufficiente."
    resto = capex_left(gs, team)
    if amount > resto:
        return False, (f"Fuori dal limite per le costruzioni: restano {resto:.1f} M$ "
                       f"su {capex_limit(gs, team):.0f} in {CAPEX_WINDOW} stagioni.")
    return True, ""


def cap_usage(gs, team) -> tuple:
    limit = cap_limit(gs, team)
    return team.spent, limit, (team.spent / limit if limit else 0.0)


def race_costs(gs, team, damage_cost: float) -> list:
    """Voci di costo di un weekend: (etichetta, importo, dentro_il_cap, categoria)."""
    items = [("Logistica e trasferta", TRAVEL_PER_RACE, True, "gara")]
    if damage_cost > 0.001:
        items.append(("Riparazioni e ricambi", round(damage_cost, 3), True, "danni"))
    n = max(1, len(gs.tracks))
    items.append(("Stipendi staff", round(team.staff_cost / n, 3), True, "personale"))
    items.append(("Gestione strutture", round(team.facility_upkeep / n, 3), True, "strutture"))
    if not team.works:
        items.append(("Fornitura power unit", round(team.engine_customer_cost / n, 3),
                      False, "powertrain"))
    # anche il terzo pilota si paga, e i ragazzi del vivaio pure
    tutti = list(team.drivers) + list(team.reserves) + list(team.academy)
    drv_salaries = sum(gs.drivers[d].salary for d in tutti if d in gs.drivers) / n
    in_cap = not gs.regulations.get("cost_cap_excludes_driver_salaries", True)
    items.append(("Ingaggi piloti", round(drv_salaries, 3), in_cap, "piloti"))
    from . import academy
    vivaio = academy.running_cost(gs, team)
    if vivaio > 0:
        # il vivaio sta fuori dal tetto di spesa, come nella realta': e' un
        # programma della casa, non un costo della monoposto
        items.append((f"Vivaio ({team.academy_name})", round(vivaio / n, 3),
                      False, "piloti"))
    return items


def prize_advance(gs, team) -> float:
    """Rata del montepremi pagata gara per gara.

    La FOM non salda a fine anno: distribuisce durante la stagione sulla base
    del piazzamento precedente, e conguaglia a dicembre. Senza questo una
    squadra resterebbe in rosso da maggio a dicembre pur essendo in attivo.
    """
    flatten = float(gs.regulations.get("prize_flatten", 0.0))
    return round(prize_money(gs, team.last_position, flatten, team) / max(1, len(gs.tracks)), 3)


def apply_race_finances(gs, team, race_points: float, position: int, damage_cost: float) -> dict:
    inc = sponsor_income(gs, team, race_points, position)
    team.add_income("Sponsor e diritti", inc, category="sponsor")
    anticipo = prize_advance(gs, team)
    team.add_income("Rata diritti commerciali", anticipo, category="premi")
    inc += anticipo
    total_out = 0.0
    for label, amt, in_cap, cat in race_costs(gs, team, damage_cost):
        team.add_expense(label, amt, in_cap, category=cat)
        total_out += amt
    return {"in": inc, "out": round(total_out, 3), "net": round(inc - total_out, 3)}


def end_of_season_finances(gs) -> list:
    """Premi FOM e verifica del tetto di spesa. Ritorna i messaggi da mostrare."""
    msgs = []
    flatten = float(gs.regulations.get("prize_flatten", 0.0))
    thr = gs.regulations["sporting"].get("budget_penalty_threshold_pct", 5) / 100.0
    massimo_riporto = float(gs.regulations.get("cap_carryover_musd", 0.0) or 0.0)
    riporti = {}
    for pos, team in enumerate(gs.constructor_standings(), 1):
        limit = cap_limit(gs, team)
        prize = prize_money(gs, pos, flatten, team)
        # durante l'anno sono gia' state pagate le rate sul piazzamento
        # precedente: a dicembre si versa solo la differenza
        anticipato = round(prize_money(gs, team.last_position, flatten, team), 2)
        saldo = round(prize - anticipato, 2)
        if saldo >= 0:
            team.add_income(f"Conguaglio FOM ({pos}o posto)", saldo, category="premi")
        else:
            team.add_expense(f"Restituzione FOM ({pos}o posto)", -saldo,
                             in_cap=False, category="premi")
        team.last_position = pos
        over = team.spent - limit
        if over > 0:
            if over <= limit * thr:
                fine = round(over * 1.5 + 2.0, 2)
                team.add_expense("Multa sforamento budget cap", fine, in_cap=False,
                                 category="sanzioni")
                msgs.append(f"{team.short}: sforamento lieve del cap, multa di {fine} M$.")
            else:
                fine = round(over * 3.0 + 8.0, 2)
                team.add_expense("Sanzione grave budget cap", fine, in_cap=False,
                                 category="sanzioni")
                pen = min(30, int(over / 3))
                team.points = max(0.0, team.points - pen)
                msgs.append(f"{team.short}: sforamento grave, {fine} M$ di multa e -{pen} punti.")
            # una violazione accertata e' l'unico motivo, oltre alla sicurezza,
            # per cui la federazione puo' cambiare le carte in corsa
            gs.regulations["violation_pending"] = True
        if team.is_player:
            msgs.append(f"Premio FOM incassato: {prize} M$ per il {pos}o posto costruttori.")
        # e quello che non si e' speso, se il regolamento lo consente, resta
        # in cassa per l'anno dopo: e' un premio a chi ha tenuto i conti in
        # ordine, e un problema per chi si illude di poterlo accumulare
        if massimo_riporto > 0:
            avanzo = max(0.0, limit - team.spent)
            riporti[team.id] = round(min(massimo_riporto, avanzo), 2)
            if team.is_player and riporti[team.id] > 0.5:
                msgs.append(f"Budget non speso riportato al {gs.season + 1}: "
                            f"{riporti[team.id]:.1f} M$.")
    if massimo_riporto > 0:
        gs.regulations["cap_carry"] = riporti
    # i conti col proprietario si chiudono dopo i premi, che e' quando si sa
    # davvero com'e' andata
    for team in gs.teams.values():
        msgs += owner_settlement(gs, team)
    return msgs


# ------------------------------------------------------------- il proprietario
# L'utile resta in squadra. Il proprietario di una scuderia di Formula 1 non e'
# un azionista che stacca il dividendo e se ne va: mette i soldi quando servono
# e li lascia dentro quando ci sono, perche' l'unica cosa che gli interessa e'
# che la macchina vada piu' forte.
#
# E i soldi in cassa servono davvero, perche' non tutto passa dal tetto di
# spesa: costruzioni, ingaggi dei piloti e indennizzi per portare via un
# ingegnere a un'altra squadra si pagano con la liquidita'. Chi ne ha poca non
# riesce nemmeno a riempire il budget che il regolamento gli concederebbe, ed
# e' esattamente la differenza fra il fondo e la testa della griglia.
#
# Quello che il proprietario fa sul serio e' l'altro lato: copre le perdite, e
# l'anno dopo si spende meno.
RESERVE_SHARE = 0.35     # riserva di lavoro, in quote di tetto di spesa
AUSTERITY_STEP = 0.35    # quanto stringe la cinghia chi si fa coprire le perdite
AUSTERITY_EASE = 0.5     # e quanto si allenta ogni stagione in cui i conti tengono


def reserve(gs) -> float:
    """La liquidita' che una squadra tiene da parte per far girare la baracca."""
    return round(cap_limit(gs) * RESERVE_SHARE, 2)


def war_chest(gs, team) -> float:
    """Quello che c'e' in cassa oltre la riserva: capitale, non fondo cassa."""
    return round(team.cash - reserve(gs), 2)


def spending_appetite(gs, team) -> float:
    """Da 0 a 1: quanto una squadra puo' permettersi di spingere oltre il minimo.

    Chi ha solo la riserva vive di quello che incassa, gara per gara. Chi ha
    capitale in cassa lo mette sul tavolo - strutture, ingegneri, piloti,
    pacchetti - perche' i soldi fermi non fanno punti.
    """
    if team.cash <= 0:
        return 0.0
    return max(0.0, min(1.0, war_chest(gs, team) / max(1.0, reserve(gs) * 0.6)))


def owner_settlement(gs, team) -> list:
    """Chiude i conti col proprietario: copre le perdite. L'utile resta dentro."""
    msgs = []
    ris = reserve(gs)
    if team.cash < 0:
        buco = -team.cash
        team.add_income("Copertura perdite dal proprietario", round(buco + ris * 0.25, 2),
                        category="proprieta")
        # la stretta si somma a quella dell'anno prima, ma quella vecchia si
        # allenta comunque: altrimenti chi perde poco tutti gli anni finirebbe
        # per non spendere piu' niente, e sarebbe la fine e non una difficolta'
        team.austerity = min(1.0, team.austerity * 0.75
                             + AUSTERITY_STEP * min(2.0, buco / max(1.0, ris)))
        if team.is_player:
            msgs.append(f"Il proprietario ha coperto {buco:.0f} M$ di perdite, ma per l'anno "
                        f"prossimo il budget e' stretto: si spende il "
                        f"{(1 - team.austerity) * 100:.0f}% del normale.")
        else:
            msgs.append(f"{team.short}: perdite coperte dalla proprieta', stagione di magra.")
    else:
        team.austerity = max(0.0, team.austerity * AUSTERITY_EASE)
        if team.is_player and war_chest(gs, team) > 0:
            msgs.append(f"Stagione chiusa in utile: {team.cash:.0f} M$ restano in cassa, "
                        f"{war_chest(gs, team):.0f} oltre la riserva di lavoro. Sono i "
                        f"soldi per costruire, per gli ingaggi e per i pacchetti.")
    return msgs


def spending_room(gs, team) -> float:
    """Quanto puo' permettersi di spendere, da 0 a 1.

    Chi e' appena stato salvato dal proprietario tira la cinghia: non e' una
    punizione, e' quello che succede davvero quando i conti non tornano.
    """
    return max(0.15, 1.0 - float(getattr(team, "austerity", 0.0)))


# Quanta parte del capitale oltre la riserva un proprietario e' disposto a
# bruciare in una stagione. Non tutto: chi svuota la cassa in un anno l'anno
# dopo non c'e' piu'.
OWNER_INJECTION = 0.18


def season_room(gs, team) -> float:
    """Quanto resta per lo sviluppo dopo i costi che non si possono evitare.

    Una squadra non decide quanto spendere guardando la cassa: guarda quello
    che incassa e quello che deve pagare comunque - stipendi, strutture,
    piloti, motore, trasferte - e mette sul tavolo la differenza. Senza questo
    conto le scuderie del computer spendevano in proporzione a quanto avevano
    in banca, quindi dare piu' soldi a una squadra di coda non la salvava: ne
    spendeva di piu' e chiudeva in perdita lo stesso.
    """
    from . import powertrain, sponsors
    gare = max(1, len(gs.tracks))
    flatten = float(gs.regulations.get("prize_flatten", 0.0))
    entrate = prize_money(gs, team.last_position, flatten, team)
    entrate += sponsors.annual_income(team)
    entrate += team.budget_base * 0.18

    # i danni non si scelgono ma si sanno: una stagione di gare li porta sempre,
    # e chi fa il budget senza metterli in conto sbaglia il budget
    fisse = team.staff_cost + team.facility_upkeep + TRAVEL_PER_RACE * gare
    fisse += DAMAGE_RESERVE
    from . import academy as _acc
    fisse += _acc.running_cost(gs, team)
    fisse += sum(gs.drivers[d].salary
                 for d in list(team.drivers) + list(team.reserves) + list(team.academy)
                 if d in gs.drivers)
    if team.works:
        fisse += powertrain.PU_OPERATING_COST
    else:
        fisse += team.engine_customer_cost
    # e poi c'e' il capitale, che e' la cosa che tiene in piedi chi non si regge
    # ancora sui propri ricavi. Il proprietario prima paga il buco - le luci si
    # accendono comunque - e di quello che avanza ne mette sul tavolo una parte.
    # E' l'unico modo in cui una squadra appena entrata, che dal promoter non
    # prende niente, sviluppa qualcosa invece di limitarsi a sopravvivere.
    scoperto = max(0.0, fisse - entrate)
    capitale = max(0.0, team.cash - reserve(gs) * 0.35)
    coperto = min(capitale, scoperto)
    resta = capitale - coperto
    return round(max(0.0, entrate + coperto + resta * OWNER_INJECTION - fisse), 2)


# Quanto avanza a una squadra in salute, dopo i costi fissi: serve a dire se
# una scuderia puo' permettersi il ritmo normale di sviluppo, test e simulatore
# o deve andarci piano.
DISCRETIONARY_REF = 40.0

# Le voci che si scelgono: sviluppo, pacchetti, simulatore, test privati. Il
# resto - stipendi, strutture, trasferte - si paga e basta.
VOCI_SCELTE = ("sviluppo",)


def spent_discretionary(gs, team) -> float:
    """Quanto ha gia' speso in cose facoltative in questa stagione."""
    return round(sum(m["amount"] for m in team.ledger
                     if m["kind"] == "out" and m.get("season") == gs.season
                     and m.get("category") in VOCI_SCELTE), 2)


def room_left(gs, team) -> float:
    """Quello che resta da spendere in questa stagione, dopo il gia' speso.

    E' il portafoglio vero: un vincolo sul singolo impegno non basta, perche'
    chiuso un pacchetto se ne apre un altro e a fine anno il conto e' triplo.
    """
    return round(max(0.0, season_room(gs, team) - spent_discretionary(gs, team)), 2)


def budget_health(gs, team) -> float:
    """0 se non resta niente, 1 se resta quanto a una squadra tranquilla."""
    return max(0.0, min(1.0, room_left(gs, team) / DISCRETIONARY_REF))


# ------------------------------------------------------- il direttore finanziario
# Quanto e' larga la forbice della previsione, da un direttore scarso a uno
# bravo. Non e' che uno spenda meno: e' che sa dove andra' a finire, e nel
# tetto di spesa saperlo in anticipo vale quanto averli, i soldi.
FORECAST_ERR_MAX = 18.0
FORECAST_ERR_MIN = 2.5


def committed(gs, team) -> float:
    """Quello che si e' gia' impegnati a pagare e non e' ancora uscito."""
    aperti = sum(max(0.0, pr.budget - pr.invested) for pr in team.dev_projects)
    prove = sum(t.cost * 0.06 * 3 for t in team.spec_trials
                if t.state == "affinamento")
    return round(aperti + prove, 2)


def forecast_error(team) -> float:
    """Di quanto puo' sbagliare la previsione, in milioni."""
    q = max(0.0, min(1.0, (team.finance_strength - 45.0) / 45.0))
    return round(FORECAST_ERR_MAX - (FORECAST_ERR_MAX - FORECAST_ERR_MIN) * q, 1)


def cap_forecast(gs, team) -> dict:
    """Dove si andra' a finire col tetto di spesa, se si va avanti cosi'.

    Somma quello che e' gia' uscito, quello a cui ci si e' impegnati e quello
    che le gare che restano si porteranno via comunque. La forbice attorno alla
    previsione la decide il direttore finanziario.
    """
    limite = cap_limit(gs, team)
    gare = max(0, len(gs.tracks) - gs.round)
    n = max(1, len(gs.tracks))
    fissi_gara = (team.staff_cost + team.facility_upkeep) / n + TRAVEL_PER_RACE
    fissi_gara += DAMAGE_RESERVE / n
    previsto = team.spent + committed(gs, team) + fissi_gara * gare
    err = forecast_error(team)
    margine = limite - previsto
    # il rischio di sforare: la previsione e' una forbice, non un numero
    if err <= 0.01:
        rischio = 1.0 if margine < 0 else 0.0
    else:
        rischio = max(0.0, min(1.0, 0.5 - margine / (2.0 * err)))
    return {"speso": round(team.spent, 2), "limite": limite,
            "impegnato": committed(gs, team), "fissi": round(fissi_gara * gare, 2),
            "previsto": round(previsto, 2), "margine": round(margine, 2),
            "errore": err, "rischio": round(rischio, 3), "gare": gare}


def spendable(gs, team) -> float:
    """Quanto si puo' ancora impegnare restando ragionevolmente al sicuro.

    E' il margine previsto meno la forbice: un direttore bravo lascia poco
    inutilizzato, uno scarso costringe a tenersi larghi.
    """
    f = cap_forecast(gs, team)
    return round(max(0.0, f["margine"] - f["errore"]), 2)


def cap_advice(gs, team, spesa: float = 0.0) -> tuple:
    """Cosa direbbe il direttore finanziario davanti a una spesa. (colore, frase)."""
    f = cap_forecast(gs, team)
    margine = f["margine"] - spesa
    err = f["errore"]
    nome = "Il direttore finanziario"
    d = team.role("financial_director")
    if d is not None:
        nome = d.name
    if margine < -err:
        return "male", (f"{nome}: cosi' si sfora di sicuro, siamo "
                        f"{abs(margine):.0f} M$ oltre il tetto.")
    if margine < err:
        return "attento", (f"{nome}: siamo al limite, il margine e' {margine:.0f} M$ "
                           f"con un'incertezza di {err:.0f}. Non ci metterei altro.")
    if margine < err * 2.5:
        return "ok", (f"{nome}: ci sta, restano {margine:.0f} M$ di margine su una "
                      f"previsione a +/-{err:.0f}.")
    return "ok", (f"{nome}: nessun problema, avanzano {margine:.0f} M$ e la "
                  f"previsione e' buona a +/-{err:.0f}.")


def can_afford(team, amount: float, gs=None, check_cap: bool = True) -> tuple:
    if team.cash < amount:
        return False, "Liquidita' insufficiente."
    if check_cap and gs is not None:
        if team.spent + amount > cap_limit(gs, team):
            return False, "Supereresti il tetto di spesa (budget cap)."
    return True, ""


# ---------------------------------------------------------------- bilancio
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

CATEGORIE = {
    "sponsor": "Sponsor e accordi commerciali",
    "premi": "Premi e diritti televisivi",
    "cessioni": "Cessioni e indennizzi",
    "personale": "Stipendi e personale",
    "piloti": "Ingaggi piloti",
    "sviluppo": "Sviluppo e aggiornamenti",
    "powertrain": "Power unit",
    "strutture": "Strutture e impianti",
    "gara": "Costi di gara e logistica",
    "danni": "Riparazioni",
    "sanzioni": "Multe e sanzioni",
    "proprieta": "Utili e coperture della proprieta'",
    "altro": "Altro",
}


def ledger_of(team, season=None) -> list:
    if season is None:
        return list(team.ledger)
    return [m for m in team.ledger if m["season"] == season]


def by_month(team, season: int) -> list:
    """Entrate, uscite e saldo mese per mese. Ritorna dodici righe."""
    righe = []
    for mese in range(1, 13):
        entrate = sum(m["amount"] for m in team.ledger
                      if m["season"] == season and m["month"] == mese and m["kind"] == "in")
        uscite = sum(m["amount"] for m in team.ledger
                     if m["season"] == season and m["month"] == mese and m["kind"] == "out")
        righe.append({"month": mese, "label": MESI[mese], "in": entrate,
                      "out": uscite, "net": entrate - uscite})
    return righe


def by_category(team, season: int, verso: str) -> list:
    """Voci aggregate per categoria, dalla piu' pesante."""
    tot = {}
    for m in team.ledger:
        if m["season"] == season and m["kind"] == verso:
            tot[m["category"]] = tot.get(m["category"], 0.0) + m["amount"]
    voci = [{"category": k, "label": CATEGORIE.get(k, k), "amount": v}
            for k, v in tot.items()]
    voci.sort(key=lambda x: -x["amount"])
    return voci


def by_year(team) -> list:
    """Conto economico di ogni stagione registrata."""
    anni = sorted({m["season"] for m in team.ledger})
    out = []
    for a in anni:
        entrate = sum(m["amount"] for m in team.ledger if m["season"] == a and m["kind"] == "in")
        uscite = sum(m["amount"] for m in team.ledger if m["season"] == a and m["kind"] == "out")
        cap = sum(m["amount"] for m in team.ledger
                  if m["season"] == a and m["kind"] == "out" and m["in_cap"])
        out.append({"season": a, "in": entrate, "out": uscite,
                    "net": entrate - uscite, "in_cap": cap})
    return out


def season_summary(team, season: int) -> dict:
    entrate = sum(m["amount"] for m in team.ledger
                  if m["season"] == season and m["kind"] == "in")
    uscite = sum(m["amount"] for m in team.ledger
                 if m["season"] == season and m["kind"] == "out")
    return {"in": entrate, "out": uscite, "net": entrate - uscite,
            "cash": team.cash, "spent": team.spent}
