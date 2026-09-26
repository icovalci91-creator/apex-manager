"""Schermata principale del gioco: barra superiore, navigazione e pagine."""
from __future__ import annotations

import pygame

from ... import storage
from ...core import economy, season as SEASON
from .. import fx
from .. import icons as I
from .. import theme as T
from ..app import Scene
from ..widgets import Button, ScrollList

# Le sezioni del gioco: sette voci nella barra, e dentro ognuna le sue
# schede. Erano diciotto voci in fila, con i nomi tagliati a meta': adesso
# si sceglie prima dove andare - la macchina, i piloti, i soldi - e poi cosa
# guardare, dalle schede in cima alla pagina.
# (id, etichetta, icona, [(pagina, scheda), ...])
SEZIONI = [
    ("home",       "Home",       "hq",        [("hq", "Quartier generale")]),
    ("vettura",    "Vettura",    "car",       [("car", "Assetto e pezzi"),
                                               ("dev", "Sviluppo"),
                                               ("powerunit", "Power unit"),
                                               ("testing", "Test privati")]),
    ("piloti",     "Piloti",     "drivers",   [("drivers", "Piloti e mercato"),
                                               ("academy", "Vivaio")]),
    ("staff",      "Staff",      "staff",     [("staff", "Staff tecnico"),
                                               ("engineers", "Ingegneri"),
                                               ("workforce", "Organico reparti")]),
    ("societa",    "Societa'",   "finance",   [("finance", "Finanze e sponsor"),
                                               ("facilities", "Infrastrutture")]),
    ("programmi",  "Programmi",  "formulae",  [("formulae", "Formula E"),
                                               ("wec", "Endurance")]),
    ("campionato", "Campionato", "standings", [("standings", "Classifiche"),
                                               ("calendar", "Calendario"),
                                               ("history", "Storico"),
                                               ("rules", "Regolamento")]),
]
# ogni pagina, con la sua sezione: (id, scheda, icona, sezione)
NAV = [(pid, scheda, pid, nome) for _sid, nome, _ic, schede in SEZIONI
       for pid, scheda in schede]


def sezione_di(pid: str):
    for sez in SEZIONI:
        if any(p == pid for p, _l in sez[3]):
            return sez
    return SEZIONI[0]


TOPBAR_H = 76
# L'intestazione di ogni pagina: la sezione sopra, il nome grande, una riga
# che dice a cosa serve. Sotto, le schede della sezione: e' quella che fa
# sapere dove si e' senza guardare la barra a sinistra.
TESTA_H = 70
SCHEDE_H = 50
DESCRIZIONI = {
    "hq": "La squadra a colpo d'occhio: soldi, macchina, piloti, prossima gara",
    "car": "I pezzi, le prestazioni e l'assetto per il prossimo weekend",
    "dev": "Galleria, CFD e pacchetti: dove si trova il tempo",
    "powerunit": "Il motore: banco, omologazioni e cosa arriva in pista",
    "engineers": "Chi progetta, chi decide e chi fa girare la fabbrica",
    "testing": "Giornate in pista fuori dai weekend, finche' ce ne sono",
    "drivers": "I titolari, le riserve e chi si puo' prendere",
    "academy": "I ragazzi del vivaio e le categorie in cui corrono",
    "staff": "Direttore tecnico, capi reparto e ingegneri di pista",
    "workforce": "Quanta gente lavora in ogni reparto, e quanto costa",
    "formulae": "Il programma elettrico: squadra, piloti e campionato",
    "wec": "L'endurance: la Hypercar e le otto tappe dell'anno",
    "finance": "Entrate, uscite, sponsor e il tetto di spesa",
    "facilities": "Galleria, simulatore, fabbrica: la base su cui si costruisce",
    "rules": "Il regolamento in vigore e quello che si vota in Commissione",
    "standings": "Il mondiale piloti e costruttori, gara dopo gara",
    "calendar": "Le gare dell'anno, di Formula 1, Formula E ed endurance",
    "history": "Gli albi d'oro e le stagioni passate",
}
NAV_W = 212
NAV_ROW_H = 60
# Quanto dura la dissolvenza quando si cambia pagina. Poco: serve a dire "sei
# in un altro posto", non a farsi guardare.
DISSOLVENZA = 0.16


