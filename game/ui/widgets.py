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
        self.style = style          # normal | primary | ghost | danger | tab
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
    """Lista scrollabile con righe disegnate da una callback."""

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
            if self.body.collidepoint(ev.pos):
                self.hover_idx = int((ev.pos[1] - self.body.y + self.offset) // self.row_h)
            else:
                self.hover_idx = -1
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.body.collidepoint(ev.pos):
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
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.value = not self.value
            if self.on_change:
                self.on_change(self.value)
            return True
        return False

    def draw(self, surf) -> None:
        knob = pygame.Rect(self.rect.right - 52, self.rect.centery - 12, 46, 24)
        T.panel(surf, knob, T.OK if self.value else T.PANEL_3, radius=12)
        cx = knob.right - 13 if self.value else knob.x + 13
        pygame.draw.circle(surf, T.WHITE, (cx, knob.centery), 9)
        T.text(surf, self.label, (self.rect.x, self.rect.centery - 9), 15, T.TEXT)


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
