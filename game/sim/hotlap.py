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
# quante volte si esce al massimo e la mescola imposta (None = la sceglie la
# squadra). "Al massimo", perche' la seconda uscita non e' scontata: se il
# tempo che si ha in mano basta, si resta ai box e si salva un treno.
SEGMENTI = {
    "gp": (("Q1", 18, 2, None), ("Q2", 15, 2, None), ("Q3", 12, 2, None)),
    "sprint": (("SQ1", 12, 2, "medium"), ("SQ2", 10, 2, "medium"),
               ("SQ3", 8, 2, "soft")),
    # una sessione di prove libere: un'ora sola e non si elimina nessuno.
    # Quante uscite si fanno lo dice il programma qui sotto
    "prove": (("PROVE LIBERE", 60, 4, None),),
}

# Il programma di un'ora di prove libere, sessione per sessione. Non sono
# quattro giri secchi: sono quattro pezzi di lavoro con uno scopo ciascuno.
# Il venerdi' si comincia con qualche giro per sentire che la macchina sia a
# posto, poi si fa un lungo per capire il passo gara; nell'ultima parte si
# monta la morbida per la simulazione di qualifica e con quelle stesse gomme
# si resta fuori a fare un altro pezzo di passo. Il sabato mattina si inverte:
# prima il passo, e il giro secco alla fine, che e' la prova generale.
PROVE_PROGRAMMA = (
    (("controllo", 3), ("passo", 14), ("qualifica", 1), ("passo", 12)),
    (("controllo", 3), ("passo", 14), ("qualifica", 1), ("passo", 12)),
    (("passo", 14), ("qualifica", 1)),
)

# Ma quel programma e' la traccia, non il turno. Due macchine non fanno la
# stessa ora: chi ha una macchina che non va gira di piu' e in pezzi corti per
# provare le cose, chi ce l'ha a posto fa il suo lungo e rientra; un pilota che
# non conosce la pista si prende dei giri in piu' per impararla, uno che c'e'
# gia' stato dieci volte no. E dove si consuma il lungo vale il doppio, mentre
# fra i muri il lungo non lo fa nessuno: si rompe la macchina e si perde il
# fine settimana.
GIRI_FORBICE = 0.28        # di quanto un lungo puo' allungarsi o accorciarsi
GIRI_MINIMI = 4            # sotto questo non e' piu' un lungo
GIRI_MASSIMI = 22
CONTROLLO_FORBICE = (2, 5)
# Quanto pesa il consumo della pista sulla lunghezza dei lunghi: dove la gomma
# si sfoglia il passo gara e' l'unica cosa che conta, e si fa lungo
PESO_CONSUMO = 0.45
# e quanto pesa avere i muri a bordo pista: si esce di meno e per meno giri
PESO_MURI = 0.30
# Chi non si fida della macchina esce in pezzi corti e ci torna sopra: sono
# giri in piu' in totale, ma nessuno lungo
SFIDUCIA_GIRI = 0.35

# Il traffico. Una pista non e' un cronometro vuoto: davanti c'e' sempre
# qualcuno che rientra piano, o che sta cominciando il suo lungo, e trovarselo
# in mezzo a una curva veloce vuol dire buttare il giro. Nelle libere il
# traffico e' il vero avversario, ed e' per questo che una macchina resta ferma
# in fondo alla corsia box con il motore acceso a guardare il monitor, e per
# cui un pilota fa un secondo giro di lancio invece di lanciarsi: sta facendo
# il buco. Dove la pista e' stretta il buco deve essere piu' grande, perche'
# per togliersi di torno non basta spostarsi.
FINESTRA_TRAFFICO = 0.035    # quanto giro davanti si guarda, in frazione di giro
TRAFFICO_STRETTO = 0.85      # e di quanto la finestra si allarga fra i muri
# Il traffico non si paga al secondo: si paga a incontro. Trovarsene uno in
# mezzo costa una staccata rovinata e l'uscita di curva sbagliata dietro alla
# sua scia, ed e' quello, non il tempo che ci si resta. Chi ha la mano lo paga
# meno: se lo vede arrivare e si organizza il giro attorno.
COSTO_INCONTRO = 0.30        # secondi buttati per ogni macchina trovata in mezzo
TRAFFICO_MAX = 1.5           # ma un giro non lo si butta piu' di cosi'
# e quanto pesa a seconda di cosa si sta facendo: su un giro secco e' il
# giro buttato, dentro a un lungo si molla un attimo e si riprende
PESO_INCONTRO = {"qualifica": 1.0, "passo": 0.72, "controllo": 0.35}
# e da chi ci si trova davanti. Uno che sta rientrando ai box si toglie: vede
# il delta, alza la mano e si sposta, e costa poco. Uno che si sta preparando
# il giro no - e' sulla traiettoria, va piano apposta per farsi il buco lui, e
# quello e' l'incubo classico del primo turno di qualifica.
PESO_CHI = {"rientro": 0.35, "uscita": 1.0, "giro": 0.70}
PRIMO_GIRO = 0.006           # quanto e' piu' lento il primo giro di uno stint
# Quanto ci si impegna a evitarlo, e non e' uguale sempre: in un'ora di libere
# il programma comanda e a un certo punto si esce comunque, in qualifica no -
# li' il giro pulito e' l'unica cosa che conta, e si aspetta quanto serve.
ATTESA_MAX = {"prove": 50.0, "quali": 85.0}
LANCI_MAX = {"prove": 2, "quali": 4}
USCITA_BOX = 0.03            # a che punto del giro sbuca la corsia box

