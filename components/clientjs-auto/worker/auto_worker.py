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
    parser.add_argument("--options-json", default="{}")
    parser.add_argument("--tuning-json", default="{}")
    args = parser.parse_args()

    try:
        requested_options = json.loads(args.options_json)
    except json.JSONDecodeError as exc:
        emit("worker_error", error=f"Options JSON không hợp lệ: {exc}")
        return 2
    if not isinstance(requested_options, dict):
        emit("worker_error", error="Options JSON phải là object")
        return 2
    allowed_option_keys = {
        "Xoa_vp_kc", "open_chest", "auto_quay_he", "auto_nang_kho",
        "thue_tom", "giao_cu", "san_xuat_ngoc", "sx_event_cam",
        "sell_all",
    }
    # Reject unknown fields and normalize every supported switch to bool.
    unknown = set(requested_options) - allowed_option_keys
    if unknown:
        emit("worker_error", error=f"Options không được hỗ trợ: {sorted(unknown)}")
        return 2
    auto_options = {
        key: bool(requested_options.get(key, False))
        for key in allowed_option_keys
    }

    tuning_defaults = {
        "harvest_speed": 0.045,
        "go_up_wait": 0.7,
        "production_wait": 0.4,
        "swipe_count": 4,
        "quay_speed": 0.5,
        "shop_drag_speed": 0.35,
        "speed_sell_item": 0.5,
        "check_harvest": 0.3,
        "click_speed": 0.3,
        "delete_check_speed": 0.5,
        "next_gieo": 0.4,
        "delete_count": 10,
        "max_sell_times": 1,
        "collect_gold_speed": 0.4,
        "check_nang_kho": 0.5,
        "delay_vao_game": 55,
    }
    integer_tuning = {"swipe_count", "delete_count", "max_sell_times", "delay_vao_game"}
    tuning_ranges = {
        "harvest_speed": (0.01, 3.0),
        "go_up_wait": (0.05, 10.0),
        "production_wait": (0.05, 10.0),
        "swipe_count": (1, 20),
        "quay_speed": (0.05, 5.0),
        "shop_drag_speed": (0.05, 3.0),
        "speed_sell_item": (0.05, 5.0),
        "check_harvest": (0.05, 5.0),
        "click_speed": (0.02, 5.0),
        "delete_check_speed": (0.05, 5.0),
        "next_gieo": (0.05, 5.0),
        "delete_count": (1, 100),
        "max_sell_times": (1, 50),
        "collect_gold_speed": (0.05, 5.0),
        "check_nang_kho": (0.05, 10.0),
        "delay_vao_game": (0, 300),
    }
    try:
        requested_tuning = json.loads(args.tuning_json)
    except json.JSONDecodeError as exc:
        emit("worker_error", error=f"Tuning JSON không hợp lệ: {exc}")
        return 2
    if not isinstance(requested_tuning, dict):
        emit("worker_error", error="Tuning JSON phải là object")
        return 2
    unknown_tuning = set(requested_tuning) - set(tuning_defaults)
    if unknown_tuning:
        emit("worker_error", error=f"Thông số tốc độ không hỗ trợ: {sorted(unknown_tuning)}")
        return 2
    auto_tuning = dict(tuning_defaults)
    try:
        for key, raw_value in requested_tuning.items():
            value = int(raw_value) if key in integer_tuning else float(raw_value)
            minimum, maximum = tuning_ranges[key]
            if not minimum <= value <= maximum:
                raise ValueError(f"{key} phải từ {minimum} đến {maximum}")
            auto_tuning[key] = value
    except (TypeError, ValueError) as exc:
        emit("worker_error", error=f"Thông số tốc độ không hợp lệ: {exc}")
        return 2

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
        constructor_tuning = {
            key: value for key, value in auto_tuning.items()
            if key != "shop_drag_speed"
        }
        automation = automation_class(
            f"PC:{args.pid}",
            136,
            gui_ref=proxy,
            options=auto_options,
            **constructor_tuning,
        )
        controller = getattr(automation, "adb", None)
        if controller is not None:
            controller.shop_drag_speed = auto_tuning["shop_drag_speed"]
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
                options=auto_options, tuning=auto_tuning,
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
        if action == "update_tuning":
            requested_update = command.get("tuning")
            if not isinstance(requested_update, dict):
                emit("tuning_error", error="Tuning cập nhật phải là object")
                continue
            unknown_update = set(requested_update) - set(tuning_defaults)
            if unknown_update:
                emit(
                    "tuning_error",
                    error=f"Thông số tốc độ không hỗ trợ: {sorted(unknown_update)}",
                )
                continue
            try:
                validated_update = {}
                for key, raw_value in requested_update.items():
                    value = int(raw_value) if key in integer_tuning else float(raw_value)
                    minimum, maximum = tuning_ranges[key]
                    if not minimum <= value <= maximum:
                        raise ValueError(f"{key} phải từ {minimum} đến {maximum}")
                    validated_update[key] = value
            except (TypeError, ValueError) as exc:
                emit("tuning_error", error=f"Thông số tốc độ không hợp lệ: {exc}")
                continue

            # Validate the complete payload first, then expose the new values.
            # Individual Python attribute assignments are atomic, so the AUTO
            # thread can safely read them at its next operation/checkpoint.
            controller = getattr(automation, "adb", None)
            if controller is None:
                emit("tuning_error", error="AUTO chưa có ADBController")
                continue
            for key, value in validated_update.items():
                setattr(controller, key, value)
                auto_tuning[key] = value
            emit("tuning_applied", tuning=dict(auto_tuning))
        elif action in {"stop", "pause"}:
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
