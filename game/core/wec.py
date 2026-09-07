"""Il mondiale endurance: il terzo campionato della casa, e il piu' caro.

E' costruito sullo stesso telaio della Formula E - un programma che la
scuderia apre accanto alla Formula 1, con la sua gente, il suo bilancio e i
suoi sponsor - ma quello che ci si gioca e' un'altra cosa, e viene tutto da
una riga: qui le gare durano da sei a ventiquattro ore.

  * Non si vince col giro secco. Il Balance of Performance livella le vetture
    gara per gara, quindi la velocita' pura conta poco: quello che resta e'
    quanto la macchina dura, quanto consuma, e quanto sono bravi quelli che la
    rimettono insieme alle tre di notte.
  * Non c'e' un tetto di spesa. C'e' un mercato: chi vince Le Mans firma
    contratti che nessun altro vede, e chi arriva quinto di classe paga tutto
    di tasca sua. E' il contrario esatto della Formula E, dove il tetto
    protegge anche chi va piano.
  * Ci sono due modi di esserci. Una Hypercar costa trenta o quaranta milioni
    a stagione ed e' il posto dove si vince Le Mans; una LMGT3 ne costa un
    quinto, insegna meno, ma ti mette in griglia lo stesso.
  * E c'e' una gara che vale piu' del campionato. Nel mondo vero ci sono case
    che fanno tutta la stagione per quelle ventiquattro ore, e squadre che si
    iscrivono solo a quella.

Quello che lascia alla Formula 1 e' quello che la Formula 1 non puo' provare
da sola: un gran premio dura un'ora e mezza, e in un'ora e mezza non scopri
cosa si rompe. Affidabilita' ed efficienza si imparano solo facendo durare le
cose per un giorno intero.
"""
from __future__ import annotations

from . import economy

_REG: dict = {}


def regolamento() -> dict:
    global _REG
    if not _REG:
        from .state import _load
        _REG = _load("wec.json")
    return _REG


def corrente() -> dict:
    return regolamento().get("corrente", {})


def classi() -> dict:
    return corrente().get("classi", {}) or {}


def scheda(classe: str) -> dict:
    return dict(classi().get(classe, {}))


def cambio() -> float:
    """Da euro a milioni di dollari, come per la Formula E."""
    return 1.08


# --------------------------------------------------------------------- i soldi
def ha(team) -> bool:
    return bool(getattr(team, "wec_nome", ""))


def classe(team) -> str:
    return getattr(team, "wec_classe", "") or "lmgt3"


def ingegneri(team) -> int:
    return int(max(0, getattr(team, "wec_ingegneri", 0)))


def costo_ingresso(team, cl: str = "") -> float:
    s = scheda(cl or classe(team))
    return round(float(s.get("ingresso_meur", 1.0)) * cambio(), 2)


def costo_stagione(gs, team) -> float:
    """Quanto costa una stagione di endurance.

    La struttura, la gente, e i tre piloti per macchina: le gare durano un
    giorno e uno solo non ce la fa. Non c'e' un tetto che fermi il conto, il
    che vuol dire che si puo' spendere quanto si vuole - e che si puo'
    fallire.
    """
    if not ha(team):
        return 0.0
    s = scheda(classe(team))
    fisso = float(s.get("gestione_meur", 6.0)) * cambio()
    gente = ingegneri(team) * float(s.get("costo_ingegnere_meur", 0.08)) * cambio()
    return round(fisso + gente, 2)


def ingegneri_massimi(team) -> int:
    return int((scheda(classe(team)).get("ingegneri") or [8, 45])[1])


def ingegneri_minimi(team) -> int:
    return int((scheda(classe(team)).get("ingegneri") or [8, 45])[0])


# ----------------------------------------------------------------- gli sponsor
def forma(team) -> float:
    """Come e' andata l'ultima stagione, da 0 a 1."""
    pos = int(getattr(team, "wec_posizione", 0) or 0)
    n = max(2, len(griglia_di(classe(team))))
    if pos <= 0:
        return 0.45
    return max(0.0, min(1.0, 1.0 - (pos - 1) / (n - 1)))


