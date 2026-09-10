# AUTO MULTI DEV — DUAL RESOLUTION SALE HANDOFF — 2026-09-10

## Operator requirement

`Bắt đầu AUTO MULTI DEV` must never resize ClientJS.

- ClientJS already 500x500 -> use native-500 recognition/sale table.
- ClientJS already 1000x1000 -> use native-1000 / recovered 1000 baseline table.
- Logical business/input coordinates remain 1000x1000 in both modes.
- Unsupported native size fails closed before AUTO business clicks; operator changes size from the GUI/profile, not from AUTO.
- Native size changing in the middle of one worker run fails closed; do not silently swap recognition tables mid-transaction.

## Source changes

### Passive resolution ownership

`components/clientjs-auto/kvtm_automation/runtime/resolution.py`

- `SUPPORTED_CLIENT_SIZES=((500,500),(1000,1000))`.
- `detect_client_resolution()` reads raw CAPTURE3; no HWND resize.
- `NativeCaptureDriver` exposes raw native CAPTURE3 to VisionEngine and blocks a mid-run resolution change.
- No `SetWindowPos`, `AdjustWindowRectEx`, `_resize_client`, `ensure_production_client_size`, or frame upscale in this module.

`components/clientjs-auto/kvtm_automation/automation.py`

Required order:

```text
Bridge V3 attach
-> detect current native CAPTURE3 size
-> select native-500 or native-1000 contract
-> NativeCaptureDriver
-> VisionEngine
```

Expected startup markers:

```text
AUTO MULTI DEV resolution • preserve-client-size • native=500x500 • table=500x500 • logical=1000x1000 • no-resize
AUTO MULTI DEV resolution • preserve-client-size • native=1000x1000 • table=1000x1000 • logical=1000x1000 • no-resize
```

Only one of those applies to one running ClientJS.

### Sale state machine

`components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py`

Canonical transition:

```text
OWN_STALL_READY
-> detect EMPTY_SLOT read-only
-> click EMPTY_SLOT exactly once
-> wait PICKER_READY
-> select/prove STORAGE2
-> scan allowed VP on fresh frames
-> open sale dialog
-> selected-item proof
-> x10 proof from native-size table
-> click Đặt bán
-> sale screen-change proof
-> POST_SALE OWN_STALL_READY stable two passes
-> only then next listing is allowed
```

Do not restore the previous `SALE_PICKER_OPEN_ATTEMPTS` loop. A picker proof miss must never authorize a second click at the old empty-slot coordinate.

Do not restore fixed `POST_SALE_STALL_SETTLE` as the readiness gate. The state gate is `quay_hang_on` stable and sale dialog absent.

### Storage2 proof

`components/clientjs-auto/kvtm_automation/actions/inventory.py`

Native 500 live calibration used by the current state proof:

- `kho_thanh_pham` before selection: ~0.332.
- `kho_thanh_pham` active after selection: ~0.508.
- other active picker markers observed around 0.6265 / 0.6369 / 0.6184.

Therefore:

- generic >=0.52 multi-marker proof means only `picker visible`;
- it must NEVER mean `storage2 active`;
- native-500 storage2 active requires target-specific `kho_thanh_pham >= 0.46` in `STORAGE2_ACTIVE_ZONE`, two consecutive passes, while picker remains visible;
- storage2 click is at most one for a transition;
- if storage2 is already active after cancel/recovery, do not click/toggle it again.

Native 1000 keeps recovered pre-native AUTO-PRO baseline table (`0.82`, scale `1.0`) and the historical logical storage2 point `(450,442)` only as fallback after picker proof.

### Resolution-specific sale proof

`components/clientjs-auto/kvtm_automation/actions/selling.py`

- native 500 sale dialog: `dat_ban` threshold 0.68 with calibrated multiscale plus native orange-button fallback;
- native 1000 sale dialog: baseline `dat_ban` threshold 0.78, scale 1.0, no native-500 orange fallback;
- own-stall state requires `quay_hang_on` and sale dialog absent;
- empty-slot recognition has a read-only API so state can be proved before the click.

`auto_main_selling.py` exact-ten table:

- native 500: threshold 0.78, calibrated multiscale, two consecutive passes;
- native 1000: recovered baseline threshold 0.95, scale 1.0, two consecutive passes.

## Static verifier changes

- `tools/verify_resolution_adaptive_contract.py`: dual-resolution/passive/no-resize contract.
- `tools/verify_auto_main_sale_contract.py`: click-once state machine, target-specific storage2, 500/1000 x10 tables, POST_SALE own-stall gate.

## Commits in this repair

- `5301f581ade9f00b6fb55665c17d50cf01affb4f` — Make AUTO resolution detection passive
- `187b082bc7207a140893acd055e8130297f254b1` — Preserve ClientJS size when AUTO starts
- `5c5f90c984d5d8d0d5f22572294547348f60a87f` — Make AUTO storage2 selection state-driven
- `0ef3ff479cf8b1a85e20b6e22743c36996846f38` — Add explicit own-stall sale state proofs
- `4677f44a870e8a1f439a960ae18ad425b09f0b48` — Rebuild AUTO sale transitions as state machine
- `963e2fc70606e247c4a7bde31f016417b9e7ed1c` — Recognize active native500 picker without retoggle
- `fb65656dd97d180a384ea6008ab727d8590106cd` — Verify passive 500 and 1000 AUTO resolution
- `64464483fa08fc3e96947c1b22ee49039b8a68da` — Verify state-driven dual-resolution VP sale

## GitHub Actions status at handoff

Do not interpret current Actions red status as a source assertion failure without logs. For the latest run at `64464483...`, both Ubuntu and Windows jobs completed with:

```text
steps=[]
runner_id=0
```

and package-smoke was skipped. The AUTO PRO inspect job also had `steps=[]`, `runner_id=0`. No workflow command or Python verifier actually started. A repository Actions infrastructure/quota/runner issue is therefore currently blocking CI evidence.

Static source contracts still need the operator Windows `[1]` build before runtime testing is called PASS.

## Next operator test

From:

```bat
cd /d "C:\Users\15130\Desktop\Tool_KVTM_Multi_DEV"
git pull --ff-only origin develop/multi-auto-dev
git rev-parse HEAD
```

Then run DEV menu `[1] Pull + build/test + gửi báo cáo`.

After build, test both modes separately when convenient:

1. leave ClientJS at 500x500, start AUTO, confirm startup says `native=500x500 • table=500x500 • no-resize` and the client remains 500x500;
2. leave ClientJS at 1000x1000, start AUTO, confirm startup says `native=1000x1000 • table=1000x1000 • no-resize` and the client remains 1000x1000.

Sale live evidence to collect:

```text
OWN_STALL READY
EMPTY_SLOT click-once
PICKER READY after EMPTY_SLOT click-once
STORAGE2 ACTIVE proof / STORAGE2 READY
Kho thành phẩm scan PASS
sale dialog READY + x10 PASS • table=500-table|1000-table
AUTO MAIN đã treo ... • chờ POST_SALE OWN_STALL
POST_SALE OWN_STALL READY • next-listing-safe=true
```

## Runtime status

Source implementation: complete.
Static-contract source: complete.
GitHub Actions execution: blocked before runner/steps.
Windows build: pending operator run.
Windows live 500: pending.
Windows live 1000: pending.

Do not call runtime PASS until Windows evidence is supplied.
