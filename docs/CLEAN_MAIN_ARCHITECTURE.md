# KVTM Clean Main Architecture

## Quyết định chuẩn

Từ 2026-09-05, hai chức năng Main của dự án là:

1. **AUTO MULTI DEV** — các lớp tự động hóa chung được dựng mới.
2. **Dọn quầy** — workflow mua, thu vàng, treo lại và lịch chạy.

Cả hai dùng chung **một image runtime thường trú trong tiến trình Multi DEV**.
Runtime nạp `PIL/cv2/numpy` đúng một lần trước khi dựng GUI. Tác vụ sau đó chỉ
tạo context Python nhẹ theo tài khoản và truyền `image_runtime_ready=True`;
không tạo process mới chỉ để import lại cùng thư viện.

## Phân lớp bắt buộc

| Lớp | Trách nhiệm |
|---|---|
| Multi DEV | GUI, lịch, hàng chờ, trạng thái và lifecycle |
| Clean Runtime | Một bản thư viện ảnh dùng chung; registry thread/stop-event |
| Task context | `profile_id`, PID hiện tại, work-dir, log và stop-event riêng |
| KVAutomation | Actions/workflows Python sạch |
| Profile resolver | Khớp profile với ClientJS, nhận lại PID sau restart |
| Bridge | Capture/input theo đúng PID; không dùng chuột thật |
| AUTO PRO | Chỉ là nguồn đối chiếu; không phải Main runtime |

## Quy tắc tài nguyên và đồng thời

- Không import lại `cv2/numpy/PIL` cho từng lần bấm hoặc từng tài khoản.
- Mỗi profile chỉ được sở hữu bởi một tác vụ Main tại một thời điểm.
- Dọn quầy cho phép tối đa hai profile độc lập chạy cùng lúc.
- AUTO MULTI DEV và Dọn quầy không được điều khiển cùng một profile.
- Mỗi tác vụ có stop-event riêng; dừng một tài khoản không dừng tài khoản khác.
- Multi đóng thì phát stop cho mọi tác vụ resident trước khi thoát.

## Restart ClientJS

Identity bền vững là `profile_id`, không phải PID. Khi ClientJS restart:

1. resolver đọc profile hiện hành;
2. đối chiếu chính xác game path và launch arguments trong bộ nhớ;
3. nhận PID thay thế đúng profile;
4. reset trạng thái capture;
5. inject/kết nối lại Bridge;
6. workflow tiếp tục từ lớp phục hồi của nó.

Không ghi secret plaintext ra log hoặc ổ đĩa.

## Runtime và build

- `[1]` đồng bộ package native một lần khi build.
- Multi DEV prewarm image runtime trước khi mở GUI.
- Nút AUTO/Dọn quầy không copy thư viện và không cold-load process mới.
- Runtime update vẫn dùng staging; không hot-swap DLL/Python đang được nạp.
- `data-dev`, profile và diagnostics được bảo toàn.

## Trạng thái migration

- Dọn quầy: đã dùng resident runtime.
- AUTO MULTI DEV: đã chuyển nút vào game/đóng popup sang resident runtime.
- `clean_auto_worker.py` chỉ còn là đường CLI/fallback chẩn đoán, không phải
  đường Main của Multi DEV.
- Business logic `.pyc` AUTO PRO không được đưa vào Clean Main.
