---
name: prova-ui
description: Prova senza schermo dell'interfaccia pygame di Apex Manager - apre ogni pagina di NAV con il driver video finto di SDL, in piu' stati (aperta, prima voce scelta, in fondo) a 1180x680 e 1600x900 e alle scale HD 1.0/1.5/2.0, con una guardia che rende fatali su Linux i numeri oltre i 32 bit che su Windows fermano il gioco ("Argument must be rect style object"). Salva le foto delle pagine da guardare. Usalo dopo ogni modifica a game/ui (pagine, widget, theme, hd, scene) e prima del push.
when_to_use: Richieste come prova l'interfaccia, le pagine si aprono?, fammi vedere la pagina, crasha su Windows; oppure da solo dopo aver toccato file in game/ui.
argument-hint: "[--only pagina ...] [--scale 1.0 1.5 2.0] [--foto]"
allowed-tools:
  - 'Bash(python "${CLAUDE_SKILL_DIR}/prova_ui.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/prova_ui.py" *)'
  - 'Bash(python ${CLAUDE_SKILL_DIR}/prova_ui.py *)'
  - 'Bash(python3 ${CLAUDE_SKILL_DIR}/prova_ui.py *)'
  - Read
---

# Prova dell'interfaccia, senza schermo

Il crash peggiore finora (commit `dada758`) succedeva solo su Windows: un pilota
di Formula E caro riempiva il tetto di spesa, il cursore degli ingegneri
divideva per quasi zero e chiedeva una barra larga miliardi di pixel. Su Windows
pygame la rifiuta e il gioco si ferma con `TypeError: Argument must be rect
style object`; su Linux `pygame.Rect` tronca in silenzio e non si vede niente.
Questa prova fa fallire anche su Linux quello che su Windows ferma il gioco, e
apre tutte le pagine nello stato che lo aveva rotto.

## Quando lanciarla

- Dopo ogni modifica a `game/ui` (pagine, widget, `theme.py`, `hd.py`, scene),
  anche se nessuno l'ha chiesto, e sempre prima del push.
- Quando chi sviluppa chiede "prova l'interfaccia", "le pagine si aprono?",
  "fammi vedere la pagina ...", "crasha su Windows".
- Quando arriva da Windows un errore con `Argument must be rect style object`
  o un `TypeError` che passa da `game/ui/hd.py`.

## Come si lancia

```
python "${CLAUDE_SKILL_DIR}/prova_ui.py" [opzioni]
```

Argomenti ricevuti: `$ARGUMENTS`. Se sono opzioni passale tali e quali; se sono
parole ("la pagina della Formula E") traducile nelle opzioni qui sotto.

