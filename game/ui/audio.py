"""Il suono: chi suona cosa, e quanto forte.

I suoni si fanno in `sintesi` e qui diventano suoni di pygame. All'avvio si
preparano tutti in un filo a parte (la musica ci mette un secondo): finche'
non sono pronti il gioco resta muto, poi parte.

Le scene non toccano il mixer: chiedono. `suona("clic")` per un colpo solo;
`ambiente("folla", 0.3)` e `motore(0, ...)` a ogni fotogramma per quello che
deve continuare a suonare - quello che non viene piu' chiesto sfuma da solo.
`musica(True)` la vuole il menu, la pista no.

Senza numpy, senza scheda audio o nel browser il gioco resta muto e basta.
Le preferenze (volume, musica, effetti) stanno in un file accanto ai
salvataggi.
"""
from __future__ import annotations

import json
import sys
import threading

import pygame

from .. import config as C

WEB = sys.platform == "emscripten"
SR = 44100
BLOCCO = 3072               # campioni per pezzo di motore: 70 millesimi

_attivo = False
_pronti = False
_suoni: dict = {}
_fondi: dict = {}           # nome -> [Sound, canale, livello, richiesto]
_voci: dict = {}            # indice -> _Voce
_musica = [None, 0.0, False]   # Sound, livello, richiesta
_canali_liberi: list = []

IMPOSTAZIONI = {"volume": 0.8, "musica": True, "effetti": True, "muto": False}
LIVELLO_MUSICA = 0.45

# i canali tenuti da parte: la musica, due motori, i fondi
_C_MUSICA = 0
_C_VOCI = (1, 2)
_C_FONDI = {"folla": 3, "pioggia": 4, "vento": 5, "campo": 6}


def _file() -> "C.Path":
    return C.UTENTE / "audio.json"


def prepara() -> None:
    """Prima di pygame.init: il mixer con un buffer corto, per il motore."""
    if WEB:
        return
    try:
        pygame.mixer.pre_init(SR, -16, 2, 1024)
    except Exception:
        pass


def avvia() -> None:
    """Accende il mixer e prepara i suoni in un filo a parte."""
    global _attivo, SR
    if WEB or _attivo:
        return
    try:
        import importlib.util
        if importlib.util.find_spec("numpy") is None:
            return
        if not pygame.mixer.get_init():
            pygame.mixer.init(SR, -16, 2, 1024)
        SR = pygame.mixer.get_init()[0]
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(1 + len(_C_VOCI) + len(_C_FONDI))
    except Exception:
        return
    _attivo = True
    _carica()
    threading.Thread(target=_prepara_tutto, daemon=True).start()


def attivo() -> bool:
    return _attivo and _pronti


def disponibile() -> bool:
    """C'e' un suono da regolare (anche se si sta ancora preparando)."""
    return _attivo


def _carica() -> None:
    try:
        with open(_file(), encoding="utf-8") as f:
            dati = json.load(f)
        for k in IMPOSTAZIONI:
            if k in dati:
                IMPOSTAZIONI[k] = type(IMPOSTAZIONI[k])(dati[k])
    except Exception:
        pass


def salva() -> None:
    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        with open(_file(), "w", encoding="utf-8") as f:
            json.dump(IMPOSTAZIONI, f)
    except Exception:
        pass


def imposta(**valori) -> None:
    """Cambia il volume, la musica, gli effetti; e se lo ricorda."""
    IMPOSTAZIONI.update(valori)
    IMPOSTAZIONI["volume"] = max(0.0, min(1.0, float(IMPOSTAZIONI["volume"])))
    salva()


def volume() -> float:
    """Il volume generale, zero se si e' tolto l'audio."""
    return 0.0 if IMPOSTAZIONI["muto"] else IMPOSTAZIONI["volume"]


def _suono(x):
    """Da campioni fra -1 e 1 (mono o stereo) a un suono di pygame."""
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    canali = pygame.mixer.get_init()[2]
    if x.ndim == 1:
        x = np.stack([x] * canali, 1) if canali > 1 else x
    elif canali == 1:
        x = x.mean(1)
    dati = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    return pygame.mixer.Sound(buffer=dati.tobytes())


def _prepara_tutto() -> None:
    global _pronti
    from . import sintesi as S
    try:
        for nome in ("clic", "sfiora", "passa", "avviso", "luce"):
            _suoni[nome] = _suono(getattr(S, nome)(SR))
        for nome in ("folla", "pioggia", "vento"):
            _fondi[nome] = [_suono(getattr(S, nome)(SR)), pygame.mixer.Channel(_C_FONDI[nome]),
                            0.0, 0.0]
        _pronti = True
        _musica[0] = _suono(S.musica(SR))
        _fondi["campo"] = [_suono(S.campo(SR)), pygame.mixer.Channel(_C_FONDI["campo"]), 0.0, 0.0]
        for nome in ("fanfara", "applausi", "partenza"):
            _suoni[nome] = _suono(getattr(S, nome)(SR))
    except Exception as exc:          # un suono che non viene non ferma il gioco
        print("audio:", type(exc).__name__, exc)


