"""L'E-Prix: la gara di Formula E, vista da dentro.

E' un'altra corsa, non la Formula 1 in piccolo, e il motivo sta tutto in una
riga di regolamento: la gara dura quarantacinque minuti e l'energia e' contata.
Da li' viene tutto il resto.

  * Non si corre un numero di giri: si corre un tempo, piu' un giro. Quanti
    giri vengono fuori dipende da quanto forte si va, e andare piu' forte vuol
    dire farne di piu' con la stessa energia in cassa. E' il rovescio esatto
    della Formula 1, dove i giri sono scritti e l'unica cosa che conta e' il
    tempo sul giro.
  * L'energia e' una sola: cinquantacinque chilowattora, e devono bastare. Non
    ci sono gomme da scegliere ne' benzina da caricare - una mescola sola e un
    serbatoio elettrico - e quindi la gara e' un problema di gestione e basta.
    Chi spinge dall'inizio arriva in fondo a piedi.
  * L'Attack Mode non e' un pulsante: per prenderlo bisogna passare fuori
    dalla traiettoria, in un punto stabilito, e quel passaggio costa tempo
    subito per averne dopo. Otto minuti in tutto, in due o tre attivazioni, e
    vanno usati: quello che avanza e' buttato.
  * Il Pit Boost e' una ricarica rapida obbligatoria, ma solo con la batteria
    fra il quaranta e il sessanta per cento. Non e' una sosta che si sceglie
    quando si vuole: e' una finestra, e ci si arriva dentro gestendo.
  * E la neutralizzazione, invece di regalare tempo come in Formula 1, toglie
    un chilowattora al minuto a tutti. Una safety car lunga trasforma la gara
    in una corsa al risparmio.

Il muretto e' lo stesso della Formula 1 - gli stessi cinque ordini al pilota,
la stessa possibilita' di lasciare tutto al Team Principal - perche' e' lo
stesso mestiere: si guarda cosa resta in cassa e si decide chi spende e quando.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..core import formulae as FE
from . import muretto as MU
from .weekend import Weather, follow_gap

# ------------------------------------------------------------------ costanti
# Quanto vale, sul giro, un punto di valutazione del pilota. In Formula E pesa
# piu' che in Formula 1: le monoposto sono quasi uguali e la gestione la fa lui.
PILOTA_S = 0.055
# Il passo: 0.90 conserva, 1.10 spinge. Costa e rende meno che in Formula 1
# perche' li' si guadagna col carico aerodinamico, qui col piede destro.
PASSO_S = 6.0
PASSO_MIN = 0.86
PASSO_MAX = 1.12
# Quanto consuma in piu' chi spinge. L'esponente e' alto: e' quello che rende
# impossibile fare tutta la gara col piede giu', ed e' il cuore del campionato.
CONSUMO_ESP = 2.8
# Quanta energia si riprende frenando, in quota di quella spesa. La GEN4 ne
# recupera quasi meta' in una gara, ed e' il numero che rende il conto fattibile.
RECUPERO = 0.46
# E quanto ne recupera in piu' chi ci sa fare: alzare il piede nel punto giusto
# e frenare forte dove si puo' e' un mestiere, e separa i piloti veri dagli altri
RECUPERO_MANO = 0.14
# Aria sporca: seguire costa, ma molto meno che in Formula 1 - queste macchine
# hanno poco carico e la scia aiuta piu' di quanto l'aria sporca tolga
ARIA_SPORCA_S = 0.18
SCIA = 0.10                # e quanto si guadagna stando dietro, in secondi
# Quanto si riesce a passare stando semplicemente attaccati, senza avere il
# passo. In Formula 1 e' quasi zero; qui e' la maggior parte dei sorpassi.
SCIA_PASSA = 0.42
# Attack Mode: quanto costa prenderlo e quanto rende mentre e' acceso
ATTACK_COSTO = 1.4         # secondi persi nel giro in cui si passa nella zona
ATTACK_GUADAGNO = 1.9      # secondi al giro guadagnati mentre e' attivo
ATTACK_SORPASSO = 0.85     # quanto pesa sul tentativo di passare
# Pit Boost: il tempo fermi, oltre alla perdita della corsia
BOOST_S = 30.0
# Duelli. Qui si passa molto piu' che in Formula 1, e non di poco: nel Monaco
# di Formula E del 2023 si sono contati centosedici sorpassi, sullo stesso
# tracciato dove un gran premio ne produce cinque. Le ragioni sono tre e sono
# tutte di regolamento: le macchine sono quasi uguali, non c'e' l'aria sporca
# che impedisce di stare attaccati, e soprattutto ognuno spende la sua energia
# quando vuole - chi risparmia adesso si fa passare adesso, e ripassa dopo.
TENTATIVI_GIRO = 4
ATTESA_ZONA = 3.5
INGAGGIO_MINIMO = 0.45
SOGLIA_ZONA = 0.10
SOGLIA_SCARSA = 0.62
FORZA_SORPASSO = 0.60
TETTO_BASE = 0.10
TETTO_PISTA = 0.50
VANTAGGIO_ENERGIA = 1.10   # avere piu' energia dell'altro conta piu' che in F1
COSTO_SORPASSO = 0.09      # e passare la spende: kWh
# Contatti e rotture. In Formula E si tocca parecchio - muri vicini, gruppo
# compatto - ma si rompe poco: le macchine sono uguali e affidabili
RISCHIO_CONTATTO = 0.045
RISCHIO_ROTTURA = 0.0045
SC_DA_CONTATTO = 0.18


def _kwh_riferimento(reg: dict) -> float:
    return float((reg.get("tecnico") or {}).get("batteria_kwh", 55.0))


@dataclass
class Corridore:
    """Una macchina in gara. Molti nomi sono quelli della Formula 1 apposta:
    il tabellone e il muretto sono gli stessi, e devono poterla leggere."""
    driver_id: str
    team_id: str
    code: str
    name: str
    colour: tuple
    number: int
    squadra: str = ""              # come si chiama la squadra in Formula E

    base_lap: float = 80.0
    skill: float = 80.0
    consistency: float = 80.0
    racecraft: float = 80.0
    aggression: float = 70.0
    estro: float = 60.0
    wet_skill: float = 80.0
    tyre_skill: float = 80.0       # qui e' la mano sull'energia
    strategy_skill: float = 75.0
    reliability: float = 0.97

    # stato in gara
    dist: float = 0.0
    lap: int = 0
    position: int = 1
    total_time: float = 0.0
    last_lap: float = 80.0
    giro_scorso: float = 0.0
    best_lap: float = 999.0
    lap_t0: float = 0.0
    clean_lap: float = 80.0
    dirty_air: float = 0.0
    status: str = "running"        # running | pitting | retired | finished
    dnf_reason: str = ""
    pit_timer: float = 0.0
    stops: int = 0
    damage: float = 0.0
    push_mode: float = 1.0
    passo_manuale: float | None = None
    # l'energia, che qui e' l'unica cosa che conta
    energia: float = 55.0
    energia_max: float = 55.0
    consumo_giro: float = 1.0      # quanta ne beve al giro al passo di adesso
    # l'Attack Mode
    attack_resta: float = 480.0    # secondi ancora disponibili
    attack_usi: int = 0            # quante attivazioni gia' fatte
    attack_attivo: float = 0.0     # secondi ancora accesi
    attack_chiesto: bool = False   # lo prende al prossimo passaggio nella zona
    # il Pit Boost
    boost_fatto: bool = False
    boost_chiesto: bool = False
    # il muretto
    # il piano energia: e' la cosa che in Formula E decide le gare. Chi
    # risparmia all'inizio va piano quando gli altri spingono e si ritrova
    # dietro, e poi negli ultimi giri ha in cassa quello che gli altri hanno
    # gia' speso. E' il motivo per cui li' l'ordine cambia dieci volte.
    piano: str = "piatto"          # presto | piatto | tardi
    ordine: str = "libero"
    ordine_da: int = -99
    delegato: bool = False
    domanda: dict = None
    domanda_cd: int = -99
    overtake_cd: float = 0.0
    tentativi_giro: int = 0
    bloccato_da: str = ""
    bloccato_giri: int = 0
    tieni_posizioni: bool = False
    scambio_a: str = ""
    scambio_giro: int = 0
    scambio_rifiuto: bool = False
    confidence: float = 65.0
    grid: int = 1
    is_player: bool = False
    finished_time: float = 0.0
    laps_led: int = 0

    def carica(self) -> float:
        """Quanta batteria resta, da 0 a 1: e' il numero che guarda il muretto."""
        return max(0.0, min(1.0, self.energia / max(0.1, self.energia_max)))

    def lap_fraction(self, track_len: float) -> float:
        return (self.dist % track_len) / track_len


