"""La monoposto in 3D, costruita dal codice.

Non c'e' un modello scaricato: la macchina si fa qui, a sezioni, come la si
disegnerebbe su un foglio a quadretti partendo dalle quote del regolamento
2026 - passo 3,4 metri, larghezza 1,9, ruote da diciotto pollici con la
spalla, il muso basso che si alza verso la paratia, la cellula di
sopravvivenza con l'halo e il casco, la presa d'aria sopra la testa, le
pance scavate sotto, il cofano che scende verso il cambio, il fondo con il
diffusore, l'ala anteriore a tre elementi e quella posteriore con il flap e
la trave bassa.

Ogni superficie dice di che cosa e' fatta - livrea, seconda tinta, carbonio,
gomma, cerchio, casco, halo - e lo shader di `vista3d` la colora con i colori
della squadra. La carrozzeria e' smussata (le normali si mediano dove due
facce si incontrano ad angolo dolce), gli spigoli veri restano vivi.

Il riferimento e' quello della macchina: x in avanti (il muso), y in alto,
z a destra; l'origine e' a terra, a meta' fra i due assi.
"""
from __future__ import annotations

import math
from array import array

# i materiali: stessi numeri nello shader delle macchine
LIVREA, SECONDA, CARBONIO, GOMMA, CERCHIO, CASCO, HALO = range(7)

PASSO = 3.4            # interasse, metri
CARREGGIATA = 1.58     # fra i centri delle ruote
RAGGIO_RUOTA = 0.355   # 710 mm di diametro
RAGGIO_CERCHIO = 0.235  # diciotto pollici, con la spalla attorno
LUNGHEZZA = 5.6        # da punta a punta, per chi deve sapere quanto e' grande

