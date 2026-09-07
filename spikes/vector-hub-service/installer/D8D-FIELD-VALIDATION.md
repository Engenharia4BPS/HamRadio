# GADX Vector - D8D field validation

## D8D.1 - Reproducible ZIP + integrity manifest

Date: 2026-09-06
Release tested: `0.8.0-dev.4 / development / D8D`

The release package builder was executed from an installed Vector tree and produced:

```text
C:\Ham\GADX-Vector\dist\GADX-Vector-0.8.0-dev.4.zip
C:\Ham\GADX-Vector\dist\GADX-Vector-0.8.0-dev.4.zip.sha256
```

Observed package SHA256:

```text
1104234c5597d371424d2195feef71bd6dec5c00d19949ed0bd67f07345fea94
```

The package contained 26 entries including `package-manifest.json`. After extraction, `verify-package.ps1` checked 25 manifest-tracked files and returned:

```text
PACKAGE_VERIFY_OK
```

Result: **D8D.1 VALIDATED IN FIELD.**

---

## D8D.2 - Immutable source pinning

Status: **VALIDATED IN FIELD**
Release: `0.8.0-dev.5 / development / D8D`
Date: 2026-09-06

Field commit lock:

```text
34deed4b4ec64285eb24598568bb4162014e8e51
```

The local bootstrap resolved `main` once and then downloaded by exact SHA:

```text
Source       : Engenharia4BPS/HamRadio @ 34deed4b4ec64285eb24598568bb4162014e8e51
Resolution   : resolved-ref
Pinned commit: 34deed4b4ec64285eb24598568bb4162014e8e51
```

The release builder used the same source lock and generated:

```text
C:\Ham\GADX-Vector\dist\GADX-Vector-0.8.0-dev.5.zip
SHA256: 941ba4f38dabc25826afff4ce9c3278e8aee27b017f87c449ddeb7ad0066d5fa
```

`verify-package.ps1` checked 27 manifest-tracked files and returned:

```text
PACKAGE_VERIFY_OK
```

The decisive packaged-bootstrap test was then run from the extracted ZIP. It reported:

```text
Source       : Engenharia4BPS/HamRadio @ 34deed4b4ec64285eb24598568bb4162014e8e51
Resolution   : package-lock
Release      : 0.8.0-dev.5 / development / D8D
Pinned commit: 34deed4b4ec64285eb24598568bb4162014e8e51
```

The installed machine remained healthy:

```text
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

Result: **D8D.2 IMMUTABLE SOURCE PINNING VALIDATED IN FIELD.**

### Development refresh policy

Field development immediately exposed an important consequence of immutable package-lock behavior: after testing an extracted pinned package, the installed bootstrap correctly continued to follow that package lock and therefore did not automatically see newer commits on `main`.

This is correct for a distributed release, but development needs an explicit escape hatch. `bootstrap-vector.ps1` now accepts:

```powershell
-RefreshSource
```

Default behavior remains immutable: when a local source lock exists, the bootstrap uses `package-lock`. Only an explicit `-RefreshSource` bypasses the local lock once, resolves the configured default ref (`main`) to a new exact SHA, downloads by that SHA, and writes a new source lock with:

```text
Resolution: resolved-ref-refresh
```

This preserves release immutability while providing a deliberate development/update path.

---

## D8D.3 - Reproducible dependency lock

### D8D.3A - Dependency artifact lock

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.6 / development / D8D.3`
Date: 2026-09-06

D8D.3A introduced `dependency-lock.json` and `verify-dependency-lock.ps1`.

The lock pins these downloadable artifacts by version, size and SHA256:

```text
Python 3.10.11 x64
pyserial 3.5 wheel
pywin32 312 cp310 win_amd64 wheel
```

The validator was exercised in both modes and passed:

```text
DEPENDENCY_LOCK_STRUCTURE_OK
DEPENDENCY_LOCK_ONLINE_OK
```

Online validation downloaded only to a temporary directory, compared exact size + SHA256, and removed the temporary files. No Vector runtime, service, COM configuration or radio state was changed.

Result: **D8D.3A DEPENDENCY ARTIFACT LOCK VALIDATED IN FIELD.**

com0com remains explicitly marked as not-yet-pinned. Its redistribution/source/hash policy remains a separate D8D.3B task.

### D8D.3A.2 - Locked wheel installation path

Status: **VALIDATED IN FIELD**
Release: `0.8.0-dev.7 / development / D8D.3`
Date: 2026-09-06

Before changing production `ensure-runtime.ps1`, the exact locked wheel installation path was validated in isolation.

Artifacts:

```text
install-locked-python-packages.ps1
verify-locked-python-install.ps1
```

The installer helper:

- reads only wheel entries from `dependency-lock.json`;
- downloads exact locked wheel URLs;
- rejects size or SHA256 mismatch;
- installs with `pip --no-index --no-deps` from the verified local wheel files;
- can install to an isolated target directory for field testing without modifying the Vector runtime.

The isolated verifier installed into a temporary site-packages directory, loaded that directory with `site.addsitedir`, imported pyserial + pywin32 service modules, and verified package versions `3.5` and `312`.

Field result:

