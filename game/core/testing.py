"""Test privati: girare lontano dai gran premi.

Il regolamento vieta di provare in stagione con la vettura dell'anno, ma lascia
due porte aperte che le squadre usano davvero. I TPC si fanno con monoposto di
almeno due anni e servono soprattutto a dare chilometri ai giovani. I filming
day sono duecento chilometri promozionali che in pratica diventano una prova
generale.

Da qui nascono quattro programmi diversi, ognuno con un ritorno diverso. Il
budget e' quello vero: giorni contati dal regolamento e soldi dentro il tetto
di spesa, quindi ogni giornata in pista e' una giornata di sviluppo in meno.
"""
from __future__ import annotations

from . import economy

PROGRAMMI = {
    "giovani": {
        "label": "Chilometri ai giovani",
        "desc": "Una monoposto di due anni fa e un pilota da far crescere. "
                "Non serve alla macchina, serve a lui.",
        "materiali": 0.20,
    },
    "correlazione": {
        "label": "Correlazione galleria-pista",
        "desc": "Si misura in pista quello che la galleria del vento promette. "
                "Quando i due numeri divergono, gli aggiornamenti falliscono.",
        "materiali": 0.30,
    },
    "assetto": {
        "label": "Lavoro di assetto",
        "desc": "Si accumula conoscenza su un circuito preciso: quando ci si "
                "torna in gara, si parte gia' vicini alla finestra giusta.",
        "materiali": 0.25,
    },
    "affidabilita": {
        "label": "Prova di affidabilita'",
        "desc": "Chilometri su chilometri per far emergere le rotture in "
                "officina invece che in gara.",
        "materiali": 0.28,
    },
}

# Quanto rende una giornata, per programma.
CRESCITA_GIOVANE = 0.9        # punti di attributo, sui piloti ancora in crescita
CORRELAZIONE_GIORNO = 0.09    # quota di rischio sviluppo tolta
CORRELAZIONE_MAX = 0.45
ASSETTO_GIORNO = 0.30         # conoscenza del circuito, da 0 a 1
USURA_RECUPERO = 9.0          # punti di condizione recuperati sui componenti

# La correlazione non dura per sempre: cambia la vettura e va rifatta.
DECADIMENTO_CORRELAZIONE = 0.5


# Chi ha una pista di proprieta' non deve chiedere il permesso a nessuno per
# girare: i filming day si organizzano in casa, con la squadra che gia' e' li'.
GIORNI_PISTA_PROPRIA = 2


def days_allowed(gs, team=None) -> int:
    giorni = int(gs.regulations["sporting"].get("private_test_days", 8))
    if team is not None and getattr(team, "has_private_track", False):
        giorni += GIORNI_PISTA_PROPRIA
    return giorni


def home_track(gs, team):
    """La pista di proprieta' della squadra, se ne ha una e se esiste davvero.

    Il Red Bull Ring e' anche una gara del mondiale, Fiorano no: sta fra le
    piste di proprieta', che non entrano mai in calendario. Chi se ne costruisce
    una nuova prende quella generica e le da' il proprio nome.
    """
    if not getattr(team, "has_private_track", False):
        return None
    tid = getattr(team, "track_id", "") or ""
    for t in gs.tracks:
        if t.id == tid:
            return t
    if gs.private_tracks is None:
        gs.private_tracks = {}
    tr = gs.private_tracks.get(tid)
    if tr is not None:
        return tr
    # una pista costruita non sta nei dati: si ricava dal modello generico e
    # prende il nome della squadra. Una copia per ciascuno, altrimenti chi
    # costruisce dopo rinominerebbe quella di chi ha costruito prima
    base = gs.private_tracks.get("pista_privata")
    if base is None or not tid:
        return None
    import copy
    tr = copy.deepcopy(base)
    tr.id = tid
    tr.name = team.track_name or f"Pista {team.short}"
    gs.private_tracks[tid] = tr
    return tr


def venues(gs, team) -> list:
    """Dove si puo' andare a girare: il calendario, i candidati, e casa propria."""
    piste = list(gs.tracks) + list(gs.candidates)
    casa = home_track(gs, team)
    if casa is not None and casa not in piste:
        piste.append(casa)
    return piste


def is_home(team, track) -> bool:
    tid = getattr(team, "track_id", "")
    return bool(tid) and track is not None and track.id == tid


def days_left(gs, team) -> int:
    return max(0, days_allowed(gs, team) - int(team.test_days_used))


