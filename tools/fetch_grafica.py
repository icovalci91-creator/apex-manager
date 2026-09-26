"""Scarica da Poly Haven le texture e i cieli fotografici per la vista 3D.

    python tools/fetch_grafica.py              # quelli che mancano
    python tools/fetch_grafica.py --force      # riscarica tutto
    python tools/fetch_grafica.py --elenco     # dice cosa sceglierebbe, non scarica

La vista 3D di base dipinge i materiali con il calcolo - asfalto, prato,
ghiaia fatti di rumore - e il cielo con una sfumatura. Con questo strumento
arrivano quelli fotografici:

  * i **materiali**: asfalto, prato, ghiaia, sabbia, cemento, terra, con il
    colore, il rilievo (normal map) e la ruvidita', in `grafica/materiali/`;
  * i **cieli**: foto a 360 gradi ad alta gamma dinamica (HDRI) - sereno,
    nuvoloso, tramonto, coperto - in `grafica/cieli/`: fanno da sfondo e
    illuminano le macchine con i riflessi veri.

Il gioco li usa quando ci sono e la qualita' grafica lo permette; quando
mancano resta tutto come prima.

**Da dove vengono.** Da Poly Haven (polyhaven.com), che pubblica tutto sotto
licenza CC0: si puo' usare, modificare e ridistribuire, anche dentro al gioco,
senza obblighi. Lo strumento sceglie dall'elenco del sito i piu' scaricati
per ogni categoria, cosi' non dipende da nomi che possono cambiare, e scrive
in `grafica/elenco.json` cosa ha preso e da dove.

Gira sulle macchine di GitHub (`.github/workflows/grafica.yml`), che internet
ce l'hanno sempre. Non serve installare niente oltre a Python.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USCITA = ROOT / "grafica"
API = "https://api.polyhaven.com"
UA = "ApexManager/0.1 (gestionale F1 open source; texture per la vista 3D)"

# I materiali della vista 3D. Per ognuno: le parole da cercare fra le etichette
# e le categorie di Poly Haven, quelle da scartare, e alcuni nomi preferiti
# da provare per primi se esistono ancora.
MATERIALI = {
    "asfalto": {"cerca": ["asphalt"], "scarta": ["wall", "brick", "tile", "marking", "crack",
                                                 "damaged", "pothole"],
                "preferiti": ["asphalt_02", "asphalt_01", "asphalt_track"]},
    "prato": {"cerca": ["grass"], "scarta": ["wall", "rock", "dry", "dead", "path", "leaves"],
              "preferiti": ["grass_field", "aerial_grass_rock"]},
    "ghiaia": {"cerca": ["gravel"], "scarta": ["wall", "concrete", "road"],
               "preferiti": ["gravel_floor", "gravel_ground_01"]},
    "sabbia": {"cerca": ["sand"], "scarta": ["wall", "stone", "rock", "brick"],
               "preferiti": ["aerial_beach_01", "sand_01"]},
    "cemento": {"cerca": ["concrete"], "scarta": ["wall", "brick", "tile", "damaged",
                                                  "painted", "moss"],
                "preferiti": ["concrete_floor_02", "concrete_pavement"]},
    "terra": {"cerca": ["dirt", "soil", "mud"], "scarta": ["wall", "rock", "leaves", "grass"],
              "preferiti": ["dirt_floor", "brown_mud"]},
}

# I cieli: uno per ogni tempo che fa in gara.
CIELI = {
    "sereno": {"cerca": ["clear"], "scarta": ["night", "indoor", "studio", "sunset",
                                               "sunrise", "urban"]},
    "nuvoloso": {"cerca": ["partly cloudy", "cloudy"], "scarta": ["night", "indoor",
                                                                   "studio", "overcast"]},
    "coperto": {"cerca": ["overcast"], "scarta": ["night", "indoor", "studio"]},
    "tramonto": {"cerca": ["sunset", "sunrise-sunset", "sunrise"], "scarta": ["indoor",
                                                                             "studio"]},
}

# Le mappe di ogni materiale, e a che risoluzione: il colore si vede di piu'
# e merita il 2K; rilievo e ruvidita' reggono bene anche a 1K.
MAPPE = (("colore", ("Diffuse", "diff"), "2k"),
         ("normale", ("nor_gl",), "2k"),
         ("ruvidita", ("Rough", "rough"), "1k"))


def _get(url: str, binario: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for tentativo in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                dati = r.read()
            return dati if binario else json.loads(dati.decode("utf-8"))
        except Exception as ex:          # la rete di tutti: si riprova con calma
            if tentativo == 3:
                raise
            print(f"  riprovo ({ex})", flush=True)
            time.sleep(5 * (tentativo + 1))


def _parole(info: dict) -> set:
    fuori = set()
    for x in list(info.get("tags", [])) + list(info.get("categories", [])) + [info.get("name", "")]:
        fuori.add(str(x).lower())
    return fuori


def scegli(elenco: dict, regola: dict, gia: set) -> str | None:
    """Il nome dell'asset da prendere: un preferito se c'e', altrimenti il
    piu' scaricato fra quelli che corrispondono."""
    for nome in regola.get("preferiti", []):
        if nome in elenco and nome not in gia:
            return nome
    candidati = []
    for nome, info in elenco.items():
        if nome in gia:
            continue
        parole = _parole(info)
        testo = " ".join(parole) + " " + nome
        if not any(c in testo for c in regola["cerca"]):
            continue
        if any(s in testo for s in regola.get("scarta", [])):
            continue
        candidati.append((int(info.get("download_count", 0)), nome))
    candidati.sort(reverse=True)
    return candidati[0][1] if candidati else None


