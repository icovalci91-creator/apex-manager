"""Il muretto: quello che la squadra decide mentre la gara va avanti.

Fino a ieri della gara si decidevano tre cose - quando entrare ai box, che
passo tenere, come usare la batteria - e tutto il resto lo faceva il muretto
per conto suo. Il pezzo che mancava e' quello che alla radio si sente di piu':
cosa si chiede al pilota. Non "vai piu' forte", ma come deve correre quel
pezzo di gara - se spendere la gomma adesso per prendere quello davanti, se
tenerla per l'ultimo stint, se difendere il posto e basta, se portare a casa
una macchina che non e' piu' intera.

Sono cinque istruzioni e ognuna ha un prezzo. Attaccare fa passare piu' spesso
e rompe piu' spesso; gestire allunga lo stint e regala il posto a chi arriva;
difendere tiene la posizione ma non ne prende un'altra. Nessuna e' un pulsante
che regala tempo: e' un baratto, ed e' per questo che sceglierla e' una scelta.

Lo stesso vale per gli avversari: il loro muretto sceglie con le stesse regole
e le stesse conseguenze, filtrate da quanto e' bravo. Non c'e' niente qui che
il giocatore possa fare e il computer no.
"""
from __future__ import annotations

from . import benzina as BZ

# ------------------------------------------------------------------- ordini
# passo:      il passo che l'ordine chiede, None = decide il muretto
# tentativi:  quante volte in piu' o in meno si prova a passare, in un giro
# attacco:    quanto pesa quell'ordine sulla riuscita di un sorpasso. E' piccolo
#             di proposito: il passo che l'ordine chiede finisce gia' dentro al
#             tempo sul giro, e quindi dentro al conto del duello. Quello che
#             resta qui e' solo la voglia di infilarsi dove non e' scontato
# difesa:     e quanto pesa su quella di chi prova a passare lui
# rischio:    quanto si rischia il contatto, e con quello la gara
# motore:     quanto si tira la power unit
ORDINI = {
    "libero": {
        "label": "Libero", "corto": "LIB",
        "nota": "Decide lui: corre la sua gara.",
        "radio": "Gara tua, gestiscila come vuoi.",
        "passo": None, "tentativi": 0, "attacco": 1.0, "difesa": 1.0,
        "rischio": 1.0, "motore": 1.0,
    },
    "attacca": {
        "label": "Attacca", "corto": "ATT",
        "nota": "Prende quello davanti adesso. Costa gomma, benzina e rischio.",
        "radio": "Vai a prenderlo: da qui in avanti spingiamo.",
        "passo": 1.08, "tentativi": 1, "attacco": 1.10, "difesa": 0.95,
        "rischio": 1.20, "motore": 1.15,
    },
    "gestisci": {
        "label": "Gestisci", "corto": "GES",
        "nota": "Allunga lo stint: gomma e benzina in cassa, passo indietro.",
        "radio": "Gestisci: ci serve arrivare in fondo con questa gomma.",
        "passo": 0.94, "tentativi": -1, "attacco": 0.70, "difesa": 1.0,
        "rischio": 0.80, "motore": 0.90,
    },
    "difendi": {
        "label": "Difendi", "corto": "DIF",
        "nota": "Il posto e' questo e resta questo: chiude la porta.",
        "radio": "Difendi la posizione, non ci interessa altro.",
        "passo": 1.02, "tentativi": -1, "attacco": 0.55, "difesa": 1.18,
        "rischio": 1.05, "motore": 1.0,
    },
    "casa": {
        "label": "Porta a casa", "corto": "CASA",
        "nota": "Zero rischio: si torna al traguardo con quello che si ha.",
        "radio": "Porta a casa la macchina, non serve altro.",
        "passo": 0.90, "tentativi": -2, "attacco": 0.0, "difesa": 0.95,
        "rischio": 0.30, "motore": 0.80,
    },
}
ELENCO = ("libero", "attacca", "gestisci", "difendi", "casa")


def di(e) -> dict:
    """L'ordine sotto cui sta correndo questa vettura."""
    return ORDINI.get(getattr(e, "ordine", "libero"), ORDINI["libero"])


def applica_passo(sim, e) -> None:
    """L'ordine sopra al passo scelto dal muretto.

    Non scavalca la benzina: chiedere di attaccare a chi non ha di che
    arrivare in fondo non fa apparire i chili nel serbatoio. Chiedere di
    gestire invece si puo' sempre - alzare il piede e' un ordine che si esegue
    anche quando non serve.
    """
    if e.passo_manuale is not None:
        return
    o = di(e)
    voluto = o["passo"]
    if voluto is None:
        return
    if voluto > 1.0:
        tetto = BZ.passo_necessario(sim, e)
        e.push_mode = max(e.push_mode, min(voluto, tetto))
    else:
        e.push_mode = min(e.push_mode, voluto)
    e.push_mode = max(BZ.PASSO_MIN, min(BZ.PASSO_MAX, e.push_mode))
    e.passo_benzina = round(e.push_mode - 1.0, 3)


def tentativi(e, base: int) -> int:
    """Quante volte al giro ci prova, con l'ordine che ha."""
    return max(0, base + di(e)["tentativi"])


def rischio(e) -> float:
    """Quanto rischia il contatto quando si infila."""
    return di(e)["rischio"]


# ------------------------------------------------------- il muretto del computer
# Ogni quanto il muretto avversario si rimette a guardare le sue due macchine.
# Non a ogni giro: si guarda la gara, si decide, e quella decisione resta per
# un pezzo. Cambiare idea ogni passaggio non e' gestire, e' agitarsi.
GIRI_ORDINE = 4
# Sotto quanti secondi si considera "a tiro" quello davanti, e "addosso"
# quello dietro
TIRO = 1.1
ADDOSSO = 1.1
# Quanta vita deve restare alla gomma perche' abbia ancora senso attaccare
# qualcuno. E' vita residua, non rendimento: dentro il suo stint una gomma
# rende quasi uguale fino in fondo, ed e' la vita che finisce
VITA_SCARICA = 0.25


