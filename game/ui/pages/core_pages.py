"""Pagine: quartier generale, vettura e assetto, sviluppo, ingegneri."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import (development, driving, economy, engineering, kits, nextcar,
                      penalties, powertrain, rules)
from ...core import setup as SETUP
from ...model.car import SETUP_KEYS
from ...sim import session as S
from .. import theme as T
from .. import cardraw, trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, Slider, Toggle, card, stat_row


# =========================================================== QUARTIER GENERALE
class HQPage(Page):
    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.news = ScrollList((r.x + r.w * 0.68, r.y + 190, r.w * 0.32 - 4, r.h - 200),
                               row_h=54, draw_row=self._draw_news)
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
        words = item["text"].split()
        line, lines = "", []
        f = T.font(13)
        for wd in words:
            if f.size(line + " " + wd)[0] > rect.w - 30:
                lines.append(line)
                line = wd
            else:
                line = (line + " " + wd).strip()
        lines.append(line)
        for j, ln in enumerate(lines[:2]):
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


def _posto_in_griglia(campo: dict, part: str, valore: float):
    """Quanto un pezzo sta sopra o sotto la media della griglia, da -1 a +1."""
    voce = campo.get(part)
    if not voce:
        return None
    lo, media, hi = voce
    return max(-1.0, min(1.0, (valore - media) / max(1.5, (hi - lo) / 2.0)))


def _car_rank_text(gs, team) -> str:
    rank = sorted(gs.teams.values(), key=lambda t: -t.car.rating)
    pos = [t.id for t in rank].index(team.id) + 1
    if pos == 1:
        gap = team.car.rating - rank[1].car.rating
        return f"1a vettura della griglia, +{gap:.1f} sulla seconda"
    return f"{pos}a vettura della griglia, {team.car.rating - rank[0].car.rating:+.1f} dalla prima"


# Quanto spazio si tiene in cima al pannello dell'assetto, prima dei cursori.
# Lo usano sia chi costruisce i cursori sia chi disegna l'intestazione: se lo
# sapesse uno solo, basterebbe una frase piu' lunga per farli sovrapporre.
TESTA_ASSETTO = 224
# Il pulsante che monta una parte contingentata: stretto, perche' sulla stessa
# riga ci stanno gia' il nome del pezzo, quante ne restano e quanto e' logora.
LARG_NUOVO = 66
# Quanto spazio si prende una specifica in verifica: il titolo, cosa dice la
# pista, cosa ne dicono i due piloti, quanto costa insistere e i due pulsanti.
# Lo sanno sia chi disegna sia chi piazza i pulsanti, se no si sovrappongono.
ALT_VERIFICA = 148
Y_PULSANTI_VERIFICA = 108
# Dove sta il pulsante che avvia il pacchetto, sotto costo, fiducia, bande e
# le due righe di commento: le stesse che sopra vanno a capo da sole.
Y_AVVIA = 320
# Quanto si tiene l'intestazione della pagina Ingegneri: titolo, interruttore
# e le due linguette fra la nostra vettura e tutta la griglia.
TESTA_TECNICA = 84


# ================================================================== VETTURA
class CarPage(Page):
    """Una macchina per pilota: stesso pacchetto, due assetti."""

    def __init__(self, shell):
        super().__init__(shell)
        self.sel_driver = None
        self.sel_part = "floor"
        self.car_rect = pygame.Rect(0, 0, 10, 10)

    def handle(self, ev) -> None:
        # il disegno della macchina non e' un widget: si clicca il pezzo
        if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                and self.car_rect.collidepoint(ev.pos)):
            part = cardraw.hit(self.car_rect, ev.pos)
            if part:
                self.sel_part = part
                self.build()
                return
        super().handle(ev)

    def _kit_for(self, part: str):
        for k in (self.team.kits or []):
            if k.part == part:
                return k
        return None

    def _fit_kit(self, driver) -> None:
        k = self._kit_for(self.sel_part)
        if k is None:
            return
        ok, msg = kits.fit(self.gs, self.team, k, driver)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _unfit_kit(self, driver) -> None:
        k = self._kit_for(self.sel_part)
        if k is None:
            return
        ok, msg = kits.remove(self.gs, self.team, k, driver)
        self.app.toast(msg)
        self.build()

    def _piloti(self) -> list:
        return self.gs.lineup_of(self.team.id)

    def _driver(self):
        piloti = self._piloti()
        if self.sel_driver is None or self.sel_driver not in piloti:
            self.sel_driver = piloti[0] if piloti else None
        return self.sel_driver

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.sliders = {}
        x = r.x + r.w * 0.42 + 16
        larg = r.w * 0.58 - 32
        d = self._driver()

        # con quale delle due macchine stiamo lavorando
        self.drv_buttons = []
        piloti = self._piloti()
        bw2 = (larg - 10) / max(1, len(piloti))
        for i, p in enumerate(piloti):
            b = Button((x + i * (bw2 + 10), r.y + TESTA_ASSETTO - 42, bw2, 28), p.short)
            b.on_click = (lambda pp=p: self._pick_driver(pp))
            self.drv_buttons.append(b)
            self.widgets.append(b)
        self._mark_driver()

        mio = driving.setup_of(self.team, d) if d else {}
        y = r.y + TESTA_ASSETTO
        for k, lab in SETUP_KEYS.items():
            s = Slider((x, y, larg, 30), lab, mio.get(k, 50.0),
                       on_change=(lambda v, k=k: self._set(k, v)))
            self.sliders[k] = s
            self.widgets.append(s)
            y += 36
        y += 8
        bw = (larg - 10) / 2
        costo = SETUP.sim_cost(self.team)
        self.widgets.append(Button((x, y, bw, 38), f"Simulatore  ({costo:.2f} M$)",
                                   self.simulate, "normal"))
        self.widgets.append(Button((x + bw + 10, y, bw, 38), "Monta su questa macchina",
                                   self.delegate, "primary"))
        self.widgets.append(Button((x, y + 44, bw, 34), "Monta su tutte e due",
                                   self.delegate_all, "ghost"))
        self.widgets.append(Button((x + bw + 10, y + 44, bw, 34), "Assetto neutro",
                                   self.neutral, "ghost"))
        self.auto_toggle = Toggle((x, y + 88, larg, 30),
                                  "Se ne occupano gli ingegneri di pista",
                                  self.team.auto_setup, on_change=self._set_auto_setup)
        self.widgets.append(self.auto_toggle)

        # --- il pezzo nuovo: su quale macchina lo montiamo
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        # su una finestra stretta il disegno si rimpicciolisce: accanto ci va
        # la scheda del pezzo, e con 160 pixel non ci si scrive niente
        larga = 150 if left.w >= 430 else max(104, int(left.w * 0.30))
        self.car_rect = pygame.Rect(left.x + 16, left.y + 34, larga,
                                    int(larga * cardraw.RATIO))
        k = self._kit_for(self.sel_part)
        self.kit_bottom = 0
        if k is not None:
            bx = self.car_rect.right + 16
            bw = left.right - 16 - bx
            for i, pil in enumerate(self._piloti()):
                montato = pil.id in k.fitted
                # su un pezzo distrutto non si smonta niente: si aspetta il
                # ricambio e lo si rimette sulla macchina rimasta indietro
                if montato and k.reason == "danno":
                    continue
                b = Button((bx, self.car_rect.y + 206 + i * 32, bw, 26),
                           ("Togli da " if montato else "Monta su ") + pil.short,
                           style="danger" if montato else "primary")
                b.on_click = ((lambda pp=pil: self._unfit_kit(pp)) if montato
                              else (lambda pp=pil: self._fit_kit(pp)))
                b.enabled = montato or k.spare > 0
                self.widgets.append(b)
                self.kit_bottom = max(self.kit_bottom, b.rect.bottom)

        # le parti che il regolamento conta: si cambiano quando sono finite,
        # sapendo cosa costa farlo fuori contingente
        cy = self._contingente_y(left) + 22
        for p in self._piloti():
            for i, quale in enumerate(("pu", "cambio")):
                b = Button((left.right - 16 - LARG_NUOVO, cy + i * 24 - 2,
                            LARG_NUOVO, 22), "Nuovo")
                b.on_click = (lambda pp=p, q=quale: self._fit(pp, q))
                self.widgets.append(b)
            cy += 60
        self._update_markers()

    def _sotto_scheda(self) -> int:
        """Dove finisce la scheda del pezzo: sotto il disegno o sotto i pulsanti.

        Il disegno si stringe quando la finestra e' stretta, i pulsanti per
        montare il pezzo nuovo no: quello che viene dopo deve partire da
        qualunque dei due scende di piu'.
        """
        return int(max(self.car_rect.bottom, getattr(self, "kit_bottom", 0))) + 16

    def _contingente_y(self, left) -> int:
        """Dove comincia il blocco delle parti contingentate.

        Sotto le prestazioni derivate, che sono sempre sette righe, e mai piu'
        in alto del fondo del pannello: su una finestra bassa scende, e la
        pagina si scorre, invece di finire sopra a quello che c'e' gia'.
        """
        sotto = (self._sotto_scheda() + 22 + len(engineering.AREAS) * 20
                 + 8 + 24 + 16)
        return int(max(sotto, left.bottom - 140))

    def _fit(self, driver, quale) -> None:
        ok, msg = penalties.fit_new(self.gs, self.team, driver, quale)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")
        self.build()

    def _set_auto_setup(self, v) -> None:
        self.team.auto_setup = bool(v)
        self.build()

    def _pick_driver(self, p) -> None:
        self.sel_driver = p
        self.build()

    def _mark_driver(self) -> None:
        for b, p in zip(self.drv_buttons, self._piloti()):
            b.active = (p is self.sel_driver)
            b.style = "tab" if b.active else "normal"

    def _set(self, k, v) -> None:
        d = self._driver()
        if d is not None:
            driving.set_value(self.team, d, k, v)

    def _update_markers(self) -> None:
        """Il triangolo mostra quello che il reparto crede, corretto per lui."""
        nt = self.gs.next_track
        d = self._driver()
        if not nt or d is None:
            return
        SETUP.ensure_paper(self.gs, self.team, nt)
        bersaglio = SETUP.target_for(self.team, d)
        for k, s in self.sliders.items():
            s.marker = bersaglio.get(k)

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
        nt, d = self.gs.next_track, self._driver()
        if not nt or d is None:
            return
        S.auto_setup(self.gs, self.team, nt, driver=d)
        self.app.toast(f"Assetto del reparto montato sulla macchina di {d.short}.")
        self.build()

    def delegate_all(self) -> None:
        nt = self.gs.next_track
        if not nt:
            return
        S.auto_setup(self.gs, self.team, nt)
        self.app.toast("Assetto del reparto montato su tutte e due le macchine.")
        self.build()

    def neutral(self) -> None:
        d = self._driver()
        if d is None:
            return
        for k, s in self.sliders.items():
            driving.set_value(self.team, d, k, 50.0)
            s.value = 50.0

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, team, gs = self.rect, self.team, self.gs
        car = team.car
        left = pygame.Rect(r.x, r.y, r.w * 0.42, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LA MACCHINA", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, "clicca un pezzo", (left.right - 16, left.y + 12), 11, T.DIM_2,
               align="right")
        # il colore dice come sta messo un pezzo rispetto agli altri undici,
        # non rispetto al riferimento del ciclo: quello a inizio era sempre
        # lontano e faceva sembrare rossa anche la macchina piu' veloce
        campo = engineering.part_field(gs)
        d0 = self._driver()
        colori, segni = {}, {}
        for k in C.CAR_PARTS:
            p = car.parts[k]
            valore = kits.perf_for(team, d0.id, k) if d0 is not None else p.perf
            colori[k] = cardraw.tinta(_posto_in_griglia(campo, k, valore),
                                      acceso=(k == self.sel_part))
            if d0 is not None and k in (kits.deltas(team, d0.id) or {}):
                segni[k] = T.ACCENT                  # pezzo nuovo montato qui
            elif p.condition < 55:
                segni[k] = T.BAD                     # e' da rifare
        cardraw.draw(surf, self.car_rect, colori, self.sel_part, segni,
                     livery=T.hex_rgb(team.colour))
        if "floor" in segni:
            cardraw.floor_badge(surf, self.car_rect, segni["floor"])

        # --- la scheda del pezzo scelto
        px = self.car_rect.right + 16
        pw = left.right - 16 - px
        meta = C.CAR_PARTS[self.sel_part]
        part = car.parts[self.sel_part]
        T.text(surf, meta["label"], (px, self.car_rect.y), 17, T.TEXT, bold=True, maxw=pw)
        valore = kits.perf_for(team, d0.id, self.sel_part) if d0 else part.perf
        T.text(surf, "Prestazione", (px, self.car_rect.y + 28), 13, T.DIM)
        posto = _posto_in_griglia(campo, self.sel_part, valore)
        T.text(surf, f"{valore:.1f}", (px + pw, self.car_rect.y + 28), 14,
               T.OK if (posto or 0) > 0.25 else (T.BAD if (posto or 0) < -0.25 else T.WARN),
               bold=True, align="right")
        campo_sel = campo.get(self.sel_part)
        if campo_sel:
            pos = 1 + sum(1 for t in gs.teams.values()
                          if t.car.parts[self.sel_part].perf > valore)
            T.text(surf, f"{pos}i della griglia, media {campo_sel[1]:.1f}",
                   (px, self.car_rect.y + 46), 11, T.DIM_2, maxw=pw)
        T.text(surf, "Stato del pezzo", (px, self.car_rect.y + 68), 13, T.DIM)
        cond_col = (T.OK if part.condition > 80 else
                    T.WARN if part.condition > 55 else T.BAD)
        T.text(surf, f"{part.condition:.0f}%", (px + pw, self.car_rect.y + 68), 14,
               cond_col, bold=True, align="right")
        T.bar(surf, (px, self.car_rect.y + 88, pw, 8), part.condition, 100, cond_col)

        kit = self._kit_for(self.sel_part)
        if kit is not None:
            danno = kit.reason == "danno"
            T.text(surf, "PEZZO DISTRUTTO, IN RICOSTRUZIONE" if danno
                   else "SPECIFICA NUOVA IN FABBRICA", (px, self.car_rect.y + 112), 11,
                   T.BAD if danno else T.ACCENT, bold=True, maxw=pw)
            T.text(surf, f"{kit.old_perf:.1f}  ->  {kit.perf:.1f}   ({kit.gain:+.1f})",
                   (px, self.car_rect.y + 132), 15, T.OK if kit.gain > 0 else T.BAD,
                   bold=True, maxw=pw)
            T.paragraph(surf, f"esemplari integri {kit.ready} su 2, montati "
                              f"{len(kit.fitted)}", (px, self.car_rect.y + 154), 12,
                        T.DIM, pw)
            gare = max(0, kits.build_time(team, kit.size) - (gs.round - kit.round_ready))
            quando = "alla prossima gara" if gare <= 1 else f"fra {gare} gare"
            if kit.gain <= 0:
                T.text(surf, "peggio della vecchia: non conviene montarla",
                       (px, self.car_rect.y + 172), 12, T.BAD, maxw=pw)
            elif kit.spare <= 0 and len(kit.fitted) < 2:
                T.text(surf, (f"il pezzo rifatto arriva {quando}" if danno
                              else f"il secondo esemplare esce {quando}"),
                       (px, self.car_rect.y + 172), 12, T.WARN, maxw=pw)
            elif len(kit.fitted) == 1:
                T.text(surf, "una macchina aggiornata, l'altra no",
                       (px, self.car_rect.y + 172), 12, T.WARN, maxw=pw)
        else:
            T.paragraph(surf, "Nessun pezzo nuovo in arrivo per questo componente: "
                              "si migliora con un pacchetto di sviluppo.",
                        (px, self.car_rect.y + 112), 12, T.DIM_2, pw)

        y = self._sotto_scheda()
        T.text(surf, "PRESTAZIONI DERIVATE", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        prof = engineering.car_profile(team, gs)
        for key, lab in engineering.AREAS.items():
            stat_row(surf, pygame.Rect(left.x + 16, y, left.w - 32, 20), lab, prof[key])
            y += 20
        y += 8
        cost = car.repair_cost()
        T.text(surf, f"Costo di ripristino stimato: {cost:.2f} M$", (left.x + 16, y), 13,
               T.WARN if cost > 0.5 else T.DIM)

        # --- power unit e cambio: quello che il regolamento conta
        reg = gs.regulations
        max_pu = int(reg["power_unit"].get("units_per_season", 4))
        max_cb = int(reg["sporting"].get("gearbox_units", 5))
        cy = self._contingente_y(left)
        T.text(surf, "PARTI CONTINGENTATE", (left.x + 16, cy), 12, T.DIM_2, bold=True)
        T.text(surf, f"oltre il limite: {penalties.GRIGLIA_PU} posizioni",
               (left.right - 16, cy), 11, T.DIM_2, align="right")
        cy += 22
        for d in self._piloti():
            T.text(surf, d.short, (left.x + 16, cy), 13, T.TEXT, bold=True, maxw=120)
            for i, (lab, logoro, usate, limite) in enumerate(
                    (("Power unit", d.pu_wear, d.pu_used, max_pu),
                     ("Cambio", d.gearbox_wear, d.gearbox_used, max_cb))):
                yy = cy + i * 24
                col = (T.OK if logoro > 55 else
                       T.WARN if logoro > penalties.SOGLIA_ROTTURA else T.BAD)
                col_n = T.BAD if usate >= limite else T.DIM
                # quante ne ha usate sta accanto al nome del pezzo: sulla riga
                # non c'e' posto per tre colonne e un pulsante
                T.text(surf, lab, (left.x + 116, yy), 12, T.DIM, maxw=76)
                T.text(surf, f"{usate}/{limite}", (left.x + 196, yy), 12, col_n, bold=True)
                bx = left.x + 236
                bw2 = max(40, (left.right - 24 - LARG_NUOVO) - bx)
                T.bar(surf, (bx, yy + 5, bw2, 7), logoro, 100, col)
            cy += 60

        right = pygame.Rect(r.x + r.w * 0.42 + 16, r.y, r.w * 0.58 - 16, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ASSETTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        nt = gs.next_track
        d = self._driver()
        if nt and d is not None:
            q = SETUP.believed_quality(team, d)
            qc = T.OK if q > 0.85 else (T.WARN if q > 0.6 else T.BAD)
            T.text(surf, f"per {nt.name}", (right.x + 16, right.y + 30), 16, T.TEXT,
                   bold=True, maxw=right.w - 32)
            # lo stile ha una riga sua: accanto al nome della pista non ci sta,
            # e su una finestra stretta veniva tagliato a meta'
            T.text(surf, f"stile di {d.short}: {driving.label(d)}",
                   (right.x + 16, right.y + 52), 12, T.GOLD, maxw=right.w - 32)
            barra = max(90, right.w - 250)
            # quanto si fida di quello che ha sotto: non e' il morale, e' il
            # motivo per cui in curva quattro alza il piede o no
            fiducia = float(getattr(d, "confidence", driving.FIDUCIA_BASE))
            fc = T.stat_colour(fiducia, 45, 75)
            T.text(surf, "Fiducia nella macchina", (right.x + 16, right.y + 70), 13, T.DIM)
            T.bar(surf, (right.x + 176, right.y + 74, barra, 10), fiducia, 100, fc)
            T.text(surf, f"{fiducia:.0f}", (right.right - 16, right.y + 68), 15, fc,
                   bold=True, align="right")
            T.text(surf, "Vicinanza al riferimento", (right.x + 16, right.y + 90), 13, T.DIM)
            T.bar(surf, (right.x + 176, right.y + 94, barra, 10), q * 100)
            T.text(surf, f"{q*100:.0f}%", (right.right - 16, right.y + 88), 15, qc,
                   bold=True, align="right")
            T.text(surf, driving.confidence_label(d), (right.x + 16, right.y + 110), 12,
                   fc, maxw=right.w - 32)
            err = SETUP.paper_error(team, nt, team.sim_sessions)
            fid = max(0.0, min(1.0, 1.0 - (err - SETUP.ERR_MIN) / (SETUP.ERR_MAX - SETUP.ERR_MIN)))
            T.text(surf, f"riferimento +/-{err:.0f} punti, {team.sim_sessions} "
                         f"sessioni su {SETUP.SIM_MAX} al simulatore",
                   (right.x + 16, right.y + 128), 12,
                   T.stat_colour(fid * 100, 40, 75), bold=True, maxw=right.w - 210)
            und = team.car_understanding
            T.text(surf, f"vettura capita al {und*100:.0f}%", (right.right - 16, right.y + 128),
                   12, T.stat_colour(und * 100, 30, 65), bold=True, align="right")
            car.setup = dict(driving.setup_of(team, d))
            T.text(surf, f"Carico {car.downforce:.2f}  |  Resistenza {car.drag:.2f}  |  "
                         f"Potenza {car.power:.2f}  |  Aderenza {car.mech_grip:.2f}",
                   (right.x + 16, right.y + 148), 13, T.DIM, maxw=right.w - 32)
        else:
            T.text(surf, "Nessuna gara in programma.", (right.x + 16, right.y + 40), 15, T.DIM)
        yy = getattr(self, "auto_toggle", None)
        yy = (yy.rect.bottom + 18) if yy is not None else right.y + TESTA_ASSETTO + 360
        if nt and d is not None:
            T.text(surf, "RISCONTRO DEGLI INGEGNERI", (right.x + 16, yy), 12, T.DIM_2, bold=True)
            yy += 22
            for line in S.setup_hints(team, nt, d)[:6]:
                yy += T.paragraph(surf, line, (right.x + 16, yy), 13, T.DIM, right.w - 32) + 2
        super().draw(surf)


# ================================================================= SVILUPPO
class DevPage(Page):
    SIZES = ["piccolo", "medio", "grande"]

    def __init__(self, shell):
        super().__init__(shell)
        self.sel_part = "floor"
        self.sel_size = "medio"
        self.sel_focus = ""      # su che parte del giro disegnarlo

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.alloc_sliders = {}
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        y = left.y + 40
        for k, meta in C.CAR_PARTS.items():
            s = Slider((left.x + 16, y, left.w - 32, 28), meta["label"],
                       self.team.resource_alloc.get(k, 0.1) * 100.0, 0, 100,
                       on_change=(lambda v, k=k: self._alloc(k, v)), fmt="{:.0f}%")
            self.alloc_sliders[k] = s
            self.widgets.append(s)
            y += 32
        self.widgets.append(Button((left.x + 16, y + 8, (left.w - 42) / 2, 34),
                                   "Bilancia", self.balance, "ghost"))
        self.widgets.append(Button((left.x + 26 + (left.w - 42) / 2, y + 8, (left.w - 42) / 2, 34),
                                   "Consiglio ingegneri", self.suggest, "primary"))

        # specifiche che non hanno convinto: si rimonta la vecchia o si insiste
        # sotto l'interruttore, non sopra: prima ci finiva a meta'
        self.trial_y = y + 96
        ty = self.trial_y + 26
        bw = (left.w - 42) / 2
        for tr in self.team.spec_trials[:2]:
            peggio = development.deficit(self.team, tr) < -0.05
            if peggio:
                self.widgets.append(Button((left.x + 16, ty + Y_PULSANTI_VERIFICA, bw, 26),
                                           "Rimonta la vecchia",
                                           (lambda t=tr: self.revert(t)), "danger"))
            if tr.state == "in prova":
                x = left.x + 26 + bw if peggio else left.x + 16
                self.widgets.append(Button((x, ty + Y_PULSANTI_VERIFICA, bw, 26),
                                           "Tienila e affinala",
                                           (lambda t=tr: self.keep(t)), "primary"))
            ty += ALT_VERIFICA
        # sotto le verifiche c'e' il registro di quello che e' gia' arrivato in
        # pista: il pannello si allunga per tenerlo, e quello che sfora lo
        # recupera lo scorrimento della pagina
        self.log_y = int(ty + 10)
        ty = self.log_y + self._alt_registro()
        self.left_h = max(r.h - 96, ty + 16 - (r.y + 96))

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        bx, by = right.x + 16, right.y + 200
        self.part_buttons = []
        for i, (k, meta) in enumerate(C.CAR_PARTS.items()):
            b = Button((bx + (i % 3) * ((right.w - 44) / 3 + 6), by + (i // 3) * 34,
                        (right.w - 44) / 3, 30), meta["label"], style="tab")
            b.on_click = (lambda k=k: self._pick_part(k))
            b.active = (k == self.sel_part)
            self.part_buttons.append(b)
            self.widgets.append(b)
        sy = by + 4 * 34 + 10
        self.size_buttons = []
        for i, sz in enumerate(self.SIZES):
            b = Button((bx + i * ((right.w - 44) / 3 + 6), sy, (right.w - 44) / 3, 30),
                       sz.capitalize(), style="tab")
            b.on_click = (lambda s=sz: self._pick_size(s))
            b.active = (sz == self.sel_size)
            self.size_buttons.append(b)
            self.widgets.append(b)
        # su cosa disegnarlo: un fondo per le veloci non e' un fondo per le
        # lente, e su un calendario intero la differenza si vede
        self.focus_buttons = []
        scelte = [("", "Nessun focus")] + [(d, engineering.NOMI_DOMINIO[d])
                                           for d in self._domini()]
        larg = (right.w - 32 - 6 * (len(scelte) - 1)) / max(1, len(scelte))
        for i, (dom, lab) in enumerate(scelte):
            b = Button((bx + i * (larg + 6), sy + 36, larg, 28), lab, style="tab")
            b.on_click = (lambda d=dom: self._pick_focus(d))
            b.active = (dom == self.sel_focus)
            self.focus_buttons.append(b)
            self.widgets.append(b)
        self.auto_toggle = Toggle((left.x + 16, y + 50, left.w - 32, 30),
                                  "Decide il reparto", self.team.auto_dev,
                                  on_change=self._set_auto)
        self.widgets.append(self.auto_toggle)
        # sotto tutto quello che c'e' da leggere sul pacchetto: le spiegazioni
        # vanno a capo, e su una finestra stretta occupano una riga in piu'
        b = Button((bx, sy + Y_AVVIA, right.w - 32, 40), "Avvia progetto",
                   self.start_project, "primary")
        b.enabled = not self.team.auto_dev
        self.widgets.append(b)
        # la quota sull'anno prossimo si decide con i propri uomini, nella
        # pagina Ingegneri: qui si lavora sulla macchina di adesso
        self.reg_slider = None

    # Quante righe di registro si mostrano: le altre restano nel salvataggio,
    # ma una pagina che scorre per sempre non la legge nessuno.
    RIGHE_REGISTRO = 12

    def _registro(self) -> list:
        """Gli aggiornamenti portati in pista, dal piu' recente."""
        return list(reversed(self.team.upgrade_log or []))[:self.RIGHE_REGISTRO]

    def _alt_registro(self) -> int:
        voci = self._registro()
        if not voci:
            return 60
        return 46 + len(voci) * 34 + (18 if len(self.team.upgrade_log or []) >
                                      self.RIGHE_REGISTRO else 0)

    def _disegna_registro(self, surf, left) -> None:
        """Cosa prometteva ogni pacchetto e cosa ha reso davvero.

        Quanti aggiornamenti si sono fatti non dice niente: quello che conta e'
        se quello che il reparto promette poi in pista si vede. Qui restano
        tutte e due le cose, gara per gara.
        """
        team = self.team
        y = getattr(self, "log_y", left.y + 400)
        T.text(surf, "AGGIORNAMENTI PORTATI IN PISTA", (left.x + 16, y), 12,
               T.DIM_2, bold=True)
        voci = self._registro()
        if not voci:
            T.paragraph(surf, "Il registro e' vuoto. Da qui in avanti ogni pacchetto "
                              "lascia una riga: quanto prometteva, quanto ha reso e "
                              "com'e' finita.", (left.x + 16, y + 20), 12, T.DIM_2,
                        left.w - 32)
            return
        tutti = team.upgrade_log or []
        reso = sum(v.get("reso", 0.0) for v in tutti)
        atteso = sum(v.get("atteso", 0.0) for v in tutti)
        resa = (reso / atteso * 100.0) if atteso > 0.01 else 0.0
        col_r = T.OK if resa > 85 else (T.WARN if resa > 55 else T.BAD)
        # su una riga sua: accanto al titolo, con il pannello stretto, ci
        # finiva sopra
        T.text(surf, f"{reso:+.1f} punti in pista sui {atteso:+.1f} promessi "
                     f"({resa:.0f}%)", (left.x + 16, y + 18), 12, col_r, bold=True,
               maxw=left.w - 32)
        y += 44
        for v in voci:
            col = _esito_colore(v)
            T.text(surf, f"{v.get('stagione', '')}  g{v.get('gara', '')}",
                   (left.x + 16, y), 12, T.DIM_2)
            T.text(surf, f"{v.get('label', '')} ({v.get('size', '')})",
                   (left.x + 82, y), 13, T.TEXT, maxw=left.w * 0.42)
            T.text(surf, f"{v.get('atteso', 0.0):+.1f}", (left.right - 74, y), 12,
                   T.DIM, align="right")
            T.text(surf, f"{v.get('reso', 0.0):+.1f}", (left.right - 16, y), 13, col,
                   bold=True, align="right")
            nota = f"{v.get('esito', '')}  -  {v.get('costo', 0.0):.2f} M$"
            if v.get("gp"):
                nota += f"  -  {v['gp']}"
            T.text(surf, nota, (left.x + 82, y + 16), 11, T.DIM_2, maxw=left.w - 108)
            y += 34
        if len(tutti) > self.RIGHE_REGISTRO:
            T.text(surf, f"e altri {len(tutti) - self.RIGHE_REGISTRO} prima di questi",
                   (left.x + 16, y), 11, T.DIM_2)

    def _set_auto(self, v) -> None:
        self.team.auto_dev = bool(v)
        self.build()

    def _alloc(self, k, v) -> None:
        self.team.resource_alloc[k] = max(0.0, v) / 100.0

    def _set_reg_share(self, v) -> None:
        """Quota del budget di sviluppo dirottata sul regolamento che verra'."""
        self.team.next_reg_share = max(0.0, min(0.90, v / 100.0))

    def _domini(self) -> list:
        from ...model.car import DOMINI_PEZZO
        return list(DOMINI_PEZZO.get(self.sel_part, {}).keys())

    def _pick_part(self, k) -> None:
        self.sel_part = k
        for b, key in zip(self.part_buttons, C.CAR_PARTS.keys()):
            b.active = (key == k)
        if self.sel_focus not in self._domini():
            self.sel_focus = ""
        self.build()

    def _pick_focus(self, dom) -> None:
        self.sel_focus = dom
        for b, (d, _l) in zip(self.focus_buttons,
                              [("", "")] + [(x, "") for x in self._domini()]):
            b.active = (d == dom)

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
        ok, msg = development.start_project(self.gs, self.team, self.sel_part,
                                            self.sel_size, self.sel_focus)
        self.app.toast(msg)
        if ok:
            self.gs.push(msg, "tecnico")

    def refresh(self) -> None:
        self.build()

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

        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, getattr(self, "left_h", r.h - 96))
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "LAVORO DI REPARTO: DOVE LIMARE", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        T.text(surf, "affinamenti, non aggiornamenti", (left.right - 16, left.y + 12), 11,
               T.DIM_2, align="right")

        ty = getattr(self, "trial_y", left.y + 460)
        if team.spec_trials:
            T.text(surf, "SPECIFICHE IN VERIFICA", (left.x + 16, ty), 12, T.WARN, bold=True)
            ty += 26
            for tr in team.spec_trials[:2]:
                buco = development.deficit(team, tr)
                col = T.BAD if buco < -0.05 else (T.OK if buco > 0.05 else T.WARN)
                T.text(surf, tr.label, (left.x + 16, ty), 14, T.TEXT, bold=True, maxw=200)
                T.text(surf, f"{buco:+.1f} sulla vecchia", (left.right - 16, ty), 13, col,
                       bold=True, align="right")
                stato = ("da decidere" if tr.state == "in prova" else
                         f"in affinamento, {max(0, development.TRIAL_RACES + 1 - tr.races)} gare")
                alta = T.paragraph(surf, f"{stato}  -  {tr.news}",
                                   (left.x + 16, ty + 19), 12, T.DIM, left.w - 32)
                # cosa ne dicono quelli che la guidano: un pacchetto che fa
                # girare la macchina non sta bene a tutti e due allo stesso modo
                vy = ty + 22 + alta
                for d in gs.lineup_of(team.id):
                    idx, frase = development.driver_verdict(gs, team, tr, d)
                    segno = "+" if idx > 0.12 else ("-" if idx < -0.12 else "=")
                    col_v = (T.OK if idx > 0.12 else T.BAD if idx < -0.12 else T.DIM_2)
                    vy += T.paragraph(surf, f"{segno} {d.short}: {frase}",
                                      (left.x + 16, vy), 11, col_v, left.w - 32)
                vy += 4
                tetto = development.trial_ceiling(gs, team, tr) - tr.old_perf
                nota = (f"insistere puo' portarla a {tetto:+.1f} sulla vecchia e costa "
                        f"{tr.cost * development.TRIAL_UPKEEP:.2f} M$ a gara, con un "
                        f"banco occupato")
                if buco < -0.05:
                    nota += (f"  -  rimontare la vecchia costa "
                             f"{tr.cost * development.REVERT_SHARE:.2f} M$")
                vy += T.paragraph(surf, nota, (left.x + 16, vy), 11, T.DIM_2, left.w - 32)
                ty = max(ty + ALT_VERIFICA, vy + 12)
        elif team.dev_projects:
            T.text(surf, "Nessuna specifica in discussione: quello che e' arrivato "
                         "in pista ha funzionato.", (left.x + 16, ty), 12, T.DIM_2,
                   maxw=left.w - 32)
        self._disegna_registro(surf, left)

        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROGETTI DI AGGIORNAMENTO", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        from ...core import season as SEASON
        dev_gara, _pu = SEASON.player_budgets(gs)
        T.text(surf, f"Il reparto lavora con {dev_gara:.2f} M$ a gara: e' quello che "
                     f"avanza dopo i costi fissi.",
               (right.x + 16, right.y + 34), 13, T.DIM, maxw=right.w - 32)
        T.text(surf, f"Restano {economy.room_left(gs, team):.0f} M$ per la stagione, "
                     f"pacchetti compresi.",
               (right.x + 16, right.y + 52), 12, T.DIM_2, maxw=right.w - 32)
        y = right.y + 76
        if team.dev_projects:
            for pr in team.dev_projects:
                T.panel(surf, (right.x + 16, y, right.w - 32, 30), T.PANEL_2, radius=6)
                T.text(surf, pr.label, (right.x + 26, y + 7), 13, T.TEXT, maxw=right.w - 200)
                T.bar(surf, (right.right - 170, y + 12, 90, 8), pr.progress * 100)
                T.text(surf, f"{pr.races_left} gare", (right.right - 26, y + 7), 12, T.DIM,
                       align="right")
                y += 34
        else:
            T.text(surf, "Nessun progetto in corso.", (right.x + 16, y + 4), 13, T.DIM)
            y += 34
        T.text(surf, "NUOVO PACCHETTO", (right.x + 16, right.y + 178), 12, T.DIM_2, bold=True)
        sy = right.y + 200 + 4 * 34 + 10
        st = rules.talks(gs)
        if st:
            # il tavolo e' aperto: non si sa ancora la data, ma si sa la direzione
            dom = max(st["aree"], key=st["aree"].get)
            ry = sy + 368
            T.text(surf, f"TAVOLO TECNICO  -  RIUNIONE {st['riunioni']} DI {st['servono']}",
                   (right.x + 16, ry), 12, T.GOLD, bold=True)
            T.text(surf, f"Si sta andando verso {rules.ETICHETTA_AREA[dom]} "
                         f"({st['aree'][dom]*100:.0f}%). Finche' non si firma puo' ancora "
                         f"cambiare, e prepararsi adesso e' una scommessa.",
                   (right.x + 16, ry + 18), 12, T.DIM, maxw=right.w - 32)
        left = development.seasons_to_reset(gs)
        if left is not None and left <= 3:
            era = development.next_era(gs)
            f = era.get("focus", {})
            dom = max(f, key=f.get) if f else "aero"
            nome = {"pu": "power unit", "chassis": "telaio", "aero": "aerodinamica"}[dom]
            ry = sy + 316
            T.text(surf, f"REGOLAMENTO {era['from']}  -  fra {left} "
                         f"{'stagione' if left == 1 else 'stagioni'}",
                   (right.x + 16, ry), 12, T.GOLD, bold=True)
            T.text(surf, f"{era['label']}: a decidere sara' soprattutto {nome} "
                         f"({f.get(dom, 0)*100:.0f}%).",
                   (right.x + 16, ry + 18), 12, T.DIM, maxw=right.w - 32)
            conv = development.prep_conversion(gs, team, era)
            rank = 1 + sum(1 for t in gs.teams.values()
                           if development.prep_conversion(gs, t, era) > conv)
            T.text(surf, f"Con i nostri reparti convertiamo a {conv:.2f}: "
                         f"{rank}i della griglia su questo fronte.",
                   (right.x + 16, ry + 34), 12, T.DIM, maxw=right.w - 32)
            if left == 1:
                T.text(surf, "Ultima stagione utile: dopo il cambio la preparazione non conta piu'.",
                       (right.x + 16, ry + 50), 12, T.WARN, maxw=right.w - 32)

        conto = development.cost_breakdown(gs, team, self.sel_part, self.sel_size)
        cost = conto["totale"]
        gain = development.expected_gain(gs, team, self.sel_part, self.sel_size)
        conf = development.project_confidence(gs, team, self.sel_part, self.sel_size)
        odds = development.outcome_odds(conf, self.sel_size)
        races = development.RACES_OF[self.sel_size]
        liberi = development.free_people(team, self.sel_part)
        serve = development.people_needed(self.sel_size)
        # quello che conta non e' "+4.9 punti": e' quanti secondi al giro, dove
        # si corre adesso e sulle piste che restano
        focus = self.sel_focus or None
        sec_qui = development.gain_seconds(gs, team, self.sel_part, gain,
                                           gs.next_track, focus)
        sec_cal = development.calendar_gain(gs, team, self.sel_part, gain, focus)
        T.text(surf, f"Costo {cost:.2f} M$   |   Sulla carta +{gain:.1f}   |   "
                     f"Tempo {races} gare",
               (right.x + 16, sy + 78), 14, T.TEXT)
        T.text(surf, f"{sec_qui:+.3f} s al giro qui, {sec_cal:+.3f} di media "
                     f"sul calendario che resta",
               (right.x + 16, sy + 98), 13,
               T.OK if sec_cal > 0.03 else (T.WARN if sec_cal > 0.005 else T.BAD),
               maxw=right.w - 32)
        dove = development.gain_domains(gs, team, self.sel_part, gain, gs.next_track, focus)
        T.text(surf, development.spiega_dove(dove, 3).capitalize(),
               (right.x + 16, sy + 116), 12, T.DIM, maxw=right.w - 32)
        migliore, quanto = development.best_focus(gs, team, self.sel_part, gain)
        if migliore and (self.sel_focus != migliore) and quanto - sec_cal > 0.004:
            T.text(surf, f"Il reparto lo disegnerebbe per "
                         f"{engineering.NOMI_DOMINIO[migliore].lower()}: {quanto:+.3f} s",
                   (right.x + 16, sy + 134), 12, T.GOLD, maxw=right.w - 32)
        col_p = T.OK if liberi >= serve else T.BAD
        T.text(surf, f"{serve} persone del reparto per {races} gare "
                     f"({liberi} libere)   -   materiali {conto['materiali']:.2f} M$, "
                     f"straordinari {conto['lavoro']:.2f}",
               (right.x + 16, sy + 154), 12, col_p, maxw=right.w - 32)
        stato, parere = economy.cap_advice(gs, team, cost)
        col_cfo = {"male": T.BAD, "attento": T.WARN, "ok": T.DIM}[stato]
        T.text(surf, parere, (right.x + 16, sy + 172), 12, col_cfo, maxw=right.w - 32)

        col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
        T.text(surf, "Fiducia del reparto", (right.x + 16, sy + 196), 13, T.DIM)
        T.bar(surf, (right.x + 170, sy + 201, right.w - 260, 8), conf * 100, 100, col)
        T.text(surf, f"{conf*100:.0f}%", (right.right - 16, sy + 196), 13, col,
               bold=True, align="right")

        # come puo' finire: quattro bande, disegnate in proporzione
        bx, bw = right.x + 16, right.w - 32
        bande = (("fallito", T.BAD), ("sottotono", T.WARN),
                 ("in linea", T.ACCENT), ("oltre", T.OK))
        x = bx
        for nome, colore in bande:
            w = bw * odds[nome]
            pygame.draw.rect(surf, colore, (int(x), sy + 224, max(2, int(w)), 10),
                             border_radius=2)
            x += w
        yy = sy + 240
        yy += T.paragraph(surf, f"fallisce {odds['fallito']*100:.0f}%   "
                                f"sotto le attese {odds['sottotono']*100:.0f}%   "
                                f"come previsto {odds['in linea']*100:.0f}%   "
                                f"oltre {odds['oltre']*100:.0f}%",
                          (bx, yy), 12, T.DIM_2, bw) + 4
        yy += T.paragraph(surf, development.weakest_link(gs, team, self.sel_part).capitalize()
                          if conf < 0.62 else
                          "Reparto e strumenti sono all'altezza: quello che promettiamo, arriva.",
                          (bx, yy), 12, T.DIM if conf >= 0.62 else T.WARN, bw) + 4
        # quanto lavoro d'assetto rimette in discussione, e chi lo ritrova prima
        upset = development.setup_upset(team, self.sel_size)
        quanto = "poco" if upset < 0.15 else ("parecchio" if upset < 0.32 else "molto")
        casa = (f"il simulatore e {team.private_track_name} ce lo fanno ritrovare prima"
                if team.has_private_track else "senza pista di proprieta' si ritrova il venerdi'")
        T.paragraph(surf, f"Assetto da ritrovare: {quanto} (-{upset*100:.0f}% di quello "
                          f"che sappiamo della vettura). "
                          f"{casa[0].upper()}{casa[1:]}.", (bx, yy), 12, T.GOLD, bw)
        super().draw(surf)


