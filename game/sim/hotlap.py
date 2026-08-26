"""Un turno in pista visto dal muretto: prove libere e qualifica, dal vivo.

Un turno non e' un tabellone che compare tutto insieme. E' un'ora in cui le
macchine escono, fanno il loro giro, rientrano, e intanto il tempo scorre e la
pista migliora. Chi guarda vede i parziali cadere uno alla volta e sa, a meta'
turno, se quello che ha in mano basta per passare il taglio.

Qui dentro c'e' quel turno: chi e' in pista e a che punto del giro, che tempo
sta facendo, quanto manca alla bandiera. I tempi sono quelli di sempre - stesso
modello di giro, stessa vettura, stesso pilota - solo che invece di uscire in
blocco escono quando le macchine li fanno davvero. Guardarlo o saltarlo porta
allo stesso risultato.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import pace

# I tre turni della qualifica, come stanno sul regolamento: nome, minuti,
# quante volte si esce e la mescola imposta (None = la sceglie la squadra).
SEGMENTI = {
    "gp": (("Q1", 18, 2, None), ("Q2", 15, 2, None), ("Q3", 12, 2, None)),
    "sprint": (("SQ1", 12, 2, "medium"), ("SQ2", 10, 1, "medium"),
               ("SQ3", 8, 1, "soft")),
    # una sessione di prove libere: un'ora sola, si esce quattro volte e non
    # si elimina nessuno. Quello che conta e' il lavoro, non la classifica
    "prove": (("PROVE LIBERE", 60, 4, None),),
}

# Quanto dura un giro di uscita e uno di rientro rispetto al giro buono: si
# esce piano per portare le gomme in temperatura e si rientra pianissimo per
# non consumarle.
GIRO_USCITA = 1.32
GIRO_RIENTRO = 1.45


@dataclass
class Corsa:
    """Un'uscita dai box: fuori, giro buono, dentro."""
    mescola: str = "soft"
    tempo: float = 0.0                 # il giro che verra' fuori
    settori: list = field(default_factory=list)
    t_uscita: float = 0.0              # quando si accende il semaforo del box
    valido: bool = True                # un giro buttato resta, ma non conta


@dataclass
class InPista:
    """Lo stato di una vettura dentro al turno, istante per istante."""
    e: object
    corse: list = field(default_factory=list)
    indice: int = 0
    stato: str = "box"                 # box | uscita | giro | rientro | finito
    quota: float = 0.0                 # a che punto del giro e', 0..1
    live: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    settori: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    migliori: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    tempo: float = 0.0                 # il miglior giro di questo turno
    ultimo: float = 0.0
    mescola: str = "soft"
    fuori: bool = False                # eliminato in un turno precedente
    fase_uscita: int = -1              # in che turno e' stato eliminato


