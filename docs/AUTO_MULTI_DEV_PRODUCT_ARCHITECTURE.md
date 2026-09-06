# AUTO MULTI DEV — Kiến trúc sản phẩm và bàn giao AI

## Quyết định sản phẩm

AUTO MULTI DEV là sản phẩm thay thế. AUTO PRO chỉ là nguồn bằng chứng tham chiếu tạm thời và sẽ bị loại bỏ sau khi Multi Dev ổn định qua kiểm thử live.

## Quy tắc bắt buộc

1. Logic nghiệp vụ mới nằm trong `components/clientjs-auto/kvtm_automation`.
2. Không import hoặc chạy `.pyc`, `automation`, `adb_controller` hay workflow nghiệp vụ của AUTO PRO.
3. Mọi ảnh Multi Dev sử dụng phải nằm trong `components/clientjs-auto/assets`. AssetLibrary không được fallback sang `source-archive/auto-pro-reference/assets`.
4. Ảnh Auto Pro đã được chứng minh đúng phải sao chép nguyên binary sang Multi Dev, đặt tên snake_case theo ngữ nghĩa và khai báo trong `tools/verify_multi_dev_asset_contract.py`.
5. Ảnh chụp người dùng gửi chỉ là bằng chứng bố cục/log. Không cắt thành template sản phẩm nếu người dùng không yêu cầu rõ.
6. Trong giai đoạn migration, OpenCV/NumPy/Pillow và Bridge được phép resident một lần trong process. Trước khi xóa AUTO PRO, file runtime kỹ thuật phải được chuyển sang vùng sở hữu Multi Dev. Logic nghiệp vụ tuyệt đối không phụ thuộc AUTO PRO.
7. Người dùng Pull/Build duy nhất qua BAT Control Center. Full Build phải chạy mọi static contract và đóng gói đệ quy `components/clientjs-auto`.
8. Giữ fail-closed, cooperative stop, identity profile/PID, tối đa 2 tài khoản và tối đa 10 hàm mỗi file Python.

## Chức năng chính 1: 9 Táo sấy → 9 Vải vàng

Thứ tự hiện tại:
- bán VP ổn định;
- thu/trồng 27 Táo;
- mở máy sấy tầng 1, thu VP hoàn thành;
- xác minh đúng ảnh sản xuất `tao_say`;
- xác minh đủ 9 ô trống bằng `o_trong`;
- xếp đúng 9 Táo sấy;
- bước kế tiếp sau LIVE PASS: xây lớp 9 Vải vàng.

Không bắt đầu lớp Vải vàng trước khi lớp Táo sấy PASS live cả tiền điều kiện, 9 swipe, thiếu nguyên liệu và hậu kiểm. Gửi đủ 9 gesture không đồng nghĩa PASS.

## Bộ kiểm tra bắt buộc

- `tools/verify_multi_dev_asset_contract.py`
- `tools/verify_auto_main_production_contract.py`
- Full Build trong BAT Control Center
- Live log phải thấy ô trên từ `o_trong.png` của Multi Dev, tổng 9/9 trước sản xuất và thay đổi đủ 9/9 sau sản xuất.
