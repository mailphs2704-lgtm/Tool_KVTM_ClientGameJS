# AUTO MULTI DEV — FUNCTION & RECOVERY MAPPING METHOD

Cập nhật: 2026-09-11
Trạng thái: DESIGN / SPECIFICATION IN PROGRESS
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`

> Tài liệu này định nghĩa cách tiếp nhận mô tả nghiệp vụ từ operator trong giai đoạn chuẩn hóa Function và Recovery. Operator không cần biết cấu trúc Python; chỉ cần mô tả một vòng Function hoàn chỉnh theo đúng thứ tự thực tế và đánh dấu các điểm có nhánh lỗi.

## 1. Cách operator mô tả

Operator có thể mô tả tự nhiên từ đầu đến cuối:

```text
Bắt đầu Function
→ làm A
→ làm B
→ làm C
→ nếu lỗi X thì xử lý theo hướng 1
→ nếu không lỗi thì đi tiếp
→ làm D
→ kết thúc Function
```

Không cần tự quyết định đoạn nào là class, file, action hay module.

Nếu một bước có lỗi, chỉ cần ghi rõ hai hướng:

```text
Bình thường:
→ ...

Nếu lỗi:
→ phát hiện gì
→ cần làm gì
→ sau xử lý quay lại bước nào
```

## 2. Trách nhiệm của phần chuẩn hóa

Mỗi mô tả của operator sẽ được phân loại thành 4 nhóm:

```text
ACTION
= thao tác tái sử dụng: click, swipe, nhận diện, chọn vật phẩm, plant path, open/close panel...

MODULE / RECIPE
= một công việc hoàn chỉnh được ghép từ nhiều Actions: sản xuất VP, trồng cây, bán VP, sửa máy...

FUNCTION ORCHESTRATION
= thứ tự các Module/Recipe tạo thành một vòng Function hoàn chỉnh

RECOVERY
= nhánh lỗi, retry, phục hồi state/floor, Friend Refresh, restart và resume checkpoint
```

## 3. Cách phân biệt lỗi

Mỗi điểm lỗi được phân loại tối thiểu thành một trong các nhóm sau:

### A. Expected / Specialized Recoverable Error

Lỗi đã biết rõ nguyên nhân và có cách phục hồi riêng.

Ví dụ:

```text
InventoryFull
WrongProductionMachine
MaterialShortage
NavigationError có state xác định
```

Luồng:

```text
Module đang chạy
→ typed error
→ lưu/giữ checkpoint
→ handler chuyên biệt
→ trở lại đúng state/floor
→ resume CÙNG module
```

### B. Transient / Local Retry Error

Lỗi tạm thời, có thể thử lại cùng thao tác với số lần giới hạn mà không gây side effect nguy hiểm.

Luồng:

```text
Action/Module FAIL
→ retry theo policy giới hạn
→ thành công: tiếp tục
→ cạn retry: nâng cấp recovery
```

### C. Unknown / Unhandled Recoverable State

Không xác định được lỗi chuyên biệt nhưng UI/game có vẻ còn sống.

Luồng mục tiêu:

```text
local retry cạn
→ Friend Refresh #1
→ về exact-main
→ resume checkpoint
→ nếu vẫn lỗi: Friend Refresh #2
→ resume
→ nếu vẫn lỗi: recovery escalation cao hơn theo policy
```

### D. Unsafe-to-retry / Fail-close Error

Không đủ bằng chứng để biết thao tác đã có side effect hay chưa, hoặc retry có thể tạo giao dịch/sản xuất/trồng lặp nguy hiểm.

Không blind retry. Phải dừng hoặc chuyển qua recovery có proof rõ ràng trước khi tiếp tục.

## 4. Quy tắc checkpoint tại từng nhánh lỗi

Mỗi điểm có thể bị interrupt phải xác định:

```text
function_id
module_id / recipe_id
action/step hiện tại
floor/state hiện tại
target/product/crop
completed_count / target_count
retry_count
recovery_stage
```

Checkpoint chỉ là metadata nhẹ; không giữ frame/image/numpy object.

Recovery xử lý xong phải quay về đúng checkpoint và tiếp tục công việc đang dở. Không được coi recovery là Function PASS.

## 5. Quy tắc phân rã một Function hoàn chỉnh

Sau khi operator mô tả xong một vòng, tài liệu sẽ được chuyển thành dạng:

```text
FUNCTION X
  1. Module A
     - Action A1
     - Action A2
     - Recovery points...

  2. Module B
     - Action B1
     - Action B2
     - Recovery points...

  3. Module C
     ...

  FUNCTION PASS CONDITION
```

Mỗi Module phải có:

- precondition;
- actions chính;
- postcondition/PASS proof;
- typed/recoverable errors có thể phát sinh;
- retry policy nếu an toàn;
- checkpoint/resume point;
- escalation path nếu recovery cục bộ thất bại.

## 6. Nguyên tắc tránh nhầm tầng

Không tự động coi mọi đoạn nhiều bước là Module.

Một đoạn nên là Action nếu nó chỉ mô tả **cách thực hiện một thao tác tái sử dụng**.

Một đoạn nên là Module/Recipe nếu nó có **mục tiêu nghiệp vụ riêng, precondition/postcondition và có thể được nhiều Function gọi lại**.

Function chỉ giữ orchestration và điều kiện hoàn tất vòng.

Recovery không được nhúng copy vào từng Function.

## 7. Cách phản biện logic

Khi operator mô tả, nếu có điểm mâu thuẫn hoặc dễ tạo bug, phải đánh dấu rõ:

```text
CHỐT
CẦN CHỐT
RỦI RO LOGIC
ĐỀ XUẤT KỸ THUẬT
```

Không tự đổi yêu cầu nghiệp vụ chỉ vì code hiện tại đang làm khác.

Nếu source cũ xung đột với mô tả mới, mô tả mới được coi là target thiết kế nhưng chưa tự động là runtime PASS.

## 8. Mục tiêu cuối của giai đoạn này

Khi operator nói `kết thúc`, phải có đủ:

```text
1. Function flow từ đầu đến cuối
2. Danh sách Module/Recipe
3. Danh sách Actions dùng lại
4. Tất cả recovery points
5. Retry/escalation policy
6. Checkpoint/resume contract
7. PASS condition cho từng Module và Function
8. Mapping source hiện tại -> kiến trúc target
```

Sau đó mới audit/refactor code theo thứ tự ít regression nhất.