def entrate(gs, team) -> float:
    """Sponsor e montepremi. Vincere Le Mans vale piu' del campionato."""
    if not ha(team):
        return 0.0
    s = scheda(classe(team))
    d = corrente().get("soldi", {}) or {}
    rep = float(getattr(team, "reputation", 60.0))
    prestigio = float(s.get("prestigio", 0.5))
    nome = 1.0 + float(d.get("peso_nome", 1.0)) * (rep - 60.0) / 100.0
    risultato = 0.65 + float(d.get("peso_risultato", 0.85)) * forma(team)
    base = float(d.get("sponsor_base_meur", 9.0)) * cambio() * prestigio
    premi = float(s.get("premio_meur", 2.0)) * cambio() * (0.30 + 1.0 * forma(team))
    # e Le Mans: chi l'ha vinta l'anno scorso ha una stagione di contratti
    if getattr(team, "wec_lemans", 0):
        base *= 1.45
    return round(max(0.0, base * nome * risultato + premi), 2)


def bilancio(gs, team) -> float:
    return round(entrate(gs, team) - costo_stagione(gs, team), 2)


# -------------------------------------------------------------- la performance
INGEGNERI_RIF = {"hypercar": 85.0, "lmgt3": 26.0}
PESO_STRUTTURE = 0.14
PASSO = 0.40


def muro(gs, team) -> float:
    """Fin dove puo' arrivare questo programma, con questa gente."""
    cl = classe(team)
    s = scheda(cl)
    lo, hi = (s.get("muro") or [50, 92])
    n = ingegneri(team) / INGEGNERI_RIF.get(cl, 30.0)
    resa = max(0.0, min(1.25, n ** 0.62))
    livello = float(lo) + (float(hi) - float(lo)) * resa * 0.85
    fab = (float(team.facilities.get("factory", 60.0))
           + float(team.facilities.get("pit_crew", 60.0))) / 2.0
    livello += PESO_STRUTTURE * (fab - 60.0)
    return round(max(40.0, min(97.0, livello)), 1)


def livello(team) -> float:
    return float(getattr(team, "wec_livello", 0.0) or 50.0)


def sviluppa(gs, team) -> float:
    if not ha(team):
        return 0.0
    ora, obiettivo = livello(team), muro(gs, team)
    passo = (obiettivo - ora) * PASSO
    team.wec_livello = round(ora + passo, 2)
    return round(passo, 2)


# ------------------------------------------------------------- si puo' aprire?
def puo_aprire(gs, team, cl: str) -> tuple:
    if ha(team):
        return False, f"Il programma esiste gia': {team.wec_nome}."
    costo = costo_ingresso(team, cl)
    ok, why = economy.can_afford(team, costo, gs, check_cap=False)
    if not ok:
        return False, why
    s = scheda(cl)
    annuo = (float(s.get("gestione_meur", 6.0))
             + (s.get("ingegneri") or [8])[0]
             * float(s.get("costo_ingegnere_meur", 0.08))) * cambio()
    if economy.war_chest(gs, team) < costo + annuo:
        return False, (f"L'ingresso costa {costo:.0f} M$ e tenerlo aperto almeno "
                       f"{annuo:.0f} M$ l'anno: non ci sono.")
    return True, (f"{costo:.0f} M$ di ingresso, poi almeno {annuo:.0f} M$ "
                  f"a stagione.")


def apri(gs, team, nome: str, cl: str) -> str:
    ok, why = puo_aprire(gs, team, cl)
    if not ok:
        return why
    team.add_expense(f"Ingresso nel mondiale endurance ({nome})",
                     costo_ingresso(team, cl), in_cap=False, category="wec")
    team.wec_nome = nome
    team.wec_classe = cl
    team.wec_ingegneri = ingegneri_minimi(team)
    team.wec_livello = float((scheda(cl).get("muro") or [50])[0]) + 6.0
    team.wec_posizione = 0
    return f"{nome}: iscritta al mondiale endurance, classe {scheda(cl).get('nome')}."


def chiudi(gs, team) -> str:
    if not ha(team):
        return "Non c'e' nessun programma endurance da chiudere."
    nome, team.wec_nome = team.wec_nome, ""
    team.wec_ingegneri = 0
    team.wec_livello = 0.0
    team.wec_piloti = []
    return f"{nome}: programma endurance chiuso."


