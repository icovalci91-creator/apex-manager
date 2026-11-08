"""La sonda dei salvataggi: le partite di prima si aprono ancora, e salvare
non perde niente.

Un salvataggio di Apex Manager non e' una fotografia della partita: e' quello
che e' cambiato rispetto ai dati. `GameState.from_dict` rifonda il mondo da
capo con `new_game`, come per una carriera nuova, e poi ci scrive sopra i
valori salvati. E' il modo giusto per non portarsi dietro trentacinque
circuiti tarati in ogni file, ma ha un difetto che non si vede: un attributo
che non finisce in `to_dict` non da' nessun errore. Al caricamento torna in
silenzio al valore di `data/`, e nessun confronto fra due JSON lo puo' notare,
perche' manca da tutti e due (e' gia' successo con il nome della pista di
proprieta'). Il guaio opposto e' un campo rinominato o tolto: le partite
salvate con l'eseguibile di prima non si aprono piu'.

Qui si fanno le due prove che il giocatore fa senza saperlo ogni volta che
riapre il gioco:

(a) una carriera salvata dal codice di un commit (HEAD, se non si dice altro,
    estratto con `git archive` in una cartella temporanea) si apre con il
    codice di adesso, si gioca un po' (una tappa di Formula E, una di
    endurance, un gran premio), si risalva e si riapre. Se qualcosa si rompe
    e' ROTTO. Appena aperta la si risalva anche, e le chiavi che c'erano nel
    file e non ci sono piu' sono un nome cambiato che le partite di prima
    perdono: PERDE DATI.
(b) una carriera giocata dal codice di adesso si confronta attributo per
    attributo - la partita, ogni squadra, ogni pilota, ogni tecnico, ogni
    contratto - prima di salvarla e dopo averla ricaricata. Quello che cambia
    si e' perso: PERDE DATI, con il nome dell'attributo e la riga di
    `to_dict` o `from_dict` da aggiungere.

La carriera di prova ha la Formula E e l'endurance aperte: una partita di
sola Formula 1 lascia a zero meta' dello stato e non vede quello che si perde
li'. Corre due gran premi con le tappe degli altri campionati in mezzo, si
controlla, chiude la stagione e si controlla di nuovo in inverno. La stessa
carriera la gioca anche il codice di HEAD: quello che si perdeva gia' li' si
segnala come DIFETTO VECCHIO, ma non e' colpa della modifica di adesso e non
cambia l'esito.

    python tools/sonda_salvataggi.py                 # base HEAD
    python tools/sonda_salvataggi.py --base bcdd3ad  # un commit qualsiasi
    python tools/sonda_salvataggi.py --json          # il rapporto in JSON

Esce con 0 se e' tutto a posto, 1 se qualcosa e' ROTTO o PERDE DATI, 2 se la
prova non si e' potuta fare (git che manca, commit sconosciuto, librerie non
installate, una base che non riesce nemmeno a salvare).

Non tocca i file del repository. I salvataggi stanno in una cartella
temporanea che sparisce alla fine; l'unica cosa che il codice di adesso puo'
scrivere e' la cache delle tarature in `cache/`, che git ignora, come quando
si lancia il gioco dai sorgenti.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib
import inspect
import io
import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
STATE = "game/core/state.py"

# La carriera di prova. Una squadra cliente, perche' alla partenza prova a
# fondare il suo reparto motori e cosi' si muove anche quella parte dello
# stato; un seme fisso, perche' due giri della sonda sulla stessa modifica
# devono dire la stessa cosa.
SQUADRA = "williams"
SEME = 2026
GARE_F1 = 2
# un calendario che non avanza non deve far girare la sonda per sempre
EVENTI_MAX = 40
# Il tempo di un processo figlio. Di solito ne basta un decimo; una base
# vecchia, di prima della cache delle tarature, ritara i circuiti a ogni
# apertura, e un portatile Windows puo' essere tre volte piu' lento di qui.
LIMITE_S = 420

CLASSE = "__classe__"
ASSENTE = "(assente)"

# Quello che non si confronta, e perche'.
#  - gs.rng: il generatore non si salva, per scelta. Ricaricando riparte dal
#    seme, e da li' la partita prende un'altra strada con gli stessi numeri.
#  - gli attributi con il trattino basso davanti: sono i conti di lavoro, le
#    cache che il modello si tiene per non rifare un calcolo (la linea di un
#    circuito, le penalita' dell'assetto appena valutato). Si rifanno da soli.
#  - Car.setup_quality e Car.fuel_kg: li riscrive il modello del giro ogni
#    volta che guarda la macchina. Sono gli stessi che development._ESCLUSI
#    tiene fuori dalla firma di una vettura, e per la stessa ragione.
SALTA = {("GameState", "rng"), ("Car", "setup_quality"), ("Car", "fuel_kg")}

# Elenchi in cui conta chi c'e', non in che ordine. I candidati al calendario
# _restore_calendar li rimette nell'ordine dei dati, e chi li usa li ordina da
# se' (calendar.roll_contracts per offerta, testing li cerca per id).
ORDINE_LIBERO = {("GameState", "candidates")}


class Impossibile(Exception):
    """La sonda non ha potuto fare la prova: non e' un difetto del gioco."""


# ================================================================ il figlio
def _facoltativo(nome: str):
    """Un modulo del gioco che una base vecchia puo' non avere."""
    try:
        return importlib.import_module(nome)
    except ModuleNotFoundError as exc:
        if exc.name == nome:
            return None
        raise