# le parti che si smussano: la vernice e il casco. Carbonio, gomma e halo no,
# lo spigolo li' e' vero
SMUSSATE = (LIVREA, SECONDA, CASCO)
SMUSSO_COS = math.cos(math.radians(48))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _croce(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


class _Mesh:
    def __init__(self):
        self.tris = []          # (a, b, c, parte, normale della faccia)

    def tri(self, a, b, c, parte: int, fuori=None) -> None:
        """Un triangolo; `fuori` e' un punto interno: la faccia guarda via da li'."""
        n = _croce(_sub(b, a), _sub(c, a))
        if n[0] * n[0] + n[1] * n[1] + n[2] * n[2] < 1e-16:
            return
        n = _norm(n)
        if fuori is not None:
            m = ((a[0] + b[0] + c[0]) / 3 - fuori[0], (a[1] + b[1] + c[1]) / 3 - fuori[1],
                 (a[2] + b[2] + c[2]) / 3 - fuori[2])
            if n[0] * m[0] + n[1] * m[1] + n[2] * m[2] < 0:
                b, c = c, b
                n = (-n[0], -n[1], -n[2])
        self.tris.append((a, b, c, parte, n))

    def quad(self, a, b, c, d, parte: int, fuori=None) -> None:
        self.tri(a, b, c, parte, fuori)
        self.tri(a, c, d, parte, fuori)

    def loft(self, sezioni: list, parte: int, tappo_davanti=None, tappo_dietro=None) -> None:
        """Un solido che passa per delle sezioni: (x, [(y, z), ...]), tutte con
        lo stesso numero di punti. I tappi hanno la loro parte (o nessuno)."""
        for (x0, s0), (x1, s1) in zip(sezioni, sezioni[1:]):
            n = len(s0)
            cy = (sum(p[0] for p in s0) + sum(p[0] for p in s1)) / (2 * n)
            cz = (sum(p[1] for p in s0) + sum(p[1] for p in s1)) / (2 * n)
            centro = ((x0 + x1) / 2, cy, cz)
            for i in range(n):
                j = (i + 1) % n
                self.quad((x0, s0[i][0], s0[i][1]), (x0, s0[j][0], s0[j][1]),
                          (x1, s1[j][0], s1[j][1]), (x1, s1[i][0], s1[i][1]), parte, centro)
        for (x, s), p, dx in ((sezioni[0], tappo_davanti, -1.0), (sezioni[-1], tappo_dietro, 1.0)):
            if p is None:
                continue
            cy = sum(q[0] for q in s) / len(s)
            cz = sum(q[1] for q in s) / len(s)
            for i in range(len(s)):
                j = (i + 1) % len(s)
                self.tri((x, cy, cz), (x, s[i][0], s[i][1]), (x, s[j][0], s[j][1]), p,
                         (x + dx * 0.5 * (1 if sezioni[0][0] < sezioni[-1][0] else -1), cy, cz))

    def scatola(self, x0, x1, y0, y1, z0, z1, parte: int) -> None:
        c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        p = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        facce = [(0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)]
        for f in facce:
            self.quad(*(p[k] for k in f), parte, c)

    def piastra(self, punti: list, spessore: float, parte: int, zc: float = 0.0) -> None:
        """Una lastra sottile col contorno `punti` (nel piano x-y), spessa lungo z
        e centrata in `zc`: paratie, pinne."""
        z0 = zc - spessore / 2
        z1 = zc + spessore / 2
        dentro = (sum(p[0] for p in punti) / len(punti), sum(p[1] for p in punti) / len(punti),
                  zc)
        for z in (z0, z1):
            for i in range(1, len(punti) - 1):
                a, b, c = punti[0], punti[i], punti[i + 1]
                self.tri((a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z), parte, dentro)
        for i in range(len(punti)):
            j = (i + 1) % len(punti)
            a, b = punti[i], punti[j]
            self.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1),
                      parte, dentro)

    def ruota(self, cx, cy, z0, z1, esterno: int, parte_gomma, parte_cerchio,
              lati: int = 24, raggi=None) -> None:
        """La ruota: battistrada, spalla e cerchio, con il mozzo al centro."""
        r, rc = raggi or (RAGGIO_RUOTA, RAGGIO_CERCHIO)
        c = (cx, cy, (z0 + z1) / 2)
        ang = [2 * math.pi * k / lati for k in range(lati)]
        tondo = [(cx + math.cos(a), cy + math.sin(a)) for a in ang]

        def punto(k, raggio, z):
            return (cx + (tondo[k][0] - cx) * raggio, cy + (tondo[k][1] - cy) * raggio, z)
        # il battistrada, un filo bombato
        zm = (z0 + z1) / 2
        for k in range(lati):
            j = (k + 1) % lati
            for za, zb, ra, rb in ((z0, zm, r * 0.97, r), (zm, z1, r, r * 0.97)):
                self.quad(punto(k, ra, za), punto(j, ra, za), punto(j, rb, zb),
                          punto(k, rb, zb), parte_gomma, c)
        # le due spalle, e il cerchio sul lato esterno, un poco rientrato
        for z, lato in ((z0, -1), (z1, 1)):
            rientro = z - lato * 0.02
            for k in range(lati):
                j = (k + 1) % lati
                self.quad(punto(k, r * 0.97, z), punto(j, r * 0.97, z),
                          punto(j, rc, rientro), punto(k, rc, rientro), parte_gomma,
                          (cx, cy, z - lato * 0.5))
                parte = parte_cerchio if lato == esterno else parte_gomma
                self.tri((cx, cy, rientro - lato * 0.03), punto(k, rc, rientro),
                         punto(j, rc, rientro), parte, (cx, cy, z - lato * 0.5))
        # il dado centrale
        zf = (z1 if esterno > 0 else z0) - esterno * 0.035
        self.cilindro_z(cx, cy, min(zf, zf + esterno * 0.04), max(zf, zf + esterno * 0.04),
                        0.05, CARBONIO, 8)

    def cilindro_z(self, cx, cy, z0, z1, r, parte: int, lati: int = 14) -> None:
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
               for a in (2 * math.pi * k / lati for k in range(lati))]
        c = (cx, cy, (z0 + z1) / 2)
        for i in range(lati):
            j = (i + 1) % lati
            (xa, ya), (xb, yb) = pts[i], pts[j]
            self.quad((xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1), parte, c)
            self.tri((cx, cy, z0), (xa, ya, z0), (xb, yb, z0), parte, c)
            self.tri((cx, cy, z1), (xa, ya, z1), (xb, yb, z1), parte, c)

    def trave(self, a, b, spessore: float, parte: int, lati: int = 6) -> None:
        """Un tubo da a a b: le sospensioni, l'halo."""
        f = _norm(_sub(b, a))
        aiuto = (0.0, 1.0, 0.0) if abs(f[1]) < 0.9 else (1.0, 0.0, 0.0)
        u = _norm(_croce(f, aiuto))
        w = _norm(_croce(f, u))
        giro = [(math.cos(2 * math.pi * k / lati), math.sin(2 * math.pi * k / lati))
                for k in range(lati)]
        pa = [tuple(a[i] + (u[i] * s + w[i] * t) * spessore for i in range(3)) for s, t in giro]
        pb = [tuple(b[i] + (u[i] * s + w[i] * t) * spessore for i in range(3)) for s, t in giro]
        for i in range(lati):
            j = (i + 1) % lati
            # il centro si prende sulla retta, all'altezza della faccia
            m = tuple((a[k] + b[k]) / 2 for k in range(3))
            self.quad(pa[i], pa[j], pb[j], pb[i], parte, m)

    def sfera(self, c, rx, ry, rz, parte: int, fette: int = 10, spicchi: int = 14) -> None:
        def punto(t, p):
            return (c[0] + rx * math.sin(t) * math.cos(p), c[1] + ry * math.cos(t),
                    c[2] + rz * math.sin(t) * math.sin(p))
        for i in range(fette):
            t0, t1 = math.pi * i / fette, math.pi * (i + 1) / fette
            for k in range(spicchi):
                p0, p1 = 2 * math.pi * k / spicchi, 2 * math.pi * (k + 1) / spicchi
                self.quad(punto(t0, p0), punto(t0, p1), punto(t1, p1), punto(t1, p0), parte, c)

    # ------------------------------------------------------------------ fine
    def vertici(self) -> array:
        """Sette float per vertice, con le normali smussate dove serve."""
        vicine: dict = {}
        for idx, (a, b, c, parte, n) in enumerate(self.tris):
            if parte not in SMUSSATE:
                continue
            for p in (a, b, c):
                k = (parte, round(p[0], 3), round(p[1], 3), round(p[2], 3))
                vicine.setdefault(k, []).append(n)
        out = array("f")
        for a, b, c, parte, n in self.tris:
            for p in (a, b, c):
                nn = n
                if parte in SMUSSATE:
                    k = (parte, round(p[0], 3), round(p[1], 3), round(p[2], 3))
                    somma = [0.0, 0.0, 0.0]
                    for m in vicine.get(k, ()):
                        if m[0] * n[0] + m[1] * n[1] + m[2] * n[2] >= SMUSSO_COS:
                            somma[0] += m[0]
                            somma[1] += m[1]
                            somma[2] += m[2]
                    nn = _norm(somma) if any(somma) else n
                out.extend((p[0], p[1], p[2], nn[0], nn[1], nn[2], float(parte)))
        return out


