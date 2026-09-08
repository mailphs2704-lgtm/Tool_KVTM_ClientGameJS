# AUTO MULTI DEV — TỰ TẠO AUTO HANDOFF

Cập nhật: 2026-09-08 15:17 +07

## Mốc bàn giao của phiên này

- Nhánh: `develop/multi-auto-dev`.
- Source implementation baseline trước các commit tài liệu bàn giao: `6f2d7543840a946186289b978f528133f70ea455`.
- Baseline trước khi bắt đầu AUTO Builder: `8e77c90f44c37d9bd25d11b1cf61403e7695ac40`.
- So với baseline `8e77c90f...`, mốc `6f2d754...` đi trước 20 commit và chứa toàn bộ implementation AUTO Builder v1.
- Trạng thái: **SOURCE/STATIC IMPLEMENTED, CHƯA WINDOWS LIVE PASS**.
- Không được gọi runtime PASS chỉ vì source đã commit hoặc static verifier PASS.

## Mục tiêu đã khóa

Người vận hành phải tự xếp đúng thứ tự nghiệp vụ trên giao diện, thay vì AI suy luận thứ tự từ mô tả bằng chữ. AUTO Builder là Scheduler trực quan DEV-only, dùng lại engine click/swipe/vision và isolated Bridge V3 hiện tại.

Mục tiêu quan trọng nhất của kiến trúc này là tránh việc AI tự ghép sai thứ tự nghiệp vụ. Thứ tự hiển thị trên Builder chính là thứ tự thực thi.

## Ba module nghiệp vụ độc lập

### `ENTER_GAME_POPUP`

- UI: `MODULE • Vào game + đóng popup`.
- Runtime: `EnterGamePopupModule` gọi riêng `GameSessionWorkflow`.
- Không tự bán VP.
- Không tự gọi Function.
- Trong Builder không có `GameSessionWorkflow` ẩn ở đầu worker; module chỉ chạy tại đúng vị trí operator đặt.

### `SELL_FUNCTION_VP(function_id)`

- UI: `MODULE • Bán VP theo Function`.
- Runtime: `SellFunctionVpModule` tra `FunctionSpec` rồi gọi `AutoVpSaleWorkflow` với đúng danh sách VP của Function.
- Function 1 hiện khai báo `tao_say`, `vai_vang`.
- Giữ nguyên exact-x10, xác minh đúng vật phẩm sau chọn, thu vàng trước khi treo, fail-close và đóng quầy trong `finally`.
- Dọn quầy không được gọi từ module này.
- `AutoVpSaleWorkflow` đã được parameter hóa để nhận danh sách VP từ Function metadata; mặc định lịch sử Function 1 vẫn là Táo sấy + Vải vàng nên không đổi policy đang có.

### `FUNCTION(function_id)`

- UI: `FUNCTION • Function 1`.
- Runtime hiện hỗ trợ `function_1` qua `FunctionOneWorkflow`.
- Có `loops=1..999`.
- Có `sale_after_each_loop`.
- Nếu bật, Scheduler gọi **module SELL_FUNCTION_VP riêng** sau mỗi vòng Function; sale không được nhúng vào Function.

## Các block thao tác Builder v1

- Vào game + đóng popup.
- Bán VP theo Function.
- Function 1 + số vòng + bán sau mỗi vòng.
- Nhận diện ảnh người dùng chọn: threshold + zone, fresh frame, fail-close.
- Click tọa độ logic 0..1000.
- Swipe `x1,y1 → x2,y2` + duration.
- Wait.
- Kết thúc PASS.
- Kết thúc FAIL.

Chưa làm ở v1: If/Else, Goto, counter tổng quát, crop template trực tiếp từ Live View, click vào tâm match trước đó. Các phần này sẽ bổ sung sau khi v1 live-pass.

## Giao diện

Builder được gắn thành tab `TỰ TẠO AUTO` ngay sau `AUTO MULTI DEV`, dùng cùng tab strip và style của Multi DEV:

