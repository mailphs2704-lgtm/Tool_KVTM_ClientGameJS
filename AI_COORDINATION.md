# KVTM AI Session Coordination

> Tài liệu điều phối bắt buộc cho mọi phiên AI làm việc trên repository này.
> Đọc toàn bộ file trước khi sửa code. Cập nhật trạng thái/handoff trước khi kết thúc một mốc công việc.

## Mục tiêu chung

Xây `KVTM-ClientJS-Suite` gồm Multi, ClientJS Workspace và Auto chạy nền ổn định. Workspace có thể thu nhỏ xuống taskbar mà ClientJS và Auto vẫn tiếp tục chạy. Mọi thao tác thử nghiệm phải chỉ tác động tới client thuộc bộ DEV hiện tại.

Tài liệu chi tiết cho migration máy phụ + runtime updater:

- `docs/SECONDARY_MACHINE_RUNTIME_UPDATE.md`

## Phân nhánh và quyền sở hữu

| Phiên | Nhánh làm việc | Phạm vi sở hữu chính | Không tự ý sửa |
|---|---|---|---|
| AUTO/Multi | `develop/multi-auto-dev` | Logic Auto, workflow Dọn quầy, Multi hiện tại, profile/session, worker/probe, migration máy phụ, runtime updater | `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat` |
| Workspace | `develop/clientjs-workspace` | Workspace host, Live View, attach/detach, capture lifecycle, Control Center Workspace | Logic nghiệp vụ Auto/Dọn quầy đang được phiên AUTO sửa |

Hai phiên không push trực tiếp vào nhánh của nhau. Không force-push, không rebase nhánh đã chia sẻ và không sửa lịch sử Git.

## File dùng chung cần phối hợp trước

Các file sau có khả năng được cả hai phía sử dụng. Phiên muốn sửa phải ghi rõ lý do trong commit và cập nhật mục Handoff:

- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py`
- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py`
- `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1`
- `KVTM_DEV_CONTROL.bat`
- `test-candidates/auto-pro-clientjs-temp/pc_driver.py`
- `test-candidates/auto-pro-clientjs-temp/engine_driver.py`

Ưu tiên mở rộng bằng module mới và interface ổn định thay vì cùng sửa một file lớn.

## Interface giữa Workspace và Auto

Workspace không sở hữu vòng đời Auto. Auto không phụ thuộc việc cửa sổ Workspace đang hiển thị.

- Device identity: `profile_id + PID + HWND`.
- Kích thước logic ClientJS: `1000 x 1000`, DPI mục tiêu `240`.
- Capture chính: OpenGL shared memory theo PID.
- Capture dự phòng: HWND capture.
- Auto input/capture chạy độc lập với Live View.
- Workspace thu nhỏ: dừng hoặc giảm refresh giao diện; không minimize/đóng ClientJS.
- Workspace đóng: mặc định không đóng ClientJS và không dừng Auto.
- Không điều khiển mọi `GameClientJS.exe` trên máy; chỉ nhận client khớp profile DEV.

## Quy trình đồng bộ bắt buộc

1. Đọc file này và xác nhận đúng nhánh trước khi sửa.
2. Kiểm tra working tree; không ghi đè thay đổi chưa commit của người/phiên khác.
3. Mỗi commit chỉ chứa một mục tiêu rõ ràng.
4. Ghi SHA nguồn khi lấy thay đổi từ nhánh bên kia.
5. Dùng `merge --no-commit` hoặc `cherry-pick` có chọn lọc trên nhánh tích hợp; không merge mù toàn nhánh.
6. Nếu cùng cần sửa một file dùng chung, một phiên hoàn tất và commit trước; phiên còn lại lấy commit đó rồi mới tiếp tục.
7. Không coi build thành công là runtime PASS. Chỉ ghi PASS cho hành vi Windows khi có output/live evidence phù hợp.
8. Không upload/commit secret, `.kvtm`, raw `profiles.json`, plaintext launch args, token, cookie hoặc password.

## Trạng thái phiên AUTO/Multi

