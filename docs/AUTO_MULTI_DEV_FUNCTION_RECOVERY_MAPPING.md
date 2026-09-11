# AUTO MULTI DEV — FUNCTION & RECOVERY MAPPING METHOD

Cập nhật: 2026-09-11
Trạng thái: INCREMENTAL IMPLEMENTATION / STANDARDIZATION
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`

> Tài liệu này định nghĩa cách tiếp nhận mô tả nghiệp vụ từ operator trong giai đoạn vừa triển khai vừa chuẩn hóa Function và Recovery. Operator không cần mô tả trọn Function trước. Có thể mô tả từng đoạn ngay lúc thực hiện; khi operator đánh dấu một điểm bắt lỗi, AI phải tự phân loại và đưa logic đó sang đúng nhánh Recovery.

## 1. Cách operator mô tả — CHỐT MỚI NHẤT

Operator **không cần mô tả toàn bộ Function từ đầu đến cuối trước khi bắt đầu triển khai**.

Workflow mới:

```text
operator mô tả đoạn cần làm hiện tại
        ↓
AI phân loại Action / Module / Function orchestration
        ↓
triển khai đoạn đó theo kiến trúc đã chốt
        ↓
operator test / mô tả tiếp
        ↓
nếu operator đánh dấu điểm bắt lỗi
        ↓
AI phân loại lỗi + Recovery + checkpoint/resume
        ↓
tiếp tục triển khai đoạn kế tiếp
```

Khi mô tả một điểm lỗi, operator chỉ cần nói theo gameplay, ví dụ:

```text
Bình thường:
→ ...

Nếu lỗi:
→ thấy trạng thái gì
→ muốn xử lý thế nào
→ sau xử lý cần tiếp tục việc gì
```

Operator không cần tự quyết định đó là class, file, Action, Module hay Recovery handler.

### Quy tắc làm việc

- Không bắt operator mô tả lại phần đã chốt.
- Không bắt operator hoàn thành toàn bộ sơ đồ Function trước khi code phần hiện tại.
- Mỗi đoạn triển khai vẫn phải tuân thủ kiến trúc chung và tránh nhét recovery riêng vào Function.
- Khi chưa có nhánh lỗi do operator chỉ ra, không tự bịa recovery nghiệp vụ cụ thể; chỉ giữ các guard/fail-close kỹ thuật cần thiết.
- Khi operator chỉ ra điểm bắt lỗi, AI phải xác định chính xác checkpoint và nơi resume, không chỉ thêm retry chung chung.

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

## 5. Quy tắc phân rã Function trong chế độ triển khai từng đoạn

Không cần chờ operator mô tả xong toàn bộ Function mới phân rã.

Mỗi đoạn mới được map ngay vào cấu trúc đang tích lũy:

```text
FUNCTION X
  1. Module A
     - Action A1
     - Action A2
     - Recovery points đã được operator chỉ ra

  2. Module B
     - bổ sung khi operator mô tả tới

  3. Module C
     - bổ sung khi operator mô tả tới
```

Khi Function dần hoàn thiện, mỗi Module cuối cùng phải có:

- precondition;
- actions chính;
- postcondition/PASS proof;
- typed/recoverable errors đã được xác định;
- retry policy nếu an toàn;
- checkpoint/resume point;
- escalation path nếu recovery cục bộ thất bại.

Function PASS condition được chốt khi flow thực tế đủ hoàn chỉnh, không cần giả định trước.

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

Nếu source cũ xung đột với mô tả mới, mô tả mới được coi là target mới; khi đang ở chế độ triển khai từng đoạn thì refactor phần liên quan phải bám target mới nhưng vẫn không được tự gọi runtime PASS trước live evidence.

## 8. Mục tiêu tích lũy

Trong quá trình triển khai, tài liệu phải dần tích lũy đủ:

```text
1. Function flow thực tế đã triển khai
2. Danh sách Module/Recipe
3. Danh sách Actions dùng lại
4. Các recovery points operator đã xác định
5. Retry/escalation policy tương ứng
6. Checkpoint/resume contract
7. PASS condition cho Module/Function khi đã đủ flow
8. Mapping source hiện tại -> kiến trúc target
```

Không còn yêu cầu phải chờ operator nói `kết thúc` mới được audit/refactor đoạn đang được yêu cầu triển khai.

## 9. ĐOẠN FLOW ĐÃ ĐƯỢC OPERATOR XÁC NHẬN — CHỐT

Phần dưới đây là đoạn đầu của một vòng AUTO hoàn chỉnh mà operator đã mô tả và đã xác nhận bản chuẩn hóa là đúng ý.

### 9.1 Startup sau Login / Restart — CHỐT

```text
Login game thành công
        ↓
