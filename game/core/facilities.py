"""Infrastrutture: potenziamenti, obsolescenza e investimenti delle IA.

Le regole stavano dentro la pagina che le disegnava, quindi le scuderie gestite
dal computer non potevano toccarle: restavano ferme ai valori di partenza per
sempre mentre il giocatore poteva salire indisturbato.

Qui c'e' anche l'obsolescenza. Una galleria del vento non si consuma, ma invec-
chia: quella di dieci anni fa non regge il passo con una nuova. Chi non rein-
veste scivola indietro senza fare niente di sbagliato.
"""
from __future__ import annotations

from .. import config as C
from . import economy

# Una struttura non invecchia il giorno dopo averla costruita. Una galleria del
# vento nuova resta all'avanguardia per qualche stagione: e' quello il premio di
# chi investe. Solo dopo comincia a restare indietro, e piu' passa il tempo piu'
# in fretta lo fa, perche' nel frattempo gli altri sono andati avanti.
GRACE_SEASONS = 3.0   # anni in cui resta di riferimento, senza perdere nulla
# Questi numeri erano tarati su un mondo in cui costruire si pagava dal tetto di
# spesa, cioe' con decine di milioni l'anno a disposizione. Adesso il budget
# delle costruzioni e' quello vero - una quindicina di milioni l'anno - e
# l'invecchiamento va rimesso in scala: com'era, una squadra perdeva dieci punti
# di strutture l'anno e con tutto il budget ne comprava uno.
DECAY = 0.12          # punti persi nel primo anno dopo il periodo di grazia
DECAY_RAMP = 0.04     # e quanto accelera ogni anno che passa
DECAY_MAX = 0.50      # oltre non si scivola, per quanto vecchia sia
FLOOR = 35.0          # sotto questo livello non si scende: resta un capannone

# Ogni quante stagioni una scuderia del computer si concede l'intervento grosso
# invece di spendere a rate: senza questo userebbero il margine capitale un
# pezzetto alla volta e non arriverebbero mai a un salto vero.
CAPEX_SPREAD = 2

# Non tutte le strutture esistono per forza. Una pista di proprieta' ce l'ha
# chi se l'e' costruita: Ferrari a Fiorano, Red Bull al Red Bull Ring. Gli
# altri corrono a casa d'altri, e per averne una devono tirarla su da zero.
OPTIONAL = ("private_track",)
BUILD_LEVEL = 55.0    # con che livello nasce una struttura appena costruita


def is_built(team, key: str) -> bool:
    """Una struttura opzionale che nessuno ha costruito non esiste."""
    if key not in OPTIONAL:
        return True
    return float(team.facilities.get(key, 0.0)) > 0.0


def build_cost(key: str) -> float:
    return float(C.FACILITIES[key].get("build_cost", 0.0))


def build(gs, team, key: str) -> tuple:
    """Tira su da zero una struttura opzionale. Costa molto, e giustamente.

    Un autodromo privato non e' un potenziamento: e' terra, asfalto, permessi e
    un reparto che ci lavora. Chi lo fa se ne accorge in bilancio per anni.
    """
    if is_built(team, key):
        return False, "Questa struttura c'e' gia'."
    price = build_cost(key)
    if price <= 0:
        return False, "Questa struttura non si costruisce."
    # Fiorano e' della Ferrari, il Red Bull Ring della Red Bull: un autodromo e'
    # proprieta' del gruppo, non del reparto corse, e infatti nessuno l'ha mai
    # messo nei conti della squadra. Si paga con i soldi veri e basta: niente
    # tetto tecnico, niente limite capitale. Poi pero' mantenerlo e potenziarlo
    # segue le regole di tutte le altre strutture.
    if team.cash < price:
        return False, "Liquidita' insufficiente."
    team.add_expense(f"Costruzione {C.FACILITIES[key]['label']}", price, in_cap=False,
                     category="strutture")
    team.facilities[key] = BUILD_LEVEL
    if team.facility_age is None:
        team.facility_age = {}
    team.facility_age[key] = 0.0
    if key == "private_track" and not getattr(team, "track_id", ""):
        # da adesso c'e' un posto dove andare a girare, e ha un nome
        team.track_id = f"pista_{team.id}"
        team.track_name = team.track_name or f"Pista {team.short}"
    return True, (f"{C.FACILITIES[key]['label']} costruita: parte da "
                  f"{BUILD_LEVEL:.0f} ed e' costata {price:.0f} M$. Da ora si puo' "
                  f"girare in casa quando si vuole.")


def average(team) -> float:
    """Livello medio, contando solo quello che esiste davvero."""
    vals = [float(v) for k, v in team.facilities.items() if is_built(team, k)]
    return sum(vals) / max(1, len(vals))


def cost(level: float, base: float) -> float:
    """Costo per alzare di un gradino una struttura.

    Le infrastrutture di una squadra di Formula 1 costano moltissimo, e ogni
    gradino in piu' costa piu' del precedente: portare una galleria del vento
    da 90 a 92 non e' come portarla da 60 a 65.
    """
    return round(base * (0.67 + (level / 100.0) ** 2.6 * 3.75), 2)


def gain(level: float) -> float:
    """Quanto sale una struttura con un potenziamento."""
    return max(1.5, 6.0 - level / 22.0)


