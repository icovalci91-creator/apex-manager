"""Di chi e' una squadra, e cosa cambia.

In Formula 1 non si e' proprietari allo stesso modo, e non e' un dettaglio da
organigramma: decide da dove arrivano i soldi, dove vanno quelli che avanzano,
e quanto si e' disposti a perdere prima di tirare il freno.

Una casa costruttrice corre per vendere macchine: mette dentro quello che
serve senza guardare il conto commerciale, ma l'utile risale al gruppo e il
consiglio giudica il programma per quello che rende al marchio - e quando
smette di rendere si chiude, come hanno chiuso Honda, BMW e Toyota. Un marchio
che non fa automobili corre per farsi vedere: e' un budget di marketing, e
finche' la vetrina funziona nessuno chiede dividendi. Un fondo ci ha messo dei
soldi per rivederli piu' grossi: paga meno di tasca sua, si porta a casa
l'utile e sulle perdite non ha pazienza. E poi c'e' il padrone: uno che ha
comprato una squadra con i propri soldi, che non deve rendere conto a nessuno
e a cui nessuno porta via l'utile, ma che ha le tasche che ha.

E' anche il modo in cui il giocatore entra: una squadra fondata da lui e' sua,
di un proprietario solo.
"""
from __future__ import annotations

TIPI = {
    "costruttore": {
        "label": "Casa costruttrice",
        "desc": "Corre per vendere macchine. Il gruppo mette quello che serve, "
                "l'utile risale, e il consiglio giudica il programma per quanto "
                "rende al marchio.",
        # quanto piu' del normale mette chi sta dietro
        "apporto": 1.25,
        # quanta parte dell'utile esce a fine anno
        "dividendo": 0.85,
        # quanto stringe dopo una stagione in perdita. Poco: per un gruppo
        # industriale il programma e' una voce di marketing e la perdita si
        # assorbe. Un consiglio d'amministrazione non taglia il budget di un
        # milione alla volta - o finanzia, o chiude tutto, come hanno chiuso
        # Honda, BMW e Toyota. Con la stretta severa che aveva prima, unita al
        # dividendo alto, era una tenaglia: l'utile usciva e quindi non si
        # costruiva mai un cuscinetto, poi qualunque perdita stringeva. Misurato
        # su sei stagioni, l'Audi arrivava a mezzo budget con la stretta che
        # saliva di anno in anno senza tornare piu' giu'.
        "stretta": 0.75,
    },
    "marchio": {
        "label": "Marchio",
        "desc": "Corre per farsi vedere: e' un budget di marketing. Finche' la "
                "vetrina funziona nessuno chiede dividendi.",
        "apporto": 1.15,
        "dividendo": 0.35,
        "stretta": 0.80,
    },
    "fondo": {
        "label": "Fondo d'investimento",
        "desc": "Ci ha messo dei soldi per rivederli piu' grossi. Paga meno di "
                "tasca sua, si porta a casa l'utile, e sulle perdite non ha "
                "pazienza.",
        "apporto": 0.85,
        "dividendo": 1.00,
        "stretta": 1.40,
    },
    "padrone": {
        "label": "Proprietario unico",
        "desc": "Una persona sola, i suoi soldi, le sue decisioni. Nessuno gli "
                "porta via l'utile e nessuno gli chiude il programma, ma ha le "
                "tasche che ha.",
        "apporto": 0.70,
        "dividendo": 0.30,
        "stretta": 0.70,
    },
}

DEFAULT = "fondo"

