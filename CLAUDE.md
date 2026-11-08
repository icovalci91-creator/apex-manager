# Apex Manager

Gioco manageriale di Formula 1, Formula E ed endurance in Python (pygame-ce,
Panda3D, numpy), tutto in italiano. Chi lo sviluppa lo gioca con l'eseguibile
Windows costruito dalle Actions: un errore che si vede solo su Windows e' un
errore vero. README.md descrive ogni funzione del gioco.

## Come si lavora
- Ramo di lavoro `claude/game-analysis-l4v034`: commit e push li', niente PR se
  non chieste. `main` e' molto indietro.
- Commit in italiano, nella forma `Area: cosa cambia` (vedi `git log`).
- Dopo un push che tocca il gioco si controlla la corsa "Build Windows e allega
  alla release" (`.github/workflows/windows.yml`) e si da' il link
  all'artefatto `ApexManager-installatore`. Una release che resta si fa solo
  con un tag `v*`.
- In un contenitore cloud nuovo le librerie mancano:
  `python3 -m pip install -r requirements.txt` (il `pip` nudo puo' puntare a
  un altro Python).

## Comandi
- `python main.py`: avvio. `python main.py --prova-3d`: controllo di Panda3D
  (lo usa la CI). `APEX_NO_PANDA=1`: vista 3D con moderngl.
- `/collaudo`: stagioni intere senza interfaccia, confrontate con le soglie di
  `.claude/skills/collaudo/soglie.json`. Dopo ogni modifica a game/sim,
  game/core, game/model.
- `/prova-ui`: tutte le pagine senza schermo, con la guardia dei 32 bit. Dopo
  ogni modifica a game/ui.
- `python tools/sonda_salvataggi.py` (o il subagent `custode-salvataggi`):
  le partite salvate prima si aprono ancora, e il salvataggio non perde niente.
- `python tools/sovrapposizioni.py`: scritte che si pestano, pagina per pagina.
- Hook in `.claude/settings.json`: dopo ogni modifica a un .py controlla il
  file; prima di ogni `git commit` prova i salvataggi. Se nega il commit si
  legge il motivo e si corregge, non si aggira.
- `/revise-claude-md`: a fine sessione, per aggiornare questo file.

## Trappole
- Salvataggi: la carriera passa da un eseguibile all'altro. In `from_dict` un
  campo nuovo si legge con `.get(chiave, predefinito)`, mai con `td["..."]`.
  Un attributo che non finisce in `to_dict` torna in silenzio al valore di
  `data/` quando si ricarica. Anche il generatore (`gs.rng`) si salva: una
  partita ricaricata riparte dallo stesso punto.
- Taratura dei circuiti: `game/core/taratura.py` la tiene in cache con una
  chiave fatta dai sorgenti in `_MODULI`. Un modulo nuovo del modello del giro
  va aggiunto li', se no si rileggono tarature vecchie.
- Windows: pygame rifiuta un rettangolo con un numero oltre i 32 bit
  ("Argument must be rect style object"), Linux lo tronca senza dire niente.
  Scale HD e cursori con minimo uguale al massimo sono i casi visti.
- Eseguibile: `apex.spec` esclude `direct` e i pezzi di Panda3D che non
  servono, e tiene Cg (serve a libpandagl). Un import nuovo di Panda3D
  funziona dai sorgenti ma puo' mancare nell'exe.
- Generati dalla CI, da non toccare a mano: `dintorni/*.json.gz`
  (dintorni.yml, OpenStreetMap, ODbL) e `grafica/` (grafica.yml).
- Vista 3D: Panda3D disegna fuori schermo (`vista_panda.py`,
  `motore_panda.py`) e pygame incolla il fotogramma; `vista3d.py` con moderngl
  fa da riserva. Stessi shader GLSL, y in alto.
- Equilibrio: le misure delle stagioni pulite (ritiri, safety car,
  giro/riferimento, eta' dei titolari, esordienti, dominio) e le soglie stanno
  in `.claude/skills/collaudo/soglie.json`. Se un collaudo non passa si
  corregge il gioco, non la soglia.

## Convenzioni
- Nomi, commenti, messaggi e testi in italiano.
- Niente lettere accentate nelle stringhe del codice: `piu'`, `e'`, oppure
  escape come `·`. Il README puo' usare gli accenti.
- I commenti spiegano il perche', in prosa (il tono e' quello di
  `game/core/taratura.py`).
- Quando cambia qualcosa che il giocatore vede si aggiorna il README.
