"""Gli effetti: luce, ombre, movimento, particelle, i momenti che si ricordano.

La grafica del gioco e' fatta di rettangoli, e i rettangoli restano: sono loro
che portano i numeri. Qui sta quello che ci si mette sopra perche' sembrino
lastre di vetro sotto le luci di uno studio televisivo invece che caselle di
un foglio di calcolo - il bagliore, l'ombra morbida, il riflesso che passa su
un pulsante - e i momenti della gara che meritano la scena: il semaforo della
partenza, la bandiera a scacchi, i coriandoli del podio, il passaggio da una
schermata all'altra.

Tutto quello che si puo' preparare una volta si prepara una volta e si tiene
da parte: un bagliore e' un'immagine, un'ombra e' un'immagine, e a ogni
fotogramma si incollano e basta. Nel browser, dove ogni millisecondo pesa, le
cose che si muovono da sole sullo sfondo restano ferme.
"""
from __future__ import annotations

import math
import random
import sys

import pygame

from . import audio

LEGGERO = sys.platform == "emscripten"

# ------------------------------------------------------------------ il tempo
_ORA = [0.0]


_VIVO = [False]


def tick(dt: float) -> None:
    """Fa avanzare l'orologio degli effetti: lo chiama il ciclo principale."""
    _ORA[0] += max(0.0, min(0.25, dt))
    _VIVO[0] = True


def ora() -> float:
    return _ORA[0]


def dolce(t: float) -> float:
    """Accelera e rallenta: l'andamento di tutto quello che si muove qui."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def esce(t: float) -> float:
    """Parte veloce e si posa: per quello che entra in scena."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


# Quando e' comparsa la schermata o la pagina di adesso: le barre crescono
# da zero al loro valore nel primo mezzo secondo, e cosi' una pagina nuova
# si legge come una cosa che si accende invece che come un cartello.
_ENTRATA = [-10.0]
ENTRATA_S = 0.7


def entra() -> None:
    """Segna che e' comparsa una schermata nuova."""
    _ENTRATA[0] = ora()


def entrata() -> float:
    """Da 0 a 1: quanto e' andata avanti la comparsa della schermata."""
    if not _VIVO[0]:
        # senza il ciclo principale (uno strumento, una prova) il tempo non
        # scorre: tutto si mostra gia' arrivato
        return 1.0
    return esce((ora() - _ENTRATA[0]) / ENTRATA_S)


# I numeri che scorrono: un valore nuovo non compare, ci arriva contando.
# Quando si apre una pagina i suoi numeri partono da zero; quando un numero
# cambia mentre lo si guarda, scorre dal vecchio al nuovo.
_ROTOLI: dict = {}
ROTOLA_S = 0.9
_NUMERO = __import__("re").compile(r"\d+(?:[.,]\d+)?")


def rotola(chiave, valore: float, da_zero: bool = True) -> float:
    """Il valore da mostrare adesso per `chiave`, che corre verso `valore`.

    `da_zero` fa ripartire il conto da zero ogni volta che la schermata
    ricompare; senza, il numero scorre solo quando cambia.
    """
    if not _VIVO[0]:
        return valore
    t = ora()
    st = _ROTOLI.get(chiave)
    if st is None or (da_zero and st[3] < _ENTRATA[0]):
        partenza = 0.0 if da_zero else valore
        st = (partenza, valore, t, _ENTRATA[0])
    elif abs(st[1] - valore) > 1e-9:
        # cambiato: si riparte da dove si era arrivati
        q = esce((t - st[2]) / ROTOLA_S)
        st = (st[0] + (st[1] - st[0]) * q, valore, t, st[3])
    _ROTOLI[chiave] = st
    if len(_ROTOLI) > 3000:
        _ROTOLI.clear()
    q = esce((t - st[2]) / ROTOLA_S)
    return st[0] + (st[1] - st[0]) * q


