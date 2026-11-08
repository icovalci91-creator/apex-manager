"""La prova dei salvataggi, subito prima di ogni commit che tocca il gioco.

Chi gioca si porta la carriera da un eseguibile all'altro: scarica la build
nuova e riapre il salvataggio della sera prima. GameState.from_dict legge i
campi recenti con .get(chiave, predefinito) e i piu' vecchi con td["..."]:
un campo nuovo letto con le parentesi quadre fa saltare ogni salvataggio che
gia' esiste, e dai test non si vede, perche' una carriera nuova quel campo ce
l'ha. Lo stesso per un import circolare, che dai sorgenti puo' passare o no a
seconda di quale modulo si importa per primo.

Claude fa i commit dentro il suo turno, quindi un hook Stop arriverebbe tardi:
questo e' un PreToolUse su Bash (e PowerShell, su Windows) che si accende solo
per `git commit`, e solo se le modifiche toccano game/, data/ o main.py. Fa
tre cose, in processi Python separati perche' il codice di HEAD e quello
nuovo non possono stare nello stesso interprete:

1. importa ogni modulo del gioco senza schermo, ognuno come primo import
   (cosi' un ciclo salta fuori qualunque sia l'ordine); i moduli
   dell'interfaccia si saltano, dicendolo, se manca pygame o Panda3D, e i
   file che git ignora (i `_*.py` di prova) non si toccano;
2. crea una carriera con Formula E ed endurance aperte usando il codice di
   HEAD (estratto con git archive in una cartella temporanea), la fa correre
   fino al primo gran premio e la salva; il salvataggio si tiene in cache,
   una volta per HEAD. Poi la riapre con il codice nuovo e va avanti ancora
   un po': e' quello che fa un giocatore la sera dopo l'aggiornamento;
3. salva e ricarica una carriera nuova fatta con il codice nuovo.

Se qualcosa si rompe nega il comando con il motivo in italiano, nel formato
JSON che la documentazione degli hook prevede per PreToolUse
(permissionDecision "deny" e permissionDecisionReason). Se lo stesso commit -
stesso HEAD, stesse modifiche - torna dopo un rifiuto, la rottura e' voluta:
passa, con un avviso. Un commit gia' provato con esito buono passa subito.

La prima volta per un HEAD nuovo costa una decina di secondi (la carriera di
HEAD piu' quella nuova, in parallelo); dopo, qualche secondo in meno. Un
commit che non tocca il gioco esce in pochi centesimi. La cache sta in
cache/prova_salvataggi/ (ignorata da git, accanto alle tarature) o, se cache/
non fosse ignorata, nella cartella temporanea del sistema.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

PERCORSI = ("game", "data", "main.py")
SEME = 2026                    # una carriera sempre uguale: lo stesso salvataggio per HEAD
# quanto puo' durare ogni processo figlio, contando da quando parte: la carriera
# di HEAD e quella nuova vanno in parallelo, poi la riapertura. Al peggio fanno
# 150 + 120 secondi, e devono stare nei 300 che .claude/settings.json da'
# all'hook: oltre, Claude Code lo fermerebbe e i figli resterebbero a girare
TEMPO_FIGLIO = 150
TEMPO_RIAPERTURA = 120
SALVATAGGI_TENUTI = 6          # uno per HEAD: quelli vecchi non servono piu'
ESITI_TENUTI = 200
SEGNO = "@@ESITO@@"
SENZA_FINESTRA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# git commit, anche come `git -C cartella commit` o `git -c chiave=valore commit`,
# in mezzo a una catena di comandi; non `git commit-tree`
RE_COMMIT = re.compile(r"(?:^|[\s;&|(`{])git(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|\S+)"
                       r"|--[\w-]+(?:=\S+)?))*\s+commit(?![\w-])")
# comandi che mettono in commit anche quello che adesso non e' nell'indice:
# `git add ... && git commit`, `git commit -a`, `git commit game/x.py -m ...`
RE_AGGIUNGE = re.compile(r"\bgit\b[^;&|\n]*?\s(?:add|rm|mv|stage)(?![\w-])")
RE_COMMIT_TUTTO = re.compile(r"\bcommit\b[^;&|\n]*?\s(?:-[A-Za-z]*a[A-Za-z]*|--all|--include|-i"
                             r"|(?:\./)?(?:game/|data/|main\.py))(?=[\s\"']|$)")


# =================================================================== git
def git(radice, *argomenti: str, binario: bool = False) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ, GIT_OPTIONAL_LOCKS="0")   # mai bloccare l'indice di chi lavora
    try:
        return subprocess.run(["git", "-C", str(radice), *argomenti], capture_output=True,
                              text=not binario, encoding=None if binario else "utf-8",
                              errors=None if binario else "replace", timeout=60, env=ambiente,
                              creationflags=SENZA_FINESTRA)
    except (OSError, subprocess.SubprocessError) as ex:
        return subprocess.CompletedProcess(argomenti, 1, b"" if binario else "", str(ex))


def radice_del_gioco(ingresso: dict) -> Path | None:
    """Il repository del gioco su cui cade il commit: quello della cartella di Claude.

    `cwd` segue Claude (anche dentro un worktree); CLAUDE_PROJECT_DIR e' la
    cartella in cui la sessione e' partita, e fa da ripiego.
    """
    candidati = []
    comando = (ingresso.get("tool_input") or {}).get("command") or ""
    m = re.search(r"\bgit\s+-C\s+(\"[^\"]*\"|'[^']*'|\S+)\s", comando)
    base = ingresso.get("cwd") or os.getcwd()
    if m:
        candidati.append(Path(base) / m.group(1).strip("\"'"))
    candidati += [base, os.environ.get("CLAUDE_PROJECT_DIR")]
    for c in candidati:
        if not c or not Path(c).is_dir():
            continue
        r = git(c, "rev-parse", "--show-toplevel")
        if r.returncode == 0 and r.stdout.strip():
            radice = Path(r.stdout.strip())
            if (radice / "game" / "core" / "state.py").is_file():
                return radice
    return None


def file_toccati(radice: Path, anche_fuori_indice: bool) -> list:
    """I file del commit: quelli nell'indice, e se il comando aggiunge anche il resto."""
    r = git(radice, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if r.returncode != 0:
        return []
    voci, uscita = r.stdout.split("\0"), []
    i = 0
    while i < len(voci):
        voce = voci[i]
        i += 1
        if len(voce) < 4:
            continue
        stato, percorso = voce[:2], voce[3:]
        if stato[0] in "RC":
            i += 1                        # il nome vecchio di un file rinominato
        if stato[0] not in " ?" or anche_fuori_indice:
            uscita.append(percorso)
    return uscita


def tocca_il_gioco(percorsi: list) -> bool:
    return any(p == "main.py" or p.startswith(("game/", "data/")) for p in percorsi)


def impronta(radice: Path, head: str) -> str:
    """Un'impronta del codice provato: HEAD piu' ogni differenza di game/, data/ e main.py.

    E' quello che decide se un commit e' "lo stesso" di prima: dopo un
    rifiuto, la stessa impronta vuol dire che nessuno ha corretto niente.
    """
    h = hashlib.sha1(head.encode())
    h.update(git(radice, "diff", "HEAD", "--binary", "--no-color", "--no-ext-diff", "--",
                 *PERCORSI, binario=True).stdout or b"")
    nuovi = git(radice, "ls-files", "--others", "--exclude-standard", "-z", "--", *PERCORSI)
    for nome in sorted(x for x in nuovi.stdout.split("\0") if x):
        h.update(nome.encode("utf-8"))
        try:
            h.update((radice / nome).read_bytes())
        except OSError:
            pass
    return h.hexdigest()


def cartella_cache(radice: Path) -> Path:
    """cache/prova_salvataggi se git la ignora (come le tarature), se no la cartella temporanea."""
    if git(radice, "check-ignore", "-q", "cache/prova_salvataggi/x").returncode == 0:
        d = radice / "cache" / "prova_salvataggi"
    else:
        sigla = hashlib.sha1(str(radice).encode("utf-8")).hexdigest()[:12]
        d = Path(tempfile.gettempdir()) / "apex_prova_salvataggi" / sigla
    d.mkdir(parents=True, exist_ok=True)
    return d


def scrivi_sicuro(percorso: Path, testo: str) -> None:
    """Scrive tutto in un file accanto e poi lo rinomina: mai un file a meta'."""
    tmp = percorso.with_name(percorso.name + f".{os.getpid()}.tmp")
    tmp.write_text(testo, encoding="utf-8")
    os.replace(tmp, percorso)


def sfoltisci(cartella: Path, schema: str, quanti: int) -> None:
    try:
        vecchi = sorted(cartella.glob(schema), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in vecchi[quanti:]:
            p.unlink()
    except OSError:
        pass


def estrai_head(radice: Path) -> Path | None:
    """game/ e data/ come sono in HEAD, in una cartella temporanea."""
    r = git(radice, "archive", "--format=tar", "HEAD", "game", "data", binario=True)
    if r.returncode != 0:
        return None
    dove = Path(tempfile.mkdtemp(prefix="apex_head_"))
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dove, filter="data")
        else:
            tar.extractall(dove)
    return dove


# ============================================================ i processi figli
def prepara_figlio(radice_codice: Path) -> None:
    """Il gioco senza schermo, importato da `radice_codice` e da nessun altro posto."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, str(radice_codice))


def dimentica_il_gioco() -> None:
    for k in [k for k in sys.modules if k == "game" or k.startswith("game.")]:
        del sys.modules[k]


def esterno_mancante(ex: BaseException) -> str | None:
    """Se l'errore e' una libreria esterna non installata (pygame, panda3d...), il suo nome."""
    while ex is not None:
        if isinstance(ex, ModuleNotFoundError) and ex.name:
            primo = ex.name.split(".")[0]
            if primo != "game" and importlib.util.find_spec(primo) is None:
                return primo
        ex = ex.__cause__ or ex.__context__
    return None


def _rumore(nome_file: str) -> bool:
    """Le righe del traceback che non dicono niente a chi deve correggere il gioco."""
    nome_file = nome_file.replace("\\", "/")
    return (nome_file.startswith("<frozen") or "/importlib/" in nome_file
            or Path(nome_file).name == Path(__file__).name)


def traccia(ex: BaseException, radice: Path, righe: int = 14) -> str:
    """Le ultime righe del traceback, senza questo file ne' importlib, percorsi corti."""
    tb = traceback.TracebackException.from_exception(ex)
    tb.stack = traceback.StackSummary.from_list([f for f in tb.stack if not _rumore(f.filename)])
    testo = "".join(tb.format(chain=False))
    for r in {str(radice), str(radice).replace("\\", "/")}:
        testo = testo.replace(r + os.sep, "").replace(r + "/", "")
    return "\n".join(testo.rstrip().splitlines()[-righe:])


def prima_squadra(radice_codice: Path) -> str:
    try:
        dati = json.loads((radice_codice / "data" / "teams.json").read_text(encoding="utf-8"))
        ids = [t["id"] for t in dati["teams"]]
        return "ferrari" if "ferrari" in ids else ids[0]
    except Exception:
        return "ferrari"


def apri_fe_wec(gs, note: list) -> None:
    """La squadra del giocatore iscritta in Formula E e all'endurance, come dal menu."""
    from game.core import formulae as FE
    gs.player.cash += 600
    try:
        if not FE.ha(gs.player):
            FE.apri(gs, gs.player, f"{gs.player.short} FE")
    except Exception as ex:
        note.append(f"Formula E non aperta ({type(ex).__name__}: {ex})")
    try:
        from game.core import wec as WEC
        if not WEC.ha(gs.player):
            WEC.apri(gs, gs.player, f"{gs.player.short} Endurance", "hypercar")
    except Exception as ex:
        note.append(f"endurance non aperta ({type(ex).__name__}: {ex})")


def avanza(gs, note: list, gran_premi: int = 1, massimo: int = 12) -> list:
    """Il calendario intrecciato fino al primo gran premio corso: E-Prix e tappe endurance comprese.

    Il weekend di Formula 1 e' ridotto a qualifica e gara: qui non si misura
    il gioco, si vuole solo che una carriera caricata vada avanti. Se le
    funzioni che servono hanno cambiato nome non e' colpa del salvataggio: si
    dice e ci si ferma.
    """
    from game.core import season as SEASON
    try:
        from game.core import formulae as FE, rules as RULES, tyres as TY, wec as WEC
        from game.sim import session as S
        from game.sim.weekend import Weather
    except ImportError as ex:
        note.append(f"non si e' fatta avanzare la carriera: {ex}")
        return []
    servono = [(SEASON, "prossimo_evento"), (SEASON, "apply_result"), (SEASON, "after_race"),
               (S, "WeekendState"), (S, "run_qualifying"), (S, "make_race"),
               (TY, "allocate"), (TY, "suggested"), (Weather, "generate"),
               (FE, "simula_gara"), (WEC, "avanza")]
    manca = [n for m, n in servono if not hasattr(m, n)]
    if manca:
        note.append("non si e' fatta avanzare la carriera: mancano " + ", ".join(manca))
        return []
    fatti, gp = [], 0
    for _ in range(massimo):
        ev = SEASON.prossimo_evento(gs)
        if ev is None or gp >= gran_premi:
            break
        if ev["serie"] == "fe":
            FE.simula_gara(gs, gs.player)
        elif ev["serie"] == "wec":
            WEC.avanza(gs)
        else:
            tr = ev["pista"]
            ws = S.WeekendState(track=tr, weather=Weather.generate(tr, gs.rng))
            TY.allocate(gs, ws, TY.suggested(tr))
            S.run_qualifying(gs, ws, "gp")
            sim = S.make_race(gs, ws, kind="gp")
            sim.fast_forward()
            SEASON.apply_result(gs, ws, sim, kind="gp")
            SEASON.after_race(gs)
            if getattr(gs, "pending_votes", None) and gs.phase != "offseason":
                RULES.close_meeting(gs, {})
            gp += 1
        fatti.append(f"{ev['serie']}:{getattr(ev.get('pista'), 'id', '')}")
    return fatti


def salva_e_ricarica(gs, GameState):
    """Come fa il gioco (storage.write_save e read_save): json, utf-8, e di nuovo da capo."""
    testo = json.dumps(gs.to_dict(), ensure_ascii=False)
    gs2 = GameState.from_dict(json.loads(testo))
    json.dumps(gs2.to_dict(), ensure_ascii=False)
    return testo


def moduli_del_gioco(radice: Path) -> list:
    """I moduli di game/ da importare: quelli che git conosce o vedrebbe, non gli ignorati.

    Il .gitignore del progetto tiene fuori i `_*.py`, i file di prova di chi
    lavora: uno lasciato in game/ non va nel commit, e importarlo vorrebbe dire
    eseguirlo - magari per minuti - o fermare un commit che con lui non c'entra.
    Se git non risponde si prendono tutti i .py, come prima.
    """
    r = git(radice, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "game")
    if r.returncode == 0:
        file = [radice / x for x in r.stdout.split("\0") if x.endswith(".py")]
    else:
        file = list((radice / "game").rglob("*.py"))
    moduli = set()
    for p in file:
        if not p.is_file():
            continue                      # cancellato, e non ancora tolto dall'indice
        parti = list(p.relative_to(radice).with_suffix("").parts)
        if parti[-1] == "__init__":
            parti = parti[:-1]
        moduli.add(".".join(parti))
    return sorted(moduli)


def figlio_nuovo(radice: Path) -> dict:
    """Passi 1 e 3 con il codice nuovo: ogni modulo importato da solo, una carriera nuova."""
    prepara_figlio(radice)
    errori, note, saltati, mancanti = [], [], [], set()
    for m in moduli_del_gioco(radice):
        dimentica_il_gioco()
        try:
            importlib.import_module(m)
        except BaseException as ex:          # anche un SystemExit al momento dell'import
            esterno = esterno_mancante(ex)
            if esterno:
                saltati.append(m)
                mancanti.add(esterno)
            else:
                errori.append(f"L'import di {m} (come primo modulo del gioco) fallisce:\n"
                              f"{traccia(ex, radice)}")
    if saltati:
        note.append(f"{len(saltati)} moduli non importati perche' manca "
                    f"{', '.join(sorted(mancanti))} (python -m pip install -r requirements.txt)")
    try:
        compile((radice / "main.py").read_text(encoding="utf-8"), "main.py", "exec")
    except FileNotFoundError:
        pass
    except Exception as ex:
        errori.append(f"main.py non si compila:\n{traccia(ex, radice)}")
    dimentica_il_gioco()
    try:
        from game.core.state import GameState
        gs = GameState.new_game(prima_squadra(radice), True, seed=SEME)
        apri_fe_wec(gs, note)
        salva_e_ricarica(gs, GameState)
    except BaseException as ex:
        esterno = esterno_mancante(ex)
        if esterno:
            note.append(f"carriera nuova non provata: manca {esterno}")
        else:
            errori.append("Una carriera nuova, con Formula E ed endurance, non si salva e "
                          f"ricarica:\n{traccia(ex, radice)}")
    return {"errori": errori, "note": note}


def figlio_crea(copia: Path, radice: Path, destinazione: Path) -> dict:
    """Passo 2, prima meta': la carriera di HEAD, salvata come la salverebbe un giocatore."""
    prepara_figlio(copia)
    note = []
    try:
        from game import config as C
        # le tarature si leggono e si scrivono nella cache del repository: la
        # copia di HEAD e' usa e getta, e ritararla da zero costerebbe secondi
        C.UTENTE = radice
        from game.core.state import GameState
        gs = GameState.new_game(prima_squadra(copia), True, seed=SEME)
        apri_fe_wec(gs, note)
        try:
            avanza(gs, note)
        except Exception as ex:
            note.append(f"la carriera di HEAD non e' andata avanti ({type(ex).__name__}: {ex}); "
                        "si salva com'e'")
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        scrivi_sicuro(destinazione, json.dumps(gs.to_dict(), ensure_ascii=False))
    except BaseException as ex:
        note.append("con il codice di HEAD non si e' riusciti a fare un salvataggio "
                    f"({type(ex).__name__}: {ex}): la prova dei salvataggi vecchi e' saltata")
    return {"errori": [], "note": note}


def figlio_apri(radice: Path, salvataggio: Path, head: str) -> dict:
    """Passo 2, seconda meta': il salvataggio di HEAD aperto con il codice nuovo."""
    prepara_figlio(radice)
    errori, note = [], []
    sigla = head[:7]
    try:
        from game.core.state import GameState
        dati = json.loads(salvataggio.read_text(encoding="utf-8"))
    except BaseException as ex:
        esterno = esterno_mancante(ex)
        note.append(f"salvataggio di HEAD non provato ({esterno or type(ex).__name__})")
        return {"errori": errori, "note": note}
    try:
        gs = GameState.from_dict(dati)
    except BaseException as ex:
        errori.append(f"Una carriera salvata con il codice di HEAD ({sigla}), Formula E ed "
                      f"endurance aperte, non si apre piu':\n{traccia(ex, radice)}")
        return {"errori": errori, "note": note}
    try:
        avanza(gs, note)
    except BaseException as ex:
        errori.append(f"La carriera salvata con il codice di HEAD ({sigla}) si apre, ma non va "
                      f"avanti:\n{traccia(ex, radice)}")
        return {"errori": errori, "note": note}
    try:
        salva_e_ricarica(gs, GameState)
    except BaseException as ex:
        errori.append(f"La carriera salvata con il codice di HEAD ({sigla}), aperta e fatta "
                      f"avanzare, non si salva e ricarica:\n{traccia(ex, radice)}")
    return {"errori": errori, "note": note}


def figlio(argomenti: list) -> int:
    """Un passo della prova, in un interprete tutto suo. Il risultato va su stdout, marcato."""
    ruolo, *resto = argomenti
    vero_stdout = sys.stdout
    # quello che il gioco stampa non deve confondersi con l'esito
    with contextlib.redirect_stdout(sys.stderr):
        if ruolo == "nuovo":
            esito = figlio_nuovo(Path(resto[0]))
        elif ruolo == "crea":
            esito = figlio_crea(Path(resto[0]), Path(resto[1]), Path(resto[2]))
        else:
            esito = figlio_apri(Path(resto[0]), Path(resto[1]), resto[2])
    vero_stdout.write(SEGNO + json.dumps(esito, ensure_ascii=True) + "\n")
    vero_stdout.flush()
    return 0


# ============================================================== la prova
def lancia(tempo: float, *argomenti: str) -> tuple:
    """Un passo della prova in un processo a parte; l'uscita va in due file temporanei.

    Due file e non due pipe: i figli corrono in parallelo e si leggono uno
    alla volta, e un figlio che scrive tanto su una pipe che nessuno legge
    ancora si fermerebbe ad aspettare. Il tempo concesso parte adesso, non da
    quando lo si aspetta: contato dall'attesa, un figlio aspettato per ultimo
    avrebbe il suo tempo piu' quello degli altri.
    """
    ambiente = dict(os.environ, PYTHONIOENCODING="utf-8", SDL_VIDEODRIVER="dummy",
                    SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
    ambiente.pop("PYTHONPATH", None)      # il gioco si importa solo da dove si dice
    out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--figlio",
                             *argomenti], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                            env=ambiente, creationflags=SENZA_FINESTRA)
    return proc, out, err, time.monotonic() + tempo, tempo


