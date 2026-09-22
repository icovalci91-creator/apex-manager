"""Il circuito in tre dimensioni: la geometria, senza disegnarla.

Qui si costruisce quello che sta fermo - il nastro d'asfalto, i cordoli, le
vie di fuga, il terreno, l'acqua, i palazzi, gli alberi, i parcheggi - come un
elenco di triangoli. Non si tocca OpenGL: chi disegna e' `vista3d`, che questo
elenco lo carica una volta sulla scheda video. Tenerli separati vuol dire poter
costruire e controllare la geometria anche su una macchina senza scheda video.

Lo stile e' quello di una foto da satellite ridisegnata a mano: la geometria
porta le forme grosse, e ogni triangolo dice di che *materiale* e' fatto - prato,
campi, citta', acqua, tetti, folla - cosi' che i dettagli fini (i solchi dei
campi, le siepi, le strisce del prato tagliato, le strade fra gli isolati) li
dipinga la scheda video pixel per pixel, a qualunque distanza.

Il mondo ha la x verso est, la y verso l'alto e la z verso sud, in metri veri:
e' il piano della carta del tracciato (`track._metri`, con il nord a y
positiva) coricato in terra, con l'altezza presa dal profilo altimetrico vero.
"""
from __future__ import annotations

import math
import random
from array import array

# Quanto si esagera il dislivello: una volta e mezza rende leggibili i cento
# metri di Spa senza trasformare le Ardenne nelle Dolomiti.
ESAGERA_Z = 1.5
MEZZA_PISTA = 7.5          # metri: un nastro da quindici
CORDOLO = 1.6
RAGGIO_CURVA = 130.0       # sotto questo raggio un pezzo di pista e' una curva
LIVELLO_ACQUA = -1.2
TERRA_MIN = -0.3           # sotto questa quota, fuori dall'acqua, non si scende
BLOCCO = 110.0             # il lato di un isolato in citta', strada compresa

# I materiali: stessi numeri nello shader di `vista3d`.
M_PIANO, M_TERRA, M_SABBIA, M_CITTA = 0, 1, 2, 3
M_ASFALTO, M_TETTO, M_CHIOMA, M_PARCHEGGIO, M_FOLLA = 5, 6, 7, 8, 9
M_GHIAIA, M_ACQUA, M_STRADA = 10, 11, 12

# L'ambiente attorno al tracciato: una scelta di messa in scena, non una
# misura. Un circuito nuovo senza voce prende la campagna.
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

# L'acqua che si vede davvero dall'alto: il lago dentro Albert Park e il
# bacino del canottaggio a Montreal, il mare dalla parte dove sta (in gradi
# dal nord, in senso orario). Solo dove si e' sicuri di che parte sia.
ACQUA = {
    "melbourne": ("lago",), "montreal": ("lago",),
    "monaco": ("mare", 140), "baku": ("mare", 165), "jeddah": ("mare", 270),
    "singapore": ("mare", 110), "zandvoort": ("mare", 285),
}

PALETTE = {
    "parco":   dict(terra=(0.33, 0.47, 0.22), fuga=14.0, colline=7.0, mat=M_TERRA),
    "bosco":   dict(terra=(0.28, 0.43, 0.20), fuga=14.0, colline=22.0, mat=M_TERRA),
    "deserto": dict(terra=(0.80, 0.67, 0.47), fuga=16.0, colline=5.0, mat=M_SABBIA),
    "dune":    dict(terra=(0.46, 0.53, 0.30), fuga=10.0, colline=14.0, mat=M_TERRA),
    "citta":   dict(terra=(0.56, 0.56, 0.54), fuga=3.0, colline=0.0, mat=M_CITTA),
}

