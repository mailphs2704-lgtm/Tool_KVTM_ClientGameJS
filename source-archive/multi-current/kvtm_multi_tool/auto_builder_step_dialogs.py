from __future__ import annotations

from pathlib import Path

from auto_builder_gesture_picker import pick_swipe_on_game


__all__ = ["configure_step"]
FILE_FUNCTIONS = (
    "Cấu hình module Vào game/Bán VP/Function có sẵn",
    "Chọn Function tự tạo đã lưu, số vòng và thời gian chờ giữa các vòng",
    "Chọn ảnh từ thư viện Multi DEV hoặc mục ảnh AUTO PRO",
    "Tự copy ảnh AUTO PRO được chọn vào thư viện Multi DEV",
    "Cấu hình Swipe nhiều điểm bằng kéo trực tiếp trên game hoặc nhập polyline",
    "Cấu hình Click/Wait và block kết thúc PASS/FAIL",
)


def _choose_saved_function(core, store, parent, initial_id: str = "") -> dict | None:
    functions = store.list_functions()
    if not functions:
        core.messagebox.showinfo(
            core.APP_NAME,
            "Chưa có Function tự tạo nào. Hãy bấm ‘＋ Function mới’ hoặc ‘📂 Load Function’ trong Builder trước.",
            parent=parent,
        )
        return None
    lines = [
        f"{index}. {item['name']}  [{item['function_id']}]"
        for index, item in enumerate(functions, start=1)
    ]
    initial_index = 1
    for index, item in enumerate(functions, start=1):
        if item["function_id"] == initial_id:
            initial_index = index
            break
    choice = core.simpledialog.askinteger(
        "Chọn Function đã lưu",
        "Chọn số Function:\n\n" + "\n".join(lines),
        initialvalue=initial_index,
        minvalue=1,
        maxvalue=len(functions),
        parent=parent,
    )
    if choice is None:
        return None
    return functions[int(choice) - 1]


def _choose_image_source(core, parent) -> str | None:
    """Return exactly one of ``multi_library`` / ``auto_pro`` from a native modal."""
    result = {"value": None}
    win = core.tk.Toplevel(parent)
    win.title("Nguồn ảnh nhận diện")
    win.geometry("520x210")
    win.resizable(False, False)
    win.transient(parent)
    win.configure(background="#f3f6fa")
    body = core.ttk.Frame(win, padding=(16, 14), style="App.TFrame")
    body.pack(fill="both", expand=True)
    core.ttk.Label(
        body, text="Chọn nguồn ảnh nhận diện", style="Key.TLabel"
    ).pack(anchor="w")
    core.ttk.Label(
        body,
        text="1 = thư viện Multi DEV • 2 = mục ảnh AUTO PRO (sẽ tự copy sang Multi DEV)",
        style="AutoValue.TLabel",
    ).pack(anchor="w", pady=(6, 14))

    def choose(value: str) -> None:
        result["value"] = value
        win.destroy()

    buttons = core.ttk.Frame(body, style="App.TFrame")
    buttons.pack(fill="x")
    core.ttk.Button(
        buttons, text="1 • Thư viện Multi DEV", width=24,
        style="AutoStart.TButton", command=lambda: choose("multi_library"),
    ).pack(side="left", padx=(0, 10))
    core.ttk.Button(
        buttons, text="2 • Ảnh AUTO PRO", width=22,
        style="Action.TButton", command=lambda: choose("auto_pro"),
    ).pack(side="left")
    core.ttk.Button(
        body, text="Hủy", width=12, style="Action.TButton", command=win.destroy,
    ).pack(anchor="e", pady=(14, 0))
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.grab_set()
    win.wait_window()
    return result["value"]


