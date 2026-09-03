"""L'inverno: i mesi in cui nasce la macchina che correra' l'anno prossimo.

D'inverno non si sviluppa: si riprogetta. E' un lavoro diverso da quello che
si fa fra una gara e l'altra, e la differenza e' il tempo. In stagione un
pacchetto grande blocca cinquantadue persone per sei gare e quando arriva la
macchina e' gia' un'altra; d'inverno ci sono quattro mesi in cui nessuno deve
correre, tutti i reparti lavorano insieme, e quello che esce non e' un pezzo
nuovo su una macchina vecchia - e' una macchina nuova che dovrebbe risolvere
i problemi di quella vecchia.

Il giro e' quello vero. A fine stagione i responsabili si siedono e dicono
cosa non ha funzionato: non opinioni, i numeri della stagione appena finita -
dove si e' persi rispetto alla griglia, cosa si e' rotto, quali gomme si sono
mangiate. Da quei problemi escono i cantieri d'inverno, ognuno con dentro un
reparto, delle settimane e dei soldi. Il patron decide quali aprire, e il
vincolo e' doppio: le settimane dell'inverno e la cassa.

E poi conta chi lo fa. Con gli stessi quattro mesi e gli stessi soldi, un
reparto forte con strumenti buoni chiude tre cantieri su quattro e li chiude
bene; uno debole ne chiude due e su uno si accorge a marzo di aver peggiorato
le cose. E' lo stesso criterio di tutto il resto: chi lavora meglio migliora
di piu'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C

# Quante settimane di lavoro vero ha un inverno, e quante ne ha un reparto.
# Sono il doppio abbondante di quelle che si trovano fra due gare: e' questo
# che rende l'inverno il momento in cui si cambia davvero qualcosa, e non un
# aggiornamento un po' piu' grosso.
SETTIMANE = 16
# Quante di quelle settimane il reparto riesce a coprire in parallelo. Non e'
# una sola coda, e non sono nemmeno tre: fra un anno e l'altro le modifiche
# sono tante, perche' su alcune ci si lavora da mesi e d'inverno c'e' il tempo
# di assemblarle e di svilupparle ancora. Soprattutto non c'e' la gara: niente
# trasferte, niente pacchetti da mandare in pista per domenica, niente muretto
# da seguire - tutto quello che in stagione porta via attenzione, risorse e
# fatica qui non c'e', e si concentra tutto sulla macchina nuova.
SQUADRE_PARALLELE = 5

# I cantieri: quanto tempo chiedono e quanto costano, per taglia. Il conto e'
# in settimane di una delle squadre parallele, e in milioni.
TAGLIE = {
    "ritocco":   {"settimane": 3,  "costo": 1.4, "resa": 1.0,
                  "label": "ritocco", "desc": "Si tocca quello che c'e' senza rimetterlo in discussione."},
    "revisione": {"settimane": 7,  "costo": 4.2, "resa": 2.8,
                  "label": "revisione", "desc": "Si rifa' il gruppo, tenendo il concetto."},
    "concetto":  {"settimane": 13, "costo": 9.5, "resa": 6.4,
                  "label": "concetto nuovo", "desc": "Si riparte dal foglio bianco. O si azzecca, o si perde l'anno."},
}

# Quale reparto guida il lavoro su ogni area, e con che strumenti si valida.
REPARTO_AREA = {
    "carico":       "aero",
    "efficienza":   "aero",
    "potenza":      "powertrain",
    "trazione":     "progetto",
    "frenata":      "progetto",
    "gomme":        "progetto",
    "affidabilita": "powertrain",
}

# Quanto pesa, sul risultato di un cantiere, ognuna delle tre cose che il
# patron puo' comprare. Sono i tre assi di cui si parla sempre: le persone,
# gli strumenti con cui lavorano, e i soldi che si mettono sul tavolo.
PESO_UOMINI = 0.42
PESO_STRUMENTI = 0.33
PESO_SOLDI = 0.25

# La forbice vera della griglia, la stessa con cui si misura il muro dello
# sviluppo: sotto questa non si scende e sopra non si sale.
QUALITA_MIN, QUALITA_MAX = 62.0, 92.0

# Come esce un cantiere. Sono le stesse quattro bande dello sviluppo in
# stagione, perche' e' lo stesso mestiere fatto con piu' tempo: la differenza
# la fa che d'inverno un lavoro riuscito vale molto di piu'.
BANDE = {
    "fallito":   (-0.35, 0.10),
    "sottotono": (0.35, 0.70),
    "in linea":  (0.85, 1.15),
    "oltre":     (1.25, 1.70),
}


@dataclass
class Problema:
    """Una cosa che nella macchina di quest'anno non andava.

    Non e' un'opinione: e' un numero della stagione appena finita.
    """
    area: str
    label: str
    gravita: float             # 0..1, quanto pesa rispetto alla griglia
    distacco: float            # punti di profilo dal migliore
    voce: str = ""             # come lo racconta chi lo ha in mano
    reparto: str = "aero"


@dataclass
class Cantiere:
    """Un lavoro d'inverno messo in programma."""
    area: str
    label: str
    taglia: str
    settimane: int
    costo: float
    atteso: float              # punti di prestazione previsti
    fiducia: float             # 0..1, quanto il reparto se la sente
    reparto: str = "aero"
    esito: str = ""            # come e' andata, a lavori finiti
    reso: float = 0.0          # e quanto ha portato davvero


