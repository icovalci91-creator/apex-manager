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


def aggiungi_video(widgets: list, x: int, y: int, largo: int, app, rifai) -> int:
    """Le righe della grafica: la qualita' della vista 3D (un clic passa alla
    prossima: automatica, Bassa, Media, Alta, Ultra) e il motore che la
    disegna (Panda3D o moderngl), poi la scala
    dell'interfaccia e lo schermo intero. Dice quante righe ha messo: una sola
    nel browser, dove la scala e lo schermo intero li decide il browser."""
    from . import hd, qualita, vista3d
    righe = 0
    if vista3d.disponibile():
        def cambia_qualita():
            qualita.prossima()
            rifai()
        largo_q = (largo - 6) * 11 // 20

        def cambia_motore():
            vista3d.prossimo_motore()
            rifai()
        widgets.append(Button((x, y, largo_q, 34), qualita.etichetta(), cambia_qualita, "ghost",
                              tip="Quanto lavora la scheda video nella vista 3D: "
                                  "risoluzione, bordi, ombre, materiali e cielo fotografici"))
        widgets.append(Button((x + largo_q + 6, y, largo - largo_q - 6, 34),
                              vista3d.etichetta_motore(), cambia_motore, "ghost",
                              tip="Chi disegna la vista 3D: Panda3D, il motore, o moderngl, "
                                  "quello di prima. Se Panda3D non si accende si passa "
                                  "da soli a moderngl"))
        righe += 1
        y += 44
    if getattr(app, "display", None) is None:
        return righe
    imp = hd.IMPOSTAZIONI
    scelte = [0.0] + list(hd.SCALE)
    attuale = float(imp.get("scala") or 0.0)
    adesso = getattr(app.screen, "S", 1.0)
    if attuale <= 0:
        etichetta = f"Scala: auto ({adesso * 100:.0f}%)"
    else:
        etichetta = f"Scala: {attuale * 100:.0f}%"

    def prossima():
        i = next((k for k, v in enumerate(scelte) if abs(v - attuale) < 0.01), 0)
        app.cambia_video(scala=scelte[(i + 1) % len(scelte)])
        rifai()
    meta = (largo - 6) // 2
    widgets.append(Button((x, y, meta, 34), etichetta, prossima, "ghost",
                          tip="Quanto sono grandi scritte e pulsanti: il gioco e' "
                              "disegnato alla risoluzione vera dello schermo"))
    widgets.append(Toggle((x + meta + 6, y, meta, 34), "Schermo intero (F11)",
                          bool(imp.get("schermo_intero")),
                          lambda v: (app.cambia_video(schermo_intero=bool(v)), rifai())))
    return righe + 1
