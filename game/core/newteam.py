"""Fondare una scuderia, e cosa vuol dire entrare in Formula 1 da zero.

Una squadra nuova non e' una squadra debole: e' un'altra cosa. Non ha una
fabbrica, non ha una galleria, non ha un simulatore, non ha nessuno che sappia
dove mettere le mani su quella macchina perche' quella macchina non l'ha mai
fatta nessuno. Non ha sponsor, perche' gli sponsor pagano per farsi vedere e
non c'e' ancora niente da vedere. E soprattutto non ha il montepremi: il piatto
del promoter si divide fra chi si e' classificato nei campionati scorsi, e chi
arriva adesso nei campionati scorsi non c'era.

In cambio deve pagare per entrare. La quota di anti-diluizione va agli undici
che ci sono gia', a compensarli del piatto che da qui in avanti si divide in
dodici invece che in undici. Sono i soldi che si mettono sul tavolo prima
ancora di aver disegnato un'ala.

E' andata cosi' alla Haas, che per due stagioni dal promoter non ha visto una
lira, ed e' andata cosi' alla Cadillac. Chi fonda una squadra qui dentro fa la
stessa strada.
"""
from __future__ import annotations

from .. import config as C
from ..model.car import Car
from ..model.team import Team

# Quanto si paga per entrare, e a chi va. Sta nel regolamento perche' e' una
# norma commerciale come le altre: la commissione puo' cambiarla.
QUOTA_INGRESSO = 450.0

# Per quante stagioni si e' una squadra nuova agli occhi del promoter. Il primo
# anno dal piatto non arriva niente, il secondo arriva la sola quota di merito,
# dal terzo si e' una squadra come le altre.
STAGIONI_DA_NUOVI = 2

# Il regolamento concede a chi entra di costruirsi le strutture: senza, con il
# limite normale in conto capitale una fabbrica non la si tira su in tempo.
CAPEX_INGRESSO = 190.0


# I tre modi in cui si entra in Formula 1. Cambia quanto si mette sul tavolo, e
# quindi cosa resta dopo aver pagato la quota.
PROFILI = {
    "costruttore": {
        "label": "Casa costruttrice",
        "capitale": 900.0,
        "reputation": 42.0,
        "budget_base": 130.0,
        "desc": "Un marchio dell'auto che entra in prima persona. La quota la "
                "paga senza battere ciglio e resta con mezzo miliardo per "
                "costruirsi la casa. In cambio non ci sono scuse.",
        "pu_capable": True,
        "livello_auto": -2.0,
        "strutture": 1.18,
    },
    "privato": {
        "label": "Progetto privato",
        "capitale": 650.0,
        "reputation": 30.0,
        "budget_base": 95.0,
        "desc": "Un gruppo di investitori con un piano industriale e un fondo "
                "dietro. La quota si porta via due terzi del capitale: quello "
                "che resta basta per una fabbrica onesta, non per due.",
        "pu_capable": False,
        "livello_auto": -3.5,
        "strutture": 1.0,
    },
    "garage": {
        "label": "Sfida da garage",
        "capitale": 600.0,
        "reputation": 22.0,
        "budget_base": 72.0,
        "desc": "Il modo in cui in Formula 1 ci si e' sempre entrati: un "
                "capannone, quattro persone brave e i soldi contati. Restano "
                "centocinquanta milioni: si sopravvive, non si corre.",
        "pu_capable": False,
        "livello_auto": -5.0,
        "strutture": 0.86,
    },
}

# Le strutture di chi comincia: si affitta la galleria di qualcun altro, il
# simulatore non c'e', e il capannone e' un capannone.
STRUTTURE_BASE = {
    "windtunnel": 26.0, "cfd": 44.0, "simulator": 18.0, "factory": 32.0,
    "aero_dept": 34.0, "design_office": 38.0, "pit_crew": 33.0,
    "academy": 0.0, "logistics": 42.0, "private_track": 0.0,
}


