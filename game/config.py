"""Costanti globali del gioco."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SAVES = ROOT / "saves"

GAME_TITLE = "Apex Manager"
GAME_VERSION = "0.1"

SCREEN_W, SCREEN_H = 1600, 900
# sotto queste misure le schermate non stanno piu' in piedi
MIN_SCREEN_W, MIN_SCREEN_H = 1180, 680
FPS = 60

# --- Fisica della vettura (era 2026) -------------------------------------
RHO = 1.225                 # densita aria kg/m3
G = 9.81
CAR_MASS_KG = 768.0         # peso minimo regolamentare
FUEL_MASS_KG = 70.0         # carico massimo di benzina: il 2026 ne concede meno
# Il tetto di potenza del regolamento: 400 kW dal termico piu' 350 dal motore
# elettrico. Non e' una taratura, e' un limite - nessuna power unit puo'
# superarlo, per quanto sia fatta bene, perche' il flusso di energia del
# carburante e la potenza dell'MGU-K sono scritti nel regolamento tecnico. Il
# valore vero lo legge la vettura dal regolamento in vigore; questo e' il
# ripiego per quando il regolamento non lo dice.
POWER_W = 750_000.0
# Meta' di quella potenza e' elettrica, e la batteria non la puo' erogare
# ovunque: il pacco ha un budget per giro, e in fondo a un rettilineo lungo e'
# gia' finito. Da qui la spinta elettrica si spegne mano a mano - la stessa
# cosa che il regolamento 2026 scrive nero su bianco, con la potenza che cala
# oltre una certa andatura. Le due velocita' sono tarate sulle punte vere:
# senza questo il modello arrivava a quattrocento all'ora a Monza, cinquanta
# piu' del vero, e ci compensava rallentando nelle curve.
QUOTA_ELETTRICA = 0.47

# Quanto del tetto tira fuori la power unit peggiore della griglia. Fra la
# migliore e la peggiore, nel mondo vero, ballano pochi punti percentuali di
# potenza di picco - non il venti per cento che serviva a far vedere la
# differenza quando il tetto non c'era. La differenza vera fra due power unit
# si e' spostata dove sta davvero: consumi, recupero, affidabilita'.
# La forbice si legge fra questi due: sotto il primo valore una power unit e'
# la peggiore che si sia vista, sopra il secondo e' la migliore possibile, e in
# mezzo si distribuisce il quattro per cento scarso che separa davvero le due.
PU_MINIMO = 0.960
PU_BASSO = 0.70
PU_ALTO = 0.97
# Quanta ne entra in un giro, al massimo, per regolamento: e' il tetto, poi
# quanta se ne riesca davvero a riprendere lo dice quanto si frena li'.
RECUPERO_MAX_MJ = 8.5
BATTERIA_MJ = 4.0
V_TAGLIO_ERS = 290.0 / 3.6
V_FINE_ERS = 355.0 / 3.6
# Una monoposto ha due ruote motrici, e la spinta la mette a terra solo il
# carico che quelle due ruote sentono: il peso che sta dietro piu' la parte di
# carico aerodinamico che grava sul posteriore. Con la ripartizione vera - poco
# piu' della meta' dietro - da fermo si tira poco piu' di un g, che e' il
# motivo per cui una Formula 1 fa lo 0-100 in due secondi e mezzo e non in uno
# e mezzo. In frenata invece lavorano tutte e quattro, e infatti si stacca a
# cinque g.
QUOTA_MOTRICE = 0.55
# --- I due assali --------------------------------------------------------
# Una monoposto non e' un punto con dentro tutta la massa: ha un assale
# davanti e uno dietro, e ognuno dei due ha il suo peso da portare in curva e
# la sua aderenza per portarlo. Quello che ferma la macchina e' il piu' in
# difficolta' dei due, ed e' esattamente la definizione di sottosterzo e di
# sovrasterzo - due parole che nel modello non esistevano, perche' c'erano una
# aderenza sola e una massa sola, cioe' una vettura sempre perfettamente
# bilanciata su tutte le curve di tutti i circuiti.
#
# Il peso da fermo sta piu' dietro, perche' dietro c'e' la power unit. Il
# carico aerodinamico invece si ripartisce come vogliono le ali e il fondo, e
# siccome cresce con il quadrato della velocita' e' lui a decidere il
# bilanciamento nelle curve veloci mentre in quelle lente non conta niente. E'
# il motivo per cui la stessa macchina sottosterza in fondo al curvone e
# sovrasterza al tornante, e adesso lo fa anche qui dentro.
QUOTA_MASSA_ANT = 0.45
QUOTA_AERO_ANT = 0.45        # con la vettura neutra i due coincidono
BILANCIA_AERO = 0.050        # e il bilanciamento della vettura li separa
# Ma quella ripartizione e' quella da fermo, e da fermo non ci si sta mai. Nel
# momento in cui si spinge, la macchina si siede sul posteriore: il carico si
# sposta indietro di quanto vale il baricentro diviso il passo, e le due ruote
# motrici si trovano sotto piu' peso di quello che avevano un attimo prima.
# Con un baricentro a trenta centimetri da terra e un passo di tre metri e
# sessanta fa poco piu' di otto punti di ripartizione per ogni g di spinta -
# ed e' il motivo per cui una monoposto in uscita di curva ha piu' trazione di
# quanta ne dica il conto statico. Il conto si morde la coda (piu' spinge piu'
# si siede, piu' si siede piu' spinge) e si scioglie rigirandolo due volte.
TRASFERIMENTO = 0.083
QUOTA_MOTRICE_MAX = 0.86    # oltre non ci si va: davanti resta comunque del peso

# La gomma non tiene uguale in tutte le direzioni, e trattare la trazione come
# se fosse tenuta laterale era la scorciatoia piu' grossa rimasta: una slick
# di traverso e' al suo massimo, la stessa gomma che deve trasmettere coppia
# tiene meno. E' anche il motivo per cui una monoposto scatta forte ma non
# quanto direbbe il suo peso e la sua aderenza.
MU_TRAZIONE = 1.90

# --- Il cambio -----------------------------------------------------------
# Otto rapporti, come vuole il regolamento, e per regolamento sono fissi per
# la stagione. Quello che una squadra sceglie e' dove metterli: corti, e la
# macchina scatta ma arriva al limitatore prima della fine del rettilineo;
# lunghi, e in fondo al dritto ce n'e' ancora ma in uscita di curva si spinge
# di meno. E' un baratto vero, e finche' i rapporti non entravano nel modello
# di giro il cursore che li regola non decideva niente.
MARCE = 8
# Quanto arriva a terra di quello che esce dal motore: il resto se lo prendono
# gli ingranaggi, i cuscinetti e i trenta millesimi di strappo di ogni
# cambiata. Su un giro sono cambiate a decine.
RESA_TRASMISSIONE = 0.94
# E come cala la potenza del termico quando i giri scendono. Appena dopo una
# cambiata il motore non e' al regime di potenza massima, e ci torna salendo:
# piu' i rapporti sono lunghi, piu' in basso lo si butta a ogni cambiata, e
# meno potenza media si ha per accelerare.
CADUTA_COPPIA = 0.90
COPPIA_MINIMA = 0.72
# La prima e' quella che serve a partire da fermo e a uscire dai tornanti: la
# si mette dove la si mette da sempre. L'ultima invece la si sceglie, ed e' il
# cursore dei rapporti a dire dove.
V_PRIMA = 88.0 / 3.6        # m/s: dove la prima arriva al limitatore
V_ULTIMA_CORTA = 302.0 / 3.6
V_ULTIMA_LUNGA = 372.0 / 3.6

# Quanto della larghezza della pista finisce nella linea. Una monoposto non
# passa dal centro dell'asfalto: entra larga, tocca la corda, esce larga, e
# cosi' facendo percorre una curva di raggio piu' grande di quella che ha
# disegnato il progettista. Il guadagno e' geometrico e non e' uguale ovunque:
# su un tornante da trenta metri di raggio vale l'undici per cento di velocita'
# in piu', su un curvone da trecento poco piu' dell'uno. E' il pezzo di realta'
# che pesa di piu' fra quelli che mancavano: il centro pista non e' la strada
# che fa nessuno.
QUOTA_LINEA = 0.62
MU_LAT = 2.15               # coefficiente di aderenza laterale slick
MU_BRAKE = 1.60             # aderenza longitudinale in frenata
CLA_BASE = 3.10             # ClA di riferimento (downforce index 1.0)
CDA_BASE = 2.05             # CdA di riferimento, con le ali in assetto da curva

# L'ala mobile del 2026 non e' il vecchio DRS. In curva la vettura sta in
# Z-mode, con tutto il carico; sul dritto le ali si appiattiscono - X-mode - e
# con loro se ne va un quinto della resistenza. Sono due macchine diverse nello
# stesso giro, ed e' il motivo per cui una CdA sola non descriveva ne' le curve
# ne' i rettilinei: teneva il valore di compromesso e sbagliava tutti e due.
QUOTA_XMODE = 0.26
# e sotto questa curvatura - un raggio di ottocento metri - la macchina va
# dritta abbastanza da poterle appiattire
K_DRITTO = 1.0 / 800.0

# Raggi di curvatura indicativi per classe di curva (metri)
CORNER_RADIUS = {1: 22.0, 2: 45.0, 3: 90.0, 4: 170.0, 5: 340.0}

# --- Gomme ---------------------------------------------------------------
COMPOUNDS = {
    "soft":   {"label": "Soft",   "grip": 1.000, "wear": 1.55, "colour": (225, 6, 0),     "warmup": 0.8},
    "medium": {"label": "Medium", "grip": 0.985, "wear": 1.00, "colour": (255, 214, 0),   "warmup": 1.0},
    "hard":   {"label": "Hard",   "grip": 0.970, "wear": 0.70, "colour": (235, 235, 235), "warmup": 1.3},
    "inter":  {"label": "Inter",  "grip": 0.930, "wear": 1.10, "colour": (67, 176, 42),   "warmup": 1.0},
    "wet":    {"label": "Wet",    "grip": 0.870, "wear": 0.95, "colour": (0, 103, 173),    "warmup": 1.0},
}

# --- Aree di sviluppo della vettura --------------------------------------
CAR_PARTS = {
    "front_wing":  {"label": "Ala anteriore",  "aero": 0.9, "mech": 0.1, "pu": 0.0, "cost": 1.0},
    "rear_wing":   {"label": "Ala posteriore", "aero": 0.9, "mech": 0.1, "pu": 0.0, "cost": 1.0},
    "floor":       {"label": "Fondo",          "aero": 1.3, "mech": 0.1, "pu": 0.0, "cost": 1.6},
    "sidepods":    {"label": "Fiancate",       "aero": 0.7, "mech": 0.2, "pu": 0.2, "cost": 1.2},
    "suspension":  {"label": "Sospensioni",    "aero": 0.2, "mech": 1.1, "pu": 0.0, "cost": 1.1},
    "gearbox":     {"label": "Trasmissione",   "aero": 0.0, "mech": 0.7, "pu": 0.5, "cost": 1.0},
    "brakes":      {"label": "Impianto frenante", "aero": 0.1, "mech": 0.9, "pu": 0.0, "cost": 0.8},
    "chassis":     {"label": "Telaio",         "aero": 0.3, "mech": 1.2, "pu": 0.0, "cost": 1.8},
    "active_aero": {"label": "Aero attiva",    "aero": 1.0, "mech": 0.3, "pu": 0.2, "cost": 1.4},
    "cooling":     {"label": "Raffreddamento", "aero": 0.4, "mech": 0.2, "pu": 0.7, "cost": 0.9},
}

# --- Infrastrutture ------------------------------------------------------
FACILITIES = {
    "windtunnel":    {"label": "Galleria del vento", "cost": 4.2, "boost": "aero"},
    "cfd":           {"label": "Cluster CFD",        "cost": 3.0, "boost": "aero"},
    "simulator":     {"label": "Simulatore",         "cost": 3.4, "boost": "setup"},
    "factory":       {"label": "Fabbrica",           "cost": 5.0, "boost": "production"},
    "aero_dept":     {"label": "Reparto aerodinamica", "cost": 3.6, "boost": "aero"},
    "design_office": {"label": "Ufficio tecnico",    "cost": 3.2, "boost": "mech"},
    "pit_crew":      {"label": "Squadra ai box",     "cost": 1.8, "boost": "pitstop"},
    "academy":       {"label": "Academy",            "cost": 2.2, "boost": "youth"},
    "logistics":     {"label": "Logistica",          "cost": 2.0, "boost": "cost"},
    # Una pista di proprieta': chi ce l'ha prova quando vuole invece di
    # aspettare le prove libere. Costruirla da zero e' un investimento a parte.
    "private_track": {"label": "Pista di proprieta'", "cost": 5.5, "boost": "testing",
                      "build_cost": 140.0},
}

POINTS_DEFAULT = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

WEATHER_TYPES = ["sereno", "nuvoloso", "coperto", "pioggia leggera", "pioggia intensa"]
