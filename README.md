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

   Oppure la squadra non la scegli: la **fondi**. Il pulsante *Fonda una scuderia*
   apre l'iscrizione al campionato come dodicesima squadra, e da li' si comincia da
   niente - senza montepremi, senza sponsor, senza fabbrica. Sotto c'e' come funziona.

   Oppure la squadra non la scegli: la **fondi**. Il pulsante *Fonda una scuderia*
   apre l'iscrizione al campionato come dodicesima squadra, e da li' si comincia da
   niente - senza montepremi, senza sponsor, senza fabbrica. Sotto c'e' come funziona.

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
| Vettura e assetto | La monoposto vista dall'alto: si clicca un pezzo e si vede com'e' messo, cosa c'e' di nuovo in fabbrica e su quale macchina montarlo. Sotto, power unit e cambio da sostituire prima che cedano e un assetto per pilota con il riferimento corretto per il suo stile |
| Sviluppo | La scala delle ore di galleria con la nostra posizione e quanti run e calcoli CFD ci restano, i vincoli che tengono fermo il reparto (banchi occupati, persone libere, tetto di spesa, giornate di test, pezzi di fornitura unica, sviluppo power unit congelato), lavoro di reparto per area, conoscenza della vettura, pacchetti di aggiornamento con costo, tempi e forbice degli esiti, specifiche in verifica da tenere o rimontare |
| Power unit | Confronto fra i motoristi, specifica in lavorazione al banco e quando omologarla con i cinque assi su cui si sviluppa (potenza, recupero, software, affidabilità, efficienza) e quanto banco puntare su ognuno, programma per costruirsi la propria unità, e il programma sull'architettura del ciclo che verrà |
| Ingegneri | Riunione con i tuoi uomini: dove sei rispetto alla griglia, su cosa lavorare, e la linea per la vettura dell'anno prossimo |
| Vivaio | I ragazzi che crescono in casa: due schede, una per il ragazzo e una per decidere **in che categoria corre** — con il costo del posto, cosa insegna e perché una categoria è preclusa — oppure per lasciare la scelta al responsabile del vivaio. Come è finito il loro campionato e a che punto sono con la superlicenza. Quando promuoverlo a terzo pilota o a titolare. Chi il vivaio non ce l'ha può aprirlo, se se lo può permettere |
| Piloti e mercato | La scheda di ogni pilota - attributi col numero accanto alla barra, potenziale residuo, indennizzo per portarlo via, licenza e carriera - e sotto il tavolo della trattativa: ingaggio, durata, bonus vittoria/podio/punto, clausola |
| Staff tecnico | Organigramma, mercato e la scheda di chiunque: attributi con il numero accanto alla barra, valore nel ruolo, confronto con chi quel posto ce l'ha adesso e probabilita' che accetti |
| Organico reparti | Quante persone lavorano in aerodinamica, progettazione, powertrain, simulazione e affidabilita': si assume, si taglia, e si paga |
| Infrastrutture | Dieci strutture da potenziare o costruire, budget capitale a parte dal cap, obsolescenza, confronto con gli avversari |
| Test privati | Otto giornate l'anno (dieci con una pista di proprieta') piu' le prove collettive di inizio stagione: dove girare, con chi, per quale programma |
| Finanze e sponsor | Bilancio per mese e per anno, trattative con gli sponsor |
| Regolamento | Tre schede: **In vigore** (il libro delle regole con i numeri veri: motore, energia, componenti, telaio, aero, gomme, punti, soldi, scala ATR e le norme straordinarie che una Commissione ha votato), **Il ciclo che verrà** (a che punto è il tavolo, la bozza sul motore, la spinta verso l'elettrico, il nostro programma e le architetture a confronto con quanto siamo attrezzati per ognuna), **Commissione** (chi vota, cosa è già passato, cosa si vota adesso) |
| Classifiche / Calendario / Storico | Mondiali, i tracciati con la scheda di ogni gran premio, cicli tecnici e albo d'oro |

### La scheda di un gran premio

Dal calendario si clicca su un circuito e si apre la sua scheda, che tiene insieme tutto
quello che riguarda quel gran premio:

- **Il tracciato** disegnato in grande, con lunghezza, curve, giri (quelli veri di questa
  carriera, se si corre a distanza ridotta) e perdita ai box. Non è un filo grigio su fondo
  nero: c'è il prato dentro l'anello, la via di fuga attorno al nastro, i cordoli rossi e
  bianchi dove si gira davvero, le caselle della griglia prima del traguardo e **la corsia
  dei box** con il muretto e la fila dei garage.
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

### La scala che porta alla Formula 1

Il vivaio non è più un numero che sale: i ragazzi corrono davvero, in un campionato con un
campo partenti, una classifica e un costo. Le categorie stanno in `data/series.json` con i
numeri veri:

| categoria | gare | vetture | un posto costa | ci si entra a | superlicenza al primo |
|---|---|---|---|---|---|
| Formula 4 | 21 | 30 | 0,35 M$ | 15 anni | 12 punti |
| Formula Regional | 21 | 34 | 0,70 M$ | 16 anni | 25 punti |
| Formula 3 | 20 | 30 | 1,10 M$ | 16 anni | 30 punti |
| Formula 2 | 28 | 22 | 2,60 M$ | 17 anni | 40 punti |

Si sale **un gradino alla volta** — nessuno passa dalla Formula 4 alla Formula 2, nemmeno se
è bravo — e per guidare in Formula 1 servono **40 punti superlicenza in tre stagioni**, che
in pratica vuol dire finire sul podio in Formula 2 o vincere una Formula 3.

Quanto cresce un ragazzo dipende da **come è andata**: una stagione davanti vale il doppio di
una in mezzo al gruppo, e una storta abbassa anche il potenziale, perché il potenziale vero
si scopre correndo. Vincere alza la notorietà, e quindi quello che chiede sul mercato.

Il conto lo si sente: tre ragazzi in Formula 2 costano 7,8 M$ di soli posti in pista, sette
volte quanto ne costerebbero in Formula 4. È il motivo per cui un vivaio serio si tiene
largo in basso e stretto in alto.

**La categoria la scegli tu**, ragazzo per ragazzo, nella scheda *Dove corre* della pagina
Vivaio: ogni categoria mostra quanto costa il posto, se è possibile e perché no — età fuori
finestra, un gradino di troppo, un campionato già vinto che non si rifà. Chi non vuole
occuparsene lascia la mano al **responsabile del vivaio**, che sceglie come sceglierebbe uno
bravo quanto lui: un responsabile forte azzecca la categoria quasi sempre, uno mediocre
sbaglia una volta su cinque e ogni tanto brucia un ragazzo in Formula 2 o lo lascia un anno
di troppo in Formula 4.

La scelta pesa perché **una categoria insegna solo se è della misura giusta**. Chi vale più
del livello di promozione di quella serie si porta a casa una frazione della crescita — fino
a un quarto — e chi non arriva nemmeno al valore d'ingresso impara di meno di quanto
imparerebbe un gradino più in basso: dominare una Formula 4 a vent'anni è un anno buttato,
non una scorciatoia. Anche la notorietà segue la vetrina: vincere in Formula 2 vale sul
mercato molto più che vincere in Formula 4.

Da qui in avanti i ragazzi del vivaio **crescono solo correndo**: non ricevono più la
progressione generica di fine stagione, e l'anno in più se lo prendono dopo aver corso, così
che la categoria decisa a ottobre sia ancora quella giusta quando si va in pista.

### Le gomme del weekend

Il weekend comincia prima di scendere in pista. Il fornitore nomina tre mescole della sua
gamma - da C1, la più dura, a C5 - scelte in base a quanta energia il tracciato mette
nelle gomme: **C1-C2-C3 a Losail**, **C2-C3-C4 a Bahrain e Silverstone**, **C3-C4-C5 a
Monaco**. Nel 2026 le mescole sono tornate cinque: la C6 provata nel 2025 non c'è più. E non e' solo un'etichetta: la stessa "morbida" a Monaco e a Silverstone e' una
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

E i set si consumano davvero: due per ogni sessione di libere - il lungo di passo gara e
la simulazione di qualifica - **uno per ogni uscita di qualifica** e uno per ogni stint di
gara. Se arrivi al sabato senza morbide nuove il giro buono lo fai su gomme gia' usate e
paghi un decimo e mezzo; se arrivi alla domenica senza dure, il piano soste te lo detta il
camion e non il muretto. Le squadre del computer scelgono in base a dove sono in
classifica: chi sta davanti difende la gara e carica dure, chi insegue si gioca la
qualifica.

### Il programma di un turno

Un'ora di libere non e' fatta di quattro giri secchi. Si comincia con tre giri di
controllo sulle gomme che si hanno gia' addosso - si guarda che la macchina sia a posto -
poi si monta un treno da gara e si fa un **lungo di quattordici giri** per capire il passo.
Nell'ultima parte si monta la morbida per la **simulazione di qualifica**, e con quelle
stesse gomme si resta fuori a fare un altro pezzo di passo gara. Il sabato mattina il
programma si inverte: prima il lungo, e il giro secco alla fine, che e' la prova generale
della qualifica. Il tabellone dice cosa sta facendo ognuno - *passo gara, giro 9 di 14* -
e il tempo che avanza sono i minuti ai box, spalmati diversamente da ogni squadra.

In qualifica la seconda uscita non e' scontata. Si esce una prima volta con gomme nuove;
quando la macchina rientra, il muretto guarda dove ci si vede arrivare e di quanto si e'
davanti a chi resterebbe fuori, e decide. Se il tempo tiene si resta ai box e **si salva
un treno per la domenica**: succede a un quinto della griglia in Q1 e in Q2, e sono quasi
sempre le macchine di testa. Nell'ultimo turno esce sempre due volte, perche' li' non c'e'
niente da risparmiare.

La previsione puo' sbagliare, e sbaglia piu' spesso dove il muretto vale meno: chi legge
male la pista resta ai box con un tempo che non basta e si ritrova eliminato. Anche
l'orario e' una scelta: chi rischia il taglio esce presto per mettere un tempo in
cassaforte, chi e' tranquillo aspetta - la pista si gomma mentre il turno va avanti, e
l'ultimo giro buono lo si comincia con la bandiera che sta gia' cadendo.

### Durante la gara

- Velocità di simulazione: `II` pausa, `x1`, `x4`, `x12`, `x40`, oppure "Simula fino alla fine".
- `BOX <pilota>`: chiama ai box al passaggio successivo.
- `-` `=` `+`: modalità di guida (conserva / normale / attacca): più passo ma più consumo
  gomme e più rischio di errore.
- **Batteria** (`RIC` `NOR` `ATT`, nel pannello di ogni vettura): quanta energia si spende
  al giro rispetto a quella che si recupera. `RIC` mette via, `ATT` scarica. Sotto 0,9 MJ
  arriva il **clipping** - in fondo ai rettilinei la spinta finisce - e sotto 0,3 MJ la
  batteria è **a terra**: costa il triplo e non se ne esce in un giro, per tornare a
  spingere bisogna risalire oltre 1,25 MJ. Chi insegue entro un secondo può chiedere
  l'**override**: 0,5 MJ per avere tutta la potenza fino quasi a fondo dritto.
- **I due modi di ricaricare** (`L&C` e `SUP`): il *lift and coast* alza il piede prima di
  staccare - riprende energia, risparmia benzina e costa qualche decimo in ingresso curva.
  Il **superclipping** fa il contrario: gas spalancato e una parte di quello che fa il
  termico va in batteria invece che a terra (il regolamento lo tappa a 250 kW). Rimette
  dentro molta più energia e non tocca la curva, ma sul rettilineo sei corto - quindi non
  lo si fa mentre si difende o si attacca, e chi ti segue lo sfrutta.
- **Temperatura delle gomme**: una gomma ha una finestra larga una ventina di gradi, e
  dentro quella tiene. Sotto non si accende — è il giro dopo la sosta — e sopra si sfoglia,
  perde aderenza e si consuma il 55% più in fretta. A portarla dentro o fuori è tutto quello
  che succede in gara: le curve la scaldano e i rettilinei la raffreddano (a Budapest è
  sempre al limite, a Monza non si scalda mai), chi spinge la cuoce, chi sta attaccato a un
  altro pure — nell'aria sporca si scivola e all'anteriore arriva meno aria fresca — e
  dietro alla safety car si gela. Con l'asfalto a 50 °C a Budapest si finisce a 125 °C e si
  fanno 1,7 soste; con l'asfalto a 22 °C a Monza si resta a 84 °C e si perdono tre decimi al
  giro senza mai riuscire ad accenderle.
- **L'attacco preparato**: se resti tre giri entro 1,6 s dallo stesso avversario senza
  passarlo, il muretto smette di spingere e prepara. Due giri di ricarica - a gas
  spalancato, che seguendo costa sul dritto ma non costa in curva, quindi resti comunque
  attaccato - e poi due giri di attacco, arrivando in fondo al rettilineo con un megajoule
  più di lui. Il vantaggio di carica conta davvero nel tentativo: mezza batteria in più
  vale un terzo abbondante di possibilità, e altrettanto in meno a chi ce l'ha di meno.
  È la stessa energia spesa in un ordine diverso, ed è quello che scioglie i trenini.
- **Mappature del motore** (`CONS` `BASE` `SPIN`): l'altra manopola della power unit.
  `SPIN` vale fino a tre decimi al giro sui circuiti di potenza, beve il 6% di benzina in
  più e stressa il motore; `CONS` fa il contrario. Quanto lo si è tirato si legge nella
  barra `MOTORE`: un motore tenuto sempre in spinta arriva a fine gara con quasi il doppio
  delle probabilità di rompersi, uno tenuto lungo con meno del normale.

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

**Dove sta il traguardo.** Una strada di OpenStreetMap comincia dove ha cominciato a
disegnarla chi l'ha disegnata, e va nel verso in cui l'ha disegnata: nessuna delle due cose
ha a che vedere con la gara. Il gioco però conta tutto da quella linea — i giri, i settori,
i distacchi, la posizione delle vetture sul disegno — quindi ogni circuito porta anche
`start` (le coordinate della linea del traguardo) e `senso` (`orario` o `antiorario`), e il
tracciato viene ruotato e girato al momento di costruirlo.

**E il nord sta in alto.** La proiezione da gradi a metri mette il nord in y positiva, come
una carta geografica; lo schermo la y la fa crescere verso il basso. I punti che finiscono
a video vengono quindi ribaltati: senza, ogni circuito uscirebbe specchiato — non ruotato,
proprio a specchio — con le curve dalla parte sbagliata e le vetture che girano al
contrario del verso di gara. Il modello di giro, la curvatura e il verso di marcia restano
nel piano della carta, dove il nord sta in alto: il ribaltamento riguarda solo il disegno.
Il controllo è meccanico — si calcola l'area con segno del tracciato disegnato e si
confronta con il `senso` dichiarato — e oggi torna su tutti e 23 i circuiti con la traccia:

```bash
python tools/verso_tracciati.py    # esce con 1 se qualcuno si vede a specchio
```

```bash
python tools/anchor_tracks.py            # trova la linea e la scrive
python tools/anchor_tracks.py --dry-run  # stampa il referto senza scrivere
```

Per una ventina di circuiti la linea si trova da sola: si confronta il profilo di curvatura
del nostro tracciato con quello delle linee mediane del
[racetrack-database](https://github.com/TUMFTM/racetrack-database) del Politecnico di
Monaco di Baviera, che cominciano dal traguardo, provando tutte le rotazioni e tutti e due
i versi. Di quei dati non resta niente nel gioco: il risultato è un punto sul nostro
tracciato. Gli altri — le cittadine soprattutto — hanno la coordinata scritta a mano nello
strumento, che la aggancia al tracciato e dice di quanto l'ha dovuta spostare.

**E poi si controlla.** Un traguardo spostato non si vede: i tempi restano quelli, il
disegno resta quello, e intanto i settori cadono nel posto sbagliato e le vetture sul
tracciato sono avanti o indietro di qualche centinaio di metri.

```bash
python tools/verifica_traguardi.py    # esce con 1 se qualche linea è da rifare
```

Due prove indipendenti. Per i circuiti che la banca dati ha, si guarda **la prima curva
dopo il traguardo** — a che metro comincia e da che parte gira — e la si confronta con la
stessa curva nella mediana del TUM, che parte dalla linea per costruzione: oggi le 18 linee
trovate così stanno tutte entro 76 m dal riferimento, con una media di 28 m. Per gli altri
vale la regola che non sbaglia mai: **una linea del traguardo sta su un rettilineo**, e si
misura quanto dritto c'è prima e quanto dopo. Non tanto quanto si crederebbe — a Budapest
sono 37 m dall'uscita dell'ultima curva e a Silverstone 49, e sono giuste tutte e due — ma
sotto i 25 m la linea è dentro la curva, e un circuito così non esiste.

Il controllo ha trovato quattro linee sbagliate, tutte fra le coordinate scritte a mano:
Portimão e Kyalami erano **dentro una curva**, Ímola e Losail sul **rettilineo sbagliato**
(a Ímola la Variante Tamburello risultava a destra invece che a sinistra). Rimesse sul
rettilineo principale, a quattrocento metri circa dal suo inizio, che è dove la linea sta
quasi sempre. Restano fuori dal controllo Miami e Tsukuba, che non hanno un traguardo
perché la traccia scaricata non è quel circuito.

**Quanto ci si puo' fidare di un circuito.** Ogni pista porta un fattore di taratura che
allunga o accorcia il giro fino a farlo combaciare con la pole vera: comodo, e pericoloso,
perché fa tornare i tempi e nasconde tutto il resto. `tools/track_report.py` lo spegne e
guarda cosa esce dal modello da solo — errore sul giro, punta di velocità contro quella
vera, curve trovate contro quelle in scheda, com'è stato trovato il traguardo:

```bash
python tools/track_report.py            # il calendario
python tools/track_report.py --tutti    # anche i candidati
```

Sotto il 3% di errore il circuito è in ordine (una vettura di metà schieramento sta lì
dietro alla pole). Sopra il 10% il tracciato o la scheda non descrivono quel circuito, e la
riga viene segnata.

**I settori.** La federazione mette le due linee degli intertempi in modo che i tre settori
durino più o meno uguale: non un terzo di strada per uno — un terzo di Spa fatto di curvoni
si percorre in molto meno tempo di un terzo fatto di tornanti — ma un terzo di cronometro.
È quello che fa il gioco dove del circuito non si sa altro. Dove invece i settori veri sono
molto diversi fra loro il circuito porta il campo `settori`, e quello comanda: a Spa e a
Monaco le due linee stanno dove i tempi dei settori dicono che stanno.

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

Quattro cose che il modello prende sul serio e che si sentono sul cronometro:

- **La linea non passa dal centro della pista.** Una monoposto entra larga, tocca la corda
  ed esce larga: percorre una curva di raggio più grande di quella disegnata. Il guadagno è
  geometrico e non è uguale ovunque — su un tornante da trenta metri vale l'11% di velocità
  in più, su un curvone da trecento poco più dell'1% — e ogni circuito porta la sua
  larghezza (`larghezza_m`: Monaco 9 m, Sepang 16). È il pezzo che pesava di più fra quelli
  che mancavano: senza, il modello sbagliava il giro del 5%.
- **Il tetto di potenza è quello del regolamento.** 400 kW dal termico più 350 dall'elettrico,
  letti da `data/regulations.json`: nessuna power unit lo supera, per quanto sia fatta bene.
  Fra la migliore e la peggiore della griglia ballano **27 kW** (722-750), che a Monza valgono
  0,32 s e a Spa 0,55 — la forbice vera. Il resto della differenza fra due motori sta dove sta
  davvero: recupero (7,8-8,4 MJ a giro), consumi, affidabilità.

- **La trazione la fanno due ruote, e sotto spinta la macchina si siede.** A terra la
  spinta la mette il carico che sente l'assale posteriore — il suo peso più la sua fetta di
  carico aerodinamico — e quel carico cresce con l'accelerazione: baricentro diviso passo fa
  poco più di otto punti di ripartizione per ogni g. Il conto si morde la coda e si scioglie
  girandolo due volte. E la gomma non tiene uguale in tutte le direzioni: di traverso è al
  massimo, mentre trasmette coppia tiene meno. Da fermo si tira 1,3 g: **0-100 in 2,1 s**
  (il vero è 2,6, ma quei cinque decimi sono la frizione e i primi metri, che un modello di
  giro non ha). In frenata lavorano tutte e quattro, e si stacca a 5-6 g.
- **Due assali, non un punto.** Ognuno dei due ha il suo peso da portare in curva e la sua
  aderenza per portarlo, e a decidere quanto forte ci si passa è il più in difficoltà dei
  due — che è la definizione di sottosterzo e di sovrasterzo. Il peso da fermo sta più
  dietro; il carico aerodinamico lo ripartisce il bilanciamento della vettura, e siccome
  cresce col quadrato della velocità si sente nelle curve veloci e sparisce nei tornanti.
  Da qui esce, senza che sia scritto da nessuna parte, che a **Spa** la macchina la si vuole
  neutra (uscirne costa 0,66 s da tutte e due le parti) e a **Monte Carlo** piantata dietro
  (0,24 s guadagnati), perché lì il tempo lo fa la trazione fuori dai tornanti.
- **Otto rapporti, e sono una scelta.** Corti, il motore sta sempre vicino al regime di
  potenza massima e in uscita di curva si spinge, ma si arriva al limitatore prima della
  fine del rettilineo; lunghi, in fondo al dritto ce n'è ancora ma a ogni cambiata il
  termico viene buttato più in basso e riprende peggio — l'elettrico no, quello la coppia
  ce l'ha tutta da subito. Quali siano i rapporti giusti lo trova il modello provandoli,
  come fa con l'ala: a Monza 66 su 100 (limitatore a 348, punta 342), a Barcellona e a
  Budapest i più corti che ci sono. E i 750 kW del regolamento sono all'albero: ingranaggi,
  cuscinetti e lo strappo di ogni cambiata se ne prendono il 6%.
- **Sul dritto le ali si appiattiscono.** Il 2026 non ha più il DRS: ha due assetti nello
  stesso giro, Z-mode in curva e X-mode sul rettilineo, e X-mode toglie un quinto della
  resistenza. Tenere una CdA sola sbagliava sia le curve sia i dritti; con i due assetti le
  punte sui 24 circuiti stanno a **-3 km/h** di media dal vero (erano -10).
- **La punta dichiarata è quella che si tocca.** Non l'asintoto su un rettilineo infinito:
  quella che segnerebbe una rilevazione in fondo al dritto. A Monza sono due numeri diversi
  di 35 km/h, e prima veniva stampato quello sbagliato.

Le g di punta che ne escono: 6,0-6,6 laterali, 5,2-6,5 in frenata, 1,8 in uscita di curva,
e fra i 150 e i 250 km/h il laterale sta entro l'1% da quello vero. Con tutto questo il giro
**senza taratura** sbaglia in media dell'**1,5%** con uno scarto tipo del **2,9%**, e 21
circuiti su 24 stanno entro l'8%. La media è salita da 0,0% a 1,5% quando sono entrati il
rendimento della trasmissione e il trasferimento di carico, che tolgono prestazione vera:
quello che conta è lo scarto tipo, cioè quanto il modello è d'accordo con la realtà circuito
per circuito, e quello non si è mosso. La media se la mangia la taratura per pista.

**Le quattro sensibilità.** La gara, giro dopo giro, somma al passo i chili di benzina
ancora a bordo, la mescola e quanto è consumata, l'aria sporca di chi sta davanti e quanto è
bravo chi guida. Erano quattro costanti uguali per le ventiquattro piste — l'unico pezzo di
simulazione che non guardava dove si stava correndo. Adesso il livello resta tarato sul
mondo vero ma la forma la misura il modello di giro quando la pista si tara, cambiando una
cosa sola e guardando il cronometro: `python tools/sensibilita_piste.py` fa vedere i numeri.
Le forbici sono grosse — la benzina va da 0,65 a Monza a 1,44 a Losail, la scia da 0,42 a
Monza a 1,65 a Losail, il pilota da 0,74 a Spa a 1,55 a Monte Carlo.

La spinta elettrica cala da **290 a 355 km/h**, che è il numero del regolamento 2026 e non
un compromesso: le punte scendono di una quindicina di km/h rispetto alla generazione
precedente, ed è quello che succederà in pista.

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

**Fondare una squadra, e cosa vuol dire davvero.** Si sceglie un nome, una sede, una
livrea e il motorista a cui chiedere la power unit; poi si decide quanto si mette sul
tavolo, ed e' l'unica scelta che conti perche' da li' dipende tutto il resto.

| | sul tavolo | dopo la quota | reputazione |
|---|---|---|---|
| Casa costruttrice | 900 M$ | 450 M$ | 42 |
| Progetto privato | 650 M$ | 200 M$ | 30 |
| Sfida da garage | 600 M$ | 150 M$ | 22 |

La differenza sono i **450 M$ di quota di ingresso**, che non restano in cassa: vanno
alle undici squadre gia' iscritte, quaranta milioni a testa, a compensarle del piatto che
da adesso si divide in dodici. Si chiama anti-diluizione ed e' cosi' che si entra
davvero.

Quello che si trova il giorno dopo:

- **Dal promoter, il primo anno, non arriva niente.** Il montepremi si divide fra chi si
  e' classificato nei campionati scorsi, e uno che e' appena arrivato nei campionati
  scorsi non c'era. Il secondo anno arriva la sola colonna di merito, meno della meta';
  dal terzo si conta come tutti. E' la cosa che piu' di ogni altra rende dura la prima
  stagione, ed e' successa alla Haas.
- **Una macchina un secondo e mezzo dietro l'ultima**, e piu' di tre dietro la prima.
  Cambio e freni si comprano gia' fatti da chi li fa per mezza griglia, tutto il resto
  e' disegnato da zero da gente che quella macchina non l'ha mai vista girare.
- **Galleria del vento in affitto, nessun simulatore, una fabbrica da tirare su.**
  Portare tutte le strutture al livello di una squadra di meta' gruppo costa circa
  **400 M$**: con il limite ordinario in conto capitale non ci si arriva nemmeno avendoli,
  quindi il regolamento concede a chi entra fino a **190 M$ in piu' all'anno**, che si
  spengono nell'arco di sei stagioni. E' quello che rende il capitale iniziale una scelta
  e non un numero.
- **Il proprietario paga il buco, e non e' poco.** Una squadra nuova perde circa **60 M$
  l'anno** solo per esistere: gli incassi sono 15-25, i costi fissi 76-80. Il capitale e'
  l'autonomia, e quello che avanza dopo aver coperto il buco e' il budget di sviluppo -
  66 M$ l'anno per una casa costruttrice, 20 per un progetto privato, 11 per un garage.
- **Uno sponsor, forse due.** Gli accordi grossi chiedono un nome che non si ha. Restano
  l'officina di provincia e il distributore regionale, che pagano poco e ci credono.
- **Due piloti che hanno detto di si'**: un veterano che sa dire se la macchina va, e un
  ragazzo che si prende l'occasione dove gliela danno. Contratti di un anno, pagati sopra
  il loro valore, perche' quello e' il prezzo per convincere qualcuno a salire su una
  macchina che non esiste.
- **Si parte ultimi, e per una volta conviene**: la scala ATR da' a chi sta in fondo tutte
  le ore di galleria. E' l'unico vantaggio che c'e', e va speso.

**E si sale piano.** Con una casa costruttrice dietro, giocando bene, il distacco
dall'ultima delle altre passa da un secondo a nove decimi in sei stagioni: prima si
peggiora - mentre si costruisce la fabbrica gli altri sviluppano - e solo dopo si comincia
a recuperare. Con un progetto privato si galleggia intorno al secondo e mezzo finche' non
arrivano montepremi e sponsor. Con un garage si sopravvive, e basta. Non e' una difficolta'
tarata a tavolino: e' quello che esce dai conti, ed e' anche quello che succede davvero a
chi entra in Formula 1.

**Il nome se lo si fa, e ci vogliono anni.** La reputazione non era mai cambiata in tutta
la carriera: adesso a fine stagione ogni squadra si muove di un quarto verso quello che i
risultati dicono che vale, e chi e' entrato da poco ha comunque un tetto che si alza da
solo, una stagione per volta. Serve a rendere vero quello che si sente giocando una
squadra nuova: all'inizio dicono di no tutti - ingegneri, piloti, sponsor - e non c'e'
niente da fare se non arrivare davanti a qualcuno. Una scuderia che sale di un posto
l'anno passa da 30 a 57 in sette stagioni, e a quel punto le porte cominciano ad aprirsi.

**Fondare una squadra, e cosa vuol dire davvero.** Si sceglie un nome, una sede, una
livrea e il motorista a cui chiedere la power unit; poi si decide quanto si mette sul
tavolo, ed e' l'unica scelta che conti perche' da li' dipende tutto il resto.

| | sul tavolo | dopo la quota | reputazione |
|---|---|---|---|
| Casa costruttrice | 900 M$ | 450 M$ | 42 |
| Progetto privato | 650 M$ | 200 M$ | 30 |
| Sfida da garage | 520 M$ | 70 M$ | 22 |

La differenza sono i **450 M$ di quota di ingresso**, che non restano in cassa: vanno
alle undici squadre gia' iscritte, quaranta milioni a testa, a compensarle del piatto che
da adesso si divide in dodici. Si chiama anti-diluizione ed e' cosi' che si entra
davvero.

Quello che si trova il giorno dopo:

- **Dal promoter, il primo anno, non arriva niente.** Il montepremi si divide fra chi si
  e' classificato nei campionati scorsi, e uno che e' appena arrivato nei campionati
  scorsi non c'era. Il secondo anno arriva la sola colonna di merito, meno della meta';
  dal terzo si conta come tutti. E' la cosa che piu' di ogni altra rende dura la prima
  stagione, ed e' successa alla Haas.
- **Una macchina un secondo e mezzo dietro l'ultima**, e piu' di tre dietro la prima.
  Cambio e freni si comprano gia' fatti da chi li fa per mezza griglia, tutto il resto
  e' disegnato da zero da gente che quella macchina non l'ha mai vista girare.
- **Galleria del vento in affitto, nessun simulatore, una fabbrica da tirare su.** Con
  il limite normale in conto capitale non ci si arriva, quindi il regolamento concede a
  chi entra **190 M$ in piu'** per mettersi in pari: e' quello che rende il capitale
  iniziale una scelta e non un numero.
- **Uno sponsor, forse due.** Gli accordi grossi chiedono un nome che non si ha. Restano
  l'officina di provincia e il distributore regionale, che pagano poco e ci credono.
- **Due piloti che hanno detto di si'**: un veterano che sa dire se la macchina va, e un
  ragazzo che si prende l'occasione dove gliela danno. Contratti di un anno, pagati sopra
  il loro valore, perche' quello e' il prezzo per convincere qualcuno a salire su una
  macchina che non esiste.
- **Si parte ultimi, e per una volta conviene**: la scala ATR da' a chi sta in fondo tutte
  le ore di galleria. E' l'unico vantaggio che c'e', e va speso.

**Il nome se lo si fa, e ci vogliono anni.** La reputazione non era mai cambiata in tutta
la carriera: adesso a fine stagione ogni squadra si muove di un quarto verso quello che i
risultati dicono che vale, e chi e' entrato da poco ha comunque un tetto che si alza da
solo, una stagione per volta. Serve a rendere vero quello che si sente giocando una
squadra nuova: all'inizio dicono di no tutti - ingegneri, piloti, sponsor - e non c'e'
niente da fare se non arrivare davanti a qualcuno. Una scuderia che sale di un posto
l'anno passa da 30 a 57 in sette stagioni, e a quel punto le porte cominciano ad aprirsi.

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

**Delegare, e a chi.** Il reparto puo' lavorare da solo: si accende **"fanno da soli gli
aggiornamenti"** nella pagina Ingegneri - la loro - e da li' in poi ripartizione, pacchetti
e taglie li sceglie lui. E li sceglie **dove ha appena detto di volerli fare**: se in
riunione dicono "gestione gomme ci costa quattordici punti, lavorerei su sospensioni e
telaio", il pacchetto lo aprono li'. In cima alla riunione si legge su cosa stanno
lavorando, e su una stagione intera escono otto pacchetti sui componenti che avevano
indicato. Non
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

**La vettura dell'anno prossimo.** Una monoposto non nasce a gennaio: nasce durante la
stagione precedente, mentre si corre con quella di adesso. Nella pagina Ingegneri si decide
**quanta parte del lavoro va sull'anno prossimo** invece che su questo - una quota ci va
sempre, e cresce da sola man mano che la stagione finisce e migliorare la macchina di adesso
ha sempre meno senso.

E li' si da' la **linea**. Non si disegna la macchina: si dice cosa si vuole, con cinque
direzioni - piu' carico, piu' efficienza sui rettilinei, piu' trazione, piu' gentile con le
gomme, piu' affidabilita' - e si guarda cosa arriva.

Fra quello che si chiede e quello che arriva ci sono due persone. Il **team principal**, che
deve far remare tutti nella stessa direzione, e il **direttore tecnico**, che deve tradurre
una frase in un progetto. Da loro esce la *fedelta' alla linea*: al 97% il reparto fa quello
che si e' chiesto, sotto il 55% fa quello che gli riesce e il lavoro finisce sparso dove
capita - che e' esattamente come nasce una macchina che non e' quella che ci si era
immaginati.

A dicembre il progetto diventa la vettura con cui si corre. Una stagione al 40% con la linea
su carico e gomme porta **+1,9 di media**, e si vede dove: carico +9,7 e gestione gomme
+13,9, mentre le aree lasciate a mezzo punto si muovono appena. Le squadre del computer
fanno lo stesso conto e chiedono quello che gli manca, che e' il motivo per cui una squadra
che soffre in trazione l'anno dopo arriva con un'altra sospensione.

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

**Il rilievo della macchina, e i pezzi da montare.** La vettura non e' piu' una lista di
righe: e' disegnata dall'alto, e ogni componente si clicca. Il colore dice quanto vale
rispetto al riferimento del ciclo, un pallino segnala il pezzo nuovo appena montato o
quello che sta per finire, e a lato si apre la scheda con prestazione, stato e cosa c'e'
in fabbrica.

**Quanti esemplari escono lo dice la fabbrica.** Una squadra grande non ha mai fatto
distinzioni fra i due box: il pezzo nuovo arriva doppio e le macchine restano uguali.
Una squadra piccola, su un pacchetto importante, ne porta uno solo - e li' comincia una
scelta. La soglia la decidono il capannone e la gente che ci lavora dentro:

| Fabbrica | pacchetto piccolo | medio | grande |
|---|---|---|---|
| Ferrari, Mercedes, Red Bull, McLaren, Aston | 2 subito | 2 subito | 2 subito |
| Williams, Audi, Alpine, Racing Bulls | 2 subito | 2 subito | 1, il secondo fra 3 gare |
| Haas, Cadillac | 2 subito | 1, il secondo fra 2 gare | 1, il secondo fra 3-4 gare |

Finche' c'e' un esemplare solo, montarlo su un pilota vuol dire non montarlo sull'altro -
e l'altro lo sa. Da quel momento le due monoposto sono diverse davvero, in tutto:
simulatore, prove, qualifica, gara. Quando il secondo arriva e va in macchina, la
specifica nuova diventa quella di squadra e le vetture tornano uguali. Le scuderie del
computer non tirano a sorte: il pezzo lo mettono a chi sta piu' avanti in classifica.

**E poi c'e' il muro.** Per una squadra grande e' l'unico modo in cui le due macchine
finiscono diverse. Nelle libere si va a sbattere - piu' spesso chi guida sul filo, chi
sbaglia di piu' e quando piove - e ogni tanto quello che si porta via e' il pezzo nuovo.
Succede anche in gara, dopo una botta vera. Se il ricambio non c'e', quella monoposto
rimonta la specifica precedente e ci corre finche' la fabbrica non ne rifa' un altro:
sulla pagina della vettura il componente diventa **"pezzo distrutto, in ricostruzione"**,
e non c'e' niente da decidere se non aspettare. Su una stagione intera capita a mezza
squadra: raro abbastanza da essere una notizia, frequente abbastanza da farsi sentire.

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

**Regolamento: due discussioni diverse.** Una volta per stagione si riunisce la
Commissione, **in primavera**: piu' avanti non ci sarebbe piu' il tempo di progettarci
sopra. Quattro proposte sul tavolo, una riunione sola, e chi c'era c'era. Li' si trattano
i **ritocchi** al regolamento
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
- `regulations.json` — regolamento 2026 con i numeri ufficiali, cicli storici, catalogo delle proposte votabili

### Il regolamento 2026, e cosa ne fa il gioco

`regulations.json` non è un elenco di etichette: dentro `current` ci sono i numeri del
regolamento tecnico, sportivo e finanziario FIA 2026, con la nota che dice da dove vengono.
I principali:

| | |
|---|---|
| Vettura | 768 kg minimo (pilota 82), passo 3400 mm, larghezza 1900, fondo −150 mm, 8 marce |
| Aero | carico −30% e resistenza −55% rispetto al 2022, ala anteriore a 2 elementi, posteriore a 3, niente beam wing |
| Straight mode | zone segnate, ognuna di almeno **3 secondi**, aperte a tutti; niente DRS |
| Overtake mode | entro **1 s** al punto di rilevamento: 350 kW fino a 337 km/h, 0,5 MJ a botta |
| Termico | 1600 cc V6 turbo, 15.000 giri, 400 kW, energia del carburante ≤ **3000 MJ/h** (sotto i 10.500 giri: 0,27·N + 165), ~70 kg di benzina a gara |
| Elettrico | 350 kW, recupero ≤ **8,5 MJ** al giro (il tetto scritto è 9), batteria **4 MJ** utili, niente MGU-H |
| Superclipping | ricarica a gas spalancato, tappata a **250 kW** |
| Componenti | 4 termici, 4 turbo, 3 MGU-K, 3 batterie, 3 centraline, 4 scarichi: poi 10 posizioni, poi 5 |
| Gomme | Pirelli C1-C5, 25 mm più strette davanti e 30 dietro, 13 set (12 nei weekend sprint) |
| Soldi | cost cap 215 M$ fino a 24 gare (+1,8 per gara in più), tetto motoristi 190 M$ |
| Galleria | scala dal 70% del primo al 115% del decimo, riferimento 320 run e 2000 CFD ogni due mesi |

Dove il modello si discosta dal regolamento c'è scritto perché. Il caso principale è la
discesa della spinta elettrica: il regolamento la fa calare fra 290 e 355 km/h, il modello
di giro fra 320 e 380, perché lì la batteria non esiste e quei numeri rappresentano
l'erogazione media di un giro. Quei valori stanno in `power_unit.modello` e sono gli stessi
che una modifica votata in Commissione va a spostare.

### Il motore del ciclo che verrà, e come arrivarci pronti

Un ciclo tecnico non è una percentuale: è una decisione su **come sarà fatto il motore**.
`data/regulations.json` porta un catalogo di sette architetture con i numeri veri (o
plausibili, dove il regolamento non esiste ancora), e quando il tavolo tecnico si apre la
bozza dice a ogni riunione quale sta vincendo.

| architettura | cosa è | giro | punta | peso | benzina | energia |
|---|---|---|---|---|---|---|
| V6 turbo 1.6 ibrido | il regolamento 2026: 15.000 giri, 400 kW + 350 elettrici | — | — | 768 kg | 70 kg | 5,7 MJ |
| V8 turbo 2.4, ibrido minimo | la strada che la FIA guarda per il 2031 | +0,99 s | −17 km/h | 733 kg | 90 kg | 1,6 MJ |
| V6 turbo a ibrido spinto | l'altra direzione: 300 kW termici e 450 elettrici | +0,51 s | +2 km/h | 783 kg | 55 kg | **7,0 MJ** |
| 4 cilindri turbo 1.5 | il motore che somiglia a quello delle auto di serie | +0,66 s | −8 km/h | 748 kg | 60 kg | 5,4 MJ |
| V10 aspirato 3.0 | quello di cui si è parlato nel 2025: 19.000 giri, niente ibrido | −1,03 s | −7 km/h | 678 kg | 110 kg | 0 |
| V8 aspirato 2.4 + KERS | quello che ha corso dal 2009 al 2013 | +0,81 s | −22 km/h | 678 kg | 100 kg | 0,4 MJ |
| V12 aspirato 3.0 | quello che nessuno propone e tutti vorrebbero sentire | **−1,34 s** | −3 km/h | 688 kg | 115 kg | 0 |

I secondi sono misurati con `tools/sensibilita.py` sul calendario vero. E non cambia solo il
cronometro: con un V10 l'energia recuperata a giro è **zero**, quindi batteria, clipping,
override e superclipping spariscono; con un ibrido spinto la gara diventa quasi solo
gestione dell'energia. Le soglie del gioco dell'energia si scalano da sole sulla
batteria e su quanta energia gira in un giro, così un modo che oggi vale mezzo secondo lo
vale anche in un regolamento con una cassa da trenta megajoule.

**Dove ha la testa la federazione.** Ogni ciclo firmato sposta di un po' la direzione
(`trend_elettrico`), e il tavolo si sposta con lei verso le architetture in cui l'elettrico
conta di più: a zero cicli un ibrido spinto non prende voti, dopo tre o quattro diventa la
strada che tutti chiedono.

**La scommessa.** Dalla pagina Power unit si apre un *programma sull'architettura che verrà*
— quella che si pensa arriverà, anche prima che il tavolo decida, anche una che nella bozza
sta ultima. Costa un budget annuale dentro il cost cap, cioè soldi tolti alla macchina di
adesso. Quando il ciclo entra in vigore:

- se l'architettura è quella su cui si è lavorato, il programma diventa vantaggio, e vale di
  più quanto prima si è cominciato (fino a +70% partendo cinque stagioni prima);
- se il tavolo ha deciso diversamente resta il 10%: materiali, combustione, banchi.

**Ma i soldi non bastano: contano gli ingegneri e la fabbrica.** Ogni architettura chiede un
mestiere diverso — termico (reparto motori e fabbrica), elettrico (elettronica, batterie,
simulatore), integrazione (telaio) — e il programma rende in proporzione a quanto si è
attrezzati per *quel* mestiere. Il numero si legge nella pagina Power unit (`noi valiamo
x1,28`): una squadra di testa sta sopra 1,2, una di coda sotto 0,6, e chi il motore lo
compra invece di costruirlo parte con meno della metà, perché può preparare la vettura
attorno alla power unit nuova ma non la power unit. Il mestiere si accumula anche: ogni
milione speso in un programma insegna qualcosa in quella famiglia, e chi ha passato un ciclo
sull'ibrido comincia il successivo avanti sull'elettrico e indietro sul termico.

In una prova su un ciclo intero — scommessa sul V10 dal 2028, accordo nel 2033, motore nuovo
nel 2034 — chi aveva speso 60 M$ sull'architettura giusta è uscito dal reset con **+12,5** di
media sulla vettura, chi ne aveva spesi 47 sull'architettura sbagliata con +2,8, cioè meno di
chi ne aveva spesi 22 azzeccandola.

### Quanto vale cambiare una regola

```
python tools/sensibilita.py
```

Muove una leva alla volta e misura sul calendario vero cosa cambia. Serve a scrivere
proposte nuove con effetti della grandezza giusta invece di tirare a indovinare:

| leva | giro medio | punta | energia |
|---|---|---|---|
| peso −10 kg | −0,20 s | — | — |
| carico +0,05 | −0,69 s | — | — |
| elettrico +5% | +0,01 s | +1,5 km/h | +0,44 MJ, +1,6 s di valore |
| effetto suolo abolito | +1,79 s | — | — |
| gomme scanalate | +2,16 s | — | — |

Due cose che si leggono solo così. Spostare la ripartizione fra termico ed elettrico **non**
cambia il tempo sul giro (la potenza totale resta quella): cambia la punta e cambia tutto il
gioco dell'energia, e va votata sapendolo. E il tetto al recupero di 8,5 MJ oggi non morde
mai: il circuito più generoso del calendario ne rimette dentro 8,2, quindi abbassarlo si
sente e alzarlo no.

Lo stesso strumento stampa anche le voci che una proposta può cambiare e che non legge
nessuno. Oggi non ce n'è nessuna: ogni voce di `rules.DESTINAZIONE` dice chi la legge, e
una modifica votata in Commissione arriva sempre da qualche parte.

### Cosa fa ognuna delle norme votabili

Le dodici che fino a poco fa erano solo etichette:

| norma | cosa succede davvero |
|---|---|
| Rifornimento in gara | si parte con la benzina di un solo stint - a Sakhir 20 kg invece di 70 - e alla sosta se ne rimette dentro dell'altra, 0,12 s al chilo. Macchine più leggere, soste più lunghe |
| Terza vettura | le prime tre del costruttori schierano una macchina in più con un giovane di riserva o del vivaio: 25 al via, e la terza non prende punti né li toglie a chi la segue |
| Vetture cliente | le ultime quattro che non costruiscono la power unit prendono il telaio dal proprio motorista al 94%: Cadillac guadagna 7 punti di media sulla vettura, Haas 3,4 |
| Componenti standard | freni, sospensioni e trasmissione diventano uguali per tutti il giorno stesso, e non si possono più sviluppare - né dal giocatore né dalle IA |
| Ibrido standard | l'ERS di tutti i motoristi va sulla media e esce dallo sviluppo: al banco restano termico e affidabilità |
| Ore di banco contate | lo sviluppo della power unit rallenta come la galleria del vento, e toglie di più a chi sta davanti: il primo lavora al 60%, l'ultimo all'82% |
| Obbligo di fornitura | un motorista regge al massimo tre clienti; con l'obbligo chi cerca un motore lo trova sempre e il prezzo è calmierato, senza paga il 25% in più (McLaren 32,5 M$ contro 26) |
| Massimale ingaggi | il monte stipendi dei titolari non può superare il tetto: chi è già sopra non può firmare nessuno finché non scadono i contratti |
| Riporto del budget | quello che non si è speso resta in cassa per l'anno dopo, fino al massimale, e alza il tetto solo di quella squadra |
| FP1 ai debuttanti | ogni squadra cede un tot di prime libere a un giovane, sfalsate fra squadre: quel venerdì si impara meno sull'assetto e il ragazzo cresce (+2,8 di overall in una stagione, +3,6 se le sessioni raddoppiano) |
| Qualifica aggregata | conta la media dei due piloti: le squadre si schierano in coppia e una seconda guida lenta ti rovina la griglia |
| Griglia invertita | nelle sprint si parte al contrario della classifica, e a inizio stagione al contrario della qualifica |

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

La posizione della linea del traguardo è stata trovata confrontando i tracciati con le
linee mediane del [racetrack-database](https://github.com/TUMFTM/racetrack-database) del
Politecnico di Monaco di Baviera (licenza LGPL): nel gioco non ne è finito alcun dato, solo
il risultato del confronto.

## Limiti noti

- Tre circuiti su 24 sbagliano il giro di più del 10% anche senza taratura: **Melbourne**
  (+10%), **Jeddah** (+15%) e **Madrid** (+13%). Le tracce sono giuste — quella di Melbourne
  combacia entro 4 m con una seconda fonte indipendente — quindi il problema è nel modello,
  non nel disegno. Melbourne è il caso peggiore: il cercatore di zone di straight mode non
  ne trova nessuna, e senza quelle in gara non si sorpassa mai (0 sorpassi contro 25 veri).
- L'altimetria manca del tutto: Spa senza l'Eau Rouge in salita e Interlagos senza la
  discesa sono più facili di quanto siano.
- Il tracciato di Tsukuba, fra i candidati, non è quello vero: è un anello della lunghezza
  giusta ma quattordici chilometri a ovest del circuito. Va riscaricato
  (`tools/fetch_layouts.py --force --only tsukuba`), e finché non lo si fa non ha una linea
  del traguardo. Miami aveva lo stesso problema ed è stato rifatto.
- La corsia dei box è ricostruita, non rilevata: OpenStreetMap la strada dei box non la
  disegna quasi mai. Si sa però dove passa — parallela al rettilineo del traguardo, dalla
  parte interna, con l'ingresso prima della linea e l'uscita dopo — e la lunghezza segue il
  `pit_loss` di quel circuito. È giusta come disegno e come posizione, non come rilievo.
- Melbourne e Jeddah sbagliano il giro del 9% e del 16%: il tracciato scaricato non è quello
  di adesso (Albert Park è stato rifatto nel 2021) o è troppo approssimativo. Vanno
  riscaricati anche loro.
- Madrid non ha riferimenti con cui allineare il traguardo — è un circuito nuovo: la linea
  è messa in fondo al rettilineo più lungo, che è dove sta quasi sempre, ma è una stima.
- Le coordinate di OpenStreetMap sono rade: a Monza il tracciato ha un punto ogni
  quarantacinque metri, e le chicane più strette escono smussate. Il tempo sul giro non ne
  risente (è tarato sul reale) ma qualche curva secca il modello non la conta.
- Il traguardo dei circuiti che il confronto automatico non copre — le cittadine — è messo
  a mano: la coordinata è agganciata al tracciato, quindi cade sull'asfalto, ma può essere
  qualche decina di metri più avanti o più indietro di quella vera.
