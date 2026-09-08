# KVTM AI Working Rules

This file is a mandatory first-read for every AI session that works on this repository. Also read `AI_COORDINATION.md` before changing code. For AUTO/Multi continuation, also read `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`; when that handoff points to a feature-specific document, read that document before changing the feature.

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
- Keep the strict protocol/revision contract required by the current source: `CAPTURE3`, `INPUT4`, `BATCH_SWIPE`, `NO_LAYOUT`, `CAPTURE3_SYNC2`, `CAPTURE3_FIXEDMAP`, `CAPTURE3_WRITERMAP2`, and `CAPTURE3_WRITERMSG1`.
- `CAPTURE3_WRITERMAP2` is mandatory after the 2026-09-08 live evidence where one frame id had different coherent dimensions in the pipe response and PID-only shared mapping. Multi Dev must use `CAPTUREW`, receive the native writer id, and open only `Local\\KVTM-CaptureV3-{pid}-{writer_id}` for that request.
- `CAPTURE3_WRITERMSG1` is mandatory after live evidence where the current pipe writer returned success with `writer_id=0`. `CAPTUREW` must dispatch to the render thread through the registered message unique to that PID + writer id; do not regress it to the shared `WM_APP` capture message.
- Do not regress Multi Dev to the legacy PID-only `CAPTURE` mapping. Legacy `CAPTURE` remains native compatibility only for other packaged consumers.
- Do not accept an older/newer frame from another request merely because it is complete. Multi Dev WRITERMAP2 binds one `CAPTUREW` to one writer and one exact expected frame.
- Do not reintroduce HWND capture fallback into AUTO MULTI DEV main flow without explicit evidence and approval.

## 6. AUTO Builder ordering contract

- `TỰ TẠO AUTO` is a DEV-only visual Scheduler layered onto the existing Multi DEV UI. Keep its controls/styles synchronized with the Multi DEV tab strip and existing ttk styles; do not invent a separate visual theme.
- The authoritative current Builder continuation state is `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`; follow the feature-specific handoff named there before changing Builder.
- `Vào game + đóng popup`, `Bán VP theo Function`, and each `Function` are independent callable modules. A module must not secretly insert another business module before/after itself.
- Builder execution order is exactly the operator-visible step order. Do not silently prepend `GameSessionWorkflow` in Builder mode.
- VP sale policy belongs to Function metadata. The Scheduler supplies the Function id; the sale module sells only the VP explicitly allowed for that Function and keeps exact-x10/post-selection verification.
- A Function block may have a loop count. `sale_after_each_loop=true` means the Scheduler calls the separate sale module after each completed Function loop; the Function implementation itself must not absorb or hide that sale operation.
- The previously completed built-in Function 1 must be available in `Load Function` as **`9 Táo sấy - 9 Vải vàng`** through a wrapper that calls the proven built-in implementation. Do not reconstruct it into guessed click/swipe JSON just to make it editable.
- A Builder `Swipe` may contain an ordered path of 2 or more points. Runtime must execute that path as **one** native `driver.swipe_points(...)` / `BATCH_SWIPE` gesture. Do not split the path into independent swipe actions that lift/restart input between segments.
- Recognition-image source order is explicit: option 1 is the persistent **Multi DEV image library**; option 2 is the packaged **AUTO PRO image catalog**. Selecting an AUTO PRO image must copy/dedupe it into the Multi DEV library and the Builder step must use the copied library path thereafter.
- If a Function ends at a camera state from which the sale module cannot prove the main screen, fail closed. Do not invent an unverified floor route just to make a configured loop continue.
- Builder plans, saved Functions, and recognition images are persistent user data and must survive normal Control Center `[1]` rebuilds.
- Builder must reuse the isolated AUTO MULTI DEV worker, stop relay, busy/profile ownership rules, strict Bridge V3 transport, and no-HWND-fallback policy. It must not call Dọn quầy runtime.

When these rules conflict with an older handoff note, follow the user's latest explicit instruction and update the coordination documentation accordingly.
