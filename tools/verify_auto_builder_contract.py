from __future__ import annotations

"""Static contract for the DEV-only modular AUTO Builder."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "components/clientjs-auto/kvtm_automation"
MULTI = ROOT / "source-archive/multi-current/kvtm_multi_tool"
CATALOG = CLEAN / "workflows/auto_builder/catalog.py"
MODULES = CLEAN / "workflows/auto_builder/modules.py"
RUNNER = CLEAN / "workflows/auto_builder/runner.py"
IMAGE_MATCH = CLEAN / "workflows/auto_builder/image_match.py"
WORKER = ROOT / "components/clientjs-auto/worker/auto_multi_dev_worker.py"
SALE_ACTION = CLEAN / "actions/auto_main_selling.py"
SALE_WORKFLOW = CLEAN / "workflows/auto_vp_sale/workflow.py"
MODEL = MULTI / "auto_builder_model.py"
DIALOGS = MULTI / "auto_builder_step_dialogs.py"
GESTURE = MULTI / "auto_builder_gesture_picker.py"
UI = MULTI / "auto_builder_ui.py"
INTEGRATION = MULTI / "auto_builder_integration.py"
HOST = MULTI / "kvtm_multi_dev_host.py"
CORE_GUI = MULTI / "kvtm_multi.py"

FILE_FUNCTIONS = (
    "Parse toàn bộ module Builder bắt buộc",
    "Khóa module nghiệp vụ độc lập và Function metadata",
    "Khóa Function tự tạo nhiều tab/load/save/call graph + Function 1 cũ load được",
    "Khóa Swipe nhiều điểm liên tục qua native swipe_points/BATCH_SWIPE",
    "Khóa thư viện ảnh Multi DEV và import AUTO PRO vào thư viện",
    "Khóa custom image/click/swipe/wait fail-close",
    "Khóa giao diện Builder dùng style/tab Multi DEV",
    "Khóa plan bền qua Control Center build và worker isolated V3",
)


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing AUTO Builder file: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ast.parse(text, filename=str(path))
    return text


def require(text: str, token: str, message: str) -> None:
    if token not in text:
        raise AssertionError(message)


def forbid(text: str, token: str, message: str) -> None:
    if token in text:
        raise AssertionError(message)


def main() -> int:
    catalog = read(CATALOG)
    modules = read(MODULES)
    runner = read(RUNNER)
    image_match = read(IMAGE_MATCH)
    worker = read(WORKER)
    sale_action = read(SALE_ACTION)
    sale_workflow = read(SALE_WORKFLOW)
    model = read(MODEL)
    dialogs = read(DIALOGS)
    gesture = read(GESTURE)
    ui = read(UI)
    integration = read(INTEGRATION)
    host = read(HOST)
    core_gui = read(CORE_GUI)

    require(catalog, '"function_1": FunctionSpec(', "Function-1 Builder catalog missing")
    require(catalog, 'sale_item_ids=("tao_say", "vai_vang")',
            "Function-1 sale ownership missing")

    require(modules, "class EnterGamePopupModule", "Enter-game callable module missing")
    require(modules, "GameSessionWorkflow(self.auto).run", "Enter-game module wiring missing")
    require(modules, "class SellFunctionVpModule", "Function VP sale callable module missing")
    require(modules, "allowed_item_ids=spec.sale_item_ids", "Sale module is not bound to Function metadata")
    require(modules, "class FunctionModule", "Callable built-in Function module missing")

    require(sale_action, 'ITEM_ORDER = ("tao_say", "vai_vang")',
            "Stable Function-1 default sale order changed")
    require(sale_action, "item_order: tuple[str, ...] | None = None",
            "Sale action is not parameterizable by Function")
    require(sale_workflow, "allowed_item_ids: tuple[str, ...] | None = None",
            "Sale workflow does not accept Function VP policy")

    for step_type in (
        "enter_game_popup", "sell_function_vp", "function", "call_saved_function",
        "recognize_image", "click", "swipe", "wait", "finish_pass", "finish_fail",
    ):
        require(runner, f'"{step_type}"', f"Builder block missing: {step_type}")
    require(runner, "saved_functions", "Saved Function bundle missing from runtime")
    require(runner, "def _run_saved_function", "Reusable Function runner missing")
    require(runner, "Function tự tạo bị vòng gọi đệ quy", "Saved Function recursion guard missing")
    require(runner, "for loop_index in range(1, loops + 1):", "Function loop missing")
    require(runner, 'step.get("sale_after_each_loop", False)',
            "Function sale-after-loop switch missing")
    require(runner, "self.sale.run(", "Scheduler does not call independent sale module")
    require(runner, "self.function.run(function_id=function_id)",
            "Scheduler does not call built-in Function module")
    require(runner, "self.context.ensure_running()", "Builder stop checkpoints missing")
    require(image_match, "automation.vision.frame()", "Custom recognition lacks fresh frame")
    require(image_match, "cv2.matchTemplate", "Custom recognition matcher missing")
    require(runner, "raise ScreenTimeout", "Recognition failure is not fail-closed")

    # Reusable Function library + prior built-in Function exposed in Load Function.
    require(model, 'self.functions_dir = self.root / "functions"',
            "Persistent Function library missing")
    require(model, "def save_function", "Builder cannot save reusable Functions")
    require(model, "def load_function", "Builder cannot load reusable Functions")
    require(model, "def list_functions", "Builder cannot list reusable Functions")
    require(model, "def bundle_plan", "Builder cannot bundle saved Functions for worker")
    require(model, '_BUILTIN_WRAPPER_ID = "builtin_function_1_existing"',
            "Prior Function-1 stable load-library id missing")
    require(model, '"name": "9 Táo sấy - 9 Vải vàng"',
            "Prior 9 Táo sấy - 9 Vải vàng Function is not exposed")
    require(model, "def _seed_existing_function_one", "Prior Function seed hook missing")
    require(model, "self._seed_existing_function_one()", "Prior Function is not seeded on store startup")
    require(model, '"function_id": "function_1"',
            "Prior Function wrapper is not bound to proven built-in Function 1")
    require(model, '"type": "enter_game_popup"', "Default plan enter-game block missing")
    require(model, '"type": "sell_function_vp"', "Default plan sale module missing")

    # Recognition images: Multi DEV library is first-class; AUTO PRO is import-only.
    require(model, 'self.image_library_dir = self.root / "image-library"',
            "Persistent Multi DEV image library missing")
    require(model, "def list_library_images", "Multi DEV image library cannot be listed")
    require(model, "def list_auto_pro_images", "AUTO PRO image catalog cannot be listed")
    require(model, "def resolve_auto_pro_root", "Packaged AUTO PRO root resolver missing")
    require(model, "def import_auto_pro_image", "AUTO PRO image import path missing")
    require(model, "self._copy_image_to_library(path)",
            "AUTO PRO image selection must copy into Multi DEV library")
    require(dialogs, 'text="1 • Thư viện Multi DEV"',
            "Recognition source option 1 must be Multi DEV library")
    require(dialogs, 'text="2 • Ảnh AUTO PRO"',
            "Recognition source option 2 must be AUTO PRO images")
    require(dialogs, "store.list_library_images()", "Recognition dialog does not list Multi DEV library")
    require(dialogs, "store.list_auto_pro_images(auto_root)", "Recognition dialog does not list AUTO PRO images")
    require(dialogs, "store.import_auto_pro_image(chosen, auto_root)",
            "AUTO PRO selection is not copied into Multi DEV library")
    require(dialogs, 'step["image_source"] = source',
            "Recognition step does not record source provenance")

    # Swipe v1.2 is one ordered multi-point gesture, not N independent swipes.
    require(dialogs, "pick_swipe_on_game", "Swipe dialog is not wired to live picker")
    require(dialogs, 'step_type == "call_saved_function"',
            "Saved Function call configuration missing")
    require(dialogs, "Kéo trực tiếp nhiều đoạn trên màn hình game", "Multi-segment live Swipe prompt missing")
    require(dialogs, 'step["points"] = points', "Swipe dialog does not persist ordered points")
    require(dialogs, '"x,y; x,y; x,y ..."', "Manual multi-point Swipe fallback missing")

    require(gesture, "self.core.capture_shared_bgra(",
            "Gesture picker must use OpenGL shared capture")
    forbid(gesture, "capture_bgra(",
           "Gesture picker must not use HWND/PrintWindow fallback")
    require(gesture, "self._points", "Gesture picker does not retain multiple points")
    require(gesture, "<ButtonPress-1>", "Gesture picker drag start binding missing")
    require(gesture, "<B1-Motion>", "Gesture picker drag motion binding missing")
    require(gesture, "<ButtonRelease-1>", "Gesture picker drag release binding missing")
    require(gesture, "↶ Undo đoạn cuối", "Gesture picker cannot undo last segment")
    require(gesture, "✕ Xóa đường", "Gesture picker cannot clear the path")
    require(gesture, "1000.0", "Gesture picker logical 0..1000 mapping missing")
    require(gesture, 'self.result = [[int(x), int(y)] for x, y in self._points]',
            "Gesture picker does not return the full ordered polyline")

    require(runner, "def _normalize_swipe_points", "Runtime multi-point Swipe validation missing")
    require(runner, 'step["points"] = points', "Runtime does not normalize Swipe points")
    require(runner, "self.auto.driver.swipe_points(points, duration=duration)",
            "Runtime Swipe must execute one native multi-point swipe_points gesture")
    forbid(runner, "for segment in points", "Runtime must not split one Builder Swipe into independent swipes")
    require(runner, "segments={len(points) - 1}", "Runtime multi-segment Swipe diagnostic missing")

    require(worker, 'choices=("main", "floor-demo", "builder")',
            "Isolated worker Builder mode missing")
    require(worker, 'marker = Path(args.work_dir).resolve() / "auto-builder-plan.json"',
            "Per-run Builder plan marker missing")
    require(worker, 'if effective_mode == "builder":', "Builder worker branch missing")
    require(worker, "AutoBuilderRunner(automation, builder_plan).run()",
            "Builder worker Scheduler wiring missing")
    require(worker, 'outcome="auto_builder_ready"', "Builder terminal event missing")
    builder_branch = worker.split('if effective_mode == "builder":', 1)[1].split(
        "GameSessionWorkflow(automation).run", 1
    )[0]
    forbid(builder_branch, "GameSessionWorkflow(automation).run",
           "Builder silently prepends enter-game module")
    require(worker, "CAPTURE3_WRITERMAP2", "Builder worker lost strict CAPTURE3 revision")
    require(worker, "CAPTURE3_WRITERMSG1", "Builder worker lost writer-specific dispatch")

    require(model, 'appdata / "KVTM Multi DEV" / "auto-builder"',
            "Builder plan/assets must survive rebuilt dist tree")

    require(ui, 'text="TỰ TẠO AUTO"', "Builder tab label missing")
    require(ui, 'background="#e8eef7"', "Builder tab does not match Multi DEV tab background")
    require(ui, 'foreground="#263653"', "Builder tab does not match Multi DEV text color")
    require(ui, 'font=("Segoe UI Semibold", 9)', "Builder tab does not match Multi DEV font")
    require(ui, 'style="Queue.Treeview"', "Builder editor does not reuse Multi DEV Treeview style")
    require(ui, 'style="AutoStart.TButton"', "Builder run/save buttons do not reuse Multi DEV style")
    require(ui, "core.ttk.Notebook(win)", "Builder multi-document Notebook missing")
    require(ui, 'text="＋ Function mới"', "New Function tab button missing")
    require(ui, 'text="📂 Load Function"', "Load Function tab button missing")
    require(ui, '"FUNCTION TỰ TẠO • Gọi Function đã lưu"',
            "Saved Function call block missing from add menu")
    require(ui, '"SWIPE • kéo trực tiếp trên game"',
            "Live Swipe block label missing")
    require(ui, "def insert_function_into_main", "Function-to-main insertion missing")
    require(ui, "def run_document", "Independent Function test runner UI missing")
    require(ui, "self.store.bundle_plan", "UI must bundle saved Functions before worker launch")

    # Canvas.create_window returns an integer item id. Builder must attach its
    # native tab to the real tab_bar widget, never to that integer id.
    require(core_gui, "self.auto_tabs_window = self.auto_tabs_canvas.create_window(",
            "Core tab-strip canvas item contract changed")
    require(ui, 'anchor = app.auto_tab_buttons.get("multi_dev")',
            "Builder must anchor after the native AUTO MULTI DEV tab")
    require(ui, "tab_bar = anchor.master",
            "Builder must recover the real Tk tab-bar widget from the anchor")
    require(ui, "button = core.tk.Button(\n            tab_bar",
            "Builder tab must use the real Tk widget as its parent")
    forbid(ui, "core.tk.Button(\n            app.auto_tabs_window",
           "Builder cannot parent a Tk button to the integer canvas item id")

    for token in (
        'background="#e8eef7"', 'foreground="#263653"',
        'activebackground="#dce8f8"', 'activeforeground="#1768c4"',
        'font=("Segoe UI Semibold", 9)',
    ):
        require(core_gui, token, f"Core Multi DEV no longer carries shared style token: {token}")
        require(ui, token, f"Builder UI style drift: {token}")

    require(integration, "install_auto_builder_tab(self, core)", "Builder UI integration missing")
    require(integration, 'work_dir / "auto-builder-plan.json"', "Builder run marker wiring missing")
    require(integration, "return original_run_thread(self, *args, **kwargs)",
            "Builder must reuse proven worker lifecycle")
    require(integration, "self._start_clean_auto_session()",
            "Builder does not reuse Multi DEV ownership/busy gates")
    require(host, "install_auto_builder_integration(", "Multi DEV host does not install Builder")

    for text in (catalog, modules, runner, image_match, model, dialogs, gesture, ui, integration):
        forbid(text, "clear_stall_probe_runtime", "Builder must not call Dọn quầy runtime")
        forbid(text, ".pyc", "Builder must not execute legacy business pyc")
        require(text, "FILE_FUNCTIONS", "Every Builder module must document FILE_FUNCTIONS")

    print("AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED")
    print("ui=multi-dev-native-style-multi-tab-function-editor")
    print("functions=create-save-load-call-nested-no-recursion+builtin-function1-loadable")
    print("gesture_picker=multi-segment-opengl-drag-to-logical-1000-no-hwnd-fallback")
    print("swipe_runtime=one-native-swipe-points-batch")
    print("recognition_library=multi-dev-first-auto-pro-copy-in")
    print("modules=enter_game_popup,sell_function_vp,builtin_function")
    print("blocks=call_saved_function,recognize_image,click,swipe,wait,finish_pass,finish_fail")
    print("scheduler=function-loop-sale-after-each-loop-configurable")
    print("plan_storage=appdata-persistent-across-control-center-build")
    print("runtime=isolated-worker-v3-strict-capture")
    print("clear_stall=untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