# ---------------------------------------------------------- i numeri
# Il tipo dice che razza di proprieta' e'; questi dicono chi e' quella
# proprieta' li'. Sono quattro numeri da 1 a 10, come si fa nei gestionali di
# calcio, e ognuno ha un effetto che si vede:
#
#   ricchezza   quanto puo' mettere in una stagione, in milioni. Non e' il
#               budget della squadra: quello lo fanno montepremi e sponsor. E'
#               quello che il proprietario aggiunge di tasca sua.
#   ambizione   quanto vuole vincere, e quindi quanta parte di quel massimo
#               tira fuori davvero. Un ambizioso mette tutto anche stando
#               bene; uno tranquillo aspetta di essere in difficolta'.
#   pazienza    quanto regge le stagioni storte prima di stringere la cinghia.
#   visione     dove vanno i soldi che mette: sul pacchetto di domenica
#               prossima (1) o sulla fabbrica dei prossimi cinque anni (10).
#
# Il senso, che e' quello che mancava: montepremi e sponsor coprono la
# stagione, e basta. A far crescere una squadra e' il proprietario. Prima non
# esisteva questo passaggio, i soldi venivano solo dai risultati, e quindi chi
# vinceva continuava a vincere: su ventiquattro stagioni misurate la McLaren
# ne vinceva venti.
ATTRIBUTI = ("ricchezza", "ambizione", "pazienza", "visione")

ETICHETTE = {
    "ricchezza": "Ricchezza",
    "ambizione": "Ambizione",
    "pazienza": "Pazienza",
    "visione": "Visione",
}

SPIEGA = {
    "ricchezza": "Quanto puo' mettere in una stagione, oltre a quello che la "
                 "squadra guadagna da sola.",
    "ambizione": "Quanto vuole vincere: da questo dipende quanta parte di quel "
                 "massimo tira fuori davvero.",
    "pazienza": "Quante stagioni storte regge prima di stringere la cinghia.",
    "visione": "Dove mette i soldi: sul pacchetto della prossima gara o sulla "
               "fabbrica dei prossimi cinque anni.",
}

# Da 1 a 10 a milioni l'anno. Non e' lineare: fra il nono e il decimo c'e' piu'
# differenza che fra il primo e il quinto, che e' come stanno le cose davvero.
# Il tetto sta a centocinquanta e non a trecento perche' e' l'ordine di
# grandezza vero - quello che un proprietario ambizioso mette in una squadra di
# Formula 1 in un anno, fabbrica compresa - e perche' oltre quella cifra, con
# il tetto di spesa in mezzo, tutti arrivavano al massimo consentito e la
# differenza fra le squadre spariva: e un campionato dove il denaro non conta
# piu' non e' piu' giocabile di uno dove conta solo lui.
DENARO = (5.0, 10.0, 16.0, 24.0, 35.0, 48.0, 65.0, 88.0, 115.0, 150.0)

# Da che intervalli si pesca ogni numero, per tipo di proprieta'. Una casa
# costruttrice e' ricca e paziente ma non e' li' per vincere a ogni costo; un
# fondo ha i soldi e nessuna pazienza; un padrone ha le tasche che ha ma non
# deve rendere conto a nessuno.
INTERVALLI = {
    "costruttore": {"ricchezza": (7, 10), "ambizione": (5, 9),
                    "pazienza": (5, 9), "visione": (6, 10)},
    "marchio":     {"ricchezza": (5, 8), "ambizione": (4, 8),
                    "pazienza": (6, 9), "visione": (4, 8)},
    "fondo":       {"ricchezza": (6, 9), "ambizione": (6, 10),
                    "pazienza": (2, 5), "visione": (2, 6)},
    "padrone":     {"ricchezza": (2, 7), "ambizione": (5, 10),
                    "pazienza": (6, 10), "visione": (3, 8)},
}


def numeri(team) -> dict:
    """I quattro numeri del proprietario di questa squadra."""
    d = getattr(team, "owner_stats", None) or {}
    return {a: int(max(1, min(10, d.get(a, 5)))) for a in ATTRIBUTI}


def genera(rng, tipo: str, reputazione: float = 70.0) -> dict:
    """Pesca i numeri di un proprietario di questo tipo.

    La reputazione della squadra sposta la ricchezza: dietro a un nome grosso
    c'e' quasi sempre qualcuno che i soldi ce li ha davvero, e non e' un caso -
    e' il motivo per cui quel nome e' diventato grosso.
    """
    intervalli = INTERVALLI.get(tipo, INTERVALLI[DEFAULT])
    out = {}
    for a, (lo, hi) in intervalli.items():
        v = rng.randint(lo, hi)
        if a == "ricchezza":
            v += int(round((reputazione - 70.0) / 15.0))
        out[a] = int(max(1, min(10, v)))
    return out


