# AUTO MULTI DEV — STANDARDIZATION CHECKPOINT 2026-09-11

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **SOURCE REFACTOR IN PROGRESS — NOT RUNTIME PASS**

Tài liệu này là checkpoint chống mất ngữ cảnh trong lúc chuẩn hóa toàn bộ AUTO. Nếu tài liệu cũ mâu thuẫn với checkpoint này, ưu tiên contract user đã chốt trong checkpoint và tài liệu standardization mới nhất.

## 1. Kiến trúc mục tiêu đang áp dụng

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
```

- Function chỉ mô tả thứ tự nghiệp vụ.
- Recipe/Module ghép các Action dùng chung.
- Action chỉ thực hiện thao tác có thể tái sử dụng; không sở hữu scheduler/retry escalation.
- Recovery giữ checkpoint và resume đúng công việc đang dở.
- Build/static PASS không đồng nghĩa runtime PASS.

## 2. Startup — source đã refactor, chờ live test

Contract user chốt:

- sau login/restart camera mặc định ở MAIN;
- không dùng `goDown(1)` để tạo exact-main ở startup;
- trong đủ 60 giây phải liên tục check popup;
- popup xuất hiện lúc nào đóng lúc đó;
- đủ 60 giây thì dừng popup watch;
- nếu startup MAIN contract bị mất thì fail-close, không tự điều hướng mù.

Source hiện có `GameSessionWorkflow.POPUP_WATCH_SECONDS = 60.0` và `mark_startup_exact_main()`.

## 3. Navigation Actions — source đã refactor, chờ live test

Quy ước user:

```text
goUp(1) = swipe lên 1 tầng
goUp(2) = click chậu mốc; từ tầng 1 đưa camera lên trạng thái tầng 3
goUp(4) = swipe dài 4 tầng; từ tầng 1 lên tầng 5
goUp(3) = chưa định nghĩa, phải fail-close
```

Không được hiểu `goUp(n)` là lặp `goUp(1)` n lần.

## 4. Sale theo Function — source đã refactor, chờ live test

- View 1 bắt đầu ở 8 ô đầu.
- Mỗi view: check/thu vàng -> check QC -> tìm ô trống -> mở Kho 2 -> tìm VP thuộc Function -> chỉ bán khi chứng minh được x10.
- Không đủ 10 thì bỏ VP đó và xét VP hợp lệ khác.
- Không có ô trống thì chuyển view bằng đúng 2 nhịp swipe.
- Tổng cộng 5 view; View 5 là final overlap/end check.
- Sale kết thúc khi không còn VP hợp lệ đủ 10 hoặc đã quét hết 5 view mà không còn chỗ dùng được.

## 5. Planting Actions — source đã refactor, chờ live test

Geometry/path được dùng chung theo count, tách khỏi loại cây:

- PATH 5
- PATH 27
- PATH 28
- PATH 30

Action nhận `crop/template + count/path`, không chứa business choreography riêng của Function.

## 6. Function 2 / TDHH — phân loại chính xác đã CHỐT

### Nguyên liệu cây

- **Hoa hồng** = cây/nguyên liệu.
- **Cây tuyết** = cây/nguyên liệu.
- PlantingActions chỉ xử lý hai nhóm nguyên liệu này.

### Thành phẩm

- **TDHH / Tinh dầu hoa hồng = VP thành phẩm, KHÔNG phải cây.**
- TDHH phải đi qua Production Action/Module (`RoseOilProductionActions`), không đi qua Planting Action.

Flow chuẩn:

```text
trồng/thu Hồng 35
→ về MAIN
→ trồng/thu Tuyết 28
→ đi tới máy TDHH
→ sản xuất VP TDHH x7
→ sửa máy
→ về MAIN
```

`RoseOilRecipe` chỉ là Recipe nghiệp vụ ghép Material Preparation + Navigation + VP Production + Repair + Return MAIN.

## 7. Recovery — source đang được gom về một manager dùng chung

- Mỗi Function dùng một `RecoveryManager` chung cho toàn chuỗi Recipe.
- `WrongProductionMachine` và `InventoryFull` là typed recovery đã có source path.
- Generic `ScreenTimeout` không được tự coi là recoverable nếu chưa có policy.
- Recovery không được trả control cho Scheduler như thể Function đã PASS.

Invariant:

```text
Recovery != Function PASS
Recovery = interrupt -> recover -> resume same checkpoint
```

## 8. Scheduled ClientJS Restart — source đã đổi target 3h, chưa runtime PASS

Target đã chốt:

```text
CLIENT_RESTART_INTERVAL = 3h = 10800s
```

Scheduled restart:

- không cắt ngang Function;
- nếu đến hạn giữa Function thì defer;
- Function hiện tại phải PASS trước;
- tại safe boundary chạy sale an toàn trước restart nếu cần;
- sau restart phải startup/login -> popup watch 60s -> MAIN -> tiếp tục scheduler.

Emergency recovery restart giữa Function vẫn cần durable checkpoint policy riêng; chưa được tự coi là hoàn tất.

## 9. Điểm audit còn phải xử lý tiếp

### 9.1 Worker catch-all đang trái kiến trúc mới

`components/clientjs-auto/worker/auto_multi_dev_worker.py` hiện vẫn có lớp catch-all runtime:

```text
Exception
→ normalize camera về MAIN
→ chạy lại pipeline
```

Vấn đề:

- có thể biến lỗi chưa đăng ký thành recovery chung;
- có thể làm mất checkpoint của Module đang dở;
- có thể khởi động lại Function từ đầu;
- chồng chéo trách nhiệm với `RecoveryManager`.

Chuẩn hóa tiếp theo phải làm worker trở thành lifecycle host; typed recovery thuộc `RecoveryManager`, unregistered error phải fail-close/log rõ, không tự restart business pipeline.

### 9.2 Scheduled restart supervisor handoff cần audit

Phải xác nhận đầy đủ:

```text
ClientRestartRequested
→ parent Multi nhận signal
→ đóng đúng ClientJS/profile
→ mở lại đúng profile
→ bind PID mới
→ Bridge generation mới
→ worker mới
→ startup 60s
→ resume đúng scheduler contract
```

Không được gọi scheduled restart 3h runtime PASS trước khi chuỗi này được chứng minh.

### 9.3 Static/CI

CI gần nhất từng trả failure ở cấp job nhưng không có step chạy/runner thực thi, nên chưa phải bằng chứng source compile fail hay PASS. Cần static verification thực sự chạy sau khi worker/supervisor được chuẩn hóa.

## 10. Checkpoint commit quan trọng

- `82bc3da80d62e2d56691761dc28583aa9c9f690c` — share one RecoveryManager across Function recipes.
- `e26bbfbc26776a242bf806f9d3e5a23ccb49ddf2` — khóa thuật ngữ/source comment: Hồng/Tuyết là cây nguyên liệu, TDHH là VP thành phẩm.

Tiếp tục chuẩn hóa từ **worker/supervisor lifecycle**, sau đó cập nhật verifier + handoff và mới chuyển sang live test.