ETICHETTA = {"controllo": "controllo", "passo": "passo gara",
             "qualifica": "simulazione qualifica"}

# Quanto e' piu' lento un giro a seconda di cosa si sta facendo. Con il pieno
# e senza spingere si perdono quattro secondi su novanta; nel giro di
# controllo non si spinge affatto, si guardano i sensori.
RITMO = {"controllo": 1.075, "passo": 1.042, "qualifica": 1.006}

# Quanto si perde a ogni giro di un lungo: le gomme calano, il serbatoio si
# svuota, e le due cose quasi si annullano - quasi.
DEGRADO_GIRO = 0.0016

# Il minimo che ci vuole ai box fra un'uscita e l'altra: si scaricano i dati,
# si parla con il pilota, si cambiano le gomme.
BOX_MINIMO = 150.0

# Quanto si guadagna a passare per ultimi: la pista si gomma mentre il turno
# va avanti, e chi taglia il traguardo con la bandiera che cade gira su un
# asfalto che a inizio turno non c'era. E' il motivo per cui tutti vorrebbero
# uscire alla fine, e per cui restare ai box costa qualcosa anche a chi e'
# gia' dentro.
GOMMATURA = 0.0040

# Quanto dura un giro di uscita e uno di rientro rispetto al giro buono: si
# esce piano per portare le gomme in temperatura e si rientra pianissimo per
# non consumarle.
GIRO_USCITA = 1.32
GIRO_RIENTRO = 1.45

# Quanto migliora la pista da meta' turno alla bandiera. E' il margine che una
# squadra deve mettere in conto prima di decidere che il tempo che ha in mano
# basta: nel primo turno l'asfalto e' ancora sporco e migliora tanto, in Q3
# ormai e' fatto.
MIGLIORA_PISTA = (0.55, 0.40, 0.30)

# Quando si puo' restare ai box invece di uscire un'altra volta. Al muretto
# guardano due cose insieme, e devono dire di si' tutte e due: dove ci si vede
# arrivare - stare nella prima meta' di chi passa, non un posto qualunque
# dentro il taglio - e di quanto si e' davanti a chi resterebbe fuori. Il
# tempo conta perche' mezzo secondo in una griglia larga vale meno che in una
# stretta, e la posizione conta perche' una previsione a due decimi non e' una
# previsione.
QUOTA_SICURA = 0.42
MARGINE_SICURO = 0.004

# Quanti set si tengono comunque per la domenica: sotto questa soglia si esce
# con le gomme che si hanno gia' addosso.
RISERVA_GARA = 3
# e quanti se ne tengono per l'ultimo turno: e' la morbida che il regolamento
# mette da parte per giocarsi la pole, quella che chi non arriva in fondo deve
# restituire. Non si brucia in Q1, e chi lo fa in Q3 ci arriva con le gomme
# di prima
RISERVA_ULTIMO = 1
# e quanto costa girare su un treno gia' usato invece che su uno nuovo. Poco:
# un set con sopra un giro lanciato non e' finito, e' solo un po' meno
# generoso nel primo settore. Ma su un giro secco si sente.
PENALITA_USATE = 0.15

# Quanto spesso un pilota tira fuori il giro che non doveva venire. Si scala
# con l'inventiva: chi ce l'ha lo trova una volta su sei, chi non ce l'ha
# quasi mai. Ed e' la stessa qualita' che gli fa buttare gli altri.
GIRO_MAGICO = 0.19

# Quanta benzina si porta in qualifica: quella per il giro di uscita, quello
# buono e il rientro, e nemmeno un chilo di piu'.
BENZINA_QUALI = 8.0


