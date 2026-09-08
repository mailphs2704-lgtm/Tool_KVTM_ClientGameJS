from __future__ import annotations


__all__ = ["MANIFEST_VERSION", "display_steps", "runtime_steps"]
FILE_FUNCTIONS = (
    "Mô tả đầy đủ thứ tự thực thi Function 1 đã có để Load Function hiển thị",
    "Giữ riêng blueprint hiển thị với runtime wrapper proven function_1",
    "Liệt kê module, click, swipe, wait, nhận diện, loop/gate theo đúng thứ tự source",
)

MANIFEST_VERSION = 3


def _row(new_step_id, kind: str, detail: str) -> dict:
    return {"id": new_step_id(), "type": f"trace_{kind}", "detail": detail}


def display_steps(new_step_id) -> list[dict]:
    """Return the operator-visible execution blueprint for proven Function 1.

    These rows are an inspection manifest. They intentionally describe the
    exact business-module order and atomic input/vision operations already
    implemented in clean AUTO MULTI DEV source. Runtime execution stays bound
    to ``function_1`` through :func:`runtime_steps` so displaying the internals
    cannot silently replace the proven fail-close workflow with guessed JSON.
    """

    rows: list[dict] = []
    add = lambda kind, detail: rows.append(_row(new_step_id, kind, detail))

    add("module", "FunctionOneWorkflow.run • bắt đầu Function 1")
    add("gate", "check tùy chọn chưa cấu hình • bỏ qua")

    # PASS 1 — 27 Táo -> 9 Táo sấy.
    add("module", "AppleDryerWorkflow.run • PASS 1 • 27 Táo → 9 Táo sấy")
    add("module", "PlantingActions.plant_27_apples")
    add("click", "Đóng panel cạnh trước goUp(1) • (975,316)")
    add("wait", "0.20s")
    add("swipe", "goUp(1) • (514,214) → (514,314) • duration=floor_swipe_duration")
    add("wait", "0.65s")
    add("gate", "Fresh frame baseline trước mở bảng gieo")
    add("loop", "Tối đa 5 lần xác định chậu đầu: RIPE / EMPTY / UNKNOWN")
    add("click", "Mở chậu đầu • (388,946)")
    add("wait", "0.45s")
    add("recognize", "thu_hoach • threshold=0.80 • zone=(222,703,218,191)")
    add("recognize", "next_gieo_trai • threshold=0.70 • zone=(124,729,347,236)")
    add("recognize", "cay_tao • threshold=0.87 • zone=(179,773,230,166)")
    add("gate", "Nếu RIPE: thu hoạch 27 chậu rồi scan lại")
    add("swipe", "Thu hoạch 27 chậu • FARM_PATH_27 • duration=plant_harvest_duration")
    add("wait", "0.50s sau thu hoạch nếu nhánh RIPE")
    add("gate", "Nếu UNKNOWN: đóng panel rồi scan lại")
    add("click", "Đóng panel gieo • (965,198) • nhánh UNKNOWN")
    add("wait", "0.30s • nhánh UNKNOWN")
    add("recognize", "cay_tao lần cuối để lấy seed.center • threshold=0.87")
    add("swipe", "Gieo 27 Táo • seed.center + FARM_PATH_27[1:] • duration=plant_harvest_duration")
    add("wait", "0.40s")
    add("click", "Đóng bảng gieo • (965,198)")
    add("wait", "0.55s")
    add("gate", "Diagnostic changed_waypoint_regions/27 • non_blocking=true")

    add("module", "ProductionActions.produce_9_dried_apples")
    add("loop", "Click thu VP/mở máy sấy tầng 1 cho tới khi panel_ready")
    add("click", "Máy sấy tầng 1 • (262,917)")
    add("wait", "0.30s sau mỗi click mở/thu VP")
    add("recognize", "full_kho • threshold=0.90 • zone=(333,363,313,115)")
    add("recognize", "o_trong panel_ready • threshold=0.70 • zone=(335,781,395,186)")
    add("gate", "Nếu full_kho: đóng panel và FAIL-CLOSE")
    add("recognize", "tao_say • tối đa 3 lần • threshold=0.70 • scales=0.75..1.25")
    add("wait", "0.35s giữa các lần tìm tao_say")
    add("recognize", "o_trong top slot • threshold=0.82 • zone=(335,650,130,135)")
    add("gate", "Đếm ô trống top+lower • yêu cầu >=9 trước sản xuất")
    add("loop", "Lặp 9 lần xếp Táo sấy")
    add("swipe", "tao_say.center → top_empty.center • duration=0.02s")
    add("wait", "vp_production_delay")
    add("recognize", "x thiếu nguyên liệu • threshold=0.80 • zone=(682,337,142,120)")
    add("gate", "Sau mỗi swipe: số ô trống phải giảm")
    add("click", "Đóng panel máy • (965,198) sau đủ 9/9")
    add("gate", "Hậu kiểm consumed == 9 • PASS 1/3")

    # Apple supply refresh and floor 6.
    add("module", "AppleSupplyActions.wait_until_floor_1_ripe")
    add("loop", "Chờ tối đa 120s, kiểm tra cây tầng 1 theo crop_check_interval")
    add("click", "Mở chậu đầu • (388,946)")
    add("wait", "0.12s")
    add("recognize", "thu_hoach / next_gieo_trai / cay_tao trên cùng fresh frame")
    add("click", "Nếu GROWING: đóng panel • (965,198)")
    add("wait", "crop_check_interval nếu chưa chín")

    add("module", "AppleSupplyActions.harvest_and_replant_five_floors")
    add("swipe", "Thu hoạch 5 tầng • FIVE_FLOOR_PATH • duration=plant_harvest_duration")
    add("wait", "0.55s")
    add("loop", "Scan tới khi 5 tầng chuyển EMPTY")
    add("click", "Mở chậu đầu • (388,946)")
    add("wait", "0.12s")
    add("recognize", "next_gieo_trai + cay_tao để xác nhận EMPTY và lấy seed.center")
    add("swipe", "Gieo lại 30 Táo • seed.center + FIVE_FLOOR_PATH[1:]")
    add("wait", "0.45s")
    add("click", "Đóng panel • (965,198)")
    add("wait", "0.55s")

    add("module", "FunctionOneNavigationActions.floor_1_to_floor_6")
    add("click", "Đóng panel cạnh • (975,316) trước floor1-goUp(4)")
    add("swipe", "goUp(4) • (387,69) → (387,918)")
    add("wait", "0.70s + 0.15s")
    add("gate", "Fresh-frame change >= 1.0")
    add("click", "Đóng panel cạnh • (975,316) trước floor5-goUp(1)")
    add("swipe", "goUp(1) • (514,214) → (514,314)")
    add("wait", "0.70s + 0.15s")
    add("gate", "Fresh-frame change >= 1.0")

    add("module", "AppleSupplyActions.harvest_and_replant_floor_6_row")
    add("loop", "Scan hàng dưới tầng 6: EMPTY thì gieo ngay; RIPE thì thu hoạch trước")
    add("click", "Mở chậu đầu • (388,946)")
    add("wait", "0.12s")
    add("recognize", "thu_hoach / next_gieo_trai / cay_tao")
    add("swipe", "Nếu RIPE: thu hoạch FLOOR_6_ROW • (325,799) → (335,940) → (835,940)")
    add("wait", "0.55s sau thu hoạch tầng 6")
    add("loop", "Nếu vừa thu hoạch: scan tới EMPTY")
    add("swipe", "Gieo 6 Táo tầng 6 • seed.center + FLOOR_6_ROW[1:]")
    add("wait", "0.45s")
    add("click", "Đóng panel • (965,198)")
    add("wait", "0.55s")

    add("module", "FunctionOneNavigationActions.floor_6_to_main")
    for label, swipe in (
        ("floor6-goDown(4)-to-floor2", "(387,918) → (387,69)"),
        ("floor2-goDown(1)-to-floor1", "(514,314) → (514,214)"),
        ("floor1-goDown(1)-to-main", "(514,314) → (514,214)"),
    ):
        add("click", f"Đóng panel cạnh • (975,316) trước {label}")
        add("swipe", f"{label} • {swipe}")
        add("wait", "0.70s + 0.15s")
        add("gate", "Fresh-frame change >= 1.0")
    add("gate", "Exact main PASS • sau trồng Táo tầng 6 → trước SX Nước táo")

    # PASS 2 — 9 Nước táo.
    add("module", "FunctionOneNavigationActions.main_to_floor_2")
    for label in ("main-goUp(1)-to-floor1", "floor1-goUp(1)-to-floor2"):
        add("click", f"Đóng panel cạnh • (975,316) trước {label}")
        add("swipe", f"{label} • (514,214) → (514,314)")
        add("wait", "0.70s + 0.15s")
        add("gate", "Fresh-frame change >= 1.0")

    add("module", "AppleJuiceProductionActions.produce_9_apple_juices")
    add("loop", "Click thu VP/mở máy tầng 2 cho tới panel_ready")
    add("click", "Máy Nước táo tầng 2 • (262,917)")
    add("wait", "0.30s sau mỗi click")
    add("recognize", "full_kho + o_trong panel state")
    add("recognize", "nuoc_tao • tối đa 3 lần • threshold=0.70")
    add("wait", "0.20s giữa các lần tìm nuoc_tao")
    add("recognize", "o_trong top slot • threshold=0.82")
    add("gate", "Yêu cầu đúng 9/9 ô trống")
    add("loop", "Lặp 9 lần xếp Nước táo")
    add("swipe", "nuoc_tao.center → top_empty.center • duration=0.02s")
    add("wait", "vp_production_delay")
    add("gate", "Sau mỗi swipe: số ô trống phải giảm")
    add("click", "Đóng panel • (965,198)")
    add("gate", "Hậu kiểm 9/9 • TẠM PASS 2/3")

    # Normalize to main, then PASS 3.
    add("module", "FunctionOnePassThreeNavigationActions.floor_2_to_main")
    add("loop", "4 nhịp goDown(1): probe 1/4 + settle 2/4..4/4")
    for ordinal in range(1, 5):
        add("click", f"Đóng panel cạnh • (975,316) • post-juice {ordinal}/4")
        add("wait", "0.15s")
        add("swipe", f"post-juice goDown(1) {ordinal}/4 • (514,314) → (514,214)")
        add("wait", "0.70s")
        add("gate", "Fresh frame recorded • boundary_change_non_blocking=true")
    add("gate", "Exact main PASS • sau SX Nước táo → trước trồng Bông")

    add("module", "CottonPlantingActions.plant_27_cotton")
    add("gate", "Asset cay_bong phải tồn tại trước mọi gesture")
    add("click", "Đóng panel cạnh trước goUp(1) • (975,316)")
    add("wait", "0.20s")
    add("swipe", "goUp(1) • (514,214) → (514,314)")
    add("wait", "0.65s")
    add("gate", "Fresh frame baseline trước bảng gieo Bông")
    add("loop", "Tối đa 5 lần xác định chậu đầu: RIPE / EMPTY / UNKNOWN")
    add("click", "Mở chậu đầu • (388,946)")
    add("wait", "0.45s")
    add("recognize", "thu_hoach • threshold=0.80")
    add("recognize", "next_gieo_trai • threshold=0.70")
    add("recognize", "cay_bong • threshold=0.87")
    add("swipe", "Nếu RIPE: thu hoạch FARM_PATH_27 rồi scan lại")
    add("wait", "0.50s sau thu hoạch nếu nhánh RIPE")
    add("click", "Nếu UNKNOWN: đóng panel • (965,198)")
    add("wait", "0.30s • nhánh UNKNOWN")
    add("recognize", "cay_bong lần cuối để lấy seed.center • threshold=0.87")
    add("swipe", "Gieo 27 Bông • seed.center + FARM_PATH_27[1:]")
    add("wait", "0.40s")
    add("click", "Đóng bảng gieo • (965,198)")
    add("wait", "0.55s")
    add("gate", "Diagnostic changed_waypoint_regions/27 • non_blocking=true")

    add("module", "FunctionOnePassThreeNavigationActions.floor_1_to_floor_3")
    for label in ("floor1-goUp(1)-to-floor2", "floor2-goUp(1)-to-floor3"):
        add("click", f"Đóng panel cạnh • (975,316) trước {label}")
        add("swipe", f"{label} • (514,214) → (514,314)")
        add("wait", "0.70s + 0.15s")
        add("gate", "Fresh-frame change >= 1.0")

    add("module", "YellowFabricProductionActions.produce_9_yellow_fabrics")
    add("loop", "Tối đa 30 click thu VP/mở máy tầng 3 cho tới panel_ready")
    add("click", "Máy Vải vàng tầng 3 • (262,917)")
    add("wait", "0.30s sau mỗi click")
    add("recognize", "full_kho + o_trong panel state")
    add("gate", "Nếu không panel_ready sau 30 click: FAIL-CLOSE")
    add("recognize", "vai_vang • tối đa 3 lần • threshold=0.70")
    add("wait", "0.20s giữa các lần tìm vai_vang")
    add("recognize", "o_trong top slot • threshold=0.82")
    add("gate", "Yêu cầu đúng 9/9 ô trống")
    add("loop", "Lặp 9 lần xếp Vải vàng")
    add("swipe", "vai_vang.center → top_empty.center • duration=0.02s")
    add("wait", "vp_production_delay")
    add("recognize", "x thiếu nguyên liệu • threshold=0.80 • zone=(682,337,142,120)")
    add("gate", "Sau mỗi swipe: số ô trống phải giảm")
    add("click", "Đóng panel • (965,198)")
    add("gate", "Hậu kiểm 9/9 • PASS 3/3")
    add("module", "FunctionOneWorkflow.run • hoàn tất 9 Táo sấy + 9 Nước táo + 9 Vải vàng")

    return rows


def runtime_steps(new_step_id) -> list[dict]:
    """Keep runtime bound to the already-proven fail-close Function 1 workflow."""
    return [
        {
            "id": new_step_id(),
            "type": "function",
            "function_id": "function_1",
            "loops": 1,
            "sale_after_each_loop": False,
            "sale_timeout": 120.0,
        }
    ]
