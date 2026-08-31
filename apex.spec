# -*- mode: python ; coding: utf-8 -*-
"""Ricetta con cui PyInstaller impacchetta Apex Manager in un eseguibile.

    pyinstaller apex.spec

Ne esce un file solo - dist/ApexManager.exe su Windows, dist/ApexManager su
Linux e Mac - che si porta dietro Python, pygame e tutti i dati del gioco. Chi
lo riceve non deve installare niente: lo copia dove vuole e ci clicca sopra.

Due cose vale la pena spiegare, perche' non sono ovvie.

**I dati viaggiano dentro.** `datas` mette `data/` e `assets/` dentro
all'eseguibile. All'avvio PyInstaller li scompatta in una cartella temporanea e
ne scrive il percorso in `sys._MEIPASS`, che e' quello che `game/config.py`
legge per sapere dove stanno. I salvataggi invece *non* finiscono li': quella
cartella viene cancellata alla chiusura, quindi vanno in %APPDATA% - se ne
occupa sempre config.py.

**Cosa resta fuori.** Le librerie che pygame si porta dietro per cose che
questo gioco non fa - numpy, i test, tkinter - si escludono a mano: sono
qualche decina di megabyte di roba che nessuno aprira' mai. `tools/` e gli
screenshot non entrano affatto: servono a chi sviluppa, non a chi gioca.
"""

blocco = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # (da dove, dove finisce dentro al pacchetto): le due cartelle che il gioco
    # legge all'avvio, con la stessa struttura che hanno nel progetto
    datas=[('data', 'data'), ('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'tkinter', 'unittest', 'pydoc_data', 'test',
        'pygame.tests', 'PIL', 'setuptools', 'pip',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ApexManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX comprime l'eseguibile ma su Windows fa insospettire piu' di un
    # antivirus, e un gioco che l'antivirus mette in quarantena non lo apre
    # nessuno. Meglio venti megabyte in piu'
    upx=False,
    runtime_tmpdir=None,
    # niente finestra del terminale dietro al gioco: si apre la finestra e
    # basta, come ci si aspetta da un programma
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/apex.ico' if __import__('os').path.exists('assets/apex.ico') else None,
)