ASFALTO = (0.21, 0.22, 0.24)
FUGA_ASFALTO = (0.36, 0.37, 0.40)
GHIAIA = (0.66, 0.59, 0.45)
ROSSO = (0.74, 0.12, 0.12)
BIANCO = (0.90, 0.90, 0.92)
# i colori delle motorhome nel paddock: uno per scuderia, piu' o meno
SQUADRE = [(0.80, 0.10, 0.12), (0.95, 0.50, 0.05), (0.05, 0.25, 0.55), (0.10, 0.65, 0.60),
           (0.05, 0.40, 0.25), (0.10, 0.35, 0.80), (0.92, 0.92, 0.94), (0.20, 0.30, 0.70),
           (0.85, 0.85, 0.87), (0.55, 0.60, 0.65), (0.15, 0.15, 0.18)]


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
    """Rumore a reticolo, liscio: colline, boschi, la costa."""

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

    `vert` e' un array di float, tredici per vertice: posizione, normale,
    colore, bagliore (quanto e' acceso di notte), materiale, un parametro
    del materiale (la distanza dalla pista per il terreno, la posizione
    trasversale per l'asfalto) e quanto bosco c'e' sotto, per il terreno.
    """

    def __init__(self, track):
        self.track = track
        self.bioma = bioma(track)
        self.pal = PALETTE[self.bioma]
        self.notte = bool(getattr(track, "night", False))
        self.vert = array("f")
        seme = sum(ord(c) * (k + 1) for k, c in enumerate(track.id))
        self.rng = random.Random(seme)
        self.rumore = _Rumore(seme % 9973 + 3)
        self.fuga = self.pal["fuga"]
        self._punti(track)
        self._indice()
        self._corsia_box()
        self._prepara_acqua()
        self._terreno()
        self._pista()
        self._box()
        self._tribune()
        self._strade()
        self._citta()
        self._alberi()
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
        self.F, self.R = [], []
        for i in range(n):
            a, b = self.P[(i - 2) % n], self.P[(i + 2) % n]
            f = _norm((b[0] - a[0], b[1] - a[1], b[2] - a[2]))
            fh = _norm((f[0], 0.0, f[2]))
            self.F.append(f)
            self.R.append((-fh[2], 0.0, fh[0]))
        # la curvatura con il segno: positiva quando si gira a destra
        K = []
        for i in range(n):
            a, b = self.F[(i - 3) % n], self.F[(i + 3) % n]
            K.append((a[2] * b[0] - a[0] * b[2]) / (6 * track.ds))
        self.K = [sum(K[(i + k) % n] for k in range(-4, 5)) / 9.0 for i in range(n)]
        xs = [p[0] for p in self.P]
        zs = [p[2] for p in self.P]
        self.cx = (min(xs) + max(xs)) / 2
        self.cz = (min(zs) + max(zs)) / 2
        self.span = max(max(xs) - min(xs), max(zs) - min(zs))
        self.cy = sum(p[1] for p in self.P) / n
        # quanto largo e' il mondo attorno: il terreno, il bosco, la citta'
        self.ext = self.span * 0.5 + max(550.0, self.span * 0.5)

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
    def tri(self, a, b, c, col, glow=0.0, nor=None, mat=M_PIANO, par=(0.0, 0.0, 0.0),
            aux=(0.0, 0.0, 0.0)) -> None:
        if nor is None:
            nor = _norm(_cross((b[0] - a[0], b[1] - a[1], b[2] - a[2]),
                               (c[0] - a[0], c[1] - a[1], c[2] - a[2])))
            if nor[1] < 0:
                nor = (-nor[0], -nor[1], -nor[2])
        nors = nor if isinstance(nor[0], tuple) else (nor, nor, nor)
        g = glow if isinstance(glow, tuple) else (glow, glow, glow)
        pr = par if isinstance(par, tuple) else (par, par, par)
        v = self.vert
        for p, nn, gl, pp, ax in zip((a, b, c), nors, g, pr, aux):
            v.extend((p[0], p[1], p[2], nn[0], nn[1], nn[2], col[0], col[1], col[2],
                      gl, mat, pp, ax))

    def quad(self, a, b, c, d, col, glow=0.0, nor=None, mat=M_PIANO, par=0.0) -> None:
        g = glow if isinstance(glow, tuple) else (glow,) * 4
        pr = par if isinstance(par, tuple) else (par,) * 4
        self.tri(a, b, c, col, (g[0], g[1], g[2]), nor, mat, (pr[0], pr[1], pr[2]))
        self.tri(a, c, d, col, (g[0], g[2], g[3]), nor, mat, (pr[0], pr[2], pr[3]))

    def scatola(self, x, y, z, lungo, largo, alto, ang, col, glow_lati=0.0, tetto=None,
                mat_tetto=M_TETTO) -> None:
        """Un parallelepipedo girato di `ang` attorno all'asse verticale."""
        ca, sa = math.cos(ang), math.sin(ang)
        ang4 = [(-lungo / 2, -largo / 2), (lungo / 2, -largo / 2),
                (lungo / 2, largo / 2), (-lungo / 2, largo / 2)]
        base = [(x + ca * u - sa * w, z + sa * u + ca * w) for u, w in ang4]
        b = [(p[0], y, p[1]) for p in base]
        t = [(p[0], y + alto, p[1]) for p in base]
        self.quad(t[0], t[1], t[2], t[3], tetto or col, 0.0, (0, 1, 0), mat_tetto)
        for k in range(4):
            j = (k + 1) % 4
            ex, ez = base[j][0] - base[k][0], base[j][1] - base[k][1]
            nor = _norm((ez, 0.0, -ex))
            mx, mz = (base[j][0] + base[k][0]) / 2 - x, (base[j][1] + base[k][1]) / 2 - z
            if nor[0] * mx + nor[2] * mz < 0:
                nor = (-nor[0], 0.0, -nor[2])
            self.quad(b[k], b[j], t[j], t[k], _mix(col, (0, 0, 0), 0.12), glow_lati, nor)

    # ---------------------------------------------------------------- acqua
    def _prepara_acqua(self) -> None:
        """Dove sta l'acqua: il lago dentro al giro o il mare da una parte."""
        self.acqua = ACQUA.get(self.track.id)
        self.lago_righe = None
        if not self.acqua:
            return
        if self.acqua[0] == "mare":
            b = math.radians(self.acqua[1])
            self.mare_dir = (math.sin(b), -math.cos(b))
            self.mare_c = max(p[0] * self.mare_dir[0] + p[2] * self.mare_dir[1] for p in self.P) + 45
            return
        # il lago: per ogni riga del terreno, i tratti che stanno dentro al giro
        self.lago_righe = {}

    def _dentro_giro(self, z: float) -> list:
        """I tratti di una riga orizzontale che stanno dentro al tracciato."""
        tagli = []
        P, n = self.P, self.n
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            if (a[2] <= z) != (b[2] <= z):
                t = (z - a[2]) / (b[2] - a[2])
                tagli.append(a[0] + (b[0] - a[0]) * t)
        tagli.sort()
        return [(tagli[k], tagli[k + 1]) for k in range(0, len(tagli) - 1, 2)]

    def bagnato(self, x: float, z: float, d: float) -> float:
        """0 asciutto .. 1 sott'acqua, con una riva che sfuma."""
        if not self.acqua:
            return 0.0
        if self.acqua[0] == "mare":
            s = x * self.mare_dir[0] + z * self.mare_dir[1] - self.mare_c
            s += (self.rumore(x / 260.0 + 7, z / 260.0) - 0.5) * 70
            return _smooth(s / 50.0)
        righe = self.lago_righe
        k = round(z, 1)
        tratti = righe.get(k)
        if tratti is None:
            tratti = righe[k] = self._dentro_giro(z)
        if not any(a <= x <= b for a, b in tratti):
            return 0.0
        return _smooth((d - 70.0) / 45.0)

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

    def _altezza(self, x: float, z: float) -> tuple:
        """(quota, distanza dalla pista, quanto e' acqua)."""
        base, lontano = self.altezza_base(x, z)
        amp = self.pal["colline"]
        colline = (self.rumore.ottave(x / 420.0, z / 420.0) - 0.45) * 2.0 * amp
        base += colline * _smooth((lontano - 120.0) / 600.0)
        d, zn = self.vicino(x, z, 130.0)
        if zn is None:
            h = base
            d = min(lontano, 5000.0)
        else:
            bordo = MEZZA_PISTA + CORDOLO + self.fuga + 4.0
            tetto = zn - 0.35
            if d <= bordo:
                h = tetto
            else:
                t = _smooth((d - bordo) / 120.0)
                h = tetto * (1 - t) + base * t
        h = max(h, TERRA_MIN)
        w = self.bagnato(x, z, d)
        if w > 0:
            h = h * (1 - w) + (LIVELLO_ACQUA - 2.0) * w
        return h, d, w

    def _terreno(self) -> None:
        ext = self.ext
        G = 150
        passo = ext * 2 / G
        self.t_ext, self.t_G, self.t_passo = ext, G, passo
        x0, z0 = self.cx - ext, self.cz - ext
        bosco = self.bioma in ("bosco", "parco")
        soglia = 0.52 if self.bioma == "bosco" else 0.66
        H, D, W, BO = [], [], [], []
        for gx in range(G + 1):
            rh, rd, rw, rb = [], [], [], []
            for gz in range(G + 1):
                x, z = x0 + gx * passo, z0 + gz * passo
                h, d, w = self._altezza(x, z)
                # verso il bordo della griglia si scende piano alla pianura
                bordo = _smooth(min(gx, gz, G - gx, G - gz) / (G * 0.1))
                if w < 0.5:
                    h = h * bordo + TERRA_MIN * (1 - bordo)
                rh.append(h)
                rd.append(d)
                rw.append(w)
                b = 0.0
                if bosco and w < 0.01:
                    m = self.rumore(x / 520.0 + 31, z / 520.0 - 5)
                    b = _smooth((m - soglia) / 0.05)
                    b *= _smooth((d - MEZZA_PISTA - self.fuga - 30) / 25.0)
                rb.append(b)
            H.append(rh)
            D.append(rd)
            W.append(rw)
            BO.append(rb)
        self.t_H = H
        self.t_B = BO
        self.t_D = D
        # le normali dei vertici, dal pendio: il terreno e' liscio, non a gradini
        N = [[None] * (G + 1) for _ in range(G + 1)]
        for gx in range(G + 1):
            for gz in range(G + 1):
                hl = H[max(0, gx - 1)][gz]
                hr = H[min(G, gx + 1)][gz]
                hd = H[gx][max(0, gz - 1)]
                hu = H[gx][min(G, gz + 1)]
                N[gx][gz] = _norm((hl - hr, 2 * passo, hd - hu))
        base = self.pal["terra"]
        mat = self.pal["mat"]
        notte = self.notte
        self.bosco_celle = []
        for gx in range(G):
            for gz in range(G):
                ang = ((gx, gz), (gx + 1, gz), (gx + 1, gz + 1), (gx, gz + 1))
                pos = [(x0 + i * passo, H[i][j], z0 + j * passo) for i, j in ang]
                nor = [N[i][j] for i, j in ang]
                dist = [D[i][j] for i, j in ang]
                bo = [BO[i][j] for i, j in ang]
                col = base
                if sum(bo) > 1.2:
                    self.bosco_celle.append((gx, gz))
                glow = 0.0
                if notte:
                    luce = lambda dd: (1.0 - _smooth((dd - 15.0) / 110.0)) * 0.7  # noqa: E731
                    glow = tuple(luce(dd) for dd in dist)
                par = tuple(min(dd, 5000.0) for dd in dist)
                g = glow if isinstance(glow, tuple) else (glow,) * 4
                self.tri(pos[0], pos[1], pos[2], col, (g[0], g[1], g[2]),
                         (nor[0], nor[1], nor[2]), mat, (par[0], par[1], par[2]),
                         (bo[0], bo[1], bo[2]))
                self.tri(pos[0], pos[2], pos[3], col, (g[0], g[2], g[3]),
                         (nor[0], nor[2], nor[3]), mat, (par[0], par[2], par[3]),
                         (bo[0], bo[2], bo[3]))
        self._pianura(base, mat)
        if self.acqua:
            L = self.span * 60
            y = LIVELLO_ACQUA
            self.quad((self.cx - L, y, self.cz - L), (self.cx + L, y, self.cz - L),
                      (self.cx + L, y, self.cz + L), (self.cx - L, y, self.cz + L),
                      (0.10, 0.26, 0.32), 0.0, (0, 1, 0), M_ACQUA)

    def _pianura(self, col, mat) -> None:
        """La pianura attorno alla griglia, fino all'orizzonte - senza il mare.

        E' una cornice, non un quadrato pieno: sotto alla griglia non deve
        passare, se no copre il lago.
        """
        L = self.span * 60
        e = self.t_ext - 1.0
        cx, cz = self.cx, self.cz
        cornice = [
            [(cx - L, cz - L), (cx + L, cz - L), (cx + L, cz - e), (cx - L, cz - e)],
            [(cx - L, cz + e), (cx + L, cz + e), (cx + L, cz + L), (cx - L, cz + L)],
            [(cx - L, cz - e), (cx - e, cz - e), (cx - e, cz + e), (cx - L, cz + e)],
            [(cx + e, cz - e), (cx + L, cz - e), (cx + L, cz + e), (cx + e, cz + e)],
        ]
        y = TERRA_MIN - 0.02
        for poli in cornice:
            if self.acqua and self.acqua[0] == "mare":
                poli = self._taglia_mare(poli)
            for k in range(1, len(poli) - 1):
                a, b, c3 = poli[0], poli[k], poli[k + 1]
                self.tri((a[0], y, a[1]), (b[0], y, b[1]), (c3[0], y, c3[1]), col, 0.0,
                         (0, 1, 0), mat, 5000.0)

    def _taglia_mare(self, poli: list) -> list:
        """La parte di un poligono che resta dalla parte della terra."""
        dx, dz = self.mare_dir
        c = self.mare_c + 20

        def lato(p):
            return p[0] * dx + p[1] * dz - c

        fuori = []
        for k in range(len(poli)):
            a, b = poli[k], poli[(k + 1) % len(poli)]
            if lato(a) <= 0:
                fuori.append(a)
            if (lato(a) <= 0) != (lato(b) <= 0):
                t = lato(a) / (lato(a) - lato(b))
                fuori.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        return fuori

    def terra(self, x: float, z: float) -> float:
        """L'altezza del terreno costruito, per chi deve appoggiarci qualcosa."""
        gx = (x - (self.cx - self.t_ext)) / self.t_passo
        gz = (z - (self.cz - self.t_ext)) / self.t_passo
        G = self.t_G
        if not (0 <= gx < G and 0 <= gz < G):
            return TERRA_MIN
        i, j = int(gx), int(gz)
        fx, fz = gx - i, gz - j
        H = self.t_H
        a = H[i][j] + (H[i + 1][j] - H[i][j]) * fx
        b = H[i][j + 1] + (H[i + 1][j + 1] - H[i][j + 1]) * fx
        return a + (b - a) * fz

    def all_asciutto(self, x: float, z: float) -> bool:
        return self.terra(x, z) > LIVELLO_ACQUA + 0.4

    # ----------------------------------------------------------------- pista
    def _fascia(self, da: float, a: float, alza: float, colore, glow=0.0, mat=M_PIANO,
                par=None) -> None:
        """Una striscia parallela al nastro, da `da` ad `a` metri dal centro.

        `colore` e' un colore fisso o una funzione dell'indice del punto che
        restituisce un colore, o None dove la striscia non c'e'.
        """
        P, R, n = self.P, self.R, self.n
        pr = (0.0, 0.0, 0.0, 0.0) if par is None else par
        for i in range(n):
            j = (i + 1) % n
            col = colore(i) if callable(colore) else colore
            if col is None:
                continue
            m = mat(i) if callable(mat) else mat
            pi, pj, ri, rj = P[i], P[j], R[i], R[j]
            q = [(pi[0] + ri[0] * da, pi[1] + alza, pi[2] + ri[2] * da),
                 (pj[0] + rj[0] * da, pj[1] + alza, pj[2] + rj[2] * da),
                 (pj[0] + rj[0] * a, pj[1] + alza, pj[2] + rj[2] * a),
                 (pi[0] + ri[0] * a, pi[1] + alza, pi[2] + ri[2] * a)]
            self.quad(q[0], q[1], q[2], q[3], col, glow, (0, 1, 0), m, pr)

    def _muro(self, off: float, alto: float, colore, glow: float = 0.0) -> None:
        P, R, n = self.P, self.R, self.n
        for i in range(n):
            j = (i + 1) % n
            col = colore(i) if callable(colore) else colore
            pi, pj, ri, rj = P[i], P[j], R[i], R[j]
            a = (pi[0] + ri[0] * off, pi[1], pi[2] + ri[2] * off)
            b = (pj[0] + rj[0] * off, pj[1], pj[2] + rj[2] * off)
            s = 1 if off > 0 else -1
            nor = (-ri[0] * s, 0.0, -ri[2] * s)
            self.quad(a, b, (b[0], b[1] + alto, b[2]), (a[0], a[1] + alto, a[2]), col, glow, nor)
            self.quad((a[0], a[1] + alto, a[2]), (b[0], b[1] + alto, b[2]),
                      (b[0] + rj[0] * 0.4 * s, b[1] + alto, b[2] + rj[2] * 0.4 * s),
                      (a[0] + ri[0] * 0.4 * s, a[1] + alto, a[2] + ri[2] * 0.4 * s),
                      col, glow, (0, 1, 0))

    def _pista(self) -> None:
        g = 1.0 if self.notte else 0.0
        K = self.K
        curva = 1.0 / RAGGIO_CURVA
        m = MEZZA_PISTA
        f = self.fuga

        def fuga(lato):
            def mat(i):
                return M_GHIAIA if lato * K[i] < -curva * 0.8 else M_PIANO

            def col(i):
                return GHIAIA if lato * K[i] < -curva * 0.8 else FUGA_ASFALTO
            return col, mat

        for lato, da, a in ((1, m + CORDOLO, m + CORDOLO + f), (-1, -m - CORDOLO - f, -m - CORDOLO)):
            col, mat = fuga(lato)
            self._fascia(da, a, 0.04, col, g, mat)
        # l'asfalto sa dove sta la traiettoria: il parametro e' la posizione
        # trasversale, da -1 a 1, e lo shader ci scurisce la gommatura
        self._fascia(-m, m, 0.10, ASFALTO, g, M_ASFALTO, (-1.0, -1.0, 1.0, 1.0))

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
        self._fascia(-m, m, 0.18, lambda i: BIANCO if i == 0 else None, g)
        for k in range(20):
            i = (-(3 + k * 2)) % self.n
            lato = -1 if k % 2 == 0 else 1
            p, r, fw = self.P[i], self.R[i], self.F[i]
            cx, cz = p[0] + r[0] * lato * 3.2, p[2] + r[2] * lato * 3.2
            y = p[1] + 0.18
            a = (cx - r[0] * 1.2, y, cz - r[2] * 1.2)
            b = (cx + r[0] * 1.2, y, cz + r[2] * 1.2)
            self.quad(a, b, (b[0] + fw[0] * 0.5, y, b[2] + fw[2] * 0.5),
                      (a[0] + fw[0] * 0.5, y, a[2] + fw[2] * 0.5), BIANCO, g, (0, 1, 0))
        citta = self.bioma == "citta"

        def barriera(i):
            if citta:
                return BIANCO if (i // 6) % 2 else (0.20, 0.34, 0.62)
            return (0.62, 0.64, 0.67)
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
        self.paddock = None
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
        mid = B[len(B) // 2]
        lm = lati[len(B) // 2]
        d, _ = self.vicino(mid[0] + lm[0] * 20, mid[2] + lm[2] * 20)
        d2, _ = self.vicino(mid[0] - lm[0] * 20, mid[2] - lm[2] * 20)
        verso = 1.0 if d > d2 else -1.0
        for k in range(len(B) - 1):
            a, b = B[k], B[k + 1]
            ra, rb = lati[k], lati[k + 1]
            y = max(a[1], b[1]) + 0.12
            q = [(a[0] - ra[0] * largo, y, a[2] - ra[2] * largo),
                 (b[0] - rb[0] * largo, y, b[2] - rb[2] * largo),
                 (b[0] + rb[0] * largo, y, b[2] + rb[2] * largo),
                 (a[0] + ra[0] * largo, y, a[2] + ra[2] * largo)]
            self.quad(q[0], q[1], q[2], q[3], (0.26, 0.27, 0.30), g, (0, 1, 0))
        n = len(B)
        k0, k1 = int(n * 0.22), int(n * 0.78)
        for k in range(k0, k1, 3):
            a, b = B[k], B[min(n - 1, k + 3)]
            ang = math.atan2(b[2] - a[2], b[0] - a[0])
            r = lati[k]
            x = (a[0] + b[0]) / 2 + r[0] * verso * (largo + 9)
            z = (a[2] + b[2]) / 2 + r[2] * verso * (largo + 9)
            lungo = math.hypot(b[0] - a[0], b[2] - a[2]) + 0.4
            self.scatola(x, a[1], z, lungo, 16, 11, ang, (0.80, 0.81, 0.84),
                         0.6 if self.notte else 0.0, (0.86, 0.87, 0.89))
        # il paddock, dietro ai box: un piazzale con le motorhome in fila
        a, b = B[k0], B[k1]
        ang = math.atan2(b[2] - a[2], b[0] - a[0])
        r = lati[(k0 + k1) // 2]
        lungo = math.hypot(b[0] - a[0], b[2] - a[2])
        px = (a[0] + b[0]) / 2 + r[0] * verso * (largo + 50)
        pz = (a[2] + b[2]) / 2 + r[2] * verso * (largo + 50)
        py = (a[1] + b[1]) / 2
        ca, sa = math.cos(ang), math.sin(ang)
        angoli = [(px + ca * u - sa * w, pz + sa * u + ca * w)
                  for u in (-lungo / 2, 0, lungo / 2) for w in (-35, 0, 35)]
        if not all(self.all_asciutto(x, z) for x, z in angoli):
            return
        self.paddock = (px, pz, ang)
        self._piazzale(px, py, pz, lungo, 70, ang, M_PIANO, (0.30, 0.31, 0.34), g)
        for fila in (-18, 12):
            for j, u in enumerate(range(int(-lungo / 2) + 12, int(lungo / 2) - 12, 26)):
                x = px + ca * u - sa * fila
                z = pz + sa * u + ca * fila
                col = SQUADRE[(j + (fila > 0) * 5) % len(SQUADRE)]
                self.scatola(x, py + 0.2, z, 20, 9, 6 + (j % 3), ang, col,
                             0.5 if self.notte else 0.0, _mix(col, (1, 1, 1), 0.35))

    def _piazzale(self, x, y, z, lungo, largo, ang, mat, col, glow=0.0) -> None:
        """Un rettangolo piatto appoggiato sul terreno (parcheggi, paddock)."""
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(-lungo / 2, -largo / 2), (lungo / 2, -largo / 2), (lungo / 2, largo / 2),
               (-lungo / 2, largo / 2)]
        q = [(x + ca * u - sa * w, z + sa * u + ca * w) for u, w in pts]
        alto = max([self.terra(px, pz) for px, pz in q] + [y]) + 0.15
        self.quad(*[(px, alto, pz) for px, pz in q], col, glow, (0, 1, 0), mat)
        # un gradino sotto, cosi' non resta sospeso sui pendii
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            ya, yb = self.terra(*a) - 0.3, self.terra(*b) - 0.3
            self.quad((a[0], ya, a[1]), (b[0], yb, b[1]), (b[0], alto, b[1]),
                      (a[0], alto, a[1]), (0.40, 0.40, 0.40), 0.0)

    # --------------------------------------------------------------- tribune
    def _tribuna(self, i: int, lato: float, lungo: float, colore) -> bool:
        p, r, fw = self.P[i], self.R[i], self.F[i]
        dist = MEZZA_PISTA + CORDOLO + self.fuga + 6
        x0, z0 = p[0] + r[0] * lato * dist, p[2] + r[2] * lato * dist
        # dietro a una tribuna in un tornante c'e' l'altro pezzo di pista
        for u in (-lungo / 2, 0.0, lungo / 2):
            for v in (4.0, 18.0):
                x = x0 + fw[0] * u + r[0] * lato * v
                z = z0 + fw[2] * u + r[2] * lato * v
                if self.vicino(x, z, 40.0)[0] < MEZZA_PISTA + CORDOLO + self.fuga + 2:
                    return False
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
        self.quad(a, b, c, d, colore, g, None, M_FOLLA)
        grigio = (0.62, 0.63, 0.66)
        self.quad(pt(-L, 0, 0), pt(L, 0, 0), b, a, grigio, g, (-rx, 0, -rz))
        self.quad(pt(-L, prof, 0), pt(L, prof, 0), c, d, grigio, 0.0, (rx, 0, rz))
        self.quad(pt(-L, 0, 0), a, d, pt(-L, prof, 0), grigio, 0.0, (-fx, 0, -fz))
        self.quad(pt(L, 0, 0), b, c, pt(L, prof, 0), grigio, 0.0, (fx, 0, fz))
        self.quad(pt(-L, prof * 0.3, alto + 5), pt(L, prof * 0.3, alto + 5),
                  pt(L, prof + 1, alto + 4), pt(-L, prof + 1, alto + 4), (0.90, 0.91, 0.93), g,
                  None, M_TETTO)
        return True

    def _tribune(self) -> None:
        colori = [(0.22, 0.34, 0.64), (0.72, 0.18, 0.18), (0.86, 0.74, 0.22), (0.20, 0.54, 0.42)]
        verso = -1.0
        if self.box_P:
            mid = self.box_P[len(self.box_P) // 2]
            p, r = self.P[0], self.R[0]
            verso = -1.0 if (mid[0] - p[0]) * r[0] + (mid[2] - p[2]) * r[2] > 0 else 1.0
        for k, i in enumerate(range(-40, 50, 18)):
            self._tribuna(i % self.n, verso, 80.0, colori[k % len(colori)])
        fatte = []
        for i in range(0, self.n, 3):
            if abs(self.K[i]) > 1.0 / 60.0 and all(abs(i - j) > 120 for j in fatte):
                lato = -1.0 if self.K[i] > 0 else 1.0
                if self._tribuna(i, lato, 70.0, colori[len(fatte) % len(colori)]):
                    fatte.append(i)
            if len(fatte) >= 7:
                break

    # ---------------------------------------------------------------- strade
    def _libero(self, x: float, z: float, margine: float) -> bool:
        d, _ = self.vicino(x, z, margine + 5)
        if d < margine:
            return False
        for b in self.box_P[::4]:
            if (b[0] - x) ** 2 + (b[2] - z) ** 2 < (margine + 30) ** 2:
                return False
        if self.paddock and (self.paddock[0] - x) ** 2 + (self.paddock[1] - z) ** 2 < 120 ** 2:
            return False
        return self.all_asciutto(x, z)

    def _strade(self) -> None:
        """Le strade d'accesso e i parcheggi: in citta' le strade le fa la griglia."""
        self.strade = []
        rng = self.rng
        if self.bioma == "citta":
            return
        partenza = (self.paddock[0], self.paddock[1]) if self.paddock else (self.cx, self.cz)
        g = 0.6 if self.notte else 0.0
        for k in range(3):
            ang = math.atan2(partenza[1] - self.cz, partenza[0] - self.cx) + (k - 1) * 1.1
            x, z = partenza
            punti = []
            for _ in range(200):
                x += math.cos(ang) * 18
                z += math.sin(ang) * 18
                ang += rng.uniform(-0.12, 0.12)
                if math.hypot(x - self.cx, z - self.cz) > self.ext * 1.1:
                    break
                if punti or self._libero(x, z, MEZZA_PISTA + self.fuga + 20):
                    if punti and not self._libero(x, z, MEZZA_PISTA + self.fuga + 20):
                        break
                    punti.append((x, z))
            if len(punti) > 4:
                self.strade.append(punti)
                self._nastro(punti, 7.0, (0.30, 0.31, 0.33), M_STRADA, g)
        # i parcheggi dei tifosi, lungo le strade
        for strada in self.strade:
            for j in range(4, min(len(strada) - 2, 40), 9):
                x, z = strada[j]
                a, b = strada[j - 1], strada[j + 1]
                ang = math.atan2(b[1] - a[1], b[0] - a[0])
                ox, oz = -math.sin(ang) * 60, math.cos(ang) * 60
                cx, cz = x + ox, z + oz
                if self._libero(cx, cz, 90):
                    mat = M_PARCHEGGIO
                    col = (0.30, 0.31, 0.33) if self.bioma == "deserto" else (0.36, 0.37, 0.38)
                    self._piazzale(cx, self.terra(cx, cz), cz, 110, 70, ang, mat, col, g)

    def _nastro(self, punti, largo, col, mat, glow=0.0) -> None:
        for k in range(len(punti) - 1):
            a, b = punti[k], punti[k + 1]
            dx, dz = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dz) or 1.0
            rx, rz = -dz / d * largo / 2, dx / d * largo / 2
            ya, yb = self.terra(*a) + 0.6, self.terra(*b) + 0.6
            self.quad((a[0] - rx, ya, a[1] - rz), (b[0] - rx, yb, b[1] - rz),
                      (b[0] + rx, yb, b[1] + rz), (a[0] + rx, ya, a[1] + rz),
                      col, glow, (0, 1, 0), mat)

    # ------------------------------------------------------------------ citta
    def _citta(self) -> None:
        """Gli isolati: le strade le dipinge lo shader, qui si alzano i palazzi."""
        if self.bioma != "citta":
            return
        rng = self.rng
        B = BLOCCO
        strada = 16.0
        k0 = int(self.ext / B)
        mediterranea = self.track.id in ("monaco", "baku", "madrid")
        tinte = ([(0.86, 0.78, 0.66), (0.80, 0.56, 0.42), (0.90, 0.86, 0.78), (0.74, 0.70, 0.62)]
                 if mediterranea else
                 [(0.62, 0.64, 0.68), (0.72, 0.72, 0.70), (0.52, 0.55, 0.60), (0.80, 0.80, 0.78)])
        for ix in range(-k0, k0 + 1):
            for iz in range(-k0, k0 + 1):
                bx, bz = self.cx + (ix + 0.5) * B, self.cz + (iz + 0.5) * B
                interno = B - strada
                tipo = rng.random()
                centro = math.hypot(bx - self.cx, bz - self.cz) / (self.span * 0.8)
                # l'isolato si divide in due o quattro lotti
                parti = 2 if tipo < 0.5 else 1
                lato = interno / parti
                for u in range(parti):
                    for v in range(parti):
                        lx = bx - interno / 2 + (u + 0.5) * lato
                        lz = bz - interno / 2 + (v + 0.5) * lato
                        margine = lato * 0.55 + MEZZA_PISTA + self.fuga + 3
                        if not self._libero(lx, lz, margine):
                            continue
                        if rng.random() < 0.10:
                            # un giardino fra i palazzi
                            for _ in range(5):
                                self._chioma(lx + rng.uniform(-lato / 3, lato / 3),
                                             lz + rng.uniform(-lato / 3, lato / 3),
                                             rng.uniform(4, 6), (0.20, 0.38, 0.16))
                            continue
                        alto = 10 + rng.random() ** 2.2 * 80 * max(0.3, 1.25 - centro)
                        col = rng.choice(tinte)
                        acceso = (0.25 + rng.random() * 0.5) if self.notte else 0.0
                        w = lato - rng.uniform(4, 10)
                        y = self.terra(lx, lz) - 0.5
                        self.scatola(lx, y, lz, w, w * rng.uniform(0.7, 1.0), alto, 0.0, col,
                                     acceso, _mix(col, (0.3, 0.3, 0.3), 0.25))
                        if alto > 25 and rng.random() < 0.6:
                            # gli impianti sul tetto: da sopra fanno la citta'
                            self.scatola(lx + rng.uniform(-w / 5, w / 5), y + alto,
                                         lz + rng.uniform(-w / 5, w / 5), w * 0.3, w * 0.25,
                                         3.0, 0.0, (0.55, 0.56, 0.58))

    # ----------------------------------------------------------------- alberi
    def _chioma(self, x: float, z: float, r: float, col, alto: float | None = None) -> None:
        """Un albero visto dall'alto: una chioma tonda, bassa, a facce."""
        y = self.terra(x, z)
        alto = alto or r * 1.8
        lati = 7
        a0 = self.rng.random()
        anello = [(x + math.cos(a0 + k * 2 * math.pi / lati) * r, y + alto * 0.45,
                   z + math.sin(a0 + k * 2 * math.pi / lati) * r) for k in range(lati)]
        basso = [(x + math.cos(a0 + (k + 0.5) * 2 * math.pi / lati) * r * 0.7, y + alto * 0.1,
                  z + math.sin(a0 + (k + 0.5) * 2 * math.pi / lati) * r * 0.7) for k in range(lati)]
        cima = (x, y + alto, z)
        for k in range(lati):
            a, b = anello[k], anello[(k + 1) % lati]
            self.tri(a, b, cima, col, 0.0, None, M_CHIOMA)
            c = basso[k]
            nor = _norm((c[0] - x, -0.3 * r, c[2] - z))
            self.tri(a, c, b, _mix(col, (0, 0, 0), 0.2), 0.0, nor, M_CHIOMA)

    def _alberi(self) -> None:
        rng = self.rng
        passo = self.t_passo
        x0, z0 = self.cx - self.t_ext, self.cz - self.t_ext
        verdi = [(0.16, 0.32, 0.13), (0.20, 0.38, 0.15), (0.13, 0.28, 0.12), (0.24, 0.40, 0.17)]
        tetto = 5200
        fatti = 0
        # i boschi: fitti, chiome che si toccano
        celle = sorted(self.bosco_celle, key=lambda c: self.t_D[c[0]][c[1]])
        per_cella = max(1, int((passo / 11.0) ** 2))
        B = self.t_B
        for gx, gz in celle:
            for _ in range(per_cella):
                if fatti >= tetto:
                    break
                fx, fz = rng.random(), rng.random()
                a = B[gx][gz] + (B[gx + 1][gz] - B[gx][gz]) * fx
                b = B[gx][gz + 1] + (B[gx + 1][gz + 1] - B[gx][gz + 1]) * fx
                if rng.random() > a + (b - a) * fz:
                    continue
                x = x0 + (gx + fx) * passo
                z = z0 + (gz + fz) * passo
                self._chioma(x, z, rng.uniform(5.5, 8.5), rng.choice(verdi))
                fatti += 1
        # gli alberi sparsi e i filari lungo le strade
        sparsi = {"parco": 700, "bosco": 500, "dune": 260, "deserto": 0, "citta": 0}[self.bioma]
        tentativi = 0
        while sparsi > 0 and tentativi < 9000 and fatti < tetto + 900:
            tentativi += 1
            x = self.cx + rng.uniform(-self.ext, self.ext)
            z = self.cz + rng.uniform(-self.ext, self.ext)
            if not self._libero(x, z, MEZZA_PISTA + self.fuga + 14):
                continue
            r = rng.uniform(3.0, 6.5) if self.bioma != "dune" else rng.uniform(1.8, 3.0)
            self._chioma(x, z, r, rng.choice(verdi))
            sparsi -= 1
            fatti += 1
        for strada in self.strade:
            for j in range(0, len(strada) - 1, 3):
                if self.bioma == "deserto" or rng.random() < 0.55:
                    continue
                a, b = strada[j], strada[j + 1]
                dx, dz = b[0] - a[0], b[1] - a[1]
                d = math.hypot(dx, dz) or 1.0
                for s in (-1, 1):
                    x, z = a[0] - dz / d * 8 * s, a[1] + dx / d * 8 * s
                    if self._libero(x, z, MEZZA_PISTA + self.fuga + 10):
                        self._chioma(x, z, rng.uniform(3.5, 5.0), rng.choice(verdi))
        # nel deserto le palme stanno dove c'e' l'uomo: paddock e strade
        if self.bioma == "deserto" and self.paddock:
            px, pz, _ = self.paddock
            for _ in range(60):
                x, z = px + rng.uniform(-260, 260), pz + rng.uniform(-260, 260)
                if self._libero(x, z, MEZZA_PISTA + self.fuga + 10):
                    self._chioma(x, z, rng.uniform(3.0, 4.0), (0.28, 0.42, 0.18), 10.0)

    # ------------------------------------------------------------------ fari
    def _fari(self) -> None:
        """Le torri dei fari lungo il giro, per le gare di notte."""
        if not self.notte:
            return
        for k, i in enumerate(range(0, self.n, 24)):
            lato = 1 if k % 2 else -1
            p, r = self.P[i], self.R[i]
            dist = MEZZA_PISTA + CORDOLO + self.fuga + 4
            x, z = p[0] + r[0] * lato * dist, p[2] + r[2] * lato * dist
            y = self.terra(x, z)
            self.scatola(x, y, z, 0.8, 0.8, 26.0, 0.0, (0.35, 0.36, 0.40))
            ang = math.atan2(r[2], r[0])
            self.scatola(x, y + 26.0, z, 2.0, 5.0, 2.2, ang, (1.0, 0.95, 0.80), 1.6,
                         (1.0, 0.95, 0.80), M_PIANO)

    def _portale(self) -> None:
        """Il portale del via, sopra al traguardo."""
        p, r = self.P[0], self.R[0]
        g = 1.0 if self.notte else 0.0
        largo = MEZZA_PISTA + 3.0
        scuro = (0.14, 0.15, 0.18)
        for lato in (-1, 1):
            x, z = p[0] + r[0] * largo * lato, p[2] + r[2] * largo * lato
            self.scatola(x, p[1], z, 1.2, 1.2, 9.0, 0.0, scuro, 0.0, None, M_PIANO)
        ang = math.atan2(r[2], r[0])
        self.scatola(p[0], p[1] + 8.0, p[2], largo * 2 + 1.2, 1.4, 1.6, ang, scuro, g, None,
                     M_PIANO)

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
