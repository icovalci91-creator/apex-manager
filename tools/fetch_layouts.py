"""Scarica i tracciati reali da OpenStreetMap e li scrive in data/tracks.json.

    python tools/fetch_layouts.py                 # quelli che ancora non ce l'hanno
    python tools/fetch_layouts.py --only monza spa
    python tools/fetch_layouts.py --pool candidati  # solo i circuiti fuori calendario
    python tools/fetch_layouts.py --dry-run       # controlla senza scrivere
    python tools/fetch_layouts.py --force --only monza   # rifa' uno gia' scaricato

Guarda sia le gare in calendario sia i circuiti candidati a entrarci, e salta
quelli che hanno gia' il tracciato: cosi' rilanciarlo costa poche richieste.

La fonte e' OpenStreetMap, non Google Maps: i dati di Google sono proprietari
e le loro condizioni d'uso vietano di estrarli o derivarne mappe da usare
altrove. OSM e' aperto (licenza ODbL) e richiede solo di citare la fonte, cosa
che il gioco fa nel README.

Serve rete verso openstreetmap.org e overpass-api.de. Entrambi chiedono
gentilezza: una richiesta al secondo e uno user agent riconoscibile.

Un tracciato appena scaricato comincia dove ha cominciato a disegnarlo chi
l'ha disegnato: per dire al gioco dov'e' la linea del traguardo e da che parte
si corre c'e' tools/anchor_tracks.py, da lanciare dopo questo.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "data" / "tracks.json"

UA = "ApexManager/0.1 (gestionale F1 open source; layout circuiti da OSM)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Piu' istanze dello stesso servizio: la prima e' quella ufficiale, le altre
# sono mirror pubblici. Si prova in ordine finche' una risponde.
OVERPASS_HOSTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
)
PAUSE = 3.0                 # secondi fra una richiesta e l'altra
TOLERANCE = 0.12            # scarto massimo accettato sulla lunghezza
# Sotto questa soglia il risultato e' cosi' buono che non vale la pena
# interrogare altre fonti. Fra le due si continua a cercare e si tiene il
# migliore: fermarsi al primo "accettabile" faceva prendere varianti corte.
GOOD_ENOUGH = 0.02


def _get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8")


def geocode(track: dict) -> tuple | None:
    """Trova il circuito. Ritorna (lat, lon).

    Se il circuito porta gia' un campo `coords` nei dati si usa quello: la
    ricerca per nome non trova tutto, e per certe piste e' piu' semplice
    scrivere le coordinate una volta che sperare che il servizio le indovini.
    """
    fisse = track.get("coords")
    if fisse and len(fisse) == 2:
        return float(fisse[0]), float(fisse[1])
    for query in (f"{track['name']} circuit", track["name"],
                  f"{track['name']} {track['country']}",
                  f"{track['gp']} circuit", f"{track['id']} circuit"):
        q = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
        try:
            res = json.loads(_get(f"{NOMINATIM}?{q}"))
        except Exception as exc:
            print(f"    geocodifica fallita ({exc})")
            time.sleep(PAUSE * 2)
            continue
        time.sleep(PAUSE)
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    return None


def _overpass(query: str, attempts: int = 2) -> dict:
    """Interroga Overpass, cambiando server quando quello in uso non risponde.

    L'istanza principale limita chi fa molte richieste di fila e ogni tanto e'
    semplicemente sovraccarica: i mirror servono a non restare a piedi. Se non
    risponde nessuno si rinuncia, e la pista tiene il tracciato che ha gia'.
    """
    payload = query.encode("utf-8")
    wait = PAUSE
    for n in range(attempts):
        for url in OVERPASS_HOSTS:
            try:
                res = json.loads(_get(url, payload))
                time.sleep(PAUSE)
                return res
            except Exception as exc:
                host = urllib.parse.urlparse(url).netloc
                print(f"    {host} non risponde ({str(exc)[:60]})")
        if n < attempts - 1:
            wait *= 2.5
            print(f"    nessun server disponibile, riprovo fra {wait:.0f}s")
            time.sleep(wait)
    return {}


def _geoms(res: dict) -> list:
    out = []
    for el in res.get("elements", []):
        for part in ([el] if el.get("geometry") else el.get("members", [])):
            geom = part.get("geometry") or []
            if len(geom) >= 2:
                out.append([[p["lat"], p["lon"]] for p in geom])
    return out


def _looks_like_circuit(rel: dict) -> bool:
    """Scarta cio' che porta il nome giusto ma non e' un circuito.

    Cercando per nome saltano fuori linee di autobus ("320 Barcellona - Mollet"),
    ferrovie ("Amsterdam Centraal - Zandvoort aan Zee"), alberghi e confini
    amministrativi: hanno la parola giusta nel nome e nient'altro in comune.
    """
    tags = rel.get("tags", {})
    if tags.get("highway") == "raceway":
        return True
    if tags.keys() & {"boundary", "admin_level", "place", "landuse", "building",
                      "tourism", "amenity", "public_transport", "shop", "office"}:
        return False
    if tags.get("type") == "route" and tags.get("route") not in (None, "raceway"):
        return False           # bus, treno, tram, bicicletta, sentiero...
    if tags.get("type") == "multipolygon" and "sport" not in tags:
        return False
    sport = (tags.get("sport") or "").lower()
    if sport and "motor" not in sport and "race" not in sport:
        return False
    return True


def circuit_candidates(lat: float, lon: float, name: str):
    """Genera un candidato alla volta, dal piu' affidabile.

    E' un generatore di proposito: ogni fonte costa una richiesta a un servizio
    pubblico che limita chi insiste, e chi chiama si ferma appena la lunghezza
    torna. Interrogarle tutte in anticipo faceva sessanta richieste per
    circuito e ci faceva bloccare prima di arrivare a quella giusta.
    """
    stop = {"circuit", "circuito", "autodromo", "international", "raceway",
            "racing", "course", "street", "park", "de", "di", "the", "nazionale"}
    words = [w for w in name.lower().replace("-", " ").split()
             if len(w) > 3 and w not in stop] or [name.lower()]

    def relazioni(query, etichetta):
        res = _overpass(f"[out:json][timeout:90];{query}out geom;")
        rels = [e for e in res.get("elements", [])
                if e.get("type") == "relation" and _looks_like_circuit(e)]
        rels.sort(key=lambda r: -sum(2 for w in words
                                     if w in (r.get("tags", {}).get("name", "") or "").lower()))
        for rel in rels[:3]:
            nome = rel.get("tags", {}).get("name") or "senza nome"
            ways = _geoms({"elements": [rel]})
            if ways:
                yield f"{etichetta} '{nome}'", ways

    # 1. L'impianto sportivo: e' il filtro piu' selettivo e il piu' economico
    #    per il servizio, e prende anche i cittadini che non hanno vie da corsa
    #    (Albert Park e' un parco pubblico, sono strade normali).
    yield from relazioni(f'relation(around:3000,{lat},{lon})["sport"~"motor",i];',
                         "relazione sportiva")
    # 2. la relazione dedicata alla pista, per i circuiti permanenti
    yield from relazioni(f'relation(around:4000,{lat},{lon})["highway"="raceway"];',
                         "relazione")
    # 3. ricerca per nome, ultima spiaggia fra le relazioni
    yield from relazioni(f'relation(around:4000,{lat},{lon})["name"~"{words[0]}",i];',
                         "relazione per nome")
    # 4. vie sciolte: il raggio stretto esclude pista junior, ovale e kartodromo
    for raggio in (1500, 3000):
        res = _overpass(f'[out:json][timeout:90];'
                        f'way(around:{raggio},{lat},{lon})["highway"="raceway"];'
                        f'out geom;')
        ways = [w for w in _geoms(res) if len(w) >= 2]
        if ways:
            yield f"{len(ways)} vie sciolte (r{raggio})", ways


# ------------------------------------------------------------------ geometria
def _metres(a, b) -> float:
    mx = 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot((b[1] - a[1]) * mx, (b[0] - a[0]) * 110540.0)


def length_km(ring: list) -> float:
    return sum(_metres(ring[i], ring[i + 1]) for i in range(len(ring) - 1)) / 1000.0


JOIN_TOL = 25.0                      # metri entro cui due estremi sono lo stesso punto
MAX_TURN = math.radians(100.0)       # oltre questo angolo non e' una continuazione


def _bearing(a, b) -> float:
    mx = 111320.0 * math.cos(math.radians(a[0]))
    return math.atan2((b[0] - a[0]) * 110540.0, (b[1] - a[1]) * mx)


def _turn(h1: float, h2: float) -> float:
    d = h2 - h1
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return abs(d)


def _head_of(ring: list) -> float:
    """Direzione di marcia in fondo all'anello, saltando i punti coincidenti."""
    for i in range(len(ring) - 2, -1, -1):
        if _metres(ring[i], ring[-1]) > 1.0:
            return _bearing(ring[i], ring[-1])
    return 0.0