def raccogli(lanciato: tuple, nome: str) -> dict:
    proc, out, err, scadenza, tempo = lanciato
    try:
        try:
            proc.wait(timeout=max(0.0, scadenza - time.monotonic()))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"errori": [], "note": [f"{nome}: oltre {int(tempo)} s, fermata e non contata"]}
        out.seek(0)
        err.seek(0)
        testo = out.read().decode("utf-8", errors="replace")
        for riga in reversed(testo.splitlines()):
            if riga.startswith(SEGNO):
                return json.loads(riga[len(SEGNO):])
        coda = err.read().decode("utf-8", errors="replace").strip().splitlines()[-12:]
        return {"errori": [f"{nome}: il processo di prova e' finito senza esito "
                           f"(codice {proc.returncode}):\n" + "\n".join(coda)], "note": []}
    finally:
        out.close()
        err.close()


def prova(radice: Path, cache: Path, head: str) -> tuple:
    """I tre passi. (errori, note).

    L'import dei moduli con la carriera nuova parte subito, e intanto si
    prepara il salvataggio di HEAD; la riapertura parte appena il salvataggio
    c'e' - subito, se e' gia' in cache - e i due processi corrono insieme.
    """
    salvataggio = cache / f"salvataggio-{head}.json"
    nuovo = lancia(TEMPO_FIGLIO, "nuovo", str(radice))
    esiti, apri = [], None
    if not salvataggio.is_file():
        copia = estrai_head(radice)
        if copia is None:
            esiti.append({"errori": [], "note": ["git archive di HEAD non riuscito: "
                                                  "la prova dei salvataggi vecchi e' saltata"]})
        else:
            try:
                esiti.append(raccogli(lancia(TEMPO_FIGLIO, "crea", str(copia), str(radice),
                                             str(salvataggio)), "carriera di HEAD"))
            finally:
                shutil.rmtree(copia, ignore_errors=True)
    if salvataggio.is_file():
        os.utime(salvataggio)             # usato adesso: e' l'ultimo da buttare
        apri = lancia(TEMPO_RIAPERTURA, "apri", str(radice), str(salvataggio), head)
    esiti.append(raccogli(nuovo, "import dei moduli e carriera nuova"))
    if apri is not None:
        esiti.append(raccogli(apri, "salvataggio di HEAD riaperto"))
    sfoltisci(cache, "salvataggio-*.json", SALVATAGGI_TENUTI)
    errori = [e for x in esiti for e in x.get("errori", [])]
    note = [n for x in esiti for n in x.get("note", [])]
    return errori, note


