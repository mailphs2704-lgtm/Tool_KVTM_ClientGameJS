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

## CURRENT STAGE

```text
Stage 2 — audit direct ROI/custom detector
```

Next exact task:

1. rà `components/clientjs-auto/kvtm_automation` cho direct `cv2.matchTemplate`, frame slicing, ROI pixel;
2. sửa `actions/production.py::_count_matches()` dùng VisionEngine mapping;
3. sửa `runtime/down_floor_button.py` để center trả logical 1000 nếu caller đưa vào `driver.click()`;
4. rà các custom detector khác;
5. commit Stage 2 riêng;
6. cập nhật file checkpoint này sang Stage 3.

## Contract bất biến

```text
source coordinate: logical 1000x1000
production target cuối migration: 500x500
Vision: logical -> frame for matching -> logical result
Driver: logical -> actual input, đúng 1 lần
```

Không đổi Function/Recipe/Recovery/Sale/QC chỉ để đạt 500x500.