class Page:
    """Base per le pagine del gestionale.

    Una pagina puo' avere piu' roba di quanta ne stia nello schermo: su un
    portatile la finestra e' 1180x680, e le stesse pagine che a 1600x900 ci
    stavano comode finiscono sotto il bordo. Invece di riscrivere ogni
    schermata si sposta il foglio: la pagina viene costruita e disegnata a
    partire da un rettangolo alzato di `scroll`, cosi' quello che si disegna e
    quello che risponde al mouse restano la stessa cosa senza che le pagine
    debbano saperne niente.

    Chi disegna dice quanto spazio ha usato davvero scrivendo `content_h` alla
    fine del proprio `draw`; chi non lo scrive non scorre, come prima.
    """

    def __init__(self, shell):
        self.shell = shell
        self.app = shell.app
        self.widgets: list = []
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.view = pygame.Rect(0, 0, 10, 10)   # quello che si vede davvero
        self.scroll = 0.0
        self.content_h = 0                       # 0 = non lo sa: niente scorrimento

    @property
    def gs(self):
        return self.app.gs

    @property
    def team(self):
        return self.app.gs.player

    @property
    def scroll_max(self) -> float:
        if not self.content_h:
            return 0.0
        return max(0.0, self.content_h - self.view.h)

    def layout(self, rect) -> None:
        self.view = pygame.Rect(rect)
        self.scroll = min(self.scroll, self.scroll_max)
        self.rect = self.view.move(0, -int(self.scroll))
        self.build()

    def set_scroll(self, valore: float) -> None:
        valore = max(0.0, min(self.scroll_max, valore))
        if abs(valore - self.scroll) < 0.5:
            return
        self.scroll = valore
        self.rect = self.view.move(0, -int(self.scroll))
        self.build()

    def build(self) -> None:
        pass

    def handle(self, ev) -> None:
        # quello che e' scorso fuori dalla finestra non si vede e non si clicca:
        # senza questo, un cursore finito sotto la barra in alto rispondeva
        # ancora al mouse
        if hasattr(ev, "pos") and not self.view.collidepoint(ev.pos):
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                for w in self.widgets:
                    if hasattr(w, "drag") or hasattr(w, "pressed"):
                        w.handle(ev)          # un trascinamento si chiude ovunque
                self._presa = None
                return
        for w in self.widgets:
            if w.handle(ev):
                return
        # nessun widget se l'e' presa: se la pagina sfora, si scorre
        if self.scroll_max <= 0:
            return
        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.view.collidepoint(mx, my):
                self.set_scroll(self.scroll - ev.y * 60)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.view.collidepoint(ev.pos):
                self._presa = ev.pos[1]
                self._presa_scroll = self.scroll
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._presa = None
        elif ev.type == pygame.MOUSEMOTION and getattr(self, "_presa", None) is not None:
            self.set_scroll(self._presa_scroll - (ev.pos[1] - self._presa))

    def update(self, dt: float) -> None:
        # serve ai pulsantini dei cursori, che tenuti premuti ripetono
        for w in self.widgets:
            w.update(dt)

    def draw(self, surf) -> None:
        for w in self.widgets:
            w.draw(surf)

    def refresh(self) -> None:
        self.build()


