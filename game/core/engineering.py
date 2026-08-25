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


# ------------------------------------------------------- carattere della vettura
# Due macchine con la stessa valutazione media non sono la stessa macchina: una
# nasce attorno al fondo e alle ali, l'altra attorno a sospensioni e telaio. La
# prima vive di carico aerodinamico, che cresce col quadrato della velocita', e
# va forte dove si curva forte; la seconda vive di aderenza meccanica, che c'e'
# anche da fermi, e va forte dove si curva piano. Da qui - e non da un
# coefficiente scritto a mano - nasce il fatto che l'ordine cambi da Monza a
# Monaco.
#
# Gli scostamenti sono a somma zero: la filosofia non rende una squadra piu'
# forte, le da' una forma.
CARATTERE = {
    "aero": {"floor": 3.2, "front_wing": 2.4, "rear_wing": 1.4, "active_aero": 1.6,
             "sidepods": 0.4, "cooling": -0.8, "gearbox": -1.6, "brakes": -1.4,
             "chassis": -1.2, "suspension": -4.0},
    "mechanical": {"suspension": 3.4, "chassis": 2.2, "brakes": 1.8, "gearbox": 1.2,
                   "sidepods": -0.4, "cooling": -0.4, "floor": -2.6, "front_wing": -1.8,
                   "rear_wing": -1.6, "active_aero": -1.8},
    "powertrain": {"cooling": 2.8, "gearbox": 2.4, "sidepods": 1.8, "chassis": 0.6,
                   "brakes": -1.0, "suspension": -1.2, "floor": -1.8, "front_wing": -1.6,
                   "rear_wing": -0.4, "active_aero": -1.6},
    "efficiency": {"rear_wing": 2.4, "sidepods": 2.2, "cooling": 1.8, "active_aero": 1.6,
                   "gearbox": -0.6, "brakes": -0.8, "chassis": -1.2, "suspension": -1.4,
                   "front_wing": -1.8, "floor": -2.2},
}


def shape_car(team, forza: float = 1.0) -> None:
    """Da' alla vettura la forma della filosofia della squadra.

    Si chiama quando la macchina nasce: dopo ci pensano gli aggiornamenti, che
    seguono la stessa linea, a tenerla in quella direzione.
    """
    delta = CARATTERE.get(team.philosophy)
    if not delta or not team.car:
        return
    medio = sum(delta.values()) / max(1, len(delta))
    for parte, d in delta.items():
        p = team.car.parts.get(parte)
        if p is None:
            continue
        p.perf = max(20.0, min(99.0, p.perf + (d - medio) * forza))


def part_field(gs) -> dict:
    """Come sta messa la griglia, componente per componente.

    Restituisce per ogni pezzo il minimo, la media e il massimo di tutte le
    vetture. Serve a leggere la nostra macchina per quello che conta davvero -
    dove siamo avanti e dove indietro rispetto agli altri - e non rispetto a un
    numero assoluto che da solo non dice niente.
    """
    out = {}
    for k in C.CAR_PARTS:
        vals = [t.car.parts[k].perf for t in gs.teams.values()]
        if not vals:
            continue
        out[k] = (min(vals), sum(vals) / len(vals), max(vals))
    return out


def part_standing(gs, team) -> dict:
    """Per ogni pezzo: quanto siamo sopra o sotto la griglia, da -1 a +1."""
    campo = part_field(gs)
    out = {}
    for k, (lo, media, hi) in campo.items():
        v = team.car.parts[k].perf
        span = max(1.5, (hi - lo) / 2.0)
        out[k] = max(-1.0, min(1.0, (v - media) / span))
    return out


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
    """Stima rumorosa del profilo di un avversario.

    Il rumore viene dal generatore delle schermate, non da quello della
    partita: la stima resta ferma mentre la si guarda e cambia da un weekend
    all'altro, senza spostare il corso della stagione.
    """
    truth = car_profile(rival, gs)
    known = min(1.0, 0.25 + gs.round / max(1, len(gs.tracks)) * 0.75)
    skill = (0.55 * observer.scouting_strength + 0.45 * observer._s("technical_director", "analysis")) / 100.0
    sigma = (1.0 - 0.65 * skill) * (1.0 - 0.45 * known) * 16.0
    rng = gs.view_rng("scouting", observer.id, rival.id)
    return {k: max(1.0, min(100.0, v + rng.gauss(0.0, sigma))) for k, v in truth.items()}


