# AUTO MULTI DEV — Function Boundary Delay

Cập nhật: 2026-09-11
Branch: `develop/multi-auto-dev`
Trạng thái: **CHỐT / SOURCE IMPLEMENTED — CHỜ LIVE TEST**

## Quy tắc

`function_loop_delay_seconds` là **thời gian boundary tối thiểu giữa hai vòng Function**, không phải một lệnh `sleep` bắt buộc chạy sau Sale.

Luồng chuẩn:

```text
Function N PASS
→ bắt đầu tính boundary time
→ Sale nếu đến hạn
→ Friend Refresh nếu đến hạn
→ maintenance khác nếu có
→ tính elapsed boundary
→ remaining = max(0, configured_delay - elapsed)
→ nếu remaining > 0: chỉ chờ phần còn thiếu
→ nếu remaining == 0: vào Function N+1 ngay
```

Ví dụ cấu hình chờ 60 giây:

```text
Function PASS
→ Sale mất 25 giây
→ chỉ chờ thêm khoảng 35 giây
→ Function tiếp theo
```

Nếu Sale/maintenance mất 70 giây:

```text
Function PASS
→ Sale/maintenance mất 70 giây
→ configured delay = 60 giây đã được đáp ứng
→ KHÔNG chờ thêm
→ Function tiếp theo ngay
```

## Không áp dụng sai

- Initial Sale sau Startup không phải boundary giữa hai Function nên không tạo/chờ loop delay.
- Scheduled ClientJS Restart tại boundary vẫn ưu tiên lifecycle restart; không chờ thêm delay trước restart.
- Builder `sale_after_each_loop` dùng cùng semantics.
- Delay = 0 vẫn chạy Function kế tiếp ngay sau maintenance.
- Stop-check vẫn phải giữ trong phần wait còn lại.

## Source

- `workflows/auto_main/boundary_delay.py`
- `workflows/auto_main/__init__.py`
- `workflows/auto_builder/loop_delay_patch.py`
- `tools/verify_function_boundary_delay_contract.py`

Không gọi runtime PASS cho tới khi operator chạy live và xác nhận log/nhịp thực tế.
