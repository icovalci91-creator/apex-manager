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
OVERPASS = "https://overpass-api.de/api/interpreter"
PAUSE = 1.2                 # secondi fra una richiesta e l'altra
TOLERANCE = 0.12            # scarto massimo accettato sulla lunghezza


def _get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8")


def geocode(track: dict) -> tuple | None:
    """Trova il circuito per nome. Ritorna (lat, lon)."""
    for query in (f"{track['name']} circuit", f"{track['name']} {track['country']}",
                  f"{track['gp']} circuit"):
        q = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
        try:
            res = json.loads(_get(f"{NOMINATIM}?{q}"))
        except Exception as exc:
            print(f"    geocodifica fallita ({exc})")
            return None
        time.sleep(PAUSE)
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    return None


def raceway_ways(lat: float, lon: float, radius_m: int = 4000) -> list:
    """Tutte le vie da corsa attorno a quel punto, come liste di coordinate."""
    query = (f'[out:json][timeout:80];'
             f'way(around:{radius_m},{lat},{lon})["highway"="raceway"];'
             f'out geom;')
    try:
        res = json.loads(_get(OVERPASS, query.encode("utf-8")))
    except Exception as exc:
        print(f"    Overpass fallita ({exc})")
        return []
    time.sleep(PAUSE)
    out = []
    for el in res.get("elements", []):
        geom = el.get("geometry") or []
        if len(geom) >= 4:
            out.append([[p["lat"], p["lon"]] for p in geom])
    return out


# ------------------------------------------------------------------ geometria
def _metres(a, b) -> float:
    mx = 111320.0 * math.cos(math.radians(a[0]))
    return math.hypot((b[1] - a[1]) * mx, (b[0] - a[0]) * 110540.0)


def length_km(ring: list) -> float:
    return sum(_metres(ring[i], ring[i + 1]) for i in range(len(ring) - 1)) / 1000.0


def stitch(ways: list, tol_m: float = 25.0) -> list:
    """Unisce i pezzi che si toccano, per ricostruire l'anello completo.

    In OSM un circuito e' spesso spezzato in piu' vie: qui si riattaccano
    seguendo gli estremi che coincidono.
    """
    pool = [list(w) for w in ways]
    rings = []
    while pool:
        ring = pool.pop(0)
        joined = True
        while joined:
            joined = False
            for i, w in enumerate(pool):
                for cand in (w, w[::-1]):
                    if _metres(ring[-1], cand[0]) < tol_m:
                        ring += cand[1:]
                        pool.pop(i)
                        joined = True
                        break
                    if _metres(ring[0], cand[-1]) < tol_m:
                        ring = cand[:-1] + ring
                        pool.pop(i)
                        joined = True
                        break
                if joined:
                    break
        rings.append(ring)
    return rings


def best_ring(rings: list, target_km: float) -> tuple:
    """L'anello chiuso la cui lunghezza somiglia di piu' a quella ufficiale."""
    best, best_err = None, 9e9
    for r in rings:
        if len(r) < 20:
            continue
        if _metres(r[0], r[-1]) > 120.0:      # deve chiudersi
            continue
        err = abs(length_km(r) - target_km) / max(0.1, target_km)
        if err < best_err:
            best, best_err = r, err
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
        ways = raceway_ways(*here)
        if not ways:
            print("    nessuna via da corsa nei dintorni")
            failed += 1
            continue
        ring, err = best_ring(stitch(ways), t["length_km"])
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
