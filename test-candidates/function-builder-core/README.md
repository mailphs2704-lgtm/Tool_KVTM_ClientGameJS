# KVTM Function Builder - test candidate

Đây là bản thử nghiệm, chưa được promote vào mã nguồn chính.

## Có thể làm

- Kết nối GameClientJS theo PID và kiểm tra Engine Bridge.
- Chụp ảnh client mà không đổi kích thước cửa sổ.
- Ghi click hoặc đường swipe trực tiếp trên Live View.
- Gửi thao tác vừa ghi vào game và lưu tọa độ logic 1000 x 1000.
- Kéo-thả hoặc chọn PNG/JPG/BMP vào thư viện ảnh.
- Thêm bước chờ ảnh, click ảnh và chờ thời gian.
- Sắp xếp, xóa, lưu/mở chức năng JSON.
- Chạy thử toàn bộ danh sách bước.

## Chạy

Client phải được mở bằng Multi và Bridge phải báo sẵn sàng.

```powershell
Get-Process GameClientJS | Select-Object Id
RUN_FUNCTION_BUILDER.bat PID
```

## Phím/nút kiểm thử

- `Chụp lại`: cập nhật Live View.
- Click trên Live View: gửi click và thêm một step.
- Giữ chuột rồi kéo: gửi swipe và thêm một step.
- Kéo ảnh từ Explorer vào cửa sổ hoặc dùng `Thêm ảnh`.
- `Chạy thử`: phát lại tất cả step qua Engine Bridge.
- `Lưu JSON`: lưu trong thư mục `workspace/functions` theo mặc định.

## Điều kiện PASS

- Tool mở được và không làm cửa sổ game thay đổi kích thước/vị trí.
- Click và swipe đúng khi client 1000x1000 và khi client đã co nhỏ.
- Chuột thật không bị chiếm trong lúc phát lại.
- Ảnh kéo-thả xuất hiện trong thư viện.
- JSON đóng/mở lại giữ nguyên thứ tự và dữ liệu step.
- Chức năng chạy thử không được chứa hay thực thi mã Python tùy ý.

