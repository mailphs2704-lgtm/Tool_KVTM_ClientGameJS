# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-08 15:17 +07

Đây là handoff ngắn để phiên AI kế tiếp tiếp tục ngay mà không phải phục dựng lại toàn bộ ngữ cảnh. Tài liệu chi tiết của mốc hiện tại: `docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md`.

## Trạng thái hiện tại

- Branch: `develop/multi-auto-dev`.
- AUTO Builder implementation baseline: `6f2d7543840a946186289b978f528133f70ea455`.
- Commit `b44625e190154c088e143cbd16d24cd81d3671c6` chỉ cập nhật tài liệu bàn giao, không thay runtime business logic.
- Feature hiện tại: `TỰ TẠO AUTO v1`.
- Status: `SOURCE_STATIC_READY / WINDOWS_LIVE_PENDING`.
- Không được gọi Builder runtime PASS trước khi có Windows live evidence.

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

Không thay bằng manual git/powershell/dist edit.

Nếu `[1]` PASS mới chuyển `[2]`, rồi kiểm tra:

1. tab `TỰ TẠO AUTO` nằm ngay sau `AUTO MULTI DEV` và đồng bộ giao diện;
2. editor mở được;
3. plan mặc định đúng 3 block;
4. runtime test đầu tiên chỉ dùng `Vào game + đóng popup → Kết thúc PASS`.

Chưa chạy Function loop ngay.

## Blocker đã biết của Function loop

Function 1 hiện kết thúc sau sản xuất Vải vàng ở khu vực tầng 3. Route `tầng 3 → main` trước module bán VP sau vòng chưa được live-prove đầy đủ. Scheduler phải fail-close nếu sale module không chứng minh được main. Không được tự phát minh route tầng chỉ để loop chạy tiếp.

## Khi người dùng gửi log mới

- Đọc từ Bridge PING/runtime READY tới terminal event.
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
