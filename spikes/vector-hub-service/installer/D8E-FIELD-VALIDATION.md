# GADX Vector - D8E field validation

## Baseline entering D8E

Date: 2026-09-07
Release baseline: `0.8.0-dev.13 / development / D8D.3B`

D8D distribution/dependency work is considered field-validated for the current machine.

The final production Preview reported:

```text
Dependency lock: Python 3.10.11 / pyserial 3.5 / pywin32 312 / com0com 3.0.0.0
Runtime      : OK - locked versions
Service host : OK
com0com      : OK - locked 3.0.0.0 (C:\Program Files (x86)\com0com\setupc.exe)
com0com setup: not required - installed files match dependency lock
PREVIEW ONLY - no changes were made.
COM0COM_DEPENDENCY_LOCK_OK
```

Together with the previous online distribution test:

```text
COM0COM_INSTALLED_LOCK_OK
COM0COM_DISTRIBUTION_LOCK_OK
COM0COM_LOCK_ONLINE_OK
```

this closes the D8D dependency-lock objective for Python, Python wheels and the selected com0com distribution on the current field baseline.

Clean-machine kernel-driver installation and Secure Boot compatibility remain intentionally deferred to the D8G release-candidate matrix.

Result: **D8D DISTRIBUTION/DEPENDENCY BASELINE VALIDATED IN FIELD.**

---

## D8E.1 - Product Port Manager entry point

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.14 / development / D8E`
Date: 2026-09-07

D8E integrates the already-existing Port Manager into the product workflow without rewriting its COM planning/apply logic.

The product launcher is:

```text
installer/launch-port-manager.ps1
```

The field execution reported:

```text
GADX Vector - Port Manager launcher
Install root : C:\Ham\GADX-Vector
Python       : C:\Ham\GADX-Vector\runtime\python.exe
Port Manager : C:\Ham\GADX-Vector\tools\port_manager.py
Config       : C:\Ham\GADX-Vector\config\vector.ini
PORT_MANAGER_LAUNCHED
```

The GUI opened normally as Administrator and loaded the field inventory. The operator did not press `Aplicar configuracao`, so no COM pair or `vector.ini` change was made during this validation.

Observed existing com0com pairs:

```text
COM9  <-> COM101
COM29 <-> COM102
COM15 <-> COM103
COM30 <-> COM104
COM31 <-> COM106
COM16 <-> COM105
```

Observed active physical ports included:

```text
COM20 - IC-7760 Serial Port A (CI-V)
COM22 - IC-7760 Serial Port B
```

Result: **D8E.1 PRODUCT PORT MANAGER ENTRY POINT VALIDATED IN FIELD.**

---

## D8E.2 - Port Manager button inside GADX Vector Setup

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.15 / development / D8E`

The main `setup-launcher.ps1` now includes a `Port Manager` button.

Behavior:

- the button is enabled only when the Vector private runtime is available and the product Port Manager launcher exists;
- the Port Manager opens in a separate process/window;
- opening the tool does not satisfy or bypass Setup Preview/Apply gating;
- while Setup is busy with Refresh/Preview/Apply, the Port Manager button is disabled;
- the existing D1-D7 backend and Apply safety rules are unchanged;
- no COM/config change occurs merely by opening Port Manager; changes still require explicit confirmation inside the tool.

Field acceptance:

1. `GADX Vector Setup` opens normally on Windows PowerShell 5.1.
2. Release shows `0.8.0-dev.15 / development / D8E`.
3. Healthy installation remains `CURRENT / NONE / Payload drift NO`.
4. `Port Manager` button is enabled.
5. Clicking `Port Manager` opens the already validated Port Manager GUI.
6. `Apply` remains disabled for the healthy `NONE` state.
7. Closing Port Manager does not affect the Hub/service/COM configuration.
