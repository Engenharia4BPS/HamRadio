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

Status: **RETEST PENDING AFTER CURRENT-STATE HEALTH FIX**
Current release: `0.8.0-dev.17 / development / D8F`
Date: 2026-09-07

A new read-only product report was added:

```text
installer/installation-report.ps1
```

The first field execution on `0.8.0-dev.16` correctly reported almost every current-state check as healthy:

```text
Detected       : CURRENT
Recommended    : NONE
Payload drift  : NO
Runtime        : OK - dependency lock
com0com        : OK - locked 3.0.0.0
vector.ini     : OK
Service        : Running / Auto
CAT ports      : COM101, COM103, COM105
Keying ports   : COM102, COM104, COM106
Radio keying   : COM22 @ 9600 PTT=RIGCTLD CW=RTS
rigctld        : 127.0.0.1:4532 OK
PTT safe state : OK - t -> 0
Reboot pending : False
```

But it ended with:

```text
Hub ready log  : FAIL
INSTALLATION STATUS : ATTENTION REQUIRED
```

The field investigation showed that this was a report-design problem, not evidence that the Hub process was down. The log file contained 32721 lines. `Vector Hub ready` existed at lines 11 and 3293, while the original D8F report searched only the last 200 lines.

The same log also showed a burst of transient rigctld poll errors ending at 17:21, followed by:

```text
INFO Connecting to rigctld at 127.0.0.1:4532
INFO Connected to rigctld
```

At report time, direct read-only probes were again healthy (`f` returned frequency and `t` returned `0`). Hamlib `RPRT -9` means the command was rejected by the rig; these historical errors remain useful diagnostics but are not by themselves proof that the currently running Hub is unhealthy after recovery.

### D8F.1.1 - Current-state health model

`0.8.0-dev.17` changes the report so final readiness no longer depends on an old startup marker remaining inside an arbitrary log tail.

The report now requires current evidence:

- `GADXVectorHub` service is Running;
- an actual `vector_hub.py` child process for this install root exists;
- default rigctld frequency query succeeds;
- the same Hamlib Extended Response protocol used by the Hub succeeds for `get_freq` and `get_mode`;
- PTT read-only query returns safe state `0`;
- runtime/com0com/config/source state remains healthy;
- no reboot is pending.

The historical `Vector Hub ready` marker is still reported as informational evidence, not as a hard gate. Recent `rigctld poll failed` lines are reported as `WARN` history when present. Current live probes decide readiness.

Expected field acceptance for `0.8.0-dev.17`:

```text
Hub process    : OK - PID ...
rigctld        : 127.0.0.1:4532 OK freq=...
Hub protocol   : OK freq=... mode=...
Hub ready mark : INFO - found in log history
Rig poll hist  : WARN ...   # allowed if current probes are healthy
PTT safe state : OK - t -> 0
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

No Apply parameter exists in this D8F report; it remains read-only by design.
