"""Sviluppo della vettura: affinamenti, pacchetti di aggiornamento, ATR.

Due cose diverse, che in Formula 1 non vanno confuse. Il lavoro continuo di
reparto - dati, messa a punto, piccoli affinamenti - non sposta quasi niente
sul potenziale della macchina: serve a capirla e a sfruttarla meglio, cioe' a
partire ogni weekend piu' vicino alla finestra giusta. Il salto vero lo fanno
i pacchetti di aggiornamento, che si progettano, si pagano e si portano in
pista una volta sola.

E un pacchetto puo' non funzionare. Succede spesso, e non a caso: dipende da
chi lo ha disegnato, dagli strumenti con cui e' stato validato e da quanto la
galleria del vento dice la verita'. Chi ha reparto e fabbrica di prim'ordine
porta in pista quello che aveva promesso; chi non li ha scopre in pista che il
fondo nuovo non funziona, e rimonta quello vecchio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C
from . import economy

# Il livello delle monoposto non ha un tetto. Averlo a 100 significava che
# prima o poi tutti ci arrivavano e la griglia si appiattiva contro un muro:
# in sedici stagioni un pezzo su tre stava sopra 97 e le prime quattro squadre
# erano indistinguibili. Il numero e' libero di crescere, e a rallentarlo non
# e' un limite ma la difficolta': dentro un ciclo tecnico i primi punti si
# trovano, gli ultimi si strappano.
#
# Il riferimento del ciclo (`cycle_base`) e' il livello a cui sta la griglia
# quando un regolamento e' nuovo. Da li' si misura quanto e' difficile
# guadagnare ancora, e a ogni cambio di regolamento il conto si rifa' piu' in
# basso: la macchina nuova e' peggiore di quella vecchia perfezionata, come
# nella realta'.
CYCLE_SPAN = 18.0    # punti oltre il riferimento prima che diventi durissima
CYCLE_STEP = 2.2     # di quanto sale il riferimento a ogni nuovo ciclo
CYCLE_DEFAULT = 82.0


def cycle_base(gs) -> float:
    return float(gs.regulations.get("cycle_base", CYCLE_DEFAULT))


def yield_factor(gs, perf: float) -> float:
    """Quanto rende ancora lo sviluppo a questo livello, come moltiplicatore.

    Sopra il riferimento del ciclo ogni punto costa piu' del precedente, e non
    si arriva mai a zero: si arriva a rendimenti cosi' bassi che conviene
    spendere altrove. Sotto il riferimento invece si va piu' in fretta, perche'
    i problemi grossi sono ancora tutti li' da risolvere: e' il motivo per cui
    una squadra di coda recupera piu' in fretta di quanto una di testa scappi.
    """
    over = (perf - cycle_base(gs)) / CYCLE_SPAN
    if over <= 0.0:
        return 1.0 + min(0.35, -over * 0.45)
    return 1.0 / (1.0 + over ** 2.2 * 1.8)


def reference_level(gs) -> float:
    """Livello attorno a cui si legge la griglia: serve alle schermate."""
    return cycle_base(gs) + CYCLE_SPAN

# Quanto rende, in prestazione pura, il lavoro continuo di reparto. Basso di
# proposito: gli affinamenti esistono, ma non sono aggiornamenti.
REFINE_YIELD = 0.22

# Il resto di quel lavoro diventa conoscenza della vettura: si scopre come
# farla funzionare, e questo si vede nell'assetto, non nella scheda tecnica.
UNDERSTANDING_RATE = 0.020     # per milione speso, a reparto pieno
UNDERSTANDING_CARRY = 0.35     # quanto ne resta l'anno dopo, con una macchina nuova

# Quanto invecchia la vettura in una stagione se non ci si investe. Tarato su
# quello che rende lo sviluppo: con circa 1,6 M$ a gara si sta in pari, sotto
# si arretra, sopra si guadagna. Una monoposto ferma non resta competitiva.
TECH_DECAY = 0.45


@dataclass
class Project:
    part: str
    label: str
    invested: float          # M$ gia' spesi
    budget: float            # M$ totali previsti
    races_left: int
    expected: float          # guadagno atteso in punti prestazione
    confidence: float = 0.5  # 0..1 quanto il reparto se la sente
    size: str = "medio"
    started_round: int = 0

    @property
    def progress(self) -> float:
        return 0.0 if self.budget <= 0 else min(1.0, self.invested / self.budget)


@dataclass
class Trial:
    """Una specifica in verifica: e' in macchina, ma non ha convinto.

    In Formula 1 un aggiornamento sbagliato non si scopre in fabbrica: si
    scopre in pista, quando i cronometri dicono un'altra cosa rispetto alla
    galleria. A quel punto ci sono due strade, e nessuna delle due e' gratis.
    Si rimonta la specifica vecchia - i pezzi ci sono ancora, ma vanno rifatti
    e rimontati, e il pacchetto pagato e' buttato - oppure la si tiene e ci si
    lavora sopra, sperando che il problema sia capirla e non lei.
    """
    part: str
    label: str
    old_perf: float          # la specifica ferma in garage
    expected: float          # quanto prometteva sulla carta
    size: str
    races: int = 0           # gare passate con questa specifica addosso
    cost: float = 0.0        # quanto e' costato il pacchetto
    state: str = "in prova"  # in prova | affinamento
    news: str = ""           # l'ultima cosa che hanno detto gli ingegneri
    gain: float = 0.0        # quanto ha portato davvero, misurato in pista
    new_perf: float = 0.0    # quanto vale la specifica nuova, montata
    carattere: float = 0.0   # -1 macchina piu' piantata, +1 piu' nervosa
    band: str = ""           # come e' uscita: fallito, sottotono, in linea, oltre


def next_era(gs):
    """Il prossimo ciclo tecnico.

    Oltre l'ultimo ciclo scritto nei dati la carriera continua, quindi i cicli
    successivi vengono immaginati: cadenza e natura seguono il ritmo storico,
    dove a una rivoluzione della power unit segue di solito un periodo di
    motori congelati in cui a decidere e' l'aerodinamica.
    """
    ciclo = gs.regulations.get("pending_cycle")
    if ciclo and ciclo.get("season"):
        from . import rules
        return {"from": ciclo["season"], "to": ciclo["season"] + 5,
                "label": "Ciclo in preparazione", "focus": rules.cycle_focus(gs),
                "reset_strength": min(0.95, 0.35 + 0.45 * ciclo["pressure"]),
                "in_discussione": True}
    eras = gs.history_data.setdefault("eras", [])
    for era in eras:
        if era["from"] > gs.season:
            return era
    return None


def seasons_to_reset(gs):
    era = next_era(gs)
    return None if era is None else era["from"] - gs.season


def prep_conversion(gs, team, era: dict) -> float:
    """Quanto rende un milione speso sul regolamento che verra'.

    Non tutti i reset premiano le stesse cose. Nel 2014 contava la power unit
    e chi non ce l'aveva ha inseguito per anni; nel 2022 i motori erano
    congelati e l'unica leva era il concetto aerodinamico. Una squadra forte
    nell'area giusta converte molto meglio le stesse risorse.
    """
    focus = era.get("focus") or {"pu": 0.34, "chassis": 0.33, "aero": 0.33}
    pu = team.pu_strength if team.works else 55.0
    val = (focus.get("aero", 0.0) * team.aero_strength
           + focus.get("chassis", 0.0) * team.mech_strength
           + focus.get("pu", 0.0) * pu)
    return val / 100.0


def atr_factor(gs, team) -> float:
    """Ore di galleria del vento consentite in base alla classifica dell'anno prima."""
    scale = gs.regulations["aero_testing_restriction"]["scale"]
    idx = max(0, min(len(scale) - 1, team.last_position - 1))
    base = scale[idx] / 100.0
    slope = float(gs.regulations.get("atr_slope", 1.0))
    return 1.0 + (base - 1.0) * slope


