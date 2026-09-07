"""La Formula E: il secondo campionato della casa, e cosa ci si gioca.

Non e' un gradino della scala verso la Formula 1 - quella scala porta da
un'altra parte - ed e' l'errore da non fare quando la si mette in un gioco
come questo. La Formula E e' un programma che la scuderia apre accanto alla
Formula 1: due macchine sue, un campionato suo, un bilancio suo.

E soprattutto: non toglie niente alla Formula 1. Non e' che gli ingegneri
dell'aerodinamica smettano di disegnare l'ala per andare a fare il software
della batteria - sono altre persone, in un altro reparto, con un altro tetto
di spesa. Se vuoi andare piu' forte qui, assumi qui: piu' gente ci metti piu'
performance porti, e piu' ti costa. E' l'unica manopola, ed e' quella vera.

Il conto lo si sente. Il regolamento finanziario della serie mette un tetto da
quindici milioni di euro a stagione, stipendi dei piloti compresi - un decimo
di quello della Formula 1 - e chi costruisce il propulsore ne ha un altro da
venticinque su due stagioni. Sono pochi per chi corre in Formula 1, ma non
sono zero, e vanno trovati ogni anno: per questo non lo fanno tutti.

Dall'altra parte ci sono gli sponsor, ed e' li' che il programma si ripaga o
non si ripaga. Un marchio noto porta a casa contratti che una squadra sconosciuta
non vede nemmeno, e vincere ne porta altri: e' lo stesso meccanismo della
Formula 1, con la differenza che qui i numeri sono un decimo e quindi una
stagione storta si sente subito.

I regolamenti stanno in `data/formulae.json`, completi e modificabili, come
quelli di Formula 1 stanno in `regulations.json`.
"""
from __future__ import annotations

from . import economy

_REG: dict = {}


def regolamento() -> dict:
    """Il regolamento in vigore, dai dati."""
    global _REG
    if not _REG:
        from .state import _load
        _REG = _load("formulae.json")
    return _REG


def corrente() -> dict:
    return regolamento().get("corrente", {})


def tecnico() -> dict:
    return corrente().get("tecnico", {})


def soldi() -> dict:
    return corrente().get("soldi", {})


# ------------------------------------------------------------------ i soldi
# Aprire il programma: due monoposto - una GEN4 costa attorno al milione - la
# sede, i contratti, la cauzione di iscrizione. Non e' il costo grosso: quello
# e' tenerlo aperto ogni anno, ed e' li' che i programmi muoiono.
INGRESSO = 9.0
# Il conto fisso di una stagione: trasferte in tredici citta', ricambi,
# meccanici, la struttura. Ci sta dentro anche il propulsore comprato.
GESTIONE_BASE = 6.4
# Quanto costa un ingegnere del programma per una stagione. E' la manopola:
# se ne assumi di piu' vai piu' forte e spendi di piu', e il tetto della serie
# dice fin dove ti puoi spingere.
COSTO_INGEGNERE = 0.088
INGEGNERI_MIN = 12
INGEGNERI_MAX = 90
# Chi si costruisce il propulsore invece di comprarlo: costa molto di piu' e
# rende molto di piu', ed e' il motivo per cui in Formula E i costruttori
# vincono e i clienti no
COSTRUTTORE_COSTO = 5.8
# E i costruttori l'ingresso lo pagano meno: la casa madre ci mette la sua
# parte, perche' un programma elettrico e' quello che vuole vedere
SCONTO_COSTRUTTORE = 0.70


def cambio() -> float:
    """Da euro a milioni di dollari, che e' la moneta del resto del gioco."""
    return 1.08


def tetto(gs=None) -> float:
    """Il tetto di spesa della serie, nella moneta del gioco."""
    return round(float(soldi().get("tetto_squadra_meur", 15.0)) * cambio(), 2)


def ha(team) -> bool:
    return bool(getattr(team, "fe_nome", ""))


def costo_ingresso(team) -> float:
    """Quanto costa aprirlo, per questa squadra."""
    sconto = SCONTO_COSTRUTTORE if getattr(team, "proprieta", "") == "costruttore" else 1.0
    return round(INGRESSO * sconto, 2)


