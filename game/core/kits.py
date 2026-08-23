"""I pezzi nuovi, e su quale macchina finiscono.

Quando un pacchetto e' pronto non arrivano due esemplari: ne arriva uno. La
fabbrica ne fa un altro nei giorni successivi, e nel frattempo bisogna
decidere chi lo monta - e quello e' un problema di squadra prima ancora che
tecnico, perche' l'altro pilota lo sa e non gli fa piacere.

Quanto in fretta arriva il secondo lo dice la fabbrica: chi ha produzione e
gente ne fa due subito, chi non li ha manda in pista una macchina aggiornata e
una vecchia per due o tre gran premi. E' successo a tutti, e a volte ha deciso
un campionato.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C


@dataclass
class Kit:
    """Un esemplare nuovo di un componente, con la sua storia."""
    part: str
    label: str
    perf: float              # quanto vale la specifica nuova
    old_perf: float          # quella che resta in garage
    size: str
    ready: int = 1           # esemplari pronti adesso
    fitted: list = field(default_factory=list)  # id dei piloti che ce l'hanno
    round_ready: int = 0     # da che gara e' disponibile
    cost: float = 0.0

    @property
    def gain(self) -> float:
        return round(self.perf - self.old_perf, 2)

    @property
    def spare(self) -> int:
        return max(0, self.ready - len(self.fitted))


# Quante gare ci mette la fabbrica a fare il secondo esemplare, secondo quanto
# vale la produzione. Un reparto grande li fa in parallelo, uno piccolo no.
def build_time(team, size: str) -> int:
    from . import departments
    fab = float(team.facilities.get("factory", 60.0))
    gente = departments.headcount(team, "progetto") + departments.headcount(team, "aero")
    q = 0.55 * (fab / 100.0) + 0.45 * min(1.0, gente / 160.0)
    base = {"piccolo": 1, "medio": 2, "grande": 4}[size]
    return max(0, int(round(base * (1.6 - 1.2 * q))))


def first_batch(team, size: str) -> int:
    """Quanti esemplari escono subito: uno, o due se la fabbrica ce la fa."""
    return 2 if build_time(team, size) <= 0 else 1


# --------------------------------------------------------------- il magazzino
def deltas(team, driver_id: str) -> dict:
    """Le specifiche montate solo su quella macchina, componente per componente."""
    if team.part_delta is None:
        team.part_delta = {}
    return team.part_delta.setdefault(driver_id, {})


def perf_for(team, driver_id: str, part: str) -> float:
    """La prestazione di quel componente su quella macchina."""
    d = (team.part_delta or {}).get(driver_id) or {}
    if part in d:
        return float(d[part])
    return team.car.parts[part].perf


def best_perf(team, part: str) -> float:
    """La specifica piu' avanti che esiste per quel componente, montata o no."""
    valori = [team.car.parts[part].perf]
    valori += [k.perf for k in (team.kits or []) if k.part == part]
    return max(valori)


def open_kits(team) -> list:
    return [k for k in (team.kits or []) if k.spare > 0 or len(k.fitted) < 2]


def add(gs, team, part: str, new_perf: float, old_perf: float, size: str,
        cost: float = 0.0) -> Kit:
    """Registra un pezzo nuovo appena uscito dalla fabbrica."""
    if team.kits is None:
        team.kits = []
    # una specifica alla volta per componente: quella nuova manda in pensione
    # quella precedente ancora in coda. Chi ce l'ha gia' in macchina se la
    # tiene finche' non arriva questa
    for vecchio in [x for x in team.kits if x.part == part]:
        team.kits.remove(vecchio)
    k = Kit(part=part, label=C.CAR_PARTS[part]["label"], perf=round(new_perf, 2),
            old_perf=round(old_perf, 2), size=size,
            ready=first_batch(team, size), round_ready=gs.round, cost=cost)
    team.kits.append(k)
    return k


def can_fit(gs, team, kit: Kit, driver) -> tuple:
    if driver.id in kit.fitted:
        return False, f"{driver.short} ce l'ha gia' montato."
    if kit.spare <= 0:
        return False, ("Il secondo esemplare non e' ancora pronto: la fabbrica ci "
                       "sta lavorando.")
    return True, ""


def fit(gs, team, kit: Kit, driver) -> tuple:
    """Monta il pezzo nuovo su una macchina."""
    ok, why = can_fit(gs, team, kit, driver)
    if not ok:
        return False, why
    kit.fitted.append(driver.id)
    deltas(team, driver.id)[kit.part] = kit.perf
    if len(kit.fitted) >= 2:
        # ce l'hanno tutte e due: da qui e' la specifica della squadra
        _promote(team, kit)
        return True, (f"{kit.label}: montato anche su {driver.short}. Adesso e' la "
                      f"specifica di tutte e due le macchine.")
    return True, (f"{kit.label}: montato sulla macchina di {driver.short} "
                  f"({kit.gain:+.1f}). L'altra resta con la specifica vecchia "
                  f"finche' non esce il secondo esemplare.")


def remove(gs, team, kit: Kit, driver) -> tuple:
    """Rimonta la specifica vecchia su quella macchina."""
    if driver.id not in kit.fitted:
        return False, "Non ce l'ha montato."
    kit.fitted.remove(driver.id)
    deltas(team, driver.id).pop(kit.part, None)
    return True, f"{kit.label}: {driver.short} torna alla specifica precedente."


def _promote(team, kit: Kit) -> None:
    """La specifica nuova diventa quella base: le due macchine tornano uguali."""
    team.car.parts[kit.part].perf = kit.perf
    for d in (team.part_delta or {}).values():
        d.pop(kit.part, None)
    if kit in (team.kits or []):
        team.kits.remove(kit)


def produce(gs, team) -> list:
    """La fabbrica lavora: prima o poi il secondo esemplare arriva."""
    msgs = []
    for k in list(team.kits or []):
        if k.ready >= 2:
            continue
        if gs.round - k.round_ready >= build_time(team, k.size):
            k.ready = 2
            if team.is_player:
                msgs.append(f"{k.label}: pronto il secondo esemplare, si puo' "
                            f"montare anche sull'altra macchina.")
        # un pezzo pagato che resta in magazzino non fa un decimo: se il muretto
        # se lo dimentica, gli si ricorda
        if (team.is_player and not team.auto_dev and k.spare > 0
                and not k.fitted and gs.round - k.round_ready >= 1):
            msgs.append(f"{k.label}: la specifica nuova ({k.gain:+.1f}) e' ancora "
                        f"in magazzino, non l'ha montata nessuno.")
    return msgs


def ai_fit(gs, team) -> None:
    """Il muretto monta appena puo', sul pilota davanti.

    Non e' un dettaglio di contorno: quando c'e' un pezzo solo lo mette chi sta
    piu' avanti in classifica, ed e' sempre stato cosi'. Vale per le scuderie
    del computer e per la propria, quando si e' delegato al reparto.
    """
    piloti = sorted(gs.drivers_of(team.id), key=lambda d: -d.points)
    for k in list(team.kits or []):
        if k.gain <= 0:
            continue          # un pacchetto fallito in macchina non ci va
        for d in piloti:
            if k.spare <= 0:
                break
            if d.id not in k.fitted:
                fit(gs, team, k, d)


def summary(team, driver_id: str) -> tuple:
    """(quanti pezzi nuovi ha questa macchina, quanti ne ha l'altra)."""
    mine = len((team.part_delta or {}).get(driver_id) or {})
    other = sum(len(v) for k, v in (team.part_delta or {}).items() if k != driver_id)
    return mine, other