@dataclass
class Corsa:
    """Un'uscita dai box: fuori, giro buono, dentro.

    In qualifica e' un giro solo. Nelle libere puo' essere un lungo da quindici
    giri, e allora `giri` dice quanti se ne fanno e `tipo` a cosa serve.
    """
    mescola: str = "soft"
    tempo: float = 0.0                 # il giro che verra' fuori
    settori: list = field(default_factory=list)
    t_uscita: float = 0.0              # quando si accende il semaforo del box
    valido: bool = True                # un giro buttato resta, ma non conta
    tipo: str = "qualifica"            # controllo | passo | qualifica
    giri: int = 1                      # quanti giri buoni si fanno in questa uscita
    nuovo: bool = True                 # treno nuovo o quello che si aveva addosso


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
    giri_fatti: int = 0                # a che punto e' dell'uscita in corso
    restanti: int = 0                  # uscite ancora concesse in questo turno
    saltata: bool = False              # ha deciso di non uscire piu': treno salvo
    traffico: list = field(default_factory=lambda: [0.0, 0.0, 0.0])   # secondi buttati per settore
    attesa: float = 0.0                # da quanto aspetta il buco in fondo ai box
    lanci: int = 0                     # giri di lancio in piu' fatti per trovarlo
    persi: float = 0.0                 # secondi lasciati nel traffico in tutto il turno
    lanci_tot: int = 0                 # quanti giri di lancio in piu' in tutto il turno
    visto: str = ""                    # chi si sta gia' avendo davanti, per non pagarlo due volte
    attese: float = 0.0                # e quanti secondi fermi in fondo ai box


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
        self.sessione = int(getattr(ws, "practice_done", 0) or 0)
        # quanto largo dev'essere il buco su questa pista: fra i muri di Monte
        # Carlo si sta lontani il doppio che sul rettilineo di Silverstone
        stretto = max(0.0, min(1.0, (13.0 - float(getattr(self.track, "larghezza_m", 12.0))) / 5.0))
        self.finestra_traffico = FINESTRA_TRAFFICO * (1.0 + TRAFFICO_STRETTO * stretto)
        # e quanto costa non riuscire a togliersi di torno: fra i muri, tanto
        self.durezza_traffico = 1.0 + TRAFFICO_STRETTO * stretto
        chiave = "prove" if kind == "prove" else "quali"
        self.attesa_max = ATTESA_MAX[chiave]
        self.lanci_max = LANCI_MAX[chiave]
        self._pista_ora: list = []
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
        self.imposta = imposta
        self._ordine_pista = self._ordine_atteso()
        for e in self.vivi:
            p = self.piste[e.driver_id]
            p.corse = self._programma(e, tentativi, imposta)
            p.indice, p.stato, p.quota = 0, "box", 0.0
            p.giri_fatti = 0
            p.restanti = max(0, tentativi - len(p.corse))
            p.saltata = False
            p.live = [0.0, 0.0, 0.0]
            p.settori = [0.0, 0.0, 0.0]
            p.migliori = [0.0, 0.0, 0.0]
            p.tempo, p.ultimo = 0.0, 0.0
            p.traffico = [0.0, 0.0, 0.0]
            p.attesa, p.lanci, p.persi = 0.0, 0, 0.0
            p.lanci_tot, p.attese, p.visto = 0, 0.0, ""
        self.log(f"{nome}: semaforo verde in fondo alla corsia box", "flag")

    # ------------------------------------------------------- quando si esce
    def _atteso(self, e) -> float:
        """Il tempo che ci si aspetta da quella macchina in questo turno.

        Non e' il tempo che fara' - quello ha dentro il caso - e' quello che il
        muretto scrive sulla lavagna prima che si esca. Serve a due cose: a
        decidere in che ordine si va in pista e a capire, a meta' turno, se il
        tempo che si ha in mano terra'.
        """
        from .weekend import DRIVER_S_PER_POINT, FUEL_S_PER_KG
        from ..core import tyres
        t = e.base_lap + (85.0 - e.skill) * DRIVER_S_PER_POINT * self.track.pilota_rel
        t += BENZINA_QUALI * FUEL_S_PER_KG * self.track.benzina_rel
        t -= tyres.QUALI_GAIN.get(self.imposta or "soft", 0.35)
        t *= 1.0 - 0.0022 * self.phase - 0.0012
        if self.weather.wet > 0.05:
            t += (85.0 - e.wet_skill) * 0.06 * self.weather.wet * 4.0
        return t

    def _ordine_atteso(self) -> dict:
        """Chi e' atteso davanti a chi: zero il piu' veloce."""
        ordine = sorted(self.vivi, key=self._atteso)
        return {e.driver_id: i for i, e in enumerate(ordine)}

    def _uscita_prima(self, e) -> float:
        """Quando esce per il primo tentativo.

        In fondo alla corsia box non ci si mette a caso: chi rischia il taglio
        esce per primo, perche' un tempo in cassaforte vale piu' di mezzo
        decimo di asfalto gommato, e chi va forte aspetta - ma non fino alla
        fine, perche' un giro in Q1 vuole comunque essere fatto per tempo.
        """
        n = max(1, len(self.vivi) - 1)
        rango = self._ordine_pista.get(e.driver_id, n) / n     # 0 = il piu' veloce
        quota = 0.015 + 0.175 * (1.0 - rango) + self.gs.rng.gauss(0.0, 0.016)
        return max(1.0, self.durata * max(0.005, quota))

    def _uscita_ultima(self, p, sicuro: float) -> float:
        """Quando esce per l'ultimo tentativo.

        Tutti vogliono l'asfalto della fine, ma non tutti se lo possono
        permettere: chi e' fuori dal taglio esce prima, perche' se il giro gli
        viene sporcato deve avere il tempo di rifarlo. Chi e' tranquillo
        aspetta la bandiera e taglia il traguardo mentre cade.
        """
        c = p.corse[p.indice] if p.indice < len(p.corse) else None
        tempo = c.tempo if c else 90.0
        # si conta all'indietro dal momento in cui si vuole *cominciare* il
        # giro buono, non da quando lo si finisce: il giro cominciato prima
        # della bandiera si porta a termine, quello cominciato dopo no, ed e'
        # la differenza fra fare un tempo e restare fermi in pit lane
        quota = 0.862 + 0.128 * max(0.0, min(1.0, sicuro))
        quota += self.gs.rng.gauss(0.0, 0.012)
        inizio = min(self.durata * quota, self.durata - 4.0)
        return max(self.t + 1.0, inizio - tempo * GIRO_USCITA)

    # ------------------------------------------------------------ i programmi
    def _programma(self, e, tentativi: int, imposta) -> list:
        """Cosa ha in programma questa macchina all'apertura del turno.

        In qualifica si programma solo la prima uscita: la seconda si decide
        dopo, guardando il cronometro, ed e' li' che una squadra sceglie se
        bruciare un treno o portarselo alla domenica. Nelle libere invece il
        programma e' scritto la mattina e si segue.
        """
        if self.kind == "prove":
            return self._piano_prove(e)
        prima = self._corsa(e, "qualifica", 1, imposta, 0)
        prima.t_uscita = self._uscita_prima(e)
        self._asfalto(prima)
        return [prima]

    def _piano_base(self, e) -> list:
        """Cosa vuole fare oggi questa macchina: non quello che vogliono tutte.

        Il foglio del programma e' una traccia, e da li' in poi ognuno fa la
        sua ora. Dove la gomma si sfoglia il lungo e' l'unica cosa che conta e
        si allunga; dove ci sono i muri si esce meno e per meno giri, perche'
        un errore costa il fine settimana intero. Un pilota che non si fida
        della macchina il lungo da quattordici giri non lo fa: fa due pezzi
        corti e in mezzo si cambia qualcosa. E la simulazione di qualifica il
        venerdi' mattina non la fa nessuno per obbligo: chi ha altro da
        provare se la tiene per il pomeriggio.
        """
        gs, tr = self.gs, self.track
        piano = list(PROVE_PROGRAMMA[min(self.sessione, len(PROVE_PROGRAMMA) - 1)])
        consumo = float((tr.traits or {}).get("tyre_wear", 0.5))
        stretto = max(0.0, min(1.0, (13.0 - float(getattr(tr, "larghezza_m", 12.0))) / 5.0))
        k = 1.0 + PESO_CONSUMO * (consumo - 0.5) * 2.0 - PESO_MURI * stretto
        k *= 1.0 + gs.rng.gauss(0.0, GIRI_FORBICE * 0.6)
        # quanto poco si fida della macchina chi la deve guidare
        sfiducia = max(0.0, min(1.0, (70.0 - e.confidence) / 40.0))
        fuori = []
        for tipo, giri in piano:
            if tipo == "controllo":
                fuori.append((tipo, gs.rng.randint(*CONTROLLO_FORBICE)))
                continue
            if tipo == "qualifica":
                # il giro secco della mattina si salta volentieri, se c'e'
                # altro da capire; il pomeriggio e il sabato no
                if self.sessione == 0 and gs.rng.random() < 0.30 + 0.25 * sfiducia:
                    continue
                fuori.append((tipo, giri))
                continue
            n = max(GIRI_MINIMI, min(GIRI_MASSIMI, int(round(giri * k))))
            if sfiducia > 0.35 and n >= GIRI_MINIMI * 2:
                # spezzato in due: si rientra, si cambia qualcosa, si riesce
                meta = max(GIRI_MINIMI, int(n * 0.55))
                fuori.append((tipo, meta))
                n = max(GIRI_MINIMI, n - meta + int(SFIDUCIA_GIRI * meta))
            fuori.append((tipo, n))
        return fuori or [("passo", GIRI_MINIMI)]

    def _piano_prove(self, e) -> list:
        """L'ora di libere di questa macchina, distesa sull'orologio.

        Prima si scrive cosa si vuole fare, poi si guarda se ci sta: se il
        programma e' piu' lungo dell'ora si accorciano i lunghi, cominciando
        dall'ultimo, che e' quello a cui si rinuncia piu' volentieri. Il tempo
        che avanza sono i minuti ai box a guardare i dati, e finiscono spalmati
        fra un'uscita e l'altra - per questo non escono tutti insieme.
        """
        gs = self.gs
        piano = self._piano_base(e)
        corse = [self._corsa(e, tipo, giri, None, r)
                 for r, (tipo, giri) in enumerate(piano)]

        def costo(c):
            return c.tempo * (GIRO_USCITA + GIRO_RIENTRO + c.giri)

        finestra = self.durata * 0.97
        pause = BOX_MINIMO * (len(corse) - 1)
        while sum(costo(c) for c in corse) + pause > finestra:
            lunghi = [c for c in corse if c.tipo == "passo" and c.giri > 3]
            if not lunghi:
                break
            lunghi[-1].giri -= 1
        # quello che avanza sono i minuti ai box: si spalmano fra le uscite,
        # e ogni squadra li spalma a modo suo
        avanzo = max(0.0, finestra - sum(costo(c) for c in corse) - pause)
        pesi = [gs.rng.random() + 0.35 for _ in corse]
        somma = sum(pesi)
        t = avanzo * pesi[0] / somma
        for i, c in enumerate(corse):
            c.t_uscita = t
            self._asfalto(c)
            t += costo(c) + BOX_MINIMO
            if i + 1 < len(corse):
                t += avanzo * pesi[i + 1] / somma
        return [c for c in corse if c.t_uscita < self.durata]

    def _corsa(self, e, tipo: str, giri: int, imposta, indice: int,
               precedente: str = "") -> "Corsa":
        """Un'uscita: che gomme monta, che giro fara' e se il treno e' nuovo."""
        mescola, nuovo = self._gomma(e, tipo, imposta, indice, precedente)
        tempo = self._tempo_di(e, tipo, mescola, nuovo)
        return Corsa(mescola=mescola, tempo=tempo, settori=self._spezza(tempo, e),
                     tipo=tipo, giri=giri, nuovo=nuovo)

    def _gomma(self, e, tipo: str, imposta, indice: int,
               precedente: str = "") -> tuple:
        """Che treno si monta per questa uscita, e se e' nuovo.

        In qualifica ogni uscita vorrebbe il suo treno nuovo, ma i treni sono
        contati e due cose vengono prima: la morbida buona per l'ultimo turno,
        che non si brucia in Q1, e le gomme della domenica. Quando il nuovo non
        c'e' non si cambia mescola - si riesce su quelle di prima, che e'
        quello che fanno in pista - e si paga in tempo sul giro.

        Nelle libere il treno lo detta il programma: dura per il lungo,
        morbida per il giro secco, e il pezzo di passo gara dopo la
        simulazione resta sulle stesse gomme, che e' esattamente il suo punto.
        """
        from ..core import tyres
        gs, ws = self.gs, self.ws
        if not getattr(ws, "tyre_stock", None):
            if self.kind != "prove":
                return (imposta or "soft"), True
            return ({"controllo": "hard", "passo": "medium",
                     "qualifica": "soft"}.get(tipo, "medium"), tipo != "controllo")
        if self.kind == "prove":
            if tipo == "controllo":
                # si esce con quello che c'e' gia' montato: nessun treno nuovo
                return tyres.best_available(ws, e.driver_id,
                                            ("hard", "medium", "soft")), False
            if tipo == "qualifica":
                return tyres.best_available(ws, e.driver_id,
                                            ("soft", "medium", "hard")), True
            if indice > 2:
                # il passo gara dopo la simulazione: stesse gomme di prima
                return tyres.best_available(ws, e.driver_id,
                                            ("soft", "medium", "hard")), False
            return tyres.best_available(ws, e.driver_id,
                                        ("medium", "hard", "soft")), True
        st = tyres.stock_of(ws, e.driver_id)
        voluta = imposta or "soft"
        # quanti se ne devono lasciare stare: quelli della domenica sempre,
        # quelli dell'ultimo turno finche' l'ultimo turno non e' questo
        libero = st.get(voluta, 0)
        if (self.phase < len(self.fasi) - 1 and self._punta_alla_fine(e)
                and (self.fasi[-1][3] or "soft") == voluta):
            # i treni dell'ultimo turno li mette da parte solo chi pensa di
            # arrivarci: chi lotta per uscire dal primo turno usa tutto quello
            # che ha, e fa bene - la pole non e' un suo problema
            libero -= RISERVA_ULTIMO
        if libero > 0 and sum(st.values()) > RISERVA_GARA:
            return tyres.quali_run(gs, ws, e.driver_id, voluta), True
        if precedente:
            return precedente, False       # si riesce con quelle di prima
        return tyres.best_available(ws, e.driver_id,
                                    (voluta, "soft", "medium", "hard")), False

    def _punta_alla_fine(self, e) -> bool:
        """Se questa macchina si aspetta di arrivare all'ultimo turno."""
        finale = self.tagli[-2] if len(self.tagli) > 1 else 10
        return self._ordine_pista.get(e.driver_id, 99) < finale

    def _tempo_di(self, e, tipo: str, mescola: str, nuovo: bool) -> float:
        """Il giro che quella vettura, con quel pilota, fa qui adesso."""
        from ..core import tyres
        from .weekend import DRIVER_S_PER_POINT, FUEL_S_PER_KG
        gs = self.gs
        t = e.base_lap
        t += (85.0 - e.skill) * DRIVER_S_PER_POINT * self.track.pilota_rel
        # il serbatoio da qualifica: pochi chili, ma dove pesano pesano
        t += BENZINA_QUALI * FUEL_S_PER_KG * self.track.benzina_rel
        t -= tyres.QUALI_GAIN.get(mescola, 0.35)
        if not nuovo:
            t += PENALITA_USATE
        # la pista si gomma turno dopo turno: in Q3 si gira sull'asfalto
        # migliore di tutto il fine settimana
        t *= 1.0 - 0.0022 * self.phase
        if self.kind == "prove":
            # e nelle libere il giro dipende da cosa si sta facendo: con il
            # pieno addosso non si va come in qualifica, e nel giro di
            # controllo non ci si prova nemmeno
            t *= RITMO.get(tipo, 1.02)
        if self.weather.wet > 0.05:
            t += (85.0 - e.wet_skill) * 0.06 * self.weather.wet * 4.0
        t += gs.rng.gauss(0.0, 0.09 + (100.0 - e.consistency) * 0.0028
                          + pace.wind_noise(self.cond))
        # chi non si fida della macchina il giro perfetto non lo trova
        sporco = 0.055 + (100.0 - e.consistency) * 0.0022
        sporco *= 1.0 + (65.0 - e.confidence) * 0.009
        # e l'inventiva lavora nelle due direzioni: chi si azzarda trova il
        # giro che non doveva venire piu' spesso, e piu' spesso lo butta
        estro = getattr(e, "estro", 60.0)
        sporco *= 0.82 + 0.36 * (estro / 100.0)
        if tipo == "qualifica" and gs.rng.random() < max(0.010, sporco):
            t += gs.rng.uniform(0.4, 2.4)                 # giro sporcato
        elif tipo == "qualifica" and gs.rng.random() < GIRO_MAGICO * (estro / 100.0):
            # la traiettoria che nessuno aveva provato, la staccata tenuta
            # mezzo metro piu' in la': e' quello che fa le pole a sorpresa
            t -= gs.rng.uniform(0.10, 0.42)
        return t

    def _asfalto(self, c: "Corsa") -> None:
        """La pista si gomma mentre il turno va avanti.

        Il giro non vale uguale a tutte le ore: chi passa alla bandiera trova
        l'asfalto migliore del turno. Si applica qui, quando si sa a che ora
        quella macchina taglierebbe il traguardo, e non al momento di scrivere
        il programma: e' l'orologio a decidere, non il numero dell'uscita.
        """
        quando = (c.t_uscita + c.tempo * GIRO_USCITA) / max(1.0, self.durata)
        k = 1.0 - GOMMATURA * max(0.0, min(1.0, quando))
        c.tempo *= k
        c.settori = [x * k for x in c.settori]

    def _spezza(self, tempo: float, e) -> list:
        """Il giro diviso nei tre settori, come lo divide questa vettura."""
        a, b = (getattr(e, "sector_shares", None)
                or getattr(self.track, "sector_time", (0.3333, 0.6667)))
        quote = [a, b - a, 1.0 - b]
        rng = self.gs.rng
        pezzi = [max(0.05, q * (1.0 + rng.gauss(0.0, 0.006))) for q in quote]
        k = tempo / sum(pezzi)
        return [p * k for p in pezzi]

    # ------------------------------------------------- si esce un'altra volta?
    def _proiezione(self, escluso: str = "") -> list:
        """Con che tempi finira' il turno, per come si mette adesso.

        E' il conto che fa il muretto quando la macchina rientra: chi ha gia'
        girato e ha ancora un'uscita migliorera' di quanto migliora la pista,
        chi non ha ancora girato fara' il tempo che ci si aspetta da lui. Non
        e' la verita' - e' una previsione, e infatti si sbaglia.
        """
        migliora = MIGLIORA_PISTA[min(self.phase, len(MIGLIORA_PISTA) - 1)]
        fuori = []
        for q in self.piste.values():
            if q.fuori or q.e.driver_id == escluso:
                continue
            atteso = self._atteso(q.e)
            if q.tempo > 0 and (q.restanti <= 0 or q.saltata):
                fuori.append(q.tempo)
            elif q.tempo > 0:
                fuori.append(min(q.tempo, atteso) - migliora)
            else:
                fuori.append(atteso - migliora * 0.5)
        return sorted(fuori)

    def _basta_cosi(self, p: InPista) -> bool:
        """Se il tempo che ha in mano lo tiene dentro senza bruciare un treno.

        E' la decisione che in Q1 fa restare ai box le macchine di testa: il
        primo giro e' bastato, il secondo treno serve alla domenica. Il muretto
        la prende sui numeri che ha, e i numeri sono una previsione: una
        squadra che legge male la pista ogni tanto resta ai box e si ritrova
        eliminata.
        """
        keep = self.taglio_ora
        if keep == 0 or p.tempo <= 0:
            return False           # nell'ultimo turno si esce sempre due volte
        altri = self._proiezione(escluso=p.e.driver_id)
        if len(altri) < keep:
            return False
        # il tempo del primo che resta fuori, per come si mette: e' quello da
        # battere, e battuto va di quel margine che vale la pena rischiare
        taglio = altri[keep - 1]
        # l'errore di valutazione: chi ha un muretto forte legge la pista
        # meglio di chi non ce l'ha, e sbaglia meno spesso questa scelta
        errore = self.gs.rng.gauss(0.0, 0.10 + (100.0 - p.e.strategy_skill) * 0.006)
        if p.tempo + MARGINE_SICURO * p.tempo + errore >= taglio:
            return False
        posto = sum(1 for v in altri if v < p.tempo + errore) + 1
        return posto <= max(1, int(keep * QUOTA_SICURA))

    def _dopo_corsa(self, p: InPista) -> None:
        """La macchina e' rientrata: si guarda se ne serve un'altra."""
        if self.kind == "prove" or p.restanti <= 0:
            return
        if self.t >= self.durata:
            p.restanti = 0
            return
        if self._basta_cosi(p):
            p.restanti = 0
            p.saltata = True
            if p.e.is_player:
                self.radio_say(p.e, "Il tempo tiene: restiamo dentro e ci teniamo "
                                    "il treno per domenica.", "muretto")
            self.log(f"{p.e.code} resta ai box: si tiene il treno", "info")
            return
        # quanto e' al sicuro adesso: da questo dipende se aspetta la bandiera.
        # Nell'ultimo turno non c'e' nessun taglio da temere e la pista non e'
        # mai stata cosi' buona: vogliono passare tutti per ultimi
        if self.taglio_ora == 0:
            sicuro = 1.0
        else:
            altri = self._proiezione(escluso=p.e.driver_id)
            keep = self.taglio_ora
            davanti = sum(1 for v in altri if v < p.tempo) if p.tempo > 0 else len(altri)
            sicuro = 1.0 - min(1.0, max(0.0, (davanti + 1) / max(1, keep)))
        nuova = self._corsa(p.e, "qualifica", 1, self.imposta, 1, p.mescola)
        p.corse.append(nuova)
        p.restanti -= 1
        nuova.t_uscita = self._uscita_ultima(p, sicuro)
        self._asfalto(nuova)

    # ------------------------------------------------------------- il traffico
    def _in_pista(self) -> list:
        """Chi e' fuori adesso e a che punto del giro, in ordine di pista."""
        out = [(q.quota, q) for q in self.piste.values()
               if not q.fuori and q.stato not in ("box", "finito")]
        out.sort(key=lambda x: x[0])
        return out

    def _andatura(self, q: InPista) -> float:
        """Quanto ci mette a fare il giro che sta facendo adesso, in secondi."""
        if q.indice >= len(q.corse):
            return 1e6
        c = q.corse[q.indice]
        if q.stato == "uscita":
            return c.tempo * GIRO_USCITA
        if q.stato == "rientro":
            return c.tempo * GIRO_RIENTRO
        return self._giro_di(c, q.giri_fatti)

    def _uscita_libera(self) -> bool:
        """Se in fondo alla corsia box, adesso, non sta passando nessuno.

        Qui non conta chi va piu' piano di chi: conta che uscire proprio
        mentre passa un altro vuol dire fargli il giro e farselo fare. Il
        meccanico col cartello tiene la macchina ferma dieci secondi e la
        molla nel buco, ed e' esattamente quello che si vede in televisione.
        """
        for q_pos, q in self._pista_ora:
            if (q_pos - USCITA_BOX) % 1.0 <= self.finestra_traffico * 0.8:
                return False
        return True

    def _davanti(self, p: InPista, quota: float, andatura: float):
        """Chi si ha davanti dentro alla finestra, se va piu' piano di noi.

        Uno che va come noi non e' traffico: e' uno che gira. Traffico e' chi
        sta rientrando, chi si sta lanciando, chi e' al decimo giro di un lungo
        con la gomma andata - quelli che ci si trova fermi in mezzo alla curva.
        """
        for q_pos, q in self._pista_ora:
            if q is p:
                continue
            d = (q_pos - quota) % 1.0
            if 0.0 < d <= self.finestra_traffico and self._andatura(q) > andatura * 1.03:
                return q
        return None

    def _settore_di(self, quota: float) -> int:
        a, b = getattr(self.track, "sector_time", (0.3333, 0.6667))
        return 0 if quota < a else (1 if quota < b else 2)

    # -------------------------------------------------------------- il turno
    def update(self, dt: float) -> None:
        if self.finita:
            return
        self.t += dt
        # dove sono tutti, adesso: si guarda una volta sola e vale per tutti
        self._pista_ora = self._in_pista()
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
        if p.indice >= len(p.corse):
            p.stato = "finito"
            return
        c = p.corse[p.indice]
        if p.stato == "box":
            if self.t < c.t_uscita:
                return
            # in fondo alla corsia box si guarda il monitor prima di mollare i
            # freni: uscire dentro a un gruppo vuol dire buttare l'uscita, e
            # allora si aspetta. Ma non all'infinito: a un certo punto il turno
            # finisce, e un'uscita nel traffico vale piu' di nessuna uscita
            if (p.attesa < self.attesa_max and self.t < self.durata - 90.0
                    and not self._uscita_libera()):
                p.attesa += dt
                p.attese += dt
                return
            p.stato, p.quota, p.mescola = "uscita", 0.0, c.mescola
            p.giri_fatti = 0
            p.attesa, p.lanci = 0.0, 0
            p.live = [0.0, 0.0, 0.0]
            p.traffico = [0.0, 0.0, 0.0]
            return
        durata = {"uscita": c.tempo * GIRO_USCITA, "giro": self._giro_di(c, p.giri_fatti),
                  "rientro": c.tempo * GIRO_RIENTRO}.get(p.stato, c.tempo)
        p.quota += dt / max(1.0, durata)
        if p.stato == "giro":
            self._parziali(p, c)
            # e quello che il traffico si prende. Si paga quando se ne trova
            # uno nuovo davanti, non per tutto il tempo che ci si resta
            addosso = self._davanti(p, p.quota, self._andatura(p))
            chi = addosso.e.driver_id if addosso is not None else ""
            if chi and chi != p.visto and sum(p.traffico) < TRAFFICO_MAX:
                i = self._settore_di(min(0.999, p.quota))
                # chi guida pulito il giro se lo riorganizza attorno
                mano = 0.75 + 0.5 * (100.0 - p.e.consistency) / 40.0
                p.traffico[i] += (COSTO_INCONTRO * self.durezza_traffico * mano
                                 * PESO_INCONTRO.get(c.tipo, 1.0)
                                 * PESO_CHI.get(addosso.stato, 1.0))
            p.visto = chi
        if p.quota < 1.0:
            return
        p.quota = 0.0
        if p.stato == "uscita":
            # il giro lo si comincia solo se la bandiera non e' ancora caduta:
            # quello iniziato prima si porta a termine, quello dopo no
            if self.t >= self.durata:
                p.stato = "rientro"
                return
            # e solo se davanti si vede libero: se no si fa un altro giro
            # piano, si lascia andare chi si ha davanti e ci si lancia dopo.
            # E' la cosa che in pista si vede tutti i sabati
            if (p.lanci < self.lanci_max and self.t < self.durata - durata * 2.0
                    and self._davanti(p, 0.0, c.tempo) is not None):
                p.lanci += 1
                p.lanci_tot += 1
                return
            p.stato = "giro"
            p.lanci = 0
            p.live = [0.0, 0.0, 0.0]
            p.traffico = [0.0, 0.0, 0.0]
        elif p.stato == "giro":
            self._chiudi_giro(p, c)
            p.giri_fatti += 1
            if p.giri_fatti < c.giri and self.t < self.durata:
                p.live = [0.0, 0.0, 0.0]     # si resta fuori: e' un lungo
                p.traffico = [0.0, 0.0, 0.0]
            else:
                p.stato = "rientro"
        else:
            p.indice += 1
            p.stato = "box"
            self._dopo_corsa(p)
            if p.indice >= len(p.corse):
                p.stato = "finito"

    def etichetta(self, p: InPista, corta: bool = False) -> str:
        """Cosa sta facendo questa macchina adesso, in due parole.

        In qualifica c'e' poco da dire: o si e' ai box o si e' lanciati. Nelle
        libere no: un'ora e' fatta di pezzi diversi, e sapere che quella
        macchina e' al quinto giro di un lungo di quattordici e' esattamente
        quello che si vuole leggere sul tabellone.
        """
        if p.fuori or p.indice >= len(p.corse):
            return "" if corta else ("eliminato" if p.fuori else "ha finito")
        c = p.corse[p.indice]
        if p.stato == "box":
            if p.attesa > 1.0:
                return "attende" if corta else "in fondo alla corsia, aspetta il buco"
            return "" if corta else "ai box"
        if p.stato == "uscita":
            if p.lanci > 0:
                return "spazio" if corta else "un altro lancio per trovare lo spazio"
            return "lancio" if corta else "giro di lancio"
        if p.stato == "rientro":
            return "rientra" if corta else "rientra ai box"
        if c.tipo == "qualifica":
            return "LANCIATO" if corta else "GIRO LANCIATO"
        dove = f"{p.giri_fatti + 1}/{c.giri}"
        if corta:
            return f"{'passo' if c.tipo == 'passo' else 'check'} {dove}"
        return f"{ETICHETTA[c.tipo]}, giro {dove}"

    def _giro_di(self, c: Corsa, k: int) -> float:
        """Il giro numero k di questa uscita: in un lungo le gomme calano.

        E il primo giro di un lungo non e' come gli altri: la gomma non e'
        ancora dentro alla finestra e mezzo secondo se ne va li'. Chi guarda
        il tabellone lo sa e il primo giro di uno stint non lo guarda.
        """
        t = c.tempo * (1.0 + DEGRADO_GIRO * k)
        if k == 0 and c.giri > 1:
            t *= 1.0 + PRIMO_GIRO
        return t


    def _parziali(self, p: InPista, c: Corsa) -> None:
        """I traguardi di settore, mano a mano che si passa.

        Il parziale che va a tabellone e' quello vero, traffico compreso: se
        in quel settore ci si e' trovati dietro a qualcuno, quel tempo se lo
        e' preso e a schermo si vede giallo.
        """
        a, b = getattr(self.track, "sector_time", (0.3333, 0.6667))
        for i, soglia in enumerate((a, b)):
            if p.quota >= soglia and p.live[i] <= 0:
                t = c.settori[i] + p.traffico[i]
                p.live[i] = t
                self._segna(p, i, t)

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
                perso = p.settori[i] - self.best_sectors[i]
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
        # il giro che va a tabellone e' quello fatto davvero: al tempo che la
        # macchina aveva in mano si somma quello che il traffico si e' preso
        settori = [c.settori[i] + p.traffico[i] for i in range(3)]
        giro = sum(settori)
        perso = giro - c.tempo
        p.persi += perso
        p.live[2] = settori[2]
        self._segna(p, 2, settori[2])
        p.settori = list(settori)
        p.ultimo = giro
        if p.tempo <= 0 or giro < p.tempo:
            p.tempo = giro
            self.times[p.e.driver_id] = giro
        if self.best_lap <= 0 or giro < self.best_lap:
            self.best_lap, self.best_by = giro, p.e.code
            self.log(f"{p.e.name} in testa: {_mmss(giro)}", "pass")
        elif p.e.is_player and c.tipo == "qualifica":
            coda = f" ({perso:.2f} nel traffico)" if perso > 0.15 else ""
            self.log(f"{p.e.name}: {_mmss(giro)}{coda}", "info")
        if p.e.is_player and perso > 0.35 and c.tipo == "qualifica":
            self.radio_say(p.e, f"Me lo sono trovato davanti in curva, "
                                f"buttati {perso:.2f}.", "pilota")
        # dopo un giro secco si commenta; dentro un lungo si parla alla fine
        if c.tipo == "qualifica" or p.giri_fatti + 1 >= c.giri:
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
            # e si spengono: senza questo il pallino di chi e' stato eliminato
            # restava fermo sulla mappa per tutto il turno successivo
            q = self.piste[e.driver_id]
            q.fuori = True
            q.fase_uscita = self.phase
            q.stato = "finito"
            q.quota = 0.0
            q.restanti = 0
            q.live = [0.0, 0.0, 0.0]
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
