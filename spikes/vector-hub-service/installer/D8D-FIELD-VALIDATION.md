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

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.5 / development / D8D`

Design:

1. `bootstrap-vector.ps1` resolves a moving ref such as `main` to one exact 40-character Git commit before download.
2. The bootstrap downloads the archive by commit SHA, not by moving branch name.
3. The installed installer receives `source-lock.json` containing the resolved commit.
4. `build-release-package.ps1` requires an immutable source commit from `source-lock.json` or a real Git checkout.
5. The distribution package receives its own `source-lock.json` with `resolution = immutable-package-lock`.
6. When the packaged bootstrap is executed, it reads the package lock and downloads that exact commit without resolving `main` again.

Expected package behavior:

```text
Source       : Engenharia4BPS/HamRadio @ <40-char SHA>
Resolution   : package-lock
```

The same SHA must appear in:

```text
source-lock.json
package-manifest.json -> source_commit
PACKAGE-README.txt -> Source
bootstrap console output
```

Acceptance requires that package verification still returns `PACKAGE_VERIFY_OK` and that the packaged bootstrap reports `Resolution: package-lock` using the same commit SHA.
