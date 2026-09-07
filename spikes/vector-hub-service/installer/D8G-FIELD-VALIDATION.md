# GADX Vector - D8G release-candidate field validation

## Baseline entering D8G

Date: 2026-09-07
Release baseline: `0.8.0-dev.18 / development / D8F`
Current D8G release: `0.8.0-dev.19 / development / D8G`

D8F is field-validated on the current station. The main GADX Vector Setup GUI exposes both Port Manager and Health Report. The read-only commissioning report ended with:

```text
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

The current field machine is therefore a suitable baseline for the `CURRENT healthy` scenario of the release-candidate matrix.

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

Status: **IN FIELD VALIDATION**
Release: `0.8.0-dev.19 / development / D8G`

The first D8G test intentionally uses the already healthy field station and is non-destructive.

Purpose:

1. refresh the installed installer to the exact D8G source commit;
2. build a ZIP from that immutable source lock;
3. verify every packaged file using `package-manifest.json`;
4. extract the package into a temporary/local test directory;
5. verify the extracted package again;
6. execute the packaged bootstrap in Preview mode only;
7. confirm the package remains pinned to its immutable commit and detects the real installation as `CURRENT / NONE / Payload drift NO`;
8. optionally open the packaged Setup GUI and run Health Report; Apply must remain disabled.

This test must not change service, COMs, runtime, `vector.ini` or radio state.

Expected package verification:

```text
PACKAGE_VERIFY_OK
```

Expected packaged-bootstrap state:

```text
Resolution   : package-lock
Release      : 0.8.0-dev.19 / development / D8G
Detected     : CURRENT
Mode         : NONE
Payload drift: NO
```

Expected packaged GUI/health state:

```text
Detected       CURRENT
Recommended    NONE
Payload drift  NO
INSTALLATION STATUS : READY
D8F_COMMISSIONING_REPORT_OK
```

Result remains pending field execution.

---

## Matrix status

| Scenario | Status | Evidence |
| --- | --- | --- |
| CLEAN Windows 10/11 | Pending | Requires clean VM/machine, including com0com driver test |
| CURRENT healthy | In validation | D8G.1 packaged baseline on current field station |
| CURRENT payload drift | Pending | Existing D8C evidence will be repeated on D8G package |
| CURRENT broken/incomplete | Pending | Requires controlled test state |
| LEGACY GADXVectorBridge | Pending | Requires legacy fixture/VM |
| Runtime absent | Pending | Requires isolated/clean test root or VM |
| Runtime incomplete/version drift | Pending | Requires controlled fixture |
| Reboot after COM changes | Pending | Requires COM provisioning test |
| Repeated repair/idempotence | Pending | Requires D8G package repeat test |
| Induced failure + rollback | Pending | Requires controlled failure test |

