# Dọn quầy standalone — GUI checkpoint 2026-09-16

Branch: `feature/clear-stall-standalone-ui`  
Base: `develop/multi-auto-dev` @ `41144da50d5bb5ccd9f064bcfd599cbc0a403316`

## Operator decision

Operator chọn **Mẫu 8 — Compact quản lý account** làm design contract cho tool Dọn quầy tách riêng.

## Scope mốc này

Chỉ dựng GUI standalone; chưa tách/wire nghiệp vụ Dọn quầy.

Source mới:

- `components/clear_stall_tool/app.py`
- `components/clear_stall_tool/main.py`
- `components/clear_stall_tool/__init__.py`
- `components/clear_stall_tool/README.md`
- `tools/verify_clear_stall_standalone_ui.py`

## UI contract

- Header `KVTM - Dọn Quầy`, trạng thái tổng góc phải.
- Toolbar: Bắt đầu tất cả / Dừng tất cả / Thêm tài khoản / Đồng bộ profile / Cấu hình nhanh.
- 5 stat cards: Tổng tài khoản / Đang chạy / Sẵn sàng / Đã dừng / Chu kỳ mặc định.
- Bảng account 8 dòng/trang: checkbox, STT, account, profile, trạng thái, lần dọn cuối, chu kỳ, ghi chú, thao tác.
- Có chọn nhiều account, start/stop từng account, phân trang, popup add/sync/config.
- Windows DPI-awareness hook để hạn chế sai bố cục ở 125%/150% scaling.
- Chỉ dùng Python standard library (`tkinter`), không thêm dependency GUI ngoài.

## Boundary

- Không sửa AUTO MULTI DEV production UI.
- Không sửa business/runtime Dọn quầy.
- Không tạo profile/settings thật.
- Dữ liệu preview là dữ liệu giả; không commit account/profile thật.
- `Đồng bộ profile` mới chỉ là UI shell. Thiết kế persistence/profile riêng sẽ thực hiện sau khi operator mô tả/chốt.

## Verification

Local source check:

```text
python -m py_compile components/clear_stall_tool/*.py
python tools/verify_clear_stall_standalone_ui.py
```

Static/source PASS. Windows operator visual review: PENDING. Runtime Dọn quầy: NOT IN SCOPE/PENDING.
