# AUTO MULTI DEV — LEVEL-UP POPUP RECOVERY CHECKPOINT

Date: 2026-09-18
Branch: `develop/multi-auto-dev`
Status: **SOURCE COMPLETE — BUILD/LIVE PENDING**

## Operator contract

The supplied 1000x1000 frame is the blocking level-up reward modal. The existing
`assets/items/lv_up.png` title template matches the marked `LÊN CẤP` text.

During AUTO Main, one cooperative guard runs from the existing worker
`ensure_running()` checkpoints every 0.80 seconds. It does not create a new
thread, UI poll, or competing input owner.

On detection:

1. stop the interrupted foreground checkpoint with `LevelUpPopupDetected`;
2. click the verified `Nhận` button center at logical `(500, 688)`;
3. prove the title template disappeared;
4. invalidate stale camera evidence and recover unknown camera to exact MAIN;
5. retry the same Function-loop checkpoint without incrementing Function counters.

Startup's existing popup sweep uses the same exact claim path. Generic popup
handling no longer clicks the `LÊN CẤP` title itself.

## Safety

- recognition remains template guarded at threshold 0.69 in a constrained title
  zone and bounded scales;
- guard matching is quiet so the periodic check cannot flood detail logs;
- recovery pauses the guard recursively while it owns capture/input;
- all guard captures and clicks stay serialized on the worker owner thread;
- no background screenshot thread and no HWND fallback are introduced;
- runtime PASS requires Windows operator evidence.

## Live gate

Use `KVTM_DEV_CONTROL.bat -> [1] Cap nhat source + build runtime DEV`, then
`[2]`. When the popup appears, require logs in this order:

`detected=true -> click Nhận -> popup đã đóng PASS -> exact-main PASS ->
chạy lại Function vòng N, không tăng counter`.