- Lancia il comando da solo, cosi' com'e': niente `cd ... &&` davanti e niente
  `; echo $?` dietro. Il permesso della skill copre solo quella forma, e
  l'esito lo stampa gia' lo script nella riga `Esito:` (e il codice d'uscita).
- Dai al comando Bash un timeout di almeno 180000 ms. La prova intera dura una
  ventina di secondi; in un container appena nato il gioco tara prima i
  circuiti e ci mette qualche secondo in piu'.
- Il percorso va fra virgolette doppie, come sopra: su Windows contiene barre
  rovesciate. Su Windows usa `python` e non `python3`, che li' e' spesso il
  finto alias dello Store.
- Non serve uno schermo: lo script imposta da se' `SDL_VIDEODRIVER=dummy`,
  trova la cartella del gioco salendo dalla propria, e non legge ne' scrive
  `video.json` e `audio.json` di chi gioca (se succedesse, esce con 2).

| Opzione | Cosa fa |
|---|---|
| (nessuna) | tutte le pagine di NAV, 3 stati, 1180x680 e 1600x900, scale 1.0 1.5 2.0 |
| `--only pagina ...` | solo quelle pagine (id di NAV) |
| `--scale 1.0 1.5 2.0` | solo quelle scale HD (va bene anche 1.25) |
| `--foto` | salva una PNG per ogni vista |
| `--cartella DIR` | dove mettere le foto, invece di `cache/prova-ui` |

Gli id delle pagine: `hq car dev powerunit testing drivers academy staff
engineers workforce finance facilities formulae wec standings calendar history
rules`. Dalle parole: Formula E = `formulae`, endurance = `wec`, piloti =
`drivers`, vivaio = `academy`, ingegneri = `engineers`, organico = `workforce`,
finanze e sponsor = `finance`, infrastrutture = `facilities`, regolamento =
`rules`, classifiche = `standings`, calendario = `calendar`, storico =
`history`, test privati = `testing`, power unit = `powerunit`, sviluppo = `dev`,
assetto = `car`, quartier generale = `hq`. Con un id sbagliato lo script esce
con 2 e stampa quelli giusti, che sono sempre quelli di NAV in
`game/ui/scenes/shell.py`.

## Cosa fa

1. **Lo stato estremo.** Una carriera nuova (sempre lo stesso seme) con
   Formula E ed endurance aperti, i due piloti di Formula E piu' cari del
   mercato messi in macchina senza chiedere al tetto, tutti gli ingegneri, il
   budget sviluppo oltre il tetto della serie, la Formula 1 oltre il suo tetto
   di spesa e le giornate di test finite. Se il gioco cambia e lo stato non si
   ricrea piu' (il tetto non si sfonda), la prova esce con 2 e lo dice.
2. **Ogni pagina, in piu' stati.** `aperta` (appena scelta dalla barra),
   `prima-voce` (la prima riga di ogni lista scelta, come un clic), `in-fondo`
   (pagina e liste scorse fino in fondo), piu' `scheda2`, `scheda3`... per le
   pagine con le schede interne (Formula E, finanze, regolamento). Ogni vista passa
   da `update` e `draw` della shell vera, come nel ciclo del gioco.
3. **Cursori al limite.** Dopo ogni vista ogni cursore della pagina si
   ridisegna col massimo crollato sotto al valore e poi sotto al minimo: e'
   quello che succede quando un pilota caro riempie il tetto o i soldi
   finiscono. La barra deve restare fra vuota e piena. Questi controlli hanno
   `:cursori` attaccato allo stato.
4. Tutto a 1180x680 e 1600x900 (le misure di `game/config.py`) e a ogni scala.

## La guardia a 32 bit

Su Windows un long di C e' a 32 bit: pygame rifiuta qualunque coordinata fuori
da -2147483648 .. 2147483647 e il gioco si ferma. Su Linux il long e' a 64 bit e
pygame tronca senza dire niente (5e9 diventa 705032704). La prova mette una
guardia nei punti da cui passa tutto il disegno:

- `pygame.Rect`: la costruzione, e poi `r.w = ...`, `r.topleft = ...`,
  `r.move(...)`, `r.inflate(...)`, che su Windows passano dallo stesso long di
  C (`invalid rect assignment`). Vale anche per i Rect nati da questi;
- la tela HD (`Tela.rett`, `Tela.punto`, `Tela.v` in `game/ui/hd.py`), dove un
  numero logico ancora buono, moltiplicato per la scala, smette di starci: a
  1.0 passa, a 2.0 no;
- le funzioni di disegno vere che `hd.installa` mette da parte in `hd._ORIG`,
  anche quando si disegna su una superficie qualunque;
- la posizione di ogni scritta, all'ingresso di `T.text`.

Un numero fuori dai 32 bit (o `nan`, o `inf`) diventa lo stesso `TypeError` di
Windows, e la vista e' ROTTA. Se un `try` del gioco lo inghiotte, la vista e'
ROTTA lo stesso: su Windows quel disegno salterebbe.

## Leggere il risultato

- **Exit 0**, `Esito: tutte le pagine si aprono`: a posto.
- **Exit 1**, righe ROTTA:
  ```
  ROTTA formulae aperta 1180x680 1.0: pygame.Rect con un numero oltre i 32 bit (5.35e+09)
      in game/ui/widgets.py:357 in draw: pygame.draw.rect(surf, T.ACCENT, (tr.x, tr.y, int(tr.w * f), tr.h), border_radius=4)
      da game/ui/scenes/shell.py:176 in draw
      da game/ui/pages/formulae_page.py:225 in draw
  ```
  Il formato e' `ROTTA <pagina> <stato> <misura> <scala>: <causa>`. Sotto la
  prima riga di ogni causa ci sono la riga di codice da cui e' partito il
  numero (`in`) e chi l'ha chiamata (`da`), senza `hd.py` che e' solo il
  tramite; le righe dopo con la stessa causa non lo ripetono. Si stampano al
  massimo 25 righe delle viste vere e 10 dei cursori al limite, contate a
  parte, cosi' i cursori non nascondono le viste; le altre si contano e basta.
  Il `Riassunto` in fondo raccoglie le cause: prima quelle delle viste vere,
  poi quelle dei cursori al limite, con le pagine coinvolte.
- **Exit 2**: la prova non e' partita (il gioco non si importa, lo stato
  estremo non si ricrea, un id sbagliato, le impostazioni toccate). Non e' un
  giudizio sulle pagine: leggi il traceback.

