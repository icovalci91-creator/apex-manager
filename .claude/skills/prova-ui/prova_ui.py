"""Prova senza schermo dell'interfaccia: ogni pagina, in piu' stati, a piu' scale.

Il crash peggiore finora (commit dada758, "Formula E: niente crash scegliendo i
piloti") succedeva solo su Windows. Un pilota caro riempiva il tetto di spesa,
il cursore degli ingegneri divideva per quasi zero e chiedeva una barra larga
miliardi di pixel. Su Windows pygame la rifiuta - un long di C li' e' a 32 bit
- e il gioco si ferma con "Argument must be rect style object". Su Linux il
long e' a 64 bit e pygame.Rect tronca in silenzio (5e9 diventa 705032704): non
si vede niente, e una prova fatta li' passa tranquilla.

Qui si fa il contrario: si mette una guardia nei punti da cui passa tutto
quello che si disegna - pygame.Rect (fatto, spostato, allargato o cambiato),
la tela HD che porta i numeri logici a quelli veri, le funzioni di disegno
vere di pygame, la posizione delle scritte - e un numero che non sta in 32
bit diventa un errore anche su Linux, con il punto del codice che l'ha
prodotto. Poi si ricrea lo stato che aveva rotto il gioco
(Formula E ed endurance aperti, i piloti piu' cari, tutti gli ingegneri, la
spesa oltre il tetto) e si apre ogni pagina di NAV in tre stati - appena
aperta, con la prima voce scelta, scorsa fino in fondo - piu' le sue schede
interne, alle due misure di finestra del gioco e alle scale HD 1.0, 1.5 e 2.0.

Dopo ogni vista ogni cursore della pagina si ridisegna col massimo crollato
sotto al valore, che e' quello che succede quando i soldi finiscono: cosi' un
cursore che torna a non tenere la barra dentro si vede su qualunque pagina, e
non solo su quella di Formula E il giorno che qualcuno ci prende un pilota caro.

Uso (da qualunque cartella):
    python .claude/skills/prova-ui/prova_ui.py
    python .claude/skills/prova-ui/prova_ui.py --only formulae wec --scale 2.0 --foto

Esce con 0 se tutto si e' aperto, con 1 se qualcosa si e' rotto (righe ROTTA),
con 2 se la prova stessa non e' riuscita a partire.
"""
from __future__ import annotations

import argparse
import copy
import numbers
import os
import re
import sys
import time
import traceback
from pathlib import Path

# prima di importare pygame: niente finestra vera e niente scheda audio. Si
# impone, non si suggerisce: se chi lancia ha un driver video impostato, la
# prova aprirebbe una finestra in faccia a chi sta lavorando
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

STATI = ("aperta", "prima-voce", "in-fondo")
SCALE = (1.0, 1.5, 2.0)
SEME = 7                 # lo stato estremo e' sempre lo stesso, da una prova all'altra
LIMITE = 2 ** 31         # un long di C su Windows: da -2**31 a 2**31 - 1
MAX_RIGHE = 25           # oltre, le righe ROTTA delle viste si contano e basta
MAX_CURSORI = 10         # e quelle dei cursori al limite, che vengono in serie


def _radice() -> Path:
    """La cartella del gioco: la prima, salendo da questo file, che ha dentro
    game/ui/hd.py e main.py. Cosi' la prova funziona anche in una copia del
    repository, o lanciata da un'altra cartella."""
    qui = Path(__file__).resolve().parent
    for p in (qui, *qui.parents):
        if (p / "game" / "ui" / "hd.py").is_file() and (p / "main.py").is_file():
            return p
    raise SystemExit(f"prova_ui: non trovo la cartella del gioco sopra {qui}")


RADICE = _radice()
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))


# ------------------------------------------------------------------ la guardia
class Oltre32Bit(TypeError):
    """Lo stesso errore che pygame da' su Windows, ma anche qui."""