def entry_fee(gs) -> float:
    return float(gs.regulations.get("entry_fee_musd", QUOTA_INGRESSO))


def is_new(gs, team) -> bool:
    """Se agli occhi del promoter e' ancora una squadra appena entrata."""
    entrata = int(getattr(team, "entry_season", 0) or 0)
    return entrata > 0 and gs.season < entrata + STAGIONI_DA_NUOVI


def seasons_in(gs, team) -> int:
    """Da quante stagioni corre, contando questa."""
    entrata = int(getattr(team, "entry_season", 0) or 0)
    return 99 if entrata <= 0 else (gs.season - entrata + 1)


def prize_factor(gs, team) -> float:
    """Quanta parte del montepremi le spetta davvero.

    Il primo anno niente: non ci si e' classificati in nessuno dei campionati
    precedenti e il piatto si divide fra chi c'era. Il secondo anno arriva la
    sola quota di merito, quella legata a dove si e' arrivati. Dal terzo si
    conta come tutti.
    """
    if not is_new(gs, team):
        return 1.0
    return 0.0 if seasons_in(gs, team) <= 1 else 0.45


# Per quanti anni il regolamento lascia costruire piu' del normale a chi entra.
# Non due: una fabbrica, una galleria e un simulatore sono quattrocento milioni
# di lavori, e con il limite ordinario non si arriva in fondo nemmeno avendoli.
ANNI_DI_CANTIERE = 6


def capex_bonus(gs, team) -> float:
    """Quanto in piu' puo' costruire chi e' appena entrato.

    Massimo il primo anno, poi scende: quando la squadra dovrebbe reggersi da
    sola il regolamento smette di aiutarla, e da li' si costruisce coi propri
    soldi come tutti.
    """
    anni = seasons_in(gs, team)
    if anni > ANNI_DI_CANTIERE:
        return 0.0
    return round(CAPEX_INGRESSO * max(0.0, 1.0 - (anni - 1) / ANNI_DI_CANTIERE), 1)


