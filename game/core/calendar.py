"""Contratti dei circuiti: chi resta, chi esce, chi entra.

Il calendario non e' fisso. Ogni circuito ha un contratto con una scadenza, e
quando arriva si rinnova o si esce. A decidere sono tre cose che tirano in
direzioni diverse: quanto paga il promotore, quanto pubblico porta, e quanto
la pista e' intoccabile per tradizione. Monaco paga poco e non si tocca; una
pista nuova paga molto ma non ha storia da spendere quando i conti cambiano.
"""
from __future__ import annotations

CALENDARIO_MIN = 20
CALENDARIO_MAX = 24

# Quanto dura un rinnovo, in stagioni.
RINNOVO = (3, 7)


def expiring(gs, season: int | None = None) -> list:
    season = gs.season if season is None else season
    return [t for t in gs.tracks if getattr(t, "contract_until", 9999) <= season]


def renewal_score(gs, track) -> float:
    """Da 0 a 1: quanto conviene tenerlo in calendario.

    La tradizione pesa piu' di tutto perche' e' cio' che rende la categoria
    riconoscibile; i soldi contano, ma un circuito che nessuno guarda non si
    compra un posto per sempre.
    """
    canone = min(1.0, getattr(track, "fee", 25.0) / 55.0)
    pubblico = getattr(track, "popularity", 60) / 100.0
    trad = getattr(track, "tradition", 0.3)
    return max(0.0, min(1.0, 0.30 * canone + 0.30 * pubblico + 0.40 * trad))


def candidate_score(gs, track) -> float:
    """Quanto e' appetibile un circuito che vuole entrare."""
    canone = min(1.0, getattr(track, "fee", 25.0) / 55.0)
    pubblico = getattr(track, "popularity", 60) / 100.0
    trad = getattr(track, "tradition", 0.3)
    # per entrare i soldi pesano di piu': e' una trattativa, non un'eredita'
    return max(0.0, min(1.0, 0.45 * canone + 0.35 * pubblico + 0.20 * trad))


def roll_contracts(gs) -> list:
    """Fine stagione: scadenze, rinnovi, uscite e nuovi ingressi."""
    msgs = []
    in_scadenza = expiring(gs)
    usciti = []

    for t in in_scadenza:
        punteggio = renewal_score(gs, t)
        # la tradizione non si discute quasi mai
        if t.tradition >= 0.85 or gs.rng.random() < punteggio:
            anni = gs.rng.randint(*RINNOVO)
            aumento = gs.rng.uniform(1.0, 1.18) if punteggio > 0.6 else gs.rng.uniform(0.88, 1.05)
            t.contract_until = gs.season + anni
            t.fee = round(t.fee * aumento, 1)
            msgs.append(f"{t.gp}: contratto rinnovato fino al {t.contract_until} "
                        f"({t.fee:.0f} M$ a stagione).")
        else:
            usciti.append(t)

    for t in usciti:
        gs.tracks.remove(t)
        gs.candidates.append(t)
        msgs.append(f"{t.gp}: accordo scaduto, {t.name} esce dal calendario.")

    # Posti liberi: entra chi offre di piu' fra i candidati. Chi e' appena
    # uscito resta fuori almeno una stagione: un contratto scaduto non si
    # rifirma il giorno dopo.
    posti = CALENDARIO_MAX - len(gs.tracks)
    disponibili = [c for c in gs.candidates if c not in usciti]
    if posti > 0 and disponibili:
        ordine = sorted(disponibili, key=lambda c: -candidate_score(gs, c))
        # non tutti entrano: si prende dalla testa con un po' di casualita'
        quanti = min(posti, len(ordine), gs.rng.randint(max(0, posti - 1), posti))
        for t in ordine[:quanti]:
            gs.candidates.remove(t)
            t.contract_until = gs.season + gs.rng.randint(*RINNOVO)
            gs.tracks.append(t)
            msgs.append(f"{t.gp}: {t.name} entra in calendario fino al {t.contract_until}.")

    if len(gs.tracks) < CALENDARIO_MIN:
        msgs.append(f"Attenzione: il calendario e' sceso a {len(gs.tracks)} gare.")

    _reorder(gs)
    return msgs


def _reorder(gs) -> None:
    """Rimette le gare in ordine di stagione e ridistribuisce i mesi.

    Il calendario segue il clima e la logistica: si parte a marzo e si chiude a
    dicembre, quindi i mesi vanno ricalcolati ogni volta che cambia il numero
    di gare.
    """
    gs.tracks.sort(key=lambda t: (getattr(t, "month", 6), t.id))
    n = max(1, len(gs.tracks))
    for i, t in enumerate(gs.tracks):
        t.month = 3 + int(i * 10 / n)


def summary(gs) -> dict:
    """Numeri di sintesi per la schermata del calendario."""
    tot = sum(getattr(t, "fee", 0.0) for t in gs.tracks)
    return {
        "gare": len(gs.tracks),
        "canoni": round(tot, 1),
        "in_scadenza": [t for t in gs.tracks
                        if getattr(t, "contract_until", 9999) <= gs.season + 1],
        "candidati": sorted(gs.candidates, key=lambda c: -candidate_score(gs, c)),
    }
