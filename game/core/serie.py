"""Le categorie che portano alla Formula 1, e cosa ci succede davvero.

Fino a ieri il vivaio era un numero che saliva: a fine stagione ogni ragazzo
guadagnava qualche punto e nessuno sapeva perche'. Ma un pilota non cresce
perche' passa il tempo: cresce perche' corre, e quello che impara dipende da
dove corre, contro chi, e come e' andata.

Qui dentro c'e' la scala - Formula 4, Formula Regional, Formula 3, Formula 2 -
con i costi veri di un posto, i calendari veri e i punti superlicenza che
servono per avere il permesso di guidare in Formula 1. Ogni stagione si
schierano i nostri ragazzi, si corre il campionato contro un campo di
avversari che non sono numeri a caso, e da come e' finita dipende quanto
crescono, quanto valgono sul mercato e se il gradino dopo se lo sono
meritato.

E' anche il primo pezzo di una cosa piu' grande: da qui in avanti una serie e'
un dato, non del codice. Quando arriveranno il mondiale endurance e la Formula
E, arriveranno cosi'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_CATALOGO: dict = {}

# I nomi con cui si chiamano le squadre delle categorie minori: non sono
# quelle della Formula 1, sono strutture che vivono solo li'.
SCUDERIE = ("Prema", "ART", "Campos", "Hitech", "Rodin", "Invicta", "MP Motorsport",
            "Trident", "DAMS", "Van Amersfoort", "AIX", "PHM", "Jenzer", "US Racing")

NOMI = ("Alessio", "Mattia", "Tobias", "Lucas", "Nikita", "Enzo", "Rafael", "Joshua",
        "Kaito", "Marcus", "Owen", "Diego", "Sacha", "Bruno", "Ivan", "Noah",
        "Leo", "Filippo", "Callum", "Yuki", "Pedro", "Arthur", "Elias", "Milan")
COGNOMI = ("Reiter", "Sorensen", "Baptista", "Kovacs", "Lindqvist", "Moreau", "Okada",
           "Ferrer", "Bianchi", "Whitfield", "Nowak", "Duarte", "Ivanov", "Haugen",
           "Salvatori", "Meyer", "Ferreira", "Kaminski", "O'Brien", "Tanaka")


def catalogo() -> dict:
    """Le serie che esistono, dai dati."""
    global _CATALOGO
    if not _CATALOGO:
        from .state import _load
        _CATALOGO = _load("series.json").get("serie", {})
    return _CATALOGO


def scheda(sid: str) -> dict:
    return dict(catalogo().get(sid, {}))


def scala() -> list:
    """Le serie dal basso in alto, che e' l'ordine in cui si sale."""
    return sorted(catalogo(), key=lambda s: catalogo()[s].get("livello", 0))


def sigla(sid: str) -> str:
    return scheda(sid).get("sigla", sid.upper())


def costo_posto(sid: str) -> float:
    return float(scheda(sid).get("costo_posto", 1.0))


# ------------------------------------------------------- dove si mette un ragazzo
# Quanto sbaglia il responsabile del vivaio a cui si lascia la mano. Non e' un
# dado puro: uno che sa guardare i ragazzi mette ognuno dove deve stare, uno
# che vale poco ogni tanto brucia un diciassettenne in Formula 2 o tiene un
# anno di troppo in Formula 4 uno che era pronto.
DELEGA_ERRORE = 0.40


def verifica(gs, d, sid: str) -> tuple:
    """Se questo ragazzo puo' correre in questa categoria. Ritorna (si puo', perche' no).

    Le regole non sono di gusto: sono quelle vere. Ogni categoria ha la sua
    finestra d'eta', si sale un gradino alla volta - dalla Formula 4 non si
    salta in Formula 2 nemmeno pagando - e un campionato vinto non si rifa'.
    """
    s = scheda(sid)
    if not s:
        return False, "categoria che non esiste"
    livelli = scala()
    eta = int(d.age)
    emin, emax = s.get("eta", [15, 24])
    if eta < emin:
        return False, f"troppo giovane (da {emin} anni)"
    if eta > emax:
        return False, f"fuori eta' (fino a {emax})"
    if sid in (getattr(d, "titoli", None) or []):
        return False, "l'ha gia' vinta"
    prima = getattr(d, "ultima_serie", "") or ""
    if prima in livelli and livelli.index(sid) > livelli.index(prima) + 1:
        dopo = livelli[livelli.index(prima) + 1]
        return False, f"un gradino alla volta: prima la {sigla(dopo)}"
    return True, ""


def consigliata(gs, d) -> str:
    """In che categoria ha senso schierarlo, se non lo decide nessun altro.

    Si guarda quanto vale e quanti anni ha: un sedicenne bravo si mette in
    Formula Regional e non in Formula 2, perche' in Formula 2 lo distruggono e
    l'anno dopo non lo vuole nessuno. Se non vale abbastanza per nessuna delle
    categorie che potrebbe fare, si prende comunque la piu' bassa dove ci sta:
    correre in fondo al gruppo insegna piu' che stare fermo.
    """
    val = float(d.overall)
    scelta = ""
    for sid in scala():
        if not verifica(gs, d, sid)[0]:
            continue
        if val >= scheda(sid).get("ingresso", 50):
            scelta = sid
    if scelta:
        return scelta
    for sid in scala():
        if verifica(gs, d, sid)[0]:
            return sid
    return ""


def serie_adatta(gs, d) -> str:
    """Dove corre davvero questo ragazzo la prossima stagione.

    Se qualcuno ha deciso - il giocatore o il responsabile del vivaio - vale
    quella decisione, finche' resta una decisione possibile: un anno passa,
    l'eta' cambia, e una scelta di ottobre a marzo puo' non stare piu' in
    piedi. Altrimenti si ricade su quello che ha senso.
    """
    scelta = getattr(d, "serie_scelta", "") or ""
    if scelta and verifica(gs, d, scelta)[0]:
        return scelta
    return consigliata(gs, d)


def nota(gs, d, sid: str) -> str:
    """Il giudizio del responsabile su una categoria possibile: una riga.

    La percentuale e' quella vera: quanto di una stagione di crescita si
    porta a casa se lo si schiera li'.
    """
    s = scheda(sid)
    if not s:
        return ""
    val = float(d.overall)
    ingresso = float(s.get("ingresso", 50))
    quota = sfida(d, sid)
    if quota >= 0.98:
        return "e' la sua misura"
    if val >= float(s.get("promozione", 99)):
        return f"non impara piu': {quota * 100:.0f}%"
    if val < ingresso - 8:
        return f"lo massacrano: {quota * 100:.0f}%"
    return f"ci sta stretto: {quota * 100:.0f}%"


def scegli(gs, d, sid: str) -> tuple:
    """Il giocatore decide dove schierarlo. Sid vuoto vuol dire: decidi tu."""
    if not sid:
        d.serie_scelta = ""
        return True, f"{d.short}: decide il responsabile del vivaio."
    ok, why = verifica(gs, d, sid)
    if not ok:
        return False, f"{d.short} non puo' correre in {sigla(sid)}: {why}."
    d.serie_scelta = sid
    return True, (f"{d.short} correra' in {scheda(sid).get('nome', sid)}: "
                  f"{costo_posto(sid):.2f} M$ il posto.")


def delega(gs, team, d) -> str:
    """La scelta del responsabile del vivaio, con la sua fallibilita'."""
    ideale = consigliata(gs, d)
    if not ideale:
        return ""
    q = float(getattr(team, "scouting_strength", 55.0))
    if gs.rng.random() > max(0.0, DELEGA_ERRORE * (1.0 - q / 100.0)):
        return ideale
    livelli = scala()
    i = livelli.index(ideale)
    for passo in ((1, -1) if gs.rng.random() < 0.5 else (-1, 1)):
        j = i + passo
        if 0 <= j < len(livelli) and verifica(gs, d, livelli[j])[0]:
            return livelli[j]
    return ideale


