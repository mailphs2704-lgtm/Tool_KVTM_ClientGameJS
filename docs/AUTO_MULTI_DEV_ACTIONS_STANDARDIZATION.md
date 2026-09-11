# AUTO MULTI DEV — ACTIONS STANDARDIZATION

Cập nhật: 2026-09-11
Trạng thái: DESIGN / SPECIFICATION IN PROGRESS
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch: `develop/multi-auto-dev`

> Tài liệu này là phần mở rộng của `AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` trong giai đoạn operator đang chuẩn hóa AUTO. Chưa refactor runtime theo tài liệu này cho tới khi operator nói kết thúc phần thiết kế hoặc yêu cầu triển khai rõ ràng.

## 1. Mục tiêu — CHỐT

`Actions` là thư viện hành động dùng chung cho toàn dự án AUTO.

Mọi Function/Module khi cần thao tác với ClientJS phải ưu tiên gọi action dùng chung thay vì tự chứa click/swipe/vision riêng.

Các hành động có thể gồm:

- click;
- swipe;
- drag theo path;
- mở/đóng panel;
- nhận diện trạng thái/template;
- chọn hạt/cây/vật phẩm;
- thu hoạch;
- trồng cây theo path/count;
- mở kho/chọn kho;
- chọn VP;
- thao tác máy sản xuất;
- điều hướng các bước nhỏ đã xác minh;
- verify hậu điều kiện của một thao tác.

Mục tiêu là khi thêm Function mới, phần lớn hành động đã tồn tại sẵn trong `actions/` và Function chỉ ghép chúng theo nghiệp vụ.

## 2. Ranh giới bắt buộc giữa Function / Module / Action — CHỐT

```text
FUNCTION
= nói CẦN LÀM GÌ và thứ tự nghiệp vụ

MODULE / RECIPE
= ghép một nhóm actions thành một công việc có nghĩa

ACTION
= biết CÁCH thực hiện một thao tác có thể tái sử dụng

GLOBAL RECOVERY
= xử lý lỗi/retry/escalation/checkpoint
```

Action không được tự quyết định:

- bắt đầu Function loop mới;
- Function nào chạy tiếp;
- tăng `function_loops`;
- lịch bán;
- lịch Friend Refresh;
- lịch restart ClientJS;
- reset checkpoint của Function;
- retry vô hạn hoặc tự escalation sang Friend/Restart.

Action có thể phát typed error/event để RecoveryManager xử lý.

## 3. Không nhân bản action chỉ vì khác Function — CHỐT

Không tạo logic kiểu:

```text
function_1_click_seed
function_2_click_seed
function_3_click_seed
```

nếu cùng một thao tác có thể parameterize.

Ưu tiên:

```python
select_seed(seed_template)
open_seed_picker()
plant_path(path)
harvest_path(path)
```

Function/Recipe chỉ truyền context phù hợp.

## 4. Action theo count/path cây — CHỐT HƯỚNG

Operator muốn các hành động trồng phổ biến như 27 cây, 28 cây... được chuẩn bị sẵn để Function gọi lại.

Điểm kỹ thuật cần khóa: **Function không nên biết chi tiết cách biến 28 thành 27 + 1**, vì như vậy geometry nghiệp vụ lại rò vào Function.

Ví dụ không nên:

```text
Function 2
→ nhận diện Cây tuyết
→ gọi plant_27
→ tự viết thêm thao tác cây thứ 28
```

Nên dùng một trong hai dạng sau.

### Dạng A — action tổng quát theo path/count (ưu tiên nếu geometry cho phép)

```python
plant_crop(
    seed_template="cay_tuyet",
    path=PATH_28,
    expected_count=28,
)
```

Hoặc API tương đương:

```python
select_seed("cay_tuyet")
plant_path(PATH_28, expected_count=28)
```

### Dạng B — action đã xác minh sẵn theo geometry

Nếu mỗi count có choreography/path riêng đã live-verified thì có thể expose:

```text
plant_27(...)
plant_28(...)
plant_30(...)
plant_5(...)
```

nhưng các action này vẫn phải dùng chung primitive/path engine, không copy nguyên code click/swipe nhiều lần.

Ví dụ:

```python
plant_27(seed_template="cay_bong")
plant_28(seed_template="cay_tuyet")
plant_30(seed_template="cay_hong")
```

## 5. Tách “nhận diện cây” khỏi “đường trồng” — CHỐT HƯỚNG

