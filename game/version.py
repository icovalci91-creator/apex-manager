"""Quale copia del gioco si sta eseguendo.

Serve a rispondere a una domanda che altrimenti si risponde a indovinare:
"sto vedendo l'ultima versione o una vecchia?". La risposta e' una sigla corta
che si legge nel menu: se non e' quella che ci si aspetta, la copia e'
vecchia, e non c'e' niente da cercare nel codice.

La sigla viene dal commit. Nella build web la scrive la macchina che la
prepara, in un file dentro i dati; in locale la si chiede a git. Se non c'e'
ne' l'uno ne' l'altro non e' un problema: si dice che non si sa.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config as C

_CACHE: list = []


def build_id() -> str:
    if _CACHE:
        return _CACHE[0]
    _CACHE.append(_leggi())
    return _CACHE[0]


def _leggi() -> str:
    # 1) la build web: il file lo scrive chi impacchetta
    try:
        f = Path(C.DATA) / "build.txt"
        if f.exists():
            testo = f.read_text(encoding="utf-8").strip()
            if testo:
                return testo.splitlines()[0][:40]
    except Exception:
        pass
    # 2) in locale: quello che dice git
    try:
        out = subprocess.run(["git", "-C", str(C.ROOT), "log", "-1",
                              "--format=%h %cd", "--date=format:%d/%m %H:%M"],
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:40]
    except Exception:
        pass
    return "sconosciuta"


def etichetta() -> str:
    """Come si scrive in una schermata."""
    return f"versione {C.GAME_VERSION}  -  build {build_id()}"
