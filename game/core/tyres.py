"""Le gomme del weekend: cosa porta il fornitore, e quante se ne sceglie ciascuno.

Prima di ogni gran premio il fornitore nomina tre mescole della sua gamma - la
piu' dura, la media e la morbida di quel fine settimana - scelte in base a
quanta energia il tracciato mette nelle gomme: a Losail e a Barcellona le piu'
dure, a Monaco e a Las Vegas le piu' morbide.

Poi ogni squadra decide come riempire i tredici set che le spettano. Tre sono
obbligati dal regolamento: due mescole diverse tenute per la gara e un set
della morbida riservato al Q3. Gli altri dieci se li divide come vuole, e la
scelta va comunicata prima di arrivare in pista, dopodiche' la federazione
pubblica quella di tutti. Da li' in avanti si corre con quello che si e'
portato: chi ha caricato morbide fa un giro secco migliore e finisce le gomme
in gara, chi ha caricato dure vive il venerdi' peggio e la domenica meglio.
"""
from __future__ import annotations

# La gamma del fornitore: C1 e' la piu' dura, C5 la piu' morbida. Nel 2026 le
# mescole tornano a essere cinque: la C6 provata nel 2025 non c'e' piu'.
GAMMA = ("C1", "C2", "C3", "C4", "C5")
MESCOLE = ("soft", "medium", "hard")
LABEL = {"soft": "Morbida", "medium": "Media", "hard": "Dura"}

SETS_GP = 13              # set a disposizione in un weekend normale
SETS_SPRINT = 12          # nel weekend con la sprint se ne portano meno
# Quelli che il regolamento decide al posto tuo: due mescole diverse messe da
# parte per la gara e una morbida che si puo' usare solo in Q3.
OBBLIGATORI = {"hard": 1, "medium": 1, "soft": 1}

# Quanto una mescola della gamma dura rispetto a un'altra: la C1 e' un
# macigno che non finisce mai, la C5 si consuma guardandola.
def life_scale(c: int) -> float:
    return round(1.16 - 0.06 * c, 3)


def nomination(track) -> dict:
    """Le tre mescole portate su questo circuito, come numeri di gamma.

    Le sceglie l'energia che il tracciato mette nelle gomme: dove si scalda e
    si consuma si va sul duro, dove serve grip e non si consuma si va sul
    morbido. E' il motivo per cui a Monaco corrono con mescole che a
    Silverstone durerebbero mezzo giro.
    """
    wear = float(track.traits.get("tyre_wear", 0.6))
    dura = max(1, min(len(GAMMA) - 2, int(round(1 + 3.4 * (1.0 - wear)))))
    return {"hard": dura, "medium": dura + 1, "soft": dura + 2}


def nomination_label(track) -> str:
    n = nomination(track)
    return " - ".join(GAMMA[n[m] - 1] for m in ("hard", "medium", "soft"))


def total_sets(track) -> int:
    return SETS_SPRINT if getattr(track, "sprint", False) else SETS_GP


def free_sets(track) -> int:
    return total_sets(track) - sum(OBBLIGATORI.values())


def is_valid(track, scelta: dict) -> tuple:
    """Una scelta sta in piedi se i conti tornano. Ritorna (va bene, perche')."""
    if any(scelta.get(m, 0) < 0 for m in MESCOLE):
        return False, "Non si possono scegliere set negativi."
    n = sum(scelta.get(m, 0) for m in MESCOLE)
    liberi = free_sets(track)
    if n != liberi:
        return False, f"Vanno assegnati esattamente {liberi} set liberi: ne hai messi {n}."
    return True, ""


def full_stock(track, scelta: dict) -> dict:
    """I set totali per pilota: quelli scelti piu' quelli obbligatori."""
    return {m: int(scelta.get(m, 0)) + OBBLIGATORI[m] for m in MESCOLE}


# ------------------------------------------------------------------ le scelte
def suggested(track, aggressivita: float = 0.5) -> dict:
    """Come la riempirebbe un ingegnere di gara.

    Dove le gomme si consumano si portano piu' dure, dove il giro secco decide
    tutto si portano piu' morbide. L'aggressivita' e' quanto si e' disposti a
    scommettere sulla qualifica invece che sulla domenica.
    """
    liberi = free_sets(track)
    wear = float(track.traits.get("tyre_wear", 0.6))
    sorpassi = float(track.traits.get("overtaking", 0.5))
    # dove non si sorpassa la qualifica vale doppio, quindi morbide
    voglia = (0.12 + 0.45 * (1.0 - wear) + 0.25 * (1.0 - sorpassi)
              + 0.75 * (aggressivita - 0.5))
    voglia = max(0.0, min(1.0, voglia))
    soft = int(round(liberi * (0.35 + 0.42 * voglia)))
    hard = int(round(liberi * (0.05 + 0.30 * wear) * (1.20 - 0.40 * voglia)))
    soft = max(2, min(liberi - 3, soft))
    hard = max(0, min(liberi - soft - 2, hard))
    medium = liberi - soft - hard
    # senza medie la domenica non si va da nessuna parte, e nel weekend sprint
    # il regolamento ne vuole due buone per SQ1 e SQ2
    minimo = 3 if getattr(track, "sprint", False) else 2
    if medium < minimo:
        soft -= minimo - medium
        medium = minimo
    return {"soft": soft, "medium": medium, "hard": hard}


def ai_choice(gs, team, track) -> dict:
    """Quanto osa una squadra del computer.

    Chi parte davanti difende la gara, chi insegue si jetta sulla qualifica:
    e' l'unico modo che ha di trovarsi davanti la domenica.
    """
    pos = team.last_position
    aggressivita = 0.20 + 0.075 * max(0, pos - 1) + gs.rng.uniform(-0.15, 0.15)
    return suggested(track, max(0.02, min(0.98, aggressivita)))


