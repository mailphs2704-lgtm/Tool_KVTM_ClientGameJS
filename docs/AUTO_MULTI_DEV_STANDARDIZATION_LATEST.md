# AUTO MULTI DEV — STANDARDIZATION LATEST

Cập nhật: 2026-09-11
Trạng thái: DESIGN / SPECIFICATION IN PROGRESS
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`

> Đây là tài liệu chuẩn hóa tích lũy cho phiên thiết kế AUTO KVTM MULTI DEV hiện tại. Mục tiêu là giữ chính xác các quyết định đã thống nhất qua nhiều phiên chat. Không được tự suy diễn phần chưa chốt thành runtime contract.

## 0. Quy tắc trạng thái tài liệu

Các nhãn dùng trong tài liệu:

- **CHỐT**: user đã yêu cầu/xác nhận, được xem là mục tiêu kiến trúc chính thức.
- **SOURCE CÓ SẴN**: source hiện tại đã có một phần cơ chế tương ứng, nhưng có thể chưa đúng chuẩn mới.
- **READY FOR LIVE TEST**: source đã thay đổi nhưng chưa được operator xác nhận runtime PASS.
- **CẦN CHỐT**: có đề xuất hoặc xung đột logic cần user xác nhận trước khi triển khai.
- **KHÔNG ĐƯỢC TỰ PASS**: build/static PASS không thay thế live/runtime evidence.

## 1. Mục tiêu chuẩn hóa tổng thể — CHỐT

AUTO được chuẩn hóa thành các tầng rõ vai trò:

```text
AUTO MAIN / SCHEDULER
        ↓
FUNCTION
        ↓
MODULE
        ↓
ACTION

        ↕
GLOBAL RECOVERY / ERROR MANAGER
```

### AUTO MAIN / Scheduler

Chỉ điều phối:

- Function đang chọn;
- vòng Function;
- lịch bán định kỳ;
- maintenance định kỳ;
- lịch restart ClientJS;
- safe boundary giữa các vòng.

Scheduler không được chứa click/vision nghiệp vụ chi tiết và không được coi recovery là một vòng Function mới.

### Function

Function chỉ mô tả một vòng nghiệp vụ cần làm gì và thứ tự các Module/Recipe.

Function không copy:

- logic bán VP;
- logic sửa máy;
- logic đóng popup;
- logic retry/recovery;
- logic restart/refresh dùng chung.

### Module

Module là một khối nghiệp vụ có thể tái sử dụng, ví dụ:

- startup/login/popup;
- bán VP;
- production;
- sửa máy;
- trồng/thu hoạch;
- sang nhà bạn;
- restart ClientJS.

### Action

Action là thao tác nguyên tử/tái sử dụng:

- click;
- swipe;
- nhận diện ảnh;
- mở/đóng panel;
- chọn kho;
- chọn VP;
- đợi state;
- verify state;
- trồng/thu hoạch theo path/count đã xác minh.

### Global Recovery

Recovery nhận typed error/event từ Module/Action, xử lý theo policy chung, sau đó đưa control về đúng checkpoint đang dở.

Nguyên tắc bắt buộc:

```text
Recovery != Function completion
Recovery = interrupt -> recover -> resume
```

## 2. Module bắt buộc: Game Startup / Login / Popup — CHỐT

Tên logic đề xuất: `GameStartupModule`.

### Luồng bắt buộc

```text
ClientJS OPEN / RESTART
        ↓
Login game hoàn tất
        ↓
LOGIN_VERIFIED
        ↓
CHỜ 60 GIÂY
        ↓
Popup sweep
        ↓
Nhận diện popup nào đang tồn tại
        ↓
Đóng đúng popup
        ↓
Quét lại
        ↓
Không còn popup cần xử lý
        ↓
Xác minh exact-main
        ↓
STARTUP PASS
```

### Contract 60 giây

- 60 giây là **settle delay sau login hoàn tất**, mục tiêu là chờ các popup tải chậm hiển thị đầy đủ.
- 60 giây **không thay thế vision/verification**.
- Không blind-click một chuỗi tọa độ rồi coi là PASS.
- Sau 60 giây vẫn phải scan/đóng popup và verify exact-main.
- Chỉ áp dụng sau ClientJS open mới hoặc restart; không chạy sau mỗi Function loop.

## 3. Module bắt buộc: Bán VP theo Function — CHỐT

Tên logic đề xuất: `SellFunctionVpModule`.

Function/Scheduler chỉ truyền context chính:

```text
function_id
allowed_item_ids
```

Module bán tự chịu trách nhiệm toàn bộ giao dịch.

### Luồng nghiệp vụ

```text
đảm bảo exact-main
        ↓
