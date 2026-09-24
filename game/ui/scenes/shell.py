"""Schermata principale del gioco: barra superiore, navigazione e pagine."""
from __future__ import annotations

import math

import pygame

from ... import storage
from ...core import economy, season as SEASON
from .. import fx
from .. import icons as I
from .. import theme as T
from ..app import Scene
from ..widgets import Button, ScrollList

# (id, etichetta, icona, gruppo). Il gruppo decide dove finisce una voce
# nella barra - non e' decorazione, e' la mappa che dice "questo e' un
# programma, quello e' gestione" - e la prima voce di ogni gruppo si
# riconosce anche disegnata, con l'etichetta del gruppo sopra.
NAV = [
    ("hq",         "Quartier Generale", "hq",         "SQUADRA"),
    ("car",        "Vettura e assetto", "car",        "SQUADRA"),
    ("dev",        "Sviluppo",          "dev",        "SQUADRA"),
    ("powerunit",  "Power unit",        "powerunit",  "SQUADRA"),
    ("engineers",  "Ingegneri",         "engineers",  "SQUADRA"),
    ("testing",    "Test privati",      "testing",    "SQUADRA"),
    ("drivers",    "Piloti e mercato",  "drivers",    "PERSONE"),
    ("academy",    "Vivaio",            "academy",    "PERSONE"),
    ("staff",      "Staff tecnico",     "staff",      "PERSONE"),
    ("workforce",  "Organico reparti",  "workforce",  "PERSONE"),
    ("formulae",   "Formula E",         "formulae",   "PROGRAMMI"),
    ("wec",        "Endurance",         "wec",        "PROGRAMMI"),
    ("finance",    "Finanze e sponsor", "finance",    "GESTIONE"),
    ("facilities", "Infrastrutture",    "facilities", "GESTIONE"),
    ("rules",      "Regolamento",       "rules",      "GESTIONE"),
    ("standings",  "Classifiche",       "standings",  "MONDO"),
    ("calendar",   "Calendario",        "calendar",   "MONDO"),
    ("history",    "Storico",           "history",    "MONDO"),
]

