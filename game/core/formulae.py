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
    return round(spesa_nel_tetto(gs, team) + fuori_tetto(team), 2)


def spesa_nel_tetto(gs, team) -> float:
    """Quanto di quella spesa conta contro il tetto della serie.

    Il regolamento finanziario della Formula E mette sotto tetto la squadra -
    struttura, gente, propulsore comprato a listino e gli ingaggi dei piloti,
    che qui ci stanno dentro. Non ci mette lo sviluppo del propulsore di chi se
    lo costruisce: quello ha un tetto suo, venticinque milioni su due stagioni,
    ed e' un budget della casa e non della squadra.
    """
    if not ha(team):
        return 0.0
    listino = float(soldi().get("prezzo_powertrain_cliente_meur", 0.42)) * cambio() * 2
    return round(GESTIONE_BASE + ingegneri(team) * COSTO_INGEGNERE + listino
                 + monte_ingaggi(gs, team), 2)


def fuori_tetto(team) -> float:
    """Lo sviluppo del propulsore di chi se lo costruisce: budget della casa."""
    if not ha(team) or not getattr(team, "fe_costruttore", False):
        return 0.0
    listino = float(soldi().get("prezzo_powertrain_cliente_meur", 0.42)) * cambio() * 2
    return round(max(0.0, COSTRUTTORE_COSTO - listino), 2)


def dentro_il_tetto(gs, team) -> tuple:
    """Se la spesa programmata sta dentro al tetto della serie."""
    spesa = spesa_nel_tetto(gs, team)
    t = tetto(gs)
    if spesa <= t:
        return True, f"{spesa:.1f} di {t:.1f} M$ di tetto"
    # e quanto bisognerebbe tagliare per starci: dirlo e' meta' del lavoro
    quanti = int((spesa - t) / COSTO_INGEGNERE) + 1
    return False, (f"{spesa:.1f} M$ contro un tetto di {t:.1f}: la FIA non lo "
                   f"accetta. Servirebbe togliere {quanti} ingegneri.")


def ingegneri_massimi(gs, team) -> int:
    """Quanti se ne possono tenere restando dentro al tetto."""
    resto = tetto(gs) - (spesa_nel_tetto(gs, team)
                        - ingegneri(team) * COSTO_INGEGNERE)
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


# ------------------------------------- cosa la Formula E lascia alla Formula 1
# E' il motivo per cui una casa ci va davvero, e fino a ieri nel gioco non
# c'era: il programma costava, rendeva, aveva il suo campionato, e alla
# monoposto non dava niente.
#
# In Formula 1 la parte elettrica si sviluppa dentro al tetto di spesa e dentro
# alle restrizioni di prova: ore di banco contate, niente collaudi veri, e un
# gran premio che dura un'ora e mezza. In Formula E la stessa roba si sviluppa
# in pista, ventuno volte l'anno, con un budget che non tocca quello della
# monoposto e con una gara che non e' altro che gestione dell'energia. E' il
# solo posto dove quel sapere si compra invece di aspettarlo.
#
# Tre cose, e non vanno tutte alla stessa gente:
#
#   software   la centralina, cioe' come si passano la palla il termico e
#              l'elettrico e quanto di quello che hai in cassa riesci davvero
#              a mettere a terra. E' l'asse piu' difficile della power unit e
#              quello che oggi separa i motoristi. Lo prende solo chi il motore
#              se lo costruisce: in una che compri non ci metti le mani.
#   recupero   quanta energia si riprende frenando. Hardware, quindi si muove
#              meno del software, e anche questo solo per chi costruisce.
#   gestione   come la squadra la spende in gara: quando ricaricare, quando
#              scaricare, dove chiedere l'override. Questo lo impara chiunque,
#              anche chi il motore lo compra, perche' non e' la power unit -
#              e' il muretto e gli ingegneri di pista.
RESA_SOFTWARE = 0.85
RESA_RECUPERO = 0.45
RESA_GESTIONE = 0.90
# Quanto di quel sapere resta l'anno dopo se il programma si chiude. Non si
# dimentica quello che si e' imparato, ma il vantaggio si consuma: gli altri
# arrivano, e quello che oggi e' un'idea fra due anni e' il minimo sindacale.
GESTIONE_DECADE = 0.80
GESTIONE_MAX = 8.0
# Di quanto la Formula E puo' spingere la power unit oltre al tetto che la
# fabbrica e le persone permettono. Poco, ma sopra a quel tetto: e' esattamente
# il punto: il banco arriva dove arriva, e li' si ferma; in Formula E si corre,
# e correndo si scopre roba che al banco non si scopre. Se non fosse cosi' il
# programma non lo aprirebbe nessuno - basterebbe comprare un banco piu' grosso.
OLTRE_IL_BANCO = 2.5