def ingegneri(team) -> int:
    return int(max(0, getattr(team, "fe_ingegneri", 0)))


def costo_stagione(gs, team) -> float:
    """Quanto costa una stagione di programma.

    Tre voci e sono quelle vere: la struttura che gira, la gente che ci lavora
    e il propulsore - comprato a listino, o fatto in casa, che e' un'altra
    cosa e un altro conto.
    """
    if not ha(team):
        return 0.0
    fisso = GESTIONE_BASE
    gente = ingegneri(team) * COSTO_INGEGNERE
    if getattr(team, "fe_costruttore", False):
        pu = COSTRUTTORE_COSTO
    else:
        pu = float(soldi().get("prezzo_powertrain_cliente_meur", 0.42)) * cambio() * 2
    return round(fisso + gente + pu, 2)


def dentro_il_tetto(gs, team) -> tuple:
    """Se la spesa programmata sta dentro al tetto della serie."""
    spesa = costo_stagione(gs, team)
    t = tetto(gs)
    if spesa <= t:
        return True, f"{spesa:.1f} di {t:.1f} M$ di tetto"
    return False, f"{spesa:.1f} M$ contro un tetto di {t:.1f}: la FIA non lo accetta"


def ingegneri_massimi(gs, team) -> int:
    """Quanti se ne possono tenere restando dentro al tetto."""
    resto = tetto(gs) - (costo_stagione(gs, team) - ingegneri(team) * COSTO_INGEGNERE)
    return max(INGEGNERI_MIN, min(INGEGNERI_MAX, int(resto / COSTO_INGEGNERE)))


# --------------------------------------------------------------- gli sponsor
# Quanto porta a casa un programma in una stagione. La base la fa il marchio -
# un nome noto firma contratti che una squadra sconosciuta non vede - e sopra
# ci sta il risultato, che e' quello che li rinnova o non li rinnova.
SPONSOR_BASE = 8.0
SPONSOR_NOME = 0.95        # quanto pesa la reputazione della scuderia
SPONSOR_RISULTATO = 0.70   # e quanto pesa come e' andata l'anno prima
MONTEPREMI = 4.2           # e quello che paga la serie, diviso per merito


def forma(team) -> float:
    """Come e' andata l'ultima stagione, da 0 (ultimi) a 1 (campioni)."""
    pos = int(getattr(team, "fe_posizione", 0) or 0)
    squadre = max(2, int(corrente().get("squadre", 11)))
    if pos <= 0:
        return 0.45                     # non si e' ancora corso: si parte in mezzo
    return max(0.0, min(1.0, 1.0 - (pos - 1) / (squadre - 1)))


def entrate(gs, team) -> float:
    """Sponsor e montepremi di una stagione di Formula E."""
    if not ha(team):
        return 0.0
    rep = float(getattr(team, "reputation", 60.0))
    nome = 1.0 + SPONSOR_NOME * (rep - 60.0) / 100.0
    risultato = 0.72 + SPONSOR_RISULTATO * forma(team)
    premi = MONTEPREMI * (0.35 + 0.95 * forma(team))
    return round(max(0.0, SPONSOR_BASE * nome * risultato + premi), 2)


def bilancio(gs, team) -> float:
    """Quanto lascia o quanto costa, in una stagione."""
    return round(entrate(gs, team) - costo_stagione(gs, team), 2)


# ------------------------------------------------------------ la performance
# Il tetto che si puo' raggiungere con la gente che si ha. Non e' lineare:
# i primi ingegneri valgono tantissimo, gli ultimi molto meno, ed e' il motivo
# per cui a un certo punto assumere ancora non serve piu'.
MURO_MIN = 45.0
MURO_MAX = 95.0
INGEGNERI_RIF = 55.0       # quanti ne ha un programma di vertice
PESO_COSTRUTTORE = 5.0     # quanto vale farsi il propulsore in casa
PESO_STRUTTURE = 0.12      # e quanto vale avere una fabbrica seria dietro
PASSO = 0.42               # quanto ci si avvicina al proprio muro in una stagione


