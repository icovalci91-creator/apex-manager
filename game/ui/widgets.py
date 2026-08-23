"""Widget di base: pulsanti, liste, tabelle, slider, tab, schede."""
from __future__ import annotations

import pygame

from . import theme as T


class Widget:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.enabled = True
        self.visible = True

    def handle(self, ev) -> bool:
        return False

    def draw(self, surf) -> None:
        pass

    def update(self, dt: float) -> None:
        pass


class Button(Widget):
    def __init__(self, rect, label, on_click=None, style="normal", icon="", tip=""):
        super().__init__(rect)
        self.label = label
        self.on_click = on_click
        self.style = style          # normal | primary | ghost | danger | tab | invisible
        self.icon = icon
        self.tip = tip
        self.hover = False
        self.active = False

    def handle(self, ev) -> bool:
        if not (self.enabled and self.visible):
            return False
        if ev.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surf) -> None:
        if not self.visible:
            return
        if self.style == "invisible":
            # zona cliccabile sopra qualcosa che si disegna da solo: si limita a
            # far capire che ci si puo' cliccare
            if self.hover:
                pygame.draw.rect(surf, T.ACCENT, self.rect, 2, border_radius=10)
            return
        bg, fg, border = T.PANEL_2, T.TEXT, None
        if self.style == "primary":
            bg, fg = (T.ACCENT if not self.hover else (60, 220, 255)), (8, 14, 22)
        elif self.style == "ghost":
            bg, fg, border = (T.PANEL_2 if self.hover else T.PANEL), T.DIM, T.LINE
        elif self.style == "danger":
            bg, fg = (T.BAD if not self.hover else (245, 110, 115)), T.WHITE
        elif self.style == "tab":
            bg = T.PANEL_3 if self.active else (T.PANEL_2 if self.hover else T.PANEL)
            fg = T.TEXT if self.active else T.DIM
        elif self.hover:
            bg = T.PANEL_3
        if not self.enabled:
            bg, fg = T.PANEL, T.DIM_2
        T.panel(surf, self.rect, bg, radius=8, border=border)
        if self.style == "tab" and self.active:
            pygame.draw.rect(surf, T.ACCENT, (self.rect.x, self.rect.bottom - 3, self.rect.w, 3),
                             border_radius=2)
        lbl = (self.icon + "  " if self.icon else "") + self.label
        f = T.font(15, self.style == "primary")
        img = f.render(T.ellipsize(lbl, f, self.rect.w - 16), True, fg)
        surf.blit(img, img.get_rect(center=self.rect.center))


class Slider(Widget):
    def __init__(self, rect, label, value=50.0, lo=0.0, hi=100.0, on_change=None, fmt="{:.0f}"):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.lo, self.hi = lo, hi
        self.on_change = on_change
        self.drag = False
        self.fmt = fmt
        self.marker = None      # valore consigliato dagli ingegneri

    @property
    def track_rect(self):
        return pygame.Rect(self.rect.x + 190, self.rect.centery - 4, self.rect.w - 260, 8)

    def _set_from_x(self, x):
        tr = self.track_rect
        f = max(0.0, min(1.0, (x - tr.x) / max(1, tr.w)))
        self.value = self.lo + f * (self.hi - self.lo)
        if self.on_change:
            self.on_change(self.value)

    def handle(self, ev) -> bool:
        if not self.enabled:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos) and ev.pos[0] > self.rect.x + 175:
                self.drag = True
                self._set_from_x(ev.pos[0])
                return True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.drag = False
        elif ev.type == pygame.MOUSEMOTION and self.drag:
            self._set_from_x(ev.pos[0])
            return True
        return False

    def draw(self, surf) -> None:
        T.text(surf, self.label, (self.rect.x, self.rect.centery - 9), 15, T.DIM)
        tr = self.track_rect
        pygame.draw.rect(surf, T.PANEL_3, tr, border_radius=4)
        f = (self.value - self.lo) / max(1e-6, self.hi - self.lo)
        pygame.draw.rect(surf, T.ACCENT, (tr.x, tr.y, int(tr.w * f), tr.h), border_radius=4)
        if self.marker is not None:
            mf = (self.marker - self.lo) / max(1e-6, self.hi - self.lo)
            mx = tr.x + int(tr.w * mf)
            pygame.draw.line(surf, T.GOLD, (mx, tr.y - 6), (mx, tr.bottom + 6), 2)
        cx = tr.x + int(tr.w * f)
        pygame.draw.circle(surf, T.WHITE, (cx, tr.centery), 8)
        pygame.draw.circle(surf, T.ACCENT, (cx, tr.centery), 5)
        T.text(surf, self.fmt.format(self.value), (self.rect.right, self.rect.centery - 9),
               15, T.TEXT, bold=True, align="right")


