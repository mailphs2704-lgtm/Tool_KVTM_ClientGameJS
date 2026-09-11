# AUTO MULTI DEV — LATEST HANDOFF

Cập nhật: 2026-09-11
Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
Branch bắt buộc: `develop/multi-auto-dev`
Trạng thái phiên: **INCREMENTAL IMPLEMENTATION / STANDARDIZATION**

> Đây là handoff hiện hành cho AUTO KVTM MULTI DEV. Operator không còn yêu cầu phải mô tả trọn Function hoặc nói `kết thúc` trước khi triển khai. Từ bây giờ AI được phép triển khai từng đoạn ngay khi operator mô tả phần cần thực hiện; các điểm bắt lỗi sẽ được operator chỉ ra trong quá trình làm và AI phải tự phân loại sang đúng nhánh Recovery.

## 1. Read-first bắt buộc

Đọc theo thứ tự:

1. `docs/AUTO_MULTI_DEV_STANDARDIZATION_LATEST.md` — kiến trúc tổng thể và các quyết định tích lũy;
2. `docs/AUTO_MULTI_DEV_CONFIRMED_FLOW_LATEST.md` — contract mới nhất đã chốt cho Startup/Popup, Sale VP và Navigation goUp; **file này override wording cũ nếu có xung đột ở ba phần đó**;
3. `docs/AUTO_MULTI_DEV_ACTIONS_STANDARDIZATION.md` — contract Actions dùng chung;
4. `docs/AUTO_MULTI_DEV_FUNCTION_RECOVERY_MAPPING.md` — phương pháp triển khai từng đoạn + phân loại Function/Module/Action/Recovery;
5. `docs/AUTO_MULTI_DEV_GLOBAL_RECOVERY_CHECKPOINTS.md`;
6. `docs/AUTO_MULTI_DEV_RECOVERY_ARCHITECTURE.md`;
7. `docs/AUTO_MULTI_DEV_CLIENT_RESTART.md` — lưu ý implementation cũ vẫn là 2h;
8. `docs/AUTO_MULTI_DEV_FRIEND_REFRESH.md`;
9. `AI_COORDINATION.md`.

Nếu tài liệu cũ xung đột với quyết định mới, dùng tài liệu có wording mới hơn và nhãn `CHỐT / CẦN CHỐT / READY FOR LIVE TEST`.

## 2. Giai đoạn hiện tại — CHỐT MỚI NHẤT

Operator sẽ mô tả Function **trong lúc thực hiện**, không cần hoàn tất tài liệu flow trước.

AI phải:

- không yêu cầu operator biết Python/class/file;
- nhận từng đoạn nghiệp vụ và phân loại Action / Module-Recipe / Function orchestration;
- triển khai phần operator đang yêu cầu theo kiến trúc đã chốt;
- khi operator nói một điểm là điểm bắt lỗi, tự phân loại sang specialized recovery / local retry / unknown escalation / fail-close;
- xác định checkpoint và nơi resume cho nhánh lỗi;
- không copy recovery riêng vào từng Function nếu có thể dùng global recovery;
- cập nhật tài liệu khi một contract mới được xác nhận;
- không tự gọi runtime PASS nếu chưa có live evidence.

### Workflow mới

```text
operator mô tả đoạn hiện tại
→ AI phân nhóm + triển khai
→ operator test/mô tả tiếp
→ nếu có điểm bắt lỗi
   → AI tách Recovery
   → giữ checkpoint/resume đúng việc đang dở
→ tiếp tục đoạn kế
```

Không còn quy tắc cũ `chưa code cho tới khi operator nói kết thúc`.

## 3. Kiến trúc đã chốt

```text
AUTO MAIN / SCHEDULER
        ↓
FUNCTION
        ↓
MODULE / RECIPE
        ↓
ACTION

        ↕
GLOBAL RECOVERY / ERROR MANAGER
        ↕
ACTIVE CHECKPOINT (RAM, metadata-only)
```

Nguyên tắc:

```text
Recovery != Function completion
Recovery = interrupt -> recover -> resume same work
```

Mỗi profile chỉ giữ một ActiveCheckpoint nhỏ, update tại chỗ; không giữ frame/image/numpy/template/driver/log history nặng trong checkpoint.

## 4. Startup / Login / Popup — CHỐT MỚI NHẤT

Sau ClientJS open/restart:

```text
login game thành công
→ camera mặc định ở MAIN
→ bắt đầu timer 60 giây
→ TRONG SUỐT 60 GIÂY liên tục check popup
→ popup nào xuất hiện thì đóng ngay
→ tiếp tục scan
→ đủ 60 giây thì dừng popup check
→ giữ nguyên camera MAIN
```

Không dùng `goDown(1)` chỉ để exact-main sau login/restart. Đây là contract mới nhất và thay wording cũ kiểu chờ đủ 60 giây rồi mới popup sweep.

## 5. Sale VP trước vòng Function — CHỐT MỚI NHẤT

Mở quầy và check View 1 gồm 8 ô đầu mặc định.

Trong mỗi View:

```text
ô vàng?
  Có → thu vàng → check QC
  Không → check QC
        ↓
tìm ô trống
```