mở quầy
        ↓
check ô vàng
        ↓
thu vàng
        ↓
check QC VP / bật QC miễn phí nếu hợp lệ
        ↓
check vị trí ô trống
        ↓
mở Kho
        ↓
chọn Kho thành phẩm
        ↓
quét đúng VP được Function cho phép
        ↓
xác minh số lượng đủ 10
        ↓
bán đúng x10
        ↓
lặp đến khi hết ô trống quầy hoặc hết VP hợp lệ
        ↓
đóng kho/panel nếu còn mở
        ↓
đóng quầy
        ↓
trở về + xác minh main
        ↓
SALE PASS
```

### View quầy: 4 -> 5 — CHỐT

Yêu cầu mới:

```text
VIEW 1
VIEW 2
VIEW 3
VIEW 4
VIEW 5 = FINAL OVERLAP / END CHECK
```

Mục tiêu View 5 là kéo/check thêm một lượt để không bỏ sót 2 ô cuối quầy.

View 5 vẫn phải chạy nghiệp vụ scan cần thiết như view bình thường:

- vàng;
- QC;
- ô trống;
- bán VP.

Không được coi swipe ít thay đổi hoặc chạm boundary cuối quầy là lỗi chỉ vì camera không dịch như các view trước.

### Sale recovery progress — SOURCE READY FOR LIVE TEST

Source hiện tại đã đổi policy để một lượt sale recovery được tính là có tiến triển khi:

- treo được ít nhất một listing; hoặc
- thu được ít nhất một ô vàng.

Nếu cả hai đều bằng 0 mới fail-close để tránh loop recovery vô hạn.

Commit source liên quan trước giai đoạn chuẩn hóa tài liệu: `b52befd4dbfab5c3a17175f1ddd43948244dcf32`.

## 4. Module bắt buộc: Sửa máy sau Production — CHỐT

Tên logic đề xuất: `RepairMachineModule`.

Sau mỗi production hoàn tất phải đi qua module sửa máy dùng chung:

```text
Production hoàn tất
        ↓
RepairMachineModule
        ↓
Máy cần sửa?
   ├─ Không -> PASS
   └─ Có
        ↓
      thực hiện sửa
        ↓
      verify kết quả
        ↓
      PASS
```

Không tạo một bản recovery/sửa máy riêng cho từng Function nếu cùng một cơ chế có thể dùng chung. Context máy/sản phẩm hiện tại được truyền vào module.

## 5. Module maintenance: Sang nhà bạn — CHỐT MỤC TIÊU

Tên logic hiện có/phù hợp: `FriendRefreshModule`.

Cùng một thao tác sang nhà bạn -> về nhà chính có **hai mục đích độc lập**.

### 5.1 Periodic Friend Refresh

Sau mỗi N vòng Function theo cấu hình:

```text
Function loop PASS
        ↓
completed_loops += 1
        ↓
đủ N vòng?
  ├─ Không -> tiếp tục
  └─ Có
       ↓
     sang nhà bạn
       ↓
     scene settle
       ↓
     trở về nhà chính
       ↓
     re-prove exact-main
       ↓
     tiếp tục vòng kế
```

Mục tiêu:

- làm mới scene;
- xóa/tránh trạng thái item treo;
- giảm lag/kẹt màn hình do state lâu chạy.

### 5.2 Friend Refresh như Recovery Escalation

Khi AUTO gặp lỗi chưa có giải pháp chuyên biệt, hoặc giải pháp hiện tại thử lại nhiều lần vẫn không giải quyết được:

```text
module/action lỗi
        ↓
local retry có giới hạn
        ↓
vẫn FAIL
        ↓
Friend Refresh
        ↓
sang nhà bạn
        ↓
về nhà chính
        ↓
exact-main
        ↓
resume checkpoint
        ↓