# I numeri oltre i 32 bit trovati, con la pila di chiamate: si segnano anche
# quando l'errore lo inghiotte un try del gioco, perche' su Windows quel
# disegno salterebbe lo stesso
_COLPI: list = []
_RECT_VERO = None
_SALTA: tuple = ()       # quello che non si guarda dentro: Rect veri e colori


def _numeri(x, giro: int = 0):
    """Tutti i numeri dentro a un argomento di disegno: un numero, una coppia,
    un rettangolo scritto come tupla, una lista di punti."""
    if isinstance(x, (bool, str, bytes)):
        return
    if isinstance(x, numbers.Real):
        yield float(x)
        return
    # un Rect vero ha gia' i suoi numeri a 32 bit, e un colore non e' una misura
    if giro >= 3 or x is None or isinstance(x, _SALTA):
        return
    if hasattr(x, "__len__") and hasattr(x, "__getitem__"):
        try:
            for v in x:
                yield from _numeri(v, giro + 1)
        except TypeError:
            return


def _controlla(valori, scala: float = 1.0, somme: bool = False) -> None:
    nums = list(_numeri(valori))
    if somme and len(nums) == 4:
        # (x, y, w, h): anche il bordo destro e quello in basso devono starci
        nums += [nums[0] + nums[2], nums[1] + nums[3]]
    for v in nums:
        w = v * scala
        # scritto cosi' cattura anche nan e inf, che non stanno da nessuna parte
        if not (-LIMITE <= w < LIMITE):
            _COLPI.append((w, traceback.extract_stack()[:-2]))
            raise Oltre32Bit(f"Argument must be rect style object (prova_ui: {w:.4g} "
                             f"non sta in 32 bit)")


def installa_guardia(hd) -> None:
    """Mette la guardia nei punti da cui passa tutto il disegno.

    pygame.Rect, perche' e' li' che Windows rifiuta il numero: una pagina che
    si costruisce da se' un rettangolo largo miliardi, o che lo allarga dopo,
    su Linux non se ne accorge. La tela HD (rett, punto, v), perche' e' li'
    che un numero logico ancora buono diventa, moltiplicato per la scala, uno
    che non ci sta: a 1.0 passa, a 2.0 no. Le funzioni di disegno vere,
    quelle che hd.installa ha messo da parte in hd._ORIG, che ricevono i
    numeri finali anche quando si disegna su una superficie qualunque e non
    sulla tela. E la posizione delle scritte, all'ingresso di T.text."""
    global _RECT_VERO, _SALTA
    import pygame
    hd.installa()
    _RECT_VERO = pygame.Rect
    _SALTA = (pygame.Rect, pygame.Color)

    class _Rettangolo(type):
        # chi chiede isinstance(r, pygame.Rect) con un Rect fatto da pygame
        # stesso (get_rect, move, clip...) deve continuare a sentirsi dire si'
        def __instancecheck__(cls, x):
            return isinstance(x, _RECT_VERO)

        def __subclasscheck__(cls, c):
            return issubclass(c, _RECT_VERO)

    # Non basta guardare la costruzione: su Windows anche `r.w = ...`,
    # `r.topleft = ...`, `r.move(...)` e `r.inflate(...)` passano dallo stesso
    # long di C e rifiutano il numero ("invalid rect assignment"), mentre su
    # Linux lo troncano. Una barra fatta con `barra.w = int(r.w * f)` o una
    # scritta messa in fondo a una barra impazzita (T.text fa `r.topleft = pos`)
    # si rompono da li', e senza questi controlli qui passerebbero. I Rect che
    # nascono da questi (move, copy, clip...) restano di questa classe, quindi
    # sono guardati anche loro
    class RectGuardato(_RECT_VERO, metaclass=_Rettangolo):
        __slots__ = ()

        def __init__(self, *a):
            _controlla(a, somme=True)
            super().__init__(*a)

        def __setattr__(self, nome, valore):
            _controlla(valore)
            super().__setattr__(nome, valore)

        def __setitem__(self, i, valore):
            _controlla(valore)
            super().__setitem__(i, valore)

        def update(self, *a):
            _controlla(a, somme=True)
            return super().update(*a)

        def move(self, *a):
            _controlla(a)
            return super().move(*a)

        def move_ip(self, *a):
            _controlla(a)
            return super().move_ip(*a)

        def inflate(self, *a):
            _controlla(a)
            return super().inflate(*a)

        def inflate_ip(self, *a):
            _controlla(a)
            return super().inflate_ip(*a)

    pygame.Rect = RectGuardato

    # Le scritte: a scala 1.0 il rettangolo di una scritta lo fa pygame stesso
    # (get_rect di una superficie normale) e non passa da RectGuardato, quindi
    # la posizione si guarda all'ingresso di T.text, da cui passano tutte
    from game.ui import theme as T
    testo = T.text

    def testo_guardato(surf, s, pos, *a, **k):
        _controlla(pos)
        return testo(surf, s, pos, *a, **k)

    T.text = testo_guardato

    Tela = hd.Tela
    rett, punto, v = Tela.rett, Tela.punto, Tela.v

    def rett_guardata(self, r):
        _controlla(r, self.S, somme=True)
        return rett(self, r)

    def punto_guardato(self, p):
        _controlla(p, self.S)
        return punto(self, p)

    def v_guardato(self, x):
        _controlla(x, self.S)
        return v(self, x)

    Tela.rett, Tela.punto, Tela.v = rett_guardata, punto_guardato, v_guardato

    def guarda(vera):
        def guardata(surface, color, *a, **k):
            _controlla(a)
            _controlla(list(k.values()))
            return vera(surface, color, *a, **k)
        return guardata

    for nome in list(hd._ORIG):
        if nome != "get_pos":
            hd._ORIG[nome] = guarda(hd._ORIG[nome])


