# AUTO MULTI DEV — CONFIRMED FLOW LATEST

Cập nhật: 2026-09-11
Trạng thái: DESIGN / SPECIFICATION IN PROGRESS
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`

> Đây là phần mở rộng CHỐT mới nhất của bộ tài liệu chuẩn hóa. Nếu wording cũ trong tài liệu trước mâu thuẫn với file này về Startup/Popup, Sale VP hoặc quy ước goUp, dùng file này làm contract mới hơn. Chưa refactor runtime/source cho tới khi operator nói `kết thúc` hoặc yêu cầu triển khai rõ ràng.

## 1. Startup / Login / Popup — CHỐT

Sau ClientJS open mới hoặc restart:

```text
Login game thành công
        ↓
Camera mặc định ở MAIN
        ↓
Bắt đầu timer 60 giây
        ↓
TRONG SUỐT 60 GIÂY:
    liên tục check popup
    popup nào xuất hiện → đóng popup đó ngay
    tiếp tục scan popup
        ↓
Đủ 60 giây
        ↓
Dừng Popup Check
        ↓
Giữ camera MAIN
        ↓
Startup hoàn tất
```

Quy tắc bắt buộc:

- Không phải `sleep 60s rồi mới scan popup`.
- Trong 60 giây, popup xuất hiện lúc nào xử lý ngay lúc đó.
- Hết 60 giây thì kết thúc vòng popup check.
- Sau login/restart, camera mặc định đã ở MAIN.
- Không gọi `goDown(1)` chỉ để prove/exact-main sau login/restart.
- Không tự điều hướng camera nếu chưa có lỗi/navigation recovery yêu cầu.

Điểm này **thay thế wording cũ** kiểu `LOGIN_VERIFIED → CHỜ 60 GIÂY → popup sweep → exact-main`.

## 2. Sale VP trước vòng Function — CHỐT

### 2.1 Mở quầy và quét View 1

Sau Startup hoặc khi Scheduler yêu cầu Sale:

```text
Mở quầy hàng
        ↓
VIEW 1 = 8 ô đầu mặc định
        ↓
scan trạng thái quầy
```

Trong mỗi View:

```text
Có ô vàng (VP đã bán)?
  ├─ Có → thu vàng → check QC VP nếu có
  └─ Không → check QC VP nếu có
        ↓
Tìm ô trống
```

QC và thu vàng là phần của module Sale, không phải Function-specific action.

### 2.2 Khi có ô trống

```text
Có ô trống
    ↓
click ô trống
    ↓
mở Kho
    ↓
chọn Kho 2 / kho thành phẩm
    ↓
quét VP được phép bán theo Function hiện tại
```

Với từng VP hợp lệ:

```text
Tìm thấy VP
    ↓
click chọn VP
    ↓
check số lượng
    ↓
SL >= 10 ?
  ├─ Có → đăng bán x10 → quay lại tìm ô trống tiếp theo
  └─ Không → bỏ qua VP này → tìm VP hợp lệ kế tiếp
```

Không dừng sau khi đăng một VP nếu quầy vẫn còn ô trống và còn VP khác đủ batch 10.

Nếu không còn VP nào hợp lệ đủ 10:

```text
đóng Kho
→ đóng Quầy
→ check chức năng tùy chọn
   ├─ có → chạy chức năng tùy chọn
   └─ không → bắt đầu vòng Function mới
```

### 2.3 Khi View hiện tại không có ô trống

```text
Không có ô trống
    ↓
SWIPE 2 NHỊP
    ↓
chuyển sang View kế tiếp
    ↓
scan lại từ đầu:
  ô vàng → thu vàng → QC → ô trống → bán VP
