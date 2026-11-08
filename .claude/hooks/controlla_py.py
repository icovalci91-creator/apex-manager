"""Il controllo di un file appena scritto da Claude, prima di costruirci sopra.

Claude cambia un file alla volta, e l'errore fatto in un punto si vede spesso
da un'altra parte: una costante rinominata in sim/weekend.py rompe
sim/benzina.py, che la importa dentro una funzione e se ne accorge solo a
meta' di una gara. Un import di Panda3D che dai sorgenti funziona manca
nell'eseguibile, e lo si scopre su Windows, giocando. Un data/*.json con una
virgola di troppo non fa partire nemmeno il menu.

Questo controllo gira dopo ogni Edit o Write (e' un hook PostToolUse, in
.claude/settings.json) e guarda il solo file appena scritto: che si compili,
che pyflakes (o ruff) non trovi niente di nuovo, che i nomi presi da altri
moduli del gioco ci siano davvero - e, se il file e' un modulo che ha perso
un nome, chi lo usa ancora - che non arrivi un import escluso da apex.spec,
che i json di data/ si leggano. Piu' due avvisi di casa: lettere accentate
nelle stringhe e moduli del modello del giro che mancano in _MODULI di
core/taratura.py, con il rischio di rileggere tarature vecchie.

Di problemi ne riporta solo di nuovi rispetto al file com'e' in HEAD: quelli
che c'erano gia' non li ha portati questa modifica, e ripeterli a ogni Edit
li renderebbe rumore. Un import non ancora usato e' solo un avviso: a meta'
di una modifica e' normale, si usa due righe dopo.

Tace quando va tutto bene. Quando qualcosa non va lo dice a Claude come la
documentazione degli hook prevede per PostToolUse: un oggetto JSON con
"decision": "block" e il motivo per gli errori, "additionalContext" per i
soli avvisi. Il file e' gia' scritto e nessuno lo annulla: il messaggio
arriva accanto al risultato dello strumento, e Claude corregge.

Non scrive niente su disco e non tiene niente in cache fra un'esecuzione e
l'altra: legge con ast i soli moduli che servono, e resta sotto il secondo
anche sui file piu' lunghi del gioco.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tokenize
import unicodedata
from collections import Counter
from pathlib import Path

# un hook non deve lasciare tracce: niente __pycache__ accanto ai moduli letti
sys.dont_write_bytecode = True

# i problemi di pyflakes che a meta' di una modifica sono normali: un import
# messo prima di scrivere il codice che lo usa, una variabile che servira'
# alla riga dopo. Sono avvisi, non errori
AVVISI_RUFF = {"F401", "F841", "F541"}
AVVISI_PYFLAKES = {"UnusedImport", "UnusedVariable", "FStringMissingPlaceholders"}

# i nomi che ogni modulo ha senza definirli
NOMI_DI_MODULO = {"__name__", "__file__", "__doc__", "__dict__", "__spec__", "__path__",
                  "__loader__", "__package__", "__builtins__", "__all__", "__cached__",
                  "__annotations__", "__version__"}

# dove non si cercano moduli che usano un nome perso: roba generata, scaricata
# o lasciata da altri programmi
CARTELLE_SALTATE = {".git", "__pycache__", "build", "dist", "cache", "node_modules", "venv",
                    ".venv", "env", ".ruff_cache", "grafica", "dintorni", "assets",
                    "screenshots", "saves", "build_cartella", "dist_cartella"}

# le eccezioni che, attorno a un import, vogliono dire "se manca si fa senza"
GUARDIE = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}

# oltre queste righe per sezione il messaggio diventa un muro: le prime bastano
MASSIMO = 30

# su Windows ogni processo figlio aprirebbe per un attimo una console
SENZA_FINESTRA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# i sorgenti si leggono come li legge Python: utf-8, e un BOM in testa - che il
# Blocco note e Visual Studio su Windows mettono volentieri - non e' un errore.
# Letto con "utf-8" il BOM resterebbe nel testo, e ast.parse lo prenderebbe per
# un carattere non valido alla riga 1
SORGENTE = "utf-8-sig"

# ruff e pyflakes scrivono la riga anche dentro il messaggio ("redefinition of
# unused `os` from line 3"): per dire se un problema c'era gia' in HEAD il
# numero va tolto, se no basta una riga aggiunta sopra a farlo sembrare nuovo
RIGA_NEL_MESSAGGIO = re.compile(r"\bline \d+", re.IGNORECASE)


# ------------------------------------------------------------------ git
def leggi_da_head(radice: Path, percorsi: list) -> dict:
    """Il testo di piu' file com'e' in HEAD, con un solo processo git.

    Un `git show` per file costa poco su Linux ma su Windows ogni processo
    pesa: `cat-file --batch` li legge tutti in una volta. Un file che in HEAD
    non c'e' (nuovo, o repository senza commit) torna None.
    """
    esito = {p: None for p in percorsi}
    if not percorsi:
        return esito
    richiesta = "".join(f"HEAD:{p}\n" for p in percorsi).encode("utf-8")
    try:
        r = subprocess.run(["git", "-C", str(radice), "cat-file", "--batch"], input=richiesta,
                           capture_output=True, timeout=10, creationflags=SENZA_FINESTRA)
    except (OSError, subprocess.SubprocessError):
        return esito
    dati, pos = r.stdout, 0
    for p in percorsi:
        fine = dati.find(b"\n", pos)
        if fine < 0:
            break
        testata = dati[pos:fine].split()
        pos = fine + 1
        if len(testata) != 3 or testata[1] != b"blob":
            continue                      # "missing", o una cartella
        lungo = int(testata[2])
        # gli a capo come li legge read_text: su Windows, con autocrlf, il
        # file sul disco ha \r\n e quello in HEAD no, e i confronti sbaglierebbero
        esito[p] = (dati[pos:pos + lungo].decode(SORGENTE, errors="replace")
                    .replace("\r\n", "\n"))
        pos += lungo + 1
    return esito


def trova_radice(percorso: Path) -> Path | None:
    """La cartella del repository che contiene il file, se c'e'."""
    for d in percorso.parents:
        if (d / ".git").exists():
            return d
    return None


# ------------------------------------------------------------ i moduli
def nome_modulo(rel: Path) -> tuple:
    """game/sim/benzina.py -> ("game.sim.benzina", False); un __init__ e' il pacchetto."""
    parti = list(rel.with_suffix("").parts)
    pacchetto = bool(parti) and parti[-1] == "__init__"
    if pacchetto:
        parti = parti[:-1]
    return ".".join(parti), pacchetto


