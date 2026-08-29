# Demo 97

Demo này mô tả phần sản xuất trong `produceItems_97` của AUTO PRO cũ:

- 8 Táo sấy (`makeItems("1", "1", "tao_say", ..., 8)`)
- 6 Vải vàng
- 6 Tinh dầu hoa hồng
- kiểm tra màn hình game và đóng popup
- swipe giỏ hàng bằng một chuỗi `DOWN -> MOVE... -> UP`
- thử lại tối đa 5 lần khi thiếu nguyên liệu
- rẽ nhánh theo ảnh và ghi log khi thất bại

Các tọa độ click nút sản xuất trong demo là điểm mẫu logic 1000x1000. Hãy mở JSON trong Function Builder, chụp màn hình tài khoản test rồi kéo điểm cho khớp trước khi chạy.

Để nhập ảnh từ AUTO PRO cũ, kéo thư mục `AUTO_KVTM_PRO_recovered_local` thả lên `IMPORT_AUTO_PRO_DEMO_ASSETS.bat`.