```

Tổng cộng 5 View:

```text
VIEW 1
VIEW 2
VIEW 3
VIEW 4
VIEW 5 = final/end check
```

`swipe 2 nhịp` phải được đóng gói thành một Action dùng chung, ví dụ logic `stall_next_view()`. Function không tự gọi hai swipe primitive rời rạc.

View 5 là lần kiểm tra cuối nhằm không bỏ sót các ô cuối quầy. Ở boundary cuối, việc swipe ít/không dịch không tự động được coi là lỗi nếu scan View cuối vẫn thực hiện được.

### 2.4 Điều kiện kết thúc Sale

Sale kết thúc khi:

```text
A. không còn VP hợp lệ đủ SL >= 10
hoặc
B. đã kiểm tra đủ 5 View và không còn ô trống sử dụng được
```

Sau đó:

```text
đóng Kho nếu còn mở
→ đóng Quầy
→ check chức năng tùy chọn
→ nếu không có chức năng tùy chọn thì bắt đầu vòng Function mới
```

## 3. Quy ước Navigation Actions / goUp — CHỐT

`goUp(n)` là **mode hành động**, không được hiểu mặc định là `n` lần swipe một tầng.

### goUp(1)

```text
Loại: swipe ngắn
Ý nghĩa: kéo lên 1 tầng
```

Source tham chiếu hiện tại dùng gesture khoảng:

```text
(514,214) → (514,314)
```

### goUp(2)

```text
Loại: click anchor/chậu mốc
Ý nghĩa: click chậu đầu tiên của tầng 4
Ví dụ trạng thái: nếu đang tầng 1 → nhảy camera lên tầng 3
```

Đây là primitive riêng. Tuyệt đối không thay bằng `goUp(1)` hai lần.

Tọa độ anchor click chính xác chưa được khóa trong tài liệu; không tự lấy tọa độ chậu khác để thay thế.

### goUp(4)

```text
Loại: swipe dài
Ý nghĩa: kéo đoạn 4 tầng
Ví dụ trạng thái: nếu đang tầng 1 → lên tầng 5
```

Source tham chiếu hiện tại dùng gesture:

```text
(387,69) → (387,918)
```

Đây là một gesture riêng, không phải 4 lần `goUp(1)`.

### goUp(3)

```text
CHƯA ĐỊNH NGHĨA
```

Không tự suy đoán hoặc map sang click/swipe cho tới khi operator quy ước.

### Dispatcher mục tiêu

Conceptual contract:

```text
goUp(1) → short one-floor swipe
goUp(2) → anchor click jump
goUp(4) → long four-floor swipe
goUp(3) → reject / undefined
```

Navigation Action phải cập nhật state/floor candidate chỉ sau khi thao tác thành công/đủ evidence. Nếu thao tác lỗi, Recovery giữ checkpoint cũ và không được tự tăng tầng theo số mode.

## 4. Mapping kiến trúc của phần vừa chốt

```text
GameStartupModule
  ├─ login action
  ├─ popup scanner
  └─ popup close action

SellFunctionVpModule
  ├─ open stall
  ├─ scan 8 visible slots
  ├─ collect sold-gold
  ├─ check/enable QC
  ├─ find empty slot
  ├─ open warehouse
  ├─ select warehouse 2
  ├─ find allowed VP
  ├─ verify quantity >= 10
  ├─ list x10
  ├─ stall_next_view() = 2 swipe beats
  └─ close warehouse/stall

NavigationActions
  ├─ goUp(1) = one-floor swipe
  ├─ goUp(2) = anchor click jump
  ├─ goUp(4) = four-floor long swipe
  └─ goUp(3) = undefined
```

Scheduler/Function chỉ quyết định thứ tự nghiệp vụ. Các click/swipe/vision cụ thể thuộc Actions; retry/escalation thuộc Global Recovery.

## 5. Trạng thái triển khai

- Các flow trong tài liệu này: **CHỐT về thiết kế**.
- Chưa refactor runtime/source theo flow mới.
- Source hiện tại có thể khác ở popup timing, exact-main behavior, sale views hoặc navigation dispatcher.
- Không gọi runtime PASS cho tới khi giai đoạn thiết kế kết thúc, refactor được thực hiện và operator live-test xác nhận.

## 6. Điểm chờ operator mô tả tiếp

Operator sẽ tiếp tục mô tả một vòng Function hoàn chỉnh từ đầu tới cuối và đánh dấu các nhánh lỗi. Khi nhận phần tiếp theo, cần:

1. giữ nguyên các contract đã chốt trong file này;
2. phân loại từng đoạn thành Action / Module-Recipe / Function orchestration / Recovery;
3. xác định checkpoint/resume point;
4. chỉ ra xung đột/rủi ro logic nếu có;
5. tiếp tục cập nhật tài liệu, chưa code cho tới khi operator nói `kết thúc`.
