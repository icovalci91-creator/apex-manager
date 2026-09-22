"""Scarica da OpenStreetMap quello che c'e' attorno a ogni circuito.

    python tools/fetch_dintorni.py                       # quelli che non ce l'hanno
    python tools/fetch_dintorni.py --only monaco spa
    python tools/fetch_dintorni.py --force               # riscarica anche quelli fatti
    python tools/fetch_dintorni.py --dry-run             # scarica e conta, non scrive
    python tools/fetch_dintorni.py --only monaco --da-file risposta.json

La vista 3D delle sessioni disegna il circuito vero - tracciato, dislivelli,
corsia box - ma quello che gli sta attorno lo inventa: campi, boschi, isolati
credibili ma non quelli veri. Questo strumento va a prendere i dintorni veri e
li scrive in `dintorni/<circuito>.json.gz`, uno per circuito:

  * l'acqua: laghi, porti, fiumi, e la linea di costa per capire dov'e' il mare;
  * i boschi, i parchi e i prati, i campi coltivati;
  * le zone costruite (residenziali, industriali, commerciali) e i palazzi,
    ognuno con la sua altezza quando la mappa la conosce;
  * le strade, le ferrovie e i parcheggi.

Quando il file c'e', il gioco usa quello; quando manca, resta l'ambiente
inventato di prima. Non serve scaricarli tutti: si puo' cominciare da uno.

**Da dove vengono.** Dall'API Overpass di OpenStreetMap, gratuita e senza
chiave: una richiesta per circuito, con una pausa fra una e l'altra perche' il
servizio e' condiviso e chi lo tempesta viene rallentato. Se il primo server
e' occupato si prova il successivo.

**La licenza.** I dati di OpenStreetMap sono sotto licenza ODbL: si possono
usare e ridistribuire, anche dentro al gioco, a patto di citare la fonte
("(c) OpenStreetMap contributors"). Il gioco lo scrive sulla vista 3D quando
li usa, e ogni file se lo porta scritto dentro.

**Cosa si salva.** Solo le forme, semplificate a un paio di metri, con le
coordinate in milionesimi di grado dall'angolo del riquadro: un circuito in
campagna pesa qualche centinaio di kilobyte, uno in citta' un paio di mega.
Non serve installare niente oltre a Python.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "data" / "tracks.json"
USCITA = ROOT / "dintorni"

UA = "ApexManager/0.1 (gestionale F1 open source; dintorni dei circuiti)"
SERVER = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
PAUSA = 8.0                  # secondi fra un circuito e l'altro
MARGINE_M = 1400.0           # quanto oltre il tracciato si guarda, almeno
SCALA = 1e-6                 # le coordinate si salvano in milionesimi di grado
VERSIONE = 1

# Le strade, con la larghezza con cui si disegnano (in metri)
STRADE = {
    "motorway": 18, "trunk": 14, "primary": 11, "secondary": 9, "tertiary": 8,
    "unclassified": 6, "residential": 6, "living_street": 5, "service": 4,
    "motorway_link": 8, "trunk_link": 7, "primary_link": 7, "secondary_link": 6,
}

QUERY = """[out:json][timeout:240];
(
  way["building"]({b});
  relation["building"]["type"="multipolygon"]({b});
  way["natural"~"^(water|wood|sand|beach|scrub|grassland|heath|wetland)$"]({b});
  relation["natural"~"^(water|wood|sand|beach|scrub|grassland)$"]({b});
  way["water"]({b});
  way["landuse"~"^(forest|farmland|farmyard|meadow|grass|orchard|vineyard|allotments|recreation_ground|village_green|cemetery|residential|commercial|industrial|retail|construction|brownfield|railway|reservoir|basin)$"]({b});
  relation["landuse"~"^(forest|farmland|meadow|grass|orchard|vineyard|residential|commercial|industrial|retail|reservoir|basin)$"]({b});
  way["leisure"~"^(park|garden|golf_course|pitch|marina|nature_reserve)$"]({b});
  relation["leisure"~"^(park|golf_course|nature_reserve)$"]({b});
  way["amenity"="parking"]({b});
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|motorway_link|trunk_link|primary_link|secondary_link)$"]({b});
  way["railway"~"^(rail|light_rail|tram|narrow_gauge)$"]({b});
  way["waterway"~"^(river|canal|riverbank)$"]({b});
  way["natural"="coastline"]({b});
);
out geom qt;
"""


# ------------------------------------------------------------ classificazione
def area_di(tag: dict) -> str | None:
    """In quale famiglia cade un'area, dai suoi tag. None: non interessa."""
    nat, land, leis = tag.get("natural"), tag.get("landuse"), tag.get("leisure")
    if (nat == "water" or "water" in tag or land in ("reservoir", "basin")
            or leis == "marina" or tag.get("waterway") == "riverbank"):
        return "acqua"
    if land == "forest" or nat == "wood":
        return "bosco"
    if nat in ("sand", "beach"):
        return "sabbia"
    if land in ("farmland", "farmyard", "orchard", "vineyard"):
        return "campi"
    if (leis in ("park", "garden", "golf_course", "pitch", "nature_reserve")
            or land in ("meadow", "grass", "allotments", "recreation_ground",
                        "village_green", "cemetery")
            or nat in ("scrub", "grassland", "heath", "wetland")):
        return "verde"
    if land in ("residential", "commercial", "industrial", "retail", "construction",
                "brownfield", "railway"):
        return "urbano"
    if tag.get("amenity") == "parking":
        return "parcheggi"
    return None