def muro(gs, team) -> float:
    """Fin dove puo' arrivare questo programma, con questa gente."""
    n = ingegneri(team) / INGEGNERI_RIF
    # rendimento calante: raddoppiare la gente non raddoppia la macchina
    resa = n ** 0.62
    livello = MURO_MIN + (MURO_MAX - MURO_MIN) * max(0.0, min(1.25, resa)) * 0.85
    if getattr(team, "fe_costruttore", False):
        livello += PESO_COSTRUTTORE
    fab = (float(team.facilities.get("factory", 60.0))
           + float(team.facilities.get("simulator", 60.0))) / 2.0
    livello += PESO_STRUTTURE * (fab - 60.0)
    return round(max(40.0, min(96.0, livello)), 1)


def livello(team) -> float:
    return float(getattr(team, "fe_livello", 0.0) or MURO_MIN)


def sviluppa(gs, team) -> float:
    """Quanto cresce - o cala - il programma in una stagione.

    Ci si avvicina al proprio muro un pezzo per volta: una squadra che assume
    sessanta ingegneri non si ritrova la macchina buona l'anno dopo, ci mette
    due o tre stagioni. E se si taglia, si scende con la stessa lentezza.
    """
    if not ha(team):
        return 0.0
    obiettivo = muro(gs, team)
    ora = livello(team)
    passo = (obiettivo - ora) * PASSO
    team.fe_livello = round(ora + passo, 2)
    return round(passo, 2)


# ------------------------------------------------------------- si puo' aprire?
def puo_aprire(gs, team) -> tuple:
    """Se questa squadra puo' aprire il programma. Ritorna (si puo', perche')."""
    if ha(team):
        return False, f"Il programma esiste gia': {team.fe_nome}."
    ok, why = economy.can_afford(team, costo_ingresso(team), gs, check_cap=False)
    if not ok:
        return False, why
    # il conto vero non e' l'ingresso, e' tenerlo aperto: un programma che non
    # si riesce a mantenere e' peggio di nessun programma
    annuo = GESTIONE_BASE + INGEGNERI_MIN * COSTO_INGEGNERE
    if economy.war_chest(gs, team) < costo_ingresso(team) + annuo:
        return False, (f"Aprirlo costa {costo_ingresso(team):.0f} M$ e poi almeno "
                       f"{annuo:.0f} M$ l'anno per tenerlo in piedi: non ci sono.")
    return True, (f"{costo_ingresso(team):.0f} M$ di ingresso, poi almeno "
                  f"{annuo:.0f} M$ a stagione.")


def apri(gs, team, nome: str, costruttore: bool = False) -> str:
    ok, why = puo_aprire(gs, team)
    if not ok:
        return why
    # sta fuori dal tetto di spesa della Formula 1: e' un programma della casa,
    # non un costo della monoposto, esattamente come il vivaio
    team.add_expense(f"Ingresso in Formula E ({nome})", costo_ingresso(team),
                     in_cap=False, category="formulae")
    team.fe_nome = nome
    team.fe_ingegneri = max(INGEGNERI_MIN, ingegneri(team))
    team.fe_costruttore = bool(costruttore)
    team.fe_livello = MURO_MIN + 8.0
    team.fe_posizione = 0
    return f"{nome}: iscritta al mondiale di Formula E."


def chiudi(gs, team) -> str:
    """Si chiude, e non si torna indietro gratis: riaprire e' un altro ingresso."""
    if not ha(team):
        return "Non c'e' nessun programma da chiudere."
    nome, team.fe_nome = team.fe_nome, ""
    team.fe_ingegneri = 0
    team.fe_livello = 0.0
    team.fe_piloti = []
    return f"{nome}: programma di Formula E chiuso."


