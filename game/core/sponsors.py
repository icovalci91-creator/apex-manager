"""Accordi commerciali: chi paga la squadra e a quali condizioni.

I ricavi da sponsor sono la base su cui si regge un team: il montepremi arriva
tardi e dipende dai risultati, gli sponsor firmano per anni e danno la
prevedibilita' che permette di programmare. Qui si trattano, si rinnovano e si
perdono.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Quanti accordi si reggono contemporaneamente, per fascia.
SLOTS = {"title": 1, "primary": 2, "secondary": 3, "technical": 3}

# Un marchio commerciale sta su una vettura sola. I fornitori tecnici no: nella
# realta' lo stesso produttore di freni o di compositi lavora con mezza griglia.
EXCLUSIVE_TIERS = ("title", "primary", "secondary")

TIER_LABEL = {"title": "Title sponsor", "primary": "Partner principale",
              "secondary": "Partner secondario", "technical": "Fornitore tecnico"}

# Il valore reale di un accordo dipende da quanto la squadra vale per lo
# sponsor: risultati, reputazione e appeal dei piloti.
POSITION_WEIGHT = 0.45
REPUTATION_WEIGHT = 0.35
DRIVER_WEIGHT = 0.20


@dataclass
class Deal:
    """Un contratto firmato."""
    sponsor: str
    tier: str
    value: float                 # M$ all'anno
    years_left: int
    signed: int                  # stagione della firma
    bonus_win: float = 0.0
    bonus_podium: float = 0.0
    bonus_title: float = 0.0
    earned_bonus: float = 0.0    # bonus maturati nella stagione in corso

    def to_dict(self) -> dict:
        return asdict(self)


def catalogue(gs) -> list:
    return gs.sponsor_pool


def find(gs, sid: str) -> dict | None:
    for s in gs.sponsor_pool:
        if s["id"] == sid:
            return s
    return None


# ------------------------------------------------------------- valutazione
def team_appeal(gs, team) -> float:
    """Quanto vale questa squadra per uno sponsor, da 0 a 1."""
    n = max(1, len(gs.teams))
    pos = gs.position_of(team.id) if any(t.points for t in gs.teams.values()) else team.last_position
    standing = 1.0 - (pos - 1) / max(1, n - 1)
    rep = team.reputation / 100.0
    drivers = [gs.drivers[d] for d in team.drivers if d in gs.drivers]
    star = (sum(d.marketability for d in drivers) / len(drivers) / 100.0) if drivers else 0.5
    return max(0.05, min(1.0, POSITION_WEIGHT * standing
                         + REPUTATION_WEIGHT * rep + DRIVER_WEIGHT * star))


def offer_value(gs, team, sponsor: dict) -> float:
    """Quanto e' disposto a mettere sul piatto questo sponsor, oggi."""
    appeal = team_appeal(gs, team)
    atteso = sponsor.get("wants_position", 8)
    pos = gs.position_of(team.id) if any(t.points for t in gs.teams.values()) else team.last_position
    scarto = (atteso - pos) / max(1.0, len(gs.teams))       # positivo se facciamo meglio
    # la curva e' ripida di proposito: uno sponsor paga il vertice, non la meta'
    # gruppo, e una squadra di coda non incassa come una di testa
    fattore = (0.10 + 1.15 * appeal) * (1.0 + 0.50 * scarto)
    fattore *= 0.92 + 0.16 * (sponsor.get("prestige", 60) / 100.0)
    return round(max(0.3, sponsor["base"] * max(0.18, min(1.25, fattore))), 2)


def holder_of(gs, sid: str):
    """La squadra che ha gia' quello sponsor, se c'e'."""
    for t in gs.teams.values():
        if any(d.sponsor == sid for d in t.deals):
            return t
    return None