def _colonne_griglia(f_w: int, n_aree: int) -> tuple:
    """Larghezza di nome, media e di ogni colonna d'area."""
    nome = 190 if f_w > 900 else 150
    tot = 76
    col = max(58, (f_w - nome - tot - 12) / n_aree)
    return nome, tot, col


def _esito_colore(v: dict):
    """Il colore con cui si legge com'e' finito un pacchetto."""
    return {"oltre": T.OK, "in linea": T.ACCENT, "sottotono": T.WARN,
            "fallito": T.BAD, "recuperata": T.OK, "pareggiata": T.WARN,
            "mai capita": T.BAD, "rimontata la vecchia": T.BAD}.get(v.get("esito"), T.DIM)


# ================================================================ INGEGNERI
class EngineersPage(Page):
    """La riunione con i propri uomini, la linea per la macchina che verra',
    e il confronto con tutte le altre squadre della griglia."""

    SOTTO = [("noi", "La nostra vettura"), ("griglia", "Tutta la griglia")]

    def __init__(self, shell):
        super().__init__(shell)
        self.vista = "noi"

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.tab_buttons = []
        for i, (key, lab) in enumerate(self.SOTTO):
            tb = Button((r.x + i * 188, r.y + TESTA_TECNICA - 38, 180, 30), lab,
                        style="tab")
            tb.on_click = (lambda k=key: self._vista(k))
            tb.active = (key == self.vista)
            self.tab_buttons.append(tb)
            self.widgets.append(tb)
        b = Button((r.right - 300, r.y + 8, 300, 36),
                   "Applica il piano suggerito", self.apply_plan, "primary")
        b.enabled = not self.team.auto_dev
        self.widgets.append(b)
        # e' la loro pagina: qui si decide se lasciarli lavorare da soli
        self.widgets.append(Toggle((r.right - 620, r.y + 8, 300, 36),
                                   "Fanno da soli gli aggiornamenti",
                                   self.team.auto_dev, on_change=self._set_auto_dev))
        self._brief = None
        self._report = None
        if self.vista == "griglia":
            return

        # --- la linea per la vettura dell'anno prossimo
        left = pygame.Rect(r.x, r.y + TESTA_TECNICA, r.w * 0.46, r.h - TESTA_TECNICA)
        self.nc_y = left.bottom - 40 - (len(nextcar.AREE) + 1) * 30
        self.share = Slider((left.x + 16, self.nc_y, left.w - 32, 26),
                            "Sull'anno prossimo", self.team.next_reg_share * 100.0,
                            0.0, 80.0, on_change=self._set_share, fmt="{:.0f}%")
        self.widgets.append(self.share)
        self.area_sliders = {}
        y = self.nc_y + 30
        brief = self.team.next_car_brief or {}
        for key, meta in nextcar.AREE.items():
            sl = Slider((left.x + 16, y, left.w - 32, 26), meta["label"],
                        float(brief.get(key, 1.0)), 0.0, 5.0,
                        on_change=(lambda v, k=key: self._set_area(k, v)), fmt="{:.1f}")
            self.area_sliders[key] = sl
            self.widgets.append(sl)
            y += 30

    def _disegna_griglia(self, surf, r) -> None:
        """Tutte le squadre, area per area: dove siamo avanti e dove indietro.

        La nostra riga e' quella vera. Le altre sono le stime dello scouting:
        una macchina avversaria non la si misura, la si guarda girare, e quanto
        bene dipende da chi ci lavora e da quante gare si sono viste.
        """
        gs, team = self.gs, self.team
        aree = list(engineering.AREAS.items())
        righe = []
        for t in gs.teams.values():
            prof = (engineering.car_profile(t, gs) if t.id == team.id
                    else engineering.estimate(gs, team, t))
            tot = sum(prof[a] for a, _l in aree) / len(aree)
            righe.append((t, prof, tot))
        righe.sort(key=lambda x: -x[2])

        x0, y = r.x, r.y + TESTA_TECNICA - 4
        T.paragraph(surf, "Ogni casella e' quanto vale quella squadra in quell'area, da "
                          "0 a 100 rispetto al resto della griglia. La nostra riga e' "
                          "quella vera; le altre sono stime dello scouting, e diventano "
                          "piu' precise con le gare disputate.",
                    (x0, y), 12, T.DIM_2, r.w - 8)
        y += 34
        nome_w, tot_w, col_w = _colonne_griglia(r.w - 8, len(aree))
        T.text(surf, "SQUADRA", (x0, y + 30), 11, T.DIM_2, bold=True)
        T.text(surf, "MEDIA", (x0 + nome_w + tot_w - 8, y + 30), 11, T.DIM_2,
               bold=True, align="right")
        for i, (_a, lab) in enumerate(aree):
            x = x0 + nome_w + tot_w + i * col_w
            for j, parola in enumerate(T.wrap(lab, 11, col_w - 14, bold=True)[:3]):
                T.text(surf, parola, (x, y + j * 13), 11, T.DIM_2, bold=True,
                       maxw=col_w - 8)
        y += 46
        migliori = {a: max(x[1][a] for x in righe) for a, _l in aree}
        for t, prof, tot in righe:
            noi = (t.id == team.id)
            riga = pygame.Rect(x0, y, r.w - 8, 30)
            if noi:
                T.panel(surf, riga, T.PANEL_3, radius=6)
            pygame.draw.rect(surf, T.hex_rgb(t.colour), (riga.x + 4, riga.y + 5, 4, 20))
            T.text(surf, t.name, (riga.x + 16, riga.y + 6), 14,
                   T.TEXT if noi else T.DIM, bold=noi, maxw=nome_w - 24)
            T.text(surf, f"{tot:.0f}", (x0 + nome_w + tot_w - 8, riga.y + 6), 15,
                   T.stat_colour(tot, 40, 80), bold=True, align="right")
            for i, (a, _lab) in enumerate(aree):
                v = prof[a]
                cella = pygame.Rect(int(x0 + nome_w + tot_w + i * col_w), riga.y + 3,
                                    int(col_w - 6), 24)
                tinta = T.mix(T.PANEL_2, T.stat_colour(v, 35, 78),
                              0.30 + 0.55 * (v / 100.0))
                pygame.draw.rect(surf, tinta, cella, border_radius=4)
                if abs(v - migliori[a]) < 0.01:
                    pygame.draw.rect(surf, T.GOLD, cella, 2, border_radius=4)
                T.text(surf, f"{v:.0f}", (cella.centerx, cella.y + 4), 13, T.TEXT,
                       bold=noi, align="center")
            y += 32

        # dove conviene mettere i soldi, viste le gare che restano
        y += 14
        T.text(surf, "DOVE CONVIENE LAVORARE", (x0, y), 12, T.DIM_2, bold=True)
        y += 22
        for lab, dx in (("AREA", 0), ("POSIZIONE", 240), ("DAL MIGLIORE", 360),
                        ("QUANTO LA CHIEDONO LE GARE CHE RESTANO", 500)):
            T.text(surf, lab, (x0 + dx, y), 11, T.DIM_2, bold=True)
        y += 20
        bias = engineering.calendar_bias(gs)
        rep = self._report or engineering.field_report(gs)
        ordinati = sorted(engineering.AREAS.items(),
                          key=lambda kv: -(max(0.0, rep[kv[0]]["best"] - rep[kv[0]]["mine"])
                                           * (0.6 + 0.8 * bias.get(kv[0], 0.5))))
        for a, lab in ordinati:
            d = rep[a]
            gap = d["delta"]
            colore = T.OK if gap >= -2 else (T.WARN if gap > -14 else T.BAD)
            T.text(surf, lab, (x0, y), 13, T.TEXT, maxw=230)
            T.text(surf, f"{d['rank']}i della griglia", (x0 + 240, y), 13, T.DIM)
            T.text(surf, f"{gap:+.0f} da {d['best_team']}", (x0 + 360, y), 13, colore,
                   bold=True)
            dom = bias.get(a, 0.5)
            T.bar(surf, (x0 + 500, y + 5, 200, 8), dom * 100, 100,
                  T.GOLD if dom > 0.6 else T.DIM)
            T.text(surf, f"{dom*100:.0f}%", (x0 + 712, y), 13,
                   T.GOLD if dom > 0.6 else T.DIM)
            y += 22
        y += 6
        T.paragraph(surf, "Recuperare dove le gare rimaste non premiano niente e' fatica "
                          "sprecata: conviene guardare insieme il distacco e la colonna "
                          "qui accanto.", (x0, y), 12, T.DIM_2, r.w - 8)

    def _vista(self, k) -> None:
        self.vista = k
        self.build()
        self.refresh()

    def _set_auto_dev(self, v) -> None:
        self.team.auto_dev = bool(v)
        self.build()

    def _set_share(self, v) -> None:
        self.team.next_reg_share = max(0.0, min(0.80, v / 100.0))

    def _set_area(self, key, v) -> None:
        nextcar.set_brief(self.team, key, v)

    def apply_plan(self) -> None:
        sug = engineering.suggested_allocation(self.gs)
        self.team.resource_alloc = sug
        self.app.toast("Piano di sviluppo aggiornato secondo gli ingegneri.")

    def refresh(self) -> None:
        self.build()
        self._brief = engineering.briefing(self.gs)
        self._report = engineering.field_report(self.gs)

    def draw(self, surf) -> None:
        r = self.rect
        if self._brief is None:
            self.refresh()
        T.text(surf, "CONFRONTO TECNICO", (r.x, r.y + 4), 22, T.TEXT, bold=True)
        if self.vista == "griglia":
            self._disegna_griglia(surf, r)
            super().draw(surf)
            return
        left = pygame.Rect(r.x, r.y + TESTA_TECNICA, r.w * 0.46, r.h - TESTA_TECNICA)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "RIUNIONE CON I RESPONSABILI", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        if self.team.auto_dev:
            parti = engineering.suggested_parts(self.gs, self.team, 3)
            nomi = ", ".join(C.CAR_PARTS[p]["label"].lower() for p in parti[:3])
            T.text(surf, f"lavorano da soli su {nomi}", (left.right - 16, left.y + 12),
                   11, T.OK, align="right", maxw=left.w * 0.6)
        y = left.y + 40
        saltati = 0
        for speaker, line in self._brief:
            righe = T.wrap(line, 13, left.w - 44)
            alto = 20 + len(righe) * 18 + 12
            # si guarda prima se ci sta tutto: sotto ci va il progetto della
            # macchina nuova, e mezza frase sopra il titolo non si legge
            if y + alto > self.nc_y - 62:
                saltati += 1
                continue
            T.text(surf, speaker, (left.x + 16, y), 14, T.ACCENT, bold=True)
            y += 20
            for riga in righe:
                T.text(surf, riga, (left.x + 24, y), 13, T.TEXT)
                y += 18
            y += 12
        if saltati:
            T.text(surf, f"e altri {saltati} interventi: la riunione e' lunga",
                   (left.x + 16, y), 11, T.DIM_2, maxw=left.w - 32)

        # --- il progetto della vettura dell'anno prossimo
        gs, team = self.gs, self.team
        f = nextcar.fidelity(team)
        proj = nextcar.projection(gs, team)
        atteso = nextcar.expected_gain(gs, team)
        ty = self.nc_y - 62
        T.text(surf, f"PROGETTO VETTURA {gs.season + 1}", (left.x + 16, ty), 12,
               T.GOLD, bold=True)
        T.text(surf, f"gia' in cassaforte: {atteso:+.1f} di media",
               (left.right - 16, ty), 11,
               T.OK if atteso > 0.4 else T.DIM_2, align="right")
        tp = team.role("team_principal")
        td = team.role("technical_director")
        col_f = T.OK if f > 0.75 else (T.WARN if f > 0.5 else T.BAD)
        chi = f"{tp.last if tp else 'Il team principal'} e {td.last if td else 'il tecnico'}"
        if f > 0.8:
            frase = f"{chi}: quello che chiedi, il reparto lo fa."
        elif f > 0.55:
            frase = f"{chi}: la linea arriva, ma per strada si perde qualcosa."
        else:
            frase = f"{chi}: il reparto fa quello che gli riesce, non quello che chiedi."
        T.text(surf, frase, (left.x + 16, ty + 18), 12, col_f, maxw=left.w - 32)
        T.text(surf, f"fedelta' alla linea {f*100:.0f}%", (left.right - 16, ty + 18), 11,
               col_f, align="right")
        forte = max(proj, key=proj.get) if proj else None
        T.paragraph(surf, (f"Finora il lavoro e' andato soprattutto su "
                           f"{nextcar.AREE[forte]['label'].lower()} ({proj[forte]:+.1f})."
                           if forte and proj[forte] > 0.2 else
                           "Nessun lavoro ancora dirottato sull'anno prossimo: ogni punto "
                           "va sulla macchina di adesso."),
                    (left.x + 16, ty + 36), 11, T.DIM_2, left.w - 32)

        right = pygame.Rect(r.x + r.w * 0.48, r.y + TESTA_TECNICA, r.w * 0.52 - 4,
                            r.h - TESTA_TECNICA)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "DOVE SIAMO RISPETTO ALLA GRIGLIA", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        hy = right.y + 40
        # le colonne si spartiscono il pannello: a larghezza fissa, su una
        # finestra stretta l'ultima finiva fuori e non si vedeva
        cx = {"noi": right.w * 0.44, "migliore": right.w * 0.55,
              "gap": right.w * 0.79, "pos": right.w * 0.92}
        for lab, x in (("AREA", 16), ("NOI", cx["noi"]), ("MIGLIORE", cx["migliore"]),
                       ("GAP", cx["gap"]), ("POS", cx["pos"])):
            T.text(surf, lab, (right.x + x, hy), 11, T.DIM_2, bold=True)
        y = hy + 22
        for area, lab in engineering.AREAS.items():
            d = self._report[area]
            T.text(surf, lab, (right.x + 16, y), 14, T.TEXT, maxw=cx["noi"] - 24)
            T.text(surf, f"{d['mine']:.0f}", (right.x + cx["noi"], y), 14,
                   T.stat_colour(d["mine"], 40, 80), bold=True)
            T.text(surf, f"{d['best']:.0f} {d['best_team']}", (right.x + cx["migliore"], y),
                   13, T.DIM, maxw=cx["gap"] - cx["migliore"] - 8)
            gap = d["delta"]
            T.text(surf, f"{gap:+.0f}", (right.x + cx["gap"], y), 14,
                   T.OK if gap >= -2 else (T.WARN if gap > -14 else T.BAD), bold=True)
            T.text(surf, f"{d['rank']}o", (right.x + cx["pos"], y), 14, T.TEXT)
            T.bar(surf, (right.x + 16, y + 20, right.w - 40, 5), d["mine"], 100,
                  T.stat_colour(d["mine"], 40, 80))
            y += 40
        T.text(surf, "Le stime sugli avversari migliorano con lo scouting e con le gare disputate.",
               (right.x + 16, right.bottom - 30), 12, T.DIM_2)
        super().draw(surf)


