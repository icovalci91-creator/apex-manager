"""Il progetto della vettura dell'anno prossimo, e chi lo porta avanti.

Una monoposto non nasce a gennaio: nasce durante la stagione precedente,
mentre si corre con quella di adesso. Ogni ora che il reparto passa sul
progetto nuovo e' un'ora che non passa sulla macchina con cui si corre oggi,
ed e' la scelta che fa la differenza fra una squadra che vince adesso e una
che vincera' fra un anno.

Il patron non disegna la macchina. Il patron dice cosa vuole - piu' carico,
piu' efficienza, una vettura che le gomme non le mangi - e poi guarda cosa
gli portano. Fra quello che ha chiesto e quello che arriva ci sono il team
principal, che deve tenere insieme il reparto, e il direttore tecnico, che
deve tradurre una frase in una macchina. Piu' valgono, piu' quello che arriva
somiglia a quello che si era chiesto.
"""
from __future__ import annotations

from .. import config as C

# Le direzioni che si possono dare. Non sono componenti: sono le cose che un
# patron dice davvero in una riunione.
AREE = {
    "carico": {
        "label": "Piu' carico aerodinamico",
        "desc": "Una macchina che sta incollata nelle curve veloci. Si paga sui rettilinei.",
        "parts": {"floor": 0.34, "front_wing": 0.24, "rear_wing": 0.22, "sidepods": 0.12,
                  "chassis": 0.08},
    },
    "efficienza": {
        "label": "Piu' efficienza sui rettilinei",
        "desc": "Meno resistenza a parita' di carico: velocita' di punta e sorpassi.",
        "parts": {"rear_wing": 0.34, "sidepods": 0.28, "cooling": 0.22, "active_aero": 0.16},
    },
    "meccanica": {
        "label": "Piu' trazione e grip meccanico",
        "desc": "Sospensioni e telaio: la macchina che si appoggia sui cordoli e tira fuori.",
        "parts": {"suspension": 0.42, "chassis": 0.34, "gearbox": 0.24},
    },
    "gomme": {
        "label": "Piu' gentile con le gomme",
        "desc": "Una vettura che non le distrugge: meno soste, piu' gara.",
        "parts": {"suspension": 0.36, "chassis": 0.26, "floor": 0.22, "brakes": 0.16},
    },
    "affidabilita": {
        "label": "Piu' affidabilita'",
        "desc": "Meno rotture e meno usura. Non fa un decimo, fa arrivare in fondo.",
        "parts": {"cooling": 0.34, "gearbox": 0.30, "brakes": 0.22, "chassis": 0.14},
    },
}

# Quanto lavoro serve perche' il progetto nuovo valga davvero qualcosa. E' la
# stessa scala del resto: un milione dirottato per una stagione intera fa una
# macchina sensibilmente diversa, non una rivoluzione.
WORK_TO_PERF = 0.42

# La forbice vera di reparti fra l'ultima e la prima della griglia, e quanto
# quella forbice moltiplica il progetto dell'anno nuovo. Piu' larga di quella
# della stagione, ed e' voluto: d'inverno si sbaglia o si azzecca il concetto,
# e quello vale per dodici mesi.
PROGETTO_MIN, PROGETTO_MAX = 62.0, 92.0
PROGETTO_RESA = (0.70, 1.55)


def brief_of(team) -> dict:
    """Le indicazioni date al reparto, normalizzate."""
    b = team.next_car_brief or {}
    tot = sum(max(0.0, b.get(k, 0.0)) for k in AREE)
    if tot <= 0:
        return {k: 1.0 / len(AREE) for k in AREE}
    return {k: max(0.0, b.get(k, 0.0)) / tot for k in AREE}


def set_brief(team, area: str, valore: float) -> None:
    if team.next_car_brief is None:
        team.next_car_brief = {k: 1.0 for k in AREE}
    team.next_car_brief[area] = max(0.0, min(5.0, float(valore)))


def fidelity(team) -> float:
    """Quanto quello che arriva somiglia a quello che si era chiesto, da 0 a 1.

    Fra il patron e la macchina ci sono due persone. Il direttore tecnico deve
    tradurre una richiesta in un progetto, il team principal deve far remare
    tutti nella stessa direzione: se sono bravi il reparto fa quello che si e'
    chiesto, se non lo sono fa quello che gli riesce.
    """
    td = team._s("technical_director", "development", 55.0)
    com = team._s("technical_director", "communication", 55.0)
    tp = team._s("team_principal", "management", 55.0)
    q = 0.45 * td + 0.25 * com + 0.30 * tp
    return max(0.20, min(0.97, (q - 40.0) / 52.0))


def work_of(team) -> dict:
    if team.next_car_work is None:
        team.next_car_work = {k: 0.0 for k in AREE}
    for k in AREE:
        team.next_car_work.setdefault(k, 0.0)
    return team.next_car_work


def total_work(team) -> float:
    return round(sum(work_of(team).values()), 2)


def invest(gs, team, budget: float) -> None:
    """Manda un pezzo di budget sul progetto dell'anno prossimo.

    Va dove si e' chiesto che vada, ma non tutto: la quota che si perde per
    strada la decidono le persone che stanno in mezzo, e finisce sparsa dove
    capita - che e' esattamente come nasce una macchina che non e' quella che
    si era immaginata.
    """
    if budget <= 0:
        return
    lavoro = work_of(team)
    b = brief_of(team)
    f = fidelity(team)
    reso = budget * team.dev_rate
    for area, quota in b.items():
        # la parte fedele va dove si e' chiesto, il resto si spalma
        lavoro[area] += reso * (f * quota + (1.0 - f) / len(AREE))