def risolvi(modulo: str, pacchetto: bool, nodo: ast.ImportFrom) -> str | None:
    """Il modulo pieno di un `from ... import`, relativo o no."""
    if not nodo.level:
        return nodo.module
    parti = modulo.split(".") if pacchetto else modulo.split(".")[:-1]
    if nodo.level - 1 >= len(parti):
        return None                       # piu' punti che pacchetti: lo dira' Python
    if nodo.level > 1:
        parti = parti[:len(parti) - (nodo.level - 1)]
    base = ".".join(parti)
    return f"{base}.{nodo.module}" if nodo.module else base


class _Aperto(Exception):
    """Un modulo che puo' avere nomi che ast non vede (import *, __getattr__)."""


def nomi_definiti(albero: ast.Module) -> set | None:
    """I nomi che un modulo ha al primo livello, o None se non si possono sapere.

    Si scende negli if, nei try, nei with e nei cicli del primo livello, non
    nelle funzioni: ma un `global` dentro una funzione crea un nome del
    modulo, e quelli si contano. Un `import *` o un `__getattr__` di modulo
    rendono l'elenco aperto, e allora non si giudica niente.
    """
    nomi = set(NOMI_DI_MODULO)

    def bersaglio(t) -> None:
        for n in ast.walk(t):
            if isinstance(n, ast.Name):
                nomi.add(n.id)

    def blocco(corpo) -> None:
        for n in corpo:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nomi.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    bersaglio(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                bersaglio(n.target)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    nomi.add(a.asname or a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module == "__future__":
                    continue              # nessuno importa `annotations` da un modulo del gioco
                for a in n.names:
                    if a.name == "*":
                        raise _Aperto
                    nomi.add(a.asname or a.name)
            elif isinstance(n, (ast.For, ast.AsyncFor)):
                bersaglio(n.target)
                blocco(n.body)
                blocco(n.orelse)
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                for voce in n.items:
                    if voce.optional_vars is not None:
                        bersaglio(voce.optional_vars)
                blocco(n.body)
            elif isinstance(n, (ast.If, ast.While)):
                blocco(n.body)
                blocco(n.orelse)
            elif isinstance(n, ast.Try) or type(n).__name__ == "TryStar":
                blocco(n.body)
                for h in n.handlers:
                    if h.name:
                        nomi.add(h.name)
                    blocco(h.body)
                blocco(n.orelse)
                blocco(n.finalbody)
            elif type(n).__name__ == "Match":
                for caso in n.cases:
                    blocco(caso.body)

    try:
        blocco(albero.body)
    except _Aperto:
        return None
    for n in ast.walk(albero):
        if isinstance(n, ast.Global):
            nomi.update(n.names)
        elif isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
            nomi.add(n.target.id)     # largo: meglio un nome in piu' che un falso allarme
    if "__getattr__" in nomi:
        return None
    return nomi


class Moduli:
    """I moduli del repository, letti con ast quando servono e solo per questa esecuzione."""

    def __init__(self, radice: Path):
        self.radice = radice
        try:
            self.pacchetti = {d.name for d in radice.iterdir()
                              if d.is_dir() and (d / "__init__.py").is_file()}
        except OSError:
            self.pacchetti = set()
        self._file: dict = {}
        self._nomi: dict = {}

    def locale(self, nome: str | None) -> bool:
        return bool(nome) and nome.split(".")[0] in self.pacchetti

    def file(self, nome: str) -> Path | None:
        if nome not in self._file:
            base = self.radice.joinpath(*nome.split("."))
            trovato = None
            for p in (base.parent / f"{base.name}.py", base / "__init__.py"):
                if p.is_file():
                    trovato = p
                    break
            self._file[nome] = trovato
        return self._file[nome]

    def nomi(self, nome: str) -> set | None:
        if nome not in self._nomi:
            f = self.file(nome)
            try:
                albero = ast.parse(f.read_text(encoding=SORGENTE)) if f else None
                self._nomi[nome] = nomi_definiti(albero) if albero else None
            except (OSError, SyntaxError, ValueError):
                self._nomi[nome] = None
        return self._nomi[nome]

    def ha(self, modulo: str, nome: str) -> bool:
        """`modulo.nome` esiste? Un sottomodulo vale come nome; un elenco aperto anche."""
        if self.file(f"{modulo}.{nome}") is not None:
            return True
        noti = self.nomi(modulo)
        return noti is None or nome in noti


def legami_moduli(albero: ast.Module, modulo: str, pacchetto: bool, moduli: Moduli) -> dict:
    """Quali nomi del file sono moduli del gioco: {"C": "game.config", "pace": "game.sim.pace"}.

    Un nome che nel file e' anche un parametro, una variabile o un import di
    qualcos'altro si lascia stare: senza seguire gli ambiti uno per uno non si
    saprebbe a cosa punta in quella riga, e un falso allarme costa piu' di un
    controllo saltato.
    """
    legami: dict = {}
    dubbi: set = set()

    def lega(alias: str, pieno: str) -> None:
        if legami.get(alias, pieno) != pieno:
            dubbi.add(alias)
        legami[alias] = pieno

    for n in ast.walk(albero):
        if isinstance(n, ast.ImportFrom):
            base = risolvi(modulo, pacchetto, n)
            for a in n.names:
                alias = a.asname or a.name
                if base and moduli.locale(base) and moduli.file(f"{base}.{a.name}"):
                    lega(alias, f"{base}.{a.name}")
                else:
                    dubbi.add(alias)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.asname and moduli.locale(a.name) and moduli.file(a.name):
                    lega(a.asname, a.name)
                elif a.asname:
                    dubbi.add(a.asname)
        elif isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
            dubbi.add(n.id)
        elif isinstance(n, ast.arg):
            dubbi.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            dubbi.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            dubbi.add(n.name)
        elif isinstance(n, ast.Global):
            dubbi.update(n.names)
    for alias in dubbi:
        legami.pop(alias, None)
    return legami


def testo_import(n: ast.ImportFrom) -> str:
    nomi = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in n.names)
    return f"from {'.' * n.level}{n.module or ''} import {nomi}"


def nomi_mancanti(albero, modulo, pacchetto, moduli: Moduli) -> list:
    """I nomi presi da moduli del gioco che quei moduli non hanno: [(riga, testo)]."""
    trovati = []
    for n in ast.walk(albero):
        if isinstance(n, ast.ImportFrom):
            base = risolvi(modulo, pacchetto, n)
            if not moduli.locale(base):
                continue
            if moduli.file(base) is None:
                trovati.append((n.lineno, f"`{testo_import(n)}`: il modulo {base} non esiste"))
                continue
            for a in n.names:
                if a.name != "*" and not moduli.ha(base, a.name):
                    trovati.append((n.lineno, f"`{testo_import(n)}`: in {base} non c'e' "
                                              f"`{a.name}`"))
        elif isinstance(n, ast.Import):
            for a in n.names:
                if moduli.locale(a.name) and moduli.file(a.name) is None:
                    trovati.append((n.lineno, f"`import {a.name}`: il modulo non esiste"))
    # gli attributi letti su un modulo del gioco: C.NOME con C = game.config,
    # pace.funzione(...) con pace = game.sim.pace. Uno per nome, con le righe
    legami = legami_moduli(albero, modulo, pacchetto, moduli)
    righe: dict = {}
    for n in ast.walk(albero):
        if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
                and isinstance(n.value, ast.Name) and n.value.id in legami):
            m = legami[n.value.id]
            if not moduli.ha(m, n.attr):
                righe.setdefault((n.value.id, n.attr, m), []).append(n.lineno)
    for (alias, attr, m), elenco in righe.items():
        trovati.append((elenco[0], f"`{alias}.{attr}` (righe {elenca(elenco)}): in {m} "
                                   f"non c'e' `{attr}`"))
    return trovati