class EPrix:
    """Una gara di Formula E, dal via alla bandiera."""

    def __init__(self, gs, track, corridori: list, weather: Weather,
                 formato: str = "eprix", rng: random.Random | None = None):
        self.gs = gs
        self.track = track
        self.entrants = corridori
        self.weather = weather
        self.rng = rng or random.Random()
        self.reg = FE.corrente()
        f = (self.reg.get("formati") or {}).get(formato, {})
        self.formato = formato
        self.durata = float(f.get("durata_min", 45)) * 60.0
        self.col_boost = bool(f.get("pit_boost", False))
        self.time = 0.0
        self.track_len = track.length_km * 1000.0
        self.follow = follow_gap(track)
        self.safety_car = 0.0
        self.vsc = False
        self.sc_conta = 0
        self.events: list = []
        self.radio: list = []
        self.classification: list = []
        self.finished = False
        self.ultimo_giro = False       # scattato il "piu' un giro"
        self.leader_lap = 0
        self.best_lap = 0.0
        self.best_lap_by = ""
        self.perdita_box = float(track.pit_loss)
        self._radio_cd: dict = {}
        self._pos_prima: dict = {}
        self._coda = list(corridori)
        # l'Attack Mode di questa gara: quante attivazioni e quanto lunghe. Lo
        # decide la FIA un'ora prima, circuito per circuito, e qui si fa uguale
        am = self.reg.get("attack_mode") or {}
        quante = list(am.get("attivazioni") or [2, 3])
        self.attack_usi_max = self.rng.randint(min(quante), max(quante))
        self.attack_totale = float(am.get("minuti_totali", 8)) * 60.0
        self.attack_durata = self.attack_totale / max(1, self.attack_usi_max)
        self.attack_vietato_giri = int(am.get("vietato_primi_giri", 2))
        pb = self.reg.get("pit_boost") or {}
        self.boost_kwh = float(pb.get("energia_kwh", 5.5))
        self.boost_min = float(pb.get("carica_min", 0.40))
        self.boost_max = float(pb.get("carica_max", 0.60))
        self.penale_sc = float((self.reg.get("energia") or {})
                               .get("penale_neutralizzazione_kwh_min", 1.0))
        for e in self.entrants:
            e.attack_resta = self.attack_totale
            # il piano energia di ognuno. Risparmiare prima per spendere dopo e'
            # la mossa che vince le gare di Formula E, e non la fanno tutti: ci
            # vuole un muretto che se la senta e un pilota che sappia stare
            # dietro senza innervosirsi
            r = self.rng.random()
            bravura = (e.strategy_skill - 60.0) / 60.0
            if r < 0.28 + 0.22 * bravura:
                e.piano = "tardi"
            elif r < 0.50:
                e.piano = "presto"
            else:
                e.piano = "piatto"
        # quanta energia serve al giro per arrivare in fondo: e' il numero
        # attorno al quale gira tutta la gara
        self.giri_previsti = max(10, int(self.durata / self._giro_base()) + 1)
        self.kwh_giro = self._kwh_giro()
        for e in self.entrants:
            e.consumo_giro = self.kwh_giro

    # ------------------------------------------------------------- utilita'
    # la forbice del passo, che il muretto legge da qui
    PASSO_MIN = PASSO_MIN
    PASSO_MAX = PASSO_MAX

    def _giro_base(self) -> float:
        return float(getattr(self.track, "ref_lap", 80.0))

    # Quanto margine si lascia il regolamento fra l'energia che c'e' e quella
    # che serve. E' poco di proposito: in Formula E si arriva al traguardo con
    # la batteria quasi vuota, e chi ne porta a casa troppa ha corso piano.
    MARGINE = 1.02

    def _kwh_giro(self) -> float:
        """Quanta energia si puo' spendere per giro, per arrivare in fondo.

        E' il conto del muretto, ed e' quello che rende la Formula E quello che
        e': tutta l'energia che si avra' - quella in cassa piu' quella del Pit
        Boost - divisa per i giri che si faranno. Il recupero in frenata sta
        gia' dentro a questo numero, perche' quello che svuota la batteria e' il
        saldo fra quello che si spende e quello che si riprende. Chi va sopra
        non arriva, e non e' un modo di dire: resta a piedi davvero.
        """
        totale = _kwh_riferimento(self.reg) + (self.boost_kwh if self.col_boost else 0.0)
        return totale / max(1.0, self.giri_previsti * self.MARGINE)

    def log(self, testo: str, tipo: str = "info") -> None:
        self.events.insert(0, {"lap": self.leader_lap + 1, "text": testo, "kind": tipo})
        del self.events[60:]

    def radio_say(self, e, testo: str, chi: str = "pilota") -> None:
        if not e.is_player:
            return
        self.radio.insert(0, {"driver_id": e.driver_id, "code": e.code, "chi": chi,
                              "text": testo, "lap": e.lap + 1, "t": self.time})
        del self.radio[12:]

    def radio_of(self, driver_id: str):
        for m in self.radio:
            if m["driver_id"] == driver_id:
                return m
        return None

    def order(self) -> list:
        """L'ordine sul tabellone: chi ha finito nell'ordine in cui ha finito."""
        finiti = [e for e in self.entrants if e.status == "finished"]
        finiti.sort(key=lambda e: e.finished_time)
        vivi = [e for e in self.entrants if e.status == "running" or e.status == "pitting"]
        vivi.sort(key=lambda e: -e.dist)
        fuori = [e for e in self.entrants if e.status == "retired"]
        fuori.sort(key=lambda e: -e.dist)
        return finiti + vivi + fuori

    def tempo_restante(self) -> float:
        return max(0.0, self.durata - self.time)

    def speed_of(self, e) -> float:
        if e.status == "pitting":
            return 60.0
        if e.status == "retired":
            return 0.0
        v = self.track.speed_at(e.lap_fraction(self.track_len)) \
            if hasattr(self.track, "speed_at") else 150.0
        return v * 0.82        # una Formula E va piu' piano di una Formula 1

    def zone_of(self, e) -> str:
        if e.status == "pitting":
            return "box"
        return self.track.zone_at(e.lap_fraction(self.track_len))

    # -------------------------------------------------------- tempo sul giro
    def lap_time_of(self, e: Corridore) -> float:
        """Quanto ci mette a fare un giro, adesso.

        Non c'e' gomma che si consuma ne' benzina che si svuota: quello che
        muove il cronometro qui e' il piede destro e l'Attack Mode. E' un
        modello piu' semplice di quello della Formula 1 perche' la macchina e'
        piu' semplice - una mescola, una batteria, nessuna aerodinamica da
        regolare - e perche' quello che decide la gara sta altrove.
        """
        t = e.base_lap
        t += (85.0 - e.skill) * PILOTA_S * float(getattr(self.track, "pilota_rel", 1.0))
        t -= (max(PASSO_MIN, min(PASSO_MAX, e.push_mode)) - 1.0) * PASSO_S
        if e.attack_attivo > 0:
            t -= ATTACK_GUADAGNO
        t += e.damage * 0.05
        # l'aria di quello davanti: toglie poco, e la scia sul dritto ne
        # restituisce quasi altrettanto. E' per questo che qui si sta attaccati
        t += e.dirty_air * ARIA_SPORCA_S - e.dirty_air * SCIA
        # la batteria vuota non e' un modo di dire: sotto il cinque per cento
        # la potenza cala e si va a passo di trasferimento
        if e.carica() < 0.05:
            t += 6.0 * (1.0 - e.carica() / 0.05)
        # l'acqua
        bagnato = float(self.weather.wet)
        if bagnato > 0.02:
            t += bagnato * 12.0 * (1.0 + (80.0 - e.wet_skill) / 120.0)
        if self.safety_car > 0:
            t *= 1.45 if not self.vsc else 1.28
        t *= 1.0 + self.rng.gauss(0.0, (100.0 - e.consistency) * 0.00012)
        return max(20.0, t)

    def consumo_di(self, e: Corridore) -> float:
        """Quanti chilowattora beve in un giro, al passo di adesso."""
        base = self.kwh_giro * (max(PASSO_MIN, min(PASSO_MAX, e.push_mode)) ** CONSUMO_ESP)
        if e.attack_attivo > 0:
            base *= 1.22           # seicento kilowatt costano
        # chi ci sa fare recupera di piu' in frenata, e quindi consuma di meno
        mano = RECUPERO_MANO * (e.tyre_skill - 75.0) / 100.0
        base *= 1.0 - mano
        if self.safety_car > 0:
            base *= 0.35
        return max(0.05, base)

    def consumo_riferimento(self, e: Corridore) -> float:
        """Quanto berrebbe a gara lanciata, che e' il numero su cui si fa il conto.

        Sotto safety car si consuma un terzo, e usare quello per dire di quanti
        giri si e' avanti farebbe leggere al muretto che ce n'e' d'avanzo per
        ottanta giri. Il conto si fa sempre sul passo di gara.
        """
        vero, self.safety_car = self.safety_car, 0.0
        try:
            return self.consumo_di(e)
        finally:
            self.safety_car = vero

    def margine_energia(self, e: Corridore) -> float:
        """Di quanti giri si e' avanti o indietro sul bisogno.

        E' il numero che il muretto guarda per tutta la gara: sopra lo zero c'e'
        da spendere, sotto si deve alzare il piede. In Formula E e' l'unico
        numero che conta davvero.
        """
        restano = self.giri_restanti(e)
        if restano <= 0:
            return 9.9
        # dentro al conto ci va anche il Pit Boost, se si deve ancora fare:
        # quei chilowattora sono gia' nostri, e senza contarli il numero direbbe
        # a tutti che non arrivano quando invece arrivano
        in_cassa = e.energia
        if self.col_boost and not e.boost_fatto:
            in_cassa += self.boost_kwh
        return in_cassa / max(0.01, self.consumo_riferimento(e)) - restano

    def giri_restanti(self, e: Corridore) -> int:
        """Quanti giri mancano, stimati sul tempo che resta."""
        if self.ultimo_giro:
            return 1
        # e il giro su cui si conta e' quello di gara, non quello dietro alla
        # safety car: se no, neutralizzando, il muretto crede che manchi meta'
        giro = e.base_lap if self.safety_car > 0 else (e.last_lap or e.base_lap)
        return max(1, int(round(self.tempo_restante() / max(20.0, giro))) + 1)

    def passo_necessario(self, e: Corridore) -> float:
        """Il passo massimo con cui l'energia arriva in fondo."""
        restano = self.giri_restanti(e)
        if restano <= 1:
            return PASSO_MAX
        serve = e.energia / restano
        base = self.kwh_giro * (1.0 - RECUPERO_MANO * (e.tyre_skill - 75.0) / 100.0)
        return max(PASSO_MIN, min(PASSO_MAX, (serve / max(0.01, base)) ** (1.0 / CONSUMO_ESP)))

    # ---------------------------------------------------------- il muretto
    def scegli_passo(self, e: Corridore) -> None:
        """Che passo tiene, adesso.

        La regola e' quella vera e non e' complicata: si spende quello che c'e'
        e non un chilowattora di piu'. Chi risparmia piu' del necessario regala
        posizioni, chi risparmia meno arriva a piedi.
        """
        if e.passo_manuale is not None and not e.delegato:
            e.push_mode = e.passo_manuale
            return
        tetto = self.passo_necessario(e)
        margine = self.margine_energia(e)
        restano = self.giri_restanti(e)
        # il piano energia: dove si mette la roba buona. Non cambia quanta
        # energia si ha, cambia quando la si spende, ed e' esattamente per
        # questo che in Formula E l'ordine si rimescola per tutta la gara
        avanti_gara = 1.0 - restano / max(1.0, self.giri_previsti)
        if e.piano == "tardi":
            voluto = 0.95 if avanti_gara < 0.62 else PASSO_MAX
        elif e.piano == "presto":
            voluto = PASSO_MAX if avanti_gara < 0.45 else 0.95
        else:
            voluto = 1.0
        if tetto < 1.0:
            e.push_mode = tetto                     # non basta: si stringe
        elif margine > 1.2 or restano <= 3:
            # ce n'e' d'avanzo, o e' finita: quello che resta in cassa al
            # traguardo non serve a niente
            e.push_mode = min(PASSO_MAX, tetto)
        else:
            e.push_mode = min(voluto, tetto)
        MU.applica_passo(self, e)

    def attack_disponibile(self, e: Corridore) -> bool:
        """Se adesso l'Attack Mode si puo' prendere."""
        return (e.attack_resta > 1.0 and e.attack_attivo <= 0
                and e.attack_usi < self.attack_usi_max
                and e.lap >= self.attack_vietato_giri
                and self.safety_car <= 0 and e.status == "running")

    def chiedi_attack(self, e: Corridore) -> bool:
        """Il muretto lo chiede: si prendera' al prossimo passaggio nella zona."""
        if not self.attack_disponibile(e):
            return False
        e.attack_chiesto = True
        self.radio_say(e, "Attack Mode al prossimo passaggio, vai largo.", "muretto")
        return True

    def _prendi_attack(self, e: Corridore, lt: float) -> None:
        """Il passaggio fuori traiettoria: costa tempo adesso per averne dopo."""
        durata = min(e.attack_resta, self.attack_durata)
        e.attack_attivo = durata
        e.attack_resta -= durata
        e.attack_usi += 1
        e.attack_chiesto = False
        # il tempo perso passando largo si paga subito, sul posto
        e.dist -= ATTACK_COSTO * (self.track_len / max(20.0, lt))
        self.log(f"{e.name} prende l'Attack Mode ({durata / 60:.0f}')", "attack")
        self.radio_say(e, f"Attack Mode attivo: {durata:.0f} secondi.", "muretto")

    def _ai_attack(self, e: Corridore) -> None:
        """Quando lo prende chi non e' guidato dal giocatore.

        La regola del muretto vero: si prende quando serve - c'e' qualcuno da
        prendere o da tenere dietro - e comunque prima che la gara finisca,
        perche' quello che avanza e' buttato. Chi sta al muretto bravo lo usa
        dove rende, chi non lo e' lo brucia in aria libera.
        """
        if e.is_player and not e.delegato:
            return
        if not self.attack_disponibile(e) or e.attack_chiesto:
            return
        # quello che avanza e' buttato: quando il tempo che resta basta appena
        # per spendere l'Attack Mode che si ha in mano, si prende e basta
        deve = self.tempo_restante() < e.attack_resta * 1.7
        avanti = self._chi_davanti(e)
        dietro = self._chi_dietro(e)
        ga = self._gap_s(avanti, e) if avanti else 99.0
        gd = self._gap_s(e, dietro) if dietro else 99.0
        utile = (ga < 1.5) or (gd < 1.0)
        if not (deve or utile):
            return
        # e ci vuole anche l'energia per spenderla: prenderlo a secco e' regalarlo
        if self.margine_energia(e) < -0.4 and not deve:
            return
        if self.rng.random() > 0.25 + 0.0070 * e.strategy_skill:
            return
        self.chiedi_attack(e)

    # ---------------------------------------------------------- il Pit Boost
    def finestra_boost(self, e: Corridore) -> bool:
        """Se adesso la batteria e' nella finestra in cui si puo' ricaricare."""
        return self.boost_min <= e.carica() <= self.boost_max

    def chiedi_boost(self, e: Corridore) -> bool:
        if not self.col_boost or e.boost_fatto or e.status != "running":
            return False
        e.boost_chiesto = True
        self.radio_say(e, "Box per il Pit Boost quando siamo in finestra.", "muretto")
        return True

    def _ai_boost(self, e: Corridore) -> None:
        """Il Pit Boost e' obbligatorio: chi non lo fa e' squalificato.

        Quindi non e' se farlo, e' quando. La finestra e' stretta - batteria fra
        il quaranta e il sessanta per cento - e chi ci arriva dentro al momento
        giusto lo fa perdendo poco, chi ci arriva male lo fa buttando la gara.
        """
        if not self.col_boost or e.boost_fatto or e.boost_chiesto:
            return
        if e.is_player and not e.delegato:
            return
        if not self.finestra_boost(e):
            return
        # sotto safety car costa molto meno, come sempre
        if self.safety_car > 0:
            e.boost_chiesto = True
            return
        # altrimenti si entra quando la finestra sta per chiudersi, o quando il
        # muretto vede che conviene
        stretta = e.carica() < self.boost_min + 0.06
        if stretta or self.rng.random() < 0.10 + 0.0025 * e.strategy_skill:
            e.boost_chiesto = True

    def _fai_boost(self, e: Corridore) -> None:
        e.status = "pitting"
        perdita = self.perdita_box * (0.55 if self.safety_car > 0 else 1.0)
        e.pit_timer = BOOST_S + perdita
        e.energia = min(e.energia_max, e.energia + self.boost_kwh)
        e.boost_fatto = True
        e.boost_chiesto = False
        e.stops += 1
        self.log(f"{e.name}: Pit Boost, +{self.boost_kwh:.1f} kWh", "pit")
        self.radio_say(e, f"Boost fatto: {e.carica() * 100:.0f} per cento in cassa.",
                       "muretto")

    # ------------------------------------------------------------- vicinato
    def _chi_davanti(self, e):
        avanti = [x for x in self.entrants if x.status == "running" and x.dist > e.dist]
        return min(avanti, key=lambda x: x.dist - e.dist) if avanti else None

    def _chi_dietro(self, e):
        dietro = [x for x in self.entrants if x.status == "running" and x.dist < e.dist]
        return max(dietro, key=lambda x: x.dist) if dietro else None

    def _gap_s(self, a, b) -> float:
        if a is None or b is None:
            return 99.0
        metri_s = max(15.0, self.track_len / max(20.0, b.last_lap or b.base_lap))
        return (a.dist - b.dist) / metri_s

    # ------------------------------------------------------------ il passo
    def update(self, dt: float) -> None:
        if self.finished:
            return
        if self.classification and all(x.status in ("finished", "retired")
                                       for x in self.entrants):
            self.finished = True
            return
        self.time += dt
        if self.safety_car > 0:
            self.safety_car = max(0.0, self.safety_car - dt)
            # la neutralizzazione non regala tempo: toglie energia a tutti,
            # ed e' la differenza piu' grossa con la Formula 1
            via = self.penale_sc * dt / 60.0
            for e in self.entrants:
                if e.status == "running":
                    e.energia = max(0.0, e.energia - via)
            if self.safety_car == 0.0:
                self.log("Si riparte.", "sc")
                self.vsc = False

        for e in self.entrants:
            if e.status in ("retired", "finished"):
                continue
            if e.status == "pitting":
                e.pit_timer -= dt
                e.total_time += dt
                if e.pit_timer <= 0:
                    e.status = "running"
                continue
            lt = self.lap_time_of(e)
            e.last_lap = lt
            e.clean_lap = lt - e.dirty_air * (ARIA_SPORCA_S - SCIA)
            e.dist += (self.track_len / lt) * dt
            e.total_time += dt
            e.overtake_cd = max(0.0, e.overtake_cd - dt)
            if e.attack_attivo > 0:
                e.attack_attivo = max(0.0, e.attack_attivo - dt)
                if e.attack_attivo == 0.0:
                    self.radio_say(e, "Attack Mode finito.", "muretto")
            e.energia = max(0.0, e.energia - self.consumo_di(e) * dt / lt)
            e.consumo_giro = self.consumo_di(e)
            nuovo = int(e.dist // self.track_len)
            if nuovo > e.lap:
                e.lap = nuovo
                self._giro_chiuso(e, lt)

        self._coda_dietro()
        self._duelli(dt)
        self._posizioni()
        self._forse_incidente(dt)
        self._coda = [e for e in self.entrants if e.status == "running"]
        self._coda.sort(key=lambda e: -e.dist)
        # la bandiera: scaduto il tempo, chi passa dal traguardo comincia
        # l'ultimo giro. E' il "piu' un giro" del regolamento
        if not self.ultimo_giro and self.time >= self.durata:
            self.ultimo_giro = True
            self.log("Tempo scaduto: ultimo giro!", "flag")

    def _giro_chiuso(self, e: Corridore, lt: float) -> None:
        giro = e.total_time - e.lap_t0
        e.lap_t0 = e.total_time
        if giro > 20.0:
            e.giro_scorso = giro
            if giro < e.best_lap:
                e.best_lap = giro
            if self.best_lap <= 0 or giro < self.best_lap:
                self.best_lap, self.best_lap_by = giro, e.code
        self.leader_lap = max(self.leader_lap, e.lap)
        e.tentativi_giro = 0
        if e.position == 1:
            e.laps_led += 1
        # il passaggio nella zona dell'Attack Mode, se l'hanno chiesto
        if e.attack_chiesto and self.attack_disponibile(e):
            self._prendi_attack(e, lt)
        # il muretto guarda i conti una volta a giro, come si fa davvero
        avanti, dietro = self._chi_davanti(e), self._chi_dietro(e)
        ga = self._gap_s(avanti, e) if avanti else 99.0
        gd = self._gap_s(e, dietro) if dietro else 99.0
        MU.ai_ordine(self, e, avanti, dietro, ga, gd)
        self.scegli_passo(e)
        self._ai_attack(e)
        self._ai_boost(e)
        self._parla(e, giro, avanti, dietro, ga, gd)
        if e.boost_chiesto and (self.finestra_boost(e) or e.carica() < self.boost_min):
            self._fai_boost(e)
            return
        self._forse_rottura(e)
        # e la fine: il tempo e' scaduto e questo era l'ultimo giro
        if self.ultimo_giro and e.lap > self.leader_lap - 1 and self.time >= self.durata:
            self._taglia(e)

    def _taglia(self, e: Corridore) -> None:
        e.status = "finished"
        e.finished_time = e.total_time
        e.position = len(self.classification) + 1
        if not self.classification:
            self.log(f"BANDIERA A SCACCHI: vince {e.name}!", "flag")
        # il Pit Boost e' obbligatorio: chi non l'ha fatto non e' classificato
        if self.col_boost and not e.boost_fatto:
            e.finished_time += 600.0
            self.log(f"{e.name} non ha fatto il Pit Boost: penalita'", "pen")
        self.classification.append(e)
        if all(x.status in ("finished", "retired") for x in self.entrants):
            self.finished = True

    def _posizioni(self) -> None:
        for i, e in enumerate(self.order(), 1):
            e.position = i

    def _coda_dietro(self) -> None:
        coda = [e for e in self._coda if e.status == "running"]
        for i in range(1, len(coda)):
            davanti, dietro = coda[i - 1], coda[i]
            limite = davanti.dist - self.follow
            if dietro.dist > limite:
                dietro.dist = limite

    # ------------------------------------------------------------- i duelli
    def _duelli(self, dt: float) -> None:
        """Chi sta dietro prova a passare.

        Il conto e' quello della Formula 1, con due differenze che vengono dal
        regolamento: qui pesa moltissimo quanta energia si ha in piu' dell'altro
        - e' l'unica cosa che si puo' spendere - e chi ha l'Attack Mode acceso
        ha centocinquanta kilowatt in piu' per otto minuti, che sul dritto non
        si tengono dietro in nessun modo.
        """
        vivi = [e for e in self.entrants if e.status == "running"]
        vivi.sort(key=lambda e: -e.dist)
        ot = float(self.track.traits.get("overtaking", 0.5))
        for i in range(1, len(vivi)):
            davanti, dietro = vivi[i - 1], vivi[i]
            gap_m = davanti.dist - dietro.dist
            if gap_m > self.follow * 2.4 or gap_m < 0:
                dietro.dirty_air = max(0.0, dietro.dirty_air - dt * 1.5)
                dietro.bloccato_da = ""
                continue
            if davanti.team_id == dietro.team_id:
                # "lascialo passare", quando il pilota ha deciso di farlo
                if MU.scambio_pronto(self, davanti, dietro):
                    MU.chiudi_scambio(davanti)
                    davanti.dist, dietro.dist = dietro.dist, davanti.dist
                    self.log(f"Ordine di squadra: {davanti.code} lascia passare "
                             f"{dietro.code}", "team")
                    self.radio_say(davanti, f"Fatto, {dietro.code} e' passato.",
                                   "pilota")
                    continue
                # e "tenete le posizioni": fra le nostre due non si combatte
                if davanti.tieni_posizioni and dietro.tieni_posizioni:
                    continue
            dietro.dirty_air = min(1.0, dietro.dirty_air + dt * 0.9)
            if dietro.bloccato_da == davanti.driver_id:
                pass
            else:
                dietro.bloccato_da = davanti.driver_id
                dietro.bloccato_giri = 0
            if self.safety_car > 0 or dietro.overtake_cd > 0 \
                    or gap_m > self.follow * 1.25:
                continue
            if dietro.tentativi_giro >= MU.tentativi(dietro, TENTATIVI_GIRO):
                continue
            posto = self.track.zona_di(dietro.lap_fraction(self.track_len))
            if posto <= 0.0:
                continue
            if self.rng.random() > INGAGGIO_MINIMO + (1.0 - INGAGGIO_MINIMO) * posto:
                continue
            dietro.overtake_cd = ATTESA_ZONA
            dietro.tentativi_giro += 1
            vantaggio = davanti.clean_lap - dietro.clean_lap + self.rng.gauss(0.0, 0.25)
            # l'Attack Mode: centocinquanta kilowatt in piu' non sono un
            # dettaglio, e sono la ragione per cui in Formula E si passa
            if dietro.attack_attivo > 0 and davanti.attack_attivo <= 0:
                vantaggio += ATTACK_GUADAGNO
            elif davanti.attack_attivo > 0 and dietro.attack_attivo <= 0:
                vantaggio -= ATTACK_GUADAGNO
            soglia = SOGLIA_ZONA + SOGLIA_SCARSA * (1.0 - posto)
            p = max(0.0, (vantaggio - 0.35 * soglia) / soglia) * FORZA_SORPASSO
            # e qui sta la differenza vera con la Formula 1: in Formula E si
            # passa anche senza andare piu' forte. Non c'e' l'aria sporca che
            # ti stacca, la scia su questi rettilinei vale mezzo secondo, e
            # dietro si arriva sempre. Chi sta davanti deve difendersi a ogni
            # staccata, non solo quando l'altro ha il passo
            p = max(p, SCIA_PASSA * posto)
            # e chi ha piu' energia in cassa arriva in fondo al dritto con
            # qualcosa da spendere, e l'altro lo sa
            piu = (dietro.energia - davanti.energia) / max(1.0, dietro.energia_max)
            p *= 1.0 + VANTAGGIO_ENERGIA * max(-0.4, min(0.4, piu))
            p *= 0.20 + 0.80 * ot
            p *= 0.70 + 0.60 * (dietro.racecraft / 100.0)
            p *= 0.85 + 0.35 * (dietro.aggression / 100.0)
            p /= max(0.60, 0.65 + 0.55 * (davanti.racecraft / 100.0))
            p *= 0.82 + 0.36 * (dietro.estro / 100.0)
            p *= 1.0 + 0.45 * float(self.weather.wet)
            p *= MU.di(dietro)["attacco"]
            p /= max(0.60, MU.di(davanti)["difesa"])
            if self.rng.random() >= min(TETTO_BASE + TETTO_PISTA * ot, p):
                continue
            dietro.dist, davanti.dist = davanti.dist + 6.0, davanti.dist - self.follow * 0.6
            dietro.energia = max(0.0, dietro.energia - COSTO_SORPASSO)
            dietro.overtake_cd = max(20.0, dietro.last_lap * 1.1)
            davanti.overtake_cd = 6.0
            self.log(f"SORPASSO: {dietro.name} passa {davanti.name}", "pass")
            if self.rng.random() < (RISCHIO_CONTATTO * (dietro.aggression / 100.0)
                                    * (1.0 + self.weather.wet) * MU.rischio(dietro)):
                danno = self.rng.uniform(5, 28)
                dietro.damage = min(100.0, dietro.damage + danno)
                davanti.damage = min(100.0, davanti.damage + danno * 0.8)
                self.log(f"Contatto tra {dietro.name} e {davanti.name}!", "warn")
                for x, quota in ((dietro, 0.26), (davanti, 0.20)):
                    if danno > 18 and x.status == "running" and self.rng.random() < quota:
                        x.status = "retired"
                        x.dnf_reason = "danni da contatto"
                        self.log(f"RITIRO: {x.name} - danni da contatto", "dnf")
                self._forse_sc(SC_DA_CONTATTO)

    def _forse_rottura(self, e: Corridore) -> None:
        """Le monoposto di Formula E si rompono poco: sono quasi tutte uguali."""
        rischio = (1.0 - e.reliability) * RISCHIO_ROTTURA * (1.0 + e.damage / 70.0)
        if self.rng.random() < rischio:
            e.status = "retired"
            e.dnf_reason = self.rng.choice(
                ["problema all'inverter", "guasto al software", "surriscaldamento",
                 "perdita di potenza", "rottura sospensione"])
            self.log(f"RITIRO: {e.name} - {e.dnf_reason}", "dnf")
            self._forse_sc(0.15)

    def _forse_incidente(self, dt: float) -> None:
        """I muri sono vicini: qui la safety car esce piu' spesso che in F1."""
        if self.safety_car > 0:
            return
        base = 0.000052 * (1.0 + 2.2 * self.weather.wet)
        base *= 1.0 + 1.6 * (1.0 - self.track.traits.get("overtaking", 0.5))
        if self.rng.random() < base * dt:
            self._forse_sc(0.55, forzata=True)

    def _forse_sc(self, quota: float, forzata: bool = False) -> None:
        if self.safety_car > 0 or self.ultimo_giro:
            return
        if not forzata and self.rng.random() > quota:
            return
        self.sc_conta += 1
        # meta' delle volte basta la neutralizzazione a distanza
        self.vsc = self.rng.random() < 0.5
        self.safety_car = self.rng.uniform(90.0, 240.0)
        nome = "Full course yellow" if self.vsc else "Safety car in pista"
        self.log(f"{nome}: si perde un chilowattora al minuto.", "sc")

    # -------------------------------------------------------------- la radio
    DOMANDA_ATTESA = 5
    DOMANDA_SCADENZA = 2

    def _parla(self, e: Corridore, giro: float, avanti, dietro,
               ga: float, gd: float) -> None:
        """Quello che si sente alla radio, e quello che il muretto chiede.

        Come in Formula 1, ogni frase esce da un numero che sta succedendo
        davvero. Qui pero' i numeri sono altri: quanta energia resta, quanti
        minuti di Attack Mode ci sono ancora in mano, se la finestra del Boost
        si sta chiudendo.
        """
        if not e.is_player or e.status != "running":
            return
        if e.domanda and e.lap > e.domanda["scadenza"]:
            e.domanda = None
            e.domanda_cd = e.lap
            self.radio_say(e, "Nessuna risposta: faccio come mi sembra.", "pilota")
        # uno scambio chiesto e non eseguito non resta li' per sempre
        if e.scambio_a:
            if e.scambio_rifiuto and e.lap >= e.scambio_giro:
                MU.chiudi_scambio(e)
            elif not e.scambio_rifiuto and e.lap > e.scambio_giro + 6:
                MU.chiudi_scambio(e)
                self.radio_say(e, "Non me lo trovo piu' dietro, lascio stare.",
                               "pilota")
        self._domanda(e, avanti, ga, gd)
        if e.domanda or e.lap < self._radio_cd.get(e.driver_id, -9):
            return
        margine = self.margine_energia(e)
        voci = []
        if e.damage > 25:
            voci.append((9, "pilota", "Ho preso un colpo, la macchina non e' piu' dritta."))
        if margine < -0.8:
            voci.append((9, "muretto", f"Siamo {abs(margine):.1f} giri sotto: alza il "
                                       f"piede, cosi' non arriviamo."))
        elif margine < -0.2:
            voci.append((7, "muretto", "Un filo corti di energia: piu' rilascio in "
                                       "staccata e rientriamo."))
        elif margine > 1.5:
            voci.append((6, "muretto", f"Hai {margine:.1f} giri di energia d'avanzo: "
                                       f"spendila, non serve portarla al traguardo."))
        if self.col_boost and not e.boost_fatto:
            if self.finestra_boost(e):
                voci.append((8, "muretto", f"Siamo in finestra per il Boost: "
                                           f"{e.carica() * 100:.0f} per cento."))
            elif e.carica() < self.boost_min:
                voci.append((10, "muretto", "Finestra del Boost passata, siamo sotto "
                                            "il quaranta: siamo nei guai."))
        if e.attack_attivo > 0:
            voci.append((7, "muretto", f"Attack Mode acceso per altri "
                                       f"{e.attack_attivo:.0f} secondi: adesso."))
        elif self.attack_disponibile(e):
            resta = e.attack_resta / 60.0
            voci.append((6, "muretto", f"Hai ancora {resta:.0f} minuti di Attack Mode "
                                       f"da usare: non ce li portiamo a casa."))
        if 0.1 < ga < 1.0 and avanti is not None:
            voci.append((6, "muretto", f"Sei a {ga:.1f} da {avanti.code}: e' il momento."))
        if 0.1 < gd < 1.0 and dietro is not None:
            voci.append((5, "muretto", f"{dietro.code} e' a {gd:.1f}, ti sta arrivando."))
        if self.safety_car > 0:
            voci.append((7, "muretto", "Neutralizzata: stiamo perdendo un chilowattora "
                                       "al minuto come tutti."))
        if self.ultimo_giro:
            voci.append((8, "muretto", "Ultimo giro, portala a casa."))
        if not voci:
            return
        voci.sort(key=lambda x: -x[0])
        peso, chi, testo = voci[0]
        self.radio_say(e, testo, chi)
        self._radio_cd[e.driver_id] = e.lap + max(2, 9 - peso)

    def _domanda(self, e: Corridore, avanti, ga: float, gd: float) -> None:
        """Quando il pilota alza la radio e chiede cosa fare."""
        if e.domanda or e.delegato or e.status != "running":
            return
        if e.lap < e.domanda_cd + self.DOMANDA_ATTESA or self.giri_restanti(e) <= 2:
            return
        margine = self.margine_energia(e)
        d = None
        if self.col_boost and not e.boost_fatto and self.finestra_boost(e) \
                and e.carica() < self.boost_min + 0.07:
            d = ("boost", "Sono in finestra e sta per chiudersi. Boost adesso?",
                 [("Box, Boost", "boost"), ("Ancora un giro", "niente")])
        elif margine < -0.8:
            d = ("energia", f"Siamo {abs(margine):.1f} giri sotto di energia.",
                 [("Gestisci", "gestisci"), ("Spingo lo stesso", "libero")])
        elif self.attack_disponibile(e) and avanti is not None and ga < 1.6:
            d = ("attack", f"Ho {avanti.code} davanti e l'Attack Mode in mano.",
                 [("Prendilo", "attack"), ("Tienilo", "niente")])
        elif e.damage > 30:
            d = ("danni", "Ho preso un colpo forte, la macchina non e' a posto.",
                 [("Porta a casa", "casa"), ("Vai avanti", "niente")])
        if d is None:
            return
        chiave, testo, opzioni = d
        e.domanda = {"chiave": chiave, "testo": testo, "opzioni": opzioni,
                     "scadenza": e.lap + self.DOMANDA_SCADENZA}
        self.radio_say(e, testo, "pilota")
        self._radio_cd[e.driver_id] = e.lap + 1

    def rispondi(self, driver_id: str, scelta: str) -> str:
        e = next((x for x in self.entrants if x.driver_id == driver_id), None)
        if e is None or not e.domanda:
            return ""
        e.domanda = None
        e.domanda_cd = e.lap
        if scelta in MU.ORDINI:
            e.ordine = scelta
            e.ordine_da = e.lap
            detto = MU.ORDINI[scelta]["radio"]
        elif scelta == "boost":
            self.chiedi_boost(e)
            detto = "Box, Boost."
        elif scelta == "attack":
            self.chiedi_attack(e)
            detto = "Prendilo al prossimo passaggio."
        else:
            detto = "Ricevuto, resta cosi'."
        self.radio_say(e, detto, "muretto")
        return detto

    def fast_forward(self, passo: float = 2.0) -> None:
        """Corre la gara fino in fondo senza guardarla."""
        giri = 0
        while not self.finished and giri < 200000:
            self.update(passo)
            giri += 1


# ------------------------------------------------------------ costruzione
def _colore(gs, team_id: str, squadra: str):
    t = gs.teams.get(team_id)
    if t is not None:
        from ..ui import theme as _T
        try:
            return _T.hex_rgb(t.colour)
        except Exception:
            pass
    # le squadre di Formula E che non sono nostre hanno un colore loro, stabile
    h = abs(hash(squadra)) % 360
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, 0.55, 0.92)
    return (int(r * 255), int(g * 255), int(b * 255))