# Girare costa tre cose diverse, e conviene tenerle separate perche' si
# comportano in modo diverso.
#
# I materiali sono quello che la macchina consuma: benzina, gomme, ricambi,
# pezzi di prova. Sono uguali dovunque si vada, perche' la macchina consuma
# quello che consuma.
#
# Il noleggio e la trasferta dipendono invece da dove si va: una pista si
# affitta, e portarci uomini e camion costa. In casa propria non si paga ne'
# l'uno ne' l'altra - si accende la luce e si gira - e quello che resta e' il
# mantenimento della pista, che si paga tutto l'anno che ci si giri o no, e le
# migliorie, che passano dal budget delle costruzioni come ogni struttura.
# Una giornata di prove private non e' un weekend di gara: si gira con una
# monoposto di due anni fa, con mezza squadra e senza ospitalita'. I materiali
# valgono qualche centinaio di migliaia di dollari al giorno, non un milione.
NOLEGGIO = 0.30            # M$ al giorno per affittare una pista che non e' nostra
TRASFERTA = 0.30           # M$ al giorno di logistica, restando dalle nostre parti
TRASFERTA_LONTANO = 1.00   # e quanto costa in piu' andare lontano da casa


def cost_breakdown(gs, team, track, programme: str, days: int) -> dict:
    """Le voci di una sessione, separate."""
    materiali = PROGRAMMI[programme]["materiali"] * days
    if is_home(team, track):
        return {"materiali": round(materiali, 2), "noleggio": 0.0, "trasferta": 0.0}
    lontano = 0.0 if _vicino(team, track) else TRASFERTA_LONTANO
    return {"materiali": round(materiali, 2),
            "noleggio": round(NOLEGGIO * days, 2),
            "trasferta": round((TRASFERTA + lontano) * days, 2)}


def cost_of(gs, team, track, programme: str, days: int) -> float:
    """Quanto costa una sessione in tutto."""
    return round(sum(cost_breakdown(gs, team, track, programme, days).values()), 2)


# Le fabbriche stanno tutte in Europa, anche quelle delle squadre americane:
# Haas lavora a Banbury, la sede legale e' dall'altra parte dell'oceano ma i
# camion partono da qui. Quindi una trasferta e' comoda se resta in Europa.
EUROPA = ("Italia", "Spagna", "Regno Unito", "Belgio", "Paesi Bassi", "Ungheria",
          "Austria", "Germania", "Francia", "Portogallo", "Monaco", "Svizzera",
          "Turchia", "Europa")


def _vicino(team, track) -> bool:
    return track.country in EUROPA


def can_run(gs, team, track, programme: str, days: int) -> tuple:
    if days <= 0:
        return False, "Serve almeno una giornata."
    if days > days_left(gs, team):
        return False, (f"Il regolamento ne concede {days_allowed(gs, team)} a stagione: "
                       f"te ne restano {days_left(gs, team)}.")
    prezzo = cost_of(gs, team, track, programme, days)
    ok, why = economy.can_afford(team, prezzo, gs)
    if not ok:
        return False, why
    return True, ""


def run(gs, team, track, driver, programme: str, days: int) -> tuple:
    """Manda la squadra a girare. Ritorna (riuscito, messaggio)."""
    ok, why = can_run(gs, team, track, programme, days)
    if not ok:
        return False, why
    if programme == "giovani" and driver is None:
        return False, "Scegli il pilota da mandare in pista."

    prezzo = cost_of(gs, team, track, programme, days)
    team.add_expense(f"Test privati a {track.name}", prezzo, in_cap=True, category="sviluppo")
    team.test_days_used += days

    if programme == "giovani":
        cresciuto = _cresci(gs, driver, days)
        if cresciuto <= 0.01:
            return True, (f"{driver.short} ha girato {days} giorni a {track.name}, "
                          f"ma a questo punto della carriera i chilometri non lo "
                          f"cambiano piu'.")
        return True, (f"{driver.short}: {days} giorni a {track.name}, "
                      f"+{cresciuto:.1f} di crescita complessiva.")

    if programme == "correlazione":
        prima = team.correlation
        team.correlation = min(CORRELAZIONE_MAX,
                               team.correlation + CORRELAZIONE_GIORNO * days)
        return True, (f"Correlazione galleria-pista da {prima*100:.0f}% a "
                      f"{team.correlation*100:.0f}%: gli aggiornamenti rischiano meno.")

    if programme == "assetto":
        if team.setup_knowledge is None:
            team.setup_knowledge = {}
        prima = team.setup_knowledge.get(track.id, 0.0)
        team.setup_knowledge[track.id] = min(1.0, prima + ASSETTO_GIORNO * days)
        return True, (f"Conoscenza di {track.name} da {prima*100:.0f}% a "
                      f"{team.setup_knowledge[track.id]*100:.0f}%.")

    if programme == "affidabilita":
        for p in team.car.parts.values():
            p.condition = min(100.0, p.condition + USURA_RECUPERO * days)
        return True, (f"{days} giorni di chilometraggio a {track.name}: componenti "
                      f"rimessi a punto, meno rotture in vista.")

    return False, "Programma sconosciuto."