# ------------------------------------------------------------- il campionato
# La griglia vera: undici squadre, ventidue macchine. Sono i nomi del mondiale
# GEN4, e ognuna ha un livello suo che si muove da una stagione all'altra come
# si muove il nostro: chi investe sale, chi taglia scende.
GRIGLIA = (
    ("Porsche", 88.0, True), ("Jaguar", 87.0, True), ("Nissan", 85.0, True),
    ("Stellantis", 83.0, True), ("Lola", 79.0, True), ("Citroen", 81.0, True),
    ("Mahindra", 76.0, True), ("Opel", 78.0, True),
    ("Envision", 82.0, False), ("Andretti", 80.0, False), ("ERT", 72.0, False),
)
# Di quanto si muove il livello di una squadra avversaria da un anno all'altro:
# poco, ma abbastanza perche' in tre stagioni la griglia non sia piu' quella
DERIVA = 2.2
# Quanto pesa il pilota rispetto alla macchina. La macchina resta la cosa
# principale - e' quella che si compra con gli ingegneri - ma in Formula E il
# pilota pesa piu' che in Formula 1: le monoposto sono quasi uguali e la
# gestione dell'energia la fa lui, ed e' per questo che li' i campioni si
# ripetono. Un pilota dieci punti migliore vale quattro punti e mezzo di
# macchina, che nel mondiale sono qualche posizione.
PESO_PILOTA = 0.45
# Quanto e' lotteria una gara, dal circuito dove non si passa a quello dove si
# passa sempre. Non e' un numero a caso: e' la ragione per cui certe gare di
# Formula E finiscono nell'ordine di partenza e altre le vince il quindicesimo
RUMORE_MIN = 2.6
RUMORE_MAX = 6.4
# Quanto vale un pilota normale di Formula E: gente che viene dalla Formula 1
# o ci e' arrivata vicino, non ragazzi. E' il riferimento attorno a cui il
# pilota sposta la macchina in su o in giu'
PILOTA_RIF = 72.0
# E chi si trova a guidare se non si sceglie nessuno: un professionista preso
# sul mercato della serie, che fa il suo senza spostare niente
PILOTA_INGAGGIATO = 69.0


def stato_griglia(gs) -> dict:
    """Il livello delle squadre avversarie, che vive fra una stagione e l'altra."""
    if not hasattr(gs, "fe_griglia") or not gs.fe_griglia:
        gs.fe_griglia = {n: liv for n, liv, _ in GRIGLIA}
    return gs.fe_griglia


def deriva_griglia(gs) -> None:
    """Un anno di lavoro delle altre: qualcuna cresce, qualcuna si perde."""
    g = stato_griglia(gs)
    for nome in list(g):
        g[nome] = round(max(62.0, min(94.0, g[nome] + gs.rng.gauss(0.0, DERIVA))), 1)


def forza_macchina(gs, team, d=None) -> float:
    """Quanto vale una nostra macchina: il programma, spostato dal pilota."""
    pilota = float(getattr(d, "overall", PILOTA_INGAGGIATO)) if d is not None \
        else PILOTA_INGAGGIATO
    return livello(team) + PESO_PILOTA * (pilota - PILOTA_RIF)


def piloti(gs, team) -> list:
    """I due che corrono per noi. Se non si sceglie, ci vanno le riserve."""
    ids = list(getattr(team, "fe_piloti", []) or [])
    scelti = [gs.drivers[i] for i in ids if i in gs.drivers]
    return scelti[:2]


def campo(gs, team=None) -> list:
    """Il campo partenti: le undici squadre, due macchine ognuna."""
    from . import serie
    g = stato_griglia(gs)
    posti = []
    for nome, liv in g.items():
        for _ in range(2):
            # i piloti degli altri sono professionisti veri, non ragazzi: si
            # muovono attorno al livello normale della serie
            pilota = gs.rng.gauss(PILOTA_RIF, 5.0)
            forza = liv + PESO_PILOTA * (pilota - PILOTA_RIF)
            posti.append(serie.Posto(
                nome=f"{gs.rng.choice(serie.NOMI)} {gs.rng.choice(serie.COGNOMI)}",
                forza=forza + gs.rng.gauss(0.0, 0.6), squadra=nome))
    if team is not None and ha(team):
        # la nostra squadra prende il posto della piu' debole: la griglia ha
        # undici squadre e non dodici
        peggiore = min(g, key=lambda n: g[n])
        posti = [p for p in posti if p.squadra != peggiore]
        nostri = piloti(gs, team)
        for i in range(2):
            d = nostri[i] if i < len(nostri) else None
            # chi non sceglie non resta a piedi: il programma ingaggia un
            # professionista della serie. Fa il suo, e non cresce
            nome = d.short if d is not None else f"pilota ingaggiato {i + 1}"
            posti.append(serie.Posto(nome=nome, forza=forza_macchina(gs, team, d),
                                     squadra=team.fe_nome,
                                     driver_id=d.id if d is not None else ""))
    return posti


