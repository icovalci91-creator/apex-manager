"""Come si muovono due macchine che si battono.

La gara decide in un attimo se un sorpasso riesce: il conto e' tarato sui
numeri veri (quanti sorpassi a Monza, quanti a Monte Carlo) e resta com'e'.
Prima pero' anche il movimento era di un attimo: chi attaccava si ritrovava
sei metri davanti da un passo all'altro, chi difendeva arretrava di colpo, e
sulla mappa la macchina saltava.

Qui la decisione diventa un movimento, fatto come si fa in pista. Chi attacca
esce dalla scia, si affianca lungo il dritto con qualche decina di km/h in
piu' - mai piu' di quanto scia e override possono dare - e chiude il sorpasso
in staccata; chi lo subisce perde il suo in uscita di curva, un po' alla
volta. Un attacco che non riesce arriva al massimo col muso a meta' macchina,
e in staccata si rimette dietro, con i metri persi per aver frenato tardi.
Chi difende sposta la macchina all'interno prima della staccata e paga la
traiettoria piu' lenta. E il sorpasso finisce nella cronaca quando e' fatto,
non quando e' deciso.

Ogni spostamento e' una "spinta": tanti metri in tanti secondi, con la
partenza e l'arrivo morbidi, che la gara somma alla strada fatta a ogni passo.
Due macchine in duello non si fanno da tappo a vicenda finche' dura: e' li'
che stanno affiancate.
"""
from __future__ import annotations

# quanto piu' veloce puo' andare chi attacca: scia, override e staccata
# ritardata insieme valgono una trentina di km/h, non di piu'
VREL_MAX = 8.0
FRENATA_S = 0.9         # la staccata, dove il sorpasso si chiude
DURATA_MIN = 1.8
DURATA_MAX = 9.0
USCITA_S = 1.6          # chi e' stato passato perde il suo uscendo dalla curva
DAVANTI_M = 6.0         # di quanto e' davanti chi ha passato, a manovra finita
AFFIANCATO_M = 3.0      # un attacco che non riesce arriva col muso fin qui
RIENTRO_S = 1.8         # e in tanto si rimette in fila
SCAMBIO_S = 4.0         # "lascialo passare": si alza il piede sul dritto
RIENTRA_MS = 6.0        # a che ritmo chi e' troppo addosso si rimette a distanza