# ---------------------------------------------------- dove e' nato il guaio
def _dove(pila) -> list:
    """Le righe del gioco da cui e' partito il guaio, dalla piu' vicina: le
    tre piu' interne fuori da hd.py, che e' solo il tramite. Le righe di
    questa prova non contano."""
    righe, tramite = [], []
    for f in reversed(pila):
        try:
            rel = Path(f.filename).resolve().relative_to(RADICE).as_posix()
        except (ValueError, OSError):
            continue
        if not rel.startswith("game/"):
            continue
        riga = f"{rel}:{f.lineno} in {f.name}"
        if not righe and f.line:
            riga += f": {f.line.strip()}"
        if rel == "game/ui/hd.py":
            tramite.append(riga)
            continue
        righe.append(riga)
        if len(righe) == 3:
            break
    return righe or tramite[:1]


def _fmt_scala(s: float) -> str:
    t = f"{s:.2f}".rstrip("0")
    return t + "0" if t.endswith(".") else t


# ------------------------------------------------------- lo stato estremo
def stato_estremo():
    """La partita che aveva rotto il gioco, e un po' di piu'.

    Formula E ed endurance aperti, i due piloti di Formula E piu' cari del
    mercato messi in macchina senza chiedere al tetto, tutti gli ingegneri che
    il regolamento permette, il budget sviluppo oltre quello che ci sta: il
    tetto della Formula E e' sfondato, e il massimo degli ingegneri crolla al
    minimo mentre se ne hanno il massimo. In piu' la Formula 1 oltre il suo
    tetto di spesa e le giornate di test finite, che lasciano il cursore delle
    giornate senza intervallo."""
    from game.core import economy
    from game.core import formulae as FE
    from game.core import testing as TT
    from game.core import wec as WEC
    from game.core.state import GameState, _load

    squadra = _load("teams.json")["teams"][0]["id"]
    gs = GameState.new_game(squadra, True, seed=SEME)
    team = gs.player
    team.cash = 900.0        # abbastanza per aprire tutto
    msg = FE.apri(gs, team, f"{team.short} Formula E")
    if not FE.ha(team):
        raise RuntimeError(f"la Formula E non si apre: {msg}")
    cara = max(WEC.classi(), key=lambda cl: WEC.costo_ingresso(team, cl))
    msg = WEC.apri(gs, team, f"{team.short} Endurance", cara)
    if not WEC.ha(team):
        raise RuntimeError(f"l'endurance non si apre: {msg}")

    # i piloti piu' cari, messi li' come li metteva il gioco prima della
    # correzione: il tetto se ne accorge dopo
    cari = sorted(FE.mercato(gs), key=lambda d: -d.salary)[:2]
    team.fe_piloti = [d.id for d in cari] + [""] * (2 - len(cari))
    for d in cari:
        d.team = team.id
        d.contract_until = gs.season + 2
    team.fe_ingegneri = FE.INGEGNERI_MAX
    team.wec_ingegneri = WEC.ingegneri_massimi(team)
    team.wec_dev_budget = WEC.dev_budget_massimo(team)
    gare = max(1, int(FE.corrente().get("gare", 21)))
    senza_dev = FE.spesa_nel_tetto(gs, team) - FE.dev_budget(team) * gare
    team.fe_dev_budget = round(max(0.0, (FE.tetto(gs) - senza_dev) / gare) + 0.5, 2)
    if FE.dentro_il_tetto(gs, team)[0] or FE.ingegneri_massimi(gs, team) > FE.INGEGNERI_MIN:
        raise RuntimeError("il tetto della Formula E non si sfonda: lo stato estremo "
                           "non e' piu' quello del crash, va rivisto")

    spesi, limite, _quota = economy.cap_usage(gs, team)
    team.add_expense("Prova dell'interfaccia: spesa oltre il tetto",
                     max(1.0, limite * 1.15 - spesi), in_cap=True, category="altro")
    team.cash = max(team.cash, 25.0)
    team.test_days_used = TT.days_allowed(gs, team)
    return gs