def calendario(gs) -> list:
    """I circuiti su cui si corre questa stagione.

    Quelli veri ci sono da sempre; quelli inventati entrano dalla stagione
    scritta nei dati. Non e' colore: un campionato che corre sempre negli
    stessi tredici posti per vent'anni non somiglia a niente, e la Formula E
    in particolare cambia meta' calendario ogni due anni.
    """
    piste = list(getattr(gs, "fe_tracks", []) or [])
    debutti = getattr(gs, "fe_debutti", {}) or {}
    return [t for t in piste if int(debutti.get(t.id, 0) or 0) <= gs.season]


def corri_stagione(gs, team=None):
    """Una stagione di Formula E, gara per gara.

    I punti sono quelli del regolamento - venticinque al primo, la pole, il
    giro veloce fra i primi dieci - e i due formati valgono uguale, come dice
    il regolamento del 2026/27. Quello che qui non c'e' ancora e' la gara vista
    da dentro: questa e' la stagione contata, non guardata.
    """
    from . import serie
    reg = corrente()
    tabella = list(reg.get("punti", {}).get("gara", [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]))
    pole = float(reg.get("punti", {}).get("pole", 3))
    veloce = float(reg.get("punti", {}).get("giro_veloce", 1))
    entro = int(reg.get("punti", {}).get("giro_veloce_entro", 10))
    posti = campo(gs, team)
    # su quali circuiti si corre, e quante volte: il calendario ha piu' gare
    # che citta' - meta' sono doppiette - quindi si gira sulle piste che ci
    # sono finche' le gare non sono finite
    piste = calendario(gs)
    gare = int(reg.get("gare", 21))
    giro_piste = [piste[i % len(piste)] for i in range(gare)] if piste else [None] * gare
    for pista in giro_piste:
        # in Formula E le macchine sono quasi uguali e le gare sono di gestione:
        # il rumore e' piu' alto che in Formula 1, ed e' per questo che li' vince
        # gente diversa quasi ogni domenica. E dipende da dove si corre: a
        # Londra, dove non si passa, la griglia arriva com'era partita; a
        # Portland, che e' un rettilineo lungo con la scia, vince chiunque
        ot = float(pista.traits.get("overtaking", 0.5)) if pista is not None else 0.5
        rumore = RUMORE_MIN + (RUMORE_MAX - RUMORE_MIN) * ot
        ordine = sorted(posti, key=lambda p: -(p.forza + gs.rng.gauss(0.0, rumore)))
        for i, p in enumerate(ordine):
            if i < len(tabella):
                p.punti += tabella[i]
            if i == 0:
                p.vittorie += 1
            if i < 3:
                p.podi += 1
        # la pole e il giro veloce non vanno sempre a chi vince
        qualifica = sorted(posti, key=lambda p: -(p.forza + gs.rng.gauss(0.0, 3.4)))
        qualifica[0].punti += pole
        veloci = [p for p in ordine[:entro]]
        if veloci:
            gs.rng.choice(veloci).punti += veloce
    classifica = sorted(posti, key=lambda p: (-p.punti, -p.vittorie, -p.podi))
    return serie.Campionato(serie="formulae", stagione=gs.season, ordine=classifica)


def classifica_squadre(camp) -> list:
    """Il mondiale costruttori: le due macchine di ognuna sommate."""
    somma: dict = {}
    for p in camp.ordine:
        r = somma.setdefault(p.squadra, {"punti": 0.0, "vittorie": 0, "podi": 0})
        r["punti"] += p.punti
        r["vittorie"] += p.vittorie
        r["podi"] += p.podi
    return sorted(((n, v) for n, v in somma.items()), key=lambda x: -x[1]["punti"])


