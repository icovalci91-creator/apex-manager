"""Il circuito in tre dimensioni: la geometria, senza disegnarla.

Qui si costruisce quello che sta fermo - il nastro d'asfalto, i cordoli, le
vie di fuga, il terreno che ci sta attorno, le tribune, i box, gli alberi o i
palazzi - come un elenco di triangoli colorati. Non si tocca OpenGL: chi
disegna e' `vista3d`, che questo elenco lo carica una volta sulla scheda video
e poi lo fa solo girare. Tenerli separati vuol dire poter costruire e
controllare la geometria anche su una macchina senza scheda video.

Il mondo ha la x verso est, la y verso l'alto e la z verso sud, in metri veri:
e' il piano della carta del tracciato (`track._metri`, con il nord a y
positiva) coricato in terra, con l'altezza presa dal profilo altimetrico vero
del circuito.

Tutto e' a facce piatte, un colore per triangolo, niente texture: e' lo stile
"plastico da tavolo" che si legge bene da lontano e costa poco, e non ha
bisogno di immagini da scaricare.
"""
from __future__ import annotations

import math
import random
from array import array

# Quanto si esagera il dislivello. In scala vera i cento metri di Spa su due
# chilometri si vedono appena da un elicottero: una volta e mezza li rende
# leggibili senza trasformare le Ardenne nelle Dolomiti.
ESAGERA_Z = 1.5
MEZZA_PISTA = 7.5          # metri: un nastro da quindici
CORDOLO = 1.6
RAGGIO_CURVA = 130.0       # sotto questo raggio un pezzo di pista e' una curva

# L'ambiente attorno al tracciato. Non e' nei dati del circuito perche' e'
# una scelta di messa in scena, non una misura: si decide qui, e un circuito
# nuovo senza voce prende il parco.
BIOMI = {
    "melbourne": "parco", "shanghai": "parco", "suzuka": "bosco",
    "bahrain": "deserto", "jeddah": "citta", "miami": "citta",
    "montreal": "parco", "monaco": "citta", "barcelona": "parco",
    "redbullring": "bosco", "silverstone": "parco", "spa": "bosco",
    "hungaroring": "parco", "zandvoort": "dune", "monza": "bosco",
    "madrid": "citta", "baku": "citta", "singapore": "citta",
    "cota": "parco", "mexico": "citta", "interlagos": "citta",
    "lasvegas": "citta", "lusail": "deserto", "yasmarina": "deserto",
}

# colori in 0..1, gia' pensati per la luce del sole che li scalda
PALETTE = {
    "parco":   dict(terra=(0.30, 0.46, 0.22), terra2=(0.36, 0.50, 0.24),
                    fuga=14.0, colline=7.0, alberi=900),
    "bosco":   dict(terra=(0.24, 0.40, 0.19), terra2=(0.30, 0.44, 0.20),
                    fuga=14.0, colline=22.0, alberi=2600),
    "deserto": dict(terra=(0.76, 0.63, 0.44), terra2=(0.82, 0.70, 0.50),
                    fuga=16.0, colline=6.0, alberi=140),
    "dune":    dict(terra=(0.72, 0.64, 0.46), terra2=(0.44, 0.52, 0.28),
                    fuga=10.0, colline=16.0, alberi=250),
    "citta":   dict(terra=(0.40, 0.41, 0.42), terra2=(0.46, 0.46, 0.46),
                    fuga=2.5, colline=0.0, alberi=180),
}

ASFALTO = (0.19, 0.20, 0.22)
ASFALTO_BAGNATO = (0.11, 0.12, 0.14)
FUGA_ASFALTO = (0.33, 0.35, 0.39)
GHIAIA = (0.62, 0.55, 0.42)
ROSSO = (0.74, 0.12, 0.12)
BIANCO = (0.90, 0.90, 0.92)
TRONCO = (0.30, 0.22, 0.14)


def bioma(track) -> str:
    return BIOMI.get(getattr(track, "id", ""), "parco")


def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


