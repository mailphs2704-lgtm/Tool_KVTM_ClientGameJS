from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "components/clientjs-auto/kvtm_automation/runtime/driver.py"
ENGINE = ROOT / "test-candidates/auto-pro-clientjs-temp/engine_driver.py"
NATIVE = ROOT / "bridge-v3/native/kvtm_bridge_v3.cpp"
PACKAGE = ROOT / "packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
CAPTURE_ADAPTER = ROOT / "components/clientjs-auto/worker/capture3_same_request.py"
SHARED_IMAGE = ROOT / "components/clientjs-auto/shared_runtime/image_runtime.py"
ENTRY = ROOT / "source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py"


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def main() -> int:
    texts = {}
    paths = (
        FACTORY,
        ENGINE,
        NATIVE,
        PACKAGE,
        WORKER,
        CAPTURE_ADAPTER,
        SHARED_IMAGE,
        ENTRY,
    )
    for path in paths:
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
    capture_adapter = texts[CAPTURE_ADAPTER]
    shared_image = texts[SHARED_IMAGE]
    entry = texts[ENTRY]

    required_tokens = (
        "KVTM_BRIDGE_V3",
        "CAPTURE3",
        "INPUT4",
        "BATCH_SWIPE",
        "NO_LAYOUT",
        "CAPTURE3_SYNC2",
        "CAPTURE3_FIXEDMAP",
        "CAPTURE3_WRITERMAP2",
    )
    require(factory, '_load_module("engine_driver")',
            "Multi Dev does not select EngineDriver V3")
    require(factory, 'driver._pipe("PING\\n", 1000)',
            "Strict V3 PING gate missing")
    for token in required_tokens:
        require(factory, token, f"Factory V3 capability gate missing: {token}")
        require(native, token, f"Native V3 capability missing: {token}")

    require(factory, "ClientJS đang giữ Bridge V3 resident cũ",
            "Stale resident Bridge V3 fail-closed message missing")
    require(factory, '"CAPTURE3_WRITERMAP2"',
            "Factory must reject pre-writer-map resident V3 binaries")

    if "CocosBridgeDriver(" in factory or "kvtm_bridge.dll" in factory:
        raise AssertionError("AUTO MULTI DEV still wires the legacy CAPTURE1 bridge")

    # Shared EngineDriver remains compatible with legacy CAPTURE for other
    # packaged consumers. Multi Dev replaces only _capture_shared_bgra with the
    # writer-bound CAPTUREW adapter before KVAutomation constructs the driver.
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
    require(engine, "with self._pipe_lock:",
            "V3 capture must hold the pipe lock through shared-memory copy")
    require(engine, "verified_key != snapshot_key",
            "Legacy Capture3 seqlock post-copy verification missing")

    # WRITERMAP2 root contract: one native module generation owns a unique
    # mapping and the CAPTUREW response carries that exact writer identity.
    require(native, "ULONGLONG g_writer_id = 0;",
            "Native writer generation id missing")
    require(native, "initialize_writer_id()",
            "Native writer id initialization missing")
    require(native, "Local\\\\KVTM-BridgeV3-Owner-%lu",
            "Per-PID native writer owner mutex missing")
    require(native, "ERROR_ALREADY_EXISTS",
            "Native duplicate ownership/mapping collision must fail closed")
    require(native, "FILE_FLAG_FIRST_PIPE_INSTANCE",
            "Named pipe must reject a competing first server instance")
    require(native, "g_writer_capture_mapping",
            "Writer-generation mapping handle missing")
    require(native, "g_writer_capture_header",
            "Writer-generation mapping header missing")
    require(native, "g_writer_capture_frame",
            "Writer-generation frame counter missing")
    require(native, 'L"Local\\\\KVTM-CaptureV3-%lu-%016llX"',
            "Writer-generation mapping name must include writer id")
    require(native, "kCaptureMappingBytes, name",
            "Capture3 mappings must keep fixed maximum capacity")
    require(native, "command->mapping_mode == kCaptureModeWriterMap",
            "Native capture dispatch must distinguish writer mapping mode")
    require(native, "command->writer_id = command->mapping_mode == kCaptureModeWriterMap",
            "Actual capture writer id must be returned by dispatch")
    require(native, 'std::strncmp(input, "CAPTUREW", 8)',
            "Writer-bound CAPTUREW command missing")
    require(native, '"OK FRAMEW %lu %lu %lu %lu %016llX\\n"',
            "CAPTUREW response must include writer identity")
    require(native, "command.writer_id == g_writer_id",
            "Pipe must reject a response produced by another writer")
    require(native, '"ERR WRITER %016llX %016llX\\n"',
            "Writer mismatch diagnostic missing")
    require(native, 'std::strncmp(input, "CAPTURE", 7)',
            "Legacy CAPTURE compatibility command missing")
    require(native, '"OK FRAME %lu %lu %lu %lu\\n"',
            "Legacy CAPTURE response changed unexpectedly")

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

    # Multi Dev reader must never fall back to the PID-only mapping. It requests
    # CAPTUREW once, validates a 16-hex writer id and opens only that generation.
    require(capture_adapter, 'self._pipe("CAPTUREW\\n", 3000)',
            "Multi Dev must request writer-bound CAPTUREW")
    require(capture_adapter, '["OK", "FRAMEW"]',
            "CAPTUREW response marker validation missing")
    require(capture_adapter, "_WRITER_ID_RE",
            "Writer id shape validation missing")
    require(capture_adapter, 'rf"Local\\KVTM-CaptureV3-{int(self.pid)}-{writer_id}"',
            "Reader must open the writer-generation mapping")
    require(capture_adapter, "frame_id < expected_frame",
            "Writer-map reader stale-frame rejection missing")
    require(capture_adapter, "frame_id > expected_frame",
            "Writer-map reader must reject an out-of-request newer frame")
    require(capture_adapter, "verified_key == snapshot_key",
            "Writer-map post-copy seqlock verification missing")
    require(capture_adapter, "không phát request mới và không đổi writer",
            "Writer-map retry must stay on one request and one writer")
    if 'self._pipe("CAPTURE\\n"' in capture_adapter:
        raise AssertionError(
            "AUTO MULTI DEV writer-bound adapter regressed to PID-only CAPTURE"
        )
    if "self.capture_mapping_name" in capture_adapter:
        raise AssertionError(
            "AUTO MULTI DEV must not open the legacy PID-only mapping"
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
    require(worker,
            '"NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2"',
            "Worker must require writer-bound synchronized Bridge V3 revision")
    require(worker, "engine_driver._PROTOCOL_PREFIX = _REQUIRED_BRIDGE_PROTOCOL",
            "Worker must install the strict resident Bridge V3 revision gate")
    require(worker, "install_capture3_same_request_wait(engine_driver)",
            "Worker must install writer-bound capture adapter")
    require(worker, "CAPTURE3 WRITERMAP2 ENABLED",
            "Live writer-map revision marker missing")
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
    require(worker, "AutoMainWorkflow(automation).run()",
            "Worker must own the complete main workflow")
    require(worker, "result_payload = result.to_dict()",
            "AUTO MULTI DEV result payload normalization missing")
    require(worker, 'result_payload.pop("profile_id", None)',
            "AUTO MULTI DEV result event may duplicate profile_id")

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
    print(
        "protocol=KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT "
        "CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2"
    )
    print("capture3_writer=status-first-seqlock writer-id-bound")
    print("capture3_mapping=legacy-fixed-plus-writer-generation-fixed-64m")
    print("capture3_reader=one-CAPTUREW-one-writer-exact-frame")
    print("bridge_owner=pid-mutex first-pipe-instance")
    print("resident_bridge=revision-gated")
    print("worker_result_emit=profile-id-normalized")
    print("image_runtime=shared-clean local_launcher=false")
    print("legacy_capture1_fallback=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
