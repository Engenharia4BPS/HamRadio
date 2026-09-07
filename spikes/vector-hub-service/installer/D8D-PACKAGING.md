# GADX Vector - D8D Distribution Packaging

## Status

D8D.1 IMPLEMENTED - awaiting field build/verification.

Release under test:

```text
0.8.0-dev.4 / development / D8D
baseline: D8C-field-validated-2026-09-06
```

## D8D.1 - Versioned ZIP + integrity manifest

The installer now contains:

```text
build-release-package.ps1
verify-package.ps1
```

`build-release-package.ps1` builds a versioned distribution artifact from the current installer tree.

Default output:

```text
spikes/vector-hub-service/dist/
  GADX-Vector-<version>.zip
  GADX-Vector-<version>.zip.sha256
```

The ZIP contains a top-level folder named with the release version and includes the complete product installer tree required by the D1-D8 launcher/backend, excluding development-only simulation files and local installer cache.

The package also contains:

```text
PACKAGE-README.txt
package-manifest.json
verify-package.ps1
```

`package-manifest.json` records:

- product/version/phase/channel/baseline;
- repository and repository path;
- source Git commit when built from a checkout;
- relative path, size and SHA256 for every packaged file.

The adjacent `.zip.sha256` records the SHA256 of the final ZIP artifact.

## Build command

From a repository checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\spikes\vector-hub-service\installer\build-release-package.ps1"
```

An alternate output directory can be supplied:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File ".\spikes\vector-hub-service\installer\build-release-package.ps1" `
  -OutputDir "C:\Temp\GADX-Vector-dist"
```

## Package verification

After extracting the generated ZIP, run inside the extracted `GADX-Vector-<version>` folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\verify-package.ps1"
```

Expected result:

```text
PACKAGE_VERIFY_OK
```

Any missing file, size mismatch or SHA256 mismatch fails verification.

## Distribution exclusions

D8D.1 intentionally excludes:

```text
cache\
D8C-Repair-Simulation.cmd
setup-repair-simulation.ps1
```

The cache is machine/local-download state and must not silently become part of a release artifact. The D8C simulation files are development validation tools and are not part of the operator-facing package.

## Current limitation

D8D.1 makes the package contents explicit and verifiable, but the legacy `bootstrap-vector.ps1` still resolves the repository `main` branch when used as an updater.

Therefore D8D.1 is not yet a fully immutable release mechanism.

## D8D.2 - Next

Pin remote bootstrap/update operations to immutable release metadata:

```text
release identity
      -> immutable Git ref/commit
      -> download
      -> expected SHA256 / package manifest
      -> verify
      -> install/update
```

A release must never silently change because `main` advanced after the artifact was published.

## D8D.3 - Dependencies

After immutable source pinning, define predictable acquisition/verification for:

- Python 3.10 x64 with Tcl/Tk;
- pyserial 3.5;
- pywin32 312;
- com0com.

The target is a small GADX distribution artifact that obtains known dependencies from explicit sources, verifies them, and builds the private runtime without relying on arbitrary software already installed on the operator machine.