def resa(gs, team) -> dict:
    """Quanto sapere elettrico porta a casa il programma in una stagione.

    Dipende da tre cose e sono quelle vere: quanto e' grosso il programma -
    una macchina che va forte e' una macchina che ha imparato qualcosa -
    quanto e' andato bene, e se il motore te lo costruisci o lo compri.
    """
    if not ha(team):
        return {}
    # quanto vale il programma, da 0 a 1 sopra la soglia in cui si impara
    forza = max(0.0, min(1.3, (livello(team) - 58.0) / 32.0))
    esito = 0.55 + 0.75 * forma(team)
    peso = forza * esito
    fuori = {"gestione": round(RESA_GESTIONE * peso, 3)}
    if getattr(team, "fe_costruttore", False) and team.works:
        # e chi il motore se lo fa in casa se lo porta dentro: sono le stesse
        # persone, e in Formula E quel software gira in gara tutte le domeniche
        fuori["software"] = round(RESA_SOFTWARE * peso, 3)
        fuori["recupero"] = round(RESA_RECUPERO * peso, 3)
    return fuori


def applica_resa(gs, team) -> str:
    """Porta il sapere della Formula E dentro alla monoposto."""
    r = resa(gs, team)
    if not r:
        return ""
    fatte = []
    if r.get("gestione"):
        vecchio = float(getattr(team, "fe_gestione", 0.0))
        team.fe_gestione = round(min(GESTIONE_MAX, vecchio + r["gestione"]), 3)
        fatte.append(f"gestione dell'energia in gara +{r['gestione']:.2f}")
    m = gs.engine_makers.get(team.engine) if team.works else None
    if m is not None and (r.get("software") or r.get("recupero")):
        from . import powertrain
        # il tetto e' quello del banco piu' un po': la Formula E fa scavalcare
        # quel muro, ma di poco, se no diventerebbe una scorciatoia
        soglia = min(powertrain.PU_MAX,
                     powertrain.ceiling(gs, team) + OLTRE_IL_BANCO)
        mossi = {}
        for asse in ("software", "recupero"):
            if not r.get(asse):
                continue
            prima = float(m.get(asse, 85.0))
            dopo = min(soglia, prima + r[asse]) if prima < soglia else prima
            if dopo > prima:
                m[asse] = dopo
                mossi[asse] = dopo - prima
        if mossi:
            powertrain.prepara(m)      # `ers` torna a essere la media dei due
            gs.sync_engines()
            fatte.append(f"centralina +{mossi.get('software', 0):.2f}, "
                         f"recupero +{mossi.get('recupero', 0):.2f}")
        else:
            fatte.append("sulla power unit non c'e' piu' niente da imparare qui")
    return ", ".join(fatte)


def decadi_gestione(gs) -> None:
    """Il vantaggio in gestione si consuma: gli altri arrivano.

    Chi tiene aperto il programma lo rinnova ogni anno; chi lo chiude se lo
    vede sciogliere in tre o quattro stagioni. Non si dimentica quello che si
    e' imparato - si smette di essere gli unici a saperlo.
    """
    for team in gs.teams.values():
        v = float(getattr(team, "fe_gestione", 0.0))
        if v > 0.01:
            team.fe_gestione = round(v * GESTIONE_DECADE, 3)
        else:
            team.fe_gestione = 0.0


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


# E il verso opposto, che e' l'altra meta' della stessa cosa: una squadra che
# in Formula 1 ha una centralina buona non riparte da zero in Formula E. Sono
# le stesse persone, lo stesso software, la stessa fabbrica - ed e' per questo
# che i costruttori che ci vanno ci vanno forte dal primo anno.
PESO_CENTRALINA = 0.22


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
    # quello che si sa gia' di elettrico in Formula 1 vale anche qui
    eng = (getattr(team.car, "engine", None) or {}) if team.car else {}
    ers = float(eng.get("ers", 85.0))
    livello += PESO_CENTRALINA * (ers - 85.0)
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


# ------------------------------------------------------------ le rose
# Le squadre di questo campionato non sono comparse: hanno due piloti veri,
# con un nome, un'eta', un contratto e uno stipendio, esattamente come le
# scuderie di Formula 1. Prima erano nomi inventati a inizio stagione e
# buttati via a dicembre, e il campionato non era di nessuno.
def rose(gs) -> dict:
    """Chi corre per ogni squadra della serie: {nome squadra: [id, id]}."""
    if not hasattr(gs, "fe_rose") or gs.fe_rose is None:
        gs.fe_rose = {}
    return gs.fe_rose


def rosa(gs, squadra: str) -> list:
    """I piloti di quella squadra, come schede."""
    ids = rose(gs).get(squadra) or []
    return [gs.drivers[i] for i in ids if i in gs.drivers]


def squadra_di(gs, d) -> str:
    """La squadra di Formula E che ce l'ha sotto contratto, se ce n'e' una."""
    return getattr(d, "fe_squadra", "") or ""


def togli_da_rosa(gs, d) -> str:
    """Lo toglie dalla sua squadra della serie. Ritorna da dove l'ha tolto."""
    nome = squadra_di(gs, d)
    if not nome:
        return ""
    ids = rose(gs).get(nome) or []
    rose(gs)[nome] = [x for x in ids if x != d.id]
    d.fe_squadra = ""
    return nome