def pianifica(gs, solo=None) -> list:
    """Si decide dove correra' ognuno la stagione prossima.

    Dove il vivaio e' delegato - tutte le squadre del computer, e la nostra se
    la mano l'abbiamo lasciata al responsabile - decide lui. Dove decide il
    giocatore non si tocca niente, ma le scelte che l'anno nuovo ha reso
    impossibili si cancellano: meglio una casella vuota che un ragazzo
    iscritto a un campionato in cui non puo' entrare.
    """
    from . import academy
    msgs = []
    for team in gs.teams.values():
        if not academy.has(team) or (solo is not None and team is not solo):
            continue
        auto = (not team.is_player) or bool(getattr(team, "vivaio_auto", True))
        for d in academy.roster(gs, team):
            scelta = getattr(d, "serie_scelta", "") or ""
            if auto:
                nuova = delega(gs, team, d)
                d.serie_scelta = nuova
                if team.is_player and nuova and nuova != consigliata(gs, d):
                    msgs.append(f"Vivaio: il responsabile schiera {d.short} in "
                                f"{sigla(nuova)}, e se ne prende la responsabilita'.")
            elif scelta and not verifica(gs, d, scelta)[0]:
                d.serie_scelta = ""
                if team.is_player:
                    msgs.append(f"Vivaio: {d.short} non puo' piu' correre in "
                                f"{sigla(scelta)}: va deciso dove schierarlo.")
    return msgs