# ------------------------------------------------------- i problemi veri
def problemi(gs, team) -> list:
    """Cosa non ha funzionato quest'anno, in ordine di gravita'.

    Si guarda il profilo della vettura contro quello della griglia: le aree in
    cui si e' piu' lontani dal migliore sono i problemi, e quanto si e'
    lontani e' la gravita'. Chi e' primo dappertutto non ha problemi da
    risolvere e d'inverno cerca prestazione, che e' un'altra cosa.
    """
    from . import engineering
    mio = engineering.car_profile(team, gs)
    griglia = {t.id: engineering.car_profile(t, gs) for t in gs.teams.values()}
    out = []
    for area, label in engineering.AREAS.items():
        valori = [g[area] for g in griglia.values()]
        migliore = max(valori)
        distacco = migliore - mio[area]
        # la gravita' e' il distacco riportato sulla scala del profilo: un'area
        # in cui si e' a meta' griglia non e' un problema, e' normale
        grav = max(0.0, min(1.0, distacco / 55.0))
        out.append(Problema(area=area, label=label, gravita=round(grav, 3),
                            distacco=round(distacco, 1),
                            reparto=REPARTO_AREA.get(area, "aero")))
    out.sort(key=lambda p: -p.gravita)
    return out


# --------------------------------------------------- i colloqui di fine anno
# Chi parla di cosa. Non e' un elenco di frasi: e' che ogni responsabile ha in
# mano un pezzo della macchina e vede quello, e a fine stagione dice quello
# che ha visto lui.
VOCI = {
    "carico":       ("head_of_aero", "Aerodinamica"),
    "efficienza":   ("head_of_aero", "Aerodinamica"),
    "potenza":      ("head_of_powertrain", "Powertrain"),
    "trazione":     ("chief_designer", "Progetto"),
    "frenata":      ("chief_designer", "Progetto"),
    "gomme":        ("chief_designer", "Progetto"),
    "affidabilita": ("chief_mechanic", "Affidabilita'"),
}

