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

# Su cosa si lavora, adesso che la potenza di picco ha un tetto che nessuno
# puo' scavalcare. Quando il numero grosso e' scritto nel regolamento, la
# power unit non si fa piu' con i cavalli: si fa con tutto il resto.
#
#   power       il termico: quanto ci si avvicina ai quattrocento kilowatt che
#               il regolamento concede. E' l'asse che satura prima, perche' il
#               tetto e' li' e non si sposta
#   recupero    quanta energia si riprende frenando. Il regolamento ne concede
#               8.5 MJ a giro: prenderli tutti e' un problema di batteria, di
#               freno elettrico e di raffreddamento, e nessuno ci arriva
#   software    la centralina: come si passano la palla il termico e
#               l'elettrico, quanto e' pulito il taglio della spinta, quanto
#               dell'energia che si ha in cassa si riesce davvero a mettere a
#               terra dove serve. E' l'asse che oggi separa le power unit
#   reliability quello che non si rompe
#   efficiency  quanta benzina serve per fare la gara: meno se ne carica, piu'
#               leggera parte la macchina
PU_ATTRS = ("power", "recupero", "software", "reliability", "efficiency")
PU_MAX = 99.0

# Quanto e' difficile muovere ognuno di questi assi. Il termico e' quasi
# arrivato al tetto e ogni decimo costa; la centralina e' software, e il
# software si scrive; il recupero sta in mezzo perche' e' fatto di hardware.
DIFFICOLTA = {"power": 0.62, "recupero": 1.00, "software": 1.35,
              "reliability": 1.05, "efficiency": 0.88}

# E da cosa dipende ciascuno, oltre che dai soldi: il termico e il recupero
# vogliono la fabbrica e i banchi, la centralina vuole il reparto simulazione e
# la gente che scrive modelli, l'affidabilita' vuole qualita' e materiali.
FONTE = {"power": "factory", "recupero": "factory", "software": "simulator",
         "reliability": "factory", "efficiency": "simulator"}

# Tirare il termico verso il tetto scalda, e quello che scalda si rompe: oltre
# questa quota di lavoro sul termico l'affidabilita' comincia ad arretrare.
POWER_SICURO = 0.40
POWER_COSTO = 0.055

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
    # un motorista al completo sa di avere il coltello dalla parte del manico e
    # il prezzo lo fa lui. Con l'obbligo di fornitura il listino e' calmierato:
    # e' la meta' del senso della norma, l'altra e' che nessuno resta a piedi
    if (len(customers_of(gs, team.engine)) >= LIMITE_CLIENTI
            and not gs.regulations.get("supply_obligation")):
        full *= 1.25
    if team.is_partner:
        return round(full * PARTNER_COST_SHARE, 2)
    parent = gs.teams.get(team.parent_team) if team.parent_team else None
    if parent is not None and parent.engine == team.engine:
        return round(full * SISTER_COST_SHARE, 2)
    return full


# Quanti clienti puo' reggere un motorista, oltre alla propria squadra. Il
# tetto e' vero: sopra un certo numero di forniture non ci stanno ne' i banchi
# ne' le persone in pista. Quando sono tutti pieni, chi cerca un motore resta
# a piedi - a meno che il regolamento non obblighi qualcuno a prenderselo.
LIMITE_CLIENTI = 3


def fornitore_libero(gs) -> str | None:
    """Chi puo' ancora vendere una power unit, o chi e' obbligato a farlo.

    Si guarda prima chi ha posto, e fra quelli si prende il meno carico: e' il
    modo in cui le forniture si distribuiscono da sole. Se non ha posto
    nessuno, decide il regolamento: con l'obbligo di fornitura il motorista con
    meno clienti se lo prende comunque, senza si resta senza motore.
    """
    conta = {eid: len(customers_of(gs, eid)) for eid in gs.engine_makers}
    if not conta:
        return None
    liberi = [e for e, n in conta.items() if n < LIMITE_CLIENTI]
    if liberi:
        return min(liberi, key=lambda e: (conta[e], -rating(gs.engine_makers[e])))
    if gs.regulations.get("supply_obligation"):
        return min(conta, key=lambda e: conta[e])
    return None


# La ripartizione del lavoro, quando nessuno l'ha ancora scelta: un quinto per
# uno non e' una strategia, e' il punto di partenza.
FOCUS_BASE = {a: 1.0 / len(PU_ATTRS) for a in PU_ATTRS}