class Gioco:
    """Il gioco di una cartella, guidato senza schermo.

    Lo stesso codice gioca la base e il codice di adesso, e la base puo' essere
    un commit di mesi fa: quello che non c'e' sempre stato (il calendario
    unico, la Formula E, l'endurance, la riunione d'inverno) si cerca prima di
    usarlo, e se manca si fa a meno.
    """

    def __init__(self, radice: Path):
        self.radice = radice
        # prima di tutto la cartella da provare, e via quella della sonda:
        # tools/ non deve poter coprire un modulo del gioco
        qui = Path(__file__).resolve().parent
        sys.path[:] = [str(radice)] + [p for p in sys.path
                                       if p and Path(p).resolve() != qui]
        # i moduli del gioco non aprono finestre, ma se uno importa pygame non
        # deve cercare uno schermo che in un contenitore non c'e'
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from game.core import rules, season
        from game.core.state import GameState
        from game.sim import session
        from game.sim.weekend import Weather
        self.GameState, self.rules, self.season = GameState, rules, season
        self.session, self.Weather = session, Weather
        self.tyres = _facoltativo("game.core.tyres")
        self.fe = _facoltativo("game.core.formulae")
        self.wec = _facoltativo("game.core.wec")
        self.inverno = _facoltativo("game.core.inverno")

    # ----------------------------------------------------------- la carriera
    def nuova(self):
        dati = json.loads((self.radice / "data" / "teams.json").read_text(encoding="utf-8"))
        squadre = [t["id"] for t in dati["teams"]]
        squadra = SQUADRA if SQUADRA in squadre else squadre[0]
        gs = self.GameState.new_game(squadra, True, seed=SEME)
        # nessuno davanti allo schermo: lo sviluppo lo decide il reparto, la
        # delega che il giocatore puo' dare
        gs.player.auto_dev = True
        # i soldi per entrare negli altri due campionati: senza, una squadra
        # piccola resterebbe fuori e quella parte dello stato non si vedrebbe
        if self.fe is not None and hasattr(self.fe, "apri"):
            gs.player.cash += 300.0
            self.fe.apri(gs, gs.player, f"{gs.player.short} E")
        if self.wec is not None and hasattr(self.wec, "apri"):
            gs.player.cash += 300.0
            self.wec.apri(gs, gs.player, f"{gs.player.short} Endurance", "hypercar")
        return gs

    def programmi(self, gs) -> dict:
        return {"fe": bool(self.fe is not None and self.fe.ha(gs.player)),
                "wec": bool(self.wec is not None and self.wec.ha(gs.player))}

    def prossimo(self, gs):
        if hasattr(self.season, "prossimo_evento"):
            return self.season.prossimo_evento(gs)
        # prima del calendario unico si correvano solo i gran premi, e Formula
        # E ed endurance le chiudeva tutte la fine della stagione
        if gs.phase != "offseason" and gs.round < len(gs.tracks):
            return {"serie": "f1", "pista": gs.tracks[gs.round]}
        return None

    def gioca(self, gs, gare_f1: int, eventi_max: int = EVENTI_MAX) -> dict:
        """Avanti nel calendario finche' non si sono corsi `gare_f1` gran premi."""
        fatti = {}
        for _ in range(eventi_max):
            if fatti.get("f1", 0) >= gare_f1:
                break
            ev = self.prossimo(gs)
            if ev is None:
                break
            serie = ev.get("serie", "f1")
            if serie == "f1":
                self.weekend(gs, ev["pista"])
            elif serie == "fe":
                self.fe.simula_gara(gs, gs.player)
            elif serie == "wec":
                self.wec.avanza(gs)
            else:
                raise Impossibile(f"la sonda non sa correre un evento della serie "
                                  f"'{serie}': va aggiornata (Gioco.gioca)")
            fatti[serie] = fatti.get(serie, 0) + 1
        return fatti

    def altri_campionati(self, gs) -> dict:
        """Una tappa di Formula E e una di endurance, subito, fuori calendario.

        fe_stato e wec_stato tornano dal file tali e quali, e a meta' stagione
        il codice di adesso continua il campionato che ha aperto quello di
        prima: una chiave nuova di quei dizionari letta con le quadre si rompe
        solo li', alla prima tappa dopo la ricarica. Il prossimo evento del
        calendario pero' e' quasi sempre un gran premio, e fino alla prossima
        tappa endurance ce ne sono tre: correrle tutte costerebbe dieci
        secondi, una tappa per campionato fuori ordine non costa niente.
        """
        fatti = {}
        if (self.fe is not None and self.fe.ha(gs.player)
                and self.fe.prossima(gs, gs.player)[0] is not None):
            self.fe.simula_gara(gs, gs.player)
            fatti["fe"] = 1
        if self.wec is not None and self.wec.ha(gs.player) and self.wec.prossima(gs) is not None:
            self.wec.avanza(gs)
            fatti["wec"] = 1
        return fatti

    def weekend(self, gs, tr) -> None:
        """Lo stesso ordine della scena del weekend, un passo dopo l'altro."""
        S = self.session
        ws = S.WeekendState(track=tr, weather=self.Weather.generate(tr, gs.rng))
        if self.tyres is not None and hasattr(self.tyres, "allocate"):
            self.tyres.allocate(gs, ws, self.tyres.suggested(tr))
        for _ in range(S.practice_sessions(tr)):
            S.run_practice(gs, ws)
        if getattr(tr, "sprint", False):
            S.run_qualifying(gs, ws, "sprint")
            self.corri(gs, ws, "sprint")
            ws.sprint_done = True
            if hasattr(S, "learn_from_sprint"):
                S.learn_from_sprint(gs, ws)
        S.run_qualifying(gs, ws, "gp")
        self.corri(gs, ws, "gp")
        self.season.after_race(gs)
        # la Commissione di meta' stagione: chi gioca la trova uscendo dal
        # weekend, e qui non vota, come chi la chiude senza scegliere
        if getattr(gs, "pending_votes", None) and gs.phase != "offseason":
            self.rules.close_meeting(gs, {})

    def corri(self, gs, ws, kind: str) -> None:
        sim = self.session.make_race(gs, ws, kind=kind)
        sim.fast_forward()
        self.season.apply_result(gs, ws, sim, kind=kind)

    def fine_stagione(self, gs) -> None:
        """Come la chiude la scena di fine anno: nessun cantiere, nessun voto."""
        self.season.end_season(gs)
        if self.inverno is not None and getattr(gs.player, "inverno_aperto", False):
            self.inverno.chiudi_giocatore(gs, [])
        self.rules.close_meeting(gs, {})

    # ------------------------------------------------------------ salvataggi
    def salva(self, gs) -> str:
        # esattamente quello che fa storage.write_save, sul desktop e nel browser
        return json.dumps(gs.to_dict(), ensure_ascii=False)

    def apri(self, testo: str):
        return self.GameState.from_dict(json.loads(testo))

    def prepara(self, gs) -> None:
        """Ricalcola prima della fotografia quello che from_dict ricalcola da se'.

        sync_engines riaggancia le vetture ai motoristi e rifa' integrazione e
        prezzo della fornitura: sono numeri che dipendono da altri, e nella
        partita in corso possono essere rimasti indietro di qualche gara. Se
        non li si rifa' anche qui, la ricarica sembra cambiarli.
        """
        if hasattr(gs, "sync_engines"):
            gs.sync_engines()


# -------------------------------------------------------------- fotografia
def foto(x, pila=None):
    """La partita come alberi di dizionari e liste, da confrontare."""
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, random.Random):
        return "<rng>"
    if isinstance(x, (types.FunctionType, types.MethodType, types.ModuleType, type)):
        return f"<{getattr(x, '__qualname__', type(x).__name__)}>"
    pila = set() if pila is None else pila
    if id(x) in pila:
        return "<giro>"
    pila.add(id(x))
    try:
        if isinstance(x, dict):
            return {k: foto(v, pila) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [foto(v, pila) for v in x]
        if isinstance(x, (set, frozenset)):
            return sorted((foto(v, pila) for v in x), key=repr)
        if hasattr(x, "tolist"):                  # numpy
            return x.tolist()
        attributi = getattr(x, "__dict__", None)
        if attributi is None:
            return repr(x)
        nome = type(x).__name__
        out = {CLASSE: nome}
        for k, v in attributi.items():
            if k.startswith("_") or (nome, k) in SALTA:
                continue
            out[k] = foto(v, pila)
        return out
    finally:
        pila.discard(id(x))


def conta_classi(albero, conti=None) -> dict:
    conti = {} if conti is None else conti
    if isinstance(albero, dict):
        if CLASSE in albero:
            conti[albero[CLASSE]] = conti.get(albero[CLASSE], 0) + 1
        for v in albero.values():
            conta_classi(v, conti)
    elif isinstance(albero, list):
        for v in albero:
            conta_classi(v, conti)
    return conti


def _vuoto(x) -> bool:
    # None, "", [] e {} dicono la stessa cosa: un attributo mai riempito.
    # new_game lascia None dove from_dict mette un dizionario vuoto
    return x is None or x == ASSENTE or (isinstance(x, (str, list, dict)) and not x
                                         and not (isinstance(x, dict) and CLASSE in x))


def _numero(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _oggetto(x) -> bool:
    return isinstance(x, dict) and CLASSE in x


def _per_id(lista):
    """{id: elemento} se ogni elemento ha un id suo, se no None."""
    if not lista:
        return None
    out = {}
    for el in lista:
        if not isinstance(el, dict):
            return None
        k = el.get("id")
        if not isinstance(k, (str, int)) or isinstance(k, bool) or k in out:
            return None
        out[k] = el
    return out


def breve(x, n: int = 70) -> str:
    if _oggetto(x):
        return f"<{x[CLASSE]} {x.get('id', '')}>".replace(" >", ">")
    if isinstance(x, str):
        s = x if x == ASSENTE else repr(x)
    elif isinstance(x, float):
        s = f"{x:.6g}"
        s = s if any(c in s for c in ".en") else s + ".0"
    else:
        try:
            s = json.dumps(x, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            s = repr(x)
    return s if len(s) <= n else s[:n - 3] + "..."


class Confronto:
    """Due fotografie della stessa partita, prima del salvataggio e dopo."""

    def __init__(self):
        self.perdite = {}       # (classe, attributo) -> raccolta
        self.tollerati = {}     # tipo -> {"Classe.attributo": quante volte}

    def segna(self, ctx, via, a, b) -> None:
        # ctx: la classe e l'attributo dell'oggetto piu' vicino, chi e' (l'id
        # della squadra, del pilota...) e il valore intero dell'attributo, che
        # serve al consiglio per dire come rileggerlo
        classe, attr, chi, valore = ctx
        g = self.perdite.setdefault((classe, attr), {"chi": [], "esempi": [], "valore": valore})
        if chi not in g["chi"]:
            g["chi"].append(chi)
        if len(g["esempi"]) < 3:
            g["esempi"].append({"dove": via, "prima": breve(a), "dopo": breve(b)})

    def tollera(self, tipo, ctx) -> None:
        voci = self.tollerati.setdefault(tipo, {})
        k = f"{ctx[0]}.{ctx[1]}"
        voci[k] = voci.get(k, 0) + 1

    def guarda(self, a, b, via: str, ctx) -> None:
        if _vuoto(a) and _vuoto(b):
            return
        if _oggetto(a) and _oggetto(b):
            if a[CLASSE] != b[CLASSE]:
                self.segna(ctx, via, f"<{a[CLASSE]}>", f"<{b[CLASSE]}>")
                return
            classe = a[CLASSE]
            chi = a.get("id") if isinstance(a.get("id"), (str, int)) else ctx[2]
            for k in list(a) + [k for k in b if k not in a]:
                if k == CLASSE:
                    continue
                if k not in a and not _vuoto(b[k]):
                    # c'e' solo dopo la ricarica: from_dict crea qualcosa che la
                    # partita in corso non aveva. Non si e' perso niente, ma si
                    # fa vedere
                    self.tollera("comparsi solo dopo la ricarica", (classe, k))
                    continue
                self.guarda(a.get(k, ASSENTE), b.get(k, ASSENTE), f"{via}.{k}",
                            (classe, k, chi, a.get(k, b.get(k))))
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a) != set(b) and {str(k) for k in a} == {str(k) for k in b}:
                # il JSON scrive ogni chiave come testo: un dizionario con le
                # chiavi numeriche torna indietro con le chiavi stringa, e chi lo
                # legge con un numero non trova piu' niente
                self.segna(ctx, via, "chiavi " + _tipi(a), "chiavi " + _tipi(b))
                a = {str(k): v for k, v in a.items()}
                b = {str(k): v for k, v in b.items()}
            for k in list(a) + [k for k in b if k not in a]:
                self.guarda(a.get(k, ASSENTE), b.get(k, ASSENTE), f"{via}[{k}]", ctx)
            return
        if isinstance(a, list) and isinstance(b, list):
            self._liste(a, b, via, ctx)
            return
        if _numero(a) and _numero(b):
            if a == b or abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b)):
                return
            # un arrotondamento voluto (to_dict scrive certe classifiche con
            # due decimali, per tenere piccolo il file): non e' una perdita.
            # Lo zero no: e' il valore di partenza di quasi tutto, e un numero
            # che torna a zero e' tornato al predefinito
            if isinstance(a, float) and b != 0 and any(round(a, n) == b for n in range(1, 7)):
                self.tollera("arrotondati", ctx)
                return
        if a != b:
            self.segna(ctx, via, a, b)

    def _liste(self, a, b, via, ctx) -> None:
        ida, idb = _per_id(a), _per_id(b)
        if ida is not None and idb is not None:
            if list(ida) != list(idb):
                if set(ida) == set(idb):
                    if ctx[:2] not in ORDINE_LIBERO:
                        self.segna(ctx, via, f"ordine {list(ida)[:4]}", f"ordine {list(idb)[:4]}")
                else:
                    persi = [k for k in ida if k not in idb]
                    nuovi = [k for k in idb if k not in ida]
                    self.segna(ctx, via,
                               f"{len(a)} elementi" + (f", fra cui {persi[:3]}" if persi else ""),
                               f"{len(b)} elementi" + (f", in piu' {nuovi[:3]}" if nuovi else ""))
            for k, el in ida.items():
                if k in idb:
                    self.guarda(el, idb[k], f"{via}[{k}]", ctx)
            return
        if len(a) != len(b):
            # gli elenchi che crescono si salvano accorciati (il libro mastro,
            # la storia degli aggiornamenti): se quello che torna e' la coda di
            # quello che c'era, e' un taglio voluto, non una perdita
            if 0 < len(b) < len(a):
                self.tollera("elenchi accorciati", ctx)
                coda = a[len(a) - len(b):]
                for i, (x, y) in enumerate(zip(coda, b)):
                    self.guarda(x, y, f"{via}[{len(a) - len(b) + i}]", ctx)
                return
            self.segna(ctx, via, f"{len(a)} elementi", f"{len(b)} elementi")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            self.guarda(x, y, f"{via}[{i}]", ctx)