# ------------------------------------------------------------------ richieste
def suona(nome: str, forza: float = 1.0, pan: float = 0.0) -> None:
    """Un colpo solo: il clic, il semaforo, la bandiera."""
    if not (attivo() and IMPOSTAZIONI["effetti"]):
        return
    s = _suoni.get(nome)
    if s is None:
        return
    ch = s.play()
    if ch is not None:
        v = forza * volume()
        ch.set_volume(v * min(1.0, 1.0 - pan), v * min(1.0, 1.0 + pan))


def ambiente(nome: str, livello: float) -> None:
    """Un fondo che deve suonare adesso, a questo livello (0-1)."""
    f = _fondi.get(nome)
    if f is not None:
        f[3] = max(f[3], max(0.0, min(1.0, livello)))


def musica(accesa: bool) -> None:
    _musica[2] = bool(accesa)


def motore(indice: int, chi, velocita: float, accel: float, volume: float,
           pan: float = 0.0, doppler: float = 1.0, elettrico: bool = False) -> None:
    """Una monoposto da far sentire adesso: velocita' in m/s, accelerazione in
    m/s2, volume 0-1, pan da -1 (sinistra) a 1, doppler come rapporto di
    frequenza. `chi` cambia a ogni stacco: il motore salta sulla nuova."""
    if not (attivo() and IMPOSTAZIONI["effetti"]) or indice not in (0, 1):
        return
    v = _voci.get(indice)
    if v is None or v.elettrico != elettrico:
        if v is not None:
            v.canale.stop()
        v = _voci[indice] = _Voce(pygame.mixer.Channel(_C_VOCI[indice]), indice, elettrico)
    v.chiedi(chi, velocita, accel, volume, pan, doppler)


class _Voce:
    """Un motore che suona un pezzo dopo l'altro sul suo canale."""

    def __init__(self, canale, indice: int, elettrico: bool):
        from . import sintesi as S
        self.canale = canale
        self.elettrico = elettrico
        self.m = S.Motore(SR, 5 + indice * 11, elettrico)
        self.chi = None
        self.stato = (0.0, 0.0, 0.0, 0.0, 1.0)
        self.volume = 0.0
        self.pan = 0.0
        self.richiesta = False

    def chiedi(self, chi, velocita, accel, volume, pan, doppler) -> None:
        if chi != self.chi:
            self.chi = chi
            self.m.salta(velocita)
        self.stato = (velocita, accel, max(0.0, min(1.0, volume)), max(-1.0, min(1.0, pan)),
                      max(0.6, min(1.6, doppler)))
        self.richiesta = True

    def pompa(self) -> None:
        """Tiene sempre un pezzo in coda: quando quello che suona finisce,
        il prossimo e' gia' li'."""
        import numpy as np
        v, a, vol, pan, dop = self.stato
        if not self.richiesta:
            vol = 0.0
        if vol <= 0.0 and self.volume < 0.01:
            if self.canale.get_busy():
                self.canale.stop()
            self.volume = 0.0
            return
        for _ in range(2):
            if self.canale.get_busy() and self.canale.get_queue() is not None:
                break
            x = self.m.blocco(BLOCCO, v, a, dop)
            v0, v1 = self.volume, vol
            p0, p1 = self.pan, pan
            self.volume, self.pan = v1, p1
            g = np.linspace(v0, v1, BLOCCO) * 0.5
            p = np.linspace(p0, p1, BLOCCO)
            s = self._suono(np.stack([x * g * np.minimum(1.0, 1.0 - p),
                                      x * g * np.minimum(1.0, 1.0 + p)], 1))
            if not self.canale.get_busy():
                self.canale.play(s)
            else:
                self.canale.queue(s)
        self.canale.set_volume(volume())

    @staticmethod
    def _suono(x):
        return _suono(x)


# ------------------------------------------------------------------ il giro
def aggiorna(dt: float) -> None:
    """Una volta per fotogramma, dopo che le scene hanno chiesto."""
    if not attivo():
        return
    vol = volume()
    k = min(1.0, dt * 3.0)
    # la musica
    s, livello, voluta = _musica
    meta = LIVELLO_MUSICA if (voluta and IMPOSTAZIONI["musica"]) else 0.0
    livello += (meta - livello) * min(1.0, dt * (1.5 if meta > livello else 2.5))
    _musica[1] = livello
    ch = pygame.mixer.Channel(_C_MUSICA)
    if s is not None:
        if livello > 0.005:
            if not ch.get_busy():
                ch.play(s, loops=-1)
            ch.set_volume(livello * vol)
        elif ch.get_busy():
            ch.stop()
    _musica[2] = False
    # i fondi
    for nome, f in _fondi.items():
        suono, canale, livello, richiesto = f
        meta = richiesto if IMPOSTAZIONI["effetti"] else 0.0
        livello += (meta - livello) * k
        f[2], f[3] = livello, 0.0
        if livello > 0.005:
            if not canale.get_busy():
                canale.play(suono, loops=-1)
            canale.set_volume(livello * vol)
        elif canale.get_busy():
            canale.stop()
    # i motori
    for voce in _voci.values():
        voce.pompa()
        voce.richiesta = False


def zitto() -> None:
    """Spegne tutto subito (chiusura, cambio di scena brusco)."""
    if _attivo:
        try:
            pygame.mixer.stop()
        except Exception:
            pass
