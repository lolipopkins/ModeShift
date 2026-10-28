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
DisableWelcomePage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableFinishedPage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UsePreviousAppDir=no
SetupLogging=yes

[Files]
Source: "..\dist\ModeShift\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Icons]
Name: "{autoprograms}\ModeShift"; Filename: "{app}\ModeShift.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ModeShift"; Filename: "{app}\ModeShift.exe"; Tasks: desktopicon; WorkingDir: "{app}"

; No automatic launch: the manual installer must finish visibly before ModeShift opens.

; Presets, snapshots, history and guard logs live in
; %LOCALAPPDATA%\ModeShift, NOT in the installation directory.
; An uninstall must never delete user data.

[Code]
var
  BrandPage: TWizardPage;
  InstallDir: TNewEdit;
  DesktopOption: TNewCheckBox;

procedure BrowseInstallDir(Sender: TObject); forward;

procedure InitializeWizard;
var
  Heading: TNewStaticText;
  Subheading: TNewStaticText;
  DirLabel: TNewStaticText;
  Footnote: TNewStaticText;
  BrowseButton: TNewButton;
begin
  BrandPage := CreateCustomPage(wpWelcome, 'ModeShift Setup', 'Your workstation, your workflow.');
  BrandPage.Surface.Color := $001B120B;

  Heading := TNewStaticText.Create(BrandPage);
  Heading.Parent := BrandPage.Surface;
  Heading.Left := ScaleX(18);
  Heading.Top := ScaleY(18);
  Heading.Font.Name := 'Segoe UI';
  Heading.Font.Size := 23;
  Heading.Font.Style := [fsBold];
  Heading.Font.Color := $0038ADFF;
  Heading.Caption := 'MODESHIFT';

  Subheading := TNewStaticText.Create(BrandPage);
  Subheading.Parent := BrandPage.Surface;
  Subheading.Left := ScaleX(20);
  Subheading.Top := ScaleY(73);
  Subheading.AutoSize := False;
  Subheading.Width := ScaleX(370);
  Subheading.Height := ScaleY(48);
  Subheading.Font.Name := 'Segoe UI';
  Subheading.Font.Size := 10;
  Subheading.Font.Color := clWhite;
  Subheading.Caption := 'Set up your personal Windows workstation manager.' + #13#10 +
    'No account. No subscription. Your settings stay on this PC.';

  DirLabel := TNewStaticText.Create(BrandPage);
  DirLabel.Parent := BrandPage.Surface;
  DirLabel.Left := ScaleX(20);
  DirLabel.Top := ScaleY(138);
  DirLabel.Font.Color := clWhite;
  DirLabel.Caption := 'INSTALL LOCATION';

  InstallDir := TNewEdit.Create(BrandPage);
  InstallDir.Parent := BrandPage.Surface;
  InstallDir.Left := ScaleX(20);
  InstallDir.Top := ScaleY(163);
  InstallDir.Width := ScaleX(285);
  InstallDir.Height := ScaleY(26);
  InstallDir.Text := WizardDirValue();

  BrowseButton := TNewButton.Create(BrandPage);
  BrowseButton.Parent := BrandPage.Surface;
  BrowseButton.Left := ScaleX(314);
  BrowseButton.Top := ScaleY(162);
  BrowseButton.Width := ScaleX(73);
  BrowseButton.Height := ScaleY(27);
  BrowseButton.Caption := 'Browse...';
  BrowseButton.OnClick := @BrowseInstallDir;

  DesktopOption := TNewCheckBox.Create(BrandPage);
  DesktopOption.Parent := BrandPage.Surface;
  DesktopOption.Left := ScaleX(20);
  DesktopOption.Top := ScaleY(211);
  DesktopOption.Width := ScaleX(350);
  DesktopOption.Caption := 'Create a desktop shortcut';
  DesktopOption.Font.Color := clWhite;
  DesktopOption.Checked := WizardIsTaskSelected('desktopicon');

  Footnote := TNewStaticText.Create(BrandPage);
  Footnote.Parent := BrandPage.Surface;
  Footnote.Left := ScaleX(20);
  Footnote.Top := ScaleY(268);
  Footnote.AutoSize := False;
  Footnote.Width := ScaleX(364);
  Footnote.Height := ScaleY(35);
  Footnote.Font.Color := $00C3A996;
  Footnote.Caption := 'Your saved presets and snapshots are preserved across updates.';
end;

procedure BrowseInstallDir(Sender: TObject);
var
  Dir: String;
begin
  Dir := InstallDir.Text;
  if BrowseForFolder('Choose where to install ModeShift', Dir, False) then
    InstallDir.Text := Dir;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = BrandPage.ID then begin
    if Trim(InstallDir.Text) = '' then begin
      MsgBox('Choose an installation folder.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    WizardForm.DirEdit.Text := InstallDir.Text;
    if DesktopOption.Checked then
      WizardSelectTasks('desktopicon')
    else
      WizardSelectTasks('!desktopicon');
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := PageID = wpSelectTasks;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = BrandPage.ID then
    WizardForm.NextButton.Caption := 'Install ModeShift'
  else if CurPageID = wpFinished then
    WizardForm.NextButton.Caption := 'Finish';
end;