# Come raccontano un problema, a seconda di quanto e' grosso. Sono le parole
# che si sentono davvero in una riunione di fine anno.
FRASI = {
    "carico": ("Nelle curve veloci non stiamo attaccati: dove gli altri sono piatti "
               "noi alziamo il piede.",
               "Di carico ce n'e', ma lo paghiamo troppo in scorrevolezza."),
    "efficienza": ("Sui rettilinei siamo fermi: la macchina fa muro contro l'aria "
                   "e in fondo al dritto ce lo ritroviamo davanti chiunque.",
                   "Di resistenza ne abbiamo un filo di troppo, si vede solo dove "
                   "si viaggia."),
    "potenza": ("Il gruppo non da' quello che dovrebbe, e quando lo tiriamo "
                "scalda: siamo corti dappertutto.",
                "In dispiegamento ci manca qualcosa nell'ultimo pezzo di dritto."),
    "trazione": ("Fuori dalle lente non riusciamo a scaricare a terra: la "
                 "macchina pattina e le gomme se ne vanno.",
                 "In trazione siamo onesti, si perde solo dove si tira fuori "
                 "dalle lentissime."),
    "frenata": ("In staccata non e' stabile: i piloti non si fidano e frenano "
                "prima, ed e' li' che si perdono i decimi.",
                "Sotto ai freni qualcosa da guadagnare c'e', ma non e' la nostra "
                "prima cosa."),
    "gomme": ("Mangiamo le gomme: in gara siamo un'altra macchina rispetto al "
              "sabato, e sulle piste che consumano non ci siamo.",
              "Le gomme le gestiamo, ma sotto stress qualcosa si perde."),
    "affidabilita": ("Ci siamo rotti troppe volte: ci sono punti fragili che "
                     "vanno rifatti, non rattoppati.",
                     "Qualche noia l'abbiamo avuta, niente di strutturale."),
}


def colloqui(gs, team, quanti: int = 7) -> list:
    """La riunione di fine stagione: chi ha in mano cosa dice cosa non andava.

    Non e' colore. Ogni frase esce da un numero della stagione appena finita -
    il distacco dal migliore della griglia in quell'area - e il responsabile
    che la dice e' quello che quel pezzo lo ha davvero in mano. Alla fine
    ognuno propone il suo cantiere, con dentro le sue settimane e i suoi
    soldi, e quanto se la sente lo dicono i suoi strumenti e la sua gente.
    """
    out = []
    for p in problemi(gs, team)[:quanti]:
        ruolo, ripiego = VOCI.get(p.area, ("technical_director", "Il tecnico"))
        persona = team.role(ruolo)
        chi = persona.name if persona else ripiego
        grosso, piccolo = FRASI.get(p.area, ("Qui siamo indietro.", "Qui si puo' limare."))
        testo = grosso if p.gravita > 0.30 else piccolo
        proposte = [proposta(gs, team, p, t) for t in TAGLIE]
        out.append({"problema": p, "chi": chi, "ruolo": ruolo, "testo": testo,
                    "proposte": proposte})
    return out


def parere_tecnico(gs, team) -> str:
    """Cosa dice il direttore tecnico dell'inverno che si sta per fare.

    E' il quadro d'insieme che il patron si aspetta prima di firmare: quante
    settimane ci sono, quanto vale il reparto che le usera', e se conviene
    concentrare o spargere.
    """
    from . import development
    td = team.role("technical_director")
    chi = td.name if td else "Il direttore tecnico"
    aero = qualita_reparto(team, "aero")
    attrezzi = qualita_strumenti(team, "aero")
    if aero > 0.70 and attrezzi > 0.70:
        come = ("Con la gente e gli strumenti che abbiamo possiamo permetterci un "
                "concetto nuovo: se lo azzecchiamo cambiamo categoria.")
    elif attrezzi < 0.40:
        come = ("Con la galleria che abbiamo un concetto nuovo e' una scommessa: "
                "non sapremmo dire se funziona finche' non lo vediamo in pista. "
                "Meglio revisioni su cose che conosciamo.")
    elif aero < 0.40:
        come = ("Il reparto non ha la profondita' per aprire tre cantieri seri: "
                "meglio due fatti bene che tre lasciati a meta'.")
    else:
        come = ("Possiamo aprire tre cantieri e portarli in fondo, ma uno solo "
                "puo' essere un concetto nuovo: gli altri due tenerli su cose "
                "che sappiamo gia' fare.")
    return f"{chi}: {come}"


# ------------------------------------------------- quanto vale chi ci lavora
def qualita_reparto(team, reparto: str) -> float:
    """Quanto vale il reparto che guida quel lavoro, da 0 a 1."""
    forza = {"aero": team.aero_strength,
             "progetto": team.mech_strength,
             "powertrain": (team.pu_strength if team.works else 60.0)}.get(reparto, 70.0)
    return max(0.0, min(1.0, (forza - QUALITA_MIN) / (QUALITA_MAX - QUALITA_MIN)))


