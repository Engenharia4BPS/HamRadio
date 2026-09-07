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

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.14 / development / D8E`

D8E integrates the already-existing Port Manager into the product workflow without rewriting its COM planning/apply logic.

The first small step adds:

```text
installer/launch-port-manager.ps1
```

The launcher:

- accepts the Vector install root;
- elevates with UAC when needed;
- requires the private Vector Python runtime;
- requires the deployed `tools\port_manager.py`;
- requires the existing `config\vector.ini`;
- launches the Port Manager with the private runtime;
- does not create/remove/rename any COM pair itself;
- leaves all actual COM/config changes behind the Port Manager's existing explicit `Aplicar configuracao` confirmation.

Field acceptance for D8E.1:

```text
PORT_MANAGER_LAUNCHED
```

Then visually confirm that the Port Manager opens, inventory loads and the current configuration can be viewed. Do not press `Aplicar configuracao` during this first integration test.

Only after this entry point is field-validated will it be exposed as a button inside the main GADX Vector Setup GUI.