# ------------------------------------------------------------------- fondare
def create(gs, spec: dict) -> Team:
    """Mette in griglia la dodicesima squadra, e le fa pagare l'ingresso."""
    profilo = PROFILI[spec.get("profilo", "privato")]
    tid = spec.get("id") or "nuova"
    quota = entry_fee(gs)
    capitale = float(spec.get("capitale", profilo["capitale"]))

    strutture = {k: (round(v * profilo["strutture"], 1) if v > 0 else 0.0)
                 for k, v in STRUTTURE_BASE.items()}
    # la macchina del primo anno sta sotto l'ultima della griglia: e' la prima
    # che si disegna e non l'ha mai vista girare nessuno. Cambio e freni no,
    # quelli si comprano gia' fatti da chi li fa per mezza Formula 1
    coda = min(t.car.parts[k].perf for t in gs.teams.values() for k in C.CAR_PARTS)
    pezzi = {k: round(max(40.0, coda + profilo["livello_auto"]
                          + (2.0 if k in ("gearbox", "brakes") else 0.0)), 1)
             for k in C.CAR_PARTS}

    motore = spec.get("engine") or _motorista_disponibile(gs)
    emergenza = False
    if motore is None:
        # nessuno ha posto e nessuno e' obbligato: si entra lo stesso, ma con
        # la fornitura che si riesce a strappare - specifica dell'anno prima e
        # prezzo da chi sa di averti in pugno
        from . import powertrain
        motore = min(gs.engine_makers,
                     key=lambda e: len(powertrain.customers_of(gs, e)))
        emergenza = True
    eng = gs.engine_makers[motore]
    team = Team(
        id=tid, name=spec.get("name", "Nuova Scuderia"),
        short=spec.get("short", "Nuova"), base=spec.get("base", "Europa"),
        colour=spec.get("colour", "#7C5CFF"), accent=spec.get("accent", "#F5C542"),
        founded=gs.season, engine=motore, works=False,
        reputation=profilo["reputation"], budget_base=profilo["budget_base"],
        cash=round(capitale - quota, 2), facilities=strutture,
        philosophy=spec.get("philosophy", "balance"),
        titles={"drivers": 0, "constructors": 0},
        pu_status="customer", pu_capable=profilo["pu_capable"],
        pu_reason=("Marchio dell'auto: il reparto motori si puo' fondare"
                   if profilo["pu_capable"] else
                   "Squadra cliente: la power unit si compra, non si costruisce"),
        last_position=len(gs.teams) + 1, heritage=False,
    )
    team.entry_season = gs.season
    team.car = Car.build(pezzi, eng, gs.regulations)
    team.is_player = True
    team.engine_customer_cost = eng.get("cost_per_customer", 25.0)
    if emergenza:
        team.engine_customer_cost = round(team.engine_customer_cost * 1.5, 2)
        team.pu_reason = ("Fornitura d'emergenza: nessun motorista aveva posto, "
                          "si corre con la specifica dell'anno scorso")
        team.pu_emergency = True
    team.resource_alloc = {k: 1.0 / len(C.CAR_PARTS) for k in C.CAR_PARTS}
    team.set_clock(gs.season, 1, 0)
    # niente e' vecchio e niente e' da rifare: e' tutto appena messo in piedi
    team.facility_age = {k: 0.0 for k in strutture}
    team.setup_knowledge = {}
    from .departments import starting_workforce
    team.workforce = starting_workforce(team)
    team.hired_this_season = {}
    gs.teams[team.id] = team

    # la quota di ingresso va agli altri, che da adesso il piatto lo dividono in
    # dodici: e' esattamente per questo che si chiama anti-diluizione
    altri = [t for t in gs.teams.values() if t.id != team.id]
    fetta = round(quota / max(1, len(altri)), 2)
    for t in altri:
        t.cash = round(t.cash + fetta, 2)
    gs.push(f"{team.name} e' iscritta al campionato. Quota di ingresso "
            f"{quota:.0f} M$, divisa fra le altre {len(altri)} squadre: "
            f"{fetta:.1f} M$ a testa.", "team")
    return team


def _motorista_disponibile(gs):
    """Chi il motore lo venderebbe: quello con meno clienti, se ha ancora posto."""
    from . import powertrain
    return powertrain.fornitore_libero(gs)


def suppliers(gs) -> list:
    """I motoristi a cui ci si puo' rivolgere, e quanti clienti hanno gia'."""
    fuori = []
    for eid, eng in gs.engine_makers.items():
        clienti = sum(1 for t in gs.teams.values() if t.engine == eid)
        fuori.append((eid, eng.get("name", eid.title()), clienti))
    return sorted(fuori, key=lambda x: (x[2], x[0]))


