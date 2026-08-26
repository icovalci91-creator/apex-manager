"""Le architetture di power unit, e cosa cambia passare da una all'altra.

Un ciclo tecnico non e' una percentuale: e' una decisione su come sara' fatto
il motore. Sei cilindri turbo con meta' della potenza elettrica, otto cilindri
turbo con l'ibrido ridotto all'osso, dieci aspirati senza niente. Cambia il
suono, cambia il peso, cambia quanto costa costruirlo, e cambia soprattutto il
mestiere: con il V6 del 2026 la gara si vince gestendo l'energia, con un V10 la
si vince in staccata e basta.

Qui dentro c'e' il catalogo - sta in data/regulations.json, con i numeri veri -
e il modo di metterne una in vigore. Metterla in vigore vuol dire toccare i
numeri che il modello di giro legge davvero: quanta potenza c'e', quanta ne e'
elettrica, dove smette di spingere, quanta energia si recupera, quanta benzina
serve. Da li' in poi i circuiti si rimisurano da soli.
"""
from __future__ import annotations


_CATALOGO: dict = {}


def catalogo(gs=None) -> dict:
    """Tutte le architetture fra cui il tavolo tecnico puo' scegliere.

    Stanno nei dati e non nel salvataggio: sono un catalogo, non uno stato, e
    si leggono una volta sola per tutta la sessione.
    """
    global _CATALOGO
    if not _CATALOGO:
        from .state import _load
        _CATALOGO = _load("regulations.json").get("architetture", {})
    return _CATALOGO


def scheda(gs, aid: str) -> dict:
    return dict(catalogo(gs).get(aid, {}))


def corrente(gs) -> str:
    return str((gs.regulations.get("power_unit") or {}).get("architettura",
                                                            "v6_turbo_ibrido"))


def etichetta(gs, aid: str) -> str:
    return scheda(gs, aid).get("breve", aid)


def descrizione(gs, aid: str) -> str:
    a = scheda(gs, aid)
    if not a:
        return ""
    aspir = "turbo" if a.get("aspirazione") == "turbo" else "aspirato"
    return (f"{a.get('cilindri', 6)} cilindri {a.get('cilindrata_cc', 1600) / 1000:.1f} "
            f"litri {aspir}, {a.get('giri_max', 15000):,} giri, "
            f"{a.get('ice_kw', 400)} kW termici e {a.get('elettrico_kw', 0)} elettrici"
            .replace(",", "."))


def applica(gs, aid: str) -> list:
    """Mette in vigore un'architettura. Ritorna le righe da mostrare.

    Non e' un'etichetta: i numeri finiscono dove il gioco li legge davvero -
    nel modello di giro, nella gestione dell'energia, nel serbatoio - e i
    circuiti vanno rimisurati subito dopo, perche' con un'altra power unit si
    frena in un altro punto.
    """
    a = scheda(gs, aid)
    if not a:
        return []
    pu = gs.regulations.setdefault("power_unit", {})
    pu["architettura"] = aid
    pu["layout"] = f"V{a.get('cilindri', 6)} {a.get('aspirazione', 'turbo')}"
    pu["capacity_cc"] = a.get("cilindrata_cc", 1600)
    pu["max_rpm"] = a.get("giri_max", 15000)
    pu["ice_kw"] = a.get("ice_kw", 400)
    pu["electric_kw"] = a.get("elettrico_kw", 350)
    pu["batteria_mj"] = a.get("batteria_mj", 4.0)
    pu["es_usable_mj"] = a.get("batteria_mj", 4.0)
    pu["harvest_max_mj_lap"] = a.get("recupero_max_mj", 8.5)
    pu["fuel_race_target_kg"] = a.get("benzina_kg", 70)
    pu["pu_min_weight_kg"] = a.get("peso_pu_kg", 185)
    mod = pu.setdefault("modello", {})
    # il modello di giro sa fare i conti su quanta potenza e' elettrica, ma non
    # saprebbe cosa farsene di "tutta": il giro senza spinta elettrica, quello
    # con cui si misura quanto vale l'energia, con quota 1.0 non esisterebbe
    mod["quota_elettrica"] = min(0.90, a.get("quota_elettrica", 0.47))
    mod["v_taglio_kmh"] = a.get("v_taglio_kmh", 320)
    mod["v_fine_kmh"] = a.get("v_fine_kmh", 380)
    mod["recupero_max_mj"] = a.get("recupero_max_mj", 8.5)
    mod["potenza_rel"] = a.get("potenza_rel", 1.0)
    # il peso della vettura segue quello della power unit: un V10 senza batteria
    # non pesa come un ibrido con quattro megajoule a bordo
    base = float(gs.regulations.get("min_weight_kg", 768.0))
    delta = a.get("peso_pu_kg", 185) - 185
    if delta:
        gs.regulations["min_weight_kg"] = round(max(600.0, base + delta), 0)
        for t in gs.teams.values():
            t.car.mass_base = float(gs.regulations["min_weight_kg"])
    return [f"Architettura {a.get('nome', aid)}: {descrizione(gs, aid)}.",
            f"Peso minimo {gs.regulations['min_weight_kg']:.0f} kg, "
            f"{a.get('benzina_kg', 70)} kg di benzina a gara, "
            f"batteria da {a.get('batteria_mj', 0.0):.1f} MJ."]


