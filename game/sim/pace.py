"""Quanto va forte una macchina: aria, asfalto, vettura, assetto, pilota.

Il tempo sul giro non e' un punteggio: e' quello che viene fuori mettendo
insieme quanta aria c'e' - a Citta' del Messico ce n'e' un quarto di meno che
sul mare - quanto scotta l'asfalto, quanta gomma ci hanno gia' steso sopra,
com'e' fatta la macchina, come e' regolata e chi ci sta dentro.

Sta tutto qui, in un posto solo, e lo usano le prove libere, la qualifica e la
gara: quello che si vede al venerdi' e' la stessa macchina che scende in pista
la domenica, e se cambia il tempo cambia per tutti allo stesso modo.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import config as C

R_ARIA = 287.05          # costante dell'aria secca, J/(kg K)
P0 = 101325.0            # pressione al livello del mare, Pa
H_SCALA = 8434.0         # quota di scala dell'atmosfera, m

# Temperatura dell'asfalto attorno a cui la gomma lavora meglio. Sotto non
# arriva in temperatura e scivola, sopra si surriscalda e scivola lo stesso.
T_IDEALE = 37.0
T_AMPIEZZA = 24.0
T_PERDITA = 0.030        # quanto grip si perde a una campata di distanza

# Evoluzione della pista: il venerdi' mattina e' un deserto, la domenica
# pomeriggio e' una striscia di gomma. Fra i due estremi ci passa piu' di un
# secondo, ed e' il motivo per cui i tempi calano turno dopo turno.
PISTA_VERDE = 0.952
PISTA_GOMMATA = 1.005

# Quanto pesa trovarsi bene su una pista: e' la traduzione in secondi dei punti
# forti e deboli della vettura, pesati su quello che il circuito chiede.
AFFINITA_S = 0.007


@dataclass
class Conditions:
    """Le condizioni di un turno: valgono per tutti quelli che scendono in pista."""
    wet: float = 0.0
    air_temp: float = 22.0
    track_temp: float = 32.0
    wind: float = 8.0
    rho: float = C.RHO
    rubber: float = 1.0
    session: str = "gara"

    @property
    def label(self) -> str:
        return (f"{self.air_temp:.0f}C aria, {self.track_temp:.0f}C asfalto, "
                f"vento {self.wind:.0f} km/h")


# ------------------------------------------------------------------ aria
def air_density(air_temp: float, altitude: float = 0.0) -> float:
    """Densita' dell'aria, in kg/m3, alla quota e alla temperatura del giorno.

    Meno aria vuol dire meno carico aerodinamico e meno resistenza insieme: in
    Messico si va fortissimo in fondo al rettilineo e non si gira in curva, e
    si porta l'ala di Monaco per avere il carico di Monza.
    """
    p = P0 * pow(2.718281828459045, -max(0.0, altitude) / H_SCALA)
    return p / (R_ARIA * (air_temp + 273.15))


def surface_grip(cond: Conditions) -> float:
    """L'aderenza che offre l'asfalto: gomma stesa e temperatura."""
    d = (cond.track_temp - T_IDEALE) / T_AMPIEZZA
    return cond.rubber * (1.0 - T_PERDITA * d * d)


def wind_penalty(cond: Conditions, track) -> float:
    """Il vento non fa perdere tanto, fa perdere il riferimento.

    Sul giro vale poco; quello che fa davvero e' rendere la macchina diversa a
    ogni passaggio, e quello sta nella dispersione, non qui.
    """
    carico = float(track.traits.get("downforce", 0.5))
    return 1.0 + 0.00055 * (cond.wind / 10.0) * (0.6 + 0.8 * carico)


def wind_noise(cond: Conditions) -> float:
    """Quanto il vento allarga la dispersione dei tempi, in secondi."""
    return 0.030 * (cond.wind / 10.0)


# ------------------------------------------------------- condizioni del turno
def nominal(track) -> Conditions:
    """Le condizioni tipiche di quel gran premio: servono a tarare il modello.

    I tempi di riferimento sono quelli veri delle pole: sono stati fatti col
    clima di quel posto in quel mese, su una pista gommata. E' li' che il
    modello va allineato, cosi' tutto quello che succede dopo - una giornata
    fredda, una pista verde, la quota - si legge come uno scarto da quello.
    """
    clima = getattr(track, "climate", None) or {}
    aria = float(clima.get("temp", 22.0))
    sole = 0.30 if getattr(track, "night", False) else 1.0
    return Conditions(
        wet=0.0, air_temp=aria, track_temp=aria + 3.0 + 17.0 * sole * 0.81,
        wind=float(clima.get("wind", 10.0)),
        rho=air_density(aria, getattr(track, "altitude", 0.0)),
        rubber=PISTA_GOMMATA, session="quali")


def of_weekend(ws, session: str = "gara") -> Conditions:
    """Le condizioni di adesso, dal meteo del fine settimana."""
    w = ws.weather
    track = ws.track
    return Conditions(
        wet=w.wet, air_temp=w.air_temp, track_temp=w.track_temp,
        wind=float(getattr(w, "wind", 8.0)),
        rho=air_density(w.air_temp, getattr(track, "altitude", 0.0)),
        rubber=float(getattr(ws, "rubber", PISTA_VERDE)),
        session=session)


def from_weather(track, weather, session: str = "gara", rubber: float = PISTA_GOMMATA) -> Conditions:
    """Condizioni ricavate dal solo meteo, quando il weekend non c'e'."""
    return Conditions(
        wet=weather.wet, air_temp=weather.air_temp, track_temp=weather.track_temp,
        wind=float(getattr(weather, "wind", 8.0)),
        rho=air_density(weather.air_temp, getattr(track, "altitude", 0.0)),
        rubber=rubber, session=session)


def rubber_in(ws, quanto: float) -> float:
    """Un turno in piu' sulla pista: la gomma stesa cresce, la pioggia la lava."""
    ora = float(getattr(ws, "rubber", PISTA_VERDE))
    if ws.weather.wet > 0.20:
        ora = max(PISTA_VERDE - 0.004, ora - 0.010 * ws.weather.wet)
    else:
        ora = min(PISTA_GOMMATA, ora + quanto)
    ws.rubber = round(ora, 4)
    return ws.rubber