def _tipi(d: dict) -> str:
    return "/".join(sorted({type(k).__name__ for k in d}))


# ------------------------------------------------- le chiavi dei salvataggi
def chiavi_perse(vecchio, nuovo, via: str = "", out=None, vero: str = "") -> dict:
    """Le chiavi di un salvataggio che il codice di adesso non riscrive.

    La prova (b) non vede un nome cambiato: se to_dict e from_dict passano
    tutti e due da `car_memoria` a `memoria_vettura`, o se un campo di Driver
    cambia nome, la partita di adesso torna uguale. Le partite di prima pero'
    hanno ancora il nome vecchio, che nessuno legge piu', e lo perdono senza
    un errore (Driver e Staff scartano le chiavi che non conoscono). Si vede
    aprendo un salvataggio di prima e risalvandolo subito: le chiavi che
    c'erano e non ci sono piu' sono quello che si perde.

    Le chiavi che sono nomi di qualcosa (le squadre, i piloti, i pezzi della
    vettura) diventano `*` e gli indici delle liste `[]`, cosi' cento piloti
    che perdono la stessa chiave sono una voce sola; `vero` e' il percorso
    com'e', per l'esempio.
    """
    out = {} if out is None else out
    if isinstance(vecchio, dict) and isinstance(nuovo, dict):
        nomi = len(vecchio) > 1 and all(isinstance(v, dict) for v in vecchio.values())
        comparse = [k for k in nuovo if k not in vecchio and not _vuoto(nuovo[k])]
        for k, v in vecchio.items():
            passo = (via + "." if via else "") + ("*" if nomi else str(k))
            passo_vero = (vero + "." if vero else "") + str(k)
            if k in nuovo:
                chiavi_perse(v, nuovo[k], passo, out, passo_vero)
            elif not _vuoto(v):
                g = out.setdefault(passo, {"quanti": 0, "esempio": "", "zero": True,
                                           "al_posto": []})
                g["quanti"] += 1
                # uno zero dice poco di quello che si perde: meglio un
                # esempio con un valore vero, se c'e'
                zero = isinstance(v, (bool, int, float)) and not v
                if not g["esempio"] or (g["zero"] and not zero):
                    g["esempio"], g["zero"] = f"{passo_vero} = {breve(v, 50)}", zero
                for c in comparse:
                    if c not in g["al_posto"] and len(g["al_posto"]) < 3:
                        g["al_posto"].append(str(c))
    elif isinstance(vecchio, list) and isinstance(nuovo, list):
        for i, (x, y) in enumerate(zip(vecchio, nuovo)):
            chiavi_perse(x, y, via + "[]", out, f"{vero}[{i}]")
    return out


# Chi rilegge cosa: dal percorso di una chiave persa, dove si mette la
# traduzione del nome vecchio. Le dataclass si costruiscono da un dizionario
# filtrato sui campi (None: la traduzione va fatta sul dizionario, prima),
# il resto di from_dict legge chiave per chiave da `td` o da `data`.
LETTORI = (("drivers.", "Driver.from_dict (game/model/people.py)", None),
           ("free_agents[]", "Driver.from_dict (game/model/people.py)", None),
           ("free_staff[]", "Staff.from_dict (game/model/people.py)", None),
           ("fe_staff[]", "Staff.from_dict (game/model/people.py)", None),
           ("teams.*.staff[]", "Staff.from_dict (game/model/people.py)", None),
           ("teams.*.dev_projects[]", "il filtro su fields(Project) in from_dict", None),
           ("teams.*.spec_trials[]", "il filtro su fields(Trial) in from_dict", None),
           ("teams.*.kits[]", "il filtro su fields(Kit) in from_dict", None),
           ("teams.*.", "il giro delle squadre in GameState.from_dict", "td"),
           ("", "GameState.from_dict", "data"))


def lettore(percorso: str) -> tuple:
    """(chi rilegge la chiave, da che dizionario) e il nome della chiave."""
    chi, sorgente = next((d, s) for p, d, s in LETTORI if percorso.startswith(p))
    return chi, sorgente, re.split(r"[.\[\]]+", percorso.rstrip("[]"))[-1]


def consiglio_chiave(percorso: str, esempio: str, al_posto: list) -> list:
    chi, sorgente, foglia = lettore(percorso)
    if foglia == "*":
        return [(f"Un elemento intero ({esempio.split(' = ')[0]}) c'e' nel salvataggio di "
                 f"prima e sparisce appena riaperto: guardare {chi}.")]
    nuovo = al_posto[0] if len(al_posto) == 1 else "nome_nuovo"
    out = [(f"I salvataggi di prima hanno '{foglia}' e il codice di adesso non lo rilegge "
            f"piu' (rinominato o tolto?): chi apre una partita vecchia lo perde senza un "
            f"errore.")]
    if al_posto:
        out.append(f"Accanto, il codice di adesso scrive: {', '.join(al_posto)}.")
    if sorgente is None:
        out.append(f"Se e' rinominato, {chi} deve tradurre il nome vecchio nel dizionario "
                   f"prima di costruire (d e' il dizionario di ciascuno):")
        out.append(f'    if "{foglia}" in d and "{nuovo}" not in d: '
                   f'd = {{**d, "{nuovo}": d["{foglia}"]}}')
    else:
        out.append(f"Se e' rinominato, {chi} deve leggere anche il nome vecchio:")
        out.append(f'    ... = {sorgente}.get("{nuovo}", {sorgente}.get("{foglia}", '
                   f'<il predefinito di adesso>))')
    out.append("Se e' tolto apposta, dirlo: e' questo che perdono le partite di prima.")
    return out