def costruisci(gs, track, team=None, formato: str = "eprix") -> list:
    """Il campo partenti di un E-Prix: ventidue macchine, undici squadre.

    Non se le inventa qui: sono le stesse ventidue di tutta la stagione, con
    gli stessi nomi e gli stessi valori, prese dal registro del campionato. E'
    quello che fa la differenza fra correre una gara e correre un campionato.
    """
    from ..ui import theme as _T
    reg = FE.corrente()
    e0 = _kwh_riferimento(reg)
    base = float(getattr(track, "ref_lap", 80.0))
    fuori = []
    for n, c in enumerate(FE.campo_di(gs, team), 1):
        nostro = team is not None and FE.ha(team) and c["squadra"] == team.fe_nome
        d = gs.drivers.get(c.get("driver_id") or "")
        forza = float(c["forza"])
        colore = _T.hex_rgb(team.colour) if nostro else _colore(gs, "", c["squadra"])
        codice = (d.code if d is not None
                  else "".join(w[0] for w in c["nome"].split()[:2]).upper()[:3]
                  or c["squadra"][:3].upper())
        fuori.append(Corridore(
            driver_id=c["id"], team_id=(team.id if nostro else f"fe_{c['squadra']}"),
            code=codice, squadra=c["squadra"], name=c["nome"], colour=colore, number=n,
            base_lap=base + (85.0 - forza) * PILOTA_S, skill=forza,
            consistency=float(getattr(d, "consistency", 78.0)) if d else
            min(95.0, forza + gs.rng.uniform(-4, 4)),
            racecraft=float(getattr(d, "racecraft", 78.0)) if d else
            min(95.0, forza + gs.rng.uniform(-4, 4)),
            aggression=float(getattr(d, "aggression", 70.0)) if d else
            gs.rng.uniform(55, 85),
            estro=float(getattr(d, "estro", 60.0)) if d else gs.rng.uniform(45, 85),
            wet_skill=float(getattr(d, "wet_skill", 78.0)) if d else forza,
            tyre_skill=float(getattr(d, "tyre_skill", 78.0)) if d else forza,
            confidence=float(getattr(d, "confidence", 65.0)) if d else 65.0,
            strategy_skill=(float(getattr(team, "strategy_strength", 70.0)) if nostro
                            else forza),
            energia=e0, energia_max=e0, is_player=nostro))
    return fuori