def dev_capacity(gs, team) -> float:
    """Punti prestazione teorici che il team puo' produrre in un weekend."""
    core = team.dev_rate * (0.55 + 0.45 * atr_factor(gs, team))
    people = 0.5 * team.aero_strength + 0.5 * team.mech_strength
    return core * (people / 100.0) * 1.05


# Quante persone del reparto lavorano a un pacchetto, e per quante gare. Un
# aggiornamento non e' una fattura: e' un gruppo di gente che per settimane
# disegna, prova in galleria, fa i pezzi e li monta. E' li' che va il grosso
# del tetto di spesa.
PEOPLE = {"piccolo": 10, "medio": 26, "grande": 52}
MATERIALS = {"piccolo": 1.0, "medio": 2.2, "grande": 3.6}
RACES_OF = {"piccolo": 1, "medio": 3, "grande": 6}


def people_needed(size: str) -> int:
    return PEOPLE[size]


def people_busy(team) -> int:
    """Quante persone sono gia' impegnate sui pacchetti aperti."""
    return sum(PEOPLE.get(pr.size, 0) for pr in team.dev_projects)


def cost_breakdown(gs, team, part: str, size: str) -> dict:
    """Da cosa e' fatto il costo di un pacchetto.

    Il lavoro sono le persone dedicate per il tempo che ci mettono; i materiali
    sono galleria, stampi, fibra e pezzi. Chi ha un reparto grande paga di piu'
    le stesse ore, ma le fa meglio - ed e' il motivo per cui l'organico si vede
    due volte: qui nel conto e nella fiducia del pacchetto.
    """
    from . import departments
    mix = _mix(part)
    # il reparto che ci mette le persone dipende da cosa si sta rifacendo
    quota = {"aero": mix["aero"], "progetto": mix["mech"], "powertrain": mix["pu"]}
    costo_testa = sum(departments.REPARTI[a]["cost"] * q for a, q in quota.items())
    n = people_needed(size)
    gare = RACES_OF[size]
    lavoro = n * costo_testa * (gare / max(1, len(gs.tracks)))
    materiali = C.CAR_PARTS[part]["cost"] * MATERIALS[size]
    return {"persone": n, "gare": gare,
            "lavoro": round(lavoro, 2), "materiali": round(materiali, 2),
            "totale": round(lavoro + materiali, 2)}


def cost_of_upgrade(gs, team, part: str, size: str) -> float:
    return cost_breakdown(gs, team, part, size)["totale"]


def dept_people(team, part: str) -> int:
    """Quante persone puo' mettere il reparto su un pezzo del genere."""
    from . import departments
    mix = _mix(part)
    return int(sum(departments.headcount(team, a) * q for a, q in
                   (("aero", mix["aero"]), ("progetto", mix["mech"]),
                    ("powertrain", mix["pu"]))))


def free_people(team, part: str) -> int:
    return max(0, dept_people(team, part) - people_busy(team))


def expected_gain(gs, team, part: str, size: str) -> float:
    """Quanto promette il pacchetto sulla carta. Poi la pista dira'."""
    mult = {"piccolo": 1.0, "medio": 2.4, "grande": 4.8}[size]
    p = C.CAR_PARTS[part]
    dept = (p["aero"] * team.aero_strength + p["mech"] * team.mech_strength
            + p["pu"] * (team.pu_strength if team.works else 55.0))
    dept /= max(0.1, p["aero"] + p["mech"] + p["pu"])
    cur = team.car.parts[part].perf
    # 0.93 tiene i guadagni sulla stessa scala di prima a meta' ciclo: cambia
    # la forma della curva, non il ritmo con cui cresce una macchina
    return round(mult * (dept / 100.0) * team.dev_rate * yield_factor(gs, cur) * 0.93, 2)


# --------------------------------------------------- funzionera' o no?
# Le bande di esito di un pacchetto, dalla piu' brutta alla migliore. La
# forbice del "fallito" comincia sotto zero: un aggiornamento che non correla
# peggiora la macchina finche' non si torna alla specifica vecchia.
BANDS = {
    "fallito":   (-0.30, 0.15),
    "sottotono": (0.35, 0.70),
    "in linea":  (0.85, 1.15),
    "oltre":     (1.25, 1.65),
}

# Con quali strumenti si valida ogni tipo di lavoro.
TOOLS = {
    "aero": (("windtunnel", 0.45), ("cfd", 0.32), ("aero_dept", 0.23)),
    "mech": (("design_office", 0.45), ("factory", 0.33), ("simulator", 0.22)),
    "pu":   (("factory", 0.60), ("design_office", 0.40)),
}


def _mix(part: str) -> dict:
    """Quanto quel componente e' aerodinamica, meccanica e power unit."""
    p = C.CAR_PARTS[part]
    tot = max(0.1, p["aero"] + p["mech"] + p["pu"])
    return {k: p[k] / tot for k in ("aero", "mech", "pu")}


