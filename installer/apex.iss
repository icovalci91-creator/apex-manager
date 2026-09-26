; L'installatore di Apex Manager per Windows (Inno Setup 6).
;
; Mette su disco la cartella fatta da PyInstaller con APEX_CARTELLA=1
; (dist_cartella/ApexManager): l'eseguibile e, accanto, tutto il gioco gia'
; scompattato - cosi' parte subito, invece di scompattarsi in una cartella
; temporanea a ogni avvio come fa l'eseguibile a file singolo.
;
; Si installa per l'utente, senza chiedere i permessi di amministratore, in
; %LOCALAPPDATA%\Programs\Apex Manager. I salvataggi non stanno li' ma in
; %APPDATA%\ApexManager: aggiornare o disinstallare il gioco non li tocca.
;
; Si compila dalla build su GitHub (.github/workflows/windows.yml):
;   iscc /DVersione=0.1.97 installer\apex.iss

#ifndef Versione
  #define Versione "0.1"
#endif

[Setup]
AppId={{6B0E3A52-9C4F-4E7A-A1D2-5F3C8B7E9A10}
AppName=Apex Manager
AppVersion={#Versione}
AppVerName=Apex Manager {#Versione}
AppPublisher=Apex Manager
DefaultDirName={localappdata}\Programs\Apex Manager
DefaultGroupName=Apex Manager
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ApexManager-Setup
SetupIconFile=..\assets\apex.ico
UninstallDisplayIcon={app}\ApexManager.exe
UninstallDisplayName=Apex Manager
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; se il gioco e' aperto, l'installatore chiede di chiuderlo prima di aggiornarlo
CloseApplications=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; un aggiornamento non deve lasciarsi dietro i pezzi della versione vecchia
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist_cartella\ApexManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Apex Manager"; Filename: "{app}\ApexManager.exe"
Name: "{autodesktop}\Apex Manager"; Filename: "{app}\ApexManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ApexManager.exe"; Description: "{cm:LaunchProgram,Apex Manager}"; Flags: nowait postinstall skipifsilent