@dataclass
class Duello:
    """Un confronto della qualifica: due piloti, uno passa."""
    a: str = ""
    b: str = ""
    vince: str = ""
    fase: str = ""


def qualifica(gs, track, corridori: list, rng=None) -> dict:
    """La qualifica di Formula E: due gruppi e poi i duelli.

    E' il formato che il pubblico preferisce e che il regolamento non tocca: si
    gira in due gruppi, i primi quattro di ognuno passano, e da li' si va a
    eliminazione diretta uno contro uno fino alla finale. Chi arriva ai duelli
    prende anche punti iridati, dal 2026/27.

    Torna tutto quello che serve a raccontarla, non solo la griglia: i tempi
    dei due gruppi e ogni singolo duello con i due tempi. E' uno spettacolo, e
    fino a ieri lo si calcolava di nascosto.
    """
    rng = rng or gs.rng
    q = (FE.corrente().get("qualifica") or {})
    passano = int(q.get("passano_per_gruppo", 4))
    ordinati = sorted(corridori, key=lambda e: -e.skill)
    gruppi = [ordinati[0::2], ordinati[1::2]]
    tempi = {}
    for g in gruppi:
        for e in g:
            # un giro solo, con la macchina scarica: conta il pilota
            tempi[e.driver_id] = (track.ref_lap - (e.skill - 75.0) * PILOTA_S
                                  + rng.gauss(0.0, 0.35))
    ammessi = []
    tabelle = []
    for g in gruppi:
        g = sorted(g, key=lambda e: tempi[e.driver_id])
        tabelle.append([(e, tempi[e.driver_id]) for e in g])
        ammessi += g[:passano]
    resto = [e for e in corridori if e not in ammessi]
    resto.sort(key=lambda e: tempi[e.driver_id])
    ammessi.sort(key=lambda e: tempi[e.driver_id])
    duelli = []
    turno = list(ammessi)
    perdenti = []
    for fase in ("quarti", "semifinali", "finale"):
        prossimo = []
        for i in range(0, len(turno) - 1, 2):
            a = turno[i]
            b = turno[-(i + 1)] if fase == "quarti" else turno[i + 1]
            ta = tempi[a.driver_id] + rng.gauss(0.0, 0.30)
            tb = tempi[b.driver_id] + rng.gauss(0.0, 0.30)
            vince, perde = (a, b) if ta <= tb else (b, a)
            duelli.append({"fase": fase, "a": a, "b": b, "ta": ta, "tb": tb,
                           "vince": vince.driver_id})
            prossimo.append(vince)
            perdenti.insert(0, perde)
        turno = prossimo
        if len(turno) <= 1:
            break
    griglia = list(turno) + perdenti + resto
    for i, e in enumerate(griglia, 1):
        e.grid = i
        e.dist = -(i - 1) * 7.0
    return {"griglia": griglia, "gruppi": tabelle, "duelli": duelli, "tempi": tempi}


def make_eprix(gs, track, team=None, formato: str = "eprix", weather=None) -> EPrix:
    """Prepara un E-Prix: griglia, meteo, energia in cassa."""
    w = weather or Weather.generate(track, gs.rng)
    corridori = costruisci(gs, track, team, formato)
    q = qualifica(gs, track, corridori)
    sim = EPrix(gs, track, q["griglia"], w, formato=formato, rng=gs.rng)
    sim.qualifica = q
    return sim