def find_loop(ways: list, target_km: float, tol_m: float = JOIN_TOL) -> tuple:
    """Ricostruisce l'anello di gara camminando fra le vie da corsa.

    In OSM un circuito e' spezzato in decine di tratti, e attorno ce ne sono
    altri: pista junior, anello sopraelevato, corsia dei box. Ai bivi qui si
    sceglie sempre la continuazione piu' dritta, che e' come resta sul
    tracciato principale chi ci gira davvero. Fra tutti gli anelli chiusi
    ottenuti partendo da ogni tratto vince quello di lunghezza piu' vicina a
    quella ufficiale.
    """
    polys = [list(w) for w in ways if len(w) >= 2]
    best, best_err = None, 9e9
    for seed, poly in enumerate(polys):
        for direction in (1, -1):
            ring = poly[::direction]
            used = {seed}
            while True:
                if len(ring) > 8 and _metres(ring[-1], ring[0]) < tol_m:
                    break                                   # anello chiuso
                head = _head_of(ring)
                pick = pick_i = None
                pick_turn = MAX_TURN
                for i, w in enumerate(polys):
                    if i in used:
                        continue
                    for cand in (w, w[::-1]):
                        if _metres(ring[-1], cand[0]) >= tol_m:
                            continue
                        t = _turn(head, _bearing(cand[0], cand[1]))
                        if t < pick_turn:
                            pick, pick_turn, pick_i = cand, t, i
                if pick is None:
                    break                                   # vicolo cieco
                ring += pick[1:]
                used.add(pick_i)
                if length_km(ring) > target_km * 2.2:
                    break                                   # ci siamo persi
            if len(ring) < 20 or _metres(ring[-1], ring[0]) > tol_m * 4:
                continue
            err = abs(length_km(ring) - target_km) / max(0.1, target_km)
            if err < best_err:
                best, best_err = ring, err
    return best, best_err


