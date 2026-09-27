"""Le risorse fotografiche della vista 3D: materiali e cieli.

Le scarica `tools/fetch_grafica.py` (Poly Haven, licenza CC0) in `grafica/`:

  * `grafica/materiali/<nome>/colore.jpg, normale.jpg, ruvidita.jpg` - un
    materiale per ogni superficie che la vista 3D sa dipingere;
  * `grafica/cieli/<nome>.hdr` - foto a 360 gradi ad alta gamma dinamica.

Qui si caricano sulla scheda video. Se un file manca - un sorgente senza la
cartella, un materiale che Poly Haven non ha - quello strato resta vuoto e il
pittore della vista 3D dipinge come prima, con il calcolo.

I cieli sono in formato Radiance (.hdr): pixel RGBE, righe compresse a
corse. Il formato e' vecchio e semplice, e leggerlo qui evita di portarsi
dietro una libreria intera per un file solo.
"""
from __future__ import annotations

import math
from pathlib import Path

import pygame

from .. import config as C

# L'ordine degli strati nelle tele dei materiali: lo stesso che usa il pittore
# della vista 3D (vista3d._FS_MONDO, `strato`)
MATERIALI = ("asfalto", "prato", "ghiaia", "sabbia", "cemento", "terra")
# Quanti metri copre una ripetizione del materiale sul terreno. Poly Haven
# fotografa di solito due o tre metri quadri: l'asfalto si ripete fitto, il
# prato e la terra si vedono da piu' lontano e reggono una scala piu' larga.
METRI = {"asfalto": 3.0, "prato": 4.0, "ghiaia": 2.5, "sabbia": 4.0, "cemento": 3.0,
         "terra": 4.0}
CIELI = ("sereno", "nuvoloso", "coperto", "tramonto")


def cartella() -> Path:
    return Path(C.GRAFICA)


def disponibili() -> dict:
    """Cosa c'e' su disco: {'materiali': [...], 'cieli': [...]}."""
    base = cartella()
    return {"materiali": [m for m in MATERIALI
                          if (base / "materiali" / m / "colore.jpg").exists()],
            "cieli": [c for c in CIELI if (base / "cieli" / f"{c}.hdr").exists()]}


# ------------------------------------------------------------------ materiali
def _immagine(percorso: Path, lato: int, canali: int, neutro: tuple) -> bytes:
    """I byte di un'immagine quadrata `lato` x `lato`, o del colore neutro."""
    try:
        img = pygame.image.load(str(percorso))
        if img.get_size() != (lato, lato):
            img = pygame.transform.smoothscale(img.convert(24) if img.get_bitsize() < 24
                                               else img, (lato, lato))
        dati = pygame.image.tobytes(img, "RGB")
        if canali == 1:
            dati = dati[0::3]
        return dati
    except Exception:
        return bytes(neutro) * (lato * lato)


