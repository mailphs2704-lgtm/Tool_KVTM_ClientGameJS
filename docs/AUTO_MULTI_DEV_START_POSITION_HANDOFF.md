# AUTO MULTI DEV — Chuẩn hóa vị trí khởi điểm

Tài liệu này là handoff bắt buộc cho chuỗi sửa startup camera. Mỗi yêu cầu của người dùng được làm thành một bước nhỏ; xong bước nào thì cập nhật trạng thái tại đây để cửa sổ làm việc tiếp theo không làm lệch luồng.

## Mục tiêu gốc

Mỗi lần bấm chạy AUTO MULTI DEV, camera phải được đưa về **màn hình chính của chính clone** trước khi bắt đầu chuỗi nghiệp vụ. Không được giả định camera đang ở tầng 1, tầng 2 hay màn hình chính.

Sau khi đã xác nhận đúng màn hình chính, chuỗi nghiệp vụ mới được phép tiếp tục. Transition từ màn hình chính lên mốc gieo là đúng **một** `goUp(1)` do action gieo hiện có sở hữu; không phát thêm một `goUp(1)` ở lớp session để tránh kéo hai lần.

## Trạng thái từng dòng yêu cầu

### STEP 1 — Đã xong

**Trường hợp bắt đầu ngay tại màn hình chính.**

Quy tắc đã khóa:

- Probe `is_own_main_screen()` ngay khi `GameSessionWorkflow` bắt đầu.
- Nếu đúng màn hình chính: ghi stage `clean-session-start-main-detected`.
- Không phát `goDown` nào.
- Vẫn chạy `ensure_main_screen()` để giữ cơ chế đóng popup / xác minh home hiện tại.
- Khi main đã được xác nhận, bàn giao cho pipeline hiện có.
- Không đưa `goUp(1)` vào `GameSessionWorkflow`; `PlantingActions._open_seed_picker()` vẫn là chủ sở hữu duy nhất của nhịp `goUp(1)` trước gieo.

Commit runtime của STEP 1:

`f33406931990ea50144a871c2a1878fcc67bc110` — `fix(auto-multi): lock main-screen startup anchor`

### STEP 2 — Chưa làm

**Trường hợp bắt đầu ở tầng 1 hoặc tầng 2.**

Yêu cầu chính xác:

1. Thực hiện một `goDown(1)`.
2. Quan sát cửa sổ ngắn của nút xuống tầng.
3. Nếu **không xuất hiện nút xuống tầng**, coi đây là nhánh tầng thấp.
4. Thực hiện tiếp **3 lần `goDown(1)`** để chắc chắn camera đã kéo hết về màn hình chính, kể cả trường hợp camera bị lệch/kẹt.
5. Sau các gesture phải xác nhận lại `is_own_main_screen()` trên fresh frame.
6. Không xác nhận main thì fail-close; không tiếp tục production.

Không được suy ra rằng một `goDown(1)` từ tầng 1 là đã về main.

### STEP 3 — Chưa làm

**Trường hợp bắt đầu từ tầng 3 đến tầng 10.**

Yêu cầu chính xác:

1. Thực hiện một `goDown(1)`.
2. Sau gesture này nút xuống tầng sẽ xuất hiện trong thời gian ngắn.
3. Chỉ click khi template nút xuống tầng thực sự được nhận diện trên fresh frame.
4. Chờ camera/game hoàn tất animation chuyển xuống.
5. Sau đó thực hiện tiếp **3 lần `goDown(1)`** để ép camera rời vùng mây / vị trí treo trung gian.
6. Xác nhận `is_own_main_screen()`.
7. Không xác nhận main thì fail-close.

### STEP 4 — Chưa làm

**Timing và nhận diện nút xuống tầng.**

Đặc tính game đã được người dùng xác nhận:

- Nút xuống tầng **chỉ xuất hiện sau thao tác kéo tầng**.
- Nút chỉ tồn tại vài giây rồi biến mất.
- Detection phải bắt đầu ngay sau fresh frame hậu kiểm của `goDown(1)`.
- Cần giới hạn cửa sổ tìm kiếm; không loop vô hạn.
- Chỉ click template đã xác minh; không click tọa độ mù khi không có detection.
- Sau click phải chờ animation settle rồi mới phát ba `goDown(1)` tiếp theo.

Timing cụ thể sẽ được chốt bằng log/live evidence ở STEP 4, không đoán trước trong STEP 1-3.

## Invariant an toàn

- Không nới CAPTURE3.
- Không chấp nhận stale frame.
- Mỗi gesture phải có hậu kiểm fresh frame.
- Không gắn nhãn `main` chỉ dựa vào số lần kéo.
- Chỉ `is_own_main_screen()` xác nhận được điểm khởi đầu cuối cùng.
- Không đụng ổn định của sale / clear-stall khi đang sửa startup normalization.
- AUTO PRO tiếp tục chỉ là reference, không gọi runtime sang AUTO PRO.

## Vấn đề riêng đang chờ sau startup normalization

PASS 3 Cây bông đang có hợp đồng hậu kiểm cũ đòi đủ `27/27` vùng chậu thay đổi. Người dùng đã xác nhận hàng cây thứ 5 có thể bị khuất camera, vì vậy **27/27 visible regions không thể là gate PASS bắt buộc**. Việc này phải sửa riêng sau khi hoàn tất STEP 1-4; không trộn vào startup recovery để tránh khó truy nguyên regression.

## Điểm tiếp tục cho cửa sổ kế tiếp

Nếu STEP 1 đã có commit ở trên, **không làm lại STEP 1**.

Bắt đầu từ **STEP 2: tầng 1/2 → một `goDown(1)` → nếu không thấy nút xuống tầng thì thêm 3 `goDown(1)` → fresh-frame xác nhận màn hình chính**.

Chỉ khi STEP 2 hoàn tất mới cập nhật tài liệu này thành `STEP 2 — Đã xong`, ghi commit và chuyển sang STEP 3.
