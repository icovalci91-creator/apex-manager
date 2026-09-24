"""I comandi del suono, uguali nel menu iniziale e in quello della partita:
il volume (un clic lo abbassa di un gradino, dopo il silenzio torna al
massimo), la musica e gli effetti."""
from __future__ import annotations

from . import audio
from .widgets import Button, Toggle

GRADINI = (1.0, 0.8, 0.6, 0.4, 0.2, 0.0)


def aggiungi(widgets: list, x: int, y: int, largo: int, rifai) -> bool:
    """Mette la riga dei comandi in (x, y), larga `largo`. `rifai` ricostruisce
    la schermata dopo un cambio. False se il suono non c'e' (browser, niente
    scheda audio): allora non si mette niente."""
    if not audio.disponibile():
        return False
    imp = audio.IMPOSTAZIONI
    volume = 0 if imp["muto"] else int(round(imp["volume"] * 100))
    terzo = (largo - 12) // 3

    def abbassa():
        attuale = 0.0 if imp["muto"] else imp["volume"]
        dopo = next((g for g in GRADINI if g < attuale - 0.01), GRADINI[0])
        audio.imposta(volume=dopo, muto=False)
        rifai()
    widgets.append(Button((x, y, terzo, 34), f"Volume {volume}%", abbassa, "ghost",
                          tip="Un clic abbassa il volume; Ctrl+M lo toglie e lo rimette"))
    widgets.append(Toggle((x + terzo + 6, y, terzo, 34), "Musica", bool(imp["musica"]),
                          lambda v: (audio.imposta(musica=bool(v)), rifai())))
    widgets.append(Toggle((x + 2 * (terzo + 6), y, terzo, 34), "Effetti", bool(imp["effetti"]),
                          lambda v: (audio.imposta(effetti=bool(v)), rifai())))
    return True