# ------------------------------------------------------------------ la prova
class Prova:
    def __init__(self, foto: Path | None):
        import pygame

        from game import storage
        from game.ui import audio, hd

        # le impostazioni di chi gioca non si toccano: niente si legge da
        # video.json e audio.json e niente ci si scrive, e un salvataggio
        # chiesto per sbaglio resta in memoria
        hd.carica = lambda: None
        hd.salva = lambda: None
        audio.salva = lambda: None
        audio.avvia = lambda: None     # il suono non serve, e prepararlo costa un secondo
        storage.write_save = lambda name, data: "(non salvato: prova_ui)"

        pygame.init()
        installa_guardia(hd)
        from game.ui import widgets as W
        from game.ui.app import App
        self.pygame, self.hd, self.W = pygame, hd, W
        self.app = App()               # il vero, con la finestra finta di SDL
        self.foto = foto
        self.viste = 0
        self.cursori = 0
        self.rotte: list = []          # (etichetta, causa, righe di dove)
        self.cause: dict = {}          # (tipo, dove) -> [volte, causa, righe, pagine, tipo]
        self.stampate = {"vista": 0, "cursori": 0}

    # --- una vista: un'azione e il disegno, come nel ciclo del gioco
    def vista(self, etichetta: str, shell, azione=None) -> None:
        prima = len(_COLPI)
        errore = None
        try:
            if azione is not None:
                azione()
            self._disegna(shell, 2 if self.foto else 1)
        except Exception as exc:       # qualunque errore e' una pagina rotta
            errore = exc
            self._ripulisci()
        self.viste += 1
        self._esito(etichetta, prima, errore)
        if self.foto is not None:
            nome = etichetta.replace(" ", "_") + ".png"
            try:
                self.pygame.image.save(self.app.screen, str(self.foto / nome))
            except Exception:
                pass

    def _disegna(self, shell, volte: int) -> None:
        from game.ui import fx
        from game.ui import theme as T
        app = self.app
        for _ in range(volte):
            # un secondo di animazioni gia' passato: la dissolvenza e il nome
            # che entra da sinistra sono finiti, la foto e' quella da fermi
            for _t in range(4):
                fx.tick(0.25)
            shell.entrata = 0.0
            scena = app.scene
            scena.update(1 / 60)
            T.sfondo(app.screen)
            scena.draw(app.screen)
            if app.toast_t > 0:
                app._draw_toast()

    def _ripulisci(self) -> None:
        """Dopo un errore a meta' disegno: niente ritaglio rimasto appeso."""
        from game.ui import theme as T
        try:
            self.pygame.Surface.set_clip(self.app.screen, None)
            T.ink_stop()
        except Exception:
            pass

    def _esito(self, etichetta: str, prima: int, errore, cosa: str = "") -> None:
        if len(_COLPI) > prima:
            valore, pila = _COLPI[prima]
            causa = f"pygame.Rect con un numero oltre i 32 bit ({valore:.4g})"
            if not isinstance(errore, Oltre32Bit):
                causa += ", e l'errore l'ha inghiottito un try del gioco"
            dove = _dove(pila)
        elif errore is not None:
            testo = str(errore).strip().splitlines()
            causa = f"{type(errore).__name__}: {testo[0][:200] if testo else ''}"
            dove = _dove(traceback.extract_tb(errore.__traceback__))
        else:
            return
        self.rotte.append((etichetta, cosa + causa, dove))
        # le cause si raccolgono per riga di codice, tenendo separate le viste
        # vere da quelle coi cursori forzati: una pagina che si rompe da sola
        # e' la notizia, e non deve sparire in mezzo alle altre
        tipo = "cursori" if cosa else "vista"
        chiave = (tipo, dove[0].split(": ", 1)[0] if dove else causa)
        nuova = chiave not in self.cause
        voce = self.cause.setdefault(chiave, [0, causa, dove, [], tipo])
        voce[0] += 1
        pid = etichetta.split(" ", 1)[0]
        if pid not in voce[3]:
            voce[3].append(pid)
        # le righe stampate si contano a parte: un cursore che cede lo fa su
        # tante pagine in fila, e la Formula E sta in fondo a NAV. Con un conto
        # solo, le sue viste rotte - il crash vero - finivano oltre il tetto
        n = self.stampate[tipo] = self.stampate[tipo] + 1
        tetto = MAX_RIGHE if tipo == "vista" else MAX_CURSORI
        if n <= tetto:
            print(f"ROTTA {etichetta}: {cosa}{causa}")
            # dove e' nato si scrive la prima volta: dopo e' sempre quello
            for i, riga in enumerate(dove if nuova else []):
                print(f"    {'in' if i == 0 else 'da'} {riga}")
        elif n == tetto + 1:
            quali = "delle viste" if tipo == "vista" else "coi cursori al limite"
            print(f"... altre righe ROTTA {quali}: si contano nel riassunto")

    # --- ogni cursore col massimo crollato
    def cursori_al_limite(self, etichetta: str, pagina) -> None:
        """Ogni cursore della pagina, ridisegnato col massimo sceso al minimo
        mentre il valore resta in cima, e poi col massimo sotto il minimo: e'
        quello che succede quando un pilota caro riempie il tetto o i soldi
        finiscono. La barra deve restare fra vuota e piena."""
        prima = len(_COLPI)
        errore, cosa = None, ""
        tela = self.app.screen
        for w in list(pagina.widgets):
            if not isinstance(w, self.W.Slider) or not w.visible:
                continue
            self.cursori += 1
            salvati = (w.lo, w.hi, w.value, w.marker)
            try:
                arco = abs(w.hi - w.lo) or 1.0
                for hi in (w.lo, w.lo - arco):
                    w.hi, w.value, w.marker = hi, w.lo + arco, w.lo + arco
                    self.pygame.Surface.set_clip(tela, None)
                    w.draw(tela)
            except Exception as exc:   # il primo che cede basta
                errore = exc
                cosa = f"cursore '{w.label}' col massimo sotto il valore: "
                self._ripulisci()
                break
            finally:
                w.lo, w.hi, w.value, w.marker = salvati
        self._esito(etichetta, prima, errore, cosa)

    # --- tutte le pagine, a una misura e a una scala
    def giro(self, gs, ris: tuple, scala: float, pagine: list) -> None:
        from game.ui import fx
        from game.ui.scenes.shell import GameShell
        hd, app, W = self.hd, self.app, self.W
        tela = hd.Tela(ris, scala)
        app.screen = tela
        hd._TELA_ATTUALE[0] = tela
        app.scenes = []
        app.gs = copy.deepcopy(gs)     # quello che una pagina cambia resta qui
        app.toast_t = 0.0
        fx.entra()
        shell = GameShell(app)
        app.scenes.append(shell)
        shell.enter()
        misura = f"{ris[0]}x{ris[1]} {_fmt_scala(scala)}"

        def liste(p):
            return [w for w in p.widgets if isinstance(w, W.ScrollList)]

        for pid in pagine:
            def pagina(pid=pid):
                return shell.pages[pid]

            def apri(pid=pid):
                shell.go(pid)

            def prima_voce():
                # la prima riga di ogni lista, come un clic: scegliere puo'
                # ricostruire la pagina, quindi le liste si ricontano ogni volta
                for i in range(len(liste(pagina()))):
                    ls = liste(pagina())
                    if i >= len(ls) or not ls[i].items or not ls[i].visible:
                        continue
                    ls[i].selected = 0
                    if ls[i].on_select:
                        ls[i].on_select(0, ls[i].items[0])

            def in_fondo():
                p = pagina()
                p.set_scroll(p.scroll_max)
                for ls in liste(p):
                    ls.offset = ls.max_offset
                if shell.rail is not None:
                    shell.rail.offset = shell.rail.max_offset

            passi = list(zip(STATI, (apri, prima_voce, in_fondo)))
            for stato, azione in passi:
                self.vista(f"{pid} {stato} {misura}", shell, azione)
                self.cursori_al_limite(f"{pid} {stato}:cursori {misura}", pagina())
                self._torna(shell)

            # le schede interne (Formula E: il programma, i piloti, il mondiale):
            # la prima e' gia' "aperta", le altre si guardano una per una
            try:
                schede = [w for w in pagina().widgets if isinstance(w, W.Tabs)]
                quante = len(schede[0].buttons) if schede else 0
            except Exception:
                quante = 0
            for i in range(1, quante):
                def scheda(i=i):
                    p = pagina()
                    p.set_scroll(0)
                    t = [w for w in p.widgets if isinstance(w, W.Tabs)]
                    if t:
                        t[0].select(i)
                stato = f"scheda{i + 1}"
                self.vista(f"{pid} {stato} {misura}", shell, scheda)
                self.cursori_al_limite(f"{pid} {stato}:cursori {misura}", pagina())
                self._torna(shell)

    def _torna(self, shell) -> None:
        """Se un clic ha aperto un'altra schermata, si torna alle pagine."""
        app = self.app
        while app.scenes and app.scenes[-1] is not shell:
            app.scenes.pop()
        if not app.scenes:
            app.scenes.append(shell)


