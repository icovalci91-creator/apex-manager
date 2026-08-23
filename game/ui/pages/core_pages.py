"""Pagine: quartier generale, vettura e assetto, sviluppo, ingegneri."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import development, economy, engineering, powertrain, rules, setup as SETUP
from ...model.car import SETUP_KEYS
from ...sim import session as S
from .. import theme as T
from .. import cardraw
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, ScrollPanel, Slider, card, stat_row


# =========================================================== QUARTIER GENERALE
class HQPage(Page):
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.news = ScrollList((r.x + r.w * 0.68 + 8, r.y + 124, r.w * 0.32 - 20, r.h - 132),
                               row_h=70, draw_row=self._draw_news)
        self.widgets.append(self.news)

    def refresh(self) -> None:
        self.build()
        self.news.items = list(self.gs.inbox)

    def _draw_news(self, surf, rect, i, item) -> None:
        colours = {"tecnico": T.ACCENT, "gara": T.GOLD, "team": T.OK,
                   "mercato": (200, 140, 255), "regole": T.WARN}
        c = colours.get(item.get("kind"), T.DIM)
        pygame.draw.rect(surf, c, (rect.x + 4, rect.y + 8, 3, rect.h - 16))
        T.text(surf, item.get("kind", "info").upper(), (rect.x + 16, rect.y + 6), 11, c, bold=True)
        for j, ln in enumerate(T.wrap(item["text"], 13, rect.w - 30)[:3]):
            T.text(surf, ln, (rect.x + 16, rect.y + 21 + j * 15), 13, T.TEXT)

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        col = T.hex_rgb(team.colour)
        cw = (r.w - 48) / 4
        card(surf, (r.x, r.y, cw, 86), "Liquidita'", T.fmt_money(team.cash),
             f"budget annuo {team.budget_base:.0f} M$", accent=T.OK)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Valutazione vettura",
             f"{team.car.rating:.1f}", _car_rank_text(gs, team), accent=col)
        # il livello non ha piu' un tetto: quello che conta e' dove sta rispetto
        # agli altri e al riferimento del ciclo tecnico
        spent, limit, frac = economy.cap_usage(gs, team)
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Budget cap",
             f"{frac*100:.0f}%", f"{spent:.1f} di {limit:.0f} M$",
             colour=T.BAD if frac > 1 else T.TEXT, accent=T.WARN)
        nt = gs.next_track
        card(surf, (r.x + 3 * (cw + 16), r.y, cw, 86), "Prossimo appuntamento",
             nt.name if nt else "-", nt.gp if nt else "stagione conclusa", accent=T.ACCENT)

        # prossima gara con tracciato
        left = pygame.Rect(r.x, r.y + 92, r.w * 0.33, r.h - 100)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROSSIMA GARA", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        if nt:
            T.text(surf, nt.gp, (left.x + 16, left.y + 30), 18, T.TEXT, bold=True, maxw=left.w - 32)
            trackdraw.draw_track(surf, nt, (left.x + 10, left.y + 58, left.w - 20, left.h * 0.42),
                                 width=7, colour=(58, 70, 92))
            y = left.y + 58 + left.h * 0.42 + 10
            info = [("Lunghezza", f"{nt.length_km:.3f} km"), ("Giri", str(nt.laps)),
                    ("Curve", str(nt.corners)), ("Perdita ai box", f"{nt.pit_loss:.1f} s"),
                    ("Sprint", "si" if nt.sprint else "no")]
            for k, v in info:
                T.text(surf, k, (left.x + 16, y), 13, T.DIM)
                T.text(surf, v, (left.right - 16, y), 13, T.TEXT, bold=True, align="right")
                y += 19
            y += 6
            for k, lab in (("downforce", "Carico"), ("power", "Potenza"),
                           ("tyre_wear", "Degrado"), ("overtaking", "Sorpassi")):
                T.text(surf, lab, (left.x + 16, y), 12, T.DIM)
                T.bar(surf, (left.x + 100, y + 3, left.w - 130, 7), nt.traits[k] * 100)
                y += 18

        # piloti e reparti
        mid = pygame.Rect(r.x + r.w * 0.34, r.y + 92, r.w * 0.32, r.h - 100)
        T.panel(surf, mid, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I NOSTRI PILOTI", (mid.x + 16, mid.y + 12), 12, T.DIM_2, bold=True)
        y = mid.y + 34
        for d in gs.drivers_of(team.id):
            T.panel(surf, (mid.x + 10, y, mid.w - 20, 92), T.PANEL_2, radius=8)
            T.text(surf, f"{d.number}", (mid.x + 22, y + 10), 22, col, bold=True)
            T.text(surf, d.name, (mid.x + 60, y + 10), 17, T.TEXT, bold=True, maxw=mid.w - 150)
            T.text(surf, f"{d.nat} - {d.age} anni - {d.salary:.1f} M$/anno",
                   (mid.x + 60, y + 32), 12, T.DIM)
            T.text(surf, f"{d.overall:.0f}", (mid.right - 22, y + 10), 22,
                   T.stat_colour(d.overall, 70, 90), bold=True, align="right")
            bx = mid.x + 20
            for lab, v in (("Passo", d.pace), ("Duello", d.racecraft),
                           ("Costanza", d.consistency), ("Gomme", d.tyre_mgmt)):
                T.text(surf, lab, (bx, y + 54), 10, T.DIM_2)
                T.bar(surf, (bx, y + 68, 66, 6), v, 100, T.stat_colour(v, 65, 90))
                bx += 74
            T.text(surf, f"morale {d.morale:.0f}", (mid.right - 22, y + 62), 12,
                   T.stat_colour(d.morale, 40, 75), align="right")
            y += 100
        y += 6
        T.text(surf, "REPARTI", (mid.x + 16, y), 12, T.DIM_2, bold=True)
        y += 20
        for lab, v in (("Aerodinamica", team.aero_strength), ("Progettazione", team.mech_strength),
                       ("Strategia", team.strategy_strength), ("Pit crew", team.pit_strength),
                       ("Affidabilita'", team.reliability_strength), ("Simulatore/assetto", team.setup_strength)):
            stat_row(surf, pygame.Rect(mid.x + 16, y, mid.w - 32, 22), lab, v)
            y += 24

        right = pygame.Rect(r.x + r.w * 0.68, r.y + 92, r.w * 0.32 - 4, r.h - 100)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "NOTIZIE DALLA SQUADRA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        super().draw(surf)


def _car_rank_text(gs, team) -> str:
    rank = sorted(gs.teams.values(), key=lambda t: -t.car.rating)
    pos = [t.id for t in rank].index(team.id) + 1
    if pos == 1:
        gap = team.car.rating - rank[1].car.rating
        return f"1a vettura della griglia, +{gap:.1f} sulla seconda"
    return f"{pos}a vettura della griglia, {team.car.rating - rank[0].car.rating:+.1f} dalla prima"


# ================================================================== VETTURA
class CarPage(Page):
    """La macchina: com'e' fatta, com'e' messa, e dove sta rispetto agli altri.

    Due sotto-pagine. Nella prima si guarda la nostra vettura, componente per
    componente, con l'assetto del weekend accanto. Nella seconda si guarda
    tutta la griglia, area per area: e' li' che si capisce dove conviene
    spendere, perche' si vede in che cosa gli altri sono avanti.
    """

    SOTTO = [("vettura", "Vettura e assetto"), ("griglia", "Confronto con la griglia")]

    def __init__(self, shell):
        super().__init__(shell)
        self.vista = "vettura"
        self.sel_part = "floor"
        self.zone: dict = {}

    # ------------------------------------------------------------ costruzione
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.sliders = {}
        self.tab_buttons = []
        for i, (key, lab) in enumerate(self.SOTTO):
            b = Button((r.x + i * 232, r.y, 224, 34), lab, style="tab")
            b.on_click = (lambda k=key: self._vista(k))
            b.active = (key == self.vista)
            self.tab_buttons.append(b)
            self.widgets.append(b)
        if self.vista == "griglia":
            self.griglia = ScrollPanel((r.x, r.y + 44, r.w, r.h - 44), self._draw_griglia,
                                       pad=18)
            self.widgets.append(self.griglia)
            self.griglia.layout()
            return

        top = r.y + 44
        alt = r.h - 44
        # tre colonne: la macchina, i suoi pezzi, il lavoro del weekend
        self.car_rect = pygame.Rect(r.x, top, r.w * 0.26, alt)
        self.comp = ScrollPanel((r.x + r.w * 0.27, top, r.w * 0.34, alt),
                                self._draw_componenti, pad=16)
        self.widgets.append(self.comp)

        costo = SETUP.sim_cost(self.team)
        self.b_sim = Button((0, 0, 10, 38), f"Simulatore  ({costo:.2f} M$)",
                            self.simulate, "normal")
        self.b_del = Button((0, 0, 10, 38), "Monta l'assetto del reparto",
                            self.delegate, "primary")
        self.b_neu = Button((0, 0, 10, 34), "Assetto neutro", self.neutral, "ghost")
        for k, lab in SETUP_KEYS.items():
            self.sliders[k] = Slider((0, 0, 10, 30), lab,
                                     self.team.car.setup.get(k, 50.0),
                                     on_change=(lambda v, k=k: self._set(k, v)))
        self.assetto = ScrollPanel((r.x + r.w * 0.62, top, r.w * 0.38, alt),
                                   self._draw_assetto, pad=16)
        self.widgets.append(self.assetto)
        self._update_markers()
        self.comp.layout()
        self.assetto.layout()

    def _vista(self, k) -> None:
        self.vista = k
        self.build()

    def _set(self, k, v) -> None:
        self.team.car.setup[k] = v
        nt = self.gs.next_track
        if nt:
            self.team.car.evaluate_setup(nt)

    def _update_markers(self) -> None:
        """Il triangolo mostra quello che il reparto crede, non quello che e'."""
        nt = self.gs.next_track
        if not nt:
            return
        SETUP.ensure_paper(self.gs, self.team, nt)
        paper = self.team.setup_paper or {}
        for k, s in self.sliders.items():
            s.marker = paper.get(k)
        self.team.car.evaluate_setup(nt)

    # ------------------------------------------------------------------ azioni
    def simulate(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        ok, msg = SETUP.run_simulator(self.gs, self.team, nt)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def delegate(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        S.auto_setup(self.gs, self.team, nt)
        for k, s in self.sliders.items():
            s.value = self.team.car.setup[k]
        self.app.toast("I meccanici hanno montato l'assetto preparato dal reparto.")

    def neutral(self) -> None:
        for k, s in self.sliders.items():
            self.team.car.setup[k] = 50.0
            s.value = 50.0
        self._set("wing", 50.0)

    def refresh(self) -> None:
        self.build()

    def handle(self, ev) -> None:
        # un clic sulla macchina sceglie il componente che sta sotto il dito
        if self.vista == "vettura" and ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for key, zona in sorted(self.zone.items(),
                                    key=lambda kv: kv[1].w * kv[1].h):
                if zona.collidepoint(ev.pos):
                    self.sel_part = key
                    return
        super().handle(ev)

    # ------------------------------------------------------------ contenuti
    def _draw_componenti(self, f) -> None:
        gs, team = self.gs, self.team
        campo = engineering.part_field(gs)
        pos = engineering.part_standing(gs, team)
        f.head("Componenti")
        f.line("livello, posizione in griglia e usura - il colore e' lo stesso "
               "della macchina", 11, T.DIM_2, gap=8)
        for k, meta in C.CAR_PARTS.items():
            p = team.car.parts[k]
            lo, media, hi = campo.get(k, (p.perf, p.perf, p.perf))
            scelto = (k == self.sel_part)
            rango = 1 + sum(1 for t in gs.teams.values() if t.car.parts[k].perf > p.perf)
            colore = (T.OK if pos.get(k, 0) > 0.25 else
                      (T.BAD if pos.get(k, 0) < -0.25 else T.WARN))
            riga = f.box(30, gap=0)
            if f.surf:
                if scelto:
                    T.panel(f.surf, riga.inflate(8, 0), T.PANEL_3, radius=6)
                T.text(f.surf, meta["label"], (riga.x, riga.y + 6), 14,
                       T.TEXT if scelto else T.DIM, bold=scelto, maxw=riga.w * 0.40)
                # la barra e' la griglia: dal peggiore al migliore, noi dentro
                bx, bw = riga.x + riga.w * 0.42, riga.w * 0.26
                pygame.draw.rect(f.surf, T.PANEL_3, (bx, riga.y + 11, bw, 7),
                                 border_radius=3)
                q = 0.5 if hi - lo < 0.01 else (p.perf - lo) / (hi - lo)
                pygame.draw.rect(f.surf, colore,
                                 (int(bx + max(0.0, min(1.0, q)) * bw) - 3, riga.y + 8,
                                  6, 13), border_radius=2)
                mq = 0.5 if hi - lo < 0.01 else (media - lo) / (hi - lo)
                pygame.draw.line(f.surf, T.DIM, (int(bx + mq * bw), riga.y + 8),
                                 (int(bx + mq * bw), riga.y + 21))
                T.text(f.surf, f"{p.perf:.1f}", (riga.x + riga.w * 0.78, riga.y + 6), 13,
                       T.TEXT, bold=True, align="right")
                T.text(f.surf, f"{rango}i", (riga.x + riga.w * 0.86, riga.y + 6), 12,
                       colore, bold=True, align="right")
                cc = T.OK if p.condition > 80 else (T.WARN if p.condition > 55 else T.BAD)
                T.text(f.surf, f"{p.condition:.0f}%", (riga.x + riga.w, riga.y + 6), 13,
                       cc, bold=True, align="right")
            b = Button(riga, "", None, "invisible")
            b.on_click = (lambda k=k: setattr(self, "sel_part", k))
            f.at(b, riga)
            f.y = riga.bottom + 2
        f.gap(10)

        f.head("Prestazioni derivate")
        prof = engineering.car_profile(team, gs)
        for key, lab in engineering.AREAS.items():
            f.bar_row(lab, prof[key])
        f.gap(8)
        cost = team.car.repair_cost()
        f.line(f"Costo di ripristino stimato: {cost:.2f} M$", 13,
               T.WARN if cost > 0.5 else T.DIM, gap=10)

        f.head("Aggiornamenti recenti")
        recenti = [v for v in reversed(team.upgrade_log or [])][:6]
        if not recenti:
            f.par("Nessun pacchetto portato in pista finora: quello che si vede e' la "
                  "macchina con cui e' cominciata la stagione.")
            return
        for v in recenti:
            col = _esito_colore(v)
            f.kv(f"{v['label']} ({v['size']})",
                 f"{v['reso']:+.1f} su {v['atteso']:+.1f} attesi", 12, col, gap=1)
            f.line(f"stagione {v['stagione']}, gara {v['gara']} - {v['esito']}", 11,
                   T.DIM_2, gap=6)

    def _draw_assetto(self, f) -> None:
        gs, team, car = self.gs, self.team, self.team.car
        nt = gs.next_track
        f.head("Assetto")
        if not nt:
            f.par("Nessuna gara in programma: l'assetto si prepara quando si sa dove "
                  "si va a correre.", 13, T.DIM)
            return
        q = SETUP.believed_quality(team)
        qc = T.OK if q > 0.85 else (T.WARN if q > 0.6 else T.BAD)
        f.line(f"per {nt.name}", 16, T.TEXT, bold=True, gap=8)
        riga = f.box(18, gap=4)
        if f.surf:
            T.text(f.surf, "Vicinanza al riferimento", (riga.x, riga.y), 13, T.DIM)
            T.bar(f.surf, (riga.x + 170, riga.y + 4, riga.w - 230, 10), q * 100)
            T.text(f.surf, f"{q*100:.0f}%", (riga.x + riga.w, riga.y), 14, qc,
                   bold=True, align="right")
        err = SETUP.paper_error(team, nt, team.sim_sessions)
        fid = max(0.0, min(1.0, 1.0 - (err - SETUP.ERR_MIN) / (SETUP.ERR_MAX - SETUP.ERR_MIN)))
        f.kv("Riferimento del reparto", f"+/-{err:.0f} punti", 13,
             T.stat_colour(fid * 100, 40, 75))
        f.par(f"Il triangolo dorato e' quello che il reparto crede sia giusto: "
              f"{team.sim_sessions} sessioni al simulatore su {SETUP.SIM_MAX}. "
              f"Il resto lo dira' la pista.")
        f.line(f"Downforce {car.downforce:.2f}   Drag {car.drag:.2f}   "
               f"Potenza {car.power:.2f}   Grip {car.mech_grip:.2f}", 12, T.DIM, gap=12)

        for k in SETUP_KEYS:
            f.widget(self.sliders[k], 30, gap=6)
        f.gap(6)
        f.row([self.b_sim, self.b_del], 38)
        f.widget(self.b_neu, 34, gap=14)

        f.head("Riscontro degli ingegneri")
        for line in S.setup_hints(team, nt):
            f.par(line, 12, T.DIM, gap=2)

    def _draw_griglia(self, f) -> None:
        """Tutta la griglia, area per area: dove siamo avanti e dove indietro."""
        gs, team = self.gs, self.team
        f.head("Confronto con la griglia")
        f.par("Ogni casella e' quanto vale quella squadra in quell'area, da 0 a 100, "
              "rapportato al resto della griglia. La nostra riga e' quella vera; le "
              "altre sono stime del nostro scouting, e diventano piu' precise con le "
              "gare disputate e con chi lavora in quel reparto.", 12, T.DIM_2, gap=12)

        aree = list(engineering.AREAS.items())
        righe = []
        for t in gs.teams.values():
            prof = (engineering.car_profile(t, gs) if t.id == team.id
                    else engineering.estimate(gs, team, t))
            tot = sum(prof[a] for a, _l in aree) / len(aree)
            righe.append((t, prof, tot))
        righe.sort(key=lambda x: -x[2])

        nome_w = 190
        tot_w = 84
        col_w = max(70, (f.w - nome_w - tot_w - 12) / len(aree))
        intest = f.box(46, gap=2)
        if f.surf:
            T.text(f.surf, "SQUADRA", (intest.x, intest.bottom - 16), 11, T.DIM_2, bold=True)
            T.text(f.surf, "MEDIA", (intest.x + nome_w + tot_w - 8, intest.bottom - 16), 11,
                   T.DIM_2, bold=True, align="right")
            for i, (_a, lab) in enumerate(aree):
                x = intest.x + nome_w + tot_w + i * col_w
                for j, parola in enumerate(T.wrap(lab, 11, col_w - 16, bold=True)[:3]):
                    T.text(f.surf, parola, (x, intest.y + j * 13), 11, T.DIM_2, bold=True,
                           maxw=col_w - 10)

        migliori = {a: max(r[1][a] for r in righe) for a, _l in aree}
        for t, prof, tot in righe:
            noi = (t.id == team.id)
            riga = f.box(30, gap=2)
            if not f.surf:
                continue
            if noi:
                T.panel(f.surf, riga.inflate(10, 2), T.PANEL_3, radius=6)
            col = T.hex_rgb(t.colour)
            pygame.draw.rect(f.surf, col, (riga.x, riga.y + 5, 4, riga.h - 10))
            T.text(f.surf, t.name, (riga.x + 12, riga.y + 6), 14,
                   T.TEXT if noi else T.DIM, bold=noi, maxw=nome_w - 20)
            T.text(f.surf, f"{tot:.0f}", (riga.x + nome_w + tot_w - 8, riga.y + 6), 15,
                   T.stat_colour(tot, 40, 80), bold=True, align="right")
            for i, (a, _lab) in enumerate(aree):
                v = prof[a]
                x = riga.x + nome_w + tot_w + i * col_w
                cella = pygame.Rect(int(x), riga.y + 3, int(col_w - 6), riga.h - 6)
                tinta = T.mix(T.PANEL_2, T.stat_colour(v, 35, 78), 0.30 + 0.55 * (v / 100.0))
                pygame.draw.rect(f.surf, tinta, cella, border_radius=4)
                if abs(v - migliori[a]) < 0.01:
                    pygame.draw.rect(f.surf, T.GOLD, cella, 2, border_radius=4)
                T.text(f.surf, f"{v:.0f}", (cella.centerx, cella.y + 5), 13,
                       T.TEXT, bold=noi, align="center")
        f.gap(14)

        # dove conviene mettere i soldi, viste le gare che restano
        f.head("Dove conviene lavorare")
        bias = engineering.calendar_bias(gs)
        rep = engineering.field_report(gs)
        ordinati = sorted(engineering.AREAS.items(),
                          key=lambda kv: -(max(0.0, rep[kv[0]]["best"] - rep[kv[0]]["mine"])
                                           * (0.6 + 0.8 * bias.get(kv[0], 0.5))))
        intest = f.box(18, gap=2)
        if f.surf:
            for lab, x in (("AREA", 0), ("POSIZIONE", 260), ("DAL MIGLIORE", 380),
                           ("QUANTO LA CHIEDONO LE GARE CHE RESTANO", 520)):
                T.text(f.surf, lab, (intest.x + x, intest.y), 11, T.DIM_2, bold=True)
        for a, lab in ordinati:
            d = rep[a]
            gap = d["delta"]
            colore = T.OK if gap >= -2 else (T.WARN if gap > -14 else T.BAD)
            riga = f.box(22, gap=2)
            if not f.surf:
                continue
            T.text(f.surf, lab, (riga.x, riga.y + 3), 13, T.TEXT, maxw=250)
            T.text(f.surf, f"{d['rank']}i della griglia", (riga.x + 260, riga.y + 3), 13,
                   T.DIM)
            T.text(f.surf, f"{gap:+.0f} da {d['best_team']}", (riga.x + 380, riga.y + 3),
                   13, colore, bold=True)
            dom = bias.get(a, 0.5)
            T.bar(f.surf, (riga.x + 520, riga.y + 8, 240, 8), dom * 100, 100,
                  T.GOLD if dom > 0.6 else T.DIM)
            T.text(f.surf, f"{dom*100:.0f}%", (riga.x + 776, riga.y + 3), 13,
                   T.GOLD if dom > 0.6 else T.DIM)
        f.gap(6)
        f.par("Recuperare dove le gare rimaste non premiano niente e' fatica sprecata: "
              "conviene guardare insieme il distacco e la colonna qui accanto.")
        f.gap(10)
        self._pacchetti_griglia(f)

    def _pacchetti_griglia(self, f) -> None:
        """Chi ha portato cosa in pista, e cosa ci ha guadagnato.

        Quello che portano gli altri lo si vede: un fondo nuovo in griglia non
        si nasconde, e la stampa scrive di che pacchetto si tratta. Quanto vale
        davvero e' un'altra cosa: quello lo sanno loro, e noi lo stimiamo dai
        cronometri, tanto meglio quanto piu' sappiamo guardare.
        """
        gs, team = self.gs, self.team
        voci = []
        for t in gs.teams.values():
            for v in (t.upgrade_log or [])[-6:]:
                if v.get("stagione") == gs.season:
                    voci.append((t, v))
        voci.sort(key=lambda x: -x[1].get("gara", 0))
        f.head("Chi ha portato cosa, in questa stagione")
        if not voci:
            f.par("Nessuno ha ancora portato un pacchetto: si corre con le macchine di "
                  "inizio anno.")
            return
        for t, v in voci[:14]:
            noi = (t.id == team.id)
            riga = f.box(20, gap=3)
            if not f.surf:
                continue
            T.text(f.surf, f"g{v['gara']}", (riga.x, riga.y), 12, T.DIM_2)
            pygame.draw.rect(f.surf, T.hex_rgb(t.colour), (riga.x + 34, riga.y + 3, 3, 13))
            T.text(f.surf, t.short, (riga.x + 44, riga.y), 13, T.TEXT if noi else T.DIM,
                   bold=noi, maxw=150)
            T.text(f.surf, f"{v['label']} - pacchetto {v['size']}", (riga.x + 200, riga.y),
                   13, T.TEXT, maxw=300)
            if noi:
                T.text(f.surf, f"{v['reso']:+.1f} sui {v['atteso']:+.1f} promessi",
                       (riga.x + 520, riga.y), 13, _esito_colore(v), bold=True)
                T.text(f.surf, v["esito"], (riga.x + 760, riga.y), 12, T.DIM_2)
            else:
                giudizio, colore = _giudizio_esterno(gs, team, t, v)
                T.text(f.surf, giudizio, (riga.x + 520, riga.y), 13, colore)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, team, gs = self.rect, self.team, self.gs
        if self.vista == "griglia":
            super().draw(surf)
            return
        T.panel(surf, self.car_rect, T.PANEL, radius=10, border=T.LINE)
        cr = self.car_rect
        T.text(surf, "LA NOSTRA MONOPOSTO", (cr.x + 16, cr.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, f"{team.car.rating:.1f}", (cr.right - 16, cr.y + 10), 16,
               T.TEXT, bold=True, align="right")
        stand = engineering.part_standing(gs, team)
        zona = pygame.Rect(cr.x + 10, cr.y + 40, cr.w - 20, cr.h - 176)
        self.zone = cardraw.draw_car(surf, zona, T.hex_rgb(team.colour), stand,
                                     self.sel_part)
        # la scheda del pezzo scelto, sotto la macchina
        p = team.car.parts[self.sel_part]
        meta = C.CAR_PARTS[self.sel_part]
        campo = engineering.part_field(gs)
        lo, media, hi = campo.get(self.sel_part, (p.perf, p.perf, p.perf))
        v = stand.get(self.sel_part, 0.0)
        colore = T.OK if v > 0.25 else (T.BAD if v < -0.25 else T.WARN)
        y = cr.bottom - 128
        T.text(surf, meta["label"], (cr.x + 16, y), 17, T.GOLD, bold=True, maxw=cr.w - 32)
        y += 24
        T.text(surf, "Livello", (cr.x + 16, y), 13, T.DIM)
        T.text(surf, f"{p.perf:.1f}   ({p.perf - media:+.1f} sulla media)",
               (cr.right - 16, y), 13, colore, bold=True, align="right")
        y += 20
        T.text(surf, "Il migliore della griglia", (cr.x + 16, y), 13, T.DIM)
        T.text(surf, f"{hi:.1f}", (cr.right - 16, y), 13, T.TEXT, bold=True, align="right")
        y += 20
        pos = 1 + sum(1 for t in gs.teams.values()
                      if t.car.parts[self.sel_part].perf > p.perf)
        T.text(surf, "In griglia", (cr.x + 16, y), 13, T.DIM)
        T.text(surf, f"{pos}i su {len(gs.teams)}   -   usura {p.condition:.0f}%",
               (cr.right - 16, y), 13, T.TEXT, bold=True, align="right")
        y += 22
        T.paragraph(surf, "Verde dove siamo sopra la media della griglia, rosso dove siamo "
                          "sotto. Clicca la macchina o l'elenco per cambiare pezzo.",
                    (cr.x + 16, y), 11, T.DIM_2, cr.w - 32)
        super().draw(surf)


def _giudizio_esterno(gs, team, rivale, v: dict) -> tuple:
    """Cosa si riesce a capire di un pacchetto altrui, senza i loro dati.

    Si vede se sono andati avanti o no, non di quanto: il numero preciso resta
    in fabbrica loro. Piu' e' bravo il nostro scouting, meno vaga e' la lettura.
    """
    skill = (0.55 * team.scouting_strength
             + 0.45 * team._s("technical_director", "analysis")) / 100.0
    rng = gs.view_rng("pacchetti", team.id, rivale.id, str(v.get("gara", 0)))
    letto = v.get("reso", 0.0) + rng.gauss(0.0, (1.0 - 0.7 * skill) * 1.5)
    if letto > 1.4:
        return "sembra aver funzionato bene", T.OK
    if letto > 0.4:
        return "qualcosa hanno trovato", (150, 200, 90)
    if letto > -0.2:
        return "non si e' visto niente", T.WARN
    return "sembra che siano andati indietro", T.BAD


def _esito_colore(v: dict):
    return {"oltre": T.OK, "in linea": T.ACCENT, "sottotono": T.WARN,
            "fallito": T.BAD, "recuperata": T.OK, "pareggiata": T.WARN,
            "mai capita": T.BAD, "rimontata la vecchia": T.BAD}.get(v.get("esito"), T.DIM)


# ================================================================= SVILUPPO
class DevPage(Page):
    """Sviluppo: dove limare, cosa costruire, e com'e' andata l'ultima volta.

    I due pannelli scorrono: quello che c'e' da dire su un pacchetto - costo,
    fiducia, come puo' finire, quanto assetto rimette in discussione - non sta
    in uno schermo, e prima finiva sovrapposto al pulsante che lo avvia.
    """

    SIZES = ["piccolo", "medio", "grande"]

    def __init__(self, shell):
        super().__init__(shell)
        self.sel_part = "floor"
        self.sel_size = "medio"
        self._cache: dict = {}

    @property
    def dev_budget(self) -> float:
        return self.app.dev_budget

    # ------------------------------------------------------------ costruzione
    def _btn(self, key, label, action, style="normal"):
        """Un pulsante che sopravvive ai ridisegni, cosi' il mouse lo vede."""
        b = self._cache.get(key)
        if b is None:
            b = Button((0, 0, 10, 32), label, action, style)
            self._cache[key] = b
        b.label, b.on_click, b.style = label, action, style
        return b

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.alloc_sliders = {}
        for k, meta in C.CAR_PARTS.items():
            self.alloc_sliders[k] = Slider(
                (0, 0, 10, 28), meta["label"],
                self.team.resource_alloc.get(k, 0.1) * 100.0, 0, 100,
                on_change=(lambda v, k=k: self._alloc(k, v)), fmt="{:.0f}%")
        self.budget_slider = Slider((0, 0, 10, 28), "Affinamenti per gara",
                                    self.dev_budget, 0.0, 6.0,
                                    on_change=self._set_budget, fmt="{:.2f} M$")
        self.reg_slider = Slider((0, 0, 10, 28), "Risorse sul regolamento nuovo",
                                 self.team.next_reg_share * 100.0, 0.0, 90.0,
                                 on_change=self._set_reg_share, fmt="{:.0f}%")
        self.part_buttons = []
        for k, meta in C.CAR_PARTS.items():
            b = Button((0, 0, 10, 30), meta["label"], style="tab")
            b.on_click = (lambda k=k: self._pick_part(k))
            b.active = (k == self.sel_part)
            self.part_buttons.append(b)
        self.size_buttons = []
        for sz in self.SIZES:
            b = Button((0, 0, 10, 30), sz.capitalize(), style="tab")
            b.on_click = (lambda s=sz: self._pick_size(s))
            b.active = (sz == self.sel_size)
            self.size_buttons.append(b)

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        self.p_left = ScrollPanel(left, self._draw_left, pad=16)
        self.p_right = ScrollPanel(right, self._draw_right, pad=16)
        self.widgets += [self.p_left, self.p_right]
        self.p_left.layout()
        self.p_right.layout()

    # ------------------------------------------------------------------ azioni
    def _alloc(self, k, v) -> None:
        self.team.resource_alloc[k] = max(0.0, v) / 100.0

    def _set_budget(self, v) -> None:
        # il weekend di gara legge il budget dall'App: e' li' che va scritto
        self.app.dev_budget = v

    def _set_reg_share(self, v) -> None:
        """Quota del budget di sviluppo dirottata sul regolamento che verra'."""
        self.team.next_reg_share = max(0.0, min(0.90, v / 100.0))

    def _pick_part(self, k) -> None:
        self.sel_part = k
        for b, key in zip(self.part_buttons, C.CAR_PARTS.keys()):
            b.active = (key == k)

    def _pick_size(self, s) -> None:
        self.sel_size = s
        for b, sz in zip(self.size_buttons, self.SIZES):
            b.active = (sz == s)

    def balance(self) -> None:
        n = len(C.CAR_PARTS)
        for k in C.CAR_PARTS:
            self.team.resource_alloc[k] = 1.0 / n
            self.alloc_sliders[k].value = 100.0 / n

    def suggest(self) -> None:
        sug = engineering.suggested_allocation(self.gs)
        for k, v in sug.items():
            self.team.resource_alloc[k] = v
            if k in self.alloc_sliders:
                self.alloc_sliders[k].value = v * 100.0
        self.app.toast("Allocazione aggiornata secondo il parere del reparto tecnico.")

    def revert(self, tr) -> None:
        ok, msg = development.revert_spec(self.gs, self.team, tr)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def keep(self, tr) -> None:
        ok, msg = development.keep_spec(self.gs, self.team, tr)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
            self.build()

    def start_project(self) -> None:
        ok, msg = development.start_project(self.gs, self.team, self.sel_part, self.sel_size)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")

    def refresh(self) -> None:
        self.build()

    # ------------------------------------------------------------ contenuti
    def _draw_left(self, f) -> None:
        gs, team = self.gs, self.team
        f.head("Lavoro di reparto: dove limare")
        f.par("Non sono aggiornamenti: e' il lavoro continuo del reparto, che serve a "
              "capire la macchina e a sfruttarla meglio. Il salto lo fanno i pacchetti, "
              "qui accanto.")
        for k in C.CAR_PARTS:
            f.widget(self.alloc_sliders[k], 28, gap=4)
        f.gap(6)
        f.row([self._btn("bilancia", "Bilancia", self.balance, "ghost"),
               self._btn("consiglio", "Consiglio ingegneri", self.suggest, "primary")], 34)
        f.gap(10)

        if team.spec_trials:
            f.head("Specifiche in verifica", T.WARN)
            for i, tr in enumerate(team.spec_trials):
                buco = development.deficit(team, tr)
                col = T.BAD if buco < -0.05 else (T.OK if buco > 0.05 else T.WARN)
                f.kv(tr.label, f"{buco:+.1f} sulla vecchia", 14, col, key_colour=T.TEXT)
                stato = ("da decidere" if tr.state == "in prova" else
                         f"in affinamento, {max(0, development.TRIAL_RACES + 1 - tr.races)} gare")
                f.par(f"{stato}  -  {tr.news}", 12, T.DIM, gap=4)
                tetto = development.trial_ceiling(gs, team, tr) - tr.old_perf
                f.par(f"Insistere puo' portarla a {tetto:+.1f} sulla vecchia e costa "
                      f"{tr.cost * development.TRIAL_UPKEEP:.2f} M$ a gara, con un banco "
                      f"occupato.", 11, T.DIM_2, gap=4)
                riga = []
                if buco < -0.05:
                    riga.append(self._btn(
                        ("rev", i), f"Rimonta la vecchia "
                        f"({tr.cost * development.REVERT_SHARE:.2f} M$)",
                        (lambda t=tr: self.revert(t)), "danger"))
                if tr.state == "in prova":
                    riga.append(self._btn(("keep", i), "Tienila e affinala",
                                          (lambda t=tr: self.keep(t)), "primary"))
                if riga:
                    f.row(riga, 32)
                f.gap(8)
        elif team.dev_projects:
            f.head("Specifiche in verifica")
            f.par("Niente in discussione: quello che e' arrivato in pista ha funzionato.")

        f.head("Aggiornamenti portati in pista")
        log = list(reversed(team.upgrade_log or []))
        if not log:
            f.par("Il registro e' vuoto. Da qui in avanti ogni pacchetto lascia una riga: "
                  "quanto prometteva, quanto ha reso, e come e' finita.")
            return
        reso = sum(v["reso"] for v in log)
        atteso = sum(v["atteso"] for v in log)
        resa = (reso / atteso * 100.0) if atteso > 0.01 else 0.0
        f.kv("In totale", f"{reso:+.1f} punti su {atteso:+.1f} promessi ({resa:.0f}%)",
             13, T.OK if resa > 85 else (T.WARN if resa > 55 else T.BAD))
        f.gap(4)
        for v in log:
            col = _esito_colore(v)
            riga = f.box(20, gap=1)
            if f.surf:
                T.text(f.surf, f"{v['stagione']}  g{v['gara']}", (riga.x, riga.y), 12,
                       T.DIM_2)
                T.text(f.surf, f"{v['label']} ({v['size']})", (riga.x + 74, riga.y), 13,
                       T.TEXT, maxw=riga.w * 0.42)
                T.text(f.surf, f"{v['atteso']:+.1f}", (riga.x + riga.w * 0.78, riga.y), 12,
                       T.DIM, align="right")
                T.text(f.surf, f"{v['reso']:+.1f}", (riga.x + riga.w, riga.y), 13, col,
                       bold=True, align="right")
            f.line(f"{v['esito']}  -  {v['costo']:.2f} M$"
                   + (f"  -  {v['gp']}" if v.get("gp") else ""), 11, T.DIM_2, gap=5,
                   indent=74)

    def _draw_right(self, f) -> None:
        gs, team = self.gs, self.team
        f.head("Progetti in corso")
        if team.dev_projects:
            for pr in team.dev_projects:
                riga = f.box(30, gap=4)
                if f.surf:
                    T.panel(f.surf, riga, T.PANEL_2, radius=6)
                    T.text(f.surf, pr.label, (riga.x + 10, riga.y + 7), 13, T.TEXT,
                           maxw=riga.w * 0.55)
                    T.bar(f.surf, (riga.right - 160, riga.y + 12, 90, 8), pr.progress * 100)
                    T.text(f.surf, f"{pr.races_left} gare", (riga.right - 10, riga.y + 7),
                           12, T.DIM, align="right")
        else:
            f.line("Nessun progetto in corso.", 13, T.DIM, gap=6)
        f.gap(4)
        f.widget(self.budget_slider, 28, gap=14)

        f.head("Nuovo pacchetto")
        f.line("Su quale componente", 12, T.DIM, gap=6)
        chiavi = list(self.part_buttons)
        for i in range(0, len(chiavi), 3):
            f.row(chiavi[i:i + 3], 30, gap=6)
        f.gap(6)
        f.line("Quanto grande", 12, T.DIM, gap=6)
        f.row(self.size_buttons, 30, gap=10)

        cost = development.cost_of_upgrade(self.sel_part, self.sel_size)
        gain = development.expected_gain(gs, team, self.sel_part, self.sel_size)
        conf = development.project_confidence(gs, team, self.sel_part, self.sel_size)
        odds = development.outcome_odds(conf, self.sel_size)
        races = development.RACES_OF[self.sel_size]
        f.line(f"Costo {cost:.2f} M$   |   Sulla carta +{gain:.1f}   |   "
               f"Tempo {races} gare", 14, T.TEXT, gap=8)

        col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
        riga = f.box(18, gap=6)
        if f.surf:
            T.text(f.surf, "Fiducia del reparto", (riga.x, riga.y), 13, T.DIM)
            T.bar(f.surf, (riga.x + 170, riga.y + 5, riga.w - 240, 8), conf * 100, 100, col)
            T.text(f.surf, f"{conf*100:.0f}%", (riga.x + riga.w, riga.y), 13, col,
                   bold=True, align="right")
        f.line("Come puo' finire", 11, T.DIM_2, gap=3)
        bande = f.box(10, gap=4)
        if f.surf:
            x = bande.x
            for nome, colore in (("fallito", T.BAD), ("sottotono", T.WARN),
                                 ("in linea", T.ACCENT), ("oltre", T.OK)):
                w = bande.w * odds[nome]
                pygame.draw.rect(f.surf, colore, (int(x), bande.y, max(2, int(w)), 10),
                                 border_radius=2)
                x += w
        f.line(f"fallisce {odds['fallito']*100:.0f}%   "
               f"sotto le attese {odds['sottotono']*100:.0f}%   "
               f"come previsto {odds['in linea']*100:.0f}%   "
               f"oltre {odds['oltre']*100:.0f}%", 12, T.DIM_2, gap=6)
        f.par(development.weakest_link(gs, team, self.sel_part).capitalize()
              if conf < 0.62 else
              "Reparto e strumenti sono all'altezza: quello che promettiamo, arriva.",
              12, T.DIM if conf >= 0.62 else T.WARN)
        upset = development.setup_upset(team, self.sel_size)
        quanto = "poco" if upset < 0.15 else ("parecchio" if upset < 0.32 else "molto")
        casa = (f"il simulatore e {team.private_track_name} ce lo fanno ritrovare prima"
                if team.has_private_track else "senza pista di proprieta' si ritrova il venerdi'")
        f.par(f"Assetto da ritrovare: {quanto} (-{upset*100:.0f}% di quello che sappiamo "
              f"della vettura). {casa[0].upper()}{casa[1:]}.", 12, T.GOLD)
        f.widget(self._btn("avvia", "Avvia progetto", self.start_project, "primary"),
                 40, gap=16)

        # come e' andata l'ultima volta su questo stesso componente
        storia = [v for v in (team.upgrade_log or []) if v["part"] == self.sel_part]
        if storia:
            u = storia[-1]
            f.par(f"L'ultimo pacchetto su {u['label'].lower()} ({u['size']}, stagione "
                  f"{u['stagione']}) prometteva {u['atteso']:+.1f} e ha reso "
                  f"{u['reso']:+.1f}: {u['esito']}.", 12, _esito_colore(u), gap=14)

        left = development.seasons_to_reset(gs)
        if left is not None and left <= 3:
            f.widget(self.reg_slider, 28, gap=12)

        st = rules.talks(gs)
        if st:
            # il tavolo e' aperto: non si sa ancora la data, ma si sa la direzione
            dom = max(st["aree"], key=st["aree"].get)
            f.head(f"Tavolo tecnico  -  riunione {st['riunioni']} di {st['servono']}", T.GOLD)
            f.par(f"Si sta andando verso {rules.ETICHETTA_AREA[dom]} "
                  f"({st['aree'][dom]*100:.0f}%). Finche' non si firma puo' ancora "
                  f"cambiare, e prepararsi adesso e' una scommessa.", 12, T.DIM)
        if left is not None and left <= 3:
            era = development.next_era(gs)
            fo = era.get("focus", {})
            dom = max(fo, key=fo.get) if fo else "aero"
            nome = {"pu": "power unit", "chassis": "telaio", "aero": "aerodinamica"}[dom]
            f.head(f"Regolamento {era['from']}  -  fra {left} "
                   f"{'stagione' if left == 1 else 'stagioni'}", T.GOLD)
            f.par(f"{era['label']}: a decidere sara' soprattutto {nome} "
                  f"({fo.get(dom, 0)*100:.0f}%).", 12, T.DIM, gap=4)
            conv = development.prep_conversion(gs, team, era)
            rank = 1 + sum(1 for t in gs.teams.values()
                           if development.prep_conversion(gs, t, era) > conv)
            f.par(f"Con i nostri reparti convertiamo a {conv:.2f}: {rank}i della griglia "
                  f"su questo fronte.", 12, T.DIM, gap=4)
            if left == 1:
                f.par("Ultima stagione utile: dopo il cambio la preparazione non conta piu'.",
                      12, T.WARN)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        atr = development.atr_factor(gs, team)
        cap = development.dev_capacity(gs, team)
        cw = (r.w - 48) / 4
        card(surf, (r.x, r.y, cw, 86), "Capacita' di sviluppo", f"{cap:.2f}",
             f"efficienza reparto {team.dev_rate:.2f}", accent=T.ACCENT)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Ore galleria (ATR)", f"{atr*100:.0f}%",
             f"{team.last_position}o nel costruttori precedente",
             colour=T.OK if atr >= 1.0 else T.WARN, accent=T.WARN)
        und = team.car_understanding
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Conoscenza della vettura",
             f"{und*100:.0f}%", "quanto sappiamo sfruttarla",
             colour=T.OK if und > 0.45 else T.TEXT, accent=T.GOLD)
        card(surf, (r.x + 3 * (cw + 16), r.y, cw, 86), "Progetti attivi",
             f"{len(team.dev_projects)} / 3",
             f"{team.upgrades_done} aggiornamenti portati in pista", accent=T.OK)
        super().draw(surf)


# ================================================================ INGEGNERI
class EngineersPage(Page):
    """La riunione tecnica e il confronto con la griglia, area per area."""

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.widgets.append(Button((r.right - 300, r.y + 8, 300, 36),
                                   "Applica il piano suggerito", self.apply_plan, "primary"))
        self._brief = None
        self._report = None
        left = pygame.Rect(r.x, r.y + 56, r.w * 0.46, r.h - 56)
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 56, r.w * 0.52 - 4, r.h - 56)
        self.p_left = ScrollPanel(left, self._draw_brief, pad=16)
        self.p_right = ScrollPanel(right, self._draw_report, pad=16)
        self.widgets += [self.p_left, self.p_right]

    def apply_plan(self) -> None:
        sug = engineering.suggested_allocation(self.gs)
        self.team.resource_alloc = sug
        self.app.toast("Piano di sviluppo aggiornato secondo gli ingegneri.")

    def refresh(self) -> None:
        self.build()
        self._brief = engineering.briefing(self.gs)
        self._report = engineering.field_report(self.gs)
        self.p_left.layout()
        self.p_right.layout()

    def _draw_brief(self, f) -> None:
        f.head("Riunione con i responsabili")
        for speaker, line in (self._brief or []):
            f.line(speaker, 14, T.ACCENT, bold=True, gap=2)
            f.par(line, 13, T.TEXT, indent=8, gap=12)

    def _draw_report(self, f) -> None:
        f.head("Dove siamo rispetto alla griglia")
        intest = f.box(16, gap=6)
        if f.surf:
            for lab, x in (("AREA", 0), ("NOI", 250), ("MIGLIORE", 320), ("GAP", 440),
                           ("POS", 520)):
                T.text(f.surf, lab, (intest.x + x, intest.y), 11, T.DIM_2, bold=True)
        for area, lab in engineering.AREAS.items():
            d = (self._report or {}).get(area)
            if not d:
                continue
            riga = f.box(34, gap=4)
            if not f.surf:
                continue
            T.text(f.surf, lab, (riga.x, riga.y), 14, T.TEXT, maxw=230)
            T.text(f.surf, f"{d['mine']:.0f}", (riga.x + 250, riga.y), 14,
                   T.stat_colour(d["mine"], 40, 80), bold=True)
            T.text(f.surf, f"{d['best']:.0f} {d['best_team']}", (riga.x + 320, riga.y), 13,
                   T.DIM, maxw=110)
            gap = d["delta"]
            T.text(f.surf, f"{gap:+.0f}", (riga.x + 440, riga.y), 14,
                   T.OK if gap >= -2 else (T.WARN if gap > -14 else T.BAD), bold=True)
            T.text(f.surf, f"{d['rank']}o", (riga.x + 520, riga.y), 14, T.TEXT)
            T.bar(f.surf, (riga.x, riga.y + 22, riga.w - 8, 5), d["mine"], 100,
                  T.stat_colour(d["mine"], 40, 80))
        f.gap(8)
        f.par("Le stime sugli avversari migliorano con lo scouting e con le gare disputate. "
              "Il confronto squadra per squadra sta nella pagina della vettura, sotto "
              "\"Confronto con la griglia\".")

    def draw(self, surf) -> None:
        r = self.rect
        if self._brief is None:
            self.refresh()
        T.text(surf, "CONFRONTO TECNICO", (r.x, r.y + 10), 22, T.TEXT, bold=True)
        super().draw(surf)