# --------------------------------------------------- punti forti e deboli
def affinities(gs, track) -> dict:
    """Quanto ogni vettura si trova bene qui rispetto al resto del calendario.

    Non e' "quanto e' forte": e' dove e' forte. Si guarda in cosa una macchina
    e' meglio - il carico rispetto alla potenza, la trazione rispetto alla
    frenata - e lo si pesa su quello che questo circuito chiede invece di
    quello che chiede il campionato in media. Su una stagione intera i conti
    tornano a zero per tutti: nessuno guadagna un decimo gratis, ma chi ha la
    macchina giusta per Monaco a Monza lo paga.
    """
    from ..core import engineering
    qui = _pesi(engineering.track_bias(track))
    media = _pesi(engineering.calendar_bias(gs, gs.tracks))
    out = {}
    for team in gs.teams.values():
        prof = engineering.car_profile(team, gs)
        val = (_pesato(prof, qui) - _pesato(prof, media)) / 22.0
        out[team.id] = max(-1.0, min(1.0, val))
    return out


def _pesi(bias: dict) -> dict:
    """Cosa chiede un circuito davvero: quello che chiedono tutti non conta."""
    return {a: max(0.0, w - 0.42) for a, w in bias.items()}


def _pesato(prof: dict, pesi: dict) -> float:
    tot = sum(pesi.values()) or 1.0
    return sum(p * prof.get(a, 50.0) for a, p in pesi.items()) / tot


# ------------------------------------------------------------- giro base
def lap_base(gs, team, track, driver=None, cond: Conditions | None = None,
             affinita: float | None = None) -> float:
    """Il giro di riferimento di questa vettura, adesso, a serbatoio vuoto.

    Senza pilota vale l'assetto generico della squadra; con un pilota si monta
    il suo, perche' quello del compagno di box e' un altro.
    """
    from ..core import powertrain, driving, kits
    cond = cond or nominal(track)
    car = team.car
    # rinfrescata qui: se il reparto motori e' cambiato (ingaggi, debutto della
    # propria unita') l'integrazione deve valere gia' da questo weekend
    car.pu_integration = powertrain.integration(gs, team)
    old_fuel, old_setup = car.fuel_kg, dict(car.setup)
    car.fuel_kg = 0.0
    ripristina = {}
    if driver is not None:
        car.setup = dict(driving.setup_of(team, driver))
        # i pezzi montati solo su questa macchina valgono solo per lei
        for parte, valore in (kits.deltas(team, driver.id) or {}).items():
            if parte in car.parts:
                ripristina[parte] = car.parts[parte].perf
                car.parts[parte].perf = float(valore)
    car.evaluate_setup(track, driver, cond)
    t, _, _ = track.lap_model(car, wet=cond.wet, grip=surface_grip(cond), rho=cond.rho)
    effetto = car.apply_setup_effects()
    car.fuel_kg, car.setup = old_fuel, old_setup
    for parte, valore in ripristina.items():
        car.parts[parte].perf = valore

    t = t / effetto * wind_penalty(cond, track)
    if affinita is None:
        affinita = affinities(gs, track).get(team.id, 0.0)
    return t * (1.0 - AFFINITA_S * affinita)


# ------------------------------------------------------------------ piloti
def quali_rating(driver, cond: Conditions) -> float:
    """Quanto rende sul giro secco.

    Il giro di qualifica non e' la gara: conta il passo puro e conta il coraggio
    di tenere il piede giu' dove la macchina si muove. La forma del momento e la
    fiducia in quello che si ha sotto pesano qui piu' che in ogni altro posto.
    """
    from ..core.driving import FIDUCIA_BASE
    r = 0.66 * driver.pace + 0.20 * driver.overall + 0.14 * driver.consistency
    r += driver.form * 0.85
    r += (driver.morale - 70.0) * 0.020
    r += (float(getattr(driver, "confidence", FIDUCIA_BASE)) - FIDUCIA_BASE) * 0.10
    r += (driver.wet - r) * cond.wet * 0.75
    return r * (0.92 + 0.08 * driver.fitness / 100.0)


def race_rating(driver, cond: Conditions) -> float:
    """Quanto rende in gara: sul passo la fiducia conta, ma meno del giro secco."""
    from ..core.driving import FIDUCIA_BASE
    r = driver.race_rating(cond.wet)
    r += (float(getattr(driver, "confidence", FIDUCIA_BASE)) - FIDUCIA_BASE) * 0.05
    return r
