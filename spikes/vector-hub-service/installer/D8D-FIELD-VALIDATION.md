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

Status: **D8D.3A IN FIELD VALIDATION**
Release: `0.8.0-dev.6 / development / D8D.3`

D8D.3A introduces `dependency-lock.json` and `verify-dependency-lock.ps1`.

The initial lock pins these downloadable artifacts by version, size and SHA256:

```text
Python 3.10.11 x64
pyserial 3.5 wheel
pywin32 312 cp310 win_amd64 wheel
```

The validator has two modes:

```text
structure-only
online hash verification
```

Online validation downloads into a temporary directory only, compares exact size + SHA256, then deletes the temporary files. It does not touch the Vector runtime, service, COM configuration or radio.

com0com remains explicitly marked as not-yet-pinned in D8D.3A. Its redistribution/source/hash policy will be handled separately in D8D.3B instead of silently treating the currently installed copy as reproducible.

Acceptance for D8D.3A:

```text
DEPENDENCY_LOCK_STRUCTURE_OK
DEPENDENCY_LOCK_ONLINE_OK
```

Only after that field test will `ensure-runtime.ps1` be changed to consume the lock for actual runtime installation/repair.
