from __future__ import annotations


__all__ = ["configure_step"]
FILE_FUNCTIONS = (
    "Cấu hình module Vào game/Bán VP/Function",
    "Chọn ảnh nhận diện và vùng tìm",
    "Cấu hình Click/Swipe/Wait",
    "Cấu hình block kết thúc PASS/FAIL",
)


def configure_step(core, store, parent, step: dict) -> dict | None:
    """Edit one Builder block with native Multi DEV dialogs."""
    step_type = str(step.get("type") or "")
    try:
        if step_type == "enter_game_popup":
            timeout = core.simpledialog.askfloat(
                "Vào game + đóng popup",
                "Timeout tối đa (giây):",
                initialvalue=float(step.get("timeout", 180.0)),
                minvalue=1.0,
                maxvalue=600.0,
                parent=parent,
            )
            if timeout is None:
                return None
            step["timeout"] = float(timeout)
        elif step_type == "sell_function_vp":
            step["function_id"] = "function_1"
            timeout = core.simpledialog.askfloat(
                "Bán VP theo Function 1",
                "Timeout đưa về main/mở quầy (giây):",
                initialvalue=float(step.get("timeout", 120.0)),
                minvalue=1.0,
                maxvalue=600.0,
                parent=parent,
            )
            if timeout is None:
                return None
            step["timeout"] = float(timeout)
        elif step_type == "function":
            loops = core.simpledialog.askinteger(
                "Function 1",
                "Số vòng Function 1:",
                initialvalue=int(step.get("loops", 1) or 1),
                minvalue=1,
                maxvalue=999,
                parent=parent,
            )
            if loops is None:
                return None
            step["function_id"] = "function_1"
            step["loops"] = int(loops)
            step["sale_after_each_loop"] = bool(core.messagebox.askyesno(
                "Function 1",
                "Sau MỖI vòng hoàn tất, gọi module Bán VP theo Function 1?",
                parent=parent,
            ))
            step["sale_timeout"] = 120.0
        elif step_type == "recognize_image":
            chosen = core.filedialog.askopenfilename(
                parent=parent,
                title="Chọn ảnh nhận diện cho AUTO Builder",
                filetypes=[
                    ("Ảnh", "*.png *.jpg *.jpeg *.bmp *.webp"),
                    ("Tất cả", "*.*"),
                ],
            )
            if chosen:
                step["template_path"] = str(store.import_asset(chosen))
            elif not step.get("template_path"):
                return None
            threshold = core.simpledialog.askfloat(
                "Nhận diện ảnh",
                "Threshold (0.10 - 1.00):",
                initialvalue=float(step.get("threshold", 0.80)),
                minvalue=0.10,
                maxvalue=1.00,
                parent=parent,
            )
            if threshold is None:
                return None
            step["threshold"] = float(threshold)
            zone_text = core.simpledialog.askstring(
                "Nhận diện ảnh",
                "Vùng tìm x,y,w,h. Để trống = toàn màn hình:",
                initialvalue=(
                    ",".join(map(str, step.get("zone"))) if step.get("zone") else ""
                ),
                parent=parent,
            )
            if zone_text is None:
                return None
            zone_text = zone_text.strip()
            if zone_text:
                zone = [int(part.strip()) for part in zone_text.split(",")]
                if len(zone) != 4:
                    raise ValueError("Zone phải có đúng 4 số x,y,w,h")
                x, y, w, h = zone
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x > 1000 or y > 1000:
                    raise ValueError("Zone phải nằm trong không gian ClientJS 0..1000")
                step["zone"] = zone
            else:
                step.pop("zone", None)
            step["scales"] = [1.0]
            step["on_fail"] = "stop"
        elif step_type == "click":
            for key, label in (("x", "X"), ("y", "Y")):
                value = core.simpledialog.askinteger(
                    "Click",
                    f"{label} (0..1000):",
                    initialvalue=int(step.get(key, 500) or 0),
                    minvalue=0,
                    maxvalue=1000,
                    parent=parent,
                )
                if value is None:
                    return None
                step[key] = int(value)
        elif step_type == "swipe":
            defaults = {"x1": 500, "y1": 700, "x2": 500, "y2": 300}
            for key in ("x1", "y1", "x2", "y2"):
                value = core.simpledialog.askinteger(
                    "Swipe",
                    f"{key.upper()} (0..1000):",
                    initialvalue=int(step.get(key, defaults[key])),
                    minvalue=0,
                    maxvalue=1000,
                    parent=parent,
                )
                if value is None:
                    return None
                step[key] = int(value)
            duration = core.simpledialog.askfloat(
                "Swipe",
                "Thời lượng swipe (giây):",
                initialvalue=float(step.get("duration", 0.35)),
                minvalue=0.01,
                maxvalue=10.0,
                parent=parent,
            )
            if duration is None:
                return None
            step["duration"] = float(duration)
        elif step_type == "wait":
            seconds = core.simpledialog.askfloat(
                "Wait",
                "Chờ bao nhiêu giây?",
                initialvalue=float(step.get("seconds", 0.5)),
                minvalue=0.0,
                maxvalue=300.0,
                parent=parent,
            )
            if seconds is None:
                return None
            step["seconds"] = float(seconds)
        elif step_type == "finish_pass":
            pass
        elif step_type == "finish_fail":
            message = core.simpledialog.askstring(
                "Kết thúc FAIL",
                "Nội dung lỗi:",
                initialvalue=str(step.get("message") or "AUTO Builder kết thúc FAIL"),
                parent=parent,
            )
            if message is None:
                return None
            step["message"] = message
        else:
            raise ValueError(f"Block chưa hỗ trợ: {step_type}")
        return step
    except Exception as exc:
        core.messagebox.showerror(core.APP_NAME, f"Cấu hình bước không hợp lệ:\n{exc}")
        return None