```text
Downloading locked Python package pyserial...
Python package pyserial download: verified size + SHA256
Downloading locked Python package pywin32...
Python package pywin32 download: verified size + SHA256
Installing only verified locked wheel files...
Successfully installed pyserial-3.5 pywin32-312
LOCKED_PYTHON_PACKAGES_INSTALLED
LOCKED_PYTHON_IMPORTS_OK
LOCKED_PYTHON_INSTALL_TEST_OK
```

The real Vector runtime was not modified by this validation.

Two subsequent PowerShell `CommandNotFoundException` messages were unrelated to the test: the wheel filenames were entered manually as shell commands. `.whl` files are Python package archives, not executable PowerShell commands.

Result: **D8D.3A.2 LOCKED PYTHON INSTALLATION PATH VALIDATED IN FIELD.**

### D8D.3A.3 - Production ensure-runtime consumes lock

Status: **VALIDATED IN FIELD**
Release: `0.8.0-dev.8 / development / D8D.3`
Date: 2026-09-07

Production `ensure-runtime.ps1` consumes `dependency-lock.json` directly.

The real-machine Preview reported:

```text
Dependency lock: Python 3.10.11 / pyserial 3.5 / pywin32 312
Runtime      : OK - locked versions
Service host : OK
com0com      : C:\Program Files (x86)\com0com\setupc.exe
PREVIEW ONLY - no changes were made.
```

The isolated production-path validator then created a temporary Vector runtime and invoked the real production `ensure-runtime.ps1 -Apply`. The runtime was built from exact Python 3.10.11 and verified locked wheels. The test completed with:

```text
LOCKED_PYTHON_PACKAGES_INSTALLED
PYWIN32_SERVICE_HOST_OK
RUNTIME_DEPENDENCY_LOCK_OK
PRODUCTION_RUNTIME_IMPORTS_OK
PRODUCTION_RUNTIME_SERVICE_HOST_OK
PRODUCTION_RUNTIME_LOCK_TEST_OK
```

The temporary runtime was removed afterward. No Vector service registration/state, `vector.ini`, COM pair or radio state was changed by the validator.

Result: **D8D.3A.3 PRODUCTION RUNTIME DEPENDENCY LOCK VALIDATED IN FIELD.**

### D8D.3B - com0com distribution inventory and pinning

Status: **DISTRIBUTION LOCK VALIDATED IN FIELD**
Release tested: `0.8.0-dev.12 / development / D8D.3B`
Date: 2026-09-07

The read-only inventory identified the field installation as com0com `3.0.0.0` under `C:\Program Files (x86)\com0com` and captured exact hashes for the five relevant installed binaries. The inventory completed with:

```text
COM0COM_INVENTORY_OK
```

The installed-file validator passed for all five files:

```text
Installed com0com.sys: OK
Installed setup.dll: OK
Installed setupc.exe: OK
Installed setupg.exe: OK
Installed uninstall.exe: OK
COM0COM_INSTALLED_LOCK_OK
COM0COM_LOCK_STRUCTURE_OK
```

The first online distribution validation used the SourceForge web `/download` landing endpoint and downloaded content that did not match the locked executable. The lock was corrected to the direct SourceForge file endpoint:

```text
https://downloads.sourceforge.net/project/signed-drivers/com0com/v3.0/Setup_com0com_v3.0.0.0_W7_x64_signed.exe
```

The distribution fingerprint remained unchanged:

```text
filename: Setup_com0com_v3.0.0.0_W7_x64_signed.exe
size:     261544
sha256:   26486b28604b49a9008c54feb11b9ece0008a8287ee5caf0bcf2a62f4317128f
```

The online retest then passed:

```text
COM0COM_INSTALLED_LOCK_OK
Downloaded distribution: OK size + SHA256
COM0COM_DISTRIBUTION_LOCK_OK
COM0COM_LOCK_ONLINE_OK
```

Result: **D8D.3B COM0COM INSTALLED + DISTRIBUTION LOCK VALIDATED IN FIELD.**

### D8D.3B.2 - Production ensure-runtime consumes com0com lock

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.13 / development / D8D.3B`

Production `ensure-runtime.ps1` now treats com0com as a locked dependency instead of accepting any discovered or bundled installer.

Behavior:

- an existing com0com installation is accepted only when every locked installed-file size/SHA256 matches;
- an installed but mismatched com0com is reported as `VERSION/HASH DRIFT` and automatic replacement is blocked;
- a bundled installer is accepted only when it matches the locked distribution size/SHA256;
- if com0com is missing, the exact locked distribution is downloaded from the pinned URL and verified before execution;
- installation still suppresses creation of default CNCA0/CNCB0 and COMX/COMX pairs;
- installed files are revalidated against the lock after installation;
- a healthy Preview emits `COM0COM_DEPENDENCY_LOCK_OK` without making changes.

This stage deliberately does not reinstall com0com on the current field machine. Clean-machine installation of the locked kernel driver remains part of the D8G release-candidate compatibility matrix, especially for Windows 10/11 and Secure Boot behavior.

Acceptance for the current field machine:

```text
Dependency lock: Python 3.10.11 / pyserial 3.5 / pywin32 312 / com0com 3.0.0.0
com0com      : OK - locked 3.0.0.0 (...setupc.exe)
PREVIEW ONLY - no changes were made.
COM0COM_DEPENDENCY_LOCK_OK
```
