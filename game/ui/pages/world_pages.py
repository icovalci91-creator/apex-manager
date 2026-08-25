"""Pagine: infrastrutture, regolamento, classifiche, calendario, storico."""
from __future__ import annotations

import pygame

from ... import config as C
from ...core import calendar as CAL, economy, engineering, facilities, rules
from .. import theme as T
from .. import trackdraw
from ..scenes.shell import Page
from ..widgets import Button, ScrollList, card


facility_cost = facilities.cost


class FacilitiesPage(Page):
    # Quanto della pagina si tiene l'elenco delle strutture. Su una finestra
    # stretta se ne prende di piu': dentro ci stanno nome, livello, barra,
    # stato e il pulsante, e con meta' schermo finivano uno sopra l'altro.
    def _quota(self, r) -> float:
        return min(0.62, max(0.50, 580.0 / max(1, r.w)))

    def _colonne(self, r) -> tuple:
        """(inizio del pulsante, dove deve fermarsi il testo della riga)."""
        bx = r.x + r.w * self._quota(r) + 10 - 158
        return int(bx), int(bx - 14)

    def build(self) -> None:
        r = self.rect
        self.widgets = []
        self.buttons = {}
        y = r.y + 112
        bx, _fine = self._colonne(r)
        for k in C.FACILITIES:
            lab = "Potenzia" if facilities.is_built(self.team, k) else "Costruisci"
            b = Button((bx, y, 150, 30), lab, style="normal")
            b.on_click = (lambda k=k: self.upgrade(k))
            self.buttons[k] = b
            self.widgets.append(b)
            y += 42

    def upgrade(self, key: str) -> None:
        ok, msg = facilities.upgrade(self.gs, self.team, key)
        if ok:
            self.gs.push(msg, "team")
        self.app.toast(msg)

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, team, gs = self.rect, self.team, self.gs
        cw = (r.w - 32) / 3
        resto = economy.capex_left(gs, team)
        tetto = economy.capex_limit(gs, team)
        card(surf, (r.x, r.y, cw, 86), "Budget costruzioni",
             f"{resto:.1f} M$",
             f"di {tetto:.0f} in {economy.CAPEX_WINDOW} stagioni - fuori dal cap",
             colour=T.OK if resto > tetto * 0.3 else T.WARN, accent=T.GOLD)
        costruite = [k for k in team.facilities if facilities.is_built(team, k)]
        obs = sum(facilities.decay_of(team.facilities[k], facilities.age_of(team, k))
                  for k in costruite) / max(1, len(costruite))
        avg = facilities.average(team)
        card(surf, (r.x + cw + 16, r.y, cw, 86), "Livello medio strutture", f"{avg:.0f}",
             _infra_rank(gs, team), accent=T.ACCENT)
        # la gestione invece sta dentro il tetto tecnico: costruire e' fuori,
        # far girare quello che si e' costruito e' dentro
        fresche = sum(1 for k in costruite
                      if facilities.age_of(team, k) < facilities.GRACE_SEASONS)
        card(surf, (r.x + 2 * (cw + 16), r.y, cw, 86), "Obsolescenza",
             "nessuna" if obs < 0.01 else f"-{obs:.2f}",
             f"{fresche} strutture su {len(costruite)} all'avanguardia",
             colour=T.OK if obs < 0.2 else T.BAD, accent=T.BAD if obs >= 0.2 else T.OK)

        panel = pygame.Rect(r.x, r.y + 80, r.w * self._quota(r) + 10, r.h - 80)
        T.panel(surf, panel, T.PANEL, radius=10, border=T.LINE)
        # la gestione sta dentro il tetto tecnico: si dice qui, sopra l'elenco
        T.text(surf, f"gestione {team.facility_upkeep:.1f} M$ l'anno, quella dentro il cap",
               (panel.x + 16, panel.y + 10), 12, T.DIM_2, maxw=panel.w - 32)
        y = r.y + 112
        # dove comincia il pulsante, e fin dove puo' arrivare la riga
        bx, fine = self._colonne(r)
        for k, meta in C.FACILITIES.items():
            lvl = team.facilities.get(k, 60.0)
            if not facilities.is_built(team, k):
                # non c'e': al suo posto si mostra quanto costa tirarla su
                T.text(surf, meta["label"], (panel.x + 16, y), 15, T.DIM, maxw=150)
                T.text(surf, "da costruire", (panel.x + 172, y - 1), 13, T.DIM_2, maxw=110)
                T.text(surf, f"{facilities.build_cost(k):.0f} M$ per averla",
                       (fine, y - 1), 13, T.GOLD, align="right")
                T.text(surf, "si parte da un livello di "
                             f"{facilities.BUILD_LEVEL:.0f}, poi si potenzia come le altre",
                       (panel.x + 16, y + 20), 12, T.DIM_2, maxw=fine - panel.x - 16)
                y += 42
                continue
            cost = facility_cost(lvl, meta["cost"])
            stato, eta = facilities.state_label(team, k)
            perdita = facilities.decay_of(lvl, eta)
            col_st = {"all'avanguardia": T.OK, "ancora competitiva": (150, 200, 90),
                      "da aggiornare": T.WARN}.get(stato, T.BAD)
            # tutto quello che sta sulla riga si ferma prima del pulsante: su
            # una finestra stretta ci finiva sotto e non si leggeva piu'
            T.text(surf, meta["label"], (panel.x + 16, y), 15, T.TEXT, maxw=150)
            T.text(surf, f"{lvl:.0f}", (panel.x + 172, y - 1), 14, T.TEXT, bold=True)
            barra_x = panel.x + 206
            T.bar(surf, (barra_x, y + 5, max(40, fine - 150 - barra_x), 9), lvl, 100,
                  T.stat_colour(lvl, 60, 88))
            T.text(surf, f"+{facilities.gain(lvl):.1f} per {cost:.1f} M$",
                   (fine, y - 1), 13, T.GOLD, align="right", maxw=140)
            # seconda riga: da quanto e' ferma e quanto le costa
            if eta < 1:
                anni = "rifatta quest'anno"
            elif eta < 2:
                anni = "rifatta l'anno scorso"
            else:
                anni = f"ferma da {eta:.0f} stagioni"
            T.text(surf, f"{stato}  -  {anni}", (panel.x + 16, y + 20), 12, col_st,
                   maxw=fine - panel.x - 150)
            T.text(surf, "non invecchia" if perdita <= 0.01 else f"-{perdita:.1f} punti l'anno",
                   (fine, y + 20), 12, T.OK if perdita <= 0.01 else T.BAD, align="right")
            y += 42

        quota = self._quota(r)
        right = pygame.Rect(r.x + r.w * quota + 26, r.y + 80, r.w * (1 - quota) - 26,
                            r.h - 80)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CONFRONTO CON LA GRIGLIA", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        y = right.y + 40
        order = sorted(gs.teams.values(), key=lambda t: -facilities.average(t))
        for i, t in enumerate(order, 1):
            a = facilities.average(t)
            col = T.hex_rgb(t.colour)
            hl = (t.id == team.id)
            if hl:
                T.panel(surf, (right.x + 8, y - 3, right.w - 16, 26), T.PANEL_3, radius=6)
            pygame.draw.rect(surf, col, (right.x + 16, y + 3, 3, 14))
            T.text(surf, f"{i}.", (right.x + 26, y + 2), 13, T.DIM)
            T.text(surf, t.short, (right.x + 50, y + 2), 14, T.TEXT if hl else T.DIM, bold=hl)
            T.bar(surf, (right.x + 180, y + 7, right.w - 250, 8), a, 100, col)
            T.text(surf, f"{a:.0f}", (right.right - 16, y + 2), 13, T.TEXT, bold=True, align="right")
            y += 28
        y += 12
        y += T.paragraph(surf, f"Una struttura appena rifatta resta di riferimento per "
                               f"{facilities.GRACE_SEASONS:.0f} stagioni: in quel periodo "
                               f"non perde nulla. Poi comincia a restare indietro, sempre "
                               f"piu' in fretta.",
                         (right.x + 16, y), 12, T.GOLD, right.w - 32) + 10
        y += T.paragraph(surf, "Le strutture agiscono su sviluppo, assetto, soste e "
                               "crescita dei giovani. Ogni anno invecchiano: quello che non "
                               "si rinnova arretra, e nessuno puo' permettersi di tenerle "
                               "tutte al passo.",
                         (right.x + 16, y), 12, T.DIM_2, right.w - 32) + 10
        T.paragraph(surf, f"Costruire non passa dal tetto di spesa: ha un limite suo, "
                          f"{economy.CAPEX_WINDOW} stagioni alla volta, e chi e' indietro "
                          f"in classifica ne ha di piu' - serve a lasciargli modo di "
                          f"rimettersi in pari. Nel tetto tecnico resta la gestione di "
                          f"quello che si e' costruito.",
                    (right.x + 16, y), 12, T.GOLD, right.w - 32)
        super().draw(surf)