- nền tab `#e8eef7`;
- chữ `#263653`;
- active `#dce8f8/#1768c4`;
- `Segoe UI Semibold 9`;
- editor dùng `Queue.Treeview`;
- nút chạy/lưu dùng `AutoStart.TButton`/`Action.TButton`.

Không sửa `kvtm_multi.py` để nhét Builder trực tiếp. `auto_builder_integration.py` gắn DEV-only UI vào `MultiDevApp` tại host, nên production/shared UI core giữ nguyên.

Các file UI Builder chính:

- `source-archive/multi-current/kvtm_multi_tool/auto_builder_model.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_step_dialogs.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_ui.py`
- `source-archive/multi-current/kvtm_multi_tool/auto_builder_integration.py`
- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py`

## Runtime Scheduler Builder

Các file runtime chính:

- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/__init__.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/catalog.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/image_match.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/modules.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_builder/runner.py`
- `components/clientjs-auto/worker/auto_multi_dev_worker.py`

Các file nghiệp vụ được mở rộng có kiểm soát:

- `components/clientjs-auto/kvtm_automation/actions/auto_main_selling.py`
- `components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/workflow.py`

Builder không thay Dọn quầy và không gọi runtime Dọn quầy.

## Lưu plan và ảnh nhận diện

Builder lưu ở:

`%APPDATA%\KVTM Multi DEV\auto-builder`

Mục đích: dữ liệu người dùng không nằm trong `dist` bị xóa/rebuild bởi Control Center `[1]`. Nếu bản thử cũ từng có `data-dev/auto-builder`, store sẽ cố migrate sang vùng AppData khi vùng mới chưa tồn tại.

Plan mặc định v1:

1. `Vào game + đóng popup`.
2. `Bán VP • Function 1`.
3. `Function 1 ×1`, bật `bán VP sau mỗi vòng`.

Ảnh nhận diện do operator chọn được copy vào vùng dữ liệu Builder riêng, không biến ảnh debug thành asset nghiệp vụ chung.

## Isolated worker / CAPTURE3

Builder không tạo transport mới. Nó dùng lại lifecycle AUTO MULTI DEV:

- một worker riêng/profile;
- cùng busy gate;
- cùng Stop relay;
- preview/live capture nhường ownership trước worker;
- Bridge V3 strict;
- `CAPTURE3_WRITERMAP2`;
- `CAPTURE3_WRITERMSG1`;
- không stale frame;
- không HWND fallback.

UI đặt snapshot plan vào `auto-builder-plan.json` trong work-dir **của đúng run**. Worker chỉ chuyển `main` → `builder` khi marker riêng của run tồn tại, hoặc khi được gọi trực tiếp với `--mode builder --plan-json`. Plan khác/run khác không dùng chung marker.

Đặc biệt: Builder worker **không tự prepend GameSessionWorkflow**. Nếu operator không đặt block `Vào game + đóng popup`, Scheduler không được tự thêm nó.

## Static gate

`tools/verify_auto_builder_contract.py` khóa:

- ba module độc lập;
- Function metadata sở hữu VP sale;
- Function loop gọi sale từ Scheduler;
- Builder không prepend GameSession ẩn;
- custom image/click/swipe/wait;
- style UI khớp Multi DEV;
- AppData persistence;
- isolated worker strict V3;
- không gọi Dọn quầy / legacy business pyc.

Gate này được gọi từ `verify_auto_main_sale_contract.py`, nên Control Center `[1]` sẽ chạy nó trong chuỗi build bình thường.

Build mong đợi phải có dòng:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

sau đó các static gate AUTO Main tiếp tục chạy bình thường.

## Giới hạn runtime cần nhớ

**Chưa gọi AUTO Builder live PASS.** Đây mới là source/static implementation chờ Control Center + Windows live test.

