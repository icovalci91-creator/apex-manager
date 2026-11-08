---
name: collaudo
description: Collaudo senza interfaccia di Apex Manager - fa girare stagioni intere (weekend F1 con libere/sprint/qualifica, E-Prix, tappe WEC, Commissione, fine stagione con inverno, salva e ricarica) e confronta ritiri, safety car, giro/riferimento, eta' dei titolari e la sua deriva, dominio, tempi di fine stagione e di salvataggio con soglie note. Usalo dopo ogni modifica a game/sim, game/core o game/model e prima di dire che un cambio di bilanciamento, mercato o salvataggio funziona.
when_to_use: Richieste come collaudo, prova qualche stagione, regge su piu' anni?, controlla il bilanciamento, i piloti invecchiano?, la fine stagione e' lenta; oppure da solo dopo aver toccato simulazione, mercato, sviluppo, Formula E, WEC o GameState.to_dict/from_dict.
argument-hint: "[squadra] [--stagioni N] [--fe] [--wec] [--gare N] [--rif COMMIT]"
allowed-tools:
  - 'Bash(python "${CLAUDE_SKILL_DIR}/collaudo.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/collaudo.py" *)'
  - 'Bash(python ${CLAUDE_SKILL_DIR}/collaudo.py *)'
  - 'Bash(python3 ${CLAUDE_SKILL_DIR}/collaudo.py *)'
  - Read
---

# Collaudo

Una carriera giocata senza schermo, con gli stessi passi dell'interfaccia: il
prossimo evento del calendario intrecciato, il weekend di Formula 1 (gomme,
libere, Sprint Qualifying, sprint, qualifica, gara), gli E-Prix e le tappe
endurance se il programma e' aperto, la Commissione di meta' stagione, la fine
stagione con l'inverno e il voto. A ogni fine stagione la carriera si salva, si
ricarica e si salva di nuovo: i due file devono essere identici. Le misure si
confrontano con `soglie.json`, accanto a questo file.

Argomenti ricevuti: $ARGUMENTS

Il comando e' sempre questo, scritto cosi' (e' la forma che la skill
autorizza): niente `cd`, niente `| tail`, niente `> file`, niente `&&` - per
tenere il rapporto c'e' `--json FILE`, con FILE nello scratchpad.

```
python "${CLAUDE_SKILL_DIR}/collaudo.py" [squadra] [opzioni]
```

Non servono pygame ne' le altre librerie di `requirements.txt`: il collaudo
importa solo la libreria standard e i moduli di `game/core`, `game/sim` e
`game/model`, e gira anche in un Python appena installato. Se `python` non
c'e', `python3` con gli stessi argomenti. Funziona da qualunque cartella: il
gioco lo trova tre livelli sopra allo script. Su Windows il comando e' lo
stesso, ma va lanciato con lo strumento Bash (Git Bash): l'autorizzazione
della skill e' scritta per quello, e da PowerShell chiederebbe il permesso.

## Quale lanciare

| Situazione | Comando | Quanto dura |
|---|---|---|
| Prima prova dopo qualunque modifica, o per vedere che non si e' rotto niente | `--gare 3` | 10-30 s, in primo piano |
| Modifica alla simulazione di gara (ritiri, safety car, passo, meteo, gomme) | `--stagioni 1` | circa 100 s: in background |
| Mercato, crescita dei piloti, sviluppo, economia, salvataggi | `--stagioni 3` | circa 5 minuti: in background |
| Formula E, endurance, calendario intrecciato | aggiungi `--fe --wec` | come sopra |
| Un numero e' cambiato e vuoi sapere se e' colpa tua | `--rif HEAD` con gli stessi argomenti | come lo scenario, i due girano insieme |

- Senza argomenti: ferrari, seme 1, una stagione. `[squadra]` e' un id di
  `data/teams.json` (mclaren, ferrari, redbull, mercedes, astonmartin, alpine,
  williams, racingbulls, haas, audi, cadillac).
- `--seme N` cambia la carriera. Stesso seme e stesso codice, stessi numeri:
  l'`impronta` dell'ultima riga lo riassume (i tempi non ci entrano), e
  `--rif HEAD` su un albero senza modifiche da' due impronte uguali. Fra
  Windows e Linux, o fra due versioni di Python, i conti in virgola possono
  scostarsi di poco: le soglie hanno margine anche per questo, e per
  confrontare due versioni si usa `--rif`, sulla stessa macchina.
