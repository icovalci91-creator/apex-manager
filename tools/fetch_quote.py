"""Scarica il rilievo dei circuiti e lo scrive in data/tracks.json.

    python tools/fetch_quote.py                      # quelli che non ce l'hanno
    python tools/fetch_quote.py --only spa zandvoort
    python tools/fetch_quote.py --fonte copernicus   # forza la fonte
    python tools/fetch_quote.py --dry-run            # guarda senza scrivere

Un circuito non e' piatto, e finora nel modello lo era. Questo strumento va a
prendere la quota lungo il tracciato - un valore ogni venticinque metri, dal
traguardo in avanti - e la scrive nei dati come profilo a passo fisso. Da li'
il modello di giro ricava la pendenza: in salita la gravita' ruba
accelerazione, in discesa allunga le frenate.

**Le fonti, e perche' non sono tutte uguali.**

Servono due cose diverse e la stessa mappa non le da' tutte e due bene:

  * la *pendenza*, che si misura su decine di metri: la da' bene qualunque
    modello del terreno, anche a trenta metri di risoluzione;
  * la *curvatura verticale* - la compressione in fondo a una discesa, il
    dosso in cima a un rettilineo - che e' la derivata seconda della quota e
    per leggerla serve precisione verticale sotto il metro.

La seconda e' quella che sposta davvero il cronometro: a Eau Rouge, a
trecento all'ora su un raggio verticale di trecento metri, sono due g e mezzo
di carico in piu' sulle gomme. Ed e' quella che un modello a trenta metri non
puo' dare: misurato sul Copernicus a Spa, il rumore residuo ha punte di sei
metri e mezzo, che e' quanto la compressione vera. A finestra stretta si
leggono centoquarantadue compressioni inventate, a finestra larga sparisce
anche quella vera.

Da qui l'ordine con cui questo strumento prova le fonti:

  1. **i LIDAR nazionali**, dove ci sono: un metro di risoluzione o meno,
     precisione verticale sotto i dieci centimetri. Con quelli si legge tutto,
     compressioni comprese. Sono aperti e gratuiti;
  2. **Copernicus DEM GLO-30**, aperto, gratuito, mondiale, trenta metri.
     C'e' sempre, e sulla pendenza fa il suo mestiere: a Spa restituisce
     centodue metri e tre di dislivello contro i cento veri.

Dei LIDAR qui dentro c'e' quello statunitense - USGS 3DEP, che risponde a una
coordinata per volta e copre Austin, Miami e Las Vegas. Gli altri tre che
servirebbero non ci sono, e non per dimenticanza: dalla rete su cui questo
strumento e' stato scritto non si raggiungono, quindi scriverne il codice
avrebbe voluto dire consegnare roba che dichiara di funzionare senza che
nessuno l'abbia mai vista funzionare. Sono questi, per chi li ha a portata:

  * **AHN** (Paesi Bassi, mezzo metro) per Zandvoort, via il WCS di PDOK;
  * **LIDAR della Vallonia** (Belgio, un metro) per Spa, via l'ImageServer
    ArcGIS di geoservices.wallonie.be;
  * **Environment Agency** (Regno Unito, un metro) per Silverstone, via WCS.

Tutti e tre servono un raster su riquadro invece che un punto per volta, che
e' lo stesso schema del Copernicus qui sotto: si scarica una volta il pezzo di
mappa attorno al circuito e poi lo si campiona in locale. Aggiungerne uno vuol
dire scrivere una classe con un metodo `quota(lat, lon)`, e infilarla in
`sorgenti()` prima del Copernicus.

Google Maps Elevation non c'e' apposta, e non e' per la qualita': le sue
condizioni d'uso limitano la memorizzazione dei dati e la creazione di insiemi
derivati, e un profilo altimetrico scritto dentro tracks.json e pubblicato e'
esattamente un insieme derivato ridistribuito.

**Cosa serve installato.** numpy, tifffile e imagecodecs, che servono solo a
leggere i GeoTIFF del Copernicus e non sono richiesti dal gioco:

    pip install numpy tifffile imagecodecs
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

TRACKS = ROOT / "data" / "tracks.json"
CACHE = ROOT / "tools" / "_cache" / "dem"

PASSO = 25.0                 # un valore di quota ogni tanti metri di pista

# --------------------------------------------------------- la verifica
# Il Copernicus e' un modello di *superficie*: dentro ci sono i tetti e le
# chiome degli alberi. Su un circuito in mezzo alle colline non cambia niente,
# ma su un cittadino la traiettoria passa fra i palazzi e quello che si
# campiona sono i palazzi: a Las Vegas viene fuori un dislivello di ventidue
# metri contro i cinque veri, a Monza ventidue contro dodici perche' il
# tracciato sta dentro a un parco. E dall'altra parte, su un circuito
# pianeggiante, trenta metri di risoluzione spianano il rilievo vero: Zandvoort
# viene otto metri invece di diciassette.
#
# I due errori non sono la stessa cosa e non si trattano uguale.
#
# Un rilievo *spianato* ha la forma giusta e l'ampiezza piccola - e' quello che
# fa qualunque filtro passa-basso - quindi il profilo resta utilizzabile: le
# salite stanno dove devono stare, sono solo piu' gentili del vero. Un rilievo
# *sporcato dai tetti* ha la forma sbagliata: ci sono salite dove c'e' un
# albergo, e nessun ridimensionamento le toglie.
#
# Da qui la verifica, asimmetrica apposta: si confronta il dislivello scaricato
# con quello pubblicato del circuito, che sta nei dati scritto a mano. Se e'
# piu' basso lo si accetta fino a un bel po' sotto; se e' piu' alto di un
# quinto lo si butta, e quel circuito resta piatto finche' non arriva un
# rilievo vero.
TROPPO_ALTO = 1.20
TROPPO_BASSO = 0.55
UA = "ApexManager/0.1 (gestionale F1 open source; rilievo circuiti)"

# Il Copernicus sta su un bucket pubblico, un file per grado quadrato.
COPERNICUS = ("https://copernicus-dem-30m.s3.amazonaws.com/"
              "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
              "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")

# I LIDAR nazionali, per il pezzo di mondo che coprono. Sono servizi di
# elevazione puntuale: si chiede una coordinata e si riceve una quota. Dove
# rispondono danno la curvatura verticale vera, che il Copernicus non da'.
LIDAR = {
    "3dep": {  # Austin, Miami, Las Vegas - USGS 3DEP, un metro
        "nome": "3dep",
        "url": "https://epqs.nationalmap.gov/v1/json",
        "bbox": (24.0, -125.0, 50.0, -66.0),
    },
}


def _dentro(bbox, lat, lon) -> bool:
    a, b, c, d = bbox
    return a <= lat <= c and b <= lon <= d


# ------------------------------------------------------------- Copernicus
def _tile(lat: float, lon: float) -> str:
    la, lo = math.floor(lat), math.floor(lon)
    return COPERNICUS.format(ns="N" if la >= 0 else "S", lat=abs(la),
                             ew="E" if lo >= 0 else "W", lon=abs(lo))


def _scarica(url: str, dove: Path) -> bool:
    if dove.exists() and dove.stat().st_size > 1000:
        return True
    dove.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r:
            dove.write_bytes(r.read())
        return True
    except (urllib.error.URLError, OSError) as e:
        print(f"   non si scarica {url.rsplit('/', 1)[-1]}: {e}")
        return False


class Copernicus:
    """Il modello mondiale a trenta metri. C'e' sempre, e sulla pendenza basta."""

    nome = "copernicus"

    def __init__(self):
        try:
            import numpy, tifffile          # noqa: F401
            import imagecodecs              # noqa: F401
        except ImportError as e:
            raise SystemExit(
                f"manca {e.name}: per leggere i GeoTIFF del Copernicus servono\n"
                f"    pip install numpy tifffile imagecodecs")
        self._tiles: dict = {}

    def _apri(self, lat: float, lon: float):
        import tifffile
        chiave = (math.floor(lat), math.floor(lon))
        if chiave in self._tiles:
            return self._tiles[chiave]
        url = _tile(lat, lon)
        f = CACHE / url.rsplit("/", 1)[-1]
        if not _scarica(url, f):
            self._tiles[chiave] = None
            return None
        p = tifffile.TiffFile(f).pages[0]
        dati = p.asarray()
        tie = p.tags["ModelTiepointTag"].value
        sca = p.tags["ModelPixelScaleTag"].value
        self._tiles[chiave] = (dati, tie[3], tie[4], sca[0], sca[1])
        return self._tiles[chiave]

    def quota(self, lat: float, lon: float):
        t = self._apri(lat, lon)
        if t is None:
            return None
        dem, lon0, lat0, dlon, dlat = t
        fx, fy = (lon - lon0) / dlon, (lat0 - lat) / dlat
        x0, y0 = int(fx), int(fy)
        h, w = dem.shape
        if not (0 <= x0 < w - 1 and 0 <= y0 < h - 1):
            return None
        ax, ay = fx - x0, fy - y0
        return float(dem[y0, x0] * (1 - ax) * (1 - ay) + dem[y0, x0 + 1] * ax * (1 - ay)
                     + dem[y0 + 1, x0] * (1 - ax) * ay + dem[y0 + 1, x0 + 1] * ax * ay)


class Lidar:
    """I rilievi nazionali, uno a punto. Dove rispondono sono un'altra cosa."""

    def __init__(self, chiave: str):
        self.chiave = chiave
        self.nome = chiave
        self.info = LIDAR[chiave]
        self.morto = False

    def copre(self, lat: float, lon: float) -> bool:
        return _dentro(self.info["bbox"], lat, lon)

    def quota(self, lat: float, lon: float):
        """La quota di un punto. Se il servizio non risponde, lo si abbandona.

        Un circuito sono trecento richieste: se la prima va male non ha senso
        provare le altre duecentonovantanove. Si segna la fonte come morta e si
        passa a quella dopo, che e' sempre disponibile.
        """
        if self.morto:
            return None
        try:
            url = (f"{self.info['url']}?x={lon}&y={lat}"
                   f"&units=Meters&wkid=4326&includeDate=false")
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8"))
            v = float(d.get("value"))
            return None if v < -1000 else v
        except Exception as e:
            print(f"   {self.info['nome']} non risponde ({e}): passo al resto")
            self.morto = True
            return None


