#ifndef AppVersion
  #define AppVersion "0.5.4"
#endif
#define AppName "ModeShift"
#define AppExeName "ModeShift.exe"

[Setup]
AppId={{9ED28288-647D-47C8-8C2B-8CB8994452F5}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=ModeShift
DefaultDirName={localappdata}\Programs\ModeShift
DefaultGroupName=ModeShift
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ModeShiftSetup
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\assets\modeshift.ico
UninstallDisplayIcon={app}\ModeShift.exe
ChangesAssociations=no
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no
DisableFinishedPage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=no

[Files]
Source: "..\dist\ModeShift.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Icons]
Name: "{autoprograms}\ModeShift"; Filename: "{app}\ModeShift.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ModeShift"; Filename: "{app}\ModeShift.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\ModeShift.exe"; Description: "Launch ModeShift"; Flags: nowait postinstall skipifsilent

; Presets, snapshots, history and guard logs live in
; %LOCALAPPDATA%\ModeShift, NOT in the installation directory.
; An uninstall must never delete user data.