def assesta_rose(gs) -> None:
    """Riempie i sedili vuoti della serie, dal migliore al peggiore.

    L'ordine conta: la squadra piu' forte sceglie per prima, come succede
    dappertutto. E' il motivo per cui in fondo alla griglia ci si ritrova con
    chi e' avanzato, e per cui un pilota che cresce cambia squadra.
    """
    g = stato_griglia(gs)
    nostre = {t.fe_nome for t in gs.teams.values() if ha(t)}
    tavolo = rose(gs)
    # le squadre che quest'anno non corrono - il loro posto lo ha preso un
    # nostro programma - restano com'erano: non si sciolgono, aspettano
    for squadra in sorted(g, key=lambda k: -g[k]):
        if squadra in nostre:
            continue
        tavolo.setdefault(squadra, [])
        tavolo[squadra] = [i for i in tavolo[squadra] if i in gs.drivers]
        while len(tavolo[squadra]) < 2:
            scelta = liberi(gs)
            if not scelta:
                scelta = crea_professionisti(gs, PILOTI_LIBERI)
            d = scelta[0]
            d.fe_squadra = squadra
            d.team = None
            d.seat = "formulae"
            d.contract_until = gs.season + gs.rng.randint(1, 3)
            d.salary = ingaggio_di(d.overall, d.age)
            tavolo[squadra].append(d.id)


def scadenze_rose(gs) -> None:
    """I contratti della serie che scadono: chi non e' rinnovato torna libero."""
    for squadra, ids in list(rose(gs).items()):
        resta = []
        for did in ids:
            d = gs.drivers.get(did)
            if d is None:
                continue
            if d.contract_until > gs.season:
                resta.append(did)
                continue
            # rinnovare conviene quasi sempre: cambiare pilota costa, e in
            # Formula E il pilota che conosce la macchina vale doppio
            if gs.rng.random() < 0.62:
                d.contract_until = gs.season + gs.rng.randint(1, 3)
                d.salary = ingaggio_di(d.overall, d.age)
                resta.append(did)
            else:
                d.fe_squadra = ""
        rose(gs)[squadra] = resta


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


# ------------------------------------------------------------ il campionato
# Una stagione di Formula E non e' piu' un conto fatto tutto insieme a
# dicembre: e' un calendario. Le gare che il giocatore corre valgono quelle,
# quelle che non corre le simula il computer, e la classifica e' una sola. E'
# la stessa cosa che fa la Formula 1, ed e' l'unico modo perche' vincere un
# E-Prix serva a qualcosa.
def nuovo_campionato(gs, team=None) -> dict:
    """Apre la stagione: il campo partenti, il calendario, la classifica a zero.

    Il campo si scrive una volta e resta: sono le stesse ventidue macchine per
    tutta la stagione, con gli stessi nomi. Prima si inventavano a ogni gara, e
    il campionato non era il campionato di nessuno.

    Ed e' un campionato solo, non uno per squadra: chiunque abbia un programma -
    noi o una scuderia del computer - corre in questa griglia e prende il posto
    di una delle squadre storiche, perche' le macchine sono ventidue e non di
    piu'.
    """
    g = dict(stato_griglia(gs))
    nostre = [t for t in gs.teams.values() if ha(t)]
    # ogni programma prende il posto di una squadra della serie, partendo dalla
    # piu' debole: la griglia resta di undici squadre
    for _ in nostre:
        if not g:
            break
        del g[min(g, key=lambda k: g[k])]
    assesta_rose(gs)
    campo = []
    n = 0
    for squadra, liv in g.items():
        loro = rosa(gs, squadra)
        for i in range(2):
            d = loro[i] if i < len(loro) else None
            pilota = d.overall if d is not None else PILOTA_RIF
            campo.append({
                "id": f"fe{n}",
                "nome": d.name if d is not None else "pilota da ingaggiare",
                "squadra": squadra, "driver_id": d.id if d is not None else "",
                "forza": round(liv + PESO_PILOTA * (pilota - PILOTA_RIF)
                               + gs.rng.gauss(0.0, 0.6), 2)})
            n += 1
    for t in nostre:
        loro = piloti(gs, t)
        for i in range(2):
            d = loro[i] if i < len(loro) else None
            campo.append({
                "id": f"{t.id}{i}",
                "nome": d.name if d is not None else f"pilota ingaggiato {i + 1}",
                "squadra": t.fe_nome, "team_id": t.id,
                "driver_id": d.id if d is not None else "",
                "forza": round(forza_macchina(gs, t, d), 2)})
    piste = calendario(gs)
    gare = int(corrente().get("gare", 21))
    ids = [piste[i % len(piste)].id for i in range(gare)] if piste else []
    # meta' del calendario sono gare corte, come nel vero: si alternano
    formati = ["unleashed" if i % 3 == 2 else "eprix" for i in range(len(ids))]
    return {"stagione": gs.season, "round": 0, "calendario": ids, "formati": formati,
            "campo": campo, "punti": {c["id"]: 0.0 for c in campo},
            "vittorie": {c["id"]: 0 for c in campo},
            "podi": {c["id"]: 0 for c in campo}, "storia": []}


