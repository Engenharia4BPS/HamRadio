# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.26 / development / D8G`

D8F is field-validated on the current station. The main GADX Vector Setup GUI exposes Port Manager and Health Report, and the read-only commissioning report reaches:

```text
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

D8G proves that the productized installer/package can be repeated safely across supported installation states before promotion to an actual `rc` channel.

## Release-candidate matrix

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

Compatibility observations required during D8G include Windows build/architecture, firmware/Secure Boot where available, locked com0com behavior, immutable package/source identity, final D8F commissioning status, `vector.ini` preservation, COM-pair preservation and PTT safe state before READY.

No build is promoted to `rc` until the matrix has sufficient real-machine/VM evidence.

---

## D8G.1 - Packaged CURRENT healthy

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.19`

The package was built from immutable source commit `532024deeb15196b88ca31d2f34c6d9475024d46`.

```text
ZIP SHA256: 3468d55192d3ea9f50d632ebbca182fd1a6ba3c37290462eff4a2d38c22022a1
PACKAGE_VERIFY_OK
Resolution   : package-lock
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

Result: **VALIDATED.**

---

## D8G.2 - CURRENT payload drift

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.20`

A controlled drift in `tools\port_manager.py` was correctly detected as:

```text
Detected     : CURRENT
Mode         : REPAIR
Payload drift: YES - installed files differ from current installer payload
```

The D7 safety gate was exposed before any Apply. No repair was executed in this detector-only test. The exact original file was restored, SHA256 matched the installer payload, and final Preview returned `CURRENT / NONE / Payload drift NO`.

Result: **VALIDATED.**

---

## D8G.3 - CURRENT broken/incomplete fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.21`

`verify-d8g-broken-preview.ps1` created a temporary incomplete install root. Production detection returned `BROKEN / REPAIR`; runtime and configuration were correctly reported missing. The real station remained `CURRENT / NONE`, service `Running`, and real `vector.ini` SHA256 unchanged.

```text
D8G_BROKEN_FIXTURE_DETECTED
D8G_BROKEN_PREVIEW_SAFE
```

Result: **VALIDATED.**

---

## D8G.4 - Runtime absent

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.22`

`verify-production-runtime-lock.ps1` created a temporary install root with no runtime and exercised production `ensure-runtime.ps1 -Apply` only against that temporary root.

```text
LOCKED_PYTHON_PACKAGES_INSTALLED
PYWIN32_SERVICE_HOST_OK
RUNTIME_DEPENDENCY_LOCK_OK
COM0COM_DEPENDENCY_LOCK_OK
PRODUCTION_RUNTIME_IMPORTS_OK
PRODUCTION_RUNTIME_SERVICE_HOST_OK
PRODUCTION_RUNTIME_LOCK_TEST_OK
```

Result: **VALIDATED.**

---

## D8G.5 - Runtime incomplete/version drift

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.23`

`verify-d8g-runtime-drift.ps1` changed only temporary pyserial metadata from `3.5` to `3.4`. Production Preview rejected the runtime as `INCOMPLETE OR VERSION DRIFT`; production Apply rebuilt the temporary runtime from exact locked dependencies.

```text
D8G_RUNTIME_DRIFT_INTRODUCED pyserial=3.4
D8G_RUNTIME_DRIFT_DETECTED
D8G_RUNTIME_DRIFT_REPAIR_OK
D8G_RUNTIME_DRIFT_FIXTURE_SAFE
```

Result: **VALIDATED.**

---

## D8G.6 - LEGACY migration Preview

Status: **VALIDATED IN FIELD FOR CONFIGURATION; REAL SERVICE HANDOFF STILL REQUIRES VM**
Release tested: `0.8.0-dev.24`

`verify-d8g-legacy-preview.ps1` created a representative temporary `bridge_multi.ini`. Production detection returned `LEGACY / MIGRATE_REPAIR`; the migration plan preserved representative CAT, keying, radio keying, rigctld and com0com state.

```text
D8G_LEGACY_FIXTURE_DETECTED
D8G_LEGACY_PLAN_OK
D8G_LEGACY_PREVIEW_SAFE
```

Actual `GADXVectorBridge -> GADXVectorHub` Windows-service handoff remains reserved for a clean VM/machine.

