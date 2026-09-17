# AUTO MULTI DEV — LOG LOAD + CLIENT ISOLATION

Date: 2026-09-17  
Branch: `develop/multi-auto-dev`  
Status: **SOURCE/STATIC PASS — WINDOWS BUILD/LIVE PENDING**

## Scope

- Keep AUTO Main in one isolated worker process per profile.
- Remove always-on runtime diagnostic polling from normal operation.
- Bound log viewer work and batch detail-log disk writes.
- Prevent one hung ClientJS window thread from blocking its Bridge V3 pipe forever.

## Changes

- `runtime_diagnostic_logger.py` is default-off. Set
  `KVTM_RUNTIME_DIAGNOSTICS=1` only for a controlled diagnostic run.
- `MainLogWriter` reuses file handles, flushes action milestones immediately,
  and batches detail flushes for at most 0.75 seconds.
- `main_log_viewer.py` reads at most the newest 512 KiB per log and renders at
  most 1000 action rows instead of rereading unbounded files every second.
- Bridge V3 routes touch through a 1000 ms `SendMessageTimeoutW` and capture
  through a 2000 ms timeout. Timeout returns `ERROR_TIMEOUT` to only that
  ClientJS worker/pipe. The timed-out message payload remains valid in case the
  ClientJS window thread completes it later.
- CAPTURE3/INPUT4/BATCH_SWIPE/WRITERMAP2/WRITERMSG1 and no-HWND-fallback
  contracts are unchanged.

## Verification

- Python compile: PASS.
- `verify_runtime_diagnostic_contract.py`: PASS.
- `verify_multi_dev_bridge_v3_contract.py`: PASS.
- Main log batching smoke test: PASS.
- Repository-wide verifier run reached a pre-existing unrelated failure in
  `verify_clear_stall_contract.py` (`Gate 4 inventory must be scanned only after
  opening a stall slot`). None of the files in that contract were changed here.
- Windows DLL build and multi-client live test: PENDING.

## Live gate

Run Control Center `[1]`, then `[2]`. Start at least three clients, leave one
stuck/not-responding at ZingPlay, and verify:

1. the other AUTO workers continue progressing;
2. Multi UI remains responsive;
3. only the affected worker reports Bridge timeout/recovery;
4. action/detail/error logs remain readable without continuous diagnostic
   heartbeat files.

