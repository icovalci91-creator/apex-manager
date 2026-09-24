"""Il regista televisivo: chi si guarda, da dove, e i replay dei sorpassi.

La vista 3D dall'elicottero e' la mappa di chi comanda il muretto. La regia
e' la gara come la si vede in televisione: una telecamera a bordo pista che
aspetta la macchina in fondo al rettilineo e la segue col teleobiettivo, la
camera car che le sta dietro, la camera sopra l'airbox, l'elicottero che le
gira attorno. Il regista sceglie chi guardare - una battaglia prima di
tutto, poi chi comanda, poi le macchine di casa - e stacca quando
l'inquadratura ha detto quello che doveva.

Quando qualcuno passa, pochi secondi dopo arriva il replay: la staccata
rivista al rallentatore dal bordo pista, e poi dall'abitacolo di chi ha
attaccato. Per rivederla la regia tiene a mente l'ultimo minuto e mezzo di
gara, macchina per macchina.

Qui non c'e' niente di OpenGL: le telecamere dicono solo da dove si guarda,
verso dove e con che obiettivo. Disegna `vista3d`.
"""
from __future__ import annotations

import bisect
import math
import random

from . import pista3d

# quanto ricorda il registro, in secondi di gara, e ogni quanto prende nota
REGISTRO_S = 90.0
PASSO_REGISTRO = 0.04

# i salti: la gara sposta le macchine a strappi quando una passa l'altra (chi
# attacca si ritrova davanti di colpo). Sullo schermo lo strappo diventa una
# spinta che si smaltisce in SALTO_S secondi; oltre SALTO_MAX_M metri non e'
# un sorpasso, e' un'altra cosa (i box, un nuovo turno) e si salta e basta
SALTO_MIN_M = 1.2
SALTO_MAX_M = 80.0
SALTO_S = 0.7

# i replay: quanto aspettare prima di farlo partire, quanto lasciar passare
# fra uno e l'altro (in secondi veri), e sopra che velocita' della gara non
# si fanno piu': a x12 un replay si perderebbe mezzo giro
REPLAY_RITARDO = 1.6
REPLAY_PAUSA = 25.0
RITMO_REPLAY = 5.0

# sopra questa velocita' della gara le camere vicine non stanno dietro alle
# macchine: restano l'elicottero e il circuito
RITMO_VICINO = 6.0

# la telecamera a bordo pista: quanto dietro al muro e quanto in alto
BORDO_DIETRO_M = 3.0
BORDO_ALTO_M = 5.0

# una battaglia: due macchine a meno di questi metri
BATTAGLIA_M = 45.0

LONTANO_M = 2500.0
LARGA_M = 2.0               # la monoposto vista di fronte, con le ruote


def lunghezza(geo) -> float:
    """Il giro in metri, misurato sul nastro della geometria."""
    lungo = getattr(geo, "_lungo_regia", None)
    if lungo is None:
        P = geo.P
        lungo = sum(math.hypot(P[i][0] - P[i - 1][0], P[i][2] - P[i - 1][2])
                    for i in range(len(P)))
        lungo = geo._lungo_regia = max(100.0, lungo)
    return lungo


def _avanti(a: float, b: float, lungo: float) -> float:
    """Di quanti metri b sta davanti ad a, sul giro (negativo: dietro)."""
    return ((b - a + 0.5) % 1.0 - 0.5) * lungo


def _punto(geo, f: float, lat: float, alto: float = 0.0):
    (x, y, z), fw = geo.sul_giro(f, lat)
    return (x, y + alto, z), fw


def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