class ScrollList(Widget):
    """Lista scrollabile con righe disegnate da una callback.

    Si scorre con la rotellina o trascinando: il trascinamento serve al tocco,
    dove la rotellina non esiste.
    """

    TAP_SLOP = 8        # px di scivolamento ancora tollerati per un tocco

    def __init__(self, rect, row_h=34, draw_row=None, on_select=None, header_h=0, draw_header=None):
        super().__init__(rect)
        self.row_h = row_h
        self.items: list = []
        self.offset = 0.0
        self.selected = -1
        self.draw_row = draw_row
        self.draw_header = draw_header
        self.header_h = header_h
        self.on_select = on_select
        self.hover_idx = -1
        self.pressed = False        # trascinamento in corso (dito o mouse)
        self._grab_y = 0
        self._grab_offset = 0.0
        self._moved = 0.0

    @property
    def body(self):
        return pygame.Rect(self.rect.x, self.rect.y + self.header_h,
                           self.rect.w, self.rect.h - self.header_h)

    @property
    def max_offset(self):
        return max(0.0, len(self.items) * self.row_h - self.body.h)

    def handle(self, ev) -> bool:
        if not self.visible:
            return False
        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.offset = max(0.0, min(self.max_offset, self.offset - ev.y * 48))
                return True
        elif ev.type == pygame.MOUSEMOTION:
            if self.pressed:
                # trascinamento: la lista segue il dito
                delta = ev.pos[1] - self._grab_y
                self._moved += abs(ev.rel[1]) if hasattr(ev, "rel") else abs(delta)
                self.offset = max(0.0, min(self.max_offset, self._grab_offset - delta))
                return True
            if self.body.collidepoint(ev.pos):
                self.hover_idx = int((ev.pos[1] - self.body.y + self.offset) // self.row_h)
            else:
                self.hover_idx = -1
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.body.collidepoint(ev.pos):
                self.pressed = True
                self._grab_y = ev.pos[1]
                self._grab_offset = self.offset
                self._moved = 0.0
                return True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if not self.pressed:
                return False
            self.pressed = False
            # se il dito e' scivolato si stava scorrendo, non scegliendo
            if self._moved <= self.TAP_SLOP and self.body.collidepoint(ev.pos):
                idx = int((ev.pos[1] - self.body.y + self.offset) // self.row_h)
                if 0 <= idx < len(self.items):
                    self.selected = idx
                    if self.on_select:
                        self.on_select(idx, self.items[idx])
            return True
        return False

    def draw(self, surf) -> None:
        if not self.visible:
            return
        if self.draw_header and self.header_h:
            self.draw_header(surf, pygame.Rect(self.rect.x, self.rect.y, self.rect.w, self.header_h))
        body = self.body
        prev = surf.get_clip()
        surf.set_clip(body)
        first = max(0, int(self.offset // self.row_h))
        last = min(len(self.items), first + body.h // self.row_h + 2)
        for i in range(first, last):
            y = body.y + i * self.row_h - self.offset
            r = pygame.Rect(body.x, int(y), body.w, self.row_h)
            if i == self.selected:
                T.panel(surf, r.inflate(-4, -3), T.PANEL_3, radius=6)
            elif i == self.hover_idx:
                T.panel(surf, r.inflate(-4, -3), T.PANEL_2, radius=6)
            if self.draw_row:
                self.draw_row(surf, r, i, self.items[i])
        surf.set_clip(prev)
        if self.max_offset > 0:
            h = max(24, int(body.h * body.h / (len(self.items) * self.row_h)))
            y = body.y + int((body.h - h) * self.offset / self.max_offset)
            pygame.draw.rect(surf, T.PANEL_3, (self.rect.right - 6, y, 4, h), border_radius=2)


class Tabs(Widget):
    def __init__(self, rect, labels, on_change=None, w=150):
        super().__init__(rect)
        self.labels = labels
        self.index = 0
        self.on_change = on_change
        self.buttons = []
        x = rect[0]
        for i, lab in enumerate(labels):
            b = Button((x, rect[1], w, rect[3]), lab, style="tab")
            b.on_click = (lambda i=i: self.select(i))
            b.active = (i == 0)
            self.buttons.append(b)
            x += w + 4

    def select(self, i: int) -> None:
        self.index = i
        for j, b in enumerate(self.buttons):
            b.active = (j == i)
        if self.on_change:
            self.on_change(i)

    def handle(self, ev) -> bool:
        return any(b.handle(ev) for b in self.buttons)

    def draw(self, surf) -> None:
        for b in self.buttons:
            b.draw(surf)


class Toggle(Widget):
    def __init__(self, rect, label, value=False, on_change=None):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.on_change = on_change

    def handle(self, ev) -> bool:
        if not self.enabled:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.value = not self.value
            if self.on_change:
                self.on_change(self.value)
            return True
        return False

    def draw(self, surf) -> None:
        knob = pygame.Rect(self.rect.right - 52, self.rect.centery - 12, 46, 24)
        if not self.enabled:
            T.panel(surf, knob, T.PANEL, radius=12, border=T.LINE)
            pygame.draw.circle(surf, T.DIM_2, (knob.x + 13, knob.centery), 9)
            T.text(surf, self.label, (self.rect.x, self.rect.centery - 9), 15, T.DIM_2)
            return
        T.panel(surf, knob, T.OK if self.value else T.PANEL_3, radius=12)
        cx = knob.right - 13 if self.value else knob.x + 13
        pygame.draw.circle(surf, T.WHITE, (cx, knob.centery), 9)
        T.text(surf, self.label, (self.rect.x, self.rect.centery - 9), 15, T.TEXT)


class TextInput(Widget):
    """Campo di testo. Serve all'editor: e' l'unico modo per scrivere un valore
    qualunque senza inventarsi un cursore per ogni tipo di dato."""

    def __init__(self, rect, value="", on_commit=None, placeholder=""):
        super().__init__(rect)
        self.value = str(value)
        self.on_commit = on_commit
        self.placeholder = placeholder
        self.focused = False
        self.caret = 0.0

    def focus(self) -> None:
        self.focused = True
        pygame.key.set_repeat(320, 34)

    def blur(self) -> None:
        self.focused = False

    def handle(self, ev) -> bool:
        if not self.enabled:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            dentro = self.rect.collidepoint(ev.pos)
            if dentro and not self.focused:
                self.focus()
            elif not dentro and self.focused:
                self.blur()
            return dentro
        if not self.focused or ev.type != pygame.KEYDOWN:
            return False
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.on_commit:
                self.on_commit(self.value)
            return True
        if ev.key == pygame.K_ESCAPE:
            self.blur()
            return True
        if ev.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
            return True
        ch = getattr(ev, "unicode", "")
        if ch and ch.isprintable():
            self.value += ch
            return True
        return False

    def update(self, dt: float) -> None:
        self.caret = (self.caret + dt) % 1.0

    def draw(self, surf) -> None:
        T.panel(surf, self.rect, T.PANEL_3 if self.focused else T.PANEL_2, radius=6,
                border=T.ACCENT if self.focused else T.LINE)
        testo = self.value if self.value else self.placeholder
        col = T.TEXT if self.value else T.DIM_2
        T.text(surf, testo, (self.rect.x + 10, self.rect.centery - 9), 15, col,
               maxw=self.rect.w - 20)
        if self.focused and self.caret < 0.5:
            x = min(self.rect.right - 8, self.rect.x + 12 + T.width(self.value, 15))
            pygame.draw.line(surf, T.ACCENT, (x, self.rect.y + 7),
                             (x, self.rect.bottom - 7), 2)


def stat_row(surf, rect, label, value, maxv=100.0, colour=None, suffix="", show_bar=True):
    T.text(surf, label, (rect.x, rect.centery - 9), 14, T.DIM)
    col = colour or T.stat_colour(value)
    if show_bar:
        T.bar(surf, (rect.x + 168, rect.centery - 5, rect.w - 240, 10), value, maxv, col)
    T.text(surf, f"{value:.0f}{suffix}", (rect.right, rect.centery - 9), 15, col,
           bold=True, align="right")


def card(surf, rect, title, value, sub="", colour=None, accent=T.ACCENT):
    rect = pygame.Rect(rect)
    T.panel(surf, rect, T.PANEL, radius=10, border=T.LINE)
    pygame.draw.rect(surf, accent, (rect.x, rect.y + 8, 3, rect.h - 16))
    T.text(surf, title.upper(), (rect.x + 14, rect.y + 10), 11, T.DIM_2, bold=True,
           maxw=rect.w - 28)
    T.text(surf, value, (rect.x + 14, rect.y + 26), 24, colour or T.TEXT, bold=True,
           maxw=rect.w - 28)
    if sub:
        T.text(surf, sub, (rect.x + 14, rect.y + 58), 12, T.DIM, maxw=rect.w - 28)


# ============================================================ scorrimento
class Flow:
    """Cursore di scrittura: si scrive una riga dopo l'altra.

    Il problema delle schermate era sempre lo stesso: ogni blocco veniva
    piazzato a una distanza fissa dal bordo del pannello, calcolata a mano
    quando quel blocco e' stato scritto. Bastava che il blocco sopra crescesse
    di una riga - un testo piu' lungo, una specifica in piu', una frase che va
    a capo - e i due finivano uno sopra l'altro.

    Qui la posizione non la sceglie nessuno: la decide quello che c'e' scritto
    sopra. Ogni cosa scritta sposta il cursore di quanto ha occupato davvero, e
    due cose non possono sovrapporsi nemmeno volendo.

    Lo stesso codice serve a misurare e a disegnare: con `surf` a None non
    disegna niente ma il cursore avanza uguale, ed e' cosi' che il pannello sa
    quanto e' alto il contenuto prima di mostrarlo.
    """

    def __init__(self, surf, x: int, y: int, w: int, panel=None):
        self.surf = surf
        self.x = int(x)
        self.y = float(y)
        self.w = int(w)
        self.panel = panel      # per raccogliere i widget in fase di misura

    # ------------------------------------------------------------- testo
    def head(self, s: str, colour=T.DIM_2, gap: int = 6) -> None:
        """Titoletto di sezione."""
        if self.surf:
            T.text(self.surf, str(s).upper(), (self.x, int(self.y)), 12, colour,
                   bold=True, maxw=self.w)
        self.y += T.line_h(12) + gap

    def line(self, s: str, size: int = 13, colour=T.DIM, bold: bool = False,
             gap: int = 2, indent: int = 0) -> None:
        """Una riga sola: se non ci sta viene tagliata."""
        if self.surf:
            T.text(self.surf, s, (self.x + indent, int(self.y)), size, colour,
                   bold=bold, maxw=self.w - indent)
        self.y += T.line_h(size, bold) + gap

    def par(self, s: str, size: int = 12, colour=T.DIM_2, bold: bool = False,
            gap: int = 6, indent: int = 0) -> None:
        """Un testo che va a capo da solo quante volte serve."""
        righe = T.wrap(s, size, self.w - indent, bold)
        for riga in righe:
            if self.surf:
                T.text(self.surf, riga, (self.x + indent, int(self.y)), size, colour,
                       bold=bold)
            self.y += T.line_h(size, bold)
        self.y += gap

    def kv(self, k: str, v: str, size: int = 13, colour=T.TEXT, key_colour=T.DIM,
           gap: int = 4) -> None:
        """Etichetta a sinistra, valore a destra."""
        if self.surf:
            T.text(self.surf, k, (self.x, int(self.y)), size, key_colour,
                   maxw=self.w * 0.62)
            T.text(self.surf, v, (self.x + self.w, int(self.y)), size, colour,
                   bold=True, align="right", maxw=self.w * 0.42)
        self.y += T.line_h(size) + gap

    def bar_row(self, label: str, value: float, maxv: float = 100.0, colour=None,
                suffix: str = "", size: int = 13, gap: int = 5) -> None:
        h = T.line_h(size)
        if self.surf:
            stat_row(self.surf, pygame.Rect(self.x, int(self.y), self.w, h),
                     label, value, maxv, colour, suffix)
        self.y += h + gap

    # ----------------------------------------------------------- spazio
    def gap(self, n: int = 10) -> None:
        self.y += n

    def rule(self, gap: int = 8) -> None:
        if self.surf:
            pygame.draw.line(self.surf, T.LINE, (self.x, int(self.y)),
                             (self.x + self.w, int(self.y)))
        self.y += 1 + gap

    def box(self, h: int, gap: int = 8) -> pygame.Rect:
        """Riserva uno spazio e restituisce dove sta: per i disegni a mano."""
        r = pygame.Rect(self.x, int(self.y), self.w, int(h))
        self.y += h + gap
        return r

    # ---------------------------------------------------------- widget
    def widget(self, w, h: int | None = None, width: int | None = None,
               gap: int = 8):
        """Mette un widget nel flusso: la sua altezza fa spazio come il testo."""
        alt = int(h if h is not None else w.rect.h)
        larg = int(width if width is not None else self.w)
        w.rect = pygame.Rect(self.x, int(self.y), larg, alt)
        self.y += alt + gap
        if self.panel is not None:
            self.panel.widgets.append(w)
        return w

    def at(self, w, rect, register: bool = True):
        """Mette un widget dove dico io, senza toccare il cursore.

        Serve alle zone cliccabili sopra qualcosa che si disegna da solo: una
        riga di elenco, una casella di tabella, la sagoma della macchina.
        """
        w.rect = pygame.Rect(rect)
        if register and self.panel is not None:
            self.panel.widgets.append(w)
        return w

    def row(self, widgets: list, h: int = 34, gap: int = 8, spacing: int = 8):
        """Piu' widget affiancati sulla stessa riga."""
        widgets = [w for w in widgets if w is not None]
        if not widgets:
            return
        larg = (self.w - spacing * (len(widgets) - 1)) / len(widgets)
        x = self.x
        for w in widgets:
            w.rect = pygame.Rect(int(x), int(self.y), int(larg), h)
            if self.panel is not None:
                self.panel.widgets.append(w)
            x += larg + spacing
        self.y += h + gap


class ScrollPanel(Widget):
    """Un riquadro il cui contenuto puo' essere piu' alto dello spazio che ha.

    Quando il contenuto sfora non viene tagliato: si scorre, con la rotellina o
    trascinando col dito. Il contenuto lo scrive chi usa il pannello, con un
    `Flow`, e viene percorso due volte: una a vuoto per sapere quanto e' alto e
    dove finiscono i pulsanti, una per disegnarlo davvero.
    """

    TAP_SLOP = 8

    def __init__(self, rect, content=None, pad: int = 16, top: int = 14,
                 background=T.PANEL, border=T.LINE):
        super().__init__(rect)
        self.content = content
        self.pad = pad
        self.top = top
        self.background = background
        self.border = border
        self.offset = 0.0
        self.content_h = 0.0
        self.widgets: list = []
        self._grab_y = 0
        self._grab_offset = 0.0
        self._moved = 0.0
        self.pressed = False

    # ------------------------------------------------------------ misura
    @property
    def inner_w(self) -> int:
        return self.rect.w - 2 * self.pad

    @property
    def view_h(self) -> int:
        return self.rect.h - 2 * self.top

    @property
    def max_offset(self) -> float:
        return max(0.0, self.content_h - self.view_h)

    def layout(self) -> None:
        """Percorre il contenuto senza disegnarlo: altezza e posizione dei widget."""
        self.widgets = []
        if not self.content:
            self.content_h = 0.0
            return
        f = Flow(None, self.rect.x + self.pad, 0, self.inner_w, panel=self)
        self.content(f)
        self.content_h = f.y
        self.offset = max(0.0, min(self.max_offset, self.offset))

    # ------------------------------------------------------------ eventi
    # Quello che dentro un pannello si preme e si trascina: i cursori hanno
    # bisogno di ricevere subito la pressione, tutto il resto no. Cosi' si puo'
    # scorrere trascinando anche partendo da sopra un pulsante, come su un
    # telefono, senza che il pulsante scatti per sbaglio.
    PRESA_DIRETTA = (Slider, TextInput, ScrollList)

    def handle(self, ev) -> bool:
        if not (self.enabled and self.visible):
            return False
        dentro = hasattr(ev, "pos") and self.rect.collidepoint(ev.pos)

        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my) and self.max_offset > 0:
                self.offset = max(0.0, min(self.max_offset, self.offset - ev.y * 54))
                return True
            return False

        if ev.type == pygame.MOUSEMOTION:
            if self.pressed:
                delta = ev.pos[1] - self._grab_y
                self._moved += abs(getattr(ev, "rel", (0, 0))[1])
                self.offset = max(0.0, min(self.max_offset, self._grab_offset - delta))
                return True
            # il passaggio del mouse serve a tutti, dentro e fuori: e' cosi' che
            # un pulsante si spegne quando ce ne si allontana
            for w in self.widgets:
                w.handle(ev)
            return False

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if not dentro:
                return False
            for w in self.widgets:
                if isinstance(w, self.PRESA_DIRETTA) and w.handle(ev):
                    return True
            if self.max_offset > 0:
                self.pressed = True
                self._grab_y = ev.pos[1]
                self._grab_offset = self.offset
                self._moved = 0.0
                return True
            for w in self.widgets:
                if w.handle(ev):
                    return True
            return True

        if ev.type == pygame.MOUSEBUTTONUP:
            era = self.pressed
            self.pressed = False
            for w in self.widgets:
                if isinstance(w, self.PRESA_DIRETTA):
                    w.handle(ev)
            if era and self._moved <= self.TAP_SLOP and dentro:
                # non si stava scorrendo: era un clic, e adesso si vede a cosa
                clic = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                          {"pos": ev.pos, "button": 1})
                for w in self.widgets:
                    if not isinstance(w, self.PRESA_DIRETTA) and w.handle(clic):
                        return True
                return True
            if era:
                return True
            for w in self.widgets:
                if not isinstance(w, self.PRESA_DIRETTA) and w.handle(ev):
                    return True
            return False

        for w in self.widgets:
            if w.handle(ev):
                return True
        return False

    def update(self, dt: float) -> None:
        for w in self.widgets:
            w.update(dt)

    # ------------------------------------------------------------ disegno
    def draw(self, surf) -> None:
        if not self.visible:
            return
        if self.background:
            T.panel(surf, self.rect, self.background, radius=10, border=self.border)
        if not self.content:
            return
        prev = surf.get_clip()
        surf.set_clip(self.rect.clip(prev) if prev else self.rect)
        # il contenuto si ripercorre a ogni disegno, e i widget si raccolgono
        # qui: cosi' quello che si vede e quello che risponde al mouse sono
        # sempre la stessa cosa, anche se nel frattempo la partita e' cambiata
        self.widgets = []
        cima = self.rect.y + self.top - self.offset
        f = Flow(surf, self.rect.x + self.pad, cima, self.inner_w, panel=self)
        self.content(f)
        self.content_h = f.y - cima
        for w in self.widgets:
            w.draw(surf)
        surf.set_clip(prev)
        if self.max_offset > 0:
            # la barra dice che sotto c'e' altro: senza, non si scopre
            h = max(28, int(self.view_h * self.view_h / max(1.0, self.content_h)))
            y = self.rect.y + self.top + int((self.view_h - h) * self.offset / self.max_offset)
            pygame.draw.rect(surf, T.PANEL_3, (self.rect.right - 7, y, 4, h),
                             border_radius=2)
