# Multi DEV GPU policy — Live View removed + Bridge V3 FPS menu

Date: 2026-09-12  
Branch: `develop/multi-auto-dev`  
Safety backups:
- `backup/pre-liveview-fps-20260912`
- `backup/pre-remove-liveview-fps-menu-20260912` → `686809513a936eca4ecdbf4e2c725208a3da73be`

## Goal

Reduce GPU use without changing AUTO coordinates, recognition inputs, or the native ClientJS capture size used by the current Multi DEV workflow.

The current policy has two independent parts:

1. **Remove Live View from Multi DEV.**
   - The `Live View` button is removed from the DEV UI at runtime.
   - The Preview route is disabled in DEV even if something tries to call it directly.
   - Multi DEV does not register DWM thumbnails.
   - The historical 100 ms DWM update loop is not rescheduled.
   - The old Live View worker/result polling paths are disabled.
   - This is DEV-only; the shared production UI source remains intact.

2. **Control ClientJS render FPS through Bridge V3.**
   - Bridge V3 advertises capability `FPS_LIMIT1` and accepts `FPS <5..120>`.
   - AUTO MULTI DEV still applies **20 FPS by default** when it attaches.
   - Multi DEV now exposes a top-level **FPS** menu with presets:
     `10 / 15 / 20 / 25 / 30 / 40 / 60 FPS`.
   - Selecting a preset scans/adopts running managed ClientJS processes and sends `PING`, then `FPS <n>` only to bridges advertising `FPS_LIMIT1`.
   - The FPS command is executed on the ClientJS window/render thread.
   - The governor calls `cocos2d::Director::setAnimationInterval(1 / FPS)`.
   - Both known x86 MSVC signatures are resolved dynamically: `double` and `float`.
   - There is no `Sleep()`-based render throttle.
   - An old resident Bridge DLL is not treated as a fatal error; restart ClientJS after rebuilding to load the new capability.

## What does not change

- No AUTO Function workflow is changed, including Function 2.
- No click/swipe coordinates are changed.
- CAPTURE3 and writer-bound capture behavior are unchanged.
- Native/table/logical AUTO resolution remains 1000×1000 in the current target workflow.
- Selecting another render FPS does **not** resize the ClientJS or captured frame.
- Video recording remains an explicit feature and is not converted into background Live View.

## Static verification

Run from the repository root:

```bat
py -3.11 tools\verify_multi_dev_gpu_policy.py
py -3.11 bridge-v3\tools\verify_v3.py --root bridge-v3
```

The first verifier checks Live View removal, the seven FPS presets, default 20 FPS, Bridge V3 transport, native capture preservation, and the no-`Sleep()` governor contract. The second command expects the Bridge V3 x86 binary to have been built already.

## Runtime verification after pull/build

1. Close Multi DEV and all GameClientJS processes so no old Bridge V3 DLL remains resident.
2. Run `KVTM_DEV_CONTROL.bat`.
3. Choose **[1] Update source + build runtime DEV**.
4. Start Multi DEV and two clients.
5. Confirm there is no `Live View` button and a top-level `FPS` menu is visible.
6. Start AUTO. Confirm the AUTO detail log shows the 20 FPS GPU-policy line and native 1000×1000 CAPTURE3.
7. Change FPS from the menu, for example 20 → 30 → 20. The status line should report how many running ClientJS processes accepted the Bridge V3 command.
8. Observe Task Manager:
   - Desktop Window Manager should no longer carry the old DWM-thumbnail Live View load from Multi DEV.
   - GameClientJS GPU use should react to the selected render FPS.

AUTO startup still owns the safe default of 20 FPS. Therefore, restarting AUTO may reapply 20 FPS; a manual FPS menu choice can be applied again afterward when testing another rate.

## Rollback

For the exact state immediately before removing Live View from the UI and adding the FPS menu, use:

`backup/pre-remove-liveview-fps-menu-20260912`

That branch points to `686809513a936eca4ecdbf4e2c725208a3da73be`. Profiles/settings are not changed by this source patch.
