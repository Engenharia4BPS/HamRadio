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

Status: **VALIDATED IN FIELD**
Release tested: `0.8.0-dev.17 / development / D8F`
Date: 2026-09-07

The read-only product report is:

```text
installer/installation-report.ps1
```

The first field execution on `0.8.0-dev.16` correctly reported almost every current-state check as healthy, but ended with `Hub ready log : FAIL` because the report searched only the last 200 lines of a 32721-line log. `Vector Hub ready` existed at lines 11 and 3293, so this was a report-design false negative rather than evidence that the current Hub was down.

The field investigation also found a burst of historical rigctld poll errors with `RPRT -9`, followed by a successful reconnect. Current read-only `f` and `t` probes were healthy.

### D8F.1.1 - Current-state health model

`0.8.0-dev.17` changed final readiness to current evidence instead of an arbitrary log-tail marker. The report now requires:

- `GADXVectorHub` service Running;
- an actual `vector_hub.py` child process for this install root;
- current rigctld frequency query success;
- successful Hamlib Extended Response `get_freq` and `get_mode` probes matching the Hub protocol;
- PTT read-only query returning safe state `0`;
- locked runtime/com0com/config/source state healthy;
- no reboot pending.

Historical `Vector Hub ready` remains informational. Recent `rigctld poll failed` lines are reported as diagnostic `WARN`, but current live probes decide readiness.

The field retest passed with:

```text
Release        : 0.8.0-dev.17 / development / D8F
Detected       : CURRENT
Recommended    : NONE
Payload drift  : NO
Runtime        : OK - dependency lock
com0com        : OK - locked 3.0.0.0
vector.ini     : OK
Service        : Running / Auto
Hub process    : OK - PID 2464
CAT ports      : COM101, COM103, COM105
Keying ports   : COM102, COM104, COM106
Radio keying   : COM22 @ 9600 PTT=RIGCTLD CW=RTS
rigctld        : 127.0.0.1:4532 OK freq=10131000
Hub protocol   : OK freq=10131000 mode=PKTUSB
Hub ready mark : INFO - found in log history
Rig poll hist  : WARN - 498 errors in last 500 log lines; current probes decide readiness
PTT safe state : OK - t -> 0
Latest backup  : C:\Ham\GADX-Vector\backups\repair-20260906-215831
Reboot pending : False

INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The historical warning did not block readiness because current process/protocol/PTT probes were healthy.

Result: **D8F.1 READ-ONLY CURRENT-STATE COMMISSIONING REPORT VALIDATED IN FIELD.**

---

## D8F.2 - Health Report integrated into GADX Vector Setup

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.18 / development / D8F`

The main `setup-launcher.ps1` now exposes the validated commissioning report through a `Health Report` button.

Behavior:

- the button is enabled after the Setup state is loaded and `installation-report.ps1` is present;
- clicking it runs the same read-only D8F report and displays the full output inside the existing log area;
- `INSTALLATION STATUS : READY` maps to a `Health report: INSTALLATION STATUS READY.` status-bar message;
- `ATTENTION REQUIRED` is displayed without changing service, COMs, radio or configuration;
- running the health report does not satisfy or bypass Preview/Apply gating;
- the Port Manager button remains separate;
- the existing D1-D7 backend remains unchanged.

Field acceptance for D8F.2:

```text
Release        0.8.0-dev.18 / development / D8F
Detected       CURRENT
Recommended    NONE
Payload drift  NO
```

The main button row should contain:

```text
Health Report | Port Manager | Refresh | Run Preview | Apply | Close
```

For the current healthy station, clicking `Health Report` should show the validated D8F report inside the Setup window and end with:

```text
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

`Apply` must remain disabled for `Recommended: NONE`.
