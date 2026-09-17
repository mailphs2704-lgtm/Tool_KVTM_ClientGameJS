# KVTM Dọn Quầy — standalone

Tool Dọn quầy độc lập dùng giao diện Mẫu 8, nhưng **kế thừa nghiệp vụ Dọn quầy đã được kiểm chứng của AUTO MULTI DEV** thay vì sao chép thuật toán.

## Runtime contract

- business runtime dùng lại `components/clientjs-auto/worker/clear_stall_probe_runtime.py` từ package Multi DEV đã build;
- một lượt thật chạy full-resale: mua đúng target rồi thu vàng/treo lại đúng các lô x10 đã xác minh;
- ClientJS do tool Dọn quầy tự mở sẽ được đóng sau mỗi lượt;
- registry ownership được kiểm tra trước khi mở: nếu cùng tài khoản đang thuộc Multi/Cry hoặc instance khác, tool không giành quyền điều khiển;
- Stop gửi qua command channel của worker hiện hành.

## Profile và settings riêng

Dữ liệu runtime của tool nằm ngoài Git tại:

```text
%APPDATA%\KVTM Dọn Quầy\profiles.json
%APPDATA%\KVTM Dọn Quầy\settings.json
%APPDATA%\KVTM Dọn Quầy\runs\
```

`profiles.json` của tool là snapshot riêng lấy từ profile **AUTO MULTI DEV authoritative**:

```text
%APPDATA%\KVTM Multi DEV\profiles.json
```

Đây là cùng thư mục mà `START_MULTI_DEV_SILENT.ps1` gán vào `KVTM_MULTI_APP_DIR`. Tool Dọn Quầy chạy ở process riêng nên tự bind về đúng thư mục này; nó **không được tự động lấy `%APPDATA%\KVTM Multi\profiles.json`** của bản Multi khác/legacy.

- Mỗi lần mở tool, snapshot profile được refresh từ AUTO MULTI DEV hiện tại nếu file nguồn tồn tại.
- `Đồng bộ profile` cho phép refresh lại ngay khi Multi DEV vừa có tài khoản mới/thay đổi trong lúc tool đang mở.
- Popup `Thêm tài khoản` và thông báo đồng bộ hiển thị đường dẫn nguồn profile để operator kiểm tra trực tiếp.
- Không ghi ngược vào profile/settings của AUTO MULTI DEV.
- Settings Dọn quầy riêng được giữ khi đồng bộ profile.
- `Thêm tài khoản` chỉ cho chọn profile đã đồng bộ; **không có ô nhập account/profile tự do**.

Nếu `%APPDATA%\KVTM Multi DEV\profiles.json` chưa tồn tại, tool chỉ cho phép fallback migration tới `data-dev` của package Multi DEV cũ; tuyệt đối không chọn profile production/legacy theo thời gian sửa file.

## Startup / trạng thái

Mỗi lần mở tool, **mọi tài khoản đều bắt đầu ở trạng thái `Đã dừng`**. Trạng thái chạy không persist qua restart.

- `▶` một tài khoản: bật lịch và chạy lượt Dọn quầy đầu tiên ngay.
- `＋` một tài khoản: chọn chờ riêng cho đúng phiên đầu hoặc tính thời gian còn
  lại từ lần thành công cuối; các phiên sau trở về `interval_minutes` đã cài.
- `■`: dừng lịch và gửi stop cho worker nếu đang thao tác.
- `Bắt đầu tất cả` / `Dừng tất cả`: áp dụng cho toàn bộ tài khoản đã thêm.
- Sau lượt thành công, lịch chờ theo `interval_minutes` rồi chạy lượt kế tiếp.

## Nhịp quét/mua standalone

Mỗi nhà chạy đúng 7 view theo thứ tự cố định:

```text
scan frame 1000x1000 → nhận diện VP → mua tại tâm ảnh PASS
→ 1 swipe 0.20 giây → scan view kế tiếp
```

Không quét trước toàn bộ quầy rồi mới quay lại mua. Mỗi view chỉ có một swipe
chuyển tiếp. Nếu bất kỳ frame nào khác `1000x1000`, lượt dừng trước click để
không mở nhầm tab hoặc ghi log dây chuyền trên bố cục sai.

## Chạy

Tool cần runtime Multi DEV đã build. Nếu package chưa có, chạy `KVTM_DEV_CONTROL.bat -> [1]` trong repo Multi DEV trước.

```bat
py -3.11 components\clear_stall_tool\main.py
```

Chế độ chỉ xem demo:

```bat
py -3.11 components\clear_stall_tool\main.py --demo
```

## Boundary

- Không sửa AUTO MULTI DEV production UI.
- Không fork/chép `ClearStallWorkflow`.
- Không commit `profiles.json`, `settings.json`, token, cookie, password hay launch secret.
- Static/build PASS không phải runtime PASS; lượt thật chỉ chốt khi có operator evidence.
