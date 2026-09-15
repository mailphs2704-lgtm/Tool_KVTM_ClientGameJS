# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-15
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **FUNCTION 3 SIX-STEP SOURCE WIRED + OPERATIONS LOG/RECOVERY SOURCE COMPLETE — BUILD/LIVE PENDING**

> Build/static PASS không thay cho live/runtime evidence. Không gọi runtime PASS khi chưa có operator evidence.

## 1. Read-first bắt buộc

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_FUNCTION_3_STEP_4_CHECKPOINT_20260915.md`
5. `docs/AUTO_OPERATIONS_LOG_RECOVERY_CHECKPOINT_20260915.md`
6. Các checkpoint feature gần nhất nếu sửa đúng feature đó.

Tài liệu cũ mâu thuẫn với source/checkpoint mới nhất chỉ là lịch sử.

## 2. Luồng build chính thức

Operator dùng:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Không thay bằng manual pull/build trừ recovery chẩn đoán được operator yêu cầu.
`dist/KVTM-ClientJS-Suite-Multi-DEV` là output generated, không phải source.

Lỗi build gần nhất từng gặp là package output bị process khác giữ handle; Bridge V3 đã build PASS nhưng toàn bộ `[1]` chưa được gọi PASS nếu cleanup/package chưa hoàn tất.

## 3. Kiến trúc chuẩn

```text
AUTO MAIN / SCHEDULER
        ↓
FUNCTION
        ↓
STEP / RECIPE
        ↓
ACTION

        ↕
