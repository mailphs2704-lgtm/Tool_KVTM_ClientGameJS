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

Commit runtime STEP 1:

`f33406931990ea50144a871c2a1878fcc67bc110` — `fix(auto-multi): lock main-screen startup anchor`

### STEP 2 — Đã xong phần nhánh tầng thấp

**Trường hợp bắt đầu ở tầng 1 hoặc tầng 2.**

Runtime hiện đã khóa đúng chuỗi tầng thấp:

1. Nếu startup chưa xác nhận main, trước tiên cho luồng portal/popup hiện có một cửa sổ ngắn để vào game hoặc đóng blocker; không kéo tầng trên màn hình portal/loading.
2. Khi vẫn là trạng thái game non-main, phát một `goDown(1)` bằng đúng geometry `(514,314) -> (514,214)`.
3. Sau gesture lấy fresh CAPTURE3; `frame_change` chỉ ghi diagnostic, tuyệt đối không dùng để suy luận tầng/main.
4. Phát tiếp **đúng 3 lần `goDown(1)`** để ép camera tầng 1/2 về đáy, kể cả khi đã chạm biên camera và hình gần như không đổi.
5. Sau chuỗi `1 + 3`, bắt buộc gọi `is_own_main_screen()` trên fresh frame.
6. Chỉ khi exact main classifier PASS mới bàn giao cho AUTO.
7. Nếu chưa xác nhận main thì `ScreenTimeout` fail-close; không production tiếp.

Commit runtime STEP 2:

`e97d409f175426dceeedb8ae0a51628b9481a0af` — `fix(auto-multi): normalize floor1-floor2 startup`

Commit static contract STEP 2:

`8074f815a8d5a4055ddcd6204c9f6c84cd6db565` — `test(auto-multi): lock step2 startup route`

**Giới hạn cố ý ở bản này:** nhánh nhận diện nút xuống tầng chưa được thêm. Vì vậy startup từ tầng 3-10 không được đoán là tầng thấp; nếu `1 + 3 goDown(1)` vẫn không về exact main thì worker dừng fail-close. Tách như vậy để STEP 3/4 có thể bổ sung detector/timing của nút xuống tầng dựa trên bằng chứng thật, không click mù.

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

Không được dùng `quay_hang` hay `cua_hang` thay cho nút xuống tầng: hai asset đó là icon/quầy cửa hàng, không phải nút chuyển tầng. Nếu clean asset chưa có template nút xuống tầng thì phải thu hồi đúng reference hoặc lấy live evidence rồi tạo asset canonical; không đoán tên, tọa độ hoặc threshold.

### STEP 4 — Chưa làm

**Timing và nhận diện nút xuống tầng.**

Đặc tính game đã được người dùng xác nhận:

- Nút xuống tầng **chỉ xuất hiện sau thao tác kéo tầng**.
- Nút chỉ tồn tại vài giây rồi biến mất.
- Detection phải bắt đầu ngay sau fresh frame hậu kiểm của `goDown(1)`.
- Cần giới hạn cửa sổ tìm kiếm; không loop vô hạn.
- Chỉ click template đã xác minh; không click tọa độ mù khi không có detection.
- Sau click phải chờ animation settle rồi mới phát ba `goDown(1)` tiếp theo.

Timing cụ thể phải chốt bằng log/live evidence; không tự giảm threshold để ép PASS.

## FIX riêng — Bông 27/27 false-negative — Đã xong source

Ảnh lỗi live cho thấy gesture gieo Bông thực tế đã chạy đủ nhưng hậu kiểm visible regions trả `0/27`, làm phát `ScreenTimeout`. Đây là gate sai vì hàng cây thứ 5 có thể nằm ngoài viewport sau gesture.

Đã đối chiếu với logic gieo Táo ổn định: đường kéo 27 chậu là business action, còn `changed_waypoint_regions` chỉ là diagnostic `non_blocking=true`.

Runtime Bông hiện được sửa theo cùng mô hình:

- Vẫn fail-close nếu thiếu canonical asset `cay_bong`.
- Vẫn phải xác minh seed picker/chậu và nhận diện đúng hạt Bông trước gesture.
- Vẫn dùng nguyên đường 27 chậu: `path = (seed.center,) + self.rose_path()[1:]`.
- Sau gesture vẫn đo `changed_waypoint_regions` để log.
- **Không còn yêu cầu visible `27/27` và không raise chỉ vì `0/27` hoặc thiếu vùng nhìn thấy.**
- Trả kế toán `27` sau khi đường gieo native đã được gửi thành công; lỗi transport/stop/seed vẫn chặn như cũ.

Commit runtime:

`32cfd192325172b2b3fb63a777adb37c2e4211c0` — `fix(auto-multi): make cotton visibility check advisory`

