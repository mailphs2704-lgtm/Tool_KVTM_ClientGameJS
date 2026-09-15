# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-15
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **COMPACT OPERATOR UI + 3-TAB LOG SOURCE COMPLETE — BUILD/LIVE PENDING**

> Build/static PASS không thay cho live/runtime evidence. Không gọi runtime PASS khi chưa có operator evidence.

## 1. Read-first bắt buộc

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_FUNCTION_3_STEP_4_CHECKPOINT_20260915.md`
5. `docs/AUTO_OPERATIONS_LOG_RECOVERY_CHECKPOINT_20260915.md`
6. `docs/AUTO_MULTI_DEV_UI_LOG_CHECKPOINT_20260915.md`

Tài liệu cũ mâu thuẫn với source/checkpoint mới nhất chỉ là lịch sử.

## 2. Luồng build chính thức

Operator dùng:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Không thay bằng manual pull/build trừ recovery chẩn đoán được operator yêu cầu. `dist/KVTM-ClientJS-Suite-Multi-DEV` là output generated, không phải source.

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

- Function = complete business cycle có thể chọn/lặp độc lập.
- Step = chặng lớn bên trong Function.
- Recipe = ghép Action theo nghiệp vụ.
- Action = primitive/reusable operation + proof.
- Recovery = xử lý typed error hoặc global unhandled recovery; không phải Function completion.

## 4. Function catalog

```text
Function 1 = 9 Táo sấy - 9 Vải vàng
Function 2 = 9 Táo sấy - 9 Vải vàng - 7 Tinh dầu hoa hồng
Function 3 = 9 Nước hoa hồng - 9 Trà đá - 9 Vải vàng
```

`FunctionModule` dispatch `function_3` tới `FunctionThreeWorkflow.run()`. Function 3 hiện có 6 Step và completion gate exact MAIN đã sửa lỗi falsy `end_floor=0`.

## 5. Function 3 hiện tại

Step 4 correction hiện hành:

```text
Hồng 30 tầng1
→ Hồng 15 tầng6
→ tổng 45 Hồng
→ MAIN → tầng1
→ Tuyết 30 tầng1
→ Tuyết 6 tầng6
→ tổng 36 Tuyết
→ goDown(1) tầng6→tầng5
→ SX 9 TDHH
→ sửa máy
→ MAIN → tầng1
```

Step 5:

```text
Tuyết 30 tầng1
→ Tuyết 6 tầng6
→ SX 9 Trà đá tầng6
→ sửa máy
→ goDown(1) + wait 1s + XUỐNG
→ MAIN → tầng1
```

Step 6:

```text
Hồng 30 tầng1
→ Hồng 6 tầng6
→ goUp(2) tầng8
→ SX 9 Nước hoa hồng
→ sửa máy
→ goDown(1) + wait 1s + XUỐNG
→ exact MAIN
→ Function 3 DONE
```

Step 5 từng được operator xác nhận LIVE PASS trước correction TDHH upstream; cumulative Function 3 sau correction vẫn cần live-test lại.

## 6. Shared route / planting / production

Upper-floor→MAIN canonical:

```text
goDown(1)
→ wait 1.0s
→ detect/click XUỐNG
→ fallback (497,978) nếu template MISS/no-response
→ bắt buộc frame response
→ mark exact MAIN
```

Planting dùng seed template động; không dùng tọa độ seed tuyệt đối. Verified path: `3,5,6,15,24,27,28,30`.

Production dùng shared `ProductionPanelActions`; thu VP tối thiểu 4 burst × 5 click. Product Action hiện có Táo sấy, Nước táo, Vải vàng, TDHH, Trà sấy, Trà đá, Nước hoa hồng.

## 7. Log hành động / chi tiết / lỗi

Operator contract:

```text
[time] . Cry . Đã bán ...
[time] . Cry . Mở rương thành công N lần hôm nay
[time] . Cry . Gieo thành công 36 táo
[time] . Cry . Sản xuất 9 trà sấy
[time] . Cry . Lỗi đầy kho, chuyển trạng thái xử lí
```

`AutomationContext.action()` → Log hành động. `log()`/`detail()` + worker/bootstrap chatter → Log chi tiết.

Error journal persistent per-profile gồm timestamp, account, error class, giải thích tiếng Việt, message, phase, recovery state và traceback. Secret-looking values được redact.

## 8. Daily counters

Per-profile, sống qua restart tool/ClientJS và reset local midnight:

- `LƯỢT BÁN AUTO`: một listing x10 thành công = một lượt.
- `RƯƠNG HẢI TẶC`: chỉ `OPENED` mới +1.

## 9. Error recovery policy

Known typed recovery xử lý gần module nhất.

Unhandled AUTO Main error:

```text
ghi error journal
→ action báo lỗi
→ exact MAIN
→ nhà bạn #1
→ nhà mình
→ exact MAIN
→ restart AUTO Function đã chọn
```

Global recovery tự retry nếu chính recovery gặp lỗi. `AutomationStopped` và `ClientRestartRequested` là control/lifecycle signal, không phải lỗi.

## 10. NEW — compact AUTO MULTI DEV UI

Source checkpoint: `docs/AUTO_MULTI_DEV_UI_LOG_CHECKPOINT_20260915.md`.

UI mới giữ logic cũ nhưng đổi mặt vận hành:

```text
CHỨC NĂNG | TÀI KHOẢN ÁP DỤNG | TRẠNG THÁI

