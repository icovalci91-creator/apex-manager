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
    """Quanto stringe la cinghia dopo una stagione chiusa in perdita."""
    return scheda(team)["stretta"]
