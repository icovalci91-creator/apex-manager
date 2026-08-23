"""Editor: naviga e modifica qualunque cosa ci sia dentro una partita.

Non c'e' un elenco di cose modificabili. C'e' un modo per guardare dentro un
oggetto qualunque - una squadra, una vettura, un contratto, un circuito, una
costante di taratura - elencare cosa contiene e riscrivere un valore. Da li'
tutto il resto viene da se': se una cosa esiste nella partita, l'editor la
trova, perche' la trova allo stesso modo in cui la trova il gioco.

Le uniche cose escluse sono quelle che non hanno senso come valore: funzioni,
moduli, il generatore casuale e i riferimenti privati. Tutto il resto si
modifica, comprese le costanti di taratura dei moduli, che non stanno nel
salvataggio ma cambiano il comportamento della partita in corso.
"""
from __future__ import annotations

import math
from dataclasses import fields, is_dataclass

SCALARI = (bool, int, float, str)


class ModuleView:
    """Le costanti di un modulo, viste come un contenitore.

    I moduli non sono oggetti come gli altri - non hanno campi dichiarati - ma
    le loro maiuscole sono la taratura del gioco: TECH_DECAY, CYCLE_SPAN,
    SIM_MAX. Da qui si toccano quelle.
    """

    def __init__(self, modulo, label: str):
        self.modulo = modulo
        self.label = label

    def keys(self) -> list:
        out = []
        for nome in dir(self.modulo):
            if nome.startswith("_") or not nome.isupper():
                continue
            v = getattr(self.modulo, nome)
            if isinstance(v, SCALARI) or isinstance(v, (dict, list, tuple)):
                out.append(nome)
        return sorted(out)

    def get(self, k):
        return getattr(self.modulo, k)

    def set(self, k, v) -> None:
        setattr(self.modulo, k, v)


# --------------------------------------------------------------- ispezione
def is_scalar(v) -> bool:
    return v is None or isinstance(v, SCALARI)


def is_container(v) -> bool:
    if is_scalar(v):
        return False
    if isinstance(v, (ModuleView, dict, list, tuple, set)):
        return True
    return hasattr(v, "__dict__") or is_dataclass(v)


ESCLUSI = {"rng", "view_rng", "app", "shell", "screen", "surface"}


def entries(obj) -> list:
    """Cosa contiene un oggetto: lista di (chiave, etichetta, valore).

    La chiave e' quello che serve per rileggere e riscrivere il valore, e
    l'etichetta e' come lo si mostra: per una squadra il nome, per un pilota il
    cognome, per un indice di lista il numero piu' un'anteprima.
    """
    out = []
    if isinstance(obj, ModuleView):
        for k in obj.keys():
            out.append((k, k, obj.get(k)))
        return out
    if isinstance(obj, dict):
        for k in obj.keys():
            out.append((k, str(k), obj[k]))
        return out
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.append((i, f"[{i}] {etichetta(v)}", v))
        return out
    if is_dataclass(obj):
        for f in fields(obj):
            if f.name in ESCLUSI:
                continue
            out.append((f.name, f.name, getattr(obj, f.name, None)))
        # anche le proprieta' calcolate, in sola lettura: servono a capire
        # l'effetto di quello che si sta cambiando
        for nome, valore in _proprieta(obj):
            out.append((None, nome, valore))
        return out
    if hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k.startswith("_") or k in ESCLUSI or callable(v):
                continue
            out.append((k, k, v))
        for nome, valore in _proprieta(obj):
            out.append((None, nome, valore))
        return out
    return out


def _proprieta(obj) -> list:
    """Valori calcolati della classe: si vedono, non si scrivono."""
    out = []
    for nome in dir(type(obj)):
        if nome.startswith("_"):
            continue
        attr = getattr(type(obj), nome, None)
        if not isinstance(attr, property):
            continue
        try:
            v = getattr(obj, nome)
        except Exception:
            continue
        if is_scalar(v):
            out.append((f"{nome} (calcolato)", v))
    return out


def etichetta(v) -> str:
    """Come si chiama una cosa quando sta in un elenco."""
    for attr in ("short", "name", "label", "title", "id"):
        x = getattr(v, attr, None)
        if isinstance(x, str) and x:
            return x
    if isinstance(v, dict):
        for k in ("name", "label", "title", "id", "short"):
            if isinstance(v.get(k), str):
                return v[k]
    if is_scalar(v):
        return descrivi(v)
    return type(v).__name__


def descrivi(v) -> str:
    """Il valore come si mostra nella lista."""
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "si" if v else "no"
    if isinstance(v, float):
        if v != v or v in (math.inf, -math.inf):
            return str(v)
        return f"{v:.4g}"
    if isinstance(v, (int, str)):
        return str(v)
    if isinstance(v, dict):
        return "{%d voci}" % len(v)
    if isinstance(v, (list, tuple, set)):
        return "[%d]" % len(v)
    return etichetta(v)


