"""L'energia elettrica in gara: quanta se ne riprende, quanta se ne spende.

Dal 2026 meta' della potenza e' elettrica - quattrocento kilowatt di termico,
trecentocinquanta di motore - e non c'e' piu' l'MGU-H: tutto quello che entra
nella batteria entra frenando. Da qui nasce il gioco vero della gara, che non
e' "quanto vai forte" ma "quando la spendi":

  * in un giro si recupera quello che il circuito concede - Monte Carlo frena
    venti volte da poco, Baku quattro volte da trecentoquaranta all'ora - e mai
    piu' di 8.5 MJ, che e' il tetto del regolamento;
  * la batteria ne tiene quattro: si puo' spendere piu' di quanto si recupera,
    ma per pochi giri, e poi bisogna ridarli indietro;
  * chi resta a secco arriva in fondo al rettilineo senza spinta - e' il
    clipping - e lo si vede sul cronometro prima ancora che sullo specchietto;
    se la batteria e' proprio vuota il dritto lo si fa quasi tutto col solo
    termico - il superclipping - e da li' non si esce in un giro;
  * la mappatura del motore e' l'altra manopola: si puo' tenerlo lungo e
    tirato, oppure smagrirlo per risparmiare benzina e non cuocerlo, e la
    differenza fra le due si vede sul cronometro e sul finale di gara;
  * chi insegue entro un secondo puo' chiedere l'override e riavere i
    trecentocinquanta kilowatt pieni fin quasi a fondo dritto, ma costa mezzo
    megajoule a botta: se lo si usa a ogni giro non si arriva in fondo alla
    gara con niente in mano;
  * e alzare il piede prima di frenare - il lift and coast - restituisce
    energia e benzina al prezzo di qualche decimo.

Tutto quello che sta qui dentro lavora su due numeri misurati sul circuito:
quanti megajoule si riprendono in un giro e quanti secondi vale, li', avere la
spinta elettrica invece di non averla.
"""
from __future__ import annotations

# I modi con cui si gestisce la batteria, e quanti megajoule al giro spendono
# in piu' o in meno rispetto al pareggio fra recupero e scarica.
MODI = ("ricarica", "normale", "attacco")
SPESA = {"ricarica": -0.55, "normale": 0.0, "attacco": 0.60}
ETICHETTA = {"ricarica": "RICARICA", "normale": "NORMALE", "attacco": "ATTACCO"}

# Quanto vale un megajoule speso in piu': una quota del valore che l'elettrico
# ha su quel circuito, spalmato sull'energia che ci gira in un giro. Non e'
# tutto perche' il primo megajoule si spende dove rende di piu' e l'ultimo no.
RESA = 0.55

# Il lift and coast: si alza il piede prima di frenare, si recupera di piu' e
# si consuma meno, e si perde qualche decimo.
LIFT_MJ = 0.30            # quanta energia in piu' rimette in cassa
LIFT_SECONDI = 0.28       # e quanto costa al giro
LIFT_BENZINA = 0.94       # in cambio consuma meno

# L'override: mezzo megajoule per riavere tutta la spinta fino quasi in fondo
# al dritto. Vale qualche decimo li' dove si prova a passare.
OVERRIDE_MJ = 0.5
OVERRIDE_GAP = 1.0        # si puo' chiedere solo stando entro un secondo
OVERRIDE_SPINTA = 0.55    # quanto pesa sul tentativo di sorpasso


def valore_mj(track) -> float:
    """Quanti secondi al giro vale un megajoule speso in piu', su questa pista."""
    energia = max(0.5, float(getattr(track, "energia_giro", 4.0)))
    return RESA * float(getattr(track, "ers_secondi", 8.0)) / energia


# Quanta energia rimette in cassa un giro di ricarica su un circuito medio, e
# qual e' il circuito medio: dove si frena molto la batteria si riempie in
# fretta, dove non si frena mai non c'e' modo di rimetterla dentro.
RECUPERO_RIF = 5.5


def recupero_giro(sim, e) -> float:
    """Quanto e' generoso questo circuito con chi vuole ricaricare, da 0 a 2."""
    base = float(getattr(sim.track, "energia_giro", RECUPERO_RIF)) / RECUPERO_RIF
    # sul bagnato si frena meno forte e si recupera meno
    base *= 1.0 - 0.20 * sim.weather.wet
    # chi ha la power unit migliore la riempie meglio
    return base * (0.92 + 0.16 * (e.ers_skill / 100.0))


# Sotto questa carica la batteria non regge piu' l'erogazione fino in fondo ai
# rettilinei: e' il clipping, e si paga a ogni dritto.
SOGLIA_CLIP = 0.9
CLIPPING = 0.09

