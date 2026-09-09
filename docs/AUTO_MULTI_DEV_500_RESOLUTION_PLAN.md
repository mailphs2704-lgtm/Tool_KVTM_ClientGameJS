# AUTO MULTI DEV — 500x500 RESOLUTION MIGRATION

Cập nhật: 2026-09-09

## Mục tiêu

Chuẩn hóa AUTO MULTI DEV để **ClientJS production chạy 500x500**, nhưng **source AUTO vẫn dùng hệ tọa độ logic 1000x1000**.

Không chuyển hàng loạt tọa độ business sang 500. Không tạo một bộ Function/Recipe riêng cho 500. Mục tiêu kiến trúc là:

```text
Function / Recipe / Action
        |
        | logical 1000x1000
        v
Runtime coordinate + vision adapter
        |
        v
ClientJS thực tế 1000 / 800 / 600 / 500 ...
```

500x500 là kích thước production mục tiêu hiện tại. 1000x1000 phải tiếp tục tương thích để rollback/diagnostic.

## Vì sao không đổi tọa độ bằng tay

Driver hiện đã nhận `reference_size=(1000, 1000)` và tự scale click/touch sang client thật. Vì vậy các điểm như `(257,191)` phải tiếp tục được lưu dưới dạng logical 1000.

Điểm còn thiếu chủ yếu nằm ở vision: nhiều `zone=(x,y,w,h)` hiện đang bị dùng như pixel của frame thật. Trên frame 500x500, zone logical `(420,550,170,120)` sẽ nằm ngoài ảnh nếu không được scale.

## Hợp đồng coordinate mới

### Input/click

- Action/Workflow/Recipe ghi tọa độ logical 1000x1000.
- Driver là nơi cuối cùng đổi logical -> client pixel.
- Không pre-scale điểm click rồi đưa lại cho driver, vì sẽ bị scale hai lần.

### Vision ROI

- `VisionEngine` nhận `zone` theo logical 1000x1000.
- Trước crop: logical zone -> frame-pixel zone.
- Template 1000-reference được scale theo kích thước frame trước `matchTemplate`.
- Kết quả match phải đổi frame-pixel center/box -> logical 1000 trước khi trả về.
- `click=True` luôn click logical center qua driver.

### Custom detector

Detector tự crop/match ngoài `VisionEngine` phải tuân cùng contract. Không được trả frame-pixel center rồi gọi `driver.click()` trực tiếp.

## Chia nhỏ công việc / checkpoint

Mỗi stage phải là commit nhỏ độc lập. Sau mỗi stage cập nhật phần `CHECKPOINT` ở cuối tài liệu này để AI khác có thể tiếp tục mà không cần dựng lại lịch sử.

### Stage 0 — tài liệu và audit contract

Trạng thái: **IN PROGRESS / docs-first**

- ghi mục tiêu 500x500 + logical 1000;
- xác nhận driver đã scale input;
- xác nhận `VisionEngine` hiện chưa scale logical ROI;
- xác nhận clean image bootstrap không tự cài `adaptive_cv.install_adaptive_matching()`;
- xác định direct OpenCV/custom detector cần audit.

Không thay behavior runtime ở stage này.

### Stage 1 — VisionEngine logical/frame transform

Trạng thái: **PENDING**

File chính:

```text
components/clientjs-auto/kvtm_automation/runtime/vision.py
```

Yêu cầu:

- reference logical size mặc định 1000x1000;
- helper logical zone -> frame zone;
- helper frame point/box -> logical;
- scale template theo frame/reference;
- returned `Match.center` và `Match.box` vẫn là logical;
- log có cả logical zone + actual frame ROI + frame size;
- 1000x1000 cho kết quả tương đương behavior cũ.

### Stage 2 — direct ROI/custom detector audit

Trạng thái: **PENDING**

Rà các code bypass `VisionEngine`, đặc biệt:

- production `_count_matches()`;
- detector `XUỐNG`;
- direct `frame[y0:y1, x0:x1]`;
- direct `cv2.matchTemplate`;
- nơi dùng `match.center` để click.

Mọi center dùng để click phải ở logical 1000.