TOPBAR_H = 80
# L'intestazione di ogni pagina: il nome grande, la famiglia sopra, una riga
# che dice a cosa serve. E' quella che fa sapere dove si e' senza guardare la
# barra a sinistra, come il sottopancia di una grafica televisiva.
TESTA_H = 62
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
NAV_W = 156
NAV_ROW_H = 46
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
        # il blocco in fondo si misura prima, cosi' la barra sa quanto spazio
        # ha davvero: su un desktop da 864 pixel le diciotto voci non ci
        # stanno tutte insieme, e la barra scorre invece di stringersi
        editor = bool(getattr(self.app, "editor", False))
        save_y = h - 60                     # la riga Salva/Menu sta in fondo
        editor_y = save_y - 44
        race_y = (editor_y if editor else save_y) - 12 - 48
        rail_y = TOPBAR_H + 12
        rail_rect = (6, rail_y, NAV_W - 12, max(NAV_ROW_H, (race_y - 12) - rail_y))
        self.rail = ScrollList(rail_rect, row_h=NAV_ROW_H, draw_row=self._riga_nav,
                               on_select=self._scegli_nav)
        self.rail.items = NAV
        self.rail.selected = next((i for i, v in enumerate(NAV) if v[0] == self.page_id), -1)
        self.widgets.append(self.rail)
        self.race_btn = Button((12, race_y, NAV_W - 24, 48), "PROSSIMO EVENTO",
                               self.goto_weekend, "primary")
        self.widgets.append(self.race_btn)
        if editor:
            self.widgets.append(Button((12, editor_y, NAV_W - 24, 32), "EDITOR",
                                       self.open_editor, "danger"))
        self.widgets.append(Button((12, save_y, (NAV_W - 28) // 2, 34), "Salva", self.save, "ghost"))
        self.widgets.append(Button((12 + (NAV_W - 24) // 2, h - 60, (NAV_W - 28) // 2, 34),
                                   "Menu", self.to_menu, "ghost"))
        content = pygame.Rect(NAV_W, TOPBAR_H + TESTA_H, w - NAV_W, h - TOPBAR_H - TESTA_H)
        for p in self.pages.values():
            p.layout(content.inflate(-32, -28))

    def on_resize(self) -> None:
        self.build()

    def _riga_nav(self, surf, rect, i: int, item) -> None:
        """Una riga della barra: un gruppo si annuncia solo alla prima voce,
        cosi' diciotto destinazioni si leggono come cinque famiglie invece
        che come una colonna indistinta di etichette."""
        pid, label, icon_name, gruppo = item
        primo = i == 0 or NAV[i - 1][3] != gruppo
        attivo = pid == self.page_id
        colore = T.squadra_viva() if attivo else T.TEXT
        top = rect.y
        if primo:
            T.text(surf, gruppo, (rect.x + 12, top + 3), 9, T.DIM_2, bold=True,
                  maxw=rect.w - 18)
            top += 13
        corpo = pygame.Rect(rect.x, top, rect.w, rect.bottom - top)
        sopra = corpo.collidepoint(pygame.mouse.get_pos()) and not attivo
        h = fx.verso(("nav", pid), 1.0 if sopra else 0.0, 14.0)
        if attivo:
            # la voce aperta e' una pillola accesa del colore della squadra
            pill = corpo.inflate(-4, -4)
            fx.splendi(surf, (pill.x + 8, pill.centery), 46, T.squadra_viva(), 0.20)
            T.panel(surf, pill, T.mix(T.PANEL_2, T.squadra(), 0.22), radius=8, rilievo=False)
            pygame.draw.rect(surf, T.squadra_viva(), (rect.x + 1, corpo.y + 4, 3, corpo.h - 8),
                             border_radius=2)
        elif h > 0.02:
            pill = corpo.inflate(-4, -4)
            pill.x += int(3 * (1.0 - h))
            T.panel(surf, pill, T.mix(T.PANEL, T.PANEL_2, h), radius=8, rilievo=False)
            colore = T.mix(T.TEXT, T.WHITE, h)
        icona = pygame.Rect(0, 0, 20, 20)
        icona.center = (rect.x + 24 + int(2 * h), corpo.centery)
        I.draw(surf, icon_name, icona, colore, 2)
        T.text(surf, label, (icona.right + 10, corpo.centery - 9), 14, colore,
              bold=attivo, maxw=rect.right - icona.right - 16)

    def _scegli_nav(self, i: int, item) -> None:
        self.go(item[0])

    # ------------------------------------------------------------------ azioni
    def go(self, pid: str) -> None:
        # cambiare pagina non e' un taglio di montaggio: la nuova entra con una
        # dissolvenza di un decimo e mezzo di secondo, che e' abbastanza da far
        # capire che si e' cambiato posto e abbastanza poco da non far
        # aspettare nessuno. Solo se si cambia davvero pagina
        if pid != self.page_id:
            self.entrata = DISSOLVENZA
            fx.entra()
        self.page_id = pid
        if self.rail is not None:
            self.rail.selected = next((i for i, v in enumerate(NAV) if v[0] == pid), -1)
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
        lato.fill((*T.PANEL, 225))
        surf.blit(lato, (0, TOPBAR_H))
        pygame.draw.line(surf, T.LINE, (NAV_W, TOPBAR_H), (NAV_W, h))

        # Barra superiore. Il colore della scuderia non e' piu' un filo di sei
        # pixel in un angolo: tinge il blocco del nome e corre lungo tutto il
        # bordo di sotto, che e' la riga che separa il gioco da chi lo gioca.
        # Una partita con la Ferrari e una con la Williams si devono
        # riconoscere da lontano.
        T.panel(surf, (0, 0, w, TOPBAR_H), T.PANEL_2, radius=0)
        # il blocco del nome prende il colore della squadra, con la sua luce
        blocco = pygame.Surface((NAV_W, TOPBAR_H))
        for x in range(NAV_W):
            blocco.fill(T.mix(T.mix(T.PANEL_2, col, 0.30), T.PANEL_2, x / NAV_W),
                        (x, 0, 1, TOPBAR_H))
        surf.blit(blocco, (0, 0))
        fx.splendi(surf, (30, TOPBAR_H // 2), 120, col, 0.16)
        pygame.draw.rect(surf, col, (0, 0, 5, TOPBAR_H))
        T.text(surf, team.short.upper(), (22, 12), 21, vivo, bold=True)
        T.text(surf, f"Stagione {gs.season}", (22, 38), 13, T.DIM)

        spent, limit, frac = economy.cap_usage(gs, team)
        pos = gs.position_of(team.id)
        ev = SEASON.evento_display(gs)
        # ogni numero vive dentro il suo riquadro invece che appoggiato sul
        # fondo della barra: cosi' si legge come una scheda, non come una
        # riga di didascalie
        kpi = [
            (250, 158, "LIQUIDITA'", T.fmt_money(team.cash),
             T.OK if team.cash > 5 else T.BAD),
            (424, 178, "BUDGET CAP", f"{spent:.1f} / {limit:.0f} M$",
             T.BAD if frac > 1.0 else (T.WARN if frac > 0.85 else T.TEXT)),
            (618, 158, "COSTRUTTORI", f"{pos}o  -  {team.points:.0f} pt", T.TEXT),
        ]
        if ev:
            kpi.append((792, 296, f"{ev['sigla']} {ev['conta']}", ev["titolo"], T.TEXT))
        else:
            kpi.append((792, 160, "STAGIONE", "conclusa", T.WARN))
        drs = gs.drivers_of(team.id)
        # i piloti stanno in fondo alla barra, e in fondo vuol dire in fondo a
        # questa finestra: su uno schermo stretto a 1090 fissi finivano fuori
        if drs and w >= 1120:
            names = "  |  ".join(f"{d.last} {d.points:.0f}" for d in drs)
            largo = min(330, w - 1106)
            kpi.append((w - largo - 16, largo, "PILOTI", names, T.TEXT))
        for x, tw, label, value, colour in kpi:
            _kv(surf, x, tw, label, value, colour)
        pygame.draw.line(surf, T.LINE, (0, TOPBAR_H), (w, TOPBAR_H))
        # il filo del colore della squadra sotto la barra, acceso: una luce
        # corre avanti e indietro lungo il filo, piano
        surf.blit(fx.striscia_luce(w, 14, col, 0.35), (0, TOPBAR_H - 8),
                  special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.rect(surf, col, (0, TOPBAR_H - 2, w, 2))
        if not fx.LEGGERO:
            corre = (math.sin(fx.ora() * 0.6) * 0.5 + 0.5) * w
            surf.blit(fx.striscia_luce(260, 6, T.mix(col, T.WHITE, 0.5), 0.8),
                      (int(corre) - 130, TOPBAR_H - 4), special_flags=pygame.BLEND_RGB_ADD)

        # la pagina si disegna dentro la sua finestra: se e' piu' alta, quello
        # che esce sopra e sotto viene tagliato invece di finire sulla barra
        self._testata(surf, w)
        pagina = self.pages[self.page_id]
        prev = surf.get_clip()
        # si taglia sull'area dei contenuti, non su quella della pagina: sopra
        # c'e' la barra con liquidita' e punti, e quando si scorre le pagine
        # ci finivano sopra
        vista = pygame.Rect(NAV_W + 1, TOPBAR_H + TESTA_H, w - NAV_W - 1,
                            h - TOPBAR_H - TESTA_H)
        surf.set_clip(vista.clip(prev) if prev else vista)
        T.ink_start()
        pagina.draw(surf)
        fondo = T.ink_stop()
        if self.entrata > 0.0:
            # la dissolvenza si fa con un velo sopra a quello che e' gia'
            # disegnato: costa un rettangolo per fotogramma e non obbliga
            # nessuna pagina a sapere che esiste
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
            pygame.draw.rect(surf, T.PANEL_3, (w - 9, y, 4, alt), border_radius=2)
        super().draw(surf)

    def _testata(self, surf, w: int) -> None:
        """L'intestazione della pagina aperta.

        A sinistra il distintivo con l'icona, acceso del colore della squadra;
        sopra al nome la famiglia (squadra, persone, programmi...), poi il nome
        grande in condensato e, a destra, a cosa serve la pagina. Sotto, un filo
        del colore della squadra che sfuma. Quando si cambia pagina il nome entra
        da sinistra e il filo si allunga.
        """
        voce = next((v for v in NAV if v[0] == self.page_id), None)
        if voce is None:
            return
        pid, nome, icona, gruppo = voce
        col = T.squadra()
        vivo = T.squadra_viva()
        q = fx.entrata()
        r = pygame.Rect(NAV_W + 16, TOPBAR_H + 10, w - NAV_W - 32, TESTA_H - 14)
        # il distintivo
        badge = pygame.Rect(r.x, r.y + 2, 42, 42)
        fx.splendi(surf, badge.center, 44, col, 0.22 * q)
        T.panel(surf, badge, T.mix(T.PANEL_2, col, 0.28), radius=10, rilievo=False,
                border=T.mix(T.LINE, vivo, 0.6))
        I.draw(surf, icona, badge.inflate(-18, -18), T.WHITE, 2)
        # il nome, che entra da sinistra
        x = badge.right + 14 - int(24 * (1.0 - q))
        eyebrow = T.render("  ".join(gruppo), 10, vivo, bold=True)
        eyebrow.set_alpha(int(255 * q))
        surf.blit(eyebrow, (x, r.y + 1))
        titolo = T.render(nome.upper(), 28, T.TEXT, bold=True)
        titolo.set_alpha(int(255 * q))
        surf.blit(titolo, (x, r.y + 12))
        # a destra, a cosa serve; e le tre bande oblique del colore della squadra
        fine = r.right
        for k in range(3):
            bx = fine - 12 - k * 11
            pygame.draw.polygon(surf, T.mix(col, T.BG, 0.25 + 0.25 * k),
                                [(bx, r.y + 6), (bx + 6, r.y + 6), (bx - 6, r.y + 40),
                                 (bx - 12, r.y + 40)])
        desc = DESCRIZIONI.get(pid, "")
        spazio = fine - 60 - (x + titolo.get_width() + 30)
        if desc and spazio > 120:
            T.text(surf, desc, (fine - 52, r.y + 20), 14, T.DIM, align="right", maxw=spazio)
        # il filo sotto, che si allunga
        lungo = int((r.w) * q)
        if lungo > 4:
            surf.blit(fx.striscia_luce(max(8, lungo * 2), 3, col, 0.9), (r.x - lungo, r.bottom + 1),
                      special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.line(surf, T.mix(T.LINE, col, 0.5), (r.x, r.bottom + 2),
                             (r.x + lungo, r.bottom + 2))


def _kv(surf, x: int, w: int, label: str, value: str, colour=T.TEXT) -> None:
    """Un numero della barra superiore, dentro la sua scheda.

    Prima era una didascalia appoggiata sul fondo della barra: un riquadro
    proprio lo separa dai suoi vicini anche quando i due valori sono lunghi
    uguali, e il numero grande si legge da piu' lontano di prima.
    """
    r = pygame.Rect(x - 12, 10, w, TOPBAR_H - 20)
    T.panel(surf, r, T.PANEL_3, radius=8, rilievo=False)
    inner = w - 16
    T.text(surf, label, (x, 17), 10, T.DIM_2, bold=True, mono=True, maxw=inner)
    # i numeri della barra scorrono quando cambiano: una gara che porta punti
    # si vede salire, un pagamento si vede scendere
    value = fx.rotola_testo(("kv", label), value, da_zero=False)
    T.text(surf, value, (x, 33), 20, colour, bold=True, maxw=inner)
