# AUTO MULTI DEV — UI / LOG CHECKPOINT

Date: 2026-09-15
Branch: `develop/multi-auto-dev`
Status: **SOURCE COMPLETE — BUILD/LIVE PENDING**

## Operator request

Chuẩn hóa tab AUTO MULTI DEV theo phong cách Chức năng chính và Log Dọn quầy:

- bỏ nút `Test Function 3 - Step 1` khỏi UI vận hành;
- hàng đầu hiển thị `CHỨC NĂNG / TÀI KHOẢN ÁP DỤNG / TRẠNG THÁI`;
- toggle nhanh `Mở rương` và `Thăm bạn` nằm cạnh nhau;
- `Số vòng giữa 2 lần bán` đổi tên ngắn thành `Vòng lặp`;
- `Thời gian chờ` và `Vòng lặp` chuyển vào cửa sổ `Cấu hình`;
- hai trường dùng Entry nhập trực tiếp, không dùng nút tăng/giảm;
- `Cấu hình tốc độ` đổi tên thành `Cấu hình` và vẫn chứa các tốc độ AUTO MULTI DEV;
- một nút `Log` mở một cửa sổ có ba tab `Log hành động / Log chi tiết / Log lỗi`;
- `Xuất lỗi TXT` nằm trong tab `Log lỗi`, không chiếm hàng nút chính.

## Source implementation

### `main_log_viewer.py`

Bổ sung `open_auto_log_window(...)`:

- giao diện sáng, header/notebook theo ngôn ngữ Log Dọn quầy;
- Log hành động dùng bảng `THỜI GIAN / TÀI KHOẢN / HÀNH ĐỘNG`;
- Log chi tiết và Log lỗi dùng live text viewer;
- refresh mỗi 1 giây;
- nút `Xuất lỗi TXT` nằm trong tab Log lỗi.

### `auto_multi_dev_ui_integration.py`

Integration mới, cài sau các wrapper Builder/Profile/Counter/Optional:

- giữ nguyên widget/variable cũ để không phá scheduler persistence;
- chỉ ẩn các Spinbox scheduler cũ khỏi mặt UI;
- tạo dialog `Cấu hình AUTO MULTI DEV` dùng Entry;
- lưu `Vòng lặp` + `Thời gian chờ` qua profile setting hiện hành;
- lưu speed tuning và broadcast `update_tuning` tới worker đang chạy;
- ẩn/destroy nút test DEV và các nút log rời;
- tạo một nút `≡ Log`;
- giữ chức năng `Mở rương` per-profile thông qua optional feature snapshot hiện hành;
- `Thăm bạn` tiếp tục dùng friend-refresh policy hiện hành.

### `auto_error_log_integration.py`

- không tạo `Log lỗi`/`Xuất lỗi TXT` thành hai nút riêng nữa;
- giữ helper xem/xuất lỗi để tương thích;
- cài `optional_features_integration` rồi cài final compact UI integration;
- export TXT được gọi từ tab Log lỗi.

## Safety / behavior preserved

Không thay đổi Function choreography, Bridge V3, capture/input ownership, sale cadence semantics, daily counters, error recovery, Dọn quầy hay Workspace.

Các widget scheduler cũ chỉ bị ẩn, không bị hủy, vì `auto_main_profile_settings.py` vẫn dùng chúng để refresh/state/persistence. Dialog mới cập nhật đúng các StringVar/IntVar hiện hữu trước khi gọi save policy cũ.

## Verification gate

Chưa gọi BUILD/STATIC PASS từ source inspection.

Operator chạy:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Sau build, live-check:

1. Không còn nút Test Function 3 trên tab AUTO MULTI DEV.
2. Header giống Chức năng chính: Chức năng / Tài khoản áp dụng / Trạng thái.
3. Có hai toggle nhanh `Mở rương` và `Thăm bạn` cạnh nhau.
4. Hàng action gọn: Bắt đầu / Dừng / Cấu hình / Log.
5. Cấu hình có tốc độ + Vòng lặp + Thời gian chờ, toàn bộ nhập trực tiếp không có spinner arrow.
6. Một cửa sổ Log có đúng ba tab.
7. Tab Log lỗi có nút Xuất lỗi TXT.
8. Function, optional features và profile settings vẫn chạy đúng như trước.