def stato(gs, team=None) -> dict:
    """Lo stato del campionato in corso, aperto se non c'e' o se e' vecchio."""
    st = getattr(gs, "fe_stato", None)
    # il campionato e' uno solo, e va riaperto anche se nel frattempo qualcuno
    # ha aperto o chiuso un programma: la griglia ha ventidue macchine e chi
    # entra prende il posto di qualcuno
    quanti = sum(1 for t in gs.teams.values() if ha(t))
    if (not st or st.get("stagione") != gs.season
            or st.get("programmi") != quanti):
        st = nuovo_campionato(gs)
        st["programmi"] = quanti
        gs.fe_stato = st
    return st


def prossima(gs, team=None) -> tuple:
    """La prossima gara in calendario: (circuito, formato), o (None, "")."""
    st = stato(gs, team)
    i = int(st.get("round", 0))
    cal = st.get("calendario") or []
    if i >= len(cal):
        return None, ""
    piste = {t.id: t for t in getattr(gs, "fe_tracks", []) or []}
    return piste.get(cal[i]), (st.get("formati") or ["eprix"])[i]


def campo_di(gs, team=None) -> list:
    """Le ventidue macchine di questa stagione, come sono scritte a registro."""
    return list(stato(gs, team).get("campo") or [])


def registra(gs, ordine: list, pole: str = "", veloce: str = "",
             team=None) -> None:
    """Segna il risultato di una gara e chiude il round.

    `ordine` sono gli identificativi del campo, dal primo all'ultimo. Vale
    uguale che la gara sia stata corsa dal giocatore o simulata: la classifica
    non sa e non deve sapere la differenza.
    """
    st = stato(gs, team)
    reg = corrente().get("punti", {}) or {}
    tabella = list(reg.get("gara", [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]))
    for i, chiave in enumerate(ordine):
        if chiave not in st["punti"]:
            continue
        if i < len(tabella):
            st["punti"][chiave] += tabella[i]
        if i == 0:
            st["vittorie"][chiave] += 1
        if i < 3:
            st["podi"][chiave] += 1
    if pole and pole in st["punti"]:
        st["punti"][pole] += float(reg.get("pole", 3))
    entro = int(reg.get("giro_veloce_entro", 10))
    if veloce and veloce in st["punti"] and veloce in ordine[:entro]:
        st["punti"][veloce] += float(reg.get("giro_veloce", 1))
    cal = st.get("calendario") or []
    i = int(st.get("round", 0))
    st["storia"].append({"round": i + 1, "track": cal[i] if i < len(cal) else "",
                         "ordine": list(ordine)})
    st["round"] = i + 1


def simula_gara(gs, team=None) -> list:
    """Una gara che il giocatore non corre: la fa il computer, e conta uguale.

    Il rumore lo decide il circuito, come sempre: a Londra la griglia arriva
    com'era partita, a Portland vince chiunque.
    """
    st = stato(gs, team)
    pista, _formato = prossima(gs, team)
    ot = float(pista.traits.get("overtaking", 0.5)) if pista is not None else 0.5
    rumore = RUMORE_MIN + (RUMORE_MAX - RUMORE_MIN) * ot
    campo = st["campo"]
    ordine = sorted(campo, key=lambda c: -(c["forza"] + gs.rng.gauss(0.0, rumore)))
    quali = sorted(campo, key=lambda c: -(c["forza"] + gs.rng.gauss(0.0, 3.4)))
    entro = int((corrente().get("punti") or {}).get("giro_veloce_entro", 10))
    veloce = gs.rng.choice(ordine[:entro])["id"] if ordine else ""
    chiavi = [c["id"] for c in ordine]
    registra(gs, chiavi, pole=quali[0]["id"] if quali else "", veloce=veloce, team=team)
    return chiavi


def classifica(gs, team=None) -> list:
    """La classifica piloti: (riga del campo, punti, vittorie, podi)."""
    st = stato(gs, team)
    righe = [(c, st["punti"].get(c["id"], 0.0), st["vittorie"].get(c["id"], 0),
              st["podi"].get(c["id"], 0)) for c in st["campo"]]
    righe.sort(key=lambda x: (-x[1], -x[2], -x[3]))
    return righe


def classifica_squadre(gs, team=None) -> list:
    """Il mondiale costruttori: le due macchine di ognuna sommate."""
    somma = {}
    for c, punti, vitt, podi in classifica(gs, team):
        r = somma.setdefault(c["squadra"], {"punti": 0.0, "vittorie": 0, "podi": 0})
        r["punti"] += punti
        r["vittorie"] += vitt
        r["podi"] += podi
    return sorted(somma.items(), key=lambda x: -x[1]["punti"])