def thin(ring: list, step_m: float = 12.0) -> list:
    """Alleggerisce il tracciato: il gioco lo ricampiona comunque."""
    out = [ring[0]]
    for p in ring[1:]:
        if _metres(out[-1], p) >= step_m:
            out.append(p)
    if _metres(out[-1], out[0]) > 1.0:
        out.append(out[0])
    return [[round(a, 6), round(b, 6)] for a, b in out]


# ---------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="id dei circuiti da aggiornare")
    ap.add_argument("--dry-run", action="store_true", help="non scrive nulla")
    ap.add_argument("--pool", choices=("calendario", "candidati", "tutti"), default="tutti",
                    help="quali circuiti guardare (default: tutti)")
    ap.add_argument("--force", action="store_true",
                    help="riscarica anche quelli che hanno gia' il tracciato")
    args = ap.parse_args()

    data = json.loads(TRACKS.read_text(encoding="utf-8"))
    pools = []
    if args.pool in ("calendario", "tutti"):
        pools.append(("calendario", data.get("tracks", [])))
    if args.pool in ("candidati", "tutti"):
        pools.append(("candidato", data.get("candidates", [])))

    todo = []
    gia_fatti = 0
    for etichetta, elenco in pools:
        for t in elenco:
            if args.only and t["id"] not in args.only:
                continue
            if t.get("geo") and not args.force:
                gia_fatti += 1
                continue
            todo.append((etichetta, t))

    print(f"Circuiti da cercare: {len(todo)}"
          + (f" ({gia_fatti} gia' a posto, --force per rifarli)" if gia_fatti else "") + "\n")

    done = failed = 0
    for pool, t in todo:
        print(f"{t['id']:<14} {t['name']}  [{pool}]")
        here = geocode(t)
        if not here:
            print("    non trovato su Nominatim")
            failed += 1
            continue
        migliore, best_err, best_lab = None, 9e9, ""
        for etichetta, ways in circuit_candidates(here[0], here[1], t["name"]):
            ring, err = find_loop(ways, t["length_km"])
            if ring is None:
                print(f"    {etichetta}: nessun anello chiuso")
                continue
            print(f"    {etichetta}: {length_km(ring):.3f} km ({err*100:+.1f}%)")
            if err < best_err:
                migliore, best_err, best_lab = ring, err, etichetta
            if err <= GOOD_ENOUGH:
                break                      # combacia, inutile insistere

        if migliore is None:
            print("    nessun tracciato utilizzabile nei dintorni")
            failed += 1
            continue
        if best_err > TOLERANCE:
            print(f"    scartato: il migliore era {best_lab} a {best_err*100:+.1f}%, "
                  f"meglio nessun tracciato che uno sbagliato")
            failed += 1
            continue
        print(f"    scelto {best_lab}: {len(migliore)} punti, "
              f"{length_km(migliore):.3f} km contro {t['length_km']:.3f} ufficiali")
        t["geo"] = thin(migliore)
        done += 1

    print(f"\nTrovati {done}, falliti {failed}.")
    if args.dry_run:
        print("Prova a vuoto: data/tracks.json non e' stato toccato.")
        return 0
    if done:
        data.setdefault("_attribution", "Layout dei circuiti (c) OpenStreetMap "
                                        "contributors, licenza ODbL")
        TRACKS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Scritto {TRACKS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
