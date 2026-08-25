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

import math
from dataclasses import dataclass, field

from .. import config as C

STEP_M = 8.0  # risoluzione della discretizzazione (metri)

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

# Fin dove arriva l'uscita di curva: sopra questa frazione della velocita'
# massima non e' piu' trazione, e' un rettilineo.
V_USCITA = 0.62


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
    domain_map: list = field(default_factory=list)   # cosa e' ogni metro di pista
    corner_map: list = field(default_factory=list)   # le curve, una per una
    start: list = field(default_factory=list)   # [lat, lon] della linea del traguardo
    senso: str = ""              # "orario" | "antiorario": da che parte si gira
    settori: list = field(default_factory=list)  # dove tagliano i due intertempi
    altitude: float = 0.0        # metri sul livello del mare: l'aria che si respira
    night: bool = False          # si corre col buio: l'asfalto non prende sole
    climate: dict = field(default_factory=dict)   # temperatura, pioggia e vento del mese
    geo: list = field(default_factory=list)   # [[lat, lon], ...] del tracciato reale

    segments: list = field(default_factory=list)
    points: list = field(default_factory=list)      # [(x, y)] normalizzati 0..1
    curvature: list = field(default_factory=list)   # 1/raggio per ogni punto
    ds: float = STEP_M
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
        pts = _resample(pts, n)
        pts = _smooth(pts, passes=2)
        pts = self._al_traguardo(pts, k if raw_len > 1.0 else 1.0)

        self.ds = target / len(pts)
        self.curvature = _curvature(pts)
        self.points = _normalise(pts)
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
            tutti = _project(list(self.geo) + [list(self.start)])
            bx, by = tutti[-1][0] * scala, tutti[-1][1] * scala
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
        self.points = _normalise(pts)
        self.curvature = curv
        self.sector_bounds = (n / 3.0, 2.0 * n / 3.0)

    # ------------------------------------------------------- modello di giro
    def lap_model(self, car, wet: float = 0.0, grip: float = 1.0, rho: float | None = None,
                  bias: dict | None = None):
        """Restituisce (tempo_giro_s, vmax_kmh, profilo_velocita).

        `car` espone: downforce, drag, power, mech_grip, braking, mass_base,
        mass_extra. `rho` e' la densita' dell'aria: a Citta' del Messico ce n'e'
        un quarto di meno che sul mare, e una monoposto senza aria non ha
        carico - ne' resistenza. `bias` sono i moltiplicatori di aderenza per
        dominio: una macchina non e' brava allo stesso modo nelle curve lente e
        in quelle veloci.
        """
        t, vmax, v, _vlim, _cl = self._solve(car, wet, grip, rho, bias)
        return t, vmax, v

    def _solve(self, car, wet: float, grip: float, rho, bias: dict | None):
        """Il conto vero: profilo di velocita', limiti e classe di ogni punto."""
        rho = C.RHO if rho is None else rho
        b = bias or {}
        cla = C.CLA_BASE * car.downforce
        cda = C.CDA_BASE * car.drag
        mass = car.mass_base + car.mass_extra
        power = C.POWER_W * car.power
        mu = C.MU_LAT * car.mech_grip * grip * (1.0 - 0.30 * wet)
        mu_b = C.MU_BRAKE * car.braking * grip * (1.0 - 0.28 * wet) * b.get("frenata", 1.0)
        mu_t = mu * b.get("trazione", 1.0)

        n = len(self.curvature)
        ds = self.ds

        # velocita' massima assoluta (potenza contro resistenza)
        vmax = (2.0 * power / (rho * cda)) ** (1.0 / 3.0)
        aero = (rho * cla) / (2.0 * mass)

        def lat_limit(k: float):
            """Velocita' massima in curva e che tipo di curva e'.

            La classe si legge sulla velocita' che quella curva permette a una
            macchina di riferimento: sotto i centotrenta e' una curva lenta,
            sopra i duecento e' una curva veloce, e sono due mondi diversi -
            nella prima conta l'aderenza meccanica, nella seconda il carico.
            """
            if k <= 1e-9:
                return vmax, ""
            denom = k - aero
            if denom <= 1e-6:
                return vmax, ""
            v0 = math.sqrt(mu * C.G / denom)
            # una curva e' una curva se rallenta davvero: la curvatura residua
            # di un rettilineo non lo e', per quanto il rilievo la misuri
            if v0 >= vmax * SOGLIA_CURVA:
                return vmax, ""
            classe = ("lente" if v0 < V_LENTA else
                      "veloci" if v0 > V_VELOCE else "medie")
            v = math.sqrt(mu * b.get(classe, 1.0) * C.G / denom)
            return min(v, vmax), classe

        limiti = [lat_limit(k) for k in self.curvature]
        vlim = [x[0] for x in limiti]
        classi = [x[1] for x in limiti]

        v = list(vlim)
        for _ in range(2):  # due giri per far propagare la chiusura dell'anello
            # passata in avanti: limite di trazione/potenza
            for i in range(n):
                j = (i + 1) % n
                vi = max(v[i], 5.0)
                drag_a = 0.5 * rho * cda * vi * vi / mass
                # anche in accelerazione il carico aerodinamico spinge a terra:
                # a duecento all'ora la trazione non e' quella di un semaforo
                a = min(power / (mass * vi),
                        mu_t * (C.G + aero * vi * vi) * 0.85) - drag_a
                a = max(a, -8.0)
                cand = math.sqrt(max(1.0, vi * vi + 2.0 * a * ds))
                if cand < v[j]:
                    v[j] = cand
            # passata all'indietro: limite di frenata
            for i in range(n - 1, -1, -1):
                j = (i + 1) % n
                vj = max(v[j], 5.0)
                a_b = mu_b * C.G + 0.5 * rho * cla * vj * vj / mass
                cand = math.sqrt(max(1.0, vj * vj + 2.0 * a_b * ds))
                if cand < v[i]:
                    v[i] = cand

        t = 0.0
        for i in range(n):
            j = (i + 1) % n
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            t += ds / vm
        return t * self.calibration, vmax * 3.6, v, vlim, classi

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
        self._map_time(v, mappa)

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
        power = C.POWER_W * car.power
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
            "vmax": vmax_kmh,
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
        # e con l'ala giusta si segna, metro per metro, che cosa e' questo
        # circuito: dove si frena, dove si curva piano, dove si tira
        ref_car.setup = ref_car.optimal_setup(self, cond=cond)
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
            ref_car.setup["wing"] = float(w)
            t, _, _ = self.lap_model(ref_car, grip=grip, rho=cond.rho)
            return t

        best = min(range(0, 101, 10), key=giro)
        fine = min(range(max(0, best - 8), min(100, best + 8) + 1, 4), key=giro)
        ref_car.setup = saved
        return float(fine)

    def sector_of(self, idx: int) -> int:
        a, b = self.sector_bounds
        return 1 if idx < a else (2 if idx < b else 3)


# --------------------------------------------------------------- geometria
MIN_RADIUS = 12.0      # sotto questo raggio e' rumore di rilievo, non una curva


def _project(geo) -> list:
    """Da gradi a metri, piani, attorno al centro del circuito."""
    lats = [float(p[0]) for p in geo]
    lons = [float(p[1]) for p in geo]
    lat0 = sum(lats) / len(lats)
    lon0 = sum(lons) / len(lons)
    mx = 111320.0 * math.cos(math.radians(lat0))
    return [((lon - lon0) * mx, (lat - lat0) * 110540.0) for lat, lon in zip(lats, lons)]


def _path_length(pts) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


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


def _normalise(pts) -> list:
    """Porta la polilinea nel quadrato 0..1, centrata, senza deformarla."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    scale = 1.0 / max(w, h)
    ox, oy = min(xs), min(ys)
    cx = (1.0 - w * scale) / 2.0
    cy = (1.0 - h * scale) / 2.0
    return [((px - ox) * scale + cx, (py - oy) * scale + cy) for px, py in pts]


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