# ---------------------------------------------- ingegneri, banchi, fabbrica
# Scommettere sull'architettura giusta non basta: bisogna anche saperla fare.
# Un V10 lo costruisce chi ha un reparto termico e una fabbrica, una power unit
# a ibrido spinto la costruisce chi ha gente che sa di batterie e di software.
# Sono mestieri diversi e quasi nessuna squadra li ha tutti e due.
COMPETENZE = ("termico", "elettrico", "integrazione")
COMP_BASE = {"termico": 0.35, "elettrico": 0.40, "integrazione": 0.25}
# quanto puo' fare da sola una squadra che il motore lo compra: puo' preparare
# la vettura attorno alla power unit nuova, non la power unit
QUOTA_CLIENTE = 0.45


def competenze(gs, team) -> dict:
    """Quanto vale questa squadra nei tre mestieri che servono, da 0 a 100.

    Il termico e' il reparto motori e la fabbrica. L'elettrico e' la stessa
    gente piu' il simulatore e l'ufficio tecnico, perche' li' si lavora di
    elettronica e di software. L'integrazione e' far stare tutto dentro una
    macchina, ed e' il mestiere di chi disegna il telaio.
    """
    quota = 1.0 if team.works else QUOTA_CLIENTE
    pu = team.pu_strength
    fac = getattr(team, "facilities", {}) or {}
    sim = float(fac.get("simulator", 60.0))
    uff = float(fac.get("design_office", 60.0))
    fab = float(fac.get("factory", 60.0))
    return {
        "termico": (0.65 * pu + 0.35 * fab) * quota,
        "elettrico": (0.45 * pu + 0.35 * sim + 0.20 * uff) * quota,
        "integrazione": team.mech_strength,
    }


# E poi c'e' quello che si e' gia' fatto. Chi costruisce power unit ibride da
# dieci anni ha in casa gente che sa di batterie; chi ha passato l'ultimo ciclo
# a scommettere su un dieci cilindri ha imparato un altro mestiere. L'esperienza
# non si compra in un anno, e conta quanto la fabbrica.
ESPERIENZA_CORRENTE = 0.70     # quanto insegna correre con l'architettura di adesso
ESPERIENZA_CLIENTE = 0.22      # a chi il motore lo compra insegna molto meno
ESPERIENZA_PESO = 0.75         # e quanto sposta, alla fine, sull'attrezzatura
ESPERIENZA_MJ = 0.010          # quanta se ne accumula per milione speso in programma


def famiglia(gs, aid: str) -> tuple:
    """Quanto un'architettura e' termica e quanto e' elettrica, da 0 a 1."""
    pesi = scheda(gs, aid).get("competenze") or COMP_BASE
    t, e = float(pesi.get("termico", 0.0)), float(pesi.get("elettrico", 0.0))
    tot = t + e
    return (t / tot, e / tot) if tot > 1e-6 else (0.5, 0.5)


