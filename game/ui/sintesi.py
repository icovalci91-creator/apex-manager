"""I suoni del gioco, fatti dal codice.

Come la monoposto in 3D, nemmeno il suono si scarica: si sintetizza qui, con
numpy, all'avvio. Tre famiglie:

- il motore, che si genera mentre si guarda, un pezzetto alla volta
  (`Motore`): il V6 turbo ibrido del 2026 - la nota di scoppio, la raspa dei
  mezzi ordini, il fischio del turbo, il sibilo dell'MGU-K, i cambi marcia, gli
  scoppiettii in rilascio - o il motore elettrico della Formula E;
- i fondi che girano in loop senza cucitura (la folla, la pioggia, il vento,
  il rombo lontano del gruppo), filtrati in frequenza su tutto il giro cosi'
  la fine combacia con l'inizio;
- i colpi singoli (il clic, il passaggio di pagina, il semaforo, la partenza,
  la bandiera a scacchi) e la musica del menu.

Ogni funzione restituisce campioni in virgola mobile fra -1 e 1: e' `audio`
a farli diventare suoni di pygame.
"""
from __future__ import annotations

import math

import numpy as np

DUE_PI = 2.0 * math.pi


# ------------------------------------------------------------------ attrezzi
def _rng(seme: int):
    return np.random.default_rng(seme)


def filtra(x, sr: int, basso: float | None = None, alto: float | None = None,
           picco=None, circolare: bool = True):
    """Taglia le frequenze con la trasformata di Fourier.

    `basso`: lascia passare sotto questa frequenza; `alto`: sopra; `picco`:
    (frequenza, larghezza relativa, guadagno) di una campana in piu'. Sul giro
    intero il filtro e' circolare - perfetto per i loop; per un colpo singolo
    si allunga di un po' di silenzio perche' la coda non rientri dall'inizio.
    """
    n = len(x)
    if not circolare:
        x = np.concatenate([x, np.zeros(int(sr * 0.25))])
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    g = np.ones_like(f)
    if alto:
        g *= 1.0 / (1.0 + (alto / np.maximum(f, 1.0)) ** 4)
    if basso:
        g *= 1.0 / (1.0 + (f / basso) ** 4)
    if picco:
        fc, larga, guadagno = picco
        g *= 1.0 + guadagno * np.exp(-((f - fc) / (fc * larga)) ** 2)
    y = np.fft.irfft(X * g, len(x))
    return y[:n]


def normalizza(x, picco: float = 0.9):
    m = float(np.max(np.abs(x))) or 1.0
    return x * (picco / m)


def cuci(x, sr: int, dissolvenza: float = 0.5):
    """Un loop senza scatto: l'ultimo mezzo secondo si sfuma sull'inizio."""
    m = int(sr * dissolvenza)
    corpo = x[:-m].copy()
    rampa = np.linspace(0.0, 1.0, m)
    corpo[:m] = corpo[:m] * rampa + x[-m:] * (1.0 - rampa)
    return corpo


def _inviluppo(n: int, sr: int, attacco: float, decadimento: float):
    t = np.arange(n) / sr
    a = np.minimum(1.0, t / max(1e-4, attacco))
    return a * np.exp(-t / max(1e-4, decadimento))


def _metti(dst, src, dove: int, circolare: bool = True):
    """Somma `src` in `dst` a partire da `dove`, girando in fondo se serve."""
    n = len(dst)
    fine = dove + len(src)
    if fine <= n:
        dst[dove:fine] += src
    elif circolare:
        k = n - dove
        dst[dove:] += src[:k]
        dst[:fine - n] += src[k:]
    else:
        dst[dove:] += src[:n - dove]


def _leggi(tavola, fase):
    """Legge una tavola d'onda (un ciclo) con l'interpolazione lineare."""
    n = len(tavola)
    p = (fase % 1.0) * n
    i = p.astype(np.int64)
    u = p - i
    return tavola[i % n] * (1.0 - u) + tavola[(i + 1) % n] * u