### Stage 3 — static contract 500/adaptive

Trạng thái: **PENDING**

Thêm:

```text
tools/verify_resolution_adaptive_contract.py
```

Và wire vào build package.

Contract phải khóa tối thiểu:

- driver reference = 1000x1000;
- VisionEngine logical ROI scaling;
- template frame scaling;
- frame result -> logical result;
- production không crop logical zone trực tiếp;
- XUỐNG 500-safe + logical click center;
- production target = 500x500 ở stage launch;
- không regression 1000x1000.

### Stage 4 — launch/resize ClientJS production 500x500

Trạng thái: **PENDING**

Chỉ thực hiện sau khi vision contract xong.

Cần audit chính xác launcher của Multi DEV và restart path. Sau đó đặt một canonical production client size `(500,500)` sao cho:

- start bình thường -> client area 500x500;
- periodic restart -> client mới vẫn 500x500;
- không đổi logical `reference_size=(1000,1000)`;
- không resize account khác;
- không tạo race với worker/Bridge V3 attach.

### Stage 5 — live smoke và promote

Trạng thái: **PENDING**

Operator chạy `[1]`, sau đó live-test:

1. startup/capture xác nhận frame/client gần đúng 500x500;
2. exact-main;
3. Sale + QC;
4. Function 1;
5. Táo sấy;
6. direct Nước táo + panel probe;
7. Vải vàng + corrected floor route;
8. full_kho nếu có thể chủ động tạo case;
9. friend refresh nếu bật;
10. relaunch path phải giữ 500x500 (không cần đổi timer 2h chỉ để test resolution nếu không có lý do).

Chỉ khi smoke PASS mới ghi `500x500 LIVE PASS` vào handoff.

## Vùng ổn định không được sửa trong migration nếu không có evidence

- business Function 1;
- Recipe dependency;
- Recovery policy;
- Sale/QC logic;
- Dọn quầy business;
- 2h safe ClientJS restart scheduler;
- persistent settings;
- Bridge V3 protocol;
- cleanup/packaging relocation.

Migration resolution chỉ thay **coordinate/vision/launch-size infrastructure**.

## Risk chính

1. **Double scale click**: match center là frame pixel nhưng driver lại scale lần nữa. Giải pháp: mọi public match center trả logical.
2. **Double scale template**: clean worker không được dựa mù vào AUTO PRO `adaptive_cv`; VisionEngine phải sở hữu scale rõ ràng.
3. **Direct ROI bypass**: code tự slice frame bằng logical zone sẽ fail ở 500.
4. **Template quá nhỏ**: 500 còn 50% pixel. Chỉ thêm template/đổi threshold khi live evidence chứng minh cần; không thay toàn library trước.
5. **Restart đổi lại size**: periodic relaunch phải áp lại production 500 trước worker mới chạy business.

## CHECKPOINT — AI khác đọc đầu tiên

Base trước migration:

```text
branch: develop/multi-auto-dev
base HEAD: 6a4407435a46cf063cdff760c2f48db06e426541
baseline: Function1/Sale/QC/Recovery/Recipe/FriendRefresh/ClientRestart2h đang PASS/current
```

Current stage:

```text
Stage 0 — docs/audit
```

Đã xác nhận:

- Driver dùng logical `reference_size=(1000,1000)` và `_xy()` scale sang client thật.
- `VisionEngine.find()` hiện crop `zone` trực tiếp theo frame pixel và trả frame-pixel center; đây là blocker chính cho 500.
- Clean `shared_runtime/image_runtime.py` chỉ preload PIL/cv2/numpy, không cài `adaptive_cv.install_adaptive_matching()`.
- AUTO PRO launcher cũ có adaptive_cv riêng, nhưng clean isolated worker không được phụ thuộc implicit vào launcher đó.
- `down_floor_button.py` đã scale template tới 0.50 cho 500, nhưng return center cần được kiểm tra theo logical-click contract.

Next exact task nếu phiên bị ngắt:

```text
Implement Stage 1 in runtime/vision.py only (plus checkpoint doc update),
commit small, then proceed Stage 2.
```

Không bắt đầu cleanup repo trong migration này.
