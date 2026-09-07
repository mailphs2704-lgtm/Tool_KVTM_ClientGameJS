# AUTO MULTI DEV — Chức năng 1

Chức năng 1 chỉ hoàn thành khi cùng một vòng đã sản xuất đủ **9 Táo sấy và 9 Vải vàng**. Nước táo là thành phẩm trung gian bắt buộc để sản xuất Vải vàng, không phải kết thúc chức năng.

## Chuỗi hiện tại

1. Vào game, đóng popup và xác minh farm.
2. Bán đúng VP của chức năng hiện tại: Táo sấy, Vải vàng.
3. Chạy điểm mở rộng “check tùy chọn”; hiện chưa cấu hình nên chỉ ghi stage.
4. Từ màn hình chính lên tầng 1; trồng 27 Táo.
5. Đứng tầng 1, sản xuất và hậu kiểm 9 Táo sấy. Mốc 1/3.
6. Đóng máy; tại tầng 1 chờ template thu_hoach. Chỉ khi chín mới thu hoạch 5 tầng và gieo lại 30 Táo.
7. Vì camera đang ở tầng 1, lên tầng 6 bằng goUp(4) rồi goUp(1). Không chạy nhịp khởi tạo goUp(1) của demo màn hình chính.
8. Ở tầng 6, kiểm tra hàng dưới cùng của sơ đồ bốn tầng; thu hoạch và gieo 6 Táo.
9. Đưa camera từ tầng 6 về màn hình chính, rồi lên tầng 2.
10. Xác minh máy bằng asset Multi Dev nuoc_tao.png; kéo xuống ô top động và hậu kiểm đủ 9 Nước táo.
11. Báo TẠM PASS 2/3. Không phát stage hoàn thành chức năng 1.
12. Bước sau: dùng 9 Nước táo sản xuất 9 Vải vàng; hậu kiểm đủ mới PASS 3/3 và hoàn thành.

## Hợp đồng an toàn

- Asset nghiệp vụ nằm trong components/clientjs-auto; không gọi runtime đến AUTO_PRO.
- Ảnh sản xuất dùng template sản xuất, không dùng ảnh kho và không dùng ảnh chụp người dùng.
- Mỗi gesture sản xuất phải làm giảm bộ đếm ô trống; không thay đổi thì dừng.
- Route màn hình chính → tầng 6 (demo) là 1,4,1. Route tầng 1 → tầng 6 của chức năng là 4,1.
- Chờ cây chín có timeout 120 giây, mặc định kiểm tra mỗi 0.3 giây theo cấu hình Multi Dev và luôn tôn trọng stop event.
- Tầng 6: nếu hàng dưới cùng là chậu trống thì gieo ngay; nếu có cây chưa chín mới tiếp tục kiểm tra.

- Khi máy còn VP hoàn thành che phía trước, auto click liên tục tại máy; không giới hạn ba nhịp. Chỉ dừng click khi panel máy được xác minh đã mở. Lệnh Dừng AUTO và chặn kho đầy vẫn có hiệu lực.
