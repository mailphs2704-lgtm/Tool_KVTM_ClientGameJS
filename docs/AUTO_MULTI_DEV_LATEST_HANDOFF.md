# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-15
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái: **SECOND-PASS OPERATOR UI REFINEMENT SOURCE COMPLETE — STABLE CRY VERSION 0.1.5 BUMPED — BUILD/LIVE PENDING**

> Build/static PASS không thay cho live/runtime evidence. Không gọi runtime PASS khi chưa có operator evidence.

## 1. Read-first bắt buộc

1. `AGENTS.md`
2. `AI_COORDINATION.md`
3. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`
4. `docs/AUTO_FUNCTION_3_STEP_4_CHECKPOINT_20260915.md`
5. `docs/AUTO_OPERATIONS_LOG_RECOVERY_CHECKPOINT_20260915.md`
6. `docs/AUTO_MULTI_DEV_UI_LOG_CHECKPOINT_20260915.md`
7. `docs/AUTO_MULTI_DEV_UI_REFINEMENT_CHECKPOINT_20260915.md`

Tài liệu cũ mâu thuẫn với source/checkpoint mới nhất chỉ là lịch sử.

## 2. Luồng build chính thức

Operator dùng:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Không thay bằng manual pull/build trừ recovery chẩn đoán được operator yêu cầu. `dist/KVTM-ClientJS-Suite-Multi-DEV` là output generated, không phải source.

Build gần nhất tại HEAD `a52a415...` đã chạy tới clear-stall verifier rồi dừng vì verifier cũ còn khóa `main_log_viewer.py` phải có nền console `#202020`. Source Log mới là light 3-tab nên assertion đó đã được migrate sang contract mới tại `tools/verify_clear_stall_contract_build.py`; chưa có build evidence sau fix/refinement mới.

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

## 10. Compact AUTO MULTI DEV UI

Base compact UI vẫn giữ logic:

```text
CHỨC NĂNG
Mở rương / Thăm bạn
Bắt đầu / Dừng / Cấu hình / Log
```

- nút test Function 3 đã bị ẩn khỏi UI;
- `Mở rương` giữ optional feature per-profile;
- `Thăm bạn` giữ friend-refresh per-profile;
- `Cấu hình` chứa tốc độ + Vòng lặp + Thời gian chờ bằng Entry;
- scheduler widget cũ bị ẩn chứ không hủy để giữ persistence.

## 11. Second-pass UI refinement

Checkpoint: `docs/AUTO_MULTI_DEV_UI_REFINEMENT_CHECKPOINT_20260915.md`.

Operator live review yêu cầu:

```text
CHỨC NĂNG (rộng hơn) | TRẠNG THÁI
```

Thay đổi source:

- bỏ cột `TÀI KHOẢN ÁP DỤNG` khỏi mặt AUTO MULTI DEV;
- nới rộng Menubutton Function để tên dài như `9 Nước hoa hồng - 9 Trà đá - 9 Vải vàng` không bị che bất hợp lý;
- tạo status operator riêng chỉ có `Đang chạy` / `Đã dừng`;
- diagnostics dài của `auto_multi_dev_status` vẫn tồn tại nội bộ nhưng không còn là text hiển thị ở ô trạng thái operator;
- lifecycle start/stop/finish sync status từ worker/thread thực tế;
- giữ nguyên hidden scheduler parents để không phá profile persistence.

Source mới:

```text
source-archive/multi-current/kvtm_multi_tool/auto_multi_dev_ui_refinement.py
```

Install order:

```text
optional features
→ compact UI
→ UI refinement
```

## 12. Log window hiện hành

Một nút `Log` mở đúng ba tab:

```text
Log hành động | Log chi tiết | Log lỗi
```

- Log hành động = bảng `THỜI GIAN / TÀI KHOẢN / HÀNH ĐỘNG`;
- Log chi tiết = live text;
- Log lỗi = live text persistent;
- `Xuất lỗi TXT` nằm trong tab Log lỗi;
- refresh mỗi 1 giây;
- initial geometry được center/clamp bên trong cửa sổ Multi;
- sau khi mở operator vẫn kéo cửa sổ ra ngoài được;
- Treeview tăng rowheight và text viewer có vertical spacing để từng dòng dễ phân biệt.