def _n(v: float) -> float:
    """Porta un valore di reparto (45..95) sulla scala 0..1."""
    return max(0.0, min(1.0, (v - 45.0) / 50.0))


def _tool_score(team, mix: dict) -> float:
    """Gli strumenti con cui si valida, pesati per il tipo di componente.

    Il livello conta, ma anche l'eta': una galleria vecchia continua a dare
    numeri, solo che sono numeri di dieci anni fa.
    """
    from . import facilities
    tot = 0.0
    for area, share in mix.items():
        if share <= 0:
            continue
        val = 0.0
        for key, w in TOOLS[area]:
            lvl = float(team.facilities.get(key, 60.0))
            vecchia = max(0.0, facilities.age_of(team, key) - facilities.GRACE_SEASONS)
            val += w * lvl * (1.0 - min(0.18, 0.022 * vecchia))
        tot += share * val
    return tot


def project_confidence(gs, team, part: str, size: str) -> float:
    """Da 0 a 1: quanta fiducia il reparto puo' avere in questo pacchetto.

    Ci stanno dentro le persone, gli strumenti, le ore di galleria concesse dal
    regolamento, i chilometri di correlazione fatti in test e quanto la squadra
    ha capito la macchina di quest'anno. Un pacchetto grande e' piu' difficile
    di uno piccolo: si cambia di piu' e si sa di meno.
    """
    mix = _mix(part)
    reparti = (mix["aero"] * team.aero_strength + mix["mech"] * team.mech_strength
               + mix["pu"] * (team.pu_strength if team.works else 55.0))
    td = team._s("technical_director", "development")
    atr = max(0.0, min(1.0, (atr_factor(gs, team) - 0.60) / 0.65))
    c = (0.42 * _n(reparti) + 0.28 * _n(_tool_score(team, mix))
         + 0.16 * _n(td) + 0.14 * atr)
    c += 0.22 * max(0.0, min(1.0, team.correlation))
    c += 0.10 * max(0.0, min(1.0, team.car_understanding))
    c -= {"piccolo": 0.0, "medio": 0.06, "grande": 0.14}[size]
    return max(0.03, min(0.97, c))


def outcome_odds(conf: float, size: str) -> dict:
    """Con che probabilita' esce ognuna delle quattro bande."""
    fallito = {"piccolo": 0.10, "medio": 0.16, "grande": 0.26}[size] * (1.75 - 1.55 * conf)
    oltre = max(0.02, 0.44 * conf - 0.10)
    sotto = 0.36 * (1.25 - 0.65 * conf)
    linea = max(0.05, 1.0 - fallito - oltre - sotto)
    tot = fallito + sotto + linea + oltre
    return {"fallito": fallito / tot, "sottotono": sotto / tot,
            "in linea": linea / tot, "oltre": oltre / tot}


def roll_outcome(gs, odds: dict) -> str:
    r = gs.rng.random()
    acc = 0.0
    for band in ("fallito", "sottotono", "in linea", "oltre"):
        acc += odds[band]
        if r < acc:
            return band
    return "in linea"


def weakest_link(gs, team, part: str) -> str:
    """Cosa ci ha traditi, detto come lo direbbe un ingegnere."""
    mix = _mix(part)
    voci = [
        (_n(_tool_score(team, mix)),
         "la galleria e i modelli ci hanno raccontato una macchina che non esiste"),
        (0.30 + 0.70 * max(0.0, min(1.0, team.correlation)),
         "senza chilometri di correlazione si sviluppa alla cieca"),
        (_n(mix["aero"] * team.aero_strength + mix["mech"] * team.mech_strength
            + mix["pu"] * (team.pu_strength if team.works else 55.0)),
         "il reparto non era attrezzato per un salto del genere"),
        (max(0.0, min(1.0, (atr_factor(gs, team) - 0.60) / 0.65)),
         "con le ore di galleria che abbiamo non c'e' modo di validare tutto"),
        (0.30 + 0.70 * max(0.0, min(1.0, team.car_understanding)),
         "di questa macchina sappiamo ancora troppo poco"),
    ]
    return min(voci, key=lambda v: v[0])[1]



RACES_OF = {"piccolo": 1, "medio": 3, "grande": 6}

# Quanto un pacchetto rimette in discussione il lavoro d'assetto. Un fondo
# nuovo non e' un pezzo in piu' sulla stessa macchina: e' un'altra macchina, e
# quello che si sapeva su come farla funzionare vale meno di prima. Piu' grande
# e' il pacchetto, piu' c'e' da ritrovare.
UPSET = {"piccolo": 0.10, "medio": 0.26, "grande": 0.45}


def setup_upset(team, size: str) -> float:
    """Quota di conoscenza che il pacchetto manda in fumo, da 0 a 1.

    Chi ha simulatore e pista di proprieta' ritrova la finestra molto prima:
    e' li' che si fa il lavoro che altrimenti tocca fare il venerdi'.
    """
    sim = float(team.facilities.get("simulator", 60.0)) / 100.0
    pista = float(team.facilities.get("private_track", 0.0)) / 100.0
    return max(0.02, UPSET[size] * (1.15 - 0.30 * sim - 0.25 * pista))


def _unsettle(team, quota: float) -> None:
    """Sposta indietro conoscenza della vettura e dei circuiti."""
    team.car_understanding = max(0.0, team.car_understanding * (1.0 - quota))
    if team.setup_knowledge:
        team.setup_knowledge = {k: v * (1.0 - quota * 0.8)
                                for k, v in team.setup_knowledge.items()}