# ---------------------------------------------------------------- i consigli
class Fonti:
    """Dove stanno to_dict e from_dict nel codice provato, riga per riga.

    I consigli dicono la riga da aggiungere e dove: le righe si cercano nel
    sorgente vero, non si scrivono a mano qui, cosi' restano giuste anche
    quando state.py cresce.
    """

    def __init__(self, gioco: Gioco):
        self.gioco = gioco
        GS = gioco.GameState
        self.file = Path(inspect.getsourcefile(GS))
        self.nome = _relativo(self.file, gioco.radice)
        self.righe = self.file.read_text(encoding="utf-8").splitlines()
        self.to = _intervallo(GS.to_dict)
        self.fr = _intervallo(GS.from_dict)
        # dentro to_dict il blocco di ogni squadra, dentro from_dict il giro
        # che le rilegge: e' li' che vive quasi tutto lo stato
        self.to_sq = (self.cerca(self.to, '"teams"') or self.to[0], self.to[1])
        inizio = self.cerca(self.fr, 'data["teams"]') or self.fr[0]
        fine = self.cerca((inizio, self.fr[1]), "sync_engines") or self.fr[1]
        self.fr_sq = (inizio, fine)
        self.classi = {}
        for nome_mod, mod in list(sys.modules.items()):
            if not nome_mod.startswith("game.") or mod is None:
                continue
            for nome, obj in vars(mod).items():
                if (isinstance(obj, type) and getattr(obj, "__module__", "") == nome_mod
                        and dataclasses.is_dataclass(obj)):
                    self.classi.setdefault(nome, obj)

    def cerca(self, intervallo, testo: str):
        for n in range(intervallo[0], intervallo[1] + 1):
            if testo in self.righe[n - 1]:
                return n
        return None

    def menzioni(self, intervallo, parola: str) -> list:
        rx = re.compile(r"\b" + re.escape(parola) + r"\b")
        return [n for n in range(intervallo[0], intervallo[1] + 1)
                if rx.search(self.righe[n - 1])]

    def dove(self, intervallo) -> str:
        return f"{self.nome}:{intervallo[0]}-{intervallo[1]}"

    # ----------------------------------------------------------------
    def consiglio(self, classe: str, attr: str, valore) -> list:
        try:
            if classe == "GameState":
                return self._partita(attr, valore)
            if classe == "Team":
                return self._squadra(attr, valore)
            if classe == "Car":
                return self._vettura(attr, valore)
            if classe == "Part":
                return self._pezzo(attr)
            cls = self.classi.get(classe)
            if cls is not None:
                return self._dataclass(cls, attr, valore)
        except Exception as exc:             # un consiglio non deve fermare la sonda
            return [f"(consiglio non disponibile: {exc})"]
        return [(f"{classe} non e' una dataclass del gioco: cercare dove si salva "
                 f"(to_dict in {self.dove(self.to)}).")]

    def _due_lati(self, attr, to_rng, fr_rng, riga_to, riga_fr) -> list:
        to = self.menzioni(to_rng, attr)
        fr = self.menzioni(fr_rng, attr)
        out = []
        if to:
            out.append(f"to_dict lo scrive ({self.nome}:{to[0]}).")
        else:
            out.append(f"to_dict non lo scrive: aggiungere in {self.dove(to_rng)}")
            out.append(f"    {riga_to}")
        if fr:
            out.append(f"from_dict lo legge ({self.nome}:{fr[0]}).")
        else:
            out.append(f"from_dict non lo rilegge: aggiungere in {self.dove(fr_rng)}")
            out.append(f"    {riga_fr}")
        if to and fr:
            out.append("Li nomina tutti e due e il valore cambia lo stesso: controllare la "
                       "chiave, il tipo, un arrotondamento, o chi lo riscrive dopo "
                       "(new_game, sync_engines, _sync_to_regulations).")
        return out

    def _partita(self, attr, valore) -> list:
        # un attributo della partita puo' non esistere affatto finche' qualcuno
        # non lo scrive (fe_merito nasce a fine stagione): si legge con getattr
        resto = 'getattr(gs, "' + attr + '", ' + _zero(valore) + ")"
        return self._due_lati(
            attr, self.to, self.fr,
            f'"{attr}": getattr(self, "{attr}", {_zero(valore)}),',
            f"gs.{attr} = {_lettura('data', attr, valore, resto)}")

    def _squadra(self, attr, valore) -> list:
        campo = attr in {f.name for f in dataclasses.fields(self.classi["Team"])} \
            if "Team" in self.classi else True
        resto = f"t.{attr}" if campo else 'getattr(t, "' + attr + '", ' + _zero(valore) + ")"
        return self._due_lati(
            attr, self.to_sq, self.fr_sq,
            f'"{attr}": t.{attr},',
            f"t.{attr} = {_lettura('td', attr, valore, resto)}")

    def _vettura(self, attr, valore) -> list:
        chiave = f"car_{attr}"
        out = self._due_lati(
            attr, self.to_sq, self.fr_sq,
            f'"{chiave}": t.car.{attr},',
            f"t.car.{attr} = {_lettura('td', chiave, valore, f't.car.{attr}')}")
        out.append("La vettura si salva a pezzi dentro la squadra (car_parts, setup, "
                   "balance): se il valore si ricava da altri (regolamento, motorista), "
                   "e' meglio ricalcolarlo in from_dict che salvarlo.")
        return out

    def _pezzo(self, attr) -> list:
        to = self.cerca(self.to_sq, '"car_parts"')
        fr = self.cerca(self.fr_sq, 'td["car_parts"]')
        return [(f"Di ogni pezzo si salvano solo perf, condition e focus "
                 f"({self.nome}:{to}): aggiungere li'"),
                f'    "{attr}": p.{attr},',
                f"e rileggerlo nel giro dei pezzi ({self.nome}:{fr}):",
                f'    t.car.parts[k].{attr} = p.get("{attr}", t.car.parts[k].{attr})']

    def _dataclass(self, cls, attr, valore) -> list:
        nome = cls.__name__
        file = _relativo(Path(inspect.getsourcefile(cls)), self.gioco.radice)
        riga = inspect.getsourcelines(cls)[1]
        campi = {f.name for f in dataclasses.fields(cls)}
        if attr not in campi:
            out = [(f"{nome}.{attr} non e' un campo della dataclass ({file}:{riga}): "
                    f"to_dict usa asdict, che vede solo i campi, e il salvataggio non "
                    f"lo porta. Dichiararlo nella classe, con un predefinito per i "
                    f"salvataggi di prima:"),
                   f"    {attr}: {_tipo(valore)} = {_zero(valore)}"]
            if nome in ("Deal", "RaceResult"):
                n = self.cerca(self.fr, f"{nome}(**")
                out.append(f"({self.nome}:{n} lo ricostruisce con {nome}(**...), che "
                           f"accetta il campo nuovo; i salvataggi vecchi prendono il "
                           f"predefinito.)")
            return out
        if nome == "RaceResult":
            n = self.cerca(self.to, '"results"')
            return [f"I risultati si scrivono chiave per chiave ({self.nome}:{n}): manca",
                    f'    "{attr}": r.{attr},']
        if nome in ("Campionato", "Posto"):
            n = self.cerca(self.to, '"campionati"')
            m = self.cerca(self.fr, "Campionato(")
            return [(f"I campionati minori si salvano a liste ({self.nome}:{n}) e si "
                     f"rileggono per posizione ({self.nome}:{m}): aggiungere {attr} in "
                     f"fondo alla lista e rileggerlo solo se c'e' (r[i] if len(r) > i "
                     f"else predefinito), per i salvataggi di prima.")]
        if nome == "Track":
            n = self.cerca(self.to, '"calendar"')
            return [(f"Dei circuiti si salvano solo contract_until, fee e month "
                     f"({self.nome}:{n}); il resto si ricostruisce da data/tracks.json e "
                     f"dalla taratura. Se {attr} cambia giocando, va aggiunto li' e "
                     f"riletto in _restore_calendar.")]
        n = self.cerca(self.fr, f"{nome}(") or self.cerca(self.fr, f"{nome}.from_dict")
        return [f"{attr} e' un campo di {nome} ({file}:{riga}), quindi asdict lo salva: "
                f"qualcosa lo cambia mentre la partita si ricarica. Guardare dove "
                f"{self.nome} ricostruisce {nome}" + (f" (riga {n})" if n else "") +
                " e chi lo riscrive dopo."]