# Piu' sotto ancora c'e' il superclipping: non e' che manchi la spinta negli
# ultimi metri, e' che non ce n'e' quasi per niente e il rettilineo lo si fa
# col solo termico. Non ci si casca per sbaglio e non se ne esce in un giro:
# per tornare a spingere bisogna rimetterne dentro parecchia, per questo la
# soglia di uscita sta molto piu' in alto di quella di entrata.
SOGLIA_SUPER = 0.30
SUPER_USCITA = 1.25
SUPER_CLIP = 0.14


def aggiorna_clip(sim, e) -> None:
    """Decide in che stato e' la batteria: piena, in clipping, o a terra."""
    e.clipping = e.carica < SOGLIA_CLIP
    if e.superclip:
        # se ne esce solo quando la cassa e' tornata decente
        e.superclip = e.carica < SUPER_USCITA
    else:
        e.superclip = e.carica < SOGLIA_SUPER
    if e.superclip:
        e.clipping = True


# --------------------------------------------------------------- mappature
# L'altra manopola della power unit. Non e' il pilota che spinge di piu': e'
# il motore che gira piu' lungo e piu' grasso. Si paga in benzina e in
# stress - le power unit di una stagione sono quattro, e la quinta e' dieci
# posizioni in griglia - e sui circuiti di potenza rende una volta e mezza
# quello che rende a Monte Carlo.
MAPPE = ("conservativa", "base", "spinta")
ETICHETTA_MAPPA = {"conservativa": "CONSERVATIVA", "base": "BASE", "spinta": "SPINTA"}
CORTO_MAPPA = {"conservativa": "CONS", "base": "BASE", "spinta": "SPIN"}

SECONDI_MAPPA = {"conservativa": 0.22, "base": 0.0, "spinta": -0.16}
BENZINA_MAPPA = {"conservativa": 0.93, "base": 1.0, "spinta": 1.06}
STRESS_MAPPA = {"conservativa": 0.70, "base": 1.0, "spinta": 1.65}

# Quanto pesa lo stress accumulato sul rischio di rompere qualcosa: un motore
# tenuto in spinta per tutta la gara arriva in fondo con quasi il doppio delle
# probabilita' di lasciarti a piedi. Il conto e' fatto attorno a quello che si
# consuma in una gara normale - meta' base, un po' di spinta, un po' di lungo -
# cosi' che a cambiare le probabilita' sia la gestione, non il modello.
USURA_RISCHIO = 1.20
USURA_TIPICA = 0.13


def rischio_motore(e) -> float:
    """Di quanto la gestione del motore moltiplica il rischio di rottura."""
    return max(0.80, 1.0 + USURA_RISCHIO * (e.motore_usura - USURA_TIPICA))


def valore_mappa(track) -> float:
    """Quanto rende cambiare mappatura qui: tanto dove conta il motore."""
    traits = getattr(track, "traits", None) or {}
    return 0.65 + 0.70 * float(traits.get("power", 0.55))


def passo_mappa(sim, e) -> float:
    """I secondi al giro che costa o regala la mappatura scelta."""
    secondi = SECONDI_MAPPA.get(e.mappa, 0.0) * valore_mappa(sim.track)
    # un motore cotto non da' piu' quello che dovrebbe, qualunque mappa metti
    secondi += 0.35 * max(0.0, e.motore_usura - 0.45)
    return secondi


def logora_motore(sim, e) -> None:
    """Segna sul libretto quanto gli si e' chiesto in questo giro."""
    quota = STRESS_MAPPA.get(e.mappa, 1.0) - 1.0
    e.motore_usura = max(0.0, e.motore_usura + quota / max(10.0, float(sim.laps)))


def scegli_mappa(sim, e, gap_avanti: float, gap_dietro: float) -> None:
    """Che mappa mette il muretto, se non la sceglie il giocatore.

    La regola e' quella vera: si smagrisce quando la benzina non basta o non
    c'e' nessuno da prendere, si allunga quando c'e' qualcuno da prendere o da
    tenere dietro, e negli ultimi giri non si guarda piu' in faccia a nessuno.
    """
    if e.is_player and e.mappa_manuale:
        return
    resta = sim.laps - e.lap
    giri_benzina = e.fuel / max(0.01, sim.burn_per_lap)
    if giri_benzina < resta * 1.02:
        e.mappa = "conservativa"            # prima di tutto si arriva in fondo
        return
    # e in un duello ci stanno in due: chi attacca allunga il motore, ma chi
    # si difende non e' che lo tenga corto per educazione
    duello = (gap_avanti < 1.6) or (gap_dietro < 1.6)
    if duello or (resta <= 5 and e.position <= 10):
        e.mappa = "spinta"
        return
    if e.motore_usura > 0.55 or giri_benzina < resta * 1.10:
        e.mappa = "conservativa"            # il motore deve durare
        return
    if gap_avanti > 4.0 and gap_dietro > 3.0:
        # in aria libera tirare il motore non serve a niente: quello che si
        # risparmia adesso ce l'hai in mano quando la gara si decide
        e.mappa = "conservativa"
        return
    e.mappa = "base"