Cửa sổ `Cấu hình` cũng initial-place bên trong Multi và vẫn kéo tự do sau đó.

## 13. Stable Kvtm_tool_Cry publish gate

Operator build/publish Stable báo:

```text
Stable version 0.1.4 already points to another source HEAD.
Bump packaging/kvtm-tool-cry/VERSION before publishing.
```

Đây là guard đúng của Stable channel: cùng một version không được trỏ sang source HEAD khác. Fallback Setup cũng từ chối package cũ vì manifest source HEAD không trùng HEAD hiện tại.

Đã bump:

```text
packaging/kvtm-tool-cry/VERSION
0.1.4 → 0.1.5
```

Không hạ guard và không cho phép publish đè version cũ. Lần publish kế tiếp phải tạo Stable 0.1.5 từ HEAD mới; Stable đang chạy vẫn độc lập và chỉ nhận version mới ở lần mở tiếp theo theo contract của packager.

## 14. Source milestones gần nhất

```text
295e0961  test(auto): migrate clear-stall log viewer contract
cf59b128  refactor(ui): refine multi dev operator layout
6632157f  refactor(ui): install final multi dev refinement
2002b0dc  refactor(ui): fit log windows and improve row spacing
cf8ffada  fix(ui): preserve hidden scheduler widgets
b44efd23  docs(auto): checkpoint second-pass UI refinement
e45a91ed  build(stable): bump Kvtm_tool_Cry to 0.1.5
```

## 15. NEXT GATE

1. Pull/build lại source bằng Control Center phù hợp với Stable/local publish flow đang dùng.
2. Stable publish phải đọc version `0.1.5`, không còn lỗi reuse `0.1.4`.
3. Sau build sạch, live-check UI refinement:
   - Function 3 tên dài hiển thị đủ/không còn bị che bất hợp lý;
   - không còn cột Tài khoản áp dụng;
   - status chỉ `Đang chạy` / `Đã dừng`;
   - Mở rương + Thăm bạn vẫn đúng per-profile;
   - Cấu hình lưu đúng tốc độ/Vòng lặp/Thời gian chờ;
   - Log/Cấu hình mở lần đầu nằm gọn trong Multi và vẫn kéo ra ngoài được;
   - khoảng cách dòng Log rõ ràng hơn.
4. Function 3 completion exact MAIN, daily counter và recovery không regression.

**Chưa gọi Stable BUILD/PUBLISH PASS hoặc RUNTIME PASS trước evidence tương ứng.**

## 16. Trà đá sale-dialog false-negative fix

Operator evidence:

```text
kho_tra_da=0.9937 PASS
click Trà đá
sale dialog dat_ban=1.000 PASS
tra_da=0.7514 < 0.78 FAIL
CANCEL recovery
```

The storage selection was correct; the one-frame dialog proof was a false negative. The supplied 1000x1000 screenshot matches the existing storage presentation, so no asset was overwritten.

Source now preserves the primary `tra_da.png` proof and adds existing `kho_tra_da.png` as a dialog fallback. Safety remains fail-close:

- threshold remains `0.78`;
- scan is bounded to 3 fresh frames;
- 2 stable PASS frames are required;
- x10 proof and post-sale own-stall proof remain unchanged;
- only after all dialog proof attempts fail is the item marked unsafe and cancelled.

Commits: `978d103e`, `e7b6133d`. Build/live pending.

NEXT: Control Center `[1]`, then retest Function 3 sale and require `selected-item STABLE READY` → x10 PASS → POST_SALE OWN_STALL READY.

## 17. Stable parity, automatic versioning and DWM/GPU recovery

Operator confirmed the Trà đá sale fix LIVE PASS, then reported:

- Stable publish remained pinned to `0.1.5` and rejected a new source HEAD;
- installed Cry lacked current DEV fixed ClientJS position and speed/profile UI;
- Cry showed heavy DWM/GPU use.