RECOVERY MANAGER / CHECKPOINT
```

- Function = một complete business cycle có thể chọn/lặp độc lập.
- Step = chặng lớn bên trong Function.
- Recipe = ghép các Action theo nghiệp vụ.
- Action = primitive/reusable operation + proof.
- Recovery = xử lý typed error hoặc global unhandled recovery; không phải Function completion.

## 4. Function catalog hiện tại

```text
Function 1 = 9 Táo sấy - 9 Vải vàng
Function 2 = 9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng
Function 3 = 9 Nước hoa hồng - 9 Trà đá - 9 Vải vàng
```

`FunctionModule` đã dispatch `function_3` tới `FunctionThreeWorkflow.run()`.
AUTO Main đã có completion gate riêng cho Function 3.

## 5. Function 3 hiện tại

`FunctionThreeWorkflow.TOTAL_DEFINED_STEPS = 6`.
`run()` chạy Step 1→2→3→4→5→6 và kết thúc exact MAIN.

Các live gate đã được operator xác nhận trước đây:

- Step 1: LIVE PASS.
- Step 2: LIVE PASS.
- Step 4: từng LIVE PASS trước correction TDHH.
- Step 5: LIVE PASS trước correction TDHH upstream.

Sau correction Step 4 TDHH, cumulative Function 3 phải live-test lại; không tự kế thừa runtime PASS cho chuỗi mới.

### Step 4 TDHH correction hiện hành

```text
Hồng 30 tầng1
→ Hồng 15 tầng6
→ tổng 45 Hồng
→ về MAIN → tầng1
→ Tuyết 30 tầng1
→ Tuyết 6 tầng6
→ tổng 36 Tuyết
→ goDown(1) trực tiếp tầng6→tầng5
→ thu VP / SX 9 TDHH
→ sửa máy
→ MAIN → tầng1
```

Không quay MAIN rồi leo lại tầng5 trước TDHH.

### Step 5

```text
Tuyết 30 tầng1
→ Tuyết 6 tầng6
→ SX 9 Trà đá tầng6
→ sửa máy
→ goDown(1) + wait 1s + XUỐNG
→ MAIN → tầng1
```

### Step 6

```text
Hồng 30 tầng1
→ Hồng 6 tầng6
→ goUp(2) lên tầng8
→ SX 9 Nước hoa hồng
→ sửa máy
→ goDown(1) + wait 1s + XUỐNG
→ exact MAIN
→ Function 3 DONE
```

## 6. Shared upper-floor → MAIN route

`FarmBoundaryRouteActions.known_upper_floor_to_main_via_down_floor(...)` là canonical route.

Contract:

```text
goDown(1)
→ wait 1.0s ổn định animation
→ detect/click nút XUỐNG
→ nếu template MISS/no-response: fallback operator point (497,978)
→ bắt buộc có frame response
→ mới mark exact MAIN
```

Dùng chung cho floor3/floor5/floor6 và generic known upper floor như floor8.

## 7. Planting

Seed identity luôn dynamic bằng template. Không dùng tọa độ tuyệt đối seed.

Verified path hiện có:

```text
3, 5, 6, 15, 24, 27, 28, 30
```

Picker page chỉ được chuyển khi chứng minh bảng gieo đang mở bằng `next_gieo_trai`; điểm kéo bắt đầu tại `match.center`.

## 8. Production / VP

Shared `ProductionPanelActions` sở hữu panel proof, collect VP, empty-slot count, wrong-machine/full-kho signals và page safety.

Shared VP collection minimum:

```text
4 burst × 5 click = 20 click
```

Các product Action đang dùng shared engine gồm Táo sấy, Nước táo, Vải vàng, TDHH, Trà sấy, Trà đá, Nước hoa hồng.

## 9. Log hành động vs Log chi tiết

Operator contract mới:

### Log hành động
Chỉ milestone/error ngắn theo account, ví dụ:

```text
[time] . Cry . Đã bán 10 trà đá, 20 vải vàng, 10 nước hoa hồng, tổng số VP bán trong ngày ...
[time] . Cry . Mở rương thành công N lần hôm nay
[time] . Cry . Gieo thành công 36 táo
[time] . Cry . Sản xuất 9 trà sấy
[time] . Cry . Lỗi đầy kho, chuyển trạng thái xử lí
```

`AutomationContext.action()` đi action stream.
`AutomationContext.log()`/`detail()` đi Log chi tiết khi detail logger có mặt.
Worker/bootstrap chatter cũng đã chuyển sang detail; context logger chỉ dành cho action milestone.

### Log chi tiết
Giữ toàn bộ runtime diagnostics: stage, template match, navigation proof, timing, recovery internals, production checks, stack/error diagnostics.

## 10. Daily counters trên account info

Persistent per-profile:

- `LƯỢT BÁN AUTO`: một listing x10 thành công = một lượt; local-midnight reset.
- `RƯƠNG HẢI TẶC`: chỉ `OPENED` mới +1; local-midnight reset.

Hai counter sống qua restart tool/ClientJS.
Daily-counter UI integration đã được nối vào resident DEV host và refresh selected-account details mỗi 1 giây.

## 11. Error journal

Persistent per-profile error journal:

```text
%APPDATA%/KVTM Multi DEV/.../auto-error-log/<profile>.txt
```

Record gồm timestamp, account, error type, giải thích tiếng Việt, raw message, phase, recovery state và traceback nếu có. Secret-looking values được redact.

UI đã nối:

```text
⚠ Log lỗi
⇩ Xuất lỗi TXT
```

Typed production errors (đầy kho/sai máy), material shortage, pirate SAFE_ABORT và global unhandled runtime errors đều được journaled.

## 12. Error recovery policy

Known typed recovery vẫn xử lý gần module nhất.

Unhandled error thoát khỏi typed policy trong AUTO Main:

```text
ghi error journal
→ action log báo lỗi/chuyển xử lí
→ recover unknown camera về exact MAIN
→ sang nhà bạn #1
→ quay nhà mình
→ chứng minh exact MAIN
→ bắt đầu lại AUTO Function đã chọn
```

Global recovery tự retry nếu chính recovery gặp lỗi.

`AutomationStopped` và `ClientRestartRequested` là control/lifecycle signal, không phải lỗi và không được biến thành auto-retry.
Bootstrap/Bridge failure xảy ra trước khi business recovery graph tồn tại vẫn là lifecycle fatal; không được giả lập in-game recovery khi chưa có runtime hợp lệ.

## 13. Scheduled restart

ClientJS restart mặc định 3 giờ và chỉ tại safe Function boundary.
Không cắt ngang Function đang chạy.

## 14. Source milestone gần nhất

Các commit feature mới nhất gồm:

```text
5d12757d  feat(auto): add concise function2 TDHH milestones
94ddba17  feat(auto): wire daily counters and error journal UI
fc4dacba  refactor(auto): keep worker chatter in detail log
1fa37995  feat(auto): journal material shortage recovery
67b17a2f  feat(auto): journal pirate chest aborts
```

Checkpoint:

`docs/AUTO_OPERATIONS_LOG_RECOVERY_CHECKPOINT_20260915.md`

## 15. NEXT GATE

Chạy `[1]` bằng `KVTM_DEV_CONTROL.bat`.

Chỉ khi build sạch mới test live. Live test cần xác minh:

1. Log hành động chỉ còn milestone/error ngắn và có tên acc.
2. Log chi tiết vẫn đầy đủ.
3. Rương hải tặc hiển thị daily count đúng account và reset local midnight.
4. Log lỗi mở/xuất TXT được.
5. Typed error ghi journal nhưng resume đúng checkpoint.
6. Unhandled AUTO Main error không dừng AUTO: exact MAIN → bạn #1 → nhà mình → restart AUTO.
7. Function 3 cumulative sau TDHH correction chạy 6/6 và kết thúc exact MAIN.

**Chưa gọi BUILD/STATIC PASS hoặc RUNTIME PASS trước evidence tương ứng.**