def qualita_strumenti(team, reparto: str) -> float:
    """E quanto valgono gli strumenti con cui lo valida, da 0 a 1."""
    from . import development
    mix = {"aero": {"aero": 1.0, "mech": 0.0, "pu": 0.0},
           "progetto": {"aero": 0.0, "mech": 1.0, "pu": 0.0},
           "powertrain": {"aero": 0.0, "mech": 0.0, "pu": 1.0}}.get(
        reparto, {"aero": 0.5, "mech": 0.5, "pu": 0.0})
    return max(0.0, min(1.0, (development._tool_score(team, mix) - QUALITA_MIN)
                        / (QUALITA_MAX - QUALITA_MIN)))


def qualita_soldi(costo: float, speso: float) -> float:
    """Quanto si e' messo sul tavolo rispetto a quello che il lavoro chiedeva."""
    if costo <= 0:
        return 1.0
    return max(0.0, min(1.0, (speso / costo - 0.6) / 0.8))


def fiducia(team, area: str, taglia: str) -> float:
    """Quanto il reparto se la sente, prima di cominciare.

    Le tre cose pesano insieme, e la taglia toglie: rifare un concetto da
    zero e' un'altra cosa rispetto a ritoccare quello che c'e'.
    """
    reparto = REPARTO_AREA.get(area, "aero")
    base = (PESO_UOMINI * qualita_reparto(team, reparto)
            + PESO_STRUMENTI * qualita_strumenti(team, reparto)
            + PESO_SOLDI * 1.0) / (PESO_UOMINI + PESO_STRUMENTI + PESO_SOLDI)
    pena = {"ritocco": 0.0, "revisione": 0.10, "concetto": 0.24}[taglia]
    # d'inverno c'e' il tempo di provarci due volte: si sbaglia meno che in
    # stagione, ed e' il vero vantaggio di farlo adesso invece che a maggio
    return max(0.05, min(0.95, 0.30 + 0.70 * base - pena + 0.06))


def odds(conf: float, taglia: str) -> dict:
    """Con che probabilita' quel cantiere finisce in ognuna delle quattro bande."""
    pena = {"ritocco": 0.0, "revisione": 0.05, "concetto": 0.12}[taglia]
    fallito = max(0.02, 0.30 - 0.26 * conf + pena)
    oltre = max(0.03, 0.34 * conf - pena * 0.5)
    sotto = max(0.05, 0.34 - 0.16 * conf)
    linea = max(0.05, 1.0 - fallito - oltre - sotto)
    tot = fallito + sotto + linea + oltre
    return {"fallito": fallito / tot, "sottotono": sotto / tot,
            "in linea": linea / tot, "oltre": oltre / tot}


# ------------------------------------------------------------- i cantieri
def proposta(gs, team, p: Problema, taglia: str) -> Cantiere:
    """Il cantiere che il reparto propone per quel problema, di quella taglia."""
    t = TAGLIE[taglia]
    reparto = REPARTO_AREA.get(p.area, "aero")
    # quanto si puo' recuperare: piu' si e' indietro, piu' c'e' da prendere -
    # e' la stessa logica dei rendimenti calanti, letta al contrario
    margine = 0.45 + 0.85 * p.gravita
    atteso = t["resa"] * margine * (0.55 + 0.75 * qualita_reparto(team, reparto))
    return Cantiere(area=p.area, label=p.label, taglia=taglia,
                    settimane=t["settimane"], costo=t["costo"],
                    atteso=round(atteso, 2), fiducia=round(fiducia(team, p.area, taglia), 3),
                    reparto=reparto)


def capacita(team) -> int:
    """Settimane-reparto disponibili in un inverno."""
    return SETTIMANE * SQUADRE_PARALLELE


def impegnate(cantieri: list) -> int:
    return sum(c.settimane for c in cantieri)


def costo_totale(cantieri: list) -> float:
    return round(sum(c.costo for c in cantieri), 2)


def ci_sta(team, cantieri: list, nuovo: Cantiere) -> bool:
    """Se un altro cantiere ci sta, in settimane."""
    return impegnate(cantieri) + nuovo.settimane <= capacita(team)