Diagnosis:

- the old Stable manifest still pointed to source `4e4a9f2...`, while current source was newer;
- release code only rejected version reuse and had no automatic version selection;
- therefore Cry could not receive the current DEV host where DWM Live View is removed and Bridge V3 OpenGL-present FPS hard-cap is installed;
- setup copied DEV profiles/settings only on first install, so later DEV configuration did not refresh Stable.

Source changes:

- release version is now idempotent for the same source HEAD and automatically increments the published patch version for a new HEAD (the reported `0.1.5` channel will publish the next new HEAD as `0.1.6`);
- no tracked VERSION edit is required, avoiding a dirty worktree and future pull conflict;
- Stable release fails closed unless it contains current DEV host, DWM-off policy, FPS hard-cap, fixed-position integration, speed/profile/UI integrations, and Bridge V3 loader/DLL;
- every successful Stable version switch snapshots current DEV `profiles.json`, `settings.json`, and `clear-stall-history.jsonl`;
- setup refreshes the same safe allowlist;
- `running_clients.json`, PID/runtime state and logs remain isolated and are never copied;
- Builder functions/image library already use the persistent `%APPDATA%\KVTM Multi DEV\auto-builder` location, so Stable continues to see the same Builder data.

Commits: `0b5af84c`, `9f590505`, `7c9f8c89`, `3953e185`.

Build/live pending. NEXT: Control Center publish Stable, require automatic `0.1.5 -> 0.1.6`, packaging verifier PASS, then close/reopen Cry and verify DWM Live View OFF, FPS hard-cap APPLIED, fixed top-right ClientJS position, complete speed configuration and current DEV profiles/settings.

## 18. 2026-09-15 — Cry khôi phục đủ trường “Tốc độ kéo quầy”

- Bằng chứng ảnh operator: hộp Cấu hình DEV có đủ 6 tốc độ, còn Cry chỉ có 5 và thiếu riêng `Tốc độ kéo quầy`.
- Nguyên nhân: `kvtm_multi_owned_host.py` chỉ cài `stall_speed_integration` ở hook recorder cuối quá trình khởi tạo; lúc đó wrapper UI/profile của DEV đã được dựng nên schema `shop_drag_speed` không đi vào hộp cấu hình Cry.
- Stable nay hook `auto_builder_integration` và cài ownership + vị trí ClientJS + `stall_speed_integration` trước builder/UI. FPS hard-cap, thống kê, error log, optional features và recorder vẫn giữ ở pha sau.
- Packaging verifier khóa hai điều kiện: stall-speed phải đứng trước original builder và hook phải được gắn trước khi import `kvtm_multi_dev_host`.
- AST source/verifier: PASS. Windows build và LIVE Cry: PENDING.
- Retest: chạy `KVTM_DEV_CONTROL.bat -> [1]`, sau đó `Kvtm_tool_Cry_RELEASE.bat`; đóng/mở lại Cry và xác nhận hộp Cấu hình có đủ 6 trường, gồm `Tốc độ kéo quầy`.

## 19. 2026-09-15 — Sửa tài khoản ONL giả sau khi Dừng ClientJS

- Live report: bấm Dừng tài khoản ONL nhưng tài khoản không trở về OFF và không thể mở lại ClientJS đó.
- Root cause: ownership registry xác minh PID bằng `OpenProcess + GetProcessTimes`; Windows vẫn có thể trả creation time của process đã exit khi còn handle mở, nên stale entry tiếp tục kéo hàng OFF trở lại ONL và chặn launch mới.
- `_creation_token()` nay yêu cầu `WaitForSingleObject(handle, 0) == WAIT_TIMEOUT` trước khi chấp nhận creation token. PID đã signalled/exited được prune khỏi registry trong lần refresh kế tiếp.
- Không nới ownership: ClientJS đang sống của DEV/Cry khác vẫn read-only và không bị dừng/claim.
- Ownership verifier khóa live-state check phải chạy trước `GetProcessTimes`.
- AST/static order: PASS. Windows build/LIVE: PENDING.

