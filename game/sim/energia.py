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
        # si ricarica quanto la pista concede, e solo fin dove ci sta: alzare
        # il piede con la batteria gia' piena e' tempo buttato via
        voluta = max(voluta * resa, -(sim.batteria_max - e.carica))
    else:
        voluta = min(voluta, max(0.0, e.carica))
    if e.lift_coast:
        voluta -= LIFT_MJ * resa
    e.carica = max(0.0, min(sim.batteria_max, e.carica - voluta))
    guadagno = -voluta * valore_mj(sim.track)
    if e.lift_coast:
        guadagno += LIFT_SECONDI
    # clipping: con la batteria quasi vuota l'ultima parte di ogni rettilineo
    # si fa senza spinta
    e.clipping = e.carica < SOGLIA_CLIP
    if e.clipping:
        manca = 1.0 - e.carica / SOGLIA_CLIP
        guadagno += CLIPPING * manca * float(getattr(sim.track, "ers_secondi", 8.0))
    return guadagno


def carica_iniziale(sim) -> float:
    """La batteria con cui si va in griglia: piena, come tutti."""
    return sim.batteria_max


def puo_override(sim, e, gap_s: float) -> bool:
    """Si puo' chiedere l'override: entro un secondo e con energia in cassa."""
    return (gap_s <= OVERRIDE_GAP and e.carica >= OVERRIDE_MJ
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
    if e.carica < sim.batteria_max * 0.22:
        e.energy_mode = "ricarica"          # prima si rimette qualcosa dentro
        e.lift_coast = True
        return
    e.lift_coast = False
    vicino_avanti = avanti is not None and gap_avanti < 1.6
    vicino_dietro = dietro is not None and gap_dietro < 1.2
    if vicino_avanti:
        # se chi sta davanti e' a secco vale la pena spingere: non puo' rispondere
        scarico = avanti.carica < sim.batteria_max * 0.30
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