thử lại thao tác/module đang dở
```

Yêu cầu user: local retry khoảng **3-5 lượt** trước khi nâng cấp lên Friend Refresh.

### Retry policy — CẦN CHỐT CHI TIẾT

Đề xuất kỹ thuật hiện tại: không chọn ngẫu nhiên 3/4/5. Mỗi loại lỗi/module nên có `LOCAL_RETRY_LIMIT` xác định, ví dụ 3 hoặc 5 tùy độ an toàn của thao tác. Chưa coi con số cụ thể của từng module là contract cho tới khi user chốt.

### Counter phải độc lập — CHỐT NGUYÊN TẮC

Periodic Friend Refresh và Recovery Friend Refresh không dùng chung bộ đếm.

Một lần sang nhà bạn do lỗi không được tính là mốc N vòng của maintenance định kỳ.

## 6. Module maintenance: Restart ClientJS — CHỐT MỤC TIÊU

Tên logic đề xuất: `ClientRestartModule`.

Mục đích:

- làm mới ClientJS;
- giảm state/rác tích tụ sau thời gian chạy dài;
- hạn chế giật/lag/chậm;
- hạn chế RAM tăng do client lâu chạy;
- tạo Bridge/worker/session mới đúng profile.

### Thời gian restart định kỳ: 2h -> 3h — CHỐT

Target chuẩn hóa mới:

```text
CLIENT_RESTART_INTERVAL = 3 giờ
```

Source/runtime cũ đang có contract 2 giờ. **Không được gọi 3 giờ là runtime PASS cho tới khi refactor source và live test sau giai đoạn thiết kế.**

### Scheduled Restart — CHỐT

Restart định kỳ chỉ được xảy ra tại safe Function boundary:

```text
đủ 3 giờ
        ↓
đang giữa Function?
  ├─ Có -> defer
  │        tiếp tục Function hiện tại
  └─ Không / Function vừa PASS
           ↓
         restart đúng ClientJS/profile
```

Sau restart:

```text
rebind đúng profile
→ worker/Bridge generation mới
→ login hoàn tất
→ chờ 60 giây
→ popup cleanup
→ exact-main
→ tiếp tục scheduler
```

## 7. Restart như cấp Recovery cao hơn — USER REQUIREMENT + CẦN CHỐT CHI TIẾT

Yêu cầu user:

```text
lỗi chưa giải quyết
→ retry
→ Friend Refresh #1
→ vẫn lỗi
→ Friend Refresh #2
→ vẫn lỗi
→ restart ClientJS
```

Mục tiêu là Friend Refresh là cấp recovery rẻ hơn, restart chỉ dùng khi hai lượt Friend Refresh không giải quyết được trạng thái kẹt.

### Xung đột cần giữ rõ trong tài liệu

User đồng thời yêu cầu scheduled restart chỉ khi Function hoàn tất. Nhưng một recovery restart có thể phát sinh vì Function **không thể hoàn tất do đang kẹt**.

Đề xuất kỹ thuật hiện tại:

- **Scheduled Restart**: tuyệt đối chỉ sau Function PASS.
- **Emergency/Recovery Restart**: nếu được user chốt cho phép giữa Function thì bắt buộc lưu durable checkpoint trước restart và resume đúng Function/Module đang dở sau startup.

Phần cho phép Emergency Restart giữa Function **chưa được tự coi là CHỐT** nếu user chưa xác nhận rõ.

Không được thiết kế restart vô hạn. Cần một `EMERGENCY_RESTART_LIMIT` cho cùng checkpoint trước khi fail-close; con số cụ thể chưa chốt.

## 8. Global Recovery / Checkpoint — CHỐT NGUYÊN TẮC

Global recovery là cơ chế chung cho toàn AUTO, không thuộc riêng Function 1/2.

Các Function/Recipe/Module chỉ phát typed error/event và cung cấp context. Recovery policy nằm ở lớp dùng chung.

Luồng chuẩn:

```text
Function loop N
  -> Recipe/Module
     -> lỗi recoverable
     -> giữ checkpoint
     -> recovery
     -> quay lại đúng state/tầng
     -> resume CÙNG module
  -> module PASS
  -> Function PASS
  -> lúc này scheduler mới được tăng loop
```

### Source hiện có — READY FOR LIVE TEST

Commit `b52befd4dbfab5c3a17175f1ddd43948244dcf32` đã thêm module checkpoint lifecycle:

- `MODULE_STARTED`;
- `MODULE_INTERRUPTED`;
- `MODULE_RESUMED`;
- `MODULE_COMPLETED`.

Production `InventoryFull` / `WrongProductionMachine` đã được nối vào checkpoint executor ở source, nhưng chưa được coi runtime PASS nếu chưa có live evidence từ operator.

## 9. Active checkpoint trong RAM — CHỐT

User đã đồng ý checkpoint RAM theo nguyên tắc nhẹ tài nguyên.

### Mỗi profile chỉ giữ một ActiveCheckpoint

```text
profile
  -> 1 ActiveCheckpoint
