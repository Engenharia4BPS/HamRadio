# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.25 / development / D8G`

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

The installed bootstrap refreshed to immutable source commit `532024deeb15196b88ca31d2f34c6d9475024d46`. The package ZIP SHA256 was `3468d55192d3ea9f50d632ebbca182fd1a6ba3c37290462eff4a2d38c22022a1`, `PACKAGE_VERIFY_OK` passed, and the packaged bootstrap returned:

```text
Resolution   : package-lock
Release      : 0.8.0-dev.19 / development / D8G
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

A controlled drift in `tools\port_manager.py` was detected as:

```text
Detected     : CURRENT
Mode         : REPAIR
Payload drift: YES - installed files differ from current installer payload
```

The D7 safety gate was exposed before any possible Apply. No `-Apply` was used. The exact original file was restored, SHA256 matched the installer payload, and final Preview returned `CURRENT / NONE / Payload drift NO`.

Result: **D8G.2 CURRENT PAYLOAD-DRIFT DETECTION + SAFE RESTORE VALIDATED IN FIELD.**

---

## D8G.3 - CURRENT broken/incomplete Preview fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.21 / development / D8G`
Date: 2026-09-07

`verify-d8g-broken-preview.ps1` created a temporary install root containing only `app\vector_hub.py`. Production detection returned `BROKEN / REPAIR`; runtime and configuration were correctly reported missing. The real station remained `CURRENT / NONE`, service `Running`, and real `vector.ini` SHA256 unchanged.

```text
D8G_BROKEN_FIXTURE_DETECTED
D8G_BROKEN_PREVIEW_SAFE
```

Result: **D8G.3 CURRENT BROKEN/INCOMPLETE PREVIEW DETECTION VALIDATED IN FIELD.**

---

## D8G.4 - Runtime absent / isolated production creation

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.22 / development / D8G`
Date: 2026-09-07

`verify-production-runtime-lock.ps1` created a temporary Vector install root with no runtime and called production `ensure-runtime.ps1 -Apply` only against that temporary root. System com0com was already present and matched the lock.

```text
LOCKED_PYTHON_PACKAGES_INSTALLED
PYWIN32_SERVICE_HOST_OK
RUNTIME_DEPENDENCY_LOCK_OK
COM0COM_DEPENDENCY_LOCK_OK
PRODUCTION_RUNTIME_IMPORTS_OK
PRODUCTION_RUNTIME_SERVICE_HOST_OK
PRODUCTION_RUNTIME_LOCK_TEST_OK
```

Result: **D8G.4 RUNTIME-ABSENT PRODUCTION CREATION VALIDATED IN FIELD.**

---

## D8G.5 - Runtime version drift / production repair fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.23 / development / D8G`
Date: 2026-09-07

`verify-d8g-runtime-drift.ps1` created a healthy locked runtime in a temporary root, changed only temporary pyserial metadata from `3.5` to `3.4`, and proved production Preview rejected it as:

```text
Runtime      : INCOMPLETE OR VERSION DRIFT
```

Production `ensure-runtime.ps1 -Apply` then rebuilt the temporary private runtime from exact locked dependencies and restored pyserial `3.5`, pywin32 `312`, tkinter and the pywin32 service host.

```text
D8G_RUNTIME_DRIFT_INTRODUCED pyserial=3.4
D8G_RUNTIME_DRIFT_DETECTED
D8G_RUNTIME_DRIFT_REPAIR_OK
D8G_RUNTIME_DRIFT_FIXTURE_SAFE
```

The real installation remained `CURRENT / NONE`, service `Running`, with real `vector.ini` SHA256 unchanged.

Result: **D8G.5 RUNTIME VERSION-DRIFT DETECTION + PRODUCTION REPAIR VALIDATED IN FIELD.**

---

## D8G.6 - LEGACY configuration migration Preview fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.24 / development / D8G`
Date: 2026-09-07

`verify-d8g-legacy-preview.ps1` created a temporary representative `config\bridge_multi.ini`, then ran production detection, the production migration planner and full production Setup Preview against that temporary root.

Production detection returned:

```text
Detected    : LEGACY
Recommended : MIGRATE_REPAIR
D8G_LEGACY_FIXTURE_DETECTED
```

The migration plan preserved the representative legacy settings:

```text
CAT          : COM9, COM15
Keying       : 2 clients
Radio keying : COM22 PTT=RIGCTLD CW=RTS
rigctld      : 127.0.0.1:4532
com0com      : preserve existing pairs
D8G_LEGACY_PLAN_OK
```

Full Setup Preview remained non-destructive and described the transactional `GADXVectorBridge -> GADXVectorHub` handoff without creating `vector.ini` or touching the real station. Final real-state verification returned:

```text
Detected      : CURRENT
Recommended   : NONE
Payload drift : NO
Service       : Running
vector.ini    : SHA256 unchanged

D8G_LEGACY_PREVIEW_SAFE
```

This validates legacy-file detection and migration planning on the field machine. Actual legacy Windows-service replacement remains reserved for a clean VM/machine before RC promotion.

Result: **D8G.6 LEGACY CONFIGURATION MIGRATION PREVIEW VALIDATED IN FIELD.**

---

## D8G.7 - Repeated repair / idempotence on field station

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.25 / development / D8G`

This scenario intentionally exercises one real D7 repair transaction on the already validated field station, followed by a second detection pass proving the repaired state is idempotent.

The controlled drift target remains:

```text
C:\Ham\GADX-Vector\tools\port_manager.py
```

It is suitable because the running Hub does not load this file. Before Apply, the station must be in RX, rigctld PTT must read `0`, and the RF amplifier should be disabled/off as an additional physical precaution.

Expected sequence:

1. refresh to exact `0.8.0-dev.25` installer source;
2. save SHA256 of `vector.ini` and inventory of existing com0com pairs;
3. introduce harmless payload drift only in `tools\port_manager.py`;
4. require Preview `CURRENT / REPAIR / Payload drift YES` and the D7 safety gate;
5. run production `setup-vector.ps1 -Apply` while radio is in RX and amplifier is disabled;
6. require D7 transaction success, preserved `vector.ini`, unchanged com0com pairs, `GADXVectorHub Running / delayed-auto`, and PTT safe state OFF;
7. run Setup again and require `CURRENT / NONE / Payload drift NO`;
8. run D8F Health Report and require `INSTALLATION STATUS : READY`;
9. compare `vector.ini` SHA256 and com0com pair inventory with pre-test snapshots.

This scenario proves that a real repair returns the installation to a stable state where repeating Setup becomes a no-op rather than triggering another repair.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver test |
| CURRENT healthy | **Validated** | D8G.1 ZIP integrity + package-lock Preview on field station |
| CURRENT payload drift | **Validated** | D8G.2 controlled Port Manager drift + exact restore |
| CURRENT broken/incomplete | **Validated** | D8G.3 isolated production Preview fixture |
| LEGACY GADXVectorBridge | Partial | D8G.6 legacy INI migration Preview validated; real service handoff still requires VM |
| Runtime absent | **Validated** | D8G.4 isolated production runtime creation |
| Runtime incomplete/version drift | **Validated** | D8G.5 isolated pyserial version-drift + production repair fixture |
| Reboot after COM changes | Pending | Requires COM provisioning test |
| Repeated repair/idempotence | In validation | D8G.7 real controlled repair on field station |
| Induced failure + rollback | Pending | Requires controlled failure test |