def ai_ordine(sim, e, avanti, dietro, gap_a: float, gap_d: float) -> None:
    """Che ordine da' il muretto del computer alle sue macchine.

    Le stesse cinque istruzioni del giocatore e con le stesse conseguenze. Chi
    ha un muretto bravo le indovina piu' spesso: legge prima che la gomma sia
    finita, capisce quando difendere basta e quando serve provarci.
    """
    # le nostre macchine le gestisce il giocatore, a meno che non abbia
    # lasciato la gara al Team Principal: allora decide questo, con le stesse
    # regole degli altri e la competenza di chi si e' messo al muretto
    if (e.is_player and not e.delegato) or e.status != "running":
        return
    if e.lap < e.ordine_da + GIRI_ORDINE:
        return
    e.ordine_da = e.lap
    resta = sim.laps - e.lap
    vita = e.vita_gomma()
    # una macchina rotta si porta a casa, e non c'e' molto da decidere
    if e.damage > 30 or e.motore_usura > 0.88:
        e.ordine = "casa"
        return
    # e negli ultimi giri, chi e' nei punti e non ha nessuno intorno li porta a
    # casa. Nessuno intorno vuol dire da tutte e due le parti: se davanti c'e'
    # ancora qualcuno a tiro non si porta niente a casa, si va a prenderlo, ed
    # e' da li' che nascono i sorpassi all'ultimo giro
    if 0 < resta <= 3 and e.position <= 10 and gap_d > 3.0 and gap_a > 3.0:
        e.ordine = "casa"
        return
    # da qui in poi e' mestiere: un muretto distratto lascia correre
    if sim.rng.random() > 0.25 + 0.0070 * e.strategy_skill:
        e.ordine = "libero"
        return
    prossima = e.plan[0][0] if e.plan else sim.laps
    # la gomma non arriva alla sosta: si gestisce, ed e' la decisione che
    # separa un muretto che sa leggere da uno che scopre il problema dopo
    if vita < VITA_SCARICA and prossima - e.lap > 4:
        e.ordine = "gestisci"
    elif not sim.senza_benzina and BZ.margine_giri(sim, e) < -0.3:
        e.ordine = "gestisci"
    elif avanti and gap_a < TIRO and vita > VITA_SCARICA:
        e.ordine = "attacca"
    elif dietro and gap_d < ADDOSSO and (avanti is None or gap_a > 3.0):
        e.ordine = "difendi"
    else:
        e.ordine = "libero"


# ---------------------------------------------------------- ordini di squadra
# Quanto ci mette un pilota a obbedire, e quanto spesso non obbedisce affatto.
# Lasciar passare il compagno e' la cosa che a un pilota costa di piu': chi ha
# il morale alto e sta lottando per qualcosa ci mette di piu' a farlo, e certe
# volte semplicemente risponde alla radio e tiene la posizione.
ATTESA_MIN = 1            # giri prima di eseguire, per uno che obbedisce subito
ATTESA_MAX = 4            # e per uno che la prende molto larga
RIFIUTO_BASE = 0.30       # quanto e' probabile un no, prima del carattere


def voglia_di_obbedire(e, sim) -> float:
    """Quanto e' disposto a farsi da parte. Da 0 (mai) a 1 (subito)."""
    # chi si fida della squadra obbedisce, chi e' aggressivo di suo molto meno,
    # e nessuno si fa da parte volentieri quando il posto vale qualcosa
    v = 0.30 + 0.0055 * e.confidence - 0.0035 * e.aggression
    if e.position <= 3:
        v -= 0.20
    elif e.position <= 6:
        v -= 0.10
    if sim.laps - e.lap <= 5:
        v -= 0.15           # a cinque giri dalla fine si discute molto di piu'
    return max(0.05, min(0.95, v))


def chiedi_scambio(sim, davanti, dietro) -> str:
    """"Lascialo passare": la richiesta parte, la risposta non e' scontata.

    Torna il testo che il pilota risponde alla radio. E' il momento piu'
    famoso del muretto vero e sarebbe uno spreco farne un interruttore: qui si
    chiede, e poi si aspetta di vedere se succede.
    """
    if davanti.status != "running" or dietro.status != "running":
        return ""
    voglia = voglia_di_obbedire(davanti, sim)
    davanti.scambio_a = dietro.driver_id
    if sim.rng.random() > voglia:
        davanti.scambio_rifiuto = True
        davanti.scambio_giro = davanti.lap + 3     # ci si riprova piu' avanti
        return "Sto andando piu' forte di lui, lasciatemi correre."
    davanti.scambio_rifiuto = False
    ritardo = ATTESA_MIN + int(round((ATTESA_MAX - ATTESA_MIN) * (1.0 - voglia)))
    davanti.scambio_giro = davanti.lap + ritardo
    if ritardo <= 1:
        return "Ricevuto, lo faccio passare."
    return "Ricevuto... fatemi provare ancora un giro."


def scambio_pronto(sim, davanti, dietro) -> bool:
    """Se l'ordine dato dal giocatore va eseguito adesso."""
    if davanti.scambio_a != dietro.driver_id or davanti.scambio_rifiuto:
        return False
    return davanti.lap >= davanti.scambio_giro


def chiudi_scambio(davanti) -> None:
    davanti.scambio_a = ""
    davanti.scambio_giro = 0
    davanti.scambio_rifiuto = False
