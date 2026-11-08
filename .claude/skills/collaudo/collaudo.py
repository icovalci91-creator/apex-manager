"""Collaudo senza interfaccia: una carriera intera, stagione dopo stagione.

Il gioco si prova giocandolo, ma una stagione all'interfaccia sono ore, e i
guai di bilanciamento si vedono solo dopo tre o quattro: una griglia che
invecchia di un anno a stagione, un ritiro in piu' a gara, un salvataggio che
perde un pezzo e lo si scopre l'inverno dopo. Qui si fa la stessa strada
dell'interfaccia - il prossimo evento del calendario intrecciato, il weekend
di Formula 1 con gomme, libere, sprint e qualifica, gli E-Prix, le tappe
endurance, la Commissione, la fine stagione con l'inverno - senza disegnare
niente, e si misura quello che una stagione vera deve avere.

I numeri si confrontano con soglie.json, accanto a questo file: sono i limiti
dentro cui stanno le stagioni pulite, con un po' di margine. Uno fuori, un
errore o un salvataggio che ricaricato non torna uguale, e il collaudo esce
con 1. Stesso seme, stesso codice e stesso Python, stessi numeri: l'impronta
stampata alla fine lo dice in una riga. (Fra macchine diverse possono
scostarsi di poco: game/core/development.py ricorda dei calcoli con chiave
id(gs) e id(track), e Python riusa gli indirizzi degli oggetti liberati, come
la partita ricaricata dopo ogni salvataggio.)

    python .claude/skills/collaudo/collaudo.py [squadra] [--seme N] [--stagioni N]
        [--fe] [--wec] [--gare N] [--rif COMMIT] [--salva-in FILE]
        [--parti-da FILE] [--json FILE]

Funziona da qualunque cartella: la radice del gioco e' tre livelli sopra a
questo file (.claude/skills/collaudo/).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import signal
import stat
import statistics
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
from pathlib import Path

QUI = Path(__file__).resolve().parent
REPO = QUI.parents[2]
SOGLIE = QUI / "soglie.json"

# i tempi dipendono dalla macchina e da cosa ci gira accanto: stanno nel
# rapporto e hanno le loro soglie, ma non entrano nell'impronta, che deve
# essere la stessa su ogni computer a parita' di seme
TEMPI = ("tempo_gare_s", "tempo_fine_stagione_s", "tempo_salvataggio_s",
         "tempo_caricamento_s")

# le misure che si confrontano prima e dopo, nell'ordine in cui si stampano
MISURE = [
    ("dnf_per_gara", "ritiri per gara", 2),
    ("sc_per_gara", "safety car per gara", 2),
    ("giro_su_rif", "giro / riferimento (asciutto)", 4),
    ("eta_titolari", "eta' media titolari", 2),
    ("deriva_eta_titolari", "deriva eta' titolari", 2),
    ("esordienti", "esordienti l'anno dopo", 2),
    ("dominio", "dominio (vittorie della prima)", 3),
    ("tempo_gare_s", "tempo delle gare (s)", 1),
    ("tempo_fine_stagione_s", "tempo fine stagione (s)", 2),
    ("tempo_salvataggio_s", "tempo salvataggio (s)", 3),
    ("tempo_caricamento_s", "tempo caricamento (s)", 2),
    ("dimensione_salvataggio_kb", "salvataggio (kB)", 0),
]


# ------------------------------------------------------------------ argomenti
def leggi_argomenti(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="collaudo",
        description="Collaudo senza interfaccia di Apex Manager: stagioni intere, "
                    "salva e ricarica, numeri confrontati con soglie note.")
    p.add_argument("squadra", nargs="?", default="ferrari",
                   help="la squadra del giocatore (id di data/teams.json), "
                        "predefinita ferrari")
    p.add_argument("--seme", type=int, default=1,
                   help="seme della carriera: stesso seme, stessi numeri (predefinito 1)")
    p.add_argument("--stagioni", type=int, default=1,
                   help="quante stagioni intere far girare (predefinito 1)")
    p.add_argument("--fe", action="store_true",
                   help="apre un programma di Formula E: gli E-Prix entrano nel calendario")
    p.add_argument("--wec", action="store_true",
                   help="apre un programma endurance (Hypercar): le tappe entrano nel calendario")
    p.add_argument("--gare", type=int, default=0,
                   help="prova lampo: si ferma dopo N weekend di Formula 1 della prima "
                        "stagione, senza fine stagione")
    p.add_argument("--rif", metavar="COMMIT",
                   help="rifa' lo stesso scenario sul codice di COMMIT (estratto con "
                        "git archive) e mette prima e dopo uno accanto all'altro")
    p.add_argument("--salva-in", metavar="FILE",
                   help="alla fine scrive la carriera in FILE (formato dei salvataggi); "
                        "con --rif la scrive il codice di riferimento")
    p.add_argument("--parti-da", metavar="FILE",
                   help="riparte da una carriera salvata invece che da una nuova")
    p.add_argument("--json", metavar="FILE", help="scrive il rapporto completo in FILE")
    p.add_argument("--soglie", metavar="FILE",
                   help="soglie da usare al posto di soglie.json accanto a questo file")
    p.add_argument("--dettaglio", action="store_true",
                   help="stampa una riga per ogni gran premio")
    # uso interno di --rif: la cartella del gioco da collaudare, se non e'
    # quella in cui sta questo file
    p.add_argument("--radice", help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.stagioni < 1:
        p.error("--stagioni vuole almeno 1")
    if a.gare < 0:
        p.error("--gare vuole un numero positivo")
    return a


def prepara_console() -> None:
    """Accenti e simboli dei nomi stranieri senza far cadere la console di Windows."""
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def dici(testo: str = "") -> None:
    print(testo, flush=True)


# ------------------------------------------------------------------ le soglie
def carica_soglie(percorso) -> dict:
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _fuori(valore, limite: dict) -> bool:
    if valore is None:
        return False
    if "min" in limite and valore < limite["min"]:
        return True
    return "max" in limite and valore > limite["max"]


def _intervallo(limite: dict) -> str:
    if "min" in limite and "max" in limite:
        return f"{limite['min']} - {limite['max']}"
    if "min" in limite:
        return f">= {limite['min']}"
    return f"<= {limite['max']}"


def controlla(rapporto: dict, soglie: dict) -> list:
    """Le misure fuori soglia, stagione per stagione e sulla carriera intera.

    Una stagione con poche gare (la prova lampo, o una carriera ripresa a
    campionato quasi finito) ha medie che ballano: la si giudica con le soglie
    larghe della sezione "lampo", non con quelle di una stagione intera.
    """
    fuori = []
    minime = int(soglie.get("gare_minime", 10))
    for s in rapporto["stagioni"]:
        sezione = "stagione" if s["gp"] >= minime else "lampo"
        for chiave, limite in soglie.get(sezione, {}).items():
            if chiave.startswith("_") or not isinstance(limite, dict):
                continue
            v = s.get(chiave)
            if _fuori(v, limite):
                fuori.append({"stagione": s["anno"], "misura": chiave, "valore": v,
                              "soglia": _intervallo(limite),
                              "perche": limite.get("perche", "")})
    finite = rapporto["carriera"].get("stagioni_finite", 0)
    for chiave, limite in soglie.get("carriera", {}).items():
        if chiave.startswith("_") or not isinstance(limite, dict):
            continue
        # una media su una stagione sola e' un numero solo: certe misure della
        # carriera si giudicano soltanto quando ci sono abbastanza anni dietro
        if finite < int(limite.get("stagioni_minime", 1)):
            continue
        v = rapporto["carriera"].get(chiave)
        if _fuori(v, limite):
            fuori.append({"stagione": "carriera", "misura": chiave, "valore": v,
                          "soglia": _intervallo(limite), "perche": limite.get("perche", "")})
    return fuori


# --------------------------------------------------------------- salvataggio
def _canonico(dati) -> str:
    """Il salvataggio scritto sempre allo stesso modo: chiavi in ordine.

    Si passa prima da un giro di json per avere le chiavi tutte stringhe, come
    le ritrova chi ricarica il file: un dizionario con chiavi numeriche e di
    testo insieme non si saprebbe nemmeno ordinare.
    """
    return json.dumps(json.loads(json.dumps(dati, ensure_ascii=False)),
                      sort_keys=True, ensure_ascii=False)


def _candidati_in_ordine(testo: str) -> str:
    """Lo stesso salvataggio, con i circuiti candidati messi in fila per nome.

    GameState._restore_calendar (game/core/state.py) ricostruisce i candidati
    nell'ordine in cui stanno nei dati del gioco, non in quello del
    salvataggio: dopo il primo rinnovo dei contratti di calendario, salvare e
    ricaricare li rimescola. Sono gli stessi circuiti con gli stessi contratti,
    e il gioco non da' peso all'ordine in cui li tiene: e' un difetto noto, che
    qui non si corregge (il codice del gioco non e' affare del collaudo) e
    quindi si confronta senza badare all'ordine. Tutto il resto deve tornare
    identico.
    """
    d = json.loads(testo)
    d["candidates"] = sorted(d.get("candidates") or [],
                             key=lambda c: json.dumps(c, sort_keys=True))
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def _breve(x) -> str:
    t = json.dumps(x, ensure_ascii=False, default=str)
    return t if len(t) <= 70 else t[:67] + "..."


def _uguali(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def differenze(a, b, percorso: str = "", out=None, limite: int = 8) -> list:
    """Dove due salvataggi non tornano: i primi punti, per sapere dove guardare."""
    out = [] if out is None else out
    if len(out) >= limite:
        return out
    if type(a) is not type(b):
        out.append(f"{percorso or '/'}: {_breve(a)} -> {_breve(b)}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if len(out) >= limite:
                break
            if k not in b:
                out.append(f"{percorso}/{k}: sparito dopo la ricarica")
            elif k not in a:
                out.append(f"{percorso}/{k}: comparso dopo la ricarica")
            else:
                differenze(a[k], b[k], f"{percorso}/{k}", out, limite)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{percorso}: {len(a)} elementi -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            if len(out) >= limite:
                break
            differenze(x, y, f"{percorso}[{i}]", out, limite)
    elif not _uguali(a, b):
        out.append(f"{percorso or '/'}: {_breve(a)} -> {_breve(b)}")
    return out


# ------------------------------------------------------------- la carriera
class Collaudo:
    """Una carriera fatta girare dall'inizio alla fine, senza schermo."""

    def __init__(self, args, radice: Path):
        self.args = args
        self.radice = radice
        self.gs = None
        self.rapporto = {
            "squadra": args.squadra, "seme": args.seme, "radice": str(radice),
            "parti_da": args.parti_da or "", "fe": args.fe, "wec": args.wec,
            "gare_lampo": args.gare, "stagioni": [], "salvataggi": [], "errori": [],
            "note": [],
        }

    def importa(self) -> None:
        """I moduli del gioco, presi da `radice`.

        Si importano qui e non in cima al file perche' un gioco che non si
        importa nemmeno (un errore di sintassi lasciato in un modulo, un nome
        cambiato da una parte sola) e' un collaudo non superato come un altro:
        deve finire nel rapporto con la sua traccia, non far cadere lo script
        prima ancora di cominciare.
        """
        # il gioco si importa da `radice`: con --rif e' una copia estratta da
        # un commit vecchio, e non deve vedere i moduli di quello attuale
        sys.path.insert(0, str(self.radice))
        # i moduli del gioco non aprono finestre, ma se qualcuno importa pygame
        # non deve cercare uno schermo che in un contenitore non c'e'
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from game.core import formulae, inverno, rules, season, tyres, wec
        from game.core.state import GameState
        from game.sim import session
        from game.sim.weekend import Weather
        self.GameState, self.Weather = GameState, Weather
        self.FE, self.INV, self.RULES = formulae, inverno, rules
        self.SEASON, self.TY, self.WEC, self.S = season, tyres, wec, session

    # ----------------------------------------------------------- partenza
    def apri_carriera(self) -> None:
        a = self.args
        if a.parti_da:
            testo = Path(a.parti_da).read_text(encoding="utf-8")
            self.gs = self.GameState.from_dict(json.loads(testo))
            # squadra e seme sono quelli della carriera salvata, non quelli
            # predefiniti della riga di comando
            self.rapporto["squadra"] = self.gs.player_team
            self.rapporto["seme"] = self.gs.seed
            dici(f"Carriera ripresa da {a.parti_da}: {self.gs.player.name}, "
                 f"stagione {self.gs.season}, gara {self.gs.round + 1}, fase {self.gs.phase}.")
        else:
            self.gs = self.GameState.new_game(a.squadra, True, seed=a.seme)
        gs = self.gs
        # senza nessuno davanti allo schermo lo sviluppo lo decide il reparto:
        # e' la delega che il giocatore puo' dare, e tiene il collaudo uguale
        # per tutte le squadre
        gs.player.auto_dev = True
        if a.fe and not self.FE.ha(gs.player):
            gs.player.cash += 300
            dici(self.FE.apri(gs, gs.player, f"{gs.player.short} FE"))
        if a.wec and not self.WEC.ha(gs.player):
            gs.player.cash += 300
            dici(self.WEC.apri(gs, gs.player, f"{gs.player.short} Endurance", "hypercar"))

    def prossimo_evento(self):
        """Il prossimo evento del calendario, anche su codice di prima del calendario unico.

        Con --rif si puo' collaudare un commit vecchio, di quando la Formula E
        e l'endurance si chiudevano tutte a fine stagione e il calendario era
        solo quello della Formula 1 (prima di dd05dcc): li' si corrono i gran
        premi uno dopo l'altro, e il resto lo fa la fine stagione come allora.
        """
        if hasattr(self.SEASON, "prossimo_evento"):
            return self.SEASON.prossimo_evento(self.gs)
        nota = "il codice collaudato non ha il calendario unico: in calendario solo la Formula 1"
        if nota not in self.rapporto["note"]:
            self.rapporto["note"].append(nota)
        gs = self.gs
        if gs.phase != "offseason" and gs.round < len(gs.tracks):
            return {"serie": "f1", "pista": gs.tracks[gs.round]}
        return None

    # ----------------------------------------------------------- un weekend
    def _corri(self, ws, kind: str):
        sim = self.S.make_race(self.gs, ws, kind=kind)
        # com'e' il tempo al semaforo e cosa promette: una gara bagnata o con la
        # pioggia in arrivo non dice niente sul passo, e resta fuori dal conto
        # del giro sul riferimento
        bagnata = sim.weather.wet > 0.05 or bool(getattr(sim, "meteo_prog", None))
        sim.fast_forward()
        self.SEASON.apply_result(self.gs, ws, sim, kind=kind)
        mescole = {c for e in sim.entrants for c in (getattr(e, "used_compounds", None) or ())}
        bagnata = bagnata or sim.weather.wet > 0.05 or bool(mescole & {"inter", "wet"})
        return sim, bagnata

    def weekend_f1(self, tr) -> dict:
        """Lo stesso ordine della scena del weekend, un passo dopo l'altro."""
        gs, S = self.gs, self.S
        ws = S.WeekendState(track=tr, weather=self.Weather.generate(tr, gs.rng))
        # le gomme si consegnano prima di scendere in pista: il giocatore prende
        # il consiglio degli ingegneri, le altre scelgono da se'
        self.TY.allocate(gs, ws, self.TY.suggested(tr))
        for _ in range(S.practice_sessions(tr)):
            S.run_practice(gs, ws)
        if tr.sprint:
            S.run_qualifying(gs, ws, "sprint")
            self._corri(ws, "sprint")
            ws.sprint_done = True
            S.learn_from_sprint(gs, ws)
        S.run_qualifying(gs, ws, "gp")
        sim, bagnata = self._corri(ws, "gp")
        ordine = sim.result_order()
        finiti = sum(1 for e in ordine if e.status == "finished")
        gara = {"round": gs.round + 1, "pista": tr.id, "vince": ordine[0].team_id,
                "pilota": ordine[0].driver_id, "partenti": len(ordine),
                "dnf": len(ordine) - finiti, "sc": int(getattr(sim, "sc_conta", 0)),
                "giro": round(sim.best_lap, 3), "rif": float(getattr(tr, "ref_lap", 0.0)),
                "asciutta": not bagnata, "sprint": bool(tr.sprint)}
        self.SEASON.after_race(gs)
        # la Commissione di meta' stagione: chi gioca la trova uscendo dal
        # weekend, e qui non vota (si astiene) come chi chiude senza scegliere
        if gs.pending_votes and gs.phase != "offseason":
            self.RULES.close_meeting(gs, {})
        return gara

    # ----------------------------------------------------------- le misure
    def titolari(self) -> list:
        return [d for d in self.gs.drivers.values()
                if d.seat == "titolare" and d.team and not getattr(d, "ritirato", False)]

    def prova_salvataggio(self, anno, momento: str) -> dict:
        """Salva, ricarica e salva di nuovo: i due file devono essere uguali.

        E' la prova che un giocatore fa senza saperlo ogni volta che chiude il
        gioco: se qualcosa non torna si vede qui, e non a meta' della stagione
        dopo con una squadra che ha cambiato pilota da sola.
        """
        gs = self.gs
        t0 = time.perf_counter()
        testo = json.dumps(gs.to_dict(), ensure_ascii=False)
        t_salva = time.perf_counter() - t0
        t0 = time.perf_counter()
        gs2 = self.GameState.from_dict(json.loads(testo))
        t_carica = time.perf_counter() - t0
        testo2 = json.dumps(gs2.to_dict(), ensure_ascii=False)
        prima, dopo = _canonico(json.loads(testo)), _canonico(json.loads(testo2))
        esito = {"anno": anno, "momento": momento, "uguale": prima == dopo,
                 "solo_ordine_candidati": False, "differenze": [],
                 "kb": round(len(testo.encode("utf-8")) / 1024.0, 1),
                 "tempo_salvataggio_s": round(t_salva, 3),
                 "tempo_caricamento_s": round(t_carica, 3),
                 "impronta": hashlib.sha1(prima.encode("utf-8")).hexdigest()[:12]}
        if not esito["uguale"]:
            prima_n, dopo_n = _candidati_in_ordine(prima), _candidati_in_ordine(dopo)
            if prima_n == dopo_n:
                esito["uguale"] = True
                esito["solo_ordine_candidati"] = True
            else:
                # le differenze si cercano con i candidati gia' in fila: se no
                # le prime righe sarebbero sempre il difetto noto, e il campo
                # rotto davvero finirebbe oltre il limite
                esito["differenze"] = differenze(json.loads(prima_n), json.loads(dopo_n))
        self.rapporto["salvataggi"].append(esito)
        return esito

    # ----------------------------------------------------------- una stagione
    def stagione(self, indice: int, lampo: int) -> bool:
        """Una stagione intera (o le prime `lampo` gare). False se si e' rotto qualcosa."""
        gs = self.gs
        anno = gs.season
        gare, eventi = [], {"f1": 0, "fe": 0, "wec": 0}
        t0 = time.perf_counter()
        try:
            # un calendario che non avanza piu' girerebbe per sempre: ottanta
            # eventi sono il triplo di una stagione con tutti e tre i campionati
            for _ in range(80):
                if lampo and eventi["f1"] >= lampo:
                    break
                ev = self.prossimo_evento()
                if ev is None:
                    break
                eventi[ev["serie"]] += 1
                if ev["serie"] == "f1":
                    g = self.weekend_f1(ev["pista"])
                    gare.append(g)
                    if self.args.dettaglio or lampo:
                        dici(f"  {anno} gara {g['round']:2d} {g['pista']:<12} vince "
                             f"{g['pilota']} ({g['vince']}); ritiri {g['dnf']}, SC {g['sc']}, "
                             f"giro/rif {g['giro'] / g['rif'] if g['rif'] else 0.0:.3f}"
                             f"{'' if g['asciutta'] else ' (bagnata)'}")
                elif ev["serie"] == "fe":
                    self.FE.simula_gara(gs, gs.player)
                else:
                    self.WEC.avanza(gs)
            else:
                raise RuntimeError("il calendario non avanza: ottanta eventi e la "
                                   "stagione non e' ancora finita")
            t_gare = time.perf_counter() - t0
            tit = self.titolari()
            eta = round(statistics.mean(d.age for d in tit), 2) if tit else None
            vittorie = {}
            for g in gare:
                vittorie[g["vince"]] = vittorie.get(g["vince"], 0) + 1
            classifica = sorted(gs.teams.values(), key=lambda t: -t.points)
            campione_costr = classifica[0].id if classifica else ""
            report, t_fine, esordienti = None, None, None
            if not lampo:
                t1 = time.perf_counter()
                report = self.SEASON.end_season(gs)
                # la riunione di fine anno e la Commissione, come le chiude la
                # scena di fine stagione: nessun cantiere scelto, nessun voto
                if getattr(gs.player, "inverno_aperto", False):
                    self.INV.chiudi_giocatore(gs, [])
                self.RULES.close_meeting(gs, {})
                t_fine = time.perf_counter() - t1
                # chi sale in macchina l'anno prossimo senza un gran premio alle
                # spalle: i giovani che il mercato fa entrare davvero
                esordienti = sum(1 for d in self.titolari() if d.races == 0)
            salva = self.prova_salvataggio(anno, "fine stagione" if not lampo
                                           else f"dopo {len(gare)} gare")
        except Exception:
            self.rapporto["errori"].append({"stagione": anno, "eventi": eventi,
                                            "traccia": traceback.format_exc()})
            dici(f"{anno}: ERRORE dopo {eventi}")
            dici(traceback.format_exc())
            return False

        asciutte = [g["giro"] / g["rif"] for g in gare
                    if g["asciutta"] and g["rif"] > 0 and g["giro"] > 0]
        primo = self.rapporto["stagioni"][0]["eta_titolari"] if self.rapporto["stagioni"] else eta
        dati = {
            "anno": anno, "eventi": eventi, "gp": len(gare), "lampo": bool(lampo),
            "dnf_per_gara": round(statistics.mean(g["dnf"] for g in gare), 3) if gare else None,
            "sc_per_gara": round(statistics.mean(g["sc"] for g in gare), 3) if gare else None,
            "giro_su_rif": round(statistics.mean(asciutte), 4) if asciutte else None,
            "gare_asciutte": len(asciutte),
            "eta_titolari": eta,
            # quanto e' invecchiata (o ringiovanita) la griglia dalla prima
            # stagione del collaudo: e' il numero che si muove per primo quando
            # i giovani smettono di entrare
            "deriva_eta_titolari": (round(eta - primo, 2)
                                    if eta is not None and primo is not None else None),
            "esordienti": esordienti,
            "dominio": (round(max(vittorie.values()) / len(gare), 3) if gare else None),
            "vittorie": vittorie,
            "campione_costruttori": campione_costr,
            "campione_piloti": (report["champions"]["driver"].name
                                if report and report["champions"].get("driver") else ""),
            "titolari": len(tit), "liberi": len(gs.free_agents),
            "tempo_gare_s": round(t_gare, 1),
            "tempo_fine_stagione_s": round(t_fine, 2) if t_fine is not None else None,
            "tempo_salvataggio_s": salva["tempo_salvataggio_s"],
            "tempo_caricamento_s": salva["tempo_caricamento_s"],
            "dimensione_salvataggio_kb": salva["kb"],
            "salvataggio_uguale": salva["uguale"],
            "gare": gare,
        }
        self.rapporto["stagioni"].append(dati)
        self.stampa_stagione(dati, salva)
        return salva["uguale"]

    def stampa_stagione(self, s: dict, salva: dict) -> None:
        def f(v, cifre=2):
            return "-" if v is None else f"{v:.{cifre}f}"
        vinte = ", ".join(f"{k} {v}" for k, v in
                          sorted(s["vittorie"].items(), key=lambda kv: -kv[1]))
        testa = f"{s['anno']}" + (" (prova lampo)" if s["lampo"] else "")
        chi = "In testa ai costruttori" if s["lampo"] else "Costruttori"
        tappe = s["eventi"]["wec"]
        dici(f"{testa}: {s['gp']} GP, {s['eventi']['fe']} E-Prix, "
             f"{tappe} tapp{'a' if tappe == 1 else 'e'} "
             f"endurance. {chi}: {s['campione_costruttori'] or '-'}"
             + (f", piloti: {s['campione_piloti']}" if s["campione_piloti"] else "")
             + f". Vittorie: {vinte}")
        dici(f"   ritiri/gara {f(s['dnf_per_gara'])}  SC/gara {f(s['sc_per_gara'])}  "
             f"giro/rif {f(s['giro_su_rif'], 4)} ({s['gare_asciutte']} asciutte)  "
             f"eta' titolari {f(s['eta_titolari'])} (deriva {f(s['deriva_eta_titolari'])})  "
             f"esordienti {'-' if s['esordienti'] is None else s['esordienti']}  "
             f"dominio {f(s['dominio'], 3)}")
        if salva["uguale"]:
            nota = (" (candidati in altro ordine, difetto noto)"
                    if salva["solo_ordine_candidati"] else "")
            esito = f"salva e ricarica identico{nota}"
        else:
            esito = "SALVA E RICARICA DIVERSO: " + "; ".join(salva["differenze"][:4])
        dici(f"   tempi: gare {f(s['tempo_gare_s'], 1)} s, fine stagione "
             f"{f(s['tempo_fine_stagione_s'])} s, salva {f(s['tempo_salvataggio_s'], 3)} s, "
             f"ricarica {f(s['tempo_caricamento_s'])} s, {s['dimensione_salvataggio_kb']:.0f} kB; "
             f"{esito}")

    # ----------------------------------------------------------- tutto
    def corri(self) -> dict:
        a = self.args
        t0 = time.perf_counter()
        try:
            self.importa()
            self.apri_carriera()
        except Exception:
            self.rapporto["errori"].append({"stagione": None, "eventi": {},
                                            "traccia": traceback.format_exc()})
            dici("ERRORE all'apertura della carriera")
            dici(traceback.format_exc())
            return self.chiudi(t0)
        quante = 1 if a.gare else a.stagioni
        if a.gare and a.stagioni > 1:
            self.rapporto["note"].append("con --gare si fa solo l'inizio della prima "
                                         "stagione: --stagioni non conta")
        for k in range(quante):
            if not self.stagione(k, a.gare):
                break
        if a.salva_in and self.gs is not None and not self.rapporto["errori"]:
            p = Path(a.salva_in)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.gs.to_dict(), ensure_ascii=False), encoding="utf-8")
            dici(f"Carriera salvata in {p} (stagione {self.gs.season}, fase {self.gs.phase}).")
        return self.chiudi(t0)

    def chiudi(self, t0: float) -> dict:
        r = self.rapporto
        stag = r["stagioni"]
        derive = [s["deriva_eta_titolari"] for s in stag if s["deriva_eta_titolari"] is not None]
        esord = [s["esordienti"] for s in stag if s["esordienti"] is not None]
        domini = [s["dominio"] for s in stag if s["dominio"] is not None]
        r["carriera"] = {
            "stagioni_finite": sum(1 for s in stag if not s["lampo"]),
            "deriva_eta_titolari": derive[-1] if derive else None,
            "esordienti_per_anno": round(statistics.mean(esord), 2) if esord else None,
            "dominio_medio": round(statistics.mean(domini), 3) if domini else None,
        }
        r["tempo_totale_s"] = round(time.perf_counter() - t0, 1)
        # l'impronta: tutto quello che il seme decide, tempi esclusi
        fisso = {"stagioni": [{k: v for k, v in s.items() if k not in TEMPI} for s in stag],
                 "salvataggi": [{k: v for k, v in x.items() if k not in TEMPI}
                                for x in r["salvataggi"]],
                 "errori": len(r["errori"])}
        r["impronta"] = hashlib.sha1(json.dumps(fisso, sort_keys=True, default=str)
                                     .encode("utf-8")).hexdigest()[:16]
        return r


