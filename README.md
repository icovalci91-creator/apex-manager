# Apex Manager

Manager di Formula 1 in 2D scritto in Python + Pygame. Stagione 2026, 11 scuderie,
24 gran premi, sviluppo vettura, mercato piloti e staff, infrastrutture e votazioni
in Commissione F1.

## Avvio

```bash
python main.py
```

Prima installazione delle dipendenze:

```bash
python -m pip install -r requirements.txt
```

## Versione web (iPad e tablet)

Lo stesso codice gira nel browser via WebAssembly. Per costruirla in locale:

```bash
python -m pip install pygbag
mkdir -p stage/apex-manager && cp -r main.py game data stage/apex-manager/
python -m pygbag --build --ume_block 0 --title "Apex Manager" stage/apex-manager/main.py
```

Il risultato sta in `stage/apex-manager/build/web/`: va servito via HTTP (non
aperto come file), per esempio con `python -m http.server` dentro quella
cartella. Su iPad si apre l'indirizzo in Safari e si usa "Aggiungi a Home" per
averlo a tutto schermo.

Il workflow `.github/workflows/web.yml` fa la stessa cosa a ogni push e
pubblica su GitHub Pages. Serve internet verso `pygame-web.github.io`, da cui
pygbag scarica il runtime Python-WASM.

Differenze rispetto al desktop: i salvataggi vivono in `localStorage` invece
che in `saves/`, non c'e' il pulsante "Esci", e i font di sistema non esistono
nel browser quindi si usa quello incluso in pygame.

## Come si gioca

1. **Nuova carriera** → scegli la scuderia e decidi se essere **costruttore completo**
   (telaio + power unit) o **solo telaio** con motore cliente. Se scegli di costruire la
   power unit partendo da cliente, il progetto richiede due stagioni.
2. Dal **Quartier Generale** gestisci la squadra fra una gara e l'altra.
3. **WEEKEND DI GARA** apre prove libere → qualifica → (sprint) → gara.
4. A fine stagione arrivano premi, mercato e **votazioni sul regolamento**.

### Le sezioni

| Sezione | Cosa fai |
|---|---|
| Quartier Generale | Cruscotto: cassa, budget cap, piloti, reparti, notizie |
| Vettura e assetto | Stato dei dieci componenti, prestazioni derivate, sei regolazioni di assetto (o delega agli ingegneri) |
| Sviluppo | Ripartizione risorse fra le aree, budget di sviluppo per gara, pacchetti di aggiornamento con costo, tempi e rischio |
| Ingegneri | Riunione tecnica: dove sei rispetto alla griglia, su cosa lavorare, allocazione consigliata |
| Piloti e mercato | Contratti, clausole, trattative con gradimento del pilota |
| Staff tecnico | Organigramma completo e mercato del personale |
| Infrastrutture | Nove strutture da potenziare, confronto con gli avversari |
| Regolamento | Norme in vigore, scala ATR, proposte in discussione |
| Classifiche / Calendario / Storico | Mondiali, 24 tracciati, cicli tecnici e albo d'oro |

### Durante la gara

- Velocità di simulazione: `II` pausa, `x1`, `x4`, `x12`, `x40`, oppure "Simula fino alla fine".
- `BOX <pilota>`: chiama ai box al passaggio successivo.
- `-` `=` `+`: modalità di guida (conserva / normale / attacca): più passo ma più consumo
  gomme e più rischio di errore.

## Come funziona sotto il cofano

**Tracciati.** Ogni circuito è descritto in `data/tracks.json` da una sequenza di
rettilinei e curve (`S900 R90:3 L60:4 ...`) con il numero di curve e la lunghezza reali.
Da quella sequenza si generano sia il disegno 2D sia il profilo di curvatura.

**Tempo sul giro.** Modello quasi-statico: per ogni punto si calcola la velocità massima
consentita dall'aderenza laterale (che dipende da carico aerodinamico e velocità), poi una
passata in avanti limitata da potenza e trazione e una all'indietro limitata dalla frenata.
Il risultato viene calibrato sul tempo di riferimento reale di ogni pista (`ref_lap`), così
i tempi sono realistici ma restano sensibili alle scelte tecniche: più ala significa più
carico e più resistenza, esattamente come in pista.

**Gara.** Continua, non a giri discreti: ogni vettura avanza in metri, i duelli si
risolvono quando due monoposto sono davvero a contatto, e il confronto di passo usa il
ritmo in aria libera (altrimenti chi insegue non passerebbe mai). Gomme, carburante,
scia sporca, safety car, rotture e contatti sono simulati.

**Sviluppo.** Le risorse si trasformano in prestazione con un'efficienza che dipende da
direttore tecnico, reparti e strutture, moderata dalla scala ATR (chi vince ha meno ore di
galleria del vento). I pacchetti di aggiornamento possono non correlare.

**Regolamento.** A fine stagione la Commissione vota tre proposte estratte dal catalogo in
`data/regulations.json`. Ogni scuderia vota secondo il proprio interesse, FIA e FOM secondo
costi e spettacolo. Le proposte approvate cambiano davvero la simulazione. All'inizio di un
nuovo ciclo tecnico i valori in campo si rimescolano, premiando chi ha struttura migliore.

## Dati modificabili

Tutto il contenuto sta in `data/` ed è JSON leggibile:

- `tracks.json` — 24 circuiti: lunghezza, giri, curve, caratteristiche, layout, tempo di riferimento
- `teams.json` — 11 scuderie, motoristi, strutture, componenti di partenza
- `drivers.json` — 22 titolari + svincolati, con attributi e contratti
- `staff.json` — figure chiave nominate, staff libero, template dei ruoli
- `regulations.json` — regolamento 2026, cicli storici, catalogo delle proposte votabili

I valori di piloti, scuderie e staff sono una fotografia ragionata della stagione 2026:
se qualcosa non ti torna, correggilo nel JSON e il gioco lo usa al riavvio.

## Struttura del codice

```
main.py              avvio
game/config.py       costanti fisiche, gomme, componenti, strutture
game/model/          track (geometria + modello di giro), car, people, team
game/core/           state (mondo e salvataggi), economy, development,
                     engineering, market, rules, season
game/sim/            weekend (motore gara), session (prove, qualifica, griglia)
game/ui/             app, theme, widgets, trackdraw, scenes/, pages/
data/                database JSON
saves/               salvataggi
```

## Limiti noti

- I tracciati sono ricostruiti dai dati reali (lunghezza, numero e tipo di curve) ma non
  dalle coordinate GPS: la forma è coerente e distinta per ogni pista, non identica
  all'originale.
- Le sprint usano lo stesso formato della qualifica principale.
- Le penalità in gara (bandiere, investigazioni) non sono ancora modellate.
