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


## Contract kéo sản xuất Táo sấy

- Nguồn kéo phải là tâm match của `components/clientjs-auto/assets/items/tao_say.png`; không dùng `kho_tao_say.png`, tọa độ cứng hoặc ảnh debug.
- Đích kéo phải là tâm match ô trên của `components/clientjs-auto/assets/items/o_trong.png`; không dùng điểm thả cố định.
- Match `tao_say` dưới `0.70` bị từ chối. Mức `0.301` đã được xác định là khớp giả trên ô trống.
- Sau mỗi gesture, tổng ô trống phải giảm đúng theo tiến độ; nếu không giảm thì đóng panel và dừng ngay.
- Chỉ PASS khi đủ chín lần thay đổi trạng thái được xác minh; số gesture đã gửi không phải số sản phẩm đã xếp.


## Giai đoạn Nước táo → Vải vàng

- `9 Vải vàng` cần `9 Nước táo` được sản xuất tại máy tầng 2.
- Nguyên liệu cho 9 Nước táo là `36 cây Táo`: sáu hàng, mỗi hàng sáu cây.
- Lượt gieo đầu trồng năm tầng × sáu cây = 30 cây; sau đó chuyển từ tầng 1 lên tầng 6 và trồng thêm một hàng × sáu cây.
- Trước khi ghép vào pipeline, nút độc lập `Demo chính → tầng 6` chạy `floors.glide_up(6)`: một gesture liên tục từ `(514,214)` đến `(514,814)`, tương ứng sáu đơn vị tầng. Người vận hành đặt clone tại màn hình chính trước khi bấm. Hậu kiểm ảnh được thực hiện sau toàn cú lướt; không quay lại cách gửi từng tầng rồi chờ `0.65s`.

## Module sửa quầy dùng chung

Sau khi sản xuất ở bất kỳ máy nào, hệ thống về sau phải chạy thao tác sửa quầy dùng chung. Triển khai thành module độc lập để tái sử dụng cho mọi máy, không nhúng riêng vào Táo sấy hoặc Nước táo. Chưa ghép module này vào pipeline trong mốc demo tầng 1 → 6.


### Hiệu chỉnh demo tầng 6 từ LIVE

LIVE đầu tiên chứng minh năm gesture rời chỉ tới tầng 5. Mốc này bị đánh dấu NOT PASS. Contract đúng là sáu đơn vị tầng trong một gesture liên tục, mô phỏng nhịp lướt nhanh của Auto Pro; chỉ kết quả retest mới được phép nâng thành LIVE PASS.


## Tạm dừng 2026-09-07 — Demo điều hướng tầng 6 NOT PASS

- Retest `floors.glide_up(6)` với một gesture `(514,214)→(514,814)`, thời lượng `0.060s`, chỉ đưa màn hình từ màn hình chính lên tầng 1.
- Log bridge xác nhận gesture thật đã gửi: `DOWN`, bốn `MOVE` tại y=`364/514/664/814`, rồi `UP`; `frame_change=75.49` chỉ chứng minh màn hình có đổi, không chứng minh đúng tầng.
- Nguyên nhân đã biết: gesture quá nhanh; game gộp toàn đường kéo thành một lần chuyển tầng. Giả định “100 px = một tầng trong cùng gesture” bị bác bỏ.
- Trạng thái nút `Demo chính → tầng 6`: tồn tại để thử nghiệm nhưng **NOT PASS / KHÔNG DÙNG trong pipeline**.
- Không thay đổi kết quả đã xác nhận: lớp Táo sấy vẫn LIVE PASS `9/9`.
- Lớp `36 Táo → 9 Nước táo → 9 Vải vàng` chưa triển khai.

### Điểm tiếp tục ngày mai

1. Đối chiếu lại chính xác bytecode/log của `goUp(n)` trong Auto Pro, gồm số touch, khoảng nghỉ giữa touch và cách giữ/ngắt gesture.
2. Không suy diễn số tầng từ độ dài pixel hoặc chỉ từ `frame_change`.
3. Xây tiêu chí nhận dạng tầng 6 hoặc một bằng chứng live riêng; thay đổi hình ảnh chung không đủ để PASS.
4. Thử trong nút demo độc lập trước; chỉ sau khi tầng 6 LIVE PASS mới ghép thao tác trồng hàng thứ sáu.
5. Giữ backlog module sửa quầy dùng chung, chưa ghép vào workflow.


