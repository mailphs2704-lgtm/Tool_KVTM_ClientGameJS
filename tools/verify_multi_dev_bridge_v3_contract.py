from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "components/clientjs-auto/kvtm_automation/runtime/driver.py"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
PACKAGE = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    texts = {}
    for path in (FACTORY, ENGINE, NATIVE, PACKAGE, WORKER, ENTRY):
        if not path.is_file():
            raise AssertionError(f"Missing Bridge V3 contract file: {path}")
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            ast.parse(source, filename=str(path))
        texts[path] = source

    factory = texts[FACTORY]
    engine = texts[ENGINE]
    native = texts[NATIVE]
    package = texts[PACKAGE]
    worker = texts[WORKER]
    entry = texts[ENTRY]

    require(factory, '_load_module("engine_driver")',
            "Multi Dev does not select EngineDriver V3")
    require(factory, 'driver._pipe("PING\\n", 1000)',
            "Strict V3 PING gate missing")
    for token in ("KVTM_BRIDGE_V3", "CAPTURE3", "INPUT4",
                  "BATCH_SWIPE", "NO_LAYOUT"):
        require(factory, token, f"Factory V3 capability gate missing: {token}")
        require(native, token, f"Native V3 capability missing: {token}")

    if "CocosBridgeDriver(" in factory or "kvtm_bridge.dll" in factory:
        raise AssertionError("AUTO MULTI DEV still wires the legacy CAPTURE1 bridge")

    require(engine, "def _trace(self, _action: str, **_details)",
            "EngineDriver must own its trace compatibility shim")
    require(engine, "class EngineTouchProxy:",
            "EngineDriver must own a cursor-free chained touch proxy")
    require(engine, "self.touch = EngineTouchProxy(self)",
            "Resident PCDriver touch proxy must be replaced")
    require(engine, "def click(self, x: float, y: float)",
            "EngineDriver must override inherited click")
    require(engine, "return self.swipe_points(",
            "EngineDriver must override inherited swipe with native batch")
    if engine.index("def _trace(self, _action: str, **_details)") > engine.index("def __init__(self, device_key"):
        raise AssertionError("EngineDriver trace shim must exist before construction")
    require(engine, "with self._pipe_lock:",
            "V3 capture must hold the pipe lock through shared-memory copy")
    require(engine, "return self._capture_shared_bgra_once_locked()",
            "Atomic V3 capture wrapper missing")
    require(engine, "def _capture_shared_bgra_once_locked",
            "Locked V3 shared-memory reader missing")
    require(engine, "frame_id < expected_frame",
            "Capture3 reader must accept a stable newer completed frame")
    require(engine, "verified_key != snapshot_key",
            "Capture3 seqlock post-copy verification missing")
    if "status != 2 or frame_id != expected_frame" in engine:
        raise AssertionError("Capture3 reader still rejects valid newer frames")
    require(engine, 'command = f"SWIPE {segment_steps}',
            "EngineDriver native batch command missing")
    require(engine, 'pipe_mode="single_batch"',
            "Single-batch timing evidence missing")
    require(package, '"kvtm_loader_v3.exe", "kvtm_bridge_v3.dll"',
            "V3 binaries are not packaged")
    require(package, 'worker\\auto_multi_dev_worker.py',
            "Isolated AUTO MULTI DEV worker is not a required package input")
    require(worker, 'runtime="isolated-process"',
            "AUTO MULTI DEV worker isolation marker missing")
    require(worker, 'bridge="V3"', "AUTO MULTI DEV worker V3 marker missing")
    require(worker, 'importlib.import_module("local_launcher")',
            "Worker must use the proven AUTO image bootstrap")
    require(worker, "adaptive_cv.install_adaptive_matching()",
            "Worker must complete proven OpenCV initialization")
    require(worker, "image_runtime_ready=True",
            "Clean workflow must reuse worker-prepared image modules")
    require(worker, "KVAutomation(", "Worker must own KVAutomation")
    require(worker, "AutoMainWorkflow(automation).run()",
            "Worker must own the complete main workflow")
    require(entry, 'worker_root / "auto_multi_dev_worker.py"',
            "Multi GUI does not launch the isolated worker")
    require(entry, "self._live_enabled.discard(profile_id)",
            "Live capture must yield before AUTO MULTI DEV starts")
    thread_body = entry.split("def _run_clean_main_thread", 1)[1].split(
        "def _finish_clean_main", 1
    )[0]
    if "KVAutomation(" in thread_body:
        raise AssertionError("Multi GUI thread still constructs automation in-process")
    require(thread_body, "subprocess.Popen(",
            "Multi GUI thread must supervise a worker process")

    print("AUTO MULTI DEV BRIDGE V3 CONTRACT VERIFIED")
    print("protocol=KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT")
    print("legacy_capture1_fallback=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
