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

### Finding

The first field build reported:

```text
Source commit: unknown
```

This is expected when the package is built from `C:\Ham\GADX-Vector\installer`, because that installed tree is not a Git working copy. D8D.2 therefore adds an explicit immutable source lock rather than relying on `.git` metadata.

---

## D8D.2 - Immutable source pinning

Status: **PACKAGE BUILD + VERIFY VALIDATED; PACKAGED BOOTSTRAP TEST PENDING**
Release: `0.8.0-dev.5 / development / D8D`
Date: 2026-09-06

Design:

1. `bootstrap-vector.ps1` resolves a moving ref such as `main` to one exact 40-character Git commit before download.
2. The bootstrap downloads the archive by commit SHA, not by moving branch name.
3. The installed installer receives `source-lock.json` containing the resolved commit.
4. `build-release-package.ps1` requires an immutable source commit from `source-lock.json` or a real Git checkout.
5. The distribution package receives its own `source-lock.json` with `resolution = immutable-package-lock`.
6. When the packaged bootstrap is executed, it reads the package lock and downloads that exact commit without resolving `main` again.

### Field evidence

The local bootstrap resolved `main` to:

```text
34deed4b4ec64285eb24598568bb4162014e8e51
```

Observed bootstrap output:

```text
Source       : Engenharia4BPS/HamRadio @ 34deed4b4ec64285eb24598568bb4162014e8e51
Resolution   : resolved-ref
Release      : 0.8.0-dev.5 / development / D8D
Pinned commit: 34deed4b4ec64285eb24598568bb4162014e8e51
```

The installed source lock contained the same commit:

```text
repository    = Engenharia4BPS/HamRadio
requested_ref = main
source_commit = 34deed4b4ec64285eb24598568bb4162014e8e51
resolution    = resolved-ref
```

The release builder then reported:

```text
Source commit: 34deed4b4ec64285eb24598568bb4162014e8e51
Resolution   : source-lock
Pinned commit: 34deed4b4ec64285eb24598568bb4162014e8e51
```

Generated package:

```text
C:\Ham\GADX-Vector\dist\GADX-Vector-0.8.0-dev.5.zip
SHA256: 941ba4f38dabc25826afff4ce9c3278e8aee27b017f87c449ddeb7ad0066d5fa
```

After extraction, `verify-package.ps1` checked 27 manifest-tracked files and returned:

```text
PACKAGE_VERIFY_OK
```

The stale `%TEMP%\gadx-vector-bootstrap.ps1` was also replaced with the current pinned bootstrap to prevent accidentally returning to the pre-D8D moving-main behavior during field development.

### Remaining acceptance test

Run `bootstrap-vector.ps1` from the extracted `0.8.0-dev.5` package and confirm that it reports:

```text
Source       : Engenharia4BPS/HamRadio @ 34deed4b4ec64285eb24598568bb4162014e8e51
Resolution   : package-lock
```

The same SHA must continue to appear in:

```text
source-lock.json
package-manifest.json -> source_commit
PACKAGE-README.txt -> Source
bootstrap console output
```

If that test passes, D8D.2 immutable source pinning is fully field-validated.
