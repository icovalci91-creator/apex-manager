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


def _draw_paper(gs, team, track) -> None:
    """Estrae la previsione attorno all'ottimo vero, con l'errore del momento."""
    opt = team.car.optimal_setup(track)
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
    opt = team.car.optimal_setup(track)
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


def learn_from_track(gs, team, track, feedback: float) -> None:
    """La pista risponde: la previsione si avvicina a quello che serve."""
    ensure_paper(gs, team, track)
    opt = team.car.optimal_setup(track)
    passo = track_learning(team, feedback)
    paper = team.setup_paper
    for k in SETUP_KEYS:
        cur = paper.get(k, 50.0)
        # si scopre l'ottimo con un residuo di rumore: i dati non sono perfetti
        letto = opt[k] + gs.rng.gauss(0.0, READ_NOISE)
        paper[k] = max(0.0, min(100.0, cur + (letto - cur) * passo))
    team.setup_paper = paper


def apply_paper(team, share: float = 1.0) -> None:
    """Monta sulla macchina quello che il reparto crede sia giusto."""
    if not team.setup_paper:
        return
    for k in SETUP_KEYS:
        cur = team.car.setup.get(k, 50.0)
        team.car.setup[k] = cur + (team.setup_paper[k] - cur) * share


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
        if not team.is_player:
            _ai_prepare(gs, team, track)


def _ai_prepare(gs, team, track) -> None:
    """Quante sessioni si concede una scuderia del computer.

    Nessuno arriva in pista senza aver provato niente, ma chi ha il bilancio
    corto ne fa meno: e' la stessa scelta che ha davanti il giocatore.
    """
    voglia = 1 + int(team.cash > 40.0) + int(team.reputation > 72.0)
    for _ in range(min(SIM_MAX, voglia)):
        ok, _m = run_simulator(gs, team, track)
        if not ok:
            break
    apply_paper(team)
    team.car.evaluate_setup(track)


def believed_quality(team) -> float:
    """Quanto il reparto crede di essere in finestra, da 0 a 1.

    Non e' la verita': e' la distanza fra la macchina e il riferimento che il
    reparto si e' fatto. Quando il riferimento e' sbagliato si puo' essere
    convinti di avere tutto a posto e prendere mezzo secondo.
    """
    paper = team.setup_paper or {}
    if not paper:
        return 0.5
    err = sum(abs(team.car.setup.get(k, 50.0) - paper[k]) for k in paper) / len(paper)
    return max(0.0, 1.0 - (err / 45.0) ** 1.35)


def hints(team, track) -> list:
    """Cosa dicono gli ingegneri, sulla base di quello che credono di sapere."""
    paper = team.setup_paper or {}
    if not paper:
        return ["- Nessun riferimento per questa pista: serve lavoro al simulatore."]
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
        d = team.car.setup.get(k, 50.0) - paper.get(k, 50.0)
        if d > 12:
            out.append(f"- {SETUP_KEYS[k]}: {hi}")
        elif d < -12:
            out.append(f"- {SETUP_KEYS[k]}: {lo}")
    if not out:
        out.append("- La macchina e' dove la vogliamo: si puo' lavorare sul passo gara.")
    return out