def _nota(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


# ------------------------------------------------------------------ il motore
TAVOLA = 4096
GIRI_MAX = 12000.0
# velocita' (m/s) a GIRI_MAX in ogni marcia: otto marce, 345 all'ora in ottava
MARCE = np.array([105.0, 140.0, 172.0, 203.0, 233.0, 262.0, 292.0, 332.0]) / 3.6


def tavola_motore(seme: int, carico: float):
    """Un ciclo del V6 (due giri d'albero): i sei scoppi e tutto il resto.

    Gli ordini multipli di sei sono gli scoppi, i multipli di tre la
    pulsazione di ogni bancata, gli altri le piccole differenze fra un
    cilindro e l'altro, che fanno la raspa. Sotto carico si accende la banda
    dei 2-4 kHz; in rilascio il suono si scurisce.
    """
    rng = _rng(seme)
    k = np.arange(1, 97)
    a = rng.uniform(0.35, 1.0, len(k)) / k ** 0.55
    a[k % 3 == 0] *= 1.5
    a[k % 6 == 0] *= 2.6
    a *= 1.0 + 1.6 * carico * np.exp(-((k - 30) / 12.0) ** 2)
    if carico < 0.5:
        a *= np.exp(-k / 26.0)
    fasi = rng.uniform(0.0, DUE_PI, len(k))
    t = np.arange(TAVOLA) / TAVOLA
    w = (a[:, None] * np.sin(DUE_PI * k[:, None] * t[None, :] + fasi[:, None])).sum(0)
    return w / np.max(np.abs(w))


class Motore:
    """Una monoposto che suona: si chiede un pezzo alla volta.

    `blocco(n, velocita, accelerazione)` restituisce n campioni: dalla velocita'
    si ricavano marcia e giri, dall'accelerazione se si e' sul gas. Fra un
    pezzo e l'altro la fase continua, cosi' non si sente la cucitura.
    """

    def __init__(self, sr: int, seme: int = 1, elettrico: bool = False):
        self.sr = sr
        self.elettrico = elettrico
        self.rng = _rng(seme)
        self.on = tavola_motore(seme, 1.0)
        self.off = tavola_motore(seme + 7, 0.0)
        self.fase = 0.0
        self.fase_turbo = 0.0
        self.fase_k = 0.0
        self.fasi_e = np.zeros(4)
        self.giri = 9000.0
        self.marcia = 3
        self.gas = 1.0
        self.v = 0.0
        self.ultimo_rumore = 0.0
        self.pausa_scoppi = 0.0
        self.tempo = 0.0

    def salta(self, v: float) -> None:
        """Un'altra macchina (uno stacco di regia): niente scivolata di giri."""
        self.v = v
        self.marcia = int(np.searchsorted(MARCE, v * 1.12)) + 1
        self.marcia = max(1, min(8, self.marcia))
        self.giri = self._giri(v, self.marcia, 1.0)

    def _giri(self, v: float, marcia: int, gas: float) -> float:
        g = GIRI_MAX * v / MARCE[marcia - 1]
        if v < 2.0 and gas > 0.5:
            # fermi sulla griglia, col piede che non sta fermo: sgasate
            t = self.tempo
            return 9300.0 + 1400.0 * math.sin(DUE_PI * 0.55 * t) + 700.0 * math.sin(DUE_PI * 1.9 * t)
        # dalla frizione in su tiene il motore alto: si parte a settemila
        return max(g, 7200.0 if gas > 0.5 else 4600.0)

    def blocco(self, n: int, v: float, accel: float, doppler: float = 1.0):
        sr = self.sr
        v = max(0.0, v)
        self.tempo += n / sr
        gas_meta = 1.0 if accel > -4.0 else 0.0
        g0 = self.gas
        self.gas = g1 = g0 + (gas_meta - g0) * 0.45
        if self.elettrico:
            x = self._elettrico(n, v, g0, g1, doppler)
            self.v = v
            return x
        cambio = False
        for _ in range(2):
            giri = GIRI_MAX * v / MARCE[self.marcia - 1]
            if gas_meta and giri > 11700 and self.marcia < 8:
                self.marcia += 1
                cambio = True
            elif giri < (7400 if not gas_meta else 8200) and self.marcia > 1:
                self.marcia -= 1
                cambio = True
        meta = self._giri(v, self.marcia, g1)
        r0 = meta if cambio else self.giri
        giri = np.linspace(r0, meta, n)
        self.giri = meta
        fc = giri / 120.0 * doppler
        fase = self.fase + np.cumsum(fc) / sr
        self.fase = float(fase[-1] % 1.0)
        sopra = _leggi(self.on, fase)
        sotto = _leggi(self.off, fase)
        g = np.linspace(g0, g1, n)
        x = sopra * g + sotto * (1.0 - g) * 0.65
        # la raspa dello scarico: rumore che batte con gli scoppi
        rumore = self.rng.standard_normal(n)
        rumore = np.diff(np.concatenate(([self.ultimo_rumore], rumore)))
        self.ultimo_rumore = float(rumore[-1])
        x += rumore * 0.05 * (0.35 + g) * (0.4 + np.abs(sopra))
        # il turbo fischia sopra a tutto, piu' forte quando spinge
        ft = (2600.0 + 2600.0 * g * giri / GIRI_MAX) * doppler
        ph = self.fase_turbo + np.cumsum(ft) / sr
        self.fase_turbo = float(ph[-1] % 1.0)
        x += 0.03 * g * np.sin(DUE_PI * ph)
        # l'MGU-K: un sibilo che sale con la velocita'
        fk = (60.0 + v * 40.0) * doppler
        ph = self.fase_k + np.arange(1, n + 1) * fk / sr
        self.fase_k = float(ph[-1] % 1.0)
        x += 0.018 * np.sin(DUE_PI * ph) * min(1.0, v / 30.0)
        # in rilascio, gli scoppiettii
        self.pausa_scoppi -= n / sr
        if g1 < 0.35 and self.pausa_scoppi <= 0.0:
            for _ in range(int(self.rng.integers(1, 4))):
                dove = int(self.rng.integers(0, max(1, n - 400)))
                lungo = int(sr * 0.006)
                colpo = self.rng.standard_normal(lungo) * np.exp(-np.arange(lungo) / (lungo / 4))
                x[dove:dove + lungo] += colpo[:len(x[dove:dove + lungo])] * 0.55
            self.pausa_scoppi = float(self.rng.uniform(0.05, 0.25))
        if cambio:
            # il cambio senza interruzione del 2026: un respiro di trenta millesimi
            m = min(n, int(sr * 0.03))
            x[:m] *= np.linspace(0.4, 1.0, m)
        self.v = v
        return x * (0.6 + 0.4 * g)

    def _elettrico(self, n, v, g0, g1, doppler):
        """Il motore della Formula E: il sibilo che sale con la velocita', le
        armoniche dell'inverter, gli ingranaggi, il vento e le gomme."""
        sr = self.sr
        v0 = self.v
        vv = np.linspace(v0, v, n)
        base = (40.0 + vv * 24.0) * doppler
        x = np.zeros(n)
        for j, (mult, amp) in enumerate(((1.0, 0.55), (2.0, 0.28), (3.0, 0.12), (4.7, 0.10))):
            ph = self.fasi_e[j] + np.cumsum(base * mult) / sr
            self.fasi_e[j] = float(ph[-1] % 1.0)
            x += amp * np.sin(DUE_PI * ph)
        g = np.linspace(g0, g1, n)
        # in frenata la rigenerazione cambia voce: meno fondamentale, piu' seconda
        x *= 0.55 + 0.45 * g
        rumore = self.rng.standard_normal(n)
        k = 12
        liscio = np.convolve(rumore, np.ones(k) / k, mode="same")
        x += liscio * (0.05 + 0.25 * min(1.0, (v / 80.0) ** 2))
        return x * 0.8


# ------------------------------------------------------------------ i fondi
def folla(sr: int, secondi: float = 8.0, seme: int = 3):
    """Il brusio delle tribune: rumore nella banda della voce, che respira."""
    rng = _rng(seme)
    n = int(sr * secondi)
    x = filtra(rng.standard_normal(n), sr, basso=2600, alto=180, picco=(650, 0.8, 2.0))
    lento = filtra(rng.standard_normal(n), sr, basso=1.5)
    lento = 1.0 + 0.6 * lento / (np.max(np.abs(lento)) or 1.0)
    return normalizza(x * lento, 0.7)


def pioggia(sr: int, secondi: float = 6.0, seme: int = 5):
    rng = _rng(seme)
    n = int(sr * secondi)
    x = filtra(rng.standard_normal(n), sr, alto=1800, basso=9000) * 0.6
    gocce = np.zeros(n)
    for dove in rng.integers(0, n, int(secondi * 260)):
        gocce[dove] += rng.uniform(0.3, 1.0)
    x += filtra(gocce, sr, alto=2500, basso=7000) * 2.5
    return normalizza(x, 0.6)


def vento(sr: int, secondi: float = 5.0, seme: int = 9):
    rng = _rng(seme)
    n = int(sr * secondi)
    x = filtra(rng.standard_normal(n), sr, basso=500, alto=40)
    lento = filtra(rng.standard_normal(n), sr, basso=0.8)
    lento = 1.0 + 0.5 * lento / (np.max(np.abs(lento)) or 1.0)
    return normalizza(x * lento, 0.7)


def campo(sr: int, secondi: float = 10.0, seme: int = 11):
    """Il gruppo che gira lontano: qualche motore, smorzato dalla distanza."""
    rng = _rng(seme)
    n = int(sr * (secondi + 0.6))
    blocco = 2048
    somma = np.zeros(n)
    for k in range(6):
        m = Motore(sr, seme + k * 13)
        periodo = rng.uniform(4.0, 9.0)
        faseq = rng.uniform(0, DUE_PI)
        pezzi = []
        for i in range(0, n, blocco):
            t = i / sr
            v = 62.0 + 16.0 * math.sin(DUE_PI * t / periodo + faseq)
            a = 16.0 * DUE_PI / periodo * math.cos(DUE_PI * t / periodo + faseq)
            pezzi.append(m.blocco(min(blocco, n - i), v, a))
        voce = np.concatenate(pezzi)
        inv = 0.4 + 0.6 * (0.5 + 0.5 * np.sin(DUE_PI * np.arange(n) / sr / periodo * 0.5 + faseq))
        somma += voce * inv
    x = cuci(somma, sr, 0.6)
    return normalizza(filtra(x, sr, basso=900, alto=60), 0.7)


# ------------------------------------------------------------------ colpi
def clic(sr: int):
    n = int(sr * 0.03)
    rng = _rng(21)
    t = np.arange(n) / sr
    x = np.sin(DUE_PI * 2300 * t) * np.exp(-t / 0.004) * 0.6
    x += rng.standard_normal(n) * np.exp(-t / 0.0015) * 0.3
    return normalizza(filtra(x, sr, alto=900, circolare=False), 0.5)


def sfiora(sr: int):
    n = int(sr * 0.02)
    t = np.arange(n) / sr
    return np.sin(DUE_PI * 3800 * t) * np.exp(-t / 0.003) * 0.25


def passa(sr: int, secondi: float = 0.45, seme: int = 23):
    """Il fruscio del passaggio di pagina: dal cupo all'acuto."""
    rng = _rng(seme)
    n = int(sr * secondi)
    r = rng.standard_normal(n)
    cupo = filtra(r, sr, basso=700, circolare=False)
    acuto = filtra(r, sr, alto=2400, basso=9000, circolare=False)
    u = np.linspace(0.0, 1.0, n)
    x = cupo * (1.0 - u) + acuto * u * 0.8
    return normalizza(x * np.sin(np.pi * u) ** 2, 0.55)


def avviso(sr: int):
    n = int(sr * 0.5)
    x = np.zeros(n)
    for dove, f in ((0.0, 880.0), (0.09, 1320.0)):
        i = int(sr * dove)
        m = n - i
        t = np.arange(m) / sr
        x[i:] += (np.sin(DUE_PI * f * t) + 0.2 * np.sin(DUE_PI * 2 * f * t)) * _inviluppo(m, sr, 0.004, 0.12)
    eco = np.zeros(n)
    k = int(sr * 0.11)
    eco[k:] = x[:-k] * 0.3
    return normalizza(x + eco, 0.4)


def luce(sr: int):
    n = int(sr * 0.22)
    t = np.arange(n) / sr
    x = np.sin(DUE_PI * 660 * t) + 0.3 * np.sin(DUE_PI * 1980 * t)
    return normalizza(x * _inviluppo(n, sr, 0.005, 0.07), 0.45)


def partenza(sr: int, secondi: float = 5.5, seme: int = 31):
    """Il semaforo si spegne: venti motori che partono insieme."""
    rng = _rng(seme)
    n = int(sr * secondi)
    blocco = 1024
    sx = np.zeros(n)
    dx = np.zeros(n)
    for k in range(10):
        m = Motore(sr, seme + k * 17)
        spinta = rng.uniform(7.5, 10.0)
        ritardo = rng.uniform(0.0, 0.25)
        pezzi = []
        for i in range(0, n, blocco):
            t = max(0.0, i / sr - ritardo)
            v = min(85.0, spinta * t * (1.0 - t / 30.0))
            pezzi.append(m.blocco(min(blocco, n - i), v, spinta))
        voce = np.concatenate(pezzi) * rng.uniform(0.6, 1.0)
        pan = rng.uniform(-0.8, 0.8)
        sx += voce * (1.0 - pan) * 0.5
        dx += voce * (1.0 + pan) * 0.5
    u = np.linspace(0.0, 1.0, n)
    inv = np.minimum(1.0, u / 0.03) * np.where(u > 0.55, 1.0 - (u - 0.55) / 0.45, 1.0)
    sx, dx = sx * inv, dx * inv
    m = max(np.max(np.abs(sx)), np.max(np.abs(dx))) or 1.0
    return np.stack([sx, dx], 1) * (0.85 / m)


def applausi(sr: int, secondi: float = 4.5, seme: int = 41):
    """Le tribune in piedi: mani, urla, qualche fischio."""
    rng = _rng(seme)
    n = int(sr * secondi)
    mani = np.zeros(n)
    for dove in rng.integers(0, n, int(secondi * 900)):
        mani[dove] += rng.uniform(0.2, 1.0)
    colpo = rng.standard_normal(int(sr * 0.012)) * np.exp(-np.arange(int(sr * 0.012)) / (sr * 0.002))
    mani = np.convolve(mani, colpo, mode="same")
    x = filtra(mani, sr, alto=900, basso=5000, circolare=False)
    x = normalizza(x, 0.5) + folla(sr, secondi, seme) * 0.7
    for _ in range(5):
        i = int(rng.integers(0, n - sr))
        m = int(sr * rng.uniform(0.4, 0.8))
        f = np.linspace(rng.uniform(1700, 2100), rng.uniform(2400, 3000), m)
        fischio = np.sin(DUE_PI * np.cumsum(f) / sr) * np.sin(np.linspace(0, np.pi, m)) * 0.15
        x[i:i + m] += fischio
    u = np.linspace(0.0, 1.0, n)
    return normalizza(x * np.minimum(1.0, u / 0.12) * np.minimum(1.0, (1.0 - u) / 0.35), 0.8)


def fanfara(sr: int):
    """Quattro note d'ottone e l'accordo: si vince."""
    n = int(sr * 2.6)
    x = np.zeros(n)
    passi = [(0.00, [60], 0.16), (0.16, [64], 0.16), (0.32, [67], 0.16),
             (0.48, [72, 64, 67, 48], 1.9)]
    for dove, note, lungo in passi:
        i = int(sr * dove)
        m = min(n - i, int(sr * (lungo + 0.3)))
        t = np.arange(m) / sr
        inv = np.minimum(1.0, t / 0.02) * np.exp(-np.maximum(0.0, t - lungo) / 0.12)
        for nota in note:
            f = _nota(nota)
            voce = sum(np.sin(DUE_PI * f * k * t * (1 + 0.0015 * math.sin(k))) / k ** 1.1
                       * (1.0 - math.exp(-k / 2.5)) for k in range(1, 12))
            x[i:i + m] += voce * inv * (0.8 if len(note) > 1 else 1.0)
    return normalizza(filtra(x, sr, basso=3500, circolare=False), 0.6)


# ------------------------------------------------------------------ la musica
def musica(sr: int, seme: int = 7):
    """Il tema del menu: otto battute in la minore, da ripetere all'infinito.

    Il pad (seghe leggermente scordate fra loro), il basso a ottavi, l'arpeggio
    in sedicesimi con l'eco che rimbalza da un lato all'altro, cassa dritta,
    rullante sul due e sul quattro, charleston in levare. Tutto si scrive
    girando in fondo al giro, cosi' la fine attacca sull'inizio.
    """
    rng = _rng(seme)
    bpm = 104.0
    battito = 60.0 / bpm
    battuta = 4 * battito
    L = int(sr * battuta * 8)
    sx = np.zeros(L)
    dx = np.zeros(L)
    giro = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [52, 55, 60]), (55, [55, 59, 62])] * 2

    def mono(dst_s, dst_d, voce, dove, pan=0.0):
        _metti(dst_s, voce * (1.0 - pan) * 0.5, dove)
        _metti(dst_d, voce * (1.0 + pan) * 0.5, dove)

    # il pad
    lungo = int(sr * (battuta + 0.8))
    t = np.arange(lungo) / sr
    inv = np.minimum(1.0, t / 0.6) * np.where(t > battuta, np.exp(-(t - battuta) / 0.3), 1.0)
    for b, (_, accordo) in enumerate(giro):
        dove = int(sr * battuta * b)
        for j, nota in enumerate(accordo):
            f = _nota(nota + 12)
            for scordo, pan in ((0.9985, -0.6), (1.0015, 0.6)):
                voce = sum(np.sin(DUE_PI * f * scordo * k * t + k) / k * math.exp(-k / 6.0)
                           for k in range(1, 13))
                mono(sx, dx, voce * inv * 0.10, dove, pan * (0.4 + 0.3 * j))
    # il basso
    ottavo = battito / 2
    lungo = int(sr * ottavo)
    t = np.arange(lungo) / sr
    for b, (radice, _) in enumerate(giro):
        f = _nota(radice - 12)
        for o in range(8):
            voce = sum(np.sin(DUE_PI * f * k * t) / k * np.exp(-t * k * 9.0) for k in (1, 3, 5, 7))
            voce *= np.minimum(1.0, t / 0.004) * np.exp(-t / 0.16)
            mono(sx, dx, voce * 0.42, int(sr * (battuta * b + ottavo * o)))
    # l'arpeggio, con l'eco che rimbalza
    sedicesimo = battito / 4
    lungo = int(sr * 0.35)
    t = np.arange(lungo) / sr
    arp_s = np.zeros(L)
    arp_d = np.zeros(L)
    schema = [0, 1, 2, 1, 2, 3, 2, 1] * 2
    for b, (_, accordo) in enumerate(giro):
        note = accordo + [accordo[0] + 12]
        for s in range(16):
            if b < 2 and s % 2:
                continue
            f = _nota(note[schema[s]] + 24)
            voce = (np.sin(DUE_PI * f * t) + 0.3 * np.sin(DUE_PI * 2 * f * t)) * np.exp(-t / 0.08)
            mono(arp_s, arp_d, voce * 0.13, int(sr * (battuta * b + sedicesimo * s)), 0.2)
    eco = int(sr * sedicesimo * 3)
    sx += arp_s + np.roll(arp_d, eco) * 0.45
    dx += arp_d + np.roll(arp_s, eco) * 0.45
    # la batteria
    t = np.arange(int(sr * 0.4)) / sr
    cassa = np.sin(DUE_PI * np.cumsum(45.0 + 90.0 * np.exp(-t / 0.035)) / sr) * np.exp(-t / 0.2)
    tr = np.arange(int(sr * 0.25)) / sr
    rullante = (filtra(rng.standard_normal(len(tr)), sr, alto=1500, circolare=False) * 0.6
                + np.sin(DUE_PI * 190 * tr) * 0.4) * np.exp(-tr / 0.09)
    th = np.arange(int(sr * 0.06)) / sr
    charleston = filtra(rng.standard_normal(len(th)), sr, alto=7000, circolare=False) * np.exp(-th / 0.02)
    for b in range(8):
        for q in range(4):
            dove = int(sr * (battuta * b + battito * q))
            mono(sx, dx, cassa * 0.75, dove)
            if q in (1, 3):
                mono(sx, dx, rullante * 0.45, dove, 0.1)
            if b >= 2:
                mono(sx, dx, charleston * 0.18, dove + int(sr * ottavo), -0.3)
    y = np.stack([sx, dx], 1)
    y = np.tanh(y * 1.3)
    return y * (0.85 / (np.max(np.abs(y)) or 1.0))
