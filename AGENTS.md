# KVTM AI Working Rules

This file is a mandatory first-read for every AI session that works on this repository. Also read `AI_COORDINATION.md` before changing code.

## 1. Authoritative user update/build workflow

- The user performs source update and DEV runtime build through the root `KVTM_DEV_CONTROL.bat` Control Center.
- For normal AUTO/Multi work on `develop/multi-auto-dev`, the authoritative update/build action is **Control Center `[1] Cap nhat source + build runtime DEV`**.
- After an AI commits/pushes a fix, tell the user to run the BAT Control Center and choose `[1]`. Use `[2]` only when the next step is to launch Multi DEV.
- Do **not** replace this with manual `git pull`, `git lfs pull`, PowerShell builder commands, long CMD command sequences, or direct edits inside `dist`, unless the user explicitly asks for a manual diagnostic/recovery path.
- `[9] Full rebuild package` is exceptional and must only be requested when the current diagnosis specifically requires it.
- The generated `dist/KVTM-ClientJS-Suite-Multi-DEV` tree is runtime output. Fix source files in the repository and let Control Center rebuild/sync the runtime.

## 2. Branch and coordination rules

- AUTO/Multi source work belongs on `develop/multi-auto-dev` unless the user explicitly changes scope.
- Respect the ownership and handoff rules in `AI_COORDINATION.md`.
- No force-push, no history rewrite, and no blind cross-branch merge.
- Do not change stable Dọn quầy/Workspace/profile behavior just to make an unrelated AUTO MULTI DEV test pass.

## 3. Operator stop/profile-switch evidence rule

- If the user states that they intentionally selected another account, stopped AUTO, closed/restarted the selected ClientJS, or otherwise interrupted the run, traceback/output that starts **after that operator action** is interruption evidence, not automatically a runtime defect.
- In particular, do not diagnose or patch `EngineDriver._refresh_profile_pid`, profile rebind, Bridge reconnect, or account identity solely from a traceback produced after an intentional account switch/stop.
- Only treat such a tail as a product bug when independent evidence shows the same failure began before the operator action or reproduces in an uninterrupted run.
- Preserve and analyze all log evidence that occurred before the operator action; do not discard the whole run.

## 4. PASS / FAIL discipline

- Build/static PASS is not runtime PASS.
- A live workflow is PASS only from operator-confirmed behavior plus matching logs/evidence.
- Never lower thresholds, add blind coordinates, or bypass fail-close guards merely to silence a timeout.
- When evidence is incomplete, prefer a narrow diagnostic change or one controlled live retest over speculative business-logic changes.

## 5. Current AUTO MULTI DEV transport contract

- Main AUTO MULTI DEV worker is isolated and uses Bridge V3.
- Keep the strict protocol/revision contract required by the current source: `CAPTURE3`, `INPUT4`, `BATCH_SWIPE`, `NO_LAYOUT`, `CAPTURE3_SYNC2`, `CAPTURE3_FIXEDMAP`, and `CAPTURE3_WRITERMAP2`.
- `CAPTURE3_WRITERMAP2` is mandatory after the 2026-09-08 live evidence where one frame id had different coherent dimensions in the pipe response and PID-only shared mapping. Multi Dev must use `CAPTUREW`, receive the native writer id, and open only `Local\\KVTM-CaptureV3-{pid}-{writer_id}` for that request.
- Do not regress Multi Dev to the legacy PID-only `CAPTURE` mapping. Legacy `CAPTURE` remains native compatibility only for other packaged consumers.
- Do not accept an older/newer frame from another request merely because it is complete. Multi Dev WRITERMAP2 binds one `CAPTUREW` to one writer and one exact expected frame.
- Do not reintroduce HWND capture fallback into AUTO MULTI DEV main flow without explicit evidence and approval.

When these rules conflict with an older handoff note, follow the user's latest explicit instruction and update the coordination documentation accordingly.