# ------------------------------------------------------------ continuita'
class Continuita:
    """Toglie gli strappi dal moto delle macchine.

    La gara decide un sorpasso in un colpo: chi attacca si ritrova sei metri
    davanti, chi difende perde qualche metro. Sulla mappa non si nota, in una
    ripresa da vicino si': la macchina salterebbe in avanti. Qui lo strappo
    si mette da parte e si restituisce un po' alla volta, cosi' chi passa
    sembra prendere la scia e uscire dalla staccata piu' forte.
    """

    def __init__(self):
        self.stato: dict = {}      # chi -> [ultima frazione vera, scarto in metri, velocita']

    def applica(self, pos: dict, dt: float, lungo: float) -> dict:
        fuori = {}
        for chi, (f, lat) in pos.items():
            st = self.stato.get(chi)
            if st is None:
                st = self.stato[chi] = [f, 0.0, None]
            elif dt > 0:
                d = _avanti(st[0], f, lungo)
                v = st[2]
                messo_via = 0.0
                if v is not None:
                    extra = d - v * dt
                    if abs(extra) > max(SALTO_MIN_M, 0.35 * abs(v * dt)):
                        if abs(extra) < SALTO_MAX_M:
                            messo_via = extra
                            st[1] -= extra
                        else:
                            st[1] = 0.0
                            messo_via = d
                vn = (d - messo_via) / dt
                st[2] = vn if v is None else v + (vn - v) * min(1.0, dt * 6.0)
                st[0] = f
                st[1] *= math.exp(-dt / SALTO_S)
            fuori[chi] = ((f + st[1] / lungo) % 1.0, lat)
        for chi in [c for c in self.stato if c not in pos]:
            del self.stato[chi]
        return fuori

    def velocita(self, chi) -> float:
        st = self.stato.get(chi)
        return abs(st[2]) if st and st[2] is not None else 0.0


# ---------------------------------------------------------------- registro
class Registro:
    """Dove stava ogni macchina, istante per istante, nell'ultimo minuto e mezzo."""

    def __init__(self):
        self.tempi: list = []
        self.foto: list = []

    def aggiungi(self, t: float, pos: dict) -> None:
        if self.tempi:
            if t < self.tempi[-1] - 1.0:
                # il tempo e' tornato indietro: e' un'altra sessione
                self.tempi.clear()
                self.foto.clear()
            elif t - self.tempi[-1] < PASSO_REGISTRO:
                return
        self.tempi.append(t)
        self.foto.append(dict(pos))
        k = bisect.bisect_left(self.tempi, t - REGISTRO_S)
        if k > 200:
            del self.tempi[:k]
            del self.foto[:k]

    def inizio(self):
        return self.tempi[0] if self.tempi else None

    def a(self, t: float) -> dict:
        """Le posizioni all'istante t, fra una nota e l'altra."""
        if not self.tempi:
            return {}
        k = bisect.bisect_right(self.tempi, t)
        if k <= 0:
            return dict(self.foto[0])
        if k >= len(self.tempi):
            return dict(self.foto[-1])
        t0, t1 = self.tempi[k - 1], self.tempi[k]
        u = (t - t0) / max(1e-6, t1 - t0)
        A, B = self.foto[k - 1], self.foto[k]
        fuori = {}
        for chi, (f0, l0) in A.items():
            q = B.get(chi)
            if q is None:
                fuori[chi] = (f0, l0)
                continue
            f1, l1 = q
            df = (f1 - f0 + 0.5) % 1.0 - 0.5
            fuori[chi] = ((f0 + df * u) % 1.0, l0 + (l1 - l0) * u)
        return fuori


# --------------------------------------------------------------- telecamere
class _Camera:
    """Da dove si guarda. `inquadra` da' (occhio, bersaglio, vicino, lontano,
    angolo verticale, fuoco): il fuoco e' (forza, raggio) della sfocatura
    attorno al centro, per i teleobiettivi."""

    nome = ""

    def __init__(self, chi, altri=()):
        self.chi = chi
        self.altri = [c for c in altri if c and c != chi]

    def _centro(self, geo, pos):
        punti = [_punto(geo, *pos[c], 0.7)[0] for c in [self.chi] + self.altri if c in pos]
        if not punti:
            return None, 0.0
        c = tuple(sum(p[k] for p in punti) / len(punti) for k in range(3))
        largo = max((math.dist(punti[0], p) for p in punti[1:]), default=0.0)
        return c, largo

    def finita(self, geo, pos, trascorso: float) -> bool:
        return False


