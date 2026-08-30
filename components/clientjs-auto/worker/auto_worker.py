from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import traceback


def configure_utf8_stdio() -> None:
    """Keep Vietnamese AUTO PRO messages safe on Windows pipe consoles."""
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


configure_utf8_stdio()


def emit(event: str, **data) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def exception_frame_diagnostics(exc: BaseException) -> dict:
    """Return safe locals from the deepest recovered-runtime traceback frame."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return {}
    frame = tb.tb_frame
    local_types = {}
    local_values = {}
    for name, value in frame.f_locals.items():
        local_types[name] = type(value).__name__
        if name == "self":
            continue
        try:
            rendered = repr(value)
        except Exception:
            rendered = "<repr failed>"
        local_values[name] = rendered[:500]
    return {
        "source_file": frame.f_code.co_filename,
        "function": frame.f_code.co_name,
        "line": tb.tb_lineno,
        "local_types": local_types,
        "local_values": local_values,
    }


class GuiProxy:
    """Minimal GUI contract consumed by the recovered FarmAutomation runtime."""

    def log(self, message, device_id=None, **_kwargs):
        emit("log", message=str(message), device_id=str(device_id or ""))

    def update_task_progress(self, device_id, progress):
        emit("progress", message=str(progress), device_id=str(device_id or ""))

    def update_task_stats(self, device_id, total, current_date=None):
        emit(
            "stats", device_id=str(device_id or ""), total=total,
            current_date=str(current_date or ""),
        )

    def __getattr__(self, name):
        def no_op(*_args, **_kwargs):
            emit("gui_callback", name=name)
            # Recovered AUTO PRO reads optional GUI settings with
            # gui_callback(...).get(key, default). An empty mapping keeps
            # those built-in defaults active in the headless Multi worker.
            return {}
        return no_op


def install_clientjs_runtime(auto_root: Path):
    sys.path.insert(0, str(auto_root))
    importlib.import_module("local_launcher")

    import uiautomator2 as u2
    from engine_driver import EngineDriver
    from adaptive_cv import install_adaptive_matching
    from clientjs_auto_patch import install_clientjs_auto_patch

    install_adaptive_matching()
    install_clientjs_auto_patch()

    original_connect = u2.connect

    def pc_connect(device_id=None, *args, **kwargs):
        value = str(device_id or "")
        if value.startswith("PC:"):
            return EngineDriver(int(value[3:]), reference_size=(1000, 1000))
        return original_connect(device_id, *args, **kwargs)

    u2.connect = pc_connect
    importlib.import_module("pc_auto_launcher")
    u2.connect = pc_connect
    return importlib.import_module("automation")


def command_reader(commands: queue.Queue) -> None:
    for line in sys.stdin:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        commands.put(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-root", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--function-id", type=int, default=136)
    args = parser.parse_args()

    if args.function_id != 136:
        emit("worker_error", error="Worker thử nghiệm chỉ cho phép Function 136")
        return 2

    auto_root = Path(args.auto_root).resolve()
    try:
        automation_module = install_clientjs_runtime(auto_root)
        automation_class = automation_module.FarmAutomation
        entrypoint = getattr(automation_class, "produceItems_136", None)
        if not callable(entrypoint):
            raise RuntimeError("Thiếu FarmAutomation.produceItems_136")

        proxy = GuiProxy()
        automation = automation_class(
            f"PC:{args.pid}",
            136,
            gui_ref=proxy,
            options={},
        )
    except Exception as exc:
        emit(
            "worker_error",
            error=repr(exc),
            traceback=traceback.format_exc(),
            diagnostics=exception_frame_diagnostics(exc),
        )
        return 1

    finished = threading.Event()
    outcome = {"error": None}

    def run_auto() -> None:
        try:
            emit(
                "worker_started", pid=args.pid, profile_id=args.profile_id,
                profile_name=args.profile_name, function_id=136,
            )
            automation.start()
        except Exception as exc:
            outcome["error"] = repr(exc)
            emit("worker_error", error=repr(exc), traceback=traceback.format_exc())
        finally:
            finished.set()

    commands: queue.Queue = queue.Queue()
    threading.Thread(target=command_reader, args=(commands,), daemon=True).start()
    task = threading.Thread(target=run_auto, daemon=True)
    task.start()

    while not finished.wait(0.20):
        try:
            command = commands.get_nowait()
        except queue.Empty:
            continue
        action = str(command.get("command") or "").lower()
        if action in {"stop", "pause"}:
            emit("worker_stopping", reason=action)
            try:
                automation.stop()
            except Exception as exc:
                emit("log", message=f"Lỗi khi dừng: {exc!r}")

    task.join(timeout=5.0)
    if outcome["error"]:
        return 1
    emit("worker_finished", profile_id=args.profile_id, function_id=136)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