def elenca(righe: list, quante: int = 8) -> str:
    righe = sorted(set(righe))
    if len(righe) <= quante + 1:          # "e altre 1" non si scrive: si mette la riga
        return ", ".join(str(r) for r in righe)
    return ", ".join(str(r) for r in righe[:quante]) + f" e altre {len(righe) - quante}"


def file_python(radice: Path):
    """Tutti i .py del repository, fuori dalle cartelle di roba generata.

    Una sottocartella con un suo .git e' un altro checkout, non questo: i
    worktree di Claude Code stanno proprio in .claude/worktrees/, copie intere
    del gioco su altri rami. Contarle vorrebbe dire dare per utenti di un nome
    perso i file di un altro ramo, e leggere il gioco due o tre volte.
    """
    pila = [radice]
    while pila:
        d = pila.pop()
        try:
            voci = list(d.iterdir())
        except OSError:
            continue
        for v in voci:
            if v.is_dir():
                if v.name in CARTELLE_SALTATE or (v.name.startswith(".") and v.name != ".claude"):
                    continue
                if (v / ".git").exists():
                    continue
                pila.append(v)
            elif v.suffix == ".py":
                yield v


def usi_dei_persi(radice: Path, percorso: Path, modulo: str, persi: set,
                  moduli: Moduli) -> list:
    """Chi usa ancora i nomi che il modulo ha perso: [(rel, riga, nome)].

    Si leggono tutti i .py del repository, ma si analizzano solo quelli in
    cui il nome compare almeno come parola: e' raro che un modulo perda un
    nome, e anche allora i file da guardare davvero sono pochi. Come parola e
    non come testo qualsiasi, perche' un nome corto - la G di config, la
    gravita' - come lettera sta in ogni file.
    """
    usi = []
    parola = re.compile(r"(?<![\w])(?:" + "|".join(re.escape(p) for p in sorted(persi))
                        + r")(?![\w])")
    # e chi usa il modulo ne scrive il nome: `from .. import config as C`,
    # `from .weekend import X`, `from ..sim import pace`. Un import tolto per
    # pulizia (math, Path) come parola c'e' in mezzo gioco, insieme a questo no
    modulo_come_parola = re.compile(r"(?<![\w])" + re.escape(modulo.rsplit(".", 1)[-1])
                                    + r"(?![\w])")
    for f in file_python(radice):
        if f == percorso:
            continue
        try:
            testo = f.read_text(encoding=SORGENTE)
        except (OSError, UnicodeDecodeError):
            continue
        if not parola.search(testo) or not modulo_come_parola.search(testo):
            continue
        try:
            albero = ast.parse(testo)
        except (SyntaxError, ValueError):
            continue
        rel = f.relative_to(radice)
        mod_f, pac_f = nome_modulo(rel)
        for n in ast.walk(albero):
            if isinstance(n, ast.ImportFrom) and risolvi(mod_f, pac_f, n) == modulo:
                usi.extend((rel.as_posix(), n.lineno, a.name) for a in n.names if a.name in persi)
        legami = legami_moduli(albero, mod_f, pac_f, moduli)
        for n in ast.walk(albero):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and legami.get(n.value.id) == modulo and n.attr in persi):
                usi.append((rel.as_posix(), n.lineno, n.attr))
    return sorted(set(usi))