def altezza(tag: dict) -> float:
    """Quanto e' alto un palazzo: quello che dice la mappa, o una stima dal tipo."""
    for chiave in ("height", "building:height"):
        v = tag.get(chiave)
        if v:
            try:
                return max(2.5, min(400.0, float(v.lower().replace("m", "").strip())))
            except ValueError:
                pass
    livelli = tag.get("building:levels")
    if livelli:
        try:
            return max(2.5, min(400.0, float(livelli) * 3.2 + 1.0))
        except ValueError:
            pass
    tipo = tag.get("building", "yes")
    return {"house": 7, "detached": 7, "garage": 3, "garages": 3, "shed": 3,
            "hut": 3, "roof": 5, "apartments": 16, "residential": 12, "hotel": 22,
            "office": 20, "commercial": 12, "retail": 8, "industrial": 10,
            "warehouse": 10, "church": 16, "grandstand": 12, "stadium": 22,
            "hangar": 12}.get(tipo, 9)


# -------------------------------------------------------------- geometria
class Piano:
    """Gradi in metri, attorno a un punto: per semplificare le forme."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.mx = 111320.0 * math.cos(math.radians(lat0))

    def m(self, lat: float, lon: float) -> tuple:
        return ((lon - self.lon0) * self.mx, (lat - self.lat0) * 110540.0)


def semplifica(punti: list, piano: Piano, tolleranza: float) -> list:
    """Douglas-Peucker: toglie i punti che spostano la linea meno di `tolleranza` metri."""
    if len(punti) < 3:
        return punti
    m = [piano.m(*p) for p in punti]
    if punti[0] == punti[-1]:
        # un anello chiuso: il primo e l'ultimo punto coincidono e non fanno
        # un segmento. Lo si spezza nel punto piu' lontano dall'inizio e si
        # semplificano le due meta'
        lontano = max(range(1, len(punti) - 1),
                      key=lambda i: (m[i][0] - m[0][0]) ** 2 + (m[i][1] - m[0][1]) ** 2)
        prima = semplifica(punti[:lontano + 1], piano, tolleranza)
        dopo = semplifica(punti[lontano:], piano, tolleranza)
        return prima + dopo[1:]
    tieni = [False] * len(punti)
    tieni[0] = tieni[-1] = True
    pila = [(0, len(punti) - 1)]
    while pila:
        a, b = pila.pop()
        ax, ay = m[a]
        bx, by = m[b]
        dx, dy = bx - ax, by - ay
        lung = math.hypot(dx, dy) or 1e-9
        peggio, dove = 0.0, -1
        for i in range(a + 1, b):
            px, py = m[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / lung
            if d > peggio:
                peggio, dove = d, i
        if peggio > tolleranza and dove > 0:
            tieni[dove] = True
            pila.append((a, dove))
            pila.append((dove, b))
    return [p for p, k in zip(punti, tieni) if k]


def unisci_anelli(pezzi: list) -> list:
    """Le parti esterne di una relazione, cucite in anelli chiusi.

    Un lago grande o un bosco in OpenStreetMap e' spesso fatto di tante linee
    che si toccano agli estremi: qui le si mette in fila finche' si chiudono.
    Quello che non si chiude si lascia perdere.
    """
    pezzi = [list(p) for p in pezzi if len(p) >= 2]
    anelli = []
    while pezzi:
        anello = pezzi.pop()
        cambiato = True
        while anello[0] != anello[-1] and cambiato:
            cambiato = False
            for i, p in enumerate(pezzi):
                if p[0] == anello[-1]:
                    anello += p[1:]
                elif p[-1] == anello[-1]:
                    anello += p[::-1][1:]
                elif p[-1] == anello[0]:
                    anello = p[:-1] + anello
                elif p[0] == anello[0]:
                    anello = p[::-1][:-1] + anello
                else:
                    continue
                pezzi.pop(i)
                cambiato = True
                break
        if anello[0] == anello[-1] and len(anello) >= 4:
            anelli.append(anello)
    return anelli


def _geo(elemento) -> list:
    return [(round(g["lat"], 7), round(g["lon"], 7)) for g in elemento.get("geometry") or []
            if g is not None]


def elabora(risposta: dict, bbox: tuple) -> dict:
    """Dalla risposta di Overpass al file del gioco."""
    s, w, n, e = bbox
    piano = Piano((s + n) / 2, (w + e) / 2)
    uscita = {k: [] for k in ("acqua", "bosco", "verde", "campi", "urbano", "sabbia",
                              "parcheggi", "edifici", "strade", "ferrovie", "fiumi", "costa")}

    def codifica(punti):
        piatti = []
        for lat, lon in punti:
            piatti += [round((lat - s) / SCALA), round((lon - w) / SCALA)]
        return piatti

    for el in risposta.get("elements", []):
        tag = el.get("tags") or {}
        if el["type"] == "way":
            punti = _geo(el)
            if len(punti) < 2:
                continue
            chiuso = len(punti) >= 4 and punti[0] == punti[-1]
            if tag.get("natural") == "coastline":
                uscita["costa"].append(codifica(semplifica(punti, piano, 3.0)))
                continue
            if tag.get("building") and tag.get("building") != "no" and chiuso:
                p = semplifica(punti, piano, 1.0)
                if len(p) >= 4:
                    uscita["edifici"].append({"p": codifica(p[:-1]), "h": round(altezza(tag), 1)})
                continue
            if tag.get("highway") in STRADE and not chiuso:
                uscita["strade"].append({"l": codifica(semplifica(punti, piano, 2.0)),
                                         "w": STRADE[tag["highway"]]})
                continue
            if tag.get("railway"):
                uscita["ferrovie"].append(codifica(semplifica(punti, piano, 2.0)))
                continue
            if tag.get("waterway") in ("river", "canal") and not chiuso:
                largo = float(tag.get("width", 0) or 0) if tag.get("width", "").replace(".", "").isdigit() else 0
                uscita["fiumi"].append({"l": codifica(semplifica(punti, piano, 3.0)),
                                        "w": largo or (30 if tag["waterway"] == "river" else 14)})
                continue
            fam = area_di(tag)
            if fam and chiuso:
                uscita[fam].append(codifica(semplifica(punti, piano, 2.5)))
        elif el["type"] == "relation":
            fuori = [_geo(m) for m in el.get("members", []) if m.get("role") in ("outer", "")]
            anelli = unisci_anelli(fuori)
            if tag.get("building"):
                for a in anelli:
                    p = semplifica(a, piano, 1.0)
                    if len(p) >= 4:
                        uscita["edifici"].append({"p": codifica(p[:-1]), "h": round(altezza(tag), 1)})
                continue
            fam = area_di(tag)
            if fam:
                for a in anelli:
                    uscita[fam].append(codifica(semplifica(a, piano, 2.5)))
    return uscita


# ---------------------------------------------------------------- download
def scarica(query: str) -> dict:
    """Chiede a Overpass, provando i server uno dopo l'altro."""
    corpo = urllib.parse.urlencode({"data": query}).encode()
    ultimo = None
    for tentativo in range(3):
        for url in SERVER:
            try:
                req = urllib.request.Request(url, data=corpo, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as ex:
                ultimo = f"{url}: HTTP {ex.code}"
                if ex.code not in (429, 502, 503, 504):
                    raise
            except (urllib.error.URLError, OSError, ValueError) as ex:
                ultimo = f"{url}: {ex}"
            print(f"    {ultimo} - provo il prossimo", flush=True)
        attesa = 30 * (tentativo + 1)
        print(f"    tutti occupati, riprovo fra {attesa} secondi", flush=True)
        time.sleep(attesa)
    raise RuntimeError(f"nessun server ha risposto ({ultimo})")


def riquadro(geo: list) -> tuple:
    """Il riquadro da chiedere: il tracciato, piu' un buon margine tutto attorno."""
    lats = [float(p[0]) for p in geo]
    lons = [float(p[1]) for p in geo]
    lat0 = (min(lats) + max(lats)) / 2
    mx = 111320.0 * math.cos(math.radians(lat0))
    alto = (max(lats) - min(lats)) * 110540.0
    largo = (max(lons) - min(lons)) * mx
    margine = max(MARGINE_M, 0.6 * max(alto, largo))
    dlat, dlon = margine / 110540.0, margine / mx
    return (round(min(lats) - dlat, 5), round(min(lons) - dlon, 5),
            round(max(lats) + dlat, 5), round(max(lons) + dlon, 5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", default=None, help="solo questi circuiti")
    ap.add_argument("--force", action="store_true", help="riscarica anche quelli gia' fatti")
    ap.add_argument("--dry-run", action="store_true", help="scarica e conta, non scrive")
    ap.add_argument("--da-file", default=None,
                    help="usa una risposta di Overpass gia' salvata invece di scaricare")
    args = ap.parse_args()

    dati = json.loads(TRACKS.read_text(encoding="utf-8"))
    piste = [t for t in dati.get("tracks", []) if t.get("geo")]
    if args.only:
        piste = [t for t in piste if t["id"] in args.only]
        mancano = set(args.only) - {t["id"] for t in piste}
        if mancano:
            print(f"circuiti sconosciuti o senza coordinate: {', '.join(sorted(mancano))}")
    USCITA.mkdir(exist_ok=True)
    fatti = 0
    for k, t in enumerate(piste):
        dove = USCITA / f"{t['id']}.json.gz"
        if dove.exists() and not args.force and not args.dry_run:
            print(f"{t['id']:<14}gia' scaricato ({dove.stat().st_size // 1024} kB), salto")
            continue
        bbox = riquadro(t["geo"])
        print(f"{t['id']:<14}chiedo {bbox}...", flush=True)
        try:
            if args.da_file:
                risposta = json.loads(Path(args.da_file).read_text(encoding="utf-8"))
            else:
                if fatti:
                    time.sleep(PAUSA)
                risposta = scarica(QUERY.format(b=",".join(str(v) for v in bbox)))
        except Exception as ex:
            print(f"{t['id']:<14}non riuscito: {ex}")
            continue
        fuori = elabora(risposta, bbox)
        fuori.update({
            "versione": VERSIONE,
            "fonte": "(c) OpenStreetMap contributors, ODbL",
            "scaricato": datetime.date.today().isoformat(),
            "origine": [bbox[0], bbox[1]],
            "scala": SCALA,
        })
        testo = json.dumps(fuori, separators=(",", ":")).encode("utf-8")
        conti = ", ".join(f"{len(fuori[c])} {c}" for c in
                          ("edifici", "strade", "acqua", "bosco", "verde", "campi", "urbano")
                          if fuori[c])
        if args.dry_run:
            print(f"{t['id']:<14}{conti or 'niente'} (non scritto)")
        else:
            with gzip.open(dove, "wb", compresslevel=9) as f:
                f.write(testo)
            print(f"{t['id']:<14}{conti or 'niente'} -> {dove.name} "
                  f"({dove.stat().st_size // 1024} kB)")
        fatti += 1
    if not fatti:
        print("niente da fare")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
