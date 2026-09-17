# Dọn quầy standalone — checkpoint 2026-09-16

Branch: `feature/clear-stall-standalone-ui`  
Base ban đầu: `develop/multi-auto-dev` @ `41144da50d5bb5ccd9f064bcfd599cbc0a403316`

## Operator decisions

- Mẫu 8 là design contract.
- Dọn quầy chạy thành tool riêng nhưng kế thừa business/runtime AUTO MULTI DEV.
- Tool có `profiles.json` và `settings.json` riêng, profile đồng bộ từ AUTO MULTI DEV.
- `Thêm tài khoản` chỉ chọn account/profile đã có trong profile nguồn.
- Mỗi lần mở tool, toàn bộ account ở trạng thái **Đã dừng**; không tự resume lịch.

## Source

- `components/clear_stall_tool/app.py`: GUI Mẫu 8.
- `branding.py`: PNG logo operator đã duyệt.
- `profile_store.py`: snapshot profile + settings riêng.
- `runtime_controller.py`: scheduler, ownership và ClientJS lifecycle.
- `runtime_integration.py`: nối GUI với runtime.
- `standalone_clear_stall_worker.py`: adapter mỏng sang runtime Multi DEV.
- `main.py`: production entrypoint; `--demo` chỉ review UI.

## Runtime contract

Standalone không copy/fork thuật toán Dọn quầy. Worker chỉ dựng `ProbeConfig` rồi gọi `clear_stall_probe_runtime.run_probe()` từ package Multi DEV đã build.

Full-resale hiện hành:

```text
purchase_limit = buy_quantity / 10
resale_batch_limit = purchase_limit
```

Lifecycle:

```text
Play
→ ownership preflight
→ mở đúng ClientJS từ profile
→ claim ownership cho KVTM Dọn Quầy
→ chuẩn hóa 1000x1000
→ chạy full-resale worker
→ chỉ ghi Last Clean khi có probe_ok
→ đóng ClientJS do standalone mở
→ chờ interval
→ chạy lượt kế tiếp
```

Tối đa 2 account thực thi đồng thời.

## Profile/settings

```text
%APPDATA%\KVTM Dọn Quầy\profiles.json
%APPDATA%\KVTM Dọn Quầy\settings.json
%APPDATA%\KVTM Dọn Quầy\runs\
```

- Snapshot lấy từ `%APPDATA%\KVTM Multi\profiles.json`.
- First-run tự import nếu nguồn tồn tại; nút `Đồng bộ profile` refresh thủ công.
- Không ghi ngược về Multi.
- Settings riêng giữ selected accounts, clear-stall job config và Last Clean.
- Settings đã tồn tại không bị sync profile ghi đè.
- RUNNING/STOPPED không persist; startup luôn STOPPED.

## Ownership / fail-close

- Không attach/giành account đã được Multi/Cry/instance khác sở hữu.
- Ownership conflict tạo lỗi và lịch có thể thử lại chu kỳ sau.
- Stop dùng command channel hiện hành.
- Đóng GUI sẽ stop toàn bộ schedule.
- Không commit profile/settings/secret/token/cookie/password.

## Verification

```text
python -m py_compile components/clear_stall_tool/*.py
python tools/verify_clear_stall_standalone_ui.py
python tools/verify_clear_stall_standalone_runtime.py
```

Static/source PASS không thay cho live evidence. Windows LIVE full-resale: **PENDING**.

## Cập nhật 2026-09-17 — lịch Add, chống nhấp nháy và 7 view

- Giữ nút `＋` ngay cạnh Play của từng tài khoản.
- Popup Add có hai lựa chọn: chờ riêng cho phiên đầu, hoặc tính hạn từ lần dọn
  thành công cuối. Chỉ phiên đầu dùng lựa chọn này; các phiên sau dùng chu kỳ.
- Lưu `last_success_at` riêng trong settings Dọn quầy, không ghi sang Multi.
- Bảng account giữ nguyên widget theo `account_id` và chỉ cập nhật text/màu;
  progress tần suất cao chỉ vào Log, không phá/tạo lại toàn bộ hàng.
- Standalone chạy đúng 7 view: scan/mua tại tâm ảnh PASS, một swipe, rồi scan
  view kế tiếp.
- Mỗi frame trước scan/mua phải đúng `1000x1000`; sai kích thước thì fail-close
  trước input để tránh mở nhầm tab và log chạy loạn.