```

Checkpoint được **update tại chỗ**, không append lịch sử checkpoint liên tục.

Ví dụ tiến độ:

```text
3/9 -> update completed=3
4/9 -> update completed=4
```

Không giữ 1 checkpoint riêng cho từng bước 1/9, 2/9, 3/9...

### Checkpoint chỉ chứa metadata/state nhỏ

Ví dụ:

```text
profile_id
function_id
function_loop
module_id
recipe_id
task_id
floor
step/progress
completed_count
target_count
retry_count
recovery_reason
```

### Tuyệt đối không giữ object nặng trong checkpoint

Không lưu:

- screenshot/frame OpenCV;
- numpy image array;
- template image;
- toàn bộ automation object;
- driver/ClientJS object;
- log history không giới hạn.

Mục tiêu là checkpoint chỉ vài KB/profile và gần như không đáng kể so với ClientJS/OpenCV/capture runtime.

## 10. Durable checkpoint — CẦN CHỐT KHI THIẾT KẾ RESTART RECOVERY

Nếu chỉ retry/navigation/Friend Refresh mà Python worker vẫn sống, ActiveCheckpoint trong RAM là đủ.

Nếu recovery cần restart ClientJS/worker làm mất process state, cần một checkpoint nhỏ bền qua restart, ví dụ JSON state.

Đề xuất:

```text
Runtime ActiveCheckpoint (RAM)
        +
DurableCheckpoint (disk, chỉ khi cần sống qua restart)
```

Sau successful resume/completion phải clear durable checkpoint để không resume nhầm công việc cũ.

Đây là đề xuất kỹ thuật để giải quyết recovery restart; chưa coi toàn bộ chi tiết persistence là CHỐT cho tới khi user xác nhận Emergency Restart behavior.

## 11. Recovery ladder tích lũy hiện tại

Mô hình mục tiêu hiện tại:

```text
Typed/Specialized Recovery nếu đã có
        ↓
Local retry có giới hạn
        ↓
Friend Refresh #1
        ↓
resume checkpoint + retry
        ↓
Friend Refresh #2 nếu vẫn lỗi
        ↓
resume checkpoint + retry
        ↓
Recovery Restart nếu policy cho phép
        ↓
resume checkpoint
        ↓
Fail-close nếu vượt giới hạn recovery
```

Không được:

- retry vô hạn;
- Friend Refresh vô hạn;
- restart vô hạn;
- reset Function loop chỉ vì recovery;
- tăng `function_loops` khi Function chưa PASS.

## 12. Hai chuỗi phải tách biệt

### Normal maintenance

```text
Function loop PASS
→ periodic sale nếu đến hạn
→ periodic Friend Refresh nếu đủ N vòng
→ scheduled restart nếu quá 3h và đang ở safe boundary
→ vòng mới
```

### Error recovery

```text
Function đang dở
→ typed error / unknown recoverable state
→ local recovery/retry
→ Friend Refresh escalation
→ recovery restart nếu policy đã chốt
→ resume Function đang dở
→ Function PASS
→ lúc đó mới được tăng vòng
```

Không trộn bộ đếm của hai chuỗi.

## 13. Trạng thái source hiện tại so với target chuẩn hóa

Đây là tài liệu **target architecture**, không có nghĩa source đã đạt hết các mục sau.

Đã có một phần source:

- RecoveryManager / typed events;
- navigation recovery;
- production recovery;
- material shortage recovery;
- Friend Refresh định kỳ;
- ClientJS restart 2h hiện tại;
- module checkpoint source ở commit `b52befd4`.

Target mới chưa triển khai đầy đủ:

- startup settle delay 60 giây sau LOGIN_VERIFIED;
- sale view 5 final overlap;
- chuẩn hóa RepairMachine thành module contract chung;
- Friend Refresh escalation cho lỗi chưa có handler;
- restart interval 3h;
- recovery escalation sau 2 Friend Refresh;
- durable checkpoint nếu Emergency Restart được chốt;
- chuẩn hóa toàn bộ `Actions` thành thư viện thao tác dùng chung/parameterized theo mục 16.

## 14. Quy tắc triển khai sau khi user nói "kết thúc" phần thiết kế

Trong giai đoạn user đang trình bày cấu trúc:

- **KHÔNG refactor runtime theo spec mới trừ khi user yêu cầu rõ.**
- Mỗi tin nhắn mới của user phải được tích lũy vào tài liệu này.
- Phải phản biện/xác định xung đột logic trước khi code.
- Phần user chưa xác nhận phải ghi `CẦN CHỐT`, không biến thành contract.

Khi user nói **"kết thúc"**:

1. chốt spec cuối;
2. audit source hiện tại so với spec;
3. lập thứ tự refactor ít regression nhất;
4. sửa từng module nhỏ;
5. cập nhật static contracts;
6. build;
7. live test từng recovery path;
8. chỉ ghi PASS khi có runtime evidence.

## 15. Read-first cho phiên chat/AI tiếp theo

Đọc theo thứ tự:

1. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — source of truth cho phiên chuẩn hóa hiện tại;
2. `docs/AUTO_MULTI_DEV_ACTIONS_STANDARDIZATION.md` — chi tiết contract Actions dùng chung;
3. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md`;
4. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md` — lịch sử/kiến trúc cũ, lưu ý có một số target cũ như restart 2h;
5. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`;
6. `AI_COORDINATION.md`.

