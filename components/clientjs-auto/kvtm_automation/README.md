# KVTM Automation

`kvtm_automation` is the clean, reusable ClientJS automation runtime for KVTM Multi.
It replaces the architectural role of the recovered AUTO PRO `automation.pyc` / `adb_controller.pyc` pair without importing either file.

AUTO PRO is retained only as a behavioral/reference source for verified templates, coordinates, ordering and timing. New business logic belongs here as readable `.py` source.

## Design rules

1. **One-way dependencies only**

   ```text
   workflows
      ↓
   KVAutomation facade
      ↓
   actions
      ↓
   runtime + models + context
      ↓
   PCDriver / EngineDriver + third-party libraries
   ```

   Lower layers never import workflows. Actions never import one another through the facade. Circular imports are not allowed.

2. **Actions are reusable mechanics, workflows are business processes**

   - `actions/popup.py`: entry screen and popup recovery.
   - `actions/navigation.py`: farm/friend/home navigation.
   - `actions/stall.py`: shop opening, scrolling and 20-slot geometry.
   - `actions/buying.py`: friend-stall purchases.
   - `actions/inventory.py`: storage category selection and VP lookup.
   - `actions/selling.py`: own-stall resale in batches of ten.
   - `workflows/*.py`: orchestration only. A workflow must not reimplement clicks, template matching or low-level waits.

3. **No recovered `.pyc` in the execution path**

   `automation.pyc`, `adb_controller.pyc` and AUTO PRO's `runtime/pyc` directory are not imported by this package. The clean runtime may reuse third-party binary libraries and image assets distributed with AUTO PRO.

4. **Reference geometry has one owner**

   Fixed 1000×1000 shop coordinates, visible-slot layout, swipe mechanics and template zones live in the action that owns them. Workflows never duplicate these constants.

5. **Every destructive operation must be verified**

   Purchase/resale methods validate the expected visual state before acting and verify a post-action state whenever the recovered client exposes one. A workflow must stop rather than guess when identity or location cannot be verified.

6. **Cancellation is cooperative and universal**

   Every wait, retry, purchase loop and sale loop calls `AutomationContext.ensure_running()`. No new workflow may add a long raw `time.sleep()` loop.

7. **Persistent state is workflow-owned**

   Scheduling, carryover/remainder, checkpoints and run results belong to the workflow/job layer. Runtime/actions stay stateless between clone sessions.

8. **Compatibility fields are translated at the boundary**

   Legacy UI/config names may be accepted by a worker for backward compatibility, but internal names describe their real purpose. For example the recovered `buy_sell_friend_kho_id` is treated as a resale storage/category selector, not as a second friend-stall geometry.

9. **Safe extension pattern**

   To add a new feature:

   ```text
   a. reuse an existing action where possible
   b. add one small action module only when a reusable mechanic is genuinely new
   c. expose it through KVAutomation
   d. add workflows/<feature>.py for orchestration
   e. add worker/UI integration last
   f. add static/package tests before enabling live transactions
   ```

10. **Source tree stays distribution-clean**

    Runtime diagnostics, screenshots, manifests and traces belong under the application's data/work directory. They must never be written into this source package or bundled into release ZIPs accidentally.

## Package map

```text
kvtm_automation/
├── README.md
├── __init__.py
├── automation.py       # stable facade used by workers/workflows
├── context.py          # pid/profile/path/cancellation/reporting
├── errors.py           # typed failure contract
├── models.py           # shared immutable visual/domain models
├── runtime/
│   ├── bootstrap.py    # third-party binary-library exposure only
│   ├── driver.py       # PCDriver / EngineDriver construction
│   ├── assets.py       # lazy template catalogue
│   ├── vision.py       # deterministic OpenCV matching
│   └── wait.py         # stop-aware waits/retries
├── actions/
│   ├── popup.py
│   ├── navigation.py
│   ├── stall.py
│   ├── buying.py
│   ├── inventory.py
│   └── selling.py
└── workflows/
    └── clear_stall.py
```

`KVAutomation` is the only high-level object workers should construct. This keeps later refactors inside the package and prevents UI/worker code from depending on internal action classes.