def _intervallo(funzione) -> tuple:
    righe, inizio = inspect.getsourcelines(funzione)
    return inizio, inizio + len(righe) - 1


def _relativo(p: Path, radice: Path) -> str:
    try:
        return p.resolve().relative_to(radice.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _zero(valore) -> str:
    if isinstance(valore, bool):
        return "False"
    if isinstance(valore, int):
        return "0"
    if isinstance(valore, float):
        return "0.0"
    if isinstance(valore, str):
        return '""'
    if isinstance(valore, list):
        return "[]"
    if isinstance(valore, dict) and not _oggetto(valore):
        return "{}"
    return "None"


def _tipo(valore) -> str:
    for t, nome in ((bool, "bool"), (int, "int"), (float, "float"), (str, "str"), (list, "list")):
        if isinstance(valore, t):
            return nome
    return "dict" if isinstance(valore, dict) and not _oggetto(valore) else "object"


def _lettura(sorgente: str, chiave: str, valore, resto: str) -> str:
    """Come si rilegge una chiave che i salvataggi di prima non hanno.

    Se la chiave manca si tiene `resto`, cioe' quello che new_game ha messo
    leggendo data/: per una partita vecchia e' il valore giusto, mentre uno
    zero o un dizionario vuoto le cancellerebbero quello che aveva.
    """
    if isinstance(valore, bool):
        return f'bool({sorgente}.get("{chiave}", {resto}))'
    if isinstance(valore, int):
        return f'int({sorgente}.get("{chiave}", {resto}))'
    if isinstance(valore, float):
        return f'float({sorgente}.get("{chiave}", {resto}))'
    if isinstance(valore, list):
        return f'list({sorgente}.get("{chiave}") or {resto} or [])'
    if isinstance(valore, dict) and not _oggetto(valore):
        return f'dict({sorgente}.get("{chiave}") or {resto} or {{}})'
    return f'{sorgente}.get("{chiave}", {resto})'


def descrivi_errore(exc: BaseException, radice: Path) -> dict:
    """L'errore, con le righe del gioco da cui e' passato e un consiglio."""
    righe = []
    for fr in traceback.extract_tb(exc.__traceback__):
        rel = _relativo(Path(fr.filename), radice)
        if rel.startswith("game/"):
            righe.append({"file": rel, "riga": fr.lineno, "funzione": fr.name,
                          "codice": (fr.line or "").strip()})
    out = {"tipo": type(exc).__name__, "messaggio": str(exc)[:400],
           "righe": righe[-4:], "traccia": traceback.format_exc()[-3000:]}
    out["consiglio"] = consiglio_rotto(out, radice)
    return out


def consiglio_rotto(err: dict, radice: Path) -> str:
    tipo, msg = err["tipo"], err["messaggio"]
    ultima = err["righe"][-1] if err["righe"] else None
    dove = f"{ultima['file']}:{ultima['riga']} ({ultima['codice']})" if ultima else "?"
    if tipo == "TypeError" and "unexpected keyword argument" in msg:
        m = re.search(r"(\w+)\.__init__\(\).*'(\w+)'", msg)
        cls, campo = (m.group(1), m.group(2)) if m else ("la classe", "?")
        filtro = ""
        try:
            testo = (radice / STATE).read_text(encoding="utf-8").splitlines()
            n = next(i for i, r in enumerate(testo, 1) if "fields(Project)" in r)
            filtro = f" come per Project ({STATE}:{n})"
        except (OSError, StopIteration):
            pass
        return (f"I salvataggi di prima hanno la chiave '{campo}', che {cls} non ha piu' "
                f"(rinominata o tolta?). {dove} passa al costruttore tutte le chiavi del "
                f"file: o si tiene il nome vecchio, o si filtrano le chiavi{filtro} e si "
                f"traduce '{campo}' nel nome nuovo prima di costruire.")
    if tipo == "TypeError" and "required" in msg and "missing" in msg:
        return (f"Un campo nuovo senza predefinito: i salvataggi di prima non ce l'hanno. "
                f"Dargli un valore predefinito nella dataclass ({dove}).")
    if tipo == "KeyError":
        stati = ultima and ultima["file"].endswith(("formulae.py", "wec.py"))
        return (f"{dove} legge la chiave {msg} con le parentesi quadre, e i salvataggi di "
                f"prima non ce l'hanno: leggerla con .get({msg}, predefinito)."
                + (" Qui e' fe_stato o wec_stato, che un salvataggio di prima si porta "
                   "dietro com'era fino alla stagione dopo." if stati else ""))
    if tipo == "AttributeError":
        return (f"La partita caricata non ha un attributo che il codice si aspetta ({dove}): "
                f"from_dict deve crearlo anche quando il salvataggio non lo porta, o la "
                f"classe deve dargli un predefinito.")
    return f"Si ferma in {dove}."


# ------------------------------------------------------------- i due figli
def _scrivi(percorso: Path, esito: dict) -> None:
    percorso.write_text(json.dumps(esito, ensure_ascii=True, indent=1), encoding="utf-8")


def controlla(gioco: Gioco, fonti, gs, momento: str, esito: dict, cartella, indice: int,
              confronta: bool = True) -> dict:
    """Salva, ricarica e confronta: la prova (b) in un momento della carriera.

    Con `confronta` falso si salva e basta: a una base vecchia si chiedono solo
    i salvataggi da aprire, e ogni riapertura le costerebbe la taratura intera.
    """
    c = {"momento": momento, "stagione": gs.season, "gara": gs.round, "fase": gs.phase}
    esito["controlli"].append(c)
    esito["fase"] = f"{momento}: salvataggio"
    gioco.prepara(gs)
    prima = foto(gs)
    testo = gioco.salva(gs)
    c["kb"] = round(len(testo.encode("utf-8")) / 1024.0, 1)
    if cartella is not None:
        f = Path(cartella) / f"{indice}_{momento.replace(' ', '_')}.json"
        f.write_text(testo, encoding="utf-8")
        c["file"] = str(f)
    _scrivi(Path(esito["_file"]), esito)
    if not confronta:
        return c
    esito["fase"] = f"{momento}: riapertura"
    gs2 = gioco.apri(testo)
    # quello che il codice di questa cartella non rilegge dei suoi stessi
    # salvataggi: e' il termine di paragone per le chiavi perse della prova (a)
    esito["fase"] = f"{momento}: salvataggio subito dopo la riapertura"
    c["chiavi_perse"] = chiavi_perse(json.loads(testo), json.loads(gioco.salva(gs2)))
    esito["fase"] = f"{momento}: confronto"
    dopo = foto(gs2)
    conf = Confronto()
    conf.guarda(prima, dopo, "gs", ("GameState", "", "partita", None))
    conti = conta_classi(prima)
    c["oggetti"] = {k: conti.get(k, 0) for k in ("Team", "Driver", "Staff", "Deal")}
    c["tollerati"] = conf.tollerati
    c["perdite"] = []
    for (classe, attr), g in conf.perdite.items():
        c["perdite"].append({
            "chiave": f"{classe}.{attr}", "classe": classe, "attributo": attr,
            "quanti": len(g["chi"]), "su": conti.get(classe, 1), "chi": g["chi"][:6],
            "esempi": g["esempi"],
            "consiglio": fonti.consiglio(classe, attr, g["valore"]) if fonti else []})
    return c


def figlio(args) -> int:
    sys.dont_write_bytecode = True
    radice = Path(args.radice).resolve()
    esito = {"ok": False, "ruolo": args.figlio, "fase": "import", "controlli": [],
             "_file": args.esito}
    file_esito = Path(args.esito)
    t0 = time.perf_counter()
    try:
        gioco = Gioco(radice)
        if args.figlio == "carriera":
            esito["fase"] = "nuova carriera"
            _scrivi(file_esito, esito)
            gs = gioco.nuova()
            esito["squadra"], esito["programmi"] = gs.player_team, gioco.programmi(gs)
            fonti = Fonti(gioco)
            esito["fase"] = "gioco"
            _scrivi(file_esito, esito)
            esito["eventi"] = gioco.gioca(gs, GARE_F1)
            confronta = not args.senza_confronto
            controlla(gioco, fonti, gs, "a stagione in corso", esito, args.salva_in, 1, confronta)
            esito["fase"] = "fine stagione"
            _scrivi(file_esito, esito)
            gioco.fine_stagione(gs)
            controlla(gioco, fonti, gs, "in inverno", esito, args.salva_in, 2, confronta)
        else:
            esito["fase"] = "apertura"
            _scrivi(file_esito, esito)
            testo = Path(args.file).read_text(encoding="utf-8")
            gs = gioco.apri(testo)
            esito["stagione"], esito["gara"] = gs.season, gs.round
            esito["programmi"] = gioco.programmi(gs)
            # prima di giocare, cosi' si vede solo quello che fa la ricarica
            esito["fase"] = "salvataggio subito dopo l'apertura"
            esito["chiavi_perse"] = chiavi_perse(json.loads(testo), json.loads(gioco.salva(gs)))
            if not args.solo_apri:
                esito["fase"] = "gioco"
                # un po' di partita: una tappa degli altri due campionati, poi
                # avanti fino al prossimo gran premio
                fatti = gioco.altri_campionati(gs)
                for k, n in gioco.gioca(gs, 1, eventi_max=10).items():
                    fatti[k] = fatti.get(k, 0) + n
                esito["eventi"] = fatti
                esito["fase"] = "nuovo salvataggio"
                testo = gioco.salva(gs)
                esito["fase"] = "riapertura del nuovo salvataggio"
                gioco.apri(testo)
        esito["ok"] = True
        esito["fase"] = "fine"
    except Impossibile as exc:
        esito["sonda"] = str(exc)
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("game"):
            esito["mancante"] = exc.name
        esito["errore"] = descrivi_errore(exc, radice)
    except Exception as exc:     # qualunque cosa rompa il gioco e' la notizia
        esito["errore"] = descrivi_errore(exc, radice)
        if esito["fase"].endswith("confronto"):
            # e' la sonda che non sa leggere la partita, non il gioco rotto
            esito["sonda"] = f"errore della sonda nel confronto: {exc}"
    finally:
        esito["secondi"] = round(time.perf_counter() - t0, 1)
        esito.pop("_file", None)
        _scrivi(file_esito, esito)
    return 0


# ================================================================== il padre
def git(*argomenti, binario: bool = False):
    return subprocess.run(["git", "-C", str(RADICE), *argomenti], capture_output=True, check=False,
                          **({} if binario else {"text": True, "encoding": "utf-8",
                                                 "errors": "replace"}))


def risolvi(base: str) -> tuple:
    if shutil.which("git") is None:
        raise Impossibile("git non c'e': serve per estrarre il codice della base.")
    r = git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    sha = r.stdout.strip()
    if r.returncode != 0 or not sha:
        superficiale = git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"
        raise Impossibile(f"il commit '{base}' non c'e' in questo repository" +
                          (" (il clone e' superficiale: se e' un commit vecchio, "
                           "git fetch --unshallow)" if superficiale else "") + ".")
    riga = git("log", "-1", "--format=%h %s", sha).stdout.strip()
    corto, _, titolo = riga.partition(" ")
    return sha, corto or sha[:7], titolo


def diversi_dalla_base(sha: str) -> list:
    """I file del gioco che la cartella di lavoro ha diversi dalla base."""
    a = git("diff", "--name-only", sha, "--", "game", "data").stdout.split()
    b = git("ls-files", "--others", "--exclude-standard", "--", "game", "data").stdout.split()
    return sorted(set(a) | set(b))


def estrai(sha: str, dove: Path) -> None:
    """Il codice e i dati della base, senza toccare la cartella di lavoro."""
    r = git("archive", "--format=tar", sha, "game", "data", binario=True)
    if r.returncode != 0:
        raise Impossibile("git archive non ha estratto la base: "
                          + r.stderr.decode("utf-8", "replace").strip()[:300])
    dove.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dove, filter="data")
        else:
            tar.extractall(dove)
    # Le tarature gia' fatte: la chiave dice da che codice vengono, quindi se
    # la base ha lo stesso modello del giro le ritrova e non ritara da capo
    # trentacinque circuiti (otto secondi). Una base diversa non le usa.
    cache = RADICE / "cache" / "tarature"
    if cache.is_dir():
        dest = dove / "cache" / "tarature"
        dest.mkdir(parents=True)
        for f in cache.glob("*.pkl"):
            try:
                shutil.copyfile(f, dest / f.name)
            except OSError:
                pass