def _choose_catalog_image(core, parent, title: str, paths: list[Path], root: Path) -> Path | None:
    if not paths:
        return None
    state = {"filtered": list(paths), "result": None}
    win = core.tk.Toplevel(parent)
    win.title(title)
    win.geometry("760x560")
    win.minsize(620, 420)
    win.transient(parent)
    win.configure(background="#f3f6fa")

    top = core.ttk.Frame(win, padding=(12, 10), style="App.TFrame")
    top.pack(fill="x")
    core.ttk.Label(top, text="Tìm ảnh:", style="Key.TLabel").pack(side="left")
    query = core.tk.StringVar()
    entry = core.ttk.Entry(top, textvariable=query, width=48)
    entry.pack(side="left", padx=(8, 0), fill="x", expand=True)

    content = core.ttk.Frame(win, padding=(12, 0), style="App.TFrame")
    content.pack(fill="both", expand=True)
    listbox = core.tk.Listbox(
        content, activestyle="dotbox", exportselection=False,
        font=("Segoe UI", 9), borderwidth=1, relief="solid",
    )
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = core.ttk.Scrollbar(content, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="left", fill="y")
    listbox.configure(yscrollcommand=scrollbar.set)

    status = core.tk.StringVar()
    bottom = core.ttk.Frame(win, padding=(12, 10), style="App.TFrame")
    bottom.pack(fill="x")
    core.ttk.Label(bottom, textvariable=status, style="AutoValue.TLabel").pack(
        side="left", fill="x", expand=True
    )

    def label(path: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return path.name

    def refresh(*_args) -> None:
        needle = query.get().strip().lower()
        state["filtered"] = [
            path for path in paths if not needle or needle in label(path).lower()
        ]
        listbox.delete(0, "end")
        for path in state["filtered"]:
            listbox.insert("end", label(path))
        status.set(f"{len(state['filtered'])}/{len(paths)} ảnh")
        if state["filtered"]:
            listbox.selection_set(0)
            listbox.see(0)

    def accept(_event=None) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(state["filtered"]):
            state["result"] = state["filtered"][index]
            win.destroy()

    query.trace_add("write", refresh)
    listbox.bind("<Double-1>", accept)
    core.ttk.Button(
        bottom, text="Chọn ảnh", width=16, style="AutoStart.TButton", command=accept,
    ).pack(side="right", padx=(8, 0))
    core.ttk.Button(
        bottom, text="Hủy", width=10, style="Action.TButton", command=win.destroy,
    ).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    refresh()
    entry.focus_set()
    win.grab_set()
    win.wait_window()
    return state["result"]


def _choose_recognition_image(core, store, parent) -> tuple[Path, str] | None:
    source = _choose_image_source(core, parent)
    if source is None:
        return None
    if source == "multi_library":
        paths = store.list_library_images()
        if not paths:
            core.messagebox.showinfo(
                core.APP_NAME,
                "Thư viện ảnh Multi DEV đang trống. Chuyển sang mục ảnh AUTO PRO; ảnh chọn sẽ được copy vào thư viện Multi DEV.",
                parent=parent,
            )
            source = "auto_pro"
        else:
            chosen = _choose_catalog_image(
                core, parent, "Thư viện ảnh Multi DEV", paths, store.image_library_dir
            )
            if chosen is None:
                return None
            return store.use_library_image(chosen), "multi_library"

    if source == "auto_pro":
        auto_root = store.resolve_auto_pro_root(core.TOOL_DIR)
        paths = store.list_auto_pro_images(auto_root)
        if not paths:
            raise FileNotFoundError(f"Không tìm thấy ảnh nào trong AUTO PRO: {auto_root}")
        chosen = _choose_catalog_image(
            core, parent, "Mục ảnh AUTO PRO", paths, auto_root
        )
        if chosen is None:
            return None
        copied = store.import_auto_pro_image(chosen, auto_root)
        core.messagebox.showinfo(
            core.APP_NAME,
            f"Đã copy ảnh AUTO PRO vào thư viện Multi DEV:\n{copied.name}",
            parent=parent,
        )
        return copied, "auto_pro_imported"
    return None


def _existing_swipe_points(step: dict) -> list[list[int]]:
    raw = step.get("points")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        points: list[list[int]] = []
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                points = []
                break
            points.append([int(item[0]), int(item[1])])
        if len(points) >= 2:
            return points
    return [
        [int(step.get("x1", 500)), int(step.get("y1", 700))],
        [int(step.get("x2", 500)), int(step.get("y2", 300))],
    ]


def _parse_manual_points(text: str) -> list[list[int]]:
    points: list[list[int]] = []
    for raw_point in str(text or "").split(";"):
        raw_point = raw_point.strip()
        if not raw_point:
            continue
        parts = [part.strip() for part in raw_point.split(",")]
        if len(parts) != 2:
            raise ValueError("Mỗi điểm phải có dạng x,y; các điểm cách nhau bằng dấu ;")
        point = [int(parts[0]), int(parts[1])]
        if any(value < 0 or value > 1000 for value in point):
            raise ValueError("Mọi tọa độ Swipe phải nằm trong 0..1000")
        points.append(point)
    if len(points) < 2:
        raise ValueError("Swipe phải có ít nhất 2 điểm")
    return points


def configure_step(core, store, parent, step: dict, app=None) -> dict | None:
    """Edit one Builder block with native Multi DEV dialogs."""
    step_type = str(step.get("type") or "")
    try:
        if step_type == "enter_game_popup":
            timeout = core.simpledialog.askfloat(
                "Vào game + đóng popup", "Timeout tối đa (giây):",
                initialvalue=float(step.get("timeout", 180.0)), minvalue=1.0,
                maxvalue=600.0, parent=parent,
            )
            if timeout is None:
                return None
            step["timeout"] = float(timeout)
        elif step_type == "sell_function_vp":
            step["function_id"] = "function_1"
            timeout = core.simpledialog.askfloat(
                "Bán VP theo Function 1", "Timeout đưa về main/mở quầy (giây):",
                initialvalue=float(step.get("timeout", 120.0)), minvalue=1.0,
                maxvalue=600.0, parent=parent,
            )
            if timeout is None:
                return None
            step["timeout"] = float(timeout)
        elif step_type == "function":
            loops = core.simpledialog.askinteger(
                "9 Táo sấy - 9 Vải vàng", "Số vòng Function 1:",
                initialvalue=int(step.get("loops", 1) or 1), minvalue=1,
                maxvalue=999, parent=parent,
            )
            if loops is None:
                return None
            loop_delay = core.simpledialog.askfloat(
                "9 Táo sấy - 9 Vải vàng",
                "Thời gian chờ GIỮA các vòng Function (giây):\n"
                "Chỉ áp dụng khi Số vòng > 1; không chờ sau vòng cuối.",
                initialvalue=float(step.get("loop_delay_seconds", 0.0) or 0.0),
                minvalue=0.0, maxvalue=3600.0, parent=parent,
            )
            if loop_delay is None:
                return None
            step["function_id"] = "function_1"
            step["loops"] = int(loops)
            step["loop_delay_seconds"] = float(loop_delay)
            step["sale_after_each_loop"] = bool(core.messagebox.askyesno(
                "Function 1", "Sau MỖI vòng hoàn tất, gọi module Bán VP theo Function 1?",
                parent=parent,
            ))
            step["sale_timeout"] = 120.0
        elif step_type == "call_saved_function":
            chosen = _choose_saved_function(
                core, store, parent, str(step.get("function_id") or "")
            )
            if chosen is None:
                return None
            loops = core.simpledialog.askinteger(
                "Function tự tạo", f"Số vòng chạy {chosen['name']}:",
                initialvalue=int(step.get("loops", 1) or 1), minvalue=1,
                maxvalue=999, parent=parent,
            )
            if loops is None:
                return None
            loop_delay = core.simpledialog.askfloat(
                "Function tự tạo",
                f"Thời gian chờ GIỮA các vòng {chosen['name']} (giây):\n"
                "Không chờ sau vòng cuối.",
                initialvalue=float(step.get("loop_delay_seconds", 0.0) or 0.0),
                minvalue=0.0, maxvalue=3600.0, parent=parent,
            )
            if loop_delay is None:
                return None
            step["function_id"] = chosen["function_id"]
            step["function_name"] = chosen["name"]
            step["loops"] = int(loops)
            step["loop_delay_seconds"] = float(loop_delay)
            step["sale_after_each_loop"] = bool(core.messagebox.askyesno(
                "Function tự tạo",
                "Sau MỖI vòng Function này, gọi module Bán VP theo Function 1?",
                parent=parent,
            ))
            step["sale_function_id"] = "function_1"
            step["sale_timeout"] = float(step.get("sale_timeout", 120.0))
        elif step_type == "recognize_image":
            selected = _choose_recognition_image(core, store, parent)
            if selected is None:
                if not step.get("template_path"):
                    return None
            else:
                chosen, source = selected
                step["template_path"] = str(chosen)
                step["image_source"] = source
            threshold = core.simpledialog.askfloat(
                "Nhận diện ảnh", "Threshold (0.10 - 1.00):",
                initialvalue=float(step.get("threshold", 0.80)), minvalue=0.10,
                maxvalue=1.00, parent=parent,
            )
            if threshold is None:
                return None
            step["threshold"] = float(threshold)
            zone_text = core.simpledialog.askstring(
                "Nhận diện ảnh", "Vùng tìm x,y,w,h. Để trống = toàn màn hình:",
                initialvalue=(",".join(map(str, step.get("zone"))) if step.get("zone") else ""),
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
                    "Click", f"{label} (0..1000):",
                    initialvalue=int(step.get(key, 500) or 0), minvalue=0,
                    maxvalue=1000, parent=parent,
                )
                if value is None:
                    return None
                step[key] = int(value)
        elif step_type == "swipe":
            points = _existing_swipe_points(step)
            use_live = app is not None and core.messagebox.askyesno(
                "Swipe nhiều đoạn",
                "Kéo trực tiếp nhiều đoạn trên màn hình game?\n\n"
                "Mỗi lần kéo thêm một đoạn. Chọn đúng 1 tài khoản Online và đóng Live View trước.",
                parent=parent,
            )
            if use_live:
                picked = pick_swipe_on_game(app, core, parent=parent, initial=points)
                if picked is None:
                    return None
                points = [[int(x), int(y)] for x, y in picked]
            else:
                initial_text = "; ".join(f"{x},{y}" for x, y in points)
                raw = core.simpledialog.askstring(
                    "Swipe nhiều điểm",
                    "Nhập đường Swipe dạng x,y; x,y; x,y ...\nÍt nhất 2 điểm, tọa độ 0..1000:",
                    initialvalue=initial_text, parent=parent,
                )
                if raw is None:
                    return None
                points = _parse_manual_points(raw)
            step["points"] = points
            # Legacy summary/backward compatibility fields; runtime v1.2 uses points.
            step["x1"], step["y1"] = points[0]
            step["x2"], step["y2"] = points[-1]
            duration = core.simpledialog.askfloat(
                "Swipe nhiều đoạn", "Thời lượng toàn bộ đường Swipe (giây):",
                initialvalue=float(step.get("duration", 0.35)), minvalue=0.01,
                maxvalue=10.0, parent=parent,
            )
            if duration is None:
                return None
            step["duration"] = float(duration)
        elif step_type == "wait":
            seconds = core.simpledialog.askfloat(
                "Wait", "Chờ bao nhiêu giây?",
                initialvalue=float(step.get("seconds", 0.5)), minvalue=0.0,
                maxvalue=300.0, parent=parent,
            )
            if seconds is None:
                return None
            step["seconds"] = float(seconds)
        elif step_type == "finish_pass":
            pass
        elif step_type == "finish_fail":
            message = core.simpledialog.askstring(
                "Kết thúc FAIL", "Nội dung lỗi:",
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
