# ClientJS AUTO component

Đây là lớp tích hợp giữa KVTM Multi và runtime AUTO PRO đã phục hồi.

## Nguyên tắc

- Không sao chép hoặc viết lại logic sản xuất của AUTO PRO.
- Multi định danh tài khoản bằng profile ID; PID chỉ là giá trị tạm.
- Mỗi chức năng được khai báo trong `catalog/functions.json`.
- Worker chỉ được gọi entry point đã được cho phép trong catalog.
- AUTO LD nằm ngoài component này và không bị sửa đổi.

## Chức năng thử nghiệm hiện tại

- `6 Tinh Dầu Hoa Hồng + 6 Vải Vàng + 8 Táo Sấy`
  - Function ID: `98`
  - Entry point: `FarmAutomation.produceItems_98`
  - Được xác nhận READ-ONLY từ bytecode AUTO PRO: `tao_say=8`,
    `vai_vang=6`, `tinh_dau_hh=6`.
- `9 Vải Vàng + 9 Táo Sấy`
  - Function ID: `136`
  - Entry point: `FarmAutomation.produceItems_136`

Runtime AUTO PRO tiếp tục cung cấp các hàm trồng cây, sản xuất, thu hoạch,
bán hàng, phục hồi lỗi, reset game và qua nhà bạn bè.