def allocate(gs, ws, player_choice: dict | None = None) -> None:
    """Fissa la scelta di tutti e la rende pubblica.

    Le scelte si consegnano prima di arrivare in pista e vengono pubblicate
    tutte insieme: da quel momento si sa cosa hanno in mano gli altri, e non
    si puo' piu' cambiare idea.
    """
    track = ws.track
    ws.tyre_choice = {}
    for team in gs.teams.values():
        if team.is_player and player_choice is not None:
            scelta = dict(player_choice)
        elif team.is_player:
            scelta = suggested(track)
        else:
            scelta = ai_choice(gs, team, track)
        ws.tyre_choice[team.id] = scelta
    ws.tyre_stock = {}
    for team in gs.teams.values():
        stock = full_stock(track, ws.tyre_choice[team.id])
        for did in team.drivers:
            ws.tyre_stock[did] = dict(stock)
    ws.tyres_published = True


# ------------------------------------------------------------------ consumo
def stock_of(ws, driver_id: str) -> dict:
    return (getattr(ws, "tyre_stock", None) or {}).get(driver_id) or {}


def use(ws, driver_id: str, mescola: str, quanti: int = 1) -> bool:
    """Consuma set. Ritorna False se non ce n'erano piu'."""
    st = stock_of(ws, driver_id)
    if st.get(mescola, 0) < quanti:
        return False
    st[mescola] -= quanti
    return True


def best_available(ws, driver_id: str, preferite: tuple) -> str:
    """La prima mescola disponibile fra quelle che si vorrebbero."""
    st = stock_of(ws, driver_id)
    for m in preferite:
        if st.get(m, 0) > 0:
            return m
    for m in ("medium", "hard", "soft"):
        if st.get(m, 0) > 0:
            return m
    return "medium"


# Quante morbide un ingegnere non tocca mai il venerdi': servono al sabato, e
# chi le brucia in prova si presenta in qualifica con le gomme di ieri.
SET_PER_SESSIONE = 2
# Quello che il venerdi' non si tocca: due morbide per il sabato e le due
# mescole che il regolamento tiene da parte per la domenica.
RISERVE = {"soft": 2, "medium": 1, "hard": 1}


def reserves(track) -> dict:
    """Quello che il venerdi' non si tocca.

    Due morbide per il sabato e le due mescole che il regolamento tiene da parte
    per la domenica. Nel fine settimana con la sprint si mettono via anche due
    medie: SQ1 e SQ2 si corrono per forza con quelle, e presentarsi senza vuol
    dire buttare la Sprint Qualifying.
    """
    r = dict(RISERVE)
    if getattr(track, "sprint", False):
        r["medium"] = 2
    return r


def spend_practice(gs, ws) -> None:
    """Una sessione di libere consuma set: si gira, e girare costa gomme.

    Si comincia dalle dure, che servono a capire il passo gara, e si arriva
    alle morbide solo se non c'e' altro. Le ultime tre morbide non si toccano:
    quelle sono del sabato.
    """
    tenute = reserves(ws.track)
    for did in list(getattr(ws, "tyre_stock", {})):
        st = ws.tyre_stock[did]
        for _ in range(SET_PER_SESSIONE):
            # quello che si puo' bruciare e' solo cio' che avanza dopo aver
            # messo da parte le morbide del sabato e le due mescole che il
            # regolamento vuole intatte per la gara
            avanzo = {m: st.get(m, 0) - tenute[m] for m in MESCOLE}
            liberi = [m for m in MESCOLE if avanzo[m] > 0]
            if liberi:
                # si consuma in proporzione a quello che si e' portato: chi ha
                # caricato morbide brucia morbide, e arriva al sabato con la
                # scelta che ha fatto invece che con quella di tutti gli altri
                m = gs.rng.choices(liberi, weights=[avanzo[x] for x in liberi])[0]
                st[m] -= 1
                continue
            # non resta niente di comodo: si gira con quello che c'e'
            for m in ("medium", "soft", "hard"):
                if st.get(m, 0) > 0:
                    st[m] -= 1
                    break


# Quanto vale il giro secco a seconda di cosa si riesce a montare. Chi arriva
# al sabato senza morbide nuove il giro buono non lo fa: e' il prezzo di aver
# scelto male, o di aver girato troppo il venerdi'.
QUALI_GAIN = {"soft": 0.35, "medium": 0.05, "hard": -0.30}


def quali_run(gs, ws, driver_id: str, imposta: str | None = None) -> str:
    """Monta il set per un turno di qualifica e lo consuma. Ritorna la mescola.

    Nel fine settimana con la sprint il regolamento non lascia scegliere: media
    nei primi due turni, morbida nell'ultimo. Se quella mescola e' finita si
    monta quello che c'e' - e si paga.
    """
    if imposta:
        prefer = (imposta,) + tuple(m for m in ("soft", "medium", "hard") if m != imposta)
    else:
        prefer = ("soft", "medium", "hard")
    m = best_available(ws, driver_id, prefer)
    use(ws, driver_id, m)
    return m


def summary(ws, team_id: str) -> str:
    scelta = (getattr(ws, "tyre_choice", None) or {}).get(team_id) or {}
    tot = full_stock_from(scelta)
    return "  ".join(f"{LABEL[m][0]}{tot[m]}" for m in MESCOLE)


def full_stock_from(scelta: dict) -> dict:
    return {m: int(scelta.get(m, 0)) + OBBLIGATORI[m] for m in MESCOLE}