def _liscia(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def spingi(e, metri: float, secondi: float, ritardo: float = 0.0) -> None:
    """Sposta `e` di `metri` lungo la pista in `secondi`, dopo `ritardo`."""
    if abs(metri) < 1e-6:
        return
    e.spinte.append([float(metri), max(0.05, float(secondi)), -float(ritardo)])


def annuncia(e, secondi: float, testo: str, tipo: str, **dati) -> None:
    """Una riga di cronaca da scrivere fra tanti secondi: quando succede."""
    e.annunci.append([float(secondi), testo, tipo, dati])


def avanza(e, dt: float) -> list:
    """Applica le spinte di questo passo; restituisce la cronaca arrivata a
    scadenza, come (testo, tipo, dati)."""
    if e.spinte:
        tenute = []
        for s in e.spinte:
            metri, durata, t = s
            t1 = t + dt
            e.dist += metri * (_liscia(t1 / durata) - _liscia(t / durata))
            s[2] = t1
            if t1 < durata:
                tenute.append(s)
        e.spinte = tenute
    if e.fuori_t > 0.0:
        e.fuori_t = max(0.0, e.fuori_t - dt)
    if e.duello_t > 0.0:
        e.duello_t = max(0.0, e.duello_t - dt)
        if e.duello_t == 0.0:
            e.duello_con = ""
    pronti = []
    if e.annunci:
        resto = []
        for a in e.annunci:
            a[0] -= dt
            (pronti if a[0] <= 0.0 else resto).append(a)
        e.annunci = resto
    return [(a[1], a[2], a[3]) for a in pronti]


def duello(a, b, secondi: float) -> None:
    t = max(secondi, a.duello_t if a.duello_con == b.driver_id else 0.0)
    a.duello_con, b.duello_con = b.driver_id, a.driver_id
    a.duello_t = b.duello_t = t


def in_duello(a, b) -> bool:
    """Stanno combattendo fra loro, o uno dei due e' fuori traiettoria: nessuno
    fa da tappo all'altro."""
    return ((a.duello_t > 0.0 and a.duello_con == b.driver_id)
            or (b.duello_t > 0.0 and b.duello_con == a.driver_id)
            or a.fuori_t > 0.0 or b.fuori_t > 0.0)


def accoda(dietro, davanti, minima: float, dt: float) -> None:
    """Dietro si resta a `minima` metri. Chi si ritrova piu' vicino - finito un
    attacco, con la scia che l'ha portato sotto - si rimette a distanza
    frenando, non di colpo; ma dentro all'altro non ci entra mai."""
    eccesso = dietro.dist - (davanti.dist - minima)
    if eccesso <= 0.0:
        return
    troppo = eccesso - (minima - 1.5)
    dietro.dist -= max(troppo, min(eccesso, RIENTRA_MS * dt))


def occupato(e) -> bool:
    """E' gia' dentro a una manovra: non se ne comincia un'altra."""
    return e.duello_t > 0.0 or e.fuori_t > 0.0


def secondi_alla_staccata(track, frazione_tempo: float, giro_s: float,
                          corta: bool = False) -> float:
    """Quanto manca, da qui, alla fine della zona di sorpasso: la staccata."""
    passo = 1.0 / 360.0
    for k in range(1, 121):
        f = frazione_tempo + k * passo
        if track.zona_di(track.pos_at(f), corta=corta) <= 0.0:
            return k * passo * giro_s
    return 120 * passo * giro_s


def zona(track, frazione_tempo: float, corta: bool = False) -> float:
    """Quanto vale come posto per passare il punto dove si e' adesso.

    La tabella dei posti e' fatta sul tracciato in metri; la gara conta il
    giro sul cronometro. Si passa dall'uno all'altro: sul dritto si va forte,
    e la stessa frazione di giro in tempo e' molto piu' avanti in metri."""
    return track.zona_di(track.pos_at(frazione_tempo), corta=corta)


def _durata(gap_m: float, alla_staccata: float) -> float:
    serve = (max(0.0, gap_m) + DAVANTI_M) / VREL_MAX
    return max(DURATA_MIN, min(DURATA_MAX, max(alla_staccata + FRENATA_S, serve)))


def sorpasso(dietro, davanti, gap_m: float, perdita_m: float, alla_staccata: float,
             lato: float, lato_difesa: float | None = None) -> float:
    """Il sorpasso che riesce. Restituisce quanto dura, in secondi."""
    d = _durata(gap_m, alla_staccata)
    spingi(dietro, max(0.0, gap_m) + DAVANTI_M, d)
    spingi(davanti, -perdita_m, d + USCITA_S)
    duello(dietro, davanti, d + 0.5)
    dietro.manovra, dietro.manovra_t = lato, d + 1.0
    if lato_difesa is not None:
        davanti.manovra, davanti.manovra_t = lato_difesa, d + 1.0
    return d


def attacco_fallito(dietro, davanti, gap_m: float, costo_m: float, alla_staccata: float,
                    lato: float, lato_difesa: float | None = None,
                    quanto: float = 1.0) -> float:
    """Ci prova, si affianca quanto puo', e in staccata si rimette dietro.

    `quanto` meno di uno e' solo un'occhiata: esce dalla scia, vede che non
    c'e' e rientra, senza arrivare di fianco e senza perdere niente."""
    d1 = max(1.2, min(6.0, alla_staccata + 0.5))
    avvicina = max(0.0, min(gap_m - AFFIANCATO_M, VREL_MAX * 0.8 * d1)) * quanto
    spingi(dietro, avvicina, d1)
    spingi(dietro, -(avvicina + costo_m), RIENTRO_S, ritardo=d1)
    duello(dietro, davanti, d1 + RIENTRO_S)
    dietro.manovra, dietro.manovra_t = lato, d1 + 0.8
    if lato_difesa is not None:
        davanti.manovra, davanti.manovra_t = lato_difesa, d1 + 0.8
    return d1 + RIENTRO_S


def difesa(davanti, costo_m: float, alla_staccata: float, lato: float) -> None:
    """Si sposta all'interno prima della staccata, e la curva viene piu' lenta."""
    d = max(1.2, alla_staccata + FRENATA_S)
    spingi(davanti, -costo_m, d)
    davanti.manovra, davanti.manovra_t = lato, d + 0.8


def scambio(davanti, dietro, gap_m: float, lato: float) -> float:
    """Il compagno si sposta e alza il piede: l'altro passa senza lottare."""
    meta = max(0.0, gap_m) / 2.0 + DAVANTI_M * 0.7
    spingi(davanti, -meta, SCAMBIO_S)
    spingi(dietro, meta, SCAMBIO_S)
    duello(davanti, dietro, SCAMBIO_S + 0.5)
    davanti.manovra, davanti.manovra_t = lato, SCAMBIO_S
    dietro.manovra, dietro.manovra_t = -lato, SCAMBIO_S
    return SCAMBIO_S


def fuori(e, secondi_persi: float, velocita: float, lato: float) -> None:
    """Un errore, un lungo, il passaggio largo per l'Attack Mode: la macchina
    esce dalla traiettoria e rallenta, gli altri le passano di fianco. Il
    tempo perso e' quello di prima; solo che si perde andando piano, non
    sparendo indietro di trecento metri."""
    durata = secondi_persi * 1.2 + 1.5
    spingi(e, -secondi_persi * velocita, durata)
    e.fuori_t = max(e.fuori_t, durata)
    e.manovra, e.manovra_t = lato, durata


# ---------------------------------------------------------------- la partenza
# Da fermi, non gia' lanciati: ognuno ha i suoi riflessi al semaforo e il suo
# stacco di frizione, e nei primi secondi si guadagna o si perde un posto
# restando affiancati fino alla prima curva. Finche' dura lo scatto non c'e'
# coda: e' li' che le posizioni cambiano davvero.
LANCIO_S = 5.0          # da fermi alla velocita' di gara
PARTENZA_S = 8.0        # fin qui niente coda e niente duelli: si va alla prima curva


def scatto(e, rng) -> float:
    """Il ritardo di ognuno al via: riflessi piu' pattinamento. Chi e' costante
    parte bene piu' spesso."""
    if e.scatto < 0.0:
        costanza = float(getattr(e, "consistency", 80.0))
        e.scatto = max(0.10, rng.gauss(0.22, 0.04)
                       + abs(rng.gauss(0.0, 0.10 * (1.0 + (80.0 - costanza) / 60.0))))
    return e.scatto


def lancio(e, tempo: float, rng) -> float:
    """Quanto della velocita' di gara ha gia', a tanti secondi dal via."""
    if tempo >= LANCIO_S + 1.0:
        return 1.0
    u = tempo - scatto(e, rng)
    if u <= 0.0:
        return 0.0
    return min(1.0, (u / LANCIO_S) ** 0.75)


# ------------------------------------------------------------------ i box
def corsia_dopo_m(track) -> float:
    """Quanti metri di corsia box ci sono dopo la linea del traguardo: la
    sosta si decide sulla linea, e da li' la macchina percorre questi."""
    fatto = getattr(track, "_corsia_dopo", None)
    if fatto is not None:
        return fatto
    pts = getattr(track, "points", None) or []
    box = getattr(track, "pit_points", None) or []
    metri = 0.0
    if len(pts) > 8 and len(box) >= 4:
        giro = sum(((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5
                   for i in range(len(pts)))
        scala = track.length_km * 1000.0 / max(1e-9, giro)
        x0, y0 = pts[0]
        k = min(range(len(box)), key=lambda i: (box[i][0] - x0) ** 2 + (box[i][1] - y0) ** 2)
        resto = sum(((box[i][0] - box[i - 1][0]) ** 2 + (box[i][1] - box[i - 1][1]) ** 2) ** 0.5
                    for i in range(k + 1, len(box)))
        metri = max(0.0, min(800.0, resto * scala))
    track._corsia_dopo = metri
    return metri


def entra_box(e, sosta: float, perdita: float, track, v_media: float) -> float:
    """La sosta: si percorre la corsia a velocita' limitata, ci si ferma al
    garage e si riparte. Il tempo perso e' lo stesso di sempre - `sosta` piu'
    `perdita` - ma la macchina si muove invece di restare ferma sulla linea."""
    metri = corsia_dopo_m(track)
    e.pit_metri = metri
    e.pit_fatti = 0.0
    e.pit_sosta = sosta
    e.pit_totale = sosta + perdita + metri / max(10.0, v_media)
    return e.pit_totale


def in_box(e) -> None:
    """Dove sta nella corsia, dal tempo che resta della sosta."""
    metri = getattr(e, "pit_metri", 0.0)
    if metri <= 0.0 or e.pit_totale <= 0.0:
        return
    passato = e.pit_totale - max(0.0, e.pit_timer)
    guida = max(0.1, e.pit_totale - e.pit_sosta)
    al_garage = guida * 0.4
    if passato < al_garage:
        x = metri * 0.4 * passato / al_garage
    elif passato < al_garage + e.pit_sosta:
        x = metri * 0.4
    else:
        x = metri * (0.4 + 0.6 * min(1.0, (passato - al_garage - e.pit_sosta)
                                     / max(0.1, guida - al_garage)))
    e.dist += x - e.pit_fatti
    e.pit_fatti = x


def fermo_ai_box(e) -> bool:
    """E' fermo al garage, con i meccanici addosso."""
    if e.status != "pitting" or getattr(e, "pit_metri", 0.0) <= 0.0:
        return e.status == "pitting"
    passato = e.pit_totale - e.pit_timer
    al_garage = max(0.1, e.pit_totale - e.pit_sosta) * 0.4
    return al_garage <= passato < al_garage + e.pit_sosta


# ------------------------------------------------------------ la safety car
SC_CODA_M = 22.0        # dietro alla safety car ci si mette a qualche macchina di distanza
SC_RINCORSA = 1.15      # e chi e' staccato la raggiunge
SC_DAVANTI_M = 70.0     # la safety car sta davanti al primo


def rincorsa_sc(coda: list) -> dict:
    """Sotto safety car il gruppo si compatta: chi e' staccato va un po' piu'
    forte finche' non e' in fila. Il primo segue la safety car."""
    fattori = {}
    for k in range(1, len(coda)):
        gap = coda[k - 1].dist - coda[k].dist
        if gap > SC_CODA_M:
            fattori[coda[k].driver_id] = SC_RINCORSA
    return fattori