def _infra_rank(gs, team) -> str:
    order = sorted(gs.teams.values(), key=lambda t: -facilities.average(t))
    return f"{[t.id for t in order].index(team.id) + 1}a struttura della griglia"


class RulesPage(Page):
    def build(self) -> None:
        self.widgets = []
        self.proposals = []

    def refresh(self) -> None:
        self.build()
        self._read_proposals()

    def _read_proposals(self) -> None:
        """Prepara le proposte una volta sola.

        Farlo in draw() significava riestrarle sessanta volte al secondo, con
        il pannello che cambiava a ogni frame, e pescare ogni volta dal
        generatore della partita.
        """
        gs = self.gs
        pending = gs.pending_votes or rules.draw_proposals(gs, 3, gs.view_rng("commissione"))
        self.proposals = []
        for p in pending[:4]:
            score = rules.appeal_score(gs, gs.player, p)
            self.proposals.append({
                "p": p,
                "colour": T.OK if score > 0.2 else (T.BAD if score < -0.2 else T.WARN),
                "verdict": ("ci conviene" if score > 0.2 else
                            "ci penalizza" if score < -0.2 else "impatto neutro"),
                "yes": sum(1 for t in gs.teams.values() if rules.appeal_score(gs, t, p) > 0),
            })

    def draw(self, surf) -> None:
        r, gs = self.rect, self.gs
        reg = gs.regulations
        left = pygame.Rect(r.x, r.y, r.w * 0.46, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "REGOLAMENTO IN VIGORE", (left.x + 16, left.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, reg.get("label", ""), (left.x + 16, left.y + 32), 17, T.TEXT, bold=True,
               maxw=left.w - 32)
        pu, aero, sp = reg["power_unit"], reg["aero"], reg["sporting"]
        rows = [
            ("Budget cap", f"{reg['cost_cap_musd']:.0f} M$"),
            ("Stipendi piloti nel cap", "no" if reg.get("cost_cap_excludes_driver_salaries") else "si"),
            ("Peso minimo", f"{reg['min_weight_kg']} kg"),
            ("Power unit", f"{pu['ice_kw']} kW termico + {pu['electric_kw']} kW elettrico"),
            ("Unita' per stagione", str(pu["units_per_season"])),
            ("Aero attiva", "si" if aero["active_aero"] else "no"),
            ("Indice di carico", f"{aero['downforce_index']:.2f}"),
            ("Punti", " - ".join(str(int(p)) for p in sp["points"])),
            ("Punto giro veloce", "si" if sp.get("fastest_lap_point") else "no"),
            ("Sprint", str(sp.get("sprint_events", 0))),
            ("Mescole obbligatorie", str(sp.get("mandatory_compounds", 2))),
            ("Giornate di test", str(sp.get("testing_days", 3))),
            ("Fornitore gomme", reg["tyres"]["supplier"]),
        ]
        y = left.y + 64
        for k, v in rows:
            T.text(surf, k, (left.x + 16, y), 13, T.DIM)
            T.text(surf, v, (left.right - 16, y), 13, T.TEXT, bold=True, align="right",
                   maxw=left.w * 0.55)
            y += 22
        y += 10
        T.text(surf, "ORE DI SVILUPPO AERO (ATR)", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        scale = reg["aero_testing_restriction"]["scale"]
        for i, v in enumerate(scale[:len(gs.teams)], 1):
            T.text(surf, f"{i}o costruttori", (left.x + 16, y), 12, T.DIM)
            T.bar(surf, (left.x + 130, y + 4, left.w - 200, 7), v, 120)
            T.text(surf, f"{v}%", (left.right - 16, y), 12, T.TEXT, align="right")
            y += 18

        right = pygame.Rect(r.x + r.w * 0.48, r.y, r.w * 0.52 - 4, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "PROPOSTE IN COMMISSIONE", (right.x + 16, right.y + 12), 12, T.DIM_2, bold=True)
        com = gs.commission
        T.text(surf, f"{len(gs.teams)} scuderie ({com['team_votes']} voto ciascuna) + "
                     f"FIA {com['fia_votes']} + FOM {com['fom_votes']}",
               (right.x + 16, right.y + 32), 12, T.DIM)
        if not self.proposals:
            self._read_proposals()
        y = right.y + 60
        # quello che e' gia' passato ma non e' ancora in vigore: si sa in
        # anticipo, ed e' con quello che si progetta la macchina dell'anno dopo
        in_arrivo = rules.pending(gs)
        if in_arrivo:
            T.text(surf, "GIA' APPROVATE, IN VIGORE PIU' AVANTI",
                   (right.x + 16, y), 12, T.GOLD, bold=True)
            y += 20
            for voce in in_arrivo[:3]:
                T.text(surf, f"dal {voce['season']}", (right.x + 24, y), 12, T.GOLD)
                T.text(surf, voce["title"], (right.x + 92, y), 13, T.TEXT,
                       maxw=right.w - 120)
                y += 19
            y += 10
        for item in self.proposals:
            p = item["p"]
            T.panel(surf, (right.x + 12, y, right.w - 24, 96), T.PANEL_2, radius=8)
            T.text(surf, p["title"], (right.x + 24, y + 10), 15, T.TEXT, bold=True,
                   maxw=right.w - 140)
            col_cat = (T.WARN if p.get("safety") else
                       T.BAD if p.get("directive") else T.ACCENT)
            T.text(surf, p["category"].upper(), (right.right - 24, y + 12), 11, col_cat,
                   bold=True, align="right")
            if p.get("safety") or p.get("directive"):
                T.text(surf, "in vigore da subito", (right.right - 24, y + 27), 10,
                       col_cat, align="right")
            stretta = 130 if (p.get("safety") or p.get("directive")) else 90
            T.paragraph(surf, p["desc"], (right.x + 24, y + 30), 12, T.DIM,
                        right.w - 48 - stretta)
            T.text(surf, f"Per noi: {item['verdict']}", (right.x + 24, y + 68), 13,
                   item["colour"], bold=True)
            T.text(surf, f"scuderie favorevoli stimate: {item['yes']}/{len(gs.teams)}",
                   (right.right - 24, y + 68), 12, T.DIM, align="right")
            y += 104
        for i, riga in enumerate((
                "Quello che passa entra in vigore dalla stagione successiva: a",
                "campionato in corso non si cambiano le carte. Fanno eccezione la",
                "sicurezza e le direttive tecniche dopo una violazione accertata,",
                "che valgono dal gran premio dopo.")):
            T.text(surf, riga, (right.x + 16, right.bottom - 84 + i * 17), 12, T.DIM_2,
                   maxw=right.w - 32)
        super().draw(surf)


class StandingsPage(Page):
    def build(self) -> None:
        self.widgets = []

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, gs = self.rect, self.gs
        left = pygame.Rect(r.x, r.y, r.w * 0.52, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, f"CAMPIONATO PILOTI {gs.season}", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        y = left.y + 40
        for i, d in enumerate(gs.driver_standings(), 1):
            t = gs.teams.get(d.team)
            col = T.hex_rgb(t.colour) if t else T.DIM_2
            hl = (t and t.id == gs.player_team)
            if hl:
                T.panel(surf, (left.x + 8, y - 2, left.w - 16, 26), T.PANEL_3, radius=6)
            T.text(surf, str(i), (left.x + 24, y + 2), 14, T.DIM, align="right")
            pygame.draw.rect(surf, col, (left.x + 34, y + 3, 3, 16))
            T.text(surf, d.name, (left.x + 46, y + 2), 14, T.TEXT, maxw=190)
            T.text(surf, t.short if t else "-", (left.x + 250, y + 3), 13, T.DIM, maxw=110)
            T.text(surf, f"{d.wins}", (left.x + 380, y + 2), 13, T.GOLD)
            T.text(surf, f"{d.podiums}", (left.x + 420, y + 2), 13, T.DIM)
            T.text(surf, f"{d.points:.0f}", (left.right - 16, y + 1), 15, T.TEXT, bold=True,
                   align="right")
            y += 27
        T.text(surf, "V  P", (left.x + 380, left.y + 22), 11, T.DIM_2, bold=True)

        right = pygame.Rect(r.x + r.w * 0.54, r.y, r.w * 0.46 - 4, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, f"CAMPIONATO COSTRUTTORI {gs.season}", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        y = right.y + 40
        maxp = max([t.points for t in gs.teams.values()] + [1])
        for i, t in enumerate(gs.constructor_standings(), 1):
            col = T.hex_rgb(t.colour)
            hl = (t.id == gs.player_team)
            if hl:
                T.panel(surf, (right.x + 8, y - 2, right.w - 16, 30), T.PANEL_3, radius=6)
            T.text(surf, str(i), (right.x + 26, y + 4), 14, T.DIM, align="right")
            pygame.draw.rect(surf, col, (right.x + 36, y + 4, 4, 18))
            T.text(surf, t.short, (right.x + 50, y + 4), 15, T.TEXT, bold=hl, maxw=150)
            T.bar(surf, (right.x + 210, y + 9, right.w - 300, 10), t.points, maxp, col)
            T.text(surf, f"{t.points:.0f}", (right.right - 16, y + 3), 15, T.TEXT, bold=True,
                   align="right")
            y += 32
        super().draw(surf)


class CalendarPage(Page):
    """Il calendario, e la scheda di ogni gran premio quando ci si clicca sopra."""

    COLS = 6
    CARD_H = 150
    # quanto si tiene l'intestazione: titolo, contratti in scadenza e cosa
    # chiedono le gare che restano, senza che si scrivano una sopra l'altra
    TOP = 46

    def __init__(self, shell):
        super().__init__(shell)
        self.sel = None            # circuito aperto

    def _griglia(self) -> list:
        """Dove finisce ogni scheda: serve al disegno e ai clic."""
        r = self.rect
        cw = (r.w - (self.COLS - 1) * 12) / self.COLS
        top = r.y + self.TOP
        out = []
        for i, t in enumerate(self.gs.tracks):
            x = r.x + (i % self.COLS) * (cw + 12)
            y = top + (i // self.COLS) * (self.CARD_H + 12)
            out.append((i, t, pygame.Rect(int(x), int(y), int(cw), self.CARD_H)))
        return out

    def build(self) -> None:
        self.widgets = []
        if self.sel is not None:
            r = self.rect
            self.widgets.append(Button((r.x, r.y, 200, 34), "< Torna al calendario",
                                       self.chiudi, "ghost"))
            return
        # ogni scheda del calendario e' un pulsante trasparente
        for i, t, rect in self._griglia():
            b = Button(rect, "", style="invisible")
            b.on_click = (lambda tr=t: self.apri(tr))
            self.widgets.append(b)

    def apri(self, track) -> None:
        self.sel = track
        self.build()

    def chiudi(self) -> None:
        self.sel = None
        self.build()

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        if self.sel is not None:
            _scheda_circuito(surf, self.rect, self.gs, self.sel)
            super().draw(surf)
            return
        r, gs = self.rect, self.gs
        rias = CAL.summary(gs)
        T.text(surf, f"{rias['gare']} GARE  -  {rias['canoni']:.0f} M$ DI CANONI ALL'ANNO",
               (r.x, r.y), 12, T.DIM_2, bold=True)
        if rias["in_scadenza"]:
            # sotto il titolo, non accanto: a destra c'e' gia' quello che
            # chiedono le gare rimaste, e le due scritte si pestavano
            nomi = ", ".join(t.name for t in rias["in_scadenza"][:3])
            T.paragraph(surf, f"in scadenza: {nomi}", (r.x, r.y + 17), 12, T.WARN,
                        int(r.w * 0.52))
        # cosa chiedono le gare che restano: e' li' che vanno mandati i soldi
        restanti = gs.tracks[gs.round:]
        if restanti:
            bias = engineering.calendar_bias(gs, restanti)
            prof = engineering.car_profile(gs.player, gs)
            top = sorted(bias.items(), key=lambda kv: -kv[1])[:3]
            testo = ", ".join(engineering.AREAS[a].lower() for a, _v in top)
            largo = int(r.w * 0.44)
            righe = T.wrap(f"le {len(restanti)} gare che restano chiedono: {testo}",
                           12, largo)
            for i, riga in enumerate(righe[:2]):
                T.text(surf, riga, (r.right - 16, r.y + i * 14), 12, T.GOLD, align="right")
            manca = [engineering.AREAS[a].lower() for a, _v in top if prof.get(a, 50) < 55]
            if manca:
                T.text(surf, "e noi siamo indietro su " + ", ".join(manca),
                       (r.right - 16, r.y + len(righe[:2]) * 14), 11, T.WARN,
                       align="right", maxw=largo)
        cols, ch = self.COLS, self.CARD_H
        top = r.y + self.TOP
        for i, t, rect in self._griglia():
            done = i < gs.round
            nxt = (i == gs.round)
            T.panel(surf, rect, T.PANEL_2 if nxt else T.PANEL, radius=10,
                    border=T.ACCENT if nxt else T.LINE, width=2 if nxt else 1)
            T.text(surf, f"{i+1:02d}", (rect.x + 12, rect.y + 8), 13, T.DIM_2, bold=True)
            T.text(surf, t.flag, (rect.right - 12, rect.y + 8), 13, T.ACCENT, bold=True,
                   align="right")
            if t.sprint:
                T.text(surf, "SPRINT", (rect.right - 12, rect.y + 24), 10, T.GOLD, bold=True,
                       align="right")
            trackdraw.draw_minimap(surf, t, (rect.x + 8, rect.y + 26, rect.w - 16, 70),
                                   colour=(52, 62, 82) if not done else (38, 46, 60), width=3)
            T.text(surf, t.name, (rect.x + 12, rect.bottom - 44), 12,
                   T.DIM if done else T.TEXT, maxw=rect.w - 88)
            T.text(surf, f"{t.length_km:.3f} km - {t.laps} giri",
                   (rect.x + 12, rect.bottom - 26), 11, T.DIM_2,
                   maxw=rect.w - 24 - (86 if done else 0))
            scade = getattr(t, "contract_until", 9999)
            resta = scade - gs.season
            col = T.BAD if resta <= 0 else (T.WARN if resta <= 1 else T.DIM_2)
            if getattr(t, "tradition", 0) >= 0.85:
                T.text(surf, "STORICO", (rect.x + 12, rect.y + 8 + 14), 10, T.GOLD, bold=True)
            T.text(surf, f"fino {scade}", (rect.right - 12, rect.bottom - 44), 11, col,
                   align="right")
            if done:
                res = next((rr for rr in gs.results
                            if rr.track_id == t.id and rr.season == gs.season and rr.kind == "gp"), None)
                if res and res.order:
                    win = gs.drivers.get(res.order[0]["driver"])
                    if win:
                        T.text(surf, f"1o {win.last}", (rect.right - 12, rect.bottom - 26), 11,
                               T.GOLD, bold=True, align="right")

        # chi aspetta un posto in calendario
        righe = (len(gs.tracks) + cols - 1) // cols
        cy = top + righe * (ch + 12) + 8
        if rias["candidati"] and cy < r.bottom - 60:
            T.text(surf, "CIRCUITI CHE PREMONO PER ENTRARE", (r.x, cy), 12, T.DIM_2, bold=True)
            cy += 22
            for j, t in enumerate(rias["candidati"][:8]):
                cx = r.x + (j % 4) * (r.w / 4)
                yy = cy + (j // 4) * 20
                T.text(surf, t.name, (cx, yy), 12, T.TEXT, maxw=r.w / 4 - 130)
                T.text(surf, f"{t.fee:.0f} M$", (cx + r.w / 4 - 120, yy), 12, T.GOLD)
                T.bar(surf, (cx + r.w / 4 - 70, yy + 4, 50, 7),
                      CAL.candidate_score(gs, t) * 100, 100, T.ACCENT)
        super().draw(surf)


# ------------------------------------------------------------ scheda circuito
TRATTI = [
    ("downforce", "Carico aerodinamico", "curve veloci e appoggio"),
    ("power", "Potenza", "rettilinei e allunghi"),
    ("braking", "Frenata", "staccate forti"),
    ("tyre_wear", "Consumo gomme", "asfalto e curve lunghe"),
    ("overtaking", "Possibilita' di sorpasso", "quanto si puo' fare in gara"),
    ("bumpiness", "Sconnessioni", "cordoli e asfalto"),
]


def _scheda_circuito(surf, r, gs, t) -> None:
    """Tutto quello che riguarda un gran premio, in una schermata sola."""
    giro = gs.tracks.index(t) + 1 if t in gs.tracks else 0
    corso = giro and giro <= gs.round

    # ------------------------------------------------------------- intestazione
    T.text(surf, t.gp.upper(), (r.x + 220, r.y), 24, T.TEXT, bold=True, maxw=r.w - 460)
    stato = ("gia' disputato" if corso else
             ("il prossimo appuntamento" if giro == gs.round + 1 else f"gara {giro}"))
    T.text(surf, f"{t.name}  -  {t.country}  -  {stato}", (r.x + 220, r.y + 28), 14, T.DIM)
    if t.sprint:
        T.text(surf, "WEEKEND SPRINT", (r.right - 16, r.y), 13, T.GOLD, bold=True, align="right")
    T.text(surf, f"contratto fino al {t.contract_until}  -  canone {t.fee:.0f} M$",
           (r.right - 16, r.y + 28), 13, T.DIM_2, align="right")

    # ------------------------------------------------------------- il tracciato
    sx = pygame.Rect(r.x, r.y + 56, r.w * 0.40, r.h * 0.52)
    T.panel(surf, sx, T.PANEL, radius=10, border=T.LINE)
    trackdraw.draw_track(surf, t, sx.inflate(-28, -108), width=9)
    # dove tagliano gli intertempi e da che parte si gira: sono i due dati con
    # cui si legge tutto il resto, dai distacchi alla posizione in pista
    a, b = t.sector_time
    verso = "in senso orario" if t.senso != "antiorario" else "in senso antiorario"
    T.text(surf, f"intertempi a {t.pos_at(a) * t.length_km:.2f} e "
                 f"{t.pos_at(b) * t.length_km:.2f} km dal traguardo, {verso}",
           (sx.x + 16, sx.bottom - 74), 12, T.DIM_2, maxw=sx.w - 32)
    T.text(surf, f"{t.length_km:.3f} km   -   {t.corners} curve   -   {t.laps} giri",
           (sx.x + 16, sx.bottom - 52), 14, T.TEXT, bold=True)
    giri = int(round(t.laps * gs.race_distance))
    T.text(surf, f"in questa carriera si corre su {giri} giri  ({gs.race_distance*100:.0f}%), "
                 f"perdita ai box {t.pit_loss:.1f} s",
           (sx.x + 16, sx.bottom - 30), 12, T.DIM, maxw=sx.w - 32)

    # -------------------------------------------------- cosa chiede alla macchina
    cx = pygame.Rect(sx.right + 14, r.y + 56, r.w * 0.28, r.h * 0.52)
    T.panel(surf, cx, T.PANEL, radius=10, border=T.LINE)
    T.text(surf, "COM'E' FATTO", (cx.x + 16, cx.y + 12), 12, T.DIM_2, bold=True)
    # non un aggettivo: i dati del giro. Quanto tempo si passa in ogni parte
    # del circuito, misurato facendoci girare la nostra macchina
    dati = engineering.grid_domains(gs, t).get(gs.player_team, {})
    domini = engineering.track_demand(gs, t)
    T.text(surf, f"{dati.get('pieno_gas', 0)*100:.0f}% a tutto gas",
           (cx.right - 16, cx.y + 12), 11, T.DIM_2, align="right")
    y = cx.y + 36
    for dom, quota in domini:
        T.text(surf, engineering.NOMI_DOMINIO[dom], (cx.x + 16, y), 12, T.DIM,
               maxw=cx.w - 150)
        T.bar(surf, (cx.right - 126, y + 4, 74, 8), quota * 100, 45, T.ACCENT)
        T.text(surf, f"{quota*100:.0f}%", (cx.right - 16, y), 12, T.DIM_2, align="right")
        y += 20
    curve = dati.get("curve") or []
    lente = sum(1 for c in curve if c["classe"] == "lente")
    veloci = sum(1 for c in curve if c["classe"] == "veloci")
    T.text(surf, f"{len(curve)} curve, {lente} lente e {veloci} veloci",
           (cx.x + 16, y + 6), 11, T.DIM_2, maxw=cx.w - 32)
    T.text(surf, f"{dati.get('frenate', 0)} staccate, punta {dati.get('vmax', 0):.0f} km/h",
           (cx.x + 16, y + 22), 11, T.DIM_2, maxw=cx.w - 32)
    y += 46

    T.text(surf, "DOVE PERDIAMO QUI", (cx.x + 16, y), 12, T.GOLD, bold=True)
    # quanto questa pista ci sta bene o male rispetto a tutte le altre del
    # calendario, e quanto vale in secondi
    from ...sim import pace as PACE
    sec = PACE.affinities(gs, t).get(gs.player_team, 0.0) * PACE.AFFINITA_S * t.ref_lap
    if abs(sec) < 0.03:
        frase, colf = "pista neutra per la nostra macchina", T.DIM
    elif sec > 0:
        frase, colf = f"qui ci troviamo bene: {sec:.2f} s al giro", T.OK
    else:
        frase, colf = f"qui perdiamo {-sec:.2f} s al giro", T.BAD
    y += 20
    T.text(surf, frase, (cx.x + 16, y), 12, colf, bold=True, maxw=cx.w - 32)
    y += 20
    # e il conto vero: in che parte del giro lasciamo secondi ai migliori
    stand = engineering.domain_standing(gs, t)
    peggio = sorted(stand.items(), key=lambda kv: -kv[1]["gap"])[:4]
    for dom, d in peggio:
        col = T.BAD if d["gap"] > 0.15 else (T.WARN if d["gap"] > 0.05 else T.OK)
        T.text(surf, engineering.NOMI_DOMINIO[dom], (cx.x + 16, y), 12,
               T.TEXT if d["gap"] > 0.05 else T.DIM, maxw=cx.w - 130)
        T.text(surf, f"{d['gap']:+.2f} s", (cx.right - 16, y), 12, col, bold=True,
               align="right")
        y += 19

    # ------------------------------------------------------ il gran premio di quest'anno
    dx = pygame.Rect(cx.right + 14, r.y + 56, r.right - cx.right - 14, r.h * 0.52)
    T.panel(surf, dx, T.PANEL, radius=10, border=T.LINE)
    res = next((x for x in gs.results if x.track_id == t.id and x.season == gs.season
                and x.kind == "gp"), None)
    if res:
        T.text(surf, f"GRAN PREMIO {gs.season}", (dx.x + 16, dx.y + 12), 12, T.DIM_2, bold=True)
        T.text(surf, res.weather, (dx.right - 16, dx.y + 12), 12, T.DIM, align="right")
        y = dx.y + 38
        for riga in res.order[:10]:
            d = gs.drivers.get(riga["driver"])
            sq = gs.teams.get(riga["team"])
            if not d:
                continue
            col = T.hex_rgb(sq.colour) if sq else T.DIM
            T.text(surf, f"{riga['pos']}", (dx.x + 16, y), 12, T.DIM)
            pygame.draw.rect(surf, col, (dx.x + 40, y + 3, 3, 12))
            T.text(surf, d.short, (dx.x + 50, y), 13,
                   T.TEXT if riga["status"] == "finished" else T.BAD, maxw=dx.w * 0.42)
            T.text(surf, sq.short if sq else "", (dx.x + dx.w * 0.55, y), 12, T.DIM,
                   maxw=dx.w * 0.24)
            if riga["status"] != "finished":
                T.text(surf, riga.get("reason") or "ritirato", (dx.right - 16, y), 11,
                       T.BAD, align="right", maxw=dx.w * 0.2)
            else:
                T.text(surf, f"{riga['points']:.0f}" if riga["points"] else "",
                       (dx.right - 16, y), 12, T.GOLD, align="right")
            y += 19
        pole = gs.drivers.get(res.pole)
        vel = gs.drivers.get(res.fastest_lap)
        y += 6
        if pole:
            T.text(surf, f"pole {pole.short}", (dx.x + 16, y), 12, T.ACCENT)
        if vel:
            T.text(surf, f"giro veloce {vel.short}", (dx.x + dx.w * 0.5, y), 12, T.ACCENT)
        # il sabato conta anche lui: dove c'e' stata la sprint si vede chi ha vinto
        spr = next((x for x in gs.results if x.track_id == t.id and x.season == gs.season
                    and x.kind == "sprint"), None)
        if spr and spr.order:
            primi = []
            for riga in spr.order[:3]:
                d = gs.drivers.get(riga["driver"])
                if d:
                    primi.append(f"{riga['pos']}o {d.code}")
            T.text(surf, "sprint   " + "   ".join(primi), (dx.x + 16, y + 20), 12, T.GOLD,
                   maxw=dx.w - 32)
    else:
        T.text(surf, "GRAN PREMIO NON ANCORA DISPUTATO", (dx.x + 16, dx.y + 12), 12,
               T.DIM_2, bold=True)
        mancano = giro - gs.round
        T.text(surf, (f"manca {mancano} gara" if mancano == 1 else f"mancano {mancano} gare")
               if mancano > 0 else "in programma",
               (dx.x + 16, dx.y + 40), 15, T.TEXT)
        sap = None
        try:
            from ...core import testing as TT
            sap = TT.setup_bonus(gs.player, t)
        except Exception:
            sap = None
        if sap is not None:
            T.text(surf, f"conoscenza del circuito: {sap*100:.0f}%",
                   (dx.x + 16, dx.y + 66), 13, T.OK if sap > 0.2 else T.DIM)
            T.text(surf, "si alza girandoci nei test privati: al ritorno in gara si parte "
                         "gia' vicini alla finestra d'assetto.",
                   (dx.x + 16, dx.y + 86), 12, T.DIM_2, maxw=dx.w - 32)

    # ------------------------------------------------------------------ albo d'oro
    bassa = pygame.Rect(r.x, r.y + 56 + r.h * 0.52 + 14, r.w, r.bottom - (r.y + 56 + r.h * 0.52 + 14))
    T.panel(surf, bassa, T.PANEL, radius=10, border=T.LINE)
    T.text(surf, "ALBO D'ORO", (bassa.x + 16, bassa.y + 12), 12, T.GOLD, bold=True)
    storia = list(gs.track_history.get(t.id, []))
    if not storia:
        T.text(surf, "Nessuna edizione ancora disputata in questa carriera: l'albo si "
                     "riempie gara dopo gara.", (bassa.x + 16, bassa.y + 40), 14, T.DIM)
    else:
        T.text(surf, "STAGIONE", (bassa.x + 16, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "VINCITORE", (bassa.x + 110, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "SQUADRA", (bassa.x + 340, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "POLE", (bassa.x + 470, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "TEMPO", (bassa.x + 700, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "GIRO VELOCE", (bassa.x + 800, bassa.y + 36), 11, T.DIM_2, bold=True)
        T.text(surf, "METEO", (bassa.x + 1010, bassa.y + 36), 11, T.DIM_2, bold=True)
        y = bassa.y + 56
        for riga in storia:
            if y > bassa.bottom - 20:
                break
            T.text(surf, str(riga["season"]), (bassa.x + 16, y), 13, T.TEXT, bold=True)
            T.text(surf, riga.get("vincitore", ""), (bassa.x + 110, y), 13, T.GOLD,
                   maxw=220)
            T.text(surf, riga.get("squadra", ""), (bassa.x + 340, y), 13, T.DIM, maxw=120)
            T.text(surf, riga.get("pole", ""), (bassa.x + 470, y), 13, T.TEXT, maxw=220)
            tp = riga.get("tempo_pole") or 0
            T.text(surf, _mmss(tp) if tp else "-", (bassa.x + 700, y), 13, T.ACCENT)
            T.text(surf, riga.get("giro_veloce", ""), (bassa.x + 800, y), 13, T.DIM, maxw=200)
            T.text(surf, riga.get("meteo", ""), (bassa.x + 1010, y), 12, T.DIM_2, maxw=140)
            y += 20
        vinte = {}
        for riga in storia:
            vinte[riga.get("vincitore", "")] = vinte.get(riga.get("vincitore", ""), 0) + 1
        re_pista = max(vinte.items(), key=lambda kv: kv[1]) if vinte else None
        if re_pista and re_pista[1] > 1:
            T.text(surf, f"Il re di questa pista e' {re_pista[0]}, con {re_pista[1]} vittorie.",
                   (bassa.right - 16, bassa.y + 12), 13, T.GOLD, bold=True, align="right")


def _mmss(sec: float) -> str:
    if not sec:
        return "-"
    m = int(sec // 60)
    return f"{m}:{sec - m*60:06.3f}" if m else f"{sec:.3f}"


class HistoryPage(Page):
    def build(self) -> None:
        self.widgets = []

    def refresh(self) -> None:
        self.build()

    def draw(self, surf) -> None:
        r, gs = self.rect, self.gs
        left = pygame.Rect(r.x, r.y, r.w * 0.55, r.h)
        T.panel(surf, left, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "CICLI TECNICI DELLA FORMULA 1", (left.x + 16, left.y + 12), 12,
               T.DIM_2, bold=True)
        y = left.y + 40
        for era in gs.history_data.get("eras", []):
            cur = era["from"] <= gs.season <= era["to"]
            if cur:
                T.panel(surf, (left.x + 8, y - 4, left.w - 16, 40), T.PANEL_3, radius=6)
            T.text(surf, f"{era['from']}-{era['to']}", (left.x + 20, y), 13,
                   T.ACCENT if cur else T.DIM, bold=True)
            T.text(surf, era["label"], (left.x + 110, y), 14, T.TEXT if cur else T.DIM,
                   bold=cur, maxw=left.w - 240)
            T.text(surf, f"reset {era['reset_strength']:.2f}", (left.right - 16, y), 12,
                   T.WARN, align="right")
            if era["dominant"]:
                T.text(surf, "dominio: " + ", ".join(era["dominant"]), (left.x + 110, y + 17),
                       11, T.DIM_2, maxw=left.w - 140)
            y += 40
        y += 10
        T.text(surf, "LEZIONI DALLA STORIA", (left.x + 16, y), 12, T.DIM_2, bold=True)
        y += 22
        for ln in gs.history_data.get("lessons", []):
            y += T.paragraph(surf, "- " + ln, (left.x + 16, y), 13, T.DIM,
                             left.w - 32) + 6

        right = pygame.Rect(r.x + r.w * 0.57, r.y, r.w * 0.43 - 4, r.h)
        T.panel(surf, right, T.PANEL, radius=10, border=T.LINE)
        T.text(surf, "ALBO D'ORO DELLA TUA CARRIERA", (right.x + 16, right.y + 12), 12,
               T.DIM_2, bold=True)
        y = right.y + 44
        if not gs.season_history:
            T.text(surf, "Nessuna stagione completata.", (right.x + 16, y), 13, T.DIM)
        for h in reversed(gs.season_history):
            T.text(surf, str(h["season"]), (right.x + 16, y), 15, T.GOLD, bold=True)
            T.text(surf, h["driver_champion"], (right.x + 76, y), 14, T.TEXT, maxw=180)
            T.text(surf, h["constructor_champion"], (right.right - 16, y), 13, T.DIM,
                   align="right")
            y += 26
        y += 20
        team = gs.player
        T.text(surf, "TITOLI DELLA SCUDERIA", (right.x + 16, y), 12, T.DIM_2, bold=True)
        y += 24
        T.text(surf, f"Mondiali piloti: {team.titles.get('drivers', 0)}", (right.x + 16, y), 14, T.TEXT)
        y += 22
        T.text(surf, f"Mondiali costruttori: {team.titles.get('constructors', 0)}",
               (right.x + 16, y), 14, T.TEXT)
        y += 22
        T.text(surf, f"Fondata nel {team.founded} - {team.base}", (right.x + 16, y), 13, T.DIM)
        super().draw(surf)