def rotola_testo(chiave, testo: str, da_zero: bool = True) -> str:
    """Lo stesso testo, con i numeri che ci sono dentro che scorrono.

    Il formato resta quello scritto: quanti decimali, la virgola o il punto,
    quello che c'e' prima e dopo. "54.56 M$" conta fino a 54.56 e resta in
    milioni; un nome senza numeri resta com'e'.
    """
    if not _VIVO[0] or not testo:
        return testo
    pezzi = []
    fine = 0
    for k, m in enumerate(_NUMERO.finditer(testo)):
        cifre = m.group(0)
        sep = "," if "," in cifre else "."
        decimali = len(cifre.split(sep)[1]) if sep in cifre else 0
        v = rotola((chiave, k), float(cifre.replace(",", ".")), da_zero)
        scritto = f"{v:.{decimali}f}"
        if sep == ",":
            scritto = scritto.replace(".", ",")
        pezzi.append(testo[fine:m.start()])
        pezzi.append(scritto)
        fine = m.end()
    pezzi.append(testo[fine:])
    return "".join(pezzi)


# Quanto si e' avvicinato ognuno al suo obiettivo, per chi si anima da solo
# (un pulsante sotto al mouse, una voce di menu). La chiave e' quella che
# sceglie chi chiama: le schermate ricostruiscono i pulsanti spesso, e lo
# stato dell'animazione non puo' stare dentro al pulsante.
_VERSO: dict = {}


def verso(chiave, obiettivo: float, rapidita: float = 12.0) -> float:
    """Un valore che insegue `obiettivo` con un'andatura morbida."""
    t = ora()
    v, prima = _VERSO.get(chiave, (obiettivo, t))
    k = min(1.0, (t - prima) * rapidita)
    v += (obiettivo - v) * k
    _VERSO[chiave] = (v, t)
    if len(_VERSO) > 4000:
        _VERSO.clear()
    return v


# ------------------------------------------------------------------ la luce
_BAGLIORI: dict = {}