def _sezione(larga_basso: float, larga_alto: float, basso: float, alto: float,
             esp: float = 2.6, punti: int = 18) -> list:
    """Una sezione tonda-quadrata (una superellisse), piu' larga in basso."""
    yc, h = (basso + alto) / 2, (alto - basso) / 2
    out = []
    for k in range(punti):
        t = 2 * math.pi * k / punti
        c, s = math.cos(t), math.sin(t)
        y = yc + h * math.copysign(abs(s) ** (2 / esp), s)
        q = (y - basso) / max(1e-6, alto - basso)
        w = larga_basso + (larga_alto - larga_basso) * q
        z = w * math.copysign(abs(c) ** (2 / esp), c)
        out.append((y, z))
    return out


def costruisci() -> array:
    """La monoposto intera: sette float per vertice (posizione, normale, parte)."""
    m = _Mesh()
    fronte, retro = PASSO / 2, -PASSO / 2

    # la scocca: muso, cellula, presa d'aria, cofano, fino alla struttura dietro
    scocca = [
        (2.90, 0.11, 0.09, 0.20, 0.27),
        (2.62, 0.14, 0.12, 0.18, 0.33),
        (2.25, 0.17, 0.14, 0.16, 0.41),
        (1.85, 0.21, 0.17, 0.15, 0.50),
        (1.40, 0.24, 0.19, 0.13, 0.60),
        (0.95, 0.30, 0.24, 0.11, 0.66),
        (0.50, 0.36, 0.29, 0.10, 0.70),
        (0.05, 0.40, 0.31, 0.10, 0.72),
        (-0.30, 0.40, 0.18, 0.10, 1.00),
        (-0.55, 0.38, 0.16, 0.11, 0.99),
        (-0.95, 0.31, 0.13, 0.12, 0.85),
        (-1.40, 0.23, 0.10, 0.14, 0.66),
        (-1.85, 0.16, 0.08, 0.17, 0.51),
        (-2.25, 0.11, 0.07, 0.22, 0.41),
        (-2.45, 0.07, 0.05, 0.26, 0.36),
    ]
    m.loft([(x, _sezione(wb, wt, y0, y1)) for x, wb, wt, y0, y1 in scocca], LIVREA,
           LIVREA, CARBONIO)
    # l'abitacolo: la vasca scura, con il bordo, davanti al pilota
    m.loft([(0.52, _sezione(0.22, 0.24, 0.52, 0.735, 3.0, 12)),
            (0.10, _sezione(0.25, 0.27, 0.52, 0.745, 3.0, 12)),
            (-0.26, _sezione(0.24, 0.24, 0.52, 0.745, 3.0, 12))], CARBONIO, CARBONIO, CARBONIO)
    # il pilota: le spalle scure e il casco, con la visiera
    m.sfera((0.02, 0.81, 0.0), 0.15, 0.14, 0.13, CASCO)
    # la presa d'aria sopra la testa e la telecamera in cima
    m.loft([(-0.24, _sezione(0.12, 0.10, 0.86, 0.98, 3.0, 10)),
            (-0.30, _sezione(0.12, 0.10, 0.86, 0.98, 3.0, 10))], CARBONIO, CARBONIO, None)
    m.scatola(-0.42, -0.30, 1.00, 1.05, -0.10, 0.10, CARBONIO)
    # l'halo: il montante davanti, l'anello attorno alla testa, le gambe dietro
    anello = []
    for k in range(15):
        t = math.radians(-105 + 210 * k / 14)
        anello.append((0.03 + 0.34 * math.cos(t), 0.93 - 0.03 * (1 - math.cos(t)),
                       0.27 * math.sin(t)))
    for a, b in zip(anello, anello[1:]):
        m.trave(a, b, 0.028, HALO)
    m.trave((0.44, 0.70, 0.0), anello[7], 0.03, HALO)
    for estremo in (anello[0], anello[-1]):
        m.trave(estremo, (estremo[0] - 0.04, 0.70, estremo[2] * 1.02), 0.028, HALO)
    # gli specchietti, sui supporti ai lati dell'abitacolo
    for lato in (-1, 1):
        m.scatola(0.40, 0.48, 0.74, 0.83, *sorted((lato * 0.47, lato * 0.63)), SECONDA)
        m.trave((0.44, 0.70, lato * 0.30), (0.44, 0.78, lato * 0.48), 0.012, CARBONIO)

    # le pance: bocca in alto, scavate sotto, che scendono verso il cambio
    for lato in (-1, 1):
        def pancia(x, zi, zo, y0, y1):
            sez = [(y0 + 0.12, zi), (y0 + 0.02, zi + (zo - zi) * 0.45),
                   (y0 + 0.06, zo - 0.04), (y0 + 0.18, zo), (y1 - 0.08, zo),
                   (y1 - 0.01, zo - 0.07), (y1, zi + (zo - zi) * 0.4), (y1, zi)]
            return (x, [(y, lato * z) for y, z in sez])
        sezioni = [pancia(0.74, 0.30, 0.64, 0.30, 0.60), pancia(0.48, 0.30, 0.73, 0.22, 0.61),
                   pancia(0.00, 0.30, 0.76, 0.19, 0.58), pancia(-0.50, 0.28, 0.71, 0.18, 0.51),
                   pancia(-1.00, 0.24, 0.56, 0.16, 0.41), pancia(-1.50, 0.18, 0.37, 0.15, 0.31),
                   pancia(-1.85, 0.14, 0.21, 0.14, 0.23)]
        m.loft(sezioni, SECONDA, CARBONIO, None)
    # la pinna sul cofano
    m.piastra([(-0.60, 0.97), (-0.62, 1.01), (-1.95, 0.60), (-1.95, 0.50)], 0.016, LIVREA)

    # il fondo: piatto, largo fino alle ruote, con il bordo rialzato e il diffusore
    fondo = [(1.30, 0.38), (0.95, 0.70), (0.55, 0.78), (-1.25, 0.78), (-1.60, 0.62),
             (-2.05, 0.52)]
    for (xa, wa), (xb, wb) in zip(fondo, fondo[1:]):
        m.quad((xa, 0.035, -wa), (xa, 0.035, wa), (xb, 0.035, wb), (xb, 0.035, -wb),
               CARBONIO, ((xa + xb) / 2, 1.0, 0.0))
        m.quad((xa, 0.065, -wa), (xa, 0.065, wa), (xb, 0.065, wb), (xb, 0.065, -wb),
               CARBONIO, ((xa + xb) / 2, -1.0, 0.0))
        for lato in (-1, 1):
            m.quad((xa, 0.035, lato * wa), (xb, 0.035, lato * wb), (xb, 0.10, lato * wb),
                   (xa, 0.10, lato * wa), CARBONIO, ((xa + xb) / 2, 0.06, 0.0))
    # il diffusore: una rampa che sale dietro l'asse posteriore
    m.quad((-1.55, 0.065, -0.50), (-1.55, 0.065, 0.50), (-2.30, 0.30, 0.50),
           (-2.30, 0.30, -0.50), CARBONIO, (-1.9, 0.0, 0.0))
    for zc in (-0.50, 0.0, 0.50):
        m.piastra([(-1.55, 0.05), (-2.32, 0.05), (-2.32, 0.32), (-1.55, 0.08)], 0.012,
                  CARBONIO, zc)

    # l'ala anteriore: il piano principale basso, due flap che salgono verso
    # l'esterno, le paratie sottili
    m.scatola(2.62, 2.98, 0.055, 0.085, -0.92, 0.92, LIVREA)
    for lato in (-1, 1):
        a, b = sorted((lato * 0.22, lato * 0.90))
        m.scatola(2.46, 2.74, 0.115, 0.14, a, b, SECONDA)
        a, b = sorted((lato * 0.34, lato * 0.90))
        m.scatola(2.34, 2.56, 0.175, 0.20, a, b, SECONDA)
        m.piastra([(2.30, 0.04), (2.99, 0.04), (2.99, 0.13), (2.60, 0.30), (2.30, 0.30)],
                  0.018, LIVREA, lato * 0.915)
    # i piloni che reggono l'ala sotto al muso
    for lato in (-1, 1):
        m.trave((2.70, 0.085, lato * 0.06), (2.70, 0.22, lato * 0.05), 0.012, CARBONIO)

    # l'ala posteriore: piano, flap, trave bassa, paratie e il supporto centrale
    m.scatola(-2.62, -2.30, 0.80, 0.845, -0.50, 0.50, LIVREA)
    m.scatola(-2.76, -2.52, 0.885, 0.925, -0.50, 0.50, SECONDA)
    m.scatola(-2.52, -2.32, 0.40, 0.43, -0.42, 0.42, CARBONIO)
    for lato in (-1, 1):
        m.piastra([(-2.26, 0.42), (-2.80, 0.42), (-2.80, 0.98), (-2.62, 1.02), (-2.30, 0.95)],
                  0.02, LIVREA, lato * 0.51)
    m.trave((-2.36, 0.34, 0.0), (-2.46, 0.80, 0.0), 0.025, CARBONIO)
    # la luce rossa di sicurezza sotto la trave, e lo scarico
    m.scatola(-2.50, -2.46, 0.33, 0.39, -0.05, 0.05, SECONDA)
    m.cilindro_z(-2.40, 0.40, -0.05, 0.05, 0.05, CARBONIO, 10)

    # le ruote e le sospensioni
    for x, larga, attacco_y in ((fronte, 0.30, (0.30, 0.46)), (retro, 0.385, (0.26, 0.42))):
        for lato in (-1, 1):
            zc = lato * CARREGGIATA / 2
            z0, z1 = zc - larga / 2, zc + larga / 2
            m.ruota(x, RAGGIO_RUOTA, z0, z1, lato, GOMMA, CERCHIO)
            interno = zc - lato * larga / 2
            corpo = 0.22 if x > 0 else 0.20
            for y in attacco_y:
                m.trave((x + 0.30, y - 0.06, lato * corpo), (x, y, interno), 0.017, CARBONIO)
                m.trave((x - 0.28, y - 0.06, lato * corpo), (x, y, interno), 0.017, CARBONIO)
            # il tirante dello sterzo o del push rod
            m.trave((x + 0.05, 0.50 if x > 0 else 0.46, lato * corpo), (x, 0.28, interno),
                    0.014, CARBONIO)
    return m.vertici()