def _cresci(gs, driver, days: int) -> float:
    """I chilometri fanno crescere chi ha ancora margine, non i campioni fatti."""
    from ..model.people import DRIVER_ATTRS
    margine = max(0.0, driver.potential - driver.overall)
    if margine < 0.5:
        return 0.0
    tot = 0.0
    for a in DRIVER_ATTRS:
        cur = getattr(driver, a)
        passo = CRESCITA_GIOVANE * days * (margine / 14.0) * gs.rng.uniform(0.5, 1.2)
        passo = min(passo, max(0.0, driver.potential - cur))
        setattr(driver, a, min(99.0, cur + passo))
        tot += passo
    return tot / len(DRIVER_ATTRS)


def setup_bonus(team, track) -> float:
    """Quanto la conoscenza accumulata aiuta l'assetto su questa pista."""
    return float((team.setup_knowledge or {}).get(track.id, 0.0))


def end_season(gs) -> list:
    """Azzera i giorni e fa scadere la correlazione: la vettura e' un'altra."""
    msgs = []
    for team in gs.teams.values():
        team.test_days_used = 0
        team.preseason_done = []
        team.correlation *= DECADIMENTO_CORRELAZIONE
        # la conoscenza di un circuito invecchia con la macchina
        team.setup_knowledge = {k: v * 0.55 for k, v in (team.setup_knowledge or {}).items()
                                if v * 0.55 > 0.05}
    return msgs


def ai_plan(gs) -> None:
    """Le squadre del computer usano le loro giornate durante la stagione."""
    for team in gs.teams.values():
        if team.is_player or days_left(gs, team) <= 0:
            continue
        # piu' giornate restano rispetto alle gare che mancano, piu' spesso si esce:
        # nessuno arriva a dicembre con meta' del pacchetto ancora in mano
        gare_restanti = max(1, len(gs.tracks) - gs.round)
        from . import economy
        if economy.room_left(gs, team) < 1.0:
            continue                     # non e' aria di giornate di prove
        voglia = (days_left(gs, team) / (gare_restanti * 1.6)
                  * economy.spending_room(gs, team)
                  * (0.35 + 0.65 * economy.budget_health(gs, team)))
        if gs.rng.random() > min(0.8, max(0.12, voglia)):
            continue                      # questo weekend non escono a girare
        # a girare ci si manda chi ha ancora da crescere: prima il vivaio e il
        # terzo pilota, che e' esattamente a cosa servono
        candidati = list(team.academy) + list(team.reserves) + list(team.drivers)
        giovani = [gs.drivers[d] for d in candidati
                   if d in gs.drivers and gs.drivers[d].age <= 24]
        r = gs.rng.random()
        if giovani and r < 0.35:
            prog = "giovani"
        elif r < 0.70:
            prog = "correlazione"
        else:
            prog = "assetto"

        if prog == "assetto":
            # si prova dove si andra' a correre: e' il senso del lavoro di assetto
            prossime = gs.tracks[gs.round:gs.round + 4] or gs.tracks
            pista = gs.rng.choice(prossime)
        else:
            # chi ha una pista di casa ci gira: non si paga ne' il noleggio ne'
            # la trasferta, e non serve chiedere il permesso a nessuno
            casa = home_track(gs, team)
            if casa is not None:
                pista = casa
            else:
                vicine = [t for t in gs.tracks if _vicino(team, t)] or gs.tracks
                pista = gs.rng.choice(vicine)
        giorni = min(days_left(gs, team), gs.rng.randint(1, 2))
        run(gs, team, pista, giovani[0] if giovani else None, prog, giorni)

