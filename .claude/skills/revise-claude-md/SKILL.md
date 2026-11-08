---
name: revise-claude-md
description: Aggiorna CLAUDE.md con quello che questa sessione ha imparato sul progetto (comandi di prova, trappole, numeri di equilibrio), con diff da approvare e commit.
disable-model-invocation: true
allowed-tools: Read, Edit, Write, Glob, Grep, Bash(git status *), Bash(git diff *), Bash(git log *)
---
<!-- Adattato da plugins/claude-md-management/commands/revise-claude-md.md di
     anthropics/claude-plugins-official (Apache-2.0). Sta qui e non come plugin
     perche' le sessioni cloud partono da un clone pulito: le skill in .claude/
     arrivano con il repository, un plugin installato a mano no. -->

Rileggi questa sessione e cerca quello che a una sessione futura - che parte da
un clone pulito, senza lo scratchpad di oggi - sarebbe servito sapere prima.

## 1. Cosa e' mancato

- comandi trovati o usati per provare il gioco (`/collaudo`, `/prova-ui`,
  `python main.py --prova-3d`, `python tools/sonda_salvataggi.py`, gli altri
  strumenti in tools/)
- trappole incontrate: salvataggi (GameState.to_dict/from_dict), la taratura
  (_MODULI in game/core/taratura.py), Windows (rect oltre int32, i pezzi di
  Panda3D in apex.spec, `direct` escluso dall'eseguibile), i dati che genera
  la CI (dintorni/, grafica/)
- convenzioni rispettate o mancate: italiano, niente accenti nelle stringhe
  che il gioco mostra
- numeri di equilibrio verificati (ritiri, safety car, giro contro giro di
  riferimento, eta' media dei piloti) e come si misurano

## 2. Dove va

Solo `./CLAUDE.md` alla radice: e' in git, quindi e' l'unica memoria che arriva
alla prossima sessione cloud. Se non esiste ancora, proponi di crearlo.
Leggilo tutto prima di scrivere: niente doppioni, e se una riga e' diventata
falsa si corregge quella invece di aggiungerne un'altra. CLAUDE.md entra in
ogni conversazione: ogni riga deve valere il posto che occupa.

## 3. Proposta

Una riga per concetto: `comando o regola` - perche'. Niente cronaca della
sessione e niente correzioni una tantum. Mostra ogni modifica come diff:

    ### ./CLAUDE.md
    **Perche':** <una riga>
    + <la riga nuova>
    - <la riga che diventa falsa, se c'e'>

## 4. Solo con il si'

Chiedi se applicarle e modifica solo quello che viene approvato. Poi, sempre
dopo il si': commit del solo CLAUDE.md (`git add CLAUDE.md`, messaggio in
italiano, es. "CLAUDE.md: quello che ha insegnato la sessione") e push sul
branch corrente. Senza commit e push, in una sessione cloud la modifica
sparisce con il contenitore.
