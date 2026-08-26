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
def serie_adatta(gs, d) -> str:
    """In che categoria ha senso schierare questo ragazzo.

    Si guarda quanto vale e quanti anni ha: un sedicenne bravo si mette in
    Formula Regional e non in Formula 2, perche' in Formula 2 lo distruggono e
    l'anno dopo non lo vuole nessuno. E soprattutto si sale di un gradino alla
    volta: nessuno passa dalla Formula 4 alla Formula 2, nemmeno se e' bravo -
    la scala esiste proprio per quello.
    """
    val = float(d.overall)
    eta = int(d.age)
    livelli = scala()
    scelta = ""
    for sid in livelli:
        s = scheda(sid)
        emin, emax = s.get("eta", [15, 24])
        if val >= s.get("ingresso", 50) and emin <= eta <= emax:
            scelta = sid
    if not scelta:
        # o e' troppo giovane per la prima, o ha passato l'eta' di tutte: in
        # nessuno dei due casi lo si schiera, e nel secondo e' un problema
        piu_bassa = scheda(livelli[0])
        if eta < piu_bassa.get("eta", [15, 24])[0]:
            return ""
        return "" if eta > max(scheda(x).get("eta", [15, 24])[1] for x in livelli) else livelli[0]
    prima = getattr(d, "ultima_serie", "") or ""
    if prima in livelli:
        tetto = livelli[min(len(livelli) - 1, livelli.index(prima) + 1)]
        if livelli.index(scelta) > livelli.index(tetto):
            scelta = tetto
    return scelta


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
             * gs.rng.uniform(0.8, 1.35))
    for a in DRIVER_ATTRS:
        cur = getattr(d, a)
        setattr(d, a, min(99.0, cur + min(passo, max(0.0, d.potential - cur))))
    # il potenziale vero si scopre correndo, e una stagione storta lo abbassa
    d.potential = max(d.overall, min(97.0, d.potential + gs.rng.gauss(0.0, 1.4)
                                     + (quota - 0.45) * 1.6))
    # e il mercato guarda la classifica, non il potenziale: chi vince si fa un
    # nome, e il nome e' meta' di quello che poi gli si offre
    d.marketability = min(99.0, max(20.0, d.marketability + (quota - 0.45) * 9.0))
    licenza = getattr(d, "superlicenza", None) or []
    licenza.append({"stagione": gs.season, "punti": riga.superlicenza})
    d.superlicenza = [x for x in licenza if gs.season - x["stagione"] < LICENZA_ANNI]
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