def prepara(eng: dict) -> dict:
    """Porta una power unit scritta com'era al modo in cui si lavora adesso.

    Nei dati c'e' un solo numero per tutta la parte ibrida: `ers`. Da li' si
    ricavano i due assi veri - quanto si recupera e quanto vale la centralina -
    tenendoli vicini a quel numero ma non identici, perche' non esiste una casa
    che sia brava allo stesso modo nell'hardware e nel software.
    """
    base = float(eng.get("ers", 85))
    eng.setdefault("recupero", round(base + 1.0, 1))
    eng.setdefault("software", round(base - 1.0, 1))
    eng.setdefault("efficiency", round(base, 1))
    eng.setdefault("focus", dict(FOCUS_BASE))
    eng["ers"] = round((float(eng["recupero"]) + float(eng["software"])) / 2.0, 1)
    return eng


def focus_di(eng: dict) -> dict:
    """Come e' ripartito il lavoro al banco, normalizzato a uno."""
    f = {a: max(0.0, float((eng.get("focus") or {}).get(a, FOCUS_BASE[a])))
         for a in PU_ATTRS}
    tot = sum(f.values())
    if tot <= 1e-6:
        return dict(FOCUS_BASE)
    return {a: v / tot for a, v in f.items()}


def imposta_focus(gs, engine_id: str, quote: dict) -> tuple:
    """Il giocatore decide su cosa lavora il banco."""
    eng = gs.engine_makers.get(engine_id)
    if eng is None:
        return False, "Non e' una power unit che conosciamo."
    if locked(gs):
        return False, "Il regolamento ha congelato lo sviluppo delle power unit."
    eng["focus"] = {a: max(0.0, float(quote.get(a, 0.0))) for a in PU_ATTRS}
    if sum(eng["focus"].values()) <= 1e-6:
        eng["focus"] = dict(FOCUS_BASE)
    return True, "Il banco lavora su quello che hai deciso."


def rating(eng: dict) -> float:
    """Indice sintetico della power unit, come lo si legge nelle schermate."""
    return sum(float(eng.get(a, 85)) for a in PU_ATTRS) / len(PU_ATTRS)


# -------------------------------------------------------------- capacita' tecnica
# Il tetto alle ore di banco, quando c'e': funziona come la restrizione
# aerodinamica, cioe' toglie di piu' a chi sta davanti. Non congela lo
# sviluppo, lo rallenta e lo riavvicina.
BANCO_BASE = 0.60
BANCO_PASSO = 0.055


def bench_factor(gs, engine_id: str) -> float:
    """Quanto puo' girare il banco di questo motorista, se ci sono ore contate."""
    if not gs.regulations.get("pu_bench_limit"):
        return 1.0
    ordine = sorted(gs.engine_makers.items(), key=lambda kv: -rating(kv[1]))
    posto = next((i for i, (k, _) in enumerate(ordine) if k == engine_id), 0)
    return min(1.0, BANCO_BASE + BANCO_PASSO * posto)


def dev_rate(gs, team) -> float:
    """Da 0.5 a 1.6: quanto rende un milione speso in power unit."""
    base = 0.50 + 1.10 * (team.pu_strength / 100.0)
    return base * bench_factor(gs, team.engine)


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
def _spinta_reparto(team, attr: str) -> float:
    """Quanto aiuta la struttura su quell'asse.

    Il termico e il recupero si fanno con i banchi e la fabbrica; la centralina
    si fa con il reparto simulazione e con la gente che scrive modelli. Un
    motorista con una fabbrica bellissima e nessun simulatore fa cavalli e non
    fa software, e si vede.
    """
    if team is None:
        return 1.0
    val = float((getattr(team, "facilities", None) or {}).get(FONTE.get(attr, "factory"), 65.0))
    return 0.80 + 0.40 * max(0.0, min(1.0, val / 100.0))


