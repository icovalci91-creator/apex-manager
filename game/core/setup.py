"""Assetto: simulatore, assetto sulla carta, riscontri della pista.

Trovare l'assetto non e' una voce di bilancio: e' il lavoro del weekend, ed e'
gratis come e' gratis respirare. Quello che costa viene prima, nei giorni
precedenti, quando al simulatore si prova la pista che verra' e si arriva a un
assetto sulla carta. Quell'assetto e' una previsione, non una verita': quanto
ci prende dipende da che simulatore si ha, da quanto quel simulatore assomiglia
alla realta', da quanto si conosce il circuito e da quanto si e' capita la
macchina.

Poi si va in pista, e la pista risponde. I piloti dicono cosa fa la macchina,
gli ingegneri leggono i dati, e sessione dopo sessione la previsione si
avvicina a quello che serve davvero. Chi e' arrivato con un buon riferimento
usa le prove per limare; chi e' arrivato alla cieca le usa per capire dove sta,
e alla domenica e' ancora fuori finestra.
"""
from __future__ import annotations

from ..model.car import SETUP_KEYS
from . import economy

# Far girare un simulatore moderno costa: turni di tecnici, piloti, licenze e
# un impianto che consuma. Piu' e' avanzato, piu' costa tenerlo acceso.
SIM_BASE = 0.05
SIM_LEVEL = 0.20

# Quante sessioni ha senso fare per un weekend: due. Alla terza si gira a vuoto
# su un modello che ha gia' detto quello che sapeva, e il resto lo dice solo la
# pista.
SIM_MAX = 2

# Errore della previsione, in punti d'assetto, per una squadra senza niente.
ERR_MAX = 26.0
ERR_MIN = 3.5


def sim_cost(team) -> float:
    """Quanto costa una sessione al simulatore."""
    lvl = float(team.facilities.get("simulator", 60.0)) / 100.0
    return round(SIM_BASE + SIM_LEVEL * lvl ** 1.4, 2)


def _knowledge(team, track) -> float:
    """Quanto la squadra sa gia' di questa pista e di questa macchina, 0..1.

    Il simulatore da' il modello, la correlazione dice se quel modello e' vero,
    i giorni passati su quel circuito dicono cosa aspettarsi, e una pista di
    proprieta' vuol dire poterci girare quando si vuole invece di aspettare il
    venerdi'.
    """
    from . import testing
    sim = float(team.facilities.get("simulator", 60.0)) / 100.0
    pista = float(team.facilities.get("private_track", 0.0)) / 100.0
    corr = max(0.0, min(1.0, team.correlation))
    circuito = testing.setup_bonus(team, track)
    return max(0.0, min(1.0,
                        0.34 * sim + 0.20 * corr + 0.18 * circuito
                        + 0.16 * team.car_understanding + 0.12 * pista))


def paper_error(team, track, sessions: int) -> float:
    """Di quanto puo' sbagliare l'assetto sulla carta, in punti.

    Senza lavoro al simulatore resta l'intuito del reparto, che e' molto: la
    macchina la conoscono. Ma su una pista precisa, senza averci girato, si
    parte lontani.
    """
    base = ERR_MAX - (ERR_MAX - ERR_MIN) * _knowledge(team, track)
    # ogni sessione di simulatore stringe, ma con rendimenti calanti
    return max(ERR_MIN, base * (0.55 ** min(SIM_MAX, max(0, sessions))))


def has_paper(team, track) -> bool:
    return bool(team.setup_paper) and team.setup_paper_track == track.id


def ensure_paper(gs, team, track) -> None:
    """Il riferimento di partenza: quello che il reparto si aspetta.

    Esiste anche senza simulatore - nessuno arriva in pista senza un'idea - ma
    e' tanto piu' vago quanto meno si e' lavorato.
    """
    if has_paper(team, track):
        return
    team.setup_paper_track = track.id
    team.sim_sessions = 0
    _draw_paper(gs, team, track)


def _attese(track):
    """Le condizioni che il reparto si aspetta di trovare.

    Al simulatore non si prova il tempo di domenica: si prova quel gran premio,
    con il clima che ha di solito e l'aria che si respira a quella quota. La
    pioggia, se arriva, e' una sorpresa che si paga il venerdi'.
    """
    from ..sim import pace
    return pace.nominal(track)


def _draw_paper(gs, team, track) -> None:
    """Estrae la previsione attorno all'ottimo vero, con l'errore del momento."""
    opt = team.car.optimal_setup(track, cond=_attese(track))
    err = paper_error(team, track, team.sim_sessions)
    team.setup_paper = {k: max(0.0, min(100.0, opt[k] + gs.rng.gauss(0.0, err)))
                        for k in SETUP_KEYS}


