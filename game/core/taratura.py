"""La taratura dei circuiti, fatta una volta e poi ricordata.

Tarare un circuito vuol dire far girare il modello del giro con la vettura di
riferimento finche' non torna la pole vera, provare le ali e i rapporti, e
segnare metro per metro dove si frena e dove si tira. Sono qualche decina di
giri simulati per ognuno dei trentacinque circuiti: otto secondi buoni. E si
facevano a ogni nuova carriera e - peggio - a ogni salvataggio caricato,
anche se il risultato era sempre lo stesso: dipende solo dai dati del
circuito e dal codice del modello, non dalla partita.

Qui si fa la stessa taratura e se ne tiene il risultato, in memoria e su
disco (nella cartella del gioco, sotto `cache/`). La chiave dice da cosa
dipende: il circuito com'e' prima di tararlo, il regolamento della vettura di
riferimento e il codice del modello del giro (nell'eseguibile, la sigla della
build). Se cambia una di queste cose si ritara da capo; se no si rilegge.
"""
from __future__ import annotations

import copy
import hashlib
import pickle
from pathlib import Path

from .. import config as C

# i moduli da cui dipende il giro calcolato: se ne cambia il codice, le
# tarature vecchie non valgono piu'
_MODULI = ("model/track.py", "model/car.py", "sim/pace.py", "sim/gomme.py",
           "sim/benzina.py", "sim/energia.py", "config.py")
_MEMORIA: dict = {}
_FIRMA: list = []


def _firma() -> str:
    """Un'impronta del codice del modello: i sorgenti se ci sono, se no (nel
    gioco impacchettato) la sigla della build, che cambia a ogni versione."""
    if _FIRMA:
        return _FIRMA[0]
    h = hashlib.sha1()
    radice = Path(__file__).resolve().parent.parent
    letti = 0
    for nome in _MODULI:
        p = radice / nome
        try:
            h.update(p.read_bytes())
            letti += 1
        except OSError:
            pass
    if letti < len(_MODULI):
        try:
            h.update((Path(C.DATA) / "build.txt").read_bytes())
        except OSError:
            h.update(C.GAME_VERSION.encode())
    _FIRMA.append(h.hexdigest())
    return _FIRMA[0]


def _cartella() -> Path:
    return Path(C.UTENTE) / "cache" / "tarature"


def calibra(track, ref_car, regolamento) -> None:
    """Tara `track` come farebbe `track.calibrate(ref_car)`, ma una volta sola."""
    try:
        # una copia vera, non un elenco di riferimenti: se la taratura
        # modificasse un oggetto sul posto, il confronto lo deve vedere
        prima = copy.deepcopy(track.__dict__)
        chiave = hashlib.sha1(pickle.dumps(
            (_firma(), sorted(prima.items(), key=lambda kv: kv[0]), regolamento),
            protocol=4)).hexdigest()
    except Exception:            # qualcosa che non si sa copiare: si tara e basta
        track.calibrate(ref_car)
        return
    fatto = _MEMORIA.get(chiave)
    if fatto is None:
        try:
            fatto = pickle.loads((_cartella() / f"{chiave}.pkl").read_bytes())
        except Exception:
            fatto = None
    if fatto is not None:
        _MEMORIA[chiave] = fatto
        # una copia per circuito: due partite aperte nella stessa sessione non
        # devono condividere le stesse liste
        track.__dict__.update(copy.deepcopy(fatto))
        return
    track.calibrate(ref_car)
    fatto = {}
    for k, v in track.__dict__.items():
        try:
            uguale = k in prima and prima[k] == v
        except Exception:
            uguale = False
        if not uguale:
            fatto[k] = v
    _MEMORIA[chiave] = copy.deepcopy(fatto)
    try:
        _cartella().mkdir(parents=True, exist_ok=True)
        (_cartella() / f"{chiave}.pkl").write_bytes(pickle.dumps(fatto, protocol=4))
    except Exception:            # disco in sola lettura, browser: si ricorda solo in memoria
        pass
