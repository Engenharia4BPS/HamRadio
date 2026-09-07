# GADX Vector — D8C Field Validation

Date: 2026-09-06
Release under test: `0.8.0-dev.3 / development / D8C`

## Scope

Validate the real GUI-driven CURRENT/REPAIR flow while preserving the D1-D7 backend as the only authority for detection, Preview, Apply, safety gate, backup, rollback and final health validation.

## Healthy-state baseline

The production launcher correctly reported a healthy current installation as:

```text
Detected       CURRENT
Recommended    NONE
Payload drift  NO
Service        Running
Runtime        OK
com0com        OK
Safety         No changes required
```

`Run Preview` stayed read-only and `Apply` remained disabled.

## Controlled REPAIR trigger

A harmless payload drift was introduced only in `tools/port_manager.py`, which is not used by the running Hub service. The production launcher correctly changed to:

```text
Detected       CURRENT
Recommended    REPAIR
Payload drift  YES
Service        Running
Runtime        OK
com0com        OK
Safety         Hub will be Disabled / Stopped before Apply
```

Before Preview, `Apply REPAIR` remained disabled.

## Real Preview through GUI

`Run Preview` executed the real D1-D7 backend and showed the D7 safety plan, including:

```text
GADXVectorHub will be Disabled and forced Stopped before runtime/update work
vector.ini will be preserved
virtual COM pairs will be preserved
backup will be created before payload replacement
service health and PTT=OFF are required before READY
```

After a successful Preview, `Apply REPAIR` became enabled.

## First Apply: safe abort

The first real GUI-driven Apply aborted safely during final safety validation. The transaction created backup:

```text
C:\Ham\GADX-Vector\backups\repair-20260906-215011
```

The rollback left:

```text
GADXVectorHub  Stopped
StartMode      Disabled
```

The failed Hub log was preserved at:

```text
C:\Ham\GADX-Vector\backups\repair-20260906-215011\logs\failed-vector-hub.log
```

The preserved log showed that the new Hub itself had reached `Vector Hub ready`, opened all configured CAT/keying ports and connected to rigctld. The likely reason for the abort was that the station was transmitting during the final PTT safety check. This is expected protective behavior: D7 requires rigctld PTT state `0` before declaring READY.

## Second Apply: success in RX

The test was repeated with the radio in RX and no PTT/CW activity during commissioning.

The backend completed successfully and the GUI refreshed automatically to:

```text
Detected       CURRENT
Recommended    NONE
Payload drift  NO
Service        Running
Runtime        OK
com0com        OK
Safety         No changes required
```

The GUI displayed the successful backend completion message, and `Apply` returned to disabled state because no further action was required.

## D8C conclusions

Validated in the field:

- production GUI reflects the real detector/backend state;
- CURRENT/NONE healthy state;
- controlled CURRENT/REPAIR detection from payload drift;
- Preview required before Apply;
- Apply remains disabled until Preview succeeds;
- explicit confirmation dialog before Apply;
- D7 safety gate invoked from GUI;
- safe abort and rollback when final PTT safety condition is not satisfied;
- failed Hub evidence preserved;
- successful retry when station is in RX;
- payload drift repaired;
- final automatic refresh to CURRENT/NONE/NO;
- service returned Running;
- no `vector.ini` rewrite;
- no virtual COM renumbering.

**D8C status: VALIDATED END-TO-END IN THE FIELD.**

Next phase: **D8D — distribution and dependency packaging**.