def bagliore(raggio: int, colore, forza: float = 1.0) -> pygame.Surface:
    """Una macchia di luce tonda, da sommare a quello che c'e' sotto."""
    raggio = max(2, int(raggio))
    chiave = (raggio, tuple(colore[:3]), round(forza, 2))
    img = _BAGLIORI.get(chiave)
    if img is None:
        img = pygame.Surface((raggio * 2, raggio * 2))
        img.fill((0, 0, 0))
        passi = max(8, min(48, raggio // 3))
        for k in range(passi):
            q = k / passi
            r = int(raggio * (1.0 - q))
            if r <= 0:
                break
            luce = forza * (q + 1.0 / passi) ** 2.2
            c = tuple(min(255, int(x * luce)) for x in colore[:3])
            pygame.draw.circle(img, c, (raggio, raggio), r)
        if len(_BAGLIORI) > 300:
            _BAGLIORI.clear()
        _BAGLIORI[chiave] = img
    return img


def splendi(surf, centro, raggio: int, colore, forza: float = 1.0) -> None:
    """Accende una luce nel punto: si somma, non copre."""
    img = bagliore(raggio, colore, forza)
    surf.blit(img, (int(centro[0]) - img.get_width() // 2, int(centro[1]) - img.get_height() // 2),
              special_flags=pygame.BLEND_RGB_ADD)


_STRISCE: dict = {}


def striscia_luce(larga: int, alta: int, colore, forza: float = 1.0) -> pygame.Surface:
    """Una lama di luce orizzontale che sfuma ai due capi e sopra e sotto."""
    chiave = (larga, alta, tuple(colore[:3]), round(forza, 2))
    img = _STRISCE.get(chiave)
    if img is None:
        img = pygame.Surface((max(1, larga), max(1, alta)))
        img.fill((0, 0, 0))
        for x in range(larga):
            qx = 1.0 - abs(x / max(1, larga - 1) * 2.0 - 1.0)
            for y in range(alta):
                qy = 1.0 - abs(y / max(1, alta - 1) * 2.0 - 1.0) if alta > 1 else 1.0
                q = forza * (qx ** 1.6) * (qy ** 1.2)
                img.set_at((x, y), tuple(min(255, int(c * q)) for c in colore[:3]))
        if len(_STRISCE) > 120:
            _STRISCE.clear()
        _STRISCE[chiave] = img
    return img


# ------------------------------------------------------------------ l'ombra
_OMBRE: dict = {}


def ombra(larga: int, alta: int, raggio: int = 10, sfuma: int = 16,
          forza: int = 150) -> pygame.Surface:
    """L'ombra morbida di una lastra, piu' grande della lastra di `sfuma`."""
    chiave = (larga, alta, raggio, sfuma, forza)
    img = _OMBRE.get(chiave)
    if img is None:
        W, H = larga + 2 * sfuma, alta + 2 * sfuma
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, forza), (sfuma, sfuma, larga, alta),
                         border_radius=raggio)
        # sfocare = rimpicciolire e ringrandire: due volte, e l'ombra e' morbida
        piccola = pygame.transform.smoothscale(s, (max(1, W // 8), max(1, H // 8)))
        img = pygame.transform.smoothscale(piccola, (W, H))
        piccola = pygame.transform.smoothscale(img, (max(1, W // 4), max(1, H // 4)))
        img = pygame.transform.smoothscale(piccola, (W, H))
        if len(_OMBRE) > 400:
            _OMBRE.clear()
        _OMBRE[chiave] = img
    return img


def proietta(surf, rect, raggio: int = 10, sfuma: int = 16, scende: int = 6,
             forza: int = 150) -> None:
    """L'ombra sotto a una lastra, un po' spostata in basso come da una luce alta."""
    r = pygame.Rect(rect)
    if r.w < 8 or r.h < 8:
        return
    img = ombra(r.w, r.h, raggio, sfuma, forza)
    surf.blit(img, (r.x - sfuma, r.y - sfuma + scende))


# ------------------------------------------------------------------ il riflesso
def riflesso(surf, rect, periodo: float = 4.0, fase: float = 0.0,
             forza: float = 0.55, raggio: int = 8) -> None:
    """Una lama di luce obliqua che attraversa il rettangolo ogni tanto.

    E' il riflesso che passa su una lamiera lucida quando la si gira sotto una
    lampada: dice "questo si preme" senza dover lampeggiare.
    """
    r = pygame.Rect(rect)
    if r.w < 20 or r.h < 8:
        return
    t = ((ora() + fase) % periodo) / periodo
    corsa = 0.45             # la parte del periodo in cui la lama passa
    if t > corsa:
        return
    q = t / corsa
    larga = max(24, r.h)
    x = r.x - larga + int((r.w + 2 * larga) * dolce(q))
    lama = pygame.Surface((larga, r.h), pygame.SRCALPHA)
    for i in range(larga):
        a = int(255 * forza * (1.0 - abs(i / (larga - 1) * 2.0 - 1.0)) ** 2)
        pygame.draw.line(lama, (255, 255, 255, a), (i, 0), (i - r.h // 2, r.h))
    maschera = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.rect(maschera, (255, 255, 255, 255), maschera.get_rect(), border_radius=raggio)
    tela = pygame.Surface(r.size, pygame.SRCALPHA)
    tela.blit(lama, (x - r.x, 0))
    tela.blit(maschera, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(tela, r.topleft)


# ------------------------------------------------------------------ lo sfondo
_FONDI: dict = {}


def _fondo_fisso(w: int, h: int, alto, basso, squadra, accento) -> pygame.Surface:
    """Tutto quello dello sfondo che non si muove, dipinto una volta."""
    chiave = (w, h, tuple(alto), tuple(basso), tuple(squadra), tuple(accento))
    img = _FONDI.get(chiave)
    if img is not None:
        return img
    # la sfumatura dall'alto in basso
    col = pygame.Surface((1, h))
    for y in range(h):
        q = y / max(1.0, h - 1.0)
        col.set_at((0, y), tuple(int(a + (b - a) * q) for a, b in zip(alto, basso)))
    img = pygame.transform.scale(col, (w, h))
    # la trama: righe oblique sottilissime, come la fibra di carbonio vista
    # da lontano. Si sente, non si vede
    trama = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(-h, w, 6):
        pygame.draw.line(trama, (255, 255, 255, 5), (x, h), (x + h, 0))
    img.blit(trama, (0, 0))
    # le due luci dello studio: una del colore della squadra in alto a
    # sinistra, una fredda in basso a destra
    g = bagliore(int(max(w, h) * 0.55), squadra, 0.16)
    img.blit(g, (-g.get_width() // 3, -g.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
    g = bagliore(int(max(w, h) * 0.45), accento, 0.07)
    img.blit(g, (w - g.get_width() * 2 // 3, h - g.get_height() // 2),
             special_flags=pygame.BLEND_RGB_ADD)
    # e gli angoli che scuriscono, come in qualunque inquadratura
    vignetta = pygame.Surface((w, h), pygame.SRCALPHA)
    passi = 18
    for k in range(passi):
        a = int(9 * (1.0 - k / passi) ** 1.5)
        pygame.draw.rect(vignetta, (0, 0, 0, a), (0, 0, w, h), max(1, int(min(w, h) * 0.3 / passi)) * (passi - k))
    img.blit(vignetta, (0, 0))
    if len(_FONDI) > 6:
        _FONDI.clear()
    _FONDI[chiave] = img
    return img


# le scie che attraversano lo sfondo: poche, lente, sottili
_SCIE = [(random.Random(k).random(), random.Random(k + 99).random(),
          0.4 + random.Random(k + 7).random() * 0.9) for k in range(9)]


def sfondo(surf, alto, basso, squadra, accento, vivo: bool = True) -> None:
    """Lo sfondo di tutte le schermate: fermo nel browser, vivo altrove."""
    w, h = surf.get_size()
    surf.blit(_fondo_fisso(w, h, alto, basso, squadra, accento), (0, 0))
    if LEGGERO or not vivo:
        return
    t = ora()
    # la luce della squadra respira e si sposta piano
    cx = w * (0.18 + 0.10 * math.sin(t * 0.11))
    cy = h * (0.10 + 0.08 * math.cos(t * 0.083))
    splendi(surf, (cx, cy), int(min(w, h) * 0.42), squadra, 0.05 + 0.02 * math.sin(t * 0.5))
    # le scie di velocita'
    for a, b, v in _SCIE:
        lunga = int(180 + 260 * a)
        lama = striscia_luce(lunga, 2, (120, 170, 230), 0.10 + 0.08 * b)
        corsa = w + h * 0.4 + lunga
        x = ((a * corsa + t * 60.0 * v) % corsa) - lunga
        y = h * (0.08 + 0.84 * b) - x * 0.18 + h * 0.1
        surf.blit(lama, (int(x), int(y) % h), special_flags=pygame.BLEND_RGB_ADD)


# ------------------------------------------------------------------ particelle
class Coriandoli:
    """I coriandoli del podio, e le scintille: cadono, girano, spariscono."""

    COLORI = [(255, 214, 90), (255, 255, 255), (0, 200, 255), (230, 60, 70), (60, 210, 120)]

    def __init__(self, larga: int, alta: int, quanti: int = 160, colori=None, seme: int = 0):
        rng = random.Random(seme)
        self.w, self.h = larga, alta
        self.pezzi = []
        colori = colori or self.COLORI
        for _ in range(quanti):
            self.pezzi.append([rng.uniform(0, larga), rng.uniform(-alta * 0.9, -10),
                               rng.uniform(-40, 40), rng.uniform(80, 210),
                               rng.uniform(0, math.tau), rng.uniform(-6, 6),
                               rng.choice(colori), rng.uniform(7, 13)])
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt
        for p in self.pezzi:
            p[0] += (p[2] + 30 * math.sin(self.t * 2 + p[4])) * dt
            p[1] += p[3] * dt
            p[4] += p[5] * dt

    @property
    def finiti(self) -> bool:
        return all(p[1] > self.h + 20 for p in self.pezzi)

    def draw(self, surf, origine=(0, 0)) -> None:
        ox, oy = origine
        for x, y, _vx, _vy, ang, _va, col, lato in self.pezzi:
            if y < -10 or y > self.h + 10:
                continue
            larga = abs(math.cos(ang)) * lato
            r = pygame.Rect(0, 0, max(1, int(larga)), max(2, int(lato * 0.55)))
            r.center = (int(ox + x), int(oy + y))
            ombra_c = tuple(int(c * 0.55) for c in col)
            pygame.draw.rect(surf, col if math.cos(ang) > 0 else ombra_c, r)


# ------------------------------------------------------------------ il semaforo
class Semaforo:
    """Le cinque luci rosse della partenza, e poi via.

    Si accendono una al secondo, restano accese un tempo che nessuno conosce
    prima, e si spengono tutte insieme. Mentre sono accese la gara aspetta:
    `ferma` dice a chi la fa girare di non muoverla ancora.
    """

    PASSO = 0.75

    def __init__(self, seme: int = 0):
        self.t = 0.0
        self.attesa = 5 * self.PASSO + random.Random(seme).uniform(0.4, 1.4)
        self.via = 1.1          # quanto resta la scritta dopo lo spegnimento

    @property
    def ferma(self) -> bool:
        return self.t < self.attesa

    @property
    def finito(self) -> bool:
        return self.t >= self.attesa + self.via

    def salta(self) -> None:
        self.t = max(self.t, self.attesa)

    def _accese(self, t: float) -> int:
        return min(5, int(t / self.PASSO) + 1) if t < self.attesa else 0

    def update(self, dt: float) -> None:
        prima = self._accese(self.t) if self.t > 0 else 0
        self.t += dt
        if self._accese(self.t) > prima:
            audio.suona("luce", 0.5)
        if self.t >= self.attesa and not getattr(self, "_partiti", False):
            # e via: tutta la griglia insieme (anche se si e' saltata l'attesa)
            self._partiti = True
            audio.suona("partenza", 0.9)

    def draw(self, surf, rect) -> None:
        r = pygame.Rect(rect)
        accese = min(5, int(self.t / self.PASSO) + 1) if self.ferma else 0
        entra = esce(min(1.0, self.t / 0.35))
        # la barra delle luci, che scende dall'alto
        larga, alta = min(r.w - 40, 520), 124
        barra = pygame.Rect(0, 0, larga, alta)
        barra.midtop = (r.centerx, r.y + 18 - int((1.0 - entra) * 160))
        if self.finito:
            return
        dopo = self.t - self.attesa
        if dopo > 0:
            # spente: la barra se ne va verso l'alto e resta la scritta
            barra.y -= int(esce(min(1.0, dopo / 0.5)) * 190)
        proietta(surf, barra, 14, 20, 8, 180)
        pygame.draw.rect(surf, (10, 11, 14), barra, border_radius=14)
        pygame.draw.rect(surf, (48, 52, 62), barra, 2, border_radius=14)
        passo = larga // 5
        for k in range(5):
            cx = barra.x + passo // 2 + k * passo
            for fila in (0, 1):
                cy = barra.y + 36 + fila * 52
                acceso = k < accese
                pygame.draw.circle(surf, (26, 28, 34), (cx, cy), 21)
                if acceso:
                    splendi(surf, (cx, cy), 60, (255, 40, 30), 0.85)
                    pygame.draw.circle(surf, (255, 58, 48), (cx, cy), 18)
                    pygame.draw.circle(surf, (255, 170, 150), (cx - 5, cy - 6), 5)
                else:
                    pygame.draw.circle(surf, (58, 20, 22), (cx, cy), 18)
        if dopo > 0:
            from . import theme as T
            q = dopo / self.via
            dim = int(64 + 26 * esce(min(1.0, dopo / 0.25)))
            a = 1.0 - max(0.0, (q - 0.6) / 0.4)
            img = T.render("VIA!", dim, (255, 255, 255), bold=True)
            img.set_alpha(int(255 * max(0.0, a)))
            c = (r.centerx, r.y + r.h // 3)
            splendi(surf, c, int(dim * 2.2), (0, 200, 255), 0.35 * a)
            surf.blit(img, img.get_rect(center=c))


# ------------------------------------------------------------------ il traguardo
def scacchi(surf, rect, lato: int = 14, scorre: float = 0.0) -> None:
    """Una fascia a scacchi, che puo' scorrere come una bandiera sventolata."""
    r = pygame.Rect(rect)
    prima = surf.get_clip()
    surf.set_clip(r.clip(prima) if prima else r)
    off = int(scorre) % (2 * lato)
    for i, x in enumerate(range(r.x - 2 * lato + off, r.right + lato, lato)):
        onda = int(3 * math.sin(x * 0.03 + ora() * 6))
        for j, y in enumerate(range(r.y, r.bottom, lato)):
            if (i + j) % 2 == 0:
                pygame.draw.rect(surf, (245, 245, 245), (x, y + onda, lato, lato))
            else:
                pygame.draw.rect(surf, (14, 14, 16), (x, y + onda, lato, lato))
    surf.set_clip(prima)


class Traguardo:
    """La bandiera a scacchi: la fascia che entra, il nome del vincitore, e
    se abbiamo fatto podio, i coriandoli."""

    DURATA = 6.5

    def __init__(self, titolo: str, sotto: str = "", festa: bool = False,
                 colore=(0, 200, 255), seme: int = 0):
        self.titolo = titolo
        self.sotto = sotto
        self.colore = colore
        self.t = 0.0
        self.festa = festa
        self.coriandoli = None
        self._seme = seme

    @property
    def finito(self) -> bool:
        return self.t >= self.DURATA

    def update(self, dt: float) -> None:
        if self.t == 0.0:
            audio.suona("fanfara", 0.7)
            audio.suona("applausi", 0.9 if self.festa else 0.5)
        self.t += dt
        if self.coriandoli:
            self.coriandoli.update(dt)

    def draw(self, surf, rect) -> None:
        if self.finito:
            return
        from . import theme as T
        r = pygame.Rect(rect)
        if self.festa and self.coriandoli is None:
            self.coriandoli = Coriandoli(r.w, r.h, 220, seme=self._seme)
        entra = esce(min(1.0, self.t / 0.45))
        via = dolce(max(0.0, (self.t - (self.DURATA - 0.6)) / 0.6))
        alta = 132
        fascia = pygame.Rect(r.x, r.y + r.h // 2 - alta // 2, r.w, alta)
        fascia.x += int((1.0 - entra) * -r.w) + int(via * r.w)
        velo = pygame.Surface(fascia.size, pygame.SRCALPHA)
        velo.fill((6, 8, 13, 225))
        surf.blit(velo, fascia.topleft)
        scacchi(surf, (fascia.x, fascia.y, fascia.w, 24), 12, self.t * 40)
        scacchi(surf, (fascia.x, fascia.bottom - 24, fascia.w, 24), 12, -self.t * 40)
        c = (fascia.centerx, fascia.centery - 12)
        splendi(surf, c, 260, self.colore, 0.22)
        img = T.render(self.titolo, 40, (255, 255, 255), bold=True)
        surf.blit(img, img.get_rect(center=c))
        if self.sotto:
            img = T.render(self.sotto, 16, (210, 220, 235))
            surf.blit(img, img.get_rect(center=(fascia.centerx, fascia.centery + 26)))
        if self.coriandoli:
            self.coriandoli.draw(surf, r.topleft)


# ------------------------------------------------------------------ il passaggio
class Passaggio:
    """Da una schermata all'altra: una lama del colore della squadra passa e
    si porta via quella vecchia."""

    DURATA = 0.42

    def __init__(self, vecchia: pygame.Surface, colore):
        self.vecchia = vecchia
        self.colore = colore
        self.t = 0.0

    @property
    def finito(self) -> bool:
        return self.t >= self.DURATA

    def update(self, dt: float) -> None:
        self.t += min(dt, 0.05)

    def draw(self, surf) -> None:
        if self.finito:
            return
        w, h = surf.get_size()
        q = dolce(self.t / self.DURATA)
        pendenza = int(h * 0.28)
        bordo = int(-pendenza + (w + 2 * pendenza) * q)
        # la schermata vecchia resta a destra del bordo
        if bordo < w:
            x0 = max(0, bordo)
            surf.blit(self.vecchia, (x0, 0), pygame.Rect(x0, 0, w - x0, h))
            # il triangolo che fa il bordo obliquo
            maschera = pygame.Surface((pendenza + 2, h), pygame.SRCALPHA)
            pygame.draw.polygon(maschera, (255, 255, 255, 255),
                                [(0, 0), (pendenza, 0), (0, h)])
            pezzo = pygame.Surface((pendenza + 2, h), pygame.SRCALPHA)
            pezzo.blit(self.vecchia, (0, 0), pygame.Rect(bordo, 0, pendenza + 2, h))
            pezzo.blit(maschera, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(pezzo, (bordo, 0))
        # la lama: del colore della squadra, con un filo bianco davanti
        spessa = 34
        lama = [(bordo - spessa + pendenza, 0), (bordo + pendenza, 0),
                (bordo, h), (bordo - spessa, h)]
        pygame.draw.polygon(surf, self.colore, lama)
        pygame.draw.line(surf, (255, 255, 255), (bordo + pendenza, 0), (bordo, h), 3)
