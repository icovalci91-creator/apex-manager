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

Ogni cifra che si sceglie ha i due pulsantini ai lati del cursore: un clic vale un passo,
tenendoli premuti si accelera, e la rotellina sopra la barra fa la stessa cosa. Il passo si
ricava dal formato del numero - se si legge con due decimali, il passo non e' mai piu'
grosso di quello che si vede - e i valori restano sempre multipli tondi, cosi' l'ingaggio
si ferma a 26.5 M$ e non a 26.4837.

La misura di riferimento e' 1600x900, ma la finestra si apre grande quanto ci sta
davvero sullo schermo: un portatile a 1920x1080 con lo scaling di Windows al 125% ha un
desktop da 1536x864, e aprire piu' grandi di cosi' taglia fuori il bordo destro e il
fondo. La finestra si ridimensiona a piacere e le schermate si riadattano - il menu di
sinistra stringe il passo se le voci non ci stanno - fino a un minimo di 1180x680, sotto
il quale i pannelli non starebbero piu' in piedi.

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
   Alpine e Cadillac possono aprirlo, perche' dietro hanno Renault e General Motors.
   McLaren, Williams, Racing Bulls e Haas restano squadre da telaio: comprano la power unit
   e mettono tutto sulla macchina. Il vincolo e' il campo `pu_capable` in
   `data/teams.json`, con accanto la motivazione: se non sei d'accordo, cambialo.

2. Dal **Quartier Generale** gestisci la squadra fra una gara e l'altra.
3. **WEEKEND DI GARA** apre prove libere → qualifica → (sprint) → gara.
4. A fine stagione arrivano premi, mercato e **votazioni sul regolamento**.

### Motorista, team ufficiale, cliente

Il rapporto con la power unit ha tre forme, nel campo `pu_status`:

| Stato | Chi | Costo fornitura | Integrazione | Sviluppo PU |
|---|---|---|---|---|
| `works` | Ferrari, Mercedes, Red Bull, Audi | zero, ma paghi il reparto (45 M$/anno) | fino a 1.00 subito | lo decidi tu |
| `partner` | Aston Martin con Honda | frazione del listino (8.75 invece di 25 M$) | da 0.42 a 0.85, con gli anni | lo fa la casa, un po' piu' piano |
| `customer` | tutti gli altri | listino pieno | 0.25 | non ti riguarda |

C'e' poi il caso della **squadra satellite**: non un rapporto con un motorista esterno ma
con un'altra squadra in griglia. Racing Bulls sta dentro il gruppo Red Bull, e il campo
`parent_team` le da' quattro vantaggi concreti:

- **fornitura interna** al 45% del listino (10.80 invece di 24 M$)
- **integrazione 0.50**, il doppio di un cliente: la power unit e' gia' allineata al telaio
  della sorella maggiore
- **componenti trasferibili** - cambio, sospensione posteriore e freni arrivano dalla
  squadra maggiore a fine stagione, un passo indietro rispetto all'originale ma molto
  avanti rispetto a quello che progetterebbe da sola
- **vivaio**: quando la squadra maggiore ha un sedile libero pesca prima di tutto dalla
  satellite

Il prezzo lo paga in Commissione: una satellite vota per il 60% secondo l'interesse del
gruppo invece del proprio, che e' la critica classica a chi si ritrova due voti al tavolo.
E i suoi piloti migliori se li vede portare via.

Il caso `partner` e' la via di mezzo, e lo e' in tre modi diversi.

**Costi**: piu' bassi di chiunque, perche' non c'e' infrastruttura da mantenere e la casa
mette marchio e ingegneria. I termini veri dell'accordo Aston Martin-Honda non sono
pubblici: la quota di listino e' un'assunzione, non un dato.

**Integrazione**: non nasce alta, ci arriva. Fra Silverstone e Sakura ci sono un oceano e
un fuso orario, e ogni giro di messa a punto costa piu' tempo che a chi ha il motore nel
capannone accanto. Si parte a 0.42, poco sopra un cliente, e si arriva a 0.85 dopo una
cinquantina di gare insieme. Cambiando fornitore si ricomincia da capo.

**Sviluppo**: la casa investe come e piu' di una squadra works, ma il tramite fra i due
reparti la rallenta. Su due stagioni Honda guadagna circa +3.6 contro il +4.9 di Mercedes.

Un motorista senza squadra propria in griglia continua comunque a sviluppare per conto suo:
altrimenti la sua power unit resterebbe ferma mentre le altre crescono.


### Test privati

Il regolamento vieta di provare in stagione con la vettura dell'anno, ma lascia due porte
aperte che le squadre usano davvero: i TPC, con monoposto di almeno due stagioni fa, e i
filming day. Da qui nascono otto giornate all'anno (`sporting.private_test_days`) da
spendere in quattro programmi diversi:

| Programma | Cosa lascia |
|---|---|
| Chilometri ai giovani | Crescita degli attributi, ma solo per chi ha ancora margine sul potenziale |
| Correlazione galleria-pista | Fino al 45% di rischio in meno sui progetti di sviluppo |
| Lavoro di assetto | Conoscenza del circuito: quando ci si torna in gara si parte gia' in finestra |
| Prova di affidabilita' | Componenti rimessi a punto, meno rotture in gara |

Una giornata di prove costa tre cose diverse, tenute separate perche' si comportano in modo
diverso. I **materiali** - benzina, gomme, ricambi, pezzi di prova - sono uguali dovunque si
vada, perche' la macchina consuma quello che consuma. Il **noleggio** della pista e la
**trasferta** dipendono da dove si va. Tre giornate di correlazione, per la Ferrari:

| Dove | materiali | noleggio | trasferta | totale |
|---|---|---|---|---|
| Fiorano, casa propria | 0,90 | - | - | **0,90** |
| Silverstone | 0,90 | 0,90 | 0,90 | **2,70** |
| Losail | 0,90 | 0,90 | 3,90 | **5,70** |

In casa propria l'uso della pista non si paga: si accende la luce e si gira. Quello che si
paga comunque e' il mantenimento dell'impianto, tutto l'anno che ci si giri o no, e le
migliorie, che passano dal budget delle costruzioni come ogni altra struttura.

I materiali sono pochi perche' non e' un weekend di gara: si gira con una monoposto di due
anni fa e mezza squadra. A pesare e' andare a casa d'altri - noleggio della pista,
marshall, cronometraggio, camion - e su otto giornate la differenza fra girare in casa e
andare a Silverstone e' di 4,8 M$ l'anno.

### Le prove collettive

Prima che cominci il campionato la Formula 1 organizza le prove collettive: **due sessioni
di tre giorni**, tutte le squadre insieme sulla stessa pista, tradizionalmente **Barcellona
e il Bahrein**. Li' si gira con la macchina dell'anno, che e' la sola occasione di tutta la
stagione: da marzo in poi il regolamento lo vieta. Non tolgono giornate di test privati -
sono due conti diversi - e non si saltano per mancanza di fondi, semmai si taglia altrove.