class LapSession:
    """Un turno in pista, giocato sul suo orologio."""

    def __init__(self, gs, ws, kind: str = "gp"):
        from .session import build_entrants
        self.gs, self.ws, self.kind = gs, ws, kind
        self.track = ws.track
        # il tempo si muove fra un turno e l'altro: la qualifica non e' le
        # prove del mattino, e la domenica non e' il sabato
        if kind != "prove" or ws.practice_done:
            ws.weather = ws.weather.drift(self.track, gs.rng)
        self.weather = ws.weather
        self.cond = pace.of_weekend(ws, "prove" if kind == "prove" else "quali")
        self.ents = build_entrants(gs, self.track, self.cond, quali=(kind != "prove"))
        self.fasi = SEGMENTI[kind if kind in SEGMENTI else "gp"]
        self.piste = {e.driver_id: InPista(e=e) for e in self.ents}
        self.vivi = list(self.ents)
        self.phase = 0
        self.t = 0.0
        self.durata = 0.0
        self.finita = False
        self.applicata = False
        self.eventi: list = []
        self.best_sectors = [0.0, 0.0, 0.0]
        self.best_lap = 0.0
        self.best_by = ""
        self.times: dict = {}          # driver_id -> miglior tempo del turno
        self.reached: dict = {}        # driver_id -> ultimo turno disputato
        self.radio: list = []
        self._apri_fase()

    # ------------------------------------------------------------- anagrafica
    @property
    def nome_fase(self) -> str:
        return self.fasi[min(self.phase, len(self.fasi) - 1)][0]

    @property
    def tagli(self) -> list:
        """Quanti passano il turno: sei fuori per volta finche' non restano dieci."""
        n = len(self.ents)
        if self.kind == "prove":
            return [0]
        return [max(10, n - 6), 10, 0]

    @property
    def taglio_ora(self) -> int:
        t = self.tagli
        return t[self.phase] if self.phase < len(t) else 0

    def resta(self) -> float:
        return max(0.0, self.durata - self.t)

    def log(self, testo: str, tipo: str = "info") -> None:
        self.eventi.insert(0, {"text": testo, "kind": tipo, "t": self.t})
        del self.eventi[40:]

    # ---------------------------------------------------------- apertura fase
    def _apri_fase(self) -> None:
        nome, minuti, tentativi, imposta = self.fasi[self.phase]
        self.durata = minuti * 60.0
        self.t = 0.0
        self.times = {}
        self.best_sectors = [0.0, 0.0, 0.0]
        self.best_lap, self.best_by = 0.0, ""
        for e in self.vivi:
            p = self.piste[e.driver_id]
            p.corse = self._programma(e, tentativi, imposta)
            p.indice, p.stato, p.quota = 0, "box", 0.0
            p.live = [0.0, 0.0, 0.0]
            p.settori = [0.0, 0.0, 0.0]
            p.migliori = [0.0, 0.0, 0.0]
            p.tempo, p.ultimo = 0.0, 0.0
        self.log(f"{nome}: semaforo verde in fondo alla corsia box", "flag")

    def _programma(self, e, tentativi: int, imposta) -> list:
        """Quando esce, con che gomma e che tempo fara'.

        Il tempo lo decide il modello di sempre; qui si decide solo quando lo
        fa. Le uscite si distribuiscono nel turno come in pista: la prima
        subito per mettere un tempo al sicuro, l'ultima negli ultimi minuti
        sull'asfalto piu' gommato, con la bandiera che cade mentre si e' gia'
        lanciati.
        """
        from ..core import tyres
        gs, ws = self.gs, self.ws
        # in qualifica il set si prende una volta per turno: e' quello che si
        # monta uscendo e che si tiene fino alla bandiera. Quanti se ne bruciano
        # nel fine settimana decide cosa resta nel camion la domenica
        fissa = None
        if self.kind != "prove":
            fissa = (tyres.quali_run(gs, ws, e.driver_id, imposta)
                     if ws.tyre_stock else (imposta or "soft"))
        corse = []
        for r in range(tentativi):
            mescola, tempo = self._tempo_di(e, r, imposta, fissa)
            giro = Corsa(mescola=mescola, tempo=tempo,
                         settori=self._spezza(tempo, e))
            # il giro buono deve finire dentro al turno, o appena dopo la
            # bandiera: si conta all'indietro dal momento in cui si vuole
            # tagliare il traguardo. Nelle libere le uscite si spalmano
            # sull'ora; in qualifica la prima si mette al sicuro presto e
            # l'ultima si gioca con la bandiera che sta gia' cadendo
            if self.kind == "prove":
                quota = (r + 0.55) / tentativi + gs.rng.gauss(0.0, 0.045)
            elif r == tentativi - 1:
                quota = 0.955 + gs.rng.gauss(0.0, 0.018)
            else:
                quota = 0.16 + 0.30 * gs.rng.random()
            fine = self.durata * quota
            fine = max(tempo * 2.6, min(self.durata + tempo * 0.55, fine))
            giro.t_uscita = max(2.0, fine - tempo * (1.0 + GIRO_USCITA))
            corse.append(giro)
        corse.sort(key=lambda c: c.t_uscita)
        return corse

    def _tempo_di(self, e, tentativo: int, imposta, fissa=None):
        """Il giro che quella vettura, con quel pilota, fa qui adesso."""
        from ..core import tyres
        from .weekend import DRIVER_S_PER_POINT
        gs, ws = self.gs, self.ws
        t = e.base_lap
        t += (85.0 - e.skill) * DRIVER_S_PER_POINT
        t += 8.0 * 0.032                                  # serbatoio da qualifica
        if self.kind == "prove":
            # nelle libere il programma e' un altro: si comincia sulle dure per
            # capire il passo, e la morbida si monta solo alla fine per il giro
            # secco. I set che si bruciano li conta la sessione, non il giro
            voluta = (("hard", "medium", "soft"), ("medium", "hard", "soft"),
                      ("medium", "soft", "hard"), ("soft", "medium", "hard"))
            prefer = voluta[min(tentativo, 3)]
            mescola = (tyres.best_available(ws, e.driver_id, prefer)
                       if ws.tyre_stock else prefer[0])
        else:
            mescola = fissa or imposta or "soft"
        t -= tyres.QUALI_GAIN.get(mescola, 0.35)
        # la pista si gomma turno dopo turno: in Q3 si gira sull'asfalto
        # migliore di tutto il fine settimana, e dentro allo stesso turno la
        # seconda uscita e' su un asfalto migliore della prima
        t *= 1.0 - 0.0022 * self.phase - 0.0012 * tentativo
        if self.kind == "prove":
            # nelle libere non si gira mai col coltello fra i denti: c'e'
            # benzina a bordo, si prova l'assetto, e il giro secco arriva solo
            # quando serve
            t *= 1.0 + 0.014 - 0.004 * tentativo
        if self.weather.wet > 0.05:
            t += (85.0 - e.wet_skill) * 0.06 * self.weather.wet * 4.0
        t += gs.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.0028
                          + pace.wind_noise(self.cond))
        # chi non si fida della macchina il giro perfetto non lo trova
        sporco = 0.055 + (100.0 - e.consistency) * 0.0022
        sporco *= 1.0 + (65.0 - e.confidence) * 0.009
        if gs.rng.random() < max(0.010, sporco):
            t += gs.rng.uniform(0.4, 2.4)                 # giro sporcato
        return mescola, t

    def _spezza(self, tempo: float, e) -> list:
        """Il giro diviso nei tre settori, come lo divide questa vettura."""
        a, b = (getattr(e, "sector_shares", None)
                or getattr(self.track, "sector_time", (0.3333, 0.6667)))
        quote = [a, b - a, 1.0 - b]
        rng = self.gs.rng
        pezzi = [max(0.05, q * (1.0 + rng.gauss(0.0, 0.006))) for q in quote]
        k = tempo / sum(pezzi)
        return [p * k for p in pezzi]

    # -------------------------------------------------------------- il turno
    def update(self, dt: float) -> None:
        if self.finita:
            return
        self.t += dt
        for p in self.piste.values():
            if p.fuori:
                continue
            self._passo(p, dt)
        # il turno finisce quando cade la bandiera e l'ultimo lanciato ha
        # tagliato il traguardo: chi sta rientrando non tiene fermo nessuno
        if self.t >= self.durata and not any(
                p.stato == "giro" and not p.fuori for p in self.piste.values()):
            self._chiudi_fase()

    def _passo(self, p: InPista, dt: float) -> None:
        e = p.e
        if p.indice >= len(p.corse):
            p.stato = "finito"
            return
        c = p.corse[p.indice]
        if p.stato == "box":
            if self.t >= c.t_uscita:
                p.stato, p.quota, p.mescola = "uscita", 0.0, c.mescola
                p.live = [0.0, 0.0, 0.0]
            return
        durata = {"uscita": c.tempo * GIRO_USCITA, "giro": c.tempo,
                  "rientro": c.tempo * GIRO_RIENTRO}.get(p.stato, c.tempo)
        p.quota += dt / max(1.0, durata)
        if p.stato == "giro":
            self._parziali(p, c)
        if p.quota < 1.0:
            return
        p.quota = 0.0
        if p.stato == "uscita":
            # il giro lo si comincia solo se la bandiera non e' ancora caduta:
            # quello iniziato prima si porta a termine, quello dopo no
            if self.t >= self.durata:
                p.stato = "rientro"
                return
            p.stato = "giro"
            p.live = [0.0, 0.0, 0.0]
        elif p.stato == "giro":
            self._chiudi_giro(p, c)
            p.stato = "rientro"
        else:
            p.indice += 1
            p.stato = "box" if p.indice < len(p.corse) else "finito"

    def _parziali(self, p: InPista, c: Corsa) -> None:
        """I traguardi di settore, mano a mano che si passa."""
        a, b = getattr(self.track, "sector_time", (0.3333, 0.6667))
        for i, soglia in enumerate((a, b)):
            if p.quota >= soglia and p.live[i] <= 0:
                p.live[i] = c.settori[i]
                self._segna(p, i, c.settori[i])

    def _segna(self, p: InPista, i: int, t: float) -> None:
        if p.migliori[i] <= 0 or t < p.migliori[i]:
            p.migliori[i] = t
        if self.best_sectors[i] <= 0 or t < self.best_sectors[i]:
            self.best_sectors[i] = t

    # ------------------------------------------------------------------ radio
    def radio_say(self, e, testo: str, chi: str = "pilota") -> None:
        if not e.is_player:
            return
        self.radio.insert(0, {"driver_id": e.driver_id, "code": e.code, "chi": chi,
                              "text": testo, "t": self.t})
        del self.radio[10:]

    def radio_of(self, driver_id: str) -> dict | None:
        for m in self.radio:
            if m["driver_id"] == driver_id:
                return m
        return None

    def _commento(self, p: InPista, c: Corsa) -> None:
        """Cosa dice chi e' appena rientrato, e cosa gli risponde il muretto.

        Esce dai numeri del giro appena fatto: in che settore si e' perso, se
        la macchina e' in finestra, quanto manca al taglio. E' la stessa cosa
        che il reparto legge sui dati, detta da chi era dentro.
        """
        from ..core import setup as SETUP
        e = p.e
        if not e.is_player:
            return
        gs = self.gs
        team = gs.teams[e.team_id]
        d = gs.drivers.get(e.driver_id)
        voci = []
        # dove si e' perso di piu', settore per settore
        peggio, quanto = 0, 0.0
        for i in range(3):
            if self.best_sectors[i] > 0:
                perso = c.settori[i] - self.best_sectors[i]
                if perso > quanto:
                    peggio, quanto = i, perso
        if quanto > 0.25:
            voci.append((6, "pilota", f"Nel settore {peggio + 1} lascio {quanto:.2f}: "
                                      f"li' la macchina non gira."))
        if d is not None:
            q = SETUP.believed_quality(team, d)
            if q < 0.72:
                voci.append((7, "pilota", "Cosi' non ci siamo: la macchina fa quello "
                                          "che vuole in ingresso."))
            elif q > 0.90 and quanto < 0.15:
                voci.append((3, "pilota", "La macchina risponde, ho fiducia."))
        taglio = self.tempo_taglio()
        if taglio and p.tempo > 0:
            gap = p.tempo - taglio
            if gap > 0:
                voci.append((8, "muretto", f"Sei fuori di {gap:.3f}: serve un altro giro."))
            elif gap > -0.25:
                voci.append((5, "muretto", f"Dentro per {abs(gap):.3f}, troppo poco: "
                                           f"non basta stare cosi'."))
        if self.best_by == e.code:
            voci.append((6, "muretto", "Sei tu il piu' veloce, ottimo lavoro."))
        if self.weather.wet > 0.05:
            voci.append((4, "pilota", "Sull'acqua non trovo riferimenti, e' tutto in movimento."))
        if not voci:
            return
        voci.sort(key=lambda x: -x[0])
        _peso, chi, testo = voci[0]
        self.radio_say(e, testo, chi)

    def _chiudi_giro(self, p: InPista, c: Corsa) -> None:
        p.live[2] = c.settori[2]
        self._segna(p, 2, c.settori[2])
        p.settori = list(c.settori)
        p.ultimo = c.tempo
        if p.tempo <= 0 or c.tempo < p.tempo:
            p.tempo = c.tempo
            self.times[p.e.driver_id] = c.tempo
        if self.best_lap <= 0 or c.tempo < self.best_lap:
            self.best_lap, self.best_by = c.tempo, p.e.code
            self.log(f"{p.e.name} in testa: {_mmss(c.tempo)}", "pass")
        elif p.e.is_player:
            self.log(f"{p.e.name}: {_mmss(c.tempo)}", "info")
        self._commento(p, c)

    def sector_colour(self, p: InPista, i: int, valore: float | None = None):
        t = p.settori[i] if valore is None else valore
        if t <= 0:
            return None
        if self.best_sectors[i] > 0 and t <= self.best_sectors[i] + 1e-6:
            return "viola"
        if p.migliori[i] > 0 and t <= p.migliori[i] + 1e-6:
            return "verde"
        return "giallo"

    # ------------------------------------------------------- fine di un turno
    def _chiudi_fase(self) -> None:
        nome = self.nome_fase
        # chi non ha segnato niente resta in fondo, ma nell'ordine in cui e'
        # sceso in pista: non si inventa un tempo a chi non l'ha fatto
        senza = [e for e in self.vivi if e.driver_id not in self.times]
        for e in senza:
            self.times[e.driver_id] = 999.0
        for e in self.vivi:
            self.reached[e.driver_id] = self.phase
        classifica = sorted(self.vivi, key=lambda e: self.times[e.driver_id])
        keep = self.taglio_ora
        if keep == 0:
            self.finita = True
            self.log(f"{nome} finito: {self.best_by} il piu' veloce", "flag")
            return
        fuori = classifica[keep:]
        for e in fuori:
            self.piste[e.driver_id].fuori = True
            self.piste[e.driver_id].fase_uscita = self.phase
        nomi = ", ".join(e.code for e in fuori)
        self.log(f"Eliminati in {nome}: {nomi}", "warn")
        self.vivi = classifica[:keep]
        self.phase += 1
        if self.phase >= len(self.fasi):
            self.finita = True
        else:
            self._apri_fase()

    def corri_tutto(self, passo: float = 2.0, max_passi: int = 20000) -> None:
        n = 0
        while not self.finita and n < max_passi:
            self.update(passo)
            n += 1
        self.finita = True

    # ------------------------------------------------------------ il tabellone
    def righe(self) -> list:
        """L'ordine sul tabellone: prima chi e' ancora dentro, poi gli eliminati.

        Chi e' uscito in Q1 sta sotto a chi e' uscito in Q2 anche se nel suo
        turno aveva girato piu' forte: e' la stessa regola con cui si compone
        la griglia.
        """
        vivi = [p for p in self.piste.values() if not p.fuori]
        vivi.sort(key=lambda p: (p.tempo <= 0, p.tempo))
        fuori = [p for p in self.piste.values() if p.fuori]
        fuori.sort(key=lambda p: (-p.fase_uscita, p.tempo <= 0, p.tempo))
        return vivi + fuori

    def tempo_taglio(self) -> float:
        """Il tempo dell'ultimo posto che passa il turno."""
        keep = self.taglio_ora
        if not keep:
            return 0.0
        tempi = sorted(p.tempo for p in self.piste.values()
                       if not p.fuori and p.tempo > 0)
        if len(tempi) < keep:
            return 0.0
        return tempi[keep - 1]

    # -------------------------------------------------------------- risultati
    def applica(self) -> list:
        """Chiude il turno sul weekend: griglia, penalita', usura, quel che si e' capito."""
        if self.applicata:
            return self.ws.grid
        self.applicata = True
        if self.kind == "prove":
            return self._applica_prove()
        return self._applica_quali()

    def _applica_quali(self) -> list:
        from .session import _learn_from_running, _regola_107, ordina_griglia
        gs, ws = self.gs, self.ws
        tempi = {d: p.tempo if p.tempo > 0 else 999.0 for d, p in self.piste.items()}
        raggiunto = {d: (p.fase_uscita if p.fuori else len(self.fasi) - 1)
                     for d, p in self.piste.items()}
        ordine = sorted(tempi.items(), key=lambda kv: (-raggiunto[kv[0]], kv[1]))
        griglia = [d for d, _ in ordine]
        pole = griglia[0]
        note = _regola_107(gs, tempi, raggiunto, self.fasi[0][0])
        # e poi, se il regolamento ha qualcosa da dire sull'ordine, lo dice qui
        griglia, altre = ordina_griglia(gs, griglia, tempi, self.kind)
        note += altre
        pole = griglia[0]
        for team in gs.teams.values():
            team.car.wear(0.4, self.track)
        pace.rubber_in(ws, 0.006)
        _learn_from_running(gs, ws, 0.55)
        if self.kind == "sprint":
            ws.sprint_grid, ws.sprint_times, ws.sprint_pole = griglia, tempi, pole
            ws.sprint_phase = dict(raggiunto)
            ws.sprint_quali_done = True
            return ws.sprint_grid
        from ..core import penalties
        ws.quali_times = tempi
        ws.pole = pole
        ws.quali_phase = dict(raggiunto)
        ws.grid, ws.grid_notes = penalties.apply_grid_penalties(gs, griglia)
        ws.grid_notes = note + ws.grid_notes
        ws.quali_done = True
        return ws.grid

    def _applica_prove(self) -> list:
        from .session import run_practice
        self.ws.practice_times = {d: p.tempo for d, p in self.piste.items() if p.tempo > 0}
        return run_practice(self.gs, self.ws, turno=self)


def _mmss(t: float) -> str:
    m, s = divmod(max(0.0, t), 60.0)
    return f"{int(m)}:{s:06.3f}"