def stagione(gs) -> list:
    """Chiude il mondiale di Formula E e ne apre uno nuovo.

    Le gare che il giocatore ha corso sono gia' a registro; quelle che restano
    le simula il computer adesso. Poi si fanno i conti - quanto e' costato,
    quanto ha portato, quanto e' cresciuto il programma - e i piloti si portano
    a casa la stagione come da qualunque altra parte si corra.
    """
    from . import serie
    righe = []
    deriva_griglia(gs)
    for team in gs.teams.values():
        if not ha(team):
            continue
        st = stato(gs, team)
        # le gare che mancano: chi non e' andato a correrle le vede lo stesso
        rimaste = len(st.get("calendario") or []) - int(st.get("round", 0))
        for _ in range(max(0, rimaste)):
            simula_gara(gs, team)
        corse = sum(1 for x in st.get("storia", []) if x.get("corsa"))
        squadre = classifica_squadre(gs, team)
        pos = next((i for i, (n, _) in enumerate(squadre, 1) if n == team.fe_nome), 0)
        team.fe_posizione = pos
        team.fe_punti = round(next((v["punti"] for n, v in squadre
                                    if n == team.fe_nome), 0.0), 1)
        vinte = next((v["vittorie"] for n, v in squadre if n == team.fe_nome), 0)
        costo = costo_stagione(gs, team)
        incasso = entrate(gs, team)
        team.add_expense(f"Formula E ({team.fe_nome})", costo, in_cap=False,
                         category="formulae")
        team.add_income(f"Formula E: sponsor e montepremi ({team.fe_nome})", incasso,
                        category="formulae")
        passo = sviluppa(gs, team)
        imparato = applica_resa(gs, team)
        dove = f", {corse} corse dal muretto" if corse else ""
        righe.append(f"{team.short} in Formula E: {pos}o su {len(squadre)}, "
                     f"{team.fe_punti:.0f} punti, {vinte} vittorie{dove}. "
                     f"Bilancio {incasso - costo:+.1f} M$, programma {passo:+.1f}")
        # e i nostri piloti si portano a casa la stagione: per un ragazzo del
        # vivaio e' il vero motivo per mandarcelo, perche' i punti superlicenza
        # della Formula E valgono quanto quelli della Formula 2
        if imparato:
            righe.append(f"  dalla Formula E alla monoposto: {imparato}")
        camp = _campionato_serie(gs, team)
        for d in piloti(gs, team):
            riga = serie.cresci(gs, d, camp, team)
            if riga:
                righe.append(f"  {riga}")
            # e una stagione elettrica insegna al pilota una cosa precisa:
            # la mano sull'energia. E' la stessa che in Formula 1 serve a
            # risparmiare benzina e a far durare la gomma
            d.tyre_mgmt = min(99.0, d.tyre_mgmt + gs.rng.uniform(0.3, 1.1))
            d.feedback = min(99.0, d.feedback + gs.rng.uniform(0.1, 0.6))
        team.fe_gara = 0
    # come e' finita, prima che il campionato si chiuda: serve per sapere chi
    # in Formula 1 andranno a guardare, e serve anche dopo, quando il mercato
    # della monoposto si mette a sfogliare questa classifica
    merito = _merito(gs)
    gs.fe_merito = dict(merito)
    # i contratti scaduti liberano il pilota, e il mercato si rifornisce: e'
    # un giro piccolo, dieci nomi, ma senza di quello dopo tre stagioni non
    # resterebbe piu' nessuno da ingaggiare
    nostri = {d.id for t in gs.teams.values() if ha(t) for d in piloti(gs, t)}
    for d in list(gs.drivers.values()):
        if getattr(d, "seat", "") != "formulae":
            continue
        if d.id in nostri:
            # la stagione l'hanno gia' corsa qui sopra: resta l'anno in piu'
            d.age += 1
        else:
            # gli altri la loro stagione la fanno lo stesso, solo che non la
            # guardiamo: crescono, calano e compiono gli anni come chiunque
            d.progress(0.55, gs.rng)
        if d.age > ETA_FE[1]:
            for t in gs.teams.values():
                if d.id in (getattr(t, "fe_piloti", None) or []):
                    t.fe_piloti = [x if x != d.id else "" for x in t.fe_piloti]
            togli_da_rosa(gs, d)
            d.team = None
            if d.id.startswith("fe_"):
                # gente nata per questo campionato: quando smette, sparisce
                gs.drivers.pop(d.id, None)
            else:
                # ma chi ci era arrivato dalla Formula 1 la sua scheda ce l'ha
                # da prima, e i risultati vecchi la cercano ancora: torna
                # svincolato, con l'eta' che ha
                d.seat = "titolare"
                if d not in gs.free_agents:
                    gs.free_agents.append(d)
            continue
        if d.team and d.contract_until <= gs.season:
            d.team = None
            for t in gs.teams.values():
                if d.id in (getattr(t, "fe_piloti", None) or []):
                    t.fe_piloti = [x if x != d.id else "" for x in t.fe_piloti]
        d.salary = ingaggio_di(d.overall, d.age)
    # i contratti della serie scadono come tutti gli altri: chi non e'
    # rinnovato torna sul mercato, e i sedili rimasti vuoti si riempiono
    scadenze_rose(gs)
    righe += _passaggi(gs, merito)
    # prima le squadre della serie riempiono i loro sedili, poi si rifornisce
    # il mercato: se no chi cerca un pilota a gennaio non trova piu' nessuno
    assesta_rose(gs)
    mercato(gs)
    # e il vantaggio in gestione si consuma per tutti, anche per chi il
    # programma non ce l'ha piu': e' il vantaggio che si scioglie, non il sapere
    decadi_gestione(gs)
    # la stagione e' chiusa: il prossimo campionato si apre da zero
    gs.fe_stato = None
    return righe


