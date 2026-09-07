# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.23 / development / D8G`

D8F is field-validated on the current station. The main GADX Vector Setup GUI exposes both Port Manager and Health Report. The read-only commissioning report ended with:

```text
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The current field machine is therefore a suitable baseline for the release-candidate matrix.

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

The packaged bootstrap was then run without `-RefreshSource` and without `-Apply` and reported:

```text
Resolution   : package-lock
Release      : 0.8.0-dev.19 / development / D8G
Pinned commit: 532024deeb15196b88ca31d2f34c6d9475024d46
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

Result: **D8G.1 PACKAGED CURRENT-HEALTHY BASELINE VALIDATED IN FIELD.**

---

## D8G.2 - CURRENT payload-drift detection

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.20 / development / D8G`
Date: 2026-09-07

A controlled drift was introduced only in:

```text
C:\Ham\GADX-Vector\tools\port_manager.py
```

Production Preview correctly reported:

```text
Detected     : CURRENT
Mode         : REPAIR
Payload drift: YES - installed files differ from current installer payload
```

The D7 safety gate was exposed before any possible Apply:

```text
On Apply, GADXVectorHub will be set Disabled and forced Stopped BEFORE runtime/download/update work.
Current service status: Running
```

No `-Apply` was used. The exact original `port_manager.py` was restored from the pre-test backup. SHA256 comparison against the current installer payload returned identical hashes:

```text
Installed : D4374055DA7E56D7219A74875FE7E44F20D684C2769E30EDC27FE14A7E9647CE
Payload   : D4374055DA7E56D7219A74875FE7E44F20D684C2769E30EDC27FE14A7E9647CE
Match     : True
```

A final production Preview returned:

```text
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

Result: **D8G.2 CURRENT PAYLOAD-DRIFT DETECTION + SAFE RESTORE VALIDATED IN FIELD.**

---

## D8G.3 - CURRENT broken/incomplete Preview fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.21 / development / D8G`
Date: 2026-09-07

The isolated harness:

```text
installer/verify-d8g-broken-preview.ps1
```

created a temporary install root containing only `app\vector_hub.py`. Service/config/tools/runtime were intentionally absent. Production detection correctly reported:

```text
Detected     : BROKEN
Mode         : REPAIR
PREVIEW ONLY - orchestrator will not modify the machine.
```

The runtime preview detected the temporary runtime as missing and the service transaction identified the missing configuration. After the fixture Preview, the real installation remained unchanged:

```text
Detected      : CURRENT
Recommended   : NONE
Payload drift : NO
Service       : Running
vector.ini    : SHA256 unchanged

D8G_BROKEN_FIXTURE_DETECTED
D8G_BROKEN_PREVIEW_SAFE
```

Result: **D8G.3 CURRENT BROKEN/INCOMPLETE PREVIEW DETECTION VALIDATED IN FIELD.**

---

## D8G.4 - Runtime absent / isolated production creation

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.22 / development / D8G`
Date: 2026-09-07

The production-facing harness:

```text
installer/verify-production-runtime-lock.ps1
```

created a temporary Vector install root with no runtime and called the real production `ensure-runtime.ps1 -Apply` only against that temporary root. System com0com was already present and matched the lock, so no virtual serial driver or COM pair was changed.

The fixture started as:

```text
Runtime      : MISSING
Service host : pending runtime creation
com0com      : OK - locked 3.0.0.0
```

Production runtime creation then used exact locked Python 3.10.11 and verified wheels. The decisive output was:

```text
LOCKED_PYTHON_PACKAGES_INSTALLED
PYWIN32_SERVICE_HOST_OK
RUNTIME_DEPENDENCY_LOCK_OK
COM0COM_DEPENDENCY_LOCK_OK
PRODUCTION_RUNTIME_IMPORTS_OK
PRODUCTION_RUNTIME_SERVICE_HOST_OK
PRODUCTION_RUNTIME_LOCK_TEST_OK
```

Warnings about the temporary `runtime\Scripts` directory not being on PATH were expected and do not affect Vector, which invokes its private Python explicitly.

Result: **D8G.4 RUNTIME-ABSENT PRODUCTION CREATION VALIDATED IN FIELD.**

---

## D8G.5 - Runtime version drift / production repair fixture

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.23 / development / D8G`

A new isolated harness is provided:

```text
installer/verify-d8g-runtime-drift.ps1
```

The harness never alters the real Vector runtime. It:

1. creates a healthy locked runtime inside a temporary install root using production `ensure-runtime.ps1 -Apply`;
2. introduces controlled version drift only in the temporary pyserial package metadata (`3.5` -> `3.4`);
3. proves the temporary Python now reports pyserial `3.4`;
4. runs production `ensure-runtime.ps1` in Preview and requires it not to accept the drifted runtime as `OK - locked versions`;
5. proves Preview did not repair or modify the fixture;
6. runs production `ensure-runtime.ps1 -Apply` against the temporary fixture;
7. requires exact Python `3.10.11`, pyserial `3.5`, pywin32 `312`, tkinter and the pywin32 service host after repair;
8. rechecks the real detector state, real Hub service status and real `vector.ini` SHA256 and requires them to be unchanged.

Expected decisive markers:

```text
D8G_RUNTIME_DRIFT_INTRODUCED pyserial=3.4
D8G_RUNTIME_DRIFT_DETECTED
D8G_RUNTIME_DRIFT_REPAIR_OK
D8G_RUNTIME_DRIFT_FIXTURE_SAFE
```

No real service, configuration, COM pair, runtime or radio state may change during this fixture test.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver test |
| CURRENT healthy | **Validated** | D8G.1 ZIP integrity + package-lock Preview on field station |
| CURRENT payload drift | **Validated** | D8G.2 controlled Port Manager drift + exact restore |
| CURRENT broken/incomplete | **Validated** | D8G.3 isolated production Preview fixture |
| LEGACY GADXVectorBridge | Pending | Requires legacy fixture/VM |
| Runtime absent | **Validated** | D8G.4 isolated production runtime creation |
| Runtime incomplete/version drift | In validation | D8G.5 isolated pyserial version-drift + production repair fixture |
| Reboot after COM changes | Pending | Requires COM provisioning test |
| Repeated repair/idempotence | Pending | Requires D8G package repeat test |
| Induced failure + rollback | Pending | Requires controlled failure test |
