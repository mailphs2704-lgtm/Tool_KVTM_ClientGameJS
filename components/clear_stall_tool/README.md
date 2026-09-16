# KVTM Dọn Quầy — standalone UI scaffold

Mốc này chỉ dựng **GUI độc lập** theo mẫu 8 đã được operator chọn. Chưa nối business runtime Dọn quầy, profile persistence hay settings persistence.

## Design contract

- giao diện sáng, gọn, dùng font Segoe UI và chỉ phụ thuộc Python standard library (`tkinter`);
- header `KVTM - Dọn Quầy` + trạng thái tổng;
- toolbar: `Bắt đầu tất cả`, `Dừng tất cả`, `Thêm tài khoản`, `Đồng bộ profile`, `Cấu hình nhanh`;
- 5 card: tổng tài khoản, đang chạy, sẵn sàng, đã dừng, chu kỳ mặc định;
- bảng account có checkbox, tên tài khoản, profile, trạng thái, lần dọn cuối, chu kỳ, ghi chú và thao tác;
- hỗ trợ chọn nhiều account, phân trang, nút start/stop từng account;
- popup Thêm tài khoản / Đồng bộ profile / Cấu hình nhanh đã có shell UI để nối runtime sau;
- dữ liệu demo chỉ dùng tên giả, không chứa profile/account thật.

## Chạy preview

```bat
python components\clear_stall_tool\main.py
```

Mặc định hiển thị dữ liệu demo để review layout. Muốn xem trạng thái rỗng:

```bat
python components\clear_stall_tool\main.py --empty
```

## Boundary

- Không sửa AUTO MULTI DEV production UI.
- Không sửa `clear_stall_probe_runtime.py` hoặc nghiệp vụ Dọn quầy.
- Không tạo `profiles.json`/`settings.json` thật ở mốc GUI này.
- Giai đoạn sau sẽ nối profile riêng của tool với thao tác `Đồng bộ profile` từ AUTO MULTI DEV và giữ runtime/shared files dùng chung theo contract đã chốt với operator.
