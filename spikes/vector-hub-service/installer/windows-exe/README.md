# GADX Vector Windows EXE

This directory contains the Inno Setup wrapper used to produce the product-style `GADX-Vector-Setup-<version>.exe`.

The EXE does not replace the validated PowerShell backend. It embeds the immutable D8D release package, installs that package under `C:\Ham\GADX-Vector\installer` by default, and launches the existing `setup-launcher.ps1` GUI. Preview/Apply safety, Port Manager, runtime/com0com handling, migration, repair, rollback and commissioning remain owned by the existing installer backend.

## Build requirements

- Windows 10/11 x64
- PowerShell 5.1+
- Git checkout or installer tree with a valid immutable `source-lock.json`
- Inno Setup 6 with `ISCC.exe`

## Build

From an elevated PowerShell prompt:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\build-windows-exe.ps1
```

Expected marker:

```text
WINDOWS_EXE_BUILD_OK
```

Output is written under:

```text
dist\exe\GADX-Vector-Setup-<version>.exe
dist\exe\GADX-Vector-Setup-<version>.exe.sha256
```

The builder first creates the immutable D8D ZIP package and then compiles that exact staged package into the EXE.

## Runtime behavior

The EXE requires Administrator privileges. It copies only the installer package and then offers to open the GADX Vector Setup GUI. The GUI still requires Preview before Apply where applicable and keeps all D1-D8 safety gates intact.

`Uninstallable=no` is intentional for this first product wrapper. Removal of GADX Vector, com0com and shared station resources needs a separately designed safe uninstall workflow rather than a generic Inno Setup rollback.