# ---------------------------------------------------------- pyflakes / ruff
def problemi_pyflakes(testo: str, albero: ast.Module, rel: str, radice: Path) -> list | None:
    """[(chiave, riga, messaggio, solo_avviso)], o None se non c'e' ne' ruff ne' pyflakes.

    Ruff prima, se c'e': e' lo stesso controllo, in un processo che parte in
    pochi millesimi. Se no pyflakes, dentro a questo stesso processo. Se
    mancano tutti e due il controllo si salta e basta.
    """
    comando = None
    ruff = shutil.which("ruff")
    if ruff:
        comando = [ruff]
    elif importlib.util.find_spec("ruff") is not None:
        comando = [sys.executable, "-m", "ruff"]
    if comando:
        try:
            r = subprocess.run(comando + ["check", "--select", "F", "--output-format", "json",
                                          "--no-cache", "--exit-zero", "--stdin-filename", rel,
                                          "-"],
                               input=testo, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(radice), timeout=20,
                               creationflags=SENZA_FINESTRA)
            uscita = []
            for d in json.loads(r.stdout or "[]"):
                codice = d.get("code") or "?"
                chiave = (codice, RIGA_NEL_MESSAGGIO.sub("line N", d.get("message", "")))
                uscita.append((chiave, d["location"]["row"],
                               f"{codice} {d.get('message', '')}", codice in AVVISI_RUFF))
            return uscita
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            pass                          # un ruff rotto non e' un motivo per non controllare
    try:
        from pyflakes import checker
    except ImportError:
        return None
    try:
        w = checker.Checker(albero, filename=rel)
    except Exception:
        return None
    uscita = []
    for m in w.messages:
        tipo = type(m).__name__
        testo_m = m.message % m.message_args
        uscita.append(((tipo, RIGA_NEL_MESSAGGIO.sub("line N", testo_m)), m.lineno, testo_m,
                       tipo in AVVISI_PYFLAKES))
    return uscita