def field_report(gs, team=None) -> dict:
    """Confronto fra una vettura e il resto della griglia.

    Senza squadra vale per la nostra: e' il caso di tutte le schermate. Con
    una squadra serve al reparto di quella squadra per decidere da solo dove
    mettere le mani.
    """
    me = team if team is not None else gs.player
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


def priorities(gs, limit: int = 3, team=None) -> list:
    """Aree su cui conviene investire, ordinate per urgenza."""
    rep = field_report(gs, team)
    track_bias = _calendar_bias(gs)
    scored = []
    for area, r in rep.items():
        gap = max(0.0, r["best"] - r["mine"])
        scored.append((gap * (0.6 + 0.8 * track_bias.get(area, 0.5)), area, r))
    scored.sort(reverse=True)
    return [(a, r) for _s, a, r in scored[:limit]]


def track_bias(track) -> dict:
    """Che macchina chiede un circuito, area per area.

    E' la traduzione delle sue caratteristiche in quello su cui conviene
    lavorare: molto carico a Monaco, potenza a Monza. Da qui si capisce dove
    mandare i soldi guardando le gare che restano, non quella di domenica.
    """
    tr = track.traits
    df, pw = tr["downforce"], tr["power"]
    return {"carico": df, "efficienza": 1.0 - df * 0.5, "potenza": pw,
            "trazione": 0.5 + 0.3 * df, "frenata": tr["braking"],
            "gomme": tr["tyre_wear"], "affidabilita": 0.55}


def calendar_bias(gs, tracks=None) -> dict:
    """La stessa cosa, mediata sulle piste che restano da correre."""
    rest = tracks if tracks is not None else (gs.tracks[gs.round:] or gs.tracks)
    if not rest:
        rest = gs.tracks
    n = len(rest)
    voci = [track_bias(t) for t in rest]
    return {k: sum(v[k] for v in voci) / n for k in voci[0]}


def _calendar_bias(gs) -> dict:
    return calendar_bias(gs)


def suggested_parts(gs, team=None, limit: int = 3) -> list:
    """I componenti su cui gli ingegneri metterebbero le mani, in ordine.

    Sono gli stessi che nominano in riunione: se dicono "lavorerei su
    sospensioni e telaio", il reparto che lavora da solo apre il pacchetto
    li' e non altrove.
    """
    fuori = []
    for area, _r in priorities(gs, limit, team):
        for part in AREA_PARTS[area][:2]:
            if part not in fuori:
                fuori.append(part)
    return fuori


def suggested_allocation(gs, team=None) -> dict:
    """Ripartizione delle risorse consigliata dagli ingegneri."""
    rep = field_report(gs, team)
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
    # come stiamo a esecuzione, non solo a idee: il pezzo giusto serve a poco
    # se poi in pista non funziona
    from . import development
    conf = development.project_confidence(gs, me, "floor", "grande")
    if conf < 0.45:
        lines.append((who(td, "Il direttore tecnico"),
                      f"Il problema non e' solo dove sviluppare: cosi' come siamo "
                      f"messi, un pacchetto grande ha {development.outcome_odds(conf, 'grande')['fallito']*100:.0f}% "
                      f"di non funzionare. {development.weakest_link(gs, me, 'floor').capitalize()}."))
    elif conf > 0.72:
        lines.append((who(td, "Il direttore tecnico"),
                      "Sull'esecuzione siamo tranquilli: quello che disegniamo, in "
                      "pista si ritrova. Possiamo permetterci pacchetti ambiziosi."))
    if me.car_understanding < 0.25:
        lines.append((who(aero, "Aerodinamica"),
                      "Di questa macchina sappiamo ancora poco: ogni venerdi' "
                      "ripartiamo da capo con l'assetto. Serve tempo di reparto, "
                      "non un altro aggiornamento."))

    nxt = gs.next_track
    if nxt and strat:
        t = nxt.traits
        need = "carico e trazione" if t["downforce"] > 0.7 else (
            "efficienza sui rettilinei" if t["power"] > 0.7 else "equilibrio generale")
        lines.append((strat.name,
                      f"A {nxt.name} servira' soprattutto {need}; degrado gomme atteso "
                      f"{'alto' if t['tyre_wear'] > 0.7 else 'contenuto'}."))
    return lines