def esperienza(gs, team) -> dict:
    """Che mestiere ha in casa questa squadra, oggi.

    Un pezzo arriva dall'architettura con cui si corre - la si costruisce o la
    si monta da anni - e un pezzo da quello che si e' speso nei programmi sulle
    architetture future, anche quelli finiti male.
    """
    t, e = famiglia(gs, corrente(gs))
    quota = ESPERIENZA_CORRENTE if team.works else ESPERIENZA_CLIENTE
    avuta = getattr(team, "arch_exp", None) or {}
    return {"termico": t * quota + float(avuta.get("termico", 0.0)),
            "elettrico": e * quota + float(avuta.get("elettrico", 0.0))}


def attrezzatura(gs, team, aid: str) -> float:
    """Quanto questa squadra e' attrezzata per questa architettura.

    Uno intorno a uno vuol dire "come la media della griglia". Sotto lo 0.8 la
    scommessa si puo' anche vincere, ma il lavoro fatto rende meno di quello di
    chi ha gli strumenti giusti - e gli strumenti sono tre cose: gli ingegneri,
    la fabbrica, e il mestiere che si e' gia' in casa.
    """
    pesi = scheda(gs, aid).get("competenze") or COMP_BASE
    mie = competenze(gs, team)
    val = sum(pesi.get(k, 0.0) * mie.get(k, 60.0) for k in COMPETENZE)
    riferimento = 68.0        # una squadra di meta' griglia
    base = val / riferimento
    # e il mestiere che si ha gia': quanto di quello che serve qui lo si e'
    # gia' fatto, contro la mezza misura di chi non ha mai lavorato ne' di
    # termico ne' di elettrico
    t, e = famiglia(gs, aid)
    esp = esperienza(gs, team)
    mio = t * esp["termico"] + e * esp["elettrico"]
    base *= 1.0 + ESPERIENZA_PESO * (mio - 0.30)
    return round(max(0.30, min(1.65, base)), 3)


def impara(team, gs, aid: str, milioni: float) -> None:
    """Un milione speso su un'architettura e' anche un milione di mestiere."""
    if milioni <= 0:
        return
    t, e = famiglia(gs, aid)
    exp = getattr(team, "arch_exp", None) or {"termico": 0.0, "elettrico": 0.0}
    exp["termico"] = round(float(exp.get("termico", 0.0)) + t * milioni * ESPERIENZA_MJ, 4)
    exp["elettrico"] = round(float(exp.get("elettrico", 0.0)) + e * milioni * ESPERIENZA_MJ, 4)
    team.arch_exp = exp


def mestiere_forte(gs, aid: str) -> str:
    """Che mestiere chiede soprattutto questa architettura."""
    pesi = scheda(gs, aid).get("competenze") or COMP_BASE
    k = max(pesi, key=pesi.get)
    return {"termico": "reparto termico e fabbrica",
            "elettrico": "elettronica, batterie e simulatore",
            "integrazione": "telaio e integrazione"}.get(k, k)


