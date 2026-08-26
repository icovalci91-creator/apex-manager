"""Le architetture di power unit, e cosa cambia passare da una all'altra.

Un ciclo tecnico non e' una percentuale: e' una decisione su come sara' fatto
il motore. Sei cilindri turbo con meta' della potenza elettrica, otto cilindri
turbo con l'ibrido ridotto all'osso, dieci aspirati senza niente. Cambia il
suono, cambia il peso, cambia quanto costa costruirlo, e cambia soprattutto il
mestiere: con il V6 del 2026 la gara si vince gestendo l'energia, con un V10 la
si vince in staccata e basta.

Qui dentro c'e' il catalogo - sta in data/regulations.json, con i numeri veri -
e il modo di metterne una in vigore. Metterla in vigore vuol dire toccare i
numeri che il modello di giro legge davvero: quanta potenza c'e', quanta ne e'
elettrica, dove smette di spingere, quanta energia si recupera, quanta benzina
serve. Da li' in poi i circuiti si rimisurano da soli.
"""
from __future__ import annotations


_CATALOGO: dict = {}


def catalogo(gs=None) -> dict:
    """Tutte le architetture fra cui il tavolo tecnico puo' scegliere.

    Stanno nei dati e non nel salvataggio: sono un catalogo, non uno stato, e
    si leggono una volta sola per tutta la sessione.
    """
    global _CATALOGO
    if not _CATALOGO:
        from .state import _load
        _CATALOGO = _load("regulations.json").get("architetture", {})
    return _CATALOGO


def scheda(gs, aid: str) -> dict:
    return dict(catalogo(gs).get(aid, {}))


def corrente(gs) -> str:
    return str((gs.regulations.get("power_unit") or {}).get("architettura",
                                                            "v6_turbo_ibrido"))


def etichetta(gs, aid: str) -> str:
    return scheda(gs, aid).get("breve", aid)


def descrizione(gs, aid: str) -> str:
    a = scheda(gs, aid)
    if not a:
        return ""
    aspir = "turbo" if a.get("aspirazione") == "turbo" else "aspirato"
    return (f"{a.get('cilindri', 6)} cilindri {a.get('cilindrata_cc', 1600) / 1000:.1f} "
            f"litri {aspir}, {a.get('giri_max', 15000):,} giri, "
            f"{a.get('ice_kw', 400)} kW termici e {a.get('elettrico_kw', 0)} elettrici"
            .replace(",", "."))


def applica(gs, aid: str) -> list:
    """Mette in vigore un'architettura. Ritorna le righe da mostrare.

    Non e' un'etichetta: i numeri finiscono dove il gioco li legge davvero -
    nel modello di giro, nella gestione dell'energia, nel serbatoio - e i
    circuiti vanno rimisurati subito dopo, perche' con un'altra power unit si
    frena in un altro punto.
    """
    a = scheda(gs, aid)
    if not a:
        return []
    pu = gs.regulations.setdefault("power_unit", {})
    pu["architettura"] = aid
    pu["layout"] = f"V{a.get('cilindri', 6)} {a.get('aspirazione', 'turbo')}"
    pu["capacity_cc"] = a.get("cilindrata_cc", 1600)
    pu["max_rpm"] = a.get("giri_max", 15000)
    pu["ice_kw"] = a.get("ice_kw", 400)
    pu["electric_kw"] = a.get("elettrico_kw", 350)
    pu["batteria_mj"] = a.get("batteria_mj", 4.0)
    pu["es_usable_mj"] = a.get("batteria_mj", 4.0)
    pu["harvest_max_mj_lap"] = a.get("recupero_max_mj", 8.5)
    pu["fuel_race_target_kg"] = a.get("benzina_kg", 70)
    pu["pu_min_weight_kg"] = a.get("peso_pu_kg", 185)
    mod = pu.setdefault("modello", {})
    mod["quota_elettrica"] = a.get("quota_elettrica", 0.47)
    mod["v_taglio_kmh"] = a.get("v_taglio_kmh", 320)
    mod["v_fine_kmh"] = a.get("v_fine_kmh", 380)
    mod["recupero_max_mj"] = a.get("recupero_max_mj", 8.5)
    mod["potenza_rel"] = a.get("potenza_rel", 1.0)
    # il peso della vettura segue quello della power unit: un V10 senza batteria
    # non pesa come un ibrido con quattro megajoule a bordo
    base = float(gs.regulations.get("min_weight_kg", 768.0))
    delta = a.get("peso_pu_kg", 185) - 185
    if delta:
        gs.regulations["min_weight_kg"] = round(max(600.0, base + delta), 0)
        for t in gs.teams.values():
            t.car.mass_base = float(gs.regulations["min_weight_kg"])
    return [f"Architettura {a.get('nome', aid)}: {descrizione(gs, aid)}.",
            f"Peso minimo {gs.regulations['min_weight_kg']:.0f} kg, "
            f"{a.get('benzina_kg', 70)} kg di benzina a gara, "
            f"batteria da {a.get('batteria_mj', 0.0):.1f} MJ."]


# --------------------------------------------------------- chi vuole cosa
# Al tavolo nessuno chiede l'architettura migliore in assoluto: si chiede
# quella che conviene a se stessi. Chi ha speso una fortuna in ibrido non
# vuole buttarla, chi non ce l'ha vuole ripartire da zero, la FOM vuole il
# rumore e la federazione vuole spendere meno.
def preferenza_squadra(gs, team) -> dict:
    """Quanto ogni architettura piace a questa scuderia, da 0 a 1."""
    cat = catalogo(gs)
    if not cat:
        return {}
    attuale = corrente(gs)
    eng = gs.engine_makers.get(team.engine, {})
    tutte = [m.get("power", 85) for m in gs.engine_makers.values()] or [85]
    forza_pu = ((eng.get("power", 85) - min(tutte))
                / max(1e-6, max(tutte) - min(tutte)))
    ricca = max(0.0, min(1.0, (team.budget_base - 130.0) / 120.0))
    out = {}
    for aid, a in cat.items():
        v = 0.5
        if aid == attuale:
            # chi ha la power unit migliore vuole tenersela, chi ce l'ha
            # scarsa non vede l'ora di cambiare
            v += 0.55 * (forza_pu - 0.45) * (1.3 if team.works else 0.7)
        else:
            v += 0.35 * (0.45 - forza_pu)
            # ricominciare da zero costa, e non tutti se lo possono permettere
            v += 0.30 * (float(a.get("costo", 1.0)) - 0.8) * (ricca - 0.5) * 2.0
        # una squadra cliente guarda soprattutto al conto
        if not team.works:
            v += 0.25 * (1.0 - float(a.get("costo", 1.0)))
        out[aid] = max(0.02, min(1.0, v))
    return out


def preferenza_istituzioni(gs) -> list:
    """Cosa vogliono la federazione e il promotore, e quanto pesano."""
    cat = catalogo(gs)
    fia = {aid: max(0.05, 1.15 - float(a.get("costo", 1.0)))
           for aid, a in cat.items()}
    fom = {aid: max(0.05, float(a.get("spettacolo", 0.5)))
           for aid, a in cat.items()}
    return [(fia, 4.0, "FIA"), (fom, 3.0, "FOM")]