# ================================================ i test collettivi di inizio anno
# Prima che cominci il campionato la Formula 1 organizza le prove collettive:
# due sessioni di tre o quattro giorni, tutte le squadre insieme sulla stessa
# pista. Si va dove fa caldo e dove l'asfalto e' buono - Barcellona e il Bahrein
# da sempre - e si gira con la macchina dell'anno, che e' la sola occasione di
# tutta la stagione: da marzo in poi il regolamento lo vieta.
#
# Non si portano via giornate di test privati: sono due conti diversi. E sono
# l'unico momento in cui si scopre davvero la macchina nuova.
PRESEASON_COST = 0.55        # M$ al giorno: la squadra intera, per giorni interi
COMPRENSIONE_GIORNO = 0.055  # quanto si capisce della macchina, per giornata
CORRELAZIONE_PRE = 0.035     # e quanta correlazione si porta a casa


def preseason_sessions(gs) -> list:
    """Le sessioni collettive di quest'anno, con la pista e i giorni."""
    out = []
    for voce in gs.regulations["sporting"].get("preseason_tests", []):
        pista = next((t for t in list(gs.tracks) + list(gs.candidates)
                      if t.id == voce.get("track")), None)
        if pista is not None:
            out.append({"track": pista, "days": int(voce.get("days", 3))})
    return out


def preseason_done(team, idx: int) -> bool:
    return idx in (team.preseason_done or [])


def preseason_cost(gs, team, sessione) -> float:
    """Costa la trasferta e il materiale, come una prova qualunque.

    Il noleggio no: la pista la paga il campionato, che le organizza.
    """
    giorni = sessione["days"]
    lontano = 0.0 if _vicino(team, sessione["track"]) else TRASFERTA_LONTANO
    return round((PRESEASON_COST + TRASFERTA + lontano) * giorni, 2)


def run_preseason(gs, team, idx: int, programme: str = "correlazione",
                  forzato: bool = False) -> tuple:
    """Manda la squadra alle prove collettive. Ritorna (riuscito, messaggio).

    `forzato` salta il controllo di cassa: alle collettive non si rinuncia
    perche' mancano tre milioni, si taglia da un'altra parte. E' il motivo per
    cui in Formula 1 ci sono sempre tutti.
    """
    sessioni = preseason_sessions(gs)
    if idx >= len(sessioni):
        return False, "Questa sessione non esiste."
    if preseason_done(team, idx):
        return False, "Ci siamo gia' stati."
    if gs.phase != "preseason":
        return False, "Le prove collettive si fanno prima che cominci il campionato."
    ses = sessioni[idx]
    prezzo = preseason_cost(gs, team, ses)
    if not forzato:
        ok, why = economy.can_afford(team, prezzo, gs)
        if not ok:
            return False, why
    team.add_expense(f"Prove collettive a {ses['track'].name}", prezzo, in_cap=True,
                     category="sviluppo")
    if team.preseason_done is None:
        team.preseason_done = []
    team.preseason_done.append(idx)

    giorni = ses["days"]
    qualita = 0.55 + 0.45 * (team.setup_strength / 100.0)
    # e' la macchina di quest'anno: qui si capisce com'e' fatta
    team.car_understanding = min(1.0, team.car_understanding
                                 + COMPRENSIONE_GIORNO * giorni * qualita)
    team.correlation = min(CORRELAZIONE_MAX,
                           team.correlation + CORRELAZIONE_PRE * giorni * qualita)
    if team.setup_knowledge is None:
        team.setup_knowledge = {}
    prima = team.setup_knowledge.get(ses["track"].id, 0.0)
    team.setup_knowledge[ses["track"].id] = min(1.0, prima + 0.18 * giorni)
    if programme == "affidabilita":
        for p in team.car.parts.values():
            p.condition = min(100.0, p.condition + USURA_RECUPERO * giorni * 0.6)
    elif programme == "giovani":
        giovani = [gs.drivers[d] for d in team.drivers
                   if d in gs.drivers and gs.drivers[d].age <= 23]
        for d in giovani:
            _cresci(gs, d, giorni)
    return True, (f"{giorni} giorni di prove collettive a {ses['track'].name} per "
                  f"{prezzo:.2f} M$: conoscenza della vettura al "
                  f"{team.car_understanding*100:.0f}%, correlazione al "
                  f"{team.correlation*100:.0f}%.")


def ai_preseason(gs) -> None:
    """Alle prove collettive ci vanno tutti: e' l'unica occasione dell'anno."""
    for team in gs.teams.values():
        if team.is_player:
            continue
        for i, _ses in enumerate(preseason_sessions(gs)):
            if not preseason_done(team, i):
                run_preseason(gs, team, i, "correlazione", forzato=True)
