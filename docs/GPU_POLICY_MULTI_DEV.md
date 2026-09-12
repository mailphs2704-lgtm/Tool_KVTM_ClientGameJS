# Multi DEV GPU policy — DWM Live View off + Bridge V3 FPS governor

Date: 2026-09-12  
Branch: `develop/multi-auto-dev`  
Safety backup: `backup/pre-liveview-fps-20260912`

## Goal

Reduce GPU use without changing AUTO coordinates, recognition inputs, or the ClientJS window size used by the current Multi DEV workflow.

This change has two independent parts:

1. **Disable the account-list DWM Live View in Multi DEV.**
   - Multi DEV no longer registers DWM thumbnails.
   - The historical 100 ms DWM update loop is not rescheduled.
   - The old Live View capture worker and Tk image polling loop stay idle.
   - This change is DEV-only; the shared production UI source remains intact.

2. **Limit ClientJS rendering to 20 FPS while AUTO MULTI DEV is attached through Bridge V3.**
   - Bridge V3 adds capability `FPS_LIMIT1` and command `FPS <5..120>`.
   - The command is executed on the ClientJS window/render thread.
   - The governor calls `cocos2d::Director::setAnimationInterval(1 / FPS)`.
   - Both known x86 MSVC signatures are resolved dynamically: `double` and `float`.
   - There is no `Sleep()`-based render throttle.
   - AUTO applies 20 FPS only when the resident DLL advertises `FPS_LIMIT1`.
   - If an old Bridge V3 DLL is already resident, AUTO keeps the current FPS and logs that ClientJS must be restarted after the update.

## What does not change

- No AUTO Function workflow is changed.
- No click/swipe coordinates are changed.
- No DWM/window resize policy is added to Bridge V3.
- CAPTURE3 and writer-bound capture behavior are unchanged.
- The physical/native ClientJS capture resolution remains unchanged.
- Explicit diagnostic/recording features are not converted into background Live View.

## Static verification

Run from the repository root:

```bat
py -3.11 tools\verify_multi_dev_gpu_policy.py
py -3.11 bridge-v3\tools\verify_v3.py --root bridge-v3
```

The second command expects the Bridge V3 x86 binary to have been built already.

## Runtime verification after pull/build

1. Close Multi DEV and all GameClientJS processes so no old Bridge V3 DLL remains resident.
2. Run `KVTM_DEV_CONTROL.bat`.
3. Choose **[1] Update source + build runtime DEV**.
4. Start Multi DEV and two clients.
5. Start AUTO so Bridge V3 attaches.
6. Confirm the AUTO detail log contains the GPU policy line showing 20 FPS.
7. Observe Task Manager:
   - Desktop Window Manager should no longer carry the old DWM-thumbnail Live View load from Multi DEV.
   - GameClientJS GPU use should drop once the 20 FPS governor is active.

## Rollback

The pre-change source is preserved on:

`backup/pre-liveview-fps-20260912`

If this GPU policy causes a regression, return `develop/multi-auto-dev` to that backup commit or cherry-pick/revert the GPU-policy commit. Profiles/settings are not changed by this source patch.