def seme_scala(gs, d) -> str:
    """In che categoria si suppone che abbia corso l'anno scorso.

    Serve la prima volta che si carica una partita: senza saperlo, un
    diciannovenne bravo salterebbe in Formula 2 senza aver mai fatto un
    campionato, e la scala non esisterebbe. Si guarda l'eta', che e' quello
    che nella realta' dice a che punto del percorso uno e'.
    """
    livelli = scala()
    eta = int(d.age)
    if eta <= 16:
        return livelli[0]
    if eta <= 18:
        return livelli[min(1, len(livelli) - 1)]
    if eta <= 20:
        return livelli[min(2, len(livelli) - 1)]
    return livelli[-1]


@dataclass
class Posto:
    """Un pilota schierato in una categoria: nostro o del resto del mondo."""
    nome: str
    forza: float
    squadra: str
    driver_id: str = ""
    punti: float = 0.0
    vittorie: int = 0
    podi: int = 0
    superlicenza: int = 0


@dataclass
class Campionato:
    """Come e' finita una stagione di una categoria."""
    serie: str
    stagione: int
    ordine: list = field(default_factory=list)      # Posto, dal primo all'ultimo

    def posizione_di(self, driver_id: str) -> int:
        for i, p in enumerate(self.ordine, 1):
            if p.driver_id == driver_id:
                return i
        return 0

    def riga_di(self, driver_id: str):
        for p in self.ordine:
            if p.driver_id == driver_id:
                return p
        return None


def _campo(gs, sid: str, nostri: list) -> list:
    """Il campo partenti: i nostri ragazzi e tutti gli altri.

    Gli altri non sono numeri a caso: una categoria ha un livello suo, e
    dentro quel livello c'e' chi e' li' per vincere e chi paga per esserci.
    """
    s = scheda(sid)
    base = float(s.get("ingresso", 55)) + 3.0
    posti = []
    for d in nostri:
        posti.append(Posto(nome=d.short, forza=float(d.overall) + gs.rng.gauss(0, 0.6),
                           squadra="", driver_id=d.id))
    quanti = max(6, int(s.get("vetture", 24)) - len(posti))
    for _ in range(quanti):
        # la coda del campo paga per correre, la testa e' li' perche' qualcuno
        # ci ha visto qualcosa: la distribuzione non e' simmetrica
        forza = base + max(0.0, gs.rng.gauss(4.0, 4.2)) - gs.rng.gauss(1.0, 1.4)
        posti.append(Posto(nome=f"{gs.rng.choice(NOMI)} {gs.rng.choice(COGNOMI)}",
                           forza=forza, squadra=gs.rng.choice(SCUDERIE)))
    for p in posti:
        if not p.squadra:
            p.squadra = gs.rng.choice(SCUDERIE)
    return posti