Quan trọng nhất: Function 1 hiện kết thúc sau SX Vải vàng tại mốc tầng 3. Operator yêu cầu sau mỗi Function có thể quay lại module bán VP. Scheduler đã gọi đúng sale module theo cấu hình, nhưng **route tầng 3 → màn hình chính vẫn chưa được live-prove hoàn chỉnh**. `AutoVpSaleWorkflow` sẽ fail-close nếu không xác nhận được main; không được thêm route tầng giả/đoán để ép vòng lặp chạy.

Không được sửa ngưỡng nhận diện, thêm click mù hoặc thay CAPTURE3 chỉ để làm Builder chạy qua một bước.

## Next live test — bắt buộc làm từng bước

Bước tiếp theo duy nhất cho operator:

1. Mở root `KVTM_DEV_CONTROL.bat` → `[1] Cap nhat source + build runtime DEV`.

Sau khi `[1]` PASS mới làm tiếp:

2. `[2]` mở Multi DEV.
3. Xác nhận tab `TỰ TẠO AUTO` xuất hiện ngay sau `AUTO MULTI DEV`, đúng style.
4. Mở trình tạo và kiểm tra plan mặc định có đúng 3 bước.
5. Test plumbing an toàn đầu tiên bằng plan:
   - `Vào game + đóng popup`
   - `Kết thúc PASS`
6. Chỉ khi UI + isolated worker + block module này LIVE PASS mới thử `Bán VP` riêng.
7. Chỉ sau đó mới thử Function loop và xử lý riêng route sau Function 1 → main.

Không hướng dẫn người dùng manual `git pull`, PowerShell builder hoặc chỉnh trực tiếp `dist`; Control Center `[1]` là đường authoritative.

## Quy tắc đọc log khi tiếp tục phiên mới

- Nếu người dùng chủ động đổi tài khoản hoặc bấm Stop, traceback sau thời điểm đó là operator-interruption evidence; không patch `_refresh_profile_pid` chỉ vì tail đó.
- Kiểm tra exact Bridge PING trước khi chẩn đoán capture.
- Với Builder, log phải được hiểu theo đúng block hiện tại; không giả định block trước/sau đã chạy nếu plan không có nó.
- Build/static PASS không phải runtime PASS.

## Commit / file scope của mốc Builder

Bắt đầu từ head trước Builder: `8e77c90f44c37d9bd25d11b1cf61403e7695ac40`.

Implementation baseline hoàn tất của phiên: `6f2d7543840a946186289b978f528133f70ea455`.

Diff baseline → implementation gồm 17 path chính, trong đó Builder thêm mới 10 file runtime/UI/verifier và chỉ sửa có kiểm soát các wiring cần thiết. Không cherry-pick từng file rời khỏi chuỗi nếu không có lý do rõ ràng.

## Handoff ngắn cho AI phiên kế tiếp

```text
SESSION: AUTO/Multi
BRANCH: develop/multi-auto-dev
IMPLEMENTATION_BASELINE: 6f2d7543840a946186289b978f528133f70ea455
STATUS: SOURCE_STATIC_READY / WINDOWS_LIVE_PENDING
FEATURE: TỰ TẠO AUTO v1

READ_FIRST:
- AGENTS.md
- AI_COORDINATION.md
- docs/AUTO_MULTI_DEV_AUTO_BUILDER_HANDOFF.md

DO_NOT_TOUCH:
- Dọn quầy ổn định
- components/workspace/**
- profile/login data
- strict Bridge V3 WRITERMAP2 + WRITERMSG1

NEXT:
- User chạy Control Center [1]
- Nếu build PASS, [2]
- Verify tab TỰ TẠO AUTO + editor UI
- First runtime plan: Vào game + đóng popup -> Kết thúc PASS
- Chưa test Function loop trước khi plumbing này PASS

KNOWN_BLOCKER_FOR_LOOP:
- Function 1 kết thúc tại khu vực SX Vải vàng tầng 3
- route tầng 3 -> main chưa live-prove
- sale-after-loop phải fail-close nếu main chưa được chứng minh
```