# ------------------------------------------------------------ lettura e scrittura
def leggi(obj, key):
    if isinstance(obj, ModuleView):
        return obj.get(key)
    if isinstance(obj, dict):
        return obj[key]
    if isinstance(obj, (list, tuple)):
        return obj[key]
    return getattr(obj, key)


def scrivi(obj, key, valore) -> None:
    if isinstance(obj, ModuleView):
        obj.set(key, valore)
    elif isinstance(obj, dict):
        obj[key] = valore
    elif isinstance(obj, list):
        obj[key] = valore
    elif isinstance(obj, tuple):
        raise TypeError("una tupla non si modifica sul posto: serve il genitore")
    else:
        setattr(obj, key, valore)


def scrivi_annidato(catena: list, chiave, valore):
    """Scrive un valore risalendo la catena dei contenitori.

    Le tuple non si modificano sul posto, e nel gioco ce ne sono parecchie: la
    geometria dei circuiti sono decine di migliaia di coppie, e la taratura
    degli strumenti e' fatta di tuple dentro tuple. Qui la tupla viene
    ricostruita e riscritta nel suo contenitore; se anche quello e' una tupla si
    ripete, finche' non si trova qualcosa di modificabile. Senza questo, meta'
    dei valori della partita sarebbe stata di sola lettura.

    `catena` e' la lista (oggetto, chiave nel genitore) dal piu' esterno fino
    all'oggetto che contiene il valore da scrivere.
    """
    obj = catena[-1][0]
    if not isinstance(obj, tuple):
        scrivi(obj, chiave, valore)
        return valore
    nuova = obj[:chiave] + (valore,) + obj[chiave + 1:]
    if len(catena) < 2:
        raise TypeError("questa tupla non ha un contenitore modificabile")
    scrivi_annidato(catena[:-1], catena[-1][1], nuova)
    return nuova


def converti(vecchio, testo: str):
    """Interpreta quello che e' stato scritto, tenendo il tipo di prima.

    Un numero resta un numero e un si/no resta un si/no: cambiare il tipo di un
    campo sotto ai piedi del gioco e' il modo piu' rapido per farlo esplodere in
    un punto lontanissimo da qui.
    """
    testo = testo.strip()
    if isinstance(vecchio, bool):
        return testo.lower() in ("1", "si", "sì", "true", "vero", "yes", "y")
    if isinstance(vecchio, int) and not isinstance(vecchio, bool):
        return int(round(float(testo.replace(",", "."))))
    if isinstance(vecchio, float):
        return float(testo.replace(",", "."))
    if vecchio is None:
        # un campo vuoto puo' diventare quello che serve
        if testo == "" or testo.lower() in ("none", "-"):
            return None
        try:
            return float(testo) if "." in testo or "," in testo else int(testo)
        except ValueError:
            return testo
    return testo


# ------------------------------------------------------------------- radici
def radici(gs) -> list:
    """Da dove si parte a scavare. Copre tutto quello che c'e' in partita."""
    from . import config as C
    from .core import (development, economy, engineering, facilities, market,
                       powertrain, rules, season, setup, sponsors, testing)
    from .model import car as car_mod
    from .sim import weekend as weekend_mod

    costanti = [
        ModuleView(C, "Configurazione generale"),
        ModuleView(development, "Sviluppo"),
        ModuleView(setup, "Assetto e simulatore"),
        ModuleView(facilities, "Infrastrutture"),
        ModuleView(economy, "Economia"),
        ModuleView(market, "Mercato"),
        ModuleView(powertrain, "Power unit"),
        ModuleView(testing, "Test privati"),
        ModuleView(rules, "Commissione"),
        ModuleView(season, "Stagione"),
        ModuleView(engineering, "Ingegneria"),
        ModuleView(sponsors, "Sponsor"),
        ModuleView(car_mod, "Vettura"),
        ModuleView(weekend_mod, "Simulazione di gara"),
    ]
    return [
        ("Partita in corso", gs),
        ("Squadre", gs.teams),
        ("Piloti", gs.drivers),
        ("Piloti svincolati", gs.free_agents),
        ("Staff libero", gs.free_staff),
        ("Circuiti in calendario", gs.tracks),
        ("Circuiti candidati", gs.candidates),
        ("Regolamento in vigore", gs.regulations),
        ("Commissione", gs.commission),
        ("Proposte", gs.proposals),
        ("Motoristi", gs.engine_makers),
        ("Sponsor disponibili", gs.sponsor_pool),
        ("Cicli tecnici", gs.history_data),
        ("Risultati", gs.results),
        ("Costanti di taratura", {m.label: m for m in costanti}),
    ]
