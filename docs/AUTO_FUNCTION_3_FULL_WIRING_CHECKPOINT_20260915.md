# AUTO MULTI DEV — Function 3 full wiring checkpoint

Date: 2026-09-15
Branch: `develop/multi-auto-dev`

Status: **WIRED INTO FULL FUNCTION SET / BUILD + CUMULATIVE LIVE PENDING**

## Operator intent

Function 3 is now treated as one complete Function, not only a DEV Step test. It must be selectable from the normal AUTO MULTI DEV Function list and run through the normal `FunctionModule` / `AutoMainWorkflow` path.

## Current source wiring verified

- `FunctionThreeWorkflow.run()` delegates to the complete six-step cumulative runner.
- `FunctionModule.run(function_id="function_3")` dispatches to `FunctionThreeWorkflow(self.auto).run()`.
- `AutoMainWorkflow` has a Function-3 completion gate requiring `progress_steps=6`, `total_steps=6`, exact MAIN at the end, and the expected product/material counts.
- `_AUTO_MAIN_FUNCTION_OPTIONS` contains:
  - Function 1: `9 Táo sấy - 9 Vải vàng`
  - Function 2: `9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng`
  - Function 3: `9 Nước hoa hồng - 9 Trà đá - 9 Vải vàng`
- Shared Builder/Function catalog contains `function_3` with sale policy `nuoc_hoa_hong`, `tra_da`, `vai_vang`.

## Function terminology used by this project

**Function** = one complete business/production cycle owned by the scheduler, from its defined entry boundary through all internal Steps/Recipes/Actions to its safe completion boundary.

A Step is only one ordered stage inside a Function. A Recipe composes reusable Actions for one business stage. An Action owns the reusable manipulation/verification details. Therefore `Function 1`, `Function 2`, and `Function 3` mean three complete selectable production cycles, not three low-level calls.

## Current Function meanings

- Function 1: core cycle producing 9 Táo sấy, 9 Nước táo and 9 Vải vàng (with planting/material work), ending at exact MAIN. Sale policy exposes Táo sấy + Vải vàng.
- Function 2: Function 1 core plus Hồng/Tuyết material cycle and 7 Tinh dầu hoa hồng, ending at exact MAIN. Sale policy exposes Táo sấy + Vải vàng + Tinh dầu hoa hồng.
- Function 3: six-step cycle producing the configured VPs including Vải vàng, 9 Tinh dầu hoa hồng, 9 Trà đá and 9 Nước hoa hồng, ending at exact MAIN. Sale policy exposes Nước hoa hồng + Trà đá + Vải vàng.

## Pending evidence

The current machine build is blocked by a package-output file lock, not by a Function-3 source verifier failure. Do not call the newly corrected cumulative Function 3 runtime PASS until the operator completes a clean `[1]` build and live retest after the TDHH material correction.
