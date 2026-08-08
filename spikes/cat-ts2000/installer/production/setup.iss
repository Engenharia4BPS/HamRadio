#define MyAppName "GADX Vector"
#define MyAppVersion "0.1.1-dev"
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
; Keep third-party payloads installed so Repair/Reinstall can rebuild the
; private Python runtime or reinstall com0com without requiring a fresh EXE.
Source: "payload\python-3.10.11-amd64.exe"; DestDir: "{app}\thirdparty"; DestName: "python-installer.exe"; Flags: ignoreversion
Source: "payload\Setup_com0com_v3.0.0.0_W7_x64_signed.exe"; DestDir: "{app}\thirdparty"; DestName: "com0com-installer.exe"; Flags: ignoreversion

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\install-vector.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated; StatusMsg: "Configurando GADX Vector..."

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\uninstall-vector.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated skipifdoesntexist
