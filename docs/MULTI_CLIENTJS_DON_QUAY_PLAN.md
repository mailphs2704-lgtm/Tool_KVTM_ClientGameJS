# Kế hoạch chức năng Dọn quầy ClientJS

## 1. Phạm vi

Dọn quầy là workflow mới của Multi DEV, không ánh xạ sang Function ID hoặc method của AUTO PRO.

Mục tiêu ban đầu:

- Tài khoản clone không mở ClientJS khi chưa đến lịch.
- Chu kỳ mặc định: 65 phút.
- Đến lịch, Multi mở đúng profile clone.
- Worker tự lấy PID hiện tại từ profile ID, kể cả ClientJS vừa reset.
- Clone tìm tài khoản chính theo số thứ tự trong danh sách bạn bè, đi tới quầy, xử lý vật phẩm theo cấu hình và bán lại.
- Tài khoản chính có thể chạy trên máy khác, LDPlayer hoặc không do Multi DEV quản lý PID.
- Hoàn tất thì lưu mốc chạy kế tiếp và có thể đóng client clone.

AUTO PRO chỉ được dùng làm tài liệu tham khảo về capture, nhận diện ảnh, click/swipe, chờ có điều kiện và phục hồi màn hình. Không ghép workflow này vào bytecode `FarmAutomation`.

### Cơ chế AUTO PRO được tham khảo

Các dấu vết đã xác định trong AUTO PRO:

- Function 170 / `produceItems_170`: **Mua - Bán VP Friend**.
- Function 4 / `produceItems_4`: **Mua VP 8 Ô - Nhà Bạn**.
- Function 5 / `produceItems_5`: **Chuyển VPSK**.
- Method điều hướng: `GoFiendHome`.
- `num_friend_for_bsf`: số thứ tự bạn bè dùng cho luồng mua/bán.
- `buy_sell_friend_kho_id`: kho/quầy được chọn trong luồng mua/bán.
- `go_friend_home`: bật bước đi tới nhà bạn.

Dọn quầy sẽ viết worker mới nhưng tái sử dụng cách điều hướng theo thứ tự bạn bè. Số thứ tự được nhập theo cách người dùng nhìn thấy (dự kiến 1-based); cần trace một lượt Function 170 để chốt phép đổi sang chỉ số nội bộ trước khi viết executor.

## 2. Nguyên tắc an toàn

- Mặc định OFF.
- Không dùng kim cương.
- Không mua hoặc bán nếu chưa xác nhận đúng tài khoản, đúng quầy và đúng vật phẩm.
- Mỗi bước thay đổi trạng thái phải được xác nhận bằng ảnh sau thao tác.
- Không nhận diện chắc chắn thì dừng worker, chụp ảnh chẩn đoán và ghi log.
- Một profile chỉ có tối đa một worker Dọn quầy.
- Lệnh phải có tính lặp an toàn: chạy lại sau lỗi không được mua/bán trùng.
- Không lưu profile đăng nhập trong ZIP đóng gói.

## 3. Kiến trúc dự kiến

```text
Multi UI
  -> ClearStallConfigStore
  -> ClearStallScheduler
  -> ClearStallWorker (mỗi profile clone)
  -> ClientSessionResolver (profile ID -> PID/HWND mới nhất)
  -> Capture/Input adapter hiện có
  -> ScreenDetector + StallExecutor
  -> JSONL log + checkpoint
```

Thư mục dự kiến:

```text
components/clientjs-auto/workflows/clear_stall/
  __init__.py
  config.py
  scheduler.py
  worker.py
  session_resolver.py
  detector.py
  executor.py
  checkpoints.py
  assets/
  tests/
```

## 4. Dữ liệu cấu hình

Mỗi nhiệm vụ cần:

- `job_id`: ID cố định của nhiệm vụ.
- `clone_profile_id`: profile clone thực hiện.
- `target_mode`: mặc định `friend_ordinal`.
- `target_friend_ordinal`: số thứ tự tài khoản chính trong danh sách bạn bè của clone.
- `target_friend_hint`: tên/ảnh/đặc điểm dùng xác nhận sau khi vào nhà; không dùng để click chính.
- `target_stall_id`: kho/quầy đích, tham khảo `buy_sell_friend_kho_id`.
- `main_profile_id`: tùy chọn; chỉ dùng khi acc chính cũng được quản lý bởi Multi, không bắt buộc.
- `interval_minutes`: mặc định 65.
- `next_run_at`: thời điểm chạy kế tiếp.
- `close_client_after_run`: đóng clone sau khi hoàn tất.
- `item_rules`: danh sách vật phẩm, số lượng và giới hạn giá.
- `enabled`: mặc định false.
- `last_checkpoint`: bước cuối đã xác nhận.
- `last_result`: kết quả gần nhất.

Cấu hình được lưu trong `data-dev`, tách khỏi source và được script build cố định bảo toàn.

## 5. Máy trạng thái

