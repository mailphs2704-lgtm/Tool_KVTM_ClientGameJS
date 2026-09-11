# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-11
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái phiên: **STANDARDIZATION DESIGN IN PROGRESS**

> Đây là tài liệu handoff hiện hành. Trong giai đoạn chuẩn hóa, tài liệu phải đọc đầu tiên là `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`.

## 1. Read-first bắt buộc

Theo thứ tự:

1. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — source of truth cho các quyết định chuẩn hóa mới nhất;
2. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md` — checkpoint/recovery source + target;
3. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md` — kiến trúc recovery nền;
4. `docs/AUTO_MULTI_DEV_CLIENT_RESTART.md` — implementation restart hiện tại, lưu ý vẫn là contract cũ 2h;
5. `docs/AUTO_MULTI_DEV_FRIEND_REFRESH.md`;
6. `docs/AUTO_MULTI_DEV_RECIPE_ARCHITECTURE.md`;
7. `AI_COORDINATION.md`.

Nếu target mới và tài liệu cũ xung đột, **không tự lấy contract cũ làm yêu cầu mới**. Kiểm tra nhãn `CHỐT / CẦN CHỐT / READY FOR LIVE TEST` trong `AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`.

## 2. Trạng thái quan trọng hiện tại

### Runtime/source trước giai đoạn chuẩn hóa

Các baseline lịch sử vẫn cần giữ regression:

- Function 1 đã từng được operator runtime PASS nhiều vòng;
- Sale VP baseline đã từng PASS;
- QC/Quảng cáo VP LIVE PASS;
- exact-main đa background đã có runtime proof;
- visual nút `XUỐNG` upper-floor dùng detector, không blind click tọa độ cũ;
- Friend Refresh định kỳ đã có source/runtime behavior;
- ClientJS restart implementation hiện tại vẫn đang dùng **2 giờ** cho tới khi target 3h được triển khai và test;
- Runtime dùng isolated worker + Bridge V3/CAPTURE3;
- persistent settings ở `%APPDATA%\KVTM Multi DEV`.

Các baseline trên không có nghĩa target chuẩn hóa mới đã PASS.

### Global recovery mới

Bug phát hiện từ quá trình chạy Function nhưng được xác định là **lỗi kiến trúc chung**, không thuộc riêng Function 2:

```text
module đang chạy
→ lỗi recoverable (ví dụ kho đầy)
→ recovery tạm rời module
→ xử lý lỗi
→ quay lại đúng checkpoint
→ tiếp tục cùng module
→ chỉ khi module + Function PASS mới cho scheduler tăng vòng
```

Commit source:

`b52befd4dbfab5c3a17175f1ddd43948244dcf32`
`feat: checkpoint recoverable AUTO modules before scheduler resume`

Đã thêm lifecycle:

- `MODULE_STARTED`;
- `MODULE_INTERRUPTED`;
- `MODULE_RESUMED`;
- `MODULE_COMPLETED`.

Production `InventoryFull` và `WrongProductionMachine` đã đi qua checkpoint executor ở source.

**Trạng thái: READY FOR LIVE TEST, chưa runtime PASS.**

## 3. Giai đoạn hiện tại: chuẩn hóa trước khi refactor

Operator đang trình bày cấu trúc mong muốn từng phần. Trong giai đoạn này:

- không tự refactor runtime theo spec mới nếu operator chưa nói kết thúc/triển khai;
- mỗi yêu cầu mới phải cập nhật tích lũy vào `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`;
- phải góp ý khi logic có xung đột;
- phần chưa được xác nhận phải ghi `CẦN CHỐT`, không tự biến thành contract.

## 4. Các mục đã thống nhất tới thời điểm này

### 4.1 Game Startup / Login / Popup

Sau ClientJS open/restart:

```text
login hoàn tất
→ LOGIN_VERIFIED
→ chờ 60 giây
→ scan/đóng toàn bộ popup đã biết
→ scan lại
→ verify exact-main
→ startup PASS
```

60 giây chỉ là settle delay, không thay thế vision/verification và không chạy sau mỗi Function loop.

### 4.2 Sale VP theo Function

Sale module phải tự chịu trách nhiệm:

- exact-main;
- mở quầy;
- check + thu vàng;
- check/bật QC VP hợp lệ;
- tìm ô trống;
- mở kho + chọn Kho thành phẩm;
- quét đúng VP thuộc Function;
- chỉ bán khi đủ đúng batch x10;
- bán lần lượt tới hết ô trống hoặc hết VP hợp lệ;
- đóng panel/quầy và về main.

Thay đổi target mới:

```text
4 view -> 5 view
VIEW 5 = final overlap/end check
```

View 5 nhằm bắt 2 ô cuối đang bị bỏ sót. Swipe ở cuối quầy ít/không dịch không được tự coi là lỗi boundary.

### 4.3 Repair Machine

Sau mỗi production hoàn tất phải đi qua một module sửa máy dùng chung. Không copy logic sửa máy theo từng Function nếu cùng một cơ chế có thể reuse.

### 4.4 Friend Refresh

Có hai vai trò riêng:

1. periodic maintenance sau N vòng;
2. recovery escalation khi local retry không giải quyết được lỗi.

Recovery Friend Refresh phải về lại exact-main rồi resume checkpoint/module đang dở.

Periodic counter và recovery counter độc lập.

### 4.5 Restart ClientJS