- Nhánh chính: `develop/multi-auto-dev`.
- Chủ sở hữu cập nhật: phiên AI làm Auto/Multi.
- Trạng thái: `IN_PROGRESS / READY_FOR_NEXT_LIVE_TEST`.
- Migration máy phụ: hoạt động. Main đã export 13 profile; máy phụ đã import. Người dùng mở ít nhất 1 profile và xác nhận vào thẳng game, không đăng nhập lại.
- Máy phụ: Git/Git LFS/Python 3.11 x64/VC++ x86+x64/ZingPlay/GameClientJS/game data đã có diagnostic `ENVIRONMENT_READY` trong các lần kiểm chứng trước.
- GitHub bridge: `[8]` gửi SAFE diagnostic lên branch `machine-sync/cry-pc`; `[9]` pull/deps/LFS/build DEV runtime. Không upload profile/transfer file.
- Runtime updater UI: nút `Cập nhật DEV` đã có trong `BẢNG ĐIỀU KHIỂN`. Người dùng đã xác nhận `giao diện pass` sau bootstrap gần nhất: vị trí nút đúng và chữ tiếng Việt không còn lỗi mojibake.
- Runtime updater code mốc chính: `4806e433591b8623126e11c6e13e6ac1adec5808` (`Make staged runtime activation robust`).
- UI/text fix: `28209c3ab6a53cf90cbb232beecc646928571fa0`.
- PS5.1 branch detection fix: `01690a565c4fcf904d802e1c2d5f359ca3173a2e`.
- CI cho `4806e433...`: FULL PASS.
  - `Multi DEV checks`: `clear-stall-static` PASS, `package-smoke` PASS.
  - `Secondary machine checks`: toàn bộ PowerShell/Python parse, PS5.1 regression, bridge/updater safety, transfer crypto, diagnostic và ignore checks PASS.
- Evidence live gần nhất trước bootstrap cuối: repo source `28209c3`, runtime `01690a5`, updater UI/hook FOUND. Sau đó user chạy `[9]` và báo `pass`, rồi báo `giao diện pass`. Chưa có `[8]` mới sau `giao diện pass`, vì vậy không tự suy đoán runtime SHA hiện tại.
- Known issue đã xử lý: source có thể lên commit mới nhưng runtime vẫn cũ do watcher activation. `4806e433...` làm activation robust hơn và hỗ trợ updater self-update/retry/process tracking.
- **NEXT bắt buộc:** test một vòng update hoàn toàn bằng nút `Cập nhật DEV`, không dùng `[9]`. Có thể dùng commit tài liệu mới nhất làm target harmless. Sau update, đóng/mở Multi, chạy `[8]`, chỉ chốt FULL PASS khi `head == runtime_source_head`, updater UI/hook FOUND, `RESULT=ENVIRONMENT_READY` và profile vẫn hoạt động.
- Nếu `[8]` cho source HEAD mới nhưng `runtime_source_head` cũ: activation là PARTIAL/FAIL; debug staging/status/watcher, không dùng `[9]` như giải pháp lâu dài.
- File chính của luồng này:
  - `tools/KVTM_PROFILE_TRANSFER.ps1`
  - `tools/KVTM_PROFILE_VERIFY.ps1`
  - `tools/KVTM_MACHINE_SETUP.ps1`
  - `tools/KVTM_GITHUB_BRIDGE.ps1`
  - `tools/KVTM_RUNTIME_UPDATE.ps1`
  - `KVTM_MACHINE_TRANSFER_CONTROL.bat`
  - `KVTM_SECONDARY_BOOTSTRAP.ps1`
  - `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`
  - `source-archive/multi-current/kvtm_multi_tool/runtime_update_ui.py`
- DO_NOT_TOUCH cho task updater/migration: `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat`; không thay đổi capture/driver/Dọn quầy nếu không cần cho lỗi updater.

## Quy trình máy phụ nhanh

- `[7]`: verify profile/DPAPI READ-ONLY.
- `[8]`: gửi report an toàn lên GitHub.
- `[9]`: bootstrap/update khẩn cấp; mục tiêu cuối cùng là không cần dùng thường xuyên sau khi updater UI được live-verified.
- Mở DEV runtime: `dist\KVTM-ClientJS-Suite-Multi-DEV\02_START_MULTI_DEV.bat`.
- Khi user nói `đã gửi` sau `[8]`, đọc `machine-sync/cry-pc:machine-reports/CRY-PC/LATEST.txt` trước khi kết luận.

## Trạng thái phiên Workspace

- Nhánh: `develop/clientjs-workspace`
- Nền ban đầu lấy từ AUTO/Multi: `f10d773`
- HEAD trước tài liệu điều phối: `addc02f`
- Đã có:
  - `components/workspace/kvtm_workspace.py`
  - `KVTM_WORKSPACE_CONTROL.bat`
  - `INSTALL_KVTM_WORKSPACE.bat`
  - Workspace worktree riêng tại `Tool_KVTM_Workspace_DEV`.
  - Control Center tự build package nếu `dist` bị thiếu hoặc cũ.