def _advance(gs, engine_id: str, eng: dict, ceil: float, rate: float,
             budget: float, rng, team=None) -> float:
    """Fa lavorare il banco. Il guadagno non va sul motore: va nella specifica."""
    sp = spec(gs, engine_id)
    gained = 0.0
    push = min(2.5, max(0.0, budget) / 2.0)
    # con l'ibrido di fornitura unica la parte elettrica non e' piu' roba da
    # motoristi: al banco restano il termico, l'affidabilita' e i consumi
    standard = bool(gs.regulations.get("standard_hybrid"))
    attrs = [a for a in SPEC_ATTRS
             if not (standard and a in ("recupero", "software"))]
    quote = focus_di(eng)
    # il lavoro tolto agli assi che il regolamento chiude si ridistribuisce
    resto = sum(quote[a] for a in attrs) or 1.0
    for attr in attrs:
        cur = float(eng.get(attr, 85)) + float(sp["gain"].get(attr, 0.0))
        gap = ceil - cur
        if gap <= 0:
            continue
        # tutto il banco su un asse solo lo fa correre cinque volte piu' di
        # quanto correrebbe spalmato, ed e' esattamente la scelta che si fa
        quota = quote[attr] / resto * len(attrs)
        step = (gap * CLOSE_RATE * push * rate * quota * DIFFICOLTA[attr]
                * _spinta_reparto(team, attr) * rng.uniform(0.55, 1.45))
        sp["gain"][attr] = float(sp["gain"].get(attr, 0.0)) + step
        gained += step
    # e tirare il termico costa: quello che si guadagna in cavalli lo si perde
    # in cose che si rompono, ed e' la scelta piu' vecchia che ci sia
    troppo = quote.get("power", 0.0) - POWER_SICURO
    if troppo > 0 and "reliability" in attrs:
        sp["gain"]["reliability"] = (float(sp["gain"].get("reliability", 0.0))
                                     - troppo * POWER_COSTO * push * rng.uniform(0.6, 1.4))
    sp["races"] = int(sp.get("races", 0)) + 1
    sp["invested"] = float(sp.get("invested", 0.0)) + max(0.0, budget)
    return gained / max(1, len(attrs))


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
    prepara(eng)          # `ers` resta la media dei due assi ibridi
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
                     EXTERNAL_BUDGET, gs.rng, team=ref)
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
        _advance(gs, eid, eng, ceiling(gs, team), rate, budget, gs.rng, team=team)
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


# =============================================== il programma sull'architettura
# La cosa che una squadra puo' fare, e che nella realta' fanno tutte: mettere
# gente a lavorare sul motore che *forse* ci sara' fra tre anni, prima che il
# regolamento lo dica. Se ci si azzecca si arriva al primo anno del ciclo nuovo
# con il lavoro gia' fatto; se il tavolo decide diversamente resta in mano
# quello che si e' imparato lo stesso - materiali, combustione, banchi - che
# non e' niente ma non e' nemmeno tutto.
#
# Non serve il permesso di nessuno per aprirlo: si puo' cominciare mentre il
# tavolo sta ancora discutendo, o anche prima, su un'architettura che nella
# bozza non c'e'. E' una scommessa, e le scommesse le fa chi vuole.
PROG_MIN = 1.0            # meno di un milione a stagione non e' un programma
PROG_MAX = 20.0           # oltre, il tetto di spesa non regge
RESA_ARCH = 0.60          # quanto rende un milione speso sull'architettura giusta
RESA_SBAGLIATA = 0.10     # e quanto ne resta se il tavolo decide un'altra cosa
ANTICIPO_PASSO = 0.14     # quanto vale ogni stagione di vantaggio
ANTICIPO_MAX = 1.70


def programma_arch(team) -> dict:
    """Il programma anticipato di questa squadra, se ce n'e' uno."""
    return getattr(team, "arch_prog", None) or {}


def avvia_arch(gs, team, aid: str, budget: float) -> tuple:
    """Apre - o ridisegna - il programma su un'architettura futura."""
    from . import architetture
    if aid not in architetture.catalogo(gs):
        return False, "Questa architettura non esiste."
    budget = round(max(PROG_MIN, min(PROG_MAX, float(budget))), 1)
    vecchio = programma_arch(team)
    investito = float(vecchio.get("investito", 0.0)) if vecchio.get("arch") == aid else 0.0
    da = int(vecchio.get("da", gs.season)) if vecchio.get("arch") == aid else gs.season
    if vecchio.get("arch") and vecchio.get("arch") != aid:
        # cambiare cavallo a meta' strada non azzera tutto, ma quasi
        investito = float(vecchio.get("investito", 0.0)) * 0.25
    team.arch_prog = {"arch": aid, "budget": budget, "investito": round(investito, 2),
                      "da": da}
    return True, (f"Programma {architetture.etichetta(gs, aid)} avviato: "
                  f"{budget:.1f} M$ a stagione.")


def chiudi_arch(gs, team) -> tuple:
    """Chiude il programma. Quello che si e' speso resta speso."""
    prog = programma_arch(team)
    if not prog.get("arch"):
        return False, "Non c'e' nessun programma aperto."
    team.arch_prog = {"arch": "", "budget": 0.0,
                      "investito": round(float(prog.get("investito", 0.0)), 2),
                      "da": int(prog.get("da", gs.season))}
    return True, "Programma sospeso: la gente torna sul motore di adesso."


