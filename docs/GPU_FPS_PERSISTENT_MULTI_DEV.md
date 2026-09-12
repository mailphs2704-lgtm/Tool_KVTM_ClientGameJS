# Multi DEV — persistent ClientJS FPS policy

Date: 2026-09-12

## Problem

Bridge V3 FPS limiting was previously applied reliably when the isolated AUTO worker initialized. Before a Function started, two ClientJS processes could therefore render at different/default rates and show strongly different GPU usage. Starting a Function then forced the worker's fixed 20 FPS policy, which made GPU usage stabilize.

## New runtime ownership

The selected FPS is now owned by the resident Multi DEV process for the entire ClientJS/Bridge lifecycle.

- Menu presets remain 10 / 15 / 20 / 25 / 30 / 40 / 60 FPS.
- Default remains 20 FPS.
- The selected value is saved as `multi_dev_render_fps`.
- The selected value is exported as `KVTM_MULTI_DEV_RENDER_FPS` so isolated AUTO workers inherit the same target.
- When Multi DEV adopts a running ClientJS PID, the persistent policy attempts to apply the target.
- When Bridge V3 becomes ready/injected for a PID, the target is applied immediately.
- When the menu value changes, the new value is persisted and applied to all live ClientJS processes.
- Starting a Function no longer owns a separate hard-coded 20 FPS target. The worker reads the inherited Multi DEV target and only confirms/re-applies that same value.

## What does not change

- Bridge V3 still uses `Director::setAnimationInterval`; no `Sleep()` render throttle is introduced.
- AUTO CAPTURE3 native resolution is unchanged.
- 1000x1000 AUTO coordinates/recognition are unchanged.
- Function business logic, inventory recovery, selling logic and navigation are not changed by this patch.
- Live View remains removed from Multi DEV.

## Expected runtime logs

After a ClientJS/Bridge becomes ready:

```text
[KVTM DEV] FPS policy APPLIED • pid=<PID> • target=20 • source=bridge-ready • Director::setAnimationInterval • CAPTURE3 unchanged
```

At Multi DEV startup:

```text
[KVTM DEV] FPS persistent policy READY • target=20 • apply=ClientJS/Bridge lifecycle • AUTO worker inherits same target
```

When AUTO starts, the worker should report the same selected value, for example:

```text
GPU policy • ClientJS render=20 FPS qua Director::setAnimationInterval • target kế thừa từ Multi DEV • AUTO capture giữ nguyên native size
```

If 30 FPS is selected before AUTO starts, the worker log must show `render=30 FPS`, not reset to 20.

## Runtime test

1. Close Multi DEV and all GameClientJS processes.
2. Pull/build the updated `develop/multi-auto-dev` source.
3. Start Multi DEV and two ClientJS processes but do not start any Function yet.
4. Confirm one `FPS policy APPLIED` log per live PID and observe GPU stability in Task Manager.
5. Change the menu from 20 to 30 FPS and confirm both PIDs receive target 30.
6. Start AUTO. Confirm the AUTO worker reports 30 FPS and does not reset the clients to 20.
7. Stop AUTO. Confirm the ClientJS processes remain governed at the selected FPS.

## Rollback

Safety branch before this change:

`backup/pre-persistent-fps-20260912`

It points to commit `949f6abbe2cdb74580b3b482dfbd9cc386f98c3b`.
