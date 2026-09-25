"""L'E-Prix visto dal muretto.

E' la stessa gara della Formula 1 - la mappa, la torre, la cronaca, i due
pannelli delle nostre macchine - ma quello che si guarda e' un'altra cosa. Qui
non ci sono gomme che si consumano ne' benzina da caricare: c'e' una batteria
che si svuota, e tre numeri che decidono la corsa.

  * quanta energia resta, e di quanti giri si e' avanti o indietro sul bisogno
  * quanto Attack Mode si ha ancora in mano, e quanto ne resta acceso adesso
  * se il Pit Boost e' fatto, e se no se siamo dentro alla finestra per farlo

Il muretto e' quello della Formula 1: gli stessi cinque ordini, lo stesso
passo, la stessa possibilita' di lasciare tutto al Team Principal. Le due
manopole in piu' sono quelle che il regolamento aggiunge qui.
"""
from __future__ import annotations

import pygame

from ...core import formulae as FE
from ...sim import eprix as EP
from ...sim import muretto as MU
from ...sim.weekend import Weather
from .. import grafica_gara as GG
from .. import theme as T
from .. import bandiere, fx, trackdraw
from ..app import Scene
from ..mappa3d import Mappa3D
from ..widgets import Button

SPEEDS = [0, 1, 4, 12, 40]
SPEED_LABELS = ["II", "x1", "x4", "x12", "x40"]


def _orologio(s: float) -> str:
    m, sec = divmod(max(0.0, s), 60.0)
    return f"{int(m)}:{int(sec):02d}"