def stagione(gs) -> list:
    """La stagione di Formula E di tutti, e cosa lascia. Ritorna le righe da mostrare."""
    righe = []
    deriva_griglia(gs)
    for team in gs.teams.values():
        if not ha(team):
            continue
        camp = corri_stagione(gs, team)
        squadre = classifica_squadre(camp)
        pos = next((i for i, (n, _) in enumerate(squadre, 1) if n == team.fe_nome), 0)
        team.fe_posizione = pos
        team.fe_punti = round(next((v["punti"] for n, v in squadre if n == team.fe_nome), 0.0), 1)
        vinte = next((v["vittorie"] for n, v in squadre if n == team.fe_nome), 0)
        if pos == 1:
            team.fe_titoli = int(getattr(team, "fe_titoli", 0)) + 1
        # il conto della stagione: quello che e' costato e quello che ha portato
        costo = costo_stagione(gs, team)
        incasso = entrate(gs, team)
        team.add_expense(f"Formula E ({team.fe_nome})", costo, in_cap=False,
                         category="formulae")
        team.add_income(f"Formula E: sponsor e montepremi ({team.fe_nome})", incasso,
                        category="formulae")
        passo = sviluppa(gs, team)
        gs.fe_ultimo = camp
        righe.append(f"{team.short} in Formula E: {pos}o su {len(squadre)}, "
                     f"{team.fe_punti:.0f} punti, {vinte} vittorie. "
                     f"Bilancio {incasso - costo:+.1f} M$, programma {passo:+.1f}")
        # e i nostri piloti si portano a casa la stagione, come da qualunque
        # altra parte si corra. Per un ragazzo del vivaio e' il vero motivo per
        # mandarcelo: si cresce, ci si fa un nome, e i punti superlicenza della
        # Formula E valgono quanto quelli della Formula 2
        from . import serie
        for d in piloti(gs, team):
            riga = serie.cresci(gs, d, camp, team)
            if riga:
                righe.append(f"  {riga}")
    return righe


# ------------------------------------------------------- il computer che decide
# Chi apre un programma e chi no. Non e' una questione di gusto: e' una
# questione di soldi e di che casa hai dietro. Un costruttore ce lo vuole
# perche' e' quello che il consiglio vuole vedere; un fondo ci va se rende;
# una squadra che fatica a riempire il budget della monoposto non ci pensa.
VOGLIA = {"costruttore": 0.55, "marchio": 0.30, "fondo": 0.18, "padrone": 0.10}
CHIUDE_SOTTO = -6.0        # sotto questo bilancio, per due anni, si chiude
INGEGNERI_PASSO = 6        # di quanti alla volta il computer muove l'organico


def ai_programmi(gs) -> list:
    """Le squadre del computer aprono, chiudono e dimensionano il programma."""
    righe = []
    for team in gs.teams.values():
        if team.id == gs.player_team:
            continue
        if ha(team):
            righe += _ai_gestisci(gs, team)
            continue
        voglia = VOGLIA.get(getattr(team, "proprieta", "fondo"), 0.15)
        if gs.rng.random() > voglia * 0.55:
            continue
        ok, _ = puo_aprire(gs, team)
        if not ok:
            continue
        costruttore = (getattr(team, "proprieta", "") == "costruttore"
                       and economy.war_chest(gs, team) > 40.0)
        nome = f"{team.short} Formula E"
        apri(gs, team, nome, costruttore)
        team.fe_ingegneri = INGEGNERI_MIN + INGEGNERI_PASSO
        righe.append(f"{team.name} entra nel mondiale di Formula E.")
    return righe


def _ai_gestisci(gs, team) -> list:
    """Quanto ci mette dentro, e quando stacca la spina."""
    righe = []
    conto = bilancio(gs, team)
    respiro = economy.war_chest(gs, team)
    n = ingegneri(team)
    massimo = ingegneri_massimi(gs, team)
    if conto < CHIUDE_SOTTO and respiro < 10.0:
        righe.append(chiudi(gs, team) + " Non si reggeva piu'.")
        return righe
    # chi ha respiro cresce fino al tetto della serie, chi non ce l'ha taglia
    if respiro > 18.0 and n < massimo:
        team.fe_ingegneri = min(massimo, n + INGEGNERI_PASSO)
    elif conto < -3.0 and n > INGEGNERI_MIN:
        team.fe_ingegneri = max(INGEGNERI_MIN, n - INGEGNERI_PASSO)
    return righe
