# AUTO MULTI DEV — BUILD VERIFIER FIX 2026-09-15

Branch: `develop/multi-auto-dev`
Status: **SOURCE FIXED — OPERATOR REBUILD PENDING**

## Build evidence

Operator build at source `a52a415c3c88f7880d50fe1cecefd90fe40899ba` passed the early AUTO MULTI DEV contracts, then stopped in `verify_clear_stall_contract_build.py` because the legacy Dọn quầy verifier still required the old dark console marker:

```text
require(main_log_viewer, 'bg="#202020"', "Console-style log viewer missing")
AssertionError: Console-style log viewer missing
```

This is a stale UI assertion, not a Dọn quầy runtime regression. `main_log_viewer.py` was intentionally changed to the operator-requested light unified log window with three tabs.

## Fix

Commit `295e0961c176c778ea1e45682b54e1423e840545` updates only the migration-aware build adapter. The underlying legacy clear-stall safety verifier remains active.

The replacement contract now proves all of these in the current log viewer:

- legacy `open_log_window(...)` compatibility remains;
- `open_auto_log_window(...)` exists;
- tabs `Log hành động`, `Log chi tiết`, `Log lỗi` exist;
- `Xuất lỗi TXT` remains inside `Log lỗi`;
- light data surface `#ffffff` is present;
- one-second auto-refresh label remains.

No Dọn quầy workflow, transaction, Bridge, Function, recovery or ClientJS behavior was changed by this fix.

## Next gate

Run the normal operator build again:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Do not call BUILD PASS until the full `[1]` reaches its success terminal output. If the next verifier fails, patch only the exact stale/new contract exposed by that output.
