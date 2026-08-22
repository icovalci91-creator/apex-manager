"""Scarica i tracciati reali da OpenStreetMap e li scrive in data/tracks.json.

    python tools/fetch_layouts.py            # tutti i circuiti
    python tools/fetch_layouts.py --only monza spa
    python tools/fetch_layouts.py --dry-run  # controlla senza scrivere

La fonte e' OpenStreetMap, non Google Maps: i dati di Google sono proprietari
e le loro condizioni d'uso vietano di estrarli o derivarne mappe da usare
altrove. OSM e' aperto (licenza ODbL) e richiede solo di citare la fonte, cosa
che il gioco fa nel README.

Serve rete verso openstreetmap.org e overpass-api.de. Entrambi chiedono
gentilezza: una richiesta al secondo e uno user agent riconoscibile.
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
PAUSE = 2.0                 # secondi fra una richiesta e l'altra
TOLERANCE = 0.12            # scarto massimo accettato sulla lunghezza


def _get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8")


def geocode(track: dict) -> tuple | None:
    """Trova il circuito per nome. Ritorna (lat, lon)."""
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


def _overpass(query: str, attempts: int = 3) -> dict:
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


def circuit_ways(lat: float, lon: float, name: str, radius_m: int = 4000) -> list:
    """I tratti del circuito, presi dalla relazione OSM quando esiste.

    La relazione elenca solo le vie del tracciato di gara: usarla evita di
    raccogliere anche la pista junior, l'anello sopraelevato e la corsia dei
    box, che stanno tutti a pochi metri e sono taggati allo stesso modo.
    """
    # parola piu' distintiva del nome, per riconoscere la relazione giusta
    stop = {"circuit", "circuito", "autodromo", "international", "raceway",
            "racing", "course", "street", "park", "de", "di", "the", "nazionale"}
    words = [w for w in name.lower().replace("-", " ").split()
             if len(w) > 3 and w not in stop] or [name.lower()]

    queries = [
        f'relation(around:{radius_m},{lat},{lon})["highway"="raceway"];',
        f'relation(around:{radius_m},{lat},{lon})["name"~"{words[0]}",i];',
    ]
    for q in queries:
        res = _overpass(f'[out:json][timeout:90];{q}out geom;')
        rels = [el for el in res.get("elements", []) if el.get("type") == "relation"]
        rels = [r for r in rels if _looks_like_circuit(r)]
        if not rels:
            continue

        def score(r):
            tags = r.get("tags", {})
            nm = (tags.get("name", "") or "").lower()
            s = sum(2 for w in words if w in nm)
            if tags.get("highway") == "raceway":
                s += 3
            return s

        rels.sort(key=score, reverse=True)
        for rel in rels[:3]:
            ways = _geoms({"elements": [rel]})
            if len(ways) >= 2:
                print(f"    relazione OSM '{rel.get('tags', {}).get('name', '?')}' "
                      f"({len(ways)} tratti)")
                return ways

    # nessuna relazione: si ripiega sulle singole vie da corsa nei dintorni
    res = _overpass(f'[out:json][timeout:90];'
                    f'way(around:{radius_m},{lat},{lon})["highway"="raceway"];'
                    f'out geom;')
    ways = [w for w in _geoms(res) if len(w) >= 4]
    if ways:
        print(f"    nessuna relazione: {len(ways)} vie sciolte nei dintorni")
    return ways


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
    args = ap.parse_args()

    data = json.loads(TRACKS.read_text(encoding="utf-8"))
    todo = [t for t in data["tracks"] if not args.only or t["id"] in args.only]
    print(f"Circuiti da cercare: {len(todo)}\n")

    done = failed = 0
    for t in todo:
        print(f"{t['id']:<14} {t['name']}")
        here = geocode(t)
        if not here:
            print("    non trovato su Nominatim")
            failed += 1
            continue
        ways = circuit_ways(here[0], here[1], t["name"])
        if not ways:
            print("    nessuna via da corsa nei dintorni")
            failed += 1
            continue
        ring, err = find_loop(ways, t["length_km"])
        if ring is None:
            print(f"    nessun anello chiuso fra {len(ways)} vie trovate")
            failed += 1
            continue
        got = length_km(ring)
        flag = "ok" if err <= TOLERANCE else "SOSPETTO"
        print(f"    {len(ring)} punti - {got:.3f} km contro {t['length_km']:.3f} "
              f"ufficiali ({err*100:+.1f}%) [{flag}]")
        if err > TOLERANCE:
            print("    scartato: troppo diverso, meglio nessun tracciato che uno sbagliato")
            failed += 1
            continue
        t["geo"] = thin(ring)
        done += 1

    print(f"\nTrovati {done}, falliti {failed}.")
    if args.dry_run:
        print("Prova a vuoto: data/tracks.json non e' stato toccato.")
        return 0
    if done:
        data.setdefault("_attribution", "Layout dei circuiti (c) OpenStreetMap "
                                        "contributors, licenza ODbL")
        TRACKS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Scritto {TRACKS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