def _campionato_serie(gs, team):
    """La classifica finale nel formato che il vivaio sa leggere."""
    from . import serie
    ordine = []
    for c, punti, vitt, podi in classifica(gs, team):
        ordine.append(serie.Posto(nome=c["nome"], forza=c["forza"],
                                  squadra=c["squadra"], driver_id=c["driver_id"],
                                  punti=punti, vittorie=vitt, podi=podi))
    lic = list((serie.scheda("formulae") or {}).get("superlicenza") or [])
    for i, p in enumerate(ordine):
        if i < len(lic):
            p.superlicenza = lic[i]
    return serie.Campionato(serie="formulae", stagione=gs.season, ordine=ordine)


# ----------------------------------------------------------- i piloti del giro
# Chi guida in Formula E non e' un ragazzo: e' gente che dalla Formula 1 ci e'
# passata, o ci e' arrivata vicino, e che li' ha trovato il suo posto. Sono
# professionisti veri, hanno un ingaggio, e quell'ingaggio sta dentro al tetto
# di spesa della serie insieme a tutto il resto - stipendi compresi, dice il
# regolamento finanziario. Ed e' proprio quello a renderlo una scelta: un
# campione da due milioni sono ventitre ingegneri che non assumi.
PILOTI_LIBERI = 10         # quanti ne gira il mercato ogni stagione
ETA_FE = (21, 38)
INGAGGIO_MIN = 0.35
INGAGGIO_MAX = 2.60


def ingaggio_di(forza: float, eta: int) -> float:
    """Quanto chiede un pilota di Formula E, in milioni.

    La forbice e' quella vera della serie: si va da chi corre per farsi vedere
    a chi ha vinto un mondiale e se lo fa pagare. Non e' la Formula 1, dove il
    primo prende quaranta volte l'ultimo.
    """
    q = max(0.0, min(1.0, (forza - 62.0) / 22.0))
    prezzo = INGAGGIO_MIN + (INGAGGIO_MAX - INGAGGIO_MIN) * q ** 1.7
    # chi e' a fine carriera costa meno di quanto varrebbe, e lo sa
    if eta >= 36:
        prezzo *= 0.82
    return round(prezzo, 2)


def crea_professionisti(gs, quanti: int = PILOTI_LIBERI) -> list:
    """Mette sul mercato i piloti che corrono in Formula E.

    Non sono nel vivaio di nessuno e non arrivano dalla scala: sono gente che
    quel mestiere lo fa gia'. Chi li prende ha una macchina competitiva subito,
    e paga; chi ci mette un ragazzo paga in risultati ma cresce qualcuno.
    """
    from ..model.people import Driver
    from .state import _load
    pool = _load("staff.json")["name_pool"]
    fuori = []
    for _ in range(quanti):
        first = gs.rng.choice(pool["first"])
        last = gs.rng.choice(pool["last"])
        base = gs.rng.gauss(PILOTA_RIF, 4.6)
        # il grosso del mercato e' gente giovane: i veterani ci sono, ma sono
        # pochi, se no dopo qualche stagione il campionato e' una casa di riposo
        eta = int(gs.rng.triangular(ETA_FE[0], ETA_FE[1], 26))
        d = Driver(
            id=f"fe_{last.lower()}{gs.rng.randrange(100, 999)}", first=first, last=last,
            nat=gs.rng.choice(["IT", "GB", "FR", "DE", "ES", "BR", "JP", "US", "NL",
                               "CH", "PT", "NZ"]),
            age=eta, number=gs.rng.randint(2, 99), team=None,
            pace=base + gs.rng.uniform(-2, 3), racecraft=base + gs.rng.uniform(-1, 5),
            consistency=base + gs.rng.uniform(-3, 4),
            # in Formula E la gestione e' meta' del mestiere, e questi la sanno
            tyre_mgmt=base + gs.rng.uniform(1, 7),
            wet=base + gs.rng.uniform(-3, 4), feedback=base + gs.rng.uniform(-2, 5),
            aggression=gs.rng.uniform(58, 88), stamina=gs.rng.uniform(78, 94),
            estro=gs.rng.uniform(50, 92),
            # e uno o due, fra tutti, sono davvero forti: sono quelli che dopo
            # tre stagioni la Formula 1 va a guardare
            potential=min(94.0, base + max(0.0, (32 - eta) * 0.9)
                          + gs.rng.uniform(0.0, 4.5)),
            marketability=gs.rng.uniform(30, 70), salary=0.0,
            contract_until=gs.season)
        d.salary = ingaggio_di(d.overall, eta)
        d.seat = "formulae"
        gs.drivers[d.id] = d
        fuori.append(d)
    return fuori