class Bordo(_Camera):
    """Il cameraman dietro al muro: aspetta la macchina e la segue col
    teleobiettivo, stringendo man mano che arriva."""

    nome = "BORDO PISTA"

    def __init__(self, geo, frazione: float, chi, altri=(), rng=None):
        super().__init__(chi, altri)
        n = geo.n
        self.f = frazione % 1.0
        i = int(self.f * n) % n
        lato = _lato_fuori(geo, i, rng)
        dist = pista3d.MEZZA_PISTA + pista3d.CORDOLO + geo.fuga + BORDO_DIETRO_M
        p, r = geo.P[i], geo.R[i]
        scelte = []
        for verso in (lato, -lato):
            x, z = p[0] + r[0] * verso * dist, p[2] + r[2] * verso * dist
            # dietro al muro, non in mezzo a un altro pezzo di pista
            libero = geo.vicino(x, z, dist + 10.0)[0]
            scelte.append((libero >= dist - 1.5, libero, x, z))
        buono = scelte[0] if scelte[0][0] or scelte[0][1] >= scelte[1][1] else scelte[1]
        _, _, x, z = buono
        y = max(geo.terra(x, z), p[1]) + BORDO_ALTO_M
        self.occhio = (x, y, z)
        self.fov = None

    def inquadra(self, geo, pos, dt, aspetto):
        centro, _ = self._centro(geo, pos)
        if centro is None:
            return None
        d = max(1.0, math.dist(self.occhio, centro))
        # la macchina (o le due che si battono) prende quattro decimi del
        # quadro, qualunque sia la distanza: e' il cameraman che zooma.
        # Conta quanto e' larga vista da qui: di fronte e' larga due metri,
        # di fianco cinque e mezzo
        vx, vz = centro[0] - self.occhio[0], centro[2] - self.occhio[2]
        vd = math.hypot(vx, vz) or 1.0
        vx, vz = vx / vd, vz / vd
        macchina, lato = 0.0, []
        for c in [self.chi] + self.altri:
            if c not in pos:
                continue
            (x, _, z), fw = geo.sul_giro(*pos[c])
            seno = abs(fw[0] * vz - fw[2] * vx)
            macchina = max(macchina, LARGA_M * math.sqrt(max(0.0, 1.0 - seno * seno))
                           + monoposto_lunga() * seno)
            lato.append(x * vz - z * vx)
        quadro = max(4.0, (macchina + (max(lato) - min(lato) if lato else 0.0)) / 0.42)
        fov = math.degrees(2.0 * math.atan(quadro / max(0.5, aspetto) / 2.0 / d))
        fov = max(1.2, min(55.0, fov))
        if self.fov is None:
            self.fov = fov
        else:
            k = 1.0 - math.exp(-dt * 3.5)
            self.fov = math.exp(math.log(self.fov) + (math.log(fov) - math.log(self.fov)) * k)
        vicino = max(1.0, min(20.0, d * 0.25))
        fuoco = (0.6, 0.18 + 0.1 * bool(self.altri))
        return self.occhio, centro, vicino, geo.span * 5 + LONTANO_M, self.fov, fuoco

    def finita(self, geo, pos, trascorso: float) -> bool:
        if trascorso > 11.0:
            return True
        if self.chi not in pos:
            return True
        oltre = _avanti(self.f, pos[self.chi][0], lunghezza(geo))
        return trascorso > 1.5 and oltre > 45.0


class Segue(_Camera):
    """La camera car: dietro e un po' sopra, sulla stessa traiettoria."""

    nome = "INSEGUIMENTO"

    def inquadra(self, geo, pos, dt, aspetto):
        if self.chi not in pos:
            return None
        lungo = lunghezza(geo)
        f, lat = pos[self.chi]
        occhio, _ = _punto(geo, f - 11.0 / lungo, lat * 0.6, 3.1)
        mira, _ = _punto(geo, f + 14.0 / lungo, lat * 0.8, 0.5)
        return occhio, mira, 1.0, geo.span * 5 + LONTANO_M, 44.0, (0.0, 0.3)


class TCam(_Camera):
    """La telecamera sopra l'airbox: si vede quello che vede il pilota, con
    l'halo e il muso davanti."""

    nome = "ONBOARD"

    def inquadra(self, geo, pos, dt, aspetto):
        if self.chi not in pos:
            return None
        (x, y, z), fw = geo.sul_giro(*pos[self.chi])
        # la stessa terna della macchina nello shader: la camera e' avvitata sopra
        r = _norm((-fw[2], 0.0, fw[0]))
        u = _norm((r[1] * fw[2] - r[2] * fw[1], r[2] * fw[0] - r[0] * fw[2],
                   r[0] * fw[1] - r[1] * fw[0]))
        base = (x, y + 0.12, z)
        occhio = tuple(base[k] - fw[k] * 0.40 + u[k] * 1.22 for k in range(3))
        mira = tuple(occhio[k] + fw[k] * 20.0 - u[k] * 1.6 for k in range(3))
        return occhio, mira, 0.2, geo.span * 4 + LONTANO_M, 58.0, (0.0, 0.3)