def corri(gs, sid: str, nostri: list) -> Campionato:
    """Una stagione intera della categoria, gara per gara.

    Non e' la simulazione di un gran premio - qui non ci sono assetti ne'
    gomme - ma non e' nemmeno un dado: chi va piu' forte vince piu' spesso,
    chi e' costante raccoglie, e su venti gare la classifica finisce per
    somigliare ai valori veri. E' esattamente quello che serve per capire se
    un ragazzo e' pronto.
    """
    s = scheda(sid)
    posti = _campo(gs, sid, nostri)
    punti = list(s.get("punti", [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]))
    sprint = list(s.get("punti_sprint", []))
    gare = int(s.get("gare", 14))
    for g in range(gare):
        # il fine settimana con la gara corta assegna meno punti, come nel vero
        tabella = sprint if (sprint and g % 2 == 1) else punti
        ordine = sorted(posti, key=lambda p: -(p.forza + gs.rng.gauss(0.0, 3.6)))
        for i, p in enumerate(ordine):
            if i < len(tabella):
                p.punti += tabella[i]
            if i == 0:
                p.vittorie += 1
            if i < 3:
                p.podi += 1
    classifica = sorted(posti, key=lambda p: (-p.punti, -p.vittorie, -p.podi))
    lic = list(s.get("superlicenza", []))
    for i, p in enumerate(classifica):
        if i < len(lic):
            p.superlicenza = lic[i]
    return Campionato(serie=sid, stagione=gs.season, ordine=classifica)


# ------------------------------------------------------------- cosa lascia la stagione
# Quanto si impara in una stagione: correre insegna, e correre bene insegna di
# piu'. Chi domina una categoria ha finito quello che c'era da imparare li'.
CRESCITA_BASE = 0.55
CRESCITA_RISULTATO = 0.85
LICENZA_ANNI = 3       # quante stagioni valgono i punti superlicenza
LICENZA_SOGLIA = 40    # e quanti ne servono per avere il permesso


def sfida(d, sid: str) -> float:
    """Quanto una categoria ha ancora da insegnare a questo ragazzo.

    Dominare un campionato piu' basso del proprio livello non serve a niente:
    si vince tutto, non si impara niente, e nel frattempo si e' perso un anno.
    Il contrario - buttare un ragazzo dove non arriva - qualcosa insegna, ma
    meno di quanto insegnerebbe una categoria alla sua misura. E' anche il
    freno che tiene onesta la scelta della categoria: chi mette un
    ventunenne in Formula 4 per vincere facile si ritrova con un ventunenne
    che non e' cresciuto.
    """
    s = scheda(sid)
    if not s:
        return 1.0
    val = float(d.overall)
    ingresso = float(s.get("ingresso", 55))
    tetto = float(s.get("promozione", ingresso + 10))
    if val >= tetto:
        return max(0.25, 1.0 - (val - tetto) * 0.10)
    if val < ingresso:
        return max(0.55, 1.0 - (ingresso - val) * 0.03)
    return 1.0


def _quota_risultato(pos: int, campo: int) -> float:
    """Da 0 a 1: quanto in alto si e' finiti, contando quanti erano."""
    if campo <= 1:
        return 0.5
    return max(0.0, min(1.0, 1.0 - (pos - 1) / (campo - 1)))


