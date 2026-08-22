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
python -m pygbag --build --width 1600 --height 900 --title "Apex Manager" stage/apex-manager/main.py
```

Il risultato sta in `stage/apex-manager/build/web/`: va servito via HTTP (non
aperto come file), per esempio con `python -m http.server` dentro quella
cartella. Su iPad si apre l'indirizzo in Safari e si usa "Aggiungi a Home" per
averlo a tutto schermo.

Il workflow `.github/workflows/web.yml` fa la stessa cosa a ogni push e
pubblica su GitHub Pages.

Il pacchetto pubblicato pesa circa 200 KB perche' contiene solo i sorgenti e i
dati: il runtime Python-WASM lo carica la pagina da `pygame-web.github.io`
all'apertura. Serve quindi internet sia per costruire sia per giocare, e il
gioco dipende da quel CDN. Per renderlo autonomo bisogna ospitare anche il
runtime insieme alla build.

Differenze rispetto al desktop: i salvataggi vivono in `localStorage` invece
che in `saves/`, non c'e' il pulsante "Esci", e i font di sistema non esistono
nel browser quindi si usa quello incluso in pygame.

## Come si gioca

1. **Nuova carriera** → scegli la scuderia e decidi se essere **costruttore completo**
   (telaio + power unit) o **solo telaio** con motore cliente. Chi parte cliente puo'
   fondare il reparto motori quando vuole, dalla sezione Power unit: da li' servono almeno
   due stagioni di investimenti prima di poter scendere in pista con roba propria.

   Non tutte le squadre possono farlo, ed e' voluto. Un reparto motori e' un'azienda dentro
   l'azienda: costa una fondazione piu' decine di milioni l'anno di sola gestione, e in
   Formula 1 lo regge chi ha una casa automobilistica o un gruppo industriale alle spalle.
   Ferrari, Mercedes, Red Bull e Audi il motore lo fanno gia'. Alpine e Cadillac possono
   aprirlo, perche' dietro hanno Renault e General Motors. McLaren, Williams, Racing Bulls,
   Haas e Aston Martin restano squadre da telaio: comprano la power unit e mettono tutto
   sulla macchina. Il vincolo e' il campo `pu_capable` in `data/teams.json`, con accanto la
   motivazione: se non sei d'accordo, cambialo.
2. Dal **Quartier Generale** gestisci la squadra fra una gara e l'altra.
3. **WEEKEND DI GARA** apre prove libere → qualifica → (sprint) → gara.
4. A fine stagione arrivano premi, mercato e **votazioni sul regolamento**.

### Le sezioni

| Sezione | Cosa fai |
|---|---|
| Quartier Generale | Cruscotto: cassa, budget cap, piloti, reparti, notizie |
| Vettura e assetto | Stato dei dieci componenti, prestazioni derivate, sei regolazioni di assetto (o delega agli ingegneri) |
| Sviluppo | Ripartizione risorse fra le aree, budget di sviluppo per gara, pacchetti di aggiornamento con costo, tempi e rischio |
| Power unit | Confronto fra i motoristi, budget del reparto motori, programma per costruirsi la propria unita' |
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

In alternativa un circuito può portare il campo `geo`, cioè il tracciato vero in coordinate
geografiche: in quel caso forma e curvatura vengono da lì, e la sequenza testuale non serve
più. Le coordinate si scaricano da OpenStreetMap con:

```bash
python tools/fetch_layouts.py            # tutti i circuiti
python tools/fetch_layouts.py --dry-run  # controlla senza scrivere
```

Lo strumento cerca ogni circuito per nome, ricuce le vie spezzate in un anello unico e
confronta la lunghezza ottenuta con quella ufficiale: se lo scarto supera il 12% scarta il
risultato, perché un tracciato sbagliato è peggio di nessun tracciato. Serve rete verso
`nominatim.openstreetmap.org` e `overpass-api.de`.

Google Maps non è utilizzabile: i suoi dati sono proprietari e le condizioni d'uso vietano
di estrarli per usarli altrove. OpenStreetMap è aperto e chiede solo la citazione qui sotto.

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

**Invecchiamento.** A fine stagione vettura e strutture perdono terreno: non si consumano,
e' il resto del mondo che va avanti. Una monoposto lasciata ferma arretra di circa mezzo
punto l'anno, una struttura di poco piu' di uno, e in cima si perde di piu' che a meta'
gruppo. Per stare fermi bisogna investire, per migliorare bisogna investire parecchio: con
il tetto di spesa nessuno riesce a tenere al passo tutte e nove le strutture, quindi
bisogna scegliere quali. Anche le scuderie del computer reinvestono, e siccome le grandi
sono gia' contro il tetto mentre le piccole hanno margine, il gruppo tende a stringersi.

**Power unit.** Ogni motorista cresce gara dopo gara verso un tetto deciso da chi dirige il
reparto e da quanto vale la fabbrica: assumere un buon responsabile powertrain alza quel
tetto. Chi compra il motore da altri puo' fondare un reparto proprio, investirci per almeno
due stagioni e poi decidere quando portarlo in pista: si parte dietro all'ultimo dei
motoristi, e quanto si recupera dipende dai soldi messi e dagli ingegneri ingaggiati.

Avere il motore in casa costa: il reparto va tenuto in piedi tutto l'anno anche senza
svilupparlo, e chi non ha clienti a cui venderlo se lo paga da solo. In cambio si sviluppa
quello che si vuole e si integra la power unit nella vettura invece di riceverla come una
scatola con le sue quote: fra cliente e costruttore pieno ballano circa due decimi al giro.
Lo sviluppo motori sta fuori dal tetto di spesa della squadra.

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
                     powertrain, engineering, market, rules, season
game/storage.py      salvataggi: file su desktop, localStorage nel browser
game/sim/            weekend (motore gara), session (prove, qualifica, griglia)
game/ui/             app, theme, widgets, trackdraw, scenes/, pages/
data/                database JSON
saves/               salvataggi
```

## Crediti

I layout scaricati con `tools/fetch_layouts.py` provengono da OpenStreetMap:
© OpenStreetMap contributors, licenza [ODbL](https://www.openstreetmap.org/copyright).

## Limiti noti

- I 24 tracciati inclusi sono ancora ricostruiti dai dati reali (lunghezza, numero e tipo
  di curve) e non dalle coordinate: la forma è coerente e distinta per ogni pista, non
  identica all'originale. Con `tools/fetch_layouts.py` si sostituiscono con quelli veri.
- Le sprint usano lo stesso formato della qualifica principale.
- Le penalità in gara (bandiere, investigazioni) non sono ancora modellate.
