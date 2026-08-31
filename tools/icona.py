"""Disegna l'icona del gioco e la scrive in assets/apex.ico.

    python tools/icona.py

Un eseguibile senza icona si presenta con quella generica di Windows, che e'
il modo piu' rapido di sembrare un programma di dubbia provenienza. L'icona
serve, e come le bandiere la si disegna invece di trascinarsela dietro come
file misterioso: cosi' si puo' cambiare, e si vede da dove viene.

Il disegno e' una curva con la sua corda - l'apice, che e' il punto in cui una
monoposto tocca l'interno della curva ed e' anche il nome del gioco - su un
fondo scuro come quello delle schermate.

Il formato .ico e' un contenitore: un'intestazione, un indice, e dentro le
immagini a piu' misure. Da Windows Vista in poi quelle immagini possono essere
PNG, che e' quello che si fa qui - niente librerie in piu', pygame sa gia'
scrivere PNG.
"""
from __future__ import annotations

import math
import struct
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os                                            # noqa: E402
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame                                        # noqa: E402

MISURE = (256, 128, 64, 48, 32, 16)
FONDO = (13, 17, 26)
ASFALTO = (52, 63, 82)
APICE = (0, 200, 255)
CORDOLO = (226, 72, 77)


def disegna(lato: int) -> pygame.Surface:
    """L'icona a una data misura. Tutto in centesimi del lato, cosi' scala.

    Il disegno e' un tornante visto dall'alto, con lo stesso vocabolario dei
    circuiti del gioco: il nastro d'asfalto, il bordo piu' chiaro, e il cordolo
    rosso all'interno della curva - che e' l'apice, il punto in cui la
    monoposto tocca la corda, ed e' da li' che il gioco prende il nome.
    """
    img = pygame.Surface((lato, lato), pygame.SRCALPHA)
    pygame.draw.rect(img, FONDO, (0, 0, lato, lato), border_radius=int(lato * 0.18))
    u = lato / 100.0
    largo = max(3, int(15 * u))

    cx, cy, raggio = 56.0, 52.0, 26.0
    punti = [(26.0, 14.0)]
    for i in range(25):
        a = math.pi * (1.0 - 0.5 * i / 24)          # da 180 a 90 gradi
        punti.append((cx + raggio * math.cos(a), cy + raggio * math.sin(a)))
    punti.append((90.0, 78.0))
    tracciato = [(x * u, y * u) for x, y in punti]

    pygame.draw.lines(img, ASFALTO, False, tracciato, largo + max(2, int(5 * u)))
    pygame.draw.lines(img, APICE, False, tracciato, largo)
    for capo in (tracciato[0], tracciato[-1]):
        pygame.draw.circle(img, APICE, (int(capo[0]), int(capo[1])), largo // 2)

    # il cordolo: un arco corto all'interno della curva, dove si tocca
    dentro = []
    for i in range(9):
        a = math.pi * (0.86 - 0.36 * i / 8)
        r = raggio - largo / u * 0.62
        dentro.append(((cx + r * math.cos(a)) * u, (cy + r * math.sin(a)) * u))
    if lato >= 32:
        pygame.draw.lines(img, CORDOLO, False, dentro, max(2, int(6 * u)))
    else:
        m = dentro[len(dentro) // 2]
        pygame.draw.circle(img, CORDOLO, (int(m[0]), int(m[1])), max(2, int(7 * u)))
    return img


def png(img: pygame.Surface) -> bytes:
    buf = BytesIO()
    pygame.image.save(img, buf, "icona.png")
    return buf.getvalue()


def scrivi(dove: Path) -> None:
    pygame.init()
    immagini = [png(disegna(m)) for m in MISURE]
    testa = struct.pack("<HHH", 0, 1, len(MISURE))
    offset = len(testa) + 16 * len(MISURE)
    indice, corpo = b"", b""
    for m, dati in zip(MISURE, immagini):
        indice += struct.pack("<BBBBHHII", m % 256, m % 256, 0, 0, 1, 32,
                              len(dati), offset)
        offset += len(dati)
        corpo += dati
    dove.parent.mkdir(parents=True, exist_ok=True)
    dove.write_bytes(testa + indice + corpo)
    print(f"scritta {dove.relative_to(ROOT)}: {len(MISURE)} misure, "
          f"{len(testa + indice + corpo) / 1024:.1f} kB")
    # e una copia in PNG grande, che serve al README e alle schede del gioco
    grande = ROOT / "assets" / "apex.png"
    pygame.image.save(disegna(512), str(grande))
    print(f"scritta {grande.relative_to(ROOT)}")


if __name__ == "__main__":
    scrivi(ROOT / "assets" / "apex.ico")