def start_project(gs, team, part: str, size: str) -> tuple:
    """Apre un pacchetto. Non si paga tutto subito: si paga gara per gara."""
    from . import departments
    cost = cost_of_upgrade(gs, team, part, size)
    races = RACES_OF[size]
    aperti = len(team.dev_projects) + sum(1 for t in team.spec_trials
                                          if t.state == "affinamento")
    if aperti >= 3:
        return False, ("Il reparto e' saturo: fra progetti aperti e specifiche da "
                       "capire non c'e' un banco libero.")
    # le persone non si sdoppiano: quelle su un pacchetto non stanno su un altro
    liberi = free_people(team, part)
    if people_needed(size) > liberi:
        return False, (f"Servono {people_needed(size)} persone e il reparto ne ha "
                       f"{liberi} libere: o si assume, o si chiude un cantiere.")
    if team.cash < cost / races:
        return False, "Non c'e' liquidita' nemmeno per la prima tranche."
    if team.spent + cost > economy.cap_limit(gs):
        return False, "Il pacchetto intero non ci sta dentro il tetto di spesa."
    pr = Project(part=part, label=f"{C.CAR_PARTS[part]['label']} - pacchetto {size}",
                 invested=0.0, budget=cost, races_left=races,
                 expected=expected_gain(gs, team, part, size),
                 confidence=project_confidence(gs, team, part, size),
                 size=size, started_round=gs.round)
    team.dev_projects.append(pr)
    return True, (f"Progetto avviato: {pr.label} (+{pr.expected:.1f} attesi in {races} gare, "
                  f"fiducia del reparto {pr.confidence*100:.0f}%).")


def deliver(gs, team, pr: Project) -> list:
    """Porta il pacchetto in pista e vede cosa succede davvero.

    L'esito non e' una monetina: e' la banda che esce dalla fiducia del
    reparto, e la fiducia dipende da chi ha disegnato il pezzo, con che
    strumenti l'ha validato e quanto quegli strumenti dicono la verita'.
    """
    part = team.car.parts[pr.part]
    nome = C.CAR_PARTS[pr.part]["label"]
    band = roll_outcome(gs, outcome_odds(pr.confidence, pr.size))
    lo, hi = BANDS[band]
    gain = pr.expected * gs.rng.uniform(lo, hi)
    # se in fabbrica c'e' gia' una specifica piu' avanti di quella in garage, il
    # pacchetto nuovo parte da li': il reparto non ridisegna due volte lo stesso
    # pezzo partendo da capo
    from . import kits
    prima = kits.best_perf(team, pr.part)
    nuova = max(40.0, prima + gain)
    team.upgrades_done += 1
    # dalla fabbrica non escono due esemplari: ne esce uno, e su quale macchina
    # va lo decide il muretto. Finche' non c'e' il secondo, le due monoposto
    # sono diverse
    kit = kits.add(gs, team, pr.part, nuova, prima, pr.size, pr.budget)
    if not team.is_player or team.auto_dev:
        kits.ai_fit(gs, team)
    # ogni pacchetto ha un suo carattere: c'e' quello che pianta la macchina e
    # quello che la fa girare di piu'. Non e' un dettaglio - decide a quale dei
    # due piloti sta bene
    carattere = round(_carattere(gs, pr.part), 2)
    team.car.balance = max(-1.0, min(1.0, team.car.balance + carattere * 0.35))
    log_upgrade(gs, team, pr, band, prima, nuova)
    # anche quando funziona, l'assetto va ritrovato: la macchina non e' piu'
    # quella su cui si erano presi i riferimenti
    quota = setup_upset(team, pr.size)
    _unsettle(team, quota)
    # ogni specifica nuova passa dalla verifica: quanto ha portato lo dicono i
    # cronometri, non la galleria, e finche' non ha girato non si sa
    team.spec_trials.append(Trial(
        part=pr.part, label=nome, old_perf=prima, expected=pr.expected,
        size=pr.size, cost=pr.budget, gain=round(gain, 2),
        carattere=carattere, band=band, new_perf=round(nuova, 2)))
    if not team.is_player:
        return []
    assetto = (" Ci vorranno un paio di sessioni per ritrovare la finestra "
               "d'assetto." if quota > 0.18 else "")
    quanti = "due esemplari" if kit.ready >= 2 else "un esemplare solo"
    return [f"{nome}: specifica nuova pronta, in fabbrica c'e' {quanti}. In "
            f"galleria prometteva +{pr.expected:.1f}: si monta dalla pagina "
            f"della vettura, il verdetto arriva dopo che ha girato.{assetto}"]


# Da cosa dipende il carattere di un pacchetto: rifare l'ala anteriore o il
# fondo davanti fa girare la macchina, lavorare dietro la pianta.
CARATTERE_BASE = {
    "front_wing": 0.55, "floor": 0.20, "active_aero": 0.15, "brakes": 0.25,
    "rear_wing": -0.45, "suspension": -0.10, "chassis": 0.0, "gearbox": -0.15,
    "sidepods": 0.05, "cooling": 0.0,
}


def _carattere(gs, part: str) -> float:
    base = CARATTERE_BASE.get(part, 0.0)
    return max(-1.0, min(1.0, base + gs.rng.gauss(0.0, 0.28)))


def driver_verdict(gs, team, tr: Trial, driver) -> tuple:
    """Cosa ne pensa un pilota della specifica nuova. Ritorna (indice, frase).

    L'indice va da -1 a +1: e' l'incontro fra come e' fatto il pacchetto e come
    guida lui. Una macchina che gira di piu' e' un regalo per chi stacca tardi
    e un problema per chi ha bisogno di sentirla piantata.
    """
    from . import driving
    attacco = driving.traits(driver)["attacco"]
    idx = max(-1.0, min(1.0, tr.carattere * (0.35 + 0.85 * attacco)))
    if idx > 0.35:
        frase = "ci si trova subito, dice che la macchina fa quello che le chiede"
    elif idx > 0.12:
        frase = "gli piace, anche se deve rifare un po' di riferimenti"
    elif idx > -0.12:
        frase = "non cambia niente per lui"
    elif idx > -0.35:
        frase = "fatica a fidarsi, chiede di rimetterla come prima dietro"
    else:
        frase = "non riesce a guidarla, dice che gli scappa via"
    return round(idx, 2), frase


def log_upgrade(gs, team, pr, band: str, prima: float, dopo: float) -> None:
    """Scrive nel registro cosa e' stato portato in pista e come e' andata.

    Il numero di aggiornamenti fatti non dice niente: quello che conta e' se
    quello che il reparto prometteva si e' visto in pista. Qui restano
    entrambi, promessa e risultato, gara per gara.
    """
    team.upgrade_log.append({
        "stagione": gs.season,
        "gara": gs.round + 1,
        "gp": (gs.tracks[gs.round].gp if 0 <= gs.round < len(gs.tracks) else ""),
        "part": pr.part,
        "label": C.CAR_PARTS[pr.part]["label"],
        "size": pr.size,
        "costo": round(float(pr.budget), 2),
        "atteso": round(float(pr.expected), 2),
        "reso": round(float(dopo - prima), 2),
        "prima": round(float(prima), 2),
        "dopo": round(float(dopo), 2),
        "esito": band,
        "stato": "in verifica" if band == "fallito" else "chiuso",
    })
    if len(team.upgrade_log) > 120:
        del team.upgrade_log[:-120]