def sorgenti(scelta: str | None) -> list:
    """Le fonti da provare, nell'ordine: prima le fini, poi quella che c'e' sempre."""
    out = []
    if scelta in (None, "lidar"):
        out += [Lidar(k) for k in LIDAR]
    if scelta in (None, "lidar", "copernicus"):
        out.append(Copernicus())
    return out


# ------------------------------------------------------------------- giro
def profilo(tr, fonti: list) -> tuple:
    """Il profilo altimetrico del circuito, un valore ogni PASSO metri."""
    n = len(tr.curvature)
    giro = tr.length_km * 1000.0
    quanti = max(16, int(round(giro / PASSO)))
    usata = ""
    quote = []
    for j in range(quanti):
        i = int(j * n / quanti)
        lat, lon = tr.latlon(i)
        z = None
        for f in fonti:
            if isinstance(f, Lidar) and not f.copre(lat, lon):
                continue
            z = f.quota(lat, lon)
            if z is not None:
                usata = usata or f.nome
                break
        if z is None:
            return [], ""
        quote.append(z)
    return quote, usata


def liscia(q: list, giri: int = 2) -> list:
    """Toglie il tremolio del rilievo senza spianare le salite vere."""
    for _ in range(giri):
        n = len(q)
        q = [(q[(i - 1) % n] + 2.0 * q[i] + q[(i + 1) % n]) / 4.0 for i in range(n)]
    return q


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--fonte", choices=["lidar", "copernicus"], default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from game.model.track import Track

    dati = json.loads(TRACKS.read_text(encoding="utf-8"))
    tutti = []
    for pool in ("tracks", "candidates", "private"):
        tutti += [(pool, t) for t in dati.get(pool, [])]

    fonti = sorgenti(args.fonte)
    print(f"{'pista':<14}{'punti':>7}{'dislivello':>12}{'pendenza max':>14}  "
          f"{'fonte':<12}verifica")
    scritti = 0
    for pool, d in tutti:
        if args.only and d["id"] not in args.only:
            continue
        if not d.get("geo"):
            continue
        if d.get("quota") and not args.force:
            continue
        tr = Track.from_dict(d)
        q, fonte = profilo(tr, fonti)
        if not q:
            print(f"{d['id']:<14}{'-':>7}{'-':>12}{'-':>14}  nessuna fonte")
            continue
        q = liscia(q)
        disl = max(q) - min(q)
        pend = max(abs(q[(i + 3) % len(q)] - q[i]) / (3 * PASSO) for i in range(len(q)))
        noto = float(d.get("dislivello_noto") or 0.0)
        esito = "ok"
        if noto > 0.5:
            r = disl / noto
            if r > TROPPO_ALTO:
                esito = f"scartato: {disl:.0f} m contro {noto:.0f} veri, sono tetti"
            elif r < TROPPO_BASSO:
                esito = f"scartato: {disl:.0f} m contro {noto:.0f} veri, troppo spianato"
            else:
                esito = f"{100 * (r - 1):+.0f}% sul vero"
        else:
            esito = "nessun dislivello noto con cui confrontarlo"
        print(f"{d['id']:<14}{len(q):7d}{disl:11.1f} m{pend * 100:13.1f}%  "
              f"{fonte:<12}{esito}")
        if not args.dry_run and not esito.startswith("scartato"):
            d["quota"] = [round(x, 1) for x in q]
            d["quota_fonte"] = fonte
            scritti += 1

    if args.dry_run:
        print("\n--dry-run: non ho scritto niente.")
    elif scritti:
        TRACKS.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"\nscritti {scritti} circuiti in {TRACKS.relative_to(ROOT)}.")
    else:
        print("\nniente da scrivere: ce l'hanno gia' tutti (--force per rifarli).")


if __name__ == "__main__":
    main()