# La rifinitura d'inverno: quello che il reparto tira fuori anche senza aprire
# un cantiere. Non e' un lavoro mirato, e' che per quattro mesi non c'e' una
# gara: nessuna trasferta, nessun pezzo da avere pronto per domenica, nessuno
# che stacca gente dal progetto per risolvere il problema del weekend. Le
# stesse persone, senza quel rumore attorno, rendono di piu' - ed e' il motivo
# per cui una macchina di gennaio non e' la macchina di novembre con qualche
# pezzo nuovo: e' un'altra macchina.
# Il livello va tarato contro l'invecchiamento, non in assoluto: il mondo va
# avanti di mezzo punto a componente ogni stagione, e se l'inverno ne desse
# uno e mezzo a tutti la griglia intera scapperebbe via dal riferimento del
# ciclo - misurato, +3.1 punti in quattro stagioni - e i rendimenti calanti
# finirebbero per schiacciare tutti. Quindi un reparto medio con l'inverno sta
# in pari, uno forte guadagna, uno debole arretra lo stesso. Quello che fa la
# differenza vera sono i cantieri, che si scelgono.
RIFINITURA = 0.55          # punti su ogni componente, per un reparto medio
RIFINITURA_FORBICE = 1.30  # e quanto la sposta la qualita' del reparto


def rifinitura(gs, team) -> float:
    """Punti che ogni componente guadagna per il solo fatto che e' inverno.

    Vale per tutti, ma non uguale: con le stesse sedici settimane un reparto
    forte assembla, prova e rimette mano; uno debole arriva a gennaio con
    meta' delle cose ancora sul tavolo.
    """
    q = (qualita_reparto(team, "aero") + qualita_reparto(team, "progetto")) / 2.0
    return RIFINITURA * (1.0 - RIFINITURA_FORBICE / 2.0 + RIFINITURA_FORBICE * q)


# ------------------------------------------------------- chi sceglie da solo
def ai_pianifica(gs, team, soldi: float | None = None) -> list:
    """I cantieri che apre una squadra del computer, e il criterio e' quello vero.

    Si parte dai problemi piu' grossi e si prende la taglia piu' ambiziosa che
    ci sta dentro tre vincoli: le settimane dell'inverno, i soldi, e quanto ci
    si crede. Una squadra con la galleria che non correla non apre un concetto
    nuovo - non perche' non voglia, ma perche' sa che non saprebbe dire se
    funziona finche' non lo vede in pista, e a quel punto e' maggio.
    """
    from . import economy
    if soldi is None:
        soldi = max(0.0, economy.room_left(gs, team) * QUOTA_INVERNO)
    aperti, spesa = [], 0.0
    for p in problemi(gs, team):
        if p.gravita < SOGLIA_PROBLEMA:
            break
        for taglia in ("concetto", "revisione", "ritocco"):
            c = proposta(gs, team, p, taglia)
            if c.costo + spesa > soldi or not ci_sta(team, aperti, c):
                continue
            # non si apre un cantiere in cui non si crede: sotto questa soglia
            # il rischio di peggiorare la macchina non vale il guadagno
            if c.fiducia < FIDUCIA_MINIMA[taglia]:
                continue
            aperti.append(c)
            spesa += c.costo
            break
    return aperti


# Quanta parte di quello che una squadra puo' spendere finisce nell'inverno.
# E' la spesa piu' concentrata dell'anno: quattro mesi in cui non si corre e
# tutto il reparto lavora sulla stessa cosa.
QUOTA_INVERNO = 0.55
SOGLIA_PROBLEMA = 0.08     # sotto questo non e' un problema, e' normale
# Sotto quanta fiducia non si apre un cantiere di quella taglia. Rifare un
# concetto senza gli strumenti per validarlo e' come scommettere l'anno.
FIDUCIA_MINIMA = {"ritocco": 0.0, "revisione": 0.35, "concetto": 0.55}