def will_talk(gs, team, sponsor: dict) -> tuple:
    """Se lo sponsor accetta di sedersi al tavolo, e perche' no."""
    altro = holder_of(gs, sponsor["id"]) if sponsor["tier"] in EXCLUSIVE_TIERS else None
    if altro is not None and altro is not team:
        return False, (f"{sponsor['name']} e' sotto contratto con {altro.short}: "
                       f"un marchio sta su una vettura sola.")
    if team.reputation < sponsor.get("min_reputation", 0):
        return False, (f"{sponsor['name']} non tratta con squadre sotto "
                       f"{sponsor['min_reputation']} di reputazione.")
    occupati = [d for d in team.deals if d.tier == sponsor["tier"]]
    if len(occupati) >= SLOTS.get(sponsor["tier"], 2):
        return False, (f"Non hai piu' spazio per un {TIER_LABEL[sponsor['tier']].lower()}: "
                       f"libera un accordo esistente.")
    for d in team.deals:
        altro = find(gs, d.sponsor)
        if (altro and altro["sector"] == sponsor["sector"]
                and sponsor["tier"] in EXCLUSIVE_TIERS and d.tier in EXCLUSIVE_TIERS):
            return False, (f"Conflitto di settore con {altro['name']}: due marchi di "
                           f"{sponsor['sector']} non convivono sulla stessa vettura.")
    if any(d.sponsor == sponsor["id"] for d in team.deals):
        return False, f"{sponsor['name']} e' gia' con noi."
    return True, ""


def negotiate(gs, team, sponsor: dict, asked: float, years: int) -> tuple:
    """Il giocatore chiede una cifra. Ritorna (esito, messaggio).

    Esito: accepted | counter | rejected.
    """
    ok, why = will_talk(gs, team, sponsor)
    if not ok:
        return "rejected", why
    equo = offer_value(gs, team, sponsor)
    lo, hi = sponsor.get("years", [2, 4])
    if not (lo <= years <= hi):
        return "rejected", (f"{sponsor['name']} firma solo contratti da {lo} a {hi} anni.")

    troppo = asked / max(0.1, equo)
    # piu' anni chiedi, piu' rischio si prende: chiede uno sconto
    troppo *= 1.0 + 0.05 * (years - lo)
    if troppo <= 1.05:
        _sign(gs, team, sponsor, asked, years)
        return "accepted", (f"{sponsor['name']} firma: {asked:.1f} M$ all'anno "
                            f"per {years} stagioni.")
    if troppo <= 1.35:
        return "counter", (f"{sponsor['name']} non ci sta a {asked:.1f}: "
                           f"il suo massimo e' {equo:.1f} M$ all'anno.")
    return "rejected", (f"{sponsor['name']} si alza dal tavolo: {asked:.1f} M$ e' fuori "
                        f"mercato per una squadra come la nostra.")


def _sign(gs, team, sponsor: dict, value: float, years: int) -> None:
    team.deals.append(Deal(
        sponsor=sponsor["id"], tier=sponsor["tier"], value=round(value, 2),
        years_left=years, signed=gs.season,
        bonus_win=sponsor.get("bonus_win", 0.0),
        bonus_podium=sponsor.get("bonus_podium", 0.0),
        bonus_title=sponsor.get("bonus_title", 0.0),
    ))


def terminate(gs, team, deal: Deal) -> tuple:
    """Rescindere costa: una penale pari a mezzo anno di contratto."""
    penale = round(deal.value * 0.5 * max(1, deal.years_left) * 0.5, 2)
    if team.cash < penale:
        return False, f"Servono {penale:.1f} M$ di penale e non li abbiamo."
    team.add_expense(f"Penale rescissione {_name(gs, deal)}", penale,
                     in_cap=False, category="sponsor")
    team.deals.remove(deal)
    return True, f"Accordo con {_name(gs, deal)} chiuso: penale di {penale:.1f} M$."


def _name(gs, deal: Deal) -> str:
    s = find(gs, deal.sponsor)
    return s["name"] if s else deal.sponsor


# ------------------------------------------------------------------ incassi
def annual_income(team) -> float:
    return round(sum(d.value for d in team.deals), 2)


def race_income(gs, team) -> float:
    """Quota per gara degli accordi in corso."""
    return round(annual_income(team) / max(1, len(gs.tracks)), 3)