Commit static contract:

`d93551c5ac4374befe8d79628f928661ce5341d7` — `test(auto-multi): align cotton postcheck contract`

Static verifier hiện cấm hồi quy về `if changed != TREE_COUNT` hoặc `fail_close=true` cho hậu kiểm vùng nhìn thấy của Bông.

## FIX transport — CAPTURE3 moving expected frame — Đã xong source, LIVE pending

Live 11:49 ngày 2026-09-08 tái hiện lỗi transport **trong một run không có bằng chứng operator-stop trước lỗi**. PING đã trả đúng revision hiện tại:

`OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP`

Lỗi cuối là `expected=23, actual=12, status=2`. Source `EngineDriver` cũ retry transient stale-header bằng cách gọi lại toàn bộ `_capture_shared_bgra_once()`, nghĩa là mỗi retry lại phát **một CAPTURE mới** và tự tăng `expected_frame`. Cách đó biến một publication lag thành moving target và làm mất bằng chứng về một response cụ thể.

AUTO MULTI DEV nay cài adapter riêng `worker/capture3_same_request.py`:

- Mỗi screenshot chỉ phát **một** lệnh `CAPTURE` cho một `expected_frame` cố định.
- Sau response, reader poll đúng lifetime-fixed mapping tối đa 30 lần x 10 ms cho **cùng expected frame**.
- Không nhận `frame_id < expected_frame`.
- Vẫn kiểm tra `status=2`, KCAP v3, dimensions/stride/pixel format/buffer size và seqlock-style header ổn định trước/sau copy pixels.
- Không thêm HWND fallback, không nới stale-frame rule và không sửa native Bridge trong bước này.
- Worker log thêm `DLL bridge V3: CAPTURE3 same-request wait ENABLED • stale frame vẫn bị từ chối` để xác nhận đúng build đã chạy.

Commit adapter:

`d2db0b4f63678307869456554ecf9bbaeecdd134` — `fix(auto-multi): wait on one capture response`

Commit wiring worker:

`cc13e2a89921b006d9f58e1efdcb0ddbac041be8` — `fix(auto-multi): install same-request capture wait`

**Ý nghĩa live kế tiếp:** nếu lỗi biến mất, moving-target retry là nguyên nhân trực tiếp hoặc thành phần khuếch đại chính. Nếu lỗi vẫn xuất hiện, message mới phải giữ **một expected frame cố định** sau 30 lần đọc; khi đó có bằng chứng mạnh để chuyển sang điều tra native mapping/object identity thay vì tiếp tục tăng retry hoặc chấp nhận stale frame.

## Invariant an toàn

- Không nới CAPTURE3.
- Không chấp nhận stale frame.
- Mỗi gesture startup phải có fresh frame hậu kiểm.
- Không gắn nhãn `main` chỉ dựa vào số lần kéo hoặc `frame_change`.
- Chỉ `is_own_main_screen()` xác nhận được điểm khởi đầu cuối cùng.
- Không đụng ổn định của sale / clear-stall khi đang sửa startup normalization.
- AUTO PRO tiếp tục chỉ là reference, không gọi runtime sang AUTO PRO.
- Không dùng asset cửa hàng thay cho nút xuống tầng.

## Điểm tiếp tục cho cửa sổ kế tiếp

Không làm lại STEP 1 hoặc STEP 2.

Trước STEP 3, **LIVE retest CAPTURE3 same-request wait** vì transport phải ổn định trước khi đánh giá startup navigation. Chạy qua Control Center `[1]`, sau đó `[2]`, và xác nhận log có dòng `CAPTURE3 same-request wait ENABLED`.

Nếu CAPTURE3 ổn định, tiếp tục từ **STEP 3: tầng 3-10 -> `goDown(1)` -> bắt đúng nút xuống tầng trong cửa sổ tồn tại ngắn -> click có template guard -> chờ animation -> 3 x `goDown(1)` -> exact main**.

Trước khi viết click của STEP 3, phải có bằng chứng đúng cho template/tọa độ/timing của nút xuống tầng. Nếu chưa có asset canonical thì ưu tiên recovery/reference hoặc live diagnostic, không đoán.

Khi live retest bản hiện tại, ưu tiên ba checkpoint:

- Log phải có `CAPTURE3 same-request wait ENABLED` ngay sau image bootstrap / protocol setup.
- Startup tầng 1/2 phải có log `AUTO khởi điểm STEP 2` và kết thúc bằng exact main PASS.
- Gieo Bông có thể log `changed_waypoint_regions=0/27`, nhưng không được dừng ở đó; pipeline phải tiếp tục sang điều hướng/sản xuất Vải vàng nếu các gate nghiệp vụ khác hợp lệ.
