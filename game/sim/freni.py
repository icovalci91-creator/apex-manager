"""I freni: quanto scaldano, quando smettono di funzionare, quando cedono.

Un impianto frenante da monoposto e' fatto di carbonio, e il carbonio non e'
acciaio: freddo non frena. Sotto i trecentocinquanta gradi il disco non morde
- si stacca lungo, si blocca una ruota, si lunga alla prima staccata - e sopra
i novecentocinquanta comincia a consumarsi per davvero, il pedale si allunga e
in fondo alla gara si finisce dritti. In mezzo c'e' la finestra, ed e' larga,
ma tenerci dentro l'impianto per due ore non e' scontato: dipende da quanto si
frena su quel circuito, da quanta aria si riesce a farci arrivare e da chi si
ha davanti.

Nel gioco fino a ieri il pezzo `brakes` faceva una cosa sola: moltiplicava
l'aderenza in frenata nel modello di giro. Un valore fisso, uguale al primo
giro e all'ultimo, uguale a Montreal e a Monte Carlo, uguale in mezzo al
gruppo e in aria libera. Adesso e' un pezzo che lavora, si scalda e si
consuma, e il raffreddamento - che era una voce dello sviluppo con un effetto
quasi invisibile sulla potenza - serve a qualcosa.

I circuiti che cuociono i freni sono quelli in cui si arriva forte e si
rallenta tanto, e non sono tanti: Montreal, Monza, Baku, Losail. Monte Carlo
e' il caso opposto e per la stessa ragione - si frena in continuazione ma da
poco, e soprattutto non si va mai abbastanza forte da far entrare aria nelle
prese. E' il circuito in cui i freni si cuociono andando piano.
"""
from __future__ import annotations

# La finestra del carbonio, in gradi.
FREDDO = 380.0
CALDO = 950.0

# Dove vanno a finire i dischi e' il pareggio fra due cose: quanto calore ci
# si butta dentro e quanto se ne riesce a portare via. Sono due conti
# indipendenti, e confonderli e' il modo piu' rapido di sbagliare Monte Carlo.
#
# Il calore lo fa la frenata: quanto forte si arriva e quante volte si
# rallenta, che e' esattamente il carattere `braking` del circuito.
CALORE = 0.45
CALORE_FRENATA = 1.10

# A portarlo via e' l'aria che entra nelle prese, e l'aria entra se si va
# forte. E' il motivo per cui Monte Carlo e Singapore sono incubi per i freni
# pur non essendo circuiti da staccate violente: si frena in continuazione e
# non passa niente nei condotti. Montreal e' il caso opposto - li' e' proprio
# l'energia - e Losail e Suzuka non sono ne' l'una ne' l'altra cosa.
ARIA_FERMA = 0.62         # quanto raffredda un circuito lento
ARIA_VELOCE = 0.38        # e quanto ci aggiunge uno veloce
# e poi c'e' la macchina: il pezzo "raffreddamento" decide quanta di
# quell'aria arriva davvero ai dischi. Fra la meglio raffreddata della griglia
# e la peggio ballano trecentocinquanta gradi a Singapore, che e' la
# differenza fra arrivare in fondo e fermarsi al muro
RAFFREDDA_MIN = 0.80
RAFFREDDA_SCALA = 0.40

AMBIENTE = 1.0            # quanto pesa la temperatura dell'aria
SALTO = 501.0             # e quanto salgono i dischi su un circuito medio
# chi insegue prende l'aria calda di quello davanti, e nei condotti ne entra
# meno: e' la ragione per cui dietro a uno non si puo' stare per sempre
ARIA_SPORCA = 0.10

# Quanto in fretta i dischi seguono quello che gli si chiede. Molto piu' in
# fretta delle gomme: un disco si scalda in una staccata e si raffredda in un
# rettilineo, e quello che conta e' la media del giro.
RILASSA = 0.72

# Cosa costa starne fuori, in secondi al giro. Freddi si stacca lungo e si
# perde all'ingresso di ogni curva; caldi il pedale si allunga e si perde in
# fondo a ogni staccata.
PENA_FREDDO = 0.60
PENA_CALDO = 0.45
LARGHEZZA = 120.0         # quanti gradi fuori finestra valgono una unita'
ESPONENTE = 1.5

# E cosa costa in ricambi: sopra la finestra il disco si consuma, e un disco
# consumato e' un ritiro che aspetta. Il conto e' per giro, sulla distanza di
# una gara intera.
USURA = 0.75
USURA_RISCHIO = 1.35


def bersaglio(sim, e) -> float:
    """Dove stanno andando i dischi di questa vettura, in gradi."""
    tr = sim.track
    # quanto calore si butta dentro
    calore = CALORE + CALORE_FRENATA * float(tr.traits.get("braking", 0.5))
    calore *= max(0.85, min(1.15, e.push_mode)) ** 1.6
    # e quanto se ne porta via: l'aria del circuito per quella della macchina,
    # meno quella che non arriva perche' davanti c'e' qualcun altro
    veloce = min(1.0, max(0.0, float(tr.traits.get("power", 0.55))))
    aria = ARIA_FERMA + ARIA_VELOCE * veloce
    aria *= RAFFREDDA_MIN + RAFFREDDA_SCALA * max(0.0, min(1.0, e.raffredda))
    aria *= 1.0 - ARIA_SPORCA * e.dirty_air
    aria *= 1.0 + 0.45 * sim.weather.wet          # sull'acqua non si cuoce niente
    t = sim.cond.air_temp * AMBIENTE + SALTO * calore / max(0.30, aria)
    if sim.safety_car > 0:
        t = sim.cond.air_temp + 0.35 * (t - sim.cond.air_temp)
    return t


def aggiorna(sim, e, quota: float = 1.0) -> None:
    """Avvicina i dischi a dove stanno andando, e segna quanto si consumano."""
    passo = min(1.0, RILASSA * max(0.0, quota))
    e.freni_t += (bersaglio(sim, e) - e.freni_t) * passo
    sopra = max(0.0, (e.freni_t - CALDO) / LARGHEZZA)
    if sopra > 0.0:
        e.freni_usura += USURA * sopra * quota / max(10.0, float(sim.laps))


def fuori(e) -> float:
    """Quanto sono fuori finestra: negativo freddi, positivo caldi, 0 dentro."""
    if e.freni_t < FREDDO:
        return (e.freni_t - FREDDO) / LARGHEZZA
    if e.freni_t > CALDO:
        return (e.freni_t - CALDO) / LARGHEZZA
    return 0.0


def secondi(sim, e) -> float:
    """Quanto costano al giro, qui, i freni alla temperatura che hanno."""
    x = fuori(e)
    if x == 0.0:
        return 0.0
    quanto = 0.55 + 0.90 * float(sim.track.traits.get("braking", 0.5))
    if x < 0:
        return PENA_FREDDO * (-x) ** ESPONENTE * quanto
    return PENA_CALDO * x ** ESPONENTE * quanto


def rischio(e) -> float:
    """Di quanto i dischi consumati moltiplicano il rischio di rottura."""
    return 1.0 + USURA_RISCHIO * max(0.0, e.freni_usura)


def etichetta(e) -> str:
    """Come stanno, in una parola, per il tabellone."""
    x = fuori(e)
    if x < -0.15:
        return "freddi"
    if x > 0.15:
        return "caldi"
    return "in temperatura"
