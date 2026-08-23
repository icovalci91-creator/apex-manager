"""Bilancio: ricavi, costi, premi FOM e tetto di spesa."""
from __future__ import annotations

from .. import config as C

# quota del montepremi in base alla posizione nel costruttori
PRIZE_SHARE = [0.150, 0.130, 0.115, 0.100, 0.090, 0.080, 0.072, 0.064, 0.058, 0.052, 0.046]
PRIZE_POOL = 1150.0        # M$ distribuiti dal promoter
TRAVEL_PER_RACE = 0.42     # M$ di logistica per gara


def prize_money(gs, position: int, flatten: float = 0.0) -> float:
    idx = max(0, min(len(PRIZE_SHARE) - 1, position - 1))
    share = PRIZE_SHARE[idx]
    if flatten > 0:
        flat = 1.0 / len(gs.teams)
        share = share * (1 - flatten) + flat * flatten
    return round(PRIZE_POOL * share, 2)


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


def cap_limit(gs) -> float:
    return float(gs.regulations.get("cost_cap_musd", 215.0))


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
    return round(base * (1.0 + CAPEX_SCALE * quota), 2)


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
    limit = cap_limit(gs)
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
    drv_salaries = sum(gs.drivers[d].salary for d in team.drivers if d in gs.drivers) / n
    in_cap = not gs.regulations.get("cost_cap_excludes_driver_salaries", True)
    items.append(("Ingaggi piloti", round(drv_salaries, 3), in_cap, "piloti"))
    return items


def prize_advance(gs, team) -> float:
    """Rata del montepremi pagata gara per gara.

    La FOM non salda a fine anno: distribuisce durante la stagione sulla base
    del piazzamento precedente, e conguaglia a dicembre. Senza questo una
    squadra resterebbe in rosso da maggio a dicembre pur essendo in attivo.
    """
    flatten = float(gs.regulations.get("prize_flatten", 0.0))
    return round(prize_money(gs, team.last_position, flatten) / max(1, len(gs.tracks)), 3)


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
    limit = cap_limit(gs)
    thr = gs.regulations["sporting"].get("budget_penalty_threshold_pct", 5) / 100.0
    for pos, team in enumerate(gs.constructor_standings(), 1):
        prize = prize_money(gs, pos, flatten)
        # durante l'anno sono gia' state pagate le rate sul piazzamento
        # precedente: a dicembre si versa solo la differenza
        anticipato = round(prize_money(gs, team.last_position, flatten), 2)
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
        if team.is_player:
            msgs.append(f"Premio FOM incassato: {prize} M$ per il {pos}o posto costruttori.")
    return msgs


def can_afford(team, amount: float, gs=None, check_cap: bool = True) -> tuple:
    if team.cash < amount:
        return False, "Liquidita' insufficiente."
    if check_cap and gs is not None:
        if team.spent + amount > cap_limit(gs):
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