# ================================================================ POWER UNIT
class PowerUnitPage(Page):
    """Il reparto motori: sviluppo, confronto coi motoristi, programma proprio."""

    def build(self) -> None:
        self.found_note = ""
        r = self.rect
        self.widgets = []
        self.budget_slider = Slider((0, 0, 10, 28), "Budget power unit per gara",
                                    self.app.pu_budget, 0.0, 6.0,
                                    on_change=self._set_budget, fmt="{:.2f} M$")
        self.b_omologa = Button((0, 0, 10, 40), "Omologa la specifica nuova",
                                self.homologate, "primary")
        self.b_debutto = Button((0, 0, 10, 42), "Porta in pista la nostra power unit",
                                self.debut, "primary")
        can, why = powertrain.can_found(self.team)
        self.b_fonda = Button(
            (0, 0, 10, 42),
            f"Fonda il reparto motori ({powertrain.PROGRAM_START_COST:.0f} M$)"
            if can else "Reparto motori fuori dalla nostra portata",
            self.start_program, "primary" if can else "ghost")
        self.b_fonda.enabled = can
        self.b_fonda.tip = why
        self.found_note = "" if can else why

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        self.p_left = ScrollPanel(left, self._draw_left, pad=16)
        self.p_right = ScrollPanel(right, self._draw_right, pad=16)
        self.widgets += [self.p_left, self.p_right]
        self.p_left.layout()
        self.p_right.layout()

    def refresh(self) -> None:
        self.build()

    def _set_budget(self, v) -> None:
        self.app.pu_budget = v

    def start_program(self) -> None:
        ok, msg = powertrain.start_program(self.gs, self.team)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _can_homologate(self) -> bool:
        """La specifica la decide chi il motore lo costruisce."""
        gs, team = self.gs, self.team
        if not team.works or powertrain.locked(gs):
            return False
        sp = powertrain.spec(gs, team.engine)
        return (powertrain.spec_value(sp) > 0.05
                and powertrain.specs_left(gs, team.engine) > 0)

    def homologate(self) -> None:
        ok, msg = powertrain.homologate(self.gs, self.team.engine)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def debut(self) -> None:
        ok, msg = powertrain.debut(self.gs)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    # ------------------------------------------------------------ contenuti
    def _draw_left(self, f) -> None:
        gs, team = self.gs, self.team
        eng = powertrain.maker(gs, team)
        f.head("I motoristi")
        ranked = sorted(gs.engine_makers.items(), key=lambda kv: -powertrain.rating(kv[1]))
        for eid, m in ranked:
            mine = (eid == team.engine)
            builder = powertrain.builder_of(gs, eid)
            col = T.ACCENT if mine else T.TEXT
            f.kv(m.get("name", eid), f"{powertrain.rating(m):.1f}", 14, col,
                 key_colour=col, gap=1)
            who = builder.short if builder else "nessuna squadra ufficiale"
            n = len(powertrain.customers_of(gs, eid))
            f.line(f"{who} - {n} client{'e' if n == 1 else 'i'}", 11, T.DIM_2, gap=3)
            riga = f.box(6, gap=7)
            if f.surf:
                T.bar(f.surf, riga, powertrain.rating(m), 100,
                      T.ACCENT if mine else T.PANEL_3)
        f.gap(6)

        sp = powertrain.spec(gs, team.engine)
        nostro = team.works
        f.head("La nostra unita'" + ("  -  in banco" if nostro else ""))
        for attr, label in (("power", "Potenza termica"), ("ers", "Ibrido ed ERS"),
                            ("reliability", "Affidabilita'")):
            g = float(sp["gain"].get(attr, 0.0))
            extra = f"   +{g:.1f}" if (nostro and g > 0.01) else ""
            f.kv(label, f"{float(eng.get(attr, 85)):.1f}{extra}", 13,
                 T.OK if extra else T.TEXT)
        f.gap(10)

        f.head("Specifica in lavorazione")
        if powertrain.locked(gs):
            f.par("Sviluppo congelato: si corre con quello che c'e'.", 13, T.WARN)
            return
        if not team.works:
            costruttore = powertrain.builder_of(gs, team.engine)
            chi = costruttore.short if costruttore else eng.get("name", "il motorista")
            f.par(f"La specifica la decide {chi}: noi la montiamo e basta. E' il prezzo "
                  f"di comprare il motore invece di farlo.", 13, T.DIM)
            return
        valore = powertrain.spec_value(sp)
        conf = powertrain.spec_confidence(gs, team.engine)
        odds = powertrain.spec_odds(gs, team.engine)
        rimaste = powertrain.specs_left(gs, team.engine)
        f.kv(f"Vale {valore:+.2f} dopo {sp.get('races', 0)} gare di banco",
             f"{rimaste} su {powertrain.specs_allowed(gs)}", 13,
             T.GOLD if rimaste else T.BAD,
             key_colour=T.TEXT if valore > 0.05 else T.DIM)
        col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
        riga = f.box(18, gap=6)
        if f.surf:
            T.text(f.surf, "Fiducia del banco", (riga.x, riga.y), 13, T.DIM)
            T.bar(f.surf, (riga.x + 160, riga.y + 5, riga.w - 230, 8), conf * 100, 100, col)
            T.text(f.surf, f"{conf*100:.0f}%", (riga.x + riga.w, riga.y), 13, col,
                   bold=True, align="right")
        f.par(f"fallisce {odds['fallito']*100:.0f}%   "
              f"sotto le attese {odds['sottotono']*100:.0f}%   "
              f"oltre {odds['oltre']*100:.0f}%", 12, T.DIM_2)
        if rimaste <= 0:
            f.par("Gettoni finiti: il resto del lavoro va all'anno prossimo.", 12, T.WARN)
        elif sp.get("races", 0) < 5:
            f.par("Piu' resta al banco, meno sorprese in pista.", 12, T.DIM_2)
        if self._can_homologate():
            f.widget(self.b_omologa, 40, gap=8)

    def _draw_right(self, f) -> None:
        gs, team = self.gs, self.team
        eng = powertrain.maker(gs, team)
        hop = team.role("head_of_powertrain")
        ceil = powertrain.ceiling(gs, team)
        clients = powertrain.customers_of(gs, team.engine) if team.works else []
        f.head("Il nostro reparto")
        f.widget(self.budget_slider, 28, gap=14)
        rows = [
            ("Responsabile powertrain", hop.name if hop else "nessuno"),
            ("Qualita' del reparto", f"{team.pu_strength:.0f} / 100"),
            ("Resa dell'investimento", f"x{powertrain.dev_rate(gs, team):.2f}"),
            ("Tetto raggiungibile", f"{ceil:.1f}"),
            ("Integrazione nella vettura", f"{powertrain.integration(gs, team) * 100:.0f}%"),
        ]
        if team.works:
            rows.append(("Gestione del reparto", f"-{powertrain.PU_OPERATING_COST:.0f} M$ all'anno"))
            income = sum(c.engine_customer_cost for c in clients)
            rows.append(("Forniture ai clienti",
                         f"+{income:.0f} M$ da {len(clients)}" if clients else "nessun cliente"))
        else:
            rows.append(("Fornitura che paghiamo", f"-{team.engine_customer_cost:.0f} M$ all'anno"))
        for k, v in rows:
            f.kv(k, v)
        f.gap(8)
        if powertrain.locked(gs):
            f.par("Sviluppo power unit congelato dal regolamento.", 13, T.WARN, bold=True)
        if gs.regulations.get("pu_equalisation"):
            f.par("Equalizzazione in vigore: chi e' indietro sviluppa di piu'.", 12, T.DIM)

        # il contingente: si perdono posizioni in griglia per unita' montate
        # oltre quelle concesse, e finora quel conto non lo vedeva nessuno
        f.head("Contingente componenti")
        max_pu = int(gs.regulations["power_unit"].get("units_per_season", 4))
        max_cambi = int(gs.regulations["sporting"].get("gearbox_units", 5))
        for d in gs.drivers_of(team.id):
            riga = f.box(20, gap=2)
            if f.surf:
                T.text(f.surf, d.short, (riga.x, riga.y), 13, T.TEXT, maxw=180)
                cp = T.BAD if d.pu_used > max_pu else (T.WARN if d.pu_used >= max_pu else T.OK)
                T.text(f.surf, f"power unit {d.pu_used}/{max_pu}", (riga.x + 200, riga.y),
                       13, cp, bold=True)
                cc = (T.BAD if d.gearbox_used > max_cambi else
                      (T.WARN if d.gearbox_used >= max_cambi else T.OK))
                T.text(f.surf, f"cambi {d.gearbox_used}/{max_cambi}", (riga.x + 360, riga.y),
                       13, cc, bold=True)
                if d.grid_penalty:
                    T.text(f.surf, f"{d.grid_penalty} posizioni da scontare",
                           (riga.x + riga.w, riga.y), 13, T.BAD, bold=True, align="right")
        f.par("Le unita' si sostituiscono quando cedono, e quanto spesso cedano dipende "
              "dall'affidabilita' del progetto. Superato il contingente si parte "
              "indietro: e' il prezzo nascosto di una power unit fragile.", gap=14)

        p = powertrain.program(gs)
        if powertrain.has_program(gs):
            f.head("Programma in corso")
            f.line(f"Livello raggiunto {p['level']:.1f} su un tetto di {ceil:.1f}", 13,
                   T.TEXT, gap=6)
            riga = f.box(8, gap=8)
            if f.surf:
                T.bar(f.surf, riga, p["level"], 100, T.OK)
            f.line(f"Investiti {p['invested']:.0f} M$ - in pista dal {p['ready_season']}",
                   12, T.DIM, gap=12)
            o = powertrain.debut_outlook(gs, self.app.pu_budget)
            f.head("Quando portarla in pista")
            gap = o["gap_now"]
            f.kv("Oggi il nostro motore vale",
                 f"{o['now']:.1f}  contro il {o['supplied']:.1f} che compriamo ({gap:+.1f})",
                 13, T.OK if gap >= 0 else T.BAD)
            f.kv(f"Fra {o['horizon']} gare, se debutta subito", f"{o['if_debut_now']:.1f}",
                 13, T.OK)
            f.kv(f"Fra {o['horizon']} gare, se resta al banco", f"{o['if_wait']:.1f}",
                 13, T.WARN)
            f.par(f"Al banco si sviluppa al {o['bench_penalty']*100:.0f}% del ritmo: "
                  f"mancano i dati veri. Correre con un motore acerbo costa punti "
                  f"adesso, ma lo fa crescere piu' in fretta.")
            if powertrain.ready_to_debut(gs):
                f.widget(self.b_debutto, 42, gap=8)
        elif not team.works:
            f.head("Comprare o costruire")
            f.par(f"Compriamo la power unit da {eng.get('name', '-')} per "
                  f"{team.engine_customer_cost:.0f} M$ a stagione, e ci teniamo la "
                  f"specifica che decidono loro. Fondando un reparto nostro potremmo "
                  f"svilupparla in casa, ma servono anni e un buon responsabile "
                  f"powertrain.", 13, T.DIM)
            f.widget(self.b_fonda, 42, gap=8)
            if self.found_note:
                f.par(self.found_note, 12, T.WARN)
        else:
            f.par("Costruiamo la nostra power unit: il budget qui sopra e' quello che il "
                  "reparto motori spende a ogni gara. Sta fuori dal tetto di spesa della "
                  "squadra, come nella realta'.", 13, T.DIM)

    # ------------------------------------------------------------------ draw
    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        eng = powertrain.maker(gs, team)
        T.text(surf, "POWER UNIT", (r.x, r.y + 10), 22, T.TEXT, bold=True)
        status = ("costruttore" if team.works else
                  "team ufficiale" if team.is_partner else
                  "cliente, reparto in costruzione" if powertrain.has_program(gs) else "cliente")
        T.text(surf, f"{eng.get('name', '-')} - {status}", (r.x, r.y + 42), 14, T.DIM)
        super().draw(surf)
