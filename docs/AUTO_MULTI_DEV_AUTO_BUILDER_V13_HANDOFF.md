# AUTO MULTI DEV — AUTO BUILDER v1.3 HANDOFF

Cập nhật: 2026-09-08

## Yêu cầu operator vừa sửa nghĩa của Load Function

`📂 Load Function` không được chỉ mở một wrapper một dòng kiểu:

`FUNCTION • 9 Táo sấy - 9 Vải vàng × 1`

Khi load Function đã làm trước đó, editor phải **show đầy đủ thứ tự đã thực hiện bên trong Function**, gồm tối thiểu các nhóm:

- MODULE;
- CLICK;
- SWIPE;
- WAIT;
- NHẬN DIỆN;
- GATE / HẬU KIỂM;
- LOOP / NHÁNH.

Đặc biệt Function `9 Táo sấy - 9 Vải vàng` phải thấy chuỗi nội bộ từ trồng Táo → 9 Táo sấy → bổ sung Táo → điều hướng tầng → 9 Nước táo → về main → 27 Bông → tầng 3 → 9 Vải vàng, với click/swipe nằm đúng thứ tự source hiện tại.

## Implementation v1.3

### Full execution manifest

File mới:

`source-archive/multi-current/kvtm_multi_tool/auto_builder_function1_manifest.py`

Manifest hiện mô tả ordered execution blueprint của proven `FunctionOneWorkflow` và các action con đang dùng:

- `PlantingActions.plant_27_apples`;
- `ProductionActions.produce_9_dried_apples`;
- `AppleSupplyActions.*`;
- `FunctionOneNavigationActions.*`;
- `AppleJuiceProductionActions.produce_9_apple_juices`;
- `FunctionOnePassThreeNavigationActions.floor_2_to_main`;
- `CottonPlantingActions.plant_27_cotton`;
- `YellowFabricProductionActions.produce_9_yellow_fabrics`.

Các row inspection có type `trace_*`, nhưng UI render thành tên người dùng đọc được: MODULE / CLICK / SWIPE / WAIT / NHẬN DIỆN / GATE / LOOP.

### Không biến proven Function 1 thành gesture JSON giả

Blueprint hiển thị và runtime tách riêng:

- `steps` = full source view để operator xem đúng toàn bộ thứ tự;
- `runtime_steps` = wrapper duy nhất gọi proven built-in `function_1`.

Khi bundle plan, mọi document có `source_template_id=builtin_function_1` bắt buộc thay `steps` bằng `runtime_steps` trước khi worker validate/run.

Mục đích: operator nhìn được nội bộ Function, nhưng việc hiển thị không làm mất các loop/branch/fail-close động đang có trong source thật.

### Migration file AppData cũ

Seed cũ `builtin_function_1_existing.json` từng chỉ có một row FUNCTION.

Store hiện kiểm tra `manifest_version`. Nếu file cũ thiếu/full manifest chưa đủ version, nó tự refresh sang full manifest khi Multi DEV khởi tạo Builder. Không cần người dùng xóa AppData thủ công.

### UI read-only cho built-in full source view

Khi load `9 Táo sấy - 9 Vải vàng`, tab hiện:

`FULL SOURCE VIEW • chỉ đọc • runtime vẫn gọi proven function_1`

Các nút thêm/sửa/đưa lên/đưa xuống/xóa/lưu bị ẩn cho built-in inspection document. `▶ Chạy tab` và `＋ Chèn vào plan chính` vẫn dùng được và runtime vẫn đi qua proven Function 1.

Function tự tạo bình thường vẫn editable như trước.

## Không thay đổi

- Không sửa business logic Function 1.
- Không sửa Dọn quầy.
- Không sửa Workspace/profile/login/DPAPI.
- Không đổi Bridge V3/CAPTURE3 contract.
- Swipe Builder v1.2 vẫn là multi-point một native `swipe_points`.
- Recognition library Multi DEV / AUTO PRO import vẫn giữ nguyên.

## Static gate mới

Build phải có:

`AUTO MULTI DEV AUTO BUILDER STATIC CONTRACT VERIFIED`

và thêm:

`functions=create-save-load-call-nested-no-recursion+builtin-function1-full-source-view`

`function1_load=full-module-click-swipe-recognize-order+proven-runtime-wrapper`

## NEXT live test

1. Control Center `[1] Cap nhat source + build runtime DEV`.
2. Build PASS mới `[2] Mo Multi DEV nen`.
3. Mở `TỰ TẠO AUTO` → `📂 Load Function` → chọn `9 Táo sấy - 9 Vải vàng`.
4. Tab không còn một row FUNCTION duy nhất.
5. Phải thấy nhiều row MODULE/CLICK/SWIPE/WAIT/NHẬN DIỆN/GATE/LOOP theo thứ tự.
6. Header phải có `FULL SOURCE VIEW • chỉ đọc • runtime vẫn gọi proven function_1`.
7. Chưa gọi runtime PASS cho v1.3 cho tới khi operator xác nhận UI trên Windows.