# ------------------------------------------------------------- il giudizio
def giudica(rapporto: dict, soglie: dict) -> int:
    """Stampa il verdetto e torna il codice d'uscita: 0 tutto in regola, 1 no."""
    fuori = controlla(rapporto, soglie)
    rapporto["fuori_soglia"] = fuori
    rotti = [x for x in rapporto["salvataggi"] if not x["uguale"]]
    errori = rapporto["errori"]
    stag = rapporto["stagioni"]
    dici("")
    dici(f"Collaudo {rapporto['squadra']} seme {rapporto['seme']}: "
         f"{len(stag)} stagion{'e' if len(stag) == 1 else 'i'} in "
         f"{rapporto['tempo_totale_s']:.0f} s; impronta {rapporto['impronta']}.")
    c = rapporto["carriera"]
    if c["stagioni_finite"]:
        dici(f"Carriera: deriva eta' titolari {c['deriva_eta_titolari']}, esordienti per anno "
             f"{c['esordienti_per_anno']}, dominio medio {c['dominio_medio']}.")
    for n in rapporto["note"]:
        dici(f"Nota: {n}")
    for e in errori:
        dove = (f"nella stagione {e['stagione']}" if e["stagione"] is not None
                else "all'apertura della carriera")
        dici(f"- ERRORE {dove}: {e['traccia'].strip().splitlines()[-1]}")
        # il punto piu' interno della traccia, file e riga: e' li' che si
        # guarda per primo, anche quando la traccia intera e' scorsa via
        punti = [r.strip() for r in e["traccia"].splitlines() if r.strip().startswith('File "')]
        if punti:
            dici(f"    {punti[-1]}")
    for x in rotti:
        dici(f"- Salvataggio {x['anno']} ({x['momento']}): ricaricato non torna uguale. "
             f"Prime differenze:")
        for riga in x["differenze"]:
            dici(f"    {riga}")
    for v in fuori:
        dici(f"- {v['stagione']}: {v['misura']} = {v['valore']} fuori soglia ({v['soglia']}). "
             f"{v['perche']}")
    ok = not (fuori or rotti or errori)
    rapporto["esito"] = "superato" if ok else "non superato"
    if ok:
        dici("ESITO: collaudo superato - nessun errore, salvataggi identici, "
             "tutte le misure dentro le soglie.")
    else:
        dici(f"ESITO: collaudo NON superato - {len(errori)} errori, {len(rotti)} salvataggi "
             f"diversi, {len(fuori)} misure fuori soglia.")
    return 0 if ok else 1