class GameShell(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.page_id = "hq"
        self.ultima: dict = {}      # l'ultima scheda aperta di ogni sezione
        self.entrata = 0.0          # quanto manca alla fine della dissolvenza
        self.pages: dict = {}
        self.rail: ScrollList | None = None
        self._make_pages()
        self.build()

    # -------------------------------------------------------------- costruzione
    def _make_pages(self) -> None:
        from ..pages import (academy_page, core_pages, finance_pages, formulae_page,
                             people_pages, testing_page, wec_page, workforce_page,
                             world_pages)
        self.pages = {
            "hq": core_pages.HQPage(self),
            "car": core_pages.CarPage(self),
            "dev": core_pages.DevPage(self),
            "powerunit": core_pages.PowerUnitPage(self),
            "engineers": core_pages.EngineersPage(self),
            "testing": testing_page.TestingPage(self),
            "drivers": people_pages.DriversPage(self),
            "academy": academy_page.AcademyPage(self),
            "formulae": formulae_page.FormulaEPage(self),
            "wec": wec_page.WecPage(self),
            "staff": people_pages.StaffPage(self),
            "workforce": workforce_page.WorkforcePage(self),
            "finance": finance_pages.FinancePage(self),
            "facilities": world_pages.FacilitiesPage(self),
            "rules": world_pages.RulesPage(self),
            "standings": world_pages.StandingsPage(self),
            "calendar": world_pages.CalendarPage(self),
            "history": world_pages.HistoryPage(self),
        }

    def build(self) -> None:
        w, h = self.app.screen.get_size()
        self.widgets = []
        editor = bool(getattr(self.app, "editor", False))
        save_y = h - 56                     # la riga Salva/Menu sta in fondo
        editor_y = save_y - 44
        race_y = (editor_y if editor else save_y) - 14 - 56
        rail_y = TOPBAR_H + 14
        rail_rect = (10, rail_y, NAV_W - 20, max(NAV_ROW_H, (race_y - 12) - rail_y))
        self.rail = ScrollList(rail_rect, row_h=NAV_ROW_H, draw_row=self._riga_nav,
                               on_select=self._scegli_nav)
        self.rail.items = SEZIONI
        self.rail.selected = SEZIONI.index(sezione_di(self.page_id))
        self.widgets.append(self.rail)
        self.race_btn = Button((14, race_y, NAV_W - 28, 56), "PROSSIMO EVENTO",
                               self.goto_weekend, "primary")
        self.widgets.append(self.race_btn)
        if editor:
            self.widgets.append(Button((14, editor_y, NAV_W - 28, 34), "EDITOR",
                                       self.open_editor, "danger"))
        mezzo = (NAV_W - 36) // 2
        self.widgets.append(Button((14, save_y, mezzo, 40), "Salva", self.save, "ghost"))
        self.widgets.append(Button((22 + mezzo, save_y, mezzo, 40), "Menu", self.to_menu,
                                   "ghost"))
        # le schede della sezione aperta, sotto l'intestazione
        self.schede = []
        sez = sezione_di(self.page_id)
        if len(sez[3]) > 1:
            x = NAV_W + 24
            for pid, etichetta in sez[3]:
                larga = T.width(etichetta, 16, True) + 44
                b = Button((x, TOPBAR_H + TESTA_H + 4, larga, 38), etichetta,
                           (lambda p=pid: self.go(p)), "tab")
                b.active = pid == self.page_id
                b.style = "tab" if b.active else "ghost"
                self.schede.append(b)
                self.widgets.append(b)
                x += larga + 8
        for pid, p in self.pages.items():
            p.layout(self._area(pid).inflate(-40, -28))

    def _id_di(self, pagina) -> str:
        return next(k for k, v in self.pages.items() if v is pagina)

    def _area(self, pid: str) -> pygame.Rect:
        """Dove si disegna una pagina: sotto l'intestazione e, se la sua
        sezione ne ha, sotto le schede."""
        w, h = self.app.screen.get_size()
        sopra = TOPBAR_H + TESTA_H + (SCHEDE_H if len(sezione_di(pid)[3]) > 1 else 0)
        return pygame.Rect(NAV_W, sopra, w - NAV_W, h - sopra)

    def on_resize(self) -> None:
        self.build()

    def _riga_nav(self, surf, rect, i: int, item) -> None:
        """Una voce della barra: l'icona e il nome della sezione, grandi."""
        sid, label, icon_name, schede = item
        attivo = sezione_di(self.page_id)[0] == sid
        colore = T.WHITE if attivo else T.TEXT
        corpo = rect.inflate(0, -6)
        sopra = corpo.collidepoint(pygame.mouse.get_pos()) and not attivo
        h = fx.verso(("nav", sid), 1.0 if sopra else 0.0, 14.0)
        if attivo:
            fx.splendi(surf, (corpo.x + 20, corpo.centery), 60, T.squadra_viva(), 0.22)
            T.panel(surf, corpo, T.mix(T.PANEL_2, T.squadra(), 0.45), radius=16,
                    rilievo=False, border=T.mix(T.squadra_viva(), T.WHITE, 0.2))
        elif h > 0.02:
            T.panel(surf, corpo, T.mix(T.PANEL, T.PANEL_3, h), radius=16, rilievo=False)
            colore = T.mix(T.TEXT, T.WHITE, h)
        icona = pygame.Rect(0, 0, 24, 24)
        icona.center = (corpo.x + 28, corpo.centery)
        I.draw(surf, icon_name, icona, colore, 2)
        T.text(surf, label, (icona.right + 14, corpo.centery - 13), 19, colore,
               bold=True, maxw=corpo.right - icona.right - 20)

    def _scegli_nav(self, i: int, item) -> None:
        sid = item[0]
        # si torna all'ultima scheda aperta di quella sezione
        self.go(self.ultima.get(sid, item[3][0][0]))

    # ------------------------------------------------------------------ azioni
    def go(self, pid: str) -> None:
        # cambiare pagina non e' un taglio di montaggio: la nuova entra con una
        # dissolvenza di un decimo e mezzo di secondo, che e' abbastanza da far
        # capire che si e' cambiato posto e abbastanza poco da non far
        # aspettare nessuno. Solo se si cambia davvero pagina
        if pid not in self.pages:
            return
        cambia_sezione = sezione_di(pid) is not sezione_di(self.page_id)
        if pid != self.page_id:
            self.entrata = DISSOLVENZA
            fx.entra()
        self.page_id = pid
        self.ultima[sezione_di(pid)[0]] = pid
        if cambia_sezione or not getattr(self, "schede", None):
            self.build()
        else:
            for b in self.schede:
                b.active = b.label == dict(sezione_di(pid)[3])[pid]
                b.style = "tab" if b.active else "ghost"
        if self.rail is not None:
            self.rail.selected = SEZIONI.index(sezione_di(pid))
        self.pages[pid].refresh()

    def goto_weekend(self) -> None:
        gs = self.app.gs
        evento = SEASON.prossimo_evento(gs)
        if evento is None:
            from .offseason import OffseasonScene
            self.app.push(OffseasonScene(self.app))
            return
        serie = evento["serie"]
        if serie == "fe":
            from .eprix import EPrixScene
            self.app.push(EPrixScene(self.app, evento["pista"], evento["formato"]))
            return
        if serie == "wec":
            # niente scena: l'endurance non si guida, e otto tappe l'anno si
            # possono raccontare con un messaggio invece che con un weekend
            from ...core import wec as WEC
            self.app.toast(WEC.avanza(gs))
            self.enter()
            return
        from .weekend import WeekendScene
        # se il weekend e' gia' cominciato si riprende quello: uscire a
        # sistemare l'assetto non deve rimandare tutti a casa il venerdi'
        aperto = getattr(self.app, "weekend", None)
        if (isinstance(aperto, WeekendScene) and aperto.gs is gs
                and aperto.track is gs.next_track and aperto.stage != "fine"):
            self.app.push(aperto)
            return
        self.app.push(WeekendScene(self.app))

    def save(self) -> None:
        gs = self.app.gs
        try:
            where = storage.write_save(f"{gs.player_team}_{gs.season}", gs.to_dict())
        except Exception as exc:
            self.app.toast(f"Salvataggio non riuscito: {exc}")
            return
        self.app.toast(f"Partita salvata: {where}")

    def to_menu(self) -> None:
        """Apre il menu sopra la partita: nuova, salva, carica, editor."""
        from .gamemenu import GameMenuScene
        self.app.push(GameMenuScene(self.app))

    def open_editor(self) -> None:
        from .editor import EditorScene
        self.app.push(EditorScene(self.app))

    # ------------------------------------------------------------------- loop
    def enter(self) -> None:
        ev = SEASON.evento_display(self.app.gs)
        if ev is None:
            self.race_btn.label = "FINE STAGIONE"
        else:
            self.race_btn.label = f"{ev['sigla']}: {ev['flag']}"
        self.pages[self.page_id].refresh()

    def handle(self, ev) -> None:
        self.pages[self.page_id].handle(ev)
        super().handle(ev)

    def update(self, dt: float) -> None:
        self.entrata = max(0.0, self.entrata - dt)
        self.pages[self.page_id].update(dt)

    def draw(self, surf) -> None:
        w, h = surf.get_size()
        gs = self.app.gs
        team = gs.player
        col = T.hex_rgb(team.colour)
        T.set_squadra(col)
        vivo = T.squadra_viva()

        # barra laterale: vetro scuro sopra allo sfondo, che si vede appena
        lato = pygame.Surface((NAV_W, h - TOPBAR_H), pygame.SRCALPHA)
        lato.fill((*T.PANEL, 235))
        surf.blit(lato, (0, TOPBAR_H))
        pygame.draw.line(surf, T.LINE, (NAV_W, TOPBAR_H), (NAV_W, h))

        # Barra superiore: il blocco del nome nel colore della squadra, poi i
        # numeri che contano, ognuno nella sua pillola.
        T.panel(surf, (0, 0, w, TOPBAR_H), T.PANEL_2, radius=0)
        blocco = pygame.Surface((NAV_W, TOPBAR_H))
        for x in range(NAV_W):
            blocco.fill(T.mix(T.mix(T.PANEL_2, col, 0.38), T.PANEL_2, x / NAV_W),
                        (x, 0, 1, TOPBAR_H))
        surf.blit(blocco, (0, 0))
        fx.splendi(surf, (30, TOPBAR_H // 2), 130, col, 0.18)
        T.text(surf, team.short.upper(), (22, 12), 24, vivo, bold=True, maxw=NAV_W - 30)
        T.text(surf, f"Stagione {gs.season}", (22, 44), 14, T.DIM)

        spent, limit, frac = economy.cap_usage(gs, team)
        pos = gs.position_of(team.id)
        ev = SEASON.evento_display(gs)
        kpi = [
            ("Liquidita'", T.fmt_money(team.cash), T.OK if team.cash > 5 else T.BAD, 170),
            ("Budget cap", f"{spent:.1f} / {limit:.0f} M$",
             T.BAD if frac > 1.0 else (T.WARN if frac > 0.85 else T.TEXT), 196),
            ("Costruttori", f"{pos}o  -  {team.points:.0f} pt", T.TEXT, 170),
        ]
        if ev:
            kpi.append((f"{ev['sigla']} {ev['conta']}", ev["titolo"], T.TEXT, 320))
        else:
            kpi.append(("Stagione", "conclusa", T.WARN, 170))
        x = NAV_W + 18
        for label, value, colour, largo in kpi:
            if x + largo > w - 16:
                break
            _kv(surf, x, largo, label, value, colour)
            x += largo + 12
        drs = gs.drivers_of(team.id)
        if drs and w - 16 - x >= 240:
            names = "   ".join(f"{d.last} {d.points:.0f}" for d in drs)
            largo = min(360, w - 16 - x)
            _kv(surf, w - 16 - largo, largo, "Piloti  -  punti", names, T.TEXT)
        pygame.draw.rect(surf, col, (0, TOPBAR_H - 3, w, 3))
        surf.blit(fx.striscia_luce(w, 14, col, 0.30), (0, TOPBAR_H - 9),
                  special_flags=pygame.BLEND_RGB_ADD)

        self._testata(surf, w)
        pagina = self.pages[self.page_id]
        prev = surf.get_clip()
        vista = self._area(self.page_id)
        vista.x += 1
        vista.w -= 1
        surf.set_clip(vista.clip(prev) if prev else vista)
        T.ink_start()
        pagina.draw(surf)
        fondo = T.ink_stop()
        if self.entrata > 0.0:
            velo = pygame.Surface(vista.size, pygame.SRCALPHA)
            velo.fill((*T.BG, int(210 * min(1.0, self.entrata / DISSOLVENZA))))
            surf.blit(velo, vista.topleft)
        for wd in pagina.widgets:
            if wd.visible:
                fondo = max(fondo, wd.rect.bottom)
        # si misura dall'origine del foglio, non da quella della finestra: se
        # no, appena si scorre l'altezza sembra rimpicciolita e lo scorrimento
        # si mangia da solo
        pagina.content_h = max(pagina.view.h, fondo - pagina.rect.y + 8)
        surf.set_clip(prev)
        if pagina.scroll_max > 0:
            v = pagina.view
            alt = max(30, int(v.h * v.h / max(1.0, pagina.content_h)))
            y = v.y + int((v.h - alt) * pagina.scroll / pagina.scroll_max)
            pygame.draw.rect(surf, T.PANEL_3, (w - 10, y, 5, alt), border_radius=3)
        super().draw(surf)

    def _testata(self, surf, w: int) -> None:
        """L'intestazione della pagina aperta: la sezione in piccolo, il nome
        della scheda in grande, a destra a cosa serve. Quando si cambia pagina
        il nome entra da sinistra."""
        sez = sezione_di(self.page_id)
        nome = dict(sez[3]).get(self.page_id, sez[1])
        vivo = T.squadra_viva()
        col = T.squadra()
        q = fx.entrata()
        r = pygame.Rect(NAV_W + 24, TOPBAR_H + 12, w - NAV_W - 48, TESTA_H - 16)
        badge = pygame.Rect(r.x, r.y + 2, 48, 48)
        fx.splendi(surf, badge.center, 48, col, 0.22 * q)
        T.panel(surf, badge, T.mix(T.PANEL_2, col, 0.35), radius=16, rilievo=False,
                border=T.mix(T.LINE, vivo, 0.6))
        I.draw(surf, self.page_id, badge.inflate(-20, -20), T.WHITE, 2)
        x = badge.right + 16 - int(24 * (1.0 - q))
        sopra = T.render(sez[1].upper(), 12, vivo, bold=True)
        sopra.set_alpha(int(255 * q))
        surf.blit(sopra, (x, r.y))
        titolo = T.render(nome, 32, T.TEXT, bold=True)
        titolo.set_alpha(int(255 * q))
        surf.blit(titolo, (x, r.y + 16))
        desc = DESCRIZIONI.get(self.page_id, "")
        spazio = r.right - (x + titolo.get_width() + 40)
        if desc and spazio > 160:
            T.text(surf, desc, (r.right, r.y + 22), 15, T.DIM, align="right", maxw=spazio)


def _kv(surf, x: int, w: int, label: str, value: str, colour=T.TEXT) -> None:
    """Un numero della barra superiore, nella sua pillola: l'etichetta
    piccola sopra, il valore grande sotto."""
    r = pygame.Rect(x, 10, w, TOPBAR_H - 22)
    T.panel(surf, r, T.PANEL_3, radius=16, rilievo=False)
    inner = w - 28
    T.text(surf, label, (x + 14, 15), 11, T.DIM, bold=True, maxw=inner)
    value = fx.rotola_testo(("kv", label), value, da_zero=False)
    T.text(surf, value, (x + 14, 31), 18, colour, bold=True, maxw=inner)
