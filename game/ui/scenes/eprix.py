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
from .. import theme as T
from .. import bandiere, trackdraw
from ..app import Scene
from ..widgets import Button

SPEEDS = [0, 1, 4, 12, 40]
SPEED_LABELS = ["II", "x1", "x4", "x12", "x40"]


def _orologio(s: float) -> str:
    m, sec = divmod(max(0.0, s), 60.0)
    return f"{int(m)}:{int(sec):02d}"


class EPrixScene(Scene):
    # la barra: due righe di comandi dove c'e' altezza, una sola dove non ce
    # n'e', perche' l'altezza la vuole il tabellone che ha ventidue righe
    BARRA_H = 200
    BARRA_STRETTA = 168
    ALTEZZA_DUE_RIGHE = 700
    CRONACA_W = 280

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
        self.build()

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
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
    def update(self, dt: float) -> None:
        super().update(dt)
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
        self.result_rows = [
            {"pos": i, "code": e.code, "name": e.name, "squadra": e.squadra,
             "status": e.status, "energia": e.carica(), "attack": e.attack_usi,
             "boost": e.boost_fatto}
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
        surf.fill(T.BG)
        if self.sim is None:
            self._draw_prep(surf, w, h)
        elif self.fase == "quali":
            self._draw_quali(surf, w, h)
        elif self.sim.finished:
            self._draw_fine(surf, w, h)
        else:
            self._draw_gara(surf, w, h)
        super().draw(surf)

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
        T.text(surf, "ENERGIA", (r.x + 560, y), 11, T.DIM_2, bold=True)
        T.text(surf, "ATTACK", (r.x + 650, y), 11, T.DIM_2, bold=True)
        T.text(surf, "BOOST", (r.x + 730, y), 11, T.DIM_2, bold=True)
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
                T.text(surf, "RITIRATO", (r.x + 560, y), 12, T.BAD)
            else:
                T.text(surf, f"{riga['energia'] * 100:.0f}%", (r.x + 560, y), 12, col)
                T.text(surf, str(riga["attack"]), (r.x + 660, y), 12, col)
                T.text(surf, "si" if riga["boost"] else "NO", (r.x + 740, y), 12,
                       col if riga["boost"] else T.BAD)
            y += rh

    # ------------------------------------------------------------- la gara viva
    def _draw_gara(self, surf, w: int, h: int) -> None:
        self._header(surf, w)
        barra_y = h - 84 - self.barra_h(h)
        tower_w = max(300, min(420, int(w * 0.28)))
        vista = pygame.Rect(20, 68, w - tower_w - 48, barra_y - 76)
        cronaca = int(min(self.CRONACA_W, max(0, vista.w * 0.34)))
        if cronaca >= 180:
            self._mappa(surf, pygame.Rect(vista.x, vista.y, vista.w - cronaca - 8,
                                          vista.h))
            self._cronaca(surf, pygame.Rect(vista.right - cronaca, vista.y, cronaca,
                                            vista.h))
        else:
            self._mappa(surf, vista)
        self._torre(surf, pygame.Rect(w - tower_w - 20, 68, tower_w, barra_y - 76))
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

    def _mappa(self, surf, vista) -> None:
        sim = self.sim
        T.panel(surf, vista, (13, 17, 24), radius=10, border=T.LINE)
        if self.pts is None or self.pts_rect != tuple(vista):
            self.pts = trackdraw.fit_points(self.track, vista.inflate(-30, -30))
            self.pts_rect = tuple(vista)
        trackdraw.draw_track(surf, self.track, vista, width=14, pts=self.pts)
        self._etichette = []
        for e in reversed(sim.order()):
            if e.status == "retired":
                continue
            quota = self.track.pos_at(e.lap_fraction(sim.track_len))
            off = -7 if e.position % 2 == 0 else 7
            x, y = trackdraw.car_pos(self.pts, quota, off * 0.55)
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

    def _cronaca(self, surf, r) -> None:
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CRONACA", (r.x + 14, r.y + 12), 11, T.DIM_2, bold=True)
        cols = {"pass": T.OK, "dnf": T.BAD, "pit": T.ACCENT, "sc": T.GOLD,
                "attack": (183, 96, 255), "warn": T.WARN, "flag": T.GOLD,
                "pen": (255, 120, 90), "info": T.DIM}
        y = r.y + 34
        for ev in self.sim.events:
            if y > r.bottom - 20:
                break
            c = cols.get(ev["kind"], T.DIM)
            T.text(surf, f"g{ev['lap']}", (r.x + 14, y), 11, T.DIM_2, mono=True)
            righe = T.wrap(ev["text"], 12, r.w - 62)
            for k, riga in enumerate(righe[:2]):
                T.text(surf, riga, (r.x + 48, y + k * 14), 12, c)
            y += 14 * min(2, len(righe)) + 4

    def _torre(self, surf, r) -> None:
        """Il tabellone. Le colonne sono quelle che contano qui: energia,
        Attack Mode e Boost, non gomme e distacchi."""
        sim = self.sim
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "POS  PILOTA", (r.x + 14, r.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "ENERGIA", (r.right - 118, r.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "AM", (r.right - 46, r.y + 12), 11, T.DIM_2, bold=True)
        T.text(surf, "PB", (r.right - 20, r.y + 12), 11, T.DIM_2, bold=True,
               align="right")
        ordine = sim.order()
        y = r.y + 34
        rh = min(24.0, (r.h - 46) / max(1, len(ordine)))
        dim = 13 if rh >= 20 else (12 if rh >= 15 else 11)
        for i, e in enumerate(ordine, 1):
            mio = e.is_player
            if mio:
                T.panel(surf, (r.x + 8, y - 1, r.w - 16, rh - 1), T.PANEL_3, radius=5)
            T.text(surf, str(i), (r.x + 30, y), dim, T.DIM, align="right")
            pygame.draw.rect(surf, e.colour, (r.x + 38, y + 2, 3, max(8, int(rh) - 6)))
            col = T.BAD if e.status == "retired" else (T.TEXT if mio else T.DIM)
            T.text(surf, e.code, (r.x + 48, y), dim, col, bold=mio, mono=True)
            T.text(surf, e.squadra, (r.x + 94, y + 1), 11, T.DIM_2,
                   maxw=r.w - 230)
            if e.status == "retired":
                T.text(surf, "RIT", (r.right - 20, y), 11, T.BAD, align="right")
                y += rh
                continue
            q = e.carica()
            cq = T.OK if q > 0.35 else (T.WARN if q > 0.15 else T.BAD)
            T.bar(surf, (r.right - 118, y + 5, 44, 7), q * 100, 100, cq)
            T.text(surf, f"{q * 100:.0f}", (r.right - 66, y), 11, cq, mono=True,
                   align="right")
            am = "ON" if e.attack_attivo > 0 else str(
                sim.attack_usi_max - e.attack_usi)
            T.text(surf, am, (r.right - 40, y), 11,
                   (183, 96, 255) if e.attack_attivo > 0 else T.DIM_2)
            if sim.col_boost:
                T.text(surf, "si" if e.boost_fatto else "-", (r.right - 20, y), 11,
                       T.OK if e.boost_fatto else T.WARN, align="right")
            y += rh

    def _pannello(self, surf, r, e) -> None:
        """Le nostre due macchine viste dal muretto.

        Tre numeri e sono quelli che decidono la gara: quanta energia resta e
        di quanti giri si e' avanti o indietro sul bisogno, quanto Attack Mode
        si ha ancora in mano, e se il Boost e' fatto.
        """
        sim = self.sim
        T.panel(surf, r, T.PANEL, radius=10, border=T.LINE)
        pygame.draw.rect(surf, e.colour, (r.x, r.y + 8, 4, r.h - 16))
        # ---- riga uno
        T.text(surf, f"P{e.position}", (r.x + 16, r.y + 8), 15, T.GOLD, bold=True)
        T.text(surf, e.name, (r.x + 54, r.y + 8), 16, T.TEXT, bold=True, maxw=170)
        stato = {"pitting": "AL BOOST", "retired": "RITIRATO"}.get(e.status, "")
        if stato:
            T.text(surf, stato, (r.x + 230, r.y + 10), 12,
                   T.ACCENT if e.status == "pitting" else T.BAD, bold=True)
        if e.damage > 6:
            T.text(surf, f"DANNI {e.damage:.0f}%", (r.right - 100, r.y + 10), 12,
                   T.BAD, bold=True, align="right")
        T.text(surf, f"{sim.speed_of(e):.0f}", (r.right - 44, r.y + 4), 22, T.TEXT,
               bold=True, mono=True, align="right")
        T.text(surf, "km/h", (r.right - 14, r.y + 14), 11, T.DIM_2, align="right")
        # ---- riga due: l'energia, che qui e' tutto
        y = r.y + 36
        q = e.carica()
        cq = T.OK if q > 0.35 else (T.WARN if q > 0.15 else T.BAD)
        T.text(surf, "ENERGIA", (r.x + 16, y + 1), 11, T.DIM_2, bold=True)
        T.bar(surf, (r.x + 74, y + 4, 96, 9), q * 100, 100, cq)
        T.text(surf, f"{e.energia:.1f} kWh", (r.x + 180, y), 12, cq, mono=True)
        margine = sim.margine_energia(e)
        cm = T.OK if margine > 0.4 else (T.WARN if margine > -0.2 else T.BAD)
        T.text(surf, f"{margine:+.1f} giri", (r.right - 14, y), 13, cm, mono=True,
               align="right", bold=True)
        if e.push_mode < 0.995:
            T.text(surf, "RISPARMIO", (r.right - 86, y + 1), 11, T.WARN, bold=True,
                   align="right")
        elif e.push_mode > 1.005:
            T.text(surf, "SPINGE", (r.right - 86, y + 1), 11, T.OK, bold=True,
                   align="right")
        # ---- riga tre: Attack Mode e Pit Boost
        y = r.y + 60
        if e.attack_attivo > 0:
            T.text(surf, "ATTACK MODE", (r.x + 16, y + 1), 11, (183, 96, 255),
                   bold=True)
            T.bar(surf, (r.x + 100, y + 4, 70, 9), e.attack_attivo,
                  max(1.0, sim.attack_durata), (183, 96, 255))
            T.text(surf, f"{e.attack_attivo:.0f}s", (r.x + 180, y), 12,
                   (183, 96, 255), mono=True)
        else:
            resta = sim.attack_usi_max - e.attack_usi
            T.text(surf, "ATTACK MODE", (r.x + 16, y + 1), 11, T.DIM_2, bold=True)
            T.text(surf, f"{resta} da prendere, {e.attack_resta / 60:.0f}' in mano",
                   (r.x + 100, y), 12, T.DIM if resta else T.BAD)
        if sim.col_boost:
            if e.boost_fatto:
                T.text(surf, "BOOST FATTO", (r.right - 14, y), 12, T.OK, bold=True,
                       align="right")
            elif sim.finestra_boost(e):
                T.text(surf, "IN FINESTRA", (r.right - 14, y), 12, T.GOLD, bold=True,
                       align="right")
            elif q > sim.boost_max:
                T.text(surf, f"finestra a {sim.boost_max * 100:.0f}%",
                       (r.right - 14, y), 12, T.DIM_2, align="right")
            else:
                T.text(surf, "FINESTRA PERSA", (r.right - 14, y), 12, T.BAD,
                       bold=True, align="right")
        # ---- riga quattro: i tempi
        y = r.y + 84
        T.text(surf, "GIRO", (r.x + 16, y + 2), 11, T.DIM_2, bold=True)
        T.text(surf, T.fmt_time(e.giro_scorso) if e.giro_scorso else "--:--.---",
               (r.x + 56, y), 13, T.TEXT, mono=True)
        T.text(surf, "MIGLIORE", (r.x + 160, y + 2), 11, T.DIM_2, bold=True)
        T.text(surf, T.fmt_time(e.best_lap) if e.best_lap < 900 else "--:--.---",
               (r.x + 224, y), 13,
               (183, 96, 255) if e.best_lap and abs(e.best_lap - sim.best_lap) < 0.002
               else T.TEXT, mono=True)
        T.text(surf, f"piano {e.piano}", (r.right - 14, y), 12, T.DIM_2,
               align="right")
        # ---- le etichette dei comandi
        if self.due_righe():
            T.text(surf, "PASSO", (r.x + 16, r.y + 148), 11, T.DIM_2, bold=True)
        if e.delegato:
            T.text(surf, "TEAM PRINCIPAL", (r.right - 14, r.y + 96), 11, T.ACCENT,
                   bold=True, align="right")
        elif e.scambio_a and e.scambio_rifiuto:
            T.text(surf, "NON CEDE", (r.right - 14, r.y + 96), 11, T.BAD,
                   bold=True, align="right")
        elif e.scambio_a:
            T.text(surf, "CEDE IL POSTO", (r.right - 14, r.y + 96), 11, T.ACCENT,
                   bold=True, align="right")
        elif e.tieni_posizioni:
            T.text(surf, "POSIZIONI FERME", (r.right - 14, r.y + 96), 11, T.WARN,
                   bold=True, align="right")
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
