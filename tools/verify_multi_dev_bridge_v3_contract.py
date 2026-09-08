from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "components/clientjs-auto/kvtm_automation/runtime/driver.py"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
PACKAGE = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
SHARED_IMAGE = ROOT / "components/clientjs-auto/shared_runtime/image_runtime.py"
ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    texts = {}
    for path in (FACTORY, ENGINE, NATIVE, PACKAGE, WORKER, SHARED_IMAGE, ENTRY):
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
    shared_image = texts[SHARED_IMAGE]
    entry = texts[ENTRY]

    require(factory, '_load_module("engine_driver")',
            "Multi Dev does not select EngineDriver V3")
    require(factory, 'driver._pipe("PING\\n", 1000)',
            "Strict V3 PING gate missing")
    for token in ("KVTM_BRIDGE_V3", "CAPTURE3", "INPUT4",
                  "BATCH_SWIPE", "NO_LAYOUT", "CAPTURE3_SYNC2",
                  "CAPTURE3_FIXEDMAP"):
        require(factory, token, f"Factory V3 capability gate missing: {token}")
        require(native, token, f"Native V3 capability missing: {token}")

    require(factory, "ClientJS đang giữ Bridge V3 resident cũ",
            "Stale resident Bridge V3 fail-closed message missing")
    require(factory, '"CAPTURE3_FIXEDMAP" in missing',
            "Factory must reject pre-fixed-map resident V3 binaries")

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
    require(engine, 'or "Kích thước shared capture không khớp phản hồi" in message',
            "Capture3 dimension handoff mismatch must be retried as transient")
    require(engine, "response={expected_width}x{expected_height}",
            "Capture3 mismatch diagnostics must include response dimensions")
    require(engine, "shared={width}x{height}",
            "Capture3 mismatch diagnostics must include shared dimensions")

    mapping_body = native.split("bool ensure_capture_mapping", 1)[1].split(
        "LONG dispatch_capture", 1
    )[0]
    require(native, "kCaptureMappingBytes",
            "Capture3 fixed mapping capacity missing")
    require(mapping_body, "if (g_capture_header && g_capture_mapping) return true;",
            "Capture3 mapping must be reused for the ClientJS lifetime")
    require(mapping_body, "kCaptureMappingBytes, name",
            "Capture3 mapping must be created at fixed maximum capacity")
    require(mapping_body, "ERROR_ALREADY_EXISTS",
            "Capture3 mapping name collision must fail closed")
    if "g_capture_capacity" in native:
        raise AssertionError(
            "Capture3 still tracks resize capacity and may recreate named mappings"
        )
    if "UnmapViewOfFile(g_capture_header)" in mapping_body:
        raise AssertionError(
            "Capture3 fixed mapping must not unmap/recreate on client size changes"
        )

    capture_body = native.split("LONG dispatch_capture", 1)[1].split(
        "LONG dispatch_touch", 1
    )[0]
    require(capture_body, "header->status = 1;",
            "Capture3 writer must publish in-progress status")
    require(capture_body, "header->width = width;",
            "Capture3 writer dimensions missing")
    if capture_body.index("header->status = 1;") > capture_body.index("header->width = width;"):
        raise AssertionError(
            "Capture3 writer must publish status=1 before changing frame metadata"
        )
    require(capture_body, "MemoryBarrier();",
            "Capture3 writer memory barrier missing")
    if capture_body.rindex("header->status = 2;") < capture_body.index("header->frame_id = frame;"):
        raise AssertionError(
            "Capture3 writer must publish completed status only after frame id"
        )

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
    require(worker, '"NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP"',
            "Worker must require the synchronized fixed-map bridge revision")
    require(worker, "engine_driver._PROTOCOL_PREFIX = _REQUIRED_BRIDGE_PROTOCOL",
            "Worker must install the strict resident Bridge V3 revision gate")
    require(worker, "from shared_runtime.image_runtime import install_binary_dependencies",
            "Worker must use the shared clean image runtime")
    require(worker, "install_binary_dependencies(root, logger=bootstrap_log)",
            "Worker shared image bootstrap call missing")
    if 'importlib.import_module("local_launcher")' in worker:
        raise AssertionError(
            "AUTO MULTI DEV must not bootstrap through legacy local_launcher"
        )
    require(worker, "adaptive_cv.install_adaptive_matching()",
            "Worker must complete adaptive OpenCV initialization")
    require(worker, "image_runtime_ready=True",
            "Clean workflow must reuse worker-prepared image modules")
    require(worker, "KVAutomation(", "Worker must own KVAutomation")
    require(worker, "AutoMainWorkflow(automation).run()",
            "Worker must own the complete main workflow")
    require(worker, "result_payload = result.to_dict()",
            "AUTO MULTI DEV result payload normalization missing")
    require(worker, 'result_payload.pop("profile_id", None)',
            "AUTO MULTI DEV result event may duplicate profile_id")
    if "**result.to_dict()" in worker:
        raise AssertionError(
            "AUTO MULTI DEV worker expands result profile_id directly into emit"
        )

    require(shared_image, 'importlib.import_module("PIL._imaging")',
            "Shared runtime must preload Pillow native extension")
    require(shared_image, 'importlib.import_module("cv2")',
            "Shared runtime must load OpenCV")
    require(shared_image, 'importlib.import_module("numpy")',
            "Shared runtime must load NumPy")
    require(shared_image, "_FORBIDDEN_BUSINESS_MODULES",
            "Shared runtime must guard against AUTO PRO business imports")
    require(shared_image, "không gọi local_launcher",
            "Shared runtime must document local_launcher isolation")

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
    print("protocol=KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP")
    print("capture3_writer=status-first-seqlock")
    print("capture3_mapping=fixed-lifetime-64m")
    print("capture3_reader=dimension-handoff-retry")
    print("resident_bridge=revision-gated")
    print("worker_result_emit=profile-id-normalized")
    print("image_runtime=shared-clean local_launcher=false")
    print("legacy_capture1_fallback=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())