def rispondi(decisione: str | None, motivo: str = "", avviso: str = "") -> None:
    uscita: dict = {}
    if decisione == "deny":
        uscita["hookSpecificOutput"] = {"hookEventName": "PreToolUse",
                                        "permissionDecision": "deny",
                                        "permissionDecisionReason": motivo}
    elif avviso:
        # nessuna decisione: il commit segue il giro normale dei permessi, e
        # l'avviso arriva sia a chi guarda (systemMessage) sia a Claude
        uscita["systemMessage"] = avviso
        uscita["hookSpecificOutput"] = {"hookEventName": "PreToolUse",
                                        "additionalContext": avviso}
    if uscita:
        sys.stdout.write(json.dumps(uscita, ensure_ascii=True) + "\n")


def principale() -> int:
    try:
        ingresso = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    except ValueError:
        return 0
    if ingresso.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    comando = (ingresso.get("tool_input") or {}).get("command") or ""
    # il filtro "if" delle impostazioni e' fatto al meglio delle possibilita':
    # quando non capisce un comando lancia l'hook comunque. Si ricontrolla qui
    if not RE_COMMIT.search(comando):
        return 0
    radice = radice_del_gioco(ingresso)
    if radice is None:
        return 0
    aggiunge = bool(RE_AGGIUNGE.search(comando) or RE_COMMIT_TUTTO.search(comando))
    if not tocca_il_gioco(file_toccati(radice, aggiunge)):
        return 0
    r = git(radice, "rev-parse", "HEAD")
    if r.returncode != 0:
        return 0                          # il primo commit: non c'e' un prima da riaprire
    head = r.stdout.strip()
    cache = cartella_cache(radice)
    esiti = cache / "esiti"
    esiti.mkdir(exist_ok=True)
    firma = impronta(radice, head)
    registro = esiti / f"{firma}.json"
    try:
        gia = json.loads(registro.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gia = None
    if gia and gia.get("esito") == "ok":
        return 0                          # stesso codice, gia' provato: passa e basta
    if gia and gia.get("esito") == "negato":
        rispondi(None, avviso="Prova dei salvataggi: questo stesso commit era gia' stato "
                              "fermato e torna senza modifiche, quindi la rottura e' voluta e "
                              "lo si lascia passare. Chi ha una carriera salvata con la "
                              "versione di prima potrebbe non riaprirla. Motivo di allora:\n"
                              + gia.get("motivo", "")[:3000])
        return 0
    t0 = time.perf_counter()
    errori, note = prova(radice, cache, head)
    durata = time.perf_counter() - t0
    if errori:
        motivo = ("Commit fermato dalla prova dei salvataggi (.claude/hooks/prova_salvataggi.py, "
                  f"{durata:.0f} s). I giocatori portano la carriera da un eseguibile "
                  "all'altro, e con queste modifiche:\n\n" + "\n\n".join(errori[:6]))
        tutto = "\n".join(errori)
        if "KeyError" in tutto or "from_dict" in tutto:
            motivo += ("\n\nUn campo nuovo, in GameState.from_dict come negli stati che il "
                       "salvataggio si porta dietro (fe_stato, wec_stato...), si legge con "
                       ".get(chiave, predefinito), mai con td[\"...\"]. E un id tolto o "
                       "rinominato in data/ i salvataggi vecchi lo cercano ancora.")
        if "circular import" in tutto or "partially initialized" in tutto:
            motivo += ("\n\nUn import circolare nel gioco si scioglie come altrove nel codice: "
                       "l'import va dentro la funzione che lo usa.")
        motivo += ("\n\nSe la rottura e' voluta, lo stesso commit ripetuto senza cambiare niente "
                   "passa, con un avviso.")
        if note:
            motivo += "\n\nNote: " + "; ".join(note)
        motivo = motivo[:9000]
        scrivi_sicuro(registro, json.dumps({"esito": "negato", "motivo": motivo,
                                            "head": head, "quando": time.time()}))
        sfoltisci(esiti, "*.json", ESITI_TENUTI)
        rispondi("deny", motivo)
        return 0
    scrivi_sicuro(registro, json.dumps({"esito": "ok", "head": head, "quando": time.time(),
                                        "durata": round(durata, 1), "note": note}))
    sfoltisci(esiti, "*.json", ESITI_TENUTI)
    if note:
        rispondi(None, avviso=f"Prova dei salvataggi passata ({durata:.0f} s), con delle note: "
                              + "; ".join(note))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--figlio":
        sys.exit(figlio(sys.argv[2:]))
    try:
        sys.exit(principale())
    except Exception as ex:               # un difetto della prova non deve fermare i commit
        sys.stderr.write(f"prova_salvataggi: errore interno ({type(ex).__name__}: {ex})\n")
        sys.exit(1)