# ------------------------------------------------------------ eseguibile
def esclusi_da_spec(radice: Path) -> list:
    """I moduli che apex.spec tiene fuori dall'eseguibile (excludes=[...] di Analysis)."""
    spec = radice / "apex.spec"
    try:
        albero = ast.parse(spec.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return []
    for n in ast.walk(albero):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Analysis":
            for k in n.keywords:
                if k.arg == "excludes" and isinstance(k.value, (ast.List, ast.Tuple)):
                    return [e.value for e in k.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _cattura_import(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    tipi = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(getattr(t, "id", getattr(t, "attr", "")) in GUARDIE for t in tipi)


def import_esterni(albero: ast.Module) -> list:
    """Ogni modulo assoluto importato, con la riga e se un try lo protegge."""
    trovati = []

    def visita(nodo, protetto: bool) -> None:
        for figlio in ast.iter_child_nodes(nodo):
            p = protetto
            if isinstance(nodo, ast.Try) or type(nodo).__name__ == "TryStar":
                # solo il corpo del try e' protetto, non gli except ne' il finally
                if figlio in nodo.body and any(_cattura_import(h) for h in nodo.handlers):
                    p = True
            if isinstance(figlio, ast.Import):
                trovati.extend((a.name, figlio.lineno, p) for a in figlio.names)
            elif isinstance(figlio, ast.ImportFrom) and not figlio.level and figlio.module:
                trovati.append((figlio.module, figlio.lineno, p))
                trovati.extend((f"{figlio.module}.{a.name}", figlio.lineno, p)
                               for a in figlio.names if a.name != "*")
            visita(figlio, p)

    visita(albero, False)
    return trovati


def fuori_dall_exe(albero: ast.Module, esclusi: list) -> list:
    """[(modulo, riga, protetto, escluso)] per gli import che apex.spec esclude."""
    uscita, visti = [], set()
    for nome, riga, protetto in import_esterni(albero):
        for e in esclusi:
            if nome == e or nome.startswith(e + "."):
                # `from direct.filter.X import Y` da' due nomi esclusi: basta il primo
                if (riga, e) not in visti:
                    visti.add((riga, e))
                    uscita.append((nome, riga, protetto, e))
                break
    return uscita


# ---------------------------------------------------------- avvisi di casa
TOKEN_STRINGA = {tokenize.STRING} | {getattr(tokenize, n) for n in
                                     ("FSTRING_MIDDLE", "TSTRING_MIDDLE") if hasattr(tokenize, n)}


def accentata(ch: str) -> bool:
    return ord(ch) > 127 and any(unicodedata.combining(c)
                                 for c in unicodedata.normalize("NFD", ch))


def stringhe_accentate(testo: str) -> list:
    """[(riga, stringa)] per le stringhe che nel sorgente hanno lettere accentate.

    Si guarda il sorgente, non il valore: "pi\\u00f9" e' scritto come vuole
    la casa anche se il valore ha la u accentata.
    """
    uscita = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(testo).readline):
            if tok.type in TOKEN_STRINGA and any(accentata(c) for c in tok.string):
                uscita.append((tok.start[0], tok.string))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    return uscita


def moduli_taratura(testo_taratura: str | None) -> tuple | None:
    """La tupla _MODULI di core/taratura.py: i file del modello del giro."""
    if not testo_taratura:
        return None
    try:
        albero = ast.parse(testo_taratura)
    except (SyntaxError, ValueError):
        return None
    for n in albero.body:
        if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_MODULI" for t in n.targets)
                and isinstance(n.value, (ast.Tuple, ast.List))):
            return tuple(e.value for e in n.value.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return None


def dipendenze_sim_model(testo: str, rel: str) -> set:
    """I moduli di game/sim e game/model che un file importa, come "sim/x.py"."""
    try:
        albero = ast.parse(testo)
    except (SyntaxError, ValueError):
        return set()
    modulo, pacchetto = nome_modulo(Path(rel))
    uscita = set()
    for n in ast.walk(albero):
        nomi = []
        if isinstance(n, ast.ImportFrom):
            base = risolvi(modulo, pacchetto, n)
            if base:
                nomi = [base] + [f"{base}.{a.name}" for a in n.names]
        elif isinstance(n, ast.Import):
            nomi = [a.name for a in n.names]
        for nome in nomi:
            parti = nome.split(".")
            if len(parti) == 3 and parti[0] == "game" and parti[1] in ("sim", "model"):
                uscita.add(f"{parti[1]}/{parti[2]}.py")
    return uscita


def scoperti_dalla_taratura(testi: dict, radice: Path) -> set:
    """I moduli di sim/ e model/ che un modulo di _MODULI importa ma che _MODULI non ha.

    `testi` ha il sorgente di core/taratura.py e quello dei moduli che elenca,
    tutti dalla stessa versione (il disco o HEAD). Contano solo i moduli che
    sul disco ci sono: un import di un file che non esiste e' un altro errore,
    e lo dice gia' il controllo dei nomi.
    """
    elenco = moduli_taratura(testi.get("game/core/taratura.py"))
    if not elenco:
        return set()
    usati = set()
    for m in elenco:
        testo = testi.get(f"game/{m}")
        if testo:
            usati |= dipendenze_sim_model(testo, f"game/{m}")
    return {m for m in usati - set(elenco) if (radice / "game" / m).is_file()}


# ------------------------------------------------------------ il controllo
def controlla(percorso: Path) -> tuple:
    """(errori, avvisi, rel) per il file appena scritto."""
    errori: list = []
    avvisi: list = []
    radice = trova_radice(percorso)
    rel = percorso.relative_to(radice) if radice else Path(percorso.name)
    rel_posix = rel.as_posix()

    if percorso.suffix.lower() == ".json":
        if radice and rel.parts and rel.parts[0] == "data":
            try:
                # come lo legge il gioco: utf-8, e un BOM in testa e' un errore anche li'
                json.loads(percorso.read_text(encoding="utf-8"))
            except UnicodeDecodeError as e:
                errori.append(f"non e' utf-8: {e}")
            except ValueError as e:
                errori.append(f"il json non si legge: {e}")
        return errori, avvisi, rel_posix

    try:
        testo = percorso.read_text(encoding=SORGENTE)
    except UnicodeDecodeError as e:
        return [f"non e' utf-8: {e}"], [], rel_posix
    # a) si compila?
    try:
        albero = ast.parse(testo, filename=str(percorso))
        compile(albero, str(percorso), "exec")
    except SyntaxError as e:
        dove = f"riga {e.lineno}" + (f", colonna {e.offset}" if e.offset else "")
        return [f"{dove}: {type(e).__name__}: {e.msg}"], [], rel_posix
    except ValueError as e:
        return [f"non si compila: {e}"], [], rel_posix
    if radice is None:
        return errori, avvisi, rel_posix  # fuori da un repository: basta che si compili

    in_gioco = bool(rel.parts) and rel.parts[0] == "game"
    nell_exe = in_gioco or rel_posix == "main.py"
    modulo, pacchetto = nome_modulo(rel)

    # il file com'era in HEAD, e - se il file e' del modello del giro - anche
    # taratura.py e i moduli che elenca: un solo processo git per tutti
    da_leggere = [rel_posix]
    taratura_in_gioco = in_gioco and (rel.parts[1:2] in (("sim",), ("model",))
                                      or rel_posix in ("game/config.py", "game/core/taratura.py"))
    elenco_ora = None
    if taratura_in_gioco:
        try:
            testo_tar = (radice / "game/core/taratura.py").read_text(encoding=SORGENTE)
        except (OSError, UnicodeDecodeError):
            testo_tar = None
        elenco_ora = moduli_taratura(testo_tar)
        if elenco_ora:
            da_leggere += ["game/core/taratura.py"] + [f"game/{m}" for m in elenco_ora]
    head = leggi_da_head(radice, sorted(set(da_leggere)))
    testo_head = head.get(rel_posix)
    albero_head = None
    if testo_head is not None:
        try:
            albero_head = ast.parse(testo_head)
        except (SyntaxError, ValueError):
            albero_head = None

    # b) pyflakes, solo il nuovo rispetto a HEAD
    ora = problemi_pyflakes(testo, albero, rel_posix, radice)
    if ora is not None:
        prima = Counter()
        if albero_head is not None:
            prima = Counter(k for k, *_ in (problemi_pyflakes(testo_head, albero_head, rel_posix,
                                                              radice) or []))
        adesso = Counter(k for k, *_ in ora)
        nuove = {k for k in adesso if adesso[k] > prima[k]}
        # un problema per riga di messaggio, con tutte le sue righe: trenta
        # "math non definito" uno sotto l'altro nasconderebbero il resto
        gruppi: dict = {}
        for chiave, riga, msg, avviso in ora:
            if chiave in nuove:
                gruppi.setdefault(chiave, (msg, avviso, []))[2].append(riga)
        for msg, avviso, righe in sorted(gruppi.values(), key=lambda g: min(g[2])):
            dove = f"riga {righe[0]}" if len(set(righe)) == 1 else f"righe {elenca(righe)}"
            (avvisi if avviso else errori).append(f"{dove}: {msg}")

    # c) i nomi presi da altri moduli del gioco, e chi usa quelli persi
    moduli = Moduli(radice)
    for riga, msg in nomi_mancanti(albero, modulo, pacchetto, moduli):
        errori.append(f"riga {riga}: {msg}")
    if moduli.locale(modulo) and albero_head is not None:
        prima_n, dopo_n = nomi_definiti(albero_head), moduli.nomi(modulo)
        if prima_n is not None and dopo_n is not None:
            persi = {n for n in prima_n - dopo_n if moduli.file(f"{modulo}.{n}") is None}
            if persi:
                usi = usi_dei_persi(radice, percorso, modulo, persi, moduli)
                for nome in sorted({u[2] for u in usi}):
                    # un file per voce, con le sue righe: con trenta usi in nove
                    # file, un elenco di righe nude taglierebbe proprio i file
                    per_file: dict = {}
                    for r, n, x in usi:
                        if x == nome:
                            per_file.setdefault(r, []).append(n)
                    dove = [f"{r} (righe {elenca(n)})" for r, n in sorted(per_file.items())]
                    errori.append(f"`{nome}` non c'e' piu' in {modulo}, ma lo usano ancora "
                                  f"{len(per_file)} file: " + "; ".join(dove[:MASSIMO]))

    # d) import che l'eseguibile non avrebbe
    if nell_exe:
        esclusi = esclusi_da_spec(radice)
        if esclusi:
            gia = set()
            if albero_head is not None:
                gia = {(e, p) for _, _, p, e in fuori_dall_exe(albero_head, esclusi)}
            for nome, riga, protetto, e in fuori_dall_exe(albero, esclusi):
                if (e, protetto) in gia:
                    continue
                if protetto:
                    avvisi.append(f"riga {riga}: `{nome}` e' escluso da apex.spec ('{e}'): "
                                  "nell'eseguibile Windows l'import fallira' e si passera' "
                                  "per l'except")
                else:
                    errori.append(f"riga {riga}: `{nome}` e' escluso da apex.spec ('{e}'): "
                                  "dai sorgenti funziona, nell'eseguibile Windows no")

    # f) le due attenzioni di casa
    if in_gioco:
        gia = Counter(s for _, s in stringhe_accentate(testo_head or ""))
        for riga, s in stringhe_accentate(testo):
            if gia[s] > 0:
                gia[s] -= 1
                continue
            corta = s if len(s) <= 60 else s[:57] + "..."
            avvisi.append(f"riga {riga}: lettere accentate in una stringa ({corta}): la casa "
                          "scrive piu' e perche' con l'apostrofo, o con un escape \\u00e8")
    if taratura_in_gioco and elenco_ora:
        testi_ora = {}
        for p in ["game/core/taratura.py"] + [f"game/{m}" for m in elenco_ora]:
            try:
                testi_ora[p] = (radice / p).read_text(encoding=SORGENTE)
            except (OSError, UnicodeDecodeError):
                pass
        nuovi = (scoperti_dalla_taratura(testi_ora, radice)
                 - scoperti_dalla_taratura(head, radice))
        for m in sorted(nuovi):
            avvisi.append(f"game/{m} serve al modello del giro (lo importa un modulo di _MODULI) "
                          "ma non e' in _MODULI di game/core/taratura.py: cambiandolo, le "
                          "tarature in cache non si rifarebbero")
    return errori, avvisi, rel_posix


def messaggio(rel: str, errori: list, avvisi: list) -> str:
    righe = []
    if errori:
        righe.append(f"Controllo di {rel} dopo la modifica: {len(errori)} "
                     f"{'problema' if len(errori) == 1 else 'problemi'} da correggere.")
        righe += [f"- {e}" for e in errori[:MASSIMO]]
        if len(errori) > MASSIMO:
            righe.append(f"- ... e altri {len(errori) - MASSIMO}")
    if avvisi:
        righe.append(f"Avvisi per {rel} (non bloccano, ma vanno guardati):" if errori else
                     f"Controllo di {rel} dopo la modifica: niente errori, solo avvisi.")
        righe += [f"- {a}" for a in avvisi[:MASSIMO]]
        if len(avvisi) > MASSIMO:
            righe.append(f"- ... e altri {len(avvisi) - MASSIMO}")
    return "\n".join(righe)


def main() -> int:
    try:
        # Claude Code manda utf-8; su Windows sys.stdin decodificherebbe con
        # la codepage della console e sbaglierebbe i percorsi con gli accenti
        ingresso = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    except ValueError:
        return 0
    voce = ingresso.get("tool_input") or {}
    nome = voce.get("file_path") or (ingresso.get("tool_response") or {}).get("filePath")
    if not nome:
        return 0
    percorso = Path(nome)
    if percorso.suffix.lower() not in (".py", ".json") or not percorso.is_file():
        return 0
    errori, avvisi, rel = controlla(percorso)
    if not errori and not avvisi:
        return 0
    testo = messaggio(rel, errori, avvisi)
    if errori:
        uscita = {"decision": "block", "reason": testo}
    else:
        uscita = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                         "additionalContext": testo}}
    # solo ASCII su stdout: su Windows la codepage della console non e' utf-8
    sys.stdout.write(json.dumps(uscita, ensure_ascii=True) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:               # un difetto del controllo, non del file
        sys.stderr.write(f"controlla_py: errore interno ({type(ex).__name__}: {ex})\n")
        sys.exit(1)
