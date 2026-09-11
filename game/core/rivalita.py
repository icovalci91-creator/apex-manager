"""La rivalita' fra compagni di squadra.

Due piloti forti sulla stessa vettura dominante, stagione dopo stagione, non
restano amici per sempre. E' Prost contro Senna alla McLaren, Alonso contro
Hamilton nel 2007, Vettel contro Webber alla Red Bull, Rosberg contro
Hamilton alla Mercedes: la macchina e' la stessa, il muretto e' lo stesso, e
l'unico avversario che conta ogni weekend e' quello nel box a fianco.

Non nasce da un contatto in pista - quello si dimentica - ma da anni passati
a giocarsi lo stesso mondiale con gli stessi mezzi. E quando sale troppo, di
solito non restano tutti e due: chi ha perso quel duello se ne va, se il
contratto glielo permette.
"""
from __future__ import annotations

# Quanto forte deve essere un pilota per "contare" in questo confronto: sotto
# questa soglia non si gioca il mondiale, e non ci si scanna per un ottavo
# posto. E' circa il livello di chi lotta per il podio.
SOGLIA_FORTE = 80.0

# La squadra deve giocarsi qualcosa sul serio: fra le prime della classifica
# costruttori dell'anno appena chiuso. La rivalita' vera nasce quando la
# vittoria e' alla portata di entrambi, non quando si litiga per i punti.
DOMINANZA_POSIZIONE = 3

# Quanto sale l'attrito in una stagione che soddisfa le condizioni - di base,
# e in piu' se il duello e' stato punto a punto - e quanto scende in una che
# non le soddisfa, o quando i due non sono piu' compagni.
SALITA_BASE = 8.0
SALITA_LOTTA_SERRATA = 10.0
DISCESA = 14.0

# Da qui in poi si vede, e in squadra se ne comincia a parlare.
SOGLIA_TENSIONE = 55.0
# E da qui in poi chi sta perdendo quel duello ascolta le offerte sul serio.
SOGLIA_ROTTURA = 82.0


def _titolari(gs, team) -> list:
    ids = list(team.drivers)[:2]
    return [gs.drivers[i] for i in ids if i in gs.drivers]


def compagno(gs, driver) -> object | None:
    """L'altro titolare della sua squadra, se ce n'e' uno."""
    team = gs.teams.get(getattr(driver, "team", None))
    if team is None:
        return None
    for altro in _titolari(gs, team):
        if altro.id != driver.id:
            return altro
    return None


def descrizione(attrito: float) -> str:
    """Una parola per dire come stanno, senza guardare il numero."""
    if attrito >= SOGLIA_ROTTURA:
        return "rotto"
    if attrito >= SOGLIA_TENSIONE:
        return "teso"
    if attrito >= 25.0:
        return "corretto"
    return "tranquillo"


def aggiorna(gs, ds: list, cs: list) -> list:
    """Un anno di convivenza, per ogni coppia di compagni di squadra.

    `ds` e `cs` sono le classifiche piloti e costruttori della stagione
    appena chiusa, prese prima che punti e posizioni si azzerino: e' quella
    lotta che conta, non quella dell'anno prossimo.
    """
    news = []
    posizione_squadra = {t.id: i for i, t in enumerate(cs, 1)}
    posizione_pilota = {d.id: i for i, d in enumerate(ds, 1)}
    for team in gs.teams.values():
        piloti = _titolari(gs, team)
        for d in piloti:
            d.perdente_duello = False
        if len(piloti) != 2:
            continue
        a, b = piloti
        # cambio di compagno: si riparte da zero. La tensione e' fra due
        # persone, non un difetto della macchina o della squadra
        if getattr(a, "rivale_id", "") != b.id:
            a.rivale_id, b.rivale_id = b.id, a.id
            a.attrito_compagno = b.attrito_compagno = 0.0
            continue
        # chi dei due ha perso il duello quest'anno - serve a chi decide se
        # restare, non a far salire o scendere l'attrito, che sale per tutti
        # e due uguale: la tensione la fa il duello, non chi lo vince
        pos_a, pos_b = posizione_pilota.get(a.id, 99), posizione_pilota.get(b.id, 99)
        if pos_a != pos_b:
            (a if pos_a > pos_b else b).perdente_duello = True
        forti = a.overall >= SOGLIA_FORTE and b.overall >= SOGLIA_FORTE
        dominante = posizione_squadra.get(team.id, 99) <= DOMINANZA_POSIZIONE
        if forti and dominante:
            divario = abs(a.points - b.points) / max(1.0, max(a.points, b.points))
            serrata = SALITA_LOTTA_SERRATA * max(0.0, 1.0 - divario * 2.0)
            salita = SALITA_BASE + serrata
            prima = a.attrito_compagno
            a.attrito_compagno = min(100.0, a.attrito_compagno + salita)
            b.attrito_compagno = min(100.0, b.attrito_compagno + salita)
            if team.is_player and prima < SOGLIA_TENSIONE <= a.attrito_compagno:
                news.append(f"{a.short} e {b.short} si giocano lo stesso mondiale, con la "
                           f"stessa macchina: in garage si sente la tensione.")
            elif team.is_player and prima < SOGLIA_ROTTURA <= a.attrito_compagno:
                perdente = a if a.perdente_duello else (b if b.perdente_duello else None)
                if perdente is not None:
                    news.append(f"{perdente.short} non regge piu' il confronto in casa: "
                               f"a fine contratto rischia di andarsene da solo, senza "
                               f"bisogno che tu lo liberi.")
        else:
            a.attrito_compagno = max(0.0, a.attrito_compagno - DISCESA)
            b.attrito_compagno = max(0.0, b.attrito_compagno - DISCESA)
    return news


def penalita_rinnovo(driver) -> float:
    """Da 0 a circa 0.55: quanto la tensione riduce la voglia di restare.

    Vale solo per chi sta perdendo il duello - chi lo sta vincendo non ha
    nessun motivo per andarsene, la macchina e' la sua.
    """
    if not getattr(driver, "perdente_duello", False):
        return 0.0
    a = float(getattr(driver, "attrito_compagno", 0.0))
    if a <= SOGLIA_TENSIONE:
        return 0.0
    return 0.55 * min(1.0, (a - SOGLIA_TENSIONE) / (SOGLIA_ROTTURA - SOGLIA_TENSIONE))


def penalita_scambio(gs, id_davanti: str, id_dietro: str) -> float:
    """Quanto la rivalita' toglie alla voglia di farsi da parte per il compagno.

    "Lascialo passare" e' facile da dire alla radio. Se quello davanti e'
    l'uomo che gli sta rubando il mondiale in casa, molto meno.
    """
    a = gs.drivers.get(id_davanti)
    b = gs.drivers.get(id_dietro)
    if a is None or b is None or getattr(a, "rivale_id", "") != b.id:
        return 0.0
    att = float(getattr(a, "attrito_compagno", 0.0))
    if att <= SOGLIA_TENSIONE:
        return 0.0
    return 0.5 * min(1.0, (att - SOGLIA_TENSIONE) / (SOGLIA_ROTTURA - SOGLIA_TENSIONE))