def _log_ultimo(team, part: str):
    """L'ultima riga di registro che riguarda un componente ancora in verifica."""
    for voce in reversed(team.upgrade_log):
        if voce.get("part") == part and voce.get("stato") == "in verifica":
            return voce
    return None


def _chiudi_log(team, tr, esito: str) -> None:
    """Aggiorna il registro quando una specifica dubbia trova una fine."""
    voce = _log_ultimo(team, tr.part)
    if voce is None:
        return
    voce["stato"] = "chiuso"
    voce["esito"] = esito
    voce["dopo"] = round(float(team.car.parts[tr.part].perf), 2)
    voce["reso"] = round(voce["dopo"] - float(voce.get("prima", 0.0)), 2)


# ------------------------------------------------- specifiche che non vanno
# Quante gare gli ingegneri restano dietro a una specifica che non convince
# prima di dire che non ne vengono a capo.
TRIAL_RACES = 4
# Rifare e rimontare la specifica vecchia: i disegni ci sono, i pezzi no.
REVERT_SHARE = 0.20
# Da un pacchetto nato male non si tira fuori tutto quello che prometteva:
# al massimo si recupera il buco e un po' di quello che c'era sotto, e solo
# se il reparto ha gli strumenti per capirlo davvero.
TRIAL_TARGET = 0.55
# Insistere non e' gratis: ogni gara di lavoro sopra una specifica dubbia si
# paga, e nel frattempo quel banco non progetta nient'altro.
TRIAL_UPKEEP = 0.06


def deficit(team, tr: Trial) -> float:
    """Quanto si sta perdendo adesso rispetto alla specifica in garage."""
    attuale = tr.new_perf if tr.new_perf else team.car.parts[tr.part].perf
    return round(attuale - tr.old_perf, 2)


def revert_spec(gs, team, tr: Trial) -> tuple:
    """Rimonta la specifica vecchia. Si recupera la macchina, non i soldi."""
    if tr not in team.spec_trials:
        return False, "Questa specifica non e' piu' in verifica."
    prezzo = round(tr.cost * REVERT_SHARE, 2)
    ok, why = economy.can_afford(team, prezzo, gs)
    if not ok:
        return False, why
    perso = deficit(team, tr)
    team.add_expense(f"Ritorno alla specifica precedente: {tr.label}", prezzo,
                     in_cap=True, category="sviluppo")
    from . import kits
    team.car.parts[tr.part].perf = tr.old_perf
    for k in list(team.kits or []):
        if k.part == tr.part:
            for d in list(k.fitted):
                kits.deltas(team, d).pop(k.part, None)
            team.kits.remove(k)
    # si torna indietro, ma la macchina cambia di nuovo: l'assetto ne risente
    _unsettle(team, setup_upset(team, tr.size) * 0.5)
    _chiudi_log(team, tr, "rimontata la vecchia")
    team.spec_trials.remove(tr)
    return True, (f"{tr.label}: rimontata la specifica precedente per {prezzo:.2f} M$. "
                  f"Recuperati {abs(perso):.1f} punti, persi i {tr.cost:.1f} M$ del "
                  f"pacchetto.")


def keep_spec(gs, team, tr: Trial) -> tuple:
    """Tiene la specifica nuova e ci mette il reparto sopra."""
    if tr not in team.spec_trials:
        return False, "Questa specifica non e' piu' in verifica."
    tr.state = "affinamento"
    tr.news = "il reparto ci lavora sopra"
    return True, (f"{tr.label}: la teniamo. Il reparto ha {TRIAL_RACES} gare per "
                  f"venirne a capo.")


def trial_ceiling(gs, team, tr: Trial) -> float:
    """Il massimo che si puo' tirare fuori da questa specifica.

    Non e' quello che prometteva: dipende da quanto il reparto e' in grado di
    capire perche' non funziona. Chi ha gli strumenti che dicono il vero ci
    arriva vicino, chi non li ha resta sotto la specifica vecchia comunque.
    """
    conf = project_confidence(gs, team, tr.part, tr.size)
    return tr.old_perf + tr.expected * TRIAL_TARGET * (0.25 + 0.75 * conf)


def _trial_step(gs, team, tr: Trial) -> str:
    """Una gara di lavoro su una specifica tenuta. Ritorna cosa e' successo."""
    part = team.car.parts[tr.part]
    # il banco che ci lavora si paga, che poi ne venga fuori qualcosa o no
    quota = round(tr.cost * TRIAL_UPKEEP, 3)
    if quota > 0:
        team.add_expense(f"Lavoro sulla specifica {tr.label}", quota, in_cap=True,
                         category="sviluppo")
    tetto = trial_ceiling(gs, team, tr)
    if part.perf >= tetto - 0.02:
        return ""
    # le stesse cose che servivano a progettarla servono a capirla
    conf = project_confidence(gs, team, tr.part, tr.size)
    if gs.rng.random() > 0.18 + 0.45 * conf:
        return ""
    passo = (tetto - part.perf) * gs.rng.uniform(0.20, 0.45)
    part.perf = part.perf + passo
    return f"{tr.label}: qualcosa si e' capito, +{passo:.1f}."