- Đang kiểm thử: Giai đoạn 1, mở Multi + Workspace Live View và thu nhỏ Workspace mà ClientJS/Auto không dừng.
- Chưa bật: click/swipe nền từ Workspace, attach/detach hoàn chỉnh, chế độ host nhiều Device giống video tham chiếu.
- Yêu cầu với phiên AUTO/Multi: khi thay đổi driver/capture/bootstrap, ghi rõ interface và commit SHA tại phần Handoff.

## Handoff log

Thêm bản ghi mới lên đầu bảng. Không sửa hoặc xóa lịch sử cũ.

| Thời gian UTC | Từ phiên | Đến phiên | Commit | Nội dung / hành động cần làm |
|---|---|---|---|---|
| 2026-09-01 | AUTO/Multi | AUTO/Multi phiên kế tiếp | `51c0fed`, `d734f5b`, `1fd34ec` | Đã xác định bằng READ-ONLY bytecode evidence rằng công thức `6 Tinh Dầu Hoa Hồng + 6 Vải Vàng + 8 Táo Sấy` là Function `98` (`produceItems_98`), không phải `97` vì `97` còn sản xuất Nước Hoa Hồng. Đã thêm catalog + worker allowlist + tài liệu. Chưa gọi runtime PASS; NEXT: pull DEV, mở Multi, xác nhận chức năng xuất hiện, chạy live trên đúng clone DEV và gửi log an toàn. |
| 2026-09-01 | AUTO/Multi | AUTO/Multi phiên kế tiếp | `4806e433`, `28209c3`, docs hiện tại | Migration máy phụ + GitHub bridge + runtime updater đã vào DEV. UI vị trí/chữ được user báo PASS. CI `4806e433` FULL PASS. Việc còn lại: live test 1 vòng chỉ bằng nút `Cập nhật DEV`, sau đó `[8]` xác minh `head == runtime_source_head`; không dùng `[9]` để che lỗi activation. Đọc `docs/SECONDARY_MACHINE_RUNTIME_UPDATE.md`. |
| 2026-09-01 | AUTO/Multi | Workspace | `feature/secondary-machine-migration` | Thêm riêng luồng chuyển máy/profile + machine setup. Không sửa `kvtm_multi.py`, capture, driver hoặc Workspace; Workspace không cần merge. |
| 2026-09-01 | AUTO/Multi | Workspace | `cf32eb0`, `70a5cc3` | SAFE Step 1 chỉ thay `ai-don-quay/step1_probe.py` và `KVTM_DON_QUAY_SAFE.bat`. Bổ sung identity fallback qua `running_clients.json` còn mới <=30 giây do Multi DEV publish; không đổi interface capture/driver/bootstrap và Workspace không cần merge. |
| 2026-09-01 | Workspace | AUTO/Multi | `addc02f` | Đã tách nhánh Workspace. Không yêu cầu merge. Xin giữ ổn định interface capture theo PID/HWND và báo SHA khi thay đổi. |
| 2026-09-01 | AUTO/Multi | Workspace | `a5b4310` | HEAD AUTO/Multi được quan sát khi tạo tài liệu; Workspace chưa lấy các thay đổi sau nền `f10d773`. Cần review diff trước khi đồng bộ. |

## Mẫu cập nhật cho mỗi phiên

```text
SESSION: AUTO/Multi | Workspace
BRANCH: tên-nhánh
HEAD: SHA
STATUS: IN_PROGRESS | BLOCKED | READY_FOR_HANDOFF | VERIFIED
FILES_CHANGED: danh sách file
INTERFACE_CHANGED: không | mô tả cụ thể
TEST: lệnh/menu đã chạy và kết quả
NEXT: hành động tiếp theo
DO_NOT_TOUCH: file/phạm vi tạm khóa
```

## Điều kiện tích hợp Workspace

Chỉ đưa thay đổi Workspace về nhánh tích hợp sau khi đạt đủ:

- Multi mở được từ Control Center.
- Workspace nhận đúng client DEV, không nhận client bộ cũ.
- Live View hoạt động ở chế độ một Device và All.
- Thu nhỏ Workspace tối thiểu 5 phút không làm dừng Auto/ClientJS.
- Mở lại Workspace không đen hình, không sai tỷ lệ.
- Không chiếm chuột thật khi Auto chạy.
- Logs không chứa secret, cookie, session hoặc launch arguments đã giải mã.

## Cách tương tác với người dùng cho phiên AI tiếp theo

- Hướng dẫn ngắn, từng bước một.
- Ưu tiên command copy/paste chính xác.
- Không đưa 5-10 bước cùng lúc nếu chỉ cần một bước để lấy evidence tiếp theo.
- PASS/PARTIAL/FAIL chỉ theo log/CI/live evidence thật; không tự điền số liệu chưa thấy.
