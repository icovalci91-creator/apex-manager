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
            # senza il bordo un pulsante spento sparisce dentro il pannello,
            # e non si capisce che c'e' qualcosa che non si puo' fare
            bg, fg, border = T.PANEL, T.DIM_2, T.LINE
        T.panel(surf, self.rect, bg, radius=8, border=border)
        if self.style == "tab" and self.active:
            pygame.draw.rect(surf, T.ACCENT, (self.rect.x, self.rect.bottom - 3, self.rect.w, 3),
                             border_radius=2)
        lbl = (self.icon + "  " if self.icon else "") + self.label
        f = T.font(15, self.style == "primary")
        img = f.render(T.ellipsize(lbl, f, self.rect.w - 16), True, fg)
        surf.blit(img, img.get_rect(center=self.rect.center))


def _passo_tondo(x: float) -> float:
    """Il passo "da persona" piu' vicino: 1, 2 o 5 per la potenza di dieci giusta."""
    if x <= 0:
        return 1.0
    import math
    e = math.floor(math.log10(x))
    base = 10.0 ** e
    for m in (5.0, 2.0, 1.0):
        if m * base <= x + 1e-12:
            return m * base
    return base


def _decimali(fmt: str) -> int:
    """Quante cifre dopo la virgola mostra questo formato."""
    testa = fmt.split("}")[0]
    if "." in testa:
        cifre = testa.split(".")[1]
        cifre = "".join(c for c in cifre if c.isdigit())
        return int(cifre) if cifre else 0
    return 0


class Slider(Widget):
    """Barra con i due pulsantini ai lati.

    Trascinare va bene per capire dove si sta, ma per scegliere una cifra
    precisa serve poter fare un passo alla volta: da qui i due tasti, che
    tenuti premuti accelerano. Il passo si ricava dal formato - se il numero si
    legge con due decimali, il passo non e' mai piu' grosso di quello che si
    vede - e i valori restano sempre multipli tondi.
    """

    BTN = 22
    DELAY = 0.35            # quanto si aspetta prima che il tasto tenuto ripeta
    REPEAT = 0.055

    def __init__(self, rect, label, value=50.0, lo=0.0, hi=100.0, on_change=None,
                 fmt="{:.0f}", step=None):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.lo, self.hi = lo, hi
        self.on_change = on_change
        self.drag = False
        self.fmt = fmt
        self.marker = None      # valore consigliato dagli ingegneri
        self.step = step if step else self._passo_auto()
        self._held = 0          # -1 meno, +1 piu', 0 fermo
        self._t = 0.0
        self._hover = 0

    # ------------------------------------------------------------- geometria
    def _passo_auto(self) -> float:
        """Il passo piu' fine che si riesce a mostrare, senza esagerare.

        Se la risoluzione del formato basta a coprire l'intervallo in un numero
        ragionevole di scatti la si usa tale e quale; altrimenti si arrotonda,
        perche' duemila clic per andare da un capo all'altro non li fa nessuno.
        """
        span = abs(self.hi - self.lo)
        res = 10.0 ** -_decimali(self.fmt)
        if span <= 0:
            return res
        return res if span / res <= 200 else max(res, _passo_tondo(span / 100.0))

    @property
    def label_w(self) -> int:
        """Su un cursore stretto l'etichetta cede spazio, ma non troppo."""
        quota = 0.36 if self.rect.w < 420 else 0.42
        return max(96, min(206, int(self.rect.w * quota)))

    @property
    def VAL_W(self) -> int:
        """Lo spazio per il numero. Non scende sotto quello che serve a
        scrivere una cifra con tre decimali e l'unita'."""
        return min(88, max(70, int(self.rect.w * 0.22)))

    @property
    def minus_rect(self):
        return pygame.Rect(self.rect.x + self.label_w, self.rect.centery - self.BTN // 2,
                           self.BTN, self.BTN)

    @property
    def track_rect(self):
        x = self.rect.x + self.label_w + self.BTN + 6
        w = self.rect.w - self.label_w - 2 * self.BTN - 12 - self.VAL_W
        return pygame.Rect(x, self.rect.centery - 4, max(24, w), 8)

    @property
    def plus_rect(self):
        return pygame.Rect(self.track_rect.right + 6, self.rect.centery - self.BTN // 2,
                           self.BTN, self.BTN)

    # ---------------------------------------------------------------- valore
    def _snap(self, v: float) -> float:
        """Sempre un multiplo tondo del passo, dentro gli estremi."""
        lo, hi = min(self.lo, self.hi), max(self.lo, self.hi)
        v = lo + round((v - lo) / self.step) * self.step
        return max(lo, min(hi, round(v, 6)))

    def _emit(self, v: float) -> None:
        v = self._snap(v)
        if v != self.value:
            self.value = v
            if self.on_change:
                self.on_change(self.value)

    def nudge(self, verso: int) -> None:
        self._emit(self.value + verso * self.step)

    def _set_from_x(self, x):
        tr = self.track_rect
        f = max(0.0, min(1.0, (x - tr.x) / max(1, tr.w)))
        self._emit(self.lo + f * (self.hi - self.lo))

    # ----------------------------------------------------------------- input
    def handle(self, ev) -> bool:
        if not (self.enabled and self.visible):
            return False
        if ev.type == pygame.MOUSEMOTION:
            self._hover = (-1 if self.minus_rect.collidepoint(ev.pos) else
                           1 if self.plus_rect.collidepoint(ev.pos) else 0)
            if self.drag:
                self._set_from_x(ev.pos[0])
                return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.minus_rect.collidepoint(ev.pos):
                self._held, self._t = -1, self.DELAY
                self.nudge(-1)
                return True
            if self.plus_rect.collidepoint(ev.pos):
                self._held, self._t = 1, self.DELAY
                self.nudge(1)
                return True
            if self.track_rect.inflate(12, 20).collidepoint(ev.pos):
                self.drag = True
                self._set_from_x(ev.pos[0])
                return True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.drag = False
            self._held = 0
        elif ev.type == pygame.MOUSEWHEEL:
            # la rotellina sopra la barra fa un passo, che e' il modo piu'
            # rapido di aggiustare una cifra senza mirare a un pulsantino
            if self.rect.collidepoint(pygame.mouse.get_pos()) and ev.y:
                self.nudge(1 if ev.y > 0 else -1)
                return True
        return False

    def update(self, dt: float) -> None:
        if not self._held:
            return
        self._t -= dt
        while self._t <= 0.0:
            self.nudge(self._held)
            self._t += self.REPEAT

    # ------------------------------------------------------------------ draw
    def _draw_btn(self, surf, rect, segno) -> None:
        acceso = self._held == segno
        sopra = self._hover == segno
        bg = T.ACCENT if acceso else (T.PANEL_3 if sopra else T.PANEL_2)
        fg = (8, 14, 22) if acceso else (T.TEXT if sopra else T.DIM)
        if not self.enabled:
            bg, fg = T.PANEL, T.DIM_2
        T.panel(surf, rect, bg, radius=6, border=T.LINE)
        cx, cy = rect.center
        pygame.draw.line(surf, fg, (cx - 5, cy), (cx + 5, cy), 2)
        if segno > 0:
            pygame.draw.line(surf, fg, (cx, cy - 5), (cx, cy + 5), 2)

    def draw(self, surf) -> None:
        if not self.visible:
            return
        T.text(surf, self.label, (self.rect.x, self.rect.centery - 9), 15, T.DIM,
               maxw=self.label_w - 8)
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
        self._draw_btn(surf, self.minus_rect, -1)
        self._draw_btn(surf, self.plus_rect, 1)
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