def check_trials(gs, team) -> list:
    """Fa passare una gara alle specifiche in verifica.

    Il verdetto non arriva dalla fabbrica ma dalla pista: dopo un weekend con
    la specifica addosso i dati parlano, e da li' si decide.
    """
    msgs = []
    for tr in list(team.spec_trials):
        tr.races += 1
        buco = deficit(team, tr)
        if tr.state == "in prova":
            if buco < -0.05:
                why = weakest_link(gs, team, tr.part)
                tr.news = f"in pista va peggio della vecchia di {abs(buco):.1f}: {why}"
            elif buco < 0.15:
                why = weakest_link(gs, team, tr.part)
                tr.news = f"non ha cambiato niente rispetto alla vecchia: {why}"
            elif buco < tr.expected * 0.7:
                tr.news = (f"porta {buco:+.1f} sulla vecchia, meno dei "
                           f"+{tr.expected:.1f} promessi")
            else:
                tr.news = f"porta {buco:+.1f} sulla vecchia, come prometteva"
            # il verdetto si da' una volta sola, e lo si da' sempre: anche
            # quando il pacchetto ha funzionato si vuole sapere quanto ha
            # portato e come l'hanno trovata i piloti
            funziona = buco >= 0.15
            if team.is_player and tr.races == 1:
                msgs.append(f"{tr.label}: {tr.news}.")
                for d in gs.lineup_of(team.id):
                    _idx, frase = driver_verdict(gs, team, tr, d)
                    msgs.append(f"   {d.short}: {frase}.")
                if not funziona:
                    msgs.append("   Da decidere: rimontare la specifica vecchia "
                                "o tenerla e lavorarci.")
            if funziona:
                # ha portato qualcosa: non c'e' niente da capire, il reparto
                # passa ad altro e il banco torna libero
                team.spec_trials.remove(tr)
                continue
            if not team.is_player:
                _ai_decide(gs, team, tr, buco)
            elif tr.races > TRIAL_RACES:
                # nessuna decisione e' comunque una decisione: si va avanti cosi'
                tr.state = "affinamento"
                tr.races = 1
                msgs.append(f"{tr.label}: non avendo deciso niente, il reparto ha "
                            f"continuato a lavorarci sopra.")
            continue
        # in affinamento: si prova a tirarne fuori qualcosa, gara dopo gara
        nota = _trial_step(gs, team, tr)
        if nota and team.is_player:
            msgs.append(nota)
        if tr.races >= TRIAL_RACES + 1:
            buco = deficit(team, tr)
            _chiudi_log(team, tr, "recuperata" if buco > 0.05 else
                        ("pareggiata" if buco > -0.05 else "mai capita"))
            team.spec_trials.remove(tr)
            if not team.is_player:
                continue
            if buco > 0.05:
                msgs.append(f"{tr.label}: alla fine ne siamo venuti a capo, "
                            f"{buco:+.1f} sulla specifica vecchia.")
            elif buco > -0.05:
                msgs.append(f"{tr.label}: recuperato quello che si era perso, "
                            f"ma il pacchetto non ha portato niente.")
            else:
                msgs.append(f"{tr.label}: non ne siamo venuti a capo. Restiamo "
                            f"{abs(buco):.1f} sotto la specifica vecchia, e ormai "
                            f"quei pezzi non si rifanno.")
    return msgs


def _ai_decide(gs, team, tr: Trial, buco: float) -> None:
    """Le scuderie del computer decidono da sole, come deciderebbe un muretto."""
    prezzo = tr.cost * REVERT_SHARE
    if buco < -0.25 and team.cash > prezzo * 3:
        revert_spec(gs, team, tr)
    else:
        keep_spec(gs, team, tr)


def advance_projects(gs, team) -> list:
    """Fa avanzare i progetti di una gara. Ritorna i messaggi generati."""
    msgs = []
    done = []
    for pr in team.dev_projects:
        slice_cost = pr.budget / max(1, pr.races_left + (1 if pr.invested == 0 else 0))
        slice_cost = min(slice_cost, pr.budget - pr.invested)
        if slice_cost > 0:
            team.add_expense(f"Sviluppo: {pr.label}", round(slice_cost, 3), in_cap=True,
                             category="sviluppo")
            pr.invested += slice_cost
        pr.races_left -= 1
        if pr.races_left <= 0:
            msgs.extend(deliver(gs, team, pr))
            done.append(pr)
    for pr in done:
        team.dev_projects.remove(pr)
    return msgs


def passive_development(gs, team, budget: float) -> None:
    """Il lavoro continuo del reparto, fra la vettura di oggi e il regolamento
    di domani.

    Sulla macchina di adesso rende poco in prestazione pura: sono affinamenti,
    non aggiornamenti. Quello che lascia davvero e' la conoscenza della
    vettura, che si vede il venerdi' quando si trova subito la finestra giusta
    invece di passarci tre sessioni.

    Sul regolamento che verra' vale il dilemma classico della Formula 1: ogni
    milione speso sul progetto dell'anno prossimo e' un milione che non finisce
    sulla macchina con cui si corre adesso. La Brawn 2009 nacque da una
    stagione buttata via; la McLaren 2013 dal non averlo fatto.
    """
    if budget <= 0:
        return
    team.add_expense("Lavoro di reparto", round(budget, 3), in_cap=True,
                     category="sviluppo")
    # quello che si dirotta sull'anno prossimo: e' sempre lavoro sulla vettura
    # nuova, e quando c'e' un cambio di regolamento in arrivo vale anche come
    # preparazione al ciclo. Sono la stessa cosa, non due cose diverse
    from . import nextcar
    era = next_era(gs)
    share = max(0.0, min(0.90, team.next_reg_share))
    if share > 0:
        domani = budget * share
        nextcar.invest(gs, team, domani)
        if era is not None:
            team.reg_prep += domani * team.dev_rate * prep_conversion(gs, team, era)
        budget -= domani

    # quello che si capisce della macchina, e che finira' nell'assetto
    passo = UNDERSTANDING_RATE * budget * (0.45 + 0.55 * team.setup_strength / 100.0)
    team.car_understanding = min(1.0, team.car_understanding
                                 + passo * (1.0 - team.car_understanding))

    # e il poco che si guadagna limando quello che c'e' gia'
    pts = dev_capacity(gs, team) * (budget / 2.5) * 0.55 * REFINE_YIELD
    alloc = team.resource_alloc or {}
    tot = sum(alloc.values()) or 1.0
    for part, share in alloc.items():
        if part not in team.car.parts:
            continue
        p = team.car.parts[part]
        reso = yield_factor(gs, p.perf) * 0.49
        p.perf = p.perf + pts * (share / tot) * reso * gs.rng.uniform(0.6, 1.4)


def budget_headroom(gs, team) -> float:
    """Quanto si puo' ancora spendere per gara restando dentro il cap."""
    races_left = max(1, len(gs.tracks) - gs.round)
    fixed = (team.staff_cost + team.facility_upkeep) / len(gs.tracks) + economy.TRAVEL_PER_RACE
    room = (economy.cap_limit(gs) - team.spent) / races_left - fixed
    return max(0.0, room)