def _url(files: dict, chiavi: tuple, ris: str, fmt: str) -> str | None:
    for k in chiavi:
        voce = files.get(k)
        if not voce:
            continue
        for r in (ris, "2k", "1k", "4k"):
            u = voce.get(r, {}).get(fmt, {}).get("url")
            if u:
                return u
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="riscarica anche quelli gia' presenti")
    ap.add_argument("--elenco", action="store_true", help="dice cosa sceglierebbe, non scarica")
    args = ap.parse_args()

    registro_file = USCITA / "elenco.json"
    registro = {}
    if registro_file.exists():
        registro = json.loads(registro_file.read_text(encoding="utf-8"))
    registro.setdefault("materiali", {})
    registro.setdefault("cieli", {})

    texture = _get(f"{API}/assets?t=textures")
    hdri = _get(f"{API}/assets?t=hdris")
    print(f"Poly Haven: {len(texture)} texture, {len(hdri)} cieli", flush=True)

    gia = set()
    for chi, regola in MATERIALI.items():
        cartella = USCITA / "materiali" / chi
        nome = scegli(texture, regola, gia)
        if nome is None:
            print(f"{chi:<10}nessuna texture adatta")
            continue
        gia.add(nome)
        print(f"{chi:<10}{nome}", flush=True)
        if args.elenco:
            continue
        if (cartella / "colore.jpg").exists() and not args.force:
            print("          gia' presente, salto")
            continue
        files = _get(f"{API}/files/{nome}")
        cartella.mkdir(parents=True, exist_ok=True)
        for mappa, chiavi, ris in MAPPE:
            u = _url(files, chiavi, ris, "jpg")
            if u is None:
                print(f"          manca la mappa {mappa}")
                continue
            (cartella / f"{mappa}.jpg").write_bytes(_get(u, binario=True))
            print(f"          {mappa}: {u.rsplit('/', 1)[-1]}", flush=True)
            time.sleep(1.0)
        info = texture[nome]
        registro["materiali"][chi] = {
            "asset": nome, "nome": info.get("name", nome),
            "autori": list((info.get("authors") or {}).keys()),
            "fonte": f"https://polyhaven.com/a/{nome}", "licenza": "CC0",
            # quanti metri copre una ripetizione: Poly Haven lo scrive in
            # centimetri o metri a seconda dell'asset
            "misura": info.get("dimensions"),
        }

    gia = set()
    for chi, regola in CIELI.items():
        nome = scegli(hdri, regola, gia)
        if nome is None:
            print(f"{chi:<10}nessun cielo adatto")
            continue
        gia.add(nome)
        print(f"{chi:<10}{nome}", flush=True)
        if args.elenco:
            continue
        dove = USCITA / "cieli" / f"{chi}.hdr"
        if dove.exists() and not args.force:
            print("          gia' presente, salto")
            continue
        files = _get(f"{API}/files/{nome}")
        u = _url(files, ("hdri",), "2k", "hdr")
        if u is None:
            print("          nessun file .hdr")
            continue
        dove.parent.mkdir(parents=True, exist_ok=True)
        dove.write_bytes(_get(u, binario=True))
        print(f"          {u.rsplit('/', 1)[-1]}", flush=True)
        info = hdri[nome]
        registro["cieli"][chi] = {
            "asset": nome, "nome": info.get("name", nome),
            "autori": list((info.get("authors") or {}).keys()),
            "fonte": f"https://polyhaven.com/a/{nome}", "licenza": "CC0",
        }
        time.sleep(1.0)

    if not args.elenco:
        registro["scaricato"] = datetime.date.today().isoformat()
        registro["fonte"] = "Poly Haven (polyhaven.com), licenza CC0"
        USCITA.mkdir(exist_ok=True)
        registro_file.write_text(json.dumps(registro, indent=1, ensure_ascii=False),
                                 encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
