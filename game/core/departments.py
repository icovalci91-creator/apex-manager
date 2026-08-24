"""L'organico dei reparti: quanti ingegneri lavorano, e dove.

Un capo aerodinamico da solo non disegna una macchina. Dietro ogni nome che
compare nell'organigramma ci sono decine di persone, e quante sono conta
quanto quanto sono bravi quelli che le dirigono: e' la ragione per cui una
squadra che assume duecento persone in due anni cambia passo, e per cui il
tetto di spesa ha costretto tutti a tagliare.

Qui l'organico e' un numero per reparto. Si assume e si licenzia, costa uno
stipendio che sta dentro il tetto di spesa, e moltiplica quello che sanno i
responsabili: tanti mediocri non valgono un fuoriclasse, ma un fuoriclasse
senza nessuno sotto non produce niente.
"""
from __future__ import annotations

from . import economy

# Ogni reparto ha una dimensione di riferimento - quella di una squadra di
# vertice in salute - un costo per persona e il responsabile che lo dirige.
# I numeri sono ingegneri e tecnici, non l'organico totale della fabbrica.
REPARTI = {
    "aero": {
        "label": "Aerodinamica",
        "desc": "Galleria, CFD, superfici. E' il reparto che decide quanto carico ha la macchina.",
        "ref": 90, "cost": 0.094, "boss": "head_of_aero",
    },
    "progetto": {
        "label": "Progettazione",
        "desc": "Telaio, sospensioni, trasmissione: quello che sta sotto la carrozzeria.",
        "ref": 70, "cost": 0.102, "boss": "chief_designer",
    },
    "powertrain": {
        "label": "Powertrain",
        "desc": "Chi costruisce il motore ne ha bisogno; chi lo compra tiene solo "
                "il gruppo che lo integra nella vettura.",
        "ref": 50, "cost": 0.107, "boss": "head_of_powertrain",
    },
    "simulazione": {
        "label": "Simulazione e dati",
        "desc": "Modelli, correlazione, simulatore. Non fanno pezzi: fanno capire "
                "se i pezzi funzioneranno.",
        "ref": 45, "cost": 0.098, "boss": "technical_director",
    },
    "affidabilita": {
        "label": "Qualita' e affidabilita'",
        "desc": "Banchi, controlli, materiali. Si vede solo quando manca.",
        "ref": 35, "cost": 0.086, "boss": "chief_mechanic",
    },
}

# Quanto un reparto sottodimensionato o sovradimensionato sposta la resa dei
# suoi responsabili. Alla dimensione di riferimento vale 1: sotto si fatica,
# sopra si guadagna, ma con rendimenti decrescenti perche' oltre un certo punto
# le persone si intralciano invece di aiutarsi.
FLOOR = 0.62
SPAN = 0.38
CURVE = 0.55

# Assumere non e' istantaneo e non e' gratis: si cercano, si formano, e quelli
# bravi si portano via da qualcun altro.
RECRUIT_FEE = 0.30        # M$ una tantum per persona
SEVERANCE = 0.55          # quote di stipendio annuo per chi se ne va
MAX_GROWTH = 0.28         # quanto puo' crescere un reparto in una stagione


def ref_for(team, area: str) -> int:
    """Quanta gente serve davvero a questa squadra in quel reparto.

    Chi compra il motore non ha bisogno di cinquanta motoristi: gli basta il
    gruppo che lo integra nella vettura. Ma dal giorno in cui decide di
    costruirselo, il metro torna quello di tutti gli altri.
    """
    ref = REPARTI[area]["ref"]
    if area == "powertrain" and not team.works and not team.pu_building:
        return max(8, int(ref * 0.34))
    return ref


def size_factor(team, area: str) -> float:
    """Da 0.62 a circa 1.2: quanto l'organico moltiplica i suoi responsabili."""
    n = headcount(team, area)
    return round(FLOOR + SPAN * (n / max(1.0, ref_for(team, area))) ** CURVE, 4)


def headcount(team, area: str) -> int:
    return int((getattr(team, "workforce", None) or {}).get(area, 0))


def total_headcount(team) -> int:
    return sum(headcount(team, a) for a in REPARTI)


def area_cost(team, area: str) -> float:
    """Costo annuo di quel reparto."""
    return round(headcount(team, area) * REPARTI[area]["cost"], 2)


def payroll(team) -> float:
    """Costo annuo di tutto l'organico. Sta dentro il tetto di spesa."""
    return round(sum(area_cost(team, a) for a in REPARTI), 2)


def needed(team, area: str) -> int:
    """Quanta gente servirebbe per stare alla dimensione di riferimento."""
    return max(0, ref_for(team, area) - headcount(team, area))


def hiring_room(team, area: str) -> int:
    """Quanti se ne possono assumere ancora quest'anno.

    Una squadra non raddoppia un reparto in un inverno: le persone brave sono
    poche, hanno un preavviso da rispettare e vanno formate.
    """
    base = max(6, int(REPARTI[area]["ref"] * MAX_GROWTH))
    fatte = int((getattr(team, "hired_this_season", None) or {}).get(area, 0))
    return max(0, base - fatte)


def hire_cost(team, area: str, quanti: int) -> float:
    """Quanto costa metterli dentro: ricerca adesso, stipendio da qui a dicembre."""
    return round(quanti * (RECRUIT_FEE + REPARTI[area]["cost"] * 0.5), 2)


