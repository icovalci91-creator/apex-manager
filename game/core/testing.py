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
        "materiali": 0.55,
    },
    "correlazione": {
        "label": "Correlazione galleria-pista",
        "desc": "Si misura in pista quello che la galleria del vento promette. "
                "Quando i due numeri divergono, gli aggiornamenti falliscono.",
        "materiali": 0.85,
    },
    "assetto": {
        "label": "Lavoro di assetto",
        "desc": "Si accumula conoscenza su un circuito preciso: quando ci si "
                "torna in gara, si parte gia' vicini alla finestra giusta.",
        "materiali": 0.70,
    },
    "affidabilita": {
        "label": "Prova di affidabilita'",
        "desc": "Chilometri su chilometri per far emergere le rotture in "
                "officina invece che in gara.",
        "materiali": 0.65,
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
NOLEGGIO = 0.35            # M$ al giorno per affittare una pista che non e' nostra
TRASFERTA = 0.25           # M$ al giorno di logistica, restando dalle nostre parti
TRASFERTA_LONTANO = 0.90   # e quanto costa in piu' andare lontano da casa


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


def _vicino(team, track) -> bool:
    europa = ("Italia", "Spagna", "Regno Unito", "Belgio", "Paesi Bassi",
              "Ungheria", "Austria", "Germania", "Francia", "Portogallo", "Monaco")
    return track.country in europa and any(p in team.base for p in
                                           ("Regno Unito", "Italia", "Svizzera"))


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
        if economy.room_left(gs, team) < 3.0:
            continue                     # non e' aria di giornate di prove
        voglia = (days_left(gs, team) / (gare_restanti * 1.6)
                  * economy.spending_room(gs, team)
                  * (0.35 + 0.65 * economy.budget_health(gs, team)))
        if gs.rng.random() > min(0.8, max(0.12, voglia)):
            continue                      # questo weekend non escono a girare
        giovani = [gs.drivers[d] for d in team.drivers
                   if d in gs.drivers and gs.drivers[d].age <= 23]
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
            # per il resto si sceglie la trasferta piu' comoda
            vicine = [t for t in gs.tracks if _vicino(team, t)] or gs.tracks
            pista = gs.rng.choice(vicine)
        giorni = min(days_left(gs, team), gs.rng.randint(1, 2))
        run(gs, team, pista, giovani[0] if giovani else None, prog, giorni)