def _togli_sola_lettura(funzione, percorso, _info) -> None:
    # su Windows un file in sola lettura non si cancella: lo si rende
    # scrivibile e si riprova
    try:
        os.chmod(percorso, stat.S_IWRITE)
        funzione(percorso)
    except OSError:
        pass


def cancella(cartella: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(cartella, onexc=_togli_sola_lettura)
    else:
        shutil.rmtree(cartella, onerror=_togli_sola_lettura)


def lancia(ruolo: str, radice: Path, file_esito: Path, cwd: Path, **opzioni) -> dict:
    """Un figlio con il suo Python, e il suo esito letto dal file che scrive."""
    cmd = [sys.executable, str(Path(__file__).resolve()), "--figlio", ruolo,
           "--radice", str(radice), "--esito", str(file_esito)]
    for k, v in opzioni.items():
        if v is None or v is False:
            continue
        cmd += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
    env = dict(os.environ)
    env.update({"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
                "PYGAME_HIDE_SUPPORT_PROMPT": "1", "PYTHONIOENCODING": "utf-8",
                # lo stesso ordine dei set a ogni giro: senza, due giri della
                # sonda sulla stessa modifica potrebbero giocare due partite
                "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=LIMITE_S, check=False)
        scaduto, coda = False, (r.stderr or "")[-1500:]
    except subprocess.TimeoutExpired:
        scaduto, coda = True, ""
    try:
        esito = json.loads(file_esito.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        esito = {"ok": False, "fase": "avvio", "controlli": [],
                 "errore": {"tipo": "processo", "messaggio": coda or "nessun esito",
                            "righe": [], "consiglio": ""}}
    if scaduto:
        esito["ok"] = False
        esito["scaduto"] = True
        esito.setdefault("errore", {"tipo": "tempo", "righe": [], "consiglio": "",
                                    "messaggio": f"non ha finito in {LIMITE_S} s"})
    esito.setdefault("secondi", round(time.perf_counter() - t0, 1))
    return esito


def prova(base: str) -> dict:
    """Le due prove, e tutto quello che serve per giudicarle.

    `--base` dice di chi sono i salvataggi da aprire. Quello che si perdeva gia'
    prima della modifica invece si misura sempre su HEAD, anche quando la base
    e' un commit vecchio: una perdita arrivata fra quel commit e HEAD non e'
    colpa del lavoro di adesso, e non deve cambiare l'esito.
    """
    sha, corto, titolo = risolvi(base)
    testa, testa_corto, _ = risolvi("HEAD")
    r = {"base": base, "commit": corto, "titolo": titolo, "head": testa_corto,
         "diversi": diversi_dalla_base(testa), "squadra": SQUADRA, "seme": SEME}
    tmp = Path(tempfile.mkdtemp(prefix="sonda_salvataggi_"))
    try:
        estrai(sha, tmp / "base")
        if testa != sha:
            estrai(testa, tmp / "head")
        salvataggi = tmp / "salvataggi"
        salvataggi.mkdir()
        with ThreadPoolExecutor(max_workers=4) as ex:
            # la base, HEAD e il codice di adesso giocano la stessa carriera
            # insieme; appena la base ha i suoi salvataggi, li apre il codice di
            # adesso, mentre gli altri magari girano ancora
            f_base = ex.submit(lancia, "carriera", tmp / "base", tmp / "base.json", tmp,
                               salva_in=salvataggi, senza_confronto=testa != sha)
            f_testa = (ex.submit(lancia, "carriera", tmp / "head", tmp / "head.json", tmp)
                       if testa != sha else None)
            f_ora = ex.submit(lancia, "carriera", RADICE, tmp / "ora.json", tmp)
            r["e_base"] = f_base.result()
            file_base = [c["file"] for c in r["e_base"].get("controlli", []) if c.get("file")]
            f_car = [ex.submit(lancia, "carica", RADICE, tmp / f"carica{i}.json", tmp, file=f)
                     for i, f in enumerate(file_base)]
            # Una base vecchia aveva chiavi che HEAD non rilegge gia' piu': il
            # termine di paragone e' HEAD che apre gli stessi salvataggi, e
            # basta aprirli. Con la base uguale a HEAD lo fa gia' la carriera
            # della base, che riapre quello che ha appena salvato.
            f_rif = ([ex.submit(lancia, "carica", tmp / "head", tmp / f"rif{i}.json", tmp,
                                file=f, solo_apri=True) for i, f in enumerate(file_base)]
                     if testa != sha else [])
            r["e_ora"] = f_ora.result()
            r["e_head"] = f_testa.result() if f_testa is not None else r["e_base"]
            r["e_carica"] = [f.result() for f in f_car]
            r["e_rif"] = [f.result() for f in f_rif]
            momenti = [c for c in r["e_base"].get("controlli", []) if c.get("file")]
            for e, c in zip(r["e_carica"], momenti):
                e["momento"], e["kb_base"] = c["momento"], c.get("kb")
            for e, c in zip(r["e_rif"], momenti):
                e["momento"] = c["momento"]
    finally:
        cancella(tmp)
    return r


def _righe_errore(err: dict) -> list:
    righe, viste = [f"{err.get('tipo', '')}: {err.get('messaggio', '')}"], set()
    for x in err.get("righe", []):
        if (x["file"], x["riga"]) not in viste:          # la list comprehension ripete la riga
            viste.add((x["file"], x["riga"]))
            righe.append(f"  {x['file']}:{x['riga']} in {x['funzione']}: {x['codice']}")
    return righe + ([err["consiglio"]] if err.get("consiglio") else [])


def giudica(r: dict) -> dict:
    """Da quello che hanno visto i figli, il verdetto e le righe da stampare."""
    base, ora, testa, carichi = r["e_base"], r["e_ora"], r["e_head"], r["e_carica"]
    problemi, vecchi, note, impossibile = [], [], [], []
    sigla, sigla_testa = r["commit"], r["head"]

    tutti = (base, ora, testa, *carichi)
    mancanti = sorted({e["mancante"] for e in tutti if e.get("mancante")})
    if mancanti:
        raise Impossibile(f"mancano le librerie del gioco ({', '.join(mancanti)}): "
                          f"python -m pip install -r requirements.txt")
    for e in tutti:
        if e.get("sonda") and e["sonda"] not in impossibile:
            impossibile.append(e["sonda"])

    # (a) i salvataggi della base, aperti dal codice di adesso. Due salvataggi
    # che si rompono nello stesso punto sono un problema solo
    if not base.get("ok"):
        err = base.get("errore") or {}
        note.append(f"Il codice di {sigla} si ferma ({base.get('fase')}): "
                    f"{err.get('tipo', '')}: {err.get('messaggio', '')}")
    if not carichi:
        impossibile.append(f"il codice di {sigla} non ha prodotto nessun salvataggio: "
                           f"la prova (a) non si e' potuta fare")
    rotti = {}
    for e in carichi:
        if e.get("ok"):
            continue
        err = e.get("errore") or {}
        righe = _righe_errore(err)
        if tuple(righe) in rotti:
            rotti[tuple(righe)]["momenti"].append(e.get("momento", ""))
            continue
        voce = {"esito": "ROTTO", "momenti": [e.get("momento", "")], "fase": e.get("fase"),
                "righe": righe}
        rotti[tuple(righe)] = voce
        problemi.append(voce)
    for voce in rotti.values():
        fase = voce.pop("fase")
        # si apre e si rompe alla prima tappa e' un'altra correzione rispetto
        # a non si apre: il titolo lo dice
        cosa = ("non si apre con il codice di adesso" if fase in ("apertura", "import", "avvio")
                else "si apre con il codice di adesso ma si rompe")
        voce["titolo"] = (f"il salvataggio di {sigla} {' e '.join(voce['momenti'])} {cosa} "
                          f"({fase})")

    # (a) le chiavi dei salvataggi della base che il codice di adesso non
    # rilegge. Il paragone e' HEAD che apre gli stessi file: quello che perde
    # gia' lui non e' colpa della modifica
    if testa is base:
        rif = {c["momento"]: c.get("chiavi_perse") for c in base.get("controlli", [])
               if c.get("file")}
    else:
        rif = {e.get("momento"): e.get("chiavi_perse") for e in r.get("e_rif", [])}
    # Un campo di Driver rinominato si perde in tre posti (i piloti, gli
    # svincolati, i piloti di Formula E): e' una correzione sola, quindi una
    # voce sola, per chi rilegge e per nome della chiave
    gruppi, senza_rif = {}, set()
    for e in carichi:
        nuove = set()
        gia_rif = rif.get(e.get("momento"))
        for patt, g in (e.get("chiavi_perse") or {}).items():
            if gia_rif is None:
                senza_rif.add(patt)
                continue
            chi, _, foglia = lettore(patt)
            k = (chi, foglia, patt not in gia_rif)
            if k[2]:
                nuove.add(k)
            v = gruppi.setdefault(k, {"percorsi": [], "momenti": [], "esempi": [],
                                      "al_posto": [], "primo": (patt, g)})
            if patt not in v["percorsi"]:
                v["percorsi"].append(patt)
                v["esempi"].append(f"{g['esempio']} -> non riletto"
                                   + (f" (e altri {g['quanti'] - 1})" if g["quanti"] > 1 else ""))
            if e.get("momento", "") not in v["momenti"]:
                v["momenti"].append(e.get("momento", ""))
            v["al_posto"] += [c for c in g["al_posto"] if c not in v["al_posto"]]
        e["chiavi_nuove"] = len(nuove)
    for (_, _, nuova), v in gruppi.items():
        patt, g = v["primo"]
        voce = {"esito": "PERDE DATI" if nuova else "DIFETTO VECCHIO",
                "chiave": ", ".join(v["percorsi"]),
                "titolo": (f"il salvataggio di {sigla} riaperto con il codice di adesso perde "
                           f"{', '.join(v['percorsi'])} - {', '.join(v['momenti'])}"),
                "righe": v["esempi"][:4] + consiglio_chiave(patt, g["esempio"], v["al_posto"][:3])}
        (problemi if nuova else vecchi).append(voce)
    if senza_rif:
        note.append(f"Chiavi dei salvataggi di {sigla} che il codice di adesso non rilegge, "
                    f"senza il paragone con HEAD (non ha aperto gli stessi file): "
                    + ", ".join(sorted(senza_rif)[:8]))

    # (b) la carriera di adesso, prima e dopo il salvataggio
    if not ora.get("ok") and not ora.get("sonda"):
        fase = str(ora.get("fase"))
        cosa = {"nuova carriera": "non riesce a cominciare una carriera",
                "gioco": "si rompe giocando, prima ancora di salvare",
                "fine stagione": "si rompe chiudendo la stagione"}.get(fase, f"si ferma ({fase})")
        if "salvataggio" in fase:
            cosa = f"non riesce a salvare ({fase})"
        elif "riapertura" in fase:
            cosa = f"non riapre il salvataggio che ha appena fatto ({fase})"
        problemi.append({"esito": "ROTTO", "titolo": f"il codice di adesso {cosa}",
                         "righe": _righe_errore(ora.get("errore") or {})})
    if testa is not base and not testa.get("ok"):
        note.append(f"HEAD ({sigla_testa}) non ha finito la sua carriera ({testa.get('fase')}): "
                    f"quello che si perdeva gia' li' qui conta come nuovo.")
    gia = {p["chiave"] for c in testa.get("controlli", []) for p in c.get("perdite", [])}
    nomi = {"Team": ("squadra", "squadre"), "Driver": ("pilota", "piloti"),
            "Staff": ("tecnico", "tecnici"), "Deal": ("contratto", "contratti")}
    visti = {}
    for c in ora.get("controlli", []):
        for p in c.get("perdite", []):
            if p["chiave"] in visti:
                visti[p["chiave"]]["momenti"].append(c["momento"])
                continue
            uno, tanti = nomi.get(p["classe"], (p["classe"], p["classe"]))
            chi = (f"{p['quanti']} {uno if p['quanti'] == 1 else tanti} su {p['su']}"
                   f" ({', '.join(str(x) for x in p['chi'][:4])})"
                   if p["classe"] != "GameState" else "la partita")
            voce = {"esito": "PERDE DATI" if p["chiave"] not in gia else "DIFETTO VECCHIO",
                    "chiave": p["chiave"], "momenti": [c["momento"]], "chi": chi,
                    "righe": [f"{x['dove']}: {x['prima']} -> {x['dopo']}" for x in p["esempi"]]
                             + p.get("consiglio", [])}
            visti[p["chiave"]] = voce
            (problemi if voce["esito"] == "PERDE DATI" else vecchi).append(voce)
    for v in visti.values():
        v["titolo"] = f"{v['chiave']}: {v.pop('chi')} - {', '.join(v['momenti'])}"

    # I tollerati non cambiano l'esito: un arrotondamento o un taglio voluto
    # in to_dict e' una scelta, non un guasto. Ma uno che con HEAD non c'era
    # e' una scelta nuova, o un dato perso che si traveste da arrotondamento:
    # lo si nomina, e decide chi legge
    def _tollerati(e):
        return {(tipo, k) for c in e.get("controlli", [])
                for tipo, voci in (c.get("tollerati") or {}).items() for k in voci}
    if testa.get("ok"):
        nuovi = sorted(_tollerati(ora) - _tollerati(testa))
        if nuovi:
            note.append("Tollerati che con HEAD non c'erano: "
                        + "; ".join(f"{k} ({tipo})" for tipo, k in nuovi)
                        + ". Se e' un arrotondamento o un taglio voluto va bene; se no e' un "
                          "dato perso.")

    # la versione web salva nel localStorage del browser, che ha pochi MB per
    # tutti i salvataggi insieme: un file che cresce molto si fa notare
    kb_testa = {c["momento"]: c.get("kb") for c in testa.get("controlli", [])}
    for c in ora.get("controlli", []):
        kb0 = kb_testa.get(c["momento"])
        if kb0 and c.get("kb") and c["kb"] > kb0 * 1.25 and c["kb"] - kb0 > 50:
            note.append(f"Il salvataggio {c['momento']} pesa {c['kb']:.0f} KB contro i "
                        f"{kb0:.0f} di HEAD: nel browser sta nel localStorage, che ha "
                        f"pochi MB per tutti i salvataggi.")

    if any(p["esito"] == "ROTTO" for p in problemi):
        verdetto, codice = "ROTTO", 1
    elif problemi:
        verdetto, codice = "PERDE DATI", 1
    elif impossibile:
        verdetto, codice = "IMPOSSIBILE", 2
    else:
        verdetto, codice = "OK", 0
    return {"esito": verdetto, "codice": codice, "problemi": problemi,
            "difetti_vecchi": vecchi, "note": note, "impossibile": impossibile}


# ---------------------------------------------------------------- la stampa
def _eventi(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in (d or {}).items()) or "nessun evento"


def stampa(r: dict, g: dict) -> None:
    sigla = r.get("commit", r.get("base"))
    diversi = r.get("diversi", [])
    if r.get("commit"):
        print(f"Base {sigla} \"{r.get('titolo', '')}\"; il codice di adesso ha "
              f"{len(diversi)} file {'diverso' if len(diversi) == 1 else 'diversi'} "
              f"da HEAD in game/ e data/")
    base, ora = r.get("e_base") or {}, r.get("e_ora") or {}
    if ora.get("programmi") is not None:
        prog = ora.get("programmi") or {}
        aperti = [n for n, k in (("Formula E", "fe"), ("endurance", "wec")) if prog.get(k)]
        print(f"Carriera di prova: {ora.get('squadra', SQUADRA)}, seme {SEME}"
              + (f", con {' ed '.join(aperti)}" if aperti else ", sola Formula 1"))
    if base and not (base.get("programmi") or {}).get("fe"):
        print(f"  ({sigla} non ha la Formula E: i suoi salvataggi sono di sola Formula 1)")
    print()
    if r.get("e_carica") is not None:
        print(f"(a) Salvataggi di {sigla} aperti con il codice di adesso")
        for e in r["e_carica"]:
            stato = ("aperto, giocato (" + _eventi(e.get("eventi")) + "), risalvato e riaperto"
                     if e.get("ok") else f"non provato, manca {e['mancante']}"
                     if e.get("mancante") else f"ROTTO in {e.get('fase')}")
            if e.get("chiavi_nuove"):
                n = e["chiavi_nuove"]
                stato += f"; {n} {'chiave non riletta' if n == 1 else 'chiavi non rilette'}"
            print(f"    {e.get('momento', '?')} ({e.get('kb_base', '?')} KB): {stato} "
                  f"[{e.get('secondi', '?')} s]")
        if not r["e_carica"]:
            print("    nessun salvataggio da aprire")
        print("(b) Salva e ricarica, attributo per attributo, con il codice di adesso")
        if not ora.get("controlli"):
            print(f"    non fatto: la carriera si e' fermata prima ({ora.get('fase')})")
        for c in ora.get("controlli", []):
            if "perdite" not in c:
                print(f"    {c['momento']}: salvato ({c.get('kb', '?')} KB) ma non riaperto, "
                      f"vedi sotto")
                continue
            o = c.get("oggetti", {})
            chiavi = {x.get("chiave") for x in g["problemi"]}
            nuove = [p for p in c.get("perdite", []) if p["chiave"] in chiavi]
            vecchie = len(c.get("perdite", [])) - len(nuove)
            esito = ", ".join(x for x in (
                f"{len(nuove)} {'attributo perso' if len(nuove) == 1 else 'attributi persi'}"
                if nuove else "",
                f"{vecchie} {'perso' if vecchie == 1 else 'persi'} anche da HEAD"
                if vecchie else "") if x) or "niente di perso"
            print(f"    {c['momento']} (stagione {c['stagione']}, gara {c['gara']}): "
                  f"{o.get('Team', 0)} squadre, {o.get('Driver', 0)} piloti, "
                  f"{o.get('Staff', 0)} tecnici, {o.get('Deal', 0)} contratti; "
                  f"{c.get('kb', '?')} KB; {esito}")
        toll = {}
        for c in ora.get("controlli", []):
            for tipo, voci in (c.get("tollerati") or {}).items():
                for k, n in voci.items():
                    toll.setdefault(tipo, {})[k] = toll.get(tipo, {}).get(k, 0) + n
        for tipo, voci in toll.items():
            print(f"    tollerati, {tipo}: " + ", ".join(f"{k} ({n})" for k, n in voci.items()))
        print()
    for p in g["problemi"] + g["difetti_vecchi"]:
        print(f"{p['esito']}  {p['titolo']}")
        if p["esito"] == "DIFETTO VECCHIO":
            print(f"    si perde anche con HEAD ({r.get('head')}): non e' colpa di questa "
                  f"modifica e non cambia l'esito, ma va sistemato")
        for riga in p["righe"]:
            print(f"    {riga}")
        print()
    for n in g["note"]:
        print(f"Nota: {n}")
    for n in g["impossibile"]:
        print(f"IMPOSSIBILE: {n}")
    print(f"Esito: {g['esito']} ({r.get('secondi', 0)} s)")


def prepara_console() -> None:
    # la console di Windows non sa scrivere tutto: meglio un punto di domanda
    # al posto di una lettera che un errore a fine prova
    for flusso in (sys.stdout, sys.stderr):
        if hasattr(flusso, "reconfigure"):
            try:
                flusso.reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def leggi_argomenti(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Le partite salvate prima si aprono ancora, e il salvataggio non "
                    "perde niente. Esce con 0 se va tutto bene, 1 se qualcosa e' ROTTO "
                    "o PERDE DATI, 2 se la prova non si e' potuta fare.")
    p.add_argument("--base", default="HEAD",
                   help="il commit con cui si fanno i salvataggi da aprire (HEAD)")
    p.add_argument("--json", action="store_true", help="il rapporto in JSON, e basta")
    # quelli che usa la sonda per lanciare se stessa
    p.add_argument("--figlio", choices=("carriera", "carica"), help=argparse.SUPPRESS)
    p.add_argument("--radice", help=argparse.SUPPRESS)
    p.add_argument("--esito", help=argparse.SUPPRESS)
    p.add_argument("--file", help=argparse.SUPPRESS)
    p.add_argument("--salva-in", dest="salva_in", help=argparse.SUPPRESS)
    p.add_argument("--senza-confronto", dest="senza_confronto", action="store_true",
                   help=argparse.SUPPRESS)
    p.add_argument("--solo-apri", dest="solo_apri", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = leggi_argomenti(argv)
    if args.figlio:
        return figlio(args)
    prepara_console()
    t0 = time.perf_counter()
    if not args.json:
        print(f"Sonda dei salvataggi: base {args.base}, una mezza stagione con Formula E "
              f"ed endurance, poi l'inverno (circa mezzo minuto)...", flush=True)
    r = {"base": args.base}
    try:
        r = prova(args.base)
        g = giudica(r)
    except Impossibile as exc:
        g = {"esito": "IMPOSSIBILE", "codice": 2, "problemi": [], "difetti_vecchi": [],
             "note": [], "impossibile": [str(exc)]}
    r["secondi"] = round(time.perf_counter() - t0, 1)
    if args.json:
        uscita = {k: v for k, v in r.items()}
        uscita.update(g)
        print(json.dumps(uscita, ensure_ascii=True, indent=1))
    else:
        stampa(r, g)
    return g["codice"]


if __name__ == "__main__":
    sys.exit(main())