def massimo_annuo(team) -> float:
    """Quanti milioni puo' mettere, al massimo, in una stagione."""
    return DENARO[numeri(team)["ricchezza"] - 1]

# Con che proprieta' nasce una squadra fondata dal giocatore, a seconda di come
# ci e' entrato. Chi entra da garage e' padrone di se stesso: e' il modo in cui
# in Formula 1 ci si e' sempre entrati.
DA_PROFILO = {"costruttore": "costruttore", "privato": "fondo", "garage": "padrone"}


def tipo_di(team) -> str:
    t = getattr(team, "proprieta", "") or DEFAULT
    return t if t in TIPI else DEFAULT


def scheda(team) -> dict:
    return TIPI[tipo_di(team)]


def etichetta(team) -> str:
    return scheda(team)["label"]


def apporto(team) -> float:
    """Quanto piu' (o meno) del normale mette chi sta dietro a questa squadra."""
    return scheda(team)["apporto"]


def dividendo(team) -> float:
    """Quanta parte dell'utile esce a fine anno."""
    return scheda(team)["dividendo"]


def stretta(team) -> float:
    """Quanto stringe la cinghia dopo una stagione chiusa in perdita.

    Non e' piu' un numero per tipo di proprieta': lo dice la pazienza di
    questo proprietario qui. Un consiglio d'amministrazione paziente assorbe
    la perdita e va avanti, un fondo con la pazienza corta taglia subito.
    """
    return round(1.55 - 0.11 * numeri(team)["pazienza"], 2)


def quota_investita(team, posizione: int, squadre: int) -> float:
    """Quanta parte del suo massimo mette davvero quest'anno, da 0 a 1.

    Due cose la muovono. L'ambizione, che e' quanto uno vuole vincere: chi ce
    l'ha alta mette mano al portafoglio anche quando le cose vanno bene. E
    dove sta la squadra: un proprietario che si ritrova ultimo o paga o vende,
    ed e' esattamente il momento in cui nella realta' arrivano i soldi veri.
    """
    n = max(2, int(squadre))
    pos = max(1, min(n, int(posizione or n)))
    dietro = (pos - 1) / (n - 1.0)
    base = 0.20 + 0.08 * (numeri(team)["ambizione"] - 1)
    # E la posizione pesa molto piu' dell'ambizione, non alla pari. Chi vince
    # si finanzia da solo: il suo proprietario incassa il dividendo, non firma
    # assegni. Con le due cose alla pari succedeva il contrario di quello che
    # serve - la squadra davanti ha il nome grosso, quindi il proprietario
    # ricco, quindi metteva piu' di tutti - e la classifica restava congelata
    # come prima.
    return round(max(0.0, min(1.0, base * (0.20 + 1.45 * dietro))), 3)


def quota_fabbrica(team) -> float:
    """Quanta parte dei soldi del proprietario va nelle strutture, da 0 a 1.

    E' la visione: chi guarda lontano tira su la fabbrica, chi guarda alla
    domenica prossima paga il pacchetto nuovo.
    """
    return round(0.15 + 0.06 * (numeri(team)["visione"] - 1), 3)


def riassunto(team) -> str:
    """Una riga che dice chi e' questo proprietario, senza guardare i numeri."""
    d = numeri(team)
    soldi = ("senza mezzi", "con poco", "con qualcosa da parte", "solido",
             "ricco", "molto ricco")[min(5, (d["ricchezza"] - 1) // 2)]
    voglia = ("non ha fretta", "vuole crescere", "vuole vincere",
              "vuole vincere adesso")[min(3, (d["ambizione"] - 1) // 3)]
    testa = "guarda lontano" if d["visione"] >= 7 else (
        "guarda alla prossima gara" if d["visione"] <= 4 else "tiene i piedi per terra")
    calma = "paziente" if d["pazienza"] >= 7 else (
        "senza pazienza" if d["pazienza"] <= 3 else "di pazienza normale")
    return f"{etichetta(team)}, {soldi}: {voglia}, {testa}, {calma}."
