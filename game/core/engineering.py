"""Analisi tecnica comparata e dialogo con gli ingegneri."""
from __future__ import annotations

import math

from .. import config as C

AREAS = {
    "carico":      "Carico aerodinamico",
    "efficienza":  "Efficienza aerodinamica",
    "potenza":     "Potenza e ibrido",
    "trazione":    "Trazione e grip meccanico",
    "frenata":     "Frenata e stabilita'",
    "gomme":       "Gestione gomme",
    "affidabilita": "Affidabilita'",
}

# quali componenti lavorare per migliorare ogni area
AREA_PARTS = {
    "carico": ["floor", "front_wing", "rear_wing", "active_aero"],
    "efficienza": ["rear_wing", "sidepods", "cooling", "active_aero"],
    "potenza": ["cooling", "gearbox", "sidepods"],
    "trazione": ["suspension", "chassis", "gearbox"],
    "frenata": ["brakes", "suspension", "chassis"],
    "gomme": ["suspension", "chassis", "floor"],
    "affidabilita": ["cooling", "gearbox", "chassis"],
}


def raw_profile(team) -> dict:
    """Grandezze fisiche della vettura valutate con assetto neutro."""
    car = team.car
    saved = dict(car.setup)
    car.setup = {k: 50.0 for k in saved}
    try:
        df, dr = car.downforce, car.drag
        return {
            "carico": df,
            "efficienza": df / max(0.4, dr),
            "potenza": car.power,
            "trazione": car.mech_grip,
            "frenata": car.braking,
            "gomme": 0.6 * car.mech_grip + 0.4 * (car.p("suspension") / 100.0),
            "affidabilita": car.reliability,
        }
    finally:
        car.setup = saved


def car_profile(team, gs=None) -> dict:
    """Profilo 0-100 rapportato al resto della griglia (0 = ultimo, 100 = migliore).

    Senza `gs` si usa una scala assoluta di ripiego: serve solo quando il
    confronto con gli avversari non e' disponibile.
    """
    raw = raw_profile(team)
    if gs is None:
        return {k: max(1.0, min(100.0, v * 60.0)) for k, v in raw.items()}
    grid = {t.id: raw_profile(t) for t in gs.teams.values()}
    out = {}
    for area, v in raw.items():
        vals = [g[area] for g in grid.values()]
        lo, hi = min(vals), max(vals)
        span = max(1e-6, hi - lo)
        out[area] = max(3.0, min(100.0, 8.0 + 92.0 * (v - lo) / span))
    return out


def estimate(gs, observer, rival) -> dict:
    """Stima rumorosa del profilo di un avversario."""
    truth = car_profile(rival, gs)
    known = min(1.0, 0.25 + gs.round / max(1, len(gs.tracks)) * 0.75)
    skill = (0.55 * observer.scouting_strength + 0.45 * observer._s("technical_director", "analysis")) / 100.0
    sigma = (1.0 - 0.65 * skill) * (1.0 - 0.45 * known) * 16.0
    return {k: max(1.0, min(100.0, v + gs.rng.gauss(0.0, sigma))) for k, v in truth.items()}


def field_report(gs) -> dict:
    """Confronto fra la nostra vettura e il resto della griglia."""
    me = gs.player
    mine = car_profile(me, gs)
    rivals = {t.id: estimate(gs, me, t) for t in gs.teams.values() if t.id != me.id}
    out = {}
    for area in AREAS:
        vals = [r[area] for r in rivals.values()]
        best_id = max(rivals, key=lambda k: rivals[k][area])
        out[area] = {
            "mine": mine[area],
            "best": max(vals),
            "best_team": gs.teams[best_id].short,
            "avg": sum(vals) / len(vals),
            "rank": 1 + sum(1 for v in vals if v > mine[area]),
            "delta": mine[area] - max(vals),
        }
    return out


def priorities(gs, limit: int = 3) -> list:
    """Aree su cui conviene investire, ordinate per urgenza."""
    rep = field_report(gs)
    track_bias = _calendar_bias(gs)
    scored = []
    for area, r in rep.items():
        gap = max(0.0, r["best"] - r["mine"])
        scored.append((gap * (0.6 + 0.8 * track_bias.get(area, 0.5)), area, r))
    scored.sort(reverse=True)
    return [(a, r) for _s, a, r in scored[:limit]]


def _calendar_bias(gs) -> dict:
    """Quanto contano le varie aree sulle piste che restano in calendario."""
    rest = gs.tracks[gs.round:] or gs.tracks
    n = len(rest)
    df = sum(t.traits["downforce"] for t in rest) / n
    pw = sum(t.traits["power"] for t in rest) / n
    tw = sum(t.traits["tyre_wear"] for t in rest) / n
    br = sum(t.traits["braking"] for t in rest) / n
    return {"carico": df, "efficienza": 1.0 - df * 0.5, "potenza": pw, "trazione": 0.5 + 0.3 * df,
            "frenata": br, "gomme": tw, "affidabilita": 0.55}


def suggested_allocation(gs) -> dict:
    """Ripartizione delle risorse consigliata dagli ingegneri."""
    rep = field_report(gs)
    bias = _calendar_bias(gs)
    weight = {p: 0.4 for p in C.CAR_PARTS}
    for area, r in rep.items():
        gap = max(0.0, r["best"] - r["mine"]) / 100.0
        w = (0.35 + 2.6 * gap) * (0.55 + 0.9 * bias.get(area, 0.5))
        for part in AREA_PARTS[area]:
            weight[part] = weight.get(part, 0.0) + w
    tot = sum(weight.values()) or 1.0
    return {k: v / tot for k, v in weight.items()}


def briefing(gs) -> list:
    """Testo del confronto tecnico settimanale con i responsabili."""
    me = gs.player
    td = me.role("technical_director")
    aero = me.role("head_of_aero")
    strat = me.role("head_of_strategy")
    lines = []
    rep = field_report(gs)
    pri = priorities(gs, 3)

    def who(s, fallback):
        return s.name if s else fallback

    best_area = max(rep.items(), key=lambda kv: kv[1]["mine"] - kv[1]["avg"])
    lines.append((who(td, "Il direttore tecnico"),
                  f"Il nostro punto di forza resta {AREAS[best_area[0]].lower()}: "
                  f"siamo {best_area[1]['rank']}i della griglia in quest'area."))
    for area, r in pri:
        gap = r["best"] - r["mine"]
        speaker = who(aero, "Aerodinamica") if area in ("carico", "efficienza") else who(td, "Tecnico")
        if gap > 18:
            tone = "e' il nostro problema principale, siamo molto lontani da"
        elif gap > 8:
            tone = "ci costa ancora parecchio rispetto a"
        else:
            tone = "e' ormai vicina al riferimento di"
        lines.append((speaker,
                      f"{AREAS[area]} {tone} {r['best_team']} ({gap:+.0f} punti). "
                      f"Lavorerei su {', '.join(C.CAR_PARTS[p]['label'].lower() for p in AREA_PARTS[area][:2])}."))
    nxt = gs.next_track
    if nxt and strat:
        t = nxt.traits
        need = "carico e trazione" if t["downforce"] > 0.7 else (
            "efficienza sui rettilinei" if t["power"] > 0.7 else "equilibrio generale")
        lines.append((strat.name,
                      f"A {nxt.name} servira' soprattutto {need}; degrado gomme atteso "
                      f"{'alto' if t['tyre_wear'] > 0.7 else 'contenuto'}."))
    return lines