E' li' che si scopre la macchina nuova. Su una stagione intera, una Ferrari che ci va
arriva al 66% di conoscenza della vettura e al 20% di correlazione, contro il 51% e lo zero
di una che le salta - e sono 451 punti contro 289. Non e' un vantaggio: e' la base da cui
partono tutti, e non andarci e' una ferita che ci si fa da soli.

Tutto questo sta dentro il tetto di spesa, quindi ogni prova e' sviluppo in meno. Si puo' girare anche fuori dal calendario:
Tsukuba, Mugello, Paul Ricard, Portimao e gli altri candidati sono li' apposta.

Chi ha una pista di proprieta' gioca un altro campionato: due giornate in piu' all'anno,
perche' un filming day in casa si organizza senza chiedere niente a nessuno, e il 30% in
meno di costo, perche' buona parte del lavoro si fa senza muovere i camion.

A fine stagione le giornate si azzerano, la correlazione si dimezza e la conoscenza dei
circuiti invecchia: cambia la macchina, e il lavoro va rifatto.

### Le sezioni

| Sezione | Cosa fai |
|---|---|
| Quartier Generale | Cruscotto: cassa, budget cap, piloti, reparti, notizie |
| Vettura e assetto | Stato dei componenti, power unit e cambio da sostituire prima che cedano, e un assetto per pilota con il riferimento corretto per il suo stile |
| Sviluppo | Lavoro di reparto per area, conoscenza della vettura, pacchetti di aggiornamento con costo, tempi e forbice degli esiti, specifiche in verifica da tenere o rimontare |
| Power unit | Confronto fra i motoristi, specifica in lavorazione al banco e quando omologarla, programma per costruirsi la propria unita' |
| Ingegneri | Riunione tecnica: dove sei rispetto alla griglia, su cosa lavorare, allocazione consigliata |
| Vivaio | I ragazzi che crescono in casa: chi c'e', quanto vale, quando promuoverlo a terzo pilota o a titolare. Chi il vivaio non ce l'ha puo' aprirlo, se se lo puo' permettere |
| Piloti e mercato | La scheda di ogni pilota - attributi col numero accanto alla barra, potenziale residuo, indennizzo per portarlo via, licenza e carriera - e sotto il tavolo della trattativa: ingaggio, durata, bonus vittoria/podio/punto, clausola |
| Staff tecnico | Organigramma, mercato e la scheda di chiunque: attributi con il numero accanto alla barra, valore nel ruolo, confronto con chi quel posto ce l'ha adesso e probabilita' che accetti |
| Organico reparti | Quante persone lavorano in aerodinamica, progettazione, powertrain, simulazione e affidabilita': si assume, si taglia, e si paga |
| Infrastrutture | Dieci strutture da potenziare o costruire, budget capitale a parte dal cap, obsolescenza, confronto con gli avversari |
| Test privati | Otto giornate l'anno (dieci con una pista di proprieta') piu' le prove collettive di inizio stagione: dove girare, con chi, per quale programma |
| Finanze e sponsor | Bilancio per mese e per anno, trattative con gli sponsor |
| Regolamento | Norme in vigore, scala ATR, proposte in discussione e tavolo tecnico per il ciclo che verra' |
| Classifiche / Calendario / Storico | Mondiali, i tracciati con la scheda di ogni gran premio, cicli tecnici e albo d'oro |

### La scheda di un gran premio

Dal calendario si clicca su un circuito e si apre la sua scheda, che tiene insieme tutto
quello che riguarda quel gran premio:

- **Il tracciato** disegnato in grande, con lunghezza, curve, giri (quelli veri di questa
  carriera, se si corre a distanza ridotta) e perdita ai box.
- **Com'e' fatto**: carico, potenza, frenata, consumo gomme, possibilita' di sorpasso e
  sconnessioni.
- **Che macchina ci vuole**: le caratteristiche del circuito tradotte nelle aree su cui si
  sviluppa, ognuna col nostro livello a fianco. Se su quelle che contano qui siamo sotto, lo
  dice: *"Qui ci mancano: potenza, frenata."*
- **Il gran premio di quest'anno** se e' gia' stato corso: ordine d'arrivo, ritiri con la
  causa, punti, pole e giro veloce. Se non e' ancora stato corso, quante gare mancano e
  quanto conosciamo il circuito dai test privati.
- **L'albo d'oro**: stagione per stagione vincitore, squadra, pole con il tempo, giro veloce
  e meteo. Si riempie gara dopo gara e resta anche per i circuiti che escono dal calendario,
  perche' i risultati veri si conservano solo tre stagioni mentre l'albo no. Chi vince piu'
  volte sulla stessa pista viene chiamato per nome: *"Il re di questa pista e' Charles
  Leclerc, con 3 vittorie."*

Sulla griglia del calendario, in alto a destra, c'e' la stessa lettura fatta sull'insieme:
**cosa chiedono le gare che restano** e su quali di quelle aree siamo indietro. E' la
risposta alla domanda "dove mando i soldi adesso", che dipende da quali gran premi mancano
e non da quello di domenica.

### Menu ed editor

Il tasto **Menu** in fondo alla barra laterale apre un menu sopra la partita, senza
abbandonarla: nuova partita, salva partita (con il nome che si vuole, o sovrascrivendo un
salvataggio esistente), carica partita, e l'interruttore dell'**editor di gioco**.

L'editor non ha un elenco di cose modificabili scelto da qualcuno: ha un percorso. Si parte
dalle radici - squadre, piloti, staff, circuiti in calendario e candidati, regolamento,
Commissione, proposte, motoristi, sponsor, cicli tecnici, risultati e le costanti di
taratura di quattordici moduli - si scende dentro finche' non si arriva a un valore, e quel
valore si riscrive. Sono **91.824 valori raggiungibili e scrivibili**, contati percorrendo
tutto l'albero della partita: dalla prestazione di un fondo al bonus vittoria di un
contratto, dalla singola coordinata di un tracciato a `TECH_DECAY`.

Le voci calcolate dal gioco a partire da altre (la valutazione di una vettura, il valore di
mercato di un pilota) si vedono ma non si scrivono, e il pannello lo dice: si cambiano
quelle da cui dipendono. I tipi vengono rispettati - un numero resta un numero, un si/no
resta un si/no - perche' cambiare il tipo di un campo sotto ai piedi del gioco lo farebbe
esplodere in un punto lontanissimo da li'. Una partita toccata con l'editor se lo porta
scritto nel salvataggio.

### Le gomme del weekend