def lucidita(team) -> float:
    """Quanto bene il reparto sceglie da solo, da 0.35 a 1.

    Non e' la stessa cosa lasciar fare a un direttore tecnico da novanta o a
    uno da sessanta: il primo apre il pacchetto giusto sulla parte giusta, il
    secondo ogni tanto insegue la cosa sbagliata. Delegare non e' gratis, e'
    esattamente affidarsi a quanto valgono le persone che si sono assunte.
    """
    td = team._s("technical_director", "development", 55.0)
    tp = team._s("team_principal", "management", 55.0)
    return max(0.30, min(1.0, 0.30 + 0.75 * _n(0.7 * td + 0.3 * tp)))


def run_department(gs, team) -> None:
    """Una gara di lavoro del reparto, deciso dal reparto stesso.

    E' la stessa testa che usano le scuderie del computer. Quando il giocatore
    delega, delega a questa - e quanto viene bene lo dice chi ha in squadra.
    """
    headroom = budget_headroom(gs, team)
    # quello che resta dopo i costi fissi e dopo quello gia' speso, diviso
    # per le gare che mancano: e' cosi' che si fa un budget, non guardando
    # quanto si ha in banca
    resta = economy.room_left(gs, team)
    gare_restanti = max(1, len(gs.tracks) - gs.round)
    # chi ha capitale in cassa non si ferma a quello che incassa: lo mette
    # sul tavolo, fino a dove arriva il tetto di spesa
    fame = economy.spending_appetite(gs, team)
    budget = min(resta / gare_restanti * (0.55 + 0.40 * fame),
                 headroom * (0.45 + 0.45 * fame))
    budget = max(0.0, budget * economy.spending_room(gs, team))
    # dove mettere le mani lo dicono gli ingegneri, e sono le stesse parole che
    # usano in riunione: se dicono "lavorerei su sospensioni e telaio", il
    # reparto apre il pacchetto li'. Un reparto lucido segue la lista, uno meno
    # lucido ogni tanto pesca piu' in basso
    from . import engineering
    q = lucidita(team)
    consigliate = [p for p in engineering.suggested_parts(gs, team, 3)
                   if p in team.car.parts]
    if not consigliate:
        consigliate = [min(team.car.parts.items(), key=lambda kv: kv[1].perf)[0]]
    weak = consigliate[0] if gs.rng.random() < q else gs.rng.choice(consigliate)
    # e anche il lavoro continuo segue la stessa linea, invece di un'idea sua
    alloc = engineering.suggested_allocation(gs, team)
    alloc[weak] = alloc.get(weak, 0.1) * (1.0 + 1.6 * q)
    if team.philosophy == "aero":
        for k in ("floor", "front_wing", "rear_wing", "active_aero"):
            alloc[k] = alloc.get(k, 0.1) * 1.25
    elif team.philosophy == "mechanical":
        for k in ("suspension", "chassis", "gearbox"):
            alloc[k] = alloc.get(k, 0.1) * 1.25
    elif team.philosophy == "powertrain":
        for k in ("cooling", "gearbox", "sidepods"):
            alloc[k] = alloc.get(k, 0.1) * 1.2
    team.next_reg_share = ai_reg_share(gs, team)
    if not team.next_car_brief:
        from . import nextcar
        nextcar.ai_brief(gs, team)
    team.resource_alloc = alloc
    passive_development(gs, team, budget)
    ai_start_package(gs, team, weak, headroom, economy.room_left(gs, team))


def ai_development(gs) -> None:
    """Sviluppo delle scuderie gestite dal computer.

    Come per il giocatore, il grosso passa dai pacchetti: il lavoro continuo
    prende solo la fetta che serve a tenere in piedi il reparto e a capire la
    macchina. Quanto in grande si osa dipende da quanto ci si fida dei propri
    strumenti: chi sa di non correlare porta pacchetti piccoli e sicuri.
    """
    for team in gs.teams.values():
        if team.is_player:
            continue
        run_department(gs, team)
        check_trials(gs, team)
        advance_projects(gs, team)


def ai_start_package(gs, team, weak: str, headroom: float, avanza: float = 0.0) -> None:
    """Decide se aprire un pacchetto e quanto grande farlo.

    `avanza` e' quello che resta della stagione dopo i costi fissi e dopo quello
    gia' speso: un pacchetto e' un impegno grosso e non lo si apre se non ci sta
    dentro, per quanto spazio ci sia nel tetto di spesa. Sono due vincoli
    diversi e servono tutti e due.
    """
    # due cantieri aperti alla volta: il terzo slot resta al giocatore, che se
    # lo puo' permettere solo tenendo il reparto sotto pressione
    if len(team.dev_projects) >= 2 or gs.rng.random() > 0.55:
        return
    # a fine stagione non si comincia piu' niente che non arrivi in tempo
    gare_restanti = len(gs.tracks) - gs.round
    from . import engineering
    altre = [p for p in engineering.suggested_parts(gs, team, 4)
             if p in team.car.parts] or list(team.car.parts)
    part = weak if gs.rng.random() < 0.65 else gs.rng.choice(altre)
    scelte = []
    for size, gare in (("grande", 6), ("medio", 3), ("piccolo", 1)):
        if gare > gare_restanti:
            continue
        costo = cost_of_upgrade(gs, team, part, size)
        if costo > headroom * gare * 0.9 or costo / gare > team.cash * 0.5:
            continue
        # quello che ci si e' gia' impegnati a pagare conta: un pacchetto per
        # volta ci sta sempre, tutti insieme no
        impegnato = sum(max(0.0, x.budget - x.invested) for x in team.dev_projects)
        tetto = avanza * (0.75 + 0.55 * economy.spending_appetite(gs, team))
        if impegnato + costo > max(3.0, tetto):
            continue                     # non ce lo possiamo permettere
        conf = project_confidence(gs, team, part, size)
        atteso = expected_gain(gs, team, part, size) * (
            1.0 - 1.3 * outcome_odds(conf, size)["fallito"])
        scelte.append((atteso / max(0.5, costo), size))
    if not scelte:
        return
    scelte.sort(reverse=True)
    # il migliore lo prende chi ci vede chiaro; gli altri ogni tanto sbagliano
    if gs.rng.random() < lucidita(team) or len(scelte) == 1:
        start_project(gs, team, part, scelte[0][1])
    else:
        start_project(gs, team, part, gs.rng.choice(scelte)[1])