class Aerea(_Camera):
    """L'elicottero sopra la macchina, che le gira piano attorno."""

    nome = "ELICOTTERO"

    def __init__(self, chi, altri=(), angolo: float = 0.0):
        super().__init__(chi, altri)
        self.angolo = angolo

    def inquadra(self, geo, pos, dt, aspetto):
        centro, largo = self._centro(geo, pos)
        if centro is None:
            return None
        self.angolo += dt * 0.10
        raggio = 70.0 + largo
        occhio = (centro[0] + math.cos(self.angolo) * raggio, centro[1] + 42.0 + largo * 0.4,
                  centro[2] + math.sin(self.angolo) * raggio)
        occhio = (occhio[0], max(occhio[1], geo.terra(occhio[0], occhio[2]) + 20.0), occhio[2])
        d = math.dist(occhio, centro)
        return occhio, centro, max(2.0, d * 0.2), geo.span * 5 + LONTANO_M, 30.0, (0.45, 0.32)


def monoposto_lunga() -> float:
    from .monoposto import LUNGHEZZA
    return LUNGHEZZA + 1.0


def _lato_fuori(geo, i: int, rng=None) -> int:
    """Da che parte stare: all'esterno della prossima curva, che e' dove la
    macchina viene incontro alla telecamera. -1 a sinistra, 1 a destra."""
    n = geo.n
    passi = max(1, int(150.0 / max(0.5, lunghezza(geo) / n)))
    k = max((geo.K[(i + j) % n] for j in range(0, passi, 2)), key=abs)
    if abs(k) < 1.0 / 400.0:
        return (rng or random).choice((-1, 1))
    # K positiva e' una curva a destra: l'esterno e' a sinistra
    return -1 if k > 0 else 1


# ----------------------------------------------------------------- regista
TIPI_NOMI = {"bordo": Bordo.nome, "segue": Segue.nome, "tcam": TCam.nome,
             "aerea": Aerea.nome, "circuito": "CIRCUITO"}


