# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.28 / development / D8G`

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

No build is promoted to `rc` until the matrix has sufficient real-machine/VM evidence.

---

## D8G.1 - Packaged CURRENT healthy

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.19`

```text
ZIP SHA256: 3468d55192d3ea9f50d632ebbca182fd1a6ba3c37290462eff4a2d38c22022a1
PACKAGE_VERIFY_OK
Resolution   : package-lock
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

---

## D8G.2 - CURRENT payload drift

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.20`

A controlled drift in `tools\port_manager.py` was correctly detected as `CURRENT / REPAIR / Payload drift YES`. The exact original file was restored and final Preview returned `CURRENT / NONE / Payload drift NO`.

---

## D8G.3 - CURRENT broken/incomplete fixture

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.21`

```text
D8G_BROKEN_FIXTURE_DETECTED
D8G_BROKEN_PREVIEW_SAFE
```

The temporary fixture was detected `BROKEN / REPAIR`; the real station remained unchanged.

---

## D8G.4 - Runtime absent

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.22`

```text
LOCKED_PYTHON_PACKAGES_INSTALLED
PYWIN32_SERVICE_HOST_OK
RUNTIME_DEPENDENCY_LOCK_OK
COM0COM_DEPENDENCY_LOCK_OK
PRODUCTION_RUNTIME_IMPORTS_OK
PRODUCTION_RUNTIME_SERVICE_HOST_OK
PRODUCTION_RUNTIME_LOCK_TEST_OK
```

---

## D8G.5 - Runtime incomplete/version drift

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.23`

```text
D8G_RUNTIME_DRIFT_INTRODUCED pyserial=3.4
D8G_RUNTIME_DRIFT_DETECTED
D8G_RUNTIME_DRIFT_REPAIR_OK
D8G_RUNTIME_DRIFT_FIXTURE_SAFE
```

---

## D8G.6 - LEGACY migration Preview

Status: **VALIDATED IN FIELD FOR CONFIGURATION; REAL SERVICE HANDOFF STILL REQUIRES VM**
Release tested: `0.8.0-dev.24`

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

A controlled Port Manager drift triggered a real D7 repair. The first Apply encountered a live unsafe PTT state (`rigctld t = 1`) and correctly refused READY, preserved failed Hub evidence, restored backup state and left the Hub stopped/disabled. This is partial real-world evidence for rollback/fail-safe behavior.

A second Apply with PTT safe completed successfully:

```text
D7 REPAIR/UPDATE completed successfully.
vector.ini         : preserved (SHA256 unchanged)
com0com pairs      : unchanged
GADXVectorHub      : Running / delayed-auto
PTT safe state     : OFF
INSTALLATION STATUS: READY
```

Post-repair checks returned `CURRENT / NONE / Payload drift NO`, D8F READY, unchanged vector.ini SHA256, service `Running`, `Start=2`, `DelayedAutoStart=1`, and the original six com0com pairs.

---

## D8G.8 - Host inventory + post-reboot field validation

Status: **VALIDATED IN FIELD**
Releases observed: `0.8.0-dev.26` and `0.8.0-dev.27`
Date: 2026-09-07

The host inventory characterized the field machine as:

```text
Windows        : Microsoft Windows 10 Pro
Version        : 10.0.19045
Build          : 19045
Architecture   : 64 bits
PowerShell     : 5.1.19041.6456
Firmware       : BIOS
Secure Boot    : NOT APPLICABLE (legacy BIOS)
com0com setup  : C:\Program Files (x86)\com0com\setupc.exe
com0com lock   : 3.0.0.0
```

Before reboot, Windows reported:

```text
Reboot pending : True
reboot reason  : PendingFileRenameOperations (2 entries)
```

After a normal Windows reboot, production Setup immediately returned:

```text
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

The D8F commissioning report returned:

```text
Runtime        : OK - dependency lock
com0com        : OK - locked 3.0.0.0
Service        : Running / Auto
Hub process    : OK
Hub protocol   : OK
Rig poll hist  : OK - no errors in last 500 log lines
PTT safe state : OK - t -> 0
Reboot pending : False
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The six pre-existing com0com pairs survived reboot unchanged:

```text
COM9  <-> COM101
COM29 <-> COM102
COM15 <-> COM103
COM30 <-> COM104
COM31 <-> COM106
COM16 <-> COM105
```

Result: **POST-REBOOT FIELD STATE VALIDATED.**

---

## D8G.9 - Clean VM installation

Status: **PENDING**
Target release: `0.8.0-dev.28 / development / D8G`

The remaining high-value validation moves to a disposable clean Windows VM/machine. The clean test must begin without GADX Vector and without com0com installed, use the packaged bootstrap/source lock, and validate:

- CLEAN detection;
- locked Python 3.10.11 runtime creation;
- locked pyserial 3.5 / pywin32 312 installation;
- locked com0com 3.0.0.0 download/hash validation and driver installation;
- Port Manager COM provisioning;
- required reboot behavior after COM/driver changes;
- post-reboot detection and COM persistence;
- service installation/startup and final D8F commissioning where a suitable rigctld/radio test endpoint is available.

The same disposable VM should then be reused for the real legacy-service handoff and deliberate failure/rollback tests.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | D8G.9 clean VM/machine |
| CURRENT healthy | **Validated** | D8G.1 package integrity + package-lock Preview |
| CURRENT payload drift | **Validated** | D8G.2 controlled Port Manager drift + exact restore |
| CURRENT broken/incomplete | **Validated** | D8G.3 isolated production Preview fixture |
| LEGACY GADXVectorBridge | Partial | D8G.6 legacy config migration validated; real service handoff requires VM |
| Runtime absent | **Validated** | D8G.4 isolated production runtime creation |
| Runtime incomplete/version drift | **Validated** | D8G.5 isolated version-drift + production repair |
| Reboot after COM changes | **Field baseline validated** | D8G.8 existing six COM pairs + service/runtime survived reboot; clean provisioning reboot still belongs to D8G.9 |
| Repeated repair/idempotence | **Validated** | D8G.7 real repair, final no-op detection and preserved state |
| Induced failure + rollback | Partial evidence | D8G.7 real unsafe-PTT abort/rollback; deliberate controlled VM failure still pending |
