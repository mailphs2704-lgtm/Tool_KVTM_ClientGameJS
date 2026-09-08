# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-08 15:17+ +07

Đây là handoff ngắn để phiên AI kế tiếp tiếp tục ngay mà không phải phục dựng lại toàn bộ ngữ cảnh. Tài liệu chi tiết của mốc hiện tại: `docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md`.

## Trạng thái hiện tại

- Branch: `develop/multi-auto-dev`.
- AUTO Builder implementation baseline ban đầu: `6f2d7543840a946186289b978f528133f70ea455`.
- Live startup fix mới: `ef5cbef360d16a5cd6c070e44cac3de1c2a26800`.
- Static regression guard mới: `e9ce3f11a05b4d0716be615931ee7f1345312fb5`.
- Feature hiện tại: `TỰ TẠO AUTO v1`.
- Status: `STARTUP_FIX_READY / WINDOWS_RETEST_PENDING`.
- Không được gọi Builder runtime PASS trước khi có Windows live evidence.

## Live evidence mới nhất

Sau Control Center `[1]` sync runtime và khi `[2]` mở Multi DEV, ứng dụng thoát ngay trong lúc dựng UI:

`AttributeError: 'int' object has no attribute 'tk'`

Trace đi qua:

`kvtm_multi.py::_build_auto_panel` → `auto_builder_integration.py::build_auto_panel` → `auto_builder_ui.py::_build_tab` → `core.tk.Button(app.auto_tabs_window, ...)`.

Root cause đã xác định chắc chắn từ source core:

- `kvtm_multi.py` tạo `tab_bar` là widget thật.
- Sau đó `self.auto_tabs_window = self.auto_tabs_canvas.create_window(...)`.
- `Canvas.create_window()` trả về **canvas item id kiểu integer**, không phải Tk widget.
- Builder v1 đã dùng nhầm integer `app.auto_tabs_window` làm master của `tk.Button`, nên Tkinter crash trước khi Multi mở xong.

Đây là lỗi UI integration của Builder, **không phải Bridge/CAPTURE3, không phải profile, không phải worker runtime**.

Fix `ef5cbef...`:

- lấy tab `AUTO MULTI DEV` đã tồn tại: `anchor = app.auto_tab_buttons.get("multi_dev")`;
- lấy widget tab bar thật bằng `tab_bar = anchor.master`;
- tạo nút `TỰ TẠO AUTO` với parent `tab_bar`;
- pack `after=anchor` để vẫn nằm ngay sau `AUTO MULTI DEV`;
- không sửa `kvtm_multi.py` hay canvas scroll contract.

Verifier `e9ce3f1...` khóa regression:

- xác nhận core `auto_tabs_window` vẫn là canvas item từ `create_window`;
- Builder bắt buộc lấy `anchor.master`;
- cấm dùng `app.auto_tabs_window` làm parent của `tk.Button`.

## Kiến trúc đã khóa

- Builder là visual Scheduler DEV-only, đồng bộ style với Multi DEV.
- Thứ tự danh sách Builder = thứ tự chạy thật.
- `Vào game + đóng popup` là module riêng.
- `Bán VP theo Function` là module riêng.
- `Function` là module riêng.
- Function có số vòng; nếu `sale_after_each_loop=true`, Scheduler gọi module bán riêng sau mỗi vòng.
- Builder không tự prepend `GameSessionWorkflow`.
- Function 1 sale metadata hiện chỉ gồm `tao_say` + `vai_vang`.
- Builder có custom `Nhận diện ảnh`, `Click`, `Swipe`, `Wait`, `PASS`, `FAIL`.
- Plan và ảnh operator chọn lưu persistent dưới `%APPDATA%\KVTM Multi DEV\auto-builder`.

## Transport bắt buộc giữ nguyên

- isolated `auto_multi_dev_worker.py`;
- strict Bridge V3;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- exact same-request capture;
- không stale frame;
- không HWND fallback;
- một owner/profile;
- preview nhường capture trước worker.

## Không được đụng khi tiếp tục Builder

- Dọn quầy ổn định.
- `components/workspace/**`.
- `KVTM_WORKSPACE_CONTROL.bat`.
- profile/login/DPAPI data.
- không hạ threshold hoặc thêm click mù để ép test chạy.

## Bước tiếp theo duy nhất cho người dùng

Chỉ yêu cầu:

`KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`

Không dùng `[9]`. Không thay bằng manual git/powershell/dist edit.

Nếu `[1]` PASS mới chuyển `[2]` và xác nhận Multi DEV **mở được, không còn `int has no attribute tk`**.

Sau đó mới kiểm tra:

1. tab `TỰ TẠO AUTO` nằm ngay sau `AUTO MULTI DEV` và đồng bộ giao diện;
2. editor mở được;
3. plan mặc định đúng 3 block;
4. runtime test đầu tiên chỉ dùng `Vào game + đóng popup → Kết thúc PASS`.

Chưa chạy Function loop ngay.

## Blocker đã biết của Function loop

Function 1 hiện kết thúc sau sản xuất Vải vàng ở khu vực tầng 3. Route `tầng 3 → main` trước module bán VP sau vòng chưa được live-prove đầy đủ. Scheduler phải fail-close nếu sale module không chứng minh được main. Không được tự phát minh route tầng chỉ để loop chạy tiếp.

## Khi người dùng gửi log mới

- Nếu Multi còn crash lúc startup, ưu tiên traceback UI/integration trước; chưa đi vào worker thì không chẩn đoán Bridge.
- Nếu Multi mở và test Builder runtime, đọc từ Bridge PING/runtime READY tới terminal event.
- Phân biệt operator Stop/profile switch với lỗi runtime thật.
- Nếu test Builder, đối chiếu log theo đúng thứ tự block trong plan.
- Static/build PASS không đồng nghĩa runtime PASS.
- Nếu plumbing `Vào game + đóng popup → PASS` đạt live PASS, test tiếp `Bán VP` như module riêng trước khi ghép Function loop.

## Source chính cần đọc khi debug Builder

- `source-archive/multi-current/kvtm_multi_tool/auto_builder_model.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_step_dialogs.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_ui.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/catalog.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/modules.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/runner.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/image_match.py`
- `components/clientjs-auto/worker/auto_multi_dev_worker.py`
- `tools/verify_auto_builder_contract.py`

## Read-first cho phiên AI kế tiếp

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md`