Target interval mới:

```text
3 giờ
```

Scheduled restart chỉ sau Function PASS / safe boundary. Nếu tới hạn giữa Function thì defer.

Sau restart target startup phải đi qua:

```text
rebind đúng profile
→ worker/Bridge mới
→ login
→ wait 60s
→ popup cleanup
→ exact-main
→ scheduler tiếp tục
```

Source hiện tại vẫn là 2h; chưa sửa thành 3h trong giai đoạn thiết kế này.

### 4.6 Recovery escalation

Yêu cầu operator:

```text
lỗi chưa có giải pháp / retry vẫn lỗi
→ Friend Refresh #1
→ retry/resume
→ Friend Refresh #2
→ retry/resume
→ vẫn lỗi thì nâng cấp restart ClientJS
```

Chi tiết Emergency Restart giữa Function còn cần chốt vì scheduled restart có contract khác. Nếu cho phép restart giữa Function thì phải có checkpoint bền qua worker/process restart.

### 4.7 Checkpoint RAM

Đã thống nhất:

- mỗi profile chỉ giữ một `ActiveCheckpoint`;
- update tại chỗ, không append vô hạn;
- chỉ lưu metadata/state nhỏ;
- không giữ screenshot, OpenCV frame, numpy image, template image, automation object, driver object hoặc log history không giới hạn.

Checkpoint mục tiêu chỉ vài KB/profile và không đáng kể so với ClientJS/OpenCV/capture.

## 5. Điểm CẦN CHỐT ở các lượt trao đổi sau

Chưa tự triển khai các chi tiết sau cho tới khi operator xác nhận:

- retry limit chính xác cho từng loại lỗi/module; operator nêu khoảng 3-5 lần, đề xuất kỹ thuật là limit cố định theo policy, không random;
- Emergency/Recovery Restart có được phép xảy ra giữa Function hay không;
- nếu có Emergency Restart giữa Function: schema + persistence + clear rule của durable checkpoint;
- số lần Emergency Restart tối đa cho cùng checkpoint trước fail-close;
- các module/function tiếp theo mà operator chưa trình bày.

## 6. Nguyên tắc recovery không được regression

- lỗi recoverable không được làm scheduler tự mở vòng Function mới;
- checkpoint chỉ clear sau khi công việc tương ứng thật sự hoàn tất;
- generic `ScreenTimeout` không blind retry nếu thao tác có thể đã tạo side effect;
- không retry/Friend Refresh/restart vô hạn;
- Function không copy production/recovery policy;
- sale/recovery phải quay về đúng state/tầng/module cần resume;
- build/static PASS không được ghi thành runtime PASS.

## 7. Kiến trúc mục tiêu hiện tại

```text
AUTO MAIN / SCHEDULER
        ↓
FUNCTION
        ↓
MODULE / RECIPE
        ↓
ACTION

        ↕
GLOBAL RECOVERY / ERROR MANAGER
        ↕
ACTIVE CHECKPOINT (RAM, metadata-only)
```

Nếu sau này chốt Recovery Restart giữa Function:

```text
ACTIVE CHECKPOINT (RAM)
        +
DURABLE CHECKPOINT (disk, nhỏ, chỉ để sống qua restart)
```

## 8. Source paths quan trọng

```text
components/clientjs-auto/kvtm_automation/recovery/
components/clientjs-auto/kvtm_automation/recipes/
components/clientjs-auto/kvtm_automation/workflows/auto_main/
components/clientjs-auto/kvtm_automation/workflows/auto_vp_sale/
components/clientjs-auto/kvtm_automation/workflows/auto_function_one/
components/clientjs-auto/kvtm_automation/workflows/auto_function_two/
components/clientjs-auto/kvtm_automation/actions/
```

Checkpoint source mới:

```text
components/clientjs-auto/kvtm_automation/recovery/module_execution.py
```

## 9. Build/operator entry

Sau khi bước thiết kế kết thúc và bắt đầu triển khai source:

```text
KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Không được coi build thành công là runtime PASS. Live test vẫn bắt buộc cho behavior Windows/ClientJS/recovery.

## 10. Commit/tài liệu mốc mới

Source checkpoint:

- `b52befd4dbfab5c3a17175f1ddd43948244dcf32` — checkpoint recoverable modules before scheduler resume.

Documentation standardization:

- `c714a55962b5ded5bbad389fa1b9bf2bb9c25e72` — tạo `AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`;
- `56a4737b53243212cb6b5f251577d2e62ce427a1` — cập nhật global recovery/checkpoint contract.

## 11. Quy tắc cho phiên chat/AI tiếp theo

Nếu operator tiếp tục nói về cấu trúc AUTO:

1. đọc `AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md`;
2. tiếp tục cộng dồn yêu cầu mới, không bắt operator trình bày lại;
3. phản biện chỗ có xung đột;
4. cập nhật tài liệu sau các mốc đã thống nhất;
5. chưa refactor source cho tới khi operator yêu cầu triển khai/kết thúc giai đoạn thiết kế.

Nếu operator nói **"kết thúc"** phần chuẩn hóa:

1. chốt spec cuối;
2. audit source hiện tại so với spec;
3. lập thứ tự refactor ít regression nhất;
4. triển khai từng module nhỏ;
5. cập nhật static contracts;
6. build;
7. live test;
8. chỉ ghi PASS theo evidence thực tế.