def new_car_season(gs) -> None:
    """La macchina nuova e' un'altra macchina: quello che si era capito vale meno.

    Non si riparte da zero - il metodo di lavoro resta - ma la finestra di
    assetto va ritrovata, ed e' il motivo per cui a marzo tutti brancolano.
    """
    for team in gs.teams.values():
        team.car_understanding *= UNDERSTANDING_CARRY
        # le specifiche in verifica muoiono con la macchina su cui erano nate:
        # quello che si e' recuperato resta, il resto e' storia
        team.spec_trials = []


def technological_decay(gs) -> float:
    """Invecchia le vetture di tutti di una stagione.

    Non e' usura: e' il resto del mondo che va avanti. Restare fermi significa
    arretrare, ed e' quello che rende obbligatorio reinvestire.
    """
    lost = 0.0
    for team in gs.teams.values():
        for p in team.car.parts.values():
            # chi sta in alto fa piu' fatica a restarci: il fronte si muove
            step = TECH_DECAY * (0.60 + 0.60 * p.perf / reference_level(gs))
            new = max(40.0, p.perf - step)
            if team.is_player:
                lost += p.perf - new
            p.perf = new
    return lost / max(1, len(C.CAR_PARTS))


# Componenti che il regolamento consente di comprare dalla squadra maggiore:
# nella realta' sono cambio, sospensione posteriore e impianto frenante.
TRANSFERABLE = ("gearbox", "suspension", "brakes")


def sister_transfer(gs) -> list:
    """Le satellite montano i componenti trasferibili della sorella maggiore.

    Non e' un regalo: si comprano, e restano indietro di un passo rispetto
    all'originale. Ma per una squadra piccola vale piu' di quanto potrebbe
    progettare da sola.
    """
    msgs = []
    for team in gs.teams.values():
        parent = gs.teams.get(team.parent_team) if team.parent_team else None
        if parent is None or parent is team:
            continue
        for k in TRANSFERABLE:
            if k not in team.car.parts or k not in parent.car.parts:
                continue
            mio = team.car.parts[k]
            suo = parent.car.parts[k].perf * 0.97      # un passo indietro
            if suo > mio.perf:
                mio.perf = mio.perf + (suo - mio.perf) * 0.8
        if team.is_player:
            msgs.append(f"Dal gruppo {parent.short} arrivano cambio, sospensione "
                        f"posteriore e freni della stagione nuova.")
    return msgs


def ai_reg_share(gs, team) -> float:
    """Quanto il computer dirotta sull'anno prossimo.

    Una quota ci va sempre: la macchina del prossimo anno la si comincia
    mentre si corre con questa, e piu' la stagione va avanti piu' quella di
    adesso ha poco senso da migliorare. Poi c'e' il caso speciale del cambio
    di regolamento, dove la quota sale e chi non ha piu' niente da giocarsi
    stacca prima la spina - e' quello che fece la Brawn nel 2008.
    """
    # sempre un piede sull'anno prossimo, e il piede si appoggia sempre di piu'
    # mano a mano che la stagione finisce
    avanzamento = gs.round / max(1, len(gs.tracks))
    base = 0.08 + 0.30 * avanzamento
    # Il reset scatta a fine stagione, quindi l'ultimo anno utile per
    # prepararsi e' quello con left == 1: da li' in poi e' troppo tardi.
    left = seasons_to_reset(gs)
    if left is not None and left <= 3:
        base = max(base, {3: 0.10, 2: 0.25, 1: 0.60}.get(left, 0.0))
    standings = gs.constructor_standings()
    leader = standings[0].points if standings else 0.0
    pos = gs.position_of(team.id)
    in_lotta = pos <= 3 and team.points > leader * 0.60
    tardi = gs.round > len(gs.tracks) * 0.55
    if in_lotta:
        base *= 0.55                       # si difende il campionato in corso
    elif tardi and pos > 4:
        base = min(0.85, base + 0.25)      # niente da perdere: tutto sull'anno nuovo
    return base


def regulation_reset(gs, strength: float, era: dict | None = None) -> list:
    """Un nuovo ciclo tecnico rimescola la griglia.

    Conta chi ci ha lavorato prima e quanto la squadra e' forte nell'area che
    il nuovo regolamento premia. Chi non ha preparato nulla il reset lo subisce
    invece di sfruttarlo.
    """
    vecchio = cycle_base(gs)
    # il riferimento sale di poco: la tecnologia avanza, ma una macchina nuova
    # non nasce mai al livello di una perfezionata per anni
    nuovo = vecchio + CYCLE_STEP * max(0.3, strength)
    gs.regulations["cycle_base"] = round(nuovo, 2)

    preps = [t.reg_prep for t in gs.teams.values()]
    best_prep = max(preps) or 1.0
    avg_prep = (sum(preps) / len(preps)) or 1.0
    news = []
    for team in gs.teams.values():
        quality = (0.45 * team.aero_strength + 0.35 * team.mech_strength
                   + 0.20 * team.dev_rate * 60.0) / 100.0
        # preparazione rispetto agli altri: negativa se sotto la media
        rel = (team.reg_prep - avg_prep) / max(best_prep, 1e-6)
        prep_bonus = rel * 12.0 * strength
        # quanto ci si porta dietro del vantaggio accumulato nel ciclo che
        # finisce: chi ha preparato ne conserva molto di piu'
        carry = max(0.25, min(0.92, 0.72 - 0.34 * strength + 0.22 * rel))
        prima = sum(x.perf for x in team.car.parts.values()) / len(team.car.parts)
        for p in team.car.parts.values():
            sopra = p.perf - vecchio
            base = nuovo + sopra * carry
            bonus = (quality - 0.75) * 14.0 * strength
            p.perf = max(45.0, base + bonus + prep_bonus + gs.rng.gauss(0, 2.4))
            p.condition = 100.0
        if team.is_player:
            dopo = sum(x.perf for x in team.car.parts.values()) / len(team.car.parts)
            news.append(f"Regolamento nuovo: la vettura riparte {prima - dopo:.1f} punti "
                        f"sotto quella che avevamo perfezionato in questi anni.")
            if rel > 0.25:
                news.append("Il lavoro sul nuovo regolamento paga: siamo fra i piu' pronti.")
            elif rel < -0.25:
                news.append("Ci siamo fatti sorprendere: altri avevano cominciato molto prima.")
        team.reg_prep = 0.0
        team.next_reg_share = 0.0
        # concetto nuovo, tutto da riscoprire: e' il caos del primo anno
        team.car_understanding *= 0.15
    return news