_MESH = [None]


def mesh() -> array:
    """La monoposto, costruita una volta sola."""
    if _MESH[0] is None:
        _MESH[0] = costruisci()
    return _MESH[0]


# ------------------------------------------------------------ la Gen3
# La Formula E del 2026, la Gen3 Evo: piu' corta, piu' stretta e piu' bassa di
# una Formula 1 - cinque metri, un metro e settanta, passo 2,97 - e fatta a
# spigoli. Il muso basso e piatto con l'ala larga davanti alle ruote, niente
# presa d'aria sopra la testa (non c'e' niente da far respirare), le pance
# strette e squadrate, e dietro le carenature che coprono le ruote posteriori,
# unite dall'ala bassa. Le ruote sono piu' piccole, con la spalla alta.
PASSO_FE = 2.97
CARREGGIATA_FE = 1.44
RAGGIO_RUOTA_FE = 0.33
RAGGIO_CERCHIO_FE = 0.215
LUNGHEZZA_FE = 5.02


def costruisci_fe() -> array:
    m = _Mesh()
    fronte, retro = PASSO_FE / 2, -PASSO_FE / 2
    # la scocca: il muso piatto e largo che scende quasi a terra, l'abitacolo,
    # il roll-bar sopra la testa e il cofano che cala fino al fondo
    scocca = [
        (2.56, 0.16, 0.12, 0.09, 0.19),
        (2.30, 0.18, 0.13, 0.10, 0.27),
        (1.90, 0.20, 0.15, 0.11, 0.37),
        (1.40, 0.23, 0.18, 0.12, 0.49),
        (0.95, 0.27, 0.22, 0.10, 0.60),
        (0.50, 0.31, 0.26, 0.10, 0.65),
        (0.05, 0.34, 0.27, 0.10, 0.67),
        (-0.28, 0.33, 0.10, 0.10, 0.96),
        (-0.50, 0.31, 0.10, 0.10, 0.90),
        (-0.95, 0.26, 0.10, 0.10, 0.72),
        (-1.45, 0.20, 0.08, 0.12, 0.54),
        (-1.95, 0.14, 0.07, 0.15, 0.42),
        (-2.22, 0.10, 0.05, 0.18, 0.36),
    ]
    m.loft([(x, _sezione(wb, wt, y0, y1, 2.2)) for x, wb, wt, y0, y1 in scocca], LIVREA,
           LIVREA, CARBONIO)
    # l'abitacolo, il pilota, l'halo
    m.loft([(0.50, _sezione(0.21, 0.23, 0.50, 0.672, 3.0, 12)),
            (0.10, _sezione(0.24, 0.26, 0.50, 0.682, 3.0, 12)),
            (-0.22, _sezione(0.23, 0.23, 0.50, 0.70, 3.0, 12))], CARBONIO, CARBONIO, CARBONIO)
    m.sfera((0.02, 0.76, 0.0), 0.15, 0.14, 0.13, CASCO)
    anello = []
    for k in range(15):
        t = math.radians(-105 + 210 * k / 14)
        anello.append((0.03 + 0.33 * math.cos(t), 0.88 - 0.03 * (1 - math.cos(t)),
                       0.26 * math.sin(t)))
    for a, b in zip(anello, anello[1:]):
        m.trave(a, b, 0.027, HALO)
    m.trave((0.42, 0.65, 0.0), anello[7], 0.03, HALO)
    for estremo in (anello[0], anello[-1]):
        m.trave(estremo, (estremo[0] - 0.04, 0.66, estremo[2] * 1.02), 0.027, HALO)
    # gli specchietti
    for lato in (-1, 1):
        m.scatola(0.38, 0.46, 0.68, 0.76, *sorted((lato * 0.44, lato * 0.58)), SECONDA)
        m.trave((0.42, 0.64, lato * 0.28), (0.42, 0.71, lato * 0.45), 0.012, CARBONIO)

    # le pance: strette, squadrate, con lo spigolo in alto che scende dietro
    for lato in (-1, 1):
        def pancia(x, zi, zo, y0, y1):
            sez = [(y0 + 0.06, zi), (y0, zi + (zo - zi) * 0.5), (y0 + 0.04, zo),
                   (y1 - 0.10, zo), (y1, zo - 0.10), (y1, zi)]
            return (x, [(y, lato * z) for y, z in sez])
        sezioni = [pancia(0.80, 0.27, 0.50, 0.26, 0.48), pancia(0.50, 0.28, 0.64, 0.16, 0.52),
                   pancia(0.00, 0.28, 0.66, 0.15, 0.50), pancia(-0.55, 0.26, 0.58, 0.15, 0.42),
                   pancia(-1.05, 0.22, 0.42, 0.15, 0.33), pancia(-1.35, 0.18, 0.26, 0.15, 0.25)]
        m.loft(sezioni, SECONDA, CARBONIO, None)

    # il fondo piatto
    fondo = [(1.20, 0.34), (0.90, 0.62), (-1.10, 0.66), (-1.40, 0.50), (-2.10, 0.46)]
    for (xa, wa), (xb, wb) in zip(fondo, fondo[1:]):
        m.quad((xa, 0.035, -wa), (xa, 0.035, wa), (xb, 0.035, wb), (xb, 0.035, -wb),
               CARBONIO, ((xa + xb) / 2, 1.0, 0.0))
        m.quad((xa, 0.06, -wa), (xa, 0.06, wa), (xb, 0.06, wb), (xb, 0.06, -wb),
               CARBONIO, ((xa + xb) / 2, -1.0, 0.0))
    m.quad((-1.60, 0.06, -0.44), (-1.60, 0.06, 0.44), (-2.20, 0.22, 0.44),
           (-2.20, 0.22, -0.44), CARBONIO, (-1.9, 0.0, 0.0))

    # l'ala anteriore: larga quanto la macchina, davanti alle ruote, col bordo
    # che rientra verso i lati; sopra, un secondo profilo corto
    m.scatola(2.24, 2.60, 0.05, 0.08, -0.30, 0.30, LIVREA)
    for lato in (-1, 1):
        a, b = sorted((lato * 0.30, lato * 0.84))
        m.scatola(2.14, 2.50, 0.05, 0.08, a, b, LIVREA)
        a, b = sorted((lato * 0.34, lato * 0.80))
        m.scatola(2.16, 2.34, 0.12, 0.145, a, b, SECONDA)
        m.piastra([(2.06, 0.04), (2.52, 0.04), (2.52, 0.10), (2.30, 0.24), (2.06, 0.24)],
                  0.02, LIVREA, lato * 0.845)
    for lato in (-1, 1):
        m.trave((2.42, 0.08, lato * 0.08), (2.42, 0.16, lato * 0.07), 0.012, CARBONIO)

    # dietro: le carenature che coprono le ruote posteriori da dietro, e l'ala
    # bassa che le unisce, con il supporto al centro
    larga_post = 0.30
    for lato in (-1, 1):
        zc = lato * CARREGGIATA_FE / 2
        m.piastra([(-1.84, 0.06), (-2.28, 0.06), (-2.30, 0.44), (-2.12, 0.66), (-1.76, 0.66),
                   (-1.86, 0.48)], larga_post + 0.04, LIVREA, zc)
    m.scatola(-2.32, -2.06, 0.66, 0.70, -0.86, 0.86, LIVREA)
    m.scatola(-2.38, -2.26, 0.73, 0.76, -0.72, 0.72, SECONDA)
    m.trave((-2.10, 0.38, 0.0), (-2.20, 0.68, 0.0), 0.03, CARBONIO)
    m.scatola(-2.28, -2.24, 0.30, 0.36, -0.05, 0.05, SECONDA)

    # le ruote, piu' piccole e con la spalla alta, e le sospensioni
    raggi = (RAGGIO_RUOTA_FE, RAGGIO_CERCHIO_FE)
    for x, larga, attacco_y in ((fronte, 0.26, (0.28, 0.42)), (retro, larga_post, (0.25, 0.40))):
        for lato in (-1, 1):
            zc = lato * CARREGGIATA_FE / 2
            z0, z1 = zc - larga / 2, zc + larga / 2
            m.ruota(x, RAGGIO_RUOTA_FE, z0, z1, lato, GOMMA, CERCHIO, raggi=raggi)
            interno = zc - lato * larga / 2
            corpo = 0.21 if x > 0 else 0.19
            for y in attacco_y:
                m.trave((x + 0.28, y - 0.05, lato * corpo), (x, y, interno), 0.016, CARBONIO)
                m.trave((x - 0.26, y - 0.05, lato * corpo), (x, y, interno), 0.016, CARBONIO)
            m.trave((x + 0.05, 0.46 if x > 0 else 0.42, lato * corpo), (x, 0.26, interno),
                    0.013, CARBONIO)
    return m.vertici()


_MESH_FE = [None]


def mesh_fe() -> array:
    """La Gen3 di Formula E, costruita una volta sola."""
    if _MESH_FE[0] is None:
        _MESH_FE[0] = costruisci_fe()
    return _MESH_FE[0]