Nếu có ô trống:

```text
click ô trống
→ mở Kho
→ chọn Kho 2 / kho thành phẩm
→ quét VP được Function cho phép
→ chọn VP
→ check SL >= 10
   Có → đăng x10 → tiếp tục lấp ô trống khác
   Không → thử VP hợp lệ khác
```

Nếu không còn VP hợp lệ đủ 10:

```text
đóng Kho
→ đóng Quầy
→ check chức năng tùy chọn
→ nếu không có thì bắt đầu vòng Function mới
```

Nếu View hiện tại không có ô trống:

```text
swipe 2 nhịp
→ View tiếp theo
→ chạy lại scan vàng/QC/ô trống/sale
```

Tổng cộng 5 View. View 5 là final/end check. `swipe 2 nhịp` phải là Action dùng chung, Function không tự gửi hai swipe rời.

Sale kết thúc khi không còn VP hợp lệ đủ 10 hoặc đã quét đủ 5 View mà không còn ô trống dùng được.

## 6. Navigation Actions / goUp — CHỐT

`goUp(n)` là mode hành động, không phải mặc định `n` lần swipe.

```text
goUp(1)
= swipe ngắn lên 1 tầng
= reference hiện tại khoảng (514,214) → (514,314)

goUp(2)
= click anchor/chậu đầu tiên tầng 4
= ví dụ đang tầng 1 thì camera nhảy lên tầng 3
= KHÔNG được thay bằng goUp(1) hai lần
= tọa độ anchor chính xác chưa khóa

goUp(4)
= swipe dài 4 tầng
= nếu đang tầng 1 thì lên tầng 5
= reference hiện tại (387,69) → (387,918)
= một gesture riêng, không phải 4 lần goUp(1)

goUp(3)
= CHƯA ĐỊNH NGHĨA
= không tự suy đoán
```

Navigation Action chỉ cập nhật state/floor candidate sau khi thao tác thành công/đủ evidence. Nếu lỗi thì Recovery giữ checkpoint cũ.

## 7. Actions architecture — CHỐT HƯỚNG

`actions/` chứa toàn bộ khả năng thao tác tái sử dụng: click, swipe, nhận diện, mở/đóng panel, navigation, trồng/thu hoạch theo path/count, kho, stall, sale, production, repair...

Function không chứa tọa độ/gesture/vision trực tiếp nếu Action tương ứng đã tồn tại.

Ví dụ trồng 28 Tuyết không được làm `plant_27 + tự bù cây thứ 28` trong Function. Geometry/count nằm trong Action/path engine, còn Function/Recipe chỉ truyền crop + target/path cần thiết.

## 8. Recovery/checkpoint hiện tại

Source checkpoint trước giai đoạn chuẩn hóa đã có commit:

`b52befd4dbfab5c3a17175f1ddd43948244dcf32`

Lifecycle source:

- `MODULE_STARTED`;
- `MODULE_INTERRUPTED`;
- `MODULE_RESUMED`;
- `MODULE_COMPLETED`.

Trạng thái: **READY FOR LIVE TEST**, chưa được tự gọi runtime PASS.

Recovery escalation mục tiêu hiện tại:

```text
specialized recovery nếu có
→ local retry có giới hạn
→ Friend Refresh #1
→ resume checkpoint + retry
→ Friend Refresh #2
→ resume checkpoint + retry
→ recovery restart nếu policy được chốt
→ fail-close nếu vượt giới hạn
```

Retry limit cụ thể theo từng loại lỗi và Emergency Restart giữa Function vẫn là phần cần chốt khi operator mô tả tới các nhánh lỗi tương ứng.

## 9. Maintenance đã thống nhất

- Periodic Friend Refresh và Recovery Friend Refresh là hai counter/luồng độc lập.
- Target scheduled ClientJS restart mới là **3 giờ**.
- Scheduled restart chỉ ở Function safe boundary.
- Source/runtime cũ vẫn là 2h cho tới khi phần liên quan được refactor và live-test.
- Emergency/Recovery Restart giữa Function chưa được tự coi là CHỐT; nếu cho phép thì cần durable checkpoint sống qua restart.

## 10. Trạng thái source vs thiết kế

Từ workflow mới:

- tài liệu mới vẫn là contract kiến trúc;
- source cũ có thể khác;
- khi operator yêu cầu thực hiện một đoạn, được phép refactor source phần đó theo contract mới;
- không cần chờ toàn bộ Function hoàn thiện;
- không tự gọi source mới là runtime PASS trước live evidence;
- build/static PASS không thay live evidence.

## 11. Điểm tiếp theo

Operator đã xác nhận Startup + Sale trước vòng Function và bộ semantics `goUp(1) / goUp(2) / goUp(4)`.

Từ lượt tiếp theo:

1. nhận đúng đoạn Function/operator muốn làm hiện tại;
2. phân loại Action / Module / Function;
3. triển khai phần đó nếu operator đang yêu cầu thực hiện;
4. nếu operator đánh dấu điểm bắt lỗi, phân loại và nối Recovery/checkpoint phù hợp;
5. không bắt operator mô tả hết Function;
6. cập nhật tài liệu khi contract được chốt.