---

## D8G.7 - Real repair / idempotence

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.25`
Date: 2026-09-07

The station started healthy with D8F reporting PTT safe state `t -> 0`. A controlled drift was introduced only in `tools\port_manager.py`; Preview returned `CURRENT / REPAIR / Payload drift YES` and exposed the D7 safety gate.

### First real Apply - fail-safe path observed

The first real D7 Apply quiesced the service, validated locked runtime/com0com, deployed current payload, preserved `vector.ini`, installed and started the new Hub, then refused READY because the final live PTT check returned:

```text
PTT safety validation failed: rigctld t returned '1' instead of 0.
```

The transaction then executed its safety path:

```text
Preserving failed Hub evidence, restoring backed-up application files and leaving the Hub stopped/disabled for safety...
Failed Hub log preserved at:
C:\Ham\GADX-Vector\backups\repair-20260907-201211\logs\failed-vector-hub.log
```

This is real field evidence that a non-safe PTT state prevents READY and triggers rollback/safe shutdown. The condition was not deliberately induced, so it counts as **partial evidence** for the matrix item `induced failure + rollback`, not full validation of that scenario.

### Second real Apply - successful repair

A second Apply, with PTT safe, completed:

```text
D7 REPAIR/UPDATE completed successfully.
Backup             : C:\Ham\GADX-Vector\backups\repair-20260907-201230
vector.ini         : preserved (SHA256 unchanged)
com0com pairs      : unchanged
GADXVectorHub      : Running / delayed-auto
PTT safe state     : OFF
INSTALLATION STATUS: READY
```

Post-repair idempotence checks returned:

```text
Detected     : CURRENT
Mode         : NONE
Payload drift: NO

INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The final Health Report also showed:

```text
Runtime        : OK - dependency lock
com0com        : OK - locked 3.0.0.0
Service        : Running / Auto
Hub process    : OK
Hub protocol   : OK
Rig poll hist  : OK - no errors in last 500 log lines
PTT safe state : OK - t -> 0
Reboot pending : False
```

`vector.ini` preservation was proven with the same SHA256 before, after and in the successful repair backup:

```text
1F43E2FBA13E418C81FB86D5B0978FAA222007BD1075D2A4811EE781214D5BF8
Before match : True
Backup match : True
```

Windows service state was:

```text
GADXVectorHub Running
Start            : 2
DelayedAutoStart : 1
```

The existing six com0com pairs remained unchanged:

```text
COM9  <-> COM101
COM29 <-> COM102
COM15 <-> COM103
COM30 <-> COM104
COM31 <-> COM106
COM16 <-> COM105
```

Result: **D8G.7 REAL REPAIR + IDEMPOTENCE VALIDATED IN FIELD.**

---

## D8G.8 - Host compatibility inventory

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.26 / development / D8G`

A new read-only inventory script is provided:

```text
installer/inspect-d8g-host.ps1
```

It records Windows caption/version/build, architecture, PowerShell version, firmware mode, Secure Boot state where queryable, reboot-pending state and detected com0com path/version. It performs no install, service or COM changes.

Expected terminal marker:

```text
D8G_HOST_COMPATIBILITY_INVENTORY_OK
```

This information will be used to characterize the current field machine before the remaining clean-VM tests.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver installation |
| CURRENT healthy | **Validated** | D8G.1 package integrity + package-lock Preview |
| CURRENT payload drift | **Validated** | D8G.2 controlled Port Manager drift + exact restore |
| CURRENT broken/incomplete | **Validated** | D8G.3 isolated production Preview fixture |
| LEGACY GADXVectorBridge | Partial | D8G.6 legacy config migration validated; real service handoff requires VM |
| Runtime absent | **Validated** | D8G.4 isolated production runtime creation |
| Runtime incomplete/version drift | **Validated** | D8G.5 isolated version-drift + production repair |
| Reboot after COM changes | Pending | Requires clean COM provisioning/reboot test |
| Repeated repair/idempotence | **Validated** | D8G.7 real repair, final no-op detection and preserved state |
| Induced failure + rollback | Partial evidence | D8G.7 first Apply hit real PTT unsafe condition and executed rollback/safe shutdown; deliberate controlled failure still pending |