def run_simulator(gs, team, track) -> tuple:
    """Una sessione al simulatore nei giorni prima del weekend."""
    ensure_paper(gs, team, track)
    if team.sim_sessions >= SIM_MAX:
        return False, ("Il simulatore ha gia' detto quello che sapeva: da qui in "
                       "avanti si scopre in pista.")
    prezzo = sim_cost(team)
    ok, why = economy.can_afford(team, prezzo, gs)
    if not ok:
        return False, why
    team.add_expense(f"Simulatore - preparazione {track.name}", prezzo, in_cap=True,
                     category="sviluppo")
    team.sim_sessions += 1
    prima = paper_error(team, track, team.sim_sessions - 1)
    _refine(gs, team, track, paper_error(team, track, team.sim_sessions))
    dopo = paper_error(team, track, team.sim_sessions)
    return True, (f"Sessione al simulatore per {prezzo:.2f} M$: il riferimento passa "
                  f"da +/-{prima:.0f} a +/-{dopo:.0f} punti d'assetto.")


def _refine(gs, team, track, err: float) -> None:
    """Riporta la previsione dentro un errore piu' stretto attorno al vero."""
    opt = team.car.optimal_setup(track, cond=_attese(track))
    paper = team.setup_paper or {}
    for k in SETUP_KEYS:
        cur = paper.get(k, 50.0)
        # la stima si muove verso il vero, ma non ci arriva: resta l'errore
        target = opt[k] + gs.rng.gauss(0.0, err)
        peso = 0.65
        paper[k] = max(0.0, min(100.0, cur + (target - cur) * peso))
    team.setup_paper = paper


# ------------------------------------------------------- riscontri in pista
# Quanto si legge male la pista: anche con i migliori, un turno di prove dice
# una cosa un po' diversa dalla precedente. Gomme, benzina, vento, asfalto che
# si gomma: e' il motivo per cui a volte si insegue tutto il weekend.
READ_NOISE = 7.0

# E quanto peggiora quella lettura quando la macchina non la si e' ancora
# capita. E' il vero costo di un pacchetto grosso, ed e' un costo che le prove
# non lavano via: i dati arrivano uguali, ma nessuno sa ancora quale manopola
# risponde a cosa, quindi il turno si chiude piu' lontani dall'ottimo di quanto
# ci si sarebbe chiusi ad agosto con la stessa macchina in mano. Prima questo
# non c'era, e la conoscenza della vettura contava un centesimo al giro: si
# poteva rifare la macchina ogni tre gare senza pagarla mai.
RUMORE_IGNOTA = 3.00


def track_learning(team, feedback: float) -> float:
    """Quanto si impara da una sessione in pista, 0..1.

    Qui contano le persone, non gli strumenti: il simulatore ha gia' detto
    quello che aveva da dire. In pista serve un pilota che sappia raccontare
    cosa fa la macchina e un muretto capace di tradurlo in millimetri.
    """
    pe = team.roles("performance_engineer")
    pe_v = sum(p.analysis for p in pe) / len(pe) if pe else 60.0
    persone = (0.40 * feedback + 0.30 * pe_v
               + 0.15 * team._s("technical_director", "analysis")
               + 0.15 * team._s("race_engineer", "communication"))
    return max(0.10, min(0.45, 0.10 + 0.28 * (persone / 100.0)))


def learn_from_track(gs, team, track, feedback: float, share: float = 1.0,
                     cond=None) -> None:
    """La pista risponde: la previsione si avvicina a quello che serve.

    Con share si pesa quanto vale il turno: una gara sprint insegna qualcosa
    sulla macchina, ma meno di una sessione di prove fatta apposta. Quello che
    si scopre e' l'assetto giusto per la giornata che c'e', non per quella che
    ci si aspettava: se piove, il riferimento del simulatore va buttato.
    """
    ensure_paper(gs, team, track)
    opt = team.car.optimal_setup(track, cond=cond if cond is not None else _attese(track))
    passo = track_learning(team, feedback) * max(0.0, min(1.0, share))
    # quanto si legge male dipende anche da quanto si e' capita la macchina:
    # con una specifica appena arrivata il pilota dice cosa fa, ma tradurlo in
    # millimetri e' un'altra cosa, e si resta piu' lontani dall'ottimo
    capita = max(0.0, min(1.0, team.car_understanding))
    rumore = READ_NOISE * (1.0 + RUMORE_IGNOTA * (1.0 - capita))
    paper = team.setup_paper
    for k in SETUP_KEYS:
        cur = paper.get(k, 50.0)
        # si scopre l'ottimo con un residuo di rumore: i dati non sono perfetti
        letto = opt[k] + gs.rng.gauss(0.0, rumore)
        paper[k] = max(0.0, min(100.0, cur + (letto - cur) * passo))
    team.setup_paper = paper


def target_for(team, driver) -> dict:
    """Il riferimento del reparto, corretto per come guida quel pilota.

    Il foglio e' uno solo - e' la lettura della pista - ma sulle due macchine
    non ci finisce uguale: a chi stacca tardi si sposta il freno in avanti, a
    chi cura le gomme si ammorbidisce. Da qui due assetti diversi con lo stesso
    riferimento.
    """
    from . import driving
    paper = team.setup_paper or {}
    if not paper:
        return {}
    off = driving.offsets(driver) if driver is not None else {}
    return {k: max(0.0, min(100.0, paper.get(k, 50.0) + off.get(k, 0.0)))
            for k in SETUP_KEYS}