- Tutto quello che dura piu' di un minuto va lanciato col comando in background
  dello strumento Bash, e si legge l'uscita quando ha finito. Intanto si puo'
  fare altro, ma non dire che il collaudo e' passato prima di averlo letto.
- `--dettaglio` stampa una riga per gran premio (la prova lampo lo fa sempre).

## Come si legge

Per ogni stagione tre righe: campioni e vittorie per squadra; le misure; i
tempi e l'esito del salva-e-ricarica. Poi il riepilogo della carriera e
l'ultima riga:

- `ESITO: collaudo superato` e uscita 0: nessun errore, salvataggi identici,
  tutte le misure dentro le soglie.
- `ESITO: collaudo NON superato` e uscita 1: sopra ci sono le righe con il
  motivo - un errore con l'ultima riga della traccia, un salvataggio diverso con
  i primi punti in cui non torna (es. `/teams/alpine/reputation: 65.3 -> 68`),
  o una misura fuori soglia con il perche'.
- Uscita 2: argomenti sbagliati (anche una squadra che non c'e'), gioco non
  trovato, commit di `--rif` che non esiste.

## Le soglie

Stanno in `soglie.json`; ognuna ha il suo `perche`, che si stampa quando
scatta, e `_taratura` dice su cosa sono state misurate: 20 stagioni pulite
(quattro squadre e semi per tre stagioni, una con Formula E ed endurance, piu'
una carriera di otto stagioni), con margine.

| Misura | Cosa e' | Pulite | Soglia |
|---|---|---|---|
| `dnf_per_gara` | ritiri per gran premio, guasti e incidenti | 1.5-2.7 | 1.0-3.0 |
| `sc_per_gara` | safety car e VSC per gran premio | 0.6-1.2 | 0.3-1.7 |
| `giro_su_rif` | giro piu' veloce / riferimento del circuito, solo gare asciutte | 0.978-0.996 | 0.96-1.02 |
| `eta_titolari` | eta' media dei titolari durante la stagione | 25.6-29.3 | 24.5-29.8 |
| `deriva_eta_titolari` | la stessa, meno quella della prima stagione del collaudo | -2.6..+1.0 | -3.5..+1.5 |
| `esordienti` | titolari dell'anno dopo senza un gran premio alle spalle | 0-5 | 0-8 |
| `dominio` | quota di vittorie della squadra che ne vince di piu' | 0.29-0.67 | fino a 0.875 |
| `tempo_gare_s` | tutti gli eventi della stagione | 60-95 s | fino a 400 s |
| `tempo_fine_stagione_s` | fine stagione + inverno + Commissione | 0.03-1.4 s | fino a 8 s |
| `tempo_salvataggio_s` / `tempo_caricamento_s` | to_dict + json / from_dict | 0.07 s / 0.6 s | 1 s / 5 s |
| `dimensione_salvataggio_kb` | il salvataggio scritto | 1.0-3.6 MB | fino a 5 MB |
| `esordienti_per_anno` (carriera, da 3 stagioni) | media degli esordienti | 1.9-3.0 | 1-6 |
| `dominio_medio` (carriera, da 3 stagioni) | media del dominio | 0.43-0.60 | fino a 0.75 |

Prove fatte guastando il gioco in una copia (mai nel repository):

- il mercato di prima di b64f73d, quello con cui la griglia invecchiava: esce
  con 1 alla terza stagione (eta' 30.5, deriva +2.2, 0.3 esordienti l'anno).
  Alla seconda stagione non si distingue ancora da una pulita (+1.0 tutte e
  due): per l'eta' servono tre stagioni;
- il rischio di rottura moltiplicato per 2.5: esce con 1 alla prima stagione
  (3.25 ritiri a gara);
- `from_dict` che non rilegge la reputazione: esce con 1 al primo salvataggio,
  e la riga dice `/teams/alpine/reputation: 65.3 -> 68`;
- una squadra piu' veloce di 1.2 s al giro: 23 vittorie su 24, dominio 0.958,
  esce con 1 alla prima stagione;
- il passo di gara piu' lento del 3.5%: giro sul riferimento 1.030, esce con 1
  alla prima stagione;
- nove secondi in piu' nella fine stagione: esce con 1 (10.3 s);
- una tappa endurance che non avanza piu': il calendario si ferma, esce con 1
  in un secondo invece di girare per sempre;
