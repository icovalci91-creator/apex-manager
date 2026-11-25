@echo off
REM Apex Manager - aggiorna i sorgenti e costruisce l'eseguibile sul PC.
REM
REM Si lancia con un doppio clic, da dove si vuole (il desktop va bene): non
REM ha bisogno di stare dentro al progetto, che sta in CARTELLA qui sotto
REM (la copia di lavoro sul desktop). Se la cartella non c'e' la scarica, se
REM c'e' la aggiorna. Poi fa quello che fa la build su GitHub
REM (.github/workflows/windows.yml): installa le librerie, scrive la sigla
REM della build, impacchetta con PyInstaller e, se sul PC c'e' Inno Setup,
REM fa anche l'installatore.
REM
REM Aggiornare non butta niente: le modifiche fatte a mano nei file del gioco
REM si mettono da parte, si scarica il nuovo e si rimettono sopra, cosi'
REM l'eseguibile esce con l'ultima versione di GitHub piu' le tue modifiche.
REM I salvataggi (saves/*.json) e gli altri file ignorati da git non li tocca.
REM
REM Le librerie stanno in un ambiente virtuale (.venv dentro la cartella)
REM per non sporcare il Python di sistema, e PyInstaller e' alla stessa
REM versione della build su GitHub: se cambia la', va cambiata anche qui.
REM
REM Il file deve restare con gli a capo di Windows (CRLF, lo garantisce
REM .gitattributes): con quelli di Linux cmd.exe sbaglia i salti alle
REM etichette.

setlocal EnableExtensions
title Apex Manager - aggiorna e costruisci

REM ---------------------------------------------------------------- impostazioni
set "REPO=https://github.com/icovalci91-creator/apex-manager.git"
set "RAMO=claude/game-analysis-l4v034"
set "CARTELLA=%USERPROFILE%\Desktop\racing-manager"
set "PYINSTALLER=pyinstaller==6.11.1"
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

echo.
echo  ==========================================================
echo    APEX MANAGER - aggiornamento e nuova build
echo  ==========================================================
echo    Sorgenti in: %CARTELLA%
echo    Ramo:        %RAMO%
echo.

REM ---------------------------------------------------------------- 1. attrezzi
echo  [1/5] Controllo che ci siano Git e Python...
where git >nul 2>nul
if errorlevel 1 goto :manca_git
call :trova_python
if errorlevel 1 goto :manca_python
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%v"
echo        Git trovato, Python %PYVER% (%PY%)
echo.

REM ---------------------------------------------------------------- 2. sorgenti
if exist "%CARTELLA%\.git" goto :aggiorna
echo  [2/5] Prima volta: scarico il gioco da GitHub...
echo        (se GitHub chiede di accedere, accedi con il tuo account)
git clone --branch "%RAMO%" "%REPO%" "%CARTELLA%"
if errorlevel 1 goto :errore
goto :sorgenti_pronti

:aggiorna
echo  [2/5] Aggiorno il gioco da GitHub...
cd /d "%CARTELLA%"
git fetch origin "%RAMO%"
if errorlevel 1 goto :errore
REM Le modifiche fatte a mano si mettono da parte (git stash), si aggiorna e
REM si rimettono sopra. Se l'aggiornamento tocca le stesse righe ci si
REM ferma, e le modifiche restano salvate nello stash: non si perde niente.
set "DA_PARTE="
set "CAMBIATI="
for /f "delims=" %%f in ('git status --porcelain --untracked-files^=no') do set "CAMBIATI=1"
if not defined CAMBIATI goto :avanti
echo        Hai file cambiati a mano, li tengo:
git status --short --untracked-files=no
git stash push --quiet -m "AggiornaECostruisci"
if errorlevel 1 goto :errore
set "DA_PARTE=1"
:avanti
REM --ff-only: si va avanti solo se GitHub ha la stessa storia piu' qualcosa
REM di nuovo. Con commit tuoi che GitHub non ha non si mescola niente: si
REM costruisce la versione che c'e' qui.
git merge --ff-only --quiet FETCH_HEAD
if errorlevel 1 goto :non_aggiornato
goto :rimetti
:non_aggiornato
echo        Non aggiorno: qui ci sono commit tuoi che GitHub non ha.
echo        Costruisco la versione che hai in questa cartella.
:rimetti
if not defined DA_PARTE goto :sorgenti_pronti
git stash pop --quiet
if errorlevel 1 goto :scontro
echo        Le tue modifiche sono di nuovo al loro posto.


:sorgenti_pronti
cd /d "%CARTELLA%"
git log -1 --format="       Ultimo cambiamento: %%h %%cd - %%s" --date=format:"%%d/%%m %%H:%%M"
echo.

REM ---------------------------------------------------------------- 3. librerie
echo  [3/5] Installo le librerie (la prima volta ci mette qualche minuto)...
if exist ".venv\Scripts\python.exe" goto :venv_pronto
%PY% -m venv .venv
if errorlevel 1 goto :errore
:venv_pronto
set "VPY=%CARTELLA%\.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r requirements.txt %PYINSTALLER% --disable-pip-version-check
if errorlevel 1 goto :errore_librerie
echo        Fatto.
echo.

REM ---------------------------------------------------------------- 4. eseguibile
echo  [4/5] Costruisco ApexManager.exe (qualche minuto)...
REM la sigla che il gioco mostra nel menu, come nella build di GitHub
git log -1 --format="%%h %%cd" --date=format:"%%d/%%m %%H:%%M" > data\build.txt
"%VPY%" -m PyInstaller --noconfirm --clean --log-level WARN apex.spec
if errorlevel 1 goto :errore
if not exist "dist\ApexManager.exe" goto :errore
echo        Fatto: %CARTELLA%\dist\ApexManager.exe
echo.

REM ---------------------------------------------------------------- 5. installatore
if not exist "%ISCC%" goto :senza_installatore
echo  [5/5] Costruisco anche l'installatore...
set "APEX_CARTELLA=1"
"%VPY%" -m PyInstaller --noconfirm --log-level WARN --distpath dist_cartella --workpath build_cartella apex.spec
if errorlevel 1 goto :errore
set "APEX_CARTELLA="
"%ISCC%" /Q "/DVersione=0.1.0" installer\apex.iss
if errorlevel 1 goto :errore
echo        Fatto: %CARTELLA%\dist\ApexManager-Setup.exe
goto :fine

:senza_installatore
echo  [5/5] Installatore saltato: Inno Setup 6 non e' installato.
echo        Non serve per giocare. Se lo vuoi: winget install JRSoftware.InnoSetup

:fine
echo.
echo  ==========================================================
echo    TUTTO FATTO
echo  ==========================================================
echo.
start "" explorer "%CARTELLA%\dist"
choice /c SN /n /m "  Vuoi avviare il gioco adesso? [S/N] "
if errorlevel 2 goto :chiudi
start "" "%CARTELLA%\dist\ApexManager.exe"
goto :chiudi

REM ---------------------------------------------------------------- sottoprogrammi

:trova_python
REM prima il 3.11, che e' quello della build su GitHub; poi qualunque
REM Python 3. "python" da solo puo' essere il finto Python del Microsoft
REM Store, che non esegue niente: la prova con -c lo scarta.
set "PY="
py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (set "PY=py -3.11" & exit /b 0)
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (set "PY=py -3" & exit /b 0)
python -c "import sys" >nul 2>nul
if not errorlevel 1 (set "PY=python" & exit /b 0)
exit /b 1

:manca_git
echo.
echo  Git non c'e' su questo PC: serve per scaricare il gioco da GitHub.
choice /c SN /n /m "  Lo installo adesso con winget? [S/N] "
if errorlevel 2 goto :link_git
winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
echo.
echo  Fatto. Chiudi questa finestra e rilancia il file: Windows vede Git
echo  solo nelle finestre aperte dopo l'installazione.
goto :chiudi
:link_git
echo  Scaricalo da https://git-scm.com/download/win e poi rilancia il file.
goto :chiudi

:manca_python
echo.
echo  Python non c'e' su questo PC: serve per costruire il gioco.
choice /c SN /n /m "  Installo Python 3.11 adesso con winget? [S/N] "
if errorlevel 2 goto :link_python
winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
echo.
echo  Fatto. Chiudi questa finestra e rilancia il file.
goto :chiudi
:link_python
echo  Scarica Python 3.11 da https://www.python.org/downloads/
echo  (durante l'installazione spunta "Add python.exe to PATH") e rilancia il file.
goto :chiudi

:scontro
echo.
echo  Le tue modifiche toccano le stesse righe dell'aggiornamento e non si
echo  rimettono da sole. Non le ho buttate: i file in conflitto hanno dentro
echo  sia la tua versione sia quella nuova, segnate con ^<^<^<^<^<^<^< e ^>^>^>^>^>^>^>.
echo  Sistemali con il tuo editor e rilancia. Una copia resta in git stash.
goto :errore_msg

:errore_librerie
echo.
echo  Le librerie non si sono installate. Se il Python usato e' molto
echo  recente (%PYVER%), puo' darsi che Panda3D non sia ancora uscito per
echo  quella versione: installa Python 3.11 (winget install Python.Python.3.11),
echo  cancella la cartella %CARTELLA%\.venv e rilancia il file.
goto :errore_msg

:errore
echo.
echo  Qualcosa e' andato storto: leggi le righe qui sopra.
:errore_msg
echo.
pause
exit /b 1

:chiudi
echo.
pause
exit /b 0