# ------------------------------------------------------------- il campionato
# La griglia: le case in Hypercar e le squadre clienti in LMGT3, ognuna con un
# livello suo che si muove di anno in anno.
DERIVA = 2.0
RUMORE = 4.2               # una gara lunga e' meno lotteria di uno sprint
LEMANS = 4                 # a che gara del calendario sta Le Mans


def griglia_di(cl: str) -> dict:
    """I nomi che corrono in quella classe, con il livello di partenza."""
    reg = regolamento()
    if cl == "hypercar":
        nomi = list(reg.get("costruttori") or [])
        base = [92.0, 91.0, 90.0, 86.0, 84.0, 87.0, 82.0, 85.0]
    else:
        nomi = list(reg.get("squadre_gt") or [])
        base = [86.0, 82.0, 84.0, 80.0, 85.0, 78.0, 83.0, 76.0, 79.0]
    return {n: base[i] if i < len(base) else 78.0 for i, n in enumerate(nomi)}


def stato_griglia(gs, cl: str) -> dict:
    tutte = getattr(gs, "wec_griglia", None)
    if not tutte:
        tutte = {}
        gs.wec_griglia = tutte
    if cl not in tutte:
        tutte[cl] = griglia_di(cl)
    return tutte[cl]


def deriva_griglia(gs) -> None:
    for cl in classi():
        g = stato_griglia(gs, cl)
        for nome in list(g):
            g[nome] = round(max(64.0, min(97.0, g[nome] + gs.rng.gauss(0.0, DERIVA))), 1)


def piloti(gs, team) -> list:
    """L'equipaggio: tre per macchina, perche' una gara dura un giorno."""
    ids = list(getattr(team, "wec_piloti", []) or [])
    return [gs.drivers[i] for i in ids if i in gs.drivers][:3]


def forza_equipaggio(gs, team) -> float:
    """Quanto vale la nostra macchina: il programma, spostato dall'equipaggio.

    Conta la media dei tre, non il piu' forte: in ventiquattro ore guidano
    tutti, e il piu' lento dell'equipaggio e' quello che decide la gara. E'
    l'esatto contrario della Formula 1.
    """
    eq = piloti(gs, team)
    if not eq:
        return livello(team)
    media = sum(d.overall for d in eq) / len(eq)
    # e chi ne ha meno di tre li completa con professionisti qualunque
    if len(eq) < 3:
        media = (media * len(eq) + 70.0 * (3 - len(eq))) / 3.0
    return livello(team) + 0.35 * (media - 72.0)


def nuovo_campionato(gs) -> dict:
    """Apre la stagione endurance: le due classi, il calendario, la classifica."""
    st = {"stagione": gs.season, "round": 0, "classi": {}}
    nostre = [t for t in gs.teams.values() if ha(t)]
    for cl in classi():
        g = dict(stato_griglia(gs, cl))
        dentro = [t for t in nostre if classe(t) == cl]
        for _ in dentro:
            if g:
                del g[min(g, key=lambda k: g[k])]
        campo = [{"id": f"{cl}{i}", "nome": n, "forza": round(v, 2), "team_id": ""}
                 for i, (n, v) in enumerate(g.items())]
        for t in dentro:
            campo.append({"id": t.id, "nome": t.wec_nome, "team_id": t.id,
                          "forza": round(forza_equipaggio(gs, t), 2)})
        st["classi"][cl] = {"campo": campo,
                            "punti": {c["id"]: 0.0 for c in campo},
                            "vittorie": {c["id"]: 0 for c in campo},
                            "lemans": ""}
    return st


def stato(gs) -> dict:
    st = getattr(gs, "wec_stato", None)
    quanti = sum(1 for t in gs.teams.values() if ha(t))
    if not st or st.get("stagione") != gs.season or st.get("programmi") != quanti:
        st = nuovo_campionato(gs)
        st["programmi"] = quanti
        gs.wec_stato = st
    return st


