"""Geometria della pista e simulatore di giro quasi-statico.

Il layout testuale (S/R/L) viene trasformato in:
  * una polilinea chiusa da disegnare a schermo
  * un profilo di curvatura usato dal modello di giro

Il modello di giro e' un classico "quasi steady state": per ogni punto si
calcola la velocita' massima consentita dall'aderenza laterale, poi una
passata in avanti (limite di accelerazione) e una all'indietro (limite di
frenata) restituiscono il profilo di velocita' e quindi il tempo sul giro.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from .. import config as C

# Risoluzione della discretizzazione, in metri. Con la spline che infittisce il
# rilievo si puo' scendere: cinque metri sono un terzo di curva di Monte Carlo,
# e sotto quella soglia il modello di giro non impara piu' niente ma il conto
# raddoppia.
STEP_M = 5.0

# Dove finisce una curva lenta e dove comincia una veloce, in metri al secondo.
# Sono le soglie con cui in pista si divide il lavoro: sotto i centotrenta
# all'ora comanda l'aderenza meccanica, sopra i duecento comanda il carico.
V_LENTA = 36.0
V_VELOCE = 56.0

# I domini in cui si spezza un giro: e' su questi che una macchina e' forte o
# debole, e su questi che un aggiornamento porta o non porta.
DOMINI = ("lente", "medie", "veloci", "trazione", "frenata", "rettilinei")

# Sotto questa frazione della velocita' massima una curva conta come curva.
SOGLIA_CURVA = 0.93

# Quanto cala l'aderenza quando la gomma viene schiacciata. Una gomma non
# rende il doppio con il doppio del peso sopra: rende un po' meno del doppio,
# e piu' la si carica meno rende. E' il motivo per cui il carico aerodinamico
# ha un rendimento calante - in una curva veloce il decimo di carico in piu'
# vale meno del decimo di prima - e senza questo una curva al limite del pieno
# gas diventerebbe una scogliera: mezzo punto di ala in piu' e la si fa tutta
# spalancata, mezzo in meno e si frena.
SENSIBILITA_CARICO = 0.18

# Quanto e' piena l'ellisse dell'aderenza combinata. Con 2 e' un cerchio: quel
# che si spende in curva si toglie tutto dalla frenata. Una monoposto con le
# ali fa molto meglio - frena forte anche piegata - e il suo diagramma e' piu'
# squadrato: e' quello che dice questo esponente.
ELLISSE = 3.0

# Fin dove arriva l'uscita di curva: sopra questa frazione della velocita'
# massima non e' piu' trazione, e' un rettilineo.
V_USCITA = 0.62

# ------------------------------------------------------- le sensibilita'
# Un chilo di benzina non costa lo stesso a Monza e a Losail, un decimo di
# aderenza in meno non si paga uguale al Red Bull Ring e a Madrid, e l'aria
# sporca di chi sta davanti a Monte Carlo e' un'altra cosa che sul rettifilo.
# La gara pero' li trattava tutti come numeri unici, uguali per le
# ventiquattro piste: era l'unico pezzo di simulazione che non guardava il
# circuito. Adesso li misura il modello di giro - una volta sola, quando la
# pista si tara - e quello che arriva alla gara e' un moltiplicatore attorno a
# uno: il livello resta quello calibrato sul mondo vero, la forma la da' la
# fisica. Sono numeri con la stessa dignita' di `ers_secondi`, e nascono nello
# stesso posto.
#
# Questi sono i valori medi delle ventiquattro piste in calendario: servono
# solo a centrare i moltiplicatori su uno. Se il calendario cambia parecchio
# vanno rimisurati, e li rimisura `tools/sensibilita_piste.py`.
BENZINA_RIF = 0.0182     # secondi al giro per chilo
SCIA_RIF = 1.35          # secondi persi seguendo, a carico ridotto
GRIP_RIF = 34.13         # secondi per unita' di aderenza persa
PILOTA_RIF = 0.3233      # quota di giro che non e' rettilineo

# Quanto perde chi segue: il carico se ne va perche' l'aria arriva sporca, la
# resistenza cala un po' perche' arriva anche piu' lenta. Le due cose insieme
# fanno la scia, e non si pesano uguale su tutte le piste - ed e' esattamente
# quello che questa misura serve a tirare fuori.
SCIA_CARICO = 0.85
SCIA_RESISTENZA = 0.94

# Quanto sopra la velocita' che il circuito concede va messo il limitatore.
# Poco: l'ultima marcia serve a finire il rettilineo, non a fare da vetrina, e
# ogni chilometro all'ora di margine che non si usa e' un rapporto piu' lungo
# di quanto serva - cioe' una ripresa peggiore in tutte le altre marce.
MARGINE_LIMITATORE = 1.02


@dataclass
class Segment:
    kind: str      # "S" | "R" | "L"
    length: float  # metri
    radius: float  # metri (0 per i rettilinei)
    turn: float    # radianti con segno (+ destra, - sinistra)
    speed_class: int = 0


@dataclass
class Track:
    id: str
    name: str
    gp: str
    country: str
    flag: str
    length_km: float
    laps: int
    corners: int
    pit_loss: float
    sprint: bool
    traits: dict
    layout: str
    ref_lap: float = 90.0
    month: int = 3
    contract_until: int = 9999   # ultima stagione coperta dal contratto
    fee: float = 25.0            # canone annuo pagato dal promotore, in M$
    tradition: float = 0.3       # quanto e' intoccabile (Monaco 1.0)
    popularity: float = 60.0     # richiamo di pubblico
    calibration: float = 1.0
    wing_ref: float | None = None   # l'ala che il modello di giro vuole qui
    gearing_ref: float | None = None  # e i rapporti: quanto lunga vuole l'ultima
    domain_map: list = field(default_factory=list)   # cosa e' ogni metro di pista
    corner_map: list = field(default_factory=list)   # le curve, una per una
    zone_ala: list = field(default_factory=list)     # dove si apre l'ala e si prova a passare
    mappa_ala: list = field(default_factory=list)    # le stesse, in tabella per la gara
    energia_giro: float = 0.0    # MJ che si riescono a recuperare in un giro
    ers_secondi: float = 0.0     # quanto vale la spinta elettrica, in secondi al giro
    # quanto pesano qui, rispetto alla pista media, le cose che in gara
    # cambiano il passo giro dopo giro
    benzina_rel: float = 1.0     # un chilo di benzina
    scia_rel: float = 1.0        # l'aria sporca di chi sta davanti
    grip_rel: float = 1.0        # un punto di aderenza: mescola e usura
    pilota_rel: float = 1.0      # un punto di pilota
    start: list = field(default_factory=list)   # [lat, lon] della linea del traguardo
    senso: str = ""              # "orario" | "antiorario": da che parte si gira
    settori: list = field(default_factory=list)  # dove tagliano i due intertempi
    larghezza_m: float = 13.0    # quanto e' larga la pista: decide quanto si raddrizza
    scala_m: float = 0.0         # il lato del riquadro che contiene il circuito, in metri
    altitude: float = 0.0        # metri sul livello del mare: l'aria che si respira
    night: bool = False          # si corre col buio: l'asfalto non prende sole
    climate: dict = field(default_factory=dict)   # temperatura, pioggia e vento del mese
    geo: list = field(default_factory=list)   # [[lat, lon], ...] del tracciato reale

    segments: list = field(default_factory=list)
    points: list = field(default_factory=list)      # [(x, y)] normalizzati 0..1
    pit_points: list = field(default_factory=list)  # la corsia box, stessa scala
    curvature: list = field(default_factory=list)   # 1/raggio per ogni punto
    ds: float = STEP_M
    _curva_linea: list = None    # la curvatura della linea, calcolata una volta
    sector_bounds: tuple = (0.0, 0.0)
    # il giro visto dal cronometro invece che dal metro: a ogni frazione di
    # tempo, a che punto del tracciato si e' e a che velocita' ci si passa
    time_map: list = field(default_factory=list)     # frazione di giro percorsa
    speed_map: list = field(default_factory=list)    # velocita' in km/h, vettura campione
    zone_map: list = field(default_factory=list)     # che cosa si sta facendo li'
    sector_time: tuple = (0.3333, 0.6667)            # quando scattano gli intertempi
    ref_time: float = 0.0                            # il giro a cui quelle velocita' si riferiscono
    speed_peak: float = 0.0                          # la punta della vettura campione, km/h

    # ---------------------------------------------------------------- build
    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        t = cls(
            id=d["id"], name=d["name"], gp=d["gp"], country=d["country"], flag=d["flag"],
            length_km=d["length_km"], laps=d["laps"], corners=d["corners"],
            pit_loss=d["pit_loss"], sprint=d.get("sprint", False),
            traits=d["traits"], layout=d["layout"], ref_lap=d.get("ref_lap", 90.0), month=int(d.get("month", 3)),
            contract_until=int(d.get("contract_until", 9999)),
            fee=float(d.get("fee", 25.0)), tradition=float(d.get("tradition", 0.3)),
            popularity=float(d.get("popularity", 60.0)),
            start=list(d.get("start") or []),
            senso=str(d.get("senso", "")),
            settori=list(d.get("settori") or []),
            altitude=float(d.get("altitude", 0.0)),
            larghezza_m=float(d.get("larghezza_m", 13.0)),
            night=bool(d.get("night", False)),
            climate=dict(d.get("climate") or {}),
            geo=d.get("geo") or [],
        )
        if t.geo:
            # tracciato vero: forma e curvatura vengono dalle coordinate
            t._parse_layout()          # serve ancora per il conteggio dei segmenti
            t._build_from_geo()
        else:
            t._parse_layout()
            t._build_geometry()
        return t

    # ------------------------------------------------- geometria da coordinate
    def _build_from_geo(self) -> None:
        """Costruisce disegno e curvatura dal tracciato reale.

        Le coordinate arrivano in gradi: si proiettano in metri attorno al
        centro del circuito (su cinque chilometri la deformazione e'
        trascurabile), si riscalano sulla lunghezza ufficiale, si campionano a
        passo costante e si lisciano quel tanto che basta a togliere il rumore
        del rilievo senza smussare le curve vere.
        """
        pts = _project(self.geo)
        if len(pts) < 8:
            self._build_geometry()
            return
        if math.dist(pts[0], pts[-1]) > 1.0:
            pts.append(pts[0])                      # chiude l'anello

        target = self.length_km * 1000.0
        raw_len = _path_length(pts)
        if raw_len > 1.0:
            k = target / raw_len                    # la misura ufficiale comanda
            pts = [(x * k, y * k) for x, y in pts]

        n = max(64, int(round(target / STEP_M)))
        # prima si infittisce con la spline, poi si ricampiona a passo fisso:
        # cosi' il passo lo decide STEP_M e la forma la decide il rilievo
        pts = _resample(_spline(pts), n)
        pts = _smooth(pts, passes=2)
        pts = self._al_traguardo(pts, k if raw_len > 1.0 else 1.0)

        self.ds = target / len(pts)
        self.curvature = _curvature(pts)
        self._curva_linea = None
        box = _corsia_box(pts, self.ds, self.pit_loss)
        self.scala_m = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                           max(p[1] for p in pts) - min(p[1] for p in pts))
        self.points, extra = _normalise(pts, [box])
        self.pit_points = extra[0]
        self.sector_bounds = (len(pts) / 3.0, 2.0 * len(pts) / 3.0)

    def _al_traguardo(self, pts: list, scala: float) -> list:
        """Mette il tracciato nel verso di gara e lo fa cominciare dal traguardo.

        Le strade di OpenStreetMap cominciano dove ha cominciato a disegnarle
        chi le ha disegnate, e vanno nel verso in cui le ha disegnate: nessuna
        delle due cose ha a che vedere con la gara. Il gioco pero' conta tutto
        da quella linea - i giri, i settori, i distacchi, dove sono le vetture -
        quindi il tracciato va girato nel verso giusto e ruotato fin li'.
        """
        if self.senso:
            area = 0.0
            for i in range(len(pts)):
                j = (i + 1) % len(pts)
                area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
            antiorario = area > 0
            if antiorario != (self.senso == "antiorario"):
                pts = [pts[0]] + pts[:0:-1]        # si gira dall'altra parte
        if len(self.start) == 2:
            # la linea sta in gradi: si porta nello stesso piano in metri del
            # tracciato, con la stessa origine e la stessa scala
            linea = _project([list(self.start)], origine=_centro(self.geo))[0]
            bx, by = linea[0] * scala, linea[1] * scala
            i0 = min(range(len(pts)), key=lambda i: (pts[i][0] - bx) ** 2 + (pts[i][1] - by) ** 2)
            pts = pts[i0:] + pts[:i0]
        return pts

    def _parse_layout(self) -> None:
        raw: list[Segment] = []
        for tok in self.layout.split():
            kind = tok[0]
            if kind == "S":
                raw.append(Segment("S", float(tok[1:]), 0.0, 0.0))
            else:
                body, _, cls_s = tok[1:].partition(":")
                deg = float(body)
                sc = int(cls_s) if cls_s else 3
                r = C.CORNER_RADIUS.get(sc, 90.0)
                arc = math.radians(deg) * r
                turn = math.radians(deg) * (1 if kind == "R" else -1)
                raw.append(Segment(kind, arc, r, turn, sc))

        # riscala i soli rettilinei per far combaciare la lunghezza ufficiale
        target = self.length_km * 1000.0
        arc_total = sum(s.length for s in raw if s.kind != "S")
        str_total = sum(s.length for s in raw if s.kind == "S")
        if str_total > 0:
            k = max(0.25, (target - arc_total) / str_total)
            for s in raw:
                if s.kind == "S":
                    s.length *= k
        self.segments = raw

    def _build_geometry(self) -> None:
        """Cammina i segmenti, poi chiude il tracciato e lo normalizza."""
        pts: list[tuple[float, float]] = []
        curv: list[float] = []
        x = y = 0.0
        heading = 0.0

        # Un circuito chiuso deve girare in tutto di 360 gradi. Lo scarto fra il
        # totale delle curve descritte e il giro completo viene distribuito come
        # curvatura costante lungo tutto il tracciato: e' cio' che nella realta'
        # fanno i raccordi e i lunghi curvoni fra una curva e l'altra.
        total_turn = sum(s.turn for s in self.segments)
        abs_turn = sum(abs(s.turn) for s in self.segments) or 1.0
        target = math.tau if total_turn >= 0 else -math.tau
        residual = target - total_turn
        draw_turn = {id(s): (s.turn + residual * abs(s.turn) / abs_turn)
                     for s in self.segments}

        for seg in self.segments:
            n = max(1, int(round(seg.length / STEP_M)))
            step = seg.length / n
            dturn = draw_turn[id(seg)] / n if seg.kind != "S" else 0.0
            k = (1.0 / seg.radius) if seg.radius else 0.0
            for _ in range(n):
                heading += dturn
                x += math.cos(heading) * step
                y += math.sin(heading) * step
                pts.append((x, y))
                curv.append(k)

        self.ds = (self.length_km * 1000.0) / len(pts)

        # chiusura dell'anello: distribuisce lo scarto lungo tutto il giro
        gx, gy = pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]
        n = len(pts)
        pts = [(px - gx * i / (n - 1), py - gy * i / (n - 1)) for i, (px, py) in enumerate(pts)]

        pts = _smooth(pts, passes=3)
        box = _corsia_box(pts, self.ds, self.pit_loss)
        self.scala_m = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                           max(p[1] for p in pts) - min(p[1] for p in pts))
        self.points, extra = _normalise(pts, [box])
        self.pit_points = extra[0]
        self.curvature = curv
        self._curva_linea = None
        self.sector_bounds = (n / 3.0, 2.0 * n / 3.0)

    # ------------------------------------------------------- modello di giro
    def lap_model(self, car, wet: float = 0.0, grip: float = 1.0, rho: float | None = None,
                  bias: dict | None = None, elettrico: float = 1.0):
        """Restituisce (tempo_giro_s, punta_kmh, profilo_velocita).

        La punta e' quella che si tocca davvero sul giro, cioe' quella che
        segnerebbe una rilevazione in fondo al dritto - non la velocita' a cui
        la macchina arriverebbe su un rettilineo infinito, che e' un asintoto e
        non un dato. Le due cose sono diverse ovunque e a Monza lo erano di
        trentacinque km/h.

        `car` espone: downforce, drag, power, mech_grip, braking, mass_base,
        mass_extra. `rho` e' la densita' dell'aria: a Citta' del Messico ce n'e'
        un quarto di meno che sul mare, e una monoposto senza aria non ha
        carico - ne' resistenza. `bias` sono i moltiplicatori di aderenza per
        dominio: una macchina non e' brava allo stesso modo nelle curve lente e
        in quelle veloci.
        """
        t, _asintoto, v, _vlim, _cl = self._solve(car, wet, grip, rho, bias,
                                                  elettrico=elettrico)
        return t, max(v) * 3.6, v

    def _solve(self, car, wet: float, grip: float, rho, bias: dict | None, giri: int = 2,
               elettrico: float = 1.0):
        """Il conto vero: profilo di velocita', limiti e classe di ogni punto.

        `giri` sono le passate avanti-indietro: due fanno propagare bene la
        chiusura dell'anello, una basta quando il tempo serve solo per
        confrontare due assetti fra loro.
        """
        rho = C.RHO if rho is None else rho
        b = bias or {}
        cla = C.CLA_BASE * car.downforce
        cda = C.CDA_BASE * car.drag
        # sul dritto le ali si appiattiscono: la resistenza cala di un quinto e
        # la punta sale, ed e' li' che il 2026 ha cambiato faccia ai rettilinei
        cda_x = cda * (1.0 - C.QUOTA_XMODE)
        dritto = [k < C.K_DRITTO for k in self.curvature]
        mass = car.mass_base + car.mass_extra
        power = (getattr(car, "potenza_max_w", C.POWER_W) * car.power
                 * getattr(car, "potenza_reg", 1.0))
        mu = C.MU_LAT * car.mech_grip * grip * (1.0 - 0.30 * wet)
        mu_b = C.MU_BRAKE * car.braking * grip * (1.0 - 0.28 * wet) * b.get("frenata", 1.0)
        mu_t = (C.MU_TRAZIONE * car.mech_grip * grip * (1.0 - 0.30 * wet)
                * b.get("trazione", 1.0))

        n = len(self.curvature)
        ds = self.ds
        # la curvatura che conta non e' quella dell'asse della pista: e' quella
        # della linea che ci si passa sopra, che e' piu' larga di mezza
        # carreggiata e quindi piu' dolce
        curva = self.curvatura_linea()
        quota_e = getattr(car, "quota_elettrica", C.QUOTA_ELETTRICA)
        # la centralina non mette a terra tutto quello che c'e' in cassa: il
        # passaggio fra termico ed elettrico ha un costo, e quanto costa lo
        # decide il software del motorista
        elettrico *= max(0.0, min(1.0, getattr(car, "deploy", 1.0)))
        v_taglio = getattr(car, "v_taglio", C.V_TAGLIO_ERS)
        v_fine = getattr(car, "v_fine", C.V_FINE_ERS)

        # il cambio: dove arriva l'ultima e quanto sono distanziati gli otto
        # rapporti. La prima e' quella di sempre, l'ultima la sceglie chi
        # prepara la macchina, e il passo fra un rapporto e l'altro viene di
        # conseguenza - piu' l'ultima e' lunga, piu' i salti sono grossi
        rapporti = float((getattr(car, "setup", None) or {}).get("gearing", 50.0))
        v_ultima = C.V_ULTIMA_CORTA + (C.V_ULTIMA_LUNGA - C.V_ULTIMA_CORTA) * \
            max(0.0, min(1.0, rapporti / 100.0))
        passo_marce = (v_ultima / C.V_PRIMA) ** (1.0 / max(1, C.MARCE - 1))
        power *= C.RESA_TRASMISSIONE
        # dove arriva ogni rapporto: otto numeri, calcolati una volta. Il conto
        # dentro al giro e' una ricerca binaria su questi, non una scalata di
        # marce - la differenza sono due secondi e mezzo all'avvio del gioco
        cime = [min(v_ultima, C.V_PRIMA * passo_marce ** i) for i in range(C.MARCE)]
        giri_minimi = 1.0 / passo_marce

        def marcia(v: float) -> float:
            """A che punto del rapporto si sta girando, da poco piu' di zero a uno.

            Uno vuol dire limitatore, cioe' potenza massima; appena dopo una
            cambiata si e' in fondo alla scala e il termico da' di meno. Piu'
            i rapporti sono lunghi piu' in basso lo si butta a ogni cambiata.
            """
            i = bisect.bisect_left(cime, v)
            cima = cime[i] if i < C.MARCE else v_ultima
            return max(giri_minimi, min(1.0, v / max(1.0, cima)))

        def potenza(v: float) -> float:
            """La potenza che c'e' davvero a quella velocita'.

            Sopra una certa andatura il regolamento fa calare la parte
            elettrica fino a spegnerla: e' li' che una monoposto smette di
            accelerare, molto prima di dove la porterebbe la sola resistenza
            dell'aria. E sotto, a decidere quanta ce n'e', c'e' il rapporto
            che si sta tirando: in fondo all'ultima non ce n'e' piu' comunque,
            perche' il limitatore e' il limitatore.
            """
            if v >= v_ultima:
                return 0.0
            quota = 1.0
            if v > v_taglio:
                quota = max(0.0, 1.0 - (v - v_taglio) / max(1.0, v_fine - v_taglio))
            # il termico segue i giri, l'elettrico no: il motore elettrico la
            # coppia ce l'ha tutta da subito, ed e' per questo che nel 2026 la
            # ripresa dopo una cambiata non e' piu' quella di prima
            giri = max(C.COPPIA_MINIMA, 1.0 - C.CADUTA_COPPIA * (1.0 - marcia(v)))
            return power * ((1.0 - quota_e) * giri + quota_e * quota * elettrico)

        # Velocita' massima assoluta: dove la potenza che resta non basta piu' a
        # vincere l'aria. La si cerca per bisezione e non rigirando il conto su
        # se stesso: sopra i trecentoventi il regolamento comincia a spegnere
        # l'elettrico, e in quella fascia il conto a tentativi rimbalza fra due
        # valori lontani trenta km/h senza fermarsi mai - con il risultato che
        # la punta dichiarata dipendeva da quante volte si girava il ciclo.
        # La funzione e' monotona, quindi la bisezione ci arriva sempre.
        lo, hi = 5.0, 200.0
        for _ in range(48):
            mid = 0.5 * (lo + hi)
            if potenza(mid) > 0.5 * rho * cda_x * mid ** 3:
                lo = mid
            else:
                hi = mid
        vmax = 0.5 * (lo + hi)
        aero = (rho * cla) / (2.0 * mass)

        # come si spartiscono il lavoro i due assali. Il peso e' quello che e';
        # il carico aerodinamico lo sposta il bilanciamento della vettura - una
        # macchina piantata dietro ne mette meno davanti, una nervosa il
        # contrario - e siccome il carico cresce col quadrato della velocita',
        # quello che si sceglie qui si sente nelle curve veloci e sparisce nei
        # tornanti
        bil = max(-1.0, min(1.0, float(getattr(car, "balance", 0.0) or 0.0)))
        massa_ant = C.QUOTA_MASSA_ANT
        aero_ant = min(0.62, max(0.28, C.QUOTA_AERO_ANT + C.BILANCIA_AERO * bil))
        # quanto carico aerodinamico tocca a ogni assale per ogni chilo che
        # quell'assale deve tenere in curva: uno vuol dire in equilibrio, sotto
        # uno vuol dire che e' quell'assale a mollare per primo
        quota_ant = aero_ant / massa_ant
        quota_post = (1.0 - aero_ant) / (1.0 - massa_ant)

        def carico(v2: float) -> float:
            """Quanti pesi della macchina sta portando la gomma a quella velocita'."""
            return 1.0 + aero * v2 / C.G

        inv_ell = 1.0 / ELLISSE

        def resta(chiesto: float, presa: float, rapporto: float) -> float:
            """Quanta gomma avanza per frenare o accelerare mentre si gira.

            Una gomma ha una sola aderenza e la spende tutta insieme: quello
            che serve per tenere la macchina in curva non e' piu' disponibile
            per rallentare o per spingere. Il conto sta su un'ellisse - piena
            in rettilineo, zero all'apice della curva - ed e' la ragione per
            cui si frena forte dritti e si molla il freno entrando, e per cui
            il gas si apre poco alla volta all'uscita.

            `chiesto` e' l'accelerazione laterale che quel punto pretende,
            `presa` quella che la gomma da' in quella direzione e `rapporto`
            quanto vale l'aderenza laterale rispetto a quella: cosi' il calo
            dovuto al carico si calcola una volta sola, fuori di qui.
            """
            if chiesto <= 1e-9:
                return 1.0
            lato = chiesto * rapporto / max(1e-6, presa)
            if lato <= 0.25:
                return 1.0                     # in curva cosi' larga non si spende niente
            if lato >= 1.0:
                return 0.0
            return (1.0 - lato ** ELLISSE) ** inv_ell

        def lat_limit(k: float):
            """Velocita' massima in curva e che tipo di curva e'.

            La classe si legge sulla velocita' che quella curva permette a una
            macchina di riferimento: sotto i centotrenta e' una curva lenta,
            sopra i duecento e' una curva veloce, e sono due mondi diversi -
            nella prima conta l'aderenza meccanica, nella seconda il carico.
            """
            if k <= 1e-9:
                return vmax, ""

            def velocita(m0: float) -> float:
                # L'aderenza lavora su tutto il peso che la gomma sente, e il
                # carico aerodinamico e' peso: e' la gomma a trasformarlo in
                # tenuta, quindi anche quello va moltiplicato per l'aderenza.
                # Senza, una curva veloce viene fuori molto piu' lenta di
                # quello che e' - ed e' li' che le monoposto fanno il tempo.
                # Il conto si morde la coda - piu' si va forte piu' si schiaccia
                # la gomma, e piu' e' schiacciata meno rende - e si scioglie
                # rigirandolo tre volte, che basta e avanza.
                #
                # E lo si fa due volte, una per assale: la curva la fanno tutti
                # e due insieme, ma a decidere quanto forte ci si passa e' il
                # piu' in difficolta' dei due. Con la vettura in equilibrio le
                # due velocita' vengono uguali e il conto e' quello di sempre;
                # appena il carico non e' ripartito come il peso, una delle due
                # scende - e quella e' la macchina che sottosterza o che
                # sovrasterza, a seconda di quale delle due.
                v2 = 0.0
                for _ in range(3):
                    peggiore = vmax * vmax
                    for q in (quota_ant, quota_post):
                        aq = q * aero
                        m = m0 * (1.0 + aq * v2 / C.G) ** -SENSIBILITA_CARICO
                        d = k - m * aq
                        cand = vmax * vmax if d <= 1e-6 else min(m * C.G / d,
                                                                 vmax * vmax)
                        peggiore = min(peggiore, cand)
                    v2 = peggiore
                return math.sqrt(v2)

            v0 = min(velocita(mu), vmax)
            # una curva e' una curva se rallenta davvero: la curvatura residua
            # di un rettilineo non lo e', per quanto il rilievo la misuri
            if v0 >= vmax * SOGLIA_CURVA:
                return vmax, ""
            classe = ("lente" if v0 < V_LENTA else
                      "veloci" if v0 > V_VELOCE else "medie")
            return min(velocita(mu * b.get(classe, 1.0)), vmax), classe

        limiti = [lat_limit(k) for k in curva]
        vlim = [x[0] for x in limiti]
        classi = [x[1] for x in limiti]

        # quanto vale l'aderenza laterale rispetto a quella che si sta usando:
        # serve all'ellisse, e non cambia mai dentro al giro
        rap_t, rap_b = mu_t / mu, mu_b / mu
        v = list(vlim)
        for _ in range(giri):  # due giri per far propagare la chiusura dell'anello
            # passata in avanti: limite di trazione/potenza
            for i in range(n):
                j = (i + 1) % n
                vi = max(v[i], 5.0)
                drag_a = 0.5 * rho * (cda_x if dritto[i] else cda) * vi * vi / mass
                # anche in accelerazione il carico aerodinamico spinge a terra:
                # a duecento all'ora la trazione non e' quella di un semaforo
                mu_v = mu_t * carico(vi * vi) ** -SENSIBILITA_CARICO
                presa = mu_v * (C.G + aero * vi * vi)
                ki = curva[i]
                quota = resta(vi * vi * ki, presa, rap_t) if ki > 1e-9 else 1.0
                # e la spinta la mettono a terra due ruote sole: conta il
                # carico che sente l'assale posteriore, non tutta la vettura -
                # e sotto spinta quel carico cresce, perche' la macchina si
                # siede. Il conto si morde la coda e si scioglie girandolo due
                # volte, che e' piu' di quanto serva
                # il peso statico che gli tocca piu' la sua fetta di carico
                # aerodinamico: una macchina piantata dietro ne ha di piu', ed
                # e' esattamente il motivo per cui in uscita di curva spinge
                n_post = ((1.0 - massa_ant) * C.G
                          + (1.0 - aero_ant) * aero * vi * vi)
                tetto = C.QUOTA_MOTRICE_MAX * (C.G + aero * vi * vi)
                a_tr = 0.0
                for _ in range(2):
                    carico_post = min(tetto, n_post + C.TRASFERIMENTO * a_tr)
                    a_tr = mu_v * carico_post * quota
                a = min(potenza(vi) / (mass * vi), a_tr) - drag_a
                a = max(a, -8.0)
                cand = math.sqrt(max(1.0, vi * vi + 2.0 * a * ds))
                if cand < v[j]:
                    v[j] = cand
            # passata all'indietro: limite di frenata
            for i in range(n - 1, -1, -1):
                j = (i + 1) % n
                vj = max(v[j], 5.0)
                # in frenata rallentano le gomme, che schiacciate dal carico
                # tengono di piu', e rallenta l'aria: a trecento all'ora vale
                # quasi mezzo g da sola
                mu_v = mu_b * carico(vj * vj) ** -SENSIBILITA_CARICO
                presa = mu_v * (C.G + aero * vj * vj)
                kj = curva[j]
                quota = resta(vj * vj * kj, presa, rap_b) if kj > 1e-9 else 1.0
                a_b = presa * quota + 0.5 * rho * cda * vj * vj / mass  # in frenata l'ala e' aperta
                cand = math.sqrt(max(1.0, vj * vj + 2.0 * a_b * ds))
                if cand < v[i]:
                    v[i] = cand

        t = 0.0
        for i in range(n):
            j = (i + 1) % n
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            t += ds / vm
        return t * self.calibration, vmax * 3.6, v, vlim, classi

    def curvatura_linea(self) -> list:
        """La curvatura vista dalla linea, non dall'asse della pista.

        Una monoposto larga due metri su una pista larga tredici non passa dal
        centro: entra larga, tocca la corda, esce larga, e percorre una curva
        di raggio piu' grande di quella disegnata. Il conto e' geometrico -
        raggio piu' un pezzo di carreggiata - e vale tanto dove la curva e'
        stretta e quasi niente dove e' larga, che e' esattamente come si
        comporta in pista.
        """
        if self._curva_linea is None:
            largo = max(0.0, self.larghezza_m * C.QUOTA_LINEA)
            self._curva_linea = [k / (1.0 + k * largo) if k > 1e-9 else k
                                 for k in self.curvature]
        return self._curva_linea

    def _map_domains(self, ref_car, cond) -> None:
        """Divide il giro in domini una volta per tutte, sulla vettura campione.

        Un circuito e' fatto di pezzi: questo e' un rettilineo, questa una
        staccata, questa una curva lenta. Dove finisce uno e comincia l'altro
        non puo' dipendere da chi ci passa, se no due macchine non si possono
        confrontare. Si decide una volta, con la vettura di riferimento, e
        quella mappa vale per tutti.
        """
        from ..sim import pace
        _t, vmax_kmh, v, vlim, classi = self._solve(
            ref_car, 0.0, pace.surface_grip(cond), cond.rho, None)
        vmax = vmax_kmh / 3.6
        mappa = []
        for i in range(len(v)):
            j = (i + 1) % len(v)
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            dv = v[j] - v[i]
            if classi[i] and v[i] <= vlim[i] * 1.03:
                mappa.append(classi[i])
            elif dv < -0.012 * vm:
                mappa.append("frenata")
            elif dv > 0.002 * vm and v[i] < V_USCITA * vmax:
                mappa.append("trazione")
            else:
                mappa.append("rettilinei")
        self.domain_map = mappa
        self.corner_map = self.corner_list(v, vlim, classi)
        self._map_ala(v)
        self._map_energia(ref_car, cond, v, _t)
        self._map_sensibilita(ref_car, cond, _t, mappa)
        self._map_time(v, mappa)

    # -------------------------------------------------- le sensibilita'
    def _map_sensibilita(self, ref_car, cond, t_con: float, mappa: list) -> None:
        """Quanto pesano qui benzina, aderenza, scia e pilota.

        Tre giri simulati in piu' per circuito, una volta sola quando la pista
        si tara. Si misurano come si misurerebbero in pista: si cambia una
        cosa sola e si guarda il cronometro. Il numero che resta appeso al
        circuito e' un moltiplicatore attorno a uno - la forma - perche' il
        livello lo tiene la gara, tarato su quello che si vede davvero.
        """
        from ..sim import pace
        g = pace.surface_grip(cond)

        # la benzina: la differenza fra il primo giro e l'ultimo, divisa per i
        # chili che si sono bruciati in mezzo
        salvato = ref_car.fuel_kg
        ref_car.fuel_kg = C.FUEL_MASS_KG
        t_pieno = self.lap_model(ref_car, grip=g, rho=cond.rho)[0]
        ref_car.fuel_kg = salvato
        s_kg = (t_pieno - t_con) / max(1.0, C.FUEL_MASS_KG)
        self.benzina_rel = round(max(0.25, s_kg / BENZINA_RIF), 3)

        # l'aderenza: tre punti percentuali in meno, che e' quello che passa
        # fra una mescola e l'altra e fra una gomma nuova e una finita
        t_meno = self.lap_model(ref_car, grip=g * 0.97, rho=cond.rho)[0]
        self.grip_rel = round(max(0.25, ((t_meno - t_con) / 0.03) / GRIP_RIF), 3)

        # la scia: la stessa macchina con il carico che le lascia chi sta
        # davanti. Dove si curva forte e' un macigno, sul rettifilo e' niente
        t_scia = self.lap_model(_Scia(ref_car), grip=g, rho=cond.rho)[0]
        self.scia_rel = round(max(0.15, (t_scia - t_con) / SCIA_RIF), 3)

        # il pilota: conta dove la macchina non va dritta, cioe' dove c'e'
        # qualcosa da guidare. A Monte Carlo e' meta' giro, a Spa un quarto
        if mappa:
            quota = sum(1 for d in mappa if d != "rettilinei") / len(mappa)
            self.pilota_rel = round(max(0.35, quota / PILOTA_RIF), 3)

    # ------------------------------------------------------------- l'energia
    def _map_energia(self, ref_car, cond, v: list, t_con: float) -> None:
        """Quanta energia si riprende in un giro, e quanto vale l'elettrico qui.

        Il motore elettrico si ricarica frenando, e frenare vuol dire buttare
        via energia cinetica: quanta se ne riesce a riprendere lo dice il
        circuito - Monte Carlo frena venti volte da poco, Monza quattro volte
        da tanto - e quanto vale riaverla dipende da quanti rettilinei ci sono
        da tirare. Sono le due facce della stessa cosa, e in un weekend
        decidono se si arriva in fondo al dritto con la spinta o senza.
        """
        n, ds = len(v), self.ds
        mass = ref_car.mass_base + ref_car.mass_extra
        rho = cond.rho
        cda = C.CDA_BASE * ref_car.drag
        potenza_e = (getattr(ref_car, "potenza_max_w", C.POWER_W)
                     * getattr(ref_car, "potenza_reg", 1.0)
                     * getattr(ref_car, "quota_elettrica", C.QUOTA_ELETTRICA))
        preso = 0.0
        for i in range(n):
            j = (i + 1) % n
            if v[j] >= v[i]:
                continue
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            cinetica = 0.5 * mass * (v[i] * v[i] - v[j] * v[j])
            aria = 0.5 * rho * cda * vm * vm * ds      # questa se la porta via il vento
            dt = ds / vm
            # piu' di cosi' il motore non riesce a riprendere, per quanto forte
            # si freni: e' un motore, non un pozzo
            preso += max(0.0, min(cinetica - aria, potenza_e * dt))
        tetto = getattr(ref_car, "recupero_max_mj", C.RECUPERO_MAX_MJ)
        self.energia_giro = round(min(preso / 1e6, tetto), 2)
        # e quanto vale averla: il giro con la spinta contro il giro senza. Il
        # primo e' gia' stato fatto qui sopra, si rifa' solo quello senza
        from ..sim import pace
        t_senza, _, _ = self.lap_model(ref_car, grip=pace.surface_grip(cond),
                                       rho=cond.rho, elettrico=0.0)
        # oltre una certa soglia il confronto perde senso: un giro fatto con la
        # sola parte termica di una power unit quasi tutta elettrica non e' un
        # giro lento, e' un'altra cosa. Si tiene il numero dove resta leggibile
        self.ers_secondi = round(max(0.0, min(18.0, t_senza - t_con)), 3)

    # -------------------------------------------------- dove si apre l'ala
    # L'ala mobile del 2026 non e' il vecchio DRS: si apre in X-mode nei tratti
    # in cui la macchina va dritta, e la si richiude per curvare. I tratti sono
    # questi, e sono anche i soli posti in cui un sorpasso e' pensabile: un
    # pezzo di pista abbastanza lungo da prendere la scia, con in fondo una
    # staccata vera in cui infilarsi. Uno dei due da solo non basta.
    # Il regolamento chiede che una zona di straight mode duri almeno tre
    # secondi: e' la sola soglia scritta, e misurandola sui circuiti veri non
    # e' mai lei a decidere - il tratto piu' corto che passa gli altri filtri
    # dura gia' quattro secondi e mezzo. A dire quali tratti contano sono le
    # altre due: un pezzo di pista abbastanza lungo da prendere la scia, e una
    # staccata vera in fondo in cui infilarsi.
    ALA_MIN_S = 3.0          # la soglia del regolamento
    ALA_MIN_M = 300.0        # e un tratto piu' corto di cosi' non e' un dritto
    ALA_MIN_SALTO = 40.0     # sotto questa frenata non c'e' dove infilarsi
    ALA_ATTACCO = 0.30       # l'attacco si gioca nell'ultimo pezzo del dritto
    ALA_CASELLE = 360        # in quante caselle si spezza il giro per cercarle

    def _map_ala(self, v: list) -> None:
        """I tratti in cui l'ala si apre, misurati sul giro."""
        n, ds = len(v), self.ds
        apici = [i for i in range(n) if v[i] <= v[(i - 1) % n] and v[i] < v[(i + 1) % n]]
        if len(apici) < 2:
            self.zone_ala = []
            return
        zone = []
        for a, b in zip(apici, apici[1:] + apici[:1]):
            passi = (b - a) % n
            lung = passi * ds
            if lung < self.ALA_MIN_M:
                continue
            durata = sum(ds / max(3.0, v[(a + j) % n]) for j in range(passi))
            if durata < self.ALA_MIN_S:
                continue
            picco = max(v[(a + j) % n] for j in range(passi))
            salto = (picco - v[b]) * 3.6
            if salto < self.ALA_MIN_SALTO:
                continue
            # quanto vale come posto per passare: quanta scia si prende e
            # quanto si stacca in fondo
            qualita = max(0.15, min(1.0, (lung / 1400.0) * (salto / 250.0)))
            zone.append({"fine": b / n, "inizio": a / n, "lung": round(lung),
                         "durata": round(durata, 1),
                         "salto": round(salto), "qualita": round(qualita, 3),
                         "attacco": (b / n - self.ALA_ATTACCO * passi / n) % 1.0})
        zone.sort(key=lambda z: -z["qualita"])
        self.zone_ala = zone[:8]
        # la stessa cosa in tabella, perche' la gara la chiede a ogni passo
        # per ogni macchina: cercarla nella lista ogni volta costerebbe
        self.mappa_ala = [0.0] * self.ALA_CASELLE
        for z in self.zone_ala:
            a = int(z["attacco"] * self.ALA_CASELLE)
            b = int(z["fine"] * self.ALA_CASELLE)
            i = a
            while True:
                self.mappa_ala[i % self.ALA_CASELLE] = max(
                    self.mappa_ala[i % self.ALA_CASELLE], z["qualita"])
                if i % self.ALA_CASELLE == b % self.ALA_CASELLE:
                    break
                i += 1

    def zona_di(self, frazione: float) -> float:
        """Quanto vale come posto per passare il punto in cui si e' adesso."""
        if not self.mappa_ala:
            return 0.45          # senza tracciato non si sa: si tira a indovinare
        return self.mappa_ala[int((frazione % 1.0) * self.ALA_CASELLE) % self.ALA_CASELLE]

    # ------------------------------------------------------- il giro nel tempo
    CAMPIONI = 720          # quanto e' fitto il giro raccontato dal cronometro

    def _map_time(self, v, mappa) -> None:
        """Il giro riletto a passo di cronometro invece che a passo di metro.

        Una monoposto non percorre il giro a velocita' costante: in fondo al
        rettilineo copre trecento metri in tre secondi e nel tornantino ne
        copre trenta. Chi guarda la pista vede questo, non un puntino che
        scivola uguale ovunque. Qui il giro viene ricampionato a intervalli di
        tempo uguali: per ogni istante si sa a che punto del tracciato si e', a
        che velocita' ci si passa e che cosa si sta facendo - frenare, tirare,
        girare. Da qui vengono l'animazione, il tachimetro e gli intertempi.
        """
        n = len(v)
        if n < 8:
            return
        ds = self.ds
        acc, tempi = 0.0, [0.0]
        for i in range(n):
            j = (i + 1) % n
            acc += ds / max(3.0, 0.5 * (v[i] + v[j]))
            tempi.append(acc)
        tot = acc or 1.0
        # il tempo a cui quelle velocita' appartengono: e' il metro con cui si
        # riscalano quando in pista si gira piu' piano - serbatoio pieno,
        # gomme finite, pioggia
        self.ref_time = tot * self.calibration
        k = self.CAMPIONI
        pos, vel, zona = [], [], []
        idx = 0
        for s in range(k):
            tau = tot * s / k
            while idx < n - 1 and tempi[idx + 1] < tau:
                idx += 1
            dentro = (tau - tempi[idx]) / max(1e-9, tempi[idx + 1] - tempi[idx])
            pos.append((idx + min(1.0, max(0.0, dentro))) / n)
            vel.append(round(v[idx] * 3.6, 1))
            zona.append(mappa[idx] if idx < len(mappa) else "rettilinei")
        self.time_map, self.speed_map, self.zone_map = pos, vel, zona
        self.speed_peak = max(vel) if vel else 0.0
        self._taglia_settori(tempi, tot, pos)

    def _taglia_settori(self, tempi: list, tot: float, pos: list) -> None:
        """Dove tagliano i due intertempi.

        La federazione mette le due linee in modo che i tre settori durino piu'
        o meno uguale: non un terzo di strada per uno - un terzo di Spa fatto
        di curvoni si percorre in molto meno tempo di un terzo fatto di
        tornanti - ma un terzo di cronometro. E' quello che si fa qui, dove del
        circuito non si sa altro. Dove invece si sa dove stanno davvero le due
        linee, il dato del circuito comanda: a Spa il secondo settore e' mezzo
        giro, e i tempi che escono devono dirlo.
        """
        n = len(tempi) - 1
        if len(self.settori) == 2:
            a, b = (max(0.02, min(0.98, float(x))) for x in self.settori)
            self.sector_bounds = (a * n, b * n)
            self.sector_time = (round(tempi[int(a * n)] / tot, 4),
                                round(tempi[int(b * n)] / tot, 4))
            return
        k = len(pos)
        self.sector_time = (0.3333, 0.6667)
        self.sector_bounds = (pos[k // 3] * n, pos[2 * k // 3] * n)

    # ------------------------------------------------- dove si e', a quanto va
    def pos_at(self, frazione_tempo: float) -> float:
        """A che punto del giro si e' dopo questa frazione di tempo sul giro."""
        m = self.time_map
        if not m:
            return frazione_tempo % 1.0
        f = (frazione_tempo % 1.0) * len(m)
        i = int(f) % len(m)
        j = (i + 1) % len(m)
        a, b = m[i], m[j]
        if b < a:
            b += 1.0
        return (a + (b - a) * (f - int(f))) % 1.0

    def speed_at(self, frazione_tempo: float, giro: float = 0.0) -> float:
        """A quanto si va li', in km/h.

        Le velocita' sono quelle della vettura campione sul giro di
        riferimento: chi sta girando piu' piano - benzina a bordo, gomme
        andate, pioggia - le vede scalate nella stessa proporzione.
        """
        m = self.speed_map
        if not m:
            return 0.0
        v = m[int((frazione_tempo % 1.0) * len(m)) % len(m)]
        if giro > 1.0 and self.ref_time > 1.0:
            v *= self.ref_time / giro
        return v

    def zone_at(self, frazione_tempo: float) -> str:
        """Che cosa si sta facendo in quel punto: frenare, tirare, girare."""
        m = self.zone_map
        if not m:
            return "rettilinei"
        return m[int((frazione_tempo % 1.0) * len(m)) % len(m)]

    def sector_shares(self, car, wet: float = 0.0, grip: float = 1.0, rho=None,
                      bias: dict | None = None) -> tuple:
        """Come questa vettura spezza il giro nei tre settori, in quota di tempo.

        I due traguardi di settore stanno dove stanno - sono punti della pista -
        ma quanto tempo ci mette ognuno ad arrivarci dipende da com'e' fatta la
        macchina: una che va forte nelle curve lente guadagna nel settore in cui
        stanno le curve lente. Senza questo conto tutti farebbero tre settori
        uguali fra loro, e il tabellone non direbbe niente.
        """
        _t, _vm, v, _vl, _cl = self._solve(car, wet, grip, rho, bias)
        n, ds = len(v), self.ds
        a, b = self.sector_bounds
        tempi = [0.0]
        for i in range(n):
            j = (i + 1) % n
            tempi.append(tempi[-1] + ds / max(3.0, 0.5 * (v[i] + v[j])))
        tot = tempi[-1] or 1.0
        return (tempi[min(n, int(a))] / tot, tempi[min(n, int(b))] / tot)

    def sector_at(self, frazione_tempo: float) -> int:
        """In che settore si e' a questa frazione di giro."""
        a, b = self.sector_time
        f = frazione_tempo % 1.0
        return 1 if f < a else (2 if f < b else 3)

    # ---------------------------------------------------------- telemetria
    def telemetry(self, car, wet: float = 0.0, grip: float = 1.0, rho: float | None = None,
                  bias: dict | None = None) -> dict:
        """Il giro raccontato dai dati, non da un aggettivo.

        Dove si sta a tutto gas, dove si frena, quanto tempo si passa nelle
        curve lente e quanto in quelle veloci, quali sono le curve e a che
        velocita' si affrontano. Da qui viene tutto il resto: cosa chiede un
        circuito, dove una macchina guadagna, cosa serve svilupparle.
        """
        t, vmax_kmh, v, vlim, classi = self._solve(car, wet, grip, rho, bias)
        n = len(v)
        ds = self.ds
        scala = (t / self.calibration) if self.calibration else 1.0
        tempi = {d: 0.0 for d in DOMINI}
        mass = car.mass_base + car.mass_extra
        power = (getattr(car, "potenza_max_w", C.POWER_W) * car.power
                 * getattr(car, "potenza_reg", 1.0))
        mu = C.MU_LAT * car.mech_grip * grip * (1.0 - 0.30 * wet)
        aero = (C.RHO if rho is None else rho) * C.CLA_BASE * car.downforce / (2.0 * mass)
        vmax = vmax_kmh / 3.6
        pieno = 0.0
        frenate = 0
        in_frenata = False
        mappa = self.domain_map
        for i in range(n):
            j = (i + 1) % n
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            dt = ds / vm
            dv = v[j] - v[i]
            frena = dv < -0.012 * vm
            if frena and not in_frenata:
                frenate += 1
            in_frenata = frena
            # a che pezzo di pista appartiene questo metro lo dice la mappa del
            # circuito, uguale per tutti: cosi' due macchine si confrontano
            if mappa:
                tempi[mappa[i]] += dt
            elif classi[i] and v[i] <= vlim[i] * 1.03:
                tempi[classi[i]] += dt
            elif frena:
                tempi["frenata"] += dt
            elif dv > 0.002 * vm and v[i] < V_USCITA * vmax:
                # si accelera uscendo da una curva: e' li' che si vede chi ha
                # trazione, fra chi la mette a terra e chi pattina
                tempi["trazione"] += dt
            else:
                tempi["rettilinei"] += dt
            if not frena:
                pieno += dt
        # i tempi si riportano alla scala della calibrazione, come il giro
        k = self.calibration if self.calibration else 1.0
        tempi = {d: x * k for d, x in tempi.items()}
        return {
            "tempo": t,
            # la punta e' quella toccata sul giro, non l'asintoto: e' quella
            # che finisce sulle schede dei circuiti e nel tabellone della gara
            "vmax": max(v) * 3.6,
            "v_media": self.length_km * 1000.0 / max(1e-6, t) * 3.6,
            "domini": tempi,
            "pieno_gas": pieno * k / max(1e-6, t),
            "curve": self.corner_map or self.corner_list(v, vlim, classi),
            "frenate": frenate,
        }

    def corner_list(self, v, vlim, classi) -> list:
        """Le curve del giro: dove sono, che tipo sono, a quanto ci si passa."""
        curve = []
        dentro = False
        for i, cl in enumerate(classi):
            if cl and not dentro:
                dentro = True
                inizio = i
            elif not cl and dentro:
                dentro = False
                if i - inizio < 3:
                    continue
                tratto = range(inizio, i)
                vmin = min(v[x] for x in tratto)
                # una curva e' lenta o veloce per come la si percorre nel punto
                # piu' stretto, non per come ci si arriva
                classe = ("lente" if vmin < V_LENTA else
                          "veloci" if vmin > V_VELOCE else "medie")
                curve.append({"n": len(curve) + 1, "quota": (inizio + i) / 2.0 / len(v),
                              "classe": classe, "v": vmin * 3.6,
                              "settore": self.sector_of((inizio + i) // 2)})
        return curve

    def calibrate(self, ref_car) -> None:
        """Allinea il modello al tempo sul giro di riferimento della pista reale.

        I tempi di riferimento sono pole vere: sono state fatte col clima di
        quel posto in quel mese, a quella quota, su una pista gommata. E' li'
        che si allinea il modello, cosi' tutto il resto - una giornata fredda,
        il venerdi' mattina, l'aria sottile del Messico - si legge come uno
        scarto da quello e non come un errore di taratura.
        """
        from ..sim import pace
        self.calibration = 1.0
        ref_car.setup = ref_car.optimal_setup(self)
        ref_car.evaluate_setup(self)
        ref_car.fuel_kg = 0.0
        cond = pace.nominal(self)
        raw, _, _ = self.lap_model(ref_car, grip=pace.surface_grip(cond), rho=cond.rho)
        if raw > 1.0:
            self.calibration = self.ref_lap / raw
        # meta' quello che dice il modello e meta' quello che dice la scheda del
        # circuito: la prima sa fare i conti, la seconda sa cosa ci portano
        # davvero le squadre. Da sole sbagliano tutte e due
        fisica = self._best_wing(ref_car, cond)
        scheda = 100.0 * min(1.0, max(0.0, self.traits.get("downforce", 0.5)))
        self.wing_ref = round(0.5 * fisica + 0.5 * scheda, 1)
        # i rapporti invece li decide solo il modello, e non c'e' scheda che
        # tenga: dove finisce l'ultima marcia e' una cosa che si misura in
        # fondo al rettilineo piu' lungo, non un aggettivo sul circuito
        ref_car.setup["wing"] = self.wing_ref
        self.gearing_ref = self._best_gearing(ref_car, cond)
        # e con l'ala giusta si segna, metro per metro, che cosa e' questo
        # circuito: dove si frena, dove si curva piano, dove si tira
        ref_car.setup = ref_car.optimal_setup(self, cond=cond)
        self._map_domains(ref_car, cond)

    def rimisura(self, ref_car) -> None:
        """Rifa' le mappe del giro con la vettura di adesso, senza ritarare."""
        from ..sim import pace
        cond = pace.nominal(self)
        ref_car.setup = ref_car.optimal_setup(self, cond=cond)
        ref_car.evaluate_setup(self)
        ref_car.fuel_kg = 0.0
        self._map_domains(ref_car, cond)

    def _best_wing(self, ref_car, cond) -> float:
        """L'ala piu' veloce qui: si prova, non si indovina.

        Passata grossolana ogni dieci punti e poi una fine attorno al migliore:
        tredici giri simulati per circuito, una volta sola all'avvio.
        """
        from ..sim import pace
        saved = dict(ref_car.setup)
        grip = pace.surface_grip(cond)

        def giro(w):
            # per scegliere l'ala basta confrontare, non serve il tempo esatto:
            # una passata sola invece di due, e sono la meta' dei conti
            ref_car.setup["wing"] = float(w)
            t, _, _, _, _ = self._solve(ref_car, 0.0, grip, cond.rho, None, giri=1)
            return t

        # la curva del tempo contro l'ala ha un minimo solo: una passata larga
        # e una stretta bastano, e sono la meta' dei giri simulati di prima
        provati = {}

        def costo(w):
            if w not in provati:
                provati[w] = giro(w)
            return provati[w]

        best = min(range(0, 101, 20), key=costo)
        fine = min(range(max(0, best - 10), min(100, best + 10) + 1, 5), key=costo)
        ref_car.setup = saved
        return float(fine)

    def _best_gearing(self, ref_car, cond) -> float:
        """I rapporti piu' veloci qui: si provano, come l'ala.

        Il baratto e' quello vero. Corti, il motore sta sempre vicino al
        regime di potenza massima e in uscita di curva si spinge; ma
        l'ultima finisce presto e in fondo al rettilineo si arriva contro il
        limitatore, che e' il modo piu' stupido di perdere velocita'. Lunghi,
        in fondo al dritto ce n'e' ancora, ma a ogni cambiata il motore viene
        buttato piu' in basso e si riprende peggio. Dove sta il punto giusto
        lo dice la lunghezza dei rettilinei, cioe' il circuito.

        Il punto di partenza non e' un tentativo alla cieca: con i rapporti piu'
        lunghi che si possano mettere il limitatore non lo si tocca mai, e la
        velocita' che si tocca in quelle condizioni e' quella che il circuito
        concede. L'ultima marcia va messa poco sopra quella - come si fa
        davvero - e attorno a quel punto si prova. Cinque giri simulati invece
        di tredici, e il risultato e' lo stesso.
        """
        from ..sim import pace
        saved = dict(ref_car.setup)
        grip = pace.surface_grip(cond)
        provati = {}

        def costo(g):
            if g not in provati:
                ref_car.setup["gearing"] = float(g)
                provati[g] = self._solve(ref_car, 0.0, grip, cond.rho, None, giri=1)[0]
            return provati[g]

        ref_car.setup["gearing"] = 100.0
        _t, _v, v, _l, _c = self._solve(ref_car, 0.0, grip, cond.rho, None, giri=1)
        voluta = max(v) * MARGINE_LIMITATORE
        largo = max(1e-6, C.V_ULTIMA_LUNGA - C.V_ULTIMA_CORTA)
        partenza = 100.0 * (voluta - C.V_ULTIMA_CORTA) / largo
        centro = int(round(max(0.0, min(100.0, partenza)) / 6.0)) * 6
        intorno = [g for g in range(centro - 6, centro + 7, 6) if 0 <= g <= 100]
        best = min(intorno, key=costo)
        ref_car.setup = saved
        return float(best)

    def sector_of(self, idx: int) -> int:
        a, b = self.sector_bounds
        return 1 if idx < a else (2 if idx < b else 3)


# --------------------------------------------------------------- geometria
MIN_RADIUS = 12.0      # sotto questo raggio e' rumore di rilievo, non una curva


class _Scia:
    """La stessa vettura, vista dall'aria sporca di chi la precede.

    Non e' un'altra macchina: e' questa con meno carico e un filo meno
    resistenza, che e' quello che succede a seguire da vicino. Serve solo per
    la misura, e delega tutto il resto alla vettura vera.
    """

    def __init__(self, car, carico: float = SCIA_CARICO,
                 resistenza: float = SCIA_RESISTENZA):
        self._c, self._cl, self._cd = car, carico, resistenza

    def __getattr__(self, k):
        return getattr(self._c, k)

    @property
    def downforce(self) -> float:
        return self._c.downforce * self._cl

    @property
    def drag(self) -> float:
        return self._c.drag * self._cd


def _project(geo, origine: tuple | None = None) -> list:
    """Da gradi a metri, piani, attorno al centro del circuito.

    L'origine si puo' imporre: serve a portare nello stesso piano un punto che
    del circuito non fa parte - la linea del traguardo - senza spostare tutto
    il resto di qualche metro.
    """
    lats = [float(p[0]) for p in geo]
    lons = [float(p[1]) for p in geo]
    lat0, lon0 = origine or (sum(lats) / len(lats), sum(lons) / len(lons))
    mx = 111320.0 * math.cos(math.radians(lat0))
    return [((lon - lon0) * mx, (lat - lat0) * 110540.0) for lat, lon in zip(lats, lons)]


def _centro(geo) -> tuple:
    """Il centro attorno a cui si proietta un tracciato."""
    return (sum(float(p[0]) for p in geo) / len(geo),
            sum(float(p[1]) for p in geo) / len(geo))


def _path_length(pts) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _spline(pts, per_segmento: int = 8, alpha: float = 0.5) -> list:
    """Infittisce la polilinea con una curva che ci passa dentro.

    I punti che arrivano da OpenStreetMap stanno dove la strada piega, e in
    mezzo ci sono venti, trenta, a volte cento metri di niente: unirli con
    segmenti di retta vuol dire disegnare le curve come poligoni, e un poligono
    non ha una curvatura - ne ha una infinita in ogni vertice e zero in mezzo.
    Il modello di giro ci si trova male e l'occhio pure.

    La Catmull-Rom passa esattamente per i punti rilevati e in mezzo ci mette
    l'arco che ci starebbe: non inventa informazione, la ridistribuisce. Si usa
    la versione centripeta - il parametro sta sulla radice della distanza e non
    sulla distanza - perche' quella normale, dove due punti rilevati sono
    vicini e il terzo lontano, scavalca il punto e disegna un cappio: curve
    piu' strette di quelle vere, e un modello di giro che ci frena dentro.
    """
    n = len(pts)
    if n < 4:
        return list(pts)
    fuori = []
    for i in range(n):
        p = [pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]]
        t = [0.0] * 4
        for k in range(1, 4):
            d = math.dist(p[k], p[k - 1])
            t[k] = t[k - 1] + (d ** alpha if d > 1e-9 else 1e-6)
        if t[2] - t[1] < 1e-9:
            fuori.append(pts[i])
            continue
        for j in range(per_segmento):
            tt = t[1] + (t[2] - t[1]) * j / per_segmento
            a1 = _lerp(p[0], p[1], (t[1] - tt) / (t[1] - t[0]), (tt - t[0]) / (t[1] - t[0]))
            a2 = _lerp(p[1], p[2], (t[2] - tt) / (t[2] - t[1]), (tt - t[1]) / (t[2] - t[1]))
            a3 = _lerp(p[2], p[3], (t[3] - tt) / (t[3] - t[2]), (tt - t[2]) / (t[3] - t[2]))
            b1 = _lerp(a1, a2, (t[2] - tt) / (t[2] - t[0]), (tt - t[0]) / (t[2] - t[0]))
            b2 = _lerp(a2, a3, (t[3] - tt) / (t[3] - t[1]), (tt - t[1]) / (t[3] - t[1]))
            fuori.append(_lerp(b1, b2, (t[2] - tt) / (t[2] - t[1]),
                               (tt - t[1]) / (t[2] - t[1])))
    return fuori


def _lerp(a, b, wa: float, wb: float):
    return (a[0] * wa + b[0] * wb, a[1] * wa + b[1] * wb)


def _resample(pts, n: int) -> list:
    """Ricampiona la polilinea chiusa a n punti equidistanti."""
    total = _path_length(pts)
    if total <= 0:
        return pts
    step = total / n
    out = [pts[0]]
    i, carry = 0, 0.0
    while len(out) < n and i < len(pts) - 1:
        a, b = pts[i], pts[i + 1]
        seg = math.dist(a, b)
        if seg <= 1e-9:
            i += 1
            continue
        t = carry + step
        if t <= seg:
            f = t / seg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            pts = pts[:i] + [out[-1]] + pts[i + 1:]
            carry = 0.0
        else:
            carry -= seg
            i += 1
    return out[:n]


def _curvature(pts) -> list:
    """Curvatura in ogni punto, dal cerchio per tre punti consecutivi.

    Si guarda qualche metro avanti e indietro invece dei vicini immediati:
    su punti a otto metri il rumore residuo darebbe raggi assurdi.
    """
    n = len(pts)
    span = max(1, int(round(18.0 / max(1.0, _path_length(pts) / n))))
    out = []
    for i in range(n):
        a, b, c = pts[(i - span) % n], pts[i], pts[(i + span) % n]
        ab, bc, ca = math.dist(a, b), math.dist(b, c), math.dist(c, a)
        cross = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        denom = ab * bc * ca
        k = (2.0 * cross / denom) if denom > 1e-9 else 0.0
        out.append(min(k, 1.0 / MIN_RADIUS))
    return out


def _normalise(pts, extra=None):
    """Porta la polilinea nel quadrato 0..1, centrata, senza deformarla.

    E la gira sottosopra. Nella proiezione il nord e' y positiva, come su una
    carta geografica; sullo schermo la y cresce verso il basso. Senza questo
    giro ogni tracciato finisce disegnato con il nord in fondo - che non e'
    una rotazione, e' uno specchio: le curve vanno dalla parte sbagliata e le
    vetture girano al contrario del verso di gara. Questi sono gli unici punti
    che finiscono a schermo; il modello di giro, la curvatura e il verso di
    marcia restano nel piano della carta, dove il nord sta in alto.
    """
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    scale = 1.0 / max(w, h)
    ox, oy = min(xs), min(ys)
    cx = (1.0 - w * scale) / 2.0
    cy = (1.0 - h * scale) / 2.0

    def porta(p):
        return ((p[0] - ox) * scale + cx, 1.0 - ((p[1] - oy) * scale + cy))

    if extra is None:
        return [porta(p) for p in pts]
    # quello che sta attorno al tracciato - la corsia box - deve muoversi con
    # lui: stessa scala, stessa origine, stesso ribaltamento
    return [porta(p) for p in pts], [[porta(p) for p in e] for e in extra]


# La corsia box: quanto e' larga - la distanza fra l'asse della pista e l'asse
# della corsia - e quanto e' lunga prima e dopo la linea del traguardo. Sono le
# misure medie di un circuito vero: si entra prima della linea, si esce dopo, e
# in mezzo ci stanno venti garage da dodici metri l'uno.
BOX_LARGO = 30.0        # asse pista - asse corsia: pista, erba, muretto, corsia
BOX_PRIMA = 150.0
BOX_DOPO = 250.0
BOX_RACCORDO = 110.0    # quanto ci mette a staccarsi dalla pista e a rientrarci


def _corsia_box(pts: list, ds: float, pit_loss: float = 20.0) -> list:
    """Dove passa la corsia dei box, in metri, sullo stesso piano del tracciato.

    Non ce l'abbiamo da nessuna parte - OpenStreetMap la strada dei box non la
    disegna quasi mai - ma dove sta lo sappiamo lo stesso: corre parallela al
    rettilineo del traguardo, dalla parte interna del circuito, comincia prima
    della linea e finisce dopo. La si costruisce da li': si prende il pezzo di
    tracciato attorno al traguardo, lo si sposta di lato di una ventina di
    metri e lo si raccorda alle due estremita', che e' esattamente il disegno
    di un ingresso e di un'uscita box.

    La lunghezza segue il tempo che quella corsia fa perdere: dove si perdono
    venticinque secondi la corsia e' piu' lunga che dove se ne perdono sedici.
    """
    n = len(pts)
    if n < 16 or ds <= 0:
        return []
    scala = max(0.6, min(1.6, pit_loss / 20.0))
    prima = int(BOX_PRIMA * scala / ds)
    dopo = int(BOX_DOPO * scala / ds)
    raccordo = max(2.0, BOX_RACCORDO / ds)
    if prima + dopo >= n - 4:
        return []
    # da che parte sta l'interno del circuito: e' li' che stanno i box
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    verso = 1.0 if area > 0 else -1.0
    fuori = []
    for k in range(-prima, dopo + 1):
        i = k % n
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        d = math.hypot(tx, ty) or 1.0
        # normale verso l'interno
        nx, ny = -ty / d * verso, tx / d * verso
        # e il raccordo alle due estremita': la corsia nasce sulla pista e ci
        # torna, non compare di colpo a venti metri di distanza
        vicino = min(k + prima, dopo - k, raccordo) / raccordo
        largo = BOX_LARGO * max(0.0, min(1.0, vicino))
        fuori.append((pts[i][0] + nx * largo, pts[i][1] + ny * largo))
    return fuori


def _smooth(pts, passes: int = 2):
    """Media mobile chiusa: toglie gli spigoli introdotti dalla chiusura."""
    for _ in range(passes):
        n = len(pts)
        out = []
        for i in range(n):
            a = pts[(i - 1) % n]
            b = pts[i]
            c = pts[(i + 1) % n]
            out.append(((a[0] + 2 * b[0] + c[0]) / 4.0, (a[1] + 2 * b[1] + c[1]) / 4.0))
        pts = out
    return pts