def pay_race(gs, team) -> None:
    quota = race_income(gs, team)
    if quota > 0:
        team.add_income("Accordi commerciali", quota, category="sponsor")


def register_result(team, position: int) -> None:
    """Bonus di risultato maturati in gara."""
    if position == 1:
        for d in team.deals:
            d.earned_bonus += d.bonus_win
    elif position <= 3:
        for d in team.deals:
            d.earned_bonus += d.bonus_podium


def pay_bonuses(gs, team, champion: bool) -> float:
    tot = 0.0
    for d in team.deals:
        premio = d.earned_bonus + (d.bonus_title if champion else 0.0)
        d.earned_bonus = 0.0
        tot += premio
    if tot > 0.01:
        team.add_income("Bonus di risultato dagli sponsor", round(tot, 3), category="sponsor")
    return round(tot, 3)


# ------------------------------------------------------------- fine stagione
def roll_season(gs, team) -> list:
    """Scala i contratti di un anno e lascia andare chi non rinnova."""
    msgs = []
    for d in list(team.deals):
        d.years_left -= 1
        if d.years_left > 0:
            continue
        s = find(gs, d.sponsor)
        if s is None:
            team.deals.remove(d)
            continue
        equo = offer_value(gs, team, s)
        fedelta = s.get("loyalty", 60) / 100.0
        # rinnova da solo se il valore regge o se e' uno sponsor affezionato
        if equo >= d.value * 0.85 or gs.rng.random() < fedelta * 0.6:
            nuovo = round(max(0.3, equo * gs.rng.uniform(0.95, 1.08)), 2)
            anni = gs.rng.randint(*s.get("years", [2, 4]))
            d.value, d.years_left, d.signed = nuovo, anni, gs.season
            if team.is_player:
                msgs.append(f"{s['name']} rinnova per {anni} anni a {nuovo:.1f} M$/anno.")
        else:
            team.deals.remove(d)
            if team.is_player:
                msgs.append(f"{s['name']} non rinnova: i risultati non giustificano piu' "
                            f"i {d.value:.1f} M$ dell'accordo.")
    return msgs


def ai_fill(gs) -> None:
    """Le squadre gestite dal computer tengono pieni i propri spazi."""
    ordine = [t for t in sorted(gs.teams.values(), key=lambda x: -team_appeal(gs, x))
              if not t.is_player]
    for tier in ("title", "primary", "secondary", "technical"):
        for _ in range(SLOTS[tier]):
            _fill_round(gs, ordine, tier)


def slots_for(team) -> dict:
    """Quanti spazi riesce a riempire questa squadra, per fascia."""
    out = {}
    for tier, quanti in SLOTS.items():
        if team.reputation < 60:
            quanti = max(1, quanti - 2)
        elif team.reputation < 75:
            quanti = max(1, quanti - 1)
        out[tier] = quanti
    return out


def _fill_round(gs, teams: list, tier: str) -> None:
    """Un giro di assegnazioni: ogni squadra prende un accordo di quella fascia.

    Si procede a turni e non squadra per squadra, altrimenti la prima della
    lista si porta via tutto il mercato e le ultime restano senza niente.
    """
    for team in teams:
        if len([d for d in team.deals if d.tier == tier]) >= slots_for(team)[tier]:
            continue
        cand = [s for s in gs.sponsor_pool if s["tier"] == tier and will_talk(gs, team, s)[0]]
        if not cand:
            continue
        s = max(cand, key=lambda x: x["base"] * gs.rng.uniform(0.75, 1.25))
        _sign(gs, team, s, offer_value(gs, team, s),
              gs.rng.randint(*s.get("years", [2, 4])))


def bootstrap(gs) -> None:
    """Accordi di partenza: ogni squadra arriva al 2026 con i suoi contratti."""
    ordine = sorted(gs.teams.values(), key=lambda t: -team_appeal(gs, t))
    for tier in ("title", "primary", "secondary", "technical"):
        for _ in range(SLOTS[tier]):
            _fill_round(gs, ordine, tier)
