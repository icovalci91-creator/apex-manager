"""Vettura: componenti, usura, assetto e statistiche derivate."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config as C

# Le grandezze fisiche derivate sono scritte come "centro + scala * qualita'":
# il centro e' la macchina media della griglia, la scala dice quanto separa la
# migliore dalla peggiore. Sono tarate perche' fra la prima e l'ultima vettura
# ci sia quello che si vede in pista - due secondi e mezzo scarsi su un giro da
# novanta - e perche' nessuna delle cinque grandezze da sola faccia il campione:
# chi ha il carico e non ha la potenza vince dove si curva e perde dove si tira.
#
# Assetto: ogni voce va da 0 a 100. L'ottimo dipende dalla pista.
SETUP_KEYS = {
    "wing":        "Carico alare",
    "ride_height": "Altezza da terra",
    "stiffness":   "Rigidezza sospensioni",
    "camber":      "Campanatura",
    "gearing":     "Rapporti al cambio",
    "brake_bias":  "Ripartizione di frenata",
}


# Quanto pesa ogni pezzo sul tempo sul giro. Non e' un'opinione: e' misurato
# alzando di cinque punti un pezzo alla volta e guardando il cronometro su otto
# circuiti diversi.
PESO_PEZZI = {
    "suspension": 0.177, "chassis": 0.168, "floor": 0.146, "rear_wing": 0.129,
    "sidepods": 0.090, "gearbox": 0.087, "front_wing": 0.070, "brakes": 0.050,
    "cooling": 0.047, "active_aero": 0.038,
}


# A cosa serve ogni pezzo, dominio per dominio. Non e' una tassonomia: e' dove
# quel pezzo sposta il cronometro. Il fondo lavora quando la macchina va forte,
# le sospensioni quando va piano, il cambio in uscita di curva, i freni in
# staccata. Da qui viene il carattere di una vettura, e da qui si capisce cosa
# serve sviluppare per la pista di domenica prossima.
DOMINI_PEZZO = {
    "floor":       {"veloci": 1.00, "medie": 0.55, "lente": 0.15},
    "front_wing":  {"medie": 0.75, "lente": 0.55, "veloci": 0.35},
    "rear_wing":   {"veloci": 0.75, "medie": 0.45, "trazione": 0.35},
    "sidepods":    {"veloci": 0.45, "medie": 0.35},
    "active_aero": {"veloci": 0.65, "medie": 0.25},
    "suspension":  {"lente": 0.95, "trazione": 0.65, "frenata": 0.35},
    "chassis":     {"lente": 0.45, "medie": 0.45, "frenata": 0.35},
    "gearbox":     {"trazione": 0.95},
    "brakes":      {"frenata": 0.85, "lente": 0.20},
    "cooling":     {},
}

# Quanto pesa il carattere: un pezzo sei punti sopra la media della sua
# macchina vale circa il due per cento di aderenza in piu' nel suo dominio.
FORZA_DOMINIO = 0.30

# Quanto pesa ogni dominio in un giro medio del calendario, misurato sulle
# ventiquattro piste. Serve a tenere il carattere a somma zero su quello che
# conta davvero e non su sei caselle uguali.
QUOTA_DOMINIO = {"lente": 0.29, "medie": 0.23, "veloci": 0.12,
                 "trazione": 0.13, "frenata": 0.23}


@dataclass
class Part:
    perf: float
    condition: float = 100.0   # 0-100, scende con usura e danni
    upgrade_progress: float = 0.0
    # su cosa e' stata disegnata questa specifica: un fondo puo' nascere per le
    # curve veloci o per la trazione, e non e' la stessa cosa
    focus: str = ""

    @property
    def effective(self) -> float:
        return self.perf * (0.55 + 0.45 * self.condition / 100.0)

    def domains(self, key: str) -> dict:
        """Dove lavora questo pezzo, tenuto conto di come e' stato disegnato."""
        base = dict(DOMINI_PEZZO.get(key, {}))
        if not self.focus:
            return base
        base[self.focus] = base.get(self.focus, 0.0) * 1.5 + 0.30
        tot = sum(base.values()) or 1.0
        atteso = sum(DOMINI_PEZZO.get(key, {}).values()) or 1.0
        # la somma resta quella: un pezzo specializzato non e' un pezzo migliore
        return {d: w * atteso / tot for d, w in base.items()}


