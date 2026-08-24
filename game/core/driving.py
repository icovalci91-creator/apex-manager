"""Lo stile di guida: perche' due piloti non vogliono la stessa macchina.

Il tracciato ha un assetto ideale, ma non esiste un assetto ideale in
assoluto: esiste quello che funziona per chi la guida. Uno stacca tardissimo e
vuole l'anteriore che morde anche a costo di trovarsi la coda leggera; un
altro non riesce a guidare una macchina nervosa e chiede stabilita' anche se
gli costa un decimo in percorrenza; chi le gomme le sa gestire preferisce una
vettura piu' morbida che le fa durare.

Da qui gli scostamenti qui sotto: si sommano all'ottimo del circuito e
spostano la finestra di ognuno. Due piloti della stessa squadra, con la stessa
macchina, hanno quindi due assetti diversi - e uno stesso assetto montato su
tutte e due va bene a uno e male all'altro.
"""
from __future__ import annotations

from ..model.car import SETUP_KEYS

# Di quanto uno stile marcato sposta ogni regolazione, al massimo.
#
# Tenuto basso di proposito: la finestra di un pilota non e' un altro pianeta,
# e' qualche punto piu' in la'. Alzarlo troppo significa che rispettare lo
# stile costa mezzo secondo di prestazione pura, e non e' cosi': una macchina
# cucita addosso a chi la guida va forte, non piano.
MAX_SHIFT = 5.0


def traits(driver) -> dict:
    """I tre tratti da cui nasce lo stile, da -1 a +1.

    Non sono attributi nuovi: si leggono da quelli che gia' ci sono, perche'
    e' proprio da li' che viene il modo di guidare.
    """
    def n(v, centro, ampiezza):
        return max(-1.4, min(1.4, (v - centro) / ampiezza))

    agg = n(driver.aggression, 72.0, 12.0)
    cos = n(driver.consistency, 84.0, 9.0)
    gom = n(driver.tyre_mgmt, 84.0, 9.0)
    cura = (cos + gom) / 2.0
    # lo stile e' un contrasto, non un livello: due piloti bravi uguale
    # guidano lo stesso? no, e la differenza sta in cosa hanno di piu' e di
    # meno rispetto al resto del loro profilo
    c = lambda v: max(-1.0, min(1.0, v))
    return {
        "attacco": c(agg - 0.5 * cura),      # stacca tardi, vuole la macchina che gira
        "stabilita": c(cos - 0.5 * agg),     # non vuole essere sorpreso
        "gomme": c(gom - 0.5 * agg),         # accetta di perdere sul giro secco
    }


def offsets(driver) -> dict:
    """Quanto lo stile sposta l'assetto ideale del circuito, regolazione per regolazione."""
    t = traits(driver)
    a, s, g = t["attacco"], t["stabilita"], t["gomme"]
    raw = {
        "wing":        -0.42 * a + 0.38 * s,      # meno carico per chi attacca
        "ride_height": -0.30 * a + 0.20 * g,
        "stiffness":    0.35 * a - 0.45 * g,      # morbida per chi cura le gomme
        "camber":       0.40 * a - 0.30 * g,
        "gearing":      0.25 * a - 0.15 * s,
        "brake_bias":   0.50 * a - 0.25 * s,      # freno avanti per chi stacca tardi
    }
    return {k: round(MAX_SHIFT * v, 2) for k, v in raw.items() if k in SETUP_KEYS}


def label(driver) -> str:
    """Lo stile detto in due parole, per la scheda."""
    t = traits(driver)
    if t["attacco"] > 0.35 and t["stabilita"] < 0.1:
        return "aggressivo, vuole l'anteriore che morde"
    if t["attacco"] > 0.35:
        return "attacca la staccata ma vuole la coda piantata"
    if t["gomme"] > 0.35 and t["attacco"] < 0.1:
        return "morbido, costruisce la gara sulle gomme"
    if t["stabilita"] > 0.35:
        return "pulito e regolare, chiede stabilita'"
    if t["attacco"] < -0.25:
        return "conservativo, non forza mai la macchina"
    return "equilibrato, si adatta a quello che trova"


def distance(a, b) -> float:
    """Quanto sono lontani due stili: dice se un assetto solo puo' bastare a entrambi."""
    oa, ob = offsets(a), offsets(b)
    return round(sum(abs(oa[k] - ob[k]) for k in oa) / max(1, len(oa)), 2)


# ------------------------------------------------------- l'assetto di ciascuno
def setup_of(team, driver) -> dict:
    """L'assetto montato sulla macchina di quel pilota."""
    if team.setups is None:
        team.setups = {}
    if driver.id not in team.setups:
        base = dict(team.car.setup) if team.car else {k: 50.0 for k in SETUP_KEYS}
        team.setups[driver.id] = {k: float(base.get(k, 50.0)) for k in SETUP_KEYS}
    return team.setups[driver.id]


def set_value(team, driver, key: str, value: float) -> None:
    setup_of(team, driver)[key] = max(0.0, min(100.0, float(value)))


def quality_of(gs, team, driver, track) -> float:
    """Quanto l'assetto montato e' vicino a quello che serve a lui."""
    car = team.car
    saved = dict(car.setup)
    car.setup = dict(setup_of(team, driver))
    q = car.evaluate_setup(track, driver)
    car.setup = saved
    car.setup_quality = q
    return q