- un E-Prix che si rompe, o un errore di sintassi in `game/core`: esce con 1,
  con il file e la riga.

Restano dentro, e servono il confronto con `--rif`: il rischio di rottura per
1.6 (un quarto di ritiro in piu' a gara, meno della differenza fra due semi) e
nessuna promessa dalla Formula 2 con i ragazzi che non crescono, mercato
intatto (in tre stagioni si vede solo negli esordienti, 1.3 l'anno contro 2-3:
il vivaio che c'e' basta ancora a riempire i sedili).

Non lo vede per niente, e non e' questione di soglie: un attributo che
`to_dict` non scrive. Manca da tutti e due i file del salva-e-ricarica, che
quindi tornano identici, mentre la partita ricaricata lo riprende in silenzio
dai dati (provato: `to_dict` senza la reputazione esce con 0). Per quello c'e'
il confronto attributo per attributo di `tools/sonda_salvataggi.py`.

Una stagione con meno di `gare_minime` gran premi (la prova lampo, o una
carriera ripresa a campionato quasi finito) si giudica con le soglie larghe
della sezione `lampo`: tre gare non bastano per una media, e li' si cercano
solo gli sbagli grossi - niente minimo per ritiri e safety car, quindi una
gara in cui non si ritira piu' nessuno la vede solo la stagione intera. Il
giro sul riferimento cala di circa 0.002 a stagione (le vetture crescono): in
una carriera molto lunga il minimo va riguardato.

## Se non passa

1. Leggi il motivo nelle righe sopra l'esito. Un errore: sotto c'e' il file e
   la riga in cui si e' rotto, la traccia intera e' nel rapporto (`--json`) e
   nell'uscita; anche un gioco che non si importa (un errore di sintassi) esce
   cosi'. Un salvataggio diverso: il percorso dice quale campo scritto da
   `GameState.to_dict` non torna dopo `from_dict` (in `from_dict` un campo si
   legge con `.get(chiave, predefinito)`).
2. Rilancia lo stesso scenario con `--rif HEAD`: il codice dell'ultimo commit
   (estratto con `git archive` in una cartella temporanea, senza stash e senza
   checkout) e quello di adesso girano insieme con lo stesso seme, e la tabella
   finale mette prima, dopo e differenza uno accanto all'altro. Se anche il
   "prima" non passa, il problema c'era gia': dillo, invece di attribuirlo alla
   modifica. Se le impronte sono uguali la modifica non ha cambiato i numeri.
3. Correggi il gioco, non le soglie. Le soglie si allargano solo quando il
   cambio di equilibrio e' voluto e l'utente e' d'accordo, e si ritarano con
   almeno tre combinazioni squadra/seme per tre stagioni.

## Salvataggi di prima con il codice nuovo

- `--salva-in FILE` scrive la carriera alla fine del collaudo, nel formato dei
  salvataggi del gioco (con `--gare` e' una carriera a meta' stagione).
- `--parti-da FILE` riprende quella carriera invece di cominciarne una nuova e
  la porta avanti con il codice di adesso.
- Con `--rif COMMIT`, `--salva-in FILE` fa scrivere la carriera al codice di
  quel commit: e' il modo piu' corto per avere un salvataggio vecchio. Va bene
  anche un commit lontano (o il tag dell'ultima versione Windows): su codice di
  prima del calendario unico (dd05dcc) si corre solo la Formula 1, e il
  rapporto lo dice in una nota. Prima della Formula E (21618e0) e
  dell'endurance (85deca2) `--fe` e `--wec` non si possono chiedere: il
  "prima" si ferma e lo dice.

Il giro completo, per una modifica a `to_dict`/`from_dict`:

```
python "${CLAUDE_SKILL_DIR}/collaudo.py" ferrari --gare 3 --rif HEAD --salva-in <scratchpad>/vecchia.json
python "${CLAUDE_SKILL_DIR}/collaudo.py" --parti-da <scratchpad>/vecchia.json --stagioni 1
```

Lo stesso vale per un salvataggio vero del giocatore: quelli dell'eseguibile
Windows stanno in `%APPDATA%\ApexManager\saves\`, quelli del gioco lanciato dai
sorgenti in `saves/` nel repository. I file temporanei vanno nello scratchpad,
non nel repository.
