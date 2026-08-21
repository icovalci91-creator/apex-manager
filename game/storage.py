"""Salvataggi: file su desktop, localStorage nel browser.

La build web gira su un filesystem in memoria che sparisce a ogni ricarica
della pagina, quindi li' i salvataggi passano da localStorage. Il resto del
gioco non deve sapere quale dei due e' in uso: parla solo di nomi e di dict.
"""
from __future__ import annotations

import json
import os
import sys

from . import config as C

IS_WEB = sys.platform == "emscripten"
_PREFIX = "apexmanager/save/"


def _window():
    import platform          # iniettato da pygbag, non la stdlib
    return platform.window


# ------------------------------------------------------------------ elenco
def list_saves() -> list[str]:
    """Nomi dei salvataggi disponibili, dal piu' recente al piu' vecchio.

    Viene chiamata mentre si costruisce il menu, prima del primo frame: se
    fallisse trascinerebbe giu' tutto il gioco. Meglio dire che non ci sono
    salvataggi e lasciar giocare.
    """
    if IS_WEB:
        try:
            store = _window().localStorage
            names = []
            for i in range(int(store.length)):
                key = store.key(i)
                if key and key.startswith(_PREFIX):
                    names.append(key[len(_PREFIX):])
            # senza mtime ci si affida all'ordine alfabetico: i nomi finiscono
            # con la stagione, quindi il piu' recente resta in cima
            return sorted(names, reverse=True)
        except Exception:
            return []
    if not C.SAVES.is_dir():
        return []
    paths = sorted(C.SAVES.glob("*.json"), key=os.path.getmtime, reverse=True)
    return [p.stem for p in paths]


# ------------------------------------------------------------- lettura e scrittura
def read_save(name: str) -> dict:
    if IS_WEB:
        raw = _window().localStorage.getItem(_PREFIX + name)
        if raw is None:
            raise FileNotFoundError(name)
        return json.loads(raw)
    with open(C.SAVES / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def write_save(name: str, data: dict) -> str:
    """Scrive il salvataggio e restituisce una descrizione di dove e' finito."""
    raw = json.dumps(data, ensure_ascii=False)
    if IS_WEB:
        _window().localStorage.setItem(_PREFIX + name, raw)
        return "memoria del browser"
    C.SAVES.mkdir(exist_ok=True)
    path = C.SAVES / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw)
    return path.name