class EPrixScene(Mappa3D, Scene):
    # la barra: due righe di comandi dove c'e' altezza, una sola dove non ce
    # n'e', perche' l'altezza la vuole il tabellone che ha ventidue righe
    BARRA_H = 200
    BARRA_STRETTA = 168
    ALTEZZA_DUE_RIGHE = 700

    def __init__(self, app, track, formato: str = "eprix"):
        super().__init__(app)
        self.gs = app.gs
        self.track = track
        self.formato = formato
        self.sim = None
        self.speed_idx = 2
        self.pts = None
        self.pts_rect = None
        self._etichette = []
        self.result_rows = []
        self.applicato = False
        # la qualifica si guarda: prima i due gruppi, poi i duelli uno per uno
        self.fase = "prep"          # prep | quali | gara | fine
        self.q_passo = 0            # a che punto e' il racconto della qualifica
        self.q_t = 0.0
        self._init_3d()
        self.build()

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        self._mappa = None
        self._righe_torre = None
        if self.sim is None:
            self._build_prep(w, h)
        elif self.fase == "quali":
            self._build_quali(w, h)
        elif self.sim.finished:
            self._build_fine(w, h)
        else:
            self._build_gara(w, h)

    def _build_prep(self, w: int, h: int) -> None:
        self.widgets.append(Button((w // 2 - 130, h - 120, 260, 46),
                                   "VIA ALL'E-PRIX", self.via, "primary"))
        self.widgets.append(Button((40, h - 74, 140, 34), "Torna indietro",
                                   self.esci, "ghost"))

    def _build_quali(self, w: int, h: int) -> None:
        finita = self.q_passo >= len(self._passi_quali())
        if finita:
            self.widgets.append(Button((w // 2 - 110, h - 74, 220, 40),
                                       "IN GRIGLIA", self.al_via, "primary"))
        else:
            self.widgets.append(Button((w // 2 - 110, h - 74, 220, 40),
                                       "SALTA LA QUALIFICA", self.salta_quali,
                                       "ghost"))

    def _build_fine(self, w: int, h: int) -> None:
        self.widgets.append(Button((w // 2 - 90, h - 74, 180, 40), "Chiudi",
                                   self.esci, "primary"))

    def _build_gara(self, w: int, h: int) -> None:
        sim = self.sim
        bx, by = 40, h - 74
        for i, lab in enumerate(SPEED_LABELS):
            b = Button((bx + i * 62, by, 56, 34), lab, style="tab")
            b.on_click = (lambda i=i: self.set_speed(i))
            b.active = (i == self.speed_idx)
            self.widgets.append(b)
        x = bx + 5 * 62 + 16
        corta = w < 1180
        self.widgets.append(Button((x, by, 78 if corta else 176, 34),
                                   "FINE" if corta else "Simula fino alla fine",
                                   self.salta, "ghost"))
        x += (86 if corta else 186)
        b = Button((x, by, 112 if corta else 168, 34),
                   "TEAM PR." if corta else "TEAM PRINCIPAL", self.delega, "tab",
                   tip="La gara la gestisce lui: ordini, passo, Attack Mode, Boost")
        b.active = self.delegato()
        self.widgets.append(b)
        x += (120 if corta else 176)
        # gli ordini che riguardano tutte e due le macchine, come in Formula 1
        vive = [e for e in sim.entrants if e.is_player and e.status == "running"]
        if len(vive) >= 2:
            delegata = self.delegato()
            b = Button((x, by, 90 if corta else 100, 34), "SCAMBIO",
                       self.chiedi_scambio, "normal",
                       tip="Lascialo passare: si chiede, non si impone")
            b.enabled = not delegata
            self.widgets.append(b)
            x += (98 if corta else 108)
            b = Button((x, by, 78 if corta else 152, 34),
                       "FERMI" if corta else "TIENI LE POSIZIONI",
                       self.tieni_posizioni, "tab",
                       tip="Fra le nostre due non si combatte piu'")
            b.active = all(e.tieni_posizioni for e in vive)
            b.enabled = not delegata
            self.widgets.append(b)
        for e, r in self._pannelli(w, h):
            self._comandi(e, r)
        mappa, _riga, torre = self._rect_gara(w, h)
        self._comandi_vista(pygame.Rect(torre.right + 4, mappa.y, mappa.right - torre.right - 4,
                                        mappa.h))

    TORRE_W = 270
    MODI_TORRE = ("INTERVALLO", "DISTACCO", "ENERGIA")

    def _rect_gara(self, w: int, h: int) -> tuple:
        """La mappa a tutto schermo, il tabellone sopra a sinistra come in
        televisione, la cronaca in una riga in fondo alla mappa."""
        barra_y = h - 84 - self.barra_h(h)
        mappa = pygame.Rect(12, 64, w - 24, barra_y - 72)
        torre = pygame.Rect(mappa.x + 10, mappa.y + 10, self.TORRE_W, mappa.h - 20)
        riga = pygame.Rect(torre.right + 14, mappa.bottom - 42,
                           mappa.right - torre.right - 28, 32)
        return mappa, riga, torre

    def cambia_torre(self) -> None:
        modi = self.MODI_TORRE
        self.modo_torre = modi[(modi.index(getattr(self, "modo_torre", modi[0])) + 1)
                               % len(modi)]

    def due_righe(self, h: int = 0) -> bool:
        h = h or self.app.screen.get_size()[1]
        return h >= self.ALTEZZA_DUE_RIGHE

    def barra_h(self, h: int = 0) -> int:
        return self.BARRA_H if self.due_righe(h) else self.BARRA_STRETTA

    def _pannelli(self, w: int, h: int) -> list:
        nostre = [e for e in (self.sim.entrants if self.sim else []) if e.is_player]
        if not nostre:
            return []
        alta = self.barra_h(h)
        barra = pygame.Rect(20, h - 84 - alta, w - 40, alta)
        larga = (barra.w - 12 * (len(nostre) - 1)) / len(nostre)
        return [(e, pygame.Rect(barra.x + i * (larga + 12), barra.y, larga, barra.h))
                for i, e in enumerate(nostre)]

    def _comandi(self, e, r) -> None:
        """Gli ordini, il passo, e le due manopole che qui aggiunge il regolamento."""
        sim = self.sim
        mia = not e.delegato
        due = self.due_righe()
        largo = 46 if due else 38
        x, y = r.x + 16, r.y + 118
        for chiave in MU.ELENCO:
            b = Button((x, y, largo, 20), MU.ORDINI[chiave]["corto"], style="tab",
                       tip=MU.ORDINI[chiave]["nota"])
            b.on_click = (lambda k=e.driver_id, o=chiave: self.set_ordine(k, o))
            b.active = (e.ordine == chiave)
            b.enabled = mia
            self.widgets.append(b)
            x += largo + 3
        # il passo: sotto se c'e' spazio, di fianco se non ce n'e'
        y2 = r.y + 144 if due else y
        px = (r.x + 62) if due else (x + 10)
        largo_p = 30 if due else 24
        for lab, val in (("-", 0.92), ("=", None), ("+", 1.10)):
            b = Button((px, y2, largo_p, 20), lab, style="tab")
            b.on_click = (lambda k=e.driver_id, v=val: self.set_push(k, v))
            b.active = (val == e.passo_manuale)
            b.enabled = mia
            self.widgets.append(b)
            px += largo_p + 3
        # l'Attack Mode: si chiede, e si prende al prossimo passaggio nella zona
        larg_a = 92 if due else 74
        larg_b = 100 if due else 82
        b = Button((r.right - 16 - larg_b - 8 - larg_a, y2, larg_a, 20), "ATTACK",
                   (lambda k=e.driver_id: self.attack(k)), "normal",
                   tip="Si prende passando fuori traiettoria: costa tempo adesso")
        b.enabled = mia and sim.attack_disponibile(e) and not e.attack_chiesto
        b.active = e.attack_attivo > 0 or e.attack_chiesto
        self.widgets.append(b)
        # e il Pit Boost
        b = Button((r.right - 16 - larg_b, y2, larg_b, 20),
                   "BOOST" if not due else "PIT BOOST",
                   (lambda k=e.driver_id: self.boost(k)), "normal",
                   tip="Ricarica rapida obbligatoria: solo fra il 40 e il 60 per cento")
        b.enabled = (mia and sim.col_boost and not e.boost_fatto
                     and not e.boost_chiesto)
        b.active = e.boost_chiesto
        self.widgets.append(b)
        # e le risposte alla radio
        if e.domanda:
            larghe = 104 if r.w >= 430 else 88
            qx = r.right - 16
            for k, (lab, chiave) in enumerate(reversed(e.domanda["opzioni"])):
                qx -= larghe
                self.widgets.append(Button(
                    (qx, r.bottom - 28, larghe, 24), lab,
                    (lambda d=e.driver_id, c=chiave: self.rispondi(d, c)),
                    "normal" if k else "primary"))
                qx -= 6

    # ------------------------------------------------------------------ azioni
    def via(self) -> None:
        w = Weather.generate(self.track, self.gs.rng)
        self.sim = EP.make_eprix(self.gs, self.track, self.gs.player,
                                 formato=self.formato, weather=w)
        self.speed_idx = 2
        self.fase = "quali"
        self.q_passo = 0
        self.q_t = 0.0
        self.build()

    # ------------------------------------------------------------- la qualifica
    # Ogni quanto si scopre il duello successivo. E' lo spettacolo della
    # Formula E: otto piloti a eliminazione diretta, uno contro uno, e chi
    # perde e' fuori. Guardarlo scorrere tutto insieme non sarebbe guardarlo.
    PASSO_QUALI = 1.5

    def _passi_quali(self) -> list:
        """Il racconto della qualifica: prima i gruppi, poi un duello per volta."""
        if not self.sim or not hasattr(self.sim, "qualifica"):
            return []
        return ["gruppi"] + list(self.sim.qualifica["duelli"])

    def salta_quali(self) -> None:
        self.q_passo = len(self._passi_quali())
        self.build()

    def al_via(self) -> None:
        self.fase = "gara"
        self.semaforo = fx.Semaforo(len(self.track.id))
        self.build()

    def esci(self) -> None:
        self.app.pop()
        from .shell import GameShell
        if isinstance(self.app.scene, GameShell):
            self.app.scene.enter()

    def set_speed(self, i: int) -> None:
        self.speed_idx = i
        self.build()

    def salta(self) -> None:
        self.semaforo = None
        if self.sim:
            self.sim.fast_forward()
            self._fine()

    def delegato(self) -> bool:
        if not self.sim:
            return False
        nostre = [e for e in self.sim.entrants if e.is_player]
        return bool(nostre) and all(e.delegato for e in nostre)

    def delega(self) -> None:
        if not self.sim:
            return
        acceso = not self.delegato()
        for e in self.sim.entrants:
            if not e.is_player:
                continue
            e.delegato = acceso
            if acceso:
                e.passo_manuale = None
                e.domanda = None
                e.ordine = "libero"
                e.ordine_da = -99
        capo = self.gs.player._s("head_of_strategy", "strategy", 60.0)
        self.app.toast(f"Gara al Team Principal. Capo strategia: {capo:.0f}."
                       if acceso else "Il muretto torna a te.")
        self.build()

    def chiedi_scambio(self) -> None:
        """"Lascialo passare": si chiede, e poi si vede cosa risponde."""
        vive = [e for e in self.sim.entrants if e.is_player and e.status == "running"]
        if len(vive) < 2:
            return
        vive.sort(key=lambda e: e.position)
        davanti, dietro = vive[0], vive[1]
        risposta = MU.chiedi_scambio(self.sim, davanti, dietro)
        self.sim.radio_say(davanti, f"Lascia passare {dietro.code}.", "muretto")
        if risposta:
            self.sim.radio_say(davanti, risposta, "pilota")
        self.app.toast(f"{davanti.name}: {risposta}" if risposta else "Ordine dato.")
        self.build()

    def tieni_posizioni(self) -> None:
        """Le posizioni sono queste: fra le nostre due non si combatte piu'."""
        nostre = [e for e in self.sim.entrants if e.is_player]
        acceso = not all(e.tieni_posizioni for e in nostre if e.status == "running")
        for e in nostre:
            e.tieni_posizioni = acceso
            if acceso:
                MU.chiudi_scambio(e)
            self.sim.radio_say(e, "Tenete le posizioni." if acceso
                               else "Siete liberi di correre.", "muretto")
        self.app.toast("Ordine di tenere le posizioni." if acceso
                       else "Piloti liberi di correre.")
        self.build()

    def set_ordine(self, driver_id: str, ordine: str) -> None:
        for e in self.sim.entrants:
            if e.driver_id != driver_id:
                continue
            e.ordine = "libero" if e.ordine == ordine else ordine
            e.ordine_da = e.lap
            self.sim.radio_say(e, MU.ORDINI[e.ordine]["radio"], "muretto")
        self.build()

    def set_push(self, driver_id: str, value) -> None:
        for e in self.sim.entrants:
            if e.driver_id == driver_id:
                e.passo_manuale = value
                if value is not None:
                    e.push_mode = value
        self.build()

    def attack(self, driver_id: str) -> None:
        for e in self.sim.entrants:
            if e.driver_id == driver_id and self.sim.chiedi_attack(e):
                self.app.toast(f"{e.name}: Attack Mode al prossimo passaggio.")
        self.build()

    def boost(self, driver_id: str) -> None:
        for e in self.sim.entrants:
            if e.driver_id == driver_id and self.sim.chiedi_boost(e):
                self.app.toast(f"{e.name}: Pit Boost appena siamo in finestra.")
        self.build()

    def rispondi(self, driver_id: str, scelta: str) -> None:
        self.sim.rispondi(driver_id, scelta)
        self.build()

    def on_resize(self) -> None:
        self.pts = None
        self.build()

    # -------------------------------------------------------------------- loop
    def _scheda_3d(self, driver_id):
        """La scheda sul plastico: posizione, nome, batteria, distacco."""
        info = super()._scheda_3d(driver_id)
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        if info is None or e is None:
            return info
        carica = e.carica()
        info["dato"] = ("ATTACK " if e.attack_attivo > 0 else "") + f"{int(round(carica * 100))}%"
        info["colore"] = ((183, 96, 255) if e.attack_attivo > 0 else
                          (90, 220, 120) if carica > 0.25 else (255, 170, 60))
        sim = self.sim
        if e.status == "pitting":
            info["distacco"] = "BOX"
        elif e.position == 1:
            info["distacco"] = "PRIMO"
        elif sim is not None:
            primo = sim.order()[0]
            passo = sim.track_len / max(20.0, e.last_lap or e.base_lap)
            info["distacco"] = f"+{(primo.dist - e.dist) / passo:.1f}"
        return info

    def _livree_3d(self) -> tuple:
        """Una tela per squadra: la nostra con i nostri sponsor, le altre con
        i colori e i marchi che hanno davvero."""
        from .. import livree
        tele, indice = [], {}
        for e in self._entranti_3d():
            if e.team_id in indice:
                continue
            team = self.gs.teams.get(e.team_id)
            tele.append(livree.disegna(self.gs, team) if team is not None
                        else livree.disegna_fe(e.squadra, e.colour))
            indice[e.team_id] = len(tele) - 1
        return tele, indice

    def _livrea_3d(self, driver_id, colore) -> tuple:
        from .. import livree
        e = next((x for x in self._entranti_3d() if x.driver_id == driver_id), None)
        if e is None:
            return super()._livrea_3d(driver_id, colore)
        team = self.gs.teams.get(e.team_id)
        base = livree.livrea_di(team) if team is not None else livree.livrea_fe(e.squadra, colore)
        return base + (getattr(self, "_indice_livree", {}).get(e.team_id, -1),)

    def in_pista(self) -> bool:
        return self.fase == "gara" and self.sim is not None and not self.sim.finished

    def _elettrico_3d(self) -> bool:
        return True

    def update(self, dt: float) -> None:
        super().update(dt)
        self._dt = dt
        if self.v3d is not None:
            self.v3d.aggiorna(dt)
        if self.in_pista():
            self._suono_pista()
        if getattr(self, "traguardo", None) is not None:
            self.traguardo.update(dt)
            if self.traguardo.finito:
                self.traguardo = None
        semaforo = getattr(self, "semaforo", None)
        if semaforo is not None:
            semaforo.update(dt)
            if semaforo.finito:
                self.semaforo = None
            if semaforo.ferma:
                return
        if not self.sim:
            return
        if self.fase == "quali":
            self.q_t += dt
            if self.q_t >= self.PASSO_QUALI and self.q_passo < len(self._passi_quali()):
                self.q_t = 0.0
                self.q_passo += 1
                self.build()
            return
        if self.sim.finished:
            return
        mult = SPEEDS[self.speed_idx]
        if not mult:
            return
        passo = dt * mult
        n = max(1, int(passo / 2.0) + 1)
        for _ in range(n):
            self.sim.update(passo / n)
            if self.sim.finished:
                break
        if self.sim.finished:
            self._fine()
        else:
            self.build()

    def _fine(self) -> None:
        """La gara e' finita: il risultato entra nel campionato.

        E' il pezzo che mancava. Prima la gara si correva e finiva li': la
        classifica del mondiale la faceva un conto separato a dicembre, e
        vincere un E-Prix non serviva a niente. Adesso la gara corsa vale come
        quelle simulate, con gli stessi punti e nella stessa classifica.
        """
        if self.applicato:
            return
        self.applicato = True
        sim = self.sim
        ordine = sim.order()
        if ordine:
            podio = any(e.is_player for e in ordine[:3])
            self.traguardo = fx.Traguardo(f"VINCE {ordine[0].name.upper()}",
                                          f"{self.track.gp}  -  {ordine[0].squadra}",
                                          festa=podio, colore=tuple(ordine[0].colour[:3]),
                                          seme=len(self.track.id))
        # il distacco si legge dal tempo del primo classificato: chi e'
        # ritirato non ne ha uno, chi ha vinto parte da zero
        vincitore = next((e for e in ordine if e.status == "finished"), None)
        base = vincitore.finished_time if vincitore is not None else 0.0
        self.result_rows = [
            {"pos": i, "code": e.code, "name": e.name, "squadra": e.squadra,
             "status": e.status, "energia": e.carica(), "attack": e.attack_usi,
             "boost": e.boost_fatto,
             "distacco": (e.finished_time - base) if e.status == "finished" else None,
             "tempo": e.finished_time if e.status == "finished" else None}
            for i, e in enumerate(ordine, 1)]
        # chi ha fatto la pole e chi il giro veloce: sono punti iridati anche
        # quelli, e vanno segnati come in una gara simulata
        pole = min(ordine, key=lambda e: e.grid).driver_id if ordine else ""
        veloce = next((e.driver_id for e in ordine if e.code == sim.best_lap_by), "")
        FE.registra(self.gs, [e.driver_id for e in ordine], pole=pole,
                    veloce=veloce, team=self.gs.player)
        st = FE.stato(self.gs, self.gs.player)
        if st["storia"]:
            st["storia"][-1]["corsa"] = True
        self.build()

    # ----------------------------------------------------------------- disegno
    def draw(self, surf) -> None:
        w, h = surf.get_size()
        if self.sim is None:
            self._draw_prep(surf, w, h)
        elif self.fase == "quali":
            self._draw_quali(surf, w, h)
        elif self.sim.finished:
            self._draw_fine(surf, w, h)
        else:
            self._draw_gara(surf, w, h)
        super().draw(surf)
        if getattr(self, "semaforo", None) is not None and self.fase == "gara":
            self.semaforo.draw(surf, self._rect_gara(w, h)[0])
        if getattr(self, "traguardo", None) is not None:
            self.traguardo.draw(surf, surf.get_rect())

    def _draw_prep(self, surf, w: int, h: int) -> None:
        reg = FE.corrente()
        f = (reg.get("formati") or {}).get(self.formato, {})
        larga = bandiere.disegna(surf, self.track.flag, (40, 42), 16)
        x0 = 40 + (larga + 12 if larga else 0)
        T.text(surf, self.track.gp.upper(), (x0, 34), 26, T.TEXT, bold=True)
        T.text(surf, f"{self.track.name} - {self.track.length_km:.3f} km, "
                     f"{self.track.corners} curve", (x0, 68), 15, T.DIM)
        r = pygame.Rect(40, 110, w - 80, h - 220)
        mappa = pygame.Rect(r.x, r.y, int(r.w * 0.52), r.h)
        T.panel(surf, mappa, (13, 17, 24), radius=10, border=T.LINE)
        pts = trackdraw.fit_points(self.track, mappa.inflate(-40, -40))
        trackdraw.draw_track(surf, self.track, mappa, width=12, pts=pts)
        c = pygame.Rect(r.x + int(r.w * 0.54), r.y, int(r.w * 0.46), r.h)
        T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, f.get("nome", "E-Prix").upper(), (c.x + 20, c.y + 18), 20,
               T.TEXT, bold=True)
        y = c.y + 52
        tec = FE.tecnico()
        for eti, val in (
                ("Durata", f"{f.get('durata_min')} minuti piu' un giro"),
                ("Pit Boost", "obbligatorio" if f.get("pit_boost") else "non previsto"),
                ("Potenza", f"{tec.get('potenza_gara_kw')} kW, "
                            f"{tec.get('potenza_attack_kw')} in Attack Mode"),
                ("Energia", f"{tec.get('batteria_kwh')} kWh"),
                ("Note del circuito", "")):
            T.text(surf, eti, (c.x + 20, y), 13, T.DIM_2)
            if val:
                T.text(surf, val, (c.right - 20, y), 13, T.TEXT, align="right")
            y += 24
        T.paragraph(surf, getattr(self.track, "nota", "") or "", (c.x + 20, y),
                    13, T.DIM, maxw=c.w - 40)

    def _draw_quali(self, surf, w: int, h: int) -> None:
        """I due gruppi e il tabellone dei duelli, che si riempie da solo."""
        q = self.sim.qualifica
        T.text(surf, f"{self.track.gp.upper()} - QUALIFICA", (40, 26), 24, T.TEXT,
               bold=True)
        T.text(surf, "Due gruppi, i primi quattro di ognuno passano ai duelli: "
                     "uno contro uno, chi perde e' fuori.",
               (40, 58), 13, T.DIM_2, maxw=w - 80)
        passi = self._passi_quali()
        fatti = min(self.q_passo, len(passi))
        top = 92
        alto = h - top - 100
        # ---- i due gruppi
        gw = int((w - 80) * 0.34)
        for k, tabella in enumerate(q["gruppi"]):
            c = pygame.Rect(40 + k * (gw // 2 + 8), top, gw // 2, alto)
            T.panel(surf, c, T.PANEL, radius=10, border=T.LINE)
            T.text(surf, f"GRUPPO {chr(65 + k)}", (c.x + 12, c.y + 10), 12,
                   T.DIM_2, bold=True)
            if fatti < 1:
                T.text(surf, "in pista...", (c.x + 12, c.y + 34), 13, T.DIM)
                continue
            y = c.y + 32
            rh = min(22, (c.h - 44) / max(1, len(tabella)))
            for i, (e, t) in enumerate(tabella, 1):
                passa = i <= 4
                col = T.TEXT if e.is_player else (T.DIM if passa else (60, 70, 88))
                if e.is_player:
                    T.panel(surf, (c.x + 6, y - 1, c.w - 12, rh - 1), T.PANEL_3,
                            radius=4)
                T.text(surf, str(i), (c.x + 26, y), 12,
                       T.GOLD if passa else T.DIM_2, align="right")
                T.text(surf, e.code, (c.x + 34, y), 12, col, mono=True,
                       bold=e.is_player)
                T.text(surf, f"{t:.3f}", (c.right - 12, y), 12, col, mono=True,
                       align="right")
                y += rh
        # ---- il tabellone dei duelli
        d = pygame.Rect(40 + gw + 24, top, w - 80 - gw - 24, alto)
        T.panel(surf, d, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "DUELLI", (d.x + 14, d.y + 10), 12, T.DIM_2, bold=True)
        fasi = ("quarti", "semifinali", "finale")
        cw = (d.w - 40) / 3
        for k, fase in enumerate(fasi):
            cx = d.x + 20 + k * cw
            T.text(surf, fase.upper(), (cx, d.y + 34), 11, T.DIM_2, bold=True)
            miei = [x for x in q["duelli"] if x["fase"] == fase]
            y = d.y + 56
            for x in miei:
                # si scopre solo quello che e' gia' successo
                visto = (passi.index(x) < fatti) if x in passi else True
                self._duello(surf, pygame.Rect(int(cx), int(y), int(cw - 16), 46),
                             x, visto)
                y += 54
        if fatti >= len(passi) and q["griglia"]:
            p = q["griglia"][0]
            T.text(surf, f"POLE: {p.name} ({p.squadra})", (40, h - 88), 16,
                   T.GOLD, bold=True)

    def _duello(self, surf, r, x, visto: bool) -> None:
        """Un duello: i due, i due tempi, e chi e' passato."""
        T.panel(surf, r, T.PANEL_2, radius=6, border=T.LINE)
        for k, (chi, tempo) in enumerate(((x["a"], x["ta"]), (x["b"], x["tb"]))):
            y = r.y + 5 + k * 19
            vince = visto and x["vince"] == chi.driver_id
            col = T.OK if vince else (T.DIM if visto else (48, 58, 76))
            if chi.is_player:
                col = T.GOLD if not visto else (T.OK if vince else T.WARN)
            T.text(surf, chi.code, (r.x + 10, y), 12, col, mono=True,
                   bold=chi.is_player)
            T.text(surf, chi.squadra, (r.x + 48, y + 1), 11,
                   T.DIM_2 if visto else (48, 58, 76), maxw=r.w - 120)
            T.text(surf, f"{tempo:.3f}" if visto else "--.---",
                   (r.right - 10, y), 12, col, mono=True, align="right")

    def _draw_fine(self, surf, w: int, h: int) -> None:
        T.text(surf, f"{self.track.gp.upper()} - RISULTATO", (40, 30), 24, T.TEXT,
               bold=True)
        r = pygame.Rect(40, 78, w - 80, h - 160)
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        y = r.y + 16
        T.text(surf, "POS  PILOTA", (r.x + 18, y), 11, T.DIM_2, bold=True)
        T.text(surf, "SQUADRA", (r.x + 240, y), 11, T.DIM_2, bold=True)
        T.text(surf, "DISTACCO", (r.x + 540, y), 11, T.DIM_2, bold=True, align="right")
        T.text(surf, "ENERGIA", (r.x + 620, y), 11, T.DIM_2, bold=True)
        T.text(surf, "ATTACK", (r.x + 710, y), 11, T.DIM_2, bold=True)
        T.text(surf, "BOOST", (r.x + 790, y), 11, T.DIM_2, bold=True)
        y += 22
        rh = max(16, min(26, (r.h - 60) / max(1, len(self.result_rows))))
        for riga in self.result_rows:
            mio = riga["squadra"] == getattr(self.gs.player, "fe_nome", "")
            col = T.TEXT if mio else T.DIM
            T.text(surf, str(riga["pos"]), (r.x + 40, y), 13, T.GOLD if mio else T.DIM_2,
                   align="right")
            T.text(surf, riga["name"], (r.x + 56, y), 13, col, bold=mio, maxw=170)
            T.text(surf, riga["squadra"], (r.x + 240, y), 12, col, maxw=300)
            if riga["status"] == "retired":
                T.text(surf, "RITIRATO", (r.x + 540, y), 12, T.BAD, align="right")
            elif riga["pos"] == 1:
                T.text(surf, _orologio(riga["tempo"]), (r.x + 540, y), 12, T.GOLD,
                       mono=True, align="right", bold=mio)
            else:
                T.text(surf, f"+{riga['distacco']:.1f}s", (r.x + 540, y), 12, col,
                       mono=True, align="right")
            if riga["status"] != "retired":
                T.text(surf, f"{riga['energia'] * 100:.0f}%", (r.x + 620, y), 12, col)
                T.text(surf, str(riga["attack"]), (r.x + 720, y), 12, col)
                T.text(surf, "si" if riga["boost"] else "NO", (r.x + 800, y), 12,
                       col if riga["boost"] else T.BAD)
            y += rh

    # ------------------------------------------------------------- la gara viva
    def _draw_gara(self, surf, w: int, h: int) -> None:
        self._header(surf, w)
        mappa, riga, torre = self._rect_gara(w, h)
        self._disegna_mappa(surf, mappa)
        self._torre(surf, torre)
        GG.riga_cronaca(surf, riga, self.sim.events, self)
        for e, r in self._pannelli(w, h):
            self._pannello(surf, r, e)

    def _header(self, surf, w: int) -> None:
        sim = self.sim
        pygame.draw.rect(surf, T.PANEL_2, (0, 0, w, 58))
        larga = bandiere.disegna(surf, self.track.flag, (24, 14), 13)
        x0 = 24 + (larga + 10 if larga else 0)
        # in Formula E non si contano i giri, si conta il tempo: e' la prima
        # cosa che si guarda, e va dove in Formula 1 c'e' il numero del giro
        resta = sim.tempo_restante()
        etichetta = ("ULTIMO GIRO" if sim.ultimo_giro
                     else f"{_orologio(resta)} ALLA FINE")
        # a destra il giro veloce, e appena prima la neutralizzazione: cosi' su
        # una finestra stretta il titolo non ci finisce sopra
        destra = w - 24
        if sim.best_lap > 0:
            T.text(surf, "GIRO VELOCE", (destra, 8), 11, T.DIM_2, bold=True,
                   align="right")
            T.text(surf, f"{sim.best_lap_by}  {T.fmt_time(sim.best_lap)}",
                   (destra, 24), 14, T.TEXT, mono=True, align="right")
            destra -= 200
        if sim.safety_car > 0:
            nome = "FULL COURSE YELLOW" if sim.vsc else "SAFETY CAR"
            T.text(surf, nome, (destra, 8), 13, T.WARN, bold=True, align="right")
            T.text(surf, "si perde energia", (destra, 26), 12, T.WARN, align="right")
            destra -= 180
        T.text(surf, f"{self.track.name.upper()}  -  {etichetta}", (x0, 10), 20,
               T.GOLD if sim.ultimo_giro else T.TEXT, bold=True,
               maxw=max(120, destra - x0 - 16))
        T.text(surf, f"giro {sim.leader_lap + 1} - {FE.corrente().get('etichetta','')}",
               (x0, 34), 13, T.DIM_2, maxw=max(120, destra - x0 - 16))

    def _alone_3d(self, driver_id):
        # chi ha l'Attack Mode acceso si vede: e' la cosa che cambia la gara
        e = next((x for x in self.sim.entrants if x.driver_id == driver_id), None)
        return (183, 96, 255) if e is not None and e.attack_attivo > 0 else None

    def handle(self, ev) -> None:
        if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.sim is not None
                and self.fase == "gara" and getattr(self, "_torre_testa", None) is not None
                and self._torre_testa.collidepoint(ev.pos)):
            self.cambia_torre()
            return
        semaforo = getattr(self, "semaforo", None)
        if semaforo is not None and semaforo.ferma and ev.type == pygame.MOUSEBUTTONDOWN:
            w, h = self.app.screen.get_size()
            if self._rect_gara(w, h)[0].collidepoint(ev.pos):
                semaforo.salta()
                return
        if getattr(self, "traguardo", None) is not None and ev.type == pygame.MOUSEBUTTONDOWN:
            self.traguardo = None
        if self.sim is not None and self.fase == "gara" and self._mano_3d(ev):
            return
        super().handle(ev)

    def _disegna_mappa(self, surf, vista) -> None:
        sim = self.sim
        occupato = self.TORRE_W + 20
        self._margine_sx = occupato
        self._senza_aiuto = True
        vive = [e for e in sim.order() if e.status != "retired"]
        quote = {e.driver_id: self.track.pos_at(e.lap_fraction(sim.track_len)) for e in vive}
        if self._in_3d():
            auto = [(e.driver_id, quote[e.driver_id], e.colour, e.is_player, e.code,
                     e.status == "pitting", e.is_player or e.position <= 3)
                    for e in reversed(vive)]
            if self._mappa_3d(surf, vista, auto):
                return
        T.panel(surf, vista, (13, 17, 24), radius=10, border=T.LINE)
        vista = pygame.Rect(vista.x + occupato, vista.y, vista.w - occupato, vista.h - 44)
        if self.pts is None or self.pts_rect != tuple(vista):
            self.pts = trackdraw.fit_points(self.track, vista.inflate(-30, -30))
            self.pts_rect = tuple(vista)
        trackdraw.draw_track(surf, self.track, vista, width=14, pts=self.pts)
        self._etichette = []
        mezzo = max(0.0, trackdraw.nastro_px(self.track, vista, 14) / 2 - 1.0)
        lat = self._laterali(list(quote.items()), self._forzati_2d(quote, vista, mezzo))
        self._safety_car_2d(surf, mezzo)
        for e in reversed(vive):
            quota = quote[e.driver_id]
            x, y = trackdraw.car_pos(self.pts, quota, lat[e.driver_id] * mezzo)
            mio = e.is_player
            r = 7 if mio else 5
            if e.status == "pitting":
                pygame.draw.circle(surf, (90, 90, 100), (int(x), int(y)), r + 2)
            # chi ha l'Attack Mode acceso si vede: e' la cosa che cambia la gara
            if e.attack_attivo > 0:
                pygame.draw.circle(surf, (183, 96, 255), (int(x), int(y)), r + 3)
            pygame.draw.circle(surf, e.colour, (int(x), int(y)), r)
            pygame.draw.circle(surf, (10, 14, 20), (int(x), int(y)), r, 1)
            # la sigla solo se c'e' posto: quando due macchine sono incollate
            # il pallino basta, e due nomi sovrapposti non li legge nessuno
            if (mio or e.position <= 3) and self._spazio(int(x) + 9, int(y) - 8):
                T.text(surf, e.code, (int(x) + 9, int(y) - 8), 12,
                       T.TEXT if mio else T.DIM)

    def _spazio(self, x: int, y: int) -> bool:
        """Se in quel punto della mappa ci sta una sigla senza pestarne un'altra."""
        r = pygame.Rect(x - 2, y - 2, 34, 18)
        if any(r.colliderect(a) for a in self._etichette):
            return False
        self._etichette.append(r)
        return True

    def _torre(self, surf, r) -> None:
        """Il tabellone come in televisione. A destra la batteria di ognuno;
        il numero e' l'intervallo, il distacco dal primo o l'energia (si
        cambia con un clic sulla testata). L'Attack Mode acceso si vede."""
        sim = self.sim
        ordine = sim.order()
        modo = getattr(self, "modo_torre", self.MODI_TORRE[0])
        leader = ordine[0] if ordine else None
        righe = []
        for i, e in enumerate(ordine, 1):
            fuori = e.status == "retired"
            q = e.carica()
            cq = T.OK if q > 0.35 else (T.WARN if q > 0.15 else T.BAD)
            tag = None
            if e.attack_attivo > 0:
                tag = ("ATTACK", GG.VIOLA)
            elif sim.col_boost and e.boost_fatto and modo == "ENERGIA":
                tag = ("BOOST", T.OK)
            if fuori:
                valore = ("RIT", T.BAD)
            elif e.status == "pitting":
                valore = ("BOOST", T.ACCENT)
            elif modo == "ENERGIA":
                valore = (f"{q * 100:.0f}%", cq)
            elif i == 1:
                valore = ("LEADER" if modo == "INTERVALLO" else "PRIMO", (200, 206, 218))
            else:
                rif = leader if modo == "DISTACCO" else ordine[i - 2]
                valore = (GG.distacco(rif.dist - e.dist, sim.track_len,
                                      max(20.0, sim.track_len / max(30.0, e.last_lap or 60.0))),
                          T.WHITE)
            righe.append({"code": e.code, "colour": e.colour, "fuori": fuori, "tag": tag,
                          "mio": e.is_player, "viola": e.code == sim.best_lap_by and not fuori,
                          "valore": valore, "icona": ("batteria", q, cq)})
        resta = sim.tempo_restante()
        testa = (("ULTIMO", "GIRO", "") if sim.ultimo_giro
                 else ("FINE", _orologio(resta), ""))
        self._torre_testa, y0, rh = GG.torre(surf, r, testa, modo, righe)
        self._righe_torre = (r, y0, rh, [e.driver_id for e in ordine])

    def _pannello(self, surf, r, e) -> None:
        """Le nostre due macchine viste dal muretto.

        Tre numeri e sono quelli che decidono la gara: quanta energia resta e
        di quanti giri si e' avanti o indietro sul bisogno, quanto Attack Mode
        si ha ancora in mano, e se il Boost e' fatto.
        """
        sim = self.sim
        colore = tuple(e.colour[:3])
        GG.fondo_pannello(surf, r, colore)
        # ---- riga uno: la posizione, il nome, il tachimetro
        GG.parallelogramma(surf, pygame.Rect(r.x + 12, r.y + 8, 58, 28), colore)
        T.text(surf, f"P{e.position}", (r.x + 41, r.y + 11), 20, T.WHITE, bold=True,
               align="center")
        parti = e.name.split()
        cognome = GG.cognome(e.name)
        T.text(surf, cognome, (r.x + 80, r.y + 7), 19, T.WHITE, bold=True, maxw=170)
        larga_c = min(170, T.width(cognome, 19, bold=True))
        T.text(surf, (parti[0] + "  -  " if len(parti) > 1 else "") + e.squadra.upper(),
               (r.x + 80, r.y + 29), 10, GG.GRIGIO, bold=True)
        stato = {"pitting": ("AL BOOST", T.ACCENT), "retired": ("RITIRATO", T.BAD)}.get(e.status)
        if stato:
            GG.pastiglia(surf, r.x + 92 + larga_c, r.y + 11, stato[0], stato[1])
        elif e.attack_attivo > 0:
            GG.pastiglia(surf, r.x + 92 + larga_c, r.y + 11, "ATTACK MODE", GG.VIOLA)
        if e.damage > 6:
            GG.pastiglia(surf, r.right - 176, r.y + 11, f"DANNI {e.damage:.0f}%", T.BAD)
        v = sim.speed_of(e)
        GG.arco(surf, (r.right - 140, r.y + 22), 13, min(1.0, v / 300.0), colore)
        T.text(surf, f"{v:.0f}", (r.right - 42, r.y + 4), 26, T.WHITE, bold=True, mono=True,
               align="right")
        T.text(surf, "KM/H", (r.right - 12, r.y + 16), 10, GG.GRIGIO, bold=True, align="right")
        # ---- riga due: l'energia, che qui e' tutto
        y = r.y + 42
        q = e.carica()
        cq = T.OK if q > 0.35 else (T.WARN if q > 0.15 else T.BAD)
        T.text(surf, "ENERGIA", (r.x + 16, y + 1), 10, GG.GRIGIO, bold=True)
        GG.segmenti(surf, pygame.Rect(r.x + 72, y + 1, 120, 11), q, cq, 14)
        T.text(surf, f"{e.energia:.1f} kWh", (r.x + 200, y - 1), 12, cq, mono=True, bold=True)
        margine = sim.margine_energia(e)
        cm = T.OK if margine > 0.4 else (T.WARN if margine > -0.2 else T.BAD)
        T.text(surf, f"{margine:+.1f} giri", (r.right - 14, y - 1), 13, cm, mono=True,
               align="right", bold=True)
        if e.push_mode < 0.995:
            GG.pastiglia(surf, r.right - 150, y - 2, "RISPARMIO", T.WARN)
        elif e.push_mode > 1.005:
            GG.pastiglia(surf, r.right - 150, y - 2, "SPINGE", T.OK)
        # ---- riga tre: Attack Mode e Pit Boost
        y = r.y + 64
        if e.attack_attivo > 0:
            T.text(surf, "ATTACK MODE", (r.x + 16, y + 1), 10, GG.VIOLA, bold=True)
            GG.segmenti(surf, pygame.Rect(r.x + 100, y + 1, 92, 11),
                        e.attack_attivo / max(1.0, sim.attack_durata), GG.VIOLA, 10)
            T.text(surf, f"{e.attack_attivo:.0f}s", (r.x + 200, y - 1), 12, GG.VIOLA,
                   mono=True, bold=True)
        else:
            resta = sim.attack_usi_max - e.attack_usi
            T.text(surf, "ATTACK MODE", (r.x + 16, y + 1), 10, GG.GRIGIO, bold=True)
            for k in range(sim.attack_usi_max):
                pygame.draw.rect(surf, GG.VIOLA if k < resta else (44, 48, 60),
                                 (r.x + 100 + k * 20, y + 1, 16, 11), border_radius=3)
            T.text(surf, f"{e.attack_resta / 60:.0f}' in mano",
                   (r.x + 108 + sim.attack_usi_max * 20, y - 1), 12,
                   T.DIM if resta else T.BAD)
        if sim.col_boost:
            if e.boost_fatto:
                GG.pastiglia(surf, r.right - 96, y - 2, "BOOST FATTO", T.OK)
            elif sim.finestra_boost(e):
                GG.pastiglia(surf, r.right - 96, y - 2, "IN FINESTRA", T.GOLD)
            elif q > sim.boost_max:
                T.text(surf, f"boost sotto il {sim.boost_max * 100:.0f}%",
                       (r.right - 14, y - 1), 12, T.DIM_2, align="right")
            else:
                GG.pastiglia(surf, r.right - 112, y - 2, "FINESTRA PERSA", T.BAD)
        # ---- riga quattro: i tempi
        y = r.y + 88
        T.text(surf, "GIRO", (r.x + 16, y + 2), 10, GG.GRIGIO, bold=True)
        T.text(surf, T.fmt_time(e.giro_scorso) if e.giro_scorso else "--:--.---",
               (r.x + 50, y), 13, T.WHITE, mono=True, bold=True)
        T.text(surf, "MIGLIORE", (r.x + 160, y + 2), 10, GG.GRIGIO, bold=True)
        T.text(surf, T.fmt_time(e.best_lap) if e.best_lap < 900 else "--:--.---",
               (r.x + 224, y), 13,
               GG.VIOLA if e.best_lap and abs(e.best_lap - sim.best_lap) < 0.002
               else T.WHITE, mono=True, bold=True)
        # ---- la radio
        if e.domanda:
            resta = e.domanda["scadenza"] - e.lap
            T.text(surf, e.code, (r.x + 16, r.bottom - 22), 11, T.GOLD, bold=True)
            larghe = (104 if r.w >= 430 else 88) * 2 + 6
            T.text(surf, e.domanda["testo"], (r.x + 56, r.bottom - 23), 13, T.TEXT,
                   maxw=r.w - 92 - larghe)
            T.text(surf, f"{max(0, resta)}", (r.right - 16 - larghe - 20,
                                              r.bottom - 23), 12, T.WARN, mono=True,
                   bold=True)
            return
        m = sim.radio_of(e.driver_id)
        if m:
            chi = "MURETTO" if m["chi"] == "muretto" else e.code
            col = T.ACCENT if m["chi"] == "muretto" else T.GOLD
            T.text(surf, chi, (r.x + 16, r.bottom - 22), 11, col, bold=True)
            T.text(surf, m["text"], (r.x + 88, r.bottom - 23), 13, T.DIM,
                   maxw=r.w - 108)