class _Rumore:
    """Rumore a reticolo, liscio: le colline e le macchie di bosco."""

    def __init__(self, seme: int):
        self.seme = seme

    def _h(self, i: int, j: int) -> float:
        n = (i * 374761393 + j * 668265263 + self.seme * 1442695041) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (n & 0xFFFF) / 65535.0

    def __call__(self, x: float, y: float) -> float:
        i, j = math.floor(x), math.floor(y)
        fx, fy = _smooth(x - i), _smooth(y - j)
        a, b = self._h(i, j), self._h(i + 1, j)
        c, d = self._h(i, j + 1), self._h(i + 1, j + 1)
        return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy

    def ottave(self, x: float, y: float) -> float:
        return 0.65 * self(x, y) + 0.35 * self(x * 2.3 + 17.0, y * 2.3 - 9.0)


class Geometria:
    """Tutto quello che non si muove, pronto per la scheda video.

    `vert` e' un array di float, dieci per vertice: posizione, normale,
    colore e "bagliore" - quanto quel punto e' illuminato dai fari di un
    circuito notturno, o dalle finestre di un palazzo.
    """

    def __init__(self, track, bagnato: float = 0.0):
        self.track = track
        self.bioma = bioma(track)
        self.pal = PALETTE[self.bioma]
        self.notte = bool(getattr(track, "night", False))
        self.vert = array("f")
        self.rng = random.Random(sum(ord(c) * (k + 1) for k, c in enumerate(track.id)))
        self.rumore = _Rumore(len(track.id) * 7919 + 3)
        self._punti(track)
        self._indice()
        self.fuga = self.pal["fuga"]
        self._terreno()
        self._corsia_box()
        self._pista(bagnato)
        self._box()
        self._tribune()
        self._arredo()
        self._fari()
        self._portale()

    # ------------------------------------------------------------ il nastro
    def _punti(self, track) -> None:
        pts = track._metri
        n = len(pts)
        q = list(getattr(track, "quota", []) or [])
        giro = max(1.0, track.length_km * 1000.0)
        zmin = min(q) if q else 0.0

        def z(i):
            if not q:
                return 0.0
            x = (i * track.ds % giro) / giro * len(q)
            k = int(x)
            a = x - k
            return (q[k % len(q)] * (1 - a) + q[(k + 1) % len(q)] * a - zmin) * ESAGERA_Z

        self.n = n
        self.P = [(pts[i][0], z(i), -pts[i][1]) for i in range(n)]
        # la direzione di marcia e la destra, punto per punto
        self.F, self.R = [], []
        for i in range(n):
            a, b = self.P[(i - 2) % n], self.P[(i + 2) % n]
            f = _norm((b[0] - a[0], b[1] - a[1], b[2] - a[2]))
            fh = _norm((f[0], 0.0, f[2]))
            self.F.append(f)
            self.R.append((-fh[2], 0.0, fh[0]))
        # la curvatura con il segno: positiva quando si gira a destra
        self.K = []
        for i in range(n):
            a, b = self.F[(i - 3) % n], self.F[(i + 3) % n]
            cr = a[2] * b[0] - a[0] * b[2]
            self.K.append(cr / (6 * track.ds))
        liscia = [sum(self.K[(i + k) % n] for k in range(-4, 5)) / 9.0 for i in range(n)]
        self.K = liscia
        xs = [p[0] for p in self.P]
        zs = [p[2] for p in self.P]
        self.cx = (min(xs) + max(xs)) / 2
        self.cz = (min(zs) + max(zs)) / 2
        self.span = max(max(xs) - min(xs), max(zs) - min(zs))
        self.cy = sum(p[1] for p in self.P) / n

    def _indice(self) -> None:
        """Una griglia di caselle da 50 metri: chi sta vicino alla pista."""
        self.cella = 50.0
        self.celle: dict = {}
        for i in range(0, self.n, 2):
            x, _, z = self.P[i]
            k = (int(x // self.cella), int(z // self.cella))
            self.celle.setdefault(k, []).append(i)
        passo = max(1, self.n // 64)
        self.campioni = [self.P[i] for i in range(0, self.n, passo)]

    def vicino(self, x: float, z: float, r: float = 90.0) -> tuple:
        """(distanza dal nastro, quota piu' bassa della pista li' vicino)."""
        c = self.cella
        kx, kz = int(x // c), int(z // c)
        giri = int(r // c) + 1
        best = r * r
        zb = None
        for dx in range(-giri, giri + 1):
            for dz in range(-giri, giri + 1):
                for i in self.celle.get((kx + dx, kz + dz), ()):
                    p = self.P[i]
                    d = (p[0] - x) ** 2 + (p[2] - z) ** 2
                    if d < best:
                        best = d
                    if d < r * r and (zb is None or p[1] < zb):
                        zb = p[1]
        return math.sqrt(best), zb

    # --------------------------------------------------------- le primitive
    def tri(self, a, b, c, col, glow: float = 0.0, nor=None) -> None:
        if nor is None:
            nor = _norm(_cross((b[0] - a[0], b[1] - a[1], b[2] - a[2]),
                               (c[0] - a[0], c[1] - a[1], c[2] - a[2])))
            if nor[1] < 0:
                nor = (-nor[0], -nor[1], -nor[2])
        v = self.vert
        g = glow if isinstance(glow, tuple) else (glow, glow, glow)
        for p, gl in zip((a, b, c), g):
            v.extend((p[0], p[1], p[2], nor[0], nor[1], nor[2], col[0], col[1], col[2], gl))

    def quad(self, a, b, c, d, col, glow=0.0, nor=None) -> None:
        if isinstance(glow, tuple):
            self.tri(a, b, c, col, (glow[0], glow[1], glow[2]), nor)
            self.tri(a, c, d, col, (glow[0], glow[2], glow[3]), nor)
            return
        self.tri(a, b, c, col, glow, nor)
        self.tri(a, c, d, col, glow, nor)

    def scatola(self, x, y, z, lungo, largo, alto, ang, col, glow_lati=0.0, tetto=None):
        """Un parallelepipedo girato di `ang` attorno all'asse verticale."""
        ca, sa = math.cos(ang), math.sin(ang)
        ang4 = [(-lungo / 2, -largo / 2), (lungo / 2, -largo / 2),
                (lungo / 2, largo / 2), (-lungo / 2, largo / 2)]
        base = [(x + ca * u - sa * w, z + sa * u + ca * w) for u, w in ang4]
        b = [(p[0], y, p[1]) for p in base]
        t = [(p[0], y + alto, p[1]) for p in base]
        self.quad(t[0], t[1], t[2], t[3], tetto or _mix(col, (0, 0, 0), 0.15), 0.0, (0, 1, 0))
        for k in range(4):
            j = (k + 1) % 4
            ex, ez = base[j][0] - base[k][0], base[j][1] - base[k][1]
            nor = _norm((ez, 0.0, -ex))
            # la normale deve guardare fuori dalla scatola
            mx, mz = (base[j][0] + base[k][0]) / 2 - x, (base[j][1] + base[k][1]) / 2 - z
            if nor[0] * mx + nor[2] * mz < 0:
                nor = (-nor[0], 0.0, -nor[2])
            self.quad(b[k], b[j], t[j], t[k], col, glow_lati, nor)

    # --------------------------------------------------------------- terreno
    def altezza_base(self, x: float, z: float) -> tuple:
        num = den = 0.0
        dmin = 1e18
        for px, py, pz in self.campioni:
            d2 = (px - x) ** 2 + (pz - z) ** 2
            dmin = min(dmin, d2)
            w = 1.0 / (d2 + 300.0 ** 2)
            num += w * py
            den += w
        return num / den, math.sqrt(dmin)

    def altezza(self, x: float, z: float) -> float:
        base, lontano = self.altezza_base(x, z)
        amp = self.pal["colline"]
        colline = (self.rumore.ottave(x / 420.0, z / 420.0) - 0.45) * 2.0 * amp
        base += colline * _smooth((lontano - 120.0) / 600.0)
        d, zn = self.vicino(x, z, 110.0)
        if zn is None:
            return base
        bordo = MEZZA_PISTA + self.fuga + 5.0
        tetto = zn - 0.35
        if d <= bordo:
            return tetto
        t = _smooth((d - bordo) / 120.0)
        return tetto * (1 - t) + base * t

    def _terreno(self) -> None:
        ext = self.span * 0.5 + max(500.0, self.span * 0.45)
        G = 140
        self.t_ext, self.t_G = ext, G
        passo = ext * 2 / G
        self.t_passo = passo
        x0, z0 = self.cx - ext, self.cz - ext
        H = []
        D = []
        for gx in range(G + 1):
            riga, rd = [], []
            for gz in range(G + 1):
                x, z = x0 + gx * passo, z0 + gz * passo
                h = self.altezza(x, z)
                d, _ = self.vicino(x, z, 110.0)
                # verso il bordo della griglia il terreno scende piano al
                # livello della pianura, che corre fino all'orizzonte
                bordo = min(gx, gz, G - gx, G - gz) / (G * 0.12)
                h = h * _smooth(bordo) + (-4.0) * (1 - _smooth(bordo))
                riga.append(h)
                rd.append(d)
            H.append(riga)
            D.append(rd)
        self.t_H = H
        pal = self.pal
        glow_on = self.notte
        for gx in range(G):
            for gz in range(G):
                xa, za = x0 + gx * passo, z0 + gz * passo
                a = (xa, H[gx][gz], za)
                b = (xa + passo, H[gx + 1][gz], za)
                c = (xa + passo, H[gx + 1][gz + 1], za + passo)
                d = (xa, H[gx][gz + 1], za + passo)
                macchia = self.rumore(xa / 180.0, za / 180.0)
                col = _mix(pal["terra"], pal["terra2"], macchia)
                if glow_on:
                    luce = lambda dd: (1.0 - _smooth((dd - 15.0) / 110.0)) * 0.7  # noqa: E731
                    glow = (luce(D[gx][gz]), luce(D[gx + 1][gz]),
                            luce(D[gx + 1][gz + 1]), luce(D[gx][gz + 1]))
                else:
                    glow = 0.0
                self.quad(a, b, c, d, col, glow)
        # la pianura, fino a dove la nebbia la mangia
        L = self.span * 60
        y = -4.0
        self.quad((self.cx - L, y, self.cz - L), (self.cx + L, y, self.cz - L),
                  (self.cx + L, y, self.cz + L), (self.cx - L, y, self.cz + L),
                  pal["terra"], 0.0, (0, 1, 0))

    def terra(self, x: float, z: float) -> float:
        """L'altezza del terreno costruito, per chi deve appoggiarci qualcosa."""
        gx = (x - (self.cx - self.t_ext)) / self.t_passo
        gz = (z - (self.cz - self.t_ext)) / self.t_passo
        G = self.t_G
        if not (0 <= gx < G and 0 <= gz < G):
            return -4.0
        i, j = int(gx), int(gz)
        fx, fz = gx - i, gz - j
        H = self.t_H
        a = H[i][j] + (H[i + 1][j] - H[i][j]) * fx
        b = H[i][j + 1] + (H[i + 1][j + 1] - H[i][j + 1]) * fx
        return a + (b - a) * fz

    # ----------------------------------------------------------------- pista
    def _fascia(self, da: float, a: float, alza: float, colore, glow: float = 0.0) -> None:
        """Una striscia parallela al nastro, da `da` ad `a` metri dal centro.

        `colore` e' un colore fisso o una funzione dell'indice del punto che
        restituisce un colore, o None dove la striscia non c'e'.
        """
        P, R, n = self.P, self.R, self.n
        for i in range(n):
            j = (i + 1) % n
            col = colore(i) if callable(colore) else colore
            if col is None:
                continue
            pi, pj, ri, rj = P[i], P[j], R[i], R[j]
            q = [(pi[0] + ri[0] * da, pi[1] + alza, pi[2] + ri[2] * da),
                 (pj[0] + rj[0] * da, pj[1] + alza, pj[2] + rj[2] * da),
                 (pj[0] + rj[0] * a, pj[1] + alza, pj[2] + rj[2] * a),
                 (pi[0] + ri[0] * a, pi[1] + alza, pi[2] + ri[2] * a)]
            self.quad(q[0], q[1], q[2], q[3], col, glow)

    def _muro(self, off: float, alto: float, colore, glow: float = 0.0) -> None:
        P, R, n = self.P, self.R, self.n
        for i in range(n):
            j = (i + 1) % n
            col = colore(i) if callable(colore) else colore
            if col is None:
                continue
            pi, pj, ri, rj = P[i], P[j], R[i], R[j]
            a = (pi[0] + ri[0] * off, pi[1], pi[2] + ri[2] * off)
            b = (pj[0] + rj[0] * off, pj[1], pj[2] + rj[2] * off)
            nor = (-ri[0] if off > 0 else ri[0], 0.0, -ri[2] if off > 0 else ri[2])
            self.quad(a, b, (b[0], b[1] + alto, b[2]), (a[0], a[1] + alto, a[2]), col, glow, nor)

    def _pista(self, bagnato: float) -> None:
        g = 1.0 if self.notte else 0.0
        K = self.K
        curva = 1.0 / RAGGIO_CURVA
        asf = _mix(ASFALTO, ASFALTO_BAGNATO, max(0.0, min(1.0, bagnato)))
        m = MEZZA_PISTA
        f = self.fuga
        # la via di fuga: ghiaia fuori dalle curve, asfalto altrove
        def fuga_fuori(lato):
            def c(i):
                if lato * K[i] < -curva * 0.8:
                    return GHIAIA
                return FUGA_ASFALTO
            return c
        self._fascia(m + CORDOLO, m + CORDOLO + f, 0.04, fuga_fuori(1), g)
        self._fascia(-m - CORDOLO - f, -m - CORDOLO, 0.04, fuga_fuori(-1), g)
        self._fascia(-m, m, 0.10, asf, g)
        # i cordoli, bianchi e rossi a tratti, solo dove si gira davvero
        def cordolo(i):
            if abs(K[i]) < curva:
                return None
            return ROSSO if (i // 2) % 2 else BIANCO
        def striscia(i):
            return None if abs(K[i]) >= curva else BIANCO
        self._fascia(m, m + CORDOLO, 0.14, cordolo, g)
        self._fascia(-m - CORDOLO, -m, 0.14, cordolo, g)
        self._fascia(m - 0.5, m, 0.15, striscia, g)
        self._fascia(-m, -m + 0.5, 0.15, striscia, g)
        # il traguardo, a scacchi, e le caselle della griglia dietro
        self._fascia(-m, m, 0.18, lambda i: BIANCO if i in (0,) else None, g)
        for k in range(20):
            i = (-(3 + k * 2)) % self.n     # una casella ogni otto metri circa
            lato = -1 if k % 2 == 0 else 1
            p, r, fw = self.P[i], self.R[i], self.F[i]
            cx, cz = p[0] + r[0] * lato * 3.2, p[2] + r[2] * lato * 3.2
            y = p[1] + 0.18
            a = (cx - r[0] * 1.2, y, cz - r[2] * 1.2)
            b = (cx + r[0] * 1.2, y, cz + r[2] * 1.2)
            self.quad(a, b, (b[0] + fw[0] * 0.5, y, b[2] + fw[2] * 0.5),
                      (a[0] + fw[0] * 0.5, y, a[2] + fw[2] * 0.5), BIANCO, g, (0, 1, 0))
        # le barriere al limite della via di fuga: muri in citta', guard-rail
        # e gomme altrove
        citta = self.bioma == "citta"
        def barriera(i):
            if citta:
                return BIANCO if (i // 6) % 2 else (0.20, 0.34, 0.62)
            return (0.58, 0.60, 0.64)
        alto = 1.3 if citta else 1.0
        self._muro(m + CORDOLO + f, alto, barriera, g * 0.7)
        self._muro(-(m + CORDOLO + f), alto, barriera, g * 0.7)

    # ------------------------------------------------------------------- box
    def _corsia_box(self) -> None:
        """La corsia dei box, riportata dal disegno 2D ai metri del mondo."""
        box = getattr(self.track, "pit_points", None) or []
        pts = self.track._metri
        self.box_P = []
        if len(box) < 4:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs) or 1.0
        h = max(ys) - min(ys) or 1.0
        scala = 1.0 / max(w, h)
        ox, oy = min(xs), min(ys)
        cx = (1.0 - w * scala) / 2.0
        cy = (1.0 - h * scala) / 2.0
        for px, py in box:
            x = (px - cx) / scala + ox
            y = ((1.0 - py) - cy) / scala + oy
            _, zb = self.vicino(x, -y, 120.0)
            self.box_P.append((x, (zb if zb is not None else 0.0), -y))

    def _box(self) -> None:
        B = self.box_P
        if len(B) < 4:
            return
        g = 1.0 if self.notte else 0.0
        largo = 6.0
        lati = []
        for k in range(len(B) - 1):
            a, b = B[k], B[k + 1]
            f = _norm((b[0] - a[0], 0.0, b[2] - a[2]))
            lati.append((-f[2], 0.0, f[0]))
        lati.append(lati[-1])
        # da che parte sta la pista: i garage vanno dall'altra
        mid = B[len(B) // 2]
        d, _ = self.vicino(mid[0] + lati[len(B) // 2][0] * 20, mid[2] + lati[len(B) // 2][2] * 20)
        d2, _ = self.vicino(mid[0] - lati[len(B) // 2][0] * 20, mid[2] - lati[len(B) // 2][2] * 20)
        verso = 1.0 if d > d2 else -1.0
        for k in range(len(B) - 1):
            a, b = B[k], B[k + 1]
            ra, rb = lati[k], lati[k + 1]
            y = max(a[1], b[1]) + 0.12
            q = [(a[0] - ra[0] * largo, y, a[2] - ra[2] * largo),
                 (b[0] - rb[0] * largo, y, b[2] - rb[2] * largo),
                 (b[0] + rb[0] * largo, y, b[2] + rb[2] * largo),
                 (a[0] + ra[0] * largo, y, a[2] + ra[2] * largo)]
            self.quad(q[0], q[1], q[2], q[3], (0.24, 0.25, 0.28), g, (0, 1, 0))
        # l'edificio dei box: una fila di garage lungo il tratto centrale
        n = len(B)
        for k in range(int(n * 0.25), int(n * 0.75), 3):
            a, b = B[k], B[min(n - 1, k + 3)]
            ang = math.atan2(b[2] - a[2], b[0] - a[0])
            r = lati[k]
            x = (a[0] + b[0]) / 2 + r[0] * verso * (largo + 9)
            z = (a[2] + b[2]) / 2 + r[2] * verso * (largo + 9)
            lungo = math.hypot(b[0] - a[0], b[2] - a[2]) + 0.4
            self.scatola(x, a[1], z, lungo, 16, 11, ang, (0.78, 0.79, 0.82),
                         0.6 if self.notte else 0.0, (0.30, 0.32, 0.36))

    # --------------------------------------------------------------- tribune
    def _tribuna(self, i: int, lato: float, lungo: float, colore) -> None:
        p, r, fw = self.P[i], self.R[i], self.F[i]
        dist = MEZZA_PISTA + CORDOLO + self.fuga + 6
        x0, z0 = p[0] + r[0] * lato * dist, p[2] + r[2] * lato * dist
        y = self.terra(x0, z0) - 0.3
        prof = 18.0
        basso, alto = 1.5, 13.0
        fx, fz = fw[0], fw[2]
        rx, rz = r[0] * lato, r[2] * lato
        def pt(u, v, h):
            return (x0 + fx * u + rx * v, y + h, z0 + fz * u + rz * v)
        L = lungo / 2
        a, b = pt(-L, 0, basso), pt(L, 0, basso)
        c, d = pt(L, prof, alto), pt(-L, prof, alto)
        g = 0.7 if self.notte else 0.0
        # i gradoni, a fasce di colore: da lontano sembrano la folla
        passi = 5
        for k in range(passi):
            t0, t1 = k / passi, (k + 1) / passi
            col = colore if k % 2 == 0 else _mix(colore, (1, 1, 1), 0.25)
            self.quad(_mix(a, d, t0), _mix(b, c, t0), _mix(b, c, t1), _mix(a, d, t1), col, g)
        grigio = (0.55, 0.56, 0.60)
        self.quad(pt(-L, 0, 0), pt(L, 0, 0), b, a, grigio, g, (-rx, 0, -rz))
        self.quad(pt(-L, prof, 0), pt(L, prof, 0), c, d, grigio, 0.0, (rx, 0, rz))
        self.quad(pt(-L, 0, 0), a, d, pt(-L, prof, 0), grigio, 0.0, (-fx, 0, -fz))
        self.quad(pt(L, 0, 0), b, c, pt(L, prof, 0), grigio, 0.0, (fx, 0, fz))
        # la tettoia
        self.quad(pt(-L, prof * 0.2, alto + 5), pt(L, prof * 0.2, alto + 5),
                  pt(L, prof + 1, alto + 4), pt(-L, prof + 1, alto + 4), (0.85, 0.86, 0.88), g)

    def _tribune(self) -> None:
        colori = [(0.20, 0.32, 0.62), (0.70, 0.16, 0.16), (0.86, 0.72, 0.18), (0.18, 0.52, 0.40)]
        # la tribuna principale, di fronte ai box
        verso = -1.0
        if self.box_P:
            mid = self.box_P[len(self.box_P) // 2]
            p, r = self.P[0], self.R[0]
            verso = -1.0 if (mid[0] - p[0]) * r[0] + (mid[2] - p[2]) * r[2] > 0 else 1.0
        for k, i in enumerate(range(-40, 50, 18)):
            self._tribuna(i % self.n, verso, 80.0, colori[k % len(colori)])
        # e qualcuna nelle curve lente, dal lato di fuori
        fatte = []
        for i in range(0, self.n, 3):
            if abs(self.K[i]) > 1.0 / 60.0 and all(abs(i - j) > 120 for j in fatte):
                fatte.append(i)
                lato = -1.0 if self.K[i] > 0 else 1.0
                self._tribuna(i, lato, 70.0, colori[len(fatte) % len(colori)])
            if len(fatte) >= 7:
                break

    # ----------------------------------------------------------------- arredo
    def _libero(self, x: float, z: float, margine: float) -> bool:
        d, _ = self.vicino(x, z, margine + 5)
        if d < margine:
            return False
        for b in self.box_P[::4]:
            if (b[0] - x) ** 2 + (b[2] - z) ** 2 < (margine + 20) ** 2:
                return False
        return True

    def _albero(self, x: float, z: float, alto: float, col) -> None:
        y = self.terra(x, z)
        tr = alto * 0.25
        r = alto * 0.32
        self.scatola(x, y, z, r * 0.3, r * 0.3, tr, 0.0, TRONCO)
        lati = 6
        cima = (x, y + alto, z)
        ang0 = self.rng.random()
        base = [(x + math.cos(ang0 + k * 2 * math.pi / lati) * r, y + tr,
                 z + math.sin(ang0 + k * 2 * math.pi / lati) * r) for k in range(lati)]
        for k in range(lati):
            a, b = base[k], base[(k + 1) % lati]
            nor = _norm(_cross((b[0] - a[0], b[1] - a[1], b[2] - a[2]),
                               (cima[0] - a[0], cima[1] - a[1], cima[2] - a[2])))
            if nor[0] * (a[0] - x) + nor[2] * (a[2] - z) < 0:
                nor = (-nor[0], -nor[1], -nor[2])
            ombra = 0.85 + 0.15 * ((k % 3) / 2.0)
            self.tri(a, b, cima, tuple(c * ombra for c in col), 0.0, nor)

    def _palma(self, x: float, z: float) -> None:
        y = self.terra(x, z)
        alto = 9 + self.rng.random() * 5
        self.scatola(x, y, z, 0.7, 0.7, alto, self.rng.random(), (0.45, 0.34, 0.22))
        cima = (x, y + alto, z)
        verde = (0.24, 0.42, 0.18)
        for k in range(6):
            a = k * math.pi / 3 + self.rng.random() * 0.4
            ex, ez = x + math.cos(a) * 5.0, z + math.sin(a) * 5.0
            px, pz = -math.sin(a) * 1.0, math.cos(a) * 1.0
            fine = (ex, y + alto - 2.5, ez)
            self.tri((cima[0] + px, cima[1], cima[2] + pz), (cima[0] - px, cima[1], cima[2] - pz),
                     fine, verde, 0.0, (0, 1, 0))

    def _palazzo(self, x: float, z: float, lato: float, alto: float, ang: float) -> None:
        y = self.terra(x, z) - 0.5
        tinte = [(0.72, 0.70, 0.66), (0.60, 0.64, 0.70), (0.78, 0.74, 0.64),
                 (0.52, 0.56, 0.62), (0.84, 0.82, 0.78)]
        col = self.rng.choice(tinte)
        acceso = (0.25 + self.rng.random() * 0.5) if self.notte else 0.0
        self.scatola(x, y, z, lato, lato * (0.7 + self.rng.random() * 0.6), alto, ang, col, acceso)

    def _arredo(self) -> None:
        rng = self.rng
        span = self.span
        est = span * 0.5 + 420
        if self.bioma == "citta":
            passo = 70.0
            k0 = int(est / passo)
            for ix in range(-k0, k0 + 1):
                for iz in range(-k0, k0 + 1):
                    x = self.cx + ix * passo + rng.uniform(-8, 8)
                    z = self.cz + iz * passo + rng.uniform(-8, 8)
                    lato = rng.uniform(28, 46)
                    if rng.random() < 0.12 or not self._libero(x, z, lato * 0.75 + MEZZA_PISTA + 8):
                        continue
                    centro = math.hypot(x - self.cx, z - self.cz) / (span * 0.7)
                    alto = 12 + rng.random() ** 2 * 90 * max(0.25, 1.2 - centro)
                    self._palazzo(x, z, lato, alto, rng.uniform(-0.05, 0.05))
        quanti = self.pal["alberi"]
        fatti = 0
        tentativi = 0
        while fatti < quanti and tentativi < quanti * 8:
            tentativi += 1
            x = self.cx + rng.uniform(-est, est)
            z = self.cz + rng.uniform(-est, est)
            if self.bioma in ("bosco", "dune") and self.rumore(x / 260.0 + 40, z / 260.0) < 0.45:
                continue
            if not self._libero(x, z, MEZZA_PISTA + self.fuga + 14):
                continue
            fatti += 1
            if self.bioma == "deserto":
                self._palma(x, z)
                continue
            alto = rng.uniform(13, 24) if self.bioma != "dune" else rng.uniform(5, 9)
            if self.bioma == "bosco":
                col = _mix((0.10, 0.26, 0.12), (0.18, 0.36, 0.16), rng.random())
            else:
                col = _mix((0.16, 0.36, 0.14), (0.30, 0.46, 0.18), rng.random())
            self._albero(x, z, alto, col)

    def _fari(self) -> None:
        """Le torri dei fari lungo il giro, per le gare di notte."""
        if not self.notte:
            return
        passo = 24                         # circa centoventi metri
        for k, i in enumerate(range(0, self.n, passo)):
            lato = 1 if k % 2 else -1
            p, r = self.P[i], self.R[i]
            dist = MEZZA_PISTA + CORDOLO + self.fuga + 4
            x, z = p[0] + r[0] * lato * dist, p[2] + r[2] * lato * dist
            y = self.terra(x, z)
            self.scatola(x, y, z, 0.8, 0.8, 26.0, 0.0, (0.35, 0.36, 0.40))
            ang = math.atan2(r[2], r[0])
            self.scatola(x, y + 26.0, z, 2.0, 5.0, 2.2, ang, (1.0, 0.95, 0.80), 1.6,
                         (1.0, 0.95, 0.80))

    def _portale(self) -> None:
        """Il portale del via, sopra al traguardo."""
        p, r = self.P[0], self.R[0]
        g = 1.0 if self.notte else 0.0
        largo = MEZZA_PISTA + 3.0
        scuro = (0.14, 0.15, 0.18)
        for lato in (-1, 1):
            x, z = p[0] + r[0] * largo * lato, p[2] + r[2] * largo * lato
            self.scatola(x, p[1], z, 1.2, 1.2, 9.0, 0.0, scuro)
        ang = math.atan2(r[2], r[0])
        self.scatola(p[0], p[1] + 8.0, p[2], largo * 2 + 1.2, 1.4, 1.6, ang, scuro, g)

    # --------------------------------------------------------- lungo il giro
    def sul_giro(self, frazione: float, laterale: float = 0.0) -> tuple:
        """(posizione, direzione) a questa frazione del giro, in metri."""
        n = self.n
        f = (frazione % 1.0) * n
        i = int(f) % n
        j = (i + 1) % n
        t = f - int(f)
        a, b = self.P[i], self.P[j]
        r = self.R[i]
        pos = (a[0] + (b[0] - a[0]) * t + r[0] * laterale,
               a[1] + (b[1] - a[1]) * t,
               a[2] + (b[2] - a[2]) * t + r[2] * laterale)
        return pos, self.F[i]