Nếu có xung đột giữa target chuẩn hóa mới và tài liệu cũ, **không tự sửa theo tài liệu cũ**. Đối chiếu trạng thái CHỐT/CẦN CHỐT trong file này và hỏi/tiếp tục theo yêu cầu mới nhất của operator.

## 16. Actions dùng chung toàn dự án — CHỐT HƯỚNG

Operator xác định `Actions` là nơi chứa toàn bộ khả năng thao tác dùng chung của AUTO. Function/Module không tự viết lại click/swipe/vision nếu đã có action tương ứng.

### 16.1 Ranh giới trách nhiệm

```text
FUNCTION
= nói cần làm gì / thứ tự nghiệp vụ

MODULE / RECIPE
= ghép các action thành một công việc có nghĩa

ACTION
= biết cách thực hiện một thao tác tái sử dụng

GLOBAL RECOVERY
= xử lý retry/escalation/checkpoint
```

Action không được tự tăng vòng Function, tự đổi Function, tự schedule sale/friend/restart hoặc tự reset checkpoint.

### 16.2 Trồng/thu hoạch phải được tái sử dụng

Các thao tác như trồng 27, 28, 30 cây hoặc một nhóm 5 cây có thể tồn tại sẵn dưới dạng action/path đã xác minh.

Tuy nhiên Function không nên tự ghép kiểu `plant_27 + tự xử lý cây thứ 28` để đạt 28. Geometry phải nằm trong Actions.

Target ưu tiên:

```python
plant_crop(
    seed_template="cay_tuyet",
    path=PATH_28,
    expected_count=28,
)
```

hoặc API tương đương:

```python
select_seed("cay_tuyet")
plant_path(PATH_28, expected_count=28)
```

Nếu gameplay bắt buộc choreography riêng theo count, có thể expose `plant_27`, `plant_28`, `plant_30`, `plant_5`, nhưng các hàm này vẫn dùng chung primitive/path engine thay vì copy logic.

### 16.3 Loại cây và geometry phải tách nhau

Ví dụ:

```text
seed_template = cay_tuyet
path = PATH_28
expected_count = 28
```

Như vậy cùng path/action có thể dùng lại cho cây khác nếu gameplay cho phép.

### 16.4 Action có side effect phải hậu kiểm

Không coi `click`/`swipe` đã gửi là thành công. Action phải verify hậu điều kiện hoặc trả evidence/progress đủ cho Module/Recovery quyết định.

Ví dụ production/trồng cây bị ngắt giữa chừng phải biết đã hoàn thành bao nhiêu để resume phần còn lại, không replay mù từ đầu.

### 16.5 Actions không được trở thành một file/class khổng lồ

Nên chia theo domain, ví dụ:

```text
actions/
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

Tên/file cụ thể chỉ chốt sau khi audit source hiện tại; không di chuyển/xóa code chỉ để làm đẹp cấu trúc.

Chi tiết đầy đủ: `docs/AUTO_MULTI_DEV_ACTIONS_STANDARDIZATION.md`.