# il nome di una foto: pagina_stato_misura_scala.png (hq_aperta_1180x680_1.0.png)
_FOTO = re.compile(r"[a-z]+_[a-z0-9-]+_[0-9]+x[0-9]+_[0-9]+\.[0-9]+\.png")


def _impronta(p: Path):
    try:
        st = p.stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        prog="prova_ui",
        description="Apre ogni pagina dell'interfaccia senza schermo, con la guardia "
                    "sui numeri oltre i 32 bit. Esce con 1 se qualcosa si rompe.")
    ap.add_argument("--only", nargs="+", metavar="PAGINA",
                    help="solo queste pagine (gli id di NAV: hq car dev formulae wec ...)")
    ap.add_argument("--scale", nargs="+", type=float, metavar="S", default=list(SCALE),
                    help="le scale HD da provare (normale: 1.0 1.5 2.0)")
    ap.add_argument("--foto", action="store_true",
                    help="salva una PNG per ogni pagina, stato, misura e scala")
    ap.add_argument("--cartella", type=Path, default=None,
                    help="dove mettere le foto (normale: cache/prova-ui nel gioco, "
                         "che git ignora)")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    try:
        from game import config as C
        from game.ui.scenes.shell import NAV
    except Exception:
        print("prova_ui: il gioco non si importa:")
        traceback.print_exc(file=sys.stdout)
        return 2
    tutte = [n[0] for n in NAV]
    pagine = tutte
    if args.only:
        sconosciute = [p for p in args.only if p not in tutte]
        if sconosciute:
            print(f"prova_ui: pagine sconosciute: {' '.join(sconosciute)}")
            print(f"le pagine di NAV sono: {' '.join(tutte)}")
            return 2
        pagine = [p for p in tutte if p in args.only]
    scale = [s for s in args.scale if s > 0]
    if not scale:
        print("prova_ui: serve almeno una scala maggiore di zero")
        return 2
    risoluzioni = [(C.MIN_SCREEN_W, C.MIN_SCREEN_H), (C.SCREEN_W, C.SCREEN_H)]

    foto = None
    if args.foto:
        foto = (args.cartella or (RADICE / "cache" / "prova-ui")).resolve()
        foto.mkdir(parents=True, exist_ok=True)
        # si tengono solo le foto dell'ultima prova: quelle vecchie confondono.
        # Ma solo le nostre, col nome che da' questa prova: con --cartella la
        # cartella puo' essere una qualunque, con dentro altre immagini
        for vecchia in foto.glob("*.png"):
            if _FOTO.fullmatch(vecchia.name) and vecchia.name.split("_", 1)[0] in tutte:
                try:
                    vecchia.unlink()
                except OSError:
                    pass

    # le impostazioni di chi gioca: alla fine devono essere come prima
    impostazioni = [Path(C.UTENTE) / "video.json", Path(C.UTENTE) / "audio.json"]
    impronte = [_impronta(p) for p in impostazioni]

    try:
        prova = Prova(foto)
        gs = stato_estremo()
    except Exception:
        print("prova_ui: la prova non e' partita (gioco o stato estremo):")
        traceback.print_exc(file=sys.stdout)
        return 2

    np, ns = len(pagine), len(scale)
    print(f"prova_ui: {np} pagin{'a' if np == 1 else 'e'} x {len(STATI)} stati (piu' le "
          f"schede interne) x {len(risoluzioni)} misure x {ns} scal{'a' if ns == 1 else 'e'}, "
          f"con i cursori al limite")
    for ris in risoluzioni:
        for s in scale:
            t = time.perf_counter()
            viste, rotte = prova.viste, len(prova.rotte)
            prova.giro(gs, ris, s, pagine)
            print(f"  {ris[0]}x{ris[1]} scala {_fmt_scala(s)}: {prova.viste - viste} viste, "
                  f"{len(prova.rotte) - rotte} rotte ({time.perf_counter() - t:.1f} s)")

    durata = time.perf_counter() - t0
    print(f"Riassunto: {prova.viste} viste e {prova.cursori} cursori al limite in "
          f"{durata:.1f} s; rotte: {len(prova.rotte)}, cause diverse: {len(prova.cause)}")
    # prima le pagine che si rompono da sole, poi i cursori forzati
    for n, causa, dove, pids, tipo in sorted(prova.cause.values(),
                                             key=lambda v: (v[4] != "vista", -v[0])):
        come = "nelle viste" if tipo == "vista" else "coi cursori al limite"
        print(f"  {n} volte {come}, pagine {' '.join(pids)}: {causa}")
        for riga in dove:
            print(f"      {riga}")
    if foto is not None:
        nostre = [f for f in foto.glob("*.png") if _FOTO.fullmatch(f.name)]
        print(f"Foto: {foto} ({len(nostre)} file PNG)")

    toccate = [p.name for p, i in zip(impostazioni, impronte) if _impronta(p) != i]
    if toccate:
        print(f"prova_ui: ATTENZIONE, la prova ha cambiato {', '.join(toccate)}: "
              f"non doveva")
        return 2
    if prova.rotte:
        print("Esito: ROTTA")
        return 1
    print("Esito: tutte le pagine si aprono")
    return 0


if __name__ == "__main__":
    sys.exit(main())