def dati_materiali(lato: int) -> dict | None:
    """I materiali letti da disco, pronti per la scheda video: le tre tele
    (colore, rilievo, ruvidita') come byte, uno strato dopo l'altro, alla misura
    `lato`; e per ogni strato il colore medio, se c'e', e quanti metri copre.
    None se non c'e' nessun materiale su disco."""
    base = cartella()
    presenti = [(base / "materiali" / m / "colore.jpg").exists() for m in MATERIALI]
    if not any(presenti):
        return None
    colore, normale, ruvido, medie = [], [], [], []
    for m, c in zip(MATERIALI, presenti):
        d = base / "materiali" / m
        col = _immagine(d / "colore.jpg", lato, 3, (128, 128, 128)) if c else \
            bytes((128, 128, 128)) * (lato * lato)
        colore.append(col)
        normale.append(_immagine(d / "normale.jpg", lato, 3, (128, 128, 255)))
        ruvido.append(_immagine(d / "ruvidita.jpg", lato, 1, (200,)))
        # il colore medio, per ritingere la foto con la tinta che il pittore
        # vuole: la foto porta il dettaglio, il pittore il colore
        passo = max(1, len(col) // 3 // 4096) * 3
        campione = col[::passo]
        tot = [sum(campione[k::3]) for k in range(3)]
        cnt = max(1, len(campione) // 3)
        medie.append(tuple(max(1.0, t / cnt) / 255.0 for t in tot))
    # quanti metri copre una ripetizione: Poly Haven lo scrive (in millimetri)
    # per ogni foto; dove manca, la stima di METRI
    metri = dict(METRI)
    try:
        import json
        elenco = json.loads((base / "elenco.json").read_text(encoding="utf-8"))
        for m, voce in (elenco.get("materiali") or {}).items():
            misura = voce.get("misura")
            if m in metri and misura:
                metri[m] = max(0.5, float(misura[0]) / 1000.0)
    except Exception:
        pass
    return {"colore": b"".join(colore), "normale": b"".join(normale),
            "ruvidita": b"".join(ruvido), "lato": lato, "strati": len(MATERIALI),
            "medie": medie, "presenti": presenti, "metri": [metri[m] for m in MATERIALI]}


def carica_materiali(ctx, lato: int):
    """Le tre tele dei materiali sulla scheda video (moderngl), con le mipmap."""
    import moderngl
    d = dati_materiali(lato)
    if d is None:
        return None
    n = d["strati"]
    tele = []
    for chiave, comp in (("colore", 3), ("normale", 3), ("ruvidita", 1)):
        t = ctx.texture_array((lato, lato, n), comp, data=d[chiave])
        t.build_mipmaps()
        t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        t.repeat_x = t.repeat_y = True
        try:
            t.anisotropy = 8.0
        except Exception:
            pass
        tele.append(t)
    return {"colore": tele[0], "normale": tele[1], "ruvidita": tele[2],
            "medie": d["medie"], "presenti": d["presenti"], "metri": d["metri"]}


# ---------------------------------------------------------------------- cieli
def leggi_hdr(percorso: Path):
    """Un file Radiance .hdr come array numpy (altezza, larghezza, 3) float32."""
    import numpy as np
    dati = Path(percorso).read_bytes()
    # l'intestazione: righe di testo fino a una vuota, poi la risoluzione
    fine = dati.index(b"\n\n")
    pos = fine + 2
    riga_fine = dati.index(b"\n", pos)
    ris = dati[pos:riga_fine].decode("ascii").split()
    pos = riga_fine + 1
    h, w = int(ris[1]), int(ris[3])
    buf = np.frombuffer(dati, dtype=np.uint8)
    out = np.empty((h, w, 4), dtype=np.uint8)
    for y in range(h):
        if w < 8 or w > 0x7fff or buf[pos] != 2 or buf[pos + 1] != 2 or buf[pos + 2] & 0x80:
            # righe non compresse
            out[y] = buf[pos:pos + w * 4].reshape(w, 4)
            pos += w * 4
            continue
        pos += 4
        for c in range(4):
            x = 0
            riga = out[y, :, c]
            while x < w:
                n = int(buf[pos])
                pos += 1
                if n > 128:
                    n -= 128
                    riga[x:x + n] = buf[pos]
                    pos += 1
                else:
                    riga[x:x + n] = buf[pos:pos + n]
                    pos += n
                x += n
    esp = out[:, :, 3].astype(np.int32)
    scala = np.where(esp > 0, np.ldexp(1.0, esp - 136), 0.0).astype(np.float32)
    return out[:, :, :3].astype(np.float32) * scala[:, :, None]


def direzione(u: float, v: float) -> tuple:
    """Da coordinate della foto a 360 gradi (0-1) alla direzione nel mondo.
    La stessa convenzione del pittore del cielo in vista3d."""
    phi = (u - 0.5) * 2.0 * math.pi
    theta = v * math.pi
    return (math.sin(theta) * math.sin(phi), math.cos(theta), -math.sin(theta) * math.cos(phi))


def dati_cielo(nome: str, larghezza: int):
    """Il cielo `nome` letto da disco, largo `larghezza` pixel, gia' esposto
    (numpy float32, altezza x larghezza x 3), e quello che se ne ricava per
    illuminare il resto: dov'e' il sole e di che colore, la luce media del
    cielo e del terreno, il colore dell'orizzonte. None se il file non c'e'
    o non si legge."""
    import numpy as np
    percorso = cartella() / "cieli" / f"{nome}.hdr"
    if not percorso.exists():
        return None
    try:
        img = leggi_hdr(percorso)
    except Exception:
        return None
    h, w = img.shape[:2]
    # si rimpicciolisce a blocchi, se serve: e' una media, niente di piu'
    passo = max(1, w // max(64, larghezza))
    if passo > 1:
        hh, ww = h // passo, w // passo
        img = img[:hh * passo, :ww * passo].reshape(hh, passo, ww, passo, 3).mean(axis=(1, 3))
        h, w = hh, ww
    lum = img @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    # il sole: il punto piu' luminoso della meta' alta
    alto = lum[: h // 2]
    y, x = np.unravel_index(int(np.argmax(alto)), alto.shape)
    sole = direzione((x + 0.5) / w, (y + 0.5) / h)
    picco = float(alto[y, x])
    # la luce del cielo si misura senza il sole: il sole e' migliaia di volte
    # piu' luminoso di tutto il resto, e una media col sole dentro direbbe che
    # il cielo e' buio. Si tagliano i punti oltre il 99esimo percentile
    tetto = float(np.percentile(lum[: h // 2], 99.0))
    fattore = np.minimum(1.0, tetto / np.maximum(lum, 1e-6))[:, :, None]
    tagliata = img * fattore
    cielo_medio = tagliata[: h // 2].reshape(-1, 3).mean(axis=0)
    terra_media = tagliata[h // 2:].reshape(-1, 3).mean(axis=0)
    fascia = tagliata[int(h * 0.42): int(h * 0.5)].reshape(-1, 3).mean(axis=0)
    mediana = float(np.median(lum[: h // 2]))
    netto = picco / max(1e-4, mediana)
    # l'esposizione: il cielo tipico - la mediana - attorno a 0.62, che e' la
    # luce che il resto della scena si aspetta
    esp = 0.62 / max(1e-4, mediana)
    colore_sole = tuple(float(v) for v in img[y, x] / max(1e-4, picco))
    forza = max(0.0, min(1.0, (math.log10(max(1.0, netto)) - 1.0) / 2.0))
    # il sole va oltre quello che un numero a mezza precisione tiene: si ferma prima
    esposta = np.ascontiguousarray(np.minimum(img * esp, 60000.0).astype(np.float32))
    return {"img": esposta, "misura": (w, h), "sole": sole, "forza_sole": forza,
            "colore_sole": colore_sole,
            "amb_cielo": tuple(float(v) * esp for v in cielo_medio),
            "amb_terra": tuple(float(v) * esp for v in terra_media),
            "orizzonte": tuple(float(v) * esp for v in fascia),
            "esposizione": esp}


def carica_cielo(ctx, nome: str, larghezza: int):
    """Il cielo `nome` sulla scheda video (moderngl), con quello che se ne
    ricava per la luce (vedi `dati_cielo`)."""
    import moderngl
    d = dati_cielo(nome, larghezza)
    if d is None:
        return None
    tex = ctx.texture(d["misura"], 3, data=d["img"].astype("f2").tobytes(), dtype="f2")
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = True
    tex.repeat_y = False
    fuori = dict(d)
    del fuori["img"]
    fuori["tex"] = tex
    return fuori