Il weekend comincia prima di scendere in pista. Il fornitore nomina tre mescole della sua
gamma - da C1, la piu' dura, a C6 - scelte in base a quanta energia il tracciato mette
nelle gomme: **C1-C2-C3 a Losail**, **C2-C3-C4 a Bahrain e Silverstone**, **C4-C5-C6 a
Monaco**. E non e' solo un'etichetta: la stessa "morbida" a Monaco e a Silverstone e' una
gomma diversa, e dura di conseguenza.

Poi si scelgono i set. Tredici per pilota (dodici nei weekend con la sprint), di cui tre
li decide il regolamento - due mescole tenute per la gara e una morbida riservata al Q3 -
e **dieci si dividono come si vuole**. La scelta si consegna prima di arrivare in pista e
da quel momento e' pubblica: finche' non consegni la tua non sai cosa hanno in mano gli
altri, e appena consegni le vedi tutte.

Chi ha caricato morbide fa un giro secco migliore e finisce le gomme in gara; chi ha
caricato dure vive peggio il venerdi' e meglio la domenica. Misurato su otto gare
identiche ad Albert Park, con la stessa macchina e lo stesso pilota:

| Scelta | Qualifica media | Arrivo medio |
|---|---|---|
| 8 morbide / 2 medie / 0 dure | **2.6** | 5.1 |
| 6 / 3 / 1 | 4.9 | 6.9 |
| 3 / 3 / 4 | 4.4 | **3.0** |