def scrivi_json(percorso, dati) -> None:
    p = Path(percorso)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ------------------------------------------------------------- prima e dopo
def _togli_sola_lettura(funzione, percorso, _info) -> None:
    # su Windows un file in sola lettura non si cancella: gli si toglie il
    # blocco e si riprova
    try:
        os.chmod(percorso, stat.S_IWRITE)
        funzione(percorso)
    except OSError:
        pass


def estrai_commit(radice: Path, commit: str, dove: Path) -> str:
    """Il codice di `commit` in una cartella a parte, senza toccare il lavoro in corso.

    Niente stash e niente checkout: git archive scrive il commit cosi' com'e'
    in un tar, e lo si apre altrove. Le modifiche non ancora salvate restano
    dove sono.
    """
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git non si trova: serve per estrarre il commit di riferimento")
    # un "commit" che comincia col trattino git lo leggerebbe come un'opzione
    # (--output=... scrive dove vuole lui): si ferma prima di chiederglielo
    if not commit or commit.startswith("-"):
        raise RuntimeError(f"{commit!r} non e' un commit")

    def risolvi(*opzioni) -> str:
        # ^{commit}: un nome di ramo, un tag o una sigla vanno bene, un file o
        # una cartella no
        r = subprocess.run([git, "-C", str(radice), "rev-parse", "--verify", *opzioni,
                            commit + "^{commit}"],
                           capture_output=True, text=True, encoding="utf-8", check=False)
        if r.returncode != 0:
            raise RuntimeError(f"commit {commit!r} sconosciuto: "
                               f"{r.stderr.strip() or 'git non lo trova'}")
        return r.stdout.strip()

    completo, sigla = risolvi(), risolvi("--short")
    tar = subprocess.run([git, "-C", str(radice), "archive", "--format=tar", completo],
                         capture_output=True, check=False)
    if tar.returncode != 0:
        raise RuntimeError("git archive non riuscito: "
                           + tar.stderr.decode("utf-8", "replace").strip())
    dove.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(dove, filter="data")
        else:
            t.extractall(dove)
    # la taratura dei circuiti e' gia' fatta per il codice di adesso: se il
    # modello del giro e' lo stesso la si rilegge, se e' cambiato la chiave
    # non torna e il commit vecchio se la rifa'
    cache = radice / "cache" / "tarature"
    if cache.is_dir():
        shutil.copytree(cache, dove / "cache" / "tarature", dirs_exist_ok=True)
    return sigla