### Bằng chứng hình ảnh tầng 6 và giới hạn nhận dạng

Ảnh người dùng cung cấp ngày 2026-09-07 xác nhận bố cục trực quan khi đứng tại tầng 6, nhưng chỉ là bằng chứng tham khảo và không được đưa vào thư viện template. Những thành phần sau không ổn định: VP/cây trên chậu, giao diện máy, số sao/cấp máy và hình mây. Không được dùng riêng bất kỳ thành phần này để kết luận tầng 6.

Quyết định kỹ thuật: chưa xây detector tầng 6 từ screenshot. Phải nghiên cứu Auto Pro để xác định nó dựa vào bộ đếm nội bộ, trạng thái camera, số nhịp gesture, tọa độ máy hay một dấu hiệu ổn định khác. Chỉ sao chép asset nghiệp vụ từ Auto Pro nếu chứng minh đó là asset mà logic gốc thật sự sử dụng; không cắt ảnh debug của người dùng.


## Forensic Auto Pro `goUp` — kết quả bytecode gốc

Nguồn: `source-archive/auto-pro-reference/recovery_notes/raw_marshal/adb_controller.marshal`, code object `goUp`, dòng gốc 614.

`num_up` không phải số tầng để lặp. Auto Pro dùng nó như mã chọn bốn thao tác:

- `goUp(1)`: swipe `(514,214)→(514,314)`, duration=`harvest_speed`.
- `goUp(2)`: click `(257,416)`.
- `goUp(3)`: click `(257,191)`.
- `goUp(4)`: swipe `(387,69)→(387,918)`, duration=`harvest_speed`.
- Mỗi nhánh chờ `go_up_wait`; cuối hàm còn chờ `0.15s`.
- Trước khi chọn nhánh, hàm click đóng panel cạnh `(975,316)`.

Bản thân `goUp` không nhận dạng và không xác nhận tầng tuyệt đối. Auto Pro giữ mốc bằng thứ tự workflow; `goDownLast` mới tìm `quay_hang/check_xuong` để xác nhận đã về màn hình chính. Vì vậy `frame_change` không được chuyển thành kết luận tầng.

Nút demo mới chỉ phát lại đúng `goUp(4)` từ màn hình chính và báo `ĐÃ GỬI`, không báo tầng 6 PASS. Hai thuật toán tự suy diễn cũ — năm swipe nhỏ và gesture 600 px/0.06s — đều bị loại khỏi demo.


## LIVE mốc `goUp(4)` và chuỗi mục tiêu 6

Người vận hành xác nhận rõ: xuất phát từ màn hình chính, `goUp(4)` nguyên bản dừng tại tầng 3. Đây là mốc live, không phải suy luận từ `frame_change`.

Bytecode vòng điều hướng Auto Pro chia `target=6`: khi còn ít nhất 4 đơn vị gọi mode 4, sau đó còn 2 đơn vị gọi mode 3. Vì vậy demo kế tiếp phát đúng thứ tự `goUp(4) → goUp(3)`; mode 3 là click `(257,191)`. Demo kiểm tra mỗi lệnh có phản hồi ảnh nhưng chỉ ghi `ĐÃ GỬI`; người vận hành vẫn là nguồn xác nhận tầng 6 trong lượt live này.


## LIVE `goUp(4) → goUp(3)` chỉ tới tầng 5 — sửa state machine target 6

Live xác nhận từ màn hình chính, chuỗi mode 4 rồi mode 3 dừng ở tầng 5. Chuỗi này bị đánh dấu NOT PASS.

Đọc lại phần khởi tạo vòng target của Auto Pro cho thấy bước bắt buộc đã bị bỏ sót: `cur=0`; nếu `target>0`, gọi `goUp(1)` và đặt `cur=1`. Với `target=6`, vòng còn 5 nên gọi `goUp(4)` để thành `cur=5`; còn 1 nên gọi `goUp(1)` lần cuối. Chuỗi đúng theo state machine là `goUp(1) → goUp(4) → goUp(1)`.

Demo được thay bằng chuỗi 1-4-1, hậu kiểm từng lệnh có phản hồi nhưng vẫn chỉ báo ĐÃ GỬI. Chỉ xác nhận trực tiếp của người vận hành mới nâng tầng 6 thành LIVE PASS.