def cresci(gs, d, camp: Campionato, team) -> str:
    """Cosa si porta a casa un ragazzo dopo una stagione vera.

    Il margine che ha ancora davanti conta come prima, ma adesso non cresce
    tutto uguale: chi ha vinto sale in fretta, chi e' rimasto in mezzo al
    gruppo impara poco, e chi non ha mai visto la zona punti a volte capisce
    che quella non era la sua categoria.
    """
    from ..model.people import DRIVER_ATTRS
    riga = camp.riga_di(d.id)
    if riga is None:
        return ""
    pos = camp.posizione_di(d.id)
    quota = _quota_risultato(pos, len(camp.ordine))
    struttura = 0.55 + 0.45 * float(team.facilities.get("academy", 60.0)) / 100.0
    margine = max(0.0, d.potential - d.overall)
    passo = (struttura * (margine / 12.0)
             * (CRESCITA_BASE + CRESCITA_RISULTATO * quota)
             * sfida(d, camp.serie)
             * gs.rng.uniform(0.8, 1.35))
    for a in DRIVER_ATTRS:
        cur = getattr(d, a)
        setattr(d, a, min(99.0, cur + min(passo, max(0.0, d.potential - cur))))
    # il potenziale vero si scopre correndo, e una stagione storta lo abbassa
    d.potential = max(d.overall, min(97.0, d.potential + gs.rng.gauss(0.0, 1.4)
                                     + (quota - 0.45) * 1.6))
    # e il mercato guarda la classifica, non il potenziale: chi vince si fa un
    # nome, e il nome e' meta' di quello che poi gli si offre
    # e il nome che ci si fa dipende anche da dove lo si e' fatto: la vetrina
    # della Formula 2 non e' quella di una Formula 4 regionale
    vetrina = 0.5 + 0.5 * float(scheda(camp.serie).get("livello", 1)) / len(scala())
    d.marketability = min(99.0, max(20.0, d.marketability
                                    + (quota - 0.45) * 9.0 * vetrina))
    licenza = getattr(d, "superlicenza", None) or []
    licenza.append({"stagione": gs.season, "punti": riga.superlicenza})
    d.superlicenza = [x for x in licenza if gs.season - x["stagione"] < LICENZA_ANNI]
    if pos == 1:
        # un campionato vinto non si rifa': e' la regola vera, ed e' anche il
        # motivo per cui vincere in basso puo' diventare un problema
        titoli = list(getattr(d, "titoli", None) or [])
        if camp.serie not in titoli:
            titoli.append(camp.serie)
        d.titoli = titoli
    s = scheda(camp.serie)
    dove = f"{pos}o in {s.get('sigla', camp.serie)}"
    if pos == 1:
        return f"{d.short} vince la {s.get('nome', camp.serie)}."
    if riga.vittorie:
        return f"{d.short} chiude {dove} con {riga.vittorie} vittorie."
    return f"{d.short} chiude {dove} con {riga.punti:.0f} punti."


def punti_licenza(d) -> int:
    """Quanti punti superlicenza ha in mano adesso."""
    return int(sum(x.get("punti", 0) for x in (getattr(d, "superlicenza", None) or [])))


def puo_correre_in_f1(d) -> bool:
    return punti_licenza(d) >= LICENZA_SOGLIA


# ------------------------------------------------------------------ la stagione
def stagione(gs) -> list:
    """Fa correre tutte le categorie minori e riporta cosa e' successo.

    Si schierano prima i nostri - ognuno nella categoria che gli compete, e
    ognuno con il suo conto da pagare - poi si corre, e alla fine si guarda
    chi e' cresciuto, chi ha la superlicenza e chi ha vinto un campionato che
    non puo' piu' rifare.
    """
    from . import academy
    msgs = []
    schieramenti: dict = {}
    for team in gs.teams.values():
        if not academy.has(team):
            continue
        for d in academy.roster(gs, team):
            sid = serie_adatta(gs, d)
            if not sid:
                if team.is_player:
                    msgs.append(f"Vivaio: per {d.short} non c'e' piu' una categoria in "
                                f"cui schierarlo: o gli si trova un volante, o e' finita.")
                continue
            schieramenti.setdefault(sid, []).append((team, d))
            costo = costo_posto(sid)
            team.add_expense(f"Posto in {sigla(sid)} per {d.last}", costo,
                             in_cap=False, category="vivaio")
    gs.campionati = {}
    for sid in scala():
        righe = schieramenti.get(sid, [])
        nostri = [d for _t, d in righe]
        camp = corri(gs, sid, nostri)
        gs.campionati[sid] = camp
        for team, d in righe:
            d.ultima_serie = sid
            riga = cresci(gs, d, camp, team)
            if riga and team.is_player:
                msgs.append("Vivaio: " + riga)
    # e chi ha finito la scala: o trova un volante o resta senza corse
    for team in gs.teams.values():
        if not academy.has(team) or not team.is_player:
            continue
        for d in academy.roster(gs, team):
            if puo_correre_in_f1(d):
                msgs.append(f"Vivaio: {d.short} ha la superlicenza "
                            f"({punti_licenza(d)} punti): puo' guidare in Formula 1.")
    return msgs


def nostri_in(gs, sid: str) -> list:
    """I ragazzi del giocatore schierati in questa categoria, per le schermate."""
    from . import academy
    team = gs.player
    if not academy.has(team):
        return []
    return [d for d in academy.roster(gs, team) if serie_adatta(gs, d) == sid]


def ultimo_campionato(gs, sid: str):
    return (getattr(gs, "campionati", None) or {}).get(sid)