def passo_giro(sim, e) -> float:
    """Chiude i conti dell'energia di un giro. Ritorna i secondi guadagnati.

    Il segno e' quello del cronometro: negativo vuol dire piu' veloci. In
    modo normale si spende esattamente quello che si recupera e la batteria
    non si muove; attaccando si spende di piu' e si va piu' forte finche' ce
    n'e'; ricaricando si spende meno e si va piu' piano, ma si rimette dentro.
    Chi la lascia scendere troppo arriva in fondo ai rettilinei senza spinta.
    """
    resa = recupero_giro(sim, e)
    voluta = SPESA.get(e.energy_mode, 0.0)
    if voluta < 0:
        voluta *= resa                  # si ricarica quanto la pista concede
    if e.lift_coast:
        voluta -= LIFT_MJ * resa
    if voluta < 0:
        # e solo fin dove ci sta: quello che non entra in batteria non lo si
        # recupera nemmeno, e non costa niente non averlo recuperato
        voluta = max(voluta, -(sim.batteria_max - e.carica))
    else:
        voluta = min(voluta, max(0.0, e.carica))
    e.carica = max(0.0, min(sim.batteria_max, e.carica - voluta))
    guadagno = -voluta * valore_mj(sim.track)
    if e.lift_coast:
        guadagno += LIFT_SECONDI
    # clipping: con la batteria quasi vuota l'ultima parte di ogni rettilineo
    # si fa senza spinta. Con la batteria a terra non e' l'ultima parte: e'
    # quasi tutto il rettilineo, e sono secondi, non decimi.
    valore = float(getattr(sim.track, "ers_secondi", 8.0))
    aggiorna_clip(sim, e)
    if e.clipping:
        manca = 1.0 - min(1.0, e.carica / SOGLIA_CLIP)
        guadagno += CLIPPING * manca * valore
    if e.superclip:
        vuota = 1.0 - min(1.0, e.carica / SUPER_USCITA)
        guadagno += SUPER_CLIP * vuota * valore
    return guadagno


def carica_iniziale(sim) -> float:
    """La batteria con cui si va in griglia: piena, come tutti."""
    return sim.batteria_max


def puo_override(sim, e, gap_s: float) -> bool:
    """Si puo' chiedere l'override: entro un secondo e con energia in cassa.

    Chi e' in superclipping non lo chiede nemmeno: quei mezzi megajoule, se
    anche ce li ha, gli servono per non fare il resto del giro a spinta.
    """
    return (gap_s <= OVERRIDE_GAP and e.carica >= OVERRIDE_MJ and not e.superclip
            and e.status == "running" and sim.safety_car <= 0)


def usa_override(sim, e) -> float:
    """Spende il mezzo megajoule dell'override. Ritorna quanta spinta da'."""
    e.carica = max(0.0, e.carica - OVERRIDE_MJ)
    e.override_usi += 1
    return OVERRIDE_SPINTA


def scegli_modo(sim, e, avanti, dietro, gap_avanti: float, gap_dietro: float) -> None:
    """Cosa fa il muretto con l'energia, se non lo decide il giocatore.

    Non e' un interruttore a caso: si spende quando serve - per stare addosso a
    chi si vuole passare, o per non farsi passare - e si ricarica quando non
    serve a niente, cioe' quando davanti e dietro non c'e' nessuno. E si guarda
    anche cosa ha in mano l'altro: attaccare uno che ha la batteria piena e'
    buttare energia, attaccare uno a secco e' il momento giusto.
    """
    if e.is_player and e.energy_manual:
        return
    resta = sim.laps - e.lap
    if e.superclip or e.carica < sim.batteria_max * 0.22:
        e.energy_mode = "ricarica"          # prima si rimette qualcosa dentro
        e.lift_coast = True
        return
    e.lift_coast = False
    vicino_avanti = avanti is not None and gap_avanti < 1.6
    vicino_dietro = dietro is not None and gap_dietro < 1.2
    if vicino_avanti:
        # se chi sta davanti e' a secco vale la pena spingere: non puo' rispondere
        scarico = avanti.superclip or avanti.carica < sim.batteria_max * 0.30
        e.energy_mode = "attacco" if (scarico or e.carica > sim.batteria_max * 0.55) else "normale"
    elif vicino_dietro:
        e.energy_mode = "attacco" if e.carica > sim.batteria_max * 0.45 else "normale"
    elif resta <= 3 and e.position <= 10:
        e.energy_mode = "attacco"           # negli ultimi giri non serve tenerla
    elif gap_avanti > 3.5 and gap_dietro > 3.5 and e.carica < sim.batteria_max * 0.92:
        e.energy_mode = "ricarica"          # in aria libera si mette via
        e.lift_coast = e.fuel_warned
    else:
        e.energy_mode = "normale"