@dataclass
class Car:
    parts: dict = field(default_factory=dict)     # nome -> Part
    engine: dict = field(default_factory=dict)    # stats del motorista
    setup: dict = field(default_factory=dict)     # SETUP_KEYS -> 0..100
    setup_quality: float = 0.5                    # 0..1, quanto e' azzeccato
    _setup_cost: float = 0.0                      # quanto si perde, 0..1
    fuel_kg: float = 0.0
    reg_downforce_index: float = 0.70
    active_aero_allowed: bool = True
    mass_base: float = C.CAR_MASS_KG              # peso minimo regolamentare
    pu_integration: float = 0.25                  # 0 cliente .. 1 costruttore
    # come il regolamento in vigore ripartisce e limita la potenza: sono i
    # numeri che una modifica al regolamento sposta, e da qui arrivano al
    # modello di giro senza passare da variabili globali
    quota_elettrica: float = C.QUOTA_ELETTRICA
    v_taglio: float = C.V_TAGLIO_ERS              # m/s, dove la spinta cala
    v_fine: float = C.V_FINE_ERS                  # m/s, dove finisce
    recupero_max_mj: float = C.RECUPERO_MAX_MJ    # tetto al recupero di un giro
    reg_grip: float = 1.0                         # quanta aderenza concede la gomma
    balance: float = 0.0     # -1 macchina piantata dietro, +1 nervosa davanti

    # ------------------------------------------------------------------ init
    @classmethod
    def build(cls, team_car: dict, engine: dict, reg: dict) -> "Car":
        parts = {k: Part(float(v)) for k, v in team_car.items()}
        aero = reg.get("aero", {})
        c = cls(
            parts=parts,
            # riferimento vivo al motorista, non una copia: cosi' lo sviluppo
            # della power unit arriva a tutte le vetture che la montano
            engine=engine,
            setup={k: 50.0 for k in SETUP_KEYS},
            reg_downforce_index=aero.get("downforce_index", 0.70),
            active_aero_allowed=aero.get("active_aero", True),
            mass_base=float(reg.get("min_weight_kg", C.CAR_MASS_KG)),
        )
        mod = (reg.get("power_unit", {}) or {}).get("modello", {}) or {}
        c.quota_elettrica = float(mod.get("quota_elettrica", C.QUOTA_ELETTRICA))
        c.v_taglio = float(mod.get("v_taglio_kmh", C.V_TAGLIO_ERS * 3.6)) / 3.6
        c.v_fine = float(mod.get("v_fine_kmh", C.V_FINE_ERS * 3.6)) / 3.6
        c.recupero_max_mj = float(mod.get("recupero_max_mj", C.RECUPERO_MAX_MJ))
        c.reg_grip = float(reg.get("grip_multiplier", 1.0))
        return c

    def p(self, key: str) -> float:
        part = self.parts.get(key)
        return part.effective if part else 60.0

    # --------------------------------------------------------- derivate base
    @property
    def mass_extra(self) -> float:
        return self.fuel_kg

    @property
    def downforce(self) -> float:
        """Moltiplicatore su ClA di riferimento."""
        # il fondo e' la macchina: da li' viene la maggior parte del carico, e
        # l'ala posteriore non va contata due volte perche' pesa gia' tanto
        # sulla resistenza
        base = (0.42 * self.p("floor") + 0.20 * self.p("front_wing")
                + 0.16 * self.p("rear_wing") + 0.12 * self.p("sidepods")
                + 0.10 * self.p("chassis")) / 100.0
        aa = self.p("active_aero") / 100.0 if self.active_aero_allowed else 0.0
        wing = 0.62 + 0.74 * (self.setup.get("wing", 50.0) / 100.0)
        idx = self.reg_downforce_index / 0.70
        # La forbice fra la macchina piu' carica e la meno carica della griglia
        # e' di una decina di punti percentuali, non di venticinque: adesso che
        # il carico paga quanto paga davvero nelle curve veloci, una forbice
        # larga il doppio spalancava i distacchi a Spa e in Catalogna.
        return (0.698 + 0.700 * base) * wing * idx * (1.0 + 0.07 * aa)

    @property
    def drag(self) -> float:
        # l'ala che da' carico si porta dietro la sua resistenza, quasi in
        # proporzione: e' il motivo per cui esiste un'ala giusta per ogni pista
        # invece di metterla sempre al massimo
        wing = 0.57 + 0.90 * (self.setup.get("wing", 50.0) / 100.0)
        eff = (0.45 * self.p("rear_wing") + 0.30 * self.p("sidepods")
               + 0.25 * self.p("cooling")) / 100.0
        aa = 0.94 if self.active_aero_allowed else 1.0
        # e lo impacchetta piu' stretto, con meno resistenza all'avanzamento
        integ = 1.0 - 0.018 * self.pu_integration
        return wing * (1.214 - 0.315 * eff) * aa * integ

    @property
    def power(self) -> float:
        e = self.engine
        pu = (0.62 * e.get("power", 85) + 0.38 * e.get("ers", 85)) / 100.0
        cooling = 0.96 + 0.06 * (self.p("cooling") / 100.0)
        gears = 0.97 + 0.05 * (self.p("gearbox") / 100.0)
        # chi costruisce il motore lo sfrutta meglio: mappature, raffreddamento
        # e trasmissione sono disegnati sullo stesso tavolo
        integ = 1.0 + 0.020 * self.pu_integration
        # la scala tiene il valore medio dov'era e allarga la forbice: fra la
        # power unit migliore e la peggiore ci deve essere quello che si vede a
        # Monza, non un'inezia che sparisce nel rumore
        return (0.761 + 0.465 * pu * cooling * gears) * integ

    @property
    def mech_grip(self) -> float:
        base = (0.42 * self.p("suspension") + 0.36 * self.p("chassis")
                + 0.22 * self.p("gearbox")) / 100.0
        # L'aderenza meccanica separa le macchine molto meno dell'aerodinamica:
        # sospensioni e telaio sono simili per tutti, il fondo no. Con la
        # forbice larga di prima un punto di sospensione valeva tre di fondo,
        # che e' il contrario di quello che succede.
        return (0.981 + 0.060 * base) * self.reg_grip

    @property
    def braking(self) -> float:
        base = (0.70 * self.p("brakes") + 0.30 * self.p("suspension")) / 100.0
        return (0.790 + 0.300 * base)

    @property
    def domain_bias(self) -> dict:
        """L'aderenza che questa macchina ha in ogni dominio, attorno a 1.

        Non e' quanto e' forte: e' dove. Si guarda quali pezzi sono meglio del
        resto della macchina - un fondo migliore del suo telaio, un cambio
        migliore dei suoi freni - e si vede in che parte del giro quel vantaggio
        si trasforma in tempo. Due vetture con la stessa media vanno forte in
        posti diversi.
        """
        vals = [p.effective for p in self.parts.values()]
        if not vals:
            return {}
        medio = sum(vals) / len(vals)
        b = {}
        for k, p in self.parts.items():
            scarto = (p.effective - medio) / 100.0
            for dom, w in p.domains(k).items():
                b[dom] = b.get(dom, 0.0) + w * scarto
        if not b:
            return {}
        # il carattere e' una forma, non un livello: si centra su quanto pesa
        # ogni dominio in un giro medio, cosi' un pezzo migliore sposta dove si
        # e' forti senza regalare o togliere velocita' in assoluto
        centro = sum(QUOTA_DOMINIO.get(d, 0.2) * v for d, v in b.items())
        centro /= max(1e-6, sum(QUOTA_DOMINIO.get(d, 0.2) for d in b))
        return {d: 1.0 + FORZA_DOMINIO * (v - centro) for d, v in b.items()}

    @property
    def reliability(self) -> float:
        """0..1, probabilita' di NON rompersi in una gara.

        Fra la power unit piu' solida e quella piu' fragile ci passa quasi il
        doppio dei guasti: e' una delle ragioni per cui un motorista lo si
        sceglie, e non solo per i cavalli. Il resto lo dice come sta messa la
        macchina - un pezzo malandato e' un pezzo che cede.
        """
        mech = sum(self.parts[k].condition for k in self.parts) / (100.0 * max(1, len(self.parts)))
        eng = self.engine.get("reliability", 85) / 100.0
        return max(0.30, min(0.995, 0.22 + 0.46 * mech + 0.32 * eng))

    @property
    def rating(self) -> float:
        """Indice sintetico 0-100 per le schermate di riepilogo.

        I pezzi non contano uguale: mezzo punto di fondo vale piu' di mezzo
        punto di raffreddamento. I pesi sono misurati sul modello di giro -
        quanto sposta il cronometro cambiare quel pezzo - cosi' il numero che
        si legge a schermo e' d'accordo con quello che succede in pista.
        """
        peso = tot = 0.0
        for k, p in self.parts.items():
            w = PESO_PEZZI.get(k, 0.05)
            tot += w * p.effective
            peso += w
        car = tot / max(1e-6, peso)
        eng = (self.engine.get("power", 85) + self.engine.get("ers", 85)) / 2.0
        return 0.72 * car + 0.28 * eng

    # ------------------------------------------------------------- assetto
    def optimal_setup(self, track, driver=None, cond=None) -> dict:
        """L'assetto ideale su questo circuito, per questo pilota, con questo tempo.

        Senza pilota e' l'ottimo del tracciato e basta - quello che scrive il
        reparto sulla carta. Con un pilota ci si somma il suo stile di guida,
        ed e' per quello che due compagni di squadra non vogliono la stessa
        macchina. Con le condizioni ci si somma la giornata: sull'acqua e
        nell'aria sottile del Messico l'assetto giusto e' un altro.
        """
        base = self._track_optimum(track, cond)
        if driver is None:
            return base
        from ..core import driving
        off = driving.offsets(driver)
        return {k: max(0.0, min(100.0, v + off.get(k, 0.0))) for k, v in base.items()}

    def _track_optimum(self, track, cond=None) -> dict:
        """L'ottimo del tracciato, spostato da com'e' fatta la macchina e dal tempo.

        Un pacchetto che fa girare di piu' la vettura sposta anche dove sta la
        finestra: si frena piu' avanti e si porta un filo meno carico. Per
        questo dopo un aggiornamento l'assetto va ritrovato davvero.
        """
        t = track.traits
        b = max(-1.0, min(1.0, self.balance))
        base = self._optimum_raw(t, track)
        base["brake_bias"] = max(0.0, min(100.0, base["brake_bias"] + 5.0 * b))
        base["wing"] = max(0.0, min(100.0, base["wing"] - 3.0 * b))
        if cond is not None:
            base = self._weather_shift(base, cond)
        return {k: max(0.0, min(100.0, v)) for k, v in base.items()}

    def _weather_shift(self, base: dict, cond) -> dict:
        """Come la giornata sposta la finestra d'assetto.

        Dove l'aria e' sottile il carico non c'e': si mette l'ala grande e si
        prende comunque meno carico che altrove col cucchiaio. Sul bagnato si
        alza la macchina, la si ammorbidisce e si carica, perche' li' il tempo
        lo fa la trazione e non la percorrenza.
        """
        rho = float(getattr(cond, "rho", C.RHO))
        wet = float(getattr(cond, "wet", 0.0))
        aria = C.RHO / max(0.5, rho) - 1.0          # 0 sul mare, +0.30 in Messico
        base["wing"] += 42.0 * aria + 16.0 * wet
        base["gearing"] += 14.0 * aria
        base["ride_height"] += 22.0 * wet
        base["stiffness"] -= 20.0 * wet
        base["camber"] -= 10.0 * wet
        base["brake_bias"] -= 8.0 * wet
        return base

    def _optimum_raw(self, t, track=None) -> dict:
        # l'ala non e' un'opinione: e' il punto in cui il carico che si guadagna
        # in curva vale piu' della resistenza che si paga in fondo al rettilineo,
        # e quel punto lo trova il modello di giro, circuito per circuito
        ala = getattr(track, "wing_ref", None)
        if ala is None:
            ala = 100.0 * min(1.0, max(0.0, t["downforce"]))
        return {
            "wing":        float(ala),
            "ride_height": 100.0 * min(1.0, max(0.0, 0.28 + 0.62 * t["bumpiness"])),
            "stiffness":   100.0 * min(1.0, max(0.0, 0.72 - 0.50 * t["bumpiness"] + 0.18 * t["downforce"])),
            "camber":      100.0 * min(1.0, max(0.0, 0.35 + 0.45 * t["downforce"] - 0.15 * t["power"])),
            "gearing":     100.0 * min(1.0, max(0.0, t["power"])),
            "brake_bias":  100.0 * min(1.0, max(0.0, 0.35 + 0.40 * t["braking"])),
        }

    def evaluate_setup(self, track, driver=None, cond=None) -> float:
        """Quanto la macchina e' dentro alla finestra, e quanto costa esserne fuori.

        Non tutte le regolazioni contano uguale dappertutto: l'altezza da terra
        la si paga dove l'asfalto e' sconnesso, i rapporti dove si tira, la
        ripartizione di frenata dove si stacca forte. Il carico alare fa storia
        a se': quello lo pesa gia' il modello di giro, in resistenza e in
        percorrenza, e contarlo due volte sarebbe barare.
        """
        opt = self.optimal_setup(track, driver, cond)
        t = track.traits
        pesi = {
            "wing":        0.6 + 0.8 * t.get("downforce", 0.5),
            "ride_height": 0.5 + 1.0 * t.get("bumpiness", 0.4),
            "stiffness":   0.6 + 0.9 * t.get("bumpiness", 0.4),
            "camber":      0.5 + 0.9 * t.get("tyre_wear", 0.6),
            "gearing":     0.5 + 0.9 * t.get("power", 0.5),
            "brake_bias":  0.5 + 1.0 * t.get("braking", 0.5),
        }
        tot = peso_tot = costo = peso_costo = 0.0
        for k, ideale in opt.items():
            p = pesi.get(k, 1.0)
            fuori = min(1.0, (abs(self.setup.get(k, 50.0) - ideale) / 40.0) ** 1.4)
            tot += p * fuori
            peso_tot += p
            if k != "wing":
                costo += p * fuori
                peso_costo += p
        self.setup_quality = max(0.0, 1.0 - tot / max(1e-6, peso_tot))
        self._setup_cost = costo / max(1e-6, peso_costo)
        return self.setup_quality

    def apply_setup_effects(self):
        """Quanto si perde al giro per come e' regolata, da 0 a 1.8 per cento."""
        return 1.0 - 0.018 * float(getattr(self, "_setup_cost", 0.0))

    # --------------------------------------------------------------- usura
    def wear(self, amount: float, track) -> None:
        rough = 0.6 + 0.8 * track.traits.get("bumpiness", 0.4)
        for k, part in self.parts.items():
            part.condition = max(0.0, part.condition - amount * rough * (0.6 + 0.8 * _wear_bias(k)))

    def damage(self, key: str, amount: float) -> None:
        if key in self.parts:
            self.parts[key].condition = max(0.0, self.parts[key].condition - amount)

    def repair_cost(self) -> float:
        """Costo in M$ per riportare tutto al 100%."""
        tot = 0.0
        for k, part in self.parts.items():
            missing = (100.0 - part.condition) / 100.0
            tot += missing * C.CAR_PARTS[k]["cost"] * 0.55
        return round(tot, 3)

    def repair_all(self) -> float:
        cost = self.repair_cost()
        for part in self.parts.values():
            part.condition = 100.0
        return cost


_WEAR_BIAS = {
    "front_wing": 1.3, "floor": 1.4, "brakes": 1.5, "gearbox": 1.1,
    "suspension": 1.2, "rear_wing": 0.9, "chassis": 0.5, "sidepods": 0.7,
    "cooling": 0.8, "active_aero": 1.0,
}


def _wear_bias(key: str) -> float:
    return _WEAR_BIAS.get(key, 1.0)
