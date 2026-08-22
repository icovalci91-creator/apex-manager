"""Penalita': commissari in gara, punti sulla licenza, penalizzazioni in griglia.

Tre piani distinti, come nella realta'.

In gara i commissari aprono un'investigazione e, se decidono, assegnano secondi
che si scontano alla sosta successiva o si aggiungono al tempo finale.

Sulla licenza restano i punti: dodici in dodici mesi e il pilota salta una
gara. E' la sanzione che rende costoso guidare sempre al limite del contatto.

Fra una gara e l'altra ci sono le penalizzazioni in griglia, che arrivano da
un'altra parte del regolamento: le power unit e i cambi hanno un contingente
per stagione, e chi lo supera parte indietro.
"""
from __future__ import annotations

# Infrazioni tipiche e loro peso. I secondi sono quelli veri del regolamento:
# cinque per le scorrettezze lievi, dieci per quelle gravi.
INFRAZIONI = {
    "contatto": {"label": "Contatto con un altro pilota", "secondi": 10.0,
                 "punti": 2, "prob_indagine": 0.75},
    "contatto_lieve": {"label": "Manovra scorretta in staccata", "secondi": 5.0,
                       "punti": 1, "prob_indagine": 0.55},
    "limiti_pista": {"label": "Superati i limiti della pista", "secondi": 5.0,
                     "punti": 0, "prob_indagine": 1.0},
    "rilascio": {"label": "Rilascio non sicuro ai box", "secondi": 5.0,
                 "punti": 0, "prob_indagine": 0.9},
    "velocita_box": {"label": "Velocita' in corsia box", "secondi": 5.0,
                     "punti": 0, "prob_indagine": 1.0},
    "partenza": {"label": "Partenza anticipata", "secondi": 5.0,
                 "punti": 0, "prob_indagine": 1.0},
    "bandiere": {"label": "Mancato rispetto delle bandiere gialle", "secondi": 10.0,
                 "punti": 2, "prob_indagine": 0.85},
}

# Il regolamento sportivo: dodici punti in dodici mesi e si salta una gara.
PUNTI_PER_SOSPENSIONE = 12
GARE_PRIMA_DI_SCALARE = 24        # i punti valgono una stagione piena

# Sostituzioni oltre il contingente: quante posizioni si perde in griglia.
GRIGLIA_PU = 10
GRIGLIA_CAMBIO = 5
GRIGLIA_FONDO_GRIGLIA = 99        # oltre una certa soglia si parte ultimi


def apply_race_penalties(gs, sim) -> list:
    """Registra su piloti e squadre quanto deciso dai commissari in gara."""
    msgs = []
    for e in sim.entrants:
        d = gs.drivers.get(e.driver_id)
        if d is None:
            continue
        for inf in e.penalties_given:
            meta = INFRAZIONI.get(inf, {})
            d.penalty_points += meta.get("punti", 0)
            if meta.get("punti"):
                msgs.append(f"{d.short}: {meta['label']}, "
                            f"{meta['punti']} punti sulla licenza "
                            f"(totale {d.penalty_points}).")
        if d.penalty_points >= PUNTI_PER_SOSPENSIONE and d.banned_races <= 0:
            d.banned_races = 1
            d.penalty_points -= PUNTI_PER_SOSPENSIONE
            msgs.append(f"{d.name} raggiunge i {PUNTI_PER_SOSPENSIONE} punti: "
                        f"salta il prossimo gran premio.")
    return msgs


def decay_points(gs) -> None:
    """I punti scadono dopo un anno: si scala uno a fine stagione."""
    for d in gs.drivers.values():
        if d.penalty_points > 0:
            d.penalty_points = max(0, d.penalty_points - 2)


# ------------------------------------------------------- griglia e componenti
def register_component_use(gs, team, driver, quante_pu: int = 0, quanti_cambi: int = 0) -> list:
    """Segna le unita' usate e assegna la penalizzazione se si sfora."""
    msgs = []
    reg = gs.regulations
    max_pu = int(reg["power_unit"].get("units_per_season", 4))
    max_cambi = int(reg["sporting"].get("gearbox_units", 5))

    driver.pu_used += quante_pu
    driver.gearbox_used += quanti_cambi
    if driver.pu_used > max_pu:
        driver.grid_penalty += GRIGLIA_PU
        msgs.append(f"{driver.short}: power unit oltre il contingente "
                    f"({driver.pu_used}/{max_pu}), {GRIGLIA_PU} posizioni di penalita'.")
    if driver.gearbox_used > max_cambi:
        driver.grid_penalty += GRIGLIA_CAMBIO
        msgs.append(f"{driver.short}: cambio oltre il contingente, "
                    f"{GRIGLIA_CAMBIO} posizioni di penalita'.")
    return msgs


def wear_components(gs, team) -> list:
    """Consumo di power unit e cambi lungo la stagione.

    Un'unita' non dura per sempre: piu' e' fragile il progetto, prima si
    sostituisce, e superato il contingente si parte indietro. E' il prezzo
    nascosto di una power unit poco affidabile.
    """
    msgs = []
    affid = team.car.reliability
    for did in team.drivers:
        d = gs.drivers.get(did)
        if d is None:
            continue
        # probabilita' di dover montare un'unita' nuova in questo weekend
        p_pu = max(0.02, (1.0 - affid) * 1.6)
        p_cambio = max(0.015, (1.0 - team.car.parts["gearbox"].condition / 100.0) * 0.35)
        pu = 1 if gs.rng.random() < p_pu else 0
        cb = 1 if gs.rng.random() < p_cambio else 0
        if pu or cb:
            msgs += register_component_use(gs, team, d, pu, cb)
    return msgs


def apply_grid_penalties(gs, grid: list) -> tuple:
    """Riordina la griglia scontando le penalizzazioni. Ritorna (griglia, note)."""
    note = []
    penalizzati = [(d, gs.drivers[d].grid_penalty) for d in grid
                   if gs.drivers.get(d) and gs.drivers[d].grid_penalty > 0]
    if not penalizzati:
        return grid, note

    puliti = [d for d in grid if not (gs.drivers.get(d) and gs.drivers[d].grid_penalty > 0)]
    nuovo = list(puliti)
    for did, pen in sorted(penalizzati, key=lambda x: -x[1]):
        partenza = grid.index(did)
        d = gs.drivers[did]
        if pen >= GRIGLIA_FONDO_GRIGLIA:
            nuovo.append(did)
            note.append(f"{d.short} parte dal fondo della griglia.")
        else:
            pos = min(len(nuovo), partenza + pen)
            nuovo.insert(pos, did)
            note.append(f"{d.short}: {pen} posizioni di penalita', "
                        f"parte {pos + 1}o invece che {partenza + 1}o.")
        d.grid_penalty = 0
    return nuovo, note


def serve_bans(gs) -> list:
    """Chi e' squalificato salta il weekend."""
    fuori = []
    for d in gs.drivers.values():
        if d.banned_races > 0:
            d.banned_races -= 1
            fuori.append(d)
    return fuori