1. `WAITING`: chưa tới lịch, client clone không cần mở.
2. `LAUNCHING`: mở clone bằng profile ID.
3. `ATTACHING`: tìm PID/HWND hiện tại và chuẩn hóa kích thước.
4. `ENTERING_GAME`: chờ màn hình chính có xác nhận.
5. `OPENING_FRIEND`: mở danh sách bạn, điều hướng tới `target_friend_ordinal` theo cơ chế tham khảo `GoFiendHome`, sau đó xác nhận đúng nhà.
6. `OPENING_STALL`: xác nhận đúng quầy.
7. `SCANNING_ITEMS`: đọc từng ô hàng và đối chiếu rule.
8. `BUYING`: mua có xác nhận trước/sau.
9. `RETURNING`: quay về tài khoản clone.
10. `RESELLING`: đưa đúng vật phẩm lên quầy theo cấu hình.
11. `VERIFYING`: xác nhận kết quả và ghi checkpoint.
12. `COMPLETED`: tính `next_run_at`, tùy chọn đóng client.
13. `PAUSED/ERROR`: dừng an toàn và giữ bằng chứng chẩn đoán.

## 6. Các pha thực hiện

### Pha 1 — UI và schema

- Hoàn thiện form chọn profile clone và nhập số thứ tự bạn bè của acc chính.
- Acc chính không bắt buộc có profile/PID trong Multi DEV.
- Thêm trường kho/quầy đích và dấu hiệu xác nhận đúng nhà.
- Cấu hình chu kỳ, vật phẩm, số lượng, giá và tùy chọn đóng client.
- Lưu riêng theo job ID.
- Validation không cho một clone chạy hai job đồng thời.

### Pha 2 — Scheduler và PID

- Scheduler không mở client trước lịch.
- Mở đúng profile clone khi tới hạn.
- Resolver tự cập nhật PID/HWND sau reset.
- Pause/stop không làm mất lịch và checkpoint.

### Pha 3 — Detector

- Chuẩn hóa ảnh ClientJS về hệ tọa độ tham chiếu.
- Nhận diện màn hình chính, danh sách bạn, trạng thái phân trang, đúng nhà, quầy, ô vật phẩm và hộp xác nhận.
- Sau khi click theo số thứ tự, bắt buộc xác nhận target bằng `target_friend_hint` trước khi mua.
- Ghi confidence và ảnh lỗi.
- Không thao tác nếu confidence dưới ngưỡng.

### Pha 4 — Executor mua hàng

- Đi tới đúng quầy tài khoản chính.
- Quét ô hàng theo thứ tự ổn định.
- Chỉ mua vật phẩm khớp rule.
- Xác nhận số lượng/tồn kho sau mỗi lần mua.
- Phục hồi được khi popup hoặc mạng chậm.

### Pha 5 — Bán lại

- Quay về clone.
- Mở quầy, chọn đúng vật phẩm và số lượng.
- Đặt giá theo rule.
- Xác nhận item đã xuất hiện trên quầy.
- Chống bán lặp khi worker khởi động lại.

### Pha 6 — Chạy nhiều tài khoản

- Hàng đợi giới hạn số client mở đồng thời.
- Worker, log và checkpoint độc lập.
- UI hiển thị lần chạy tới, bước hiện tại và lỗi từng job.
- Test reset PID giữa từng trạng thái.

## 7. Tiêu chí nghiệm thu bản đầu

- Một clone dọn được quầy acc chính đang chạy trên máy khác hoặc LDPlayer.
- Thứ tự bạn bè được xác định rõ là 1-based ở UI và chuyển đổi đúng sang chỉ số nội bộ.
- Client clone không mở trước thời điểm 65 phút.
- Reset ClientJS giữa phiên vẫn tự bắt PID mới và tiếp tục từ checkpoint an toàn.
- Không chiếm chuột người dùng nếu adapter nền hỗ trợ thao tác tương ứng.
- Không dùng KC.
- Không mua/bán sai vật phẩm trong bộ ảnh kiểm thử.
- Khi nhận diện thất bại, worker dừng và tạo đủ log + ảnh chẩn đoán.
- Chạy lặp lại không tạo giao dịch trùng.

## 8. Trạng thái hiện tại

- Pha 1 đã có form cấu hình thật trong tab Dọn quầy, lưu riêng theo profile clone.
- Các trường đang hoạt động: bật/tắt lịch, thứ tự bạn bè, quầy 1–4, chu kỳ 5–1440 phút và đóng client sau khi hoàn tất.
- Mặc định OFF; chu kỳ mặc định 65 phút; quầy mặc định số 2.
- Schema chuẩn hóa và scheduler trạng thái đã có: lọc job đến hạn, khóa trạng thái đang chạy, ghi hoàn tất/thất bại và tính lịch kế tiếp.
- Scheduler chưa được nối vào vòng lặp Multi và chưa có worker thao tác game; bật lịch hiện chỉ lưu cấu hình an toàn.
- Bước tiếp theo: Pha 2 — nối scheduler vào Multi, resolver profile → PID/HWND, sau đó mới xây detector/worker.