def corri_gara(gs, n: int) -> None:
    """Una gara del mondiale, in tutte e due le classi.

    Chi vince una gara di endurance non e' chi ha il giro piu' veloce: e' chi
    e' ancora li' alla fine. Per questo il rumore e' piu' basso che altrove e
    l'affidabilita' del programma pesa parecchio: una macchina che si ferma
    non prende punti, e in ventiquattro ore le occasioni di fermarsi sono
    tante.
    """
    st = stato(gs)
    punti = corrente().get("punti", {}) or {}
    endurance = n in (LEMANS, 3, 7)
    tabella = list(punti.get("endurance" if endurance else "gara")
                   or [25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
    lunga = 3.0 if n == LEMANS else (1.5 if endurance else 1.0)
    for cl, dati in st["classi"].items():
        campo = dati["campo"]
        vivi = []
        for c in campo:
            # quanto e' probabile che arrivi in fondo: il livello del programma
            # e' anche quanto la macchina tiene, e una gara tripla la mette
            # alla prova tre volte
            rischio = max(0.02, (95.0 - c["forza"]) * 0.006) * lunga
            if gs.rng.random() < rischio:
                continue
            vivi.append(c)
        ordine = sorted(vivi, key=lambda c: -(c["forza"] + gs.rng.gauss(0.0, RUMORE)))
        for i, c in enumerate(ordine):
            if i < len(tabella):
                dati["punti"][c["id"]] += tabella[i]
            if i == 0:
                dati["vittorie"][c["id"]] += 1
                if n == LEMANS:
                    dati["lemans"] = c["id"]
        quali = sorted(campo, key=lambda c: -(c["forza"] + gs.rng.gauss(0.0, 3.0)))
        if quali:
            dati["punti"][quali[0]["id"]] += float(punti.get("pole", 1))
    st["round"] = max(st.get("round", 0), n)


def classifica(gs, cl: str) -> list:
    st = stato(gs)
    dati = st["classi"].get(cl) or {"campo": [], "punti": {}, "vittorie": {}}
    righe = [(c, dati["punti"].get(c["id"], 0.0), dati["vittorie"].get(c["id"], 0))
             for c in dati["campo"]]
    righe.sort(key=lambda x: (-x[1], -x[2]))
    return righe


# ------------------------------------------------- cosa lascia alla Formula 1
def resa(gs, team) -> dict:
    """Quanto sapere porta a casa il programma, e su cosa.

    Non e' il software elettrico della Formula E: qui si impara a far durare
    le cose e a consumare poco, che sono i due assi su cui la Formula 1 non ha
    modo di provare - un gran premio dura un'ora e mezza, e in un'ora e mezza
    non scopri cosa si rompe. Quanto ne arriva dipende da quanto e' grosso il
    programma e da come e' andato.
    """
    if not ha(team):
        return {}
    r = corrente().get("resa", {}) or {}
    s = scheda(classe(team))
    peso = float(s.get("prestigio", 0.5)) * (0.55 + 0.75 * forma(team))
    peso *= 0.6 + 0.8 * (livello(team) - 50.0) / 45.0
    return {"affidabilita": round(float(r.get("affidabilita", 0.5)) * peso, 3),
            "efficienza": round(float(r.get("efficienza", 0.3)) * peso, 3),
            "meccanici": round(float(r.get("meccanici", 0.25)) * peso, 3)}


def applica_resa(gs, team) -> str:
    """Porta il sapere dell'endurance dentro alla monoposto di Formula 1."""
    r = resa(gs, team)
    if not r:
        return ""
    fatte = []
    m = gs.engine_makers.get(team.engine) if team.works else None
    if r.get("affidabilita"):
        if m is not None:
            # chi si costruisce il motore lo impara sul motore: ventiquattro ore
            # dicono in una notte quello che venti gran premi non dicono
            m["reliability"] = min(99.0, float(m.get("reliability", 85.0))
                                   + r["affidabilita"])
            fatte.append(f"affidabilita' del motore +{r['affidabilita']:.2f}")
        else:
            # chi il motore lo compra impara sulla meccanica sua: cambio,
            # telaio, sospensioni - i pezzi che cedono
            car = getattr(team, "car", None)
            if car is not None and getattr(car, "parts", None):
                for k in ("gearbox", "suspension", "chassis"):
                    parte = car.parts.get(k)
                    if parte is not None:
                        parte.perf = min(99.0, parte.perf
                                         + r["affidabilita"] * 0.45)
                fatte.append(f"meccanica +{r['affidabilita'] * 0.45:.2f}")
    if r.get("efficienza") and m is not None:
        m["efficiency"] = min(99.0, float(m.get("efficiency", 80.0))
                              + r["efficienza"])
        fatte.append(f"efficienza motore +{r['efficienza']:.2f}")
    # e i meccanici: chi cambia quattro gomme e mezza fiancata alle tre di
    # notte lo fa anche di domenica pomeriggio
    if r.get("meccanici"):
        team.facilities["pit_crew"] = min(
            99.0, float(team.facilities.get("pit_crew", 60.0)) + r["meccanici"])
        fatte.append(f"squadra ai box +{r['meccanici']:.2f}")
    return ", ".join(fatte)


def stagione(gs) -> list:
    """Chiude il mondiale endurance: le gare che restano, i conti, il sapere."""
    righe = []
    deriva_griglia(gs)
    quante = int(corrente().get("gare", 8))
    for team in gs.teams.values():
        if not ha(team):
            continue
        break
    else:
        gs.wec_stato = None
        return righe
    st = stato(gs)
    for n in range(int(st.get("round", 0)) + 1, quante + 1):
        corri_gara(gs, n)
    for team in gs.teams.values():
        if not ha(team):
            continue
        cl = classe(team)
        cls = classifica(gs, cl)
        pos = next((i for i, (c, _p, _v) in enumerate(cls, 1)
                    if c.get("team_id") == team.id), 0)
        team.wec_posizione = pos
        team.wec_punti = round(next((p for c, p, _v in cls
                                     if c.get("team_id") == team.id), 0.0), 1)
        vinta = st["classi"][cl].get("lemans") == team.id
        team.wec_lemans = 1 if vinta else 0
        costo = costo_stagione(gs, team)
        incasso = entrate(gs, team)
        team.add_expense(f"Endurance ({team.wec_nome})", costo, in_cap=False,
                         category="wec")
        team.add_income(f"Endurance: sponsor e montepremi ({team.wec_nome})",
                        incasso, category="wec")
        passo = sviluppa(gs, team)
        imparato = applica_resa(gs, team)
        if vinta:
            team.reputation = min(99.0, team.reputation
                                  + float((corrente().get("resa") or {})
                                          .get("reputazione_lemans", 3.0)))
        riga = (f"{team.short} nel mondiale endurance ({scheda(cl).get('nome')}): "
                f"{pos}o su {len(cls)}, {team.wec_punti:.0f} punti. "
                f"Bilancio {incasso - costo:+.1f} M$, programma {passo:+.1f}")
        if vinta:
            riga += " - VINCE LE MANS"
        righe.append(riga)
        if imparato:
            righe.append(f"  dall'endurance alla monoposto: {imparato}")
    gs.wec_stato = None
    return righe


# ------------------------------------------------------- il computer che decide
VOGLIA = {"costruttore": 0.50, "marchio": 0.22, "fondo": 0.12, "padrone": 0.08}
CHIUDE_SOTTO = -14.0
PASSO_INGEGNERI = 5


def ai_programmi(gs) -> list:
    """Chi apre, chi chiude, e quanto ci mette dentro."""
    righe = []
    for team in gs.teams.values():
        if team.id == gs.player_team:
            continue
        if ha(team):
            righe += _ai_gestisci(gs, team)
            continue
        voglia = VOGLIA.get(getattr(team, "proprieta", "fondo"), 0.12)
        if gs.rng.random() > voglia * 0.30:
            continue
        respiro = economy.war_chest(gs, team)
        # in Hypercar ci si va solo con le spalle larghe: sono trenta milioni
        # l'anno, e chi non li ha va in GT3 o non va
        cl = "hypercar" if respiro > 90.0 else "lmgt3"
        ok, _ = puo_aprire(gs, team, cl)
        if not ok:
            continue
        righe.append(apri(gs, team, f"{team.short} Endurance", cl))
    return righe


def _ai_gestisci(gs, team) -> list:
    righe = []
    conto = bilancio(gs, team)
    respiro = economy.war_chest(gs, team)
    n = ingegneri(team)
    if conto < CHIUDE_SOTTO and respiro < 20.0:
        righe.append(chiudi(gs, team) + " Non si reggeva piu'.")
        return righe
    if respiro > 40.0 and n < ingegneri_massimi(team):
        team.wec_ingegneri = min(ingegneri_massimi(team), n + PASSO_INGEGNERI)
    elif conto < -6.0 and n > ingegneri_minimi(team):
        team.wec_ingegneri = max(ingegneri_minimi(team), n - PASSO_INGEGNERI)
    return righe
