# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.24 / development / D8G`

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

Decisive markers:

```text
D8G_RUNTIME_DRIFT_INTRODUCED pyserial=3.4
D8G_RUNTIME_DRIFT_DETECTED
D8G_RUNTIME_DRIFT_REPAIR_OK
D8G_RUNTIME_DRIFT_FIXTURE_SAFE
```

After the fixture test, the real installation remained:

```text
Detected      : CURRENT
Recommended   : NONE
Service       : Running
vector.ini    : SHA256 unchanged
```

Result: **D8G.5 RUNTIME VERSION-DRIFT DETECTION + PRODUCTION REPAIR VALIDATED IN FIELD.**

---

## D8G.6 - LEGACY configuration migration Preview fixture

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.24 / development / D8G`

A new isolated harness is provided:

```text
installer/verify-d8g-legacy-preview.ps1
```

It creates a temporary legacy `config\bridge_multi.ini` containing representative CAT, keying, physical keying and rigctld settings. It then:

1. requires production detection to classify the temporary root as `LEGACY` and require migration;
2. runs the production legacy migration planner and requires preservation of CAT ports, keying clients, radio keying, rigctld settings and existing com0com pairs;
3. runs the full production `setup-vector.ps1` in Preview mode against the temporary legacy root;
4. requires the legacy INI to remain unchanged and requires Preview not to create `vector.ini`;
5. rechecks the real detector state, real Hub service status and real `vector.ini` SHA256 and requires them to remain unchanged.

Expected decisive markers:

```text
D8G_LEGACY_FIXTURE_DETECTED
D8G_LEGACY_PLAN_OK
D8G_LEGACY_PREVIEW_SAFE
```

This fixture validates legacy-file detection and migration planning safely on the current field machine. It does **not** create a real `GADXVectorBridge` Windows service; actual legacy-service handoff remains a clean VM/machine test before RC promotion.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver test |
| CURRENT healthy | **Validated** | D8G.1 ZIP integrity + package-lock Preview on field station |
| CURRENT payload drift | **Validated** | D8G.2 controlled Port Manager drift + exact restore |
| CURRENT broken/incomplete | **Validated** | D8G.3 isolated production Preview fixture |
| LEGACY GADXVectorBridge | In validation | D8G.6 legacy INI migration Preview fixture; real service handoff still requires VM |
| Runtime absent | **Validated** | D8G.4 isolated production runtime creation |
| Runtime incomplete/version drift | **Validated** | D8G.5 isolated pyserial version-drift + production repair fixture |
| Reboot after COM changes | Pending | Requires COM provisioning test |
| Repeated repair/idempotence | Pending | Requires D8G package repeat test |
| Induced failure + rollback | Pending | Requires controlled failure test |