Loại cây và geometry là hai dữ liệu khác nhau.

Ví dụ:

```text
seed_template = cay_tuyet
plant_path = PATH_28
expected_count = 28
```

Action trồng không nên hard-code rằng `PATH_28` chỉ thuộc Cây tuyết nếu path đó có thể tái sử dụng cho cây khác.

Điều này cho phép cùng một action/path được Function khác gọi lại với loại cây khác nếu gameplay cho phép.

## 6. Action phải có hậu kiểm khi thao tác có side effect — CHỐT

Không coi việc đã click/swipe là thành công.

Ví dụ trồng cây:

```text
mở seed picker
→ nhận diện đúng seed
→ swipe path
→ đóng panel
→ hậu kiểm state/count/visual change phù hợp
→ ACTION PASS
```

Ví dụ mở panel sản xuất:

```text
click máy
→ nhận diện đúng product panel
→ sai máy thì phát WrongProductionMachine
→ đúng máy mới tiếp tục
```

Action có side effect phải trả result/evidence đủ để Module/Recovery biết việc nào đã thật sự hoàn tất.

## 7. Ưu tiên action idempotent hoặc resumable — CHỐT HƯỚNG

Khi có thể, action phải được thiết kế để gọi lại sau recovery mà không làm lặp side effect nguy hiểm.

Nếu action không idempotent, nó phải trả progress/evidence để checkpoint biết đã làm tới đâu.

Ví dụ production 9 sản phẩm:

```text
queued_count = 4/9
→ lỗi
→ recovery
→ resume
→ chỉ làm 5 sản phẩm còn lại
```

Không replay lại 9 sản phẩm từ đầu.

## 8. Actions và checkpoint RAM — CHỐT

Actions không được nhét frame/image/numpy array lâu dài vào checkpoint.

Checkpoint chỉ lưu metadata/progress cần resume, ví dụ:

```text
action_id
seed_template
path_id
expected_count
completed_count
floor
step
```

Mỗi profile vẫn chỉ có một ActiveCheckpoint được update tại chỗ.

## 9. Cấu trúc thư mục mục tiêu — CHỐT HƯỚNG, TÊN FILE CÓ THỂ ĐIỀU CHỈNH KHI AUDIT

Không bắt buộc đúng tên file này ngay, nhưng trách nhiệm nên tách tương tự:

```text
actions/
  input.py              # click/swipe/drag primitive wrappers nếu cần
  vision.py             # helper nhận diện/action-level verification nếu phù hợp
  popup.py
  navigation.py
  planting.py
  harvesting.py
  inventory.py
  stall.py
  selling.py
  production.py
  machine_repair.py
```

Không cần tạo quá nhiều file nhỏ nếu source hiện tại đã có nhóm tương đương. Khi refactor phải audit code thật trước, ưu tiên di chuyển ít nhất và tránh regression.

## 10. Ví dụ target: Function cần trồng 28 Cây tuyết

Function/Recipe mục tiêu nên trông gần như:

```text
Function/Recipe xác định:
- crop = Cây tuyết
- required = 28

        ↓
Planting Action
- mở/nhận diện seed Cây tuyết
- dùng PATH_28 đã xác minh
- trồng đủ 28
- hậu kiểm

        ↓
trả PlantResult(28)
```

Function không chứa tọa độ, không tự swipe, không tự biết từng waypoint của 28 cây.

## 11. Quy tắc chống phình Actions — CHỐT

`Actions` chứa toàn bộ **khả năng thao tác tái sử dụng**, nhưng không trở thành một file/class khổng lồ chứa toàn bộ nghiệp vụ.

Nên tổ chức theo domain và composition:

```text
primitive action
    ↓
domain action
    ↓
module/recipe
    ↓
function
```

Ví dụ:

```text
swipe_points()
    ↓
plant_path(PATH_28)
    ↓
PlantCropModule(cay_tuyet, 28)
    ↓
Function 2
```

## 12. Trạng thái triển khai

- Kiến trúc Actions ở tài liệu này: **DESIGN / CHỐT HƯỚNG**.
- Chưa refactor source hiện tại theo cấu trúc này.
- Khi operator nói `kết thúc`, cần audit toàn bộ `components/clientjs-auto/kvtm_automation/actions/` để map action hiện có vào contract mới trước khi sửa.
- Không xóa action cũ chỉ vì tên/file chưa đẹp; phải kiểm tra caller và live evidence trước.
