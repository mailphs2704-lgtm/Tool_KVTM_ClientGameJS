# KVTM Automation

`kvtm_automation` is the clean, reusable ClientJS automation runtime for KVTM Multi.
It replaces the architectural role of the recovered AUTO PRO `automation.pyc` / `adb_controller.pyc` pair without importing either business module.

AUTO PRO is retained as a verified source for third-party runtime libraries, bridge binaries, image assets, coordinates, ordering and behavioral reference. New business logic belongs here as readable `.py` source.

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
   CocosBridgeDriver + third-party image libraries
      ↓
   kvtm_bridge.dll / GameClientJS
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

3. **No recovered AUTO PRO business bytecode in the execution path**

   `automation.pyc`, `adb_controller.pyc`, `image_processor.pyc`, GUI bytecode and recovered business controllers are not imported by this package.

   The clean runtime is allowed to load **third-party** NumPy/OpenCV/Pillow files from AUTO PRO's extracted PyInstaller layout (`runtime/pyc` and `_internal`). This deliberately mirrors the binary environment already proven by the working main AUTO while keeping the business execution path independent. `runtime/bootstrap.py` restores the clean `sys.path` after those libraries are resident and rejects accidental loading of known AUTO PRO business modules.

4. **The native DLL bridge is the authoritative ClientJS transport**

   `runtime/cocos_bridge.py` owns `PING`, `CAPTURE`, `DOWN`, `MOVE` and `UP` communication with `kvtm_bridge.dll`. Dọn quầy does not route transaction-capable input through recovered `EngineDriver`/`ADBController` code.

5. **Reference geometry has one owner**

   Fixed 1000×1000 shop coordinates, visible-slot layout, swipe mechanics and template zones live in the action that owns them. Workflows never duplicate these constants.

6. **Every destructive operation must be verified**

   Purchase/resale methods validate the expected visual state before acting and verify a post-action state whenever the recovered client exposes one. A workflow must stop rather than guess when identity or location cannot be verified.

7. **Cancellation is cooperative and universal**

   Every wait, retry, purchase loop and sale loop calls `AutomationContext.ensure_running()`. No new workflow may add a long raw `time.sleep()` loop.

8. **Persistent state is workflow-owned**

   Scheduling, carryover/remainder, checkpoints and run results belong to the workflow/job layer. Runtime/actions stay stateless between clone sessions.

9. **Compatibility fields are translated at the boundary**

   Legacy UI/config names may be accepted by a worker for backward compatibility, but internal names describe their real purpose. For example the recovered `buy_sell_friend_kho_id` is treated as a resale storage/category selector, not as a second friend-stall geometry.

10. **Safe extension pattern**

    To add a new feature:

    ```text
    a. reuse an existing action where possible
    b. add one small action module only when a reusable mechanic is genuinely new
    c. expose it through KVAutomation
    d. add workflows/<feature>.py for orchestration
    e. add worker/UI integration last
    f. add static/package tests before enabling live transactions
    ```

11. **Source tree stays distribution-clean**

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
│   ├── bootstrap.py    # third-party AUTO_PRO library environment only
│   ├── cocos_bridge.py # direct kvtm_bridge.dll transport
│   ├── driver.py       # clean driver factory
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
    └── clear_stall/
        ├── config.py
        ├── manifest.py
        ├── result.py
        ├── state.py
        └── workflow.py
```

`KVAutomation` is the only high-level object workers should construct. This keeps later refactors inside the package and prevents UI/worker code from depending on internal action classes.