def _scenario(a) -> list:
    """Gli argomenti dello scenario, uguali per il prima e per il dopo."""
    out = [a.squadra, "--seme", str(a.seme), "--stagioni", str(a.stagioni)]
    if a.fe:
        out.append("--fe")
    if a.wec:
        out.append("--wec")
    if a.gare:
        out += ["--gare", str(a.gare)]
    if a.parti_da:
        out += ["--parti-da", str(Path(a.parti_da).resolve())]
    if a.soglie:
        out += ["--soglie", str(Path(a.soglie).resolve())]
    if a.dettaglio:
        out.append("--dettaglio")
    return out


def _fermato(numero, _quadro) -> None:
    raise SystemExit(128 + numero)


def _segui(proc, prefisso: str, blocco: threading.Lock) -> None:
    for riga in proc.stdout:
        with blocco:
            print(f"[{prefisso}] {riga.rstrip()}", flush=True)


def confronta(a) -> int:
    """Lo stesso scenario sul commit di riferimento e sul codice di adesso.

    Le due carriere girano insieme, in due processi: sono indipendenti e cosi'
    il confronto costa il tempo di una sola. Lo script e' sempre questo, con
    le soglie di adesso: cambia solo il gioco su cui gira.
    """
    radice = Path(a.radice).resolve() if a.radice else REPO
    tmp = Path(tempfile.mkdtemp(prefix="collaudo_rif_"))
    processi = {}
    # fermato da fuori (Ctrl+C, o il comando in background chiuso prima della
    # fine) deve comunque passare dal finally: se no le due carriere figlie
    # restano a girare per minuti senza padre e la copia del commit resta
    # nella cartella temporanea
    try:
        signal.signal(signal.SIGTERM, _fermato)
    except (ValueError, OSError):
        pass
    try:
        try:
            sigla = estrai_commit(radice, a.rif, tmp / "albero")
        except Exception as exc:
            dici(f"Riferimento non disponibile: {exc}")
            return 2
        dici(f"Prima: commit {sigla} (estratto in {tmp / 'albero'}); dopo: {radice}.")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        base = [sys.executable, str(Path(__file__).resolve())] + _scenario(a)
        # con --salva-in e' il codice di riferimento a scrivere la carriera: e'
        # la strada piu' corta per avere un salvataggio "di prima" da aprire
        # poi con --parti-da sul codice nuovo, senza tirare fuori un eseguibile
        # vecchio
        lanci = {
            "prima": base + ["--radice", str(tmp / "albero"), "--json", str(tmp / "prima.json")]
            + (["--salva-in", str(Path(a.salva_in).resolve())] if a.salva_in else []),
            "dopo": base + ["--radice", str(radice), "--json", str(tmp / "dopo.json")],
        }
        blocco = threading.Lock()
        fili = []
        for nome, cmd in lanci.items():
            p = subprocess.Popen(cmd, cwd=str(tmp), env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace")
            processi[nome] = p
            f = threading.Thread(target=_segui, args=(p, nome, blocco), daemon=True)
            f.start()
            fili.append(f)
        codici = {nome: p.wait() for nome, p in processi.items()}
        for f in fili:
            f.join(timeout=5)
        rapporti = {}
        for nome in lanci:
            try:
                rapporti[nome] = json.loads((tmp / f"{nome}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rapporti[nome] = None
        stampa_confronto(sigla, rapporti, codici)
        if a.json:
            scrivi_json(a.json, {"rif": a.rif, "sigla": sigla, "codici": codici, **rapporti})
        if rapporti["dopo"] is None:
            return 1
        return 0 if codici["dopo"] == 0 else 1
    finally:
        for p in processi.values():
            if p.poll() is None:
                p.kill()
                p.wait()
        # da Python 3.12 il gancio si chiama onexc, e onerror e' deprecato
        if sys.version_info >= (3, 12):
            shutil.rmtree(tmp, onexc=_togli_sola_lettura)
        else:
            shutil.rmtree(tmp, onerror=_togli_sola_lettura)


def _medie(r) -> dict:
    """Una riga per misura: la media sulle stagioni (la deriva e' quella finale)."""
    if not r:
        return {}
    out = {}
    for chiave, _, _ in MISURE:
        valori = [s[chiave] for s in r.get("stagioni", []) if s.get(chiave) is not None]
        if not valori:
            out[chiave] = None
        elif chiave in ("deriva_eta_titolari", "dimensione_salvataggio_kb"):
            out[chiave] = valori[-1]
        else:
            out[chiave] = statistics.mean(valori)
    return out


def stampa_confronto(sigla: str, rapporti: dict, codici: dict) -> None:
    prima, dopo = _medie(rapporti["prima"]), _medie(rapporti["dopo"])

    def f(v, cifre):
        return "-" if v is None else f"{v:.{cifre}f}"

    dici("")
    dici(f"{'misura':<32}{'prima (' + sigla + ')':>18}{'dopo':>12}{'delta':>12}")
    dici("-" * 74)
    for chiave, etichetta, cifre in MISURE:
        p, d = prima.get(chiave), dopo.get(chiave)
        delta = f"{d - p:+.{cifre}f}" if p is not None and d is not None else "-"
        dici(f"{etichetta:<32}{f(p, cifre):>18}{f(d, cifre):>12}{delta:>12}")
    dici("-" * 74)

    def esito(nome):
        r = rapporti[nome]
        if r is None:
            return f"nessun rapporto (uscita {codici[nome]})"
        return (f"{r.get('esito', '?')}, {len(r.get('fuori_soglia', []))} fuori soglia, "
                f"{len(r.get('errori', []))} errori, impronta {r.get('impronta', '-')}")
    dici(f"prima: {esito('prima')}")
    dici(f"dopo:  {esito('dopo')}")
    if rapporti["prima"] and rapporti["dopo"]:
        if rapporti["prima"].get("impronta") == rapporti["dopo"].get("impronta"):
            dici("Stessa impronta: a parita' di seme il codice nuovo da' esattamente "
                 "gli stessi numeri del riferimento.")
        else:
            dici("Impronte diverse: il codice nuovo cambia i risultati della carriera "
                 "(atteso se si e' toccata la simulazione).")


# ------------------------------------------------------------------ avvio
def main(argv=None) -> int:
    prepara_console()
    a = leggi_argomenti(argv)
    radice = Path(a.radice).resolve() if a.radice else REPO
    if not (radice / "game" / "core" / "state.py").is_file():
        dici(f"Non trovo il gioco in {radice}: questo file deve stare in "
             f".claude/skills/collaudo/ dentro al repository.")
        return 2
    if not a.parti_da:
        # un nome sbagliato si dice subito, con quelli giusti accanto, invece di
        # lasciarlo cadere dentro new_game con un KeyError
        try:
            dati = json.loads((radice / "data" / "teams.json").read_text(encoding="utf-8"))
            squadre = [t["id"] for t in dati.get("teams", [])]
        except (OSError, ValueError, KeyError, TypeError):
            squadre = []
        if squadre and a.squadra not in squadre:
            dici(f"Squadra {a.squadra!r} sconosciuta. Quelle in griglia: {', '.join(squadre)}.")
            return 2
    if a.rif:
        return confronta(a)
    soglie = carica_soglie(a.soglie or SOGLIE)
    descr = f"{a.squadra}, seme {a.seme}"
    if a.parti_da:
        descr = f"da {a.parti_da}"
    quante = (f"prime {a.gare} gare" if a.gare
              else f"{a.stagioni} stagion{'e' if a.stagioni == 1 else 'i'}")
    extra = "".join([" + Formula E" if a.fe else "", " + endurance" if a.wec else ""])
    dici(f"Collaudo di Apex Manager ({radice}): {descr}, {quante}{extra}.")
    collaudo = Collaudo(a, radice)
    rapporto = collaudo.corri()
    codice = giudica(rapporto, soglie)
    if a.json:
        scrivi_json(a.json, rapporto)
    return codice


if __name__ == "__main__":
    sys.exit(main())
