# GADX Vector - D8D.3B com0com lock

Status: **FIELD INVENTORY VALIDATED; DISTRIBUTION LOCK VALIDATION OPEN**
Release: `0.8.0-dev.11 / development / D8D.3B`
Date: 2026-09-07

## Field inventory

The read-only collector completed with:

```text
setupc        : C:\Program Files (x86)\com0com\setupc.exe
registry rows : 1
driver rows   : 18
binary files  : 5
installer file: 0 candidate(s)
COM0COM_INVENTORY_OK
```

Installed product metadata identifies com0com `3.0.0.0`, publisher `Vyacheslav Frolov`.

The installed binaries are:

```text
com0com.sys  90544   3ea9374e0da84ac3baba16cfd1b2cb8e1b7c18e8495ad6757e16010a85ea6c2e
setup.dll    73136   eaf2da64a93bb65bf27f8c1bcf4d5dd7f0aaaea4e64373dac248146e2912ac02
setupc.exe   17328   cf007dd1154b1b0e1190dad7840b448d1cfae2abbdd2a80cb8ee3c700cfd42d3
setupg.exe   160176  34facf876f11d1064e55a158c17057860a6a46ffbdd6375879df87687f99f684
uninstall.exe 66650  06005aae7596e07d2dfb11d06705acad59f39979833ea27e920638916a513c81
```

The first four field files report valid Authenticode signatures from CyberCircuits; `uninstall.exe` is not signed. `Win32_PnPSignedDriver` reported the currently enumerated com0com device rows as `IsSigned=false`, so GADX Vector does not equate file Authenticode state with modern Windows kernel/Secure-Boot acceptance.

## Pinned distribution

The selected field baseline is:

```text
Setup_com0com_v3.0.0.0_W7_x64_signed.exe
size   : 261544
sha256 : 26486b28604b49a9008c54feb11b9ece0008a8287ee5caf0bcf2a62f4317128f
source : SourceForge signed-drivers/com0com/v3.0
```

`dependency-lock.json` now pins that exact distribution and the five installed-file fingerprints above.

A read-only verifier was added:

```text
verify-com0com-lock.ps1
```

Default mode checks the installed file fingerprints only. `-Online` additionally downloads the pinned installer to a temporary directory, verifies exact size + SHA256, and deletes it. It never executes the installer and never changes COM pairs.

Expected acceptance:

```text
COM0COM_INSTALLED_LOCK_OK
COM0COM_LOCK_STRUCTURE_OK
```

and with `-Online`:

```text
COM0COM_INSTALLED_LOCK_OK
COM0COM_DISTRIBUTION_LOCK_OK
COM0COM_LOCK_ONLINE_OK
```

## Compatibility guard

The selected package is kept as the reproducible field baseline, not as proof of universal Windows 10/11 Secure Boot compatibility. Modern driver-signing/Secure-Boot behavior must be validated separately in the D8G release-candidate matrix. Production metadata must not infer kernel-driver acceptance from Authenticode file signatures alone.