def liberi(gs) -> list:
    """I piloti di Formula E senza contratto, dal piu' forte.

    Senza contratto vuol dire senza: ne' con un nostro programma, ne' con una
    delle squadre della serie, che adesso i piloti se li tengono anche loro.
    """
    quali = [d for d in gs.drivers.values()
             if getattr(d, "seat", "") == "formulae" and not d.team
             and not getattr(d, "fe_squadra", "")]
    quali.sort(key=lambda d: -d.overall)
    return quali


def mercato(gs) -> list:
    """Il mercato della serie, tenuto sempre pieno.

    Non e' un dettaglio: se ci si limita a riempirlo quando si svuota, dopo
    dieci stagioni sono sempre gli stessi dieci nomi con dieci anni in piu' e
    il campionato diventa una casa di riposo. Ogni anno qualcuno smette e
    qualcun altro arriva, come in qualunque serie vera.
    """
    manca = PILOTI_LIBERI - len(liberi(gs))
    if manca > 0:
        crea_professionisti(gs, manca)
    return liberi(gs)


def monte_ingaggi(gs, team) -> float:
    """Quanto pesano, sul tetto della serie, i piloti che abbiamo messo li'."""
    return round(sum(d.salary for d in piloti(gs, team)), 2)


def ingaggia(gs, team, d, posto: int) -> str:
    """Mette un pilota su una delle due macchine, se il tetto lo permette."""
    if not ha(team):
        return "Non c'e' nessun programma di Formula E."
    ids = list(getattr(team, "fe_piloti", []) or [])
    while len(ids) < 2:
        ids.append("")
    prima = ids[posto]
    ids[posto] = d.id
    team.fe_piloti = ids
    dentro, perche = dentro_il_tetto(gs, team)
    if not dentro:
        ids[posto] = prima            # non ci sta: si torna indietro
        team.fe_piloti = ids
        return f"Con {d.short} si sfonda il tetto della serie: {perche}"
    if getattr(d, "seat", "") == "formulae":
        d.team = team.id
        d.contract_until = gs.season + gs.rng.randint(1, 3)
    return f"{d.name} guidera' per {team.fe_nome}: {d.salary:.2f} M$ a stagione."


def libera(gs, team, posto: int) -> str:
    """Toglie il pilota da quel sedile: ci va un professionista qualunque."""
    ids = list(getattr(team, "fe_piloti", []) or [])
    while len(ids) < 2:
        ids.append("")
    vecchio = gs.drivers.get(ids[posto] or "")
    ids[posto] = ""
    team.fe_piloti = ids
    if vecchio is not None and getattr(vecchio, "seat", "") == "formulae":
        vecchio.team = None
    return "Sedile libero: ci va un professionista ingaggiato dalla serie."


# ------------------------------------------- fra la Formula E e la Formula 1
# La Formula E non e' un binario morto e non e' nemmeno un'anticamera: e' un
# campionato, e come tutti i campionati scambia gente con quelli vicini. Chi
# ci vince viene guardato dai direttori sportivi, e chi in Formula 1 il sedile
# lo ha perso preferisce correre li' che stare a casa a guardare.
SOGLIA_SALTO = 84.0       # sotto questa valutazione in Formula 1 non ti guardano
ETA_SALTO = 32            # e passata questa eta' non ti guardano lo stesso
SALTO_MAX = 1             # quanti ne passano al massimo, per parte, in un anno
SCESI_MAX = 2             # verso la Formula E se ne muovono un po' di piu'
VOGLIA_DI_SCENDERE = 0.30


def merito(gs) -> dict:
    """Come e' finito l'ultimo mondiale elettrico: 1 il primo, 0 l'ultimo.

    Lo legge il mercato della Formula 1, che si apre quando il campionato e'
    gia' chiuso: senza questa fotografia un direttore sportivo guarderebbe
    una classifica azzerata e non saprebbe chi ha vinto.
    """
    return dict(getattr(gs, "fe_merito", None) or {})


def _merito(gs) -> dict:
    """Come e' finito il campionato, per ognuno dei nostri: 1 il primo, 0 l'ultimo."""
    fuori = {}
    righe = classifica(gs)
    for i, (c, _punti, _vitt, _podi) in enumerate(righe):
        did = c.get("driver_id") or ""
        if did:
            fuori[did] = round(1.0 - i / max(1.0, len(righe) - 1.0), 3)
    return fuori