Cosa farne:

- Una vista vera rotta e' un crash che chi gioca vedrebbe: correggi il codice
  alla riga `in` o il chiamante che le passa il numero, poi rilancia con
  `--only` sulle pagine coinvolte e infine la prova intera.
- Rotto solo con `:cursori`: un cursore non tiene la barra fra vuota e piena
  quando il massimo crolla (guarda `Slider._frazione` in `game/ui/widgets.py`).
- Rotto a 1.5 o 2.0 ma non a 1.0: il numero logico sta in 32 bit, quello vero
  no. E' un crash su Windows con lo scaling HD, va corretto lo stesso.
- Non si fa passare la prova cambiando la prova o togliendo la guardia: si
  corregge il gioco.

## Le foto

Con `--foto` ogni vista diventa una PNG, `<pagina>_<stato>_<misura>_<scala>.png`
(per esempio `formulae_aperta_1600x900_2.0.png`), nella cartella stampata alla
fine nella riga `Foto:`. Di norma e' `cache/prova-ui/` dentro il gioco, che git
ignora; con `--cartella` va dove si vuole. A ogni prova con `--foto` si
cancellano le foto vecchie, ma solo quelle col nome fatto cosi': le altre
immagini della cartella restano. Le foto sono alla risoluzione vera (a scala
2.0 una finestra 1600x900 e' 3200x1800), dopo un secondo di animazioni, col
mouse fermo in alto a sinistra.

Guardale con Read. Tienile poche, per esempio
`--only formulae --scale 1.5 --foto` (una decina di foto, e la prova intera con
`--foto` ne fa piu' di trecento). Cerca scritte che escono dai pannelli,
pannelli uno sopra l'altro, roba tagliata a 1180x680, zone vuote dove ci
dovrebbe essere qualcosa. Una vista rotta si fotografa lo stesso, a meta'.

## Cosa non vede

- Solo le pagine di NAV dentro la shell: non il menu, il weekend di gara,
  l'E-Prix, l'inverno, l'editor, la Commissione, le viste 3D.
- Il mouse e' fermo: niente hover, niente trascinamenti.
- I numeri enormi che non passano ne' da `pygame.Rect`, ne' dalla tela HD, ne'
  da `pygame.draw`, ne' da `T.text` (per esempio `Surface.fill` su una
  superficie normale con una tupla) non sono guardati: se pygame li rifiuta
  anche su Linux escono come errore normale, se no passano. Lo stesso per i
  Rect che fa pygame da se', come `get_rect` di una superficie normale:
  spostarli a un numero enorme non si vede. Alle scale HD le scritte e le
  immagini della tela danno invece Rect guardati.
- Non e' Windows: una differenza di pygame fra i due sistemi che non riguarda i
  32 bit qui non si vede.