E i set si consumano davvero: due per ogni sessione di libere, uno per ogni turno di
qualifica, uno per ogni stint di gara. Se arrivi al sabato senza morbide nuove il giro
buono lo fai con le medie e paghi tre decimi; se arrivi alla domenica senza dure, il piano
soste te lo detta il camion e non il muretto. Le squadre del computer scelgono in base a
dove sono in classifica: chi sta davanti difende la gara e carica dure, chi insegue si
gioca la qualifica.

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
python tools/fetch_layouts.py                    # quelli che ancora non ce l'hanno
python tools/fetch_layouts.py --pool candidati   # solo i circuiti fuori calendario
python tools/fetch_layouts.py --only monza spa
python tools/fetch_layouts.py --dry-run          # controlla senza scrivere
```

Guarda sia le gare in calendario sia i circuiti candidati a entrarci, e salta quelli che
hanno gia' il tracciato: rilanciarlo costa poche richieste. Con `--force` li rifa'.

Lo strumento cerca ogni circuito per nome, ricuce le vie spezzate in un anello unico e
confronta la lunghezza ottenuta con quella ufficiale: se lo scarto supera il 12% scarta il
risultato, perché un tracciato sbagliato è peggio di nessun tracciato. Serve rete verso
`nominatim.openstreetmap.org` e `overpass-api.de`.

Google Maps non è utilizzabile: i suoi dati sono proprietari e le condizioni d'uso vietano
di estrarli per usarli altrove. OpenStreetMap è aperto e chiede solo la citazione qui sotto.

**Infrastrutture.** Una struttura appena rifatta resta di riferimento per tre stagioni e in
quel periodo non perde nulla: e' il premio di chi investe. Dopo comincia a restare indietro,
e piu' passa il tempo piu' in fretta lo fa, perche' nel frattempo gli altri sono andati
avanti. Un potenziamento azzera il contatore. Tenere una galleria del vento di livello 90
costa circa 4 M$ l'anno spalmati, non ventitre come nella prima versione del modello.

**Piste di proprieta'.** Ferrari ha Fiorano e Red Bull il Red Bull Ring: chi ce l'ha gia'
non paga niente per averla, se la ritrova nel bilancio come qualsiasi altra struttura. Chi
non ce l'ha puo' costruirla, e costa: 140 M$ di cassa vera per aprirla al livello 55, poi la si potenzia come le altre (circa 19 M$ il primo gradino, oltre 36 a
livello 80) e la si mantiene per sempre. In cambio si prova quando si vuole: due giornate
di test in piu', prove che costano il 30% in meno, assetto piu' vicino alla finestra
gia' al venerdi', aggiornamenti che si digeriscono prima e giovani che crescono di piu'.
Anche le scuderie del computer se la costruiscono, quando la cassa lo permette.

**Il calendario non e' fisso.** Ogni circuito ha un contratto con una scadenza, un canone
annuo e un grado di tradizione. Alla scadenza si rinnova o si esce, e a decidere sono tre
cose che tirano in direzioni diverse: quanto paga il promotore, quanto pubblico porta, e
quanto la pista e' intoccabile. Monaco paga poco e non si tocca; una pista nuova paga molto
ma non ha storia da spendere quando i conti cambiano. Chi esce finisce nel serbatoio dei
candidati e puo' rientrare piu' avanti, ma non la stagione dopo.

Il serbatoio parte con dieci circuiti che premono per entrare - Imola, Portimao, Mugello,
Istanbul, Sepang, Hockenheim, Kyalami, Paul Ricard, Nurburgring, Buenos Aires - e si
riempie con chi perde il posto. Su otto stagioni di prova il calendario resta fra le 23 e
le 24 gare, Monaco, Monza, Silverstone e Spa non se ne vanno mai, e i mesi si
ridistribuiscono da marzo a dicembre a ogni cambio.

Canoni e scadenze in `data/tracks.json` seguono l'ordine di grandezza di quelli riportati
dalla stampa: i circuiti mediorientali pagano 50-58 M$, i classici europei 16-27 e in
cambio non si discutono.

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

**Assetto.** Trovarlo non costa niente: e' il lavoro del weekend. Quello che costa viene
prima. Nei giorni precedenti si va al simulatore - una sessione costa fra 0,1 e 0,25 M$
dentro il tetto di spesa, e se ne possono fare due, perche' alla terza il modello ha gia'
detto quello che sapeva - e da li' esce un **assetto sulla carta**, che e' una previsione,
non una verita'. Quanto ci prende dipende da che simulatore si ha, da quanto quel
simulatore assomiglia alla realta' (la correlazione dai test), da quanto si conosce il
circuito, da quanto si e' capita la macchina e dall'avere o no una pista di proprieta':

| | senza simulatore | una sessione | due sessioni |
|---|---|---|---|
| Ferrari (simulatore 90, Fiorano) | +/-17 punti | +/-9 | +/-5 |
| Williams (simulatore 84) | +/-20 | +/-11 | +/-6 |

Poi si va in pista e la pista risponde. A ogni sessione di prove i piloti dicono cosa fa la
macchina e gli ingegneri leggono i dati: il riferimento si sposta verso quello che serve
davvero, ma di poco per volta e con un residuo di rumore, perche' gomme, benzina, vento e
asfalto raccontano ogni volta una storia leggermente diversa. Quanto si impara dipende
dalle persone - il feedback dei piloti, i performance engineer, il direttore tecnico, il
race engineer - e non dagli strumenti: quelli hanno gia' detto la loro al simulatore.

Il giocatore non vede mai l'assetto giusto. Vede il riferimento del reparto (il triangolo
dorato sui cursori), quanto quel riferimento e' affidabile, e quanto la macchina gli e'
vicina: si puo' essere convinti di avere tutto a posto e prendere mezzo secondo. La verita'
si legge solo sul cronometro.

Quanto pesa dipende da quante prove libere ci sono. In un weekend normale sono tre, e tre
sessioni rimediano gran parte di un riferimento sbagliato: si perde il venerdi', non la
domenica. In un weekend sprint ce n'e' una sola, e li' quello che non si e' preparato prima
non si recupera piu':

| Perdita al giro dopo tutte le prove | senza simulatore | una sessione | due sessioni |
|---|---|---|---|
| Weekend normale (3 prove libere) | +0,20 s | +0,07 s | +0,06 s |
| Weekend sprint (1 prova libera) | +0,78 s | +0,38 s | +0,11 s |

Su una stagione intera si vede in griglia: la Ferrari passa da 6,8 di media senza mai
toccare il simulatore a 6,1 preparando ogni weekend, la Williams da 12,5 a 10,9. Costa
dai 5 ai 12 M$ a stagione dentro il tetto di spesa, cioe' meno di un pacchetto grande di
aggiornamenti.

**Sviluppo.** Due cose distinte, come nella realta'.

Il *lavoro di reparto* - il budget continuo, ripartito fra le aree - non e' un
aggiornamento: sono affinamenti. In prestazione pura rende poco (il 22% di quello che
renderebbe se fosse sviluppo vero); quello che lascia davvero e' la **conoscenza della
vettura**, che si vede il venerdi', quando si trova subito la finestra di assetto invece
di passarci tre sessioni. A fine stagione ne resta un terzo: la macchina nuova e' un'altra
macchina, ed e' il motivo per cui a marzo brancolano tutti. Dopo un cambio di regolamento
ne resta il 15%.

Il salto vero lo fanno i **pacchetti di aggiornamento**: si scelgono componente e taglia,
si pagano, arrivano dopo una, tre o sei gare. E possono non funzionare. Quanto spesso
dipende dalla *fiducia del reparto*, che mette insieme:

| Cosa | Peso |
|---|---|
| Reparti (aero, meccanica, powertrain, pesati per il tipo di componente) | 42% |
| Strumenti con cui si valida: galleria, CFD, ufficio tecnico, fabbrica, simulatore - e quanto sono vecchi | 28% |
| Il direttore tecnico | 16% |
| Ore di galleria concesse dalla scala ATR | 14% |
| in aggiunta: correlazione dai test privati (+22%) e conoscenza della vettura (+10%) | |
| in sottrazione: la taglia del pacchetto (medio -6%, grande -14%) | |

**Quanto costa, e chi ci lavora.** Un aggiornamento non e' una fattura: e' un gruppo di
persone che per settimane disegna, prova in galleria, fa i pezzi e li monta. Il conto si
legge in chiaro prima di firmare - materiali piu' straordinari - ma il vincolo vero e'
un altro: **quelle persone non si sdoppiano**.

| Taglia | Persone | Gare | Costo tipico (fondo) |
|---|---|---|---|
| Piccolo | 10 | 1 | 1,6 M$ |
| Medio | 26 | 3 | 3,8 M$ |
| Grande | 52 | 6 | 7,0 M$ |

Un pacchetto grande sull'aerodinamica impegna 52 persone del reparto per sei gare. Se il
reparto ne ha 88, il secondo pacchetto grande non parte: *"servono 52 persone e il reparto
ne ha 36 libere: o si assume, o si chiude un cantiere"*. E' qui che l'organico smette di
essere un numero e diventa la ragione per cui una squadra sviluppa piu' in fretta di
un'altra.

Da li' escono quattro esiti: *fallito* (da -30% a +15% del previsto), *sottotono*, *in
linea*, *oltre le attese*. Con un pacchetto grande una squadra di vertice fallisce circa
una volta su sei, una di coda una volta su tre. La pagina Sviluppo mostra la forbice prima
di spendere, e gli ingegneri dicono cosa ci sta tradendo.

Un pacchetto sbagliato pero' non si scopre in fabbrica: si scopre in pista. La specifica
nuova va in macchina e il verdetto arriva dopo che ha girato un weekend, quando i
cronometri dicono un'altra cosa rispetto alla galleria. A quel punto tocca decidere, e
nessuna delle due strade e' gratis:

| | Cosa costa | Cosa lascia |
|---|---|---|
| Rimontare la vecchia | il 20% del prezzo del pacchetto - i disegni ci sono, i pezzi no | la macchina di prima, e il pacchetto pagato e' buttato |
| Tenerla e affinarla | il 6% a gara per quattro gare, e un banco del reparto occupato | una possibilita' di venirne a capo, che dipende da quanto il reparto sa capire perche' non funziona |

Quanto convenga insistere dipende dagli strumenti. Su duecento pacchetti falliti uguali,
la Ferrari che insiste finisce a +0,37 sulla specifica vecchia e resta sotto nel 12% dei
casi; la Williams a +0,23 con il 18%; la Haas a +0,15 con il 26%, e per lei quel banco
occupato per quattro gare pesa il doppio. Chi rimonta la vecchia torna sempre esattamente
da dove era partito. Spesso un pacchetto fallito non peggiora la macchina, semplicemente
non porta niente: in quel caso non c'e' niente da rimontare e l'unica strada e' provare a
capirlo. Le scuderie del computer decidono con lo stesso criterio, e a fine stagione ogni
verifica aperta si chiude da sola: la macchina nuova e' un'altra macchina.

C'e' un terzo costo, oltre ai soldi e al tempo: **l'assetto va ritrovato**. Un fondo nuovo
non e' un pezzo in piu' sulla stessa macchina, e quello che si sapeva su come farla
funzionare vale meno di prima. Un pacchetto grande manda in fumo fino al 45% della
conoscenza della vettura e buona parte del lavoro fatto sui singoli circuiti; uno piccolo
quasi niente. Anche un pacchetto fallito costa la meta' di quel disturbo, perche' in pista
ci e' comunque andato. Simulatore e pista di proprieta' riducono il conto: e' li' che si
fa il lavoro che altrimenti tocca fare il venerdi'.

**Contratti.** Rinnovi e acquisti passano da una trattativa vera, non da un si' o un no.
Il pilota apre con una richiesta e si risponde con un'offerta su cinque voci: ingaggio
fisso, durata, bonus vittoria, bonus podio, bonus per punto iridato e clausola
rescissoria. Lui giudica il pacchetto intero, non il fisso, e ai bonus da' il valore
atteso: quante vittorie, quanti podi e quanti punti si aspetta da quel sedile in un anno.
In una squadra da mondiale spostare meta' dell'ingaggio sui premi non gli cambia quasi
niente; in fondo alla griglia un bonus vittoria vale zero e lo sa. La clausola abbassa il
valore percepito - e' un vincolo a suo carico - ma e' l'unica cosa che protegge davvero da
chi lo vuole: se c'e', si paga quella cifra invece dell'indennizzo. Le trattative hanno un
numero limitato di giri: sparare basso per vedere l'effetto le brucia.

**Il livello delle monoposto non ha un tetto.** Averlo a 100 significava che prima o poi
tutti ci arrivavano: su sedici stagioni misurate, i componenti sopra 97 passavano dallo 0%
al 36% e le prime squadre diventavano indistinguibili, appoggiate allo stesso muro. Adesso
il numero e' libero di crescere, e a rallentarlo non e' un limite ma la difficolta'.

Ogni ciclo tecnico ha un **riferimento** - il livello a cui sta la griglia quando un
regolamento e' nuovo - e da li' si misura quanto e' faticoso guadagnare ancora:

| Livello del componente | Quanto rende ancora lo sviluppo |
|---|---|
| 12 punti sotto il riferimento | x1,30 - i problemi grossi sono ancora tutti li' |
| al riferimento | x1,05 |
| 8 sopra | x0,77 |
| 13 sopra | x0,54 |
| 18 sopra | x0,36 |
| 28 sopra | x0,17 |

Non si arriva mai a zero: si arriva a rendimenti cosi' bassi che conviene spendere altrove.
Chi spinge al massimo dentro un ciclo lungo arriva intorno a 105 e li' si ferma, perche' il
guadagno di un pacchetto grande scende da +5,1 a +1,5 e l'invecchiamento se lo mangia. Chi
e' sotto il riferimento recupera piu' in fretta di quanto la testa scappi.

**A ogni cambio di regolamento il livello si ricalcola al ribasso.** Non e' un reset: e'
che la macchina nuova nasce peggiore di quella perfezionata per anni, e piu' ci si era
raffinati piu' se ne perde. Il riferimento del ciclo sale di un paio di punti - la
tecnologia avanza - ma quello che si era accumulato sopra si conserva solo in parte, dal
25% se il regolamento e' una rivoluzione al 90% se e' un ritocco, e chi ha preparato il
nuovo ciclo ne conserva molto di piu' degli altri.

Su sedici stagioni con un ciclo ogni cinque anni viene fuori un dente di sega: dentro il
ciclo la griglia si allunga (divario da 12,7 a 17,3 punti), al cambio si accorcia di colpo
(a 10,2) e tutti scendono, i primi molto piu' degli ultimi - la migliore da 95,7 a 86,5,
l'ultima da 78,4 a 76,3. Nessun componente si accumula piu' contro un tetto.

**Costruire non passa dal tetto di spesa.** Come nella realta': il regolamento finanziario
tiene la spesa in conto capitale - una galleria del vento, un simulatore, un capannone
nuovo - fuori dal budget tecnico, e le da' un limite suo, contato su piu' stagioni invece
che anno per anno. Nel gioco sono **45 M$ su quattro stagioni**, con una scala che arriva a
**70 M$ per l'ultima in classifica**: serve proprio a lasciare a chi e' indietro il modo di
rimettersi in pari. Dentro il tetto tecnico resta la gestione di quello che si e'
costruito - energia, manutenzione, chi ci lavora - che per una squadra attrezzata sono
37-39 M$ l'anno.

Prima era tutto dentro il cap, e si vedeva: le strutture si mangiavano fra il 27% e il 43%
del budget tecnico ogni stagione, cioe' un quarto abbondante dei soldi dello sviluppo
finiva in mattoni. E il conto non tornava comunque: una squadra perdeva **10,3 punti di
strutture l'anno** per obsolescenza e con tutto il budget delle costruzioni ne comprava
**1,2**. Un divario di nove volte, che nessuna gestione poteva colmare.

Rimessi in scala tutti e due i lati - i potenziamenti costano meno della meta' di prima, e
l'invecchiamento un terzo - adesso si perdono 3,1 punti l'anno e con il budget pieno se ne
comprano 2,8. Su otto stagioni misurate: chi costruisce quanto puo' resta a **80,5**, chi
non costruisce mai scende a **77,7**, e il limite si sente davvero - due stagioni di
investimenti pieni e poi due di attesa, perche' la finestra dei quattro anni e' esaurita.

L'unica cosa che sta fuori da entrambi i tetti e' costruirsi un autodromo: Fiorano e' della
Ferrari e il Red Bull Ring della Red Bull, cioe' proprieta' del gruppo e non del reparto
corse. Si paga con la cassa e basta - 140 M$ - ma da li' in poi mantenerlo e potenziarlo
segue le regole di tutte le altre strutture.

E una pista di proprieta' e' un posto vero: compare fra i circuiti dove andare a provare.
Fiorano sta nei dati come tracciato (2,976 km, 14 curve) insieme a un modello generico per
chi se ne costruisce una, che prende il nome della squadra; il Red Bull Ring c'era gia',
perche' e' anche una gara del mondiale. Girarci non costa niente oltre ai materiali: e' li'
che una pista di proprieta' comincia a ripagarsi.

**Il montepremi ha due colonne.** Come nella realta': una parte del piatto e' uguale per
tutti - 47 M$ a testa, il 45% dei 1150 distribuiti dal promoter - e il resto va a scalare
sul piazzamento nel costruttori. Meta' di quello che incassa una squadra non dipende da
dove e' arrivata, ed e' il motivo per cui una di coda sta in piedi. C'e' anche il premio di
anzianita', il 5% del piatto, che nella realta' prende chi c'e' da sempre e porta pubblico
e sponsor a tutto il campionato: nel gioco e' un flag in `data/teams.json`, oggi acceso
sulla Ferrari.

Prima c'era una sola scala, tutta legata al piazzamento: il primo prendeva 172 M$ e
l'ultimo 53, un rapporto di **3,26**. Adesso sono 137 e 75, cioe' **1,84**, e la Ferrari da
prima arriva a 195 con l'anzianita'.

**Le scuderie del computer fanno il budget come si fa un budget.** Prima spendevano in
proporzione a quanto avevano in banca, e si vedeva: dare piu' soldi a una squadra di coda
non la salvava, ne spendeva di piu' e chiudeva in perdita lo stesso. Adesso partono da
quello che incassano, tolgono i costi che non si possono evitare - stipendi, strutture,
piloti, motore, trasferte, e una riserva per i danni, che arrivano sempre - e mettono sul
tavolo quello che resta. E' un portafoglio di stagione, non un limite sul singolo impegno:
un vincolo per pacchetto non bastava, perche' chiuso uno se ne apriva un altro e a fine
anno il conto era triplo. Chi resta senza margine smette di provare al simulatore, salta le
giornate di test e non apre cantieri.

Il risultato e' un bilancio che si legge: McLaren chiude a +68 con quasi 400 M$ di sponsor,
la meta' della griglia sta fra -10 e +20, e i due costruttori nuovi - Audi e Cadillac -
perdono 20-30 M$ costruendosi il reparto motori, che e' esattamente quello che sembra un
ingresso in Formula 1.

**Il proprietario, e perche' l'utile resta dentro.** A fine stagione chi ha chiuso in
perdita se la fa coprire dalla proprieta', ma non gratis: l'anno dopo il budget e' stretto,
e sviluppo, costruzioni e giornate di test scendono in proporzione. La stretta si allenta
da sola quando i conti tornano, cosi' chi perde poco tutti gli anni si stabilizza intorno
al 35%: fatica, ma non muore, che e' quello che succede davvero in fondo alla griglia.

L'utile invece **non viene prelevato**: resta in cassa. Il proprietario di una scuderia non
e' un azionista che stacca il dividendo, e soprattutto quei soldi servono, perche' non
tutto passa dal tetto di spesa. Basta guardare quanto incassa ogni squadra e quanto
potrebbe spendere al massimo - il tetto di spesa piu' gli ingaggi dei piloti, la power
unit e la quota annua per le costruzioni:

| | Entrate | Spesa massima | Saldo |
|---|---|---|---|
| McLaren | 405 | 291 | **+114** |
| Mercedes | 348 | 294 | +54 |
| Red Bull | 322 | 331 | -9 |
| Ferrari | 335 | 365 | -30 |
| Williams | 220 | 277 | -57 |
| Aston Martin | 199 | 271 | -72 |
| Haas | 147 | 264 | -117 |
| Alpine | 139 | 269 | -130 |
| Cadillac | 119 | 278 | **-159** |

Nove squadre su undici non arrivano nemmeno a riempire il budget che il regolamento gli
concederebbe: per loro il vincolo non e' il tetto di spesa, e' la liquidita'. Togliergli
l'utile a dicembre significherebbe togliergli l'unico modo di uscire da li'. Solo le prime
due generano piu' di quanto possano spendere, e quel margine si vede in cassa invece di
sparire.

**E i soldi si spendono.** Perche' la liquidita' conti davvero, chi ha capitale oltre la
riserva di lavoro (75 M$) spinge su tutto quello che il denaro puo' comprare: mette sul
tavolo fino al 95% di quello che avanza invece del 55%, apre pacchetti piu' grossi, usa
tutta la quota per le costruzioni ogni anno invece di alternarla, e paga fino al 40% sopra
il valore di mercato per prendersi il pilota che vuole.

Ed e' arrivato anche il mercato degli uomini per le scuderie del computer, che prima non
esisteva: il loro organigramma restava quello del primo giorno per sempre. Adesso chi ha
capitale interviene sul ruolo messo peggio - direttore tecnico, responsabile aerodinamica,
capo progettista, powertrain, strategia - e se lo compra dal mercato dei liberi. E' la leva
piu' diretta che ha una squadra per andare piu' forte, e adesso ce l'hanno tutti.

**L'organico dei reparti.** Un capo aerodinamico da solo non disegna una macchina.
Dietro ogni nome dell'organigramma ci sono decine di persone, e quante sono conta quanto
sono bravi quelli che le dirigono. Cinque reparti, ognuno con una dimensione di
riferimento - quella di una squadra di vertice in salute:

| Reparto | Riferimento | Costo a persona | Cosa muove |
|---|---|---|---|
| Aerodinamica | 90 | 0,094 M$ | carico e efficienza |
| Progettazione | 70 | 0,102 M$ | telaio, sospensioni, trasmissione |
| Powertrain | 50 | 0,107 M$ | la power unit, per chi se la costruisce |
| Simulazione e dati | 45 | 0,098 M$ | quanto si azzecca l'assetto |
| Qualita' e affidabilita' | 35 | 0,086 M$ | le rotture che non capitano |

L'organico moltiplica i responsabili da **x0,62** (reparto vuoto) a **x1,2** (molto sopra
il riferimento), con rendimenti decrescenti: oltre un certo punto le persone si
intralciano invece di aiutarsi. Chi compra il motore tiene solo il gruppo che lo integra,
un terzo del riferimento, e il metro torna quello di tutti dal giorno in cui fonda il
reparto motori.

Gli stipendi stanno **dentro il tetto di spesa**: ogni persona in piu' e' un pezzo di
aggiornamento in meno, ed e' letteralmente la scelta che il cost cap ha imposto a mezza
griglia. Assumere costa una ricerca una tantum e non e' istantaneo - non si cresce di piu'
del 28% del riferimento in una stagione - e mandare a casa costa una buonuscita fuori dal
cap. Le scuderie del computer fanno lo stesso conto: chi incassa assume, chi non ce la fa
taglia fino al 40% del riferimento e poi si ferma, perche' sotto quella soglia un reparto
non esiste piu'.

Il monte stipendi dei responsabili e' stato dimezzato: quello che si legge adesso e'
l'ingaggio di una persona sola, mentre il costo del reparto lo paga l'organico. I conti
totali restano dove erano - Ferrari 67 M$ di personale, Cadillac 20 - solo che adesso si
vede da cosa sono fatti.

**Un mercato vero.** Prima c'erano 12 piloti svincolati e una manciata di ingegneri
liberi. Adesso sono **42 piloti** - da Ricciardo e Magnussen senza sedile fino ai ragazzi
delle formule minori, Slater a 18 anni con 89 di potenziale - e **56 ingegneri** al via,
almeno due per ogni ruolo, con qualche pezzo pregiato da 78-88 in mezzo a tanta gente
onesta. Ogni inverno ne arrivano altri quattordici e cinque-nove giovani salgono dalle
minori; il mercato tiene i migliori centocinquanta e lascia andare la coda.

**Il terzo pilota.** Ogni contratto ha un posto: titolare o riserva. Una riserva costa il
30% di un titolare, ma chi un volante ce l'ha non firma per stare fermo, e piu' uno vale
piu' vuole essere pagato per aspettare. Serve davvero: quando un titolare sconta una
squalifica prende il suo posto invece di far correre una macchina sola, e nei test privati
e' lui che sale in macchina.

**Il vivaio.** Otto squadre su undici ne hanno uno, con i ragazzi che ci stanno davvero -
Camara, Taponen e Wharton in Ferrari, Ugochukwu e Dunne in McLaren, Goethe e Tramnitz in
Red Bull, Browning e Voisin in Williams. Racing Bulls, Haas e Cadillac no.

Aprirlo costa **15 M$** una volta sola e poi **4-6 M$ l'anno** di gestione, fuori dal tetto
di spesa: e' un programma della casa, non un costo della monoposto. Ed e' li' il punto -
non e' una spesa che si fa e finisce, e' un conto che torna solo se lo si regge per anni,
perche' un ragazzo entra a sedici anni e ne servono tre prima che valga qualcosa. Chi non
ha margine nel bilancio non lo apre: Cadillac, con quello che le avanza, non lo tiene
aperto un anno.

Che gente arriva dipende da osservatori, struttura e nome della squadra: un top team pesca
ragazzi da 72-75 con 85-92 di potenziale, una squadra di meta' gruppo da 58-62. Crescono
ogni stagione, e le giornate di test private li fanno crescere il doppio. A 24 anni il
percorso finisce: o salgono in prima squadra o lasciano il programma. E chi il vivaio non
ce l'ha compra i ragazzi degli altri, pagandoli.

**Invecchiamento.** A fine stagione vettura e strutture perdono terreno: non si consumano,
e' il resto del mondo che va avanti. Una monoposto lasciata ferma arretra di circa mezzo
punto l'anno, una struttura di poco piu' di uno, e in cima si perde di piu' che a meta'
gruppo. Per stare fermi bisogna investire, per migliorare bisogna investire parecchio: con
il tetto di spesa nessuno riesce a tenere al passo tutte le strutture, quindi
bisogna scegliere quali. Anche le scuderie del computer reinvestono, e siccome le grandi
sono gia' contro il tetto mentre le piccole hanno margine, il gruppo tende a stringersi.

**Delegare, e a chi.** Il reparto puo' lavorare da solo: si accende "decide il reparto"
nella pagina Sviluppo e da li' in poi ripartizione, pacchetti e taglie li sceglie lui. Non
e' gratis ne' uguale per tutti - quanto viene bene lo dice la **lucidita'**, che nasce dal
direttore tecnico e dal team principal. Un reparto lucido apre il pacchetto giusto sulla
parte giusta; uno meno lucido ogni tanto insegue quella sbagliata e sceglie la taglia
sbagliata. Su dodici gare simulate, delegando a un reparto forte la macchina cresce di
+0,27 contro +0,06 lasciando fare al minimo sindacale, spendendo pure un po' meno.

Lo stesso vale per l'assetto: **"se ne occupano gli ingegneri di pista"** e' acceso per
difetto. Il reparto prepara il riferimento al simulatore da solo prima di ogni weekend, e
chi ha buoni ingegneri ne fa due sessioni invece di una. Dimenticarsene porta il
riferimento da +/-6 punti a +/-19, che e' la differenza fra arrivare in pista sapendo dove
si va e arrivarci a tentoni.

**Il direttore finanziario.** Una figura nuova nell'organigramma, e serve a una cosa sola:
sapere in anticipo dove si andra' a finire col tetto di spesa. Somma quello che e' gia'
uscito, quello a cui ci si e' impegnati con i pacchetti aperti e quello che le gare che
restano si porteranno via comunque, e ne esce una previsione con una forbice.

La forbice la decide lui: da **+/-18 M$** con un direttore scarso a **+/-2,5 M$** con uno
bravo. Non fa risparmiare un milione - fa sapere quanto si puo' impegnare senza rischiare,
che nel tetto di spesa e' la stessa cosa. Nella pagina Finanze c'e' il conto intero con la
barra di quanto e' gia' impegnato e dove cade la stima; e prima di aprire un pacchetto e'
lui a dire se ci sta: *"siamo al limite, il margine e' 4 M$ con un'incertezza di 6. Non ci
metterei altro."*

**Il verdetto arriva dalla pista.** Quando un pacchetto e' pronto va in macchina, ma quanto
ha portato non lo dice la galleria: lo dicono i cronometri dopo un weekend. Alla gara dopo
arriva il verdetto - *"porta +2.9 sulla vecchia, meno dei +5.4 promessi"* - e con lui
**cosa ne pensano i due piloti**, che non e' la stessa cosa.

Ogni pacchetto ha un suo carattere: rifare l'ala anteriore fa girare la macchina, lavorare
dietro la pianta. Chi stacca tardi e vuole l'anteriore che morde si trova subito con una
specifica nervosa; chi ha bisogno di sentirla piantata dice che gli scappa via. Lo stesso
pacchetto, due giudizi opposti - e il carattere sposta anche la finestra d'assetto, quindi
dopo un aggiornamento i riferimenti vanno ritrovati davvero.

Se ha portato qualcosa il reparto passa ad altro e il banco torna libero. Se non ha
portato niente resta in verifica, e li' si decide: rimontare la specifica vecchia, o
tenerla e metterci il reparto sopra.

**Power unit.** Le power unit sono omologate: non migliorano gara per gara, si cambia
specifica. Quello che si fa al banco si accumula, e quando la si porta in pista arriva
tutta insieme - o non arriva. Il regolamento concede due omologazioni a stagione
(`sporting.pu_specs_per_season`), piu' quella invernale, che e' gratis e trasforma il
lavoro rimasto in cantina nella power unit dell'anno nuovo.

Anche qui l'esito non e' scontato: la fiducia del banco dipende dal responsabile
powertrain (46%), dalla fabbrica (26%) e da quanto a lungo la specifica e' stata validata
(28%). Una specifica sbagliata non toglie potenza - si torna a girare con la mappatura
vecchia - ma brucia il gettone e peggiora l'affidabilita', che e' esattamente come va
nella realta'.

Il tetto raggiungibile lo decidono chi dirige il reparto e quanto vale la fabbrica:
assumere un buon responsabile powertrain lo alza. Chi compra il motore da altri puo'
fondare un reparto proprio, investirci per almeno
due stagioni e poi decidere quando portarlo in pista: si parte dietro all'ultimo dei
motoristi, e quanto si recupera dipende dai soldi messi e dagli ingegneri ingaggiati.

Avere il motore in casa costa: il reparto va tenuto in piedi tutto l'anno anche senza
svilupparlo, e chi non ha clienti a cui venderlo se lo paga da solo. In cambio si sviluppa
quello che si vuole e si integra la power unit nella vettura invece di riceverla come una
scatola con le sue quote: fra cliente e costruttore pieno ballano circa due decimi al giro.
Lo sviluppo motori sta fuori dal tetto di spesa della squadra.

**Cambi di regolamento.** Non tutti i reset premiano le stesse cose, e i dati lo dicono ciclo
per ciclo in `data/regulations.json`. Nel 2014 contava la power unit e Mercedes, partita col
progetto anni prima, ne visse di rendita fino al 2021. Nel 2022 i motori erano congelati e
l'unica leva era l'aerodinamica. Il 2026 e' di nuovo un reset motoristico.

Da qui il dilemma vero: nella pagina Sviluppo decidi che quota del budget dirottare sul
regolamento che verra'. Ogni milione speso li' e' un milione che non finisce sulla macchina
con cui corri adesso. La Brawn 2009 nacque da una stagione buttata via; la McLaren 2013 dal
non averlo fatto. Al reset conta quanto hai preparato rispetto agli altri e se i tuoi
reparti sono forti proprio nell'area che il nuovo regolamento premia.

Le squadre gestite dal computer fanno lo stesso calcolo: a un anno dal cambio chi non ha
piu' niente da giocarsi dirotta fino all'85%, chi si gioca il titolo si ferma al 33%.

**Regolamento: due discussioni diverse.** Tre volte per stagione si riunisce la
Commissione, e sempre **nei primi mesi dell'anno** (marzo, aprile, maggio): piu' avanti non
ci sarebbe piu' il tempo di progettarci sopra. Li' si trattano i **ritocchi** al regolamento
in vigore - la FIA porta al tavolo alcune proposte dal catalogo di `data/regulations.json` e
le squadre votano. Non e' un sorteggio cieco - se una scuderia sta scappando si discute di
riequilibrio, se i conti sono tesi si parla di costi - e ogni squadra vota secondo il
proprio interesse sportivo ed economico, con FIA e FOM che guardano a costi e spettacolo.

**Da quando vale quello che passa.** Non da subito. Una norma approvata a maggio entra in
vigore **dalla stagione successiva**, e nella pagina Regolamento si legge dall'anno prima
sotto "gia' approvate, in vigore piu' avanti": e' con quella che si progetta la macchina.
A campionato in corso non si cambiano le carte, perche' una squadra la monoposto la
disegna d'inverno e spostare i paletti a meta' anno manderebbe all'aria dodici mesi di
lavoro.

Le eccezioni sono due, e sono quelle vere:

- **La sicurezza non aspetta il primo gennaio.** Raffreddamento obbligatorio del pilota
  oltre i 31 gradi, strutture anti-intrusione rinforzate, limite in corsia box a 60 km/h,
  metrica contro il saltellamento: se passano, valgono dal gran premio dopo.
- **La direttiva tecnica dopo una violazione accertata.** Non sta nemmeno sul tavolo
  finche' nessuno ha sforato: compare fra le proposte solo dopo che una squadra e' stata
  sanzionata, e allora si stringono i test - per esempio quelli di flessibilita' delle ali
  - con effetto immediato.

Nella pagina si riconoscono dalla targhetta: SICUREZZA in arancione, DIRETTIVA in rosso,
tutte e due con scritto "in vigore da subito".

Il **cambiamento profondo** non passa di li'. Ogni quattro o cinque anni la FIA apre un
**tavolo tecnico**, e quello ha bisogno di quattro o cinque riunioni prima di arrivare a un
accordo - cinque se le posizioni sono lontane fra loro. Al tavolo non si vota: si tratta.
Ogni squadra chiede quello che le conviene (si spinge su cio' in cui si e' forti, ed e'
sempre andata cosi'), e chi sta andando male chiede una rivoluzione mentre chi vince chiede
continuita'. La FIA vuole cambiamenti contenuti, la FOM vuole che la griglia si rimescoli, e
una squadra storica ha piu' voce di una piccola.

Il compromesso che ne esce non e' la media aritmetica delle richieste - un regolamento non
e' mai un terzo per uno: vince la coalizione piu' larga e agli altri si concede qualcosa.
Tu porti la tua linea a ogni riunione, scegliendo su cosa spingere e quanto vuoi che cambi,
e sposta il risultato di otto-dieci punti: abbastanza per contare, non abbastanza per
dettare il regolamento da soli.

Firmato l'accordo servono ancora **due stagioni** prima che le macchine nuove scendano in
pista, ed e' in quelle due stagioni che si decide tutto: la pagina Sviluppo mostra su cosa
punteranno le nuove norme e quanto bene la squadra converte, e il cursore "Risorse sul
regolamento nuovo" dirotta budget dalla macchina di adesso a quella di domani. Finche' il
tavolo e' aperto la direzione puo' ancora cambiare, quindi prepararsi troppo presto e' una
scommessa.

Un esempio reale di come si svolge: tavolo aperto nel 2028, tre riunioni quell'anno (gare 3,
5 e 8), le ultime due nel 2029, accordo alla quinta - power unit al 50% - e regolamento
nuovo nel 2031.

Il catalogo copre gli aspetti realmente discussi nella storia della categoria: fondo piatto,
sospensioni attive, controllo di trazione, gomme scanalate, guerra fra fornitori,
rifornimento, ali mobili, ritorno ai V10, quota elettrica, termocoperte, griglia invertita,
vetture cliente, tetto di spesa.

**I cicli tecnici non sono un calendario.** Ogni norma tecnica approvata porta con se' un
peso e un'area (power unit, aerodinamica, telaio). Quando la somma dei pesi supera la
soglia, i cambiamenti sono cosi' tanti da fare un'era nuova: viene fissata due stagioni piu'
avanti, e la sua natura e' la somma delle aree toccate. Se sono passate soprattutto norme
sul telaio, sara' il telaio a decidere; se e' passato il ritorno ai V10, sara' il motore.
Nessuno sa in anticipo che forma avra' il prossimo regolamento: dipende da come si e'
votato.

## Dati modificabili

Tutto il contenuto sta in `data/` ed è JSON leggibile:

- `tracks.json` — 24 circuiti: lunghezza, giri, curve, caratteristiche, layout, tempo di riferimento
- `teams.json` — 11 scuderie, motoristi, strutture, componenti di partenza e posizione nel costruttori 2025 (da cui escono ore di galleria, premi e valore per gli sponsor)
- `drivers.json` — 22 titolari + svincolati, con attributi e contratti
- `staff.json` — figure chiave nominate, staff libero, template dei ruoli
- `regulations.json` — regolamento 2026, cicli storici, catalogo delle proposte votabili

I valori di piloti e scuderie sono ancorati alla forza espressa nella stagione 2025, che e'
l'ultima cosa verificabile prima di un reset regolamentare: nel 2026 nessuno sa davvero
l'ordine. Da li' si aggiungono i fattori strutturali - eta', chi ha cambiato squadra, chi e'
stato fermo un anno.

La taratura e' verificata simulando: due stagioni complete danno McLaren campione
costruttori, Red Bull-Ferrari-Mercedes a contendersi il secondo posto, Williams prima delle
altre e Cadillac al debutto in fondo. Fra i piloti Verstappen vince quasi la meta' delle
gare pur non avendo la macchina migliore, Norris e Piastri si dividono il resto.

Se qualcosa non ti torna, correggilo nel JSON e il gioco lo usa al riavvio. Per cambiare
molti piloti insieme c'e' uno strumento:

```bash
python tools/import_ratings.py mie_valutazioni.json --dry-run
```

Accetta due formati: le quattro categorie usate dai giochi ufficiali (pace, racecraft,
awareness, experience), tradotte con formule scritte in chiaro dentro lo strumento, oppure
gli otto attributi del gioco uno per uno. Scrive solo i piloti e i campi presenti nel file.

Le valutazioni di un gioco commerciale sono un giudizio di terzi, non un dato pubblico:
usarle come riferimento per una partita e' una cosa, ridistribuirle un'altra. Lo strumento
legge un file che tieni tu e non porta con se' nessun dato altrui.

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