def decay_of(level: float, age: float = 99.0) -> float:
    """Punti persi in una stagione, dati livello ed eta' dall'ultimo intervento."""
    if age < GRACE_SEASONS:
        return 0.0
    ritmo = DECAY + DECAY_RAMP * (age - GRACE_SEASONS)
    return min(DECAY_MAX, ritmo) * (0.55 + 0.65 * level / 100.0)


def age_of(team, key: str) -> float:
    return float((team.facility_age or {}).get(key, GRACE_SEASONS))


def state_label(team, key: str) -> tuple:
    """Come sta messa una struttura, in parole. Ritorna (testo, anni)."""
    eta = age_of(team, key)
    if eta < GRACE_SEASONS:
        return "all'avanguardia", eta
    if eta < GRACE_SEASONS + 4:
        return "ancora competitiva", eta
    if eta < GRACE_SEASONS + 9:
        return "da aggiornare", eta
    return "superata", eta


def upgrade(gs, team, key: str) -> tuple:
    """Potenzia una struttura. Ritorna (riuscito, messaggio)."""
    if not is_built(team, key):
        return build(gs, team, key)
    lvl = float(team.facilities.get(key, 60.0))
    if lvl >= 99:
        return False, "Struttura gia' al massimo livello."
    price = cost(lvl, C.FACILITIES[key]["cost"])
    ok, why = economy.can_afford_capex(gs, team, price)
    if not ok:
        return False, why
    # costruire non sta nel tetto tecnico: e' spesa in conto capitale
    team.add_expense(f"Potenziamento {C.FACILITIES[key]['label']}", price, in_cap=False,
                     category="strutture", capex=True)
    team.facilities[key] = min(99.0, lvl + gain(lvl))
    # l'intervento rimette a nuovo: da qui ricominciano gli anni di grazia
    if team.facility_age is None:
        team.facility_age = {}
    team.facility_age[key] = 0.0
    return True, (f"{C.FACILITIES[key]['label']} portata a "
                  f"{team.facilities[key]:.0f} ({price:.2f} M$), "
                  f"di riferimento per le prossime stagioni.")


def decay(gs) -> float:
    """Invecchia le strutture di tutti di una stagione.

    Ritorna quanto ha perso in media il giocatore, per poterglielo dire.
    """
    lost = 0.0
    for team in gs.teams.values():
        if team.facility_age is None:
            team.facility_age = {}
        for k, v in team.facilities.items():
            if not is_built(team, k):
                continue        # non invecchia quello che non esiste
            eta = float(team.facility_age.get(k, GRACE_SEASONS))
            new = max(FLOOR, float(v) - decay_of(float(v), eta))
            if team.is_player:
                lost += float(v) - new
            team.facilities[k] = new
            team.facility_age[k] = eta + 1.0
    return lost / max(1, len(C.FACILITIES))


def priorities(team) -> list:
    """Su quali strutture punta una squadra, secondo la sua filosofia."""
    weights = {k: 1.0 for k in C.FACILITIES}
    focus = {
        "aero": ("windtunnel", "cfd", "aero_dept"),
        "mechanical": ("design_office", "factory", "simulator"),
        "powertrain": ("factory", "design_office", "cfd"),
    }.get(team.philosophy, ())
    for k in focus:
        weights[k] = 1.8
    # a parita' di interesse si rimette in pari quella messa peggio
    costruite = [k for k in C.FACILITIES if is_built(team, k)]
    return sorted(costruite,
                  key=lambda k: -(weights[k] * (100.0 - team.facilities.get(k, 60.0))))


def ai_invest(gs) -> None:
    """Le scuderie del computer reinvestono in strutture a fine stagione.

    Senza questo l'obsolescenza le farebbe scivolare all'infinito, e il
    giocatore resterebbe l'unico a poter costruire qualcosa.
    """
    for team in gs.teams.values():
        if team.is_player:
            continue
        # il budget delle costruzioni e' quello che resta nel periodo, e non si
        # spende mai tutto in un colpo: si tiene qualcosa per l'anno dopo
        budget = min(economy.capex_left(gs, team), max(0.0, team.cash - 25.0))
        # chi sta perdendo soldi non apre cantieri: il capitale e' un budget a
        # parte, ma la firma la mette lo stesso proprietario
        # chi ha capitale non aspetta il turno buono: il limite per le
        # costruzioni e' gia' un tetto, e lasciarne indietro un pezzo significa
        # solo tenere i soldi fermi
        fame = economy.spending_appetite(gs, team)
        rateo = 1.0 if not gs.season % CAPEX_SPREAD else 0.55 + 0.45 * fame
        budget *= (rateo * economy.spending_room(gs, team)
                   * (0.30 + 0.70 * max(economy.budget_health(gs, team), fame)))
        # chi nuota nei soldi prima o poi si costruisce la pista di casa, e
        # quella la paga il gruppo: non tocca nessuno dei due tetti
        for key in OPTIONAL:
            if not is_built(team, key) and build_cost(key) <= (team.cash - 60.0):
                ok, _m = build(gs, team, key)
        for key in priorities(team):
            price = cost(team.facilities.get(key, 60.0), C.FACILITIES[key]["cost"])
            if price > budget:
                continue
            ok, _msg = upgrade(gs, team, key)
            if ok:
                budget -= price
            if budget <= 0:
                break
