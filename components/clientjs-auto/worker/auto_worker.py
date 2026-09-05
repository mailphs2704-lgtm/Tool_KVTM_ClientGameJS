from __future__ import annotations

import argparse
import dis
import importlib
import json
import os
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
    none_attributes = []
    for name, value in frame.f_locals.items():
        local_types[name] = type(value).__name__
        if name == "self":
            try:
                none_attributes = sorted(
                    key for key, item in vars(value).items() if item is None
                )[:200]
            except Exception:
                none_attributes = []
            continue
        try:
            rendered = repr(value)
        except Exception:
            rendered = "<repr failed>"
        local_values[name] = rendered[:500]
    instructions = []
    nested_code = []
    try:
        for instruction in dis.get_instructions(frame.f_code):
            positions = getattr(instruction, "positions", None)
            line = getattr(positions, "lineno", None)
            if line is None:
                line = instruction.starts_line
            if line is not None and abs(int(line) - int(tb.tb_lineno)) <= 1:
                instructions.append({
                    "offset": instruction.offset,
                    "line": line,
                    "opname": instruction.opname,
                    "argrepr": instruction.argrepr,
                })
        for constant in frame.f_code.co_consts:
            if not hasattr(constant, "co_code"):
                continue
            if abs(int(getattr(constant, "co_firstlineno", 0)) - int(tb.tb_lineno)) > 1:
                continue
            nested_code.append({
                "name": constant.co_name,
                "first_line": constant.co_firstlineno,
                "names": list(constant.co_names),
                "instructions": [
                    {
                        "offset": item.offset,
                        "opname": item.opname,
                        "argrepr": item.argrepr,
                    }
                    for item in dis.get_instructions(constant)
                ][:80],
            })
    except Exception:
        instructions = []
        nested_code = []
    return {
        "source_file": frame.f_code.co_filename,
        "function": frame.f_code.co_name,
        "line": tb.tb_lineno,
        "local_types": local_types,
        "local_values": local_values,
        "none_attributes": none_attributes,
        "instructions": instructions[:80],
        "nested_code": nested_code,
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


def install_clientjs_runtime(auto_root: Path, profile_id: str):
    """Bootstrap bundled dependencies, then lock every PC transport alias."""
    sys.path.insert(0, str(auto_root))

    # local_launcher exposes AUTO_PRO/_internal where uiautomator2 is bundled.
    # It must run before importing uiautomator2 in the system Python worker.
    importlib.import_module("local_launcher")

    import uiautomator2 as u2
    from engine_driver import EngineDriver

    original_connect = u2.connect

    # Resolve the exact profile/PID and Bridge V3 before recovered AUTO wraps
    # connection errors in its generic ADB/BlueStacks message. One worker owns
    # one driver instance, so concurrent accounts cannot exchange transports.
    profile_driver = EngineDriver(str(profile_id), reference_size=(1000, 1000))
    emit(
        "pc_transport_ready",
        profile_id=str(profile_id),
        pid=int(profile_driver.pid),
        driver_type=type(profile_driver).__name__,
        profile_storage="READ_ONLY",
    )

    def pc_connect(device_id=None, *args, **kwargs):
        value = str(device_id or "")
        if value.startswith("PC:"):
            return profile_driver
        return original_connect(device_id, *args, **kwargs)

    u2.connect = pc_connect
    importlib.import_module("pc_auto_launcher")
    u2.connect = pc_connect

    from adaptive_cv import install_adaptive_matching
    from clientjs_auto_patch import _install_controller_patch
    import adb_controller

    # Recovered bytecode may retain a from-import alias during bootstrap.
    for alias in ("connect", "u2_connect", "uiautomator_connect"):
        if hasattr(adb_controller, alias):
            setattr(adb_controller, alias, pc_connect)
    bound_u2 = getattr(adb_controller, "u2", None)
    if bound_u2 is not None and hasattr(bound_u2, "connect"):
        bound_u2.connect = pc_connect

    install_adaptive_matching()
    _install_controller_patch(adb_controller)
    u2.connect = pc_connect
    module = importlib.import_module("automation")

    # automation.pyc can retain a second module-local alias.
    for alias in ("connect", "u2_connect", "uiautomator_connect"):
        if hasattr(module, alias):
            setattr(module, alias, pc_connect)
    module_u2 = getattr(module, "u2", None)
    if module_u2 is not None and hasattr(module_u2, "connect"):
        module_u2.connect = pc_connect
    u2.connect = pc_connect
    return module



def install_headless_clientjs_runtime(auto_root: Path):
    """Load recovered AUTO PRO controller code without importing its GUI."""
    root = Path(auto_root).resolve()
    pyc = root / "runtime" / "pyc"
    internal = root / "_internal"
    for path in (
        pyc,
        internal,
        internal / "win32",
        internal / "win32" / "lib",
        internal / "Pythonwin",
        internal / "pywin32_system32",
        root,
    ):
        if path.exists():
            sys.path.insert(0, str(path))
    if hasattr(os, "add_dll_directory"):
        for path in (
            internal,
            internal / "cv2",
            internal / "numpy.libs",
            internal / "pywin32_system32",
            internal / "Pythonwin",
        ):
            if path.exists():
                try:
                    os.add_dll_directory(str(path))
                except OSError:
                    pass
    os.environ["PATH"] = os.pathsep.join((
        str(internal),
        str(root / "platform-tools"),
        os.environ.get("PATH", ""),
    ))

    import uiautomator2 as u2
    from engine_driver import EngineDriver
    from adaptive_cv import install_adaptive_matching
    from clientjs_auto_patch import _install_controller_patch
    import adb_controller

    install_adaptive_matching()
    _install_controller_patch(adb_controller)
    original_connect = u2.connect

    def pc_connect(device_id=None, *args, **kwargs):
        value = str(device_id or "")
        if value.startswith("PC:"):
            return EngineDriver(int(value[3:]), reference_size=(1000, 1000))
        return original_connect(device_id, *args, **kwargs)

    u2.connect = pc_connect
    return importlib.import_module("automation")


def discover_buy_sell_items(automation_module, automation) -> tuple[list[dict], str]:
    """Find AUTO PRO's own {name, image} catalog without inventing templates."""
    candidates = []
    visited = set()

    def inspect_mapping(owner: str, mapping) -> None:
        try:
            entries = list(mapping.items())
        except Exception:
            return
        for key, value in entries:
            identity = id(value)
            if identity in visited or not isinstance(value, (list, tuple)):
                continue
            visited.add(identity)
            if not value or not all(isinstance(item, dict) for item in value):
                continue
            if not all(
                isinstance(item.get("name"), str)
                and item.get("name").strip()
                and isinstance(item.get("image"), str)
                and item.get("image").strip()
                for item in value
            ):
                continue
            label = f"{owner}.{key}"
            lowered = label.lower()
            score = len(value)
            if "buy_sell" in lowered or "buysell" in lowered:
                score += 10000
            elif "sell" in lowered:
                score += 3000
            elif "item" in lowered:
                score += 1000
            normalized = [
                {"name": item["name"].strip(), "image": item["image"].strip()}
                for item in value
            ]
            candidates.append((score, label, normalized))

    inspect_mapping("automation", vars(automation))
    inspect_mapping("FarmAutomation", vars(type(automation)))
    inspect_mapping("automation_module", vars(automation_module))
    for module_name, module in tuple(sys.modules.items()):
        lowered = str(module_name).lower()
        if not any(token in lowered for token in ("automation", "gui", "item")):
            continue
        try:
            inspect_mapping(module_name, vars(module))
        except Exception:
            continue
    if not candidates:
        return [], ""
    candidates.sort(key=lambda row: (row[0], len(row[2])), reverse=True)
    _score, source, items = candidates[0]
    unique = []
    seen = set()
    for item in items:
        signature = (item["name"], item["image"])
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(item)
    return unique, source


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
    parser.add_argument("--profile-file", required=True)
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
    boolean_option_keys = {
        "Xoa_vp_kc", "open_chest", "auto_quay_he", "auto_nang_kho",
        "thue_tom", "giao_cu", "san_xuat_ngoc", "sx_event_cam",
        "sell_all",
    }
    upgrade_option_keys = {
        "auto_nang_kho_type", "auto_nang_kho_time_hours",
        "auto_nang_kho_balance", "kc_nang_kho",
    }
    allowed_option_keys = (
        boolean_option_keys | {
            "skip_items", "quay_he_count", "num_friend_for_bsf",
            "buy_sell_friend_kho_id", "clear_stall_quantity",
            "clear_stall_max_pages", "go_friend_home",
        } | upgrade_option_keys
    )
    unknown = set(requested_options) - allowed_option_keys
    if unknown:
        emit("worker_error", error=f"Options không được hỗ trợ: {sorted(unknown)}")
        return 2
    requested_skip_items = requested_options.get("skip_items", [])
    if not isinstance(requested_skip_items, list) or not all(
        isinstance(item, str) and item.strip() for item in requested_skip_items
    ):
        emit("worker_error", error="skip_items phải là danh sách tên vật phẩm")
        return 2
    skip_items = list(dict.fromkeys(
        item.strip() for item in requested_skip_items
    ))
    try:
        quay_he_count = int(requested_options.get("quay_he_count", 1))
    except (TypeError, ValueError):
        emit("worker_error", error="quay_he_count phải là số nguyên")
        return 2
    if not 1 <= quay_he_count <= 100:
        emit("worker_error", error="quay_he_count phải trong khoảng 1..100")
        return 2
    auto_nang_kho_type = str(
        requested_options.get("auto_nang_kho_type", "Kho 1 & 2")
    )
    allowed_nang_kho_types = {"Kho 1", "Kho 2", "Kho 1 & 2", "Max Kho"}
    if auto_nang_kho_type not in allowed_nang_kho_types:
        emit("worker_error", error="auto_nang_kho_type không hợp lệ")
        return 2
    try:
        auto_nang_kho_time_hours = int(
            requested_options.get("auto_nang_kho_time_hours", 2)
        )
    except (TypeError, ValueError):
        emit("worker_error", error="auto_nang_kho_time_hours phải là số nguyên")
        return 2
    if not 1 <= auto_nang_kho_time_hours <= 168:
        emit("worker_error", error="auto_nang_kho_time_hours phải trong khoảng 1..168")
        return 2
    auto_nang_kho_balance = bool(
        requested_options.get("auto_nang_kho_balance", True)
    )
    kc_nang_kho = bool(requested_options.get("kc_nang_kho", False))
    auto_options = {
        key: bool(requested_options.get(key, False))
        for key in boolean_option_keys
    }
    clear_stall_limits = {
        "num_friend_for_bsf": (1, 500, 1),
        "buy_sell_friend_kho_id": (1, 4, 2),
        "clear_stall_quantity": (1, 999, 8),
        "clear_stall_max_pages": (1, 50, 10),
    }
    clear_stall_values = {}
    try:
        for key, (minimum, maximum, default) in clear_stall_limits.items():
            value = int(requested_options.get(key, default))
            if not minimum <= value <= maximum:
                raise ValueError(f"{key} phải từ {minimum} đến {maximum}")
            clear_stall_values[key] = value
    except (TypeError, ValueError) as exc:
        emit("worker_error", error=f"Cấu hình Dọn quầy không hợp lệ: {exc}")
        return 2
    auto_options.update(clear_stall_values)
    auto_options["go_friend_home"] = bool(
        requested_options.get("go_friend_home", False)
    )
    nang_kho_type_code = {
        "Kho 1": 1,
        "Kho 2": 2,
        "Max Kho": 3,
        "Kho 1 & 2": 4,
    }[auto_nang_kho_type]
    auto_options.update({
        "quay_he_count": quay_he_count,
        # Keep UI keys for diagnostics while also binding the exact option
        # names consumed by recovered FarmAutomation.Tuychon bytecode.
        "auto_nang_kho_type": auto_nang_kho_type,
        "auto_nang_kho_type_code": nang_kho_type_code,
        "auto_nang_kho_time_hours": auto_nang_kho_time_hours,
        "time_nang_kho": auto_nang_kho_time_hours,
        "auto_nang_kho_balance": auto_nang_kho_balance,
        "balance_nang_kho": auto_nang_kho_balance,
        "kc_nang_kho": kc_nang_kho,
    })

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

    allowed_function_ids = {98, 136, 170, 318}
    if args.function_id not in allowed_function_ids:
        emit(
            "worker_error",
            error=f"Worker thử nghiệm không cho phép Function {args.function_id}",
        )
        return 2

    auto_root = Path(args.auto_root).resolve()
    profile_file = Path(args.profile_file).resolve()
    if not profile_file.is_file():
        emit("worker_error", error=f"Không tìm thấy profile DEV chỉ-đọc: {profile_file}")
        return 2
    os.environ["KVTM_MULTI_PROFILE_FILE"] = str(profile_file)
    try:
        automation_module = install_clientjs_runtime(auto_root, args.profile_id)
        automation_class = automation_module.FarmAutomation
        entrypoint_name = f"produceItems_{args.function_id}"
        entrypoint = getattr(automation_class, entrypoint_name, None)
        if not callable(entrypoint):
            raise RuntimeError(f"Thiếu FarmAutomation.{entrypoint_name}")

        proxy = GuiProxy()
        constructor_tuning = {
            key: value for key, value in auto_tuning.items()
            if key != "shop_drag_speed"
        }
        clear_stall_constructor = {}
        if args.function_id == 170:
            clear_stall_constructor = {
                "num_friend_for_bsf": clear_stall_values["num_friend_for_bsf"],
                "buy_sell_friend_kho_id": clear_stall_values["buy_sell_friend_kho_id"],
                "go_friend_home": auto_options["go_friend_home"],
            }
        automation = automation_class(
            f"PC:{args.pid}",
            args.function_id,
            gui_ref=proxy,
            options=auto_options,
            skip_items=skip_items,
            auto_nang_kho_type=nang_kho_type_code,
            auto_nang_kho_time_hours=auto_nang_kho_time_hours,
            auto_nang_kho_balance=auto_nang_kho_balance,
            kc_nang_kho=kc_nang_kho,
            **clear_stall_constructor,
            **constructor_tuning,
        )
        # The new Dọn quầy wrapper owns these limits. Recovered Function 170
        # can read them when supported; keeping them on both objects also
        # makes runtime patching independent from constructor signatures.
        automation.clear_stall_quantity = clear_stall_values["clear_stall_quantity"]
        automation.clear_stall_max_pages = clear_stall_values["clear_stall_max_pages"]
        if args.function_id == 170 and getattr(automation, "buy_sell_items", None) is None:
            discovered_items, catalog_source = discover_buy_sell_items(
                automation_module, automation
            )
            if not discovered_items:
                raise RuntimeError(
                    "Không tìm được danh mục {name, image} của Function 170; "
                    "đã dừng trước khi mua/bán"
                )
            automation.buy_sell_items = discovered_items
            emit(
                "log",
                message=(
                    f"Dọn quầy: nạp {len(discovered_items)} vật phẩm "
                    f"từ {catalog_source}"
                ),
            )
        controller = getattr(automation, "adb", None)
        # Recovered workflows do not have one consistent owner for tuning:
        # some read FarmAutomation, others read ADBController. Keep both views
        # synchronized so one Multi setting has one effective value everywhere.
        for key, value in auto_tuning.items():
            setattr(automation, key, value)
            if controller is not None:
                setattr(controller, key, value)
        if controller is not None:
            # openChests has its own runtime kill-switch. Bind it explicitly so
            # a new worker always reflects the current Multi option.
            controller.open_chests_enabled = bool(auto_options["open_chest"])
            controller.clear_stall_quantity = clear_stall_values["clear_stall_quantity"]
            controller.clear_stall_max_pages = clear_stall_values["clear_stall_max_pages"]
            driver = getattr(controller, "driver", None)
            if driver is not None:
                driver.gesture_observer = lambda timing: emit(
                    "gesture_timing", **timing
                )
        if args.function_id == 170:
            # Function 170 already owns the purchase -> return -> resale flow.
            # Bind the new per-clone controls to the counters it reads so the
            # run is not limited to the legacy first eight visible slots.
            quantity = clear_stall_values["clear_stall_quantity"]
            scan_pages = clear_stall_values["clear_stall_max_pages"]
            automation.max_sell_times = quantity
            automation.swipe_count = scan_pages
            if controller is not None:
                controller.max_sell_times = quantity
                controller.swipe_count = scan_pages
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
                profile_name=args.profile_name, function_id=args.function_id,
                options={**auto_options, "skip_items": skip_items},
                tuning=auto_tuning,
            )
            friend_home_failures = 0
            client_reset_used = False
            while True:
                try:
                    automation.start()
                    break
                except Exception as exc:
                    error_text = str(exc).casefold()
                    friend_home_failure = any(
                        marker in error_text
                        for marker in (
                            "nhà bạn", "nha ban", "friend",
                            "màn hình chính", "man hinh chinh", "main screen",
                        )
                    )
                    if not friend_home_failure or stop_event.is_set():
                        raise
                    friend_home_failures += 1
                    emit(
                        "log",
                        message=(
                            "AUTO chính: lỗi qua/thoát nhà bạn "
                            f"{friend_home_failures}/3 • {exc}"
                        ),
                    )
                    if friend_home_failures < 3:
                        continue
                    if client_reset_used:
                        raise RuntimeError(
                            "AUTO chính vẫn lỗi qua/thoát nhà bạn sau một lần reset ClientJS"
                        ) from exc

                    current_controller = getattr(automation, "adb", None)
                    current_driver = getattr(current_controller, "driver", None)
                    if current_controller is None or current_driver is None:
                        raise RuntimeError(
                            "Không có driver ClientJS để reset sau 3 lỗi nhà bạn"
                        ) from exc
                    emit(
                        "log",
                        message=(
                            "AUTO chính: đủ 3 lỗi nhà bạn • reset đúng ClientJS "
                            "và nhận lại bằng profile_id + PID + 3 frame hợp lệ"
                        ),
                    )
                    current_driver.app_stop("vn.kvtm.js")
                    if stop_event.is_set():
                        break
                    time.sleep(1.0)
                    current_driver.app_start("vn.kvtm.js")
                    current_controller.openGame(stop_event)
                    client_reset_used = True
                    friend_home_failures = 0
        except Exception as exc:
            outcome["error"] = repr(exc)
            emit(
                "worker_error",
                error=repr(exc),
                traceback=traceback.format_exc(),
                diagnostics=exception_frame_diagnostics(exc),
            )
        finally:
            finished.set()

    commands: queue.Queue = queue.Queue()
    threading.Thread(target=command_reader, args=(commands,), daemon=True).start()
    task = threading.Thread(target=run_auto, daemon=True)
    task.start()

    reported_client_pid = int(
        getattr(getattr(controller, "driver", None), "pid", args.pid)
    )
    while not finished.wait(0.20):
        current_driver = getattr(controller, "driver", None)
        current_client_pid = int(getattr(current_driver, "pid", reported_client_pid))
        if current_client_pid != reported_client_pid:
            emit(
                "client_pid_changed",
                profile_id=args.profile_id,
                function_id=args.function_id,
                old_pid=reported_client_pid,
                new_pid=current_client_pid,
            )
            reported_client_pid = current_client_pid
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
                setattr(automation, key, value)
                setattr(controller, key, value)
                auto_tuning[key] = value
            emit(
                "tuning_applied",
                tuning=dict(auto_tuning),
                synchronized_targets=["FarmAutomation", "ADBController"],
            )
        elif action in {"stop", "pause"}:
            emit("worker_stopping", reason=action)
            try:
                automation.stop()
            except Exception as exc:
                emit("log", message=f"Lỗi khi dừng: {exc!r}")

    task.join(timeout=5.0)
    if outcome["error"]:
        return 1
    emit(
        "worker_finished", profile_id=args.profile_id,
        function_id=args.function_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