Camera mặc định ở MAIN
        ↓
Bắt đầu timer 60 giây
        ↓
Trong SUỐT 60 giây:
    → liên tục check popup
    → popup nào xuất hiện thì đóng popup đó ngay
    → tiếp tục check popup khác
        ↓
Đủ 60 giây
        ↓
Dừng popup check
        ↓
Giữ camera ở MAIN
```

Quy tắc bắt buộc:

- 60 giây là **cửa sổ kiểm tra popup liên tục**, không phải ngủ 60 giây rồi mới bắt đầu quét.
- Sau login/restart, mặc định camera đã ở MAIN.
- Không dùng `goDown(1)` chỉ để ép exact-main sau login/restart.
- Startup kết thúc sau khi đủ 60 giây check/đóng popup theo flow trên.

### 9.2 Mở quầy và bán VP theo Function — CHỐT

Sau Startup:

```text
Mở quầy hàng
        ↓
VIEW 1 = 8 ô đầu mặc định
```

Tại mỗi View:

```text
Có ô vàng (VP đã bán)?
   ├─ Có
   │    ↓
   │  Thu vàng
   │    ↓
   │  Check QC VP nếu có
   │
   └─ Không
        ↓
      Check QC VP nếu có
```

Sau đó tìm ô trống.

#### Nếu có ô trống

```text
click ô trống
→ mở Kho
→ chọn Kho 2 / Kho thành phẩm
→ quét VP được phép bán theo Function hiện tại
```

Với từng VP hợp lệ:

```text
Tìm thấy VP
→ click VP
→ check số lượng
→ số lượng >= 10?
   ├─ Có  → đăng bán x10 → tiếp tục lấp ô trống khác nếu còn
   └─ Không → bỏ qua VP này → thử VP hợp lệ tiếp theo
```

Nếu không còn VP nào thuộc Function có số lượng đủ 10:

```text
đóng Kho
→ đóng Quầy
→ check chức năng tùy chọn
→ nếu có thì chạy chức năng tùy chọn
→ nếu không có thì bắt đầu vòng Function mới
```

#### Nếu View hiện tại không có ô trống

```text
swipe chuyển View bằng đúng 2 nhịp
→ scan View tiếp theo
→ chạy lại logic:
   vàng → thu vàng → QC → tìm ô trống → bán VP
```

Tổng cộng tối đa 5 View:

```text
VIEW 1
→ VIEW 2
→ VIEW 3
→ VIEW 4
→ VIEW 5
```

View 5 là lượt kiểm tra cuối để tránh bỏ sót các ô cuối quầy.

### 9.3 Điều kiện kết thúc Sale — CHỐT

Sale kết thúc khi:

```text
A. Không còn VP hợp lệ có số lượng >= 10
hoặc
B. Đã kiểm tra đủ 5 View và không còn ô trống có thể sử dụng
```

Sau đó:

```text
đóng Kho nếu còn mở
→ đóng Quầy
→ check chức năng tùy chọn
   ├─ có → chạy chức năng tùy chọn
   └─ không → bắt đầu vòng Function mới
```

### 9.4 Phân nhóm kiến trúc tạm thời cho đoạn đã chốt

```text
GameStartupModule
  ├─ Login verification
  ├─ Popup watch 60s
  └─ Popup close actions

SellFunctionVpModule
  ├─ Open stall action
  ├─ Scan sold/gold slots action
  ├─ Collect gold action
  ├─ QC check/action
  ├─ Find empty stall slot action
  ├─ Open warehouse action
  ├─ Select warehouse 2 action
  ├─ Scan allowed VP action
  ├─ Quantity >=10 check
  ├─ List x10 action
  ├─ Stall next-view action = đúng 2 swipe nhịp
  └─ Close warehouse/stall actions

Function/Scheduler boundary
  ├─ optional function check
  └─ start selected Function loop
```

Lưu ý: Recovery point chi tiết của từng thao tác được bổ sung khi operator đánh dấu nhánh lỗi tương ứng trong lúc triển khai.
