#ifndef AppVersion
  #error AppVersion define is required
#endif
#ifndef PackageRoot
  #error PackageRoot define is required
#endif
#ifndef OutputDir
  #error OutputDir define is required
#endif

#define MyAppName "GADX Vector"
#define MyPublisher "Grupo Araucaria de DX"
#define MyAppId "{{62D78B83-5254-4B00-8E71-6BB89D32FDC6}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyPublisher}
DefaultDirName=C:\Ham\GADX-Vector
DefaultGroupName=GADX Vector
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=GADX-Vector-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.10240
WizardStyle=modern
SetupLogging=yes
Uninstallable=no
CloseApplications=no
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Criar atalho do GADX Vector Setup na area de trabalho"; Flags: unchecked

[Files]
Source: "{#PackageRoot}\*"; DestDir: "{app}\installer"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GADX Vector Setup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\setup-launcher.ps1"" -InstallRoot ""{app}"""; WorkingDir: "{app}\installer"
Name: "{commondesktop}\GADX Vector Setup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\setup-launcher.ps1"" -InstallRoot ""{app}"""; WorkingDir: "{app}\installer"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\setup-launcher.ps1"" -InstallRoot ""{app}"""; Description: "Abrir GADX Vector Setup"; Flags: postinstall nowait skipifsilent
