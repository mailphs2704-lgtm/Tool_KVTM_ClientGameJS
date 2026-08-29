# Engine Core Candidate

Ứng viên thử nghiệm độc lập cho GameClientJS. File này chưa thuộc mã nguồn chính.

## Phạm vi kiểm thử

1. Tìm đúng HWND theo PID.
2. Đọc kích thước client hiện tại.
3. Quy đổi tọa độ logic 1000 x 1000.
4. PING Engine Bridge.
5. Chụp vùng client thành BMP.
6. Chỉ swipe khi truyền rõ `--swipe`.

## Chạy trong thư mục Multi cũ

Sau khi copy `game_client_engine.py` vào thư mục test, mở client bằng Multi và lấy PID.

Kiểm tra an toàn, không thao tác game:

```powershell
python game_client_engine.py <PID>
```

Nếu ảnh BMP đúng và Bridge báo OK, kiểm tra swipe:

```powershell
python game_client_engine.py <PID> --swipe --duration 2.5
```

PASS khi:

- Không chiếm chuột thật.
- Không làm cửa sổ đổi kích thước hay nhảy về màn hình chính.
- BMP đúng nội dung hiện tại.
- Swipe liên tục và đúng hướng.
- Thu nhỏ/phóng cửa sổ rồi chạy lại vẫn cho tọa độ tâm hợp lệ.
