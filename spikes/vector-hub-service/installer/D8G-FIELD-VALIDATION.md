# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.19 / development / D8G`

D8F is field-validated on the current station. The main GADX Vector Setup GUI exposes both Port Manager and Health Report. The read-only commissioning report ended with:

```text
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The current field machine is therefore a suitable baseline for the `CURRENT healthy` scenario of the release-candidate matrix.

---

## D8G objective

D8G proves that the productized installer/package can be repeated safely across the supported installation states before promoting the build to an actual `rc` channel.

The release candidate matrix is:

```text
1. CLEAN Windows 10/11
2. CURRENT healthy
3. CURRENT with payload drift
4. CURRENT broken/incomplete
5. LEGACY with GADXVectorBridge
6. runtime absent
7. runtime incomplete/version drift
8. reboot after COM changes
9. repeated repair / idempotence
10. induced failure + rollback
```

Additional compatibility observations required during D8G:

- Windows build/version and architecture;
- Secure Boot state where available;
- locked com0com 3.0.0.0 driver installation behavior;
- package/source lock identity;
- final D8F commissioning status;
- preservation of `vector.ini` and existing COM pairs where required;
- PTT safe state before declaring READY.

No build is promoted to `rc` until the matrix has sufficient real-machine/VM evidence.

---

## D8G.1 - Packaged CURRENT-healthy baseline

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.19 / development / D8G`
Date: 2026-09-07

The first D8G test intentionally used the already healthy field station and was non-destructive with respect to service, runtime, COMs, `vector.ini` and radio state.

The installed bootstrap refreshed to immutable source commit:

```text
532024deeb15196b88ca31d2f34c6d9475024d46
```

The package builder produced:

```text
C:\Ham\GADX-Vector\dist\GADX-Vector-0.8.0-dev.19.zip
ZIP SHA256: 3468d55192d3ea9f50d632ebbca182fd1a6ba3c37290462eff4a2d38c22022a1
Package files: 42
```

The extracted package verifier checked 41 manifest-tracked files and returned:

```text
PACKAGE_VERIFY_OK
```

The decisive packaged-bootstrap test was then run from the extracted ZIP without `-RefreshSource` and without `-Apply`. It reported:

```text
Source       : Engenharia4BPS/HamRadio @ 532024deeb15196b88ca31d2f34c6d9475024d46
Resolution   : package-lock
Mode         : PREVIEW
Release      : 0.8.0-dev.19 / development / D8G
Pinned commit: 532024deeb15196b88ca31d2f34c6d9475024d46
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

The package therefore proved both integrity and immutable source behavior while recognizing the current healthy installation correctly.

Result: **D8G.1 PACKAGED CURRENT-HEALTHY BASELINE VALIDATED IN FIELD.**

---

## D8G.2 - Packaged CURRENT payload-drift detection

Status: **IN FIELD VALIDATION**
Next release: `0.8.0-dev.20 / development / D8G`

Purpose: repeat the earlier D8C drift behavior using the D8G product generation and prove that a harmless installed auxiliary-file drift is detected as `CURRENT / REPAIR / Payload drift YES` without touching the running Hub.

The selected controlled drift target is:

```text
C:\Ham\GADX-Vector\tools\port_manager.py
```

This file is part of payload-drift detection but is not loaded by the running Hub service, making it suitable for a non-radio-impacting detector test when the Port Manager itself is closed.

Acceptance before any repair Apply:

```text
Detected     : CURRENT
Mode         : REPAIR
Payload drift: YES - installed files differ from current installer payload
```

Preview must also show the D7 safety gate for a future Apply while leaving the currently running Hub untouched during Preview.

After the detector/Preview evidence is captured, the exact packaged payload copy must be restored and the machine must return to:

```text
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

No `-Apply` repair is required for this detector-only D8G.2 test.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver test |
| CURRENT healthy | **Validated** | D8G.1 ZIP integrity + package-lock Preview on field station |
| CURRENT payload drift | In validation | D8G.2 controlled Port Manager payload drift |
| CURRENT broken/incomplete | Pending | Requires controlled test state |
| LEGACY GADXVectorBridge | Pending | Requires legacy fixture/VM |
| Runtime absent | Pending | Requires isolated/clean test root or VM |
| Runtime incomplete/version drift | Pending | Requires controlled fixture |
| Reboot after COM changes | Pending | Requires COM provisioning test |
| Repeated repair/idempotence | Pending | Requires D8G package repeat test |
| Induced failure + rollback | Pending | Requires controlled failure test |
