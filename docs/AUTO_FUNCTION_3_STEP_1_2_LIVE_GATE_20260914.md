# AUTO MULTI DEV — Function 3 Step 1→2 cumulative live gate

Date: 2026-09-14
Branch: `develop/multi-auto-dev`
Status: SOURCE WIRED — BUILD/LIVE PASS PENDING

## Trigger

Operator reported that pressing the existing Function 3 DEV test stopped after Step 1. Source inspection confirmed the worker branch for the existing `function-3-step-1` DEV mode still called only `FunctionThreeWorkflow.run_step_1()` even though Step 2 source and `run_steps_1_and_2()` were already complete.

## Source change

The existing DEV test path now keeps the same mode/terminal names for current GUI compatibility, but its runtime behavior is cumulative:

```text
exact MAIN
→ Function 3 Step 1
→ remain floor 1
→ Function 3 Step 2
→ goUp(1) floor 2
→ harvest/plant Tea 24
→ collect VP/open Apple Juice machine through shared production Action
→ Apple Juice 9/9
→ repair machine
→ remain floor 2
→ worker terminal
```

Worker call is now:

```text
FunctionThreeWorkflow(automation).run_steps_1_and_2()
```

The compatibility terminal remains `function_3_step_1_finished` so the current large DEV UI does not need a risky unrelated rewrite before the live gate. Action log now states clearly that the test runs `Step 1 → Step 2`; the final worker log includes Tea 24/24, Apple Juice 9/9 and end floor 2.

## Static contract

`tools/verify_auto_builder_contract_core.py` now requires the cumulative worker call and cumulative audit log. It no longer requires the DEV worker to stop after Step 1.

## Commits

```text
1962f6ab  fix(auto): run Function 3 step 1-2 cumulatively in DEV test
2532428d  test(auto): lock cumulative Function 3 step 1-2 DEV test
```

## Next gate

Run the authoritative build:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

If build/static is clean, launch Multi DEV and press the existing Function 3 test button once. The button label may still mention Step 1 for compatibility, but runtime must continue directly into Step 2. Do not mark runtime PASS until operator confirms the live sequence reaches Tea 24, Apple Juice 9/9, repair, and remains on floor 2.
