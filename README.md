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

Le giornate costano dentro il tetto di spesa, quindi ogni prova e' sviluppo in meno, e la
trasferta pesa: una squadra inglese che va a girare in Europa spende molto meno di una che
si porta tutto dall'altra parte del mondo. Si puo' girare anche fuori dal calendario:
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
| Vettura e assetto | Stato dei dieci componenti, prestazioni derivate, sessioni al simulatore e sei regolazioni d'assetto attorno al riferimento del reparto |
| Sviluppo | Lavoro di reparto per area, conoscenza della vettura, pacchetti di aggiornamento con costo, tempi e forbice degli esiti, specifiche in verifica da tenere o rimontare |
| Power unit | Confronto fra i motoristi, specifica in lavorazione al banco e quando omologarla, programma per costruirsi la propria unita' |
| Ingegneri | Riunione tecnica: dove sei rispetto alla griglia, su cosa lavorare, allocazione consigliata |
| Piloti e mercato | Rinnovi e acquisti a trattativa: ingaggio, durata, bonus vittoria/podio/punto, clausola rescissoria |
| Staff tecnico | Organigramma completo e mercato del personale |
| Infrastrutture | Dieci strutture da potenziare o costruire, stato di obsolescenza, confronto con gli avversari |
| Test privati | Otto giornate l'anno (dieci con una pista di proprieta'): dove girare, con chi, per quale programma |
| Finanze e sponsor | Bilancio per mese e per anno, trattative con gli sponsor |
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
non ce l'ha puo' costruirla, e costa: 140 M$ dentro il tetto di spesa per aprirla al
livello 55, poi la si potenzia come le altre (circa 19 M$ il primo gradino, oltre 36 a
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

**Invecchiamento.** A fine stagione vettura e strutture perdono terreno: non si consumano,
e' il resto del mondo che va avanti. Una monoposto lasciata ferma arretra di circa mezzo
punto l'anno, una struttura di poco piu' di uno, e in cima si perde di piu' che a meta'
gruppo. Per stare fermi bisogna investire, per migliorare bisogna investire parecchio: con
il tetto di spesa nessuno riesce a tenere al passo tutte le strutture, quindi
bisogna scegliere quali. Anche le scuderie del computer reinvestono, e siccome le grandi
sono gia' contro il tetto mentre le piccole hanno margine, il gruppo tende a stringersi.

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

**Regolamento.** Tre volte per stagione si riunisce la Commissione: la FIA porta al tavolo
alcune proposte dal catalogo di `data/regulations.json` e le squadre votano. Non e' un
sorteggio cieco - se una scuderia sta scappando si discute di riequilibrio, se i conti sono
tesi si parla di costi - e ogni squadra vota secondo il proprio interesse sportivo ed
economico, con FIA e FOM che guardano a costi e spettacolo.

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
