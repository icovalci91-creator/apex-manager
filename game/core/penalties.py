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


# Quanto si consuma in un gran premio quello che il regolamento conta. Sono
# tarati sul contingente: una power unit deve reggere il numero di gare che
# viene dal dividere il calendario per le unita' concesse, e chi ha un
# progetto fragile la brucia prima.
PU_WEAR_RACE = 100.0 / 7.0
GEARBOX_WEAR_RACE = 100.0 / 6.0
SOGLIA_ROTTURA = 30.0        # sotto questa soglia comincia a cedere


def component_wear(gs, team, driver, quota: float = 1.0) -> None:
    """Un gran premio di chilometri sulle parti contate dal regolamento."""
    affid = 0.72 + 0.28 * (team.car.engine.get("reliability", 85) / 100.0)
    cambio = 0.75 + 0.25 * (team.car.parts["gearbox"].condition / 100.0)
    driver.pu_wear = max(0.0, driver.pu_wear - PU_WEAR_RACE * quota / max(0.5, affid))
    driver.gearbox_wear = max(0.0, driver.gearbox_wear
                              - GEARBOX_WEAR_RACE * quota / max(0.5, cambio))


def health_factor(driver) -> float:
    """Quanto un componente logoro abbassa l'affidabilita' della vettura.

    Fino a un certo punto non si nota niente, poi la curva si impenna: e' cosi'
    che si rompe un motore, non un po' per volta ma tutto insieme.
    """
    peggio = min(driver.pu_wear, driver.gearbox_wear)
    if peggio >= SOGLIA_ROTTURA:
        return 1.0
    return max(0.55, 0.55 + 0.45 * (peggio / SOGLIA_ROTTURA))


def fit_new(gs, team, driver, quale: str = "pu") -> tuple:
    """Monta un componente nuovo. Ritorna (fatto, messaggio).

    Oltre il contingente si parte indietro, e quello lo decide il regolamento:
    e' la scelta di sempre, tenersi un pezzo consumato e rischiare la rottura
    oppure prendersi la penalita' e correre tranquilli.
    """
    reg = gs.regulations
    if quale == "pu":
        limite = int(reg["power_unit"].get("units_per_season", 4))
        usate, etichetta = driver.pu_used, "power unit"
    else:
        limite = int(reg["sporting"].get("gearbox_units", 5))
        usate, etichetta = driver.gearbox_used, "cambio"
    oltre = usate + 1 > limite
    msgs = register_component_use(gs, team, driver,
                                  1 if quale == "pu" else 0,
                                  0 if quale == "pu" else 1)
    if quale == "pu":
        driver.pu_wear = 100.0
    else:
        driver.gearbox_wear = 100.0
    testa = f"{driver.short}: montato un {etichetta} nuovo"
    if oltre:
        return True, testa + f". Fuori contingente: {msgs[0] if msgs else 'penalita in griglia'}"
    return True, testa + f" ({usate + 1} su {limite}, nessuna penalita')."


def wear_components(gs, team) -> list:
    """Un gran premio di consumo, e le squadre del computer che decidono.

    Il giocatore sceglie dalla pagina Vettura: qui si consuma e basta. Le IA
    montano un pezzo nuovo quando quello che hanno e' agli sgoccioli, e si
    prendono la penalita' solo se non possono farne a meno.
    """
    msgs = []
    for did in list(team.drivers) + list(team.reserves):
        d = gs.drivers.get(did)
        if d is None or did not in team.drivers:
            continue
        component_wear(gs, team, d, float(getattr(gs, "race_distance", 1.0)))
        # un pezzo finito non si porta in pista: lo cambiano i meccanici da
        # soli, e se il contingente e' esaurito la penalita' arriva lo stesso
        for quale, logoro in (("pu", d.pu_wear), ("cambio", d.gearbox_wear)):
            if logoro <= 0.0:
                ok, testo = fit_new(gs, team, d, quale)
                if team.is_player:
                    msgs.append("Obbligati: " + testo)
        if team.is_player:
            if d.pu_wear <= SOGLIA_ROTTURA and d.pu_wear > 0:
                msgs.append(f"{d.short}: la power unit e' al {d.pu_wear:.0f}%, "
                            f"conviene pensare a sostituirla.")
            if d.gearbox_wear <= SOGLIA_ROTTURA and d.gearbox_wear > 0:
                msgs.append(f"{d.short}: il cambio e' al {d.gearbox_wear:.0f}%.")
            continue
        gare_restanti = max(0, len(gs.tracks) - gs.round)
        for quale, logoro, usate, limite in (
                ("pu", d.pu_wear, d.pu_used,
                 int(gs.regulations["power_unit"].get("units_per_season", 4))),
                ("cambio", d.gearbox_wear, d.gearbox_used,
                 int(gs.regulations["sporting"].get("gearbox_units", 5)))):
            if logoro > 15.0:
                continue
            passo = PU_WEAR_RACE if quale == "pu" else GEARBOX_WEAR_RACE
            if logoro >= gare_restanti * passo * 1.05:
                continue           # quello che c'e' basta fino a fine anno
            # se il contingente e' finito si tira avanti finche' si puo'
            if usate >= limite and logoro > 4.0 and gare_restanti > 2:
                continue
            fit_new(gs, team, d, "pu" if quale == "pu" else "cambio")
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
