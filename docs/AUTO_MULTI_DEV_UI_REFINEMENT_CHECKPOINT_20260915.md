# AUTO MULTI DEV — UI REFINEMENT CHECKPOINT

Date: 2026-09-15
Branch: `develop/multi-auto-dev`
Status: **SOURCE COMPLETE — BUILD/LIVE PENDING**

## Operator request

Tinh gọn lần hai mặt AUTO MULTI DEV sau live UI review:

- tên Function dài phải có đủ không gian hiển thị;
- bỏ cột `TÀI KHOẢN ÁP DỤNG` khỏi hàng đầu;
- `TRẠNG THÁI` chỉ hiển thị đúng hai giá trị operator: `Đang chạy` / `Đã dừng`;
- không hiển thị câu kỹ thuật `Khung AUTO sạch đã sẵn sàng...` trong status operator;
- cửa sổ `Log` và `Cấu hình` khi mở lần đầu phải nằm gọn bên trong cửa sổ Multi, sau đó vẫn kéo tự do được;
- tăng khoảng cách giữa các dòng log để dễ đọc và không bị dính dòng.

## Source implementation

### `auto_multi_dev_ui_refinement.py`

Lớp refinement mới chạy sau compact UI hiện hành:

- nới cột `CHỨC NĂNG`, Menubutton rộng hơn;
- bỏ box Tài khoản khỏi mặt operator;
- tạo status riêng `auto_multi_dev_operator_status`, không dùng chuỗi diagnostics dài của `auto_multi_dev_status`;
- status mới được sync từ worker/thread thực tế và chỉ normalize thành `Đang chạy` hoặc `Đã dừng`;
- wrap start/stop/finish để status cập nhật theo lifecycle;
- giữ nguyên các widget scheduler ẩn (`Vòng lặp`, `Thời gian chờ`, `Thăm bạn`, `Mở rương`) để profile persistence không bị phá;
- dialog Cấu hình giữ nguyên logic/tuning hiện hành nhưng initial geometry được center/clamp vào vùng Multi.

### `main_log_viewer.py`

- Log AUTO và compatibility log đều initial-place trong vùng cửa sổ Multi;
- dùng `transient(parent)` nhưng không khóa vị trí, operator vẫn kéo ra ngoài được;
- Log hành động tăng `Treeview rowheight`;
- Log chi tiết / Log lỗi thêm vertical text spacing;
- giữ ba tab và export TXT trong Log lỗi.

### `auto_error_log_integration.py`

Install order hiện tại:

```text
optional features
→ compact AUTO MULTI DEV UI
→ second-pass UI refinement
```

Không thay đổi Function, Bridge V3, capture/input, scheduler semantics, Dọn quầy, daily counters hay recovery.

## Verification gate

Chưa gọi BUILD/STATIC PASS từ source inspection.

Operator chạy:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Live-check sau build:

1. Function 3 tên dài không còn bị che bất hợp lý.
2. Không còn cột Tài khoản áp dụng.
3. Trạng thái ban đầu/đã dừng = `Đã dừng`.
4. Khi AUTO chạy = `Đang chạy`.
5. Dừng worker xong = `Đã dừng`.
6. Log và Cấu hình xuất hiện gọn bên trong Multi ở lần mở đầu.
7. Vẫn kéo hai cửa sổ ra ngoài Multi được.
8. Các dòng Log hành động/chi tiết/lỗi có khoảng cách rõ hơn.
9. Profile persistence cho Vòng lặp/Thời gian chờ/Mở rương/Thăm bạn vẫn hoạt động.
