"""Simulazione del fine settimana di gara.

La gara e' continua: ogni vettura avanza in metri e i sorpassi si risolvono
quando due monoposto sono realmente a contatto, cosi' l'animazione 2D e il
risultato provengono dalla stessa simulazione.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .. import config as C

from ..core.penalties import INFRAZIONI as PENALTY_RULES
from . import energia as EN
from . import freni as FR
from . import benzina as BZ
from . import gomme as GO

PENALTY_LABELS = {k: v["label"] for k, v in PENALTY_RULES.items()}

# Quanto pesano, sul giro, le cose che cambiano da un giro all'altro. Sono i
# livelli: tarati su quello che si vede nel mondo vero, e uguali per tutti. La
# forma - quanto quello stesso chilo o quello stesso decimo di aderenza costa
# *qui* - la da' il circuito, con i moltiplicatori che il modello di giro si e'
# misurato quando la pista si e' tarata. Un chilo di benzina a Losail costa
# quasi il doppio che a Monza, e adesso la gara lo sa.
DRIVER_S_PER_POINT = 0.046     # un punto di valutazione pilota
FUEL_S_PER_KG = 0.032          # un chilo di benzina nel serbatoio
MESCOLA_S = 28.0               # tutta la forbice di aderenza fra le mescole
GOMMA_S = 22.0                 # e quella fra una gomma nuova e una finita
# Come si consuma quella gomma dentro alla sua vita. L'esponente poco sopra a
# uno da' la curva vera: il degrado non aspetta la fine dello stint, comincia
# subito e cresce piano. A meta' vita di una media sono gia' otto decimi al
# giro, ed e' quello che rende sensato provare l'undercut.
PERDITA_GOMMA = 0.11           # quanto vale, in quota di GOMMA_S, l'intera vita
ESPONENTE_GOMMA = 1.25         # quasi lineare: la parabola regalava mezzo stint
CADUTA_GOMMA = 0.55            # e dopo la vita nominale la gomma non cala: cade

# Undercut e overcut. La sosta non e' un appuntamento preso il venerdi': e'
# una mossa, e la si fa quando la gomma nuova rende piu' di quello che si sta
# perdendo in pista. Il conto e' quello vero del muretto: la gomma fresca vale
# `guadagno` secondi al giro, il giro di rientro con la gomma fredda ne
# restituisce un pezzo, e quello che resta si accumula per tutti i giri in cui
# l'altro resta fuori. Se quel totale copre il distacco, ai box si prende una
# posizione che in pista non si prenderebbe mai.
ANTICIPO_MAX = 7          # di quanti giri il muretto si permette di anticipare
RITARDO_MAX = 5           # e di quanti di ritardare, quando conviene l'overcut
FINESTRA_UNDERCUT = 2.4   # entro quanti secondi chi sta davanti e' a tiro
GUADAGNO_UNDERCUT = 0.40  # s/giro di gomma fresca sotto cui non vale la pena
QUOTA_OVERCUT = 0.86      # fin dove si allunga lo stint senza cadere nel gradino
GIRI_UNDERCUT = 2.5       # su quanti giri si conta il vantaggio della gomma nuova
PREZZO_RIENTRO = 0.85     # il giro di uscita con la gomma fredda si paga
GIRI_BLOCCO_BOX = 2       # da quanti giri si e' dietro allo stesso, per provarci
COPERTURA_S = 2.0         # entro quanti secondi la sosta di chi insegue e' una minaccia
ARIA_SPORCA_S = 0.42           # stare attaccati a chi sta davanti
# E sotto l'acqua stare attaccati e' un'altra cosa ancora: dalla macchina
# davanti esce un muro di spruzzi e non si vede la staccata. Si perde di piu' e
# si prova a passare di meno, ed e' il motivo per cui certe gare bagnate sono
# file indiane che non si sbloccano.
SPRUZZI = 1.60
# Con l'acqua alta non e' piu' questione di aderenza: sotto le gomme c'e'
# l'acqua e non l'asfalto. Da li' in su si va piano e basta, per tutti, e chi
# ci sa fare ci guadagna solo un po'.
SOGLIA_ACQUAPLANO = 0.62
ACQUAPLANO_S = 9.0
# quanto gli spruzzi tolgono alla voglia di provarci. Cresce col quadrato:
# sotto la pioggerella non cambia niente, sotto l'acqua vera non si vede il
# cartello dei cento metri e nessuno si infila
SPRUZZI_SORPASSO = 0.75
# Quanto ci mette a entrare un chilo di benzina, quando il rifornimento e'
# permesso: le pompe dell'ultima era ne mandavano giu' poco piu' di otto al
# secondo, e una sosta con un pieno vero diventava una sosta lunga.
SECONDI_PER_KG = 0.12
BURN_KG_PER_LAP = 1.18    # settanta chili per una gara: il consumo del 2026

# Modalita' di guida (0.9 conserva, 1.0 normale, 1.1 attacca). Attaccare deve
# valere poco piu' di un secondo sul giro e costare caro in gomme e benzina:
# e' una scelta, non un pulsante che regala tempo.
PUSH_S_PER_LAP = 7.5      # 0.1 di push_mode = 0.75 s sul giro
PUSH_WEAR_EXP = 2.5       # attaccare consuma circa il 27% di gomma in piu'
PUSH_FUEL_EXP = 2.5       # e altrettanta benzina
DRY_TANK_PENALTY = 8.0    # secondi al giro quando il serbatoio e' vuoto

# Quanto spesso si rompe qualcosa. E' la probabilita' per giro di una vettura
# perfettamente sana moltiplicata per quanto le manca all'affidabilita' piena:
# tarata perche' in una stagione i guasti siano circa uno a gara su ventidue
# macchine, come succede davvero. Le monoposto moderne si rompono poco: quello
# che ferma le gare sono i contatti.
RISCHIO_ROTTURA = 0.0088

# A che distanza si riesce a stare dietro. Piu' vicino di cosi' non si sta:
# l'aria della macchina davanti toglie carico all'anteriore e la macchina non
# gira piu'. Dove si sorpassa facile ci si mette a mezzo secondo, dove non si
# sorpassa si resta a un secondo abbondante e si aspetta l'errore.
# Quanto si aspetta prima di riprovarci: una zona di sorpasso per volta, non
# un tentativo a giro. Su un circuito con quattro punti buoni si prova quattro
# volte, su uno che ne ha uno si prova una volta.
ATTESA_ZONA = 6.0
# Il vantaggio di passo che serve per passare: nella zona migliore che esista
# poco, in una zona scarsa molto di piu'.
SOGLIA_ZONA = 0.15
SOGLIA_SCARSA = 1.15
FORZA_SORPASSO = 0.45
# Quanto puo' arrivare a valere un tentativo, per quanto grosso sia il divario
# di passo: dove non c'e' spazio non si passa nemmeno con due secondi al giro.
TETTO_BASE = 0.022
TETTO_PISTA = 0.185
# Quanto pesa, sul tentativo, avere piu' energia in cassa dell'altro. Mezza
# batteria di vantaggio - che e' tanto, ci vogliono due giri di ricarica per
# farla - vale poco piu' di un terzo di possibilita' in piu'; e altrettanto in
# meno a chi si trova nella condizione opposta.
VANTAGGIO_CARICA = 0.70

# Quante volte al giro ci si prova davvero. Non una per ogni posto buono che il
# circuito offre: in pista si arriva a ridosso, si studia, e ci si prova nel
# punto migliore - due volte, tre su un circuito che perdona. Contarne una per
# zona faceva salire i sorpassi in proporzione al numero di rettilinei, che e'
# la ragione per cui a Baku, che di zone ne ha otto, ne uscivano sessantatre a
# gara contro i quarantacinque veri, mentre Interlagos, che ne ha tre e ne fa
# cinquanta, restava a venti.
TENTATIVI_GIRO = 2
TENTATIVI_APERTA = 3        # dove si passa facile ci si prova una volta di piu'
# e in una zona mediocre spesso non ci si prova nemmeno: si aspetta quella
# buona, che e' esattamente quello che fa un pilota
INGAGGIO_MINIMO = 0.30

# --------------------------------------------------------- il controsorpasso
# Passare costa energia: si arriva in fondo al dritto in attacco, si spende
# l'override, e quando si e' davanti la batteria e' piu' vuota di prima. Chi e'
# stato appena passato invece quell'energia ce l'ha ancora, ed e' per questo
# che in pista un sorpasso tirato via si paga al dritto successivo. Da qui il
# senso della gestione: spendere tutto per passare uno che ne ha di piu' vuol
# dire regalargli il posto due curve dopo.
COSTO_SORPASSO_MJ = 0.35
RISCOSSA_S = 55.0           # per quanto resta aperta la finestra della risposta
RISCOSSA_FORZA = 0.85       # e quanto pesa, sopra al vantaggio di carica
RISPOSTA_ATTESA = 7.0       # chi e' stato passato puo' rispondere alla zona dopo


def follow_gap(track) -> float:
    ot = float(track.traits.get("overtaking", 0.5))
    return 22.0 + 40.0 * (1.0 - ot)


# --------------------------------------------------------------------- meteo
@dataclass
class Weather:
    label: str = "sereno"
    wet: float = 0.0          # 0 asciutto .. 1 diluvio
    track_temp: float = 30.0
    air_temp: float = 22.0
    wind: float = 8.0         # km/h: quanto e' ballerina la macchina in curva
    cloud: float = 0.2        # 0 sole pieno .. 1 coperto: scalda l'asfalto o no
    rain_forecast: list = field(default_factory=list)

    @classmethod
    def generate(cls, track, rng: random.Random) -> "Weather":
        """Il tempo che fa dove e quando si corre davvero.

        Non e' un numero a caso fra dodici e trentaquattro gradi: Las Vegas si
        corre di notte a novembre e Singapore col buio in ottobre, e sono due
        mondi. Ogni circuito porta con se' la temperatura del suo mese, quanto
        piove da quelle parti e quanto tira vento; il resto - sole o nuvole,
        acquazzone o no - cambia da un fine settimana all'altro.
        """
        clima = getattr(track, "climate", None) or {}
        media = float(clima.get("temp", 22.0))
        oscilla = float(clima.get("swing", 6.0))
        pioggia = float(clima.get("rain", 0.20))
        vento_base = float(clima.get("wind", 10.0))

        wet = 0.0
        label = "sereno"
        cloud = max(0.0, min(1.0, rng.betavariate(2.0, 3.5)))
        r = rng.random()
        if r < pioggia * 0.40:
            wet, label, cloud = rng.uniform(0.55, 0.95), "pioggia intensa", 1.0
        elif r < pioggia:
            wet, label, cloud = rng.uniform(0.20, 0.55), "pioggia leggera", 0.9
        elif r < pioggia + 0.22:
            label, cloud = "nuvoloso", max(cloud, 0.55)
        elif r < pioggia + 0.32:
            label, cloud = "coperto", max(cloud, 0.80)
        else:
            cloud = min(cloud, 0.35)

        air = rng.gauss(media, oscilla * 0.45) - 4.0 * wet - 2.0 * cloud
        # l'asfalto prende il sole: di giorno arriva a venti gradi sopra
        # all'aria, di notte a pochi, e sotto la pioggia si raffredda
        sole = (0.30 if getattr(track, "night", False) else 1.0) * (1.0 - 0.75 * cloud)
        track_temp = air + 3.0 + 17.0 * sole - 6.0 * wet
        vento = max(0.0, rng.gauss(vento_base, vento_base * 0.45))
        w = cls(label=label, wet=wet, track_temp=round(track_temp, 1),
                air_temp=round(air, 1), wind=round(vento, 1), cloud=round(cloud, 2))
        w.rain_forecast = w._forecast(track, rng)
        return w

    # ------------------------------------------------------------- evoluzione
    def drift(self, track, rng: random.Random) -> "Weather":
        """Il tempo del turno dopo: somiglia a questo, ma non e' questo.

        Il venerdi' non e' il sabato e il sabato non e' la domenica. Le cose si
        muovono con calma - la temperatura di qualche grado, le nuvole a
        strappi - ma la pioggia arriva e se ne va, e chi ha preparato tutto il
        fine settimana sull'asciutto la domenica si ritrova un'altra pista.
        """
        clima = getattr(track, "climate", None) or {}
        pioggia = float(clima.get("rain", 0.20))
        cloud = max(0.0, min(1.0, 0.62 * self.cloud + 0.38 * rng.betavariate(2.0, 3.5)))
        wet = self.wet
        if wet > 0.05:
            if rng.random() < 0.45:
                wet = 0.0                                  # ha smesso
            else:
                wet = max(0.05, min(1.0, wet * rng.uniform(0.55, 1.35)))
        elif rng.random() < pioggia * 0.45:
            wet = rng.uniform(0.20, 0.90)
        if wet > 0.55:
            label, cloud = "pioggia intensa", 1.0
        elif wet > 0.05:
            label, cloud = "pioggia leggera", max(cloud, 0.9)
        elif cloud > 0.75:
            label = "coperto"
        elif cloud > 0.50:
            label = "nuvoloso"
        else:
            label = "sereno"
        media = float(clima.get("temp", 22.0))
        air = 0.70 * self.air_temp + 0.30 * rng.gauss(media, 2.5) - 3.0 * wet
        sole = (0.30 if getattr(track, "night", False) else 1.0) * (1.0 - 0.75 * cloud)
        w = Weather(label=label, wet=round(wet, 3), air_temp=round(air, 1),
                    track_temp=round(air + 3.0 + 17.0 * sole - 6.0 * wet, 1),
                    wind=round(max(0.0, 0.6 * self.wind
                                   + 0.4 * rng.gauss(float(clima.get("wind", 10.0)), 4.0)), 1),
                    cloud=round(cloud, 2))
        w.rain_forecast = w._forecast(track, rng)
        return w

    def _forecast(self, track, rng: random.Random) -> list:
        """Cosa dicono i radar per la gara: a che punto e quanta acqua.

        E' una previsione, non un fatto: dice che sta arrivando e quando, non
        quanto durera' esattamente. Basta a decidere se rischiare le gomme da
        asciutto o fermarsi subito.
        """
        clima = getattr(track, "climate", None) or {}
        p = float(clima.get("rain", 0.20))
        fuori = []
        if self.wet > 0.05:
            if rng.random() < 0.50:
                fuori.append((round(rng.uniform(0.15, 0.70), 2), 0.0))
        elif rng.random() < p * 0.75:
            quando = round(rng.uniform(0.10, 0.75), 2)
            fuori.append((quando, round(rng.uniform(0.25, 0.85), 2)))
            if rng.random() < 0.35:
                fuori.append((round(min(0.95, quando + rng.uniform(0.15, 0.40)), 2), 0.0))
        return fuori

    def forecast_label(self) -> str:
        """La previsione detta a parole, per il muretto."""
        if not self.rain_forecast:
            return ("continua a piovere per tutta la gara" if self.wet > 0.05
                    else "asciutto per tutta la gara")
        quota, forza = self.rain_forecast[0]
        quando = ("nei primi giri" if quota < 0.2 else
                  "verso il primo terzo" if quota < 0.4 else
                  "a meta' gara" if quota < 0.6 else
                  "nell'ultimo terzo")
        if forza <= 0.05:
            return f"la pioggia dovrebbe smettere {quando}"
        forte = "acquazzone" if forza > 0.55 else "pioggia leggera"
        return f"{forte} in arrivo {quando}"


def _mmss(t: float) -> str:
    """Un tempo sul giro come lo scrive il tabellone."""
    m, s = divmod(max(0.0, t), 60.0)
    return f"{int(m)}:{s:06.3f}"


# ------------------------------------------------------------------ concorrente
@dataclass
class Entrant:
    driver_id: str
    team_id: str
    code: str
    name: str
    colour: tuple
    number: int

    base_lap: float = 90.0        # giro di riferimento a secco, serbatoio vuoto
    skill: float = 80.0
    consistency: float = 80.0
    tyre_skill: float = 80.0
    aggression: float = 70.0
    estro: float = 60.0           # quanto si inventa: traiettorie, staccate, giri
    racecraft: float = 80.0
    wet_skill: float = 80.0
    stamina: float = 90.0
    confidence: float = 65.0      # quanto si fida della macchina che ha sotto
    reliability: float = 0.95
    pit_time: float = 2.6
    strategy_skill: float = 75.0

    # stato in gara
    dist: float = 0.0
    lap: int = 0
    position: int = 1
    tyre: str = "medium"
    tyre_age: float = 0.0
    gomma_t: float = 90.0         # a che temperatura e' la gomma, in gradi
    freni_t: float = 500.0        # e a che temperatura sono i dischi
    freni_usura: float = 0.0      # quanto se n'e' consumato, da 0 a 1 e oltre
    raffredda: float = 0.5        # quanto e' raffreddata questa vettura, 0..1
    tyre_life: float = 25.0
    fuel: float = 100.0
    consumo: float = 1.0          # quanta benzina beve questo motore, in quote
    total_time: float = 0.0
    last_lap: float = 0.0
    giro_scorso: float = 0.0      # l'ultimo giro chiuso davvero, da cronometro
    best_lap: float = 999.0
    # il giro spezzato in tre, come sul tabellone: quello appena fatto, il
    # migliore di ognuno e i parziali gia' presi in questo giro
    sectors: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    best_sectors: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    live_sectors: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    lap_t0: float = 0.0           # da quando si sta girando questo giro
    sector_done: int = 0          # quanti parziali sono gia' scattati
    sector_shares: list = field(default_factory=lambda: [0.3333, 0.6667])
    vmax: float = 340.0           # punta di velocita' della vettura, km/h
    status: str = "running"       # running | pitting | retired | finished
    dnf_reason: str = ""
    pit_timer: float = 0.0
    stops: int = 0
    plan: list = field(default_factory=list)     # [(giro, mescola)]
    used_compounds: set = field(default_factory=set)
    stock: dict = None            # set ancora nel camion, per mescola
    overtake_cd: float = 0.0
    dirty_air: float = 0.0
    clean_lap: float = 90.0     # passo in aria libera, usato per valutare i duelli
    damage: float = 0.0
    push_mode: float = 1.0        # 0.9 conserva .. 1.1 attacca
    passo_benzina: float = 0.0    # quanto il muretto chiede di dare o di tenere
    passo_manuale: float | None = None   # il giocatore ha preso in mano il passo
    # l'energia elettrica: quanta ce n'e' in cassa e come la si sta usando
    carica: float = 4.0           # MJ nella batteria
    energy_mode: str = "normale"  # ricarica | normale | attacco
    energy_manual: bool = False   # il giocatore ha preso in mano la gestione
    energy_delta: float = 0.0     # cosa fa al giro, in secondi
    lift_coast: bool = False      # si alza il piede prima di frenare
    clipping: bool = False        # batteria a secco: niente spinta in fondo ai dritti
    scarica: bool = False         # batteria a terra: il dritto lo fa il termico
    superclip: bool = False       # ricarica a gas spalancato: si perde sul dritto
    mappa: str = "base"           # conservativa | base | spinta
    mappa_manuale: bool = False   # la mappatura la decide il giocatore
    mappa_delta: float = 0.0      # cosa costa o regala al giro, in secondi
    motore_usura: float = 0.0     # quanto lo si e' tirato, da 0 a 1 e oltre
    override_usi: int = 0
    override_t: float = 0.0       # da quanto e' acceso, per il tabellone
    ers_skill: float = 85.0       # quanto bene questa power unit riempie la batteria
    bloccato_da: str = ""         # dietro chi si e' incastrati...
    bloccato_giri: int = 0        # ...e da quanti giri
    piano_energia: int = 0        # >0 giri messi via per l'attacco, <0 giri di attacco
    tentativi_giro: int = 0       # quante volte ci ha gia' provato in questo giro
    riscossa: float = 0.0         # secondi di finestra per rispondere a chi l'ha passato
    riscossa_su: str = ""         # e a chi
    fuel_warned: bool = False
    # cosa aveva intorno quando si e' fermato: serve al muretto degli altri
    # per capire se quella sosta era un undercut da coprire
    pit_lap: int = -99
    pit_davanti: str = ""         # chi aveva davanti al momento della sosta
    pit_dietro: str = ""          # e chi aveva dietro
    pit_gap: float = 99.0         # e a quanti secondi era da quello davanti
    ritardi_sosta: int = 0        # quante volte ha gia' allungato lo stint
    grid: int = 1
    finished_time: float = 0.0
    is_player: bool = False
    terza: bool = False           # terza vettura: corre ma non prende punti
    laps_led: int = 0
    penalty_pending: float = 0.0     # secondi assegnati e non ancora scontati
    penalty_total: float = 0.0       # secondi complessivi ricevuti
    penalties_given: list = field(default_factory=list)   # infrazioni contestate
    under_review: float = 0.0        # secondi di attesa prima della decisione
    review_kind: str = ""
    track_warnings: int = 0

    def lap_fraction(self, track_len: float) -> float:
        """A che punto del giro si e', contato sul cronometro."""
        return (self.dist % track_len) / track_len

    def compound_state(self) -> float:
        """1.0 = gomma fresca, cala fino allo 0 dopo il degrado.

        La curva e' quasi una retta, e non e' un dettaglio: con una parabola
        la prima meta' dello stint non costava niente, e siccome e' proprio
        li' che vive l'undercut, ai box non ci si fermava mai un giro prima.
        Adesso a meta' vita la gomma ha gia' restituito quasi la meta' di
        quello che ha da dare, e la sosta anticipata torna a essere una mossa.
        Oltre la vita nominale resta il gradino: la gomma non cala, cade.
        """
        x = self.tyre_age / max(1.0, self.tyre_life)
        if x <= 1.0:
            return 1.0 - PERDITA_GOMMA * x ** ESPONENTE_GOMMA
        return max(0.35, (1.0 - PERDITA_GOMMA) - CADUTA_GOMMA * (x - 1.0))


