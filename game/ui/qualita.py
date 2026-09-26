"""La qualita' grafica della vista 3D: Bassa, Media, Alta, Ultra.

Ogni livello dice quanto lavora la scheda video:

  * `scala3d` - a che frazione della risoluzione si disegna la scena (il
    passaggio finale e le scritte restano sempre a risoluzione piena);
  * `msaa` - quanti campioni per pixel contro i bordi a scalini;
  * `ombre` - quanto e' fine la mappa delle ombre;
  * `texture` - a che misura si caricano i materiali fotografici (0: niente,
    si dipinge con il calcolo come prima);
  * `cielo` - quanto e' larga la foto del cielo (0: il cielo sfumato);
  * `dettaglio` - i modelli dettagliati: le monoposto con le ali a profilo
    vero, i cerchi a razze e le curve morbide (quattro volte i triangoli), e
    attorno alla pista alberi con il tronco, gradinate, box con i garage,
    cartelloni e postazioni dei commissari.

La scelta sta nelle impostazioni video (`hd.IMPOSTAZIONI["qualita"]`); vuota
vuol dire automatica: il gioco guarda che scheda video c'e' e sceglie da
solo - Bassa per le schede senza accelerazione, Media per quelle integrate,
Alta per le altre.
"""
from __future__ import annotations

from . import hd

LIVELLI = ("bassa", "media", "alta", "ultra")
NOMI = {"bassa": "Bassa", "media": "Media", "alta": "Alta", "ultra": "Ultra"}
PRESET = {
    "bassa": dict(scala3d=0.6, msaa=0, ombre=1024, texture=0, cielo=0, dettaglio=False),
    "media": dict(scala3d=0.8, msaa=2, ombre=2048, texture=1024, cielo=1024,
                  dettaglio=False),
    "alta": dict(scala3d=1.0, msaa=4, ombre=2048, texture=2048, cielo=2048,
                 dettaglio=True),
    "ultra": dict(scala3d=1.0, msaa=8, ombre=4096, texture=2048, cielo=2048,
                  dettaglio=True),
}

# Cambia ogni volta che cambia la qualita': la vista 3D la confronta con la sua
# e, se e' diversa, si ricarica con i nuovi materiali e le nuove ombre.
VERSIONE = [0]
_SCHEDA = [""]


def scheda(nome: str) -> None:
    """Il nome della scheda video, detto dalla vista 3D quando si accende."""
    _SCHEDA[0] = str(nome or "")


def automatica() -> str:
    s = _SCHEDA[0].lower()
    if not s or any(k in s for k in ("llvmpipe", "softpipe", "swrast", "basic render",
                                     "gdi generic")):
        return "bassa"
    if any(k in s for k in ("intel", "uhd", "iris", "vega 8", "radeon graphics",
                            "adreno", "mali")):
        return "media"
    return "alta"


def livello() -> str:
    scelta = str(hd.IMPOSTAZIONI.get("qualita") or "")
    return scelta if scelta in PRESET else automatica()


def attuale() -> dict:
    return PRESET[livello()]


def etichetta() -> str:
    scelta = str(hd.IMPOSTAZIONI.get("qualita") or "")
    if scelta in PRESET:
        return f"Grafica 3D: {NOMI[scelta]}"
    return f"Grafica 3D: automatica ({NOMI[automatica()]})"


def prossima() -> None:
    """Passa al livello dopo: automatica, Bassa, Media, Alta, Ultra."""
    giro = [""] + list(LIVELLI)
    ora = str(hd.IMPOSTAZIONI.get("qualita") or "")
    i = giro.index(ora) if ora in giro else 0
    hd.IMPOSTAZIONI["qualita"] = giro[(i + 1) % len(giro)]
    hd.salva()
    VERSIONE[0] += 1
