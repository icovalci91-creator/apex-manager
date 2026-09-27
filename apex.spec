# -*- mode: python ; coding: utf-8 -*-
"""Ricetta con cui PyInstaller impacchetta Apex Manager in un eseguibile.

    pyinstaller apex.spec

Ne esce un file solo - dist/ApexManager.exe su Windows, dist/ApexManager su
Linux e Mac - che si porta dietro Python, pygame e tutti i dati del gioco. Chi
lo riceve non deve installare niente: lo copia dove vuole e ci clicca sopra.

Con APEX_CARTELLA=1 ne esce invece una cartella, dist/ApexManager/, con i dati
gia' scompattati accanto all'eseguibile: e' quella che l'installatore
(installer/apex.iss) mette su disco.

Due cose vale la pena spiegare, perche' non sono ovvie.

**I dati viaggiano dentro.** `datas` mette `data/` e `assets/` dentro
all'eseguibile. All'avvio PyInstaller li scompatta in una cartella temporanea e
ne scrive il percorso in `sys._MEIPASS`, che e' quello che `game/config.py`
legge per sapere dove stanno. I salvataggi invece *non* finiscono li': quella
cartella viene cancellata alla chiusura, quindi vanno in %APPDATA% - se ne
occupa sempre config.py.

**La vista 3D.** `moderngl` carica i suoi pezzi per il sistema operativo
(`glcontext.wgl` su Windows) solo quando serve, e PyInstaller da solo non li
vede: si elencano qui, se no l'eseguibile parte ma la gara resta in 2D.

**Panda3D.** Il motore della vista 3D: se ne prende solo il nucleo con
OpenGL (vedi sotto), e l'eseguibile sa dire se si accende con
`ApexManager.exe --prova-3d`, che scrive com'e' andata in prova3d.txt.

**Il suono.** Si sintetizza all'avvio con numpy (`game/ui/sintesi.py`): e'
l'unica libreria in piu', e pesa una quindicina di megabyte.

**Cosa resta fuori.** Le librerie che pygame si porta dietro per cose che
questo gioco non fa - i test, tkinter - si escludono a mano: sono qualche
megabyte di roba che nessuno aprira' mai. `tools/` e gli screenshot non
entrano affatto: servono a chi sviluppa, non a chi gioca.
"""

from PyInstaller.utils.hooks import collect_submodules

blocco = None

# Panda3D, il motore della vista 3D: del pacchetto (quasi duecento megabyte)
# servono il nucleo, OpenGL (con Cg, a cui il modulo di OpenGL e' legato) e
# la finestra di Windows. Il nucleo lo trova
# PyInstaller seguendo gli import; il modulo di OpenGL e quello della finestra
# Panda3D li carica da solo quando serve, e vanno elencati. Il resto - video,
# audio, fisica, DirectX, gli strumenti - resta fuori.
import os
PANDA_BIN = []
try:
    import panda3d
    _cartella_panda = os.path.dirname(panda3d.__file__)
    for _f in os.listdir(_cartella_panda):
        if _f.split('.')[0] in ('libpandagl', 'libp3windisplay', 'libp3x11display',
                                'libpandagles2', 'libp3headlessgl'):
            PANDA_BIN.append((os.path.join(_cartella_panda, _f), 'panda3d'))
except ImportError:
    pass
PANDA_FUORI = ('avcodec', 'avformat', 'avutil', 'avfilter', 'avdevice', 'swscale',
               'swresample', 'cgd3d9', 'tinydisplay', 'assimp',
               'fmod', 'openal', 'bullet', 'ode', 'libpandaegg', 'egg.', 'dx9', 'd3dx9',
               'ffmpeg', 'vrpn', 'vision', 'physics', 'libpandaai', 'ai.', 'skel', 'fx.',
               'libpandafx', 'ptloader', 'rplight')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=PANDA_BIN,
    # (da dove, dove finisce dentro al pacchetto): le due cartelle che il gioco
    # legge all'avvio, con la stessa struttura che hanno nel progetto
    # e i dintorni dei circuiti per la vista 3D, se qualcuno li ha scaricati
    # con tools/fetch_dintorni.py: finche' la cartella non c'e' si fa senza
    datas=[('data', 'data'), ('assets', 'assets')]
          + ([('dintorni', 'dintorni')] if __import__('os').path.isdir('dintorni') else [])
          # e le texture e i cieli fotografici, se tools/fetch_grafica.py li ha scaricati
          + ([('grafica', 'grafica')] if __import__('os').path.isdir('grafica') else []),
    hiddenimports=['moderngl', '_moderngl', 'panda3d.core'] + collect_submodules('glcontext'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'pydoc_data', 'test',
        'pygame.tests', 'PIL', 'setuptools', 'pip',
        'direct', 'panda3d.bullet', 'panda3d.ode', 'panda3d.egg', 'panda3d.physics',
        'panda3d.fx', 'panda3d.ai', 'panda3d.skel', 'panda3d.vision', 'panda3d.vrpn',
        'panda3d.direct', 'panda3d._rplight',
    ],
    noarchive=False,
    optimize=0,
)
# fuori i pezzi di Panda3D che non servono, anche se qualcosa li ha tirati dentro
a.binaries = [b for b in a.binaries
              if not ('panda3d' in b[0].replace('\\', '/').lower()
                      and any(k in os.path.basename(b[0]).lower() for k in PANDA_FUORI))]
pyz = PYZ(a.pure)

# Due modi di impacchettare, dalla stessa ricetta:
#   * un file solo (di norma): dist/ApexManager.exe, da copiare e lanciare;
#   * una cartella (APEX_CARTELLA=1): dist/ApexManager/ con l'eseguibile e
#     tutto il resto gia' scompattato accanto. E' quella che mette su disco
#     l'installatore (installer/apex.iss): il gioco parte subito, senza
#     scompattarsi in una cartella temporanea a ogni avvio.
import os
CARTELLA = os.environ.get("APEX_CARTELLA") == "1"
ICONA = 'assets/apex.ico' if os.path.exists('assets/apex.ico') else None

if CARTELLA:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ApexManager',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICONA,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ApexManager')
else:
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
        # antivirus, e un gioco che l'antivirus mette in quarantena non lo
        # apre nessuno. Meglio venti megabyte in piu'
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
        icon=ICONA,
    )
