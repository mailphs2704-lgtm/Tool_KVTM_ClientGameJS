# AUTO Function cycle lock — 2026-09-18

## Live evidence

Log tài khoản Bé Chanhh chứng minh Function 3 vòng 29 đã hoàn tất thu/gieo
36 Táo lúc 03:22:19. Lỗi `Trà sấy: bảng gieo vẫn mở` thoát ra global
fallback, sau đó cùng vòng chạy lại Step 1 và thu/gieo thêm 36 Táo lúc
03:23:00 trước khi chỉ xếp một lượt 9 Nước táo.

## Contract mới

- `RecoveryManager` sở hữu một `CycleCheckpoint` dùng chung cho toàn bộ Recipe
  trong một Function.
- Function workflow đang chạy được `FunctionModule` giữ nguyên qua global
  recovery; không dựng workflow/checkpoint mới khi retry cùng vòng.
- Mọi cụm cây hiện hành của Function 1, 2 và 3 được khóa ngay sau PASS, tách
  theo loại cây/tầng. Retry vẫn phát lại điều hướng chuẩn nhưng bỏ qua thao tác
  thu/gieo đã hoàn thành.
- Function 3 khóa thêm từng Step 1..6. Step đã PASS chỉ phát lại đường camera
  tới boundary đầu vào của Step kế tiếp.
- Khóa chỉ được xóa khi AUTO Main đã chạy xong Function completion gate. Builder
  cũng commit khóa sau khi lời gọi Function hoàn tất.
- Log replay dùng `AUTO khóa giai đoạn ... đã PASS • bỏ qua thao tác lặp`; không
  ghi lại action trồng/sản xuất của những phase Function 1 đã được replay.

## Phạm vi cây đã khóa

- Function 1: Táo 27 cho Táo sấy; Táo tầng 1-5 và tầng 6; Bông 27.
- Function 2: toàn bộ khóa Function 1 dùng chung; Hồng 30+5 và Tuyết 28 cho
  Tinh dầu hoa hồng.
- Function 3: Táo 30+6; Trà 24; Trà hàng dưới 6/gieo 3; Bông 27; các cụm Hồng
  và Tuyết tại tầng 1/tầng 6 của Step 4, 5 và 6.

## Verification

- `tools/verify_auto_cycle_checkpoint_contract.py`: PASS.
- AUTO Builder, recovery architecture, Recipe/Function standardization,
  production, Function 2 UI và main-boundary targeted static gates: PASS.
- Python compileall và `git diff --check`: PASS.
- Windows build/live: PENDING. Không gọi runtime PASS trước log operator.