# --------------------------------------------------------- chi vuole cosa
# Al tavolo nessuno chiede l'architettura migliore in assoluto: si chiede
# quella che conviene a se stessi. Chi ha speso una fortuna in ibrido non
# vuole buttarla, chi non ce l'ha vuole ripartire da zero, la FOM vuole il
# rumore e la federazione vuole spendere meno.
def preferenza_squadra(gs, team) -> dict:
    """Quanto ogni architettura piace a questa scuderia, da 0 a 1."""
    cat = catalogo(gs)
    if not cat:
        return {}
    attuale = corrente(gs)
    eng = gs.engine_makers.get(team.engine, {})
    tutte = [m.get("power", 85) for m in gs.engine_makers.values()] or [85]
    forza_pu = ((eng.get("power", 85) - min(tutte))
                / max(1e-6, max(tutte) - min(tutte)))
    ricca = max(0.0, min(1.0, (team.budget_base - 130.0) / 120.0))
    out = {}
    for aid, a in cat.items():
        v = 0.5
        if aid == attuale:
            # chi ha la power unit migliore vuole tenersela, chi ce l'ha
            # scarsa non vede l'ora di cambiare
            v += 0.55 * (forza_pu - 0.45) * (1.3 if team.works else 0.7)
        else:
            v += 0.35 * (0.45 - forza_pu)
            # ricominciare da zero costa, e non tutti se lo possono permettere
            v += 0.30 * (float(a.get("costo", 1.0)) - 0.8) * (ricca - 0.5) * 2.0
        # una squadra cliente guarda soprattutto al conto
        if not team.works:
            v += 0.25 * (1.0 - float(a.get("costo", 1.0)))
        # e chi e' gia' attrezzato per una certa strada la chiede piu' volentieri:
        # nessuno vota per un regolamento che lo obbliga a ricominciare da zero
        v += 0.30 * (attrezzatura(gs, team, aid) - 1.0)
        # e poi c'e' dove sta andando il mondo: un costruttore che vende auto
        # elettriche non porta al tavolo la stessa richiesta di vent'anni fa
        # la rarita' dice quanto e' un'idea da tavolo, e la direzione del mondo
        # la scavalca: e' l'unico modo in cui una cosa impensabile diventa
        # prima discutibile e poi ovvia
        v = v * float(a.get("rarita", 1.0)) + TREND_SQUADRA * trend_elettrico(gs) * spinta_elettrica(a)
        out[aid] = max(0.02, min(1.2, v))
    return out


# Quanto la federazione spinge verso l'elettrico. Non e' una posizione fissa:
# cresce di ciclo in ciclo, come nel mondo vero, e sposta il tavolo verso le
# architetture in cui l'elettrico conta di piu'. Non e' la scommessa di una
# squadra: e' vent'anni di direzione, e si vede solo su quella scala.
TREND_PASSO = 0.15      # quanto cresce a ogni ciclo firmato
TREND_PESO = 1.9        # quanto pesa sulla federazione
TREND_SQUADRA = 0.62    # e quanto sulle squadre


def trend_elettrico(gs) -> float:
    return float(gs.regulations.get("trend_elettrico", 0.0) or 0.0)


def spinta_elettrica(a: dict) -> float:
    """Quanto un'architettura e' *piu'* elettrica di quella che si corre oggi.

    Non conta la quota in se': conta di quanto si sposta in avanti. Un V6 come
    quello del 2026 non e' un passo verso l'elettrico, e' l'elettrico che c'e'
    gia'; un ibrido spinto con seicento kilowatt di motore lo e'.
    """
    quota = float(a.get("quota_elettrica", 0.0))
    return max(0.0, min(1.0, (quota - 0.45) / 0.45))


def avanza_trend(gs) -> None:
    """Un ciclo in piu' alle spalle: la spinta verso l'elettrico cresce."""
    gs.regulations["trend_elettrico"] = round(
        min(1.0, trend_elettrico(gs) + TREND_PASSO), 3)


def preferenza_istituzioni(gs) -> list:
    """Cosa vogliono la federazione e il promotore, e quanto pesano.

    La federazione guarda ai costi e alla direzione tecnica del momento; il
    promotore guarda a che spettacolo viene fuori, e su questo non ha mai
    cambiato idea.
    """
    cat = catalogo(gs)
    trend = trend_elettrico(gs)
    fia = {}
    for aid, a in cat.items():
        # due cose in una: quanto costa - e li' la federazione taglia sempre -
        # e quanto va nella direzione in cui il mondo si sta muovendo. La
        # seconda si somma, non moltiplica, se no un'architettura cara resta
        # fuori per sempre per quanto sia il futuro
        v = max(0.05, 1.15 - float(a.get("costo", 1.0))) * float(a.get("rarita", 1.0))
        v += TREND_PESO * trend * spinta_elettrica(a)
        fia[aid] = max(0.03, v)
    fom = {aid: max(0.03, float(a.get("spettacolo", 0.5)) * float(a.get("rarita", 1.0)))
           for aid, a in cat.items()}
    return [(fia, 3.4, "FIA"), (fom, 2.8, "FOM")]