def apply_paper(gs, team, share: float = 1.0, driver=None) -> None:
    """Monta sulle macchine quello che il reparto crede sia giusto.

    Una macchina per pilota: stesso foglio, due assetti, perche' l'ottimo di
    uno non e' l'ottimo dell'altro.
    """
    from . import driving
    if not team.setup_paper:
        return
    piloti = [driver] if driver is not None else gs.lineup_of(team.id)
    for d in piloti:
        if d is None:
            continue
        bersaglio = target_for(team, d)
        mio = driving.setup_of(team, d)
        for k in SETUP_KEYS:
            cur = mio.get(k, 50.0)
            mio[k] = cur + (bersaglio[k] - cur) * share


def clear(team) -> None:
    """Fine weekend: il riferimento vale per quella pista, non per la prossima."""
    team.setup_paper = {}
    team.setup_paper_track = ""
    team.sim_sessions = 0


def new_weekend(gs) -> None:
    """Apre la preparazione del prossimo appuntamento, per tutti.

    Il riferimento di partenza nasce qui e non quando qualcuno apre una
    schermata: l'idea che il reparto si e' fatto della pista non dipende da
    dove sta guardando il direttore sportivo. Le squadre del computer fanno
    qui il loro lavoro al simulatore, e lo pagano come lo paghiamo noi.
    """
    track = gs.next_track
    for team in gs.teams.values():
        clear(team)
        if track is None:
            continue
        ensure_paper(gs, team, track)
        # chi ha lasciato fare agli ingegneri se lo ritrova pronto: e' il
        # motivo per cui dimenticarsene non manda all'aria il weekend
        if not team.is_player or team.auto_setup:
            _ai_prepare(gs, team, track)


def _ai_prepare(gs, team, track) -> None:
    """Quante sessioni si concede una squadra che prepara da sola.

    Nessuno arriva in pista senza aver provato niente, ma chi ha il bilancio
    corto ne fa meno. Vale per le scuderie del computer e per il giocatore che
    ha lasciato fare agli ingegneri: quanto viene bene dipende da chi ci sta
    al simulatore.
    """
    from . import economy
    salute = economy.budget_health(gs, team)
    # una sessione la fanno tutti: arrivare in pista senza aver provato niente
    # non lo fa nessuno. La seconda si paga se il bilancio la regge, e la
    # fanno volentieri quelli che sanno cosa cercarci
    bravi = team.setup_strength >= 70.0
    voglia = 1 + int(salute > 0.5 and bravi)
    for _ in range(min(SIM_MAX, voglia)):
        ok, _m = run_simulator(gs, team, track)
        if not ok:
            break
    apply_paper(gs, team)


def believed_quality(team, driver=None) -> float:
    """Quanto il reparto crede che quella macchina sia in finestra, da 0 a 1.

    Non e' la verita': e' la distanza fra la macchina e il riferimento che il
    reparto si e' fatto, corretto per lo stile di chi la guida. Quando il
    riferimento e' sbagliato si puo' essere convinti di avere tutto a posto e
    prendere mezzo secondo.
    """
    from . import driving
    paper = team.setup_paper or {}
    if not paper:
        return 0.5
    if driver is None:
        montato = team.car.setup
        bersaglio = paper
    else:
        montato = driving.setup_of(team, driver)
        bersaglio = target_for(team, driver)
    err = sum(abs(montato.get(k, 50.0) - bersaglio[k]) for k in bersaglio) / len(bersaglio)
    return max(0.0, 1.0 - (err / 45.0) ** 1.35)


def hints(team, track, driver=None) -> list:
    """Cosa dicono gli ingegneri, sulla base di quello che credono di sapere."""
    from . import driving
    paper = team.setup_paper or {}
    if not paper:
        return ["- Nessun riferimento per questa pista: serve lavoro al simulatore."]
    montato = driving.setup_of(team, driver) if driver is not None else team.car.setup
    bersaglio = target_for(team, driver) if driver is not None else paper
    frasi = {
        "wing": ("troppo carico: siamo lenti sui rettilinei",
                 "poco carico: la macchina scivola in curva"),
        "ride_height": ("troppo alta: perdiamo carico dal fondo",
                        "troppo bassa: strisciamo sui cordoli"),
        "stiffness": ("troppo rigida: salta sulle sconnessioni",
                      "troppo morbida: rolla e consuma le gomme"),
        "camber": ("campanatura eccessiva: surriscalda l'anteriore",
                   "campanatura scarsa: manca inserimento"),
        "gearing": ("rapporti troppo lunghi: non spinge in uscita",
                    "rapporti troppo corti: tocchiamo il limitatore"),
        "brake_bias": ("freno troppo indietro: instabile in staccata",
                       "freno troppo avanti: blocca l'anteriore"),
    }
    out = []
    for k, (hi, lo) in frasi.items():
        d = montato.get(k, 50.0) - bersaglio.get(k, 50.0)
        if d > 12:
            out.append(f"- {SETUP_KEYS[k]}: {hi}")
        elif d < -12:
            out.append(f"- {SETUP_KEYS[k]}: {lo}")
    if not out:
        out.append("- La macchina e' dove la vogliamo: si puo' lavorare sul passo gara.")
    return out
