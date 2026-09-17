# AUTO MULTI DEV — LOADING RESPONSIVENESS

Date: 2026-09-17  
Branch: `develop/multi-auto-dev`  
Status: **SOURCE/STATIC PASS — WINDOWS BUILD/LIVE PENDING**

## Live evidence

After the log/Bridge-timeout build, the operator still observed Multi freezing
and stuttering while ClientJS reached the ZingPlay loading screen.
The operator then narrowed the regression chronology: it started after fixed
top-right ClientJS positioning and became materially worse after the FPS control
was added.

## Root cause

`_apply_display_to_process()` ran `_inject_bridge()` from a Tk `after()`
callback. Injection uses a blocking loader process with a timeout up to 15
seconds, followed by Bridge V3 readiness/FPS work. Several clients reaching a
window at nearly the same time serialized those waits on the Tk event thread.

`_launch_many()` also used `time.sleep(0.35)` on the Tk thread and started heavy
ClientJS loads almost simultaneously.

The fixed-position integration added one 50 ms Tk polling loop per starting
client. Every loop enumerated windows until its ClientJS HWND appeared, so the
cost multiplied exactly during the ZingPlay loading burst.

The FPS policy also capped a client as soon as Bridge attached and reasserted
the cap every two seconds during the first 60 seconds. That added Bridge traffic
and throttled rendering during the heaviest loading phase.

## Fix

- `Mở tất cả` is now a Tk `after()` queue with a 4000 ms launch stagger.
- No `sleep()` remains in `_launch_many()`.
- Window resize remains on Tk, but Bridge/FPS attachment runs in a daemon thread.
- `_bridge_injecting_pids` prevents duplicate legacy loader runs for one PID.
- Fixed top-right positioning is one-shot after the existing display-ready path
  has found the HWND; the per-client 50 ms startup poll was removed.
- ZingPlay loading remains uncapped. FPS is applied only by an explicit Multi
  menu action or by the isolated AUTO worker when automation actually starts;
  host-side periodic reassert during loading was removed.
- A slow/hung client does not gate the next launch; the queue advances by its
  own timer and Bridge attachment is per PID.
- AUTO business flow, profile identity, Bridge V3 protocol and capture ownership
  are unchanged.

## Verification

- Python compile: PASS.
- `verify_multi_dev_launch_responsiveness.py`: PASS.
- `verify_multi_dev_bridge_v3_contract.py`: PASS.
- `verify_multi_dev_gpu_policy.py`: PASS.
- `verify_kvtm_tool_cry_packaging_contract.py`: PASS.
- Windows build/live: PENDING.

## Live gate

Control Center `[1]`, then `[2]`. Use `Mở tất cả` and verify the Multi UI can be
moved/clicked continuously while ClientJS windows load. Leave one client stuck
at ZingPlay and confirm subsequent clients still launch every four seconds and
existing AUTO workers remain responsive. Confirm the top-right position is
applied once the window is ready, then start AUTO and verify its selected FPS is
applied only at that point.