# ================================================================ POWER UNIT
class PowerUnitPage(Page):
    """Il reparto motori: sviluppo, confronto coi motoristi, programma proprio."""

    def build(self) -> None:
        self.found_note = ""
        r = self.rect
        self.widgets = []
        gs, team = self.gs, self.team
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        self.b_omologa = None
        if self._can_homologate():
            # la y vera gliela da' il disegno, quando sa dove finisce il testo
            self.b_omologa = Button((left.x + 16, left.bottom - 58, left.w - 32, 40),
                                    "Omologa la specifica nuova",
                                    self.homologate, "primary")
            self.widgets.append(self.b_omologa)
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        y = right.y + 300
        if powertrain.ready_to_debut(gs):
            self.widgets.append(Button((right.x + 16, y, right.w - 32, 42),
                                       "Porta in pista la nostra power unit",
                                       self.debut, "primary"))
        elif not team.works and not powertrain.has_program(gs):
            can, why = powertrain.can_found(team)
            b = Button(
                (right.x + 16, y, right.w - 32, 42),
                f"Fonda il reparto motori ({powertrain.PROGRAM_START_COST:.0f} M$)"
                if can else "Reparto motori fuori dalla nostra portata",
                self.start_program, "primary" if can else "ghost")
            b.enabled = can
            b.tip = why
            self.widgets.append(b)
            self.found_note = "" if can else why

    def refresh(self) -> None:
        self.build()

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

    def draw(self, surf) -> None:
        r, gs, team = self.rect, self.gs, self.team
        eng = powertrain.maker(gs, team)
        T.text(surf, "POWER UNIT", (r.x, r.y + 10), 22, T.TEXT, bold=True)
        status = ("costruttore" if team.works else
                  "team ufficiale" if team.is_partner else
                  "cliente, reparto in costruzione" if powertrain.has_program(gs) else "cliente")
        T.text(surf, f"{eng.get('name', '-')} - {status}", (r.x, r.y + 42), 14, T.DIM)

        # --- confronto fra i motoristi -----------------------------------
        left = pygame.Rect(r.x, r.y + 96, r.w * 0.46, r.h - 96)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "I MOTORISTI", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        y = left.y + 42
        ranked = sorted(gs.engine_makers.items(), key=lambda kv: -powertrain.rating(kv[1]))
        for eid, m in ranked:
            mine = (eid == team.engine)
            builder = powertrain.builder_of(gs, eid)
            col = T.ACCENT if mine else T.TEXT
            T.text(surf, m.get("name", eid), (left.x + 16, y), 14, col, bold=mine,
                   maxw=left.w * 0.55)
            T.text(surf, f"{powertrain.rating(m):.1f}", (left.right - 16, y), 14, col,
                   bold=True, align="right")
            who = builder.short if builder else "nessuna squadra ufficiale"
            n = len(powertrain.customers_of(gs, eid))
            T.text(surf, f"{who} - {n} client{'e' if n == 1 else 'i'}",
                   (left.x + 16, y + 18), 11, T.DIM_2, maxw=left.w - 32)
            T.bar(surf, (left.x + 16, y + 34, left.w - 32, 6), powertrain.rating(m), 100,
                  T.ACCENT if mine else T.PANEL_3)
            y += 52

        y += 4
        sp = powertrain.spec(gs, team.engine)
        # i numeri del banco li vede solo chi il motore lo costruisce
        nostro = team.works
        T.text(surf, "LA NOSTRA UNITA'", (left.x + 16, y), 12, T.DIM_2, bold=True)
        if nostro:
            T.text(surf, "in banco", (left.right - 16, y), 11, T.DIM_2, align="right")
        y += 22
        for attr, label in (("power", "Potenza termica"), ("ers", "Ibrido ed ERS"),
                            ("reliability", "Affidabilita'")):
            T.text(surf, label, (left.x + 16, y), 13, T.DIM)
            T.text(surf, f"{float(eng.get(attr, 85)):.1f}",
                   (left.right - (96 if nostro else 16), y), 13, T.TEXT,
                   bold=True, align="right")
            g = float(sp["gain"].get(attr, 0.0))
            if nostro and g > 0.01:
                T.text(surf, f"+{g:.1f}", (left.right - 16, y), 13, T.OK,
                       bold=True, align="right")
            y += 20

        # --- la specifica che sta crescendo al banco ----------------------
        y += 12
        T.text(surf, "SPECIFICA IN LAVORAZIONE", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        if powertrain.locked(gs):
            T.text(surf, "Sviluppo congelato: si corre con quello che c'e'.",
                   (left.x + 16, y), 13, T.WARN, maxw=left.w - 32)
        elif not team.works:
            costruttore = powertrain.builder_of(gs, team.engine)
            chi = costruttore.short if costruttore else eng.get("name", "il motorista")
            T.text(surf, f"La specifica la decide {chi}: noi la montiamo e basta. "
                         f"E' il prezzo di comprare il motore invece di farlo.",
                   (left.x + 16, y), 13, T.DIM, maxw=left.w - 32)
        else:
            valore = powertrain.spec_value(sp)
            conf = powertrain.spec_confidence(gs, team.engine)
            odds = powertrain.spec_odds(gs, team.engine)
            rimaste = powertrain.specs_left(gs, team.engine)
            T.text(surf, f"Vale {valore:+.2f} dopo {sp.get('races', 0)} gare di banco",
                   (left.x + 16, y), 13, T.TEXT if valore > 0.05 else T.DIM,
                   maxw=left.w - 32)
            T.text(surf, f"{rimaste} su {powertrain.specs_allowed(gs)}",
                   (left.right - 16, y), 13, T.GOLD if rimaste else T.BAD,
                   bold=True, align="right")
            y += 22
            col = T.OK if conf > 0.62 else (T.WARN if conf > 0.38 else T.BAD)
            T.text(surf, "Fiducia del banco", (left.x + 16, y), 13, T.DIM)
            T.bar(surf, (left.x + 160, y + 5, left.w - 250, 8), conf * 100, 100, col)
            T.text(surf, f"{conf*100:.0f}%", (left.right - 16, y), 13, col,
                   bold=True, align="right")
            y += 24
            T.text(surf, f"fallisce {odds['fallito']*100:.0f}%   "
                         f"sotto le attese {odds['sottotono']*100:.0f}%   "
                         f"oltre {odds['oltre']*100:.0f}%",
                   (left.x + 16, y), 12, T.DIM_2, maxw=left.w - 32)
            y += 20
            if rimaste <= 0:
                T.text(surf, "Gettoni finiti: il resto del lavoro va all'anno prossimo.",
                       (left.x + 16, y), 12, T.WARN, maxw=left.w - 32)
            elif sp.get("races", 0) < 5:
                T.text(surf, "Piu' resta al banco, meno sorprese in pista.",
                       (left.x + 16, y), 12, T.DIM_2, maxw=left.w - 32)
            y += 24

        # il pulsante sta sotto quello che c'e' scritto, non a un'altezza fissa:
        # su una finestra bassa ci finiva in mezzo
        if getattr(self, "b_omologa", None) is not None:
            self.b_omologa.rect.y = int(max(y + 8, left.bottom - 58))

        # --- reparto e programma -----------------------------------------
        right = pygame.Rect(r.x + r.w * 0.48, r.y + 96, r.w * 0.52 - 4, r.h - 96)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "IL NOSTRO REPARTO", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)

        hop = team.role("head_of_powertrain")
        ceil = powertrain.ceiling(gs, team)
        clients = powertrain.customers_of(gs, team.engine) if team.works else []
        y = right.y + 96
        from ...core import season as SEASON
        rows = [
            ("Budget del reparto", f"{SEASON.player_budgets(gs)[1]:.2f} M$ a gara"),
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
            T.text(surf, k, (right.x + 16, y), 13, T.DIM)
            T.text(surf, v, (right.right - 16, y), 13, T.TEXT, bold=True, align="right",
                   maxw=right.w * 0.5)
            y += 22

        y += 10
        if powertrain.locked(gs):
            T.text(surf, "Sviluppo power unit congelato dal regolamento.",
                   (right.x + 16, y), 13, T.WARN, bold=True, maxw=right.w - 32)
            y += 24
        if gs.regulations.get("pu_equalisation"):
            T.text(surf, "Equalizzazione in vigore: chi e' indietro sviluppa di piu'.",
                   (right.x + 16, y), 12, T.DIM, maxw=right.w - 32)
            y += 22

        p = powertrain.program(gs)
        if powertrain.has_program(gs):
            T.text(surf, "PROGRAMMA IN CORSO", (right.x + 16, y), 12, T.DIM_2, bold=True)
            y += 22
            T.text(surf, f"Livello raggiunto {p['level']:.1f} su un tetto di {ceil:.1f}",
                   (right.x + 16, y), 13, T.TEXT, maxw=right.w - 32)
            T.bar(surf, (right.x + 16, y + 22, right.w - 32, 8), p["level"], 100, T.OK)
            y += 40
            T.text(surf, f"Investiti {p['invested']:.0f} M$ - in pista dal {p['ready_season']}",
                   (right.x + 16, y), 12, T.DIM, maxw=right.w - 32)
            y += 26
            from ...core import season as SEASON
            o = powertrain.debut_outlook(gs, SEASON.player_budgets(gs)[1])
            T.text(surf, "QUANDO PORTARLA IN PISTA", (right.x + 16, y), 12, T.DIM_2, bold=True)
            y += 22
            gap = o["gap_now"]
            T.text(surf, "Oggi il nostro motore vale", (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['now']:.1f}", (right.x + 240, y), 13, T.TEXT, bold=True)
            T.text(surf, f"contro il {o['supplied']:.1f} che compriamo ({gap:+.1f})",
                   (right.x + 280, y), 13, T.OK if gap >= 0 else T.BAD)
            y += 22
            T.text(surf, f"Fra {o['horizon']} gare, se debutta subito",
                   (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['if_debut_now']:.1f}", (right.x + 240, y), 13, T.OK, bold=True)
            y += 20
            T.text(surf, f"Fra {o['horizon']} gare, se resta al banco",
                   (right.x + 16, y), 13, T.DIM)
            T.text(surf, f"{o['if_wait']:.1f}", (right.x + 240, y), 13, T.WARN, bold=True)
            y += 24
            for line in (f"Al banco si sviluppa al {o['bench_penalty']*100:.0f}% del ritmo: "
                         f"mancano i dati veri.",
                         "Correre con un motore acerbo costa punti adesso, ma lo fa",
                         "crescere piu' in fretta."):
                T.text(surf, line, (right.x + 16, y), 12, T.DIM_2, maxw=right.w - 32)
                y += 16
        elif not team.works:
            for riga in (f"Compriamo la power unit da {eng.get('name', '-')} per "
                         f"{team.engine_customer_cost:.0f} M$ a stagione, e ci teniamo",
                         "la specifica che decidono loro. Fondando un reparto nostro",
                         "potremmo svilupparla in casa, ma servono anni e un buon",
                         "responsabile powertrain."):
                T.text(surf, riga, (right.x + 16, y), 13, T.DIM, maxw=right.w - 32)
                y += 18
        else:
            for riga in ("Costruiamo la nostra power unit: il budget qui sopra e' quello",
                         "che il reparto motori spende a ogni gara. Sta fuori dal tetto di",
                         "spesa della squadra, come nella realta'."):
                T.text(surf, riga, (right.x + 16, y), 13, T.DIM, maxw=right.w - 32)
                y += 18
        if getattr(self, "found_note", ""):
            T.text(surf, self.found_note, (r.x + 16, r.bottom - 26), 13, T.WARN,
                   maxw=r.w - 32)
        super().draw(surf)
