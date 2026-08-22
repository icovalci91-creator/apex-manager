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
    calibration: float = 1.0
    geo: list = field(default_factory=list)   # [[lat, lon], ...] del tracciato reale

    segments: list = field(default_factory=list)
    points: list = field(default_factory=list)      # [(x, y)] normalizzati 0..1
    curvature: list = field(default_factory=list)   # 1/raggio per ogni punto
    ds: float = STEP_M
    sector_bounds: tuple = (0.0, 0.0)

    # ---------------------------------------------------------------- build
    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        t = cls(
            id=d["id"], name=d["name"], gp=d["gp"], country=d["country"], flag=d["flag"],
            length_km=d["length_km"], laps=d["laps"], corners=d["corners"],
            pit_loss=d["pit_loss"], sprint=d.get("sprint", False),
            traits=d["traits"], layout=d["layout"], ref_lap=d.get("ref_lap", 90.0), month=int(d.get("month", 3)),
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

        self.ds = target / len(pts)
        self.curvature = _curvature(pts)
        self.points = _normalise(pts)
        self.sector_bounds = (len(pts) / 3.0, 2.0 * len(pts) / 3.0)

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
    def lap_model(self, car, wet: float = 0.0, grip: float = 1.0):
        """Restituisce (tempo_giro_s, vmax_kmh, profilo_velocita).

        `car` espone: downforce, drag, power, mech_grip, braking, mass_base,
        mass_extra.
        """
        cla = C.CLA_BASE * car.downforce
        cda = C.CDA_BASE * car.drag
        mass = car.mass_base + car.mass_extra
        power = C.POWER_W * car.power
        mu = C.MU_LAT * car.mech_grip * grip * (1.0 - 0.30 * wet)
        mu_b = C.MU_BRAKE * car.braking * grip * (1.0 - 0.28 * wet)

        n = len(self.curvature)
        ds = self.ds

        # velocita' massima assoluta (potenza contro resistenza)
        vmax = (2.0 * power / (C.RHO * cda)) ** (1.0 / 3.0)

        def lat_limit(k: float) -> float:
            if k <= 1e-9:
                return vmax
            denom = k - (C.RHO * cla) / (2.0 * mass)
            if denom <= 1e-6:
                return vmax
            v = math.sqrt(mu * C.G / denom)
            return min(v, vmax)

        vlim = [lat_limit(k) for k in self.curvature]

        v = list(vlim)
        for _ in range(2):  # due giri per far propagare la chiusura dell'anello
            # passata in avanti: limite di trazione/potenza
            for i in range(n):
                j = (i + 1) % n
                vi = max(v[i], 5.0)
                drag_a = 0.5 * C.RHO * cda * vi * vi / mass
                a = min(power / (mass * vi), mu * C.G * 0.85) - drag_a
                a = max(a, -8.0)
                cand = math.sqrt(max(1.0, vi * vi + 2.0 * a * ds))
                if cand < v[j]:
                    v[j] = cand
            # passata all'indietro: limite di frenata
            for i in range(n - 1, -1, -1):
                j = (i + 1) % n
                vj = max(v[j], 5.0)
                a_b = mu_b * C.G + 0.5 * C.RHO * cla * vj * vj / mass
                cand = math.sqrt(max(1.0, vj * vj + 2.0 * a_b * ds))
                if cand < v[i]:
                    v[i] = cand

        t = 0.0
        for i in range(n):
            j = (i + 1) % n
            vm = max(3.0, 0.5 * (v[i] + v[j]))
            t += ds / vm
        return t * self.calibration, vmax * 3.6, v

    def calibrate(self, ref_car) -> None:
        """Allinea il modello al tempo sul giro di riferimento della pista reale."""
        self.calibration = 1.0
        ref_car.setup = ref_car.optimal_setup(self)
        ref_car.evaluate_setup(self)
        ref_car.fuel_kg = 0.0
        raw, _, _ = self.lap_model(ref_car)
        if raw > 1.0:
            self.calibration = self.ref_lap / raw

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