def _apri(gs, team, scelti: list) -> list:
    """Paga e chiude i cantieri scelti, e ci mette sopra la rifinitura."""
    # prima quello che l'inverno da' comunque: quattro mesi senza gare in cui
    # tutta la fabbrica sta sulla stessa macchina
    quota = rifinitura(gs, team)
    for p in team.car.parts.values():
        p.perf = max(40.0, min(99.5, p.perf + quota))
    speso = {}
    for c in scelti:
        team.add_expense(f"Inverno: {c.label}", round(c.costo, 3), in_cap=True,
                         category="sviluppo")
        speso[c.area] = c.costo
    news = esegui(gs, team, scelti, speso)
    team.cantieri_inverno = []
    return news


def stagione_finita(gs) -> list:
    """L'inverno delle scuderie del computer, e di chi ha delegato il reparto.

    Il giocatore che non ha delegato non passa di qui: il suo inverno lo
    decide lui, nella riunione di fine anno, e si chiude quando ha scelto.
    Fino ad allora resta in sospeso.
    """
    news = []
    for team in gs.teams.values():
        if team.is_player and not team.auto_dev:
            team.inverno_aperto = True
            continue
        news += _apri(gs, team, ai_pianifica(gs, team))   # anche a mani vuote
    return news


def chiudi_giocatore(gs, scelti: list) -> list:
    """Il patron ha deciso: i cantieri dell'inverno partono.

    Si controlla ancora una volta che ci stiano - settimane e cassa - perche'
    fra il momento in cui si sceglie e quello in cui si firma puo' essere
    cambiato qualcosa, e un inverno che sfora non lo si scopre a marzo.
    """
    team = gs.player
    team.inverno_aperto = False
    dentro, spesa = [], 0.0
    for c in scelti:
        if not ci_sta(team, dentro, c) or spesa + c.costo > max(0.0, team.cash):
            continue
        dentro.append(c)
        spesa += c.costo
    return _apri(gs, team, dentro)


# --------------------------------------------------------- e come e' andata
def esegui(gs, team, cantieri: list, speso: dict | None = None) -> list:
    """Fine inverno: i cantieri si chiudono e la macchina nuova va in pista.

    Ogni cantiere tira il suo dado, e il dado e' truccato da chi ci ha
    lavorato: uomini, strumenti e soldi. Quello che esce finisce sui
    componenti dell'area, e chi ha fatto un lavoro sbagliato se ne accorge
    adesso, non a maggio.
    """
    from . import engineering
    speso = speso or {}
    news = []
    for c in cantieri:
        q_soldi = qualita_soldi(c.costo, speso.get(c.area, c.costo))
        conf = c.fiducia * (0.75 + 0.25 * q_soldi)
        o = odds(conf, c.taglia)
        r = gs.rng.random()
        cum = 0.0
        banda = "in linea"
        for nome in ("fallito", "sottotono", "in linea", "oltre"):
            cum += o[nome]
            if r <= cum:
                banda = nome
                break
        lo, hi = BANDE[banda]
        c.esito = banda
        c.reso = round(c.atteso * gs.rng.uniform(lo, hi), 2)
        pezzi = engineering.AREA_PARTS.get(c.area, [])
        if pezzi:
            quota = c.reso / len(pezzi)
            for parte in pezzi:
                if parte in team.car.parts:
                    p = team.car.parts[parte]
                    p.perf = max(40.0, min(99.5, p.perf + quota))
        if team.is_player:
            news.append(_racconto(c))
    return news


def _racconto(c: Cantiere) -> str:
    """Come il reparto racconta com'e' andata."""
    if c.esito == "fallito":
        return (f"{c.label}: il lavoro non ha dato quello che prometteva "
                f"({c.reso:+.1f} invece di {c.atteso:+.1f}). Se ne riparla in stagione.")
    if c.esito == "sottotono":
        return (f"{c.label}: qualcosa si e' preso, ma meno del previsto "
                f"({c.reso:+.1f} contro {c.atteso:+.1f}).")
    if c.esito == "oltre":
        return (f"{c.label}: e' venuto meglio di come lo avevamo disegnato "
                f"({c.reso:+.1f}). Al banco non ci credevamo.")
    return f"{c.label}: {c.reso:+.1f}, in linea con quello che avevamo promesso."
