#define MyAppName "GADX Vector"
#define MyAppVersion "0.1.0-dev"
#define MyAppPublisher "Araucaria DX Group / Engenharia 4BPS"

[Setup]
AppId={{8E39E85D-8A49-4EF7-ABCC-4D7C9E5A2D71}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\Ham\GADX-Vector
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=GADX-Vector-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#MyAppName}
SetupLogging=yes

[Dirs]
Name: "{app}\app"
Name: "{app}\runtime"
Name: "{app}\service"
Name: "{app}\config"
Name: "{app}\logs"
Name: "{app}\installer"
Name: "{app}\thirdparty"

[Files]
Source: "..\..\rigctld_bridge.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\ts2000.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\service\vector_bridge_service.py"; DestDir: "{app}\service"; Flags: ignoreversion
Source: "install-vector.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "uninstall-vector.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "payload\python-installer.exe"; DestDir: "{app}\thirdparty"; Flags: ignoreversion deleteafterinstall
Source: "payload\com0com\*"; DestDir: "{app}\thirdparty\com0com"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\install-vector.ps1"" -InstallRoot ""{app}"" -RadioKeyingPort ""{code:GetRadioKeyPort}"" -RadioKeyingBaud {code:GetRadioKeyBaud} -RigHost ""{code:GetRigHost}"" -RigPort {code:GetRigPort}"; Flags: runhidden waituntilterminated; StatusMsg: "Instalando runtime, portas COM e serviço GADX Vector..."

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\uninstall-vector.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
var
  RadioPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  RadioPage := CreateInputQueryPage(
    wpSelectDir,
    'Interface do rádio',
    'Configuração do rádio físico',
    'Informe a porta de keying e o endpoint rigctld. Estes valores podem ser alterados depois em config\bridge.ini.'
  );
  RadioPage.Add('Porta COM para CW keying:', False);
  RadioPage.Add('Baud da porta de keying:', False);
  RadioPage.Add('Host do rigctld:', False);
  RadioPage.Add('Porta TCP do rigctld:', False);
  RadioPage.Values[0] := 'COM22';
  RadioPage.Values[1] := '9600';
  RadioPage.Values[2] := '127.0.0.1';
  RadioPage.Values[3] := '4532';
end;

function GetRadioKeyPort(Param: String): String;
begin
  Result := RadioPage.Values[0];
end;

function GetRadioKeyBaud(Param: String): String;
begin
  Result := RadioPage.Values[1];
end;

function GetRigHost(Param: String): String;
begin
  Result := RadioPage.Values[2];
end;

function GetRigPort(Param: String): String;
begin
  Result := RadioPage.Values[3];
end;