def _passaggi(gs, merito: dict) -> list:
    """Chi sale in Formula 1 e chi ci scende. Il mercato non e' a compartimenti.

    Sale chi ha vinto ed e' ancora in eta': una stagione da primo in Formula E
    e' un biglietto da visita che in Formula 1 leggono, e chi passa ci arriva
    da svincolato, sul mercato come tutti gli altri. Scende chi in Formula 1
    un sedile non ce l'ha piu': meglio correre altrove che non correre.
    """
    righe = []
    saliti = 0
    # Qui passa solo chi in Formula E un contratto non ce l'ha piu': e' lui a
    # scegliere di provarci, e si presenta al mercato della monoposto da
    # svincolato. Chi un contratto ce l'ha non se ne va da solo: se lo vengono
    # a prendere, e chi lo prende paga l'indennizzo alla sua squadra come si
    # paga a chiunque. Quello succede piu' avanti, a mercato aperto.
    candidati = [d for d in gs.drivers.values()
                 if getattr(d, "seat", "") == "formulae" and d.age <= ETA_SALTO
                 and not d.team and not squadra_di(gs, d)]
    candidati.sort(key=lambda d: -(d.overall + 6.0 * merito.get(d.id, 0.0)))
    for d in candidati:
        if saliti >= SALTO_MAX:
            break
        q = merito.get(d.id, 0.0)
        if d.overall < SOGLIA_SALTO - 6.0:
            continue
        # la porta si spalanca per chi ha vinto e resta socchiusa per gli altri
        quanto = (0.16 + 0.85 * q ** 2
                  + 0.40 * max(0.0, (d.overall - SOGLIA_SALTO) / 8.0))
        if gs.rng.random() > min(0.85, quanto):
            continue
        for t in gs.teams.values():
            if d.id in (getattr(t, "fe_piloti", None) or []):
                t.fe_piloti = [x if x != d.id else "" for x in t.fe_piloti]
        togli_da_rosa(gs, d)
        gs.drivers.pop(d.id, None)
        d.seat = "titolare"
        d.team = None
        d.contract_until = gs.season
        d.salary = round(max(0.8, d.market_value), 1)
        gs.free_agents.append(d)
        saliti += 1
        righe.append(f"{d.name} lascia la Formula E: e' sul mercato della Formula 1.")
    return righe


def scendono(gs) -> list:
    """La strada opposta: chi in Formula 1 il sedile non ce l'ha piu'.

    Si guarda a mercato chiuso, quando si sa davvero chi e' rimasto a piedi.
    Un nome vero al posto di uno inventato vale per tutti: il campionato
    elettrico ci guadagna gente conosciuta e il pilota ci guadagna un volante.
    """
    righe = []
    scesi = sorted((d for d in gs.free_agents
                    if ETA_FE[0] <= d.age <= ETA_FE[1] and d.overall < SOGLIA_SALTO),
                   key=lambda d: -d.overall)
    for d in scesi[:SCESI_MAX]:
        if gs.rng.random() > VOGLIA_DI_SCENDERE:
            continue
        gs.free_agents.remove(d)
        d.seat = "formulae"
        d.team = None
        d.contract_until = gs.season
        d.salary = ingaggio_di(d.overall, d.age)
        gs.drivers[d.id] = d
        righe.append(f"{d.name} va a correre in Formula E.")
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
    # i sedili: un professionista della serie vale piu' di un ingaggiato
    # qualunque, e chi ha spazio sotto il tetto se lo prende
    righe += _ai_piloti(gs, team)
    n = ingegneri(team)
    massimo = ingegneri_massimi(gs, team)
    # chi ha respiro cresce fino al tetto della serie, chi non ce l'ha taglia
    if respiro > 18.0 and n < massimo:
        team.fe_ingegneri = min(massimo, n + INGEGNERI_PASSO)
    elif (conto < -3.0 or n > massimo) and n > INGEGNERI_MIN:
        team.fe_ingegneri = max(INGEGNERI_MIN, min(massimo,
                                                   n - INGEGNERI_PASSO))
    return righe


def _ai_piloti(gs, team) -> list:
    """Il computer riempie i sedili vuoti, se il tetto glielo permette.

    Prima si guarda in casa - una riserva o un ragazzo del vivaio non costa
    niente al tetto della serie - e poi si va sul mercato, dove pero' ogni
    milione speso su un pilota e' un milione tolto agli ingegneri.
    """
    righe = []
    ids = list(getattr(team, "fe_piloti", []) or [])
    while len(ids) < 2:
        ids.append("")
    team.fe_piloti = ids
    for i in range(2):
        if ids[i] and ids[i] in gs.drivers:
            continue
        spazio = tetto(gs) - spesa_nel_tetto(gs, team)
        adatti = [d for d in liberi(gs) if d.salary <= spazio - 0.4]
        if not adatti:
            continue
        # chi ha un muretto bravo prende il migliore che si puo' permettere,
        # chi non ce l'ha prende quello che gli capita
        bravura = min(1.0, max(0.0, (team.strategy_strength - 55.0) / 40.0))
        k = 0 if gs.rng.random() < 0.35 + 0.5 * bravura else gs.rng.randrange(
            min(3, len(adatti)))
        d = adatti[k]
        detto = ingaggia(gs, team, d, i)
        if d.team == team.id:
            righe.append(f"{team.short}: {d.name} in Formula E "
                         f"({d.salary:.2f} M$).")
    return righe
