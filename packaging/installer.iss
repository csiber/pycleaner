; PyCleaner — Inno Setup 6 telepítő. Fordítás (a repó gyökeréből, a PyInstaller-build után):
;   iscc /DAppVersion=5.0.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E0D5B57-3C47-4C55-9A0E-2F1E7C9B5A11}
AppName=PyCleaner
AppVersion={#AppVersion}
AppVerName=PyCleaner {#AppVersion}
AppPublisher=Polyák Csaba
AppPublisherURL=https://github.com/csiber/pycleaner
AppSupportURL=https://github.com/csiber/pycleaner/issues
AppUpdatesURL=https://github.com/csiber/pycleaner/releases
DefaultDirName={autopf}\PyCleaner
DefaultGroupName=PyCleaner
DisableProgramGroupPage=yes
; alapból a felhasználónak telepít (nem kell rendszergazda), de a varázsló felajánlja a gépszintűt
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PyCleaner-{#AppVersion}-Setup
SetupIconFile=..\pycleaner\static\favicon.ico
UninstallDisplayIcon={app}\PyCleaner.exe
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LicenseFile=..\LICENSE
CloseApplications=yes

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PyCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PyCleaner"; Filename: "{app}\PyCleaner.exe"
Name: "{group}\PyCleaner (rendszergazdaként)"; Filename: "{app}\PyCleaner.exe"; Comment: "Jobb klikk → Futtatás rendszergazdaként is működik"
Name: "{autodesktop}\PyCleaner"; Filename: "{app}\PyCleaner.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PyCleaner.exe"; Description: "{cm:LaunchProgram,PyCleaner}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; a beállítások és mentések (%LOCALAPPDATA%\PyCleaner) szándékosan megmaradnak
Type: filesandordirs; Name: "{app}"
