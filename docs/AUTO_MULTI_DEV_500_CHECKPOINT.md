# AUTO MULTI DEV — 500x500 CHECKPOINT

Cập nhật: 2026-09-09

Đây là checkpoint ngắn để AI khác resume migration 500x500 mà không phải đọc lại toàn lịch sử.

## Baseline trước migration

```text
branch: develop/multi-auto-dev
base: 6a4407435a46cf063cdff760c2f48db06e426541
```

Baseline user-confirmed/current: Function 1, Sale/QC, Recipe/Recovery, friend-refresh và ClientJS restart 2h đang ổn. Không sửa business logic trong migration resolution.

## Stage history

### Stage 0 — PLAN/AUDIT — DONE

Commit:

```text
6e7b83817d246c334e660543ca912b0da2d9734a
```

Tạo `docs/AUTO_MULTI_DEV_500_RESOLUTION_PLAN.md`.

Kết luận audit:

- input driver đã dùng logical 1000x1000 và scale sang client thật;
- blocker chính là VisionEngine dùng logical zone như frame pixel;
- clean isolated worker không tự cài adaptive_cv của AUTO PRO;
- direct ROI/custom detector phải audit riêng.

### Stage 1 — VISION CORE — DONE

Commit:

```text
39020e716cc1d4165a31ea86a169f371c7861208
```

File:

```text
components/clientjs-auto/kvtm_automation/runtime/vision.py
```

Đã làm:

- giữ logical reference 1000x1000;
- `logical_zone_to_frame()`;
- `logical_point_to_frame()`;
- `frame_point_to_logical()`;
- `frame_box_to_logical()`;
- template tự scale theo frame/reference trước match;
- `Match.center`/`Match.box` public luôn trở lại logical;
- `click=True` đưa logical center cho driver, tránh double-scale;
- trace ghi logical zone + actual frame ROI + frame scale.

1000x1000 giữ scale=1 nên behavior hình học cũ được bảo toàn.

### Stage 2 — DIRECT ROI / CUSTOM DETECTOR — DONE

Commits:

```text
469fb46ff161cc186fbc346981edebf448556b34  XUỐNG logical result
f06e53167fe319af95271ac3c285c5ab52fbb30d  production repeated-slot scaling
```

Đã làm:

- `runtime/down_floor_button.py` vẫn match trên frame thật và vẫn dùng ROI tỷ lệ;
- 500x500 dùng base template scale 0.50;
- detector đổi frame center/box trở lại logical 1000 trước khi caller nhận;
- `driver.click(*match.center)` vì vậy không double-scale ở 500;
- `actions/production.py::_count_matches()` không còn crop logical zone trực tiếp;
- logical production zone được đổi qua `VisionEngine.logical_zone_to_frame()`;
- template `o_trong` được resize theo frame scale;
- tâm các slot được đổi lại logical trước de-duplicate;
- `MIN_DISTANCE=34` tiếp tục mang nghĩa logical, không bị thành 34 pixel thật ở client 500.

Các path production dùng `VisionEngine.find()` như `full_kho`, product anchor, material error tự hưởng Stage 1.

## CURRENT STAGE

```text
Stage 3 — static contract + build gate cho adaptive resolution
```

Next exact task:

1. tạo `tools/verify_resolution_adaptive_contract.py`;
2. verifier khóa driver reference 1000, VisionEngine transform, production repeated-slot transform và XUỐNG logical center;
3. verifier scan các module clean để cảnh báo direct `cv2.matchTemplate` ngoài các path đã audit;
4. wire verifier vào `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1` và bản PS51 nếu build [1] có dùng;
5. commit Stage 3 riêng;
6. cập nhật checkpoint sang Stage 4;
7. Stage 4 mới được đụng launch/resize actual ClientJS 500x500.

## Contract bất biến

```text
source coordinate: logical 1000x1000
production target cuối migration: 500x500
Vision: logical -> frame for matching -> logical result
Driver: logical -> actual input, đúng 1 lần
```

Không đổi Function/Recipe/Recovery/Sale/QC chỉ để đạt 500x500.
