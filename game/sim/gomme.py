"""La temperatura della gomma: quella che decide se e' una gomma o un pattino.

Fino a ieri la gomma di questo gioco era due numeri - quanti giri ha fatto e
quanti ne regge - piu' una finestra di temperatura che guardava il termometro
dell'asfalto e basta. Cioe' una gomma che non si scalda guidando e non si
raffredda dietro alla safety car: la stessa alle otto del mattino e all'ultimo
giro, per tutti nello stesso modo, qualunque cosa stessero facendo.

Una gomma vera invece e' un pezzo di gara a se'. Ha una finestra di
temperatura larga una ventina di gradi, e dentro quella finestra tiene; sotto
non si accende - e' il giro dopo la sosta, quello in cui si perdono due
secondi e ogni tanto anche la macchina - e sopra si sfoglia, perde aderenza e
si consuma il doppio. Quello che la porta dentro o fuori dalla finestra e'
tutto quello che succede in gara:

  * le curve la scaldano e i rettilinei la raffreddano, per cui a Budapest e'
    sempre al limite e a Monza non si scalda mai;
  * chi spinge la scalda, chi gestisce la tiene giu';
  * chi sta attaccato a un altro cuoce: nell'aria sporca la macchina scivola
    di piu' e all'anteriore arriva meno aria fresca. E' il motivo per cui
    inseguire per dieci giri non e' gratis nemmeno quando si sta li';
  * dietro alla safety car si gela, e alla ripartenza si e' su gomme fredde;
  * e sul bagnato la gomma non arriva mai dove vorrebbe.

Non e' un numero in piu' sul cronometro: e' quello che rende diverso un giro
di lancio da un giro di gara, e una gomma tenuta bene da una buttata via in
cinque giri.
"""
from __future__ import annotations

# Dove vuole stare ogni mescola, in gradi, e quanto e' larga la finestra. Le
# morbide lavorano piu' fredde e si accendono prima; le dure vogliono essere
# maltrattate, e finche' non lo sono non danno niente.
FINESTRA = {"soft": 98.0, "medium": 104.0, "hard": 110.0,
            "inter": 72.0, "wet": 58.0}
# Quanti gradi si puo' stare fuori senza pagarla. I due numeri non sono uguali
# apposta, ed e' la gomma a non essere simmetrica: sotto la finestra la mescola
# rende meno ma la si riporta su - basta spingere un giro - mentre sopra si
# sfoglia, e quello che si e' sfogliato non torna. Il precipizio sta da una
# parte sola.
#
# Con la finestra stretta uguale dai due lati succedeva una cosa sbagliata:
# una vettura che gestiva il passo usciva dalla finestra dal basso su meta'
# calendario e non ci rientrava piu', perche' era proprio il gestire a
# raffreddarla. Un pilota che alza di un decimo non congela le gomme.
LARGO_FREDDO = 23.0
LARGO_CALDO = 14.0

# Dove va a finire la gomma se si continua cosi': l'asfalto piu' quello che le
# si sta chiedendo. Su una pista media, con l'asfalto a quaranta gradi e un
# passo di gara normale, sono un'ottantina di gradi sopra - che e' quello che
# si legge sui monitor.
SALTO = 62.0
# quanto conta quello che il circuito le chiede: dove si curva sempre si
# scalda, dove si tira dritto si raffredda
LAVORO = 0.55
# e chi la insegue la cuoce: meno aria fresca davanti e piu' scivolate
ARIA_SPORCA = 9.0
# quanti gradi al giro si avvicina a dove sta andando. Una gomma non ci
# arriva in un giro e non ci arriva mai del tutto: due o tre giri per
# accendersi, ed e' esattamente la durata di un giro di lancio
RILASSA = 0.42

# Con che temperatura si esce dai box. Con le coperte quasi in finestra, senza
# quelle si esce con la gomma dell'asfalto e ci si arrangia.
COPERTE = 80.0

# Quanto costa starne fuori, in secondi al giro, sulla pista media. Freddo e
# caldo non costano uguale: sul freddo non si ha aderenza ma si sa; sul caldo
# la gomma si muove sotto e la macchina non fa mai due curve uguali.
PENA_FREDDO = 1.30
PENA_CALDO = 1.05
ESPONENTE = 1.6
# e sopra la finestra si consuma piu' in fretta, che e' il vero prezzo
SOVRA_USURA = 0.55


def bersaglio(sim, e) -> float:
    """Dove sta andando la gomma di questa vettura, in gradi."""
    lavoro = LAVORO * float(getattr(sim.track, "pilota_rel", 1.0))
    lavoro += (1.0 - LAVORO)
    # quanto le si sta chiedendo: il passo scelto pesa piu' che linearmente,
    # perche' e' scivolando che la gomma si scalda. Ma non al quadrato: la
    # maggior parte del calore lo fa l'energia che passa nella gomma in curva,
    # e quella non cala del venti per cento perche' si e' alzato di un decimo
    spinta = max(0.85, min(1.15, e.push_mode)) ** 1.3
    deg = 0.72 + 0.55 * float(sim.track.traits.get("tyre_wear", 0.6))
    t = sim.cond.track_temp + SALTO * lavoro * spinta * deg
    t += ARIA_SPORCA * e.dirty_air
    if sim.safety_car > 0:
        # dietro alla safety car non si scalda niente: si va piano e basta
        t = sim.cond.track_temp + 0.30 * (t - sim.cond.track_temp)
    t -= 26.0 * sim.weather.wet
    # chi le gomme le sa tenere le porta dove vuole invece di subirle
    centro = FINESTRA.get(e.tyre, 100.0)
    return t + (centro - t) * 0.22 * (e.tyre_skill / 100.0)


def aggiorna(sim, e, quota: float = 1.0) -> None:
    """Avvicina la gomma a dove sta andando. `quota` e' la frazione di giro."""
    passo = min(1.0, RILASSA * max(0.0, quota))
    e.gomma_t += (bersaglio(sim, e) - e.gomma_t) * passo


def fuori(e) -> float:
    """Quanto e' fuori finestra: sotto -1 e' fredda, sopra +1 e' calda.

    Le due meta' si misurano con due righelli diversi, perche' la finestra non
    e' simmetrica: uno vale ventitre gradi sotto e uno quattordici sopra.
    """
    scarto = e.gomma_t - FINESTRA.get(e.tyre, 100.0)
    return scarto / (LARGO_CALDO if scarto > 0 else LARGO_FREDDO)


def secondi(sim, e) -> float:
    """Quanto costa al giro, qui, la gomma alla temperatura che ha."""
    x = fuori(e)
    if -1.0 < x < 1.0:
        return 0.0
    caldo = max(0.0, x - 1.0) ** ESPONENTE
    freddo = max(0.0, -x - 1.0) ** ESPONENTE
    grip = float(getattr(sim.track, "grip_rel", 1.0))
    return (PENA_CALDO * caldo + PENA_FREDDO * freddo) * grip


def usura(e) -> float:
    """Di quanto la temperatura moltiplica il consumo."""
    return 1.0 + SOVRA_USURA * max(0.0, fuori(e) - 1.0)


def dai_box(sim, comp: str) -> float:
    """Con che temperatura esce dai box una gomma nuova."""
    if getattr(sim, "senza_coperte", False):
        return sim.cond.track_temp + 6.0
    return min(COPERTE, FINESTRA.get(comp, 100.0))


def etichetta(e) -> str:
    """Come sta, in una parola, per il tabellone."""
    x = fuori(e)
    if x < -1.0:
        return "fredda"
    if x > 1.0:
        return "calda"
    return "in temperatura"