+ Mở rương   + Thăm bạn

▶ Bắt đầu   ■ Dừng   Cấu hình   ≡ Log
```

- bỏ nút `Test Function 3 - Step 1` khỏi UI;
- `Mở rương hải tặc` đổi nhãn operator thành `Mở rương`;
- friend refresh đổi nhãn operator thành `Thăm bạn`;
- `Cấu hình tốc độ` đổi thành `Cấu hình`;
- `Vòng lặp` + `Thời gian chờ` chuyển vào dialog Cấu hình;
- dialog dùng Entry nhập trực tiếp, không dùng spinner arrows;
- scheduler widget cũ chỉ ẩn, không hủy, để giữ profile persistence contract;
- optional feature Mở rương được install thật và snapshot per-profile vào worker config.

## 11. NEW — một cửa sổ Log, ba tab

Một nút `≡ Log` mở cửa sổ theo phong cách Log Dọn quầy:

```text
Log hành động | Log chi tiết | Log lỗi
```

- Log hành động = bảng `THỜI GIAN / TÀI KHOẢN / HÀNH ĐỘNG`;
- Log chi tiết = live text;
- Log lỗi = live text persistent;
- `⇩ Xuất lỗi TXT` nằm trong tab Log lỗi;
- refresh mỗi 1 giây.

Source:

```text
source-archive/multi-current/kvtm_multi_tool/main_log_viewer.py
source-archive/multi-current/kvtm_multi_tool/auto_multi_dev_ui_integration.py
source-archive/multi-current/kvtm_multi_tool/auto_error_log_integration.py
```

## 12. Source milestone gần nhất

```text
3a4b623d  feat(ui): add combined three-tab auto log viewer
cc5479c2  feat(ui): compact auto multi dev controls and logs
16646674  refactor(ui): fold error export into combined auto log
18949a4c  docs(auto): checkpoint compact multi dev UI and log tabs
```

## 13. NEXT GATE

Chạy `[1]` bằng `KVTM_DEV_CONTROL.bat`.

Sau build sạch, live-check:

1. Không còn nút test Function 3.
2. Header Chức năng/Tài khoản áp dụng/Trạng thái hiển thị đúng.
3. Mở rương + Thăm bạn nằm cạnh nhau và toggle đúng per-profile.
4. Cấu hình có tốc độ + Vòng lặp + Thời gian chờ; nhập trực tiếp không spinner.
5. Một nút Log mở đúng ba tab; export TXT nằm trong Log lỗi.
6. Function 3 completion exact MAIN và scheduler tiếp tục vòng mới.
7. Log hành động chỉ còn milestone ngắn; Log chi tiết đầy đủ.
8. Daily counters/error recovery vẫn hoạt động.

**Chưa gọi BUILD/STATIC PASS hoặc RUNTIME PASS trước evidence tương ứng.**
