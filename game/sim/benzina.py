"""La benzina: quanta se ne carica, quanta se ne risparmia, e quanto costa.

Fino a ieri il serbatoio non era una scelta: si partiva sempre con il dieci
per cento di margine, e quel margine bastava dappertutto. Cosi' la benzina non
esisteva - nessuno risparmiava, nessuno restava a piedi, e il muretto non
aveva niente da decidere.

Adesso il conto e' quello vero. Il consumo lo dice il circuito, il serbatoio lo
dice il regolamento, e i due numeri non tornano sempre: su una pista esigente i
settanta chili non bastano per fare tutta la gara col piede giu', e allora
qualcosa si deve dare indietro. Il muretto sceglie quanto caricare e quanto
chiedere; il pilota lo esegue, e quanto gli costa dipende da quanto e' pulito.

Il baratto e' quello di sempre, ed e' quello che rende la cosa una scelta e non
una tassa: alzare il piede prima della staccata regala benzina e toglie tempo.
Un decimo di passo vale circa il dodici per cento di consumo, e chi ha la mano
giusta lo paga meno degli altri.
"""

# ------------------------------------------------------------------ costanti
# Fin dove si stringe e fin dove si allunga. Sotto lo 0.90 non e' piu' gestire
# la benzina, e' fare un'altra gara; sopra l'1.10 la gomma non regge comunque.
PASSO_MIN = 0.90
PASSO_MAX = 1.10
# Quanto margine mette dentro il muretto sopra al bisogno. Poco: la benzina
# che avanza sono chili portati a spasso per tutta la gara, e sono decimi.
MARGINE_BASE = 1.030
MARGINE_FORBICE = 0.030    # quanto un muretto bravo lo stringe, e uno no
# Quanti giri di riserva si vogliono avere in mano prima di smettere di
# risparmiare: sotto questo si tira il piede, sopra si corre.
RISERVA_GIRI = 0.8
# Quanto conta la mano del pilota. Chi e' pulito col gas ricava piu' benzina
# dallo stesso decimo: l'esponente del consumo sale con lui.
MANO_MIN = 0.86
MANO_MAX = 1.16
# Sopra questo avanzo di benzina il muretto libera il pilota: c'e' da spendere
DA_SPENDERE = 1.6          # giri di benzina in piu' del necessario


def mano(e) -> float:
    """Quanto e' pulito col gas questo pilota, da 0 a 1.

    Risparmiare benzina non e' andare piano: e' alzare il piede nel punto
    giusto e riprenderlo senza scomporre la macchina. Chi ha la sensibilita'
    per la gomma ce l'ha anche per questo, e chi e' costante lo fa uguale a
    ogni giro invece che a giorni alterni.
    """
    return max(0.0, min(1.0, (0.6 * e.tyre_skill + 0.4 * e.consistency - 45.0) / 50.0))


def esponente(e, base: float) -> float:
    """L'esponente con cui il passo si trasforma in consumo, per questo pilota."""
    return base * (MANO_MIN + (MANO_MAX - MANO_MIN) * mano(e))


def carico(track, laps: int, consumo: float, serbatoio: float,
           strategia: float, kg_giro: float) -> float:
    """Quanti chili mette dentro il muretto alla partenza.

    Non e' un pieno: e' una previsione. Si carica quello che serve piu' un
    margine, e il margine e' il mestiere del muretto - chi lo sa fare lo tiene
    stretto e parte piu' leggero, chi non lo sa fare porta in giro chili
    inutili per tutta la gara. Sopra il serbatoio non si va comunque, e da li'
    in poi non e' piu' una scelta: e' un problema da risolvere in pista.
    """
    serve = laps * kg_giro * consumo
    margine = MARGINE_BASE + MARGINE_FORBICE * (75.0 - strategia) / 50.0
    return min(serbatoio, serve * max(1.0, margine))


def giri_in_mano(sim, e) -> float:
    """Quanti giri ci sono ancora nel serbatoio, al passo di adesso."""
    if getattr(sim, "senza_benzina", False):
        return 1e6
    from .energia import BENZINA_MAPPA, LIFT_BENZINA
    consumo = sim.burn_per_lap * e.consumo * BENZINA_MAPPA.get(e.mappa, 1.0)
    if e.lift_coast:
        consumo *= LIFT_BENZINA
    return e.fuel / max(0.01, consumo)


def margine_giri(sim, e) -> float:
    """Di quanti giri si e' avanti (positivo) o indietro (negativo) sul bisogno."""
    return giri_in_mano(sim, e) - (sim.laps - e.lap)


def passo_necessario(sim, e) -> float:
    """Il passo massimo con cui la benzina arriva in fondo.

    E' il conto rovesciato del consumo: se bruciare va come il passo elevato
    all'esponente, il passo che ci sta dentro e' la radice di quel rapporto.
    Sotto uno vuol dire che si deve alzare il piede, sopra uno che ce n'e'
    d'avanzo.
    """
    resta = sim.laps - e.lap
    if resta <= 0 or getattr(sim, "senza_benzina", False):
        return PASSO_MAX
    disponibili = giri_in_mano(sim, e)
    if disponibili <= 0.0:
        return PASSO_MIN
    from .weekend import PUSH_FUEL_EXP
    rapporto = disponibili / max(0.5, resta + RISERVA_GIRI)
    return rapporto ** (1.0 / max(0.5, esponente(e, PUSH_FUEL_EXP)))


def scegli_passo(sim, e, gap_avanti: float, gap_dietro: float) -> None:
    """Che passo tiene il pilota, adesso.

    Tre casi e sono quelli veri. Se la benzina non basta si stringe, e si
    stringe quel tanto che basta: risparmiare piu' del necessario e' regalare
    tempo, ed e' l'errore che fanno i muretti spaventati. Se ce n'e' d'avanzo e
    c'e' qualcosa da prendere o da difendere, si spende. Se ce n'e' d'avanzo e
    non c'e' nessuno intorno, si tiene il passo normale e i chili risparmiati
    restano in cassa per quando servira'.
    """
    if getattr(sim, "senza_benzina", False):
        e.passo_benzina = 0.0
        e.push_mode = 1.0
        return
    if e.is_player and e.passo_manuale is not None:
        # il giocatore ha messo la mano sul passo: comanda lui, anche quando
        # vuol dire non arrivare in fondo. Il muretto lo dice alla radio, e
        # poi fa quello che gli e' stato chiesto
        e.push_mode = e.passo_manuale
        e.passo_benzina = round(e.push_mode - 1.0, 3)
        return
    tetto = passo_necessario(sim, e)
    resta = sim.laps - e.lap
    avanzo = margine_giri(sim, e)
    if tetto < 1.0:
        # non basta: si stringe fin dove serve, non un decimo di piu'
        e.push_mode = max(PASSO_MIN, min(1.0, tetto))
    elif avanzo > DA_SPENDERE and (gap_avanti < 1.8 or gap_dietro < 1.8
                                   or (resta <= 6 and e.position <= 12)):
        # ce n'e' d'avanzo e c'e' un motivo: si spende, fin dove ce n'e'
        e.push_mode = min(PASSO_MAX, tetto, 1.0 + 0.06 * min(2.0, avanzo - DA_SPENDERE))
    else:
        e.push_mode = 1.0
    # e negli ultimi giri quello che resta nel serbatoio non serve a niente:
    # sono chili portati fino al traguardo per niente
    if 0 < resta <= 2 and avanzo > 0.5:
        e.push_mode = min(PASSO_MAX, max(e.push_mode, 1.0 + 0.05 * min(2.0, avanzo)))
    e.passo_benzina = round(e.push_mode - 1.0, 3)
