# GADX Vector - D8F field validation

## Baseline entering D8F

Date: 2026-09-07
Release baseline: `0.8.0-dev.15 / development / D8E`

D8E is field-validated on the current machine. The main GADX Vector Setup GUI remained healthy at:

```text
Release        0.8.0-dev.15 / development / D8E
Detected       CURRENT
Recommended    NONE
Payload drift  NO
Service        Running
Runtime        OK
com0com        OK
Safety         No changes required
```

The integrated `Port Manager` button opened the already validated Port Manager in a separate window and did not alter Preview/Apply gating.

Result: **D8E PORT MANAGER PRODUCT INTEGRATION VALIDATED IN FIELD.**

---

## D8F.1 - Read-only commissioning report

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.16 / development / D8F`

A new read-only product report was added:

```text
installer/installation-report.ps1
```

The report consolidates the existing product state into one final health summary without changing service, COM or radio configuration.

It reports:

- product/release identity;
- detector classification and recommended mode;
- payload drift;
- exact locked runtime health;
- exact locked com0com health;
- `vector.ini` presence;
- GADXVectorHub status/start mode;
- CAT ports;
- keying ports/clients;
- physical radio keying configuration;
- rigctld reachability/frequency response;
- Hub-ready log evidence;
- PTT safe state via read-only rigctld `t` query when PTT is controlled by rigctld;
- latest backup path;
- reboot-pending state;
- final `INSTALLATION STATUS`.

The report supports human-readable output and `-AsJson` for later GUI integration.

For the current field baseline, acceptance is:

```text
Detected       : CURRENT
Recommended    : NONE
Payload drift  : NO
Runtime        : OK - dependency lock
com0com        : OK - locked 3.0.0.0
vector.ini     : OK
Service        : Running
Hub ready log  : OK
PTT safe state : OK - t -> 0
Reboot pending : False
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

No Apply parameter exists in this D8F.1 report; it is read-only by design.