def resa_progetto(team) -> float:
    """Quanto rende, su una macchina nuova, avere gli strumenti e la gente giusta.

    E' l'inverno il momento in cui una galleria che correla vale davvero: in
    stagione si limano pezzi su una macchina che c'e' gia' e il margine di
    manovra e' quello che e', d'inverno si decide *che macchina sara'*, e un
    errore di concetto lo si porta per dodici mesi. Chi ha gli strumenti per
    vedere in anticipo che la strada e' sbagliata arriva a marzo con la
    macchina giusta, e questo si ripete anno dopo anno.

    Prima la forbice fra l'ultima e la prima della griglia era del 22%, e non
    bastava a spiegare perche' sono sempre le stesse squadre ad arrivarci.
    """
    forza = (0.45 * team.aero_strength + 0.35 * team.mech_strength
             + 0.20 * (team.pu_strength if team.works else 60.0))
    q = max(0.0, min(1.0, (forza - PROGETTO_MIN) / (PROGETTO_MAX - PROGETTO_MIN)))
    lo, hi = PROGETTO_RESA
    return lo + (hi - lo) * q


def projection(gs, team) -> dict:
    """Che macchina verra' fuori, area per area, in punti di prestazione."""
    lavoro = work_of(team)
    resa = resa_progetto(team)
    return {k: round(v * WORK_TO_PERF * resa, 2) for k, v in lavoro.items()}


def expected_gain(gs, team) -> float:
    """Quanto salira' in media la vettura, in punti."""
    proj = projection(gs, team)
    somma = 0.0
    for area, punti in proj.items():
        for parte, peso in AREE[area]["parts"].items():
            somma += punti * peso
    return round(somma / max(1, len(C.CAR_PARTS)), 2)


def build(gs, team) -> list:
    """A fine stagione il progetto diventa la macchina con cui si correra'.

    Quello che si e' accumulato si scarica sui componenti, area per area. Non
    e' un premio uguale per tutti: dipende da quanto si e' investito, da quanto
    valgono i reparti e da quanto il reparto ha davvero seguito la linea.
    """
    proj = projection(gs, team)
    if sum(proj.values()) <= 0.01:
        work_of(team).clear()
        return []
    delta = {k: 0.0 for k in team.car.parts}
    for area, punti in proj.items():
        for parte, peso in AREE[area]["parts"].items():
            if parte in delta:
                delta[parte] += punti * peso
    for parte, d in delta.items():
        if d > 0:
            team.car.parts[parte].perf = min(99.5, team.car.parts[parte].perf + d)
    media = expected_gain(gs, team)
    team.next_car_work = {k: 0.0 for k in AREE}
    if not team.is_player:
        return []
    forte = max(proj, key=proj.get)
    debole = min(proj, key=proj.get)
    return [f"La vettura nuova e' in pista: {media:+.1f} di media. "
            f"Il lavoro si sente soprattutto su {AREE[forte]['label'].lower()}, "
            f"molto meno su {AREE[debole]['label'].lower()}."]


def ai_brief(gs, team) -> None:
    """Che linea da' una squadra del computer al proprio reparto.

    Si chiede quello che manca, non quello che si ha gia': e' il motivo per cui
    una squadra che soffre in trazione l'anno dopo arriva con un'altra
    sospensione.
    """
    from . import engineering
    prof = engineering.car_profile(team, gs)
    mappa = {"carico": "carico", "efficienza": "efficienza",
             "meccanica": "trazione", "gomme": "gomme", "affidabilita": "affidabilita"}
    b = {}
    for area, chiave in mappa.items():
        valore = prof.get(chiave, 70.0)
        b[area] = max(0.3, min(4.0, 3.4 - (valore - 60.0) / 14.0))
    team.next_car_brief = b


def end_season(gs) -> list:
    """Tutte le macchine nuove scendono in pista insieme."""
    msgs = []
    for team in gs.teams.values():
        msgs += build(gs, team)
        if not team.is_player:
            ai_brief(gs, team)
    msgs += vetture_cliente(gs)
    return msgs


# Quanto vale il telaio comprato rispetto a quello del costruttore: non e' la
# stessa macchina - arriva piu' tardi, la si conosce meno e l'aerodinamica va
# rifatta attorno alle proprie fiancate - ma e' un altro pianeta rispetto a
# quello che una squadra piccola disegna da sola.
QUOTA_CLIENTE = 0.94


def vetture_cliente(gs) -> list:
    """Chi si compra il telaio da un altro, quando il regolamento lo permette.

    E' la proposta che torna ogni volta che una squadra piccola rischia di
    chiudere: invece di disegnare una macchina che non ha i mezzi per
    disegnare, si compra quella di chi il mezzo ce l'ha. Le ultime quattro
    della classifica che non costruiscono la power unit prendono il telaio dal
    proprio motorista, e la griglia si accorcia di brutto.
    """
    if not gs.regulations.get("customer_cars_allowed"):
        return []
    from . import powertrain
    msgs = []
    for team in gs.constructor_standings()[-4:]:
        if team.works:
            continue          # chi costruisce il motore il telaio se lo fa da solo
        donatore = powertrain.builder_of(gs, team.engine)
        if donatore is None or donatore is team:
            continue
        salto = 0.0
        for chiave, parte in team.car.parts.items():
            arrivo = donatore.car.parts.get(chiave)
            if arrivo is None:
                continue
            comprato = arrivo.perf * QUOTA_CLIENTE
            if comprato > parte.perf:
                salto += comprato - parte.perf
                parte.perf = round(comprato, 1)
        if salto > 0.5:
            msgs.append(f"{team.short} corre con il telaio {donatore.short}: "
                        f"{salto / max(1, len(team.car.parts)):+.1f} di media sulla vettura.")
            gs.push(msgs[-1], "tecnico")
    return msgs