# ------------------------------------------------------------------ simulazione
class RaceSim:
    def __init__(self, gs, track, entrants: list, weather: Weather, laps: int,
                 kind: str = "gp", rng: random.Random | None = None, cond=None):
        self.gs = gs
        self.track = track
        self.entrants = entrants
        self.weather = weather
        self.laps = laps
        self.kind = kind
        self.rng = rng or random.Random()
        self.time = 0.0
        self.track_len = track.length_km * 1000.0
        self.safety_car = 0.0
        self.sc_laps = 0
        self.vsc = False
        self.events: list = []
        self.finished = False
        self.classification: list = []
        from . import pace
        self.cond = cond if cond is not None else pace.from_weather(track, weather)
        # l'asfalto che si sono trovati - freddo o caldo, verde o gommato - sta
        # gia' dentro al giro base di ognuno. Qui resta solo quel poco che la
        # pista guadagna ancora mentre si corre, che vale mezzo secondo scarso
        self.evo = 1.004
        self.follow = follow_gap(track)
        self.wind_noise = pace.wind_noise(self.cond)
        # su un asfalto che scotta la gomma dura meno: e' la ragione per cui la
        # stessa mescola fa venti giri in Bahrain e trentacinque a Montreal
        self.temp_wear = max(0.72, min(1.55, 1.0 + 0.020 * (self.cond.track_temp - 35.0)))
        # la previsione diventa un programma: a che giro l'acqua arriva e quanta
        self.meteo_prog = [(max(1, int(q * laps)), forza)
                           for q, forza in (getattr(weather, "rain_forecast", None) or [])]
        self.meteo_target = weather.wet
        # Quanto e' bagnata la *linea*, che non e' quanto sta piovendo. Le
        # monoposto passano sempre nello stesso posto e quel posto si asciuga
        # prima di tutto il resto: e' la traiettoria che si vede scurirsi giro
        # dopo giro mentre a un metro di distanza c'e' ancora l'acqua. E' li'
        # che si decide quando montare le slick, ed e' la ragione per cui chi
        # ci prova per primo o fa il capolavoro o va a muro.
        self.linea_asciutta = 0.0
        # degrado imposto dal regolamento in vigore: fisso per tutta la gara
        reg = getattr(gs, "regulations", None) or {}
        self.tyre_deg = float(reg.get("tyres", {}).get("deg_multiplier", 1.0))
        # gare accorciate: gomme e soglie di strategia si accorciano con loro,
        # altrimenti una gara al 50% si correrebbe senza mai fermarsi
        self.distance = float(getattr(gs, "race_distance", 1.0))
        # consumo tarato sul carico imbarcato: guidando normale si arriva in
        # fondo con un filo di riserva, qualunque sia la lunghezza della gara.
        # make_race lo ricalcola appena sa quanta benzina c'e' a bordo.
        self.burn_per_lap = BURN_KG_PER_LAP
        self.leader_lap = 0
        # il meglio della sessione, settore per settore: e' quello che sul
        # tabellone si colora di viola
        self.best_sectors = [0.0, 0.0, 0.0]
        self.best_lap = 0.0
        self.best_lap_by = ""
        # quello che si sente alla radio: il pilota che racconta la macchina e
        # il muretto che risponde. Ne resta in memoria l'ultimo pezzo
        self.radio: list = []
        self._radio_cd: dict = {}
        # la batteria che il regolamento concede, e quanto vale spenderla qui
        pu = (getattr(gs, "regulations", None) or {}).get("power_unit", {})
        self.batteria_max = float(pu.get("batteria_mj", C.BATTERIA_MJ))
        self.senza_coperte = gs.regulations.get("tyre_warmers") is False
        # quanto si perde a passare dai box, con il limite in corsia che il
        # regolamento impone adesso: abbassarlo a sessanta all'ora non e' mezzo
        # secondo, sono sette o otto - la corsia si percorre tutta piano
        limite = float(gs.regulations.get("pit_lane_kmh", 80.0))
        self.perdita_box = (track.perdita_box(limite)
                            + float(gs.regulations.get("pit_lane_penalty_s", 0.0)))
        self.superclip_kw = float(pu.get("superclip_kw", 250.0))
        self.rifornimento = bool(gs.regulations.get("refuelling"))
        self.serbatoio = float(pu.get("fuel_race_target_kg", C.FUEL_MASS_KG))
        # una macchina senza motore termico non ha benzina da gestire: il
        # serbatoio, il consumo e tutto quello che ci gira attorno spariscono
        self.senza_benzina = self.serbatoio <= 0.1
        # in griglia le gomme sono quelle che escono dalle coperte, e senza
        # coperte sono quelle dell'asfalto: il primo giro non e' un giro
        for e in entrants:
            e.gomma_t = GO.dai_box(self, e.tyre)
            # i dischi in griglia sono quelli scaldati nel giro di
            # ricognizione: dentro la finestra, ma appena
            e.freni_t = FR.FREDDO + 60.0
        self._pos_prima: dict = {}
        self._order_cache = list(entrants)
        # l'ordine in pista del passo precedente: serve a tenere la fila
        self._coda = list(entrants)

    # ------------------------------------------------------------ utilita'
    def log(self, text: str, kind: str = "info") -> None:
        self.events.insert(0, {"lap": self.leader_lap + 1, "text": text, "kind": kind})
        del self.events[60:]

    def radio_say(self, e, testo: str, chi: str = "pilota") -> None:
        """Una voce alla radio. Solo per chi corre per noi: gli altri hanno la loro."""
        if not e.is_player:
            return
        self.radio.insert(0, {"driver_id": e.driver_id, "code": e.code, "chi": chi,
                              "text": testo, "lap": e.lap + 1, "t": self.time})
        del self.radio[12:]

    def radio_of(self, driver_id: str) -> dict | None:
        """L'ultima cosa detta da quel box."""
        for m in self.radio:
            if m["driver_id"] == driver_id:
                return m
        return None

    def speed_of(self, e) -> float:
        """A quanto sta andando adesso, in km/h.

        La forma del giro la da' il tracciato - dove si tira e dove si frena -
        e il livello lo da' la vettura: chi ha la punta piu' alta la vede piu'
        alta anche qui, e chi sta girando con dieci secondi di ritardo la vede
        scendere tutta insieme.
        """
        if e.status == "pitting":
            return 80.0
        if e.status == "retired":
            return 0.0
        tr = self.track
        if not tr.speed_map:
            return 0.0
        v = tr.speed_at(e.lap_fraction(self.track_len), e.last_lap or e.base_lap)
        scala = e.vmax / tr.speed_peak if tr.speed_peak else 1.0
        return v * scala

    def zone_of(self, e) -> str:
        """Che cosa sta facendo in questo momento: tirare, frenare, girare."""
        if e.status == "pitting":
            return "box"
        return self.track.zone_at(e.lap_fraction(self.track_len))

    def order(self) -> list:
        live = [e for e in self.entrants if e.status != "retired"]
        live.sort(key=lambda e: -e.dist)
        done = [e for e in self.entrants if e.status == "retired"]
        done.sort(key=lambda e: -e.dist)
        return live + done

    # -------------------------------------------------------- tempo sul giro
    def lap_time_of(self, e: Entrant) -> float:
        tr = self.track
        t = e.base_lap
        t += (85.0 - e.skill) * DRIVER_S_PER_POINT * tr.pilota_rel
        t += e.fuel * FUEL_S_PER_KG * tr.benzina_rel
        comp = C.COMPOUNDS[e.tyre]
        t += (1.0 - comp["grip"]) * MESCOLA_S * tr.grip_rel
        t += (1.0 - e.compound_state()) * GOMMA_S * tr.grip_rel
        t += e.damage * 0.06
        t *= self.evo
        t -= (max(0.90, min(1.10, e.push_mode)) - 1.0) * PUSH_S_PER_LAP
        # quello che la gestione dell'energia ha deciso per questo giro: chi
        # scarica la batteria va piu' forte, chi la ricarica piu' piano, chi
        # l'ha finita paga il clipping in fondo a ogni rettilineo
        t += e.energy_delta
        t += e.mappa_delta
        # e a che temperatura e' la gomma. Il giro dopo la sosta, quello dietro
        # alla safety car e il decimo giro passato nell'aria di un altro non
        # sono giri come gli altri, e adesso il perche' e' un numero solo
        t += GO.secondi(self, e)
        t += FR.secondi(self, e)
        if e.fuel <= 0.01 and not self.senza_benzina:
            t += DRY_TANK_PENALTY
        clean = t
        # nell'acqua chi insegue non vede: gli spruzzi di chi sta davanti sono
        # un muro, e si sta piu' lontani di quanto si vorrebbe
        t += e.dirty_air * ARIA_SPORCA_S * tr.scia_rel * (1.0 + SPRUZZI * self.weather.wet)
        acqua = self.bagnato
        if self.weather.wet > 0.05 or acqua > 0.05:
            # la gomma giusta e' quella per l'acqua che c'e' sulla linea, non
            # per quella che sta cadendo: e' esattamente la scommessa che si fa
            # quando si monta la slick su una pista che si sta asciugando
            mismatch = 0.0
            if acqua > 0.45 and e.tyre != "wet":
                mismatch = 12.0 if e.tyre in ("soft", "medium", "hard") else 2.5
            elif 0.15 < acqua <= 0.45 and e.tyre not in ("inter", "wet"):
                mismatch = 7.0
            elif acqua <= 0.15 and e.tyre in ("inter", "wet"):
                mismatch = 4.0
            t += mismatch
            t += (85.0 - e.wet_skill) * 0.06 * acqua * 4.0
            # e con l'acqua alta non e' piu' una questione di aderenza: e'
            # l'acquaplano, e a quel punto si va piano e basta, per tutti
            if acqua > SOGLIA_ACQUAPLANO:
                troppa = (acqua - SOGLIA_ACQUAPLANO) / (1.0 - SOGLIA_ACQUAPLANO)
                t += ACQUAPLANO_S * troppa ** 1.7 * (0.75 + 0.5 * (
                    100.0 - e.wet_skill) / 40.0)
        if self.safety_car > 0:
            t *= 1.42 if not self.vsc else 1.30
        var = self.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.006
                             + self.wind_noise)
        e.clean_lap = clean
        return max(20.0, t + var)

    # ----------------------------------------------------------------- passo
    def update(self, dt: float) -> None:
        if self.finished:
            return
        if self.classification and all(
                x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True
            return
        self.time += dt
        # la pista continua a gommarsi mentre si corre
        self.evo = max(0.9995, self.evo - dt * 0.0000030)
        self._meteo(dt)
        self._asciuga(dt)
        if self.safety_car > 0:
            self.safety_car = max(0.0, self.safety_car - dt)
            if self.safety_car == 0.0:
                self.log("Safety car rientrata: si riparte!", "sc")
                self.vsc = False

        for e in self.entrants:
            if e.status in ("retired", "finished"):
                continue
            if e.status == "pitting":
                e.pit_timer -= dt
                e.total_time += dt
                if e.pit_timer <= 0:
                    e.status = "running"
                continue

            lt = self.lap_time_of(e)
            e.last_lap = lt
            v = self.track_len / lt
            e.dist += v * dt
            e.total_time += dt
            e.overtake_cd = max(0.0, e.overtake_cd - dt)
            e.riscossa = max(0.0, e.riscossa - dt)
            e.override_t = max(0.0, e.override_t - dt)

            GO.aggiorna(self, e, dt / lt)
            FR.aggiorna(self, e, dt / lt)
            wear_rate = self._wear_rate(e)
            e.tyre_age += wear_rate * dt / lt
            burn = (self.burn_per_lap * e.consumo
                    * (e.push_mode ** BZ.esponente(e, PUSH_FUEL_EXP))
                    * EN.BENZINA_MAPPA.get(e.mappa, 1.0))
            if e.lift_coast:
                burn *= EN.LIFT_BENZINA     # alzare il piede si sente anche qui
            e.fuel = max(0.0, e.fuel - burn * dt / lt)

            self._track_limits(e, dt)
            self._intertempi(e, lt)

            new_lap = int(e.dist // self.track_len)
            if new_lap > e.lap:
                e.lap = new_lap
                self._on_lap_complete(e, lt)

        self._queue()
        self._resolve_battles(dt)
        self._resolve_reviews(dt)
        self._update_positions()
        self._maybe_incident(dt)
        self._coda = [e for e in self.entrants if e.status == "running"]
        self._coda.sort(key=lambda e: -e.dist)

    # ------------------------------------------------------------ intertempi
    def _intertempi(self, e, lt: float) -> None:
        """I parziali, quando si passa sotto al traguardo di settore.

        La pista e' divisa in tre, come sul tabellone vero: ogni volta che una
        macchina taglia una di quelle linee il tempo si ferma e va a schermo.
        E' con questi che si vede dove si guadagna prima ancora che il giro sia
        finito.
        """
        if e.dist < 0 or e.sector_done >= 2 or e.lap < 1:
            return
        soglie = e.sector_shares
        f = e.lap_fraction(self.track_len)
        while e.sector_done < 2 and f >= soglie[e.sector_done]:
            i = e.sector_done
            # il traguardo di settore e' stato tagliato dentro al passo di
            # calcolo, non alla fine: quel pezzo di secondo va tolto, se no i
            # parziali vengono fuori tutti arrotondati al passo
            oltre = (f - soglie[i]) * lt
            parziale = (e.total_time - e.lap_t0) - oltre - sum(e.live_sectors[:i])
            e.live_sectors[i] = max(0.1, parziale)
            e.sector_done += 1
            self._segna_settore(e, i)

    def _segna_settore(self, e, i: int) -> None:
        """Aggiorna il migliore di quel settore, personale e di tutta la pista."""
        t = e.live_sectors[i]
        if t <= 0.1:
            return
        if e.best_sectors[i] <= 0 or t < e.best_sectors[i]:
            e.best_sectors[i] = t
        if self.best_sectors[i] <= 0 or t < self.best_sectors[i]:
            self.best_sectors[i] = t

    def sector_view(self, e) -> list:
        """I tre parziali da mostrare: quelli di questo giro appena scattano.

        Finche' il giro e' in corso si vedono i settori gia' passati; quelli
        che mancano restano quelli del giro prima, cosi' la riga non si svuota
        a ogni passaggio sul traguardo.
        """
        return [(e.live_sectors[i], True) if e.live_sectors[i] > 0
                else (e.sectors[i], False) for i in range(3)]

    def sector_colour(self, e, i: int, valore: float | None = None):
        """Viola il migliore di tutti, verde il migliore suo, giallo il resto."""
        t = e.sectors[i] if valore is None else valore
        if t <= 0:
            return None
        if self.best_sectors[i] > 0 and t <= self.best_sectors[i] + 1e-6:
            return "viola"
        if e.best_sectors[i] > 0 and t <= e.best_sectors[i] + 1e-6:
            return "verde"
        return "giallo"

    def _meteo(self, dt: float) -> None:
        """Il tempo cambia mentre si corre: l'acqua arriva, e poi se ne va.

        Non e' un interruttore: la pista si bagna e si asciuga in qualche giro,
        e in quei giri sta la gara - chi si ferma subito, chi resiste, chi
        sbaglia il momento.
        """
        for giro, forza in list(self.meteo_prog):
            if self.leader_lap >= giro:
                self.meteo_target = forza
                self.meteo_prog.remove((giro, forza))
                if forza > 0.05:
                    self.log("Arriva la pioggia: cominciano a cadere gocce", "warn")
                else:
                    self.log("Ha smesso di piovere: la pista si asciuga", "warn")
        w = self.weather
        if abs(w.wet - self.meteo_target) < 0.005:
            return
        passo = dt * 0.0016 * (1.0 if self.meteo_target > w.wet else 0.7)
        prima = w.wet
        w.wet = round(min(self.meteo_target, w.wet + passo) if self.meteo_target > w.wet
                      else max(self.meteo_target, w.wet - passo), 3)
        w.label = ("pioggia intensa" if w.wet > 0.55 else
                   "pioggia leggera" if w.wet > 0.05 else "pista in asciugatura"
                   if prima > 0.05 else w.label)
        # sotto l'acqua la gomma stesa se ne va, e con lei l'aderenza
        if w.wet > 0.2:
            self.evo = min(1.02, self.evo + dt * 0.0000050)

    def _asciuga(self, dt: float) -> None:
        """La linea si asciuga, o si ribagna. E' un conto a parte dalla pioggia.

        Mentre piove la traiettoria resta bagnata come tutto il resto. Appena
        smette comincia ad asciugarsi, e non ci mette lo stesso tempo dovunque:
        la asciugano le macchine che ci passano sopra e l'asfalto caldo, per
        cui a Sepang in venti minuti la pista e' un'altra e a Spa in autunno
        no. Quello che si asciuga e' solo la linea: appena si esce di li' e'
        ancora tutto bagnato, ed e' il motivo per cui in quei giri non si
        sorpassa quasi mai.
        """
        w = self.weather
        vive = sum(1 for e in self.entrants if e.status == "running")
        if w.wet > self.linea_asciutta * 0.5 + 0.02 and self.meteo_target >= w.wet - 0.01:
            # piove ancora: quello che si era asciugato torna bagnato, e in
            # fretta - bastano due giri di acqua vera
            self.linea_asciutta = max(0.0, self.linea_asciutta - dt * 0.0022 * (0.4 + w.wet))
            return
        if w.wet <= 0.005 and self.linea_asciutta >= 0.999:
            return
        caldo = 0.45 + 0.022 * max(0.0, self.cond.track_temp - 12.0)
        traffico = 0.35 + 0.05 * min(20, vive)
        self.linea_asciutta = min(1.0, self.linea_asciutta
                                  + dt * 0.00042 * caldo * traffico)

    @property
    def bagnato(self) -> float:
        """Quanta acqua c'e' sulla linea: e' questo che decide l'aderenza."""
        return max(0.0, self.weather.wet * (1.0 - 0.85 * self.linea_asciutta))

    def _queue(self) -> None:
        """Dietro si resta finche' il sorpasso non lo si fa davvero.

        Le monoposto avanzano in metri, e due macchine con lo stesso passo si
        scambierebbero di posto in continuazione solo per il rumore dei tempi
        sul giro. In pista non funziona cosi': ci si mette a ridosso e li' si
        resta, a perdere tempo nell'aria sporca, finche' non si trova il modo
        di passare. Chi sta davanti fa da tappo, e il tempo che il secondo
        perde in coda e' tempo vero.
        """
        coda = [e for e in self._coda if e.status == "running"]
        for i in range(1, len(coda)):
            davanti, dietro = coda[i - 1], coda[i]
            limite = davanti.dist - self.follow
            if dietro.dist > limite:
                dietro.dist = limite

    def _wear_rate(self, e: Entrant) -> float:
        comp = C.COMPOUNDS[e.tyre]
        base = comp["wear"] * self.tyre_deg * (0.55 + 0.9 * self.track.traits.get("tyre_wear", 0.6))
        skill = 1.30 - 0.55 * (e.tyre_skill / 100.0)
        push = e.push_mode ** PUSH_WEAR_EXP
        sc = 0.45 if self.safety_car > 0 else 1.0
        wet = 1.0 - 0.35 * self.bagnato
        return base * skill * push * sc * wet * self.temp_wear * GO.usura(e)

    def _on_lap_complete(self, e: Entrant, lt: float) -> None:
        # il giro che il cronometro ha visto davvero: dentro ci sono la coda
        # dietro a chi non si passa, la sosta ai box, la safety car. Il
        # traguardo lo si taglia dentro al passo di calcolo, quindi il pezzo di
        # secondo gia' corso nel giro nuovo si scala da questo
        oltre = (e.dist - e.lap * self.track_len) * lt / self.track_len
        giro = e.total_time - e.lap_t0 - oltre
        e.tentativi_giro = 0          # il conto dei tentativi riparte a ogni giro
        if e.sector_done >= 2 and giro > 1.0:
            e.live_sectors[2] = max(0.1, giro - e.live_sectors[0] - e.live_sectors[1])
            self._segna_settore(e, 2)
            e.sectors = list(e.live_sectors)
        e.lap_t0 = e.total_time - oltre
        e.live_sectors = [0.0, 0.0, 0.0]
        e.sector_done = 0
        if giro > 20.0:
            e.giro_scorso = giro
        record = 20.0 < giro < e.best_lap
        if record:
            e.best_lap = giro
            if self.best_lap <= 0 or giro < self.best_lap:
                # non finisce nella cronaca: col serbatoio che si svuota il
                # primato cade quasi a ogni giro, e riempirebbe la colonna.
                # Sul tabellone dei tempi si vede, e li' basta
                self.best_lap, self.best_lap_by = giro, e.code
        self._energia(e)
        self._parla(e, giro, record)
        if e.position == 1:
            e.laps_led += 1
        self.leader_lap = max(self.leader_lap, min(e.lap, self.laps))

        # rottura meccanica
        risk = (1.0 - e.reliability) * RISCHIO_ROTTURA * (1.0 + e.damage / 70.0)
        # e quanto il regolamento in vigore mette sotto sforzo la meccanica:
        # una stagione di componenti contati non e' una con i ricambi liberi
        risk *= 1.0 + float(self.gs.regulations.get("reliability_risk", 0.0) or 0.0)
        # e quanto gli si e' chiesto col motore: le power unit dell'anno sono
        # contate, e chi le tiene sempre in spinta le paga
        risk *= EN.rischio_motore(e)
        # e coi freni: un disco cotto per mezza gara non arriva in fondo
        risk *= FR.rischio(e)
        if self.rng.random() < risk:
            e.status = "retired"
            e.dnf_reason = self.rng.choice([
                "problema idraulico", "cedimento power unit", "surriscaldamento",
                "guasto al cambio", "perdita di pressione olio", "rottura sospensione"])
            self.log(f"RITIRO: {e.name} - {e.dnf_reason}", "dnf")
            # una macchina che si spegne la si parcheggia: la bandiera
            # gialla basta quasi sempre
            self._maybe_safety_car(0.12)
            return

        # errore del pilota
        err = (100.0 - e.consistency) * 0.00013 * (0.6 + 0.8 * e.push_mode)
        if self.gs.regulations.get("traction_control"):
            err *= 0.68        # con l'elettronica che tiene, gli errori calano
        err *= 1.0 + 1.7 * self.bagnato + 0.7 * self.weather.wet
        err *= 1.0 + (1.0 - e.compound_state()) * 1.2
        # chi non si fida di quello che ha sotto sbaglia di piu': non e' che
        # guidi peggio, e' che la macchina lo sorprende
        err *= max(0.60, 1.0 + (65.0 - e.confidence) * 0.008)
        if self.rng.random() < err:
            if self.rng.random() < 0.22:
                e.status = "retired"
                e.dnf_reason = "incidente"
                self.log(f"INCIDENTE: {e.name} finisce contro le barriere!", "dnf")
                self._maybe_safety_car(0.35)
            else:
                loss = self.rng.uniform(1.5, 6.0)
                e.dist -= loss * (self.track_len / lt)
                e.damage = min(100.0, e.damage + self.rng.uniform(2, 14))
                self.log(f"Errore di {e.name}: perde {loss:.1f}s", "warn")

        if e.lap >= self.laps:
            e.status = "finished"
            over = e.dist - self.laps * self.track_len
            e.finished_time = e.total_time - over / max(1.0, self.track_len / max(30.0, lt))
            if e.penalty_pending > 0:
                # non c'e' stata piu' una sosta: i secondi si aggiungono all'arrivo
                e.finished_time += e.penalty_pending
                self.log(f"{e.name}: {e.penalty_pending:.0f}s aggiunti al tempo finale", "pen")
                e.penalty_pending = 0.0
            if not self.classification:
                self.log(f"BANDIERA A SCACCHI: vince {e.name}!", "flag")
            self.classification.append(e)
            if len([x for x in self.entrants if x.status in ("finished", "retired")]) >= len(self.entrants):
                self.finished = True
            return

        self._fuel_check(e)
        self._check_pit(e)
        if all(x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True

    # ---------------------------------------------------------------- energia
    def _energia(self, e: Entrant) -> None:
        """I conti della batteria a fine giro: quanto e' entrato, quanto e' uscito."""
        avanti, dietro = self._chi_davanti(e), self._chi_dietro(e)
        metri_s = max(20.0, self.track_len / max(30.0, e.last_lap))
        ga = (avanti.dist - e.dist) / metri_s if avanti else 99.0
        gd = (e.dist - dietro.dist) / metri_s if dietro else 99.0
        EN.aggiorna_blocco(self, e, avanti, ga)
        EN.scegli_modo(self, e, avanti, dietro, ga, gd)
        e.energy_delta = EN.passo_giro(self, e)
        EN.scegli_mappa(self, e, ga, gd)
        BZ.scegli_passo(self, e, ga, gd)
        EN.logora_motore(self, e)
        e.mappa_delta = EN.passo_mappa(self, e)

    # ------------------------------------------------------------------ radio
    def _parla(self, e: Entrant, giro: float, record: bool = False) -> None:
        """Quello che il pilota racconta e quello che il muretto risponde.

        Non e' colore: ogni frase esce da un numero che sta succedendo davvero
        - la gomma che ha finito il suo, l'aria sporca di chi sta davanti, la
        benzina che non basta, l'acqua che arriva, il posto perso al giro
        prima. Quando alla radio si sente che le gomme sono andate, sul
        tabellone la barra e' gia' scesa.
        """
        if not e.is_player or e.status != "running":
            return
        prima = self._pos_prima.get(e.driver_id, e.position)
        self._pos_prima[e.driver_id] = e.position
        if e.lap < self._radio_cd.get(e.driver_id, -9):
            return
        stato = e.compound_state()
        avanti = self._chi_davanti(e)
        dietro = self._chi_dietro(e)
        metri_s = max(20.0, self.track_len / max(30.0, giro))
        gap_a = (avanti.dist - e.dist) / metri_s if avanti else 99.0
        gap_d = (e.dist - dietro.dist) / metri_s if dietro else 99.0
        resta = self.laps - e.lap
        voci = []
        if e.damage > 25:
            voci.append((9, "pilota", "Ho preso un colpo, la macchina non e' piu' dritta."))
        if self.bagnato > 0.05 and e.tyre in ("soft", "medium", "hard"):
            voci.append((10, "pilota", "Qui piove, con queste gomme non tengo la macchina."))
        elif self.bagnato < 0.06 and e.tyre in ("inter", "wet"):
            voci.append((8, "pilota", "La linea si sta asciugando, sto cuocendo le gomme."))
        # la benzina, che adesso e' un conto che si muove giro per giro
        if not self.senza_benzina and resta > 0:
            marg = BZ.margine_giri(self, e)
            if marg < -0.6:
                voci.append((9, "muretto", f"Siamo {abs(marg):.1f} giri sotto: alza il piede "
                                           f"in fondo ai dritti o non arriviamo."))
            elif marg < -0.1:
                voci.append((7, "muretto", "Un filo corti di benzina: due staccate "
                                           "anticipate a giro e rientriamo."))
            elif e.push_mode < 0.995:
                voci.append((5, "pilota", "Sto alzando il piede, ma cosi' non tengo "
                                          "il passo di quelli davanti."))
            elif marg > 1.6 and resta <= 12:
                voci.append((6, "muretto", f"Hai {marg:.1f} giri di benzina d'avanzo: "
                                           f"non serve portarla al traguardo, spendila."))
        if stato < 0.72:
            voci.append((8, "pilota", "Le gomme sono finite, sto scivolando dappertutto."))
        elif stato < 0.82:
            voci.append((5, "pilota", "Comincio a perdere il posteriore in trazione."))
        # e la gomma: adesso e' un numero che si muove, e alla radio si sente
        caldo = GO.fuori(e)
        if caldo < -1.0:
            voci.append((8, "pilota", f"Gomme fredde, non ho niente: "
                                      f"{e.gomma_t:.0f} gradi, non si accendono."))
        elif caldo > 1.4:
            voci.append((8, "pilota", f"Le sto cuocendo, {e.gomma_t:.0f} gradi: "
                                      f"scivolo dappertutto e le sto finendo."))
        elif caldo > 1.0:
            voci.append((6, "muretto", "Sei sopra la finestra di temperatura: "
                                       "molla un decimo in staccata e rientrano."))
        elif e.tyre_age < 1.5 and e.stops:
            voci.append((6, "muretto", "Gomme nuove: due curve per metterle in temperatura."))
        if FR.fuori(e) > 0.6:
            voci.append((9, "pilota", f"Freni a {e.freni_t:.0f} gradi, il pedale "
                                      f"si sta allungando."))
        elif FR.fuori(e) < -0.4:
            voci.append((6, "pilota", "Freni freddi, alla staccata non mordono."))
        if e.position < prima:
            voci.append((7, "muretto", f"Bene cosi', sei {e.position}."))
        elif e.position > prima:
            voci.append((6, "muretto", f"Ti hanno passato, adesso sei {e.position}."))
        if e.dirty_air > 0.55 and gap_a < 2.0:
            voci.append((6, "pilota", "Nella sua aria non giro, perdo l'anteriore in ingresso."))
        elif 0.1 < gap_a < 1.0 and avanti:
            voci.append((6, "muretto", f"Sei a {gap_a:.1f} da {avanti.code}: e' il momento."))
        if 0.1 < gap_d < 1.2 and dietro:
            voci.append((5, "muretto", f"{dietro.code} e' a {gap_d:.1f}, ti sta arrivando."))
        if self.safety_car > 0:
            voci.append((7, "muretto", "Safety car in pista: tieni in temperatura le gomme."))
        # l'energia: e' meta' della macchina, e si sente
        if e.scarica:
            voci.append((9, "pilota", "Non ho piu' niente, il dritto lo sto facendo a motore."))
        elif e.superclip:
            voci.append((6, "muretto", "Ricarica a gas spalancato: sul dritto sei corto, "
                                       "ma in curva no."))
        elif e.clipping:
            voci.append((8, "pilota", "Batteria a secco, in fondo al dritto non spingo piu'."))
        elif e.piano_energia > 0:
            chi = f" su {avanti.code}" if avanti else ""
            voci.append((7, "muretto", f"Lascialo andare e carica: fra due giri{chi} "
                                       f"ci arriviamo con la batteria piena."))
        elif e.piano_energia < 0:
            voci.append((7, "muretto", f"Adesso spendila tutta: {e.carica:.1f} megajoule, "
                                       f"piu' di quelli che ha lui."))
        elif e.energy_mode == "ricarica":
            voci.append((4, "muretto", f"Due giri di ricarica: siamo a {e.carica:.1f} "
                                       f"megajoule, poi te la ridiamo tutta."))
        elif e.energy_mode == "attacco" and e.carica > 0.5:
            voci.append((5, "muretto", f"Scarica pure: {e.carica:.1f} megajoule "
                                       f"da spendere adesso."))
        if e.override_usi and e.override_t > 0:
            voci.append((6, "muretto", "Override attivo: e' adesso o mai piu'."))
        # e la mappatura: quando cambia, il pilota lo sente
        if e.mappa == "conservativa" and e.lap > 2:
            # e il perche' non e' sempre lo stesso: a volte e' la benzina che
            # non basta, a volte e' che davanti e dietro non c'e' nessuno e
            # tirare il motore adesso non serve a niente
            if not self.senza_benzina and BZ.margine_giri(self, e) < 0.6:
                voci.append((5, "muretto", "Mappa conservativa: tienilo lungo, dobbiamo "
                                           "arrivare in fondo."))
            else:
                voci.append((4, "muretto", "Mappa conservativa: qui non c'e' nessuno "
                                           "da prendere, il motore lo teniamo buono."))
        elif e.mappa == "spinta" and e.lap > 2:
            voci.append((5, "muretto", "Mappa in spinta, hai tutto quello che c'e'."))
        if e.motore_usura > 0.60:
            voci.append((7, "muretto", "Il motore sta lavorando parecchio, "
                                       "occhio alle temperature."))
        if 0 < resta <= 3:
            voci.append((6, "muretto", f"{resta} giri alla fine, porta a casa la macchina."))
        if record and self.best_lap_by == e.code and e.lap > 2:
            voci.append((4, "muretto", f"Giro veloce della gara: {_mmss(giro)}."))
        if not voci:
            return
        voci.sort(key=lambda x: -x[0])
        peso, chi, testo = voci[0]
        self.radio_say(e, testo, chi)
        # piu' e' importante quello che c'e' da dire, prima si torna a parlare
        self._radio_cd[e.driver_id] = e.lap + max(2, 12 - peso)

    def _chi_dietro(self, e: Entrant):
        dietro = [x for x in self.entrants if x.status == "running" and x.dist < e.dist]
        return max(dietro, key=lambda x: x.dist) if dietro else None

    def _chi_davanti(self, e: Entrant):
        avanti = [x for x in self.entrants if x.status == "running" and x.dist > e.dist]
        return min(avanti, key=lambda x: x.dist - e.dist) if avanti else None

    def _fuel_check(self, e: Entrant) -> None:
        """Avvisa quando la benzina non basta piu' per arrivare in fondo.

        Non impone niente: attaccare puo' voler dire restare a secco, ma il
        muretto lo dice prima, non dopo.
        """
        if self.senza_benzina:
            return
        left = self.laps - e.lap
        if self.rifornimento and e.plan:
            # col rifornimento non si deve arrivare in fondo alla gara: si
            # deve arrivare alla prossima sosta, ed e' un altro mestiere
            left = max(1, e.plan[0][0] - e.lap + 1)
        if left <= 0 or e.fuel_warned or e.fuel >= left * self.burn_per_lap * e.consumo:
            return
        e.fuel_warned = True
        if e.is_player:
            self.log(f"Benzina critica per {e.name}: cosi' non arriva in fondo", "warn")

    # ------------------------------------------------------------- strategia
    def _guadagno_fresco(self, e: Entrant) -> float:
        """Quanti secondi al giro renderebbe montare adesso una gomma nuova."""
        return (1.0 - e.compound_state()) * GOMMA_S * self.track.grip_rel

    def _gap_secondi(self, a: Entrant, b: Entrant) -> float:
        """Distacco fra due vetture in secondi, con il passo di chi insegue."""
        metri_s = max(20.0, self.track_len / max(30.0, b.last_lap or b.base_lap))
        return (a.dist - b.dist) / metri_s

    def _vede_la_mossa(self, e: Entrant) -> bool:
        """Se il muretto se ne accorge. Un muretto distratto la sosta la fa quando c'era scritto."""
        return self.rng.random() < 0.30 + 0.0062 * e.strategy_skill

    def _sosta_reattiva(self, e: Entrant) -> str | None:
        """L'undercut: fermarsi un giro prima per uscire davanti a chi non si passa.

        Due casi, e sono le due facce della stessa mossa. O si e' incollati a
        uno che non si riesce a passare in pista, e allora la gomma nuova lo
        scavalca ai box; o e' stato lui a fermarsi per scavalcare noi, e allora
        ci si ferma subito dietro per coprirlo. In tutti e due i casi la sosta
        c'era gia' in programma: la si sposta, non la si inventa.
        """
        if self.safety_car > 0 or not e.plan or e.lap < 6 or e.lap > self.laps - 6:
            return None
        lap_prog, comp = e.plan[0]
        anticipo = lap_prog - e.lap
        if anticipo <= 0 or anticipo > ANTICIPO_MAX:
            return None
        if e.stock and e.stock.get(comp, 0) <= 0:
            return None
        guadagno = self._guadagno_fresco(e)
        if guadagno < GUADAGNO_UNDERCUT:
            return None
        # a) qualcuno che ci inseguiva si e' appena fermato addosso a noi: se
        #    non si copre, al rientro se lo ritrova davanti
        for r in self.entrants:
            if r is e or r.pit_davanti != e.driver_id:
                continue
            # ma solo se era davvero addosso: chi si ferma da tre secondi
            # dietro non sta facendo una mossa, sta facendo la sua sosta
            if (e.lap - r.pit_lap <= 1 and r.stops > e.stops
                    and r.pit_gap < COPERTURA_S and self._vede_la_mossa(e)):
                e.plan.pop(0)
                self.log(f"{e.name} risponde subito ai box per coprire {r.code}", "pit")
                return comp
        # b) e la mossa in attacco: davanti c'e' uno a tiro che non si passa
        avanti = self._chi_davanti(e)
        if avanti is None or avanti.status != "running" or avanti.lap < e.lap - 0.5:
            return None
        gap = self._gap_secondi(avanti, e)
        if not 0.0 < gap < FINESTRA_UNDERCUT:
            return None
        # e soprattutto: ci si ferma prima perche' in pista non si passa. Un
        # giro solo appiccicati non basta, ci si prova ancora; due giri dietro
        # allo stesso senza venirne fuori sono la ragione per cui esiste
        # l'undercut
        if e.bloccato_da != avanti.driver_id or e.bloccato_giri < GIRI_BLOCCO_BOX:
            return None
        # quanto resta fuori lui: se si ferma insieme a noi non c'e' undercut
        resta_lui = (avanti.plan[0][0] - e.lap) if avanti.plan else ANTICIPO_MAX
        if resta_lui < 1:
            return None
        giri = max(1.0, min(GIRI_UNDERCUT, float(resta_lui)))
        # e se la sua gomma e' messa peggio della nostra non c'e' niente da
        # anticipare: si aspetta che si fermi lui e si guadagna restando fuori
        if self._guadagno_fresco(avanti) >= guadagno:
            return None
        if guadagno * giri - PREZZO_RIENTRO <= gap:
            return None
        if not self._vede_la_mossa(e):
            return None
        e.plan.pop(0)
        self.log(f"{e.name} anticipa la sosta: undercut su {avanti.code}", "pit")
        return comp

    def _conviene_overcut(self, e: Entrant) -> bool:
        """Se allungare lo stint di qualche giro rende piu' che fermarsi adesso.

        Ha senso solo con la gomma ancora buona e con chi era davanti gia' ai
        box: sono i giri in cui si gira da soli sull'asfalto libero mentre lui
        scalda le sue, e sono quelli che al proprio rientro fanno la differenza.
        """
        if self.safety_car > 0 or e.ritardi_sosta >= 2 or self.bagnato > 0.12:
            return False
        if e.lap > self.laps - RITARDO_MAX - 4:
            return False
        # allungare si puo' finche' la gomma non e' sul gradino: oltre, i giri
        # in piu' costano piu' di quello che l'aria libera regala
        if e.tyre_age > e.tyre_life * QUOTA_OVERCUT or e.dirty_air > 0.25:
            return False
        for r in self.entrants:
            if r is e or r.pit_dietro != e.driver_id:
                continue
            if e.lap - r.pit_lap <= 2 and r.stops > e.stops:
                return self._vede_la_mossa(e)
        return False

    def _check_pit(self, e: Entrant) -> None:
        bagnato = self.bagnato > 0.12
        target = None
        for lap, comp in list(e.plan):
            if e.lap >= lap:
                # l'overcut: il giro della sosta e' arrivato, ma la gomma tiene
                # ancora e chi era davanti si e' gia' fermato. Si allunga
                if not bagnato and self._conviene_overcut(e):
                    # quanti giri la gomma regge ancora prima del gradino
                    resta = int((e.tyre_life - e.tyre_age) / max(0.3, self._wear_rate(e)))
                    ritardo = max(1, min(RITARDO_MAX, resta, self.rng.randint(2, RITARDO_MAX)))
                    e.plan[0] = (min(self.laps - 3, e.lap + ritardo), comp)
                    e.ritardi_sosta += 1
                    self.log(f"{e.name} allunga lo stint: overcut", "pit")
                    return
                e.plan.remove((lap, comp))
                # quando piove il piano dell'asciutto si straccia: il muretto
                # non rimanda in pista una macchina con le slick sotto l'acqua
                if not bagnato:
                    target = comp
                break
        if bagnato:
            e.plan.clear()
        # e la mossa opposta: la sosta si anticipa quando la gomma nuova
        # scavalca chi non si riesce a passare in pista
        if target is None and not bagnato:
            target = self._sosta_reattiva(e)
        # sosta d'emergenza se la gomma e' andata
        if target is None and e.tyre_age > e.tyre_life * 1.35 and e.lap < self.laps - 2:
            target = self._pick_compound(e)
        # cambio per la pioggia. Le soglie di rientro sono piu' larghe di quelle
        # di uscita: si monta la gomma da bagnato appena serve, ma non si torna
        # indietro alla prima schiarita, altrimenti si vive ai box
        if target is None:
            if self.bagnato > 0.50 and e.tyre != "wet":
                target = "wet"
            elif 0.20 < self.bagnato <= 0.42 and e.tyre not in ("inter", "wet"):
                target = "inter"
            elif self.bagnato < 0.30 and e.tyre == "wet":
                target = "inter"
            elif self.bagnato < 0.08 and e.tyre == "inter" and e.lap < self.laps - 3:
                target = self._pick_compound(e)
        if target is None or target == e.tyre:
            return
        # chi si aveva intorno entrando ai box: e' con questo che il muretto
        # degli altri capisce se quella sosta era una mossa su di loro
        vicino_a = self._chi_davanti(e)
        vicino_d = self._chi_dietro(e)
        e.pit_lap = e.lap
        e.pit_davanti = vicino_a.driver_id if vicino_a else ""
        e.pit_dietro = vicino_d.driver_id if vicino_d else ""
        e.pit_gap = self._gap_secondi(vicino_a, e) if vicino_a else 99.0
        # opportunismo: sotto safety car si guadagna tempo
        e.status = "pitting"
        stop = e.pit_time + max(0.0, self.rng.gauss(0.25, 0.35))
        if e.penalty_pending > 0:
            # i secondi si scontano fermi ai box, prima di toccare la vettura
            stop += e.penalty_pending
            self.log(f"{e.name} sconta {e.penalty_pending:.0f}s di penalita' ai box", "pen")
            e.penalty_pending = 0.0
        if self.rng.random() < 0.035:
            stop += self.rng.uniform(2.0, 9.0)
            self.log(f"Sosta lenta per {e.name}!", "warn")
        if self.rng.random() < 0.012 + (100.0 - e.consistency) * 0.0004:
            self._investigate(e, "velocita_box")
        loss = self.perdita_box * (0.62 if self.safety_car > 0 else 1.0)
        # la vettura resta ferma per tutta la durata della sosta mentre gli
        # altri avanzano: e' gia' l'intera perdita di tempo. Toglierle anche
        # la distanza equivalente la farebbe pagare due volte.
        e.pit_timer = stop + loss
        e.tyre = target
        e.used_compounds.add(target)
        if e.stock and target in e.stock:
            e.stock[target] = max(0, e.stock[target] - 1)
        e.tyre_age = 0.0
        e.tyre_life = self._tyre_life(e, target)
        e.gomma_t = GO.dai_box(self, target)
        e.stops += 1
        # e se il regolamento permette di rifornire, alla sosta si rimette
        # dentro anche la benzina per il pezzo di gara che viene: il tempo lo
        # decide quanta ne entra, ed e' per questo che con il rifornimento le
        # soste non sono piu' tutte uguali
        if self.rifornimento:
            prossima = e.plan[0][0] if e.plan else self.laps
            serve = (prossima - e.lap + 1) * self.burn_per_lap * e.consumo * 1.06
            metti = max(0.0, min(self.serbatoio, serve) - e.fuel)
            if metti > 0.1:
                e.fuel += metti
                e.pit_timer += metti * SECONDI_PER_KG
                self.log(f"{e.name} rifornisce {metti:.0f} kg", "pit")
        self.log(f"{e.name} ai box: monta {C.COMPOUNDS[target]['label']}", "pit")
        self.radio_say(e, f"Box, box, box: montiamo {C.COMPOUNDS[target]['label'].lower()}.",
                       "muretto")
        self._radio_cd[e.driver_id] = e.lap + 2

    def _pick_compound(self, e: Entrant) -> str:
        remaining = self.laps - e.lap
        if self.weather.wet > 0.45:
            return "wet"
        if self.weather.wet > 0.18:
            return "inter"
        if remaining <= 16 * self.distance:
            voluta = ("soft", "medium", "hard")
        elif remaining <= 30 * self.distance:
            voluta = ("medium", "hard", "soft")
        else:
            voluta = ("hard", "medium", "soft")
        if not e.stock:
            return voluta[0]
        for m in voluta:
            if e.stock.get(m, 0) > 0:
                return m
        return voluta[0]           # non resta niente: si monta l'usato

    # A che temperatura d'asfalto lavora ogni mescola. La morbida arriva in
    # temperatura subito e va oltre altrettanto in fretta; la dura sull'asfalto
    # freddo non si accende e scivola tutta la gara.
    FINESTRA = {"soft": 30.0, "medium": 37.0, "hard": 44.0, "inter": 22.0, "wet": 18.0}

    def _tyre_life(self, e: Entrant, comp: str) -> float:
        base = {"soft": 17.0, "medium": 26.0, "hard": 37.0, "inter": 22.0, "wet": 26.0}[comp]
        wear_t = self.track.traits.get("tyre_wear", 0.6)
        # non tutte le "morbide" sono uguali: quella che il fornitore porta a
        # Monaco e quella che porta a Silverstone sono due gomme diverse
        if comp in ("soft", "medium", "hard"):
            from ..core import tyres
            base *= tyres.life_scale(tyres.nomination(self.track)[comp])
        # e nemmeno la stessa mescola e' uguale a se stessa: sopra la sua
        # finestra si sfoglia, sotto non si accende
        fuori = (self.cond.track_temp - self.FINESTRA.get(comp, 37.0)) / 18.0
        finestra = 1.0 - 0.22 * max(0.0, fuori) ** 1.6 - 0.10 * max(0.0, -fuori) ** 1.6
        life = (base * (1.35 - 0.62 * wear_t) * (0.78 + 0.42 * e.tyre_skill / 100.0)
                * max(0.55, finestra))
        return life * self.distance

    # --------------------------------------------------------------- duelli
    def _resolve_battles(self, dt: float) -> None:
        """Chi sta dietro prova a passare: una volta a giro, come in pista.

        Sorpassare non e' una moneta lanciata ogni secondo. Si arriva a ridosso,
        si studia il punto, e una volta a giro ci si prova: in fondo al
        rettilineo dove si puo', all'uscita dell'ultima curva dove non si puo'.
        Quanto serve per riuscirci lo dice il circuito - a Monza bastano due
        decimi al giro, a Monaco non basta un secondo - e poi contano il mestiere
        di chi attacca e quello di chi si difende.
        """
        live = [e for e in self.entrants if e.status == "running"]
        live.sort(key=lambda e: -e.dist)
        ot_track = self.track.traits.get("overtaking", 0.5)
        for i in range(1, len(live)):
            ahead, behind = live[i - 1], live[i]
            gap_m = ahead.dist - behind.dist
            if gap_m > self.follow * 2.4 or gap_m < 0:
                behind.dirty_air = max(0.0, behind.dirty_air - dt * 1.5)
                continue
            behind.dirty_air = min(1.0, behind.dirty_air + dt * 0.9) * (1.0 - 0.55 * ot_track)
            if (self.safety_car > 0 or behind.overtake_cd > 0
                    or gap_m > self.follow * 1.25):
                continue
            # quante volte al giro ci si prova e' un numero piccolo, e non
            # dipende da quanti posti buoni ci sono: si sceglie il migliore e
            # si aspetta quello
            tetto = TENTATIVI_APERTA if ot_track > 0.65 else TENTATIVI_GIRO
            if behind.tentativi_giro >= tetto:
                continue
            # e soprattutto: qui c'e' dove passare? Un sorpasso non capita in
            # mezzo a una curva, capita in fondo a un dritto lungo abbastanza
            # da prendere la scia e con una staccata vera in cui infilarsi. Il
            # circuito dice dove sono quei posti e quanto valgono
            posto = self.track.zona_di(behind.lap_fraction(self.track_len))
            if posto <= 0.0:
                continue
            # e in una zona mediocre spesso non ci si prova nemmeno: si tiene il
            # tentativo per quella buona, che e' quello che fa un pilota quando
            # sa che due curve dopo c'e' il rettilineo vero
            if self.rng.random() > INGAGGIO_MINIMO + (1.0 - INGAGGIO_MINIMO) * posto:
                continue
            # da qui in poi e' il tentativo in questa zona, riuscito o no
            behind.overtake_cd = ATTESA_ZONA
            behind.tentativi_giro += 1
            # l'override: stando entro un secondo si possono chiedere i
            # trecentocinquanta kilowatt pieni fin quasi in fondo al dritto, e
            # costano mezzo megajoule. Se chi sta davanti e' a secco non ha
            # modo di rispondere, ed e' li' che si passa
            gap_s = gap_m / max(20.0, self.track_len / max(30.0, behind.last_lap))
            spinta = 0.0
            if EN.puo_override(self, behind, gap_s):
                spinta = EN.usa_override(self, behind)
                behind.override_t = 4.0
                if ahead.clipping:
                    spinta *= 1.5
            # non conta solo il passo medio: conta come e' venuta fuori quella
            # curva, se chi difende ha bloccato una ruota, se la trazione ha
            # spinto meglio. Due macchine uguali non si passano mai per pura
            # velocita', si passano quando capita l'occasione
            vantaggio = ahead.clean_lap - behind.clean_lap + self.rng.gauss(0.0, 0.22)
            if vantaggio <= 0.0:
                continue
            # quanto vantaggio serve: in fondo al rettifilo di Monza poco, in
            # fondo a una curva veloce tantissimo
            soglia = SOGLIA_ZONA + SOGLIA_SCARSA * (1.0 - posto)
            p = max(0.0, (vantaggio - 0.35 * soglia) / soglia) * FORZA_SORPASSO
            p *= 1.0 + spinta
            # e se chi sta davanti ha la batteria a terra, sul dritto non c'e'
            # proprio: quello e' il momento in cui i sorpassi si fanno da soli.
            # Chi sta ricaricando a gas spalancato invece non prende nessun
            # bonus qui: quello che perde lo perde gia' sul passo, e contarlo
            # due volte riempiva le gare di sorpassi che non esistono
            if ahead.scarica:
                p *= 1.30
            # e senza arrivare a tanto: conta gia' averne piu' di lui. Chi
            # imbocca il dritto con un megajoule di vantaggio ce l'ha in mano
            # per tutta la staccata, e chi ne ha meno lo sa e si difende prima.
            # E' qui che la gestione diversa dell'elettrico paga: non si passa
            # perche' si va piu' forte, si passa perche' in quel giro li' si ha
            # in cassa quello che l'altro ha gia' speso
            if self.batteria_max > 0.2:
                piu = (behind.carica - ahead.carica) / self.batteria_max
                p *= 1.0 + VANTAGGIO_CARICA * max(-0.5, min(0.5, piu))
            # e la riscossa: chi e' stato passato pochi giri fa sa dove l'altro
            # ha speso, e ci riprova. Vale solo contro chi l'ha passato, e vale
            # in proporzione a quanta energia gli e' rimasta in piu'
            if behind.riscossa > 0.0 and ahead.driver_id == behind.riscossa_su:
                margine = 0.35
                if self.batteria_max > 0.2:
                    margine = max(0.0, min(1.0, 0.35 + (behind.carica - ahead.carica)
                                           / self.batteria_max))
                p *= 1.0 + RISCOSSA_FORZA * margine
            # e poi ci vuole lo spazio per stare affiancati: e' quello che
            # separa Monte Carlo dal Red Bull Ring a parita' di staccata
            p *= 0.20 + 0.80 * ot_track
            p *= 0.70 + 0.60 * (behind.racecraft / 100.0)
            p *= 0.85 + 0.35 * (behind.aggression / 100.0)
            p /= max(0.60, 0.65 + 0.55 * (ahead.racecraft / 100.0))
            p *= 1.0 + 0.55 * self.bagnato - SPRUZZI_SORPASSO * self.weather.wet ** 2
            # e poi c'e' quello che il passo non spiega: la traiettoria da
            # fuori, la staccata tenuta mezzo metro piu' in la', il buco che
            # c'era per un decimo. Chi ce l'ha passa dove non si passa - e chi
            # difende con inventiva quel buco lo chiude prima che si apra
            p *= 0.82 + 0.36 * (behind.estro / 100.0)
            p /= max(0.75, 0.86 + 0.28 * (ahead.estro / 100.0))
            # e comunque, per quanto uno sia piu' veloce, il posto per passare
            # non lo inventa: e' il tetto che separa Monza da Monte Carlo
            if self.rng.random() >= min(TETTO_BASE + TETTO_PISTA * ot_track, p):
                continue
            behind.dist, ahead.dist = ahead.dist + 6.0, ahead.dist - self.follow * 0.6
            # passare costa: si e' arrivati in fondo al dritto in attacco, e
            # quello che si e' speso adesso non ce l'hai piu' per difenderti
            behind.carica = max(0.0, behind.carica - COSTO_SORPASSO_MJ * EN.scala(self))
            behind.overtake_cd = max(25.0, behind.last_lap * 1.1)
            # chi e' stato passato non aspetta un giro intero per rispondere:
            # aspetta la prossima zona, e per un po' ci prova con piu' voglia
            ahead.overtake_cd = RISPOSTA_ATTESA
            ahead.riscossa = RISCOSSA_S
            ahead.riscossa_su = behind.driver_id
            self.log(f"SORPASSO: {behind.name} passa {ahead.name}", "pass")
            if self.rng.random() < 0.075 * (behind.aggression / 100.0) * (1.0 + self.weather.wet):
                dmg = self.rng.uniform(4, 26)
                behind.damage = min(100.0, behind.damage + dmg)
                ahead.damage = min(100.0, ahead.damage + dmg * 0.8)
                self.log(f"Contatto tra {behind.name} e {ahead.name}!", "warn")
                grave = dmg > 12
                self._investigate(behind, "contatto" if grave else "contatto_lieve")
                # una toccata forte non e' un'ala da cambiare: e' la gara finita
                if dmg > 18:
                    for x, quota in ((behind, 0.28), (ahead, 0.20)):
                        if x.status == "running" and self.rng.random() < quota:
                            x.status = "retired"
                            x.dnf_reason = "danni da contatto"
                            self.log(f"RITIRO: {x.name} - danni da contatto", "dnf")
                self._maybe_safety_car(0.18)

    # ------------------------------------------------------------ commissari
    def _investigate(self, e, kind: str) -> None:
        """Apre un'investigazione. I commissari non decidono subito."""
        if e.under_review > 0 or e.status != "running":
            return
        e.under_review = self.rng.uniform(25.0, 70.0)
        e.review_kind = kind
        self.log(f"{e.name} sotto investigazione: "
                 f"{PENALTY_LABELS.get(kind, kind).lower()}", "warn")

    def _resolve_reviews(self, dt: float) -> None:
        """Le decisioni arrivano dopo qualche minuto, come in pista."""
        for e in self.entrants:
            if e.under_review <= 0:
                continue
            e.under_review -= dt
            if e.under_review > 0:
                continue
            kind, e.review_kind = e.review_kind, ""
            meta = PENALTY_RULES.get(kind, {})
            # un pilota pulito viene creduto piu' facilmente
            scusante = 0.10 + 0.35 * (e.consistency / 100.0)
            if self.rng.random() < scusante:
                self.log(f"{e.name}: nessun provvedimento", "info")
                continue
            secondi = meta.get("secondi", 5.0)
            e.penalty_pending += secondi
            e.penalty_total += secondi
            e.penalties_given.append(kind)
            self.log(f"PENALITA': {secondi:.0f} secondi a {e.name} - "
                     f"{PENALTY_LABELS.get(kind, kind).lower()}", "pen")

    def _track_limits(self, e, dt: float) -> None:
        """Uscite di pista ripetute: tre avvertimenti e arriva la penalita'."""
        if e.status != "running" or self.safety_car > 0:
            return
        # Probabilita' al secondo, tarata perche' un pilota medio raccolga circa
        # un avvertimento a gara: servendone tre per la penalita', ne esce
        # qualcuna sparsa nell'arco del weekend, non una a ogni curva.
        rischio = (100.0 - e.consistency) * 0.0000052 * (0.6 + 0.9 * e.push_mode)
        rischio *= 1.0 + 0.8 * self.track.traits.get("bumpiness", 0.4)
        if self.rng.random() < rischio * dt:
            e.track_warnings += 1
            if e.track_warnings % 3 == 0:
                self._investigate(e, "limiti_pista")
            else:
                self.log(f"{e.name}: avvertimento per i limiti della pista "
                         f"({e.track_warnings})", "info")

    def _update_positions(self) -> None:
        for i, e in enumerate(self.order(), 1):
            e.position = i

    def _maybe_incident(self, dt: float) -> None:
        if self.safety_car > 0:
            return
        base = 0.000018 * (1.0 + 2.2 * self.weather.wet)
        base *= 1.0 + 1.4 * (1.0 - self.track.traits.get("overtaking", 0.5))
        if self.rng.random() < base * dt * 0.55:
            self._maybe_safety_car(0.45, forced=True)

    def _maybe_safety_car(self, p: float, forced: bool = False) -> None:
        if self.safety_car > 0:
            return
        if forced or self.rng.random() < p:
            vsc = self.rng.random() < 0.45
            self.vsc = vsc
            self.safety_car = self.rng.uniform(120.0, 260.0)
            self.log("Virtual Safety Car" if vsc else "SAFETY CAR IN PISTA", "sc")

    # -------------------------------------------------------------- risultati
    def fast_forward(self, max_steps: int = 60000, dt: float = 1.0) -> None:
        steps = 0
        while not self.finished and steps < max_steps:
            self.update(dt)
            steps += 1
        self.finished = True

    def result_order(self) -> list:
        fin = [e for e in self.entrants if e.status == "finished"]
        fin.sort(key=lambda e: e.finished_time)
        ret = [e for e in self.entrants if e.status not in ("finished",)]
        ret.sort(key=lambda e: (-e.lap, -e.dist))
        return fin + ret