# ------------------------------------------------------ il primo schieramento
def first_lineup(gs, team) -> list:
    """Chi accetta di salire su una macchina che non ha mai girato.

    Non i migliori: quelli liberi. Un veterano che nessuno voleva piu' e un
    ragazzo che si gioca l'occasione - e' sempre stata questa la coppia con cui
    si entra in Formula 1.
    """
    liberi = sorted(gs.free_agents, key=lambda d: -d.overall)
    if not liberi:
        return []
    # uno che ha gia' corso, per sapere se la macchina va o non va: e' la prima
    # cosa che serve a chi una macchina non l'ha mai vista girare
    veterano = next((d for d in liberi if d.age >= 30), liberi[0])
    # e accanto un ragazzo, perche' costa poco e perche' l'occasione se la
    # prende dove gliela danno. Non il migliore dei giovani liberi: quello ha
    # di meglio da fare che salire su una macchina che non esiste
    giovani = [d for d in liberi if d.age <= 24 and d.id != veterano.id]
    giovane = (giovani[len(giovani) // 2] if giovani else
               next((d for d in liberi if d.id != veterano.id), None))
    presi = []
    for d in (veterano, giovane):
        if d is None:
            continue
        gs.free_agents.remove(d)
        gs.drivers[d.id] = d
        d.team = team.id
        d.seat = "race"
        # chi firma con una squadra che non esiste ancora si fa pagare il
        # rischio: il primo contratto e' sempre caro, e corto
        d.salary = round(d.salary * 1.25, 2)
        d.contract_until = gs.season
        team.drivers.append(d.id)
        presi.append(d)
    if presi:
        nomi = " e ".join(x.short for x in presi)
        gs.push(f"Primo schieramento: {nomi}. Contratti di un anno, pagati sopra "
                f"il loro valore: e' il prezzo per convincere qualcuno a salire "
                f"su una macchina che non ha mai girato.", "mercato")
    return presi


# ------------------------------------------------------- il nome se lo si fa
# Quanto ci mette una squadra a diventare quello che i risultati dicono che e'.
# Poco per volta: la considerazione si costruisce in anni, non in una stagione
# buona, ed e' il motivo per cui a una squadra nuova all'inizio dicono di no
# tutti - ingegneri, piloti, sponsor.
PASSO_REPUTAZIONE = 0.26


def target_reputation(gs, team, pos: int) -> float:
    """Quanto varrebbe il nome di questa squadra, visti i risultati."""
    n = max(2, len(gs.teams))
    merito = 45.0 + 42.0 * (n - max(1, min(n, pos))) / (n - 1)
    # quello che si e' vinto non lo toglie nessuno: vale meno di dove si sta
    # adesso, ma vale sempre
    merito += min(13.0, 1.4 * float(team.titles.get("constructors", 0))
                  + 0.8 * float(team.titles.get("drivers", 0)))
    if heritage_like(team):
        merito += 4.0
    # e comunque nessuno diventa un nome grosso in due anni: chi e' appena
    # entrato ha un tetto che si alza da solo, stagione dopo stagione
    anni = seasons_in(gs, team)
    if anni < 7:
        merito = min(merito, 28.0 + 10.0 * anni)
    return max(15.0, min(97.0, merito))


def heritage_like(team) -> bool:
    return bool(getattr(team, "heritage", False))


def drift_reputation(gs) -> list:
    """A fine stagione ogni squadra vale un po' di piu' o un po' di meno."""
    msgs = []
    ordine = gs.constructor_standings()
    for pos, team in enumerate(ordine, start=1):
        obiettivo = target_reputation(gs, team, pos)
        prima = float(team.reputation)
        team.reputation = round(prima + (obiettivo - prima) * PASSO_REPUTAZIONE, 1)
        if team.is_player and abs(team.reputation - prima) >= 0.6:
            verso = "cresciuta" if team.reputation > prima else "scesa"
            msgs.append(f"La considerazione della squadra e' {verso}: da "
                        f"{prima:.0f} a {team.reputation:.0f}. Si sente sul "
                        f"mercato, sugli sponsor e su chi accetta di venire.")
    return msgs


def welcome(gs, team) -> None:
    """Le righe che dicono al patron dove si e' cacciato."""
    gs.push(f"Dal promoter, quest'anno, non arrivera' niente: il piatto si "
            f"divide fra chi si e' classificato nei campionati scorsi. Si vive "
            f"di capitale e di sponsor, e gli sponsor vanno trovati.", "soldi")
    gs.push(f"Galleria del vento in affitto, niente simulatore, una fabbrica da "
            f"tirare su. Si hanno pero' tutte le ore aerodinamiche che il "
            f"regolamento concede all'ultima della classe: e' l'unico vantaggio "
            f"che c'e', e va speso.", "tecnico")
    gs.push(f"Cassa: {team.cash:.0f} M$. Costruire non passa dal tetto di spesa, "
            f"e a chi entra il regolamento concede {CAPEX_INGRESSO:.0f} M$ in "
            f"piu' in conto capitale per mettersi in pari.", "soldi")