class Regista:
    """Sceglie chi guardare e da dove, e manda i replay."""

    def __init__(self, seme: int = 0):
        self.rng = random.Random(seme)
        self.registro = Registro()
        self.geo = None
        self.lungo = 1000.0
        self.camera = None          # None: il circuito dall'elicottero di `vista3d`
        self.tipo = None
        self.trascorso = 0.0
        self.durata = 0.0
        self.orologio = 0.0         # secondi veri
        self.t_sim = None
        self.ritmo = 1.0            # secondi di gara per secondo vero
        self.dt = 1 / 60
        self.live: dict = {}
        self.pos: dict = {}         # quello che si disegna adesso
        self.info: dict = {}
        self.velocita = None        # chi -> m/s, da chi smussa le posizioni
        self.fissato = None         # la macchina che ha scelto chi guarda
        self.sorpassi: list = []    # (t, chi, su, frazione)
        self._visti: set = set()
        self._primo = True
        self.replay = None
        self.coda = None
        self.ultimo_replay = -REPLAY_PAUSA
        self._taglia = False

    # ------------------------------------------------------------ comandi
    def fissa(self, chi) -> None:
        if chi != self.fissato:
            self.fissato = chi
            self._taglia = True

    def puo_rivedere(self) -> bool:
        return bool(self.sorpassi) and self.registro.inizio() is not None

    def rivedi(self) -> bool:
        """Il replay dell'ultimo sorpasso, adesso."""
        for s in reversed(self.sorpassi):
            if self._inizia_replay(s):
                return True
        return False

    def salta(self) -> None:
        """Basta replay: si torna in diretta."""
        if self.replay is not None:
            self.replay = None
            self.pos = self.live
            self._stacca()

    # ------------------------------------------------------------ ogni fotogramma
    def aggiorna(self, geo, dt: float, t_sim: float, pos: dict, info: dict, eventi) -> None:
        """`pos`: chi -> (frazione, laterale in metri); `info`: chi -> dict con
        pos (in classifica), mio, box; `eventi`: la cronaca della gara."""
        self.geo = geo
        self.lungo = lunghezza(geo)
        self.dt = dt
        self.orologio += dt
        if self.t_sim is not None and dt > 0:
            passo = max(0.0, t_sim - self.t_sim)
            self.ritmo += (passo / dt - self.ritmo) * min(1.0, dt * 2.0)
        self.t_sim = t_sim
        self.registro.aggiungi(t_sim, pos)
        self.info = info
        self.live = pos
        self._eventi(eventi or [], pos)
        if self.replay is not None:
            self._avanza_replay(dt)
            return
        self.pos = pos
        if (self.coda is not None and self.orologio >= self.coda[0]
                and t_sim >= self.coda[1][0] + 1.3):
            s = self.coda[1]
            self.coda = None
            if self._inizia_replay(s):
                self._avanza_replay(0.0)
                return
        self.trascorso += dt
        if self._finita():
            self._stacca()

    def inquadra(self, geo, aspetto: float):
        """Per `vista3d`: da dove si guarda adesso, o None per il circuito."""
        if self.camera is None:
            return None
        return self.camera.inquadra(geo, self.pos, self.dt, aspetto)

    def didascalia(self):
        """Cosa scrivere sullo schermo: chi, con chi, da quale camera."""
        cam = self.camera
        replay = self.replay is not None
        avanzato = 0.0
        if replay:
            r = self.replay
            tot = sum(a["a"] - a["da"] for a in r["angoli"])
            fatto = sum(a["a"] - a["da"] for a in r["angoli"][:r["k"]])
            ang = r["angoli"][r["k"]]
            avanzato = (fatto + max(0.0, r["t"] - ang["da"])) / max(1e-6, tot)
        return {"nome": cam.nome if cam is not None else TIPI_NOMI["circuito"],
                "chi": cam.chi if cam is not None else None,
                "altri": list(cam.altri) if cam is not None else [],
                "tipo": self.tipo, "replay": replay, "avanzato": avanzato,
                "sorpasso": self.replay["sorpasso"] if replay else None}

    # ------------------------------------------------------------ dentro
    def _eventi(self, eventi, pos) -> None:
        for ev in eventi[:8]:
            if ev.get("kind") != "pass" or not ev.get("chi") or ev.get("t") is None:
                continue
            chiave = (round(ev["t"], 3), ev["chi"], ev.get("su"))
            if chiave in self._visti:
                continue
            self._visti.add(chiave)
            if self._primo or ev["chi"] not in pos:
                # quelli di prima che la regia si accendesse non si rivedono
                continue
            s = (ev["t"], ev["chi"], ev.get("su"), pos[ev["chi"]][0])
            self.sorpassi.append(s)
            del self.sorpassi[:-8]
            conta = any(self.info.get(c, {}).get("mio") or self.info.get(c, {}).get("pos", 99) <= 10
                        for c in s[1:3] if c)
            if (conta and self.replay is None and self.coda is None
                    and self.ritmo <= RITMO_REPLAY
                    and self.orologio - self.ultimo_replay >= REPLAY_PAUSA):
                self.coda = (self.orologio + REPLAY_RITARDO, s)
        self._primo = False

    def _inizia_replay(self, s) -> bool:
        t, chi, su, f = s
        t0 = self.registro.inizio()
        if t0 is None or t - 1.5 < t0 or self.geo is None:
            return False
        lungo = self.lungo
        # il primo angolo dal bordo pista, appena dopo il punto dove si e'
        # passati: le due macchine arrivano insieme e escono in ordine nuovo
        bordo = Bordo(self.geo, f + 28.0 / lungo, chi, [su] if su else [], rng=self.rng)
        angoli = [dict(cam=bordo, da=max(t0, t - 3.0), a=t + 1.6, lento=0.6),
                  dict(cam=TCam(chi), da=max(t0, t - 2.0), a=t + 0.7, lento=0.85)]
        self.replay = dict(angoli=angoli, k=0, t=angoli[0]["da"], sorpasso=s)
        self.ultimo_replay = self.orologio
        self.coda = None
        self.camera = bordo
        self.tipo = "replay"
        return True

    def _avanza_replay(self, dt: float) -> None:
        r = self.replay
        ang = r["angoli"][r["k"]]
        r["t"] += dt * ang["lento"]
        if r["t"] >= ang["a"]:
            r["k"] += 1
            if r["k"] >= len(r["angoli"]):
                self.replay = None
                self.pos = self.live
                self._stacca()
                return
            ang = r["angoli"][r["k"]]
            r["t"] = ang["da"]
        self.camera = ang["cam"]
        self.pos = self.registro.a(r["t"])

    def _finita(self) -> bool:
        if self.tipo is None or self._taglia:
            return True
        cam = self.camera
        if self.fissato and self.fissato in self.pos and (cam is None or cam.chi != self.fissato):
            return True
        if cam is not None and cam.chi not in self.pos:
            return True
        if self.ritmo > RITMO_VICINO and self.tipo not in ("aerea", "circuito"):
            return True
        if self.tipo == "bordo":
            return cam.finita(self.geo, self.pos, self.trascorso)
        return self.trascorso >= self.durata

    def _vive(self) -> list:
        return [c for c in self.pos if not self.info.get(c, {}).get("box")]

    def _davanti(self, chi, vive):
        """La macchina subito davanti in pista, se e' abbastanza vicina."""
        f = self.pos[chi][0]
        meglio = None
        for o in vive:
            if o == chi:
                continue
            d = _avanti(f, self.pos[o][0], self.lungo)
            if 0.0 < d < BATTAGLIA_M and (meglio is None or d < meglio[1]):
                meglio = (o, d)
        return meglio

    def _scegli(self, vive):
        recenti = {s[1] for s in self.sorpassi
                   if self.t_sim is not None and self.t_sim - s[0] < 15.0}
        attuale = self.camera.chi if self.camera is not None else None
        voti = []
        for c in vive:
            i = self.info.get(c, {})
            v = self.rng.random() * 0.9
            d = self._davanti(c, vive)
            if d:
                v += 3.0 * max(0.0, 1.0 - d[1] / BATTAGLIA_M)
            v += {1: 1.2, 2: 0.7, 3: 0.5}.get(i.get("pos"), 0.0)
            if i.get("mio"):
                v += 1.1
            if c in recenti:
                v += 1.5
            if c == attuale:
                v -= 1.2
            voti.append((v, c))
        return max(voti)[1]

    def _stacca(self) -> None:
        """Nuova inquadratura."""
        self._taglia = False
        self.trascorso = 0.0
        vive = self._vive()
        if not vive or self.geo is None:
            self.camera, self.tipo, self.durata = None, "circuito", 6.0
            return
        chi = self.fissato if self.fissato in vive else self._scegli(vive)
        davanti = self._davanti(chi, vive)
        if self.ritmo > RITMO_VICINO:
            pesi = {"aerea": 1.0, "circuito": 1.0}
        elif davanti:
            pesi = {"bordo": 5.0, "segue": 3.0, "aerea": 1.5, "tcam": 2.0}
        else:
            pesi = {"bordo": 4.0, "segue": 2.0, "tcam": 2.0, "aerea": 2.0,
                    "circuito": 0.0 if self.fissato else 0.6}
        if self.ritmo > 2.0 and "bordo" in pesi:
            # di corsa, la macchina arriva alla telecamera prima di vederla
            pesi["bordo"] *= 0.3
        if self.tipo in pesi and len(pesi) > 1:
            del pesi[self.tipo]
        tipi = list(pesi)
        tipo = self.rng.choices(tipi, [pesi[t] for t in tipi])[0]
        altri = [davanti[0]] if davanti and tipo in ("bordo", "aerea") else []
        f = self.pos[chi][0]
        if tipo == "bordo":
            v = (self.velocita(chi) if self.velocita else 0.0) or 60.0
            anticipo = max(70.0, min(320.0, v * max(1.0, self.ritmo) * 3.2))
            primo = f + (davanti[1] if altri else 0.0) / self.lungo
            cam = Bordo(self.geo, primo + anticipo / self.lungo, chi, altri, rng=self.rng)
            durata = 11.0
        elif tipo == "segue":
            cam, durata = Segue(chi), 6.0 + self.rng.random() * 2.0
        elif tipo == "tcam":
            cam, durata = TCam(chi), 5.0 + self.rng.random() * 2.0
        elif tipo == "aerea":
            _, fw = self.geo.sul_giro(f, 0.0)
            ang = math.atan2(fw[2], fw[0]) + math.pi + self.rng.uniform(-0.9, 0.9)
            cam, durata = Aerea(chi, altri, ang), 7.0 + self.rng.random() * 2.0
        else:
            cam, durata = None, 6.0
        self.camera, self.tipo, self.durata = cam, tipo, durata