def can_hire(gs, team, area: str, quanti: int) -> tuple:
    if quanti <= 0:
        return False, "Serve almeno una persona."
    if quanti > hiring_room(team, area):
        return False, (f"Non si assume piu' di cosi' in una stagione: "
                       f"restano {hiring_room(team, area)} posti.")
    prezzo = hire_cost(team, area, quanti)
    ok, why = economy.can_afford(team, prezzo, gs)
    if not ok:
        return False, why
    # lo stipendio dell'anno prossimo deve starci nel tetto, non solo la ricerca
    if payroll(team) + quanti * REPARTI[area]["cost"] > economy.cap_limit(gs) * 0.62:
        return False, "Con questo organico il monte stipendi mangerebbe il tetto di spesa."
    return True, ""


def hire(gs, team, area: str, quanti: int) -> tuple:
    ok, why = can_hire(gs, team, area, quanti)
    if not ok:
        return False, why
    prezzo = hire_cost(team, area, quanti)
    team.add_expense(f"Assunzioni {REPARTI[area]['label'].lower()}", prezzo,
                     in_cap=True, category="personale")
    if team.workforce is None:
        team.workforce = {}
    team.workforce[area] = headcount(team, area) + quanti
    if team.hired_this_season is None:
        team.hired_this_season = {}
    team.hired_this_season[area] = int(team.hired_this_season.get(area, 0)) + quanti
    return True, (f"{quanti} persone in piu' in {REPARTI[area]['label'].lower()}: "
                  f"il reparto sale a {team.workforce[area]}.")


def release(gs, team, area: str, quanti: int) -> tuple:
    """Manda a casa parte di un reparto. Costa la buonuscita e si sente subito."""
    n = headcount(team, area)
    quanti = min(quanti, n)
    if quanti <= 0:
        return False, "Non c'e' nessuno da mandare via."
    costo = round(quanti * REPARTI[area]["cost"] * SEVERANCE, 2)
    ok, why = economy.can_afford(team, costo, gs, check_cap=False)
    if not ok:
        return False, why
    team.add_expense(f"Buonuscite {REPARTI[area]['label'].lower()}", costo,
                     in_cap=False, category="personale")
    team.workforce[area] = n - quanti
    return True, (f"{quanti} persone lasciano {REPARTI[area]['label'].lower()}: "
                  f"restano in {team.workforce[area]}, e si risparmiano "
                  f"{quanti * REPARTI[area]['cost']:.1f} M$ all'anno.")


def new_season(gs) -> None:
    """Il conto delle assunzioni riparte a gennaio."""
    for team in gs.teams.values():
        team.hired_this_season = {}


def starting_workforce(team) -> dict:
    """L'organico di partenza, tarato su quanto vale la squadra.

    Non e' un dato inventato a tavolino: si ricava dalla reputazione e dal
    budget, che sono le stesse cose da cui dipende quanta gente ci si puo'
    permettere. Una squadra di vertice sta intorno al riferimento, una di coda
    poco sopra la meta'.
    """
    # la fabbrica e la reputazione dicono quanto e' grande davvero una squadra:
    # dietro una galleria del vento di prim'ordine c'e' sempre molta gente
    fac = sum(team.facilities.values()) / max(1, len(team.facilities))
    q = 0.55 * fac / 100.0 + 0.45 * team.reputation / 100.0
    scala = max(0.42, min(1.20, (q / 0.86) ** 1.7))
    out = {}
    for area, meta in REPARTI.items():
        n = ref_for(team, area) * scala
        out[area] = max(6, int(round(n)))
    return out


# ------------------------------------------------------------------ computer
def ai_plan(gs) -> list:
    """Le scuderie del computer dimensionano l'organico su quello che incassano.

    E' la storia del tetto di spesa: chi ha soldi assume, chi non ne ha taglia,
    e i tagli si vedono in pista due anni dopo.
    """
    news = []
    for team in gs.teams.values():
        if team.is_player:
            continue
        avanzo = economy.season_room(gs, team)
        fame = economy.spending_appetite(gs, team)
        # quanto puo' reggere di monte stipendi: quello che avanza dopo i costi
        # inevitabili, piu' il capitale che ha in cassa
        sostenibile = payroll(team) + avanzo * (0.25 + 0.35 * fame) - 18.0
        if sostenibile > payroll(team) * 1.04:
            area = min(REPARTI, key=lambda a: size_factor(team, a))
            quanti = min(hiring_room(team, area),
                         int((sostenibile - payroll(team)) / REPARTI[area]["cost"] * 0.5))
            if quanti >= 4:
                ok, _m = hire(gs, team, area, quanti)
                if ok:
                    news.append(f"{team.short} assume {quanti} persone in "
                                f"{REPARTI[area]['label'].lower()}.")
        elif sostenibile < payroll(team) * 0.88:
            area = max(REPARTI, key=lambda a: size_factor(team, a))
            quanti = int((payroll(team) - max(0.0, sostenibile)) / REPARTI[area]["cost"] * 0.35)
            # sotto una certa soglia un reparto non esiste piu': si taglia
            # fino a li' e poi si taglia altrove
            minimo = max(8, int(ref_for(team, area) * 0.40))
            quanti = min(quanti, max(0, headcount(team, area) - minimo))
            if quanti >= 4:
                ok, _m = release(gs, team, area, quanti)
                if ok:
                    news.append(f"{team.short} taglia {quanti} posti in "
                                f"{REPARTI[area]['label'].lower()}: i conti non tornano.")
    return news