def investi_arch(gs) -> None:
    """La rata di questa gara, per chi ha un programma aperto."""
    races = max(1, len(gs.tracks))
    for team in gs.teams.values():
        prog = programma_arch(team)
        budget = float(prog.get("budget", 0.0))
        if not prog.get("arch") or budget <= 0:
            continue
        rata = round(budget / races, 3)
        if team.cash < rata:
            continue
        team.add_expense("Programma architettura futura", rata, in_cap=True,
                         category="powertrain")
        prog["investito"] = round(float(prog.get("investito", 0.0)) + rata, 3)
        from . import architetture
        architetture.impara(team, gs, prog["arch"], rata)


def resa_arch(gs, team, arch_finale: str) -> tuple:
    """Cosa resta in mano quando il ciclo nuovo arriva davvero.

    Se l'architettura e' quella su cui si e' lavorato, tutto il programma
    diventa vantaggio, e vale di piu' quanto prima si e' cominciato. Se e'
    un'altra, resta la parte che non dipende da quanti cilindri ci sono.
    """
    prog = programma_arch(team)
    investito = float(prog.get("investito", 0.0))
    if investito <= 0.5:
        return 0.0, ""
    from . import architetture
    scelta = prog.get("arch", "")
    stagioni = max(1, gs.season - int(prog.get("da", gs.season)) + 1)
    # i soldi non bastano: quel lavoro lo devono fare degli ingegneri, in una
    # fabbrica, con il mestiere giusto in casa. Chi non ce l'ha spende uguale e
    # porta a casa meno
    attrezzi = architetture.attrezzatura(gs, team, scelta)
    if scelta == arch_finale:
        anticipo = min(ANTICIPO_MAX, 1.0 + ANTICIPO_PASSO * (stagioni - 1))
        punti = (investito * RESA_ARCH * anticipo
                 * (0.75 + 0.5 * team.dev_rate) * attrezzi)
        come = ("con gli strumenti giusti" if attrezzi >= 1.05 else
                "pur senza gli strumenti di chi sta davanti" if attrezzi < 0.85 else
                "con quello che avevamo")
        nota = (f"{team.short}: il programma {architetture.etichetta(gs, scelta)} era "
                f"quello giusto - {investito:.0f} M$ spesi in {stagioni} stagioni, "
                f"{come}, arrivano sulla macchina nuova.")
    else:
        punti = investito * RESA_SBAGLIATA * (0.6 + 0.4 * attrezzi)
        nota = (f"{team.short}: il programma {architetture.etichetta(gs, scelta)} non "
                f"serve piu' - il tavolo ha scelto un'altra strada e di "
                f"{investito:.0f} M$ resta quello che si e' imparato.")
    team.arch_prog = {"arch": "", "budget": 0.0, "investito": 0.0, "da": gs.season}
    return round(punti, 2), nota


def ai_arch(gs) -> None:
    """Su cosa scommettono le squadre del computer, e con quanti soldi.

    Non lo fanno tutte e non lo fanno subito: si comincia quando il tavolo e'
    aperto, si guarda cosa dice la bozza e si mette sul piatto quello che ci si
    puo' permettere. Una squadra ricca che ha la power unit scarsa e' quella
    che ci va piu' pesante: e' il momento in cui puo' rimettersi in pari.
    """
    from . import architetture, rules
    st = rules.talks(gs)
    ciclo = gs.regulations.get("pending_cycle") or {}
    bozza = (st or {}).get("motori") or {}
    fissata = ciclo.get("arch") or ""
    if not bozza and not fissata:
        return
    for team in gs.teams.values():
        if team.is_player:
            continue
        prog = programma_arch(team)
        if prog.get("arch") and prog.get("budget"):
            continue
        if gs.rng.random() > 0.35:
            continue          # non e' una decisione che si prende ogni gara
        pref = architetture.preferenza_squadra(gs, team)
        if not pref:
            continue
        if fissata:
            scelta = fissata          # a bozza firmata non si scommette piu'
        else:
            # meta' quello che vuole il tavolo e meta' quello che vorrebbe lei
            punteggi = {k: 0.55 * bozza.get(k, 0.0) + 0.45 * pref.get(k, 0.0)
                        for k in pref}
            scelta = max(punteggi, key=punteggi.get)
        quanto = 3.0 + 9.0 * max(0.0, min(1.0, (team.budget_base - 130.0) / 120.0))
        avvia_arch(gs, team, scelta, round(quanto, 1))


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
