# AUTO MULTI DEV — CAPTURE3 WRITERMAP2 handoff

## Live evidence dẫn đến root fix

Run 2026-09-08 lúc khoảng 12:56 đã chạy đúng revision `CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP` và adapter same-request. Lỗi không còn là moving expected frame. Một request cố định trả:

- expected frame: `3`
- pipe response: `807x807`, stride `3228`
- shared mapping cùng frame id: `1536x807`, stride `6144`
- shared status: completed (`2`)

Hai bộ kích thước đều tự nhất quán nhưng không thể cùng được sinh ra bởi một lần `dispatch_capture()` duy nhất, vì writer hiện tại lấy width/height một lần, ghi header và trả cùng local values. Đây là bằng chứng identity split giữa pipe response và mapping PID-only, hoặc một writer/generation khác đang sở hữu object mà reader mở.

Adapter same-request trước đó đã làm đúng nhiệm vụ: không che lỗi bằng cách tăng expected frame. Vì vậy không tăng retry, không nhận stale frame và không bật HWND fallback.

## Root fix WRITERMAP2

### Native Bridge V3

`bridge-v3/native/kvtm_bridge_v3.cpp` nay có hai contract capture:

- `CAPTURE`: compatibility cũ, mapping PID-only `Local\\KVTM-CaptureV3-{pid}`. AUTO MULTI DEV không dùng đường này.
- `CAPTUREW`: đường bắt buộc của AUTO MULTI DEV.

Mỗi DLL writer tạo một `writer_id` 64-bit khi attach. `CAPTUREW` ghi vào mapping riêng:

`Local\\KVTM-CaptureV3-{pid}-{writer_id}`

Response:

`OK FRAMEW <frame> <width> <height> <stride> <writer_id>`

Pipe chỉ trả FRAMEW PASS nếu `writer_id` mà window-proc thực sự ghi vào `CaptureCommand` trùng writer đang sở hữu pipe. Nếu một window-proc/writer khác xử lý message, native trả `ERR WRITER ...` thay vì ghép response của writer này với mapping writer khác.

Native còn khóa duplicate owner bằng named mutex theo PID và tạo pipe với `FILE_FLAG_FIRST_PIPE_INSTANCE`.

PING revision mới:

`OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2 <writer_id>`

## Multi Dev reader

`components/clientjs-auto/worker/capture3_same_request.py` nay:

1. Gửi đúng một `CAPTUREW`.
2. Yêu cầu response `OK FRAMEW ... writer_id`.
3. Validate writer id là 16 hex chars.
4. Chỉ mở mapping `Local\\KVTM-CaptureV3-{pid}-{writer_id}`.
5. Chỉ nhận `frame_id == expected_frame` của request đó.
6. `frame_id < expected` tiếp tục bounded poll; `frame_id > expected` là identity/concurrency violation và fail-close.
7. Vẫn bắt buộc `status=2`, KCAP v3, stride/buffer hợp lệ và header ổn định trước/sau pixel copy.
8. Không phát request khác khi chờ, không đổi writer, không stale-frame acceptance, không HWND fallback.

Worker/factory bắt buộc capability `CAPTURE3_WRITERMAP2`, nên ClientJS resident DLL cũ phải bị từ chối chứ không được dùng lẫn với source mới.

## Compatibility

Không sửa business logic AUTO PRO. Native vẫn giữ command `CAPTURE` PID-only cũ cho packaged consumer khác; chỉ AUTO MULTI DEV chuyển sang `CAPTUREW` writer-bound.

Dọn quầy, sale, profile và Workspace business behavior không bị thay đổi trong root fix này.

## Commits của root fix

- `ebea9b72913f9dbd4c75fd32cf2fed3e703a4ba9` — Multi Dev reader dùng CAPTUREW + writer-specific mapping.
- `dfd7693707ed78c1d62ec40b39495cb0b88c4f10` — worker yêu cầu revision WRITERMAP2.
- `b692ca85f0e7cb45a40d95f2309d4cfa53e207d4` — factory capability gate WRITERMAP2.
- `8ef6bb69e01fead42e1837f3ed3b3546edc53d93` — native writer generation, CAPTUREW, owner mutex, first pipe instance.
- `8c565366442d57712a0ab7f5e8e688f12ebd4c16` — static verifier khóa root contract.
- `3972a21b79d88c551e3674b4bd03cd828b4940a4` — cập nhật AGENTS transport rule.

## LIVE chưa PASS

Source/static contract mới chưa phải live PASS. User phải dùng Control Center `[1]` để pull + build native DLL/runtime. Sau build PASS dùng `[2]` và mở một ClientJS mới nếu resident DLL cũ bị revision gate từ chối.

Checkpoint live bắt buộc:

1. Log có `CAPTURE3 WRITERMAP2 ENABLED`.
2. PING có `CAPTURE3_WRITERMAP2` và writer id 16 hex.
3. Không còn lỗi kiểu cùng frame id nhưng response `807x807` / shared `1536x807` từ PID-only mapping.
4. Nếu capture vẫn fail, error phải chứa writer id và phân loại rõ: writer mismatch, exact-frame mismatch, mapping-open failure hoặc same-writer dimension mismatch. Không chữa bằng tăng retry.

Sau khi transport live ổn mới quay lại đánh giá route post-juice -> Bông -> Vải vàng